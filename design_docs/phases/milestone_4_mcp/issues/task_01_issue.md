# Task 01 — FastMCP Scaffold + Pydantic I/O Models — Audit Issues

**Source task:** [../task_01_mcp_scaffold.md](../task_01_mcp_scaffold.md)
**Audited on:** 2026-04-20
**Audit scope:** `ai_workflows/mcp/__init__.py`, `ai_workflows/mcp/schemas.py`, `ai_workflows/mcp/server.py`, `tests/mcp/test_scaffold.py`, `CHANGELOG.md`, cross-checked against [architecture.md §4.4, §7](../../../architecture.md), [ADR-0002 / KDR-010](../../../adr/0002_bare_typed_response_format_schemas.md), KDR-002, KDR-008, sibling task specs (T02–T08).
**Status:** ✅ PASS — all 8 ACs met, 0 OPEN issues, 3/3 lint-imports contracts kept, ruff clean, 17 scaffold tests green and 307 full-suite tests green.

## Design-drift check (mandatory, per CLAUDE.md)

| Rule | Verdict | Evidence |
| --- | --- | --- |
| New dependency — must appear in [architecture.md §6](../../../architecture.md) or ADR; nice_to_have hard-stop | ✅ No new deps. `fastmcp` listed in [architecture.md §6](../../../architecture.md) (row 129) and already in `pyproject.toml`. |
| New module/layer — must fit four-layer contract | ✅ `ai_workflows.mcp.{schemas,server}` are surfaces; imports only `fastmcp` + `pydantic` + intra-package. `lint-imports` 3/3 kept. |
| LLM call added → must route `TieredNode` + `ValidatorNode` (KDR-004) | ✅ Not applicable — scaffold has no LLM call. Tool bodies raise `NotImplementedError`. |
| `anthropic` SDK / `ANTHROPIC_API_KEY` (KDR-003) | ✅ Not imported; `grep -R "anthropic\|ANTHROPIC_API_KEY" ai_workflows/mcp` clean. |
| Checkpoint logic → must use `SqliteSaver` (KDR-009) | ✅ Not applicable — no checkpoint code in scaffold. |
| Retry logic → three-bucket taxonomy via `RetryingEdge` (KDR-006) | ✅ Not applicable — no retry code in scaffold. |
| Observability → `StructuredLogger` only; no external backends | ✅ Not applicable — no logging added. |
| KDR-010 / ADR-0002 — bare-typed `response_format` | ✅ MCP I/O models are explicitly out-of-scope per ADR-0002. Only bound field is `ListRunsInput.limit: Field(default=20, ge=1, le=500)` — matches the exact example in the task spec and carries the "contract-at-boundary value" justification required by the ADR. |

**Drift verdict:** no drift. No HIGH blockers on architectural grounds.

## AC grading

| # | AC | Verdict | Evidence |
| --- | --- | --- | --- |
| 1 | `ai_workflows/mcp/{server.py,schemas.py,__init__.py}` land; `build_server() -> FastMCP` is the sole public constructor | ✅ | Three files present. `__all__ = ["build_server"]` in `ai_workflows/mcp/__init__.py`; `build_server` is the only export; `ai_workflows/mcp/server.py` only exports `build_server`. |
| 2 | All four tools `@mcp.tool()`-registered with pydantic `*Input` / `*Output` signatures | ✅ | `ai_workflows/mcp/server.py:58-75` — all four decorated; `tests/mcp/test_scaffold.py::test_all_four_tools_registered` pins `{"run_workflow", "resume_run", "list_runs", "cancel_run"}`. |
| 3 | Tool bodies raise `NotImplementedError` with "lands in M4 T0X" message | ✅ | Each stub raises exactly `NotImplementedError("lands in M4 T02" / "T03" / "T04" / "T05")`; tests `test_{run,resume,list,cancel}_*_raises_not_implemented` match on the `M4 T0X` substring. |
| 4 | `build_server()` idempotent on distinct calls (no global mutation) | ✅ | `test_build_server_is_idempotent_and_non_global` asserts `a is not b`. Factory constructs a new `FastMCP("ai-workflows")` per call. |
| 5 | `RunSummary` includes `total_cost_usd` as the single cost surface | ✅ | `ai_workflows/mcp/schemas.py:105-121` — `total_cost_usd: float \| None = None`. Docstring cites M4 kickoff drop of `get_cost_report`. |
| 6 | `uv run pytest tests/mcp/test_scaffold.py` green | ✅ | 17/17 pass in 0.84s (full-suite re-run: 307 passed / 1 skipped). |
| 7 | `uv run lint-imports` 3 / 3 kept | ✅ | `primitives → graph → workflows → surfaces` all kept; 0 broken. |
| 8 | `uv run ruff check` clean | ✅ | "All checks passed!" |

All 8 ACs satisfied.

## Additions beyond spec — audited and justified

- **`test_list_runs_input_limit_bounded`** — not explicitly listed in the T01 spec, but pins the one bounded field (`ListRunsInput.limit`) the spec calls out by name as an example. Cheap, 3 assertions, prevents silent removal of the bound. **Justified.**
- **Subprocess-based `test_mcp_scaffold_import_does_not_pull_langgraph`** — spec asks for an import-side regression guard; straightforward in-process `sys.modules` check was contaminated by sibling suites that already loaded `langgraph`. Subprocess run keeps the guard hermetic and matches the spec's exact wording ("`import ai_workflows.mcp` must not import `langgraph` transitively"). **Justified.**
- **Parametrized `test_schema_roundtrip`** — the spec listed round-trip as one test; parametrizing across all 8 models is mechanical and keeps the guard tight if a field is added later without a round-trip assertion. **Justified.**

No drive-by refactors. No scope creep. No changes outside `ai_workflows/mcp/` + `tests/mcp/` + `CHANGELOG.md`.

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 307 passed, 1 skipped, 2 warnings (pre-existing yoyo deprecation) |
| `uv run pytest tests/mcp/` | ✅ 17 passed |
| `uv run lint-imports` | ✅ 3/3 contracts kept, 0 broken |
| `uv run ruff check` | ✅ All checks passed |

## HIGH

None.

## MEDIUM

None.

## LOW

None.

## Issue log — cross-task follow-up

None. T01 is the scaffold; all real tool bodies are scheduled and owned by the next four tasks (T02–T05), which already carry the corresponding `NotImplementedError("lands in M4 T0X")` tag pointing at them. No forward-deferrals needed.

## Deferred to `nice_to_have.md`

None.

## Propagation status

No forward-deferrals from this audit. Nothing to append as carry-over on downstream task files.
