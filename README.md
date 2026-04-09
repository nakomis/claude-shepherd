# Claude Shepherd

A framework for orchestrating drone LLMs (Ollama, Bedrock, OpenAI, Gemini) under Claude's supervision to generate code cheaply, with Claude acting as architect, gatekeeper, and reviewer.

If you find this useful, please consider buying me a coffee:

[![Donate with PayPal](https://www.paypalobjects.com/en_GB/i/btn/btn_donate_SM.gif)](https://www.paypal.com/donate?hosted_button_id=Q3BESC73EWVNN)

## The idea

Claude is expensive for boilerplate generation but irreplaceable for reasoning. Cheap local or API models (drones) can generate code given a tight enough spec — but they make systematic errors. Claude Shepherd puts Claude in charge of the pipeline: writing specs, running gates, reviewing residual failures, and merging approved output.

## Pipeline

```
Claude writes spec
       ↓
Drone generates in worktree  (Ollama / Bedrock / OpenAI — cheap)
       ↓
Compile gate  (tsc / vite — free, catches ~40–50% of errors)
       ↓
Known-errors FAQ self-correction loop  (drone, up to N retries)
       ↓
Claude subagent checklist review  (focused, isolated context)
       ↓
Claude gate  (genuine escalations only — main context, minimised)
       ↓
Merge to branch
```

## Components

| Component | Description |
|---|---|
| `shepherd-mcp/` | MCP server — exposes pipeline as tools Claude calls directly |
| `skills/` | Claude Code slash commands wrapping pipeline operations |
| `.claude/agents/` | Custom agent definitions (reviewer, spec writer) |
| `docs/` | Pipeline design, spec format, known-errors FAQ |

## MCP tools

- `drone_generate(spec, model, project_path)` → `job_id`
- `drone_status(job_id)` → `pending \| compiling \| correcting \| ready \| failed`
- `drone_result(job_id)` → files, errors, correction rounds, token counts
- `drone_approve(job_id)` → merges worktree branch
- `drone_reject(job_id, feedback)` → re-queues with feedback appended to spec

## Drone providers

- **OllamaProvider** — local, free (default)
- **BedrockProvider** — AWS Bedrock (Claude, Llama, etc.)
- **OpenAIProvider** — GPT-4o etc.
- **GeminiProvider** — Google

Providers are pluggable per-job — you can mix within a session.

## Licence

CC0 — public domain. No rights reserved.

---

If you find this useful, please consider buying me a coffee:

[![Donate with PayPal](https://www.paypalobjects.com/en_GB/i/btn/btn_donate_SM.gif)](https://www.paypal.com/donate?hosted_button_id=Q3BESC73EWVNN)
