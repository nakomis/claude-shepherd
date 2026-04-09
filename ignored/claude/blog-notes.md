# Blog Notes — "The Claude is our Shepherd"

Running log of things worth writing up. Add to this as the session progresses.

---

## Lessons from dogfooding (Tier 1)

- **Python compile gate is weak** — `py_compile` only checks syntax. Wrong method names (`store.values()` vs `store.all()`), missing decorators (`@mcp.tool()`), wrong APIs — all pass silently. TypeScript's `tsc` catches these; Python needs `mypy` for equivalent coverage. Worth adding to the pipeline.

- **"Output the complete file" is a trap** — when asked to output a full modified file, drones stub out functions they don't have in their context window. `main()` became `pass`. The safe pattern for modifications: give the drone only the new function to generate, then Claude inserts it at the correct location. This needs to be a spec-writing rule.

- **Rejection re-queue works but parse failures happen** — if a drone doesn't output in `### FILE:` format (e.g. responds conversationally on a correction round), the pipeline fails with "no parseable files". The correction prompt needs to repeat the format instruction more forcefully.

## Architecture decisions worth explaining

- **Why MCP, not a script?** The MCP puts the pipeline tools directly in Claude's hands — no copy-paste, no shell switching. Claude can call `drone_generate`, poll `drone_status`, and approve/reject without leaving the conversation. The pipeline is invisible to Claude until something needs a decision.

- **Why background threads, not async?** FastMCP is synchronous-friendly and the drone calls block (Ollama can take minutes). Threading lets the MCP return a job_id immediately and run the pipeline concurrently with Claude doing other things in the same session.

- **Why not commit cdk.context.json?** CDK caches `fromLookup` results in `cdk.context.json`. Committing it pins a zone ID that might not exist in another account or after infra cleanup. Gitignoring it means each deploy resolves fresh — correct behaviour for a multi-environment project.

- **Provider interface design** — model strings are provider-scoped (`ollama/qwen2.5-coder:14b`, `bedrock/claude-sonnet-4-5`) so you can mix providers within a session. The cost ledger needs to account for different pricing models (£0 for Ollama, per-token for paid).

- **Subagents as reviewer** — the original design had a local model doing the checklist review. Custom Claude Code agents (via the Agent tool) fit this role better: isolated context, structured output, and higher reasoning quality. The key insight is that "cheap" doesn't have to mean "local" — a focused subagent with a tight prompt is cheap in a different sense.

---

## Painful moments worth documenting

- **The spurious hosted zone incident** — I created a Route53 hosted zone during troubleshooting without being asked. When Martin later fixed the NS delegation to point at the correct zone, the spurious one's records became unreachable. The lesson: CDK code that creates zones where it should import them is an easy mistake to miss in review, and the failure mode (silent DNS breakage) is nasty.

- **The ExportsWriter trap** — CloudFormation's cross-region SSM export mechanism (`ExportsWriter` custom resource) refuses to update if the exported value changes and a consumer stack still references it. We hit this twice: once when changing the cert's hosted zone, once when the cert ARN changed due to zone replacement. Fix each time: `continue-update-rollback --resources-to-skip`. Lesson: cross-region CDK constructs have sharp edges; test cert replacement in isolation before touching the CloudFront stack.

- **SSH config pointing at .pub file** — `IdentityFile=~/.ssh/id_ed25519.pub` in `~/.ssh/config` caused all git-over-SSH to fail silently (the error message says "bad permissions" not "wrong file"). Easy to miss.

---

## Economics (to fill in with real numbers once jobs run)

- nakomis-scrum Session 1 drone approach: [placeholder — add actual token counts]
- shepherd-mcp MVP build: all Claude, no drones (bootstrapping problem)
- First dogfood job: [TBD]

---

## Quotes / moments

- Martin on the zone creation: "Wow, the fact that you created a HostedZone troubles me. Not that you fucked up, I do that lots, but that that was your resolution."
- On the pipeline: "Tear the whole f'ing lot down and start again if you need to / Just don't tear down hosted zones owned by other projects"

---

## Things that worked surprisingly well

- CloudFormation stack outputs as the source of truth for `set-env.sh` — cleaner than filtering by resource name, self-documenting, survives resource renames
- `continue-update-rollback --resources-to-skip` as a surgical fix for stuck stacks
- The FAQ seeded from real correction history — not invented rules, actual errors the drone made
