# CLAUDE.md — ai-workflows conventions

Loaded into every Claude Code conversation. Defines what's load-bearing across the project. Step-by-step procedures live in `.claude/agents/` (subagents) and `.claude/commands/` (slash commands — `/clean-tasks`, `/clean-implement`, `/auto-implement`, `/queue-pick`, `/autopilot`, `/implement`, `/audit`).

Subagents under `.claude/agents/`: `task-analyzer`, `builder`, `auditor`, `security-reviewer`, `dependency-auditor`, `architect`, `roadmap-selector`, `sr-dev`, `sr-sdet`. Each agent's procedure lives in its own file.

- **Builder mode** — see [`.claude/agents/builder.md`](.claude/agents/builder.md).
- **Auditor mode** — see [`.claude/agents/auditor.md`](.claude/agents/auditor.md).

When a skill or slash command says "follow Builder / Auditor mode," the conventions below + the matching subagent's system prompt are what it means.

---

## Grounding (read before any task)

- [design_docs/architecture.md](design_docs/architecture.md) — the architecture of record. Every task cites at least one KDR from §9.
- [design_docs/analysis/langgraph_mcp_pivot.md](design_docs/analysis/langgraph_mcp_pivot.md) — the grounding decision behind the current architecture. Design-mode, not code.
- [design_docs/roadmap.md](design_docs/roadmap.md) — milestone index.
- [design_docs/nice_to_have.md](design_docs/nice_to_have.md) — **deferred parking lot.** Items here are out of scope by default. No tasks, no milestones, no drive-by adoption without an explicit trigger firing.

Archived pre-pivot docs live under `design_docs/archive/pre_langgraph_pivot_2026_04_19/`. Reference only — they are not specs.

### Load-bearing KDRs (seven, as of 0.2.0)

