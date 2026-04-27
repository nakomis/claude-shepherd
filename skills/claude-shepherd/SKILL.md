---
name: claude-shepherd
description: Use when generating non-trivial amounts of boilerplate code via drone LLMs. Invoked as /claude-shepherd. Never implement drone-appropriate code directly — always run this workflow.
---

# claude-shepherd

Orchestrate a drone LLM (Ollama, Together.ai) to generate code under Claude's supervision.
Claude writes the spec and reviews the output; the drone does the cheap generation.

**Rule:** Never implement code directly when the task is drone-appropriate. Use this workflow.

---

## Step 0 — Is this task drone-appropriate?

Use drones when:
- Generating one or more complete files that follow an established pattern in the codebase
- Writing boilerplate (CRUD handler, React page, test file) where the spec can be written tightly
- Token cost of direct generation would be significant

Do it solo (skip this skill) when:
- The change is small and surgical (tweak a value, rename a field, fix a typo)
- The task requires deep understanding of the whole system to get right
- Pipeline overhead would exceed the generation cost

If in doubt, start with a drone — a tight spec is almost always faster than Claude writing 300 lines.

---

## Step 1 — Write the spec

Use the format from `docs/spec-format.md`. Every field that is present will be checked by the reviewer. Every field that is absent will not. Be exact.

**Minimum required fields:**
- `target_file` — relative to repo root (include subdirectory for monorepos)
- `action` — `create` or `patch`
- `description` — one paragraph
- `interfaces` — exact signatures; copy from source where possible
- `constraints` — checkable rules, not vague adjectives

**For patch specs:** paste the current code verbatim as the FIND text. Drones cannot read the worktree.

**Write the test file first** (where applicable), then add `test_file` to the spec — the compile gate will run it.

---

## Step 2 — Choose a model

| Model | When |
|---|---|
| `ollama/qwen2.5-coder:14b` | Default — fast, free, good at TypeScript/Python/Rust |
| `together/Qwen/Qwen3-Coder-480B-A35B-FP8` | Complex logic, multi-file, high-stakes generation |

Start with the Ollama model. Escalate to Together only if the Ollama model fails repeatedly on a spec that is already tight.

---

## Step 3 — Fire the drone

```
drone_generate(
  spec=<spec text>,
  model=<model string>,
  project_path=<absolute path to git repo root>
)
```

`project_path` must be the repo root (where `.git/` lives), not a subdirectory.

The drone runs in an isolated git worktree at `{repo_parent}/.shepherd-worktrees/shepherd/{job_id[:8]}`.
Multiple parallel shepherd jobs on the same project are safe — each gets its own worktree and branch.

---

## Step 4 — Wait for the result

```
drone_wait(job_id, timeout=1800)
```

This blocks until the pipeline reaches `ready` or `failed`. Do not poll with `drone_status` in a loop.

If the result is `failed`:
- Check `drone_result(job_id)` for `failure_reason`
- If the spec was ambiguous, tighten it and call `drone_reject(job_id, feedback)`
- If the model is consistently failing, escalate to the larger model

---

## Step 5 — Review the output

Read the generated files with `drone_files(job_id)`.

Check against the spec:
- Every interface present with the correct signature?
- Every constraint satisfied?
- No unprompted additions that change behaviour?
- Logic correct for the described purpose?

**If running as Haiku:** spawn a Sonnet sub-agent for this review step.
Give it: the original spec + generated file contents + the reviewer checklist from `ignored/reviewer-prompt.md`.
Haiku should not make the approve/reject judgement alone on non-trivial output.

---

## Step 6 — Approve or reject

**Approve** (output is correct):
```
drone_approve(job_id)
```
This merges the worktree branch into the current working tree branch and removes the worktree.

**Reject** (output has fixable problems):
```
drone_reject(job_id, feedback=<specific instructions>)
```
Feedback is appended to the original spec and the pipeline reruns from generation. Be precise — "fix the logic in `acquire()`" is better than "it's wrong".

After rejection, go back to Step 4.

---

## Cost model

- Ollama drones: free
- Together.ai drones: ~$0.90/M tokens (check `drone_cost_summary()` for session total)
- Haiku orchestration: cheap (polling, applying output, running steps)
- Sonnet reviewer sub-agent: one focused call per job — justified only for the judgement step

Spawn the reviewer sub-agent only once per job, not once per file. Give it everything it needs to verdict without follow-up calls.

---

## Parallel jobs

You can fire multiple `drone_generate` calls before calling `drone_wait`. Use this when generating several independent files in one session — the drones run concurrently in separate worktrees.

```
job_a = drone_generate(spec_a, model, project_path)
job_b = drone_generate(spec_b, model, project_path)
drone_wait(job_a)  # then review + approve/reject
drone_wait(job_b)  # then review + approve/reject
```

Approve each independently. `drone_approve` merges and removes that job's worktree cleanly.

---

## Troubleshooting

**FIND text not found (patch failure):** The drone hallucinated the existing code. Add the actual current code verbatim to the spec. Use `drone_reject` with the correction.

**Compile errors persist after 3 rounds:** The model can't self-correct from the spec alone. Add a `related_files` field so the drone has more context, or switch to the larger model.

**`drone_generate` returns immediately as failed:** Worktree creation failed (branch name collision, git lock). Check `drone_result` for `failure_reason`. Stale shepherd branches can be deleted with `git branch -d shepherd/{id}`.
