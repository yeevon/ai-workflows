# Task 06 — `aiw list-runs` CLI Command

**Status:** 📝 Planned. Reframed on 2026-04-20 — see "Design drift and reframe" below.

## Design drift and reframe (2026-04-20)

The original task specced two commands: `aiw list-runs` and `aiw cost-report <run_id> --by model|tier|provider`. The `cost-report` half was written in the outside-in era, when the tool called Anthropic / Gemini / Ollama APIs directly and per-token dollar cost was real. Post-pivot three stacked problems make the cost-report half unsatisfiable as written — and, more importantly, pointless:

1. **No per-call rows to replay from.** The spec prescribed `CostTracker.from_storage(storage, run_id)` as "pure replay" of per-call `TokenUsage` rows in Storage. M1 Task 05 dropped the `llm_calls` table ([migrations/002_reconciliation.sql](../../../migrations/002_reconciliation.sql)) and M1 Task 08 documented "no per-call SQL row is written from this module anymore" ([cost.py](../../../ai_workflows/primitives/cost.py)). The replay source does not exist.
2. **No `provider` field on `TokenUsage`.** `--by provider` has no data source even with scope expansion; `TokenUsage` carries only `model` + `tier`.
3. **The by-X breakdowns drive zero decisions post-pivot.** Budget cap checks `tracker.total(run_id)` only. `by_tier()` / `by_model()` have no non-test call sites. Under subscription billing (Claude Max OAuth, Gemini Flash free tier, Ollama local) no per-model dollar breakdown drives anything — the `total_cost_usd` scalar is the only cost signal with decision value.

**Decision (2026-04-20, user-approved):** drop `aiw cost-report` from M3 entirely. `aiw list-runs` already surfaces the scalar `total_cost_usd` per row, which is sufficient. The `cost-report` command is moved to [nice_to_have.md §9](../../nice_to_have.md) with concrete triggers: Claude Code Max overages, additional per-token-billed provider integrations, or Gemini moving off its free-tier backup role.

**Not touched by this task:** `CostTracker.by_tier` / `by_model` / `sub_models` stay in `primitives/cost.py`. They have no consumers today but are zero-cost to keep and are covered by existing unit tests; removing them is a separate refactor with its own reasoning.

**M4 impact:** the MCP `get_cost_report` tool in milestone 4 inherits this reframe. When M4 opens, re-spec the tool as total-only (or drop it entirely in favour of a `list_runs`-equivalent structured return).

## What to Build

A single read-only CLI command that lists recorded runs from `SQLiteStorage`. Pure SELECT — no INSERT / UPDATE, no checkpointer, no graph compile, no `CostTracker`.

Aligns with [architecture.md §4.4](../../architecture.md).

## Deliverables

### `ai_workflows/cli.py` — `list_runs` command

```python
@app.command("list-runs")
def list_runs(
    workflow: str | None = typer.Option(None, "--workflow", "-w"),
    status: str | None = typer.Option(None, "--status", "-s"),
    limit: int = typer.Option(20, "--limit", "-n", min=1, max=500),
) -> None:
    """List recorded runs (newest first)."""
```

- Opens `SQLiteStorage.open(default_storage_path())` and calls `storage.list_runs(workflow_filter=..., status_filter=..., limit=...)`. The helper exists under the M1-trimmed Storage surface; add the optional `workflow_filter` parameter — it is a pure SELECT, no schema change, no migration.
- Prints a fixed-width table: `run_id | workflow | status | started_at | cost_usd`. `cost_usd` is `runs.total_cost_usd` when populated; `—` when NULL. Empty result prints header + `(no runs)`.

### Tests

`tests/cli/test_list_runs.py`:

- Empty Storage → prints a header + `(no runs)`.
- Three runs with two different `workflow` values; `--workflow planner` returns exactly the matching subset.
- `--status completed` filter works.
- `--limit 2` caps rows to two.
- Pure-read invariant: row count before vs. after invocation is identical.
- Cost column rendering: `total_cost_usd` scalar on a completed row prints as a dollar figure; NULL prints as `—`.

## Acceptance Criteria

- [ ] `aiw list-runs` supports `--workflow`, `--status`, `--limit`.
- [ ] Command is a pure read: no `INSERT` / `UPDATE` in the Storage SQL it issues.
- [ ] `runs.total_cost_usd` is surfaced in the table; NULL renders as `—`.
- [ ] `uv run pytest tests/cli/test_list_runs.py` green.
- [ ] `uv run lint-imports` 3 / 3 kept.

## Dependencies

- [Task 04](task_04_cli_run.md) — writes the rows this command reads.
- M1 [Task 05](../milestone_1_reconciliation/task_05_trim_storage.md) (`SQLiteStorage`).
- M1 [Task 11](../milestone_1_reconciliation/task_11_cli_stub_down.md) — revives `TODO(M3): aiw list-runs`.
