"""FastMCP server factory for the ai-workflows MCP surface.

M4 Task 01 shipped the scaffold; M4 Task 02 wires the first real tool.

* ``run_workflow``  — wired in M4 T02 against
  :func:`ai_workflows.workflows._dispatch.run_workflow`, the shared
  dispatch helper that the ``aiw run`` CLI command also routes through.
* ``resume_run``    — lands in M4 T03
* ``list_runs``     — lands in M4 T04
* ``cancel_run``    — lands in M4 T05

Relationship to other modules
-----------------------------
* :mod:`ai_workflows.mcp.schemas` — the pydantic I/O models each tool
  binds to its signature. FastMCP auto-derives the JSON-RPC schema from
  those annotations (KDR-008), so this module is only responsible for
  registering the four callables and returning the server instance.
* [architecture.md §4.4](../../design_docs/architecture.md) — lists the
  four tools; the fifth (``get_cost_report``) was dropped at M4 kickoff
  in favour of ``list_runs`` surfacing ``total_cost_usd``.
* :mod:`ai_workflows.workflows._dispatch` — the shared dispatch helper.
  Both this module and :mod:`ai_workflows.cli` call into it so the CLI
  and MCP surfaces stay in lockstep.
* :mod:`ai_workflows.cli` — the sibling CLI surface that routes through
  the same dispatch helper.

Per the import-linter four-layer contract, ``ai_workflows.mcp`` is part
of the surfaces layer: it may import
:mod:`ai_workflows.workflows` / :mod:`ai_workflows.primitives` but
nothing imports it.
"""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from ai_workflows.mcp.schemas import (
    CancelRunInput,
    CancelRunOutput,
    ListRunsInput,
    ResumeRunInput,
    ResumeRunOutput,
    RunSummary,
    RunWorkflowInput,
    RunWorkflowOutput,
)
from ai_workflows.primitives.storage import SQLiteStorage, default_storage_path
from ai_workflows.workflows._dispatch import (
    ResumePreconditionError,
    UnknownTierError,
    UnknownWorkflowError,
)
from ai_workflows.workflows._dispatch import (
    resume_run as _dispatch_resume_run,
)
from ai_workflows.workflows._dispatch import (
    run_workflow as _dispatch_run_workflow,
)

__all__ = ["build_server"]


def build_server() -> FastMCP:
    """Construct a fresh FastMCP server with all four M4 tools registered.

    Returns a new :class:`FastMCP` instance per call so tests can drive
    the surface in-process without global state (mirrors the ``aiw``
    Typer app pattern in :mod:`ai_workflows.cli`).

    Each tool is a ``@mcp.tool()``-decorated coroutine whose signature
    binds one of the pydantic I/O models from
    :mod:`ai_workflows.mcp.schemas`; FastMCP auto-derives the JSON-RPC
    schema from those annotations (KDR-008). Tool bodies raise
    :class:`NotImplementedError` until the M4 T02–T05 tasks wire them.
    """
    mcp = FastMCP("ai-workflows")

    @mcp.tool()
    async def run_workflow(payload: RunWorkflowInput) -> RunWorkflowOutput:
        """Execute a workflow end-to-end. Pauses at HumanGate interrupts.

        Mirrors ``aiw run`` by routing through
        :func:`ai_workflows.workflows._dispatch.run_workflow`. Unknown
        workflow names and unknown ``tier_overrides`` entries (M5 T05)
        surface as a :class:`fastmcp.exceptions.ToolError` (JSON-RPC
        error response); in-band failures (budget breach, validator
        exhaust) come back as ``status="errored"`` with a descriptive
        ``error`` string in the output.
        """
        try:
            result = await _dispatch_run_workflow(
                workflow=payload.workflow_id,
                inputs=payload.inputs,
                budget_cap_usd=payload.budget_cap_usd,
                run_id=payload.run_id,
                tier_overrides=payload.tier_overrides,
            )
        except (UnknownWorkflowError, UnknownTierError) as exc:
            raise ToolError(str(exc)) from None
        return RunWorkflowOutput(**result)

    @mcp.tool()
    async def resume_run(payload: ResumeRunInput) -> ResumeRunOutput:
        """Clear a pending ``HumanGate`` and advance the workflow.

        Mirrors ``aiw resume`` by routing through
        :func:`ai_workflows.workflows._dispatch.resume_run`. Precondition
        failures (unknown run id, cancelled run) and unknown workflow
        names surface as :class:`fastmcp.exceptions.ToolError` (JSON-RPC
        error response); in-band failures (post-gate exception,
        validator exhaust) come back as ``status="errored"`` with a
        descriptive ``error`` string in the output.
        """
        try:
            result = await _dispatch_resume_run(
                run_id=payload.run_id,
                gate_response=payload.gate_response,
            )
        except (ResumePreconditionError, UnknownWorkflowError) as exc:
            raise ToolError(str(exc)) from None
        return ResumeRunOutput(**result)

    @mcp.tool()
    async def list_runs(payload: ListRunsInput) -> list[RunSummary]:
        """List recorded runs (newest first). Pure read — no graph state touched.

        Filters compose with ``AND`` per :meth:`SQLiteStorage.list_runs`.
        Each :class:`RunSummary` carries ``total_cost_usd`` — the sole
        cost surface the MCP server exposes (see the M4 kickoff decision
        dropping ``get_cost_report`` in favour of this field).

        Mirrors ``aiw list-runs`` in :mod:`ai_workflows.cli`. Never opens
        the checkpointer, never compiles a graph.
        """
        storage = await SQLiteStorage.open(default_storage_path())
        rows = await storage.list_runs(
            limit=payload.limit,
            status_filter=payload.status,
            workflow_filter=payload.workflow,
        )
        return [RunSummary(**row) for row in rows]

    @mcp.tool()
    async def cancel_run(payload: CancelRunInput) -> CancelRunOutput:
        """Cancel a pending run via a storage-level status flip.

        M4 owns only the storage-level half of the cancellation story
        per ``architecture.md §8.7``: flip ``runs.status`` to
        ``cancelled`` + stamp ``finished_at``. A subsequent
        ``resume_run`` refuses cancelled rows via the T03 precondition
        guard.

        In-flight LangGraph task abort (``durability="sync"``,
        subgraph / ToolNode guards) lands at M6 T02 when parallel slice
        workers push wall-clock runtime into the minutes range. For
        the planner workflow, which spends almost all of its time
        paused at the ``HumanGate``, the flip covers the dominant case.
        """
        storage = await SQLiteStorage.open(default_storage_path())
        try:
            result = await storage.cancel_run(payload.run_id)
        except ValueError as exc:
            raise ToolError(str(exc)) from None
        return CancelRunOutput(run_id=payload.run_id, status=result)

    return mcp
