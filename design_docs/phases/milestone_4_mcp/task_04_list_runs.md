# Task 04 — `list_runs` Tool

**Status:** 📝 Planned.

## What to Build

Wire the `list_runs` tool body as a pure read over `SQLiteStorage.list_runs`. Returns `list[RunSummary]`. Each summary carries `total_cost_usd` — this is the **only** cost surface the MCP server exposes (the originally-planned `get_cost_report` tool was dropped at M4 kickoff; see [README.md](README.md) *Goal* + *Carry-over* and [architecture.md §4.4](../../architecture.md)).

Mirrors [ai_workflows/cli.py:588-644](../../../ai_workflows/cli.py) `list-runs` behaviour. Never opens the checkpointer, never compiles a graph.

Aligns with [architecture.md §4.4](../../architecture.md), KDR-008, KDR-009.

## Deliverables

### `ai_workflows/mcp/server.py` — `list_runs` tool body

```python
@mcp.tool()
async def list_runs(payload: ListRunsInput) -> list[RunSummary]:
    """List recorded runs (newest first). Pure read — no graph state touched."""
    storage = await SQLiteStorage.open(default_storage_path())
    rows = await storage.list_runs(
        limit=payload.limit,
        status_filter=payload.status,
        workflow_filter=payload.workflow,
    )
    return [RunSummary(**row) for row in rows]
```

- `RunSummary` field names must match the dict keys returned by `Storage.list_runs` (`run_id`, `workflow_id`, `status`, `started_at`, `finished_at`, `total_cost_usd`). Pin the contract in a test.
- Storage connection handling: follow the same "open per call" pattern the CLI uses. Long-running MCP server instances do not hold a connection handle across tool calls — the cost is one SQLite open per `list_runs`, which is negligible and keeps the tool functions pure.

### Tests

`tests/mcp/test_list_runs.py` (mirror [tests/cli/test_list_runs.py](../../../tests/cli/test_list_runs.py) for parity):

- Empty storage → `list_runs(ListRunsInput())` returns `[]`.
- Seed three rows across two workflows (seed directly via `SQLiteStorage.create_run(...)`); `list_runs(workflow="planner")` returns exactly the planner rows.
- Seed rows with varied statuses; `list_runs(status="completed")` returns exactly the matching subset.
- Seed 5 rows; `list_runs(limit=2)` returns two rows, newest first (assert via `started_at` order).
- Pure-read invariant: row count before + after `list_runs` is identical.
- Cost column: a row with `total_cost_usd=0.0033` round-trips as `0.0033`; a row with `NULL` round-trips as `None` in the pydantic model.

## Acceptance Criteria

- [ ] `list_runs(ListRunsInput)` returns `list[RunSummary]`, newest first, bounded by `limit` (default 20).
- [ ] `workflow` + `status` filters compose with `AND` (reusing `SQLiteStorage.list_runs`'s behaviour).
- [ ] `RunSummary.total_cost_usd` is populated from `runs.total_cost_usd` (may be `None` for pending / pre-stamping rows).
- [ ] Tool never opens the checkpointer, never compiles a graph (pure read).
- [ ] `uv run pytest tests/mcp/test_list_runs.py tests/cli/test_list_runs.py` green (MCP + CLI parity).
- [ ] `uv run lint-imports` 3 / 3 kept; `uv run ruff check` clean.

## Dependencies

- [Task 01](task_01_mcp_scaffold.md) — scaffold + `RunSummary` schema.
- M3 [Task 06](../milestone_3_first_workflow/task_06_cli_list_cost.md) — established the `list-runs` contract this tool mirrors; also the source of the `get_cost_report` drop decision.