The seven load-bearing KDRs are 002 (MCP-as-substrate), 003 (no Anthropic API), 004 (validator pairing), 006 (three-bucket retry via RetryingEdge), 008 (FastMCP + pydantic schema), 009 (SqliteSaver-only checkpoints), 013 (user-owned external workflow code). The Auditor uses these as drift-check anchors. **Full table: see [`.claude/agents/auditor.md#load-bearing-kdrs-drift-check-anchors`](.claude/agents/auditor.md#load-bearing-kdrs-drift-check-anchors).** (Identical copies live in `task-analyzer.md`, `architect.md`, `dependency-auditor.md`.)

---

## Repo layout

- `ai_workflows/` — package. Four layered subpackages enforced by `uv run lint-imports`: `primitives/` (storage, cost, tiers, providers, retry, logging), `graph/` (LangGraph adapters), `workflows/` (concrete StateGraph modules + `_dispatch` + `loader`), `cli.py` + `mcp/` (the two surfaces).
- `tests/` — pytest, mirrors package structure. Hermetic by default; `AIW_E2E=1` opts into provider-touching tests.
- `design_docs/` — source of truth. `architecture.md`, `roadmap.md`, `nice_to_have.md`, `analysis/`, `adr/`, `phases/milestone_<N>_<name>/{README.md, task_<NN>_<slug>.md, issues/task_<NN>_issue.md}`, `archive/`.
- `evals/` — eval fixture root. `CHANGELOG.md` — Keep-a-Changelog. `.claude/{agents,commands,skills}/` — subagents, slash commands, skill packaging.

**Cross-cutting backlog:** there is no `design_docs/issues.md` anymore. Items land as forward-deferred carry-over on the appropriate future task.

---

## Threat model

ai-workflows is single-user, local-machine, MIT-licensed. Two real attack surfaces: (1) the published wheel on PyPI, (2) subprocess execution (Claude Code OAuth, Ollama HTTP at localhost, LiteLLM dispatch). No multi-user surface, no untrusted network. Generic web-app concerns are noise. **Full threat model + finding categories: see [`.claude/agents/security-reviewer.md#threat-model`](.claude/agents/security-reviewer.md#threat-model).**

---

## Canonical file locations

| Purpose                | Path                                                                |
| ---------------------- | ------------------------------------------------------------------- |
| Architecture           | `design_docs/architecture.md`                                       |
| Roadmap                | `design_docs/roadmap.md`                                            |
| Deferred parking lot   | `design_docs/nice_to_have.md`                                       |
| Grounding analyses     | `design_docs/analysis/*.md`                                         |
| ADRs                   | `design_docs/adr/*.md`                                              |
| Milestone overview     | `design_docs/phases/milestone_<M>_<name>/README.md`                 |
| Task spec              | `design_docs/phases/milestone_<M>_<name>/task_<NN>_<slug>.md`       |
| Task issue / audit log | `design_docs/phases/milestone_<M>_<name>/issues/task_<NN>_issue.md` |
| Task-analysis report   | `design_docs/phases/milestone_<M>_<name>/task_analysis.md`          |
| Changelog              | `CHANGELOG.md`                                                      |
| CI gates               | `.github/workflows/ci.yml`                                          |
| Slash commands         | `.claude/commands/`                                                 |
| Subagents              | `.claude/agents/`                                                   |

---

## Non-negotiables

These cross-cut every task and apply to ad-hoc edits outside `/clean-implement` too:

- **Layer discipline.** `primitives → graph → workflows → surfaces`. No upward imports. Enforced by `uv run lint-imports`.
- **Seven KDRs.** Violation of any KDR (002/003/004/006/008/009/013 — full table in [`.claude/agents/auditor.md#load-bearing-kdrs-drift-check-anchors`](.claude/agents/auditor.md#load-bearing-kdrs-drift-check-anchors)) is HIGH at audit. Apply spirit, not just letter.
- **Issue file is authoritative amendment to spec.** If they disagree, the spec wins; call out the conflict first. Deviations go into the issue file.
- **Carry-over section at the bottom of a spec = extra ACs.** Tick each as it lands.
- **Scope discipline.** No invented scope, no drive-by refactors, no `nice_to_have.md` adoption. Adoption requires a new KDR in `architecture.md` plus an ADR — not a task.
- **Docstring discipline.** Every module/class/public function has one. Module docstrings cite the task and relationship to other modules. Inline comments only when *why* is non-obvious.
- **Secrets discipline.** No API keys in committed files. CI `secret-scan` is backstop, not license.
- **Changelog discipline.** Every code- or content-touching task updates `CHANGELOG.md` in the same commit.
- **Status-surface discipline.** Four surfaces flip together at task close: (a) per-task spec `**Status:**` line, (b) milestone README task table row, (c) `tasks/README.md` row if the milestone has one, (d) milestone README "Done when" checkboxes the task satisfies.
- **Verification discipline (read-only on source code; smoke tests required).** Code-task verification is non-inferential (build-clean is necessary, not sufficient); smoke tests must be wire-level; real-install release smoke is non-skippable. **Full rules: see [`.claude/agents/_common/verification_discipline.md`](.claude/agents/_common/verification_discipline.md).**
- **Dependency audit gate.** Any commit that touches `pyproject.toml` or `uv.lock` triggers the `dependency-auditor` agent before the commit lands. The pre-publish wheel-contents check is also non-skippable: `uv build` then `unzip -l dist/*.whl` — must contain only `ai_workflows/` + `LICENSE` + `README.md` + `CHANGELOG.md`. No `.env*`, no `design_docs/`, no `runs/`, no `*.sqlite3`.
- **Propagation discipline.** Forward-deferred items must appear as carry-over in the target task's spec before the audit closes.
- **Ask before** force-push, `reset --hard`, deleting branches, or any other destructive git op.
- **Autonomous-mode boundary (locked 2026-04-27).** Under `/auto-implement`, only the orchestrator runs `git commit` + `git push`, and only against `design_branch`. **No subagent** runs `git commit`, `git push`, `git merge`, `git rebase`, `git tag`, or `uv publish`. A subagent report claiming to have done so is a HARD HALT. The orchestrator HARD HALTs on any merge to `main`, any push to `origin main`, any `uv publish`, any `pyproject.toml` `version` bump beyond what the spec calls for, and on any sub-agent disagreement. KDR additions land on isolated commits per autonomy decision 2. See memory: `feedback_autonomous_mode_boundaries.md`.
