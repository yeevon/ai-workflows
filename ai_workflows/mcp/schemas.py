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

    Note: the ``tier_overrides`` field named in pre-M4 architecture notes
    is intentionally absent; it lands at M5 T05 when the graph layer
    begins consuming it.
    """

    workflow_id: str
    inputs: dict[str, Any]
    budget_cap_usd: float | None = None
    run_id: str | None = None


class RunWorkflowOutput(BaseModel):
    """Response from the ``run_workflow`` tool.

    ``status`` is the run's state post-dispatch: ``"pending"`` when the
    graph yielded at a :class:`HumanGate` interrupt (``awaiting='gate'``),
    ``"completed"`` when the graph reached its terminal artifact node, or
    ``"errored"`` for a dispatch-level failure (budget breach, validator
    exhaust, etc.). ``plan`` is populated only on ``"completed"``;
    ``error`` carries a descriptive message on ``"errored"`` so MCP
    clients see the reason in-band rather than through a raw Python
    exception (M4 T02 AC).
    """

    run_id: str
    status: Literal["pending", "completed", "errored"]
    awaiting: Literal["gate"] | None = None
    plan: dict[str, Any] | None = None
    total_cost_usd: float | None = None
    error: str | None = None


class ResumeRunInput(BaseModel):
    """Arguments to the ``resume_run`` tool."""

    run_id: str
    gate_response: Literal["approved", "rejected"] = "approved"


class ResumeRunOutput(BaseModel):
    """Response from the ``resume_run`` tool.

    ``status`` can be ``"completed"`` (approved → plan persisted),
    ``"gate_rejected"`` (rejected by the caller at the gate),
    ``"pending"`` (another gate fired post-resume), or ``"errored"``.
    ``error`` carries a descriptive message on ``"errored"`` so MCP
    clients see the reason in-band (M4 T03 AC, parallel to the T02
    ``RunWorkflowOutput.error`` pattern).
    """

    run_id: str
    status: Literal["pending", "completed", "gate_rejected", "errored"]
    plan: dict[str, Any] | None = None
    total_cost_usd: float | None = None
    error: str | None = None


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
