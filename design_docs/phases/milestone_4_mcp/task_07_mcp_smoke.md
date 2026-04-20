# Task 07 — In-Process Smoke Test (All Four Tools)

**Status:** 📝 Planned.

## What to Build

One in-process smoke test that drives all four MCP tools end-to-end against a stubbed tier registry (no live API). Fulfils [README.md exit criterion 4](README.md): *"One smoke test drives the server in-process (no subprocess) through all four tools."*

Contrast with [M3 Task 07](../milestone_3_first_workflow/task_07_e2e_smoke.md): that one is `AIW_E2E=1`-gated and hits real Gemini. This one is **hermetic** and always runs as part of `uv run pytest`. The two together provide the full coverage story — hermetic tool-surface validation here, live-provider validation via the M3 e2e path.

Aligns with [README.md exit criterion 4](README.md), KDR-008.

## Deliverables

### `tests/mcp/test_server_smoke.py`

```python
@pytest.mark.asyncio
async def test_mcp_server_all_four_tools(tmp_path, monkeypatch):
    """Drive run_workflow → list_runs → resume_run → cancel_run in-process.

    Stubs the tier registry so no live provider call happens. Verifies the
    full MCP surface answers end-to-end and Storage state is coherent across
    all four tools.
    """
```

Test body (sketch):

1. `_redirect_default_paths` fixture (pattern from [tests/cli/test_run.py](../../../tests/cli/test_run.py)) points `AIW_STORAGE_DB` + `AIW_CHECKPOINT_DB` under `tmp_path`.
2. Stub `planner_tier_registry()` to return a deterministic fake tier that produces canned JSON (same pattern used by T02's tests; may be liftable into a shared test fixture under `tests/mcp/conftest.py`).
3. `build_server()` → grab the four tool callables via FastMCP's in-process dispatch API.
4. **`run_workflow`** — invoke with `workflow="planner"` + a short goal. Assert response has `status="pending"`, `awaiting="gate"`, `run_id` set.
5. **`list_runs`** — invoke with no filters. Assert the returned list contains a `RunSummary` for the run id from step 4, status `"pending"`, `total_cost_usd` populated (non-None).
6. **`resume_run`** — invoke with the same `run_id`, `gate_response="approved"`. Assert response has `status="completed"`, `plan` populated, `total_cost_usd` rolled up.
7. **`list_runs` again** — assert the same row now shows `status="completed"`.
8. **`cancel_run` on an already-completed run** — assert `status="already_terminal"`; `list_runs` still shows `completed` (no mutation).
9. **Full cancel path (second run):** `run_workflow` pauses at gate → `cancel_run` flips to `cancelled` → `resume_run` refuses with a clear error.

### Shared fixtures

If repeat setup across the T02–T05 tests and T07's smoke makes `tests/mcp/conftest.py` worth extracting, land it here. Candidate fixtures:

- `_mcp_paths` — redirect storage + checkpoint DBs under `tmp_path`.
- `_stubbed_tier_registry` — monkeypatch `planner.planner_tier_registry` to a deterministic fake.
- `mcp_server` — yields `build_server()` and the four tool callables.

Decision at task start: if T02–T05 already carry inline fixtures and lifting them costs more LOC than it saves, skip the extract and inline T07's setup too.

## Acceptance Criteria

- [ ] `tests/mcp/test_server_smoke.py` drives all four tools end-to-end in-process.
- [ ] No live API call — stubbed tier registry pins hermeticity.
- [ ] Storage state remains coherent across the tool call sequence (run_id round-trips across `run_workflow` → `list_runs` → `resume_run` → `cancel_run`).
- [ ] Cancel-then-resume refusal is exercised end-to-end.
- [ ] `uv run pytest` (no `AIW_E2E` set) picks up and runs this test — not gated.
- [ ] `uv run pytest tests/mcp/` green (this file + all T01–T05 tests).
- [ ] `uv run lint-imports` 3 / 3 kept; `uv run ruff check` clean.

## Dependencies

- [Tasks 01–05](README.md) — all four tools implemented.
- M3 [Task 03](../milestone_3_first_workflow/task_03_planner_graph.md) — `build_planner` is what the smoke test dispatches against.
