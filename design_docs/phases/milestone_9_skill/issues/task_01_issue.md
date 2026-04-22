# Task 01 — `.claude/skills/ai-workflows/SKILL.md` + Supporting Files — Audit Issues

**Source task:** [../task_01_skill_md.md](../task_01_skill_md.md)
**Audited on:** 2026-04-21
**Audit scope:** new SKILL.md + shape tests + CHANGELOG entry; cross-check of frontmatter, body sections, MCP schema fidelity, KDR-002 packaging-only invariant, KDR-003 guardrail.
**Status:** ✅ PASS — Cycle 2/10. ISS-01 🟢 LOW (SKILL.md fallback-gate paragraph accuracy) resolved via inline rewrite. Gates re-run green; no OPEN issues remain.

## Design-drift check

Cross-check against [architecture.md](../../../architecture.md) + cited KDRs.

| Concern | Finding |
| --- | --- |
| New dependency | None. `pyyaml>=6.0` already in `[project].dependencies` (loaded for evals / fixtures); SKILL.md frontmatter parse reuses it. |
| New `ai_workflows.*` module | None. Zero code added under `ai_workflows/`. Packaging-only invariant honoured per KDR-002. |
| New layer / contract | None. `uv run lint-imports` still reports 4 contracts kept. |
| LLM call added | None. The skill never invokes a model directly; every action is an MCP call or `aiw` shell-out (KDR-004 not relevant here). |
| Checkpoint / resume logic | None. |
| Retry logic | None. |
| Observability backend | None. |
| Anthropic API surface | Grepped SKILL.md body: `ANTHROPIC_API_KEY` absent; `anthropic.com/api` absent. KDR-003 guardrail honoured. The explicit "No Anthropic API" body note naming the `planner-synth` OAuth tier is correct. |
| Packaging-only (KDR-002) | Honoured. The skill file is under `.claude/skills/…`, not under `ai_workflows.*`; tests live under `tests/skill/`. No module added to the primitives / graph / workflows / surfaces layers. |
| Architecture.md §4.4 fidelity | Skill documents the four M4 tools (`run_workflow`, `resume_run`, `list_runs`, `cancel_run`). Signatures match `ai_workflows/mcp/schemas.py` field-for-field (checked against `RunWorkflowInput` / `ResumeRunInput` / `ListRunsInput` / `CancelRunInput`). |

No drift. No HIGH findings.

## Acceptance criteria grading

| # | Criterion | Verdict |
| --- | --- | --- |
| 1 | SKILL.md exists with YAML frontmatter + 5 body sections | ✅ `.claude/skills/ai-workflows/SKILL.md` has `name` + `description` frontmatter and all five section headings (*When to use*, *Primary surface — MCP*, *Fallback surface — CLI*, *Gate pauses*, *What this skill does NOT do*). |
| 2 | Every action resolves to MCP call or `aiw` shell-out; no Python import or direct LLM call | ✅ Body contains only MCP tool call examples and `uv run aiw …` commands. No Python code, no provider API reference. |
| 3 | No new runtime or dev dependency (`pyproject.toml` diff empty) | ✅ `git diff pyproject.toml` empty. |
| 4 | No new `ai_workflows.*` module; no new import-linter contract; 4 contracts kept | ✅ `uv run lint-imports` → 4 kept, 0 broken. Zero `ai_workflows/` diff. |
| 5 | Every listed test passes under `uv run pytest tests/skill/test_skill_md_shape.py` | ✅ 5 passed in 0.90s. Each test maps 1-1 to the spec's test list (exists, frontmatter, four MCP tools, registered workflows, KDR-003 guardrail). |
| 6 | `uv run pytest` + `uv run lint-imports` + `uv run ruff check` all clean | ✅ 597 passed / 5 skipped / 2 unrelated yoyo deprecation warnings; lint-imports 4 kept; ruff clean. |

## 🔴 HIGH

*None.*

## 🟡 MEDIUM

*None.*

## 🟢 LOW

### M9-T01-ISS-01 — Gate-pauses paragraph overstates what `list_runs` exposes (RESOLVED — Cycle 2)

**Where:** `.claude/skills/ai-workflows/SKILL.md` §*Gate pauses*, fallback-gate bullet (lines 100-111 post-fix).

**Observation (Cycle 1):** The paragraph read "the reason (failing tier, retry count) lives in the run's state keys and is visible to the operator via `list_runs` or a direct Storage read." `RunSummary` (the `list_runs` row shape in [ai_workflows/mcp/schemas.py:125-141](../../../../ai_workflows/mcp/schemas.py#L125-L141)) carries only `run_id`, `workflow_id`, `status`, `started_at`, `finished_at`, `total_cost_usd` — no gate-reason column. `list_runs` surfaces *that* the run is pending (via `status`), not *why*. The state keys `_ollama_fallback_reason` / `_ollama_fallback_count` live in the LangGraph checkpointer, not in the `runs` Storage table, and the MCP surface does not project them.

**Severity:** 🟢 LOW (doc accuracy; does not block any AC — the skill still correctly routes gate responses through `resume_run`).

**Resolution (Cycle 2):** Paragraph rewritten inline. New wording:

> "The signal is the `run_workflow` (or `resume_run`) response itself: `status="pending"` + `awaiting="gate"`, same shape as the regular plan-review pause. `list_runs` will show the row as `status="pending"` but does *not* project the failing-tier detail — the reason (`_ollama_fallback_reason`, `_ollama_fallback_count`) lives in the LangGraph checkpointer state, not in the `runs` registry."

The four-MCP-tools shape test + registered-workflows test still green after the edit (5/5 tests passing). `_ollama_fallback_reason` substring added to the body is not a regression — the existing tests assert *presence* of MCP tool names + workflow names + absence of the Anthropic API surface; none of them forbid additional technical identifiers. No test churn needed.

## Additions beyond spec — audited and justified

- **CHANGELOG entry body is longer than a one-liner.** Lists files touched, per-AC satisfaction, and "No deviation from spec." Matches the M8 T01-T06 CHANGELOG entry style; neutral on audit grade.
- **`tests/skill/__init__.py` scaffold.** Pytest's package-discovery pattern matches other `tests/<subdir>/` dirs. Zero behaviour; package marker only.

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 592 passed, 5 skipped (Cycle 2 re-run) |
| `uv run pytest tests/skill/` | ✅ 5 passed |
| `uv run lint-imports` | ✅ 4 contracts kept |
| `uv run ruff check` | ✅ clean |
| `pyproject.toml` diff | ✅ empty (no dep change) |
| `ai_workflows/*` diff | ✅ empty (packaging-only invariant honoured) |

## Issue log

| ID | Severity | Status | Owner |
| --- | --- | --- | --- |
| M9-T01-ISS-01 | 🟢 LOW | RESOLVED (Cycle 2) | this task |

## Deferred to nice_to_have

*None.*

## Propagation status

*No forward deferrals.* ISS-01 resolved in-task at Cycle 2.
