"""M4 Task 07 — Hermetic in-process smoke test covering all four MCP tools.

Drives ``run_workflow`` → ``list_runs`` → ``resume_run`` → ``list_runs``
→ ``cancel_run`` → (second run) ``run_workflow`` → ``cancel_run`` →
``resume_run``-refused, all against a stubbed LiteLLM adapter so no
live provider fires. Fulfils the M4 exit criterion *"One smoke test
drives the server in-process (no subprocess) through all four tools"*.

Contrasts with :mod:`tests/e2e/test_planner_smoke.py` (M3 e2e, real
Gemini, ``AIW_E2E=1`` gate): that test validates the live-provider
path; this one validates the MCP tool surface hermetically and is
always part of ``uv run pytest``.

The ``_StubLiteLLMAdapter`` and ``_redirect_default_paths`` patterns
are the same the focused T02 / T03 / T05 tests use — lifting them into
a shared ``conftest.py`` was evaluated and skipped: the fixtures are
small and the duplication cost is lower than the indirection cost for
readers opening this file as the single M4 acceptance smoke.
"""

from __future__ import annotations

import json
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
    ListRunsInput,
    ResumeRunInput,
    RunWorkflowInput,
)
from ai_workflows.primitives.cost import TokenUsage
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


def _planner_inputs() -> dict[str, Any]:
    return {
        "goal": "Ship the marketing page.",
        "context": None,
        "max_steps": 10,
    }


@pytest.mark.asyncio
async def test_mcp_server_all_four_tools_end_to_end() -> None:
    """In-process tour of every M4 MCP tool against stubbed providers.

    Exercises the full M4 surface acceptance scenario:

    1. ``run_workflow`` on ``planner`` pauses at the ``HumanGate``.
    2. ``list_runs`` reflects the pending row with a populated cost.
    3. ``resume_run`` approves and completes the run.
    4. ``list_runs`` post-resume shows ``status="completed"``.
    5. ``cancel_run`` on the completed row is ``"already_terminal"``
       with no side effect (row stays ``"completed"``).
    6. A second ``run_workflow`` pauses, ``cancel_run`` flips it,
       ``resume_run`` refuses with a "cancelled" ``ToolError``.
    """
    server = build_server()
    run_tool = await server.get_tool("run_workflow")
    list_tool = await server.get_tool("list_runs")
    resume_tool = await server.get_tool("resume_run")
    cancel_tool = await server.get_tool("cancel_run")

    # 1 — run_workflow: pauses at HumanGate.
    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
    ]
    run_result = await run_tool.fn(
        RunWorkflowInput(
            workflow_id="planner",
            inputs=_planner_inputs(),
            run_id="smoke-run-1",
        )
    )
    assert run_result.status == "pending"
    assert run_result.awaiting == "gate"
    assert run_result.run_id == "smoke-run-1"
    assert run_result.total_cost_usd == pytest.approx(0.0033)

    # 2 — list_runs: row is present, pending, cost populated.
    pending_summaries = await list_tool.fn(ListRunsInput())
    by_id = {s.run_id: s for s in pending_summaries}
    assert "smoke-run-1" in by_id
    assert by_id["smoke-run-1"].status == "pending"
    assert by_id["smoke-run-1"].workflow_id == "planner"
    assert by_id["smoke-run-1"].total_cost_usd == pytest.approx(0.0033)

    # 3 — resume_run: approve → completed with rolled-up cost + plan.
    resume_result = await resume_tool.fn(
        ResumeRunInput(run_id="smoke-run-1", gate_response="approved")
    )
    assert resume_result.status == "completed"
    assert resume_result.plan is not None
    assert resume_result.plan["goal"] == "Ship the marketing page."
    assert resume_result.error is None
    assert resume_result.total_cost_usd == pytest.approx(0.0033)

    # 4 — list_runs post-resume: same row now shows completed.
    completed_summaries = await list_tool.fn(ListRunsInput())
    by_id_post = {s.run_id: s for s in completed_summaries}
    assert by_id_post["smoke-run-1"].status == "completed"

    # 5 — cancel_run on already-completed row: no-op.
    cancel_on_done = await cancel_tool.fn(CancelRunInput(run_id="smoke-run-1"))
    assert cancel_on_done.status == "already_terminal"
    # list_runs confirms no mutation.
    post_cancel_summaries = await list_tool.fn(ListRunsInput())
    by_id_nop = {s.run_id: s for s in post_cancel_summaries}
    assert by_id_nop["smoke-run-1"].status == "completed"

    # 6 — full cancel path: new run → pause → cancel → resume refuses.
    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
    ]
    second_run = await run_tool.fn(
        RunWorkflowInput(
            workflow_id="planner",
            inputs=_planner_inputs(),
            run_id="smoke-run-2",
        )
    )
    assert second_run.status == "pending"

    cancel_pending = await cancel_tool.fn(CancelRunInput(run_id="smoke-run-2"))
    assert cancel_pending.status == "cancelled"

    with pytest.raises(ToolError) as excinfo:
        await resume_tool.fn(ResumeRunInput(run_id="smoke-run-2"))
    message = str(excinfo.value)
    assert "cancelled" in message
    assert "smoke-run-2" in message

    # list_runs with status filter reflects the cancel.
    cancelled_only = await list_tool.fn(ListRunsInput(status="cancelled"))
    assert [s.run_id for s in cancelled_only] == ["smoke-run-2"]
