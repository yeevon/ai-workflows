"""Hermetic tests for the M5 Task 01 Qwen explorer tier refit.

The ``planner-explorer`` tier flips from Gemini Flash to local Qwen via
Ollama (``ollama/qwen2.5-coder:32b``). These tests verify:

* The tier registry names the new route with ``api_base`` set and
  ``max_concurrency=1`` (single local model, no parallelism win).
* The planner graph still completes to the gate when the explorer
  stub replays a Qwen-shape ``ExplorerReport`` JSON blob. ``planner-synth``
  stays on Gemini Flash in T01 — T02 flips it to Claude Code Opus.
* An ``APIConnectionError`` (daemon down) classifies as
  ``RetryableTransient`` so the ``RetryingEdge`` re-enters the explorer
  node rather than aborting the run.

Mirrors ``tests/workflows/test_planner_graph.py`` fixture shape so both
suites exercise the same hermetic substrate.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import litellm
import pytest

from ai_workflows import workflows
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.graph.checkpointer import build_async_checkpointer
from ai_workflows.graph.cost_callback import CostTrackingCallback
from ai_workflows.primitives.cost import CostTracker, TokenUsage
from ai_workflows.primitives.retry import RetryableTransient, classify
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig
from ai_workflows.workflows.planner import (
    ExplorerReport,
    PlannerInput,
    PlannerPlan,
    build_planner,
    planner_tier_registry,
)


class _StubLiteLLMAdapter:
    """Scripted LiteLLM-adapter stub shared with ``test_planner_graph.py``."""

    script: list[Any] = []
    call_count: int = 0
    response_format_log: list[Any] = []

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
        _StubLiteLLMAdapter.response_format_log.append(response_format)
        if not _StubLiteLLMAdapter.script:
            raise AssertionError("stub script exhausted")
        head = _StubLiteLLMAdapter.script.pop(0)
        if isinstance(head, BaseException):
            raise head
        text, cost = head
        return text, TokenUsage(
            input_tokens=9,
            output_tokens=13,
            cost_usd=cost,
            model=self.route.model,
        )

    @classmethod
    def reset(cls) -> None:
        cls.script = []
        cls.call_count = 0
        cls.response_format_log = []


@pytest.fixture(autouse=True)
def _reset_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    _StubLiteLLMAdapter.reset()
    monkeypatch.setattr(
        tiered_node_module, "LiteLLMAdapter", _StubLiteLLMAdapter
    )


@pytest.fixture(autouse=True)
def _reensure_planner_registered() -> Iterator[None]:
    workflows._reset_for_tests()
    workflows.register("planner", build_planner)
    yield


def _explorer_focused_registry() -> dict[str, TierConfig]:
    """Explorer uses the real Qwen/Ollama route; synth stays on LiteLLM.

    T01's hermetic graph test exercises the explorer tier change only;
    keeping synth on a LiteLLM route lets one stub (``_StubLiteLLMAdapter``)
    cover both calls so this file stays T01-scoped even after T02 flips
    synth to ``ClaudeCodeRoute`` in the production registry.
    """
    return {
        "planner-explorer": TierConfig(
            name="planner-explorer",
            route=LiteLLMRoute(
                model="ollama/qwen2.5-coder:32b",
                api_base="http://localhost:11434",
            ),
            max_concurrency=1,
            per_call_timeout_s=180,
        ),
        "planner-synth": TierConfig(
            name="planner-synth",
            route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
            max_concurrency=2,
            per_call_timeout_s=90,
        ),
    }


async def _build_config(
    tmp_path: Path, run_id: str
) -> tuple[dict[str, Any], CostTracker, SQLiteStorage]:
    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await storage.create_run(run_id, "planner", None)
    tracker = CostTracker()
    callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=None)
    cfg = {
        "configurable": {
            "thread_id": run_id,
            "run_id": run_id,
            "tier_registry": _explorer_focused_registry(),
            "cost_callback": callback,
            "storage": storage,
            "workflow": "planner",
        }
    }
    return cfg, tracker, storage


def _qwen_shape_explorer_json() -> str:
    """A realistic Qwen-shape ExplorerReport JSON blob.

    Shape matches ``ExplorerReport`` exactly; wording is intentionally
    terser / more utilitarian than the Gemini stubs in the sibling suite
    so the test documents "Qwen-shape" by example.
    """
    return json.dumps(
        {
            "summary": (
                "Goal is to ship a static marketing page with one CTA. "
                "Three steps suffice: copy, layout, and QA."
            ),
            "considerations": [
                "Copy tone matches brand voice",
                "CTA placement above the fold",
                "Mobile viewport tested",
            ],
            "assumptions": ["Design system tokens are frozen"],
        }
    )


def _gemini_shape_plan_json() -> str:
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
                },
            ],
        }
    )


def test_planner_explorer_tier_points_at_qwen_via_ollama() -> None:
    """AC: ``planner-explorer`` route + api_base + max_concurrency."""
    registry = planner_tier_registry()
    explorer = registry["planner-explorer"]
    assert explorer.route.model == "ollama/qwen2.5-coder:32b"
    assert explorer.route.api_base == "http://localhost:11434"
    assert explorer.max_concurrency == 1
    assert explorer.per_call_timeout_s == 180


def test_planner_explorer_tier_independent_of_synth() -> None:
    """Explorer + synth resolve independently.

    Sanity guard for the multi-tier registry shape — the two tiers must
    be distinct ``TierConfig`` objects with distinct routes (explorer on
    LiteLLM/Ollama, synth on whichever provider the milestone has
    reached at this task). Catches a copy-paste regression where
    ``planner-synth`` accidentally shares the explorer's config object.
    """
    registry = planner_tier_registry()
    assert registry["planner-explorer"] is not registry["planner-synth"]
    assert (
        registry["planner-explorer"].route
        is not registry["planner-synth"].route
    )


async def test_graph_completes_to_gate_with_qwen_shape_explorer_output(
    tmp_path: Path,
) -> None:
    """AC: hermetic graph run with Qwen-shape explorer JSON + Gemini plan JSON.

    The explorer stub replays a Qwen-flavoured ``ExplorerReport``; the
    planner stub replays a valid ``PlannerPlan``. The graph must complete
    up to the ``HumanGate`` interrupt and both validators must parse their
    inputs cleanly.
    """
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_planner().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [
        (_qwen_shape_explorer_json(), 0.0),  # Ollama is local → cost 0.
        (_gemini_shape_plan_json(), 0.0021),
    ]
    cfg, _tracker, storage = await _build_config(tmp_path, "run-qwen")

    try:
        paused = await app.ainvoke(
            {
                "run_id": "run-qwen",
                "input": PlannerInput(
                    goal="Ship the marketing page.",
                    context="Hero + single CTA.",
                    max_steps=5,
                ),
            },
            cfg,
        )
        assert "__interrupt__" in paused
        assert isinstance(paused["explorer_report"], ExplorerReport)
        assert isinstance(paused["plan"], PlannerPlan)
        assert _StubLiteLLMAdapter.call_count == 2
    finally:
        await checkpointer.conn.close()
        del storage


def test_ollama_api_connection_error_classifies_as_transient() -> None:
    """AC: simulated Ollama daemon-down maps to ``RetryableTransient``.

    ``litellm.APIConnectionError`` is what Ollama raises when the local
    daemon is unreachable — the same bucket that covers hosted-provider
    network flakes. Must not fall into ``NonRetryable`` or the planner
    graph would abort rather than re-try the node.
    """
    exc = litellm.APIConnectionError(
        message="Connection refused: http://localhost:11434",
        llm_provider="ollama",
        model="qwen2.5-coder:32b",
    )
    assert classify(exc) is RetryableTransient
