# Task 01 — Workflow Registry — Audit Issues

**Source task:** [../task_01_workflow_registry.md](../task_01_workflow_registry.md)
**Audited on:** 2026-04-20
**Audit scope:** `ai_workflows/workflows/__init__.py`, `tests/workflows/test_registry.py`, `CHANGELOG.md` entry; cross-checked against `design_docs/architecture.md §3`, `§4.3`, and the M3 milestone [README.md](../README.md).
**Status:** ✅ PASS — all ACs met; no OPEN issues.

## Design-drift check

| Vector | Result | Note |
| --- | --- | --- |
| New dependency | ✅ None | Pure stdlib (`collections.abc`, `typing`). |
| New module/layer | ✅ Fits | Extends existing `ai_workflows/workflows/__init__.py`; no new layer introduced. |
| LLM call added | ✅ N/A | No model calls in this task. |
| Checkpoint/resume | ✅ N/A | None added. |
| Retry logic | ✅ N/A | None added. |
| Observability | ✅ N/A | No logger calls; registry is a passive data structure. |
| Four-layer contract | ✅ Holds | `lint-imports`: 3 kept / 0 broken. `workflows` remains a top-of-stack package with no upward imports; `langgraph` not imported at module load (explicitly verified by `test_workflows_module_does_not_import_langgraph`). |
| `nice_to_have.md` items | ✅ None adopted | |

No drift. Task spec says `WorkflowBuilder` is intentionally typed as `Callable[[], Any]` to avoid pulling `langgraph` into the workflows layer at module-import time — implementation honours that.

## AC grading

| # | Acceptance criterion | Grade | Evidence |
| --- | --- | --- | --- |
| 1 | `register`, `get`, `list_workflows`, `_reset_for_tests` exported from `ai_workflows.workflows` | ✅ | [`__init__.py:45-103`](../../../../ai_workflows/workflows/__init__.py) — all four defined at module scope; `__all__` lists public triple. |
| 2 | Duplicate-name with different builder → `ValueError`; identical re-registration is a no-op | ✅ | `register` body lines 63-74; covered by `test_register_conflict_raises_value_error` + `test_register_same_pair_is_idempotent`. |
| 3 | `get` on unknown name → `KeyError` listing known names | ✅ | `get` body lines 80-89; covered by `test_get_unknown_name_lists_known_workflows` + `test_get_unknown_name_when_registry_empty`. |
| 4 | `ai_workflows.workflows` does not import `langgraph` at module load | ✅ | Module imports only stdlib + `__future__`. Verified by `test_workflows_module_does_not_import_langgraph` which pops `ai_workflows.workflows` from `sys.modules`, masks `langgraph*` modules to `None`, and reimports — if any transitive `import langgraph` existed, the re-import would raise `ImportError` (it does not). |
| 5 | `uv run pytest tests/workflows/test_registry.py` green | ✅ | 9 passed in 0.01s. |
| 6 | `uv run lint-imports` stays 3 / 3 kept, 0 broken | ✅ | Audit run confirms 3 kept, 0 broken. |

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

None.

## Additions beyond spec — audited and justified

- `__all__` tuple listing public surface (`WorkflowBuilder`, `register`, `get`, `list_workflows`) — standard Python hygiene; intentionally excludes `_reset_for_tests` which is test-only per the task spec.
- `test_get_unknown_name_when_registry_empty` and `test_list_workflows_empty_returns_empty_list` — minor edge cases under the same AC umbrellas (AC 3 and AC 1 respectively); zero coupling, zero new surface area.

None of these add scope beyond the task file; all fall inside the "reasonable test coverage" envelope.

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 245 passed, 2 warnings (pre-existing `yoyo` datetime deprecation) in 2.58s |
| `uv run pytest tests/workflows/test_registry.py` | ✅ 9 passed in 0.01s |
| `uv run lint-imports` | ✅ 3 contracts kept, 0 broken (21 files, 17 deps analyzed) |
| `uv run ruff check` | ✅ All checks passed |

## Issue log — cross-task follow-up

None. This task ships the registry shape only; concrete workflow registration lands with the planner `StateGraph` in [task 03](../task_03_planner_graph.md), which will call `register("planner", build_planner)` at import time.

## Deferred to nice_to_have

None.

## Propagation status

No deferrals from this audit — no carry-over entries written to downstream tasks.
