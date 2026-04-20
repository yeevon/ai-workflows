# Task 02 — Dependency Swap — Audit Issues

**Source task:** [../task_02_dependency_swap.md](../task_02_dependency_swap.md)
**Source audit:** [../audit.md](../audit.md) (produced by [M1 Task 01](../task_01_reconciliation_audit.md))
**Audited on:** 2026-04-19 (cycle 1 post-build audit — overwrites the PENDING BUILDER pre-build file)
**Audit scope:** pyproject.toml diff, uv.lock regeneration, tests/test_scaffolding.py update, CHANGELOG.md entry, full-suite gates, design-drift cross-check against architecture.md §6 + KDR-001/003/005/007/008/009, grep for removed-dep imports surviving elsewhere under `ai_workflows/`.
**Status:** ✅ PASS on T02's explicit ACs **with MEDIUM forward-deferral to T03/T04/T07/T09**. The post-T02 interim state leaves pytest-red on untouched modules (still importing `pydantic_ai` / `anthropic` / `logfire`); those imports are owned by downstream tasks per [audit.md](../audit.md). Milestone-level green gates land at T13.

## Design-drift check

Cross-checked every change against [architecture.md](../../../architecture.md) §6 + KDR-001/003/005/007/008/009.

| Change | Reference | Drift? |
| --- | --- | --- |
| Removed `pydantic-ai>=1.0` | KDR-001, KDR-005 | ✅ Aligned — LangGraph replaces pydantic-ai substrate. |
| Removed `pydantic-graph>=1.0` | KDR-001 | ✅ Aligned — LangGraph owns DAGs. |
| Removed `pydantic-evals>=1.0` | [roadmap.md](../../../roadmap.md) (M7 re-intro); [architecture.md §10](../../../architecture.md) | ✅ Aligned — eval harness deferred. |
| Removed `logfire>=2.0` | [architecture.md §8.1](../../../architecture.md), [nice_to_have.md §1/§3/§8](../../../nice_to_have.md) | ✅ Aligned — `StructuredLogger` is the single observability surface; hosted tracing deferred. |
| Removed `anthropic>=0.40` | KDR-003 | ✅ Aligned — no Anthropic API; Claude access OAuth-only via CLI. |
| Removed `[project.optional-dependencies].dag = ["networkx"]` | KDR-001 | ✅ Aligned — LangGraph replaces hand-rolled DAG primitive. |
| Added `langgraph>=0.2` | [architecture.md §6](../../../architecture.md), KDR-001 | ✅ Aligned — DAG + checkpoint + interrupt substrate. |
| Added `langgraph-checkpoint-sqlite>=1.0` | KDR-009, [architecture.md §4.1/§6](../../../architecture.md) | ✅ Aligned — `SqliteSaver` is the only checkpoint implementation. |
| Added `litellm>=1.40` | KDR-007, [architecture.md §4.1/§6](../../../architecture.md) | ✅ Aligned — unified Gemini + Qwen/Ollama adapter. |
| Added `fastmcp>=0.2` | KDR-008, [architecture.md §4.4/§6](../../../architecture.md) | ✅ Aligned — MCP server ergonomics. |
| Kept `httpx`, `pydantic`, `pyyaml`, `structlog`, `typer`, `yoyo-migrations`, entire `dev` group | [architecture.md §6](../../../architecture.md), [audit.md §2](../audit.md) | ✅ Aligned — every kept dep is named in §6 or has an explicit KEEP row in audit.md. |
| Updated `project.description` | Task spec + audit.md note | ✅ Aligned. |
| Rewired `tests/test_scaffolding.py::test_pyproject_declares_required_dependencies::required` set | Audit.md §3 row for `tests/test_scaffolding.py` (MODIFY → task 02) | ✅ Aligned — row explicitly targets task 02. |

**No new module. No new layer. No LLM call added. No checkpoint logic added. No retry logic added. No observability path added.** Nothing silently adopted from [nice_to_have.md](../../../nice_to_have.md).

Drift check: **clean**.

## Acceptance Criteria grading

