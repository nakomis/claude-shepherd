# Shepherd AWS Serverless Pipeline

## Overview

The Shepherd pipeline runs drone LLM jobs (generate → compile → review → merge) as a serverless
Step Functions workflow on AWS. There is no always-on compute. Model providers are a Lambda
implementation detail — the state machine is model-unaware.

This document supersedes the previous local in-process architecture (server.py background threads,
in-memory JobStore). The MCP tool interface (`drone_generate`, `drone_status`, etc.) is preserved;
only the internals change.

## Design principles

**Provider-agnostic state machine.** Each Step Functions task invokes a Lambda. The Lambda decides
how to route to a model (Together.ai, Ollama via SQS, Bedrock, or any future provider). Swapping
providers requires only an SSM parameter change — no state machine changes.

**Normalisation layer per provider.** Each provider has a translator that converts between the
canonical Shepherd spec/result format and the model-specific prompt/output format. Adding a provider
means writing a translator, not touching the pipeline.

**GitHub CI as compile gate.** Generated code is pushed to a branch and a dedicated
`workflow_dispatch` CI workflow is triggered. The same checks that run on human-written code
(pyflakes, pytest) run on drone output. Stronger guarantee than a bespoke Lambda toolchain.

**S3 for generated artefacts.** Lambdas cannot write to a shared local filesystem. Generated file
contents are stored in S3 at `{job_id}/` and read by the MCP server via the AWS SDK.

## Architecture

```
Claude → shepherd-mcp (thin AWS client)
              │  POST /jobs
              ▼
         API Gateway (REST)
              │
              ▼
    Lambda: submit-job
         │  StartExecution
         ▼
    Step Functions: shepherd-pipeline
         │
         ├── State: Generate
         │     └── Lambda: generate
         │           normalisation layer → Together.ai / Bedrock / (Ollama via SQS — Path B)
         │           writes generated files to S3
         │
         ├── State: CompileGate
         │     └── Lambda: compile-gate
         │           pushes branch to GitHub
         │           triggers compile-check.yml (workflow_dispatch)
         │           polls GitHub API until run completes
         │           returns { compile_passed: bool, output: string }
         │
         ├── State: Review
         │     └── Lambda: review
         │           normalisation layer → reviewer model
         │           returns { approved: bool, review_notes: string, feedback?: string }
         │
         ├── Choice: ReviewChoice
         │     ├── approved == true       → Merge
         │     ├── correction_rounds >= 3 → Escalate
         │     └── otherwise             → Generate (loop with feedback)
         │
         ├── State: Merge
         │     └── Lambda: merge
         │           calls GitHub API to merge the generated branch
         │
         └── State: Escalate
               └── Lambda: escalate
                     publishes to SNS shepherd-escalations topic

Job state: DynamoDB table shepherd-jobs
Artefacts: S3 bucket shepherd-artifacts/{job_id}/
```

## Model routing

Provider selection is via SSM parameters:

| Parameter | Default | Description |
|---|---|---|
| `/shepherd/generate/model` | `together/Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8` | Generation model |
| `/shepherd/review/model` | `together/Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8` | Review model |

Candidate models to evaluate (update SSM params to switch — no code changes needed):
- `together/Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8` — default; large Qwen3 Coder via Together.ai
- `together/deepseek-ai/DeepSeek-V4-Pro` — DeepSeek V4 Pro; strong at code generation, worth benchmarking against Qwen3-Coder
| `/shepherd/github/token` | — | GitHub PAT (write:repo, workflow scopes) |

### Path A — Together.ai (default)
Lambda calls Together.ai directly via the normalisation layer. Always available.

### Path B — Ollama on M5 Mac (optional, free)
Lambda posts job + Step Functions task token to the `shepherd-ollama-queue` SQS queue.
The M5 worker picks up the message, runs Ollama locally, and posts the result back via
`SendTaskSuccess`. Fallback on SQS visibility timeout: Lambda retries via Path A.

### Path C — Bedrock, future providers
Same Lambda interface and canonical format. Translator handles provider specifics.

## Normalisation layer

Implemented in SHEP-34. Each provider has a translator:

```
Canonical spec (in)
      ↓
[Translator: spec → model-specific prompt]
      ↓
Model call
      ↓
[Translator: model output → canonical result]
      ↓
Canonical result (out) → Step Functions
```

Translators handle: prompt structure, system/user message format, structured output enforcement
(JSON mode, schema injection, retry-on-malformed), model-specific prefixes/suffixes
(`/no_think` for Qwen3), and output extraction.

## Compile gate design

