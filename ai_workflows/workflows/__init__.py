"""Workflows layer — concrete workflow definitions + name registry.

Each module in here exports a built LangGraph ``StateGraph`` per
[architecture.md §4.3](../../design_docs/architecture.md); a workflow
is a Python module, not a directory of YAML + prompts. Graph instances
are registered by name so surfaces (``aiw`` CLI, MCP server) can reach
them.

Initial workflows (filled in over M3, M5, M6):

* ``planner`` (M3) — two-phase sub-graph (explorer → planner →
  validator); reusable as a sub-graph.
* ``slice_refactor`` (M5) — outermost DAG wiring the ``planner``
  sub-graph to parallel per-slice worker nodes.
* ``jvm_modernization`` (M6) — the original motivating use case.

The pre-pivot reference to a ``workflow_hash`` drift guard has been
retired per [ADR-0001](../../design_docs/adr/0001_workflow_hash.md);
if ``aiw resume`` eventually needs a source-code drift guard, it will
be designed against the module-based shape in M3, not the directory
hash.

## Registry (M3 Task 01)

Surfaces reach workflows by string id through :func:`register` /
:func:`get` / :func:`list_workflows`. Workflow modules self-register
at *import* time; callers (e.g. ``aiw run``) import the module first,
then resolve the builder by name.

``WorkflowBuilder`` is intentionally typed as ``Callable[[], Any]``.
``StateGraph`` lives in ``langgraph.graph``, but the workflows package
must not import LangGraph at module load — doing so would pull a
graph-layer dependency into the surfaces-adjacent layer. Surfaces call
``builder()`` and hand the result straight to LangGraph, so no typing
crosses the boundary.

Architectural rule: workflows are the top of the stack. Nothing imports
from this package — it's strictly an entry-point layer.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

__all__ = [
    "WorkflowBuilder",
    "register",
    "get",
    "list_workflows",
]

WorkflowBuilder = Callable[[], Any]

_REGISTRY: dict[str, WorkflowBuilder] = {}


def register(name: str, builder: WorkflowBuilder) -> None:
    """Register ``builder`` under ``name``.

    Idempotent on identical re-registration (same builder object under the
    same name is a no-op) so module-import side effects don't blow up when
    a workflow module is imported twice.

    Raises ``ValueError`` if ``name`` is already bound to a *different*
    builder — silent overwrite would mask a real naming conflict.
    """
    existing = _REGISTRY.get(name)
    if existing is builder:
        return
    if existing is not None:
        raise ValueError(
            f"workflow {name!r} is already registered to {existing!r}; "
            f"refusing to overwrite with {builder!r}"
        )
    _REGISTRY[name] = builder


def get(name: str) -> WorkflowBuilder:
    """Return the registered builder for ``name``.

    Raises ``KeyError`` with an actionable message listing the registered
    names so callers (the CLI) can surface a useful error to the user.
    """
    try:
        return _REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) if _REGISTRY else "(none)"
        raise KeyError(
            f"unknown workflow {name!r}; registered workflows: {known}"
        ) from None


def list_workflows() -> list[str]:
    """Return all registered workflow names, sorted alphabetically."""
    return sorted(_REGISTRY)


def _reset_for_tests() -> None:
    """Clear the registry. Test-only — never called from runtime code."""
    _REGISTRY.clear()
