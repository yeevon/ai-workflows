"""Tests for M4 Task 03 — `resume_run` MCP tool.

Covers the T03 acceptance criteria:

* Approved happy path — run pauses at the gate, resume approves,
  result has ``status="completed"`` + ``plan`` populated +
  ``total_cost_usd`` rolled up; the ``runs`` row lands in ``completed``.
* Rejected — resume with ``gate_response="rejected"`` returns
  ``status="gate_rejected"``, ``plan=None``, and flips the ``runs`` row
  to ``gate_rejected``.
* Unknown ``run_id`` surfaces as :class:`fastmcp.exceptions.ToolError`,
  not an uncaught Python exception.
* Cancelled-run precondition — a run whose ``status="cancelled"``
  refuses resume with a clear ToolError message (T05 depends on this).
* CLI byte-identical regression is pinned separately in
  :mod:`tests/cli/test_resume.py`.

Same sandboxing pattern as :mod:`tests/mcp/test_run_workflow.py`:
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
from ai_workflows.mcp.schemas import ResumeRunInput, RunWorkflowInput
from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.tiers import LiteLLMRoute
from ai_workflows.workflows.planner import build_planner


class _StubLiteLLMAdapter:
    """Scripted LiteLLM-adapter stub — mirrors tests/cli/test_resume.py."""

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
async def test_resume_run_happy_path_completes_and_rolls_up_cost(
    tmp_path: Path,
) -> None:
    server = build_server()
    await _run_to_gate(server, run_id="run-t03-happy")

    resume_tool = await server.get_tool("resume_run")
    result = await resume_tool.fn(
        ResumeRunInput(run_id="run-t03-happy", gate_response="approved")
    )

    assert result.run_id == "run-t03-happy"
    assert result.status == "completed"
    assert result.plan is not None
    assert result.plan["goal"] == "Ship the marketing page."
    assert result.total_cost_usd == pytest.approx(0.0033)
    assert result.error is None

    row = _read_run_row(tmp_path / "storage.sqlite", "run-t03-happy")
    assert row is not None
    assert row["status"] == "completed"
    assert row["total_cost_usd"] == pytest.approx(0.0033)


@pytest.mark.asyncio
async def test_resume_run_rejected_flips_row_and_returns_gate_rejected(
    tmp_path: Path,
) -> None:
    server = build_server()
    await _run_to_gate(server, run_id="run-t03-rej")

    resume_tool = await server.get_tool("resume_run")
    result = await resume_tool.fn(
        ResumeRunInput(run_id="run-t03-rej", gate_response="rejected")
    )

    assert result.status == "gate_rejected"
    # M11 T01 (Gap 1): the rejected branch now preserves the last-draft plan
    # for audit review; pre-M11 this was ``None``. See
    # tests/mcp/test_gate_pause_projection.py::test_gate_rejected_preserves_last_draft_plan
    # for the M11 contract; here we only pin that the existing flip + cost
    # assertions still hold.
    assert result.plan is not None
    assert result.error is None
    assert result.total_cost_usd == pytest.approx(0.0033)

    row = _read_run_row(tmp_path / "storage.sqlite", "run-t03-rej")
    assert row is not None
    assert row["status"] == "gate_rejected"
    assert row["finished_at"] is not None


@pytest.mark.asyncio
async def test_resume_run_unknown_run_id_raises_tool_error() -> None:
    server = build_server()
    resume_tool = await server.get_tool("resume_run")
    with pytest.raises(ToolError) as excinfo:
        await resume_tool.fn(ResumeRunInput(run_id="does-not-exist"))
    assert "no run found" in str(excinfo.value)
    assert "does-not-exist" in str(excinfo.value)


@pytest.mark.asyncio
async def test_resume_run_cancelled_guard_raises_tool_error(
    tmp_path: Path,
) -> None:
    """T05 relies on this: a cancelled run must refuse resume."""
    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await storage.create_run("run-t03-cancelled", "planner", None)
    await storage.update_run_status("run-t03-cancelled", "cancelled")

    server = build_server()
    resume_tool = await server.get_tool("resume_run")
    with pytest.raises(ToolError) as excinfo:
        await resume_tool.fn(ResumeRunInput(run_id="run-t03-cancelled"))
    message = str(excinfo.value)
    assert "cancelled" in message
    assert "run-t03-cancelled" in message
