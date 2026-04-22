"""Tests for the :func:`TieredNode` ↔ :class:`CircuitBreaker` integration (M8 T04).

Covers every AC from
[design_docs/phases/milestone_8_ollama/task_04_tiered_node_integration.md](
../../design_docs/phases/milestone_8_ollama/task_04_tiered_node_integration.md):

* Breaker-open short-circuits to :class:`CircuitOpen` without adapter call.
* Half-open breaker allows a single probe; success closes it.
* Transient failures call :meth:`CircuitBreaker.record_failure`; non-retryable
  failures do not.
* Non-Ollama LiteLLM routes and :class:`ClaudeCodeRoute` tiers bypass the
  breaker entirely (consult rule per spec AC-1).
* Structured-log record carries ``breaker_state=<closed|open|half_open>``
  on the success path.

All provider calls are stubbed; no network, no subprocess.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import litellm
import pytest
import structlog

from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.graph.cost_callback import CostTrackingCallback
from ai_workflows.graph.tiered_node import tiered_node
from ai_workflows.primitives.circuit_breaker import (
    CircuitBreaker,
    CircuitOpen,
    CircuitState,
)
from ai_workflows.primitives.cost import CostTracker, TokenUsage
from ai_workflows.primitives.retry import NonRetryable, RetryableTransient
from ai_workflows.primitives.tiers import (
    ClaudeCodeRoute,
    LiteLLMRoute,
    TierConfig,
)


def _prompt_fn(_state: Mapping[str, Any]) -> tuple[str | None, list[dict]]:
    return ("sys", [{"role": "user", "content": "hello"}])


def _ollama_tier() -> dict[str, TierConfig]:
    return {
        "slice-worker": TierConfig(
            name="slice-worker",
            route=LiteLLMRoute(
                model="ollama/qwen2.5-coder:32b",
                api_base="http://localhost:11434",
            ),
            max_concurrency=1,
            per_call_timeout_s=30,
        )
    }


def _gemini_tier() -> dict[str, TierConfig]:
    return {
        "gemini_flash": TierConfig(
            name="gemini_flash",
            route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
            max_concurrency=1,
            per_call_timeout_s=30,
        )
    }


def _claude_tier() -> dict[str, TierConfig]:
    return {
        "planner-synth": TierConfig(
            name="planner-synth",
            route=ClaudeCodeRoute(cli_model_flag="opus"),
            max_concurrency=1,
            per_call_timeout_s=30,
        )
    }


def _build_config(
    *,
    tier_registry: dict[str, TierConfig],
    breakers: dict[str, CircuitBreaker] | None = None,
    pricing: dict | None = None,
) -> dict[str, Any]:
    tracker = CostTracker()
    callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=None)
    configurable: dict[str, Any] = {
        "tier_registry": tier_registry,
        "cost_callback": callback,
        "run_id": "run-1",
    }
    if breakers is not None:
        configurable["ollama_circuit_breakers"] = breakers
    if pricing is not None:
        configurable["pricing"] = pricing
    return {"configurable": configurable}


class _SuccessfulLiteLLMAdapter:
    """Successful stub that also records call count."""

    call_count = 0

    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        self.route = route
        self.per_call_timeout_s = per_call_timeout_s

    async def complete(
        self, *, system: str | None, messages: list[dict], response_format: Any = None
    ) -> tuple[str, TokenUsage]:
        _SuccessfulLiteLLMAdapter.call_count += 1
        return (
            "ok",
            TokenUsage(
                input_tokens=1,
                output_tokens=1,
                cost_usd=0.0,
                model=self.route.model,
            ),
        )


class _AssertingNoCallAdapter:
    """Fails loud if :meth:`complete` is invoked — used for pre-call
    short-circuit assertions."""

    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        self.route = route
        self.per_call_timeout_s = per_call_timeout_s

    async def complete(
        self, *, system: str | None, messages: list[dict], response_format: Any = None
    ) -> tuple[str, TokenUsage]:
        raise AssertionError("adapter must not be called when breaker is OPEN")


class _ConnErrorLiteLLMAdapter:
    """Raises :class:`litellm.APIConnectionError` on every call."""

    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        self.route = route
        self.per_call_timeout_s = per_call_timeout_s

    async def complete(
        self, *, system: str | None, messages: list[dict], response_format: Any = None
    ) -> tuple[str, TokenUsage]:
        raise litellm.APIConnectionError(
            message="no route to host",
            llm_provider="ollama",
            model=self.route.model,
        )


class _AuthErrorLiteLLMAdapter:
    """Raises :class:`litellm.AuthenticationError` — classifies as
    :class:`NonRetryable`."""

    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        self.route = route
        self.per_call_timeout_s = per_call_timeout_s

    async def complete(
        self, *, system: str | None, messages: list[dict], response_format: Any = None
    ) -> tuple[str, TokenUsage]:
        raise litellm.AuthenticationError(
            message="bad creds",
            llm_provider="ollama",
            model=self.route.model,
        )


class _FakeClaudeCodeAdapter:
    def __init__(
        self,
        *,
        route: ClaudeCodeRoute,
        per_call_timeout_s: int,
        pricing: dict,
    ) -> None:
        self.route = route
        self.per_call_timeout_s = per_call_timeout_s
        self.pricing = pricing

    async def complete(
        self, *, system: str | None, messages: list[dict], response_format: Any = None
    ) -> tuple[str, TokenUsage]:
        return (
            "opus-text",
            TokenUsage(
                input_tokens=1,
                output_tokens=1,
                cost_usd=0.0,
                model=self.route.cli_model_flag,
            ),
        )


@pytest.fixture(autouse=True)
def _reset_call_counts() -> None:
    _SuccessfulLiteLLMAdapter.call_count = 0


# ---------------------------------------------------------------------------
# AC — CircuitOpen pre-call when breaker denies
# ---------------------------------------------------------------------------


async def test_breaker_open_raises_circuit_open_without_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC: breaker OPEN → :class:`CircuitOpen` before any adapter call."""
    monkeypatch.setattr(
        tiered_node_module, "LiteLLMAdapter", _AssertingNoCallAdapter
    )

    # Pre-trip a breaker by recording threshold failures.
    breaker = CircuitBreaker(tier="slice-worker", trip_threshold=1, cooldown_s=60.0)
    await breaker.record_failure(reason="connection_refused")
    assert breaker.state is CircuitState.OPEN

    node = tiered_node(
        tier="slice-worker", prompt_fn=_prompt_fn, node_name="worker"
    )
    config = _build_config(
        tier_registry=_ollama_tier(), breakers={"slice-worker": breaker}
    )

    with pytest.raises(CircuitOpen) as exc_info:
        await node({}, config)
    assert exc_info.value.tier == "slice-worker"
    assert exc_info.value.last_reason == "connection_refused"


