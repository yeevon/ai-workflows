"""Pydantic I/O models for the ai-workflows MCP surface.

M4 Task 01 ships the public contract every FastMCP tool in
:mod:`ai_workflows.mcp.server` binds to its ``@mcp.tool()`` signature.
FastMCP auto-derives the JSON-RPC schema from each model's type
annotations (KDR-008), so this module is the source of truth for both
the tool-call request shape and the response shape every MCP host
(Claude Code, Cursor, Zed, ...) consumes.

M12 Task 05 adds :class:`RunAuditCascadeInput` and
:class:`RunAuditCascadeOutput` for the standalone ``run_audit_cascade``
MCP tool.  :class:`~ai_workflows.graph.audit_cascade.AuditVerdict` is
imported from its canonical owner (``graph/audit_cascade.py:75``) for the
``verdicts_by_tier`` type hint only — it is NOT added to ``__all__`` here
(KDR-008 schema-first discipline; ``AuditVerdict`` is a graph primitive,
not an MCP surface model).

Relationship to other modules
-----------------------------
* :mod:`ai_workflows.mcp.server` — registers each tool with a signature
  of ``(payload: <Input>) -> <Output>`` drawn from this module.
* :mod:`ai_workflows.primitives.storage` — the shape of :class:`RunSummary`
  mirrors the dict keys ``SQLiteStorage.list_runs`` returns so M4 T04 can
  construct summaries via ``RunSummary(**row)`` without a translation step.
* :mod:`ai_workflows.graph.audit_cascade` — canonical owner of
  :class:`~ai_workflows.graph.audit_cascade.AuditVerdict`; imported here
  for the ``verdicts_by_tier`` type hint only (M12 T05).
* [architecture.md §4.4](../../design_docs/architecture.md) — lists the
  four M4 tools (`run_workflow`, `resume_run`, `list_runs`, `cancel_run`);
  the originally-planned fifth tool ``get_cost_report`` was dropped at
  M4 kickoff so :class:`RunSummary` carries ``total_cost_usd`` as the sole
  cost surface the MCP server exposes.
* [ADR-0002 / KDR-010](../../design_docs/adr/0002_bare_typed_response_format_schemas.md)
  — MCP I/O models are explicitly *out of scope* for the bare-typed
  rule (they never cross into an LLM's ``response_format``). Bounds on
  fields like :attr:`ListRunsInput.limit` are *permitted* and used where
  they add contract-at-boundary value.

M19 T03 (ADR-0008): :attr:`RunWorkflowOutput.artifact` and
:attr:`ResumeRunOutput.artifact` are the canonical field names for the
workflow's terminal artefact.  The ``plan`` field on each model is
preserved as a deprecated alias through the 0.2.x line (removal target
1.0) so existing 0.2.0 callers reading ``result.plan`` continue to work.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from ai_workflows.graph.audit_cascade import AuditVerdict  # type-hint only; not in __all__

__all__ = [
    "RunWorkflowInput",
    "RunWorkflowOutput",
    "ResumeRunInput",
    "ResumeRunOutput",
    "RunSummary",
    "ListRunsInput",
    "CancelRunInput",
    "CancelRunOutput",
    "RunAuditCascadeInput",
    "RunAuditCascadeOutput",
]


class RunWorkflowInput(BaseModel):
    """Arguments to the ``run_workflow`` tool.

    ``workflow_id`` names a workflow registered via
    :func:`ai_workflows.workflows.register`. ``inputs`` is a dict that the
    workflow's own pydantic input model validates (e.g. ``PlannerInput``
    for the planner workflow). ``budget_cap_usd`` and ``run_id`` mirror
    the ``aiw run`` CLI flags.

    ``tier_overrides`` (M5 T05) is the MCP-side mirror of the CLI's
    ``--tier-override`` flag: an optional ``{logical: replacement}``
    map swapped against the workflow's tier registry at invoke time
    (architecture.md §4.4). Both names must already exist in
    ``<workflow>_tier_registry()``; unknown names surface as a
    ``ToolError``. ``None``-default keeps the JSON-RPC payload
    backward-compatible with M4-era callers who never set the field.
    """

    workflow_id: str
    inputs: dict[str, Any]
    budget_cap_usd: float | None = None
    run_id: str | None = None
    tier_overrides: dict[str, str] | None = Field(
        default=None,
        description=(
            "Optional {logical: replacement} map to swap tiers at invoke "
            "time. Both names must already exist in the workflow's tier "
            "registry."
        ),
    )


class RunWorkflowOutput(BaseModel):
    """Response from the ``run_workflow`` tool.

    ``status`` is the run's state post-dispatch:

    * ``"pending"`` — the graph yielded at a :class:`HumanGate` interrupt
      (``awaiting='gate'``). ``artifact`` follows ``FINAL_STATE_KEY``; may
      be ``None`` if the workflow's ``FINAL_STATE_KEY`` channel is empty
      at gate time (e.g. ``slice_refactor``'s ``applied_artifact_count``
      is ``None`` at the review gate). ``gate_context`` carries the gate
      prompt, id, workflow id, and a projection-time ISO-8601 timestamp.
    * ``"completed"`` — the graph reached its terminal artifact node.
      ``artifact`` carries the final artefact.
    * ``"aborted"`` — the Ollama-fallback circuit-breaker gate resolved
      to ABORT (M8 T04) or the double-failure slice hard-stop fired
      (M6 T07 / architecture.md §8.2). ``artifact`` is ``None``; ``error``
      carries the distinguishing message.
    * ``"errored"`` — a dispatch-level failure (budget breach, validator
      exhaust, uncaught graph exception). ``artifact`` is ``None``; ``error``
      carries a descriptive message so MCP clients see the reason
      in-band rather than through a raw Python exception (M4 T02 AC).

    ``artifact`` (M19 T03 — ADR-0008) is the canonical field name for the
    workflow's terminal artefact, replacing the original ``plan`` field name
    which was planner-specific.  ``plan`` is preserved as a deprecated alias
    (same value) through the 0.2.x line; removal target 1.0.

    ``gate_context`` (M11 T01) is populated iff ``status="pending"`` and
    ``awaiting="gate"`` — see the field's ``description`` for the dict
    shape. The schema's public contract (KDR-008): additive field
    growth is non-breaking; a pre-M11 caller that ignored the field
    keeps working, and an M11-aware caller that reads it gets the
    gate-review payload.
    """

    run_id: str
    status: Literal["pending", "completed", "aborted", "errored"]
    awaiting: Literal["gate"] | None = None
    artifact: dict[str, Any] | None = Field(
        default=None,
        description=(
            "The workflow's terminal artefact — the value of the state field "
            "named by the workflow's FINAL_STATE_KEY (declarative spec: the "
            "first field of output_schema). For the in-tree planner this is "
            "the approved PlannerPlan; for slice_refactor it is the applied-"
            "artefact count; for an external workflow it is whatever the "
            "workflow declares. At a gate-pause-resume response, reports the "
            "value of the workflow's FINAL_STATE_KEY channel — which may be "
            "``None`` if the workflow's terminal artefact has not been computed "
            "yet (e.g. slice_refactor's ``applied_artifact_count`` is ``None`` "
            "at the ``slice_refactor_review`` gate). Surfaced through the "
            "deprecated ``plan`` field alias for backward compatibility through "
            "the 0.2.x line; removal target is 1.0."
        ),
    )
    plan: dict[str, Any] | None = Field(
        default=None,
        deprecated=True,
        description=(
            "Deprecated alias for ``artifact``. Deprecated alias preserved "
            "for backward compatibility through the 0.2.x line; removal "
            "target 1.0. Read ``artifact`` instead."
        ),
    )
    total_cost_usd: float | None = None
    error: str | None = None
    gate_context: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Populated iff status='pending' and awaiting='gate'. Keys "
            "at M11: 'gate_prompt' (str, the prompt the HumanGate "
            "recorded), 'gate_id' (str, the gate identifier), "
            "'workflow_id' (str), 'checkpoint_ts' (str, ISO-8601 "
            "stamp at projection time — not the checkpointer's own "
            "timestamp). Forward-compat: M12 will extend this dict "
            "with cascade-transcript keys (audit_verdict, "
            "audit_reasons, suggested_approach) without a schema "
            "break."
        ),
    )


class ResumeRunInput(BaseModel):
    """Arguments to the ``resume_run`` tool."""

    run_id: str
    gate_response: Literal["approved", "rejected"] = "approved"


class ResumeRunOutput(BaseModel):
    """Response from the ``resume_run`` tool.

    ``status``:

    * ``"pending"`` — another gate fired post-resume
      (``awaiting="gate"``). ``artifact`` follows ``FINAL_STATE_KEY``; may
      be ``None`` if the workflow's ``FINAL_STATE_KEY`` channel is empty at
      gate time. ``gate_context`` carries the new gate's prompt, id,
      workflow id, and projection-time ISO-8601 timestamp.
    * ``"completed"`` — approved → artefact persisted.
      ``artifact`` carries the final artefact.
    * ``"gate_rejected"`` — caller rejected at the gate. ``artifact``
      follows ``FINAL_STATE_KEY`` at rejection time (for audit review);
      ``gate_context`` is ``None`` because the gate has already
      resolved.
    * ``"aborted"`` — the Ollama-fallback gate resolved to ABORT on
      the resume path (M8 T04). ``artifact`` is ``None``; ``error``
      carries the distinguishing message.
    * ``"errored"`` — a post-gate fault (M4 T03 AC, parallel to
      ``RunWorkflowOutput.error``). ``artifact`` is ``None``; ``error``
      carries a descriptive message so MCP clients see the reason
      in-band.

    ``artifact`` (M19 T03 — ADR-0008) is the canonical field name for the
    workflow's terminal artefact.  ``plan`` is preserved as a deprecated
    alias (same value) through the 0.2.x line; removal target 1.0.

    ``awaiting`` (added in M11 T01) mirrors :attr:`RunWorkflowOutput.awaiting`:
    populated iff ``status="pending"``; ``None`` elsewhere. Before M11
    a resumed re-gate returned ``status="pending"`` without a key for
    the caller to tell what was being awaited — now the same signal
    exists on both output models.

    ``gate_context`` (M11 T01) is populated iff ``status="pending"`` and
    ``awaiting="gate"``; see the field's ``description`` for the dict
    shape. Forward-compat surface for M12's audit-cascade transcript.
    """

    run_id: str
    status: Literal["pending", "completed", "gate_rejected", "aborted", "errored"]
    awaiting: Literal["gate"] | None = None
    artifact: dict[str, Any] | None = Field(
        default=None,
        description=(
            "The workflow's terminal artefact — the value of the state field "
            "named by the workflow's FINAL_STATE_KEY (declarative spec: the "
            "first field of output_schema). For the in-tree planner this is "
            "the approved PlannerPlan; for slice_refactor it is the applied-"
            "artefact count; for an external workflow it is whatever the "
            "workflow declares. At a gate-pause-resume response, reports the "
            "value of the workflow's FINAL_STATE_KEY channel — which may be "
            "``None`` if the workflow's terminal artefact has not been computed "
            "yet (e.g. slice_refactor's ``applied_artifact_count`` is ``None`` "
            "at the ``slice_refactor_review`` gate). Surfaced through the "
            "deprecated ``plan`` field alias for backward compatibility through "
            "the 0.2.x line; removal target is 1.0."
        ),
    )
    plan: dict[str, Any] | None = Field(
        default=None,
        deprecated=True,
        description=(
            "Deprecated alias for ``artifact``. Deprecated alias preserved "
            "for backward compatibility through the 0.2.x line; removal "
            "target 1.0. Read ``artifact`` instead."
        ),
    )
    total_cost_usd: float | None = None
    error: str | None = None
    gate_context: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Populated iff status='pending' and awaiting='gate'. Keys "
            "at M11: 'gate_prompt' (str, the prompt the HumanGate "
            "recorded), 'gate_id' (str, the gate identifier), "
            "'workflow_id' (str), 'checkpoint_ts' (str, ISO-8601 "
            "stamp at projection time — not the checkpointer's own "
            "timestamp). Forward-compat: M12 will extend this dict "
            "with cascade-transcript keys (audit_verdict, "
            "audit_reasons, suggested_approach) without a schema "
            "break."
        ),
    )


class RunSummary(BaseModel):
    """A row from the ``runs`` registry table, wire-ready for MCP clients.

    Field names mirror the dict keys returned by
    :meth:`ai_workflows.primitives.storage.SQLiteStorage.list_runs` so a
    caller can construct a summary via ``RunSummary(**row)`` without a
    translation step. ``total_cost_usd`` is the single cost surface the
    MCP server exposes — per the M4 kickoff decision dropping the
    ``get_cost_report`` tool in favour of ``list_runs``.
    """

    run_id: str
    workflow_id: str
    status: str
    started_at: str
    finished_at: str | None = None
    total_cost_usd: float | None = None


class ListRunsInput(BaseModel):
    """Arguments to the ``list_runs`` tool.

    ``workflow`` and ``status`` are exact-match filters that compose with
    ``AND`` (matching the CLI's ``list-runs`` behaviour). ``limit`` is
    bounded at the boundary: the underlying SQLite query is unbounded by
    default, but a hostile client should not be able to demand 10M rows
    in one call — 500 is the same cap the CLI command enforces.
    """

    workflow: str | None = None
    status: str | None = None
    limit: int = Field(default=20, ge=1, le=500)


class CancelRunInput(BaseModel):
    """Arguments to the ``cancel_run`` tool."""

    run_id: str


class CancelRunOutput(BaseModel):
    """Response from the ``cancel_run`` tool.

    ``"cancelled"`` — the row was in ``status='pending'`` and has been
    flipped to ``'cancelled'`` with ``finished_at`` stamped.
    ``"already_terminal"`` — the row was already in a terminal state
    (``completed`` / ``gate_rejected`` / ``cancelled`` / ``errored``) so
    the cancel is a no-op. See [architecture.md §8.7](../../design_docs/architecture.md)
    for the M4 / M6 cancellation split.
    """

    run_id: str
    status: Literal["cancelled", "already_terminal"]


class RunAuditCascadeInput(BaseModel):
    """Arguments to the ``run_audit_cascade`` tool.

    Audit an existing artefact via the M12 auditor tier outside of a
    workflow run. The artefact is supplied via one of the two source
    fields below — exactly one must be set; the validator rejects the
    payload if zero or both are set.

    Per ADR-0004 §Decision item 7 (amendment to land at M12 T07 close-out
    — standalone tool is an adjacent caller of the auditor tier, not a
    re-use of the compiled cascade graph; H1 Option A locked 2026-04-27),
    this is the standalone invocation surface that lets a caller spot-
    check a completed plan, draft spec, or generated code slice without
    kicking off a full workflow.

    A future task may extend the input with a ``file_path_ref`` slot for
    sandboxed-root file-path artefact resolution; deferred from T05 per
    scope discipline (see spec §Propagation status).
    """

    run_id_ref: str | None = Field(
        default=None,
        description=(
            "Audit an artefact from a completed `aiw run` with this "
            "run_id. MUST be paired with ``artefact_kind`` (caller "
            "picks which kind — different workflows write under "
            "different kinds: planner uses 'plan', slice_refactor uses "
            "'applied_artifacts'). The tool calls "
            "``storage.read_artifact(run_id, kind)``. Raises ToolError "
            "if (run_id, kind) is not found."
        ),
    )
    artefact_kind: str | None = Field(
        default=None,
        description=(
            "Kind argument to ``storage.read_artifact(run_id, kind)``. "
            "Required iff ``run_id_ref`` is set; rejected (ValidationError) "
            "if ``run_id_ref`` is unset. Caller-known values include "
            "``'plan'`` (planner workflow) and ``'applied_artifacts'`` "
            "(slice_refactor workflow); external workflows declare their "
            "own kinds via ``storage.write_artifact(run_id, kind, ...)`` "
            "calls in their workflow code (KDR-013)."
        ),
    )
    inline_artefact_ref: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Audit this dict verbatim. The dict shape is opaque to the "
            "tool — the caller is responsible for shaping it consistent "
            "with what the auditor's prompt expects. Useful for spot-"
            "checking a draft artefact before committing it to a run."
        ),
    )
    tier_ceiling: Literal["sonnet", "opus"] = Field(
        default="opus",
        description=(
            "Auditor tier. 'opus' uses ``auditor-opus`` (highest tier). "
            "'sonnet' uses ``auditor-sonnet`` (cheaper). Default 'opus' "
            "matches ADR-0004's standalone-spot-check intent (Max flat-"
            "rate $0). Per ADR-0009 / KDR-014: this is a per-call input "
            "(operator picks which tier to spend on for this specific "
            "audit), NOT a quality knob (which would be a workflow "
            "default the framework owns). The framework default is "
            "'opus'; the per-call override is the operator's privilege."
        ),
    )

    @model_validator(mode="after")
    def _exactly_one_artefact_source(self) -> RunAuditCascadeInput:
        """Enforce one-of {run_id_ref, inline_artefact_ref}.

        Require artefact_kind iff run_id_ref is set.
        """
        sources = [self.run_id_ref, self.inline_artefact_ref]
        set_count = sum(1 for s in sources if s is not None)
        if set_count != 1:
            raise ValueError(
                f"exactly one of run_id_ref / inline_artefact_ref must be set (got {set_count})"
            )
        if self.run_id_ref is not None and self.artefact_kind is None:
            raise ValueError(
                "artefact_kind is required when run_id_ref is set "
                "(caller picks the kind: planner uses 'plan', "
                "slice_refactor uses 'applied_artifacts', etc.)"
            )
        if self.run_id_ref is None and self.artefact_kind is not None:
            raise ValueError(
                "artefact_kind is only meaningful when run_id_ref is set"
            )
        return self


class RunAuditCascadeOutput(BaseModel):
    """Response from the ``run_audit_cascade`` tool.

    Carries the verdict structure the caller can act on, plus
    telemetry for the cost-aware operator.
    """

    passed: bool = Field(
        description=(
            "True iff the auditor returned `passed=True` on the artefact. "
            "False on `passed=False`. The standalone tool uses single-pass "
            "dispatch (RetryPolicy(max_transient_attempts=1, "
            "max_semantic_attempts=1)) so there is no retry-cycle path."
        ),
    )
    verdicts_by_tier: dict[str, AuditVerdict] = Field(
        default_factory=dict,
        description=(
            "Map of {tier_name: AuditVerdict} for the auditor tier "
            "invoked. T05 lands single-tier audit (one entry: "
            "{auditor_tier_used: AuditVerdict(...)}); future multi-tier "
            "cascading would populate multiple entries. AuditVerdict is "
            "the same model T02's cascade primitive emits."
        ),
    )
    suggested_approach: str | None = Field(
        default=None,
        description=(
            "The auditor's suggested-approach text from the verdict "
            "(matches `AuditVerdict.suggested_approach`). Populated on "
            "`passed=False`; None on `passed=True`."
        ),
    )
    total_cost_usd: float = Field(
        default=0.0,
        description=(
            "Total USD cost of the audit invocation. Includes the auditor "
            "LLM call; excludes the original artefact production cost. "
            "Cost is $0 today under Claude Max flat-rate pricing "
            "(`pricing.yaml`); a future per-tier-pricing change would "
            "surface non-zero values without a schema break."
        ),
    )
    by_role: dict[str, float] | None = Field(
        default=None,
        description=(
            "Per-role cost breakdown via T04's "
            "``CostTracker.by_role(audit_run_id)``. Populated only when "
            "the audit call actually ran (not on early ToolError paths). "
            "For the standalone single-pass audit (Option A bypasses the "
            "cascade primitive — no primary call), one entry: "
            "``{'auditor': <cost>}``. The author/primary key does NOT "
            "appear because the supplied artefact is never re-generated."
        ),
    )
