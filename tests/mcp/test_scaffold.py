"""Scaffold tests for the M4 MCP surface.

Pins the Task 01 contract: :func:`ai_workflows.mcp.build_server` returns
a fresh :class:`fastmcp.FastMCP` with the four expected tools
(``run_workflow``, ``resume_run``, ``list_runs``, ``cancel_run``), each
raising :class:`NotImplementedError` until M4 T02–T05 land. Also verifies
the pydantic I/O models in :mod:`ai_workflows.mcp.schemas` round-trip
cleanly and that importing the MCP surface doesn't pull anything above
its layer.
"""

from __future__ import annotations

import subprocess
import sys

import pytest
from fastmcp import FastMCP

from ai_workflows.mcp import build_server
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

EXPECTED_TOOLS = {"run_workflow", "resume_run", "list_runs", "cancel_run"}


def test_build_server_returns_fastmcp_instance() -> None:
    server = build_server()
    assert isinstance(server, FastMCP)


def test_build_server_is_idempotent_and_non_global() -> None:
    a = build_server()
    b = build_server()
    assert a is not b


@pytest.mark.asyncio
async def test_all_four_tools_registered() -> None:
    server = build_server()
    tools = await server.list_tools()
    names = {t.name for t in tools}
    assert names == EXPECTED_TOOLS


@pytest.mark.parametrize(
    "model, kwargs",
    [
        (
            RunWorkflowInput,
            {"workflow_id": "planner", "inputs": {"goal": "x"}, "budget_cap_usd": 1.0},
        ),
        (
            RunWorkflowOutput,
            {
                "run_id": "r1",
                "status": "pending",
                "awaiting": "gate",
                "plan": None,
                "total_cost_usd": 0.01,
            },
        ),
        (ResumeRunInput, {"run_id": "r1", "gate_response": "approved"}),
        (
            ResumeRunOutput,
            {"run_id": "r1", "status": "completed", "plan": {"steps": []}, "total_cost_usd": 0.02},
        ),
        (
            RunSummary,
            {
                "run_id": "r1",
                "workflow_id": "planner",
                "status": "completed",
                "started_at": "2026-04-20T00:00:00Z",
                "finished_at": "2026-04-20T00:05:00Z",
                "total_cost_usd": 0.03,
            },
        ),
        (ListRunsInput, {"workflow": "planner", "status": "completed", "limit": 10}),
        (CancelRunInput, {"run_id": "r1"}),
        (CancelRunOutput, {"run_id": "r1", "status": "cancelled"}),
    ],
)
def test_schema_roundtrip(model: type, kwargs: dict) -> None:
    instance = model(**kwargs)
    dumped = instance.model_dump()
    restored = model.model_validate(dumped)
    assert restored == instance


def test_list_runs_input_limit_bounded() -> None:
    with pytest.raises(ValueError):
        ListRunsInput(limit=0)
    with pytest.raises(ValueError):
        ListRunsInput(limit=501)
    assert ListRunsInput(limit=1).limit == 1
    assert ListRunsInput(limit=500).limit == 500


def test_mcp_surface_imports_cleanly_in_clean_interpreter() -> None:
    """Importing ``ai_workflows.mcp`` in a clean interpreter succeeds.

    The surfaces layer is allowed to import :mod:`ai_workflows.workflows`
    / :mod:`ai_workflows.graph` (both of which transitively pull in
    LangGraph, per [architecture.md §3](../../design_docs/architecture.md));
    ``import-linter`` is the authoritative layer-boundary guard.
    This test pins only that the surface can be imported without error
    from a fresh interpreter — catches cases where side-effect imports
    in :mod:`ai_workflows.mcp.server` would blow up outside a pytest
    session (e.g. in a fresh stdio-transport boot).
    """
    proc = subprocess.run(
        [sys.executable, "-c", "import ai_workflows.mcp"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"clean-interpreter import failed:\nstdout={proc.stdout}\nstderr={proc.stderr}"
    )