A dedicated GitHub Actions workflow (`.github/workflows/compile-check.yml`) is triggered via
`workflow_dispatch` with input `branch_name`. It runs the same checks as the main CI.

The `compile-gate` Lambda:
1. Pushes the generated branch to GitHub
2. `POST /repos/{owner}/{repo}/actions/workflows/compile-check.yml/dispatches`
3. Polls `GET /repos/{owner}/{repo}/actions/runs?branch={branch}` until the run reaches
   a terminal state (`completed`, `cancelled`, `failure`)
4. Returns `{ compile_passed: bool, output: string }` to Step Functions

## Batch jobs (Map state)

Submitting an epic or a list of stories fans out concurrent Step Functions executions via an
inline Map state. Each story gets its own execution. Results are collected and returned together.
Implemented in a later story.

## Job state schema (DynamoDB)

| Attribute | Type | Notes |
|---|---|---|
| `job_id` | String (PK) | UUID |
| `status` | String | pending / generating / compiling / reviewing / merged / failed / escalated |
| `spec` | String | Original spec text |
| `model` | String | Model string passed at submission |
| `project_path` | String | Git repo root on the calling machine |
| `branch` | String | Generated branch name (set after generate) |
| `result` | Map | Final result from merge or escalate |
| `failure_reason` | String | Set on failure/escalation |
| `correction_rounds` | Number | Incremented on each generate→review loop |
| `prompt_tokens` | Number | Cumulative across all rounds |
| `completion_tokens` | Number | Cumulative across all rounds |
| `created_at` | String | ISO 8601 |
| `updated_at` | String | ISO 8601 |

## shepherd-mcp changes

The MCP server becomes a thin AWS client. Tool signatures are preserved.

| Tool | New behaviour |
|---|---|
| `drone_generate` | POST /jobs → returns execution ARN as job_id |
| `drone_status` | GET /jobs/{job_id} → reads DynamoDB status |
| `drone_wait` | Polls DynamoDB until terminal state |
| `drone_result` | GET /jobs/{job_id} → full DynamoDB item |
| `drone_files` | Reads S3 at {job_id}/ |
| `drone_approve` | POST /jobs/{job_id}/approve → triggers merge Lambda |
| `drone_reject` | POST /jobs/{job_id}/reject → restarts execution with feedback |

Deleted from shepherd-mcp:
- `jobs.py` — in-memory JobStore
- `worktree.py` — local git worktree management
- `compile.py` — local pyflakes gate
- Background threading logic in `server.py`

Added:
- `aws_client.py` — boto3/requests wrapper for DynamoDB, S3, API Gateway calls
- `boto3` dependency in `pyproject.toml`

## Infrastructure (CDK)

Stack: `ShepherdPipelineStack` in `infra/lib/shepherd-pipeline-stack.ts`

| Resource | Type | Name |
|---|---|---|
| DynamoDB | Table | `shepherd-jobs` |
| S3 | Bucket | auto-named (surfaced via CfnOutput) |
| SQS | Queue | `shepherd-ollama-queue` |
| SQS | Queue (DLQ) | `shepherd-ollama-dlq` |
| SNS | Topic | `shepherd-escalations` |
| Lambda | Function × 6 | `shepherd-{submit-job,generate,compile-gate,review,merge,escalate}` |
| Step Functions | StateMachine | `shepherd-pipeline` |
| API Gateway | RestApi | `shepherd-api` |

## Cost estimate (hobby scale)

| Service | Est. monthly cost |
|---|---|
| Step Functions | < $0.01 |
| Lambda | Free tier |
| SQS | Free tier |
| API Gateway | Free tier |
| DynamoDB | Free tier |
| S3 | < $0.01 |
| SNS | Free tier |
| GitHub CI | Free (public repo) |
| Model inference | ~$0.01–$0.10 per job (Together.ai) or free (Ollama) |

## Rollout

Shepherd goes offline during migration. The MCP server is gutted (SHEP-30) and stays
non-functional until the MVP is wired end-to-end:
1. CDK deployed → infrastructure exists (SHEP-30)
2. Normalisation layer + provider translators (SHEP-34)
3. shepherd-mcp rewritten as thin client (SHEP-30)
4. End-to-end test: submit job → merged output in GitHub

## Related stories

| Ref | Title | Status |
|---|---|---|
| SHEP-29 | Shepherd GUI | Backlog |
| SHEP-34 | Normalisation layer | Backlog |
| SHEP-36 | Step Functions CDK IaC | → folded into SHEP-30 |
| SHEP-37 | PM orchestrator | Backlog |
| SHEP-38 | Ollama SQS worker | Backlog |
