# AGENTS.md — Prado Ubuntu HFT

## Arquitetura do Projeto
- **Backend**: Python (`prado_linux/web_app.py`, `prado_linux/engine.py`, `prado_linux/ctrader_client.py`, `prado_linux/config.py`, `prado_linux/flow_math.py`, `prado_linux/auth.py`, `prado_linux/indicators.py`, `prado_linux/news_scout.py`, `prado_linux/supabase_store.py`).
- **Frontend**: React + TypeScript + Tailwind CSS + Lightweight Charts (`frontend/src/`), compilado para `prado_linux/static/` e servido na porta `8080` sem necessidade de Node.js em produção.
- **Testes**: `tests/` (`PYTHONPATH=. python -m pytest tests -v`).

## Regra Permanente da cTrader Open API (OBRIGATÓRIO)
Antes de qualquer alteração envolvendo integração com a cTrader (autenticação OAuth 2.0, Client ID/Secret, WebSocket porta 5036, símbolos, spots, trendbars, tickdata, ordens, posições, saldo, limites ou robôs), leia e siga estritamente:

- [Regra Permanente cTrader Open API](.agent/rules/ctrader-api.md)

## Fluxo Oficial de Autenticação & Negociação cTrader (Open API Porta 5036)
1. **Hosts WebSocket JSON (porta 5036)**:
   - Demo: `wss://demo.ctraderapi.com:5036`
   - Live: `wss://live.ctraderapi.com:5036`
2. **OAuth 2.0**:
   - Cadastro de App: `https://openapi.ctrader.com/apps` (`Client ID` e `Client Secret`).
   - Autorização: `https://id.ctrader.com/my/settings/openapi/grantingaccess/`
   - Troca/Refresh de Token (`GET`): `https://openapi.ctrader.com/apps/token`
3. **Handshake WebSocket**: `2100` (`ProtoOAApplicationAuthReq`) → `2149` (`ProtoOAGetAccountListByAccessTokenReq`) → `2102` (`ProtoOAAccountAuthReq`) no host (`demo` ou `live`) correspondente ao `isLive` da conta.
4. **Ordens a Mercado (`2106`)**: Usar `orderType = 1` (MARKET), `volume` em centicents conforme `lotSize` do símbolo, e proteção via `relativeStopLoss` / `relativeTakeProfit`.

## metaswarm

This project uses [metaswarm](https://github.com/dsifry/metaswarm) for multi-agent orchestration. It provides 23 agents, a 9-phase development workflow, and quality gates that enforce TDD, coverage thresholds, and spec-driven development.

### Workflow

- **Most tasks**: `$start` -- primes context, guides scoping, picks the right level of process
- **Complex features** (multi-file, spec-driven): Describe what you want built with a Definition of Done, then say: `Use the full metaswarm orchestration workflow.`

### Available Skills

Codex discovers skills by their SKILL.md `name` field. Invoke with `$name` syntax.

| Invoke | Purpose |
|---|---|
| `$start` | Begin tracked work on a task |
| `$setup` | Interactive guided setup |
| `$design-review-gate` | Trigger design review gate (6 reviewers) |
| `$pr-shepherd` | Monitor a PR through to merge |
| `$handling-pr-comments` | Handle PR review comments |
| `$brainstorming-extension` | Refine an idea with design review gate |
| `$create-issue` | Create a well-structured GitHub Issue |
| `$plan-review-gate` | Adversarial plan review (3 reviewers) |

### Quality Gates

- **Design Review Gate** -- 6-reviewer design review after a project-sized design doc is committed (`$design-review-gate`)
- **Plan Review Gate** -- 3 adversarial reviewers (Feasibility, Completeness, Scope & Alignment) -- ALL must PASS
- **Coverage Gate** -- `.coverage-thresholds.json` defines thresholds (80%). BLOCKING gate before PR creation

### Testing & Quality

- **TDD is mandatory** -- Write tests first, watch them fail, then implement
- **80% test coverage required** -- Enforced via `.coverage-thresholds.json`
- **Coverage source of truth** -- `.coverage-thresholds.json` defines thresholds. The orchestrator reads it during validation.
- **Backend tests**: `PYTHONPATH=. python -m pytest tests -v`
- **Coverage command**: `PYTHONPATH=. python -m pytest tests --cov=prado_linux --cov-fail-under=80`
- **Frontend build**: `cd frontend && npm run build`

### Workflow Enforcement (MANDATORY)

- **During brainstorming** -> load `$brainstorming-extension` at the start of brainstorming, not only after the commit, for its assumption ledger, confirmation rule and Common misreadings checklist; it applies to every brainstorming session regardless of size
- **Assumptions** -> never label your own proposal as a user decision, and restate an answer that changes the design and get it confirmed before relying on it.
- **After a project-sized design doc is committed** -> MUST run `$design-review-gate` before planning or implementation (see the metaswarm plugin's `guides/workflow-enforcement.md`)
- **After the plan is written** -> MUST run `$plan-review-gate` before writing-plans presents the plan (see the metaswarm plugin's `guides/workflow-enforcement.md`)
- **Coverage** -> `.coverage-thresholds.json` is the single source of truth. All skills must check it.
- **Agent discipline** -> NEVER use `--no-verify`, NEVER `git push --force` without approval, NEVER self-certify, ALWAYS follow TDD, STAY within file scope

### Delivery Scope & Review Iteration

Block delivery only for a credible normal-usage failure, a missing or contradictory requirement, a broken key happy path, or an important error or recovery-path failure. Every review finding carries a `severity` (critical/major/minor/nit); to block, a critical/major finding must also name what it `protects` (a user scenario, requirement or DoD item). Findings without `protects` are advisory, not blockers. After each review round the orchestrator decides whether to iterate, advance, clarify or escalate:

- **No `blocker: yes` findings** -> PASS, advance. Minor/nit findings become follow-ups (a BEADS task, or a GitHub issue if over a day).
- **Clarify** -> a Clarify signal fires: C1 a blocker only the user can answer or that rests on an unconfirmed assumption, C2 blockers not converging, C3 two or more fix-induced blockers, C4 one theme recurring across 3 rounds. Stop, run the misunderstanding analysis, and send the Clarification report. A standing instruction such as "keep going" never defaults a `needs_user` question; only the user's answer does. Clarifying never approves.
- **Escalate to the human** -> the same critical/major finding recurs after a fix attempt for it, two reviewers rate the same finding blocker vs. non-blocker, or the safety cap of 10 rounds is hit. The options include clarifying the requirement.
- **Overengineering signal** -> restate the DoD and re-classify each blocker against the policy; escalate if any still names a credible scenario, otherwise downgrade them to follow-ups and advance.
- **Iterate** (fix, re-validate, fresh review) -> this round fixed a critical/major finding, or 2+ independent reviewers reported blockers.

These rules apply in order, top to bottom (Clarify is checked before escalation, and escalation before iteration). A round that still has a blocker and matches none of them also iterates. If `bd` is unavailable, list follow-ups in a `### Follow-ups` section.

Full policy, finding contract and ordered rule: `guides/delivery-scope.md` in the metaswarm plugin.

