"""FastMCP server factory for the ai-workflows MCP surface.

M4 Task 01 shipped the scaffold; M4 Task 02 wires the first real tool.
M6 Task 02 lands in-flight ``cancel_run`` wiring (carry-over from M4
T05): ``run_workflow`` registers its dispatch task under the run id in
a process-local registry so ``cancel_run`` can call
:meth:`asyncio.Task.cancel` before performing the existing storage-level
status flip (``architecture.md §8.7``).

* ``run_workflow``  — wired in M4 T02 against
  :func:`ai_workflows.workflows._dispatch.run_workflow`, the shared
  dispatch helper that the ``aiw run`` CLI command also routes through.
  M6 T02 wraps the dispatch call in :func:`asyncio.create_task` and
  registers the task so the in-flight cancel path can abort it.
* ``resume_run``    — M4 T03.
* ``list_runs``     — M4 T04.
* ``cancel_run``    — M4 T05 (storage-flip only) + M6 T02 (in-flight
  :meth:`asyncio.Task.cancel` before the storage flip; unknown-run-id
  falls back to the M4 behaviour cleanly).

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
  and MCP surfaces stay in lockstep. ``_dispatch`` invokes LangGraph
  with ``durability="sync"`` so the last-completed-step checkpoint is
  guaranteed to hit SQLite before :class:`asyncio.CancelledError`
  unwinds the task — load-bearing for the cancel-and-immediately-resume
  path that M6 T02 tests.
* :mod:`ai_workflows.cli` — the sibling CLI surface that routes through
  the same dispatch helper. The CLI does not participate in in-flight
  cancellation (no long-running MCP session to hold the task handle).

Per the import-linter four-layer contract, ``ai_workflows.mcp`` is part
of the surfaces layer: it may import
:mod:`ai_workflows.workflows` / :mod:`ai_workflows.primitives` but
nothing imports it.
"""

from __future__ import annotations

import asyncio

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


_ACTIVE_RUNS: dict[str, asyncio.Task] = {}
"""Process-local registry of in-flight run dispatch tasks (M6 T02).

Keyed by resolved ``run_id`` (the value ``_dispatch_run_workflow``
returns — either the caller-supplied id or an auto-generated ULID).
The registry is **best-effort** by architectural contract
(``architecture.md §8.7``): the storage-level status flip that
:meth:`SQLiteStorage.cancel_run` performs is authoritative, and the
:meth:`asyncio.Task.cancel` call is a nicety that unwinds an
actively-running dispatch task sooner than waiting for a gate or
timeout. The registry does not survive process restart; a run that
was mid-flight in a crashed MCP server simply loses its in-flight
cancel path, but ``runs.status`` is still flippable via the storage
surface.

Entries are inserted by ``run_workflow`` before the ``await`` on the
wrapping task and removed in the task's ``finally`` block so the
registry does not leak — in the happy path, the completion / pause
surfaces the id is already gone by the time ``cancel_run`` would
check. That no-longer-present branch falls back to the M4 storage-only
behaviour which, for a terminal row, is a no-op (``"already_terminal"``)
and for a still-``pending`` row does the flip — precisely the M4
contract.
"""


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

        M6 T02: the dispatch call is wrapped in an
        :func:`asyncio.create_task` and registered under the resolved
        ``run_id`` in :data:`_ACTIVE_RUNS` so ``cancel_run`` can abort
        the in-flight task. The registry entry is inserted **before**
        the ``await`` (so a cancel racing the run is visible) and
        removed in a ``finally`` regardless of success / failure /
        cancellation.
        """
        run_id_key = payload.run_id

        async def _dispatch_body() -> dict:
            return await _dispatch_run_workflow(
                workflow=payload.workflow_id,
                inputs=payload.inputs,
                budget_cap_usd=payload.budget_cap_usd,
                run_id=payload.run_id,
                tier_overrides=payload.tier_overrides,
            )

        task = asyncio.create_task(_dispatch_body())
        if run_id_key is not None:
            _ACTIVE_RUNS[run_id_key] = task
        try:
            try:
                result = await task
            except (UnknownWorkflowError, UnknownTierError) as exc:
                raise ToolError(str(exc)) from None
        finally:
            if run_id_key is not None:
                _ACTIVE_RUNS.pop(run_id_key, None)
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
        """Cancel a run: abort any in-flight dispatch task, then flip storage.

        Two halves per ``architecture.md §8.7``:

        1. **In-flight abort (M6 T02).** If :data:`_ACTIVE_RUNS` has a
           task for this ``run_id``, call :meth:`asyncio.Task.cancel`.
           This is best-effort and does not block on the task actually
           unwinding — the caller is notified via the storage flip
           return value, not by awaiting the cancelled task here
           (blocking here would let a stuck worker hang the MCP
           connection indefinitely). ``durability="sync"`` on the
           dispatcher's ``ainvoke`` call guarantees the
           last-completed-step checkpoint hits SQLite before
           :class:`asyncio.CancelledError` propagates, so a subsequent
           ``resume_run`` on the same ``run_id`` can continue from the
           last durable state.
        2. **Storage flip (M4 T05).** Authoritative per the
           architectural contract. Flips ``runs.status`` to
           ``cancelled`` + stamps ``finished_at``. A subsequent
           ``resume_run`` refuses cancelled rows via the M4 T03
           precondition guard.

        If the run is not in :data:`_ACTIVE_RUNS` (already completed,
        paused at a gate, or started in another process), step 1 is a
        no-op and we fall through to the M4 storage-only path cleanly
        — no ``KeyError``.
        """
        task = _ACTIVE_RUNS.get(payload.run_id)
        if task is not None and not task.done():
            task.cancel()
        storage = await SQLiteStorage.open(default_storage_path())
        try:
            result = await storage.cancel_run(payload.run_id)
        except ValueError as exc:
            raise ToolError(str(exc)) from None
        return CancelRunOutput(run_id=payload.run_id, status=result)

    return mcp