| # | AC | Evidence | Verdict |
| --- | --- | --- | --- |
| 1 | `uv sync` completes without error on a fresh clone. | `uv lock` completed (132 packages resolved); subsequent `uv sync` → `Audited 129 packages`. | ✅ |
| 2 | `grep -r pydantic_ai ai_workflows/` returns nothing **after task 03** — flagged as a follow-on check, **not this task's gate**. | Task-spec literal text. The current grep still returns hits (`retry.py` via anthropic, `llm/*`, `tools/*` via pydantic_ai, `logging.py` via logfire — 13 files) — every hit is assigned to a downstream task per [audit.md §1](../audit.md): T03 (`llm/*`), T04 (`tools/*`), T07 (`retry.py`), T09 (`logging.py`). AC as written is not this task's gate. | ✅ (per spec's own exclusion) |
| 3 | No dependency marked REMOVE in the audit remains in `pyproject.toml`. | Post-swap `[project].dependencies` grep for `pydantic-ai`, `pydantic-graph`, `pydantic-evals`, `logfire`, `anthropic` → zero hits. `[project.optional-dependencies]` block is absent entirely (dag extras gone). | ✅ |
| 4 | Every dependency marked ADD in the audit is present with a pinned lower bound. | `langgraph>=0.2`, `langgraph-checkpoint-sqlite>=1.0`, `litellm>=1.40`, `fastmcp>=0.2` all present in `[project].dependencies`. | ✅ |
| 5 | `project.description` no longer mentions pydantic-ai. | `description = "Composable AI workflow framework built on LangGraph + MCP."` | ✅ |
| 6 | CHANGELOG.md notes the dependency swap under `[Unreleased]`. | New `### Changed — M1 Task 02: Dependency swap (2026-04-19)` entry; lists every REMOVE/ADD/KEEP with KDR citations. | ✅ |

All six explicit ACs pass.

## 🟡 MEDIUM — M1-T02-ISS-01: Post-T02 interim gate-red state; forward-deferral propagated

**Finding.** The T02 spec explicitly disclaims the `grep -r pydantic_ai` check as a follow-on for T03 (AC2). Delivering T02 as specified leaves `ai_workflows/` with 13 files that still import removed deps:

| Import surviving | File(s) | Owner task |
| --- | --- | --- |
| `pydantic_ai` | `primitives/llm/model_factory.py`, `primitives/llm/caching.py`, `primitives/llm/types.py` (REMOVE) | [task 03](../task_03_remove_llm_substrate.md) |
| `pydantic_ai` | `primitives/tools/fs.py`, `git.py`, `http.py`, `shell.py`, `stdlib.py`, `registry.py` (REMOVE) | [task 04](../task_04_remove_tool_registry.md) |
| `anthropic` | `primitives/retry.py` (MODIFY) | [task 07](../task_07_refit_retry_policy.md) |
| `logfire` | `primitives/logging.py` (MODIFY) | [task 09](../task_09_logger_sanity.md) |

Consequence — `uv run pytest` collection fails (11 errors + 4 scaffolding assertions) because `ai_workflows.cli` transitively imports `ai_workflows.primitives.logging` which imports `logfire`. `uv run lint-imports` ✅ and `uv run ruff check` ✅ are unaffected.

This is the spec-anticipated critical-path break between T02 (strip deps) and T03/T04/T07/T09 (strip matching imports). [Milestone README](../README.md) exit criterion 1 ("all three gates green") is **milestone-level**, not per-task; T02's own ACs do not list pytest-green.

**Severity rationale — MEDIUM, not HIGH.** No AC unmet; no architectural rule broken; drift-check clean; the gate-red state is literally the contract written into [audit.md §1](../audit.md)'s task-assignment map. MEDIUM captures the forward-deferral bookkeeping only — downstream tasks must know their scope includes restoring pytest-green.

**Action — forward-deferral propagation (CLAUDE.md):**

1. Append carry-over entry to [../issues/task_03_issue.md](task_03_issue.md) — deleting `ai_workflows/primitives/llm/*` closes 3 of the 11 collection errors.
2. Append carry-over entry to [../issues/task_04_issue.md](task_04_issue.md) — deleting `ai_workflows/primitives/tools/*` closes 5 of the 11 collection errors.
3. Append carry-over entry to [../issues/task_07_issue.md](task_07_issue.md) — modifying `primitives/retry.py` to drop the `anthropic` import closes 1 collection error.
4. Append carry-over entry to [../issues/task_09_issue.md](task_09_issue.md) — modifying `primitives/logging.py` to drop the `import logfire` closes the remaining 2 errors + the 4 `test_scaffolding.py` CLI-path assertions.
5. [Task 13 (milestone close-out)](../task_13_milestone_closeout.md) is the gate that verifies all 11 collection errors cleared and full `uv run pytest` returns green.

## Additions beyond spec — audited and justified

_None._ Implementation touched only `pyproject.toml`, `uv.lock` (regenerated), `tests/test_scaffolding.py` (`required` set), and `CHANGELOG.md`. No new modules, no new directories, no new CI steps, no new docs.

## Gate summary

| Gate | Result | Notes |
| --- | --- | --- |
| `uv sync` | ✅ | 132 packages resolved; `Audited 129 packages` on re-sync. |
| `uv run lint-imports` | ✅ | 2 contracts kept (primitives/components barriers). |
| `uv run ruff check` | ✅ | `All checks passed!` |
| `uv run pytest` | ⚠️ RED (expected) | 11 collection errors + 4 `test_scaffolding.py` assertions — all on files owned by T03/T04/T07/T09 per audit.md row assignments. Not a T02 AC (per spec line 40). |
| `uv run pytest tests/test_scaffolding.py` | ⚠️ 4 failed / 23 passed | All 4 failures originate in `ai_workflows.cli` → `ai_workflows.primitives.logging` → `import logfire`; owner = T09. The 23 passing cases cover the dep-set assertion, the import-linter assertion, and the secret-scan regex — all T02-scope concerns pass. |
| `grep -E 'pydantic-ai\|pydantic-graph\|pydantic-evals\|logfire\|anthropic' pyproject.toml` | ✅ zero hits | REMOVE list fully applied. |
| `grep -E 'langgraph\|litellm\|fastmcp' pyproject.toml` | ✅ all present | ADD list fully applied. |
| `grep -r pydantic_ai ai_workflows/` (T02 disclaimed, T03 gate) | ⚠️ 8 hits under `llm/*` + `tools/*` | Scoped to downstream tasks; spec explicitly not this task's gate. |

## Issue log

| ID | Severity | Owner / next touch | Status |
| --- | --- | --- | --- |
| M1-T02-ISS-01 | 🟡 MEDIUM | Forward-deferred to T03, T04, T07, T09; close-out verified by T13 | ✅ **RESOLVED** — all four slices closed: `llm/*` (T03 0d27a85), `tools/*` (T04 ed5c9e6), `retry.py` anthropic (T07 901b67c), `logging.py` logfire (T09 d427bf6); milestone close verified by T13 (607db20) |

## Deferred to nice_to_have

_None._ No finding in this audit maps to [nice_to_have.md](../../../nice_to_have.md).

## Propagation status

ISS-01 forward-deferral (interim pytest-red state) propagated to:

- ✅ [task_03_issue.md — Carry-over from prior audits](task_03_issue.md) — pydantic_ai purge under `primitives/llm/*` — **RESOLVED (T03 0d27a85)**.
- ✅ [task_04_issue.md — Carry-over from prior audits](task_04_issue.md) — pydantic_ai purge under `primitives/tools/*` — **RESOLVED (T04 ed5c9e6)**.
- ✅ [task_07_issue.md — Carry-over from prior audits](task_07_issue.md) — anthropic import removal from `primitives/retry.py` — **RESOLVED (T07 901b67c)**.
- ✅ [task_09_issue.md — Carry-over from prior audits](task_09_issue.md) — logfire removal from `primitives/logging.py` + restore of `test_scaffolding.py` CLI-path assertions — **RESOLVED (T09 d427bf6)**.

All four slices closed. Full suite green at milestone close (T13 607db20, 148 passed).
