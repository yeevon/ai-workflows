# Task 11 — CLI Stub-Down

**Status:** 📝 Planned.

## What to Build

Reduce `ai_workflows/cli.py` to the minimum that keeps `aiw --help` and `aiw version` working. Remove every command whose implementation depended on pydantic-ai Agents. Leave TODO pointers naming the M3/M4 task that will re-introduce each removed command.

## Deliverables

### `ai_workflows/cli.py`

```python
"""aiw — CLI surface for ai-workflows. Commands are stubbed pending LangGraph runtime (M3) and MCP surface (M4)."""

import typer

app = typer.Typer(help="ai-workflows CLI")


@app.command()
def version() -> None:
    """Print the installed version."""
    ...

# TODO(M3): `run <workflow> <inputs>` — drive a LangGraph StateGraph via the workflows registry.
# TODO(M3): `resume <run_id> [--gate-response ...]` — rehydrate from SqliteSaver checkpoint.
# TODO(M3): `list-runs` — query Storage.list_runs.
# TODO(M3): `cost-report <run_id>` — CostTracker rollup.
```

`[project.scripts]` entry `aiw = "ai_workflows.cli:app"` remains unchanged.

### Test updates

`tests/test_cli.py` reduced to:

- `aiw --help` exits 0 and mentions the command surface.
- `aiw version` exits 0 and prints the version from `ai_workflows.__version__` (add the dunder to `__init__.py` if not present).

Delete any test that exercised a removed command.

## Acceptance Criteria

- [ ] `uv run aiw --help` succeeds.
- [ ] `uv run aiw version` prints a non-empty version string.
- [ ] `grep -r "pydantic_ai\|Agent\[" ai_workflows/cli.py` returns zero matches.
- [ ] Every removed command has a `TODO(M3)` or `TODO(M4)` pointer at the stub site.
- [ ] `uv run pytest tests/test_cli.py` green.

## Dependencies

- [Task 03](task_03_remove_llm_substrate.md).
