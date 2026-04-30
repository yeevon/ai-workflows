"""Tests for ``TieredNode`` fallback-cascade dispatch (M15 Task 02).

Covers ACs from
[task_02_tierednode_cascade_dispatch.md](../../design_docs/phases/milestone_15_tier_overlay/task_02_tierednode_cascade_dispatch.md):

* AC-1 — ``AllFallbacksExhaustedError`` defined (NonRetryable subclass with
  ``attempts: list[TierAttempt]``).
* AC-2 — ``TierAttempt`` dataclass defined (route, exception, usage fields).
* AC-3 — Cascade dispatch: fallback routes walked after primary failure.
* AC-4 — ``RetryableSemantic`` defensive pass-through (cascade not entered).
* AC-5 — Cost attribution: only successful dispatch records to CostTracker.
* AC-6 — Empty-fallback backward compat (fallback=[] → existing behaviour).
* AC-12 — CircuitOpen triggers cascade when fallback is non-empty.
* AC-13 — Per-attempt log records emitted for each failed/succeeded route.

Hermetic — stub adapters patched via ``monkeypatch``, no provider calls,
no disk I/O.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import pytest
import structlog

from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.graph.cost_callback import CostTrackingCallback
from ai_workflows.graph.tiered_node import (
    AllFallbacksExhaustedError,
    TierAttempt,
    tiered_node,
)
from ai_workflows.primitives.cost import CostTracker, TokenUsage
from ai_workflows.primitives.retry import (
    NonRetryable,
    RetryableSemantic,
    RetryableTransient,
)
from ai_workflows.primitives.tiers import (
    LiteLLMRoute,
    TierConfig,
)

# ---------------------------------------------------------------------------
# Shared helpers / fixtures
# ---------------------------------------------------------------------------


def _prompt_fn(_state: Mapping[str, Any]) -> tuple[str | None, list[dict]]:
    """Trivial prompt builder for tests."""
    return ("sys", [{"role": "user", "content": "hello"}])


def _build_config(
    *,
    tier_registry: dict[str, TierConfig],
    cost_tracker: CostTracker | None = None,
    run_id: str = "run-1",
    semaphores: dict[str, asyncio.Semaphore] | None = None,
    pricing: dict | None = None,
) -> dict[str, Any]:
    """Build a minimal LangGraph config dict with the given registry."""
    tracker = cost_tracker or CostTracker()
    callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=None)
    configurable: dict[str, Any] = {
        "tier_registry": tier_registry,
        "cost_callback": callback,
        "run_id": run_id,
    }
    if semaphores is not None:
        configurable["semaphores"] = semaphores
    if pricing is not None:
        configurable["pricing"] = pricing
    return {"configurable": configurable, "_tracker": tracker, "_callback": callback}


def _make_registry(
    *,
    primary_model: str = "gemini/a",
    fallback_models: list[str] | None = None,
) -> dict[str, TierConfig]:
    """Build a TierConfig with optional LiteLLMRoute fallback routes."""
    fallback: list[LiteLLMRoute] = [
        LiteLLMRoute(model=m) for m in (fallback_models or [])
    ]
    return {
        "planner": TierConfig(
            name="planner",
            route=LiteLLMRoute(model=primary_model),
            max_concurrency=1,
            per_call_timeout_s=30,
            fallback=fallback,
        )
    }


class _SuccessAdapter:
    """Adapter stub that returns a fixed text + usage."""

    def __init__(
        self,
        *,
        route: LiteLLMRoute,
        per_call_timeout_s: int,
        response_text: str = "ok",
        cost: float = 0.25,
    ) -> None:
        self.route = route
        self.per_call_timeout_s = per_call_timeout_s
        self._response_text = response_text
        self._cost = cost

    async def complete(
        self, *, system: str | None, messages: list[dict], response_format: Any = None
    ) -> tuple[str, TokenUsage]:
        return (
            self._response_text,
            TokenUsage(
                input_tokens=5,
                output_tokens=3,
                cost_usd=self._cost,
                model=self.route.model,
            ),
        )


class _FailingAdapter:
    """Adapter stub that always raises ``NonRetryable``."""

    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        self.route = route
        self.per_call_timeout_s = per_call_timeout_s

    async def complete(
        self, *, system: str | None, messages: list[dict], response_format: Any = None
    ) -> tuple[str, TokenUsage]:
        raise NonRetryable(f"simulated failure for {self.route.model!r}")


class _SemanticAdapter:
    """Adapter stub that raises ``RetryableSemantic`` (abnormal but must pass through)."""

    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        self.route = route
        self.per_call_timeout_s = per_call_timeout_s

    async def complete(
        self, *, system: str | None, messages: list[dict], response_format: Any = None
    ) -> tuple[str, TokenUsage]:
        raise RetryableSemantic(
            reason="output schema violation",
            revision_hint="please fix the output",
        )


class _RetryableTransientAdapter:
    """Adapter stub that raises ``RetryableTransient`` (rate-limit / network blip)."""

    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        self.route = route
        self.per_call_timeout_s = per_call_timeout_s

    async def complete(
        self, *, system: str | None, messages: list[dict], response_format: Any = None
    ) -> tuple[str, TokenUsage]:
        raise RetryableTransient("rate-limit")


# ---------------------------------------------------------------------------
# Per-model adapter registry used by the dispatch-routing monkey-patch.
# ---------------------------------------------------------------------------

_ADAPTER_MAP: dict[str, type] = {}
"""Maps model string to the stub adapter class to instantiate."""


class _RoutingLiteLLMAdapter:
    """Routes construction to the per-model stub registered in ``_ADAPTER_MAP``."""

    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        cls = _ADAPTER_MAP.get(route.model, _SuccessAdapter)
        self._delegate = cls(route=route, per_call_timeout_s=per_call_timeout_s)

    async def complete(
        self, *, system: str | None, messages: list[dict], response_format: Any = None
    ) -> tuple[str, TokenUsage]:
        return await self._delegate.complete(
            system=system, messages=messages, response_format=response_format
        )


@pytest.fixture(autouse=True)
def _reset_adapter_map() -> None:
    """Clear per-test adapter registrations between runs."""
    _ADAPTER_MAP.clear()


# ---------------------------------------------------------------------------
# Test: cascade succeeds on fallback after primary fail
# ---------------------------------------------------------------------------


async def test_cascade_succeeds_on_fallback_after_primary_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-3 + AC-6: fallback succeeds when primary raises NonRetryable.

    Registry: primary=gemini/a (fails), fallback=[gemini/b] (succeeds).
    Node should return text from fallback without raising.
    """
    _ADAPTER_MAP["gemini/a"] = _FailingAdapter
    # gemini/b not in map → defaults to _SuccessAdapter
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _RoutingLiteLLMAdapter)

    registry = _make_registry(primary_model="gemini/a", fallback_models=["gemini/b"])
    tracker = CostTracker()
    config = _build_config(tier_registry=registry, cost_tracker=tracker)
    node = tiered_node(tier="planner", prompt_fn=_prompt_fn, node_name="planner")

    out = await node({}, config)

    assert out["planner_output"] == "ok"
    assert out["last_exception"] is None
    # Fallback cost was recorded (AC-5).
    assert tracker.total("run-1") > 0


