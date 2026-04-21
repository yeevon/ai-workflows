"""Deterministic capture of eval fixtures from a completed run (M7 Task 04).

Drives ``aiw eval capture``. Reconstructs one :class:`EvalCase` per
LLM node from the run's checkpointed LangGraph state — never re-fires
any provider, never reads an API key, never touches the ``CaptureCallback``
re-run path. The run must already be in :attr:`runs.status =
"completed"`; capture against a pending / paused / errored run raises
:class:`CaptureNotCompletedError` (surface translates to exit 2).

Design rationale
----------------
The T04 spec's preferred path is "replay against the checkpointed
state". LangGraph's ``AsyncSqliteSaver`` exposes
:meth:`aget_state(config)` which returns a :class:`StateSnapshot`
whose ``.values`` dict is the final merged state for the thread —
keyed by the same state-key convention that ``TieredNode`` writes
(``f"{node_name}_output"``). That dict is the source of truth for
"the bytes the completed run actually exchanged", and reading it
is strictly a single-SELECT operation against the checkpoint DB.

No provider call fires. No cost accrues. No live auth required.

Per-workflow schema registry
----------------------------
The capture helper needs to know which pydantic output class each
``TieredNode`` emits, so it can stamp :attr:`EvalCase.output_schema_fqn`
onto each fixture. Rather than introspecting the LangGraph builder at
runtime (fragile — node specs expose the runnable, not the
``output_schema=`` binding), each workflow module exposes a
callable ``<workflow_id>_eval_node_schemas()`` returning
``{node_name: pydantic_cls}``. The planner's version is
:func:`ai_workflows.workflows.planner.planner_eval_node_schemas`.
A workflow missing that registry raises
:class:`WorkflowCaptureUnsupportedError` — the spec explicitly pins
"fail fast on unknown workflow" as the capture contract.

Relationship to sibling modules
-------------------------------
* :mod:`ai_workflows.evals.capture_callback` — the live-run
  capture path. This module is the offline counterpart.
* :mod:`ai_workflows.evals.schemas` — constructs :class:`EvalCase`
  per captured node.
* :mod:`ai_workflows.evals.storage` — writes each case via
  :func:`save_case`.
* :mod:`ai_workflows.graph.checkpointer` — supplies the
  :class:`AsyncSqliteSaver` the capture helper reads state from.
* :mod:`ai_workflows.workflows.planner` — per-workflow registry
  the helper resolves.
"""

from __future__ import annotations

import importlib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ai_workflows.evals.capture_callback import (
    _normalize,
    _normalize_output,
    output_schema_fqn,
)
from ai_workflows.evals.schemas import EvalCase
from ai_workflows.evals.storage import default_evals_root, fixture_path, save_case
from ai_workflows.graph.checkpointer import build_async_checkpointer
from ai_workflows.primitives.storage import StorageBackend

__all__ = [
    "CaptureNotCompletedError",
    "UnknownRunError",
    "WorkflowCaptureUnsupportedError",
    "capture_completed_run",
]


# Keys the capture path drops from the reconstructed ``inputs`` dict —
# they are bucket-taxonomy / node-output bookkeeping that leaks from
# the graph run into checkpointed state, not prompt-fn inputs.
_BOOKKEEPING_STATE_KEYS: frozenset[str] = frozenset(
    {
        "last_exception",
        "last_error_bucket",
        "_retry_counts",
        "_non_retryable_failures",
    }
)


class UnknownRunError(ValueError):
    """Raised when ``run_id`` has no matching ``runs`` row."""


class CaptureNotCompletedError(ValueError):
    """Raised when the target run is not in ``status='completed'``."""


class WorkflowCaptureUnsupportedError(ValueError):
    """Raised when the workflow module exposes no ``_eval_node_schemas``."""


async def capture_completed_run(
    *,
    run_id: str,
    dataset: str,
    storage: StorageBackend,
    output_root: Path | None = None,
) -> list[Path]:
    """Reconstruct eval fixtures from a completed run's checkpointed state.

    Returns the list of written fixture paths (one per LLM node in the
    workflow's eval-schema registry). Callers handle empty returns
    (workflow with no registered LLM nodes) as a soft no-op — the
    refused-run / unknown-run / unsupported-workflow classes raise
    typed exceptions the CLI translates to ``exit 2``.

    The output layout is ``<root>/<dataset>/<workflow_id>/<node>/<case_id>.json``
    — root defaults to ``evals/`` via :func:`default_evals_root` and
    callers may override with ``output_root``.
    """

    row = await storage.get_run(run_id)
    if row is None:
        raise UnknownRunError(f"no run found for run_id={run_id!r}")
    status = row.get("status")
    if status != "completed":
        raise CaptureNotCompletedError(
            f"run {run_id!r} is in status {status!r}; capture requires "
            "status='completed'"
        )
    workflow_id = row["workflow_id"]
    schema_registry = _resolve_schema_registry(workflow_id)

    root = output_root if output_root is not None else default_evals_root()
    dataset_root = root / dataset

    state_values = await _load_final_state(run_id)
    if state_values is None:
        raise CaptureNotCompletedError(
            f"run {run_id!r} has no checkpointed state; cannot capture"
        )

    written: list[Path] = []
    now = datetime.now(UTC)
    for node_name, schema_cls in schema_registry.items():
        raw_output = state_values.get(f"{node_name}_output")
        if raw_output is None:
            # Node exists in the registry but has no captured output
            # (e.g. the run terminated before reaching this node).
            # Skipping silently keeps capture idempotent on a partial
            # state — the registry is the upper bound, not the floor.
            continue
        inputs = _filter_inputs(
            state_values,
            node_name=node_name,
            node_names_in_registry=schema_registry.keys(),
        )
        case = _build_case(
            run_id=run_id,
            workflow_id=workflow_id,
            node_name=node_name,
            inputs=inputs,
            raw_output=raw_output,
            output_schema=schema_cls,
            now=now,
        )
        path = _write_unique(case, dataset_root)
        written.append(path)

    return written


