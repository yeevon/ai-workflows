# Task 07 — In-Process Smoke Test (All Four Tools) — Audit Issues

**Source task:** [../task_07_mcp_smoke.md](../task_07_mcp_smoke.md)
**Audited on:** 2026-04-20
**Audit scope:** `tests/mcp/test_server_smoke.py` (new), `CHANGELOG.md`. Full gates (`uv run pytest`, `uv run lint-imports`, `uv run ruff check`). Cross-referenced against M4 README exit criterion 4 ("One smoke test drives the server in-process…"), `architecture.md §3` (layer contract), KDR-008, sibling MCP tests (`tests/mcp/test_resume_run.py`, `tests/mcp/test_cancel_run.py`, `tests/mcp/test_list_runs.py`) for fixture consistency, M3 [`tests/e2e/test_planner_smoke.py`](../../../../tests/e2e/test_planner_smoke.py) as the sibling live-provider coverage path.
**Status:** ✅ PASS — 0 OPEN issues.

---

## Design-drift check (architecture.md + KDRs)

| Concern | Finding |
| --- | --- |
| New dependency added? | **None.** New test uses only already-installed packages. |
| New module or layer? | No. Test lives under `tests/mcp/` alongside T01–T06 tests. Imports only what sibling tests already import. Lint-imports 3/3 KEPT. |
| LLM call added? | **No live call.** The test scripts a `_StubLiteLLMAdapter` and monkeypatches `tiered_node_module.LiteLLMAdapter` at fixture scope. `_reset_stub` autouse fixture guarantees no cross-test script leakage. Hermeticity pinned by spec AC 2. |
| Checkpoint / resume logic? | The test drives `resume_run` via the MCP surface — it does not add new checkpoint code. KDR-009 unaffected. |
| Retry logic? | No change. |
| Observability? | No change. |
| KDR-002 MCP portable surface | The test validates the full four-tool tour in-process: ``run_workflow → list_runs → resume_run → list_runs → cancel_run → run_workflow → cancel_run → resume_run``. Matches the spec's step-by-step narrative exactly. ✓ |
| KDR-003 Anthropic boundary | No provider imports added. The stub is a LiteLLM-adapter replacement, not an Anthropic SDK touch. ✓ |
| KDR-008 FastMCP | Test dispatches via `server.get_tool(name).fn(...)` — the same in-process access pattern T03 / T05 tests use, which matches FastMCP's tool-registry API (`FunctionTool.fn`). ✓ |
| Hermetic — always runs | Test is not gated by `AIW_E2E`. Full `uv run pytest` picks it up (332 passed / 1 skipped — the skipped one is the M3 e2e smoke, not this). ✓ |

**Verdict:** no drift.

---

## Acceptance-criteria grading

| # | AC | Grade | Evidence |
| --- | --- | --- | --- |
| 1 | Test drives all four tools end-to-end in-process | ✅ | `test_mcp_server_all_four_tools_end_to_end` resolves all four tools via `server.get_tool(...)` and exercises each: `run_workflow` (step 1, step 6), `list_runs` (step 2, step 4, step 5-verify, step 6-verify), `resume_run` (step 3, step 6-refused), `cancel_run` (step 5, step 6). |
| 2 | No live API call — stubbed tier registry pins hermeticity | ✅ | `_StubLiteLLMAdapter` monkeypatched into `ai_workflows.graph.tiered_node.LiteLLMAdapter` via autouse fixture `_reset_stub`. Scripted responses in lines 152-155 + 202-205 feed the two tiered calls per planner run. The stub raises `AssertionError("stub script exhausted")` on overflow — a leak to a live API would instead surface as a Gemini call, which the test harness has no credentials for in `uv run pytest`. |
| 3 | Storage state coherent across the tool-call sequence | ✅ | `run_id="smoke-run-1"` round-trips: created in step 1, surfaced in step 2's `list_runs`, resumed in step 3, re-listed in step 4 with the new `status="completed"`, cancel-no-op'd in step 5 with `list_runs` confirming unchanged status. `run_id="smoke-run-2"` similarly round-trips through the cancel path and surfaces in `list_runs(status="cancelled")` in the final assertion. |
| 4 | Cancel-then-resume refusal exercised end-to-end | ✅ | Step 6: `cancel_run("smoke-run-2")` returns `"cancelled"`, then `resume_run("smoke-run-2")` raises `ToolError` whose message contains both `"cancelled"` and `"smoke-run-2"`. Exercises the T03 precondition guard exactly as T05 AC-4 intended, but at the top-level MCP surface. |
| 5 | `uv run pytest` (no `AIW_E2E` set) picks up and runs this test — not gated | ✅ | Full `uv run pytest` → **332 passed, 1 skipped** (the one skipped is the pre-existing `tests/e2e/test_planner_smoke.py`, not this file). No `pytest.mark.skipif` / `@pytest.mark.e2e` on the new test. |
| 6 | `uv run pytest tests/mcp/` green (file + T01–T05 tests) | ✅ | Focused MCP-tree run: **38 passed** across all T01–T07 files. |
| 7 | `uv run lint-imports` 3/3 kept; `uv run ruff check` clean | ✅ | Lint-imports: `Contracts: 3 kept, 0 broken.` Ruff: `All checks passed!` |

All 7 ACs pass.

---

## 🔴 HIGH — (none)

## 🟡 MEDIUM — (none)

## 🟢 LOW — (none)

---

## Additions beyond spec — audited and justified

1. **Post-cancel `list_runs(status="cancelled")` filter check** (final 2 lines). *Justified.* Closes the step-6 narrative by verifying the storage filter catches the newly-cancelled row end-to-end — the single extra assertion exercises both ``list_runs``'s status filter and the `cancel_run` → row-state cohesion in one line. No scope creep.

2. **Cost assertions** (`total_cost_usd == pytest.approx(0.0033)`) after both `run_workflow` and `list_runs`. *Justified.* Pins the end-to-end cost roll-up — the sum of the two scripted stub costs (0.0012 + 0.0021) must land in the `runs.total_cost_usd` column and survive through `list_runs`. This is the AC-3 "coherent" clause made concrete for the cost column specifically.

3. **Explicit decision to not extract a `tests/mcp/conftest.py`** (documented in the module docstring + in the T07 CHANGELOG entry). *Justified.* The spec explicitly permits either path ("Decision at task start: if T02–T05 already carry inline fixtures and lifting them costs more LOC than it saves, skip the extract and inline T07's setup too"). The Builder chose skip — the CHANGELOG entry documents the decision and the trigger ("Revisit if T08 / M5 adds a 5th duplicate") so a future Builder has context. Matches the /clean-implement convention for recording validated judgment calls.

No other additions. No new dependencies, no new modules, no new public API.

---

## Gate summary

| Gate | Command | Result |
| --- | --- | --- |
| Full pytest | `uv run pytest` | **332 passed, 1 skipped** |
| Focused T07 | `uv run pytest tests/mcp/test_server_smoke.py` | **1 passed** |
| MCP-tree | `uv run pytest tests/mcp/` | **38 passed** |
| Layer contract | `uv run lint-imports` | **3 / 3 contracts kept** |
| Lint | `uv run ruff check` | **All checks passed** |

---

## Issue log — cross-task follow-up

None. All T07 ACs closed.

---

## Deferred to nice_to_have

None raised.

---

## Propagation status

No forward-deferrals from T07.
