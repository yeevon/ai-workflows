"""Pydantic I/O models for the ai-workflows MCP surface.

M4 Task 01 ships the public contract every FastMCP tool in
:mod:`ai_workflows.mcp.server` binds to its ``@mcp.tool()`` signature.
FastMCP auto-derives the JSON-RPC schema from each model's type
annotations (KDR-008), so this module is the source of truth for both
the tool-call request shape and the response shape every MCP host
(Claude Code, Cursor, Zed, ...) consumes.

Relationship to other modules
-----------------------------
* :mod:`ai_workflows.mcp.server` — registers each tool with a signature
  of ``(payload: <Input>) -> <Output>`` drawn from this module.
* :mod:`ai_workflows.primitives.storage` — the shape of :class:`RunSummary`
  mirrors the dict keys ``SQLiteStorage.list_runs`` returns so M4 T04 can
  construct summaries via ``RunSummary(**row)`` without a translation step.
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
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

__all__ = [
    "RunWorkflowInput",
    "RunWorkflowOutput",
    "ResumeRunInput",
    "ResumeRunOutput",
    "RunSummary",
    "ListRunsInput",
    "CancelRunInput",
    "CancelRunOutput",
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
      (``awaiting='gate'``). ``plan`` carries the in-flight draft for
      the operator to review; ``gate_context`` carries the gate prompt,
      id, workflow id, and a projection-time ISO-8601 timestamp.
    * ``"completed"`` — the graph reached its terminal artifact node.
      ``plan`` carries the final artefact.
    * ``"aborted"`` — the Ollama-fallback circuit-breaker gate resolved
      to ABORT (M8 T04) or the double-failure slice hard-stop fired
      (M6 T07 / architecture.md §8.2). ``plan`` is ``None``; ``error``
      carries the distinguishing message.
    * ``"errored"`` — a dispatch-level failure (budget breach, validator
      exhaust, uncaught graph exception). ``plan`` is ``None``; ``error``
      carries a descriptive message so MCP clients see the reason
      in-band rather than through a raw Python exception (M4 T02 AC).

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
    plan: dict[str, Any] | None = None
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
      (``awaiting="gate"``). ``plan`` carries the re-gated draft;
      ``gate_context`` carries the new gate's prompt, id, workflow
      id, and projection-time ISO-8601 timestamp.
    * ``"completed"`` — approved → plan persisted to the artifact
      store. ``plan`` carries the final artefact.
    * ``"gate_rejected"`` — caller rejected at the gate. ``plan``
      carries the last-draft plan (for audit review);
      ``gate_context`` is ``None`` because the gate has already
      resolved.
    * ``"aborted"`` — the Ollama-fallback gate resolved to ABORT on
      the resume path (M8 T04). ``plan`` is ``None``; ``error``
      carries the distinguishing message.
    * ``"errored"`` — a post-gate fault (M4 T03 AC, parallel to
      ``RunWorkflowOutput.error``). ``plan`` is ``None``; ``error``
      carries a descriptive message so MCP clients see the reason
      in-band.

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
    plan: dict[str, Any] | None = None
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