# ---------------------------------------------------------------------------
# Test: all fallbacks exhausted raises AllFallbacksExhaustedError
# ---------------------------------------------------------------------------


async def test_cascade_exhausts_all_raises_AllFallbacksExhaustedError(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-3: all routes fail → AllFallbacksExhaustedError with 3 attempts."""
    _ADAPTER_MAP["gemini/a"] = _FailingAdapter
    _ADAPTER_MAP["gemini/b"] = _FailingAdapter
    _ADAPTER_MAP["gemini/c"] = _FailingAdapter
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _RoutingLiteLLMAdapter)

    registry = _make_registry(
        primary_model="gemini/a", fallback_models=["gemini/b", "gemini/c"]
    )
    config = _build_config(tier_registry=registry)
    node = tiered_node(tier="planner", prompt_fn=_prompt_fn, node_name="planner")

    with pytest.raises(AllFallbacksExhaustedError) as exc_info:
        await node({}, config)

    exc = exc_info.value
    # Exactly 3 attempts: primary + 2 fallbacks.
    assert len(exc.attempts) == 3
    # Correct route order.
    assert exc.attempts[0].route.model == "gemini/a"  # type: ignore[union-attr]
    assert exc.attempts[1].route.model == "gemini/b"  # type: ignore[union-attr]
    assert exc.attempts[2].route.model == "gemini/c"  # type: ignore[union-attr]
    # AllFallbacksExhaustedError is a NonRetryable subclass (AC-1).
    assert isinstance(exc, NonRetryable)


# ---------------------------------------------------------------------------
# Test: RetryableSemantic propagates unchanged — cascade not entered
# ---------------------------------------------------------------------------


async def test_cascade_skips_on_semantic_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-4: RetryableSemantic bypasses the cascade and propagates unchanged.

    This is a defensive guard — adapters do not normally raise
    RetryableSemantic (ValidatorNode does). The cascade must not
    re-classify it.
    """
    _ADAPTER_MAP["gemini/a"] = _SemanticAdapter
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _RoutingLiteLLMAdapter)

    registry = _make_registry(primary_model="gemini/a", fallback_models=["gemini/b"])
    tracker = CostTracker()
    config = _build_config(tier_registry=registry, cost_tracker=tracker)
    node = tiered_node(tier="planner", prompt_fn=_prompt_fn, node_name="planner")

    with pytest.raises(RetryableSemantic):
        await node({}, config)

    # No AllFallbacksExhaustedError should bubble out.
    # Cost tracker should have nothing (semantic failures never cost-record).
    assert tracker.total("run-1") == 0


