"""Tests for M4 Task 05 — `cancel_run` MCP tool.

Covers the T05 acceptance criteria:

* Happy path — a ``pending`` row flips to ``cancelled`` with
  ``finished_at`` stamped; the tool returns ``status="cancelled"``.
* Idempotence — a second ``cancel_run`` on the same id returns
  ``status="already_terminal"`` (the first flip moved it out of
  ``pending``).
* Pre-existing terminal row (``completed`` / ``gate_rejected``) —
  ``cancel_run`` returns ``"already_terminal"`` with no side effect.
* Unknown ``run_id`` — surfaces as a :class:`fastmcp.exceptions.ToolError`
  (JSON-RPC error), not a raw Python exception.
* Cross-tool behaviour — ``run_workflow`` → ``cancel_run`` → ``resume_run``
  refuses with a clear "cancelled" error (exercises the T03 precondition
  guard end-to-end).

Sandbox pattern mirrors :mod:`tests/mcp/test_resume_run.py`:
``AIW_STORAGE_DB`` / ``AIW_CHECKPOINT_DB`` redirect under ``tmp_path``;
``_StubLiteLLMAdapter`` is installed autouse so no real API fires.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastmcp.exceptions import ToolError

from ai_workflows import workflows
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.mcp import build_server
from ai_workflows.mcp.schemas import (
    CancelRunInput,
    ResumeRunInput,
    RunWorkflowInput,
)
from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.tiers import LiteLLMRoute
from ai_workflows.workflows.planner import build_planner


class _StubLiteLLMAdapter:
    """Scripted LiteLLM-adapter stub — mirrors tests/mcp/test_resume_run.py."""

    script: list[Any] = []
    call_count: int = 0

    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        self.route = route

    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict],
        response_format: Any = None,
    ) -> tuple[str, TokenUsage]:
        _StubLiteLLMAdapter.call_count += 1
        if not _StubLiteLLMAdapter.script:
            raise AssertionError("stub script exhausted")
        head = _StubLiteLLMAdapter.script.pop(0)
        if isinstance(head, BaseException):
            raise head
        text, cost = head
        return text, TokenUsage(
            input_tokens=11,
            output_tokens=17,
            cost_usd=cost,
            model=self.route.model,
        )

    @classmethod
    def reset(cls) -> None:
        cls.script = []
        cls.call_count = 0


@pytest.fixture(autouse=True)
def _reset_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    _StubLiteLLMAdapter.reset()
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _StubLiteLLMAdapter)


@pytest.fixture(autouse=True)
def _reensure_planner_registered() -> Iterator[None]:
    workflows._reset_for_tests()
    workflows.register("planner", build_planner)
    yield


@pytest.fixture(autouse=True)
def _redirect_default_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("AIW_STORAGE_DB", str(tmp_path / "storage.sqlite"))


def _valid_explorer_json() -> str:
    return json.dumps(
        {
            "summary": "Three-step delivery.",
            "considerations": ["Copy tone", "CTA placement"],
            "assumptions": ["Design system stable"],
        }
    )


def _valid_plan_json() -> str:
    return json.dumps(
        {
            "goal": "Ship the marketing page.",
            "summary": "Three-step delivery of the static hero + CTA page.",
            "steps": [
                {
                    "index": 1,
                    "title": "Draft hero copy",
                    "rationale": "Lock tone before layout.",
                    "actions": ["Sketch headline", "List CTAs"],
                }
            ],
        }
    )


async def _run_to_gate(server: Any, run_id: str) -> None:
    """Drive ``run_workflow`` to the planner's HumanGate pause."""
    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
    ]
    run_tool = await server.get_tool("run_workflow")
    result = await run_tool.fn(
        RunWorkflowInput(
            workflow_id="planner",
            inputs={"goal": "Ship the marketing page.", "context": None, "max_steps": 10},
            run_id=run_id,
        )
    )
    assert result.status == "pending"
    assert result.awaiting == "gate"


def _read_run_row(db_path: Path, run_id: str) -> dict[str, Any] | None:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


@pytest.mark.asyncio
async def test_cancel_run_flips_pending_row_to_cancelled(tmp_path: Path) -> None:
    """Seed a ``pending`` row → cancel flips status + stamps finished_at."""
    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await storage.create_run("run-t05-cancel", "planner", None)

    server = build_server()
    tool = await server.get_tool("cancel_run")
    result = await tool.fn(CancelRunInput(run_id="run-t05-cancel"))

    assert result.run_id == "run-t05-cancel"
    assert result.status == "cancelled"

    row = _read_run_row(tmp_path / "storage.sqlite", "run-t05-cancel")
    assert row is not None
    assert row["status"] == "cancelled"
    assert row["finished_at"] is not None


@pytest.mark.asyncio
async def test_cancel_run_second_call_is_already_terminal(tmp_path: Path) -> None:
    """Idempotence — second cancel on same id returns ``already_terminal``."""
    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await storage.create_run("run-t05-idem", "planner", None)

    server = build_server()
    tool = await server.get_tool("cancel_run")

    first = await tool.fn(CancelRunInput(run_id="run-t05-idem"))
    assert first.status == "cancelled"
    second = await tool.fn(CancelRunInput(run_id="run-t05-idem"))
    assert second.status == "already_terminal"


@pytest.mark.asyncio
async def test_cancel_run_on_terminal_row_is_noop(tmp_path: Path) -> None:
    """A row already in a terminal state returns ``already_terminal``."""
    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await storage.create_run("run-t05-done", "planner", None)
    await storage.update_run_status("run-t05-done", "completed")
    pre_row = _read_run_row(tmp_path / "storage.sqlite", "run-t05-done")
    assert pre_row is not None
    pre_finished_at = pre_row["finished_at"]

    server = build_server()
    tool = await server.get_tool("cancel_run")
    result = await tool.fn(CancelRunInput(run_id="run-t05-done"))
    assert result.status == "already_terminal"

    post_row = _read_run_row(tmp_path / "storage.sqlite", "run-t05-done")
    assert post_row is not None
    assert post_row["status"] == "completed"
    assert post_row["finished_at"] == pre_finished_at


@pytest.mark.asyncio
async def test_cancel_run_unknown_run_id_raises_tool_error() -> None:
    """Unknown id → JSON-RPC error, not a raw Python exception."""
    server = build_server()
    tool = await server.get_tool("cancel_run")
    with pytest.raises(ToolError) as excinfo:
        await tool.fn(CancelRunInput(run_id="does-not-exist"))
    assert "no run found" in str(excinfo.value)
    assert "does-not-exist" in str(excinfo.value)


@pytest.mark.asyncio
async def test_cancel_then_resume_is_refused(tmp_path: Path) -> None:
    """End-to-end: pause at gate → cancel → resume refuses with clear error."""
    server = build_server()
    await _run_to_gate(server, run_id="run-t05-e2e")

    cancel_tool = await server.get_tool("cancel_run")
    cancel_result = await cancel_tool.fn(CancelRunInput(run_id="run-t05-e2e"))
    assert cancel_result.status == "cancelled"

    resume_tool = await server.get_tool("resume_run")
    with pytest.raises(ToolError) as excinfo:
        await resume_tool.fn(ResumeRunInput(run_id="run-t05-e2e"))
    message = str(excinfo.value)
    assert "cancelled" in message
    assert "run-t05-e2e" in message
