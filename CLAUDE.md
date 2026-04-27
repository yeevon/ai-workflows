# CLAUDE.md — ai-workflows conventions

Loaded into every Claude Code conversation. Defines what's load-bearing across the project. Step-by-step procedures live in `.claude/agents/` (subagents) and `.claude/commands/` (slash commands):

- `/clean-tasks <milestone>` — generate per-task spec files for a milestone (if missing) and loop the `task-analyzer` subagent + spec-fix application until the analysis returns no HIGH or MEDIUM findings. Pushes any LOWs to each spec's `## Carry-over from task analysis` section. Cap of 5 rounds.
- `/clean-implement <task>` — full Builder → Auditor loop (up to 10 cycles) + security gate. Spawns subagents via `Task`. **Auditor-agreement bypass on stop condition 2:** when the auditor (or security reviewer) surfaces a single clear recommendation and the loop controller concurs against the spec + KDRs + locked decisions, the controller stamps it as `Locked decision (loop-controller + Auditor concur, YYYY-MM-DD): <one-liner>` in the issue file and feeds it to the next Builder cycle as a carry-over AC instead of halting. Halt only when the auditor surfaces two-or-more options without a recommendation, the recommendation conflicts with a KDR / prior user decision / the spec, or it expands scope or defers work to a non-existent future task. See `.claude/commands/clean-implement.md` for the full mechanic.
- `/implement <task>` — single Builder pass; spawns the `builder` subagent.
- `/audit <task>` — single Auditor pass; spawns the `auditor` subagent.

Subagents:

- `task-analyzer` — read-mostly; deep-analysis pass on freshly-generated or recently-edited task specs (the one we run whenever tasks get tasked-out). Verifies every spec claim against the live codebase + KDRs + sibling specs; writes findings to the milestone's `task_analysis.md`.
- `builder` — implements strictly to spec; returns terse report; no self-grading.
- `auditor` — read-only on source code; mandatory architecture + KDR drift check; writes the issue file.
- `security-reviewer` — post-functional-clean threat-model check; appends to the issue file.
- `dependency-auditor` — `pyproject.toml` / `uv.lock` changes + wheel-contents pre-publish; appends to the issue file.

When a skill or slash command says "follow Builder / Auditor mode," the conventions below + the matching subagent's system prompt are what it means.

---

## Grounding (read before any task)

- [design_docs/architecture.md](design_docs/architecture.md) — the architecture of record. Every task cites at least one KDR from §9.
- [design_docs/analysis/langgraph_mcp_pivot.md](design_docs/analysis/langgraph_mcp_pivot.md) — the grounding decision behind the current architecture. Design-mode, not code.
- [design_docs/roadmap.md](design_docs/roadmap.md) — milestone index.
- [design_docs/nice_to_have.md](design_docs/nice_to_have.md) — **deferred parking lot.** Items here are out of scope by default. No tasks, no milestones, no drive-by adoption without an explicit trigger firing.

Archived pre-pivot docs live under `design_docs/archive/pre_langgraph_pivot_2026_04_19/`. Reference only — they are not specs.

### Load-bearing KDRs (seven, as of 0.2.0)

| KDR | Rule |
| --- | --- |
| **KDR-002** | MCP server is the portable inside-out surface; the Claude Code skill is optional packaging, not the substrate. |
| **KDR-003** | No Anthropic API. Runtime tiers are Gemini (LiteLLM) + Qwen (Ollama); Claude access is OAuth-only via the `claude` CLI subprocess. Zero `anthropic` SDK imports, zero `ANTHROPIC_API_KEY` reads. |
| **KDR-004** | `ValidatorNode` after every `TieredNode`. Prompting is a schema contract. |
| **KDR-006** | Three-bucket retry taxonomy via `RetryingEdge`. No bespoke try/except retry loops. |
| **KDR-008** | FastMCP is the server implementation; tool schemas derive from Pydantic signatures and are the public contract. |
| **KDR-009** | LangGraph's built-in `SqliteSaver` owns checkpoint persistence. Storage layer owns run registry + gate log only — no hand-rolled checkpoint writes. |
| **KDR-013** | User code is user-owned. Externally-registered workflow modules run in-process with full Python privileges; the framework surfaces import errors but does not lint, test, or sandbox them. In-package workflows cannot be shadowed (register-time collision guard). |

The Auditor uses these as drift-check anchors; main-context Claude uses them when the user asks ad-hoc questions about scope.

---

## Repo layout

- `ai_workflows/` — package. Four layered subpackages enforced by `uv run lint-imports`:
  - `primitives/` — storage, cost, tiers, providers, retry, logging.
  - `graph/` — LangGraph adapters (`TieredNode`, `ValidatorNode`, `HumanGate`, `CostTrackingCallback`, `RetryingEdge`, checkpointer).
  - `workflows/` — concrete LangGraph `StateGraph` modules + the `_dispatch` shared helper + `loader` (M16 T01 external-workflow loader).
  - `cli.py` + `mcp/` — the two surfaces.
- `tests/` — pytest, mirrors package structure. Hermetic by default; `AIW_E2E=1` opts into provider-touching tests.
- `design_docs/` — source of truth. `architecture.md`, `roadmap.md`, `nice_to_have.md`, `analysis/`, `adr/`, `phases/milestone_<N>_<name>/{README.md, task_<NN>_<slug>.md, issues/task_<NN>_issue.md}`, `archive/`.
- `evals/` — eval fixture root for the M7 harness.
- `CHANGELOG.md` — Keep-a-Changelog, milestone/task scoped.
- `.claude/{agents,commands,skills}/` — subagents, slash commands, skill packaging.