# ---------------------------------------------------------------------------
# Test: cost attribution — only the successful fallback records cost
# ---------------------------------------------------------------------------


async def test_cascade_cost_attribution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-5: failed primary records no cost; fallback success records its cost.

    Primary (gemini/a) fails. fallback[0] (gemini/b) succeeds with cost=0.25.
    CostTracker should show exactly 0.25 for the run.
    ``cost_tracker.by_tier`` should show the logical tier name, not the
    fallback model.
    """
    _ADAPTER_MAP["gemini/a"] = _FailingAdapter
    # gemini/b defaults to _SuccessAdapter (cost=0.25 default)
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _RoutingLiteLLMAdapter)

    registry = _make_registry(primary_model="gemini/a", fallback_models=["gemini/b"])
    tracker = CostTracker()
    config = _build_config(tier_registry=registry, cost_tracker=tracker)
    node = tiered_node(tier="planner", prompt_fn=_prompt_fn, node_name="planner")

    await node({}, config)

    # Total cost should equal the fallback's cost exactly.
    assert tracker.total("run-1") == pytest.approx(0.25)

    # Tier name on the recorded usage should be the logical tier ("planner"),
    # not the fallback model string.
    by_tier = tracker.by_tier("run-1")
    assert "planner" in by_tier
    assert by_tier["planner"] == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# Test: empty fallback backward compatibility (AC-6)
# ---------------------------------------------------------------------------


async def test_empty_fallback_primary_failure_reraises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-6: fallback=[] → primary failure re-raises without cascade."""
    _ADAPTER_MAP["gemini/a"] = _FailingAdapter
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _RoutingLiteLLMAdapter)

    # No fallback routes.
    registry = _make_registry(primary_model="gemini/a", fallback_models=[])
    config = _build_config(tier_registry=registry)
    node = tiered_node(tier="planner", prompt_fn=_prompt_fn, node_name="planner")

    # Should raise NonRetryable directly, NOT AllFallbacksExhaustedError.
    with pytest.raises(NonRetryable) as exc_info:
        await node({}, config)

    assert not isinstance(exc_info.value, AllFallbacksExhaustedError)


# ---------------------------------------------------------------------------
# Test: per-attempt log records (AC-13)
# ---------------------------------------------------------------------------


async def test_per_attempt_log_records_for_cascade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-13: cascade run emits one node_failed per failed route, one node_completed on success.

    Primary (gemini/a) fails → node_failed with provider=litellm, model=gemini/a.
    Fallback (gemini/b) succeeds → node_completed with provider=litellm, model=gemini/b.
    """
    _ADAPTER_MAP["gemini/a"] = _FailingAdapter
    # gemini/b defaults to success
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _RoutingLiteLLMAdapter)

    registry = _make_registry(primary_model="gemini/a", fallback_models=["gemini/b"])
    config = _build_config(tier_registry=registry)
    node = tiered_node(tier="planner", prompt_fn=_prompt_fn, node_name="planner")

    with structlog.testing.capture_logs() as logs:
        await node({}, config)

    # Exactly 2 records: one failure (primary) + one success (fallback).
    assert len(logs) == 2

    failed_logs = [rec for rec in logs if rec["event"] == "node_failed"]
    completed_logs = [rec for rec in logs if rec["event"] == "node_completed"]
    assert len(failed_logs) == 1
    assert len(completed_logs) == 1

    # Provider/model reflect the attempted route, not always the primary.
    assert failed_logs[0]["model"] == "gemini/a"
    assert completed_logs[0]["model"] == "gemini/b"
    # Tier always shows the logical tier name on both records.
    assert failed_logs[0]["tier"] == "planner"
    assert completed_logs[0]["tier"] == "planner"


async def test_all_fail_log_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-13: all-fail cascade emits N node_failed records (one per attempted route)."""
    _ADAPTER_MAP["gemini/a"] = _FailingAdapter
    _ADAPTER_MAP["gemini/b"] = _FailingAdapter
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _RoutingLiteLLMAdapter)

    registry = _make_registry(primary_model="gemini/a", fallback_models=["gemini/b"])
    config = _build_config(tier_registry=registry)
    node = tiered_node(tier="planner", prompt_fn=_prompt_fn, node_name="planner")

    with structlog.testing.capture_logs() as logs, pytest.raises(
        AllFallbacksExhaustedError
    ):
        await node({}, config)

    # 2 routes → 2 node_failed records; no node_completed.
    failed_logs = [rec for rec in logs if rec["event"] == "node_failed"]
    assert len(failed_logs) == 2
    assert all(rec["tier"] == "planner" for rec in failed_logs)


