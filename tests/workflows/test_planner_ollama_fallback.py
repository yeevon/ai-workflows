"""Tests for the planner workflow's Ollama-outage fallback edge (M8 T04).

Covers the three workflow-layer ACs from
[design_docs/phases/milestone_8_ollama/task_04_tiered_node_integration.md](
../../design_docs/phases/milestone_8_ollama/task_04_tiered_node_integration.md):

* ``RETRY`` re-fires the same (breakered) tier after the operator resolves
  the gate — the breaker must be in a state that permits the next call.
* ``FALLBACK`` stamps ``_mid_run_tier_overrides`` so the tripped tier
  resolves to :data:`PLANNER_OLLAMA_FALLBACK.fallback_tier` for the rest
  of the run; the replacement route actually dispatches.
* ``ABORT`` routes to ``planner_hard_stop`` which writes a
  ``hard_stop_metadata`` artefact and stamps
  ``ollama_fallback_aborted=True``; no further provider calls fire.

Both the LiteLLM adapter and the Claude Code subprocess are stubbed — no
real provider calls fire.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from langgraph.types import Command

from ai_workflows import workflows
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.graph.checkpointer import build_async_checkpointer
from ai_workflows.graph.cost_callback import CostTrackingCallback
from ai_workflows.primitives.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
)
from ai_workflows.primitives.cost import CostTracker, TokenUsage
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.tiers import (
    ClaudeCodeRoute,
    LiteLLMRoute,
    ModelPricing,
    TierConfig,
)
from ai_workflows.workflows.planner import (
    PLANNER_OLLAMA_FALLBACK,
    PlannerInput,
    build_planner,
)

# ---------------------------------------------------------------------------
# Adapter stubs — LiteLLM (explorer) + ClaudeCodeSubprocess (synth)
# ---------------------------------------------------------------------------


class _StubLiteLLMAdapter:
    """Scripted LiteLLM stub — explorer tier only."""

    script: list[Any] = []
    call_count: int = 0
    routed_models: list[str] = []

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
        _StubLiteLLMAdapter.routed_models.append(self.route.model)
        if not _StubLiteLLMAdapter.script:
            raise AssertionError("litellm stub script exhausted")
        head = _StubLiteLLMAdapter.script.pop(0)
        if isinstance(head, BaseException):
            raise head
        text, cost = head
        return text, TokenUsage(
            input_tokens=8,
            output_tokens=12,
            cost_usd=cost,
            model=self.route.model,
        )

    @classmethod
    def reset(cls) -> None:
        cls.script = []
        cls.call_count = 0
        cls.routed_models = []


class _StubClaudeCodeSubprocess:
    """Claude Code subprocess stub returning pre-built ``TokenUsage``."""

    script: list[tuple[str, TokenUsage]] = []
    call_count: int = 0
    routed_flags: list[str] = []

    def __init__(
        self,
        *,
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
        _StubClaudeCodeSubprocess.routed_flags.append(self.route.cli_model_flag)
        if not _StubClaudeCodeSubprocess.script:
            raise AssertionError("claude_code stub script exhausted")
        return _StubClaudeCodeSubprocess.script.pop(0)

    @classmethod
    def reset(cls) -> None:
        cls.script = []
        cls.call_count = 0
        cls.routed_flags = []


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


# ---------------------------------------------------------------------------
# Helpers — tier registry, breaker, config builder, fixture payloads
# ---------------------------------------------------------------------------


def _tier_registry() -> dict[str, TierConfig]:
    """Production-shape registry: explorer on Ollama, synth on Claude Code."""
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
            route=ClaudeCodeRoute(cli_model_flag="opus"),
            max_concurrency=1,
            per_call_timeout_s=300,
        ),
    }


def _build_breaker(clock: dict[str, float]) -> CircuitBreaker:
    """Breaker pre-trippable to OPEN with a controllable clock.

    Trip threshold is ``1`` so a single :meth:`record_failure` flips the
    breaker OPEN. ``cooldown_s=1.0`` + an injected clock dict lets the
    test move past the cooldown between pause and resume (for the
    RETRY case) without a real ``time.sleep``.
    """
    return CircuitBreaker(
        tier="planner-explorer",
        trip_threshold=1,
        cooldown_s=1.0,
        time_source=lambda: clock["t"],
    )


async def _build_config(
    *,
    tmp_path: Path,
    run_id: str,
    breaker: CircuitBreaker,
) -> tuple[dict[str, Any], CostTracker, SQLiteStorage]:
    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await storage.create_run(run_id, "planner", None)
    tracker = CostTracker()
    callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=None)
    cfg = {
        "configurable": {
            "thread_id": run_id,
            "run_id": run_id,
            "tier_registry": _tier_registry(),
            "cost_callback": callback,
            "storage": storage,
            "workflow": "planner",
            "ollama_circuit_breakers": {"planner-explorer": breaker},
            # ClaudeCodeSubprocess reads ``pricing`` from configurable;
            # the stub ignores it but tiered_node still looks for it.
            "pricing": {},
        }
    }
    return cfg, tracker, storage


def _explorer_report_json() -> str:
    return (
        '{"summary": "Three-step delivery.", '
        '"considerations": ["Copy", "CTA"], '
        '"assumptions": ["Design tokens frozen"]}'
    )


def _plan_json() -> str:
    return (
        '{"goal": "Ship the marketing page.", '
        '"summary": "Three-step delivery.", '
        '"steps": [{"index": 1, "title": "t", "rationale": "r", '
        '"actions": ["a"]}]}'
    )


def _opus_usage() -> TokenUsage:
    return TokenUsage(
        input_tokens=100,
        output_tokens=200,
        cost_usd=0.02,
        model="claude-opus-4-7",
    )


def _planner_input() -> PlannerInput:
    return PlannerInput(
        goal="Ship the marketing page.",
        context="Hero + single CTA.",
        max_steps=5,
    )


# ---------------------------------------------------------------------------
# AC — RETRY re-fires the same tier after the operator resolves the gate
# ---------------------------------------------------------------------------


async def test_retry_re_fires_same_tier(tmp_path: Path) -> None:
    """``FallbackChoice.RETRY`` re-enters explorer on the same tier.

    Pre-trips the breaker (OPEN). The first explorer call raises
    :class:`CircuitOpen`, routing through ``ollama_fallback_stamp`` → the
    gate. Advance the clock past cooldown. Resume with ``"retry"``. The
    next explorer call is a HALF_OPEN probe — the LiteLLM stub answers,
    the breaker flips CLOSED, and the run continues on its original
    ``planner-explorer`` (Ollama) route.
    """
    clock = {"t": 0.0}
    breaker = _build_breaker(clock)
    await breaker.record_failure(reason="connection_refused")
    assert breaker.state is CircuitState.OPEN

    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_planner().compile(checkpointer=checkpointer)

    # Explorer retry → LiteLLM; then planner → Claude Code subprocess.
    _StubLiteLLMAdapter.script = [(_explorer_report_json(), 0.0)]
    _StubClaudeCodeSubprocess.script = [(_plan_json(), _opus_usage())]

    cfg, _tracker, _storage = await _build_config(
        tmp_path=tmp_path, run_id="run-retry", breaker=breaker
    )
    try:
        paused = await app.ainvoke(
            {"run_id": "run-retry", "input": _planner_input()}, cfg
        )
        # Gate fires on the Ollama fallback path.
        assert "__interrupt__" in paused
        assert _StubLiteLLMAdapter.call_count == 0  # adapter never called

        # Advance past cooldown so HALF_OPEN lets the next call through.
        clock["t"] = 5.0

        final = await app.ainvoke(Command(resume="retry"), cfg)
        assert "__interrupt__" in final  # plan_review gate fires next

        # Explorer retry went to the Ollama LiteLLM route (no override).
        assert _StubLiteLLMAdapter.call_count == 1
        assert _StubLiteLLMAdapter.routed_models == [
            "ollama/qwen2.5-coder:32b"
        ]
        # Synth call reached Claude Code subprocess (normal planner tier).
        assert _StubClaudeCodeSubprocess.call_count == 1
        # Breaker closed after the probe succeeded.
        assert breaker.state is CircuitState.CLOSED
    finally:
        await checkpointer.conn.close()


# ---------------------------------------------------------------------------
# AC — FALLBACK routes to the replacement tier
# ---------------------------------------------------------------------------


async def test_fallback_routes_to_replacement_tier(tmp_path: Path) -> None:
    """``FallbackChoice.FALLBACK`` stamps the mid-run override.

    Post-resume the explorer's ``planner-explorer`` logical tier resolves
    to :data:`PLANNER_OLLAMA_FALLBACK.fallback_tier` (``planner-synth``),
    which routes through :class:`ClaudeCodeRoute` — a non-Ollama,
    non-breakered route. Assert the second explorer call lands on the
    subprocess stub, not the LiteLLM stub.
    """
    clock = {"t": 0.0}
    breaker = _build_breaker(clock)
    await breaker.record_failure(reason="connection_refused")

    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_planner().compile(checkpointer=checkpointer)

    # Both explorer (post-fallback) and planner route through subprocess
    # because the override redirects planner-explorer → planner-synth.
    _StubClaudeCodeSubprocess.script = [
        (_explorer_report_json(), _opus_usage()),
        (_plan_json(), _opus_usage()),
    ]

    cfg, _tracker, _storage = await _build_config(
        tmp_path=tmp_path, run_id="run-fallback", breaker=breaker
    )
    try:
        paused = await app.ainvoke(
            {"run_id": "run-fallback", "input": _planner_input()}, cfg
        )
        assert "__interrupt__" in paused

        final = await app.ainvoke(Command(resume="fallback"), cfg)
        assert "__interrupt__" in final  # plan_review gate next

        # Explorer never called LiteLLM — override routed it to Claude Code.
        assert _StubLiteLLMAdapter.call_count == 0
        # Two subprocess calls: the re-fired explorer + the planner node.
        assert _StubClaudeCodeSubprocess.call_count == 2
        assert _StubClaudeCodeSubprocess.routed_flags == ["opus", "opus"]

        assert final["_mid_run_tier_overrides"] == {
            PLANNER_OLLAMA_FALLBACK.logical: (
                PLANNER_OLLAMA_FALLBACK.fallback_tier
            )
        }
        assert final["_ollama_fallback_fired"] is True
    finally:
        await checkpointer.conn.close()


# ---------------------------------------------------------------------------
# AC — ABORT terminates via hard_stop
# ---------------------------------------------------------------------------


async def test_abort_terminates_hard_stop(tmp_path: Path) -> None:
    """``FallbackChoice.ABORT`` routes to ``planner_hard_stop``.

    Asserts the terminal node writes a ``hard_stop_metadata`` artefact,
    returns ``ollama_fallback_aborted=True``, and no further provider
    calls fire post-resume.
    """
    clock = {"t": 0.0}
    breaker = _build_breaker(clock)
    await breaker.record_failure(reason="connection_refused")

    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_planner().compile(checkpointer=checkpointer)

    # No script entries — any provider call would fail "stub exhausted".
    cfg, _tracker, storage = await _build_config(
        tmp_path=tmp_path, run_id="run-abort", breaker=breaker
    )
    try:
        paused = await app.ainvoke(
            {"run_id": "run-abort", "input": _planner_input()}, cfg
        )
        assert "__interrupt__" in paused

        final = await app.ainvoke(Command(resume="abort"), cfg)

        # Terminal state — no further interrupts, no further provider calls.
        assert "__interrupt__" not in final
        assert final.get("ollama_fallback_aborted") is True
        assert _StubLiteLLMAdapter.call_count == 0
        assert _StubClaudeCodeSubprocess.call_count == 0

        # Artefact row landed for the post-mortem surface.
        artifact = await storage.read_artifact(
            "run-abort", "hard_stop_metadata"
        )
        assert artifact is not None
        assert "ollama_fallback_abort" in artifact["payload_json"]
        assert PLANNER_OLLAMA_FALLBACK.logical in artifact["payload_json"]
    finally:
        await checkpointer.conn.close()
