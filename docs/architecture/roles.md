# Agent Role Model

Claude Shepherd is structured around a formal role model that mirrors how good software teams actually work. Each role maps to a specific agent tier, model cost point, and escalation path. This model is the *why* behind the state machine, the PM orchestrator, and the GUI — without it, those are just plumbing.

## Role table

| Role | Agent | Model tier | Responsibility |
|---|---|---|---|
| **Architect** | Claude (Sonnet/Opus) + Martin | Human + top-tier LLM | Requirements, system design, Taiga epics and stories with acceptance criteria and dependencies |
| **Business** | Martin | Human | Approves the plan before engineering starts; final escalation point |
| **Project Manager** | Shepherd orchestrator | Automated (reads Taiga) | Reads epic, resolves dependency graph, fans out unblocked stories, re-evaluates after each merge |
| **Engineering** | Drone | Ollama / Together.ai (cheap, fast) | Generates code to spec; self-corrects on compile errors up to N rounds |
| **QA** | Reviewer agent | Claude via normalisation layer | Approves or rejects with specific, actionable feedback; loops back to Engineering if rejected |
| **CI** | GitHub Actions | Automated, free | Compile gate — generated code must pass the same bar as human-written code |

## Role details

### Architect (Claude + Martin)

The Architect role is collaborative — Martin drives requirements and final decisions; Claude provides system design, identifies risks, and writes Taiga stories with enough detail for the PM to act on them autonomously.

**Responsibilities:**
- Decompose work into epics and stories with clear acceptance criteria (where appropriate)
- Write acceptance criteria in stories in a form QA can assess — specific, observable, not ambiguous
- Set `is_blocked` / `blocked_note` on stories that have dependencies
- Write or review specs tight enough for drones to generate against
- Resolve ambiguities before they reach Engineering

**Definition of done:** Epic is fully specified in Taiga. All stories have acceptance criteria, correct dependencies set, and at least a skeleton spec where Engineering work is involved.

---

### Business (Martin)

A lightweight human gate between planning and execution. Exists to prevent the PM from kicking off expensive pipelines against a plan that Martin hasn't agreed to.

**Responsibilities:**
- Review and approve the Architect's plan before the PM starts
- Remain the final escalation point when the PM is stuck or QA has rejected too many times

**Definition of done:** Martin has explicitly approved the epic and kicked off the PM run.

---

### Project Manager (Shepherd orchestrator)

The PM is fully automated. It reads Taiga, resolves the dependency graph, and fans out engineering work in the right order — concurrently where stories are independent, sequentially where they are not.

**Responsibilities:**
- Read the target epic from Taiga
- Inspect `is_blocked` flags to determine which stories are ready to assign
- Fan out concurrent engineering jobs (Step Functions Map state for independent stories)
- After each merge, re-evaluate the dependency graph — newly unblocked stories are assigned next
- Escalate to Martin when a story is stuck (QA rejected N times, CI won't pass)

**Definition of done:** All stories in the epic are merged, or escalated to Martin with a clear explanation of why they are stuck.

---

### Engineering (Drone)

The cheapest possible code generation. Drones operate entirely within a worktree — they never touch the working tree directly. They receive a spec and produce files or patches; the pipeline handles everything else.

**Responsibilities:**
- Generate code to spec (full files or FIND/REPLACE patches)
- Self-correct on compile errors (up to `MAX_CORRECTION_ROUNDS` rounds)

**Model tier:** Ollama (free, local) for cost-zero runs; Together.ai Qwen (cheap, fast) for cloud runs. Escalate to a more capable model only after N failed correction rounds.

**Definition of done:** Compile gate passes. Output surfaces to QA as `ready`.

---

### QA (Reviewer agent)

The QA reviewer is a Claude subagent with a focused, isolated context — it sees the spec and the generated files, nothing else. It runs a checklist against the spec and either approves or produces specific, actionable rejection feedback.

**Responsibilities:**
- Verify spec compliance: every `interfaces` entry present with correct signature
- Verify correctness: logic matches `description`; all `constraints` satisfied
- Verify project conventions: imports match `dependencies`; no extras
- Verify scope: no unprompted additions unless harmless
- Assess story acceptance criteria (where present) and confirm they have been met

**Escalation:** If QA rejects the same job N times, escalate to Martin rather than looping further.

**Definition of done:** Reviewer approves. Output merges to branch.

---

### CI (GitHub Actions)

The compile gate is the first and cheapest filter. It runs the same checks as the project's normal CI — type checking, linting, tests. Drone output that fails here is sent back to Engineering before QA ever sees it.

**Definition of done:** All CI checks pass. This is a hard gate — there are no exceptions.

---

## The full loop

```
Architect session (Martin + Claude)
  → Taiga epic with stories, dependencies, and specs
        ↓
Martin approves epic (Business gate)
        ↓
PM reads epic, resolves dependency graph
  → fans out unblocked stories concurrently
        ↓
Engineering drones generate code in worktrees
  → compile gate self-correction loop
        ↓
QA reviewer approves or rejects with feedback
  → rejection loops back to Engineering
        ↓
CI gate (GitHub Actions)
        ↓
Merge → PM re-evaluates dependency graph
  → newly unblocked stories assigned next
        ↓
Epic complete → notify Martin
```

Escalation paths:
- Engineering fails after N correction rounds → PM escalates to Martin
- QA rejects after N rounds → PM escalates to Martin
- CI fails after N rounds → PM escalates to Martin

---

## Adding a new role

Each role is an agent tier with a defined input, output, and escalation. To add a role — for example, a dedicated **Security Reviewer** between QA and CI:

1. Define the role's input (what it receives), output (approve / reject with feedback), and escalation path
2. Add it to the role table above
3. Add a state to the Step Functions state machine (ref 30) for the new role
4. Surface its status in the GUI (ref 29)

The pipeline structure doesn't need to change — new roles slot in as additional states.
