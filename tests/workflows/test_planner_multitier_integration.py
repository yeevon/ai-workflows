"""M5 Task 03 — Sub-graph composition validation (hermetic).

Integration pass that proves the existing ``planner`` ``StateGraph`` topology
from M3 T03 survives the two-phase tier swap wired by M5 T01 (Qwen explorer)
and M5 T02 (Claude Code synth). Every test drives the full graph with both
adapters stubbed — the ``LiteLLMAdapter`` stub covers the Qwen/Ollama
explorer call; the ``ClaudeCodeSubprocess`` stub covers the Claude Code
Opus synth call — and exercises a behaviour that the per-tier T01 / T02
suites cannot observe in isolation:

* Cross-provider transient retry on the explorer (Ollama
  ``APIConnectionError``) — confirms the ``retrying_edge`` ``on_transient``
  route still fires when the failing tier is LiteLLM/Ollama rather than
  LiteLLM/Gemini.
* Cross-provider transient retry on the planner
  (``subprocess.TimeoutExpired``) — confirms the same edge works when the
  failing tier is the Claude Code subprocess driver (KDR-006 three-bucket
  taxonomy covers subprocess timeouts).
* Cross-provider semantic retry on the explorer (malformed JSON from the
  Qwen stub) — confirms the ``explorer_validator`` → ``explorer`` semantic
  edge routes through the LiteLLM/Ollama tier.
* Mixed-provider cost rollup — Qwen primary (cost 0, local) + Claude Code
  primary + Claude Code sub-model (Haiku) all land in the per-run
  ``CostTracker``; ``tracker.total()`` matches the sum.

No code change expected under `ai_workflows/` — this file is pure
integration evidence (architecture.md §4.3 + §8.2 + KDR-004 / KDR-006).
"""

from __future__ import annotations

import json
import subprocess
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
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.tiers import (
    ClaudeCodeRoute,
    LiteLLMRoute,
    ModelPricing,
)
from ai_workflows.workflows.planner import (
    ExplorerReport,
    PlannerInput,
    PlannerPlan,
    build_planner,
    planner_tier_registry,
)

# ---------------------------------------------------------------------------
# Stubs — one LiteLLM (explorer / Qwen), one ClaudeCodeSubprocess (synth / Opus)
# ---------------------------------------------------------------------------


class _StubLiteLLMAdapter:
    """Script entries are either ``(text, cost)`` tuples or raised exceptions."""

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
            raise AssertionError("litellm stub script exhausted")
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


class _StubClaudeCodeSubprocess:
    """Script entries are either ``(text, TokenUsage)`` tuples or exceptions."""

    script: list[Any] = []
    call_count: int = 0

    def __init__(
        self,
        route: ClaudeCodeRoute,
        per_call_timeout_s: int,
        pricing: dict[str, ModelPricing],
    ) -> None:
        self.route = route
        self.per_call_timeout_s = per_call_timeout_s
        self.pricing = pricing

    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict],
        response_format: Any = None,
    ) -> tuple[str, TokenUsage]:
        _StubClaudeCodeSubprocess.call_count += 1
        if not _StubClaudeCodeSubprocess.script:
            raise AssertionError("claude_code stub script exhausted")
        head = _StubClaudeCodeSubprocess.script.pop(0)
        if isinstance(head, BaseException):
            raise head
        return head

    @classmethod
    def reset(cls) -> None:
        cls.script = []
        cls.call_count = 0


@pytest.fixture(autouse=True)
def _reset_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    _StubLiteLLMAdapter.reset()
    _StubClaudeCodeSubprocess.reset()
    monkeypatch.setattr(
        tiered_node_module, "LiteLLMAdapter", _StubLiteLLMAdapter
    )
    monkeypatch.setattr(
        tiered_node_module, "ClaudeCodeSubprocess", _StubClaudeCodeSubprocess
    )


@pytest.fixture(autouse=True)
def _reensure_planner_registered() -> Iterator[None]:
    workflows._reset_for_tests()
    workflows.register("planner", build_planner)
    yield


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
            "tier_registry": planner_tier_registry(),
            "cost_callback": callback,
            "storage": storage,
            "workflow": "planner",
            "pricing": {},
        }
    }
    return cfg, tracker, storage