**Cross-cutting backlog:** there is no `design_docs/issues.md` anymore. Items land as forward-deferred carry-over on the appropriate future task. If a finding spans milestones with no natural owner, file it in the audit issue file with `DEFERRED (owner: TBD)` and surface to the user.

---

## Builder mode (one-paragraph summary)

The Builder implements a task strictly against its spec + issue file (authoritative amendment) + carry-over section (extra ACs from prior audits). No invented scope, no drive-by refactors, no `nice_to_have.md` adoption. Tests for every AC. All gates green before handing off (`uv run pytest`, `uv run lint-imports`, `uv run ruff check`). CHANGELOG entry citing the KDR(s) the task implements. **No commits, PRs, or pushes unless the user asks.** Stop and ask if the spec is ambiguous, an AC is unsatisfiable, or implementing would break prior task behaviour.

Full procedure: see [`.claude/agents/builder.md`](.claude/agents/builder.md).

## Auditor mode (one-paragraph summary)

The Auditor is read-only on source code (write access only to the issue file + target-task carry-over for propagation). Loads the full task scope — not the diff — including `architecture.md` + every cited KDR. **Mandatory** design-drift check before AC grading: every change cross-referenced against the seven load-bearing KDRs and the four-layer rule; drift = HIGH and blocks audit pass. Re-runs every gate from scratch. Grades each AC individually (passing tests ≠ done). Updates the issue file in place — never `_v2`. Every finding carries an Action / Recommendation line.

Full procedure (including issue-file template, severity definitions, forward-deferral propagation, and `nice_to_have.md` boundary): see [`.claude/agents/auditor.md`](.claude/agents/auditor.md).

---

## Threat model (loaded by `security-reviewer`)

ai-workflows is **single-user, local-machine, MIT-licensed**. Two real attack surfaces:

1. **Published wheel on PyPI** (`jmdl-ai-workflows`). What lands in the wheel runs on every downstream consumer's machine via `uvx`. Wheel-contents leakage (secrets, design_docs, tests) is the publish-time threat. The pre-publish dependency-auditor pass is the gate.
2. **Subprocess execution.** Claude Code via OAuth `claude` CLI subprocess (KDR-003); Ollama HTTP at `http://localhost:11434`; LiteLLM dispatching to Gemini / Ollama. Argument injection, timeout enforcement, stderr capture, no `ANTHROPIC_API_KEY` leak.

There is **no** auth, no multi-user surface, no untrusted network, no TLS for `aiw-mcp --transport http` (loopback default; `--host 0.0.0.0` is a documented foot-gun). Per KDR-013, externally-registered workflow code is user-owned — the framework does not police it. Generic web-app concerns (CSRF, sessions, account lockout, rate limiting) are noise.

Full threat model + finding categories: see [`.claude/agents/security-reviewer.md`](.claude/agents/security-reviewer.md).

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
| Slash commands         | `.claude/commands/` (4 files — see top of doc)                      |
| Subagents              | `.claude/agents/` (5 files — see top of doc)                        |

---

## Non-negotiables

These cross-cut every task and apply to ad-hoc edits outside `/clean-implement` too:

- **Layer discipline.** `primitives → graph → workflows → surfaces`. No upward imports. Enforced by `uv run lint-imports`.
- **Seven KDRs.** Violation of any KDR (002/003/004/006/008/009/013 — see the table above) is HIGH at audit. Apply spirit, not just letter.
- **Issue file is authoritative amendment to spec.** If they disagree, the spec wins; call out the conflict first. Deviations go into the issue file.
- **Carry-over section at the bottom of a spec = extra ACs.** Tick each as it lands.
- **Scope discipline.** No invented scope, no drive-by refactors, no `nice_to_have.md` adoption. Adoption requires a new KDR in `architecture.md` plus an ADR — not a task.
- **Docstring discipline.** Every module/class/public function has one. Module docstrings cite the task and relationship to other modules. Inline comments only when *why* is non-obvious.
- **Secrets discipline.** No API keys in committed files. CI `secret-scan` is backstop, not license.
- **Changelog discipline.** Every code- or content-touching task updates `CHANGELOG.md` in the same commit.
- **Status-surface discipline.** Four surfaces flip together at task close: (a) per-task spec `**Status:**` line, (b) milestone README task table row, (c) `tasks/README.md` row if the milestone has one, (d) milestone README "Done when" checkboxes the task satisfies. The Auditor catches drift across them as HIGH (M14 + M16-T01 close-out both surfaced this kind of drift). Cheaper for the Builder to flip them inline than for the Auditor to file the issue.
- **Code-task verification is non-inferential.** For code (Python modules, scripts, surfaces) build-clean is necessary but not sufficient. Every code task spec MUST name an explicit smoke test the Auditor runs (an end-to-end LangGraph run, an MCP tool round-trip, a CLI invocation, a stub-LLM eval). Without one, the spec is incomplete and the audit cannot pass. Inferential claims about runtime behaviour from build success alone are HIGH.
- **Dependency audit gate.** Any commit that touches `pyproject.toml` or `uv.lock` triggers the `dependency-auditor` agent before the commit lands. The pre-publish wheel-contents check is also non-skippable: `uv build` then `unzip -l dist/*.whl` — must contain only `ai_workflows/` + `LICENSE` + `README.md` + `CHANGELOG.md`. No `.env*`, no `design_docs/`, no `runs/`, no `*.sqlite3`. Audit output goes to the originating task's issue file (or the CHANGELOG entry under a `Security` tag if no issue file exists).
- **Propagation discipline.** Forward-deferred items must appear as carry-over in the target task's spec before the audit closes.
- **Ask before** force-push, `reset --hard`, deleting branches, or any other destructive git op.