# ---------------------------------------------------------------------------
# AC — Half-open breaker allows a single probe
# ---------------------------------------------------------------------------


async def test_breaker_half_open_allows_single_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC: HALF_OPEN probe call runs; success flips the breaker CLOSED."""
    monkeypatch.setattr(
        tiered_node_module, "LiteLLMAdapter", _SuccessfulLiteLLMAdapter
    )

    clock = {"t": 0.0}

    def _time_source() -> float:
        return clock["t"]

    breaker = CircuitBreaker(
        tier="slice-worker",
        trip_threshold=1,
        cooldown_s=1.0,
        time_source=_time_source,
    )
    await breaker.record_failure(reason="timeout")
    assert breaker.state is CircuitState.OPEN
    clock["t"] += 2.0  # cooldown elapsed

    node = tiered_node(
        tier="slice-worker", prompt_fn=_prompt_fn, node_name="worker"
    )
    config = _build_config(
        tier_registry=_ollama_tier(), breakers={"slice-worker": breaker}
    )

    out = await node({}, config)
    assert out["worker_output"] == "ok"
    assert breaker.state is CircuitState.CLOSED
    assert _SuccessfulLiteLLMAdapter.call_count == 1


# ---------------------------------------------------------------------------
# AC — Transient failure records on breaker
# ---------------------------------------------------------------------------


async def test_transient_failure_records_on_breaker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC: transient provider error → :meth:`record_failure` invoked
    with the exception's class name, node re-raises
    :class:`RetryableTransient`."""
    monkeypatch.setattr(
        tiered_node_module, "LiteLLMAdapter", _ConnErrorLiteLLMAdapter
    )

    breaker = CircuitBreaker(tier="slice-worker", trip_threshold=5, cooldown_s=60.0)
    calls: list[str] = []
    original = breaker.record_failure

    async def _spy(*, reason: str) -> None:
        calls.append(reason)
        await original(reason=reason)

    breaker.record_failure = _spy  # type: ignore[method-assign]

    node = tiered_node(
        tier="slice-worker", prompt_fn=_prompt_fn, node_name="worker"
    )
    config = _build_config(
        tier_registry=_ollama_tier(), breakers={"slice-worker": breaker}
    )

    with pytest.raises(RetryableTransient):
        await node({}, config)

    assert calls == ["APIConnectionError"]


