"""Pydantic schemas for the eval harness (M7 Task 01).

Defines three frozen pydantic v2 models per
[task_01_dataset_schema.md](../../design_docs/phases/milestone_7_evals/task_01_dataset_schema.md):

* :class:`EvalTolerance` — per-case comparison mode (``strict_json`` /
  ``substring`` / ``regex``) with optional per-field overrides.
* :class:`EvalCase` — one LLM-node input/expected-output pair with the
  serialised ``TieredNode`` input state, the raw output, and the
  pydantic ``output_schema`` fully-qualified name.
* :class:`EvalSuite` — a grouping of cases under one workflow, with
  invariant that every contained case carries the suite's
  ``workflow_id``.

Every model is bare-typed per KDR-010: ``extra="forbid"`` and
``frozen=True`` are kept, but no ``Field(min_length/...)`` bounds are
declared. Runtime validation of semantic content is the job of the
T03 ``EvalRunner`` compare path, not the schema.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ToleranceMode = Literal["strict_json", "substring", "regex"]


class EvalTolerance(BaseModel):
    """Per-case comparison policy.

    * ``strict_json`` — round-trip equality after parsing both sides
      through the case's ``output_schema_fqn`` (falls back to raw
      structural equality when no schema is pinned).
    * ``substring`` — each configured string field must contain the
      expected value as a case-insensitive substring.
    * ``regex`` — each configured string field must match the expected
      regex via :func:`re.search`.

    ``field_overrides`` scopes a different mode to specific fields —
    the common case is ``strict_json`` by default with a ``substring``
    escape hatch on a single free-text ``summary`` field.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: ToleranceMode = "strict_json"
    field_overrides: dict[str, ToleranceMode] = Field(default_factory=dict)


class EvalCase(BaseModel):
    """One captured LLM-node call, replayable against the current graph.

    ``inputs`` holds the serialised ``TieredNode`` input state at the
    moment the node fired. ``expected_output`` holds the node's raw
    return value (before ``ValidatorNode`` parsing, to keep the eval
    replay exercising the full validator path). ``output_schema_fqn``
    is the fully-qualified name of the pydantic model bound as the
    node's ``output_schema=``; None for free-text nodes.

    ``case_id`` is a human-readable, sortable identifier — the T02
    ``CaptureCallback`` generates
    ``<workflow>-<node>-<UTC timestamp>-<short uuid>`` but hand-written
    fixtures may use any unique string.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    workflow_id: str
    node_name: str
    inputs: dict[str, Any]
    expected_output: Any
    output_schema_fqn: str | None = None
    tolerance: EvalTolerance = Field(default_factory=EvalTolerance)
    captured_at: datetime
    captured_from_run_id: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class EvalSuite(BaseModel):
    """A workflow-scoped collection of eval cases.

    The invariant enforced on construction: every case must carry the
    suite's ``workflow_id``. Keeping the rule here means the T03
    ``EvalRunner`` can trust the type and not re-check case-by-case.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    workflow_id: str
    cases: tuple[EvalCase, ...] = ()

    @model_validator(mode="after")
    def _cases_belong_to_suite(self) -> EvalSuite:
        for case in self.cases:
            if case.workflow_id != self.workflow_id:
                raise ValueError(
                    f"case {case.case_id!r} has workflow_id={case.workflow_id!r} "
                    f"which does not match suite workflow_id={self.workflow_id!r}"
                )
        return self