def _explorer_json() -> str:
    return json.dumps(
        {
            "summary": "Short utilitarian summary.",
            "considerations": ["A", "B", "C"],
            "assumptions": ["X"],
        }
    )


def _invalid_explorer_json() -> str:
    """Missing the required ``considerations`` key → Pydantic ValidationError."""
    return json.dumps({"summary": "only a summary"})


def _plan_json() -> str:
    return json.dumps(
        {
            "goal": "Ship the marketing page.",
            "summary": "Three-step delivery.",
            "steps": [
                {
                    "index": 1,
                    "title": "Draft hero copy",
                    "rationale": "Lock tone first.",
                    "actions": ["Sketch headline"],
                }
            ],
        }
    )


def _opus_plan_usage(
    opus_cost: float = 0.0150, haiku_cost: float = 0.0003
) -> TokenUsage:
    return TokenUsage(
        input_tokens=320,
        output_tokens=700,
        cost_usd=opus_cost,
        model="claude-opus-4-7",
        sub_models=[
            TokenUsage(
                input_tokens=80,
                output_tokens=30,
                cost_usd=haiku_cost,
                model="claude-haiku-4-5",
            )
        ],
    )


def _planner_input() -> PlannerInput:
    return PlannerInput(
        goal="Ship the marketing page.",
        context="Hero + single CTA.",
        max_steps=5,
    )


# ---------------------------------------------------------------------------
# AC: topology unchanged — no edit under ai_workflows/ required
# ---------------------------------------------------------------------------


def test_topology_unchanged_six_nodes_as_shipped_by_m3_t03() -> None:
    """Guard: T03 must not mutate the graph shape. Same nodes as M3 T03."""
    g = build_planner()
    assert set(g.nodes) == {
        "explorer",
        "explorer_validator",
        "planner",
        "planner_validator",
        "gate",
        "artifact",
    }


# ---------------------------------------------------------------------------
# AC-1: full hermetic end-to-end with both tiers
# ---------------------------------------------------------------------------


async def test_full_hermetic_end_to_end_mixed_providers(tmp_path: Path) -> None:
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_planner().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [(_explorer_json(), 0.0)]
    _StubClaudeCodeSubprocess.script = [(_plan_json(), _opus_plan_usage())]

    cfg, _tracker, storage = await _build_config(tmp_path, "run-m5-t03-full")
    try:
        paused = await app.ainvoke(
            {"run_id": "run-m5-t03-full", "input": _planner_input()}, cfg
        )
        assert "__interrupt__" in paused
        assert isinstance(paused["explorer_report"], ExplorerReport)
        assert isinstance(paused["plan"], PlannerPlan)
        assert _StubLiteLLMAdapter.call_count == 1
        assert _StubClaudeCodeSubprocess.call_count == 1
    finally:
        await checkpointer.conn.close()
        del storage


# ---------------------------------------------------------------------------
# AC-2: transient retry on the explorer (Ollama APIConnectionError)
# ---------------------------------------------------------------------------


async def test_explorer_transient_retry_routes_through_ollama_bucket(
    tmp_path: Path,
) -> None:
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_planner().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [
        litellm.APIConnectionError(
            message="Connection refused: http://localhost:11434",
            llm_provider="ollama",
            model="qwen2.5-coder:32b",
        ),
        (_explorer_json(), 0.0),
    ]
    _StubClaudeCodeSubprocess.script = [(_plan_json(), _opus_plan_usage())]

    cfg, _tracker, storage = await _build_config(tmp_path, "run-m5-t03-expretry")
    try:
        paused = await app.ainvoke(
            {"run_id": "run-m5-t03-expretry", "input": _planner_input()}, cfg
        )
        assert "__interrupt__" in paused
        assert paused["_retry_counts"] == {"explorer": 1}
        assert paused.get("_non_retryable_failures", 0) == 0
        assert _StubLiteLLMAdapter.call_count == 2
        assert _StubClaudeCodeSubprocess.call_count == 1
    finally:
        await checkpointer.conn.close()
        del storage