# ---------------------------------------------------------------------------
# AC — Non-retryable failure does NOT record on breaker
# ---------------------------------------------------------------------------


async def test_non_retryable_failure_does_not_record_on_breaker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC: :class:`NonRetryable`-bucket errors do NOT trip the breaker —
    auth / bad-request failures are not Ollama-health signals."""
    monkeypatch.setattr(
        tiered_node_module, "LiteLLMAdapter", _AuthErrorLiteLLMAdapter
    )

    breaker = CircuitBreaker(tier="slice-worker", trip_threshold=5, cooldown_s=60.0)
    calls: list[str] = []
    original = breaker.record_failure

    async def _spy(*, reason: str) -> None:
        calls.append(reason)
        await original(reason=reason)

    breaker.record_failure = _spy  # type: ignore[method-assign]

    node = tiered_node(
        tier="slice-worker", prompt_fn=_prompt_fn, node_name="worker"
    )
    config = _build_config(
        tier_registry=_ollama_tier(), breakers={"slice-worker": breaker}
    )

    with pytest.raises(NonRetryable):
        await node({}, config)

    assert calls == []
    assert breaker.state is CircuitState.CLOSED


# ---------------------------------------------------------------------------
# AC — Non-Ollama LiteLLM route bypasses breaker
# ---------------------------------------------------------------------------


async def test_non_ollama_litellm_route_bypasses_breaker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC: Gemini-backed LiteLLM tier bypasses the breaker even when one
    exists in the configurable map."""
    monkeypatch.setattr(
        tiered_node_module, "LiteLLMAdapter", _SuccessfulLiteLLMAdapter
    )

    # A tripped breaker under a **different** tier name MUST NOT trip the
    # Gemini call — `_resolve_breaker` keys off resolved tier name AND
    # route shape, and Gemini's route.model does not start with "ollama/".
    breaker = CircuitBreaker(
        tier="gemini_flash", trip_threshold=1, cooldown_s=60.0
    )
    await breaker.record_failure(reason="should_not_be_consulted")
    assert breaker.state is CircuitState.OPEN

    node = tiered_node(
        tier="gemini_flash", prompt_fn=_prompt_fn, node_name="llm"
    )
    config = _build_config(
        tier_registry=_gemini_tier(), breakers={"gemini_flash": breaker}
    )

    out = await node({}, config)
    assert out["llm_output"] == "ok"
    assert _SuccessfulLiteLLMAdapter.call_count == 1


# ---------------------------------------------------------------------------
# AC — ClaudeCodeRoute bypasses breaker
# ---------------------------------------------------------------------------


async def test_claude_code_route_bypasses_breaker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC: :class:`ClaudeCodeRoute` tier ignores any breaker in the
    configurable map."""
    monkeypatch.setattr(
        tiered_node_module, "ClaudeCodeSubprocess", _FakeClaudeCodeAdapter
    )

    breaker = CircuitBreaker(
        tier="planner-synth", trip_threshold=1, cooldown_s=60.0
    )
    await breaker.record_failure(reason="should_not_be_consulted")

    node = tiered_node(
        tier="planner-synth", prompt_fn=_prompt_fn, node_name="llm"
    )
    config = _build_config(
        tier_registry=_claude_tier(),
        breakers={"planner-synth": breaker},
        pricing={},
    )

    out = await node({}, config)
    assert out["llm_output"] == "opus-text"


# ---------------------------------------------------------------------------
# AC — Structured log includes breaker_state
# ---------------------------------------------------------------------------


async def test_structured_log_includes_breaker_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC: success log carries ``breaker_state='closed'`` when a CLOSED
    breaker was consulted."""
    monkeypatch.setattr(
        tiered_node_module, "LiteLLMAdapter", _SuccessfulLiteLLMAdapter
    )

    breaker = CircuitBreaker(tier="slice-worker", trip_threshold=5, cooldown_s=60.0)
    assert breaker.state is CircuitState.CLOSED

    node = tiered_node(
        tier="slice-worker", prompt_fn=_prompt_fn, node_name="worker"
    )
    config = _build_config(
        tier_registry=_ollama_tier(), breakers={"slice-worker": breaker}
    )

    with structlog.testing.capture_logs() as logs:
        await node({}, config)

    assert len(logs) == 1
    assert logs[0]["event"] == "node_completed"
    assert logs[0]["breaker_state"] == "closed"


