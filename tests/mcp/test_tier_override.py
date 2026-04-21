"""Tests for M5 Task 05 — MCP ``run_workflow.tier_overrides``.

Covers the ACs from
``design_docs/phases/milestone_5_multitier_planner/task_05_tier_override_mcp.md``:

* Override applied — MCP ``run_workflow`` with
  ``tier_overrides={"planner-synth": "planner-explorer"}`` runs to the
  gate; stub adapter records the replacement's ``route.model`` for the
  synth call.
* Backward compat — payload with ``tier_overrides`` absent is
  byte-identical to the M4 path.
* Empty-dict override is a no-op (same behaviour as absent).
* Unknown logical tier → ``ToolError`` with the tier name in the message.
* Unknown replacement tier → ``ToolError`` with the tier name.
* Pydantic round-trip — ``RunWorkflowInput.model_dump()`` →
  ``RunWorkflowInput.model_validate()`` preserves the ``tier_overrides``
  shape.

Mirrors the hermetic stub pattern from :mod:`tests/mcp/test_server_smoke.py`.
The directory-local ``tests/mcp/conftest.py`` autouse fixture pins the
planner registry to a LiteLLM-only pair so the MCP run path stays
hermetic; this module re-monkeypatches to two *distinct* LiteLLM
models so the adapter-boundary dispatch assertion is observable.
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
from ai_workflows.mcp.schemas import RunWorkflowInput
from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig
from ai_workflows.workflows import planner as planner_module
from ai_workflows.workflows.planner import build_planner

# ---------------------------------------------------------------------------
# Stub adapter — records per-call route for the AC-3-style dispatch assertion
# ---------------------------------------------------------------------------


class _RecordingLiteLLMAdapter:
    script: list[Any] = []
    models_seen: list[str] = []
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
        _RecordingLiteLLMAdapter.call_count += 1
        _RecordingLiteLLMAdapter.models_seen.append(self.route.model)
        if not _RecordingLiteLLMAdapter.script:
            raise AssertionError("stub script exhausted")
        head = _RecordingLiteLLMAdapter.script.pop(0)
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
        cls.models_seen = []
        cls.call_count = 0


_EXPLORER_MODEL = "gemini/gemini-2.5-flash"
_SYNTH_MODEL = "gemini/gemini-2.5-pro"


def _distinct_registry() -> dict[str, TierConfig]:
    return {
        "planner-explorer": TierConfig(
            name="planner-explorer",
            route=LiteLLMRoute(model=_EXPLORER_MODEL),
            max_concurrency=2,
            per_call_timeout_s=60,
        ),
        "planner-synth": TierConfig(
            name="planner-synth",
            route=LiteLLMRoute(model=_SYNTH_MODEL),
            max_concurrency=2,
            per_call_timeout_s=90,
        ),
    }


@pytest.fixture(autouse=True)
def _install_distinct_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        planner_module, "planner_tier_registry", _distinct_registry
    )


@pytest.fixture(autouse=True)
def _reset_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    _RecordingLiteLLMAdapter.reset()
    monkeypatch.setattr(
        tiered_node_module, "LiteLLMAdapter", _RecordingLiteLLMAdapter
    )


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


def _explorer_json() -> str:
    return json.dumps(
        {
            "summary": "Three-step delivery.",
            "considerations": ["A", "B"],
            "assumptions": ["X"],
        }
    )


def _plan_json() -> str:
    return json.dumps(
        {
            "goal": "Ship the marketing page.",
            "summary": "Delivery plan.",
            "steps": [
                {
                    "index": 1,
                    "title": "Draft hero copy",
                    "rationale": "Lock tone.",
                    "actions": ["Sketch headline"],
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


# ---------------------------------------------------------------------------
# AC: override applied — replacement route observed at the adapter boundary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_workflow_applies_tier_overrides_to_replacement_route() -> None:
    _RecordingLiteLLMAdapter.script = [
        (_explorer_json(), 0.0012),
        (_plan_json(), 0.0021),
    ]
    server = build_server()
    run_tool = await server.get_tool("run_workflow")
    result = await run_tool.fn(
        RunWorkflowInput(
            workflow_id="planner",
            inputs=_planner_inputs(),
            run_id="mcp-t05-override",
            tier_overrides={"planner-synth": "planner-explorer"},
        )
    )
    assert result.status == "pending"
    assert _RecordingLiteLLMAdapter.models_seen == [
        _EXPLORER_MODEL,
        _EXPLORER_MODEL,
    ]


# ---------------------------------------------------------------------------
# AC: backward compat — absent `tier_overrides` behaves like M4
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_workflow_without_tier_overrides_matches_m4_behaviour() -> None:
    _RecordingLiteLLMAdapter.script = [
        (_explorer_json(), 0.0012),
        (_plan_json(), 0.0021),
    ]
    server = build_server()
    run_tool = await server.get_tool("run_workflow")
    result = await run_tool.fn(
        RunWorkflowInput(
            workflow_id="planner",
            inputs=_planner_inputs(),
            run_id="mcp-t05-no-override",
        )
    )
    assert result.status == "pending"
    assert _RecordingLiteLLMAdapter.models_seen == [
        _EXPLORER_MODEL,
        _SYNTH_MODEL,
    ]


@pytest.mark.asyncio
async def test_run_workflow_empty_dict_override_is_noop() -> None:
    _RecordingLiteLLMAdapter.script = [
        (_explorer_json(), 0.0012),
        (_plan_json(), 0.0021),
    ]
    server = build_server()
    run_tool = await server.get_tool("run_workflow")
    result = await run_tool.fn(
        RunWorkflowInput(
            workflow_id="planner",
            inputs=_planner_inputs(),
            run_id="mcp-t05-empty-override",
            tier_overrides={},
        )
    )
    assert result.status == "pending"
    assert _RecordingLiteLLMAdapter.models_seen == [
        _EXPLORER_MODEL,
        _SYNTH_MODEL,
    ]


# ---------------------------------------------------------------------------
# AC: unknown logical / replacement → ToolError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_workflow_unknown_logical_tier_raises_tool_error() -> None:
    server = build_server()
    run_tool = await server.get_tool("run_workflow")
    with pytest.raises(ToolError) as excinfo:
        await run_tool.fn(
            RunWorkflowInput(
                workflow_id="planner",
                inputs=_planner_inputs(),
                run_id="mcp-t05-unknown-logical",
                tier_overrides={"nonexistent": "planner-synth"},
            )
        )
    message = str(excinfo.value)
    assert "nonexistent" in message
    assert "logical" in message
    assert _RecordingLiteLLMAdapter.call_count == 0


@pytest.mark.asyncio
async def test_run_workflow_unknown_replacement_tier_raises_tool_error() -> None:
    server = build_server()
    run_tool = await server.get_tool("run_workflow")
    with pytest.raises(ToolError) as excinfo:
        await run_tool.fn(
            RunWorkflowInput(
                workflow_id="planner",
                inputs=_planner_inputs(),
                run_id="mcp-t05-unknown-replacement",
                tier_overrides={"planner-synth": "nonexistent"},
            )
        )
    message = str(excinfo.value)
    assert "nonexistent" in message
    assert "replacement" in message
    assert _RecordingLiteLLMAdapter.call_count == 0


# ---------------------------------------------------------------------------
# AC: RunWorkflowInput schema round-trip preserves `tier_overrides`
# ---------------------------------------------------------------------------


def test_run_workflow_input_round_trip_preserves_tier_overrides() -> None:
    original = RunWorkflowInput(
        workflow_id="planner",
        inputs={"goal": "g", "context": None, "max_steps": 5},
        tier_overrides={"planner-synth": "planner-explorer"},
    )
    dumped = original.model_dump()
    assert dumped["tier_overrides"] == {"planner-synth": "planner-explorer"}
    reloaded = RunWorkflowInput.model_validate(dumped)
    assert reloaded.tier_overrides == {"planner-synth": "planner-explorer"}


def test_run_workflow_input_round_trip_without_tier_overrides() -> None:
    """Absent field round-trips as ``None``."""
    original = RunWorkflowInput(
        workflow_id="planner",
        inputs={"goal": "g", "context": None, "max_steps": 5},
    )
    dumped = original.model_dump()
    assert dumped["tier_overrides"] is None
    reloaded = RunWorkflowInput.model_validate(dumped)
    assert reloaded.tier_overrides is None
