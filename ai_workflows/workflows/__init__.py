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

## External workflow discovery (M16 Task 01)

Downstream consumers register their own workflow modules via dotted
Python paths through :data:`ai_workflows.workflows.loader.ENV_VAR_NAME`
(``AIW_EXTRA_WORKFLOW_MODULES``) or the ``--workflow-module`` CLI flag
on both surfaces. :func:`load_extra_workflow_modules` imports each
entry once at startup; the module's top-level :func:`register` call
fires as a side effect. :class:`ExternalWorkflowImportError` (a
subclass of :class:`ImportError`) surfaces import failures with a
single actionable message. See KDR-013 / ADR-0007 for the
user-owned-code contract.

## Declarative authoring surface (M19 Task 01)

External workflow authors write a :class:`WorkflowSpec` — a pydantic
data object that declares the workflow's name, input/output schemas, and
an ordered list of :class:`Step` instances.  See ADR-0008 for the
decision rationale.  The five built-in step types cover the most common
orchestration shapes; custom step types extend :class:`Step` for bespoke
logic.  :func:`register_workflow` is the primary registration entry
point; :func:`register` survives as the documented Tier 4 escape hatch.

:data:`RetryPolicy` is re-exported from :mod:`ai_workflows.primitives.retry`
per locked Q1 — the spec API does not invent a parallel retry surface.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ai_workflows.primitives.retry import RetryPolicy
from ai_workflows.workflows.loader import (
    ExternalWorkflowImportError,
    load_extra_workflow_modules,
)
from ai_workflows.workflows.spec import (
    FanOutStep,
    GateStep,
    LLMStep,
    Step,
    TransformStep,
    ValidateStep,
    WorkflowSpec,
    register_workflow,
)

__all__ = [
    "WorkflowBuilder",
    "register",
    "get",
    "get_spec",
    "list_workflows",
    "ExternalWorkflowImportError",
    "load_extra_workflow_modules",
    # M19 T01 — declarative authoring surface:
    "WorkflowSpec",
    "Step",
    "LLMStep",
    "ValidateStep",
    "GateStep",
    "TransformStep",
    "FanOutStep",
    "RetryPolicy",      # re-export from primitives.retry, not a new spec class
    "register_workflow",
]

WorkflowBuilder = Callable[[], Any]

_REGISTRY: dict[str, WorkflowBuilder] = {}
_SPEC_REGISTRY: dict[str, WorkflowSpec] = {}


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


def get_spec(name: str) -> WorkflowSpec | None:
    """Return the ``WorkflowSpec`` registered under ``name`` or ``None``.

    Spec-API workflows register both a builder (via :func:`register`) and the
    originating :class:`WorkflowSpec` (via :func:`register_workflow`). Imperative
    workflows registered via :func:`register` directly have no spec — this
    helper returns ``None`` for those.

    Dispatch's ``_build_initial_state`` consults this lookup to construct the
    typed input from ``spec.input_schema`` for spec-API workflows; without the
    spec, dispatch falls back to the imperative ``initial_state`` hook /
    ``PlannerInput`` lookup path.
    """
    return _SPEC_REGISTRY.get(name)


def list_workflows() -> list[str]:
    """Return all registered workflow names, sorted alphabetically."""
    return sorted(_REGISTRY)


def _reset_for_tests() -> None:
    """Clear the registry and any synthetic compiled-spec modules.

    Test-only — never called from runtime code.

    LOW-3 fix: ``compile_spec`` injects a synthetic module into ``sys.modules``
    under ``ai_workflows.workflows._compiled_<spec.name>`` for every compiled
    spec.  Without this cleanup, dead ``_compiled_*`` entries accumulate across
    tests in the same process, causing debugging confusion and (in theory) memory
    growth on long test runs.  We match conservatively: only keys with the exact
    ``_compiled_`` prefix inside our package namespace are removed, so unrelated
    ``sys.modules`` entries are never touched.
    """
    import sys

    _REGISTRY.clear()
    _SPEC_REGISTRY.clear()
    prefix = "ai_workflows.workflows._compiled_"
    stale = [k for k in sys.modules if k.startswith(prefix)]
    for key in stale:
        del sys.modules[key]
