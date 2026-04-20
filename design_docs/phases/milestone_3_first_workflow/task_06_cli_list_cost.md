# Task 06 — `aiw list-runs` + `aiw cost-report` CLI Commands

**Status:** 📝 Planned.

## What to Build

Two read-only CLI commands that surface the data already sitting in `SQLiteStorage` and `CostTracker`. Neither writes state; both revive `TODO(M3)` stubs in [ai_workflows/cli.py](../../../ai_workflows/cli.py).

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

- Reads `Storage.list_runs(workflow=..., status=..., limit=...)`. If that helper does not exist yet under the M1-trimmed Storage surface, add it here — it is a pure SELECT.
- Prints a fixed-width table: `run_id | workflow | status | started_at | cost_usd`. Cost is the cached column on `runs` if present, else "—".

### `ai_workflows/cli.py` — `cost_report` command

```python
@app.command("cost-report")
def cost_report(
    run_id: str = typer.Argument(...),
    by: str = typer.Option("model", "--by", help="model | tier | provider"),
) -> None:
    """Emit a cost rollup for a single run."""
```

- Rebuilds a `CostTracker` from the per-call `TokenUsage` rows persisted in Storage (new helper `CostTracker.from_storage(storage, run_id)` — add if missing; pure replay, not a new primitive).
- Prints `total`, `by <dimension>` buckets, and `model_usage` sub-rows when the dimension is `model`.

### Tests

`tests/cli/test_list_runs.py`:

- Empty Storage → prints a header + "(no runs)".
- Three runs with two different `workflow` values; `--workflow planner` returns exactly the matching subset.
- `--status completed` filter works.
- `--limit 2` caps rows to two.

`tests/cli/test_cost_report.py`:

- Seed Storage with three `TokenUsage` rows (two on the same model). `aiw cost-report <run_id>` prints a total equal to the sum and an "(n) by model" rollup line per model.
- Unknown `run_id` exits 2 with "no run found".
- `--by tier` groups by the tier name recorded on each row.

## Acceptance Criteria

- [ ] `aiw list-runs` supports `--workflow`, `--status`, `--limit`.
- [ ] `aiw cost-report <run_id>` supports `--by model | tier | provider`.
- [ ] Both commands are pure reads: no `INSERT` / `UPDATE` in the Storage SQL they issue.
- [ ] `aiw cost-report` totals match the sum of `TokenUsage.cost_usd` rows for the run (asserted in tests).
- [ ] `uv run pytest tests/cli/test_list_runs.py tests/cli/test_cost_report.py` green.
- [ ] `uv run lint-imports` 3 / 3 kept.

## Dependencies

- [Task 04](task_04_cli_run.md) — writes the rows these commands read.
- M1 [Task 05](../milestone_1_reconciliation/task_05_trim_storage.md) (`SQLiteStorage`) + M1 [Task 08](../milestone_1_reconciliation/task_08_prune_cost_tracker.md) (`CostTracker`, `TokenUsage`).
- M1 [Task 11](../milestone_1_reconciliation/task_11_cli_stub_down.md) — revives `TODO(M3): aiw list-runs / cost-report`.
