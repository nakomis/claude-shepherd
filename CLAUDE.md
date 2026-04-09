# Claude Shepherd — Framework Instructions

This repo contains the Claude Shepherd framework. When working on shepherd itself, use the pipeline to build pipeline components where possible (dogfooding).

## Using Shepherd in a project

### When to use drones vs Claude solo

**Use drones for:**
- Multiple similar files to generate (new CRUD endpoint, new React page following existing patterns)
- Well-specified, context-light work
- Tasks large enough that Claude token cost is significant

**Use Claude solo for:**
- Small, surgical changes (tweak a value, add a field, fix a typo)
- High context-dependence (requires understanding the whole system)
- Tasks where drone pipeline overhead exceeds generation cost

### Spec quality is everything

A drone with a tight spec outperforms a drone with a vague one by a large margin. Spend time on the spec. Include:
- `target_file` — exact path
- `description` — what it does
- `interfaces` — exact TypeScript types / function signatures
- `dependencies` — exact package names and import paths
- `env_vars` — environment variable names as set by CDK / infra
- `constraints` — explicit "never use X, always use Y" rules

### Compile gate

Always run the compile gate before escalating to the Claude gate. Compilation catches ~40–50% of drone errors for free. The known-errors FAQ eliminates another chunk before compilation runs.

### Worktree isolation

Each drone job runs in a dedicated git worktree. Never write drone output directly to the working tree — always via `drone_approve` after the full pipeline passes.

## Repo layout

```
shepherd-mcp/     Python MCP server
skills/           Claude Code slash command definitions
.claude/agents/   Custom agent definitions
docs/             Pipeline design, spec format, FAQ
```

## Branching

Always work on a feature branch. Create a PR when implementation is complete.

## Language

British English throughout.
