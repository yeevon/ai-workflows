# Task 04 — CLI Surface (`aiw eval capture` + `aiw eval run`)

**Status:** 📝 Planned.
**Grounding:** [milestone README §Exit criteria 2 + 3](README.md) · [architecture.md §4.4](../../architecture.md) · [KDR-002](../../architecture.md) (portable surface — CLI is a consumer of `_dispatch` + `evals`, never the other way around).

## What to Build

Two new subcommands under an `aiw eval` Typer sub-app:

```
aiw eval capture --run-id <run_id> --dataset <name> [--output-root <path>]
aiw eval run <workflow_id> [--live] [--dataset <name>] [--fail-fast]
```

**No MCP surface changes** — eval tools stay CLI-only at M7. MCP is reserved for workflow orchestration; packaging evals as MCP tools is a future decision (nice_to_have-grade) if and when an MCP host wants to drive the eval loop.

## Deliverables

### [ai_workflows/cli.py](../../../ai_workflows/cli.py)

- Register a `typer.Typer()` sub-app `eval_app` and attach it with `app.add_typer(eval_app, name="eval")`.
- Two commands on `eval_app`:

#### `aiw eval capture`

```python
@eval_app.command("capture")
def capture(
    run_id: str = typer.Option(..., "--run-id"),
    dataset: str = typer.Option(..., "--dataset"),
    output_root: Path = typer.Option(Path("evals"), "--output-root"),
) -> None:
    """Snapshot every LLM-node call from a completed run into fixture JSON."""
```

Implementation: open `SQLiteStorage.open(default_storage_path())`, confirm `runs.status == "completed"` for `run_id`, then **replay the run against the checkpointed state** using the existing `AsyncSqliteSaver` checkpoint — NOT a fresh live invocation. The capture path reconstructs the inputs + outputs from checkpoint channels, not from re-firing providers. Rationale: deterministic capture that never costs money, never requires live provider auth, and always produces the bytes the completed run actually exchanged.

If the above reconstruction turns out to be more work than the task's allotment (LangGraph's checkpoint-channel API may not expose enough to reconstruct LLM prompt + response directly), the Builder's fallback plan is to use `AIW_CAPTURE_EVALS` + re-run the workflow with the same `run_id` — but this costs live provider calls and is the **second-choice** mechanism. Decide at Builder time; capture the decision in the CHANGELOG.

#### `aiw eval run`

```python
@eval_app.command("run")
def run(
    workflow_id: str = typer.Argument(...),
    live: bool = typer.Option(False, "--live"),
    dataset: str | None = typer.Option(None, "--dataset"),
    fail_fast: bool = typer.Option(False, "--fail-fast"),
) -> None:
    """Replay the eval suite against the current graph. Exit 0 on all-pass, 1 on any fail."""
```

Implementation:

1. Resolve `workflow_id` against the workflow registry (fail fast on unknown).
2. Load the suite via `load_suite(workflow_id)`; if `dataset` is given, scope to `evals/<dataset>/<workflow_id>/...`.
3. If `--live`, require `AIW_EVAL_LIVE=1` + `AIW_E2E=1` in env (surface the same skip-with-reason message shape as the existing e2e smoke suites); else deterministic.
4. Construct `EvalRunner(mode=...)`, call `run(suite)` via `asyncio.run`, print `report.summary_lines()` to stdout, exit `0 / 1`.
5. `--fail-fast` stops iteration on first failure (useful for local CI-sim runs).

### Output format

Structured, human + CI friendly. Modeled on pytest's short summary:

```
M7 eval replay — planner (deterministic)
  PASS planner-explorer-happy-01    (0.04s)
  PASS planner-synth-happy-01       (0.12s)
  FAIL slice-worker-happy-01        (0.03s)
    expected_output.summary: ...<unified diff>...

Summary: 2 passed, 1 failed.
```

stdout only. `--json` flag **not** landed at M7 — deferred until CI wants machine-readable output (nice_to_have-grade addition).

### Tests

[tests/cli/test_eval_commands.py](../../../tests/cli/test_eval_commands.py):

- `test_eval_run_all_pass_exit_zero` — seeded passing fixture suite, deterministic mode, exit 0.
- `test_eval_run_any_fail_exit_one` — one broken fixture, deterministic, exit 1.
- `test_eval_run_unknown_workflow_exits_two` — `aiw eval run bogus` exits 2 with a readable error (matches the M3 T04 `--tier-override` unknown-name convention).
- `test_eval_run_live_requires_both_env_vars` — `--live` without `AIW_EVAL_LIVE=1` or without `AIW_E2E=1` exits 2 with a clear skip-reason; live-gated execution path covered by T03's test_runner_live, not here.
- `test_eval_capture_requires_completed_run` — seed a `runs.status=pending` row; `aiw eval capture --run-id X` exits 2.
- `test_eval_capture_writes_fixtures_under_dataset_path` — happy path with a checkpointed completed run (reuse the M3 T04 fixture pattern of direct `SQLiteStorage.create_run` + a fake completed checkpoint channel); verify JSON files land at `evals/<dataset>/<workflow>/<node>/*.json`.

Autouse fixtures mirror the M3 T04 / M3 T06 pattern (`_redirect_default_paths` + `AIW_STORAGE_DB` + `AIW_CHECKPOINT_DB` under `tmp_path`).

### CLI help surface

`aiw eval --help` lists `capture` + `run`; `aiw --help` includes the `eval` sub-group. Confirm via a smoke test that asserts the help output contains both subcommand names.

## Acceptance Criteria

- [ ] `aiw eval capture --run-id <id> --dataset foo` writes fixture JSON for every LLM-node call in the named completed run; exits 2 on unknown / non-completed run_id.
- [ ] `aiw eval run planner` runs deterministic replay, prints a per-case summary, exits 0 all-pass / 1 any-fail.
- [ ] `aiw eval run planner --live` refuses cleanly unless **both** `AIW_EVAL_LIVE=1` and `AIW_E2E=1` are set.
- [ ] `aiw eval` subcommand group surfaces under `aiw --help`.
- [ ] Shared-dispatch discipline kept: the CLI constructs `EvalRunner` from `ai_workflows.evals` and does **not** reimplement replay logic. (Layer contract: `cli` imports `evals` + `workflows` + `primitives`; confirmed by import-linter.)
- [ ] `uv run pytest && uv run lint-imports && uv run ruff check` green.

## Dependencies

- [Task 01](task_01_dataset_schema.md) — schemas.
- [Task 02](task_02_capture_callback.md) — capture callback (if the checkpoint-reconstruction path turns out infeasible, T04 falls back onto `CaptureCallback` + re-run).
- [Task 03](task_03_replay_runner.md) — `EvalRunner`.

## Out of scope (explicit)

- MCP surface (not shipped at M7).
- `--json` machine-readable output format.
- Watch / re-run-on-change mode.
- Capture against a still-running / pending / paused run.
