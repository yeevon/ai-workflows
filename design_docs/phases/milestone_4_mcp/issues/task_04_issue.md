# Task 04 — `list_runs` Tool — Audit Issues

**Source task:** [../task_04_list_runs.md](../task_04_list_runs.md)
**Audited on:** 2026-04-20
**Audit scope:** `ai_workflows/mcp/server.py` (list_runs body + new Storage imports), `tests/mcp/test_list_runs.py` (new), `tests/mcp/test_scaffold.py` (stub assertion removed), `CHANGELOG.md`. Full gates. `architecture.md` §4.4 + §6, `design_docs/nice_to_have.md §9`, `ai_workflows/primitives/storage.py:397-429` + migration `migrations/001_initial.sql` (DB default check), M4 README (carry-over from M3 T06), `tests/cli/test_list_runs.py` (parity).
**Status:** ✅ PASS — 0 OPEN issues.

---

## Design-drift check (architecture.md + KDRs)

| Concern | Finding |
| --- | --- |
| New dependency added? | **None.** `SQLiteStorage` + `default_storage_path` already in the primitives layer. |
| New module or layer? | No. `ai_workflows.mcp.server` now imports from `ai_workflows.primitives.storage` — surfaces layer may import primitives (§3 four-layer contract). Lint-imports 3/3 KEPT. |
| LLM call added? | No. `list_runs` is a pure read — never compiles a graph, never instantiates a `TieredNode`. Pure-read invariant is test-pinned. |
| Checkpoint / resume logic? | No. Tool never opens the checkpointer (test: row count before == row count after the call). KDR-009 unaffected. |
| Retry logic? | No. |
| Observability? | No change. |
| KDR-002 portable surface | ``list_runs`` mirrors the ``aiw list-runs`` CLI exactly (same filter semantics, same `Storage.list_runs` helper). One contract, two surfaces. ✓ |
| KDR-003 Anthropic boundary | No provider imports added; `grep` for `GEMINI_API_KEY`/`ANTHROPIC_API_KEY`/anthropic against `mcp/server.py` — still clean. Pinned by `tests/mcp/test_run_workflow.py::test_mcp_server_module_does_not_read_provider_secrets`. ✓ |
| KDR-008 FastMCP | Tool signature `async def list_runs(payload: ListRunsInput) -> list[RunSummary]` — FastMCP auto-derives the schema from the pydantic annotations. ✓ |
| KDR-010 bare-typed rule | MCP I/O models are out-of-scope (ADR-0002). `ListRunsInput.limit = Field(default=20, ge=1, le=500)` stays as-is. ✓ |
| M4 README carry-over | ✓ The "M3 T06 reframe — `get_cost_report` MCP tool re-spec" carry-over is honoured: `RunSummary.total_cost_usd` is the sole cost surface; no separate cost-report tool shipped. |

**Verdict:** no drift.

---

## Acceptance-criteria grading

| # | AC | Grade | Evidence |
| --- | --- | --- | --- |
| 1 | `list_runs(ListRunsInput)` returns `list[RunSummary]`, newest first, bounded by `limit` (default 20) | ✅ | `mcp/server.py:105-122` wires the tool; default comes from `ListRunsInput.limit = Field(default=20, ge=1, le=500)`. Newest-first + limit cap pinned by `test_list_runs_limit_caps_and_orders_newest_first` (seeds 5, requests 2, asserts `[r-4, r-3]`). |
| 2 | `workflow` + `status` filters compose with AND | ✅ | Inherited from `SQLiteStorage._list_runs_sync` which ANDs non-None clauses. Individual filters test-pinned: `test_list_runs_workflow_filter_is_exact_match` + `test_list_runs_status_filter_is_exact_match`. (CLI parity adds combined-filter coverage via `tests/cli/test_list_runs.py`.) |
| 3 | `RunSummary.total_cost_usd` populated from `runs.total_cost_usd` (may be `None` for pending / pre-stamping rows) | ✅ | `test_list_runs_total_cost_usd_round_trips` seeds one populated (0.0033) + one forced-NULL (via raw `UPDATE ... SET total_cost_usd = NULL`) and asserts both round-trip correctly. Forced-NULL matches the CLI's own test (`tests/cli/test_list_runs.py:228-248`) because the DB column has `DEFAULT 0.0` (migration 001 line 33). |
| 4 | Tool never opens the checkpointer, never compiles a graph (pure read) | ✅ | Source inspection: `mcp/server.py:105-122` opens only `SQLiteStorage`, calls `storage.list_runs`, returns. No import of `build_async_checkpointer`, no `builder().compile(…)`. Pinned by `test_list_runs_is_pure_read` — row count stable across the call. |
| 5 | `uv run pytest tests/mcp/test_list_runs.py tests/cli/test_list_runs.py` green | ✅ | Focused run: **17 passed** (7 new + 10 existing). Full suite: 320 passed / 1 skipped. |
| 6 | `uv run lint-imports` 3/3 kept; `uv run ruff check` clean | ✅ | Lint-imports: `Contracts: 3 kept, 0 broken.` Ruff: `All checks passed!` |

All 6 ACs pass.

---

## 🔴 HIGH — (none)

## 🟡 MEDIUM — (none)

## 🟢 LOW — (none)

---

## Additions beyond spec — audited and justified

1. **`test_run_summary_field_names_match_storage_row_keys`** — pins the `RunSummary(**row)` construction contract (spec §Deliverables: "Pin the contract in a test"). Asserts the dict keys `Storage.list_runs` returns are a superset of the required `RunSummary` fields, and explicitly pins the six-field set. Catches silent renames on either side. *Justified* — directly implements the spec's "pin the contract" instruction.

2. **Scaffold stub assertion for `list_runs` removed** (`tests/mcp/test_scaffold.py`). *Justified.* Same pattern as T02 / T03 stub-removal; body is wired, so the NotImplementedError assertion no longer holds.

3. **`SQLiteStorage` + `default_storage_path` imports in `mcp/server.py`.** *Justified.* Required by the wired body; matches the spec snippet verbatim. Storage is the primitives layer, which surfaces may import (§3).

No other additions. No new dependencies, no new modules, no new public API beyond what the spec's deliverable snippet already names.

---

## Gate summary

| Gate | Command | Result |
| --- | --- | --- |
| Full pytest | `uv run pytest` | **320 passed, 1 skipped** |
| Focused T04 + CLI parity | `uv run pytest tests/mcp/test_list_runs.py tests/cli/test_list_runs.py` | **17 passed** |
| Layer contract | `uv run lint-imports` | **3/3 contracts kept** |
| Lint | `uv run ruff check` | **All checks passed** |
| KDR-003 boundary | `grep -nE "GEMINI_API_KEY\|ANTHROPIC_API_KEY\|import anthropic\|from anthropic" ai_workflows/mcp/server.py` | **no matches** |

---

## Issue log — cross-task follow-up

None. All T04 ACs closed.

---

## Deferred to nice_to_have

None raised. The absence of a separate `get_cost_report` tool is the M4-kickoff decision documented in `nice_to_have.md §9`, not a T04 deferral.

---

## Propagation status

No forward-deferrals from T04.