def _resolve_schema_registry(workflow_id: str) -> dict[str, type[BaseModel]]:
    """Import the workflow module and return its eval-schema registry."""

    module = importlib.import_module(f"ai_workflows.workflows.{workflow_id}")
    registry_name = f"{workflow_id}_eval_node_schemas"
    registry = getattr(module, registry_name, None)
    if registry is None:
        raise WorkflowCaptureUnsupportedError(
            f"workflow {workflow_id!r} does not expose {registry_name}(); "
            "cannot capture without a per-node output-schema registry"
        )
    return registry()


async def _load_final_state(run_id: str) -> dict[str, Any] | None:
    """Return the final state dict for ``run_id`` from the checkpointer.

    Uses :func:`build_async_checkpointer` directly — the same factory
    ``aiw run`` / ``aiw resume`` drive, so path resolution
    (``AIW_CHECKPOINT_DB``) stays consistent across the three commands.
    """

    saver = await build_async_checkpointer()
    try:
        cfg: dict[str, Any] = {"configurable": {"thread_id": run_id}}
        snapshot = await saver.aget(cfg)
        if snapshot is None:
            return None
        channel_values = snapshot.get("channel_values") or {}
        return dict(channel_values)
    finally:
        await saver.conn.close()


def _filter_inputs(
    state_values: dict[str, Any],
    *,
    node_name: str,
    node_names_in_registry: Any,
) -> dict[str, Any]:
    """Reduce full state → the prompt-fn-visible inputs for one node.

    Drops:
    * The node's own output + revision-hint keys (``{node}_output`` /
      ``{node}_output_revision_hint``) — those are the capture target,
      not prompt inputs.
    * Outputs of downstream nodes in the same registry — a capture for
      ``explorer`` must not include the later ``planner_output`` as
      part of its replay inputs.
    * Error-taxonomy bookkeeping keys (``last_exception`` etc.) that
      only exist between retries.
    """

    drop: set[str] = set(_BOOKKEEPING_STATE_KEYS)
    drop.add(f"{node_name}_output")
    drop.add(f"{node_name}_output_revision_hint")
    for other in node_names_in_registry:
        if other == node_name:
            continue
        drop.add(f"{other}_output")
        drop.add(f"{other}_output_revision_hint")

    return _normalize(
        {k: v for k, v in state_values.items() if k not in drop}
    )


def _build_case(
    *,
    run_id: str,
    workflow_id: str,
    node_name: str,
    inputs: dict[str, Any],
    raw_output: Any,
    output_schema: type[BaseModel] | None,
    now: datetime,
) -> EvalCase:
    case_id = (
        f"{workflow_id}-{node_name}-"
        f"{now.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    )
    return EvalCase(
        case_id=case_id,
        workflow_id=workflow_id,
        node_name=node_name,
        inputs=inputs,
        expected_output=_normalize_output(raw_output),
        output_schema_fqn=output_schema_fqn(output_schema),
        captured_at=now,
        captured_from_run_id=run_id,
    )


def _write_unique(case: EvalCase, root: Path) -> Path:
    """Write the case, suffixing ``-NNN`` on case_id collision.

    Mirrors the ``CaptureCallback`` collision discipline — the
    :func:`save_case` primitive refuses overwrites, and the capture
    command disambiguates rather than asking the caller.
    """

    candidate = fixture_path(root, case.workflow_id, case.node_name, case.case_id)
    if not candidate.exists():
        return save_case(case, root)
    suffix = 2
    while True:
        retry = case.model_copy(
            update={"case_id": f"{case.case_id}-{suffix:03d}"}
        )
        candidate_with_suffix = fixture_path(
            root, retry.workflow_id, retry.node_name, retry.case_id
        )
        if not candidate_with_suffix.exists():
            return save_case(retry, root)
        suffix += 1
