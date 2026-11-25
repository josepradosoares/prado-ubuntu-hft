# Project Instructions — Prado Ubuntu HFT

This project uses [metaswarm](https://github.com/dsifry/metaswarm), a multi-agent orchestration framework for Claude Code. It provides 23 agents, a 9-phase development workflow, and quality gates that enforce TDD, coverage thresholds, and spec-driven development.

> **Project Rules:** Also follow [AGENTS.md](AGENTS.md) and the mandatory cTrader Open API rules in [.agent/rules/ctrader-api.md](.agent/rules/ctrader-api.md).

## How to Work in This Project

### Starting work

```text
/start-task
```

This is the default entry point. It primes the agent with relevant knowledge, guides you through scoping, and picks the right level of process for the task.

### For complex features (multi-file, spec-driven)

Describe what you want built, include a Definition of Done, and ask for the full workflow:

```text
I want you to build [description]. [Tech stack, DoD items, file scope.]
Use the full metaswarm orchestration workflow.
```

This triggers the full orchestration pipeline: Research → Plan → Plan Review Gate → Design Review Gate (reviews the plan) → Work Unit Decomposition → Orchestrated Execution (4-phase loop per unit) → Final Review → PR. When the work instead goes through brainstorming and it commits a project-sized design doc, the Design Review Gate reviews that design doc, before writing-plans (see the metaswarm plugin's `guides/workflow-enforcement.md`).

### Available Commands

| Command | Purpose |
|---|---|
| `/start-task` | Begin tracked work on a task |
| `/prime` | Load relevant knowledge before starting |
| `/review-design` | Trigger parallel design review gate (6 agents) |
| `/pr-shepherd <pr>` | Monitor a PR through to merge |
| `/self-reflect` | Extract learnings after a PR merge |
| `/handoff` | Write a self-contained handoff doc so a fresh agent can resume the work |
| `/handle-pr-comments` | Handle PR review comments |
| `/brainstorm` | Refine an idea before implementation |
| `/create-issue` | Create a well-structured GitHub Issue |
| `/external-tools-health` | Check status of external AI tools (Codex, Gemini) |
| `/setup` | Interactive guided setup — detects project, configures metaswarm |
| `/update` | Update metaswarm to latest version |
| `/metaswarm:status` | Run diagnostic checks on your installation (plain `/status` is Claude Code's built-in) |
| `/start` | Alias for `/start-task` |

### Visual Review

Use the `visual-review` skill to take screenshots of web pages, presentations, or UIs for visual inspection. Requires Playwright (`npx playwright install chromium`). See `skills/visual-review/SKILL.md`.

## Testing

- **TDD is mandatory** — Write tests first, watch them fail, then implement
- **80% test coverage required** — Lines, branches, functions, and statements. Enforced via `.coverage-thresholds.json` as a blocking gate before PR creation and task completion
- Backend test command: `PYTHONPATH=. python -m pytest tests -v`
- Coverage command: `PYTHONPATH=. python -m pytest tests --cov=prado_linux --cov-fail-under=80` (requires `pytest-cov`)
- Frontend build check: `cd frontend && npm run build`

## Coverage

Coverage thresholds are defined in `.coverage-thresholds.json` — this is the **source of truth** for coverage requirements.
If a GitHub Issue specifies different coverage requirements, update `.coverage-thresholds.json` to match before implementation begins. Do not silently use a different threshold.

The validation phase of orchestrated execution reads `.coverage-thresholds.json` and runs the enforcement command. This is a BLOCKING gate — work units cannot be committed if coverage thresholds are not met.

## Quality Gates

- **Design Review Gate**: Parallel 6-agent review after a project-sized design doc is committed (`/review-design`)
- **Plan Review Gate**: Automatic adversarial review once the plan is written, before writing-plans presents the plan. Spawns 3 independent reviewers (Feasibility, Completeness, Scope & Alignment) in parallel — ALL must PASS before the plan is presented to the user. See `skills/plan-review-gate/SKILL.md`
- **Coverage Gate**: Reads `.coverage-thresholds.json` and runs the enforcement command — BLOCKING gate before PR creation

## Workflow Enforcement (MANDATORY)

These rules override any conflicting instructions from third-party skills or plugins. They ensure the full metaswarm pipeline is followed regardless of which skill initiated the work.

### During Brainstorming (every session)

When brainstorming starts, load `metaswarm:brainstorming-extension` at the start of brainstorming, not only after the commit. It supplies the assumption ledger, the confirmation rule and the Common misreadings checklist — they apply to every brainstorming session regardless of size, before any design is presented or committed. In every session, never label your own proposal as a user decision, and restate an answer that changes the design and get it confirmed before relying on it.

### After a Project-Sized Design Doc Is Committed

When brainstorming writes and commits a project-sized design doc (see the metaswarm plugin's `guides/workflow-enforcement.md`):

1. **STOP** — do NOT proceed directly to `writing-plans` or implementation
2. **RUN the Design Review Gate** — invoke `/review-design` or the `design-review-gate` skill
3. **WAIT** for all 6 review agents (PM, Architect, Designer, Security, UX Reviewer, CTO) to approve
4. **ONLY THEN** proceed to planning/implementation

### After Any Plan Is Created

When `superpowers:writing-plans` (or any planning skill) has written an implementation plan, run the Plan Review Gate before writing-plans presents the plan: do not link the plan, ask the user to review it, or offer an execution choice until all 3 reviewers PASS. See the metaswarm plugin's `guides/workflow-enforcement.md`.

1. **STOP** — do NOT present the plan to the user or begin implementation
2. **RUN the Plan Review Gate** — invoke the `plan-review-gate` skill
3. **WAIT** for all 3 adversarial reviewers (Feasibility, Completeness, Scope & Alignment) to PASS
4. **ONLY THEN** present the plan to the user for approval

### Before Finishing a Development Branch

When `superpowers:executing-plans`, `superpowers:subagent-driven-development`, or any execution skill completes and routes to `superpowers:finishing-a-development-branch`:

1. **STOP** — before presenting merge/PR options
2. **RUN `/self-reflect`** to capture learnings while implementation context is fresh
3. **COMMIT** the knowledge base updates
4. **THEN** proceed to finishing the branch (PR creation, merge, etc.)

### Coverage Source of Truth

`.coverage-thresholds.json` is the **single source of truth** for coverage requirements. No skill may skip it.

### Subagent Discipline

- **NEVER** use `--no-verify` on git commits
- **NEVER** use `git push --force` without explicit user approval
- **ALWAYS** follow TDD — write tests first, watch them fail, then implement
- **NEVER** self-certify — the orchestrator validates independently
- **STAY** within declared file scope — do not modify files outside your assigned scope

### Delivery Scope & Review Iteration

Block delivery only for a credible normal-usage failure, a missing or contradictory requirement, a broken key happy path, or an important error or recovery-path failure. Every review finding carries a `severity` (critical/major/minor/nit); to block, a critical/major finding must also name what it `protects` (a user scenario, requirement or DoD item). Findings without `protects` are advisory, not blockers. After each review round the orchestrator decides whether to iterate, advance, clarify or escalate:

- **No `blocker: yes` findings** → PASS, advance. Minor/nit findings become follow-ups (a BEADS task, or a GitHub issue if over a day).
- **Clarify** → a Clarify signal fires: C1 a blocker only the user can answer or that rests on an unconfirmed assumption, C2 blockers not converging, C3 two or more fix-induced blockers, C4 one theme recurring across 3 rounds. Stop, run the misunderstanding analysis, and send the Clarification report. A standing instruction such as "keep going" never defaults a `needs_user` question; only the user's answer does. Clarifying never approves.
- **Escalate to the human** → the same critical/major finding recurs after a fix attempt for it, two reviewers rate the same finding blocker vs. non-blocker, or the safety cap of 10 rounds is hit. The options include clarifying the requirement.
- **Overengineering signal** → restate the DoD and re-classify each blocker against the policy; escalate if any still names a credible scenario, otherwise downgrade them to follow-ups and advance.
- **Iterate** (fix, re-validate, fresh review) → this round fixed a critical/major finding, or ≥2 independent reviewers reported blockers.

These rules apply in order, top to bottom (Clarify is checked before escalation, and escalation before iteration). A round that still has a blocker and matches none of them also iterates. If `bd` is unavailable, list follow-ups in a `### Follow-ups` section.

Full policy, finding contract and ordered rule: `guides/delivery-scope.md` in the metaswarm plugin.

## External Tools (Optional)

External AI tools are configured in `.metaswarm/external-tools.yaml` (Codex CLI enabled). The orchestrator can delegate implementation and review tasks to Codex CLI for cost savings and cross-model adversarial review.

## Code Quality

- **Backend**: Python (`prado_linux/`), tested with `pytest` (`tests/`)
- **Frontend**: React 18 + TypeScript + Vite + Tailwind CSS (`frontend/`), verified with `tsc -b && vite build`
- **cTrader Open API**: Strict compliance with [.agent/rules/ctrader-api.md](.agent/rules/ctrader-api.md)
- All quality gates must pass before PR creation
