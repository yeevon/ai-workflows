# Task 04 — `aiw run` CLI Command

**Status:** 📝 Planned.

## What to Build

Revive the `aiw run <workflow> [--input …]` command — currently a `TODO(M3)` stub in [ai_workflows/cli.py](../../../ai_workflows/cli.py) — so that `aiw run planner --goal 'ship M3'` drives the T03 graph end-to-end: creates a run, invokes the `StateGraph` under the `AsyncSqliteSaver` checkpointer, and either prints the completed plan or returns a `{run_id, awaiting: "gate"}` handle the human can resume with [task 05](task_05_cli_resume.md).

Aligns with [architecture.md §4.4](../../architecture.md) (`aiw` surfaces) and §5 (runtime data flow steps 1–6).

## Deliverables

### `ai_workflows/cli.py` — `run` command

```python
@app.command()
def run(
    workflow: str = typer.Argument(..., help="Workflow name registered in ai_workflows.workflows"),
    goal: str = typer.Option(..., "--goal", "-g", help="Planning goal"),
    context: str | None = typer.Option(None, "--context", "-c"),
    max_steps: int = typer.Option(10, "--max-steps"),
    budget_cap_usd: float | None = typer.Option(None, "--budget"),
    run_id: str | None = typer.Option(None, "--run-id", help="Override auto-generated run id"),
) -> None:
    """Execute a workflow end-to-end. Pauses at HumanGate interrupts."""
```

Inside the command:

1. Lazy-import `ai_workflows.workflows.<workflow>` so registration fires. Catch `ModuleNotFoundError` → exit code 2 with a clear message listing registered workflows.
2. Resolve the builder via `ai_workflows.workflows.get(workflow)`.
3. Open `SQLiteStorage` at the default storage path (new helper `default_storage_path()` added here if it does not already exist; mirror the default-path handling in `ai_workflows/graph/checkpointer.py`).
4. Build the async checkpointer via `build_async_checkpointer()` and compile the graph.
5. Build the config dict: `run_id` (new ULID if not supplied), `thread_id=run_id`, `tier_registry` (from a new `planner_tier_registry()` helper that returns the two routes defined in T03 — Gemini Flash), `cost_callback=CostTrackingCallback(cost_tracker=CostTracker(), budget_cap_usd=budget_cap_usd)`, `storage=<handle>`.
6. `await storage.create_run(run_id, workflow, budget_cap_usd)` then `await app.ainvoke({"input": PlannerInput(goal=goal, context=context, max_steps=max_steps)}, cfg)`.
7. If the returned state contains `"__interrupt__"`, print `run_id\nawaiting: gate\nresume with: aiw resume {run_id} --gate-response <approved|rejected>` and exit 0. If it contains `"plan"`, print the plan as formatted JSON + the cost total and exit 0.
8. Wrap the async body in `asyncio.run(...)` so Typer stays sync.

### Tier registry helper

`ai_workflows/workflows/planner.py` gains a `planner_tier_registry() -> dict[str, TierConfig]` helper so both the CLI and the T07 e2e test share one definition. Pulls `GEMINI_API_KEY` at the LiteLLM layer only — the CLI never reads the env var directly (KDR-003 spirit: secrets at provider boundary).

### Tests

`tests/cli/test_run.py` (new file; may need `tests/cli/` to be created):

- `aiw run planner --goal 'x'` (via `CliRunner`) with stubbed `LiteLLMAdapter` drives the full graph to the gate and prints `run_id` + `awaiting: gate`.
- `aiw run unknown_workflow --goal 'x'` exits non-zero with "unknown workflow 'unknown_workflow'; registered: [planner]".
- `aiw run planner` without `--goal` exits 2 (Typer's missing-option error).
- `aiw run planner --goal 'x' --budget 0.00001` trips `BudgetExceeded` and exits non-zero with a budget message.
- The test sets `AIW_CHECKPOINT_DB` + a `tmp_path` Storage DB so runs land under the test tree, not under `~/.ai-workflows/`.

## Acceptance Criteria

- [ ] `aiw run planner --goal '<text>'` runs the T03 graph to either completion or a gate interrupt and prints the expected output.
- [ ] Run id auto-generated (ULID-shape) when `--run-id` not supplied.
- [ ] `Storage.create_run(run_id, "planner", budget)` called exactly once per invocation.
- [ ] Gate interrupt output tells the user the exact `aiw resume` command to run.
- [ ] `--budget` cap enforced end-to-end (trips `BudgetExceeded`, exits non-zero).
- [ ] CLI does not read `GEMINI_API_KEY` directly (KDR-003 boundary — env read stays in `LiteLLMAdapter`).
- [ ] `uv run pytest tests/cli/test_run.py` green; `uv run lint-imports` 3 / 3 kept.

## Dependencies

- [Task 01](task_01_workflow_registry.md) — registry.
- [Task 02](task_02_planner_schemas.md) — `PlannerInput`.
- [Task 03](task_03_planner_graph.md) — `build_planner`.
- M2 [Task 06](../milestone_2_graph/task_06_cost_callback.md) (`CostTrackingCallback`) + M2 [Task 08](../milestone_2_graph/task_08_checkpointer.md) (`build_async_checkpointer`).
- M1 [Task 05](../milestone_1_reconciliation/task_05_trim_storage.md) (`SQLiteStorage`).
- M1 [Task 11](../milestone_1_reconciliation/task_11_cli_stub_down.md) — revives the `TODO(M3): aiw run …` stub.
