"""CaptureCallback — writes one EvalCase fixture per TieredNode call (M7 Task 02).

Sibling of :class:`ai_workflows.graph.cost_callback.CostTrackingCallback`
but placed under ``evals/`` rather than ``graph/`` — the callback's
implementation imports :func:`save_case` and :class:`EvalCase` from
this package, so keeping it inside ``evals/`` avoids ``graph → evals``
(a lower-layer-reaches-higher import that would invert the layer
order). ``TieredNode`` consumes the callback duck-typed through
``config.configurable["eval_capture_callback"]`` so the graph layer
stays evals-unaware.

Attach contract
---------------
The callback is pure instrumentation. Zero effect on the graph's
behaviour when ``AIW_CAPTURE_EVALS`` is unset — :mod:`ai_workflows.workflows._dispatch`
attaches the callback only when the env var (or an explicit
``capture_evals`` override) is present, and ``TieredNode`` never errors
when the key is absent from ``configurable``.

Method contract
---------------
One method: ``on_node_complete(run_id, node_name, inputs, raw_output,
output_schema_fqn)`` — called by ``TieredNode`` on the success path
after the cost callback has already recorded usage. No return value.
Exceptions raised inside the callback are logged at WARN via
:class:`StructuredLogger` and swallowed — a broken capture environment
must never break a live production run.

Relationship to sibling modules
-------------------------------
* :mod:`ai_workflows.evals.schemas` — constructs :class:`EvalCase` per
  capture.
* :mod:`ai_workflows.evals.storage` — writes via :func:`save_case`.
* :mod:`ai_workflows.graph.tiered_node` — sole caller; invokes
  ``on_node_complete`` after the cost callback when the config carries
  an ``eval_capture_callback`` entry.
* :mod:`ai_workflows.workflows._dispatch` — opt-in wiring layer.
  Constructs this callback when ``AIW_CAPTURE_EVALS`` is set and
  threads it into ``config.configurable``.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ai_workflows.evals.schemas import EvalCase
from ai_workflows.evals.storage import default_evals_root, fixture_path, save_case

__all__ = ["CaptureCallback", "output_schema_fqn"]

_LOG = logging.getLogger(__name__)


def output_schema_fqn(schema: type[BaseModel] | None) -> str | None:
    """Return the fully-qualified name of a pydantic ``output_schema`` (or None).

    Used at capture time to record the schema the T03 replay runner
    needs to resolve when parsing ``expected_output``.
    """

    if schema is None:
        return None
    return f"{schema.__module__}.{schema.__qualname__}"


class CaptureCallback:
    """Write one :class:`EvalCase` fixture per successful ``TieredNode`` call.

    Parameters
    ----------
    dataset_name:
        Sub-directory under ``root`` into which fixtures land. The T02
        convention is to set this from ``AIW_CAPTURE_EVALS`` at dispatch
        time, but callers may pass anything — directly naming the
        dataset a capture belongs to.
    workflow_id:
        Workflow name (e.g. ``"planner"``). Used both as the mid-level
        directory segment and as :attr:`EvalCase.workflow_id`.
    run_id:
        Source run id. Threaded into
        :attr:`EvalCase.captured_from_run_id` for provenance and
        re-capture debugging.
    root:
        Filesystem root for the emitted fixtures. Defaults to
        :func:`default_evals_root` / ``dataset_name`` — so with the
        default ``AIW_EVALS_ROOT`` unset, fixtures land at
        ``evals/<dataset>/<workflow>/<node>/<case>.json``.
    """

    def __init__(
        self,
        *,
        dataset_name: str,
        workflow_id: str,
        run_id: str,
        root: Path | None = None,
    ) -> None:
        self._dataset_name = dataset_name
        self._workflow_id = workflow_id
        self._run_id = run_id
        if root is None:
            root = default_evals_root() / dataset_name
        self._root = root

    @property
    def root(self) -> Path:
        """Root directory under which fixtures land (testable property)."""

        return self._root

    def on_node_complete(
        self,
        *,
        run_id: str,
        node_name: str,
        inputs: dict[str, Any],
        raw_output: str,
        output_schema: type[BaseModel] | None,
    ) -> Path | None:
        """Write one fixture for a completed TieredNode call.

        Returns the written path on success, ``None`` on captured
        failure. Exceptions are logged and swallowed so a broken
        capture never breaks a live run.
        """

        try:
            case = self._build_case(
                run_id=run_id,
                node_name=node_name,
                inputs=inputs,
                raw_output=raw_output,
                output_schema=output_schema,
            )
            path = self._resolve_unique_path(case)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(case.model_dump_json(indent=2), encoding="utf-8")
            return path
        except Exception:  # noqa: BLE001 — capture must never break a live run
            _LOG.warning(
                "eval capture failed",
                extra={
                    "dataset": self._dataset_name,
                    "workflow": self._workflow_id,
                    "node": node_name,
                    "run_id": run_id,
                },
                exc_info=True,
            )
            return None

    def _build_case(
        self,
        *,
        run_id: str,
        node_name: str,
        inputs: dict[str, Any],
        raw_output: str,
        output_schema: type[BaseModel] | None,
    ) -> EvalCase:
        now = datetime.now(UTC)
        case_id = (
            f"{self._workflow_id}-{node_name}-"
            f"{now.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        )
        return EvalCase(
            case_id=case_id,
            workflow_id=self._workflow_id,
            node_name=node_name,
            inputs=_normalize(inputs),
            expected_output=_normalize_output(raw_output),
            output_schema_fqn=output_schema_fqn(output_schema),
            captured_at=now,
            captured_from_run_id=run_id,
        )

    def _resolve_unique_path(self, case: EvalCase) -> Path:
        """Return a non-colliding path, suffixing ``-NNN`` on repeat case_ids."""

        candidate = fixture_path(
            self._root, case.workflow_id, case.node_name, case.case_id
        )
        if not candidate.exists():
            return candidate
        suffix = 2
        while True:
            candidate_with_suffix = fixture_path(
                self._root,
                case.workflow_id,
                case.node_name,
                f"{case.case_id}-{suffix:03d}",
            )
            if not candidate_with_suffix.exists():
                return candidate_with_suffix
            suffix += 1

    def save_case(self, case: EvalCase) -> Path:
        """Explicit escape hatch — writes a pre-built case via :func:`save_case`.

        Tests use this to exercise the refuse-overwrite contract from
        T01 independently of the on-node-complete path.
        """

        return save_case(case, self._root)


def _normalize(obj: Any) -> dict[str, Any]:
    """Best-effort conversion of a TieredNode input state to JSON-ready dict.

    ``TieredNode`` builds graph state as a plain dict, but leaves may
    be pydantic models. The capture path needs serialisable data; this
    helper walks one level and dumps any model it finds. Deeper
    structures (lists containing models, nested models) are handled by
    pydantic's own ``model_dump`` on the top-level model when possible.
    """

    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return {k: _normalize_value(v) for k, v in obj.items()}
    return {"value": _normalize_value(obj)}


def _normalize_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list | tuple):
        return [_normalize_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize_value(v) for k, v in value.items()}
    return value


def _normalize_output(raw_output: Any) -> Any:
    """Passthrough — TieredNode returns the raw provider text string."""

    if isinstance(raw_output, BaseModel):
        return raw_output.model_dump(mode="json")
    return raw_output