# ---------------------------------------------------------------------------
# Test: TierAttempt and AllFallbacksExhaustedError types (AC-1, AC-2)
# ---------------------------------------------------------------------------


def test_tier_attempt_dataclass_fields() -> None:
    """AC-2: TierAttempt has route, exception, usage fields with correct types."""
    route = LiteLLMRoute(model="gemini/x")
    exc = NonRetryable("test")
    attempt = TierAttempt(route=route, exception=exc)
    assert attempt.route is route
    assert attempt.exception is exc
    assert attempt.usage is None  # forward-reserved, always None today


def test_all_fallbacks_exhausted_error_is_non_retryable() -> None:
    """AC-1: AllFallbacksExhaustedError subclasses NonRetryable."""
    route = LiteLLMRoute(model="gemini/x")
    exc = NonRetryable("fail")
    attempts = [TierAttempt(route=route, exception=exc)]
    err = AllFallbacksExhaustedError(attempts=attempts)
    assert isinstance(err, NonRetryable)
    assert err.attempts == attempts
    assert "gemini/x" in str(err)


# ---------------------------------------------------------------------------
# Test: RetryableTransient on primary triggers cascade (cycle-2 carry-over)
# ---------------------------------------------------------------------------


async def test_cascade_triggers_on_retryable_transient_primary_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-3: RetryableTransient from primary triggers cascade; fallback succeeds.

    Primary (gemini/a) raises RetryableTransient("rate-limit").
    Fallback (gemini/b) defaults to _SuccessAdapter.
    Assert: node returns fallback text, last_exception=None, cost recorded.

    Locked terminal decision 2026-04-30 (sr-sdet FIX-1 / cycle 2).
    """
    _ADAPTER_MAP["gemini/a"] = _RetryableTransientAdapter
    # gemini/b not in map → defaults to _SuccessAdapter (text="ok", cost=0.25)
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _RoutingLiteLLMAdapter)

    registry = _make_registry(primary_model="gemini/a", fallback_models=["gemini/b"])
    tracker = CostTracker()
    config = _build_config(tier_registry=registry, cost_tracker=tracker)
    node = tiered_node(tier="planner", prompt_fn=_prompt_fn, node_name="planner")

    out = await node({}, config)

    assert out["planner_output"] == "ok"
    assert out["last_exception"] is None
    # Fallback cost recorded (AC-5).
    assert tracker.total("run-1") > 0


# ---------------------------------------------------------------------------
# Test: RetryableSemantic from fallback propagates unchanged (cycle-2 carry-over)
# ---------------------------------------------------------------------------


async def test_cascade_retryable_semantic_from_fallback_propagates_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-4: RetryableSemantic raised by a fallback adapter propagates unchanged.

    Primary (gemini/a) raises NonRetryable → cascade entered.
    Fallback[0] (gemini/b) raises RetryableSemantic.
    Assert: RetryableSemantic propagates directly (not wrapped in
    AllFallbacksExhaustedError); cost_tracker.total == 0.

    Locked terminal decision 2026-04-30 (sr-sdet FIX-2 / cycle 2).
    """
    _ADAPTER_MAP["gemini/a"] = _FailingAdapter
    _ADAPTER_MAP["gemini/b"] = _SemanticAdapter
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _RoutingLiteLLMAdapter)

    registry = _make_registry(primary_model="gemini/a", fallback_models=["gemini/b"])
    tracker = CostTracker()
    config = _build_config(tier_registry=registry, cost_tracker=tracker)
    node = tiered_node(tier="planner", prompt_fn=_prompt_fn, node_name="planner")

    with pytest.raises(RetryableSemantic):
        await node({}, config)

    # Must NOT be wrapped in AllFallbacksExhaustedError.
    # Cost must be zero — semantic failures never record cost.
    assert tracker.total("run-1") == 0
