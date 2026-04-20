# Task 05 — `aiw resume` CLI Command

**Status:** 📝 Planned.

## What to Build

The `aiw resume <run_id> [--gate-response …]` command. Rehydrates a run from the `AsyncSqliteSaver` checkpoint written by [task 04](task_04_cli_run.md) and clears a pending `HumanGate` via `Command(resume=<response>)`, completing the graph to the artifact.

Aligns with [architecture.md §4.4](../../architecture.md) + KDR-009 (LangGraph owns resume).

## Deliverables

### `ai_workflows/cli.py` — `resume` command

```python
@app.command()
def resume(
    run_id: str = typer.Argument(..., help="Run id returned by `aiw run`"),
    gate_response: str = typer.Option("approved", "--gate-response", "-r"),
) -> None:
    """Rehydrate a checkpointed run and clear the pending HumanGate."""
```

Inside the command:

1. Open `SQLiteStorage` and call `await storage.get_run(run_id)` — exit 2 with a clear "no run found" message if missing.
2. Re-derive the workflow name from the `runs` row (`workflow` column persisted by T04).
3. Lazy-import the workflow module and resolve the builder via `ai_workflows.workflows.get(...)`.
4. Build the same config shape as T04 (tier registry, cost callback seeded from the stored cost, Storage handle, `thread_id=run_id`). Budget cap is read back from the `runs` row.
5. Compile the graph against `build_async_checkpointer()` and call `await app.ainvoke(Command(resume=gate_response), cfg)`.
6. Print the final state:
   - If artifact written: print the plan JSON + cost total.
   - If gate rejected the plan: print the rejection + the cost total + exit code 1.
   - If another gate fires (re-interrupt): print the same "awaiting: gate …" block as T04.

### Tests

`tests/cli/test_resume.py`:

- Happy path: `aiw run` (paused at gate) → `aiw resume <id>` → artifact written, exit 0. Stubbed `LiteLLMAdapter`, stubbed Storage under `tmp_path`.
- Unknown `run_id` → exit 2 with "no run found".
- `--gate-response rejected` → no artifact written, exit 1.
- Missing checkpoint (Storage row exists but the checkpoint file was hand-deleted) → exit 1 with LangGraph's surfaced error, not a traceback.
- `Storage.update_run_status(run_id, "completed")` (or equivalent closer helper — add one if missing) called exactly once per successful resume.

## Acceptance Criteria

- [ ] `aiw resume <run_id>` rehydrates from `AsyncSqliteSaver` and completes a gate-paused `planner` run.
- [ ] `--gate-response` is forwarded verbatim to `Command(resume=...)`.
- [ ] Unknown `run_id` exits 2 with a helpful message (no traceback).
- [ ] `Storage` run-status row flips to `completed` on success, `gate_rejected` on rejection.
- [ ] Cost tracker reseeded from the stored cost so `--budget` caps carry across `run` + `resume`.
- [ ] `uv run pytest tests/cli/test_resume.py` green; `uv run lint-imports` 3 / 3 kept.

## Dependencies

- [Task 04](task_04_cli_run.md) — shares the config-builder helpers.
- M2 [Task 05](../milestone_2_graph/task_05_human_gate.md) (`human_gate` interrupt shape) + [Task 08](../milestone_2_graph/task_08_checkpointer.md).
- M1 [Task 05](../milestone_1_reconciliation/task_05_trim_storage.md) (`SQLiteStorage` run registry).
- M1 [Task 11](../milestone_1_reconciliation/task_11_cli_stub_down.md) — revives the `TODO(M3): aiw resume …` stub.
