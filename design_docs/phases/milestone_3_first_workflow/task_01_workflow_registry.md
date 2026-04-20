# Task 01 — Workflow Registry

**Status:** 📝 Planned.

## What to Build

Extend [`ai_workflows/workflows/__init__.py`](../../../ai_workflows/workflows/__init__.py) — currently a docstring-only module — into a tiny name-to-builder registry so surfaces (`aiw` CLI in T04–T06, MCP server in M4) reach workflows by string id without importing each workflow module directly. No `StateGraph` is registered yet; that happens in [task 03](task_03_planner_graph.md). This task ships the registry shape only.

Aligns with [architecture.md §4.3](../../architecture.md): "Workflows are registered by name; the registry is how surfaces reach them." Matches the M3 [README](README.md) task-order entry.

## Deliverables

### `ai_workflows/workflows/__init__.py`

Keep the existing module docstring (retire the "no logic here" sentence once a registry lands). Add:

```python
from __future__ import annotations

from collections.abc import Callable
from typing import Any

WorkflowBuilder = Callable[[], Any]  # built StateGraph; intentionally untyped to avoid a graph-layer import

_REGISTRY: dict[str, WorkflowBuilder] = {}


def register(name: str, builder: WorkflowBuilder) -> None:
    """Register ``builder`` under ``name``. Idempotent on identical re-registration; raises on conflict."""


def get(name: str) -> WorkflowBuilder:
    """Return the registered builder. Raises ``KeyError`` with an actionable message listing known names."""


def list_workflows() -> list[str]:
    """Return all registered names, sorted, for surfaces that enumerate (``aiw list-workflows`` later)."""


def _reset_for_tests() -> None:
    """Clear the registry — test-only helper, underscore-prefixed. Never called from runtime code."""
```

- `WorkflowBuilder`'s return type is `Any` on purpose: `StateGraph` lives in `langgraph.graph`, but `ai_workflows.workflows` sits in the surfaces-adjacent layer per the four-layer contract and should not introduce a direct LangGraph dep above `graph`. Surfaces call `builder()` and hand the result straight to LangGraph — no typing crosses the boundary.
- No import-time side effects. Concrete workflows (the `planner` module in T03) register themselves at *import* time — the caller of `get("planner")` imports `ai_workflows.workflows.planner` first (handled by `aiw run` in T04).

### Tests

`tests/workflows/test_registry.py`:

- `register` + `get` round-trips an arbitrary callable.
- `register` with the same `(name, builder)` pair is a no-op; `register` with a different builder under an existing name raises `ValueError` with the existing builder in the message.
- `get("missing")` raises `KeyError` listing the known names.
- `list_workflows()` returns names sorted alphabetically.
- `_reset_for_tests()` empties the registry between tests (autouse fixture).

## Acceptance Criteria

- [ ] `register(name, builder)`, `get(name)`, `list_workflows()`, `_reset_for_tests()` exported from `ai_workflows.workflows`.
- [ ] Duplicate-name registration with a different builder raises `ValueError`; identical re-registration is a no-op.
- [ ] `get` on an unknown name raises `KeyError` with a helpful message listing registered names.
- [ ] `ai_workflows.workflows` does not import `langgraph` at module load (verified by a test that imports the module with `langgraph` stubbed out of `sys.modules`).
- [ ] `uv run pytest tests/workflows/test_registry.py` green.
- [ ] `uv run lint-imports` stays 3 / 3 kept, 0 broken.

## Dependencies

- None — pure stdlib + project layout.