# ---------------------------------------------------------------------------
# Mid-run tier override: state-level takes precedence over registry default
# ---------------------------------------------------------------------------


async def test_mid_run_override_routes_to_replacement_tier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """State-level ``_mid_run_tier_overrides`` takes precedence over the
    registry default so a post-gate FALLBACK swap dispatches to the
    replacement tier's route."""
    monkeypatch.setattr(
        tiered_node_module, "LiteLLMAdapter", _SuccessfulLiteLLMAdapter
    )

    # Two tiers live in the same registry; the override redirects the
    # logical ``slice-worker`` to ``gemini_flash``.
    registry = {**_ollama_tier(), **_gemini_tier()}
    node = tiered_node(
        tier="slice-worker", prompt_fn=_prompt_fn, node_name="worker"
    )
    config = _build_config(tier_registry=registry)
    state = {
        "_mid_run_tier_overrides": {"slice-worker": "gemini_flash"},
    }

    out = await node(state, config)
    assert out["worker_output"] == "ok"
    # Structured log should reflect the resolved (post-override) tier name
    # so observers see the swap.
    with structlog.testing.capture_logs() as logs:
        await node(state, config)
    assert logs[0]["tier"] == "gemini_flash"
    assert logs[0]["model"] == "gemini/gemini-2.5-flash"


async def test_state_override_outranks_configurable_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Precedence: state-level override beats configurable-level override."""
    monkeypatch.setattr(
        tiered_node_module, "LiteLLMAdapter", _SuccessfulLiteLLMAdapter
    )

    # Registry has three tiers; configurable sends slice-worker to a
    # claude tier, but state redirects to gemini_flash. Assert gemini wins.
    registry = {**_ollama_tier(), **_gemini_tier(), **_claude_tier()}
    node = tiered_node(
        tier="slice-worker", prompt_fn=_prompt_fn, node_name="worker"
    )
    tracker = CostTracker()
    callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=None)
    configurable: dict[str, Any] = {
        "tier_registry": registry,
        "cost_callback": callback,
        "run_id": "run-1",
        "tier_overrides": {"slice-worker": "planner-synth"},
        "pricing": {},
    }
    config = {"configurable": configurable}
    state = {"_mid_run_tier_overrides": {"slice-worker": "gemini_flash"}}

    with structlog.testing.capture_logs() as logs:
        await node(state, config)
    assert logs[0]["tier"] == "gemini_flash"


# ---------------------------------------------------------------------------
# No breakers map → no CircuitOpen check
# ---------------------------------------------------------------------------


async def test_missing_breakers_map_is_no_op(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``configurable`` carries no ``ollama_circuit_breakers`` key
    at all, the node does not consult any breaker and does not emit
    ``breaker_state`` in its log (an older workflow without the breaker
    plumbing must still run)."""
    monkeypatch.setattr(
        tiered_node_module, "LiteLLMAdapter", _SuccessfulLiteLLMAdapter
    )

    node = tiered_node(
        tier="slice-worker", prompt_fn=_prompt_fn, node_name="worker"
    )
    # No breakers argument — configurable.ollama_circuit_breakers is absent.
    config = _build_config(tier_registry=_ollama_tier())

    with structlog.testing.capture_logs() as logs:
        await node({}, config)

    assert logs[0]["event"] == "node_completed"
    assert "breaker_state" not in logs[0]


# Make sure asyncio is imported for test discovery when running in
# isolation; pyproject.toml sets ``asyncio_mode = "auto"`` so the tests
# are picked up as coroutines without decorators.
_ = asyncio  # noqa: F841 — import guard for linter
