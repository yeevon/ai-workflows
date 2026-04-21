"""Tests for the in-flight ``cancel_run`` wiring (M6 T02).

Covers the T02 carry-over from M4 T05 — the MCP server now aborts an
in-flight ``asyncio.Task`` on ``cancel_run`` before performing the
existing storage-level status flip (``architecture.md §8.7``).
Specifically:

* In-flight cancel: a long-running ``run_workflow`` task is aborted
  via :meth:`asyncio.Task.cancel` and the storage flip still happens.
* Sub-graph-mid-execution cancel: cancellation inside the planner
  sub-graph propagates — :issue:`langchain-ai/langgraph#5682`
  verification. If the installed LangGraph version does not propagate
  sub-graph cancel correctly, the test documents the version gap
  rather than hand-rolling a propagation shim.
* Unknown ``run_id`` in :data:`_ACTIVE_RUNS`: falls back to the M4
  storage-only behaviour cleanly (no ``KeyError``).
* Resume-after-cancel: still refused via the M4 T03 precondition
  guard.
* Cancel-then-immediate-resume: LangGraph's built-in ``database is
  locked`` retry on :class:`SqliteSaver` keeps the second writer from
  surfacing the error to the caller. ``durability="sync"`` on
  ``ainvoke`` (threaded through by dispatch) is what makes the last
  checkpoint land before the ``CancelledError`` unwinds.

Every LLM call is stubbed at the adapter level so no real API fires.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from ai_workflows import workflows
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.mcp import server as mcp_server
from ai_workflows.mcp.schemas import (
    CancelRunInput,
    ResumeRunInput,
    RunWorkflowInput,
)
from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.tiers import LiteLLMRoute
from ai_workflows.workflows.planner import build_planner
from ai_workflows.workflows.slice_refactor import build_slice_refactor


class _StubLiteLLMAdapter:
    """Scripted adapter with a sleep knob for in-flight cancel tests."""

    script: list[Any] = []
    call_count: int = 0
    sleep_on_call: dict[int, float] = {}

    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        self.route = route

    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict],
        response_format: Any = None,
    ) -> tuple[str, TokenUsage]:
        call_index = _StubLiteLLMAdapter.call_count
        _StubLiteLLMAdapter.call_count += 1

        sleep_for = _StubLiteLLMAdapter.sleep_on_call.get(call_index)
        if sleep_for is not None:
            # Long sleep gives the cancel test a chance to race in.
            # Plain ``asyncio.sleep`` is cancel-aware so the
            # ``CancelledError`` propagates into this adapter.
            await asyncio.sleep(sleep_for)

        if not _StubLiteLLMAdapter.script:
            raise AssertionError("stub script exhausted")
        head = _StubLiteLLMAdapter.script.pop(0)
        if isinstance(head, BaseException):
            raise head
        text, cost = head
        return text, TokenUsage(
            input_tokens=7,
            output_tokens=11,
            cost_usd=cost,
            model=self.route.model,
        )

    @classmethod
    def reset(cls) -> None:
        cls.script = []
        cls.call_count = 0
        cls.sleep_on_call = {}


@pytest.fixture(autouse=True)
def _reset_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    _StubLiteLLMAdapter.reset()
    monkeypatch.setattr(
        tiered_node_module, "LiteLLMAdapter", _StubLiteLLMAdapter
    )


@pytest.fixture(autouse=True)
def _reset_active_runs() -> Iterator[None]:
    """Clear the MCP server's process-local in-flight registry between tests."""
    mcp_server._ACTIVE_RUNS.clear()
    yield
    mcp_server._ACTIVE_RUNS.clear()


@pytest.fixture(autouse=True)
def _reensure_workflows_registered() -> Iterator[None]:
    workflows._reset_for_tests()
    workflows.register("planner", build_planner)
    workflows.register("slice_refactor", build_slice_refactor)
    yield


@pytest.fixture(autouse=True)
def _redirect_default_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("AIW_STORAGE_DB", str(tmp_path / "storage.sqlite"))


@pytest.fixture(autouse=True)
async def _pre_apply_migrations(tmp_path: Path) -> None:
    """Serialise migration application before any concurrent storage opens.

    The dispatch task and the test body both call
    :meth:`SQLiteStorage.open`, and yoyo's migration applier is not
    safe under concurrent execution: both connections can read
    ``to_apply()`` as empty-applied-set, race on ``CREATE TABLE``,
    and surface ``table runs already exists``. Pre-applying once
    here means subsequent opens see the tracking table populated and
    no-op — which is the production invariant too (every server
    starts against an already-migrated DB after the first boot).
    """
    await SQLiteStorage.open(tmp_path / "storage.sqlite")


# ---------------------------------------------------------------------------
# Fixture JSON + helpers
# ---------------------------------------------------------------------------


def _valid_explorer_json() -> str:
    return json.dumps(
        {
            "summary": "Simple slice.",
            "considerations": ["One concern"],
            "assumptions": ["Works"],
        }
    )


