# Task 07 — End-to-End Smoke Test

**Status:** 📝 Planned.

## What to Build

One end-to-end smoke test that drives the full `aiw run planner …` → `aiw resume …` path against a real Gemini API call, proving the M3 stack works outside the hermetic graph-layer tests in [task 03](task_03_planner_graph.md). Gated by `@pytest.mark.e2e` + the `AIW_E2E=1` env var so `uv run pytest` on a laptop stays hermetic; CI runs it with `AIW_E2E=1` + `GEMINI_API_KEY` secret bound.

Aligns with M3 [README](README.md) exit criterion #5 + KDR-007 (LiteLLM path).

## Deliverables

### `pyproject.toml` — register the marker

Add to `tool.pytest.ini_options.markers`:

```
e2e: end-to-end test that hits a real API; only runs when AIW_E2E=1
```

### Conftest gate

`tests/e2e/conftest.py`:

```python
import os
import pytest

def pytest_collection_modifyitems(config, items):
    if os.environ.get("AIW_E2E") == "1":
        return
    skip = pytest.mark.skip(reason="Set AIW_E2E=1 to run e2e tests")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip)
```

This is the simplest correct gate: the collection hook adds a `skip` marker to every `e2e`-tagged item unless `AIW_E2E=1`. No test body change needed to enable/disable.

### `tests/e2e/test_planner_smoke.py`

```python
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_aiw_run_planner_end_to_end(tmp_path, monkeypatch):
    """Real Gemini call. Gated by AIW_E2E=1. Budget-capped."""
```

Test body (sketch):

1. `monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))` and point Storage at `tmp_path / "storage.sqlite"`.
2. Assert `os.environ.get("GEMINI_API_KEY")` is set; skip with a clear reason if not.
3. Use Typer's `CliRunner` to invoke `aiw run planner --goal 'ship a tiny marketing page for a cookie recipe app' --max-steps 3 --budget 0.05 --run-id e2e-${uuid}`.
4. Parse the `run_id` + `awaiting: gate` lines from stdout.
5. Invoke `aiw resume <run_id> --gate-response approved`.
6. Assert the returned plan is a valid `PlannerPlan`, has `1 ≤ len(steps) ≤ 3`, and the Storage artifact row round-trips back into `PlannerPlan.model_validate`.
7. Assert `CostTracker.from_storage(storage, run_id).total(run_id) <= 0.05` (budget respected).
8. Assert no log line contains the string `ANTHROPIC_API_KEY` or `anthropic.` (belt-and-braces KDR-003 probe at real-run scope).

### `.github/workflows/ci.yml` — new e2e job (optional, only if you already run CI)

Add a manual-trigger-only job:

```yaml
e2e:
  if: github.event_name == 'workflow_dispatch'
  runs-on: ubuntu-latest
  env:
    AIW_E2E: "1"
    GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
  steps:
    - uses: actions/checkout@v4
    - uses: astral-sh/setup-uv@v3
    - run: uv sync --all-extras
    - run: uv run pytest -m e2e -v
```

If CI isn't wired for M3 yet, this section is a preview — the critical deliverable is the test itself and the marker gate.

## Acceptance Criteria

- [ ] `uv run pytest` on a dev box with `AIW_E2E` unset → the e2e test is collected-and-skipped (not an error, not silently dropped).
- [ ] `AIW_E2E=1 GEMINI_API_KEY=<real> uv run pytest -m e2e` → one test runs, hits Gemini, completes, asserts all invariants.
- [ ] Budget cap `0.05` is honoured (trip a `BudgetExceeded` if the provider overruns; test asserts total ≤ cap).
- [ ] Artifact written to Storage round-trips as a valid `PlannerPlan`.
- [ ] No `ANTHROPIC_API_KEY` reference appears in any log emitted during the run (KDR-003 regression probe at e2e scope).
- [ ] `uv run pytest` remains 236 passed (or higher, depending on new unit tests) on a box with `AIW_E2E` unset — no regressions introduced.

## Dependencies

- [Tasks 04](task_04_cli_run.md), [05](task_05_cli_resume.md), [06](task_06_cli_list_cost.md) — the CLI commands the test drives.
- `GEMINI_API_KEY` available in the runtime environment.
