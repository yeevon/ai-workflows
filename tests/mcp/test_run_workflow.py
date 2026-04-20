"""Tests for M4 Task 02 — `run_workflow` MCP tool.

Covers the T02 acceptance criteria:

* Gate-pause dispatch returns ``status="pending"`` + ``awaiting="gate"``
  + a populated ``total_cost_usd`` and no ``plan``.
* ``Storage.create_run`` is called exactly once per tool call (the
  ``runs`` row is queryable post-dispatch).
* Budget breach surfaces as ``status="errored"`` with a descriptive
  error string (not as an uncaught Python exception).
* Unknown workflow raises :class:`fastmcp.exceptions.ToolError` which
  FastMCP would render as a JSON-RPC error response.
* CLI regression is pinned separately in :mod:`tests/cli/test_run.py`.

All LLM calls are stubbed at the adapter level so no real API fires;
``AIW_CHECKPOINT_DB`` / ``AIW_STORAGE_DB`` redirect under ``tmp_path``
so nothing touches ``~/.ai-workflows/`` (same pattern as
:mod:`tests/cli/test_run.py`).
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
from ai_workflows.mcp.schemas import RunWorkflowInput
from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.tiers import LiteLLMRoute
from ai_workflows.workflows.planner import build_planner


class _StubLiteLLMAdapter:
    """Scripted LiteLLM-adapter stub — mirrors tests/cli/test_run.py."""

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


def _read_run_row(db_path: Path, run_id: str) -> dict[str, Any] | None:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


@pytest.mark.asyncio
async def test_run_workflow_pauses_at_gate_and_stamps_cost(tmp_path: Path) -> None:
    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
    ]

    server = build_server()
    tool = await server.get_tool("run_workflow")
    payload = RunWorkflowInput(
        workflow_id="planner",
        inputs={"goal": "Ship the marketing page.", "context": None, "max_steps": 10},
        run_id="run-t02-gate",
    )
    result = await tool.fn(payload)

    assert result.run_id == "run-t02-gate"
    assert result.status == "pending"
    assert result.awaiting == "gate"
    assert result.plan is None
    assert result.total_cost_usd is not None
    assert result.total_cost_usd == pytest.approx(0.0033)
    assert result.error is None

    row = _read_run_row(tmp_path / "storage.sqlite", "run-t02-gate")
    assert row is not None
    assert row["workflow_id"] == "planner"
    assert row["status"] == "pending"
    assert row["total_cost_usd"] == pytest.approx(0.0033)


@pytest.mark.asyncio
async def test_run_workflow_budget_breach_returns_errored_status(
    tmp_path: Path,
) -> None:
    """AC: budget cap trips surface as ``status="errored"`` with descriptive error.

    ``BudgetExceeded`` / ``NonRetryable("budget exceeded: ...")`` is
    captured by ``wrap_with_error_handler`` and lands in the checkpoint
    state; the dispatch helper pulls it out via ``aget_state`` and
    returns it in ``result.error``. No raw Python exception escapes the
    tool.
    """
    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
        # Extra entries so a retry cascade cannot exhaust the stub and
        # mask the budget signal with a misleading AssertionError.
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
    ]

    server = build_server()
    tool = await server.get_tool("run_workflow")
    payload = RunWorkflowInput(
        workflow_id="planner",
        inputs={"goal": "Ship the marketing page.", "context": None, "max_steps": 10},
        budget_cap_usd=0.00001,
        run_id="run-t02-budget",
    )
    result = await tool.fn(payload)

    assert result.status == "errored"
    assert result.error is not None
    assert "budget" in result.error.lower()
    assert result.plan is None
    assert result.awaiting is None


@pytest.mark.asyncio
async def test_run_workflow_unknown_workflow_raises_tool_error() -> None:
    server = build_server()
    tool = await server.get_tool("run_workflow")
    payload = RunWorkflowInput(
        workflow_id="does_not_exist",
        inputs={"goal": "x", "context": None, "max_steps": 10},
    )
    with pytest.raises(ToolError) as excinfo:
        await tool.fn(payload)
    assert "does_not_exist" in str(excinfo.value)


@pytest.mark.asyncio
async def test_run_workflow_auto_generates_run_id_when_none_passed(
    tmp_path: Path,
) -> None:
    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
    ]

    server = build_server()
    tool = await server.get_tool("run_workflow")
    payload = RunWorkflowInput(
        workflow_id="planner",
        inputs={"goal": "Ship the marketing page.", "context": None, "max_steps": 10},
    )
    result = await tool.fn(payload)

    # Auto-generated ids are 26-char Crockford-base32 ULIDs.
    assert len(result.run_id) == 26
    assert result.status == "pending"
    row = _read_run_row(tmp_path / "storage.sqlite", result.run_id)
    assert row is not None


def test_mcp_server_module_does_not_read_provider_secrets() -> None:
    """KDR-003 boundary: the MCP server module doesn't read provider env vars."""
    server_src = (
        Path(__file__).resolve().parent.parent.parent
        / "ai_workflows"
        / "mcp"
        / "server.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "GEMINI_API_KEY",
        "ANTHROPIC_API_KEY",
        "import anthropic",
        "from anthropic",
    ):
        assert forbidden not in server_src, (
            f"KDR-003 violated: {forbidden!r} appears in mcp/server.py"
        )