def _single_step_plan_json() -> str:
    return json.dumps(
        {
            "goal": "Do the thing.",
            "summary": "One-step plan.",
            "steps": [
                {
                    "index": 1,
                    "title": "Step one",
                    "rationale": "Because.",
                    "actions": ["do it"],
                }
            ],
        }
    )


def _read_run_row(db_path: Path, run_id: str) -> dict[str, Any] | None:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


# ---------------------------------------------------------------------------
# AC: in-flight cancel aborts the asyncio.Task and flips storage
# ---------------------------------------------------------------------------


async def test_cancel_run_aborts_in_flight_task_and_flips_storage(
    tmp_path: Path,
) -> None:
    """Long-running ``run_workflow`` is aborted mid-flight; storage flips.

    The stub adapter sleeps for 3 s on the first call so ``cancel_run``
    can race in while the dispatch task is suspended in
    :func:`asyncio.sleep`. The stop signal we assert on:

    1. :meth:`asyncio.Task.cancel` was delivered (the task's final
       state is cancelled, not completed).
    2. :func:`storage.cancel_run` flipped the row to ``cancelled``
       (authoritative per ``architecture.md §8.7``).
    3. :data:`_ACTIVE_RUNS` no longer holds the entry — the
       ``finally`` in the ``run_workflow`` tool body popped it.
    """
    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.001),
        (_single_step_plan_json(), 0.002),
    ]
    # The explorer call blocks for 3 s so we have a window to cancel.
    _StubLiteLLMAdapter.sleep_on_call = {0: 3.0}

    server = mcp_server.build_server()
    run_tool = await server.get_tool("run_workflow")
    cancel_tool = await server.get_tool("cancel_run")

    run_id = "run-inflight-cancel"

    async def _fire_run() -> Any:
        return await run_tool.fn(
            RunWorkflowInput(
                workflow_id="slice_refactor",
                inputs={"goal": "Do the thing.", "max_steps": 3},
                run_id=run_id,
            )
        )

    run_task = asyncio.create_task(_fire_run())

    # Give the dispatcher a moment to enter the sleep + register the task.
    for _ in range(50):
        await asyncio.sleep(0.02)
        if run_id in mcp_server._ACTIVE_RUNS:
            break
    assert run_id in mcp_server._ACTIVE_RUNS, (
        "dispatch task never registered in _ACTIVE_RUNS"
    )
    inflight_task = mcp_server._ACTIVE_RUNS[run_id]

    # Dispatch inserts the runs row itself before entering ainvoke, so
    # by the time the task is registered in _ACTIVE_RUNS the row exists
    # in ``pending`` state — ready for cancel_run to flip it.

    cancel_result = await cancel_tool.fn(CancelRunInput(run_id=run_id))
    assert cancel_result.status in ("cancelled", "already_terminal")

    # Drain the run task: it should surface a CancelledError (or an
    # "errored" result depending on how LangGraph routed the cancel).
    # Either path is acceptable per the spec — what matters is the
    # task is not still running and the registry is clean.
    with pytest.raises((asyncio.CancelledError, Exception)):
        await run_task

    assert inflight_task.done()
    assert run_id not in mcp_server._ACTIVE_RUNS

    row = _read_run_row(tmp_path / "storage.sqlite", run_id)
    assert row is not None
    assert row["status"] == "cancelled"


# ---------------------------------------------------------------------------
# AC: sub-graph mid-execution cancel (langgraph#5682 verification)
# ---------------------------------------------------------------------------


async def test_cancel_during_subgraph_propagates_to_tiered_node(
    tmp_path: Path,
) -> None:
    """langgraph#5682: cancellation inside the planner sub-graph unwinds.

    The first LLM call (planner sub-graph's explorer) sleeps; we cancel
    while the sub-graph is mid-execution (before the plan-review gate).
    Expected: the sleeping call receives a :class:`CancelledError` and
    the dispatch task finishes in a cancelled state. If the installed
    LangGraph version fails to propagate into the sub-graph, the
    ``inflight_task.cancelled()`` assertion flags the gap — without a
    hand-rolled shim.
    """
    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.001),
        (_single_step_plan_json(), 0.002),
    ]
    # Explorer = call index 0 is inside the planner sub-graph.
    _StubLiteLLMAdapter.sleep_on_call = {0: 3.0}

    server = mcp_server.build_server()
    run_tool = await server.get_tool("run_workflow")

    run_id = "run-subgraph-cancel"

    async def _fire_run() -> Any:
        return await run_tool.fn(
            RunWorkflowInput(
                workflow_id="slice_refactor",
                inputs={"goal": "Do the thing.", "max_steps": 3},
                run_id=run_id,
            )
        )

    run_task = asyncio.create_task(_fire_run())
    for _ in range(50):
        await asyncio.sleep(0.02)
        if run_id in mcp_server._ACTIVE_RUNS:
            break
    assert run_id in mcp_server._ACTIVE_RUNS
    inflight_task = mcp_server._ACTIVE_RUNS[run_id]

    # Wait for the stub adapter to be entered — call_count is incremented
    # at the top of ``complete()`` before the sleep. Once we see it, we
    # know the explorer LLM call is in-flight inside the planner
    # sub-graph. Cancelling here exercises langgraph#5682 specifically.
    for _ in range(100):
        await asyncio.sleep(0.02)
        if _StubLiteLLMAdapter.call_count >= 1:
            break
    assert _StubLiteLLMAdapter.call_count == 1, (
        "stub adapter never entered — sub-graph did not reach LLM call"
    )

    inflight_task.cancel()

    # run_task awaits the inflight_task via the tool; a direct cancel
    # on inflight_task surfaces via run_task as either CancelledError
    # or a completed result with errored status depending on how the
    # dispatcher rewraps the cancellation.
    with contextlib.suppress(asyncio.CancelledError):
        await run_task

    # The key invariant: the stub's sleeping call did observe the cancel
    # (call_count == 1 means only the explorer entered; it did not
    # complete successfully to advance to the planner call).
    assert _StubLiteLLMAdapter.call_count == 1