# ---------------------------------------------------------------------------
# AC-3: transient retry on the planner (Claude Code subprocess TimeoutExpired)
# ---------------------------------------------------------------------------


async def test_planner_transient_retry_routes_through_subprocess_bucket(
    tmp_path: Path,
) -> None:
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_planner().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [(_explorer_json(), 0.0)]
    _StubClaudeCodeSubprocess.script = [
        subprocess.TimeoutExpired(cmd=["claude"], timeout=300.0),
        (_plan_json(), _opus_plan_usage()),
    ]

    cfg, _tracker, storage = await _build_config(tmp_path, "run-m5-t03-plretry")
    try:
        paused = await app.ainvoke(
            {"run_id": "run-m5-t03-plretry", "input": _planner_input()}, cfg
        )
        assert "__interrupt__" in paused
        assert paused["_retry_counts"] == {"planner": 1}
        assert paused.get("_non_retryable_failures", 0) == 0
        assert _StubLiteLLMAdapter.call_count == 1
        assert _StubClaudeCodeSubprocess.call_count == 2
    finally:
        await checkpointer.conn.close()
        del storage


# ---------------------------------------------------------------------------
# AC-4: semantic retry on the explorer (Qwen malformed JSON → valid JSON)
# ---------------------------------------------------------------------------


async def test_explorer_semantic_retry_routes_back_via_validator(
    tmp_path: Path,
) -> None:
    """Malformed JSON on call 1 → validator ``RetryableSemantic`` → edge
    routes to ``explorer`` per ``retrying_edge(on_semantic="explorer")`` —
    the validator owns the semantic-bucket decision (KDR-004).
    """
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_planner().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [
        (_invalid_explorer_json(), 0.0),  # fails the ExplorerReport schema
        (_explorer_json(), 0.0),
    ]
    _StubClaudeCodeSubprocess.script = [(_plan_json(), _opus_plan_usage())]

    cfg, _tracker, storage = await _build_config(tmp_path, "run-m5-t03-semretry")
    try:
        paused = await app.ainvoke(
            {"run_id": "run-m5-t03-semretry", "input": _planner_input()}, cfg
        )
        assert "__interrupt__" in paused
        # The wrap_with_error_handler on explorer_validator bumps the
        # validator's counter; the semantic edge then routes to the
        # upstream LLM node (`explorer`) — matches the sibling
        # planner-side test in test_planner_graph.py.
        assert paused["_retry_counts"].get("explorer_validator") == 1
        assert _StubLiteLLMAdapter.call_count == 2
        assert _StubClaudeCodeSubprocess.call_count == 1
    finally:
        await checkpointer.conn.close()
        del storage


# ---------------------------------------------------------------------------
# AC-5: mixed-provider modelUsage rollup
# ---------------------------------------------------------------------------


async def test_mixed_provider_cost_rollup(tmp_path: Path) -> None:
    """Qwen primary (cost 0) + Opus primary + Haiku sub = single rollup.

    ``CostTracker.total()`` sums through ``_roll_cost`` recursion, so the
    sub-model contribution lands even though ``CostTrackingCallback``
    receives only two top-level rows (one per node, via ``record()``).
    """
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_planner().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [(_explorer_json(), 0.0)]  # local → free
    _StubClaudeCodeSubprocess.script = [
        (_plan_json(), _opus_plan_usage(opus_cost=0.0150, haiku_cost=0.0003))
    ]

    cfg, tracker, storage = await _build_config(tmp_path, "run-m5-t03-rollup")
    try:
        await app.ainvoke(
            {"run_id": "run-m5-t03-rollup", "input": _planner_input()}, cfg
        )
        assert tracker.total("run-m5-t03-rollup") == pytest.approx(0.0153)
        by_model = tracker.by_model("run-m5-t03-rollup")
        assert by_model.get("ollama/qwen2.5-coder:32b") == pytest.approx(0.0)
        assert by_model.get("claude-opus-4-7") == pytest.approx(0.0150)
        assert by_model.get("claude-haiku-4-5") == pytest.approx(0.0003)
    finally:
        await checkpointer.conn.close()
        del storage