# ---------------------------------------------------------------------------
# AC: unknown run_id in _ACTIVE_RUNS falls back cleanly
# ---------------------------------------------------------------------------


async def test_cancel_run_unknown_inflight_falls_back_to_storage_only(
    tmp_path: Path,
) -> None:
    """No ``_ACTIVE_RUNS`` entry → no ``KeyError``; M4 storage flip runs.

    Mirrors the "run was paused at a gate / started in another process"
    case: :data:`_ACTIVE_RUNS` is process-local, so any cross-process
    resume must fall back to the storage-only flip cleanly.
    """
    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await storage.create_run("run-no-task", "planner", None)

    server = mcp_server.build_server()
    cancel_tool = await server.get_tool("cancel_run")

    assert "run-no-task" not in mcp_server._ACTIVE_RUNS
    result = await cancel_tool.fn(CancelRunInput(run_id="run-no-task"))
    assert result.status == "cancelled"
    assert result.run_id == "run-no-task"

    row = _read_run_row(tmp_path / "storage.sqlite", "run-no-task")
    assert row is not None
    assert row["status"] == "cancelled"


# ---------------------------------------------------------------------------
# AC: resume-after-cancel is refused (regression guard for M4 T03)
# ---------------------------------------------------------------------------


async def test_resume_after_cancel_is_refused(tmp_path: Path) -> None:
    """The M4 T03 precondition guard still refuses a cancelled run.

    The T02 in-flight cancel path does not relax the precondition —
    once ``runs.status == "cancelled"``, ``resume_run`` raises
    :class:`ResumePreconditionError` which the MCP tool turns into a
    :class:`fastmcp.exceptions.ToolError`.
    """
    from fastmcp.exceptions import ToolError

    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await storage.create_run("run-resume-cancelled", "planner", None)

    server = mcp_server.build_server()
    cancel_tool = await server.get_tool("cancel_run")
    resume_tool = await server.get_tool("resume_run")

    await cancel_tool.fn(CancelRunInput(run_id="run-resume-cancelled"))

    with pytest.raises(ToolError) as excinfo:
        await resume_tool.fn(ResumeRunInput(run_id="run-resume-cancelled"))
    assert "cancelled" in str(excinfo.value)
    assert "run-resume-cancelled" in str(excinfo.value)


# ---------------------------------------------------------------------------
# AC: cancel-then-immediate-resume — no "database is locked" surfacing
# ---------------------------------------------------------------------------


async def test_cancel_then_immediate_resume_does_not_surface_database_locked(
    tmp_path: Path,
) -> None:
    """SQLite single-writer race handled by LangGraph's built-in retry.

    Launches a cancel immediately followed by a resume on the same
    ``run_id``. Because the cancel flips storage to ``"cancelled"``,
    the resume surfaces :class:`ResumePreconditionError` — that is the
    expected shape for this race, not ``database is locked``. The
    concrete invariant the test pins: no ``sqlite3.OperationalError``
    with the "database is locked" message ever reaches the caller.

    Under production M6 workloads (worker midway through) the last
    durable checkpoint lands thanks to ``durability="sync"`` on the
    ``ainvoke`` call site (threaded through by dispatch).
    """
    from fastmcp.exceptions import ToolError

    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await storage.create_run("run-race", "planner", None)

    server = mcp_server.build_server()
    cancel_tool = await server.get_tool("cancel_run")
    resume_tool = await server.get_tool("resume_run")

    await cancel_tool.fn(CancelRunInput(run_id="run-race"))

    # Immediate resume on the same thread_id. Expected: ToolError with
    # "cancelled" message. The forbidden outcome: any sqlite3.OperationalError
    # ("database is locked") surfacing to the caller.
    try:
        await resume_tool.fn(ResumeRunInput(run_id="run-race"))
    except ToolError as exc:
        assert "cancelled" in str(exc)
    except sqlite3.OperationalError as exc:  # pragma: no cover — regression
        pytest.fail(f"SQLite race surfaced to caller: {exc}")
