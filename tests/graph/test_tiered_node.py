"""Tests for ``ai_workflows.graph.tiered_node`` (M2 Task 03).

Covers every AC from
[task_03_tiered_node.md](../../design_docs/phases/milestone_2_graph/task_03_tiered_node.md):

* AC-1 — Node is a standard LangGraph node (plain ``async def``, takes
  state, returns dict).
* AC-2 — Both provider paths covered (LiteLLM + Claude Code).
* AC-3 — Semaphore respected (``max_concurrency=1`` serialises
  concurrent invocations).
* AC-4 — Emits exactly one structured log record per invocation.
* AC-5 — Emits exactly one ``CostTracker.record`` call per invocation.
* AC-6 — ``uv run pytest tests/graph/test_tiered_node.py`` green.

And the carry-over from M2 Task 07's audit (M2-T07-ISS-01):

* Exception classification passes the original task spec wording —
  adapter raises ``litellm.RateLimitError`` → node raises
  ``RetryableTransient`` (option (b) of the T07 deferred issue).
* On success the node clears ``state['last_exception']`` so
  ``RetryingEdge`` does not re-fire on stale data.

Every provider call is stubbed — no live API or subprocess runs.
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
from ai_workflows.primitives.cost import CostTracker, TokenUsage
from ai_workflows.primitives.retry import (
    NonRetryable,
    RetryableTransient,
)
from ai_workflows.primitives.tiers import (
    ClaudeCodeRoute,
    LiteLLMRoute,
    TierConfig,
)

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------


def _prompt_fn(_state: Mapping[str, Any]) -> tuple[str | None, list[dict]]:
    """Return a trivial ``(system, messages)`` pair for tests."""
    return ("sys", [{"role": "user", "content": "hello"}])


def _litellm_tier(*, max_concurrency: int = 1) -> dict[str, TierConfig]:
    return {
        "planner": TierConfig(
            name="planner",
            route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
            max_concurrency=max_concurrency,
            per_call_timeout_s=30,
        )
    }


def _claude_code_tier() -> dict[str, TierConfig]:
    return {
        "planner": TierConfig(
            name="planner",
            route=ClaudeCodeRoute(cli_model_flag="sonnet"),
            max_concurrency=1,
            per_call_timeout_s=30,
        )
    }


def _build_config(
    *,
    tier_registry: dict[str, TierConfig],
    cost_tracker: CostTracker | None = None,
    run_id: str = "run-1",
    semaphores: dict[str, asyncio.Semaphore] | None = None,
    pricing: dict | None = None,
) -> dict[str, Any]:
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


class _FakeLiteLLMAdapter:
    """Stand-in for :class:`LiteLLMAdapter` with controllable behaviour."""

    last_instance: _FakeLiteLLMAdapter | None = None
    calls: list[dict[str, Any]] = []
    concurrent: int = 0
    max_concurrent: int = 0
    hold: asyncio.Event | None = None

    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        self.route = route
        self.per_call_timeout_s = per_call_timeout_s
        _FakeLiteLLMAdapter.last_instance = self

    async def complete(
        self, *, system: str | None, messages: list[dict], response_format: Any = None
    ) -> tuple[str, TokenUsage]:
        _FakeLiteLLMAdapter.calls.append(
            {"system": system, "messages": messages, "response_format": response_format}
        )
        _FakeLiteLLMAdapter.concurrent += 1
        _FakeLiteLLMAdapter.max_concurrent = max(
            _FakeLiteLLMAdapter.max_concurrent, _FakeLiteLLMAdapter.concurrent
        )
        try:
            if _FakeLiteLLMAdapter.hold is not None:
                await _FakeLiteLLMAdapter.hold.wait()
            else:
                await asyncio.sleep(0)
            usage = TokenUsage(
                input_tokens=12,
                output_tokens=7,
                cost_usd=0.00042,
                model=self.route.model,
            )
            return ("fake-text", usage)
        finally:
            _FakeLiteLLMAdapter.concurrent -= 1


class _RaisingLiteLLMAdapter:
    """Stand-in :class:`LiteLLMAdapter` that raises from ``complete``."""

    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        self.route = route
        self.per_call_timeout_s = per_call_timeout_s

    async def complete(
        self, *, system: str | None, messages: list[dict], response_format: Any = None
    ) -> tuple[str, TokenUsage]:
        raise litellm.RateLimitError(
            "429", llm_provider="gemini", model=self.route.model
        )


class _BadRequestLiteLLMAdapter:
    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        self.route = route
        self.per_call_timeout_s = per_call_timeout_s

    async def complete(
        self, *, system: str | None, messages: list[dict], response_format: Any = None
    ) -> tuple[str, TokenUsage]:
        raise litellm.BadRequestError(
            "bad", model=self.route.model, llm_provider="gemini"
        )


class _FakeClaudeCodeAdapter:
    last_instance: _FakeClaudeCodeAdapter | None = None

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
        _FakeClaudeCodeAdapter.last_instance = self

    async def complete(
        self, *, system: str | None, messages: list[dict], response_format: Any = None
    ) -> tuple[str, TokenUsage]:
        usage = TokenUsage(
            input_tokens=5,
            output_tokens=3,
            cost_usd=0.01,
            model=self.route.cli_model_flag,
        )
        return ("cli-text", usage)


@pytest.fixture(autouse=True)
def _reset_fake_adapter_state() -> None:
    """Reset the class-level counters on every test so runs stay isolated."""
    _FakeLiteLLMAdapter.calls = []
    _FakeLiteLLMAdapter.concurrent = 0
    _FakeLiteLLMAdapter.max_concurrent = 0
    _FakeLiteLLMAdapter.hold = None
    _FakeLiteLLMAdapter.last_instance = None
    _FakeClaudeCodeAdapter.last_instance = None


# ---------------------------------------------------------------------------
# AC-2 — LiteLLM dispatch path
# ---------------------------------------------------------------------------


async def test_dispatches_to_litellm_adapter_for_litellm_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-2 (LiteLLM): route.kind='litellm' → LiteLLMAdapter drives the call."""
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _FakeLiteLLMAdapter)

    node = tiered_node(tier="planner", prompt_fn=_prompt_fn, node_name="llm")
    config = _build_config(tier_registry=_litellm_tier())

    with structlog.testing.capture_logs() as logs:
        out = await node({}, config)

    assert out["llm_output"] == "fake-text"
    assert out["last_exception"] is None
    assert _FakeLiteLLMAdapter.last_instance is not None
    assert _FakeLiteLLMAdapter.last_instance.route.model == "gemini/gemini-2.5-flash"
    # AC-4 — exactly one structured log.
    assert len(logs) == 1
    assert logs[0]["provider"] == "litellm"
    assert logs[0]["model"] == "gemini/gemini-2.5-flash"
    assert logs[0]["event"] == "node_completed"


# ---------------------------------------------------------------------------
# AC-2 — Claude Code dispatch path
# ---------------------------------------------------------------------------


async def test_dispatches_to_claude_code_driver_for_claude_code_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-2 (Claude Code): route.kind='claude_code' → ClaudeCodeSubprocess drives."""
    monkeypatch.setattr(
        tiered_node_module, "ClaudeCodeSubprocess", _FakeClaudeCodeAdapter
    )

    node = tiered_node(tier="planner", prompt_fn=_prompt_fn, node_name="llm")
    config = _build_config(tier_registry=_claude_code_tier(), pricing={})

    with structlog.testing.capture_logs() as logs:
        out = await node({}, config)

    assert out["llm_output"] == "cli-text"
    assert out["last_exception"] is None
    assert _FakeClaudeCodeAdapter.last_instance is not None
    assert _FakeClaudeCodeAdapter.last_instance.route.cli_model_flag == "sonnet"
    assert len(logs) == 1
    assert logs[0]["provider"] == "claude_code"
    assert logs[0]["model"] == "sonnet"


# ---------------------------------------------------------------------------
# AC-3 — Semaphore enforcement
# ---------------------------------------------------------------------------


async def test_semaphore_enforces_max_concurrency_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-3: two concurrent invocations serialise under max_concurrency=1."""
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _FakeLiteLLMAdapter)
    _FakeLiteLLMAdapter.hold = asyncio.Event()

    node = tiered_node(tier="planner", prompt_fn=_prompt_fn, node_name="llm")
    semaphores = {"planner": asyncio.Semaphore(1)}
    config = _build_config(
        tier_registry=_litellm_tier(max_concurrency=1), semaphores=semaphores
    )

    t1 = asyncio.create_task(node({}, config))
    t2 = asyncio.create_task(node({}, config))

    # Yield repeatedly so both tasks have a chance to try entering the
    # semaphore; only one should be inside the fake adapter's complete()
    # at any time.
    for _ in range(5):
        await asyncio.sleep(0)

    assert _FakeLiteLLMAdapter.concurrent == 1
    assert _FakeLiteLLMAdapter.max_concurrent == 1

    # Release first invocation; second can now proceed.
    _FakeLiteLLMAdapter.hold.set()
    await asyncio.gather(t1, t2)

    assert _FakeLiteLLMAdapter.max_concurrent == 1
    assert len(_FakeLiteLLMAdapter.calls) == 2


async def test_no_semaphore_entry_allows_unbounded_concurrency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing semaphore entry = node does not enforce a cap itself."""
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _FakeLiteLLMAdapter)
    _FakeLiteLLMAdapter.hold = asyncio.Event()

    node = tiered_node(tier="planner", prompt_fn=_prompt_fn, node_name="llm")
    # No ``semaphores`` entry for the tier.
    config = _build_config(tier_registry=_litellm_tier(max_concurrency=1))

    t1 = asyncio.create_task(node({}, config))
    t2 = asyncio.create_task(node({}, config))
    for _ in range(5):
        await asyncio.sleep(0)

    assert _FakeLiteLLMAdapter.max_concurrent == 2

    _FakeLiteLLMAdapter.hold.set()
    await asyncio.gather(t1, t2)


# ---------------------------------------------------------------------------
# AC-4 — Exactly one structured log record per invocation
# ---------------------------------------------------------------------------


async def test_emits_exactly_one_structured_log_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-4: success path emits exactly one log with §8.1 fields populated."""
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _FakeLiteLLMAdapter)

    node = tiered_node(tier="planner", prompt_fn=_prompt_fn, node_name="planner_node")
    config = _build_config(tier_registry=_litellm_tier())
    config["configurable"]["workflow"] = "planner_wf"

    with structlog.testing.capture_logs() as logs:
        await node({}, config)

    assert len(logs) == 1
    record = logs[0]
    assert record["event"] == "node_completed"
    assert record["run_id"] == "run-1"
    assert record["workflow"] == "planner_wf"
    assert record["node"] == "planner_node"
    assert record["tier"] == "planner"
    assert record["provider"] == "litellm"
    assert record["input_tokens"] == 12
    assert record["output_tokens"] == 7
    assert record["cost_usd"] == pytest.approx(0.00042)
    assert "duration_ms" in record


async def test_emits_exactly_one_structured_log_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-4: failure path also emits exactly one record (error level)."""
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _RaisingLiteLLMAdapter)

    node = tiered_node(tier="planner", prompt_fn=_prompt_fn, node_name="llm")
    config = _build_config(tier_registry=_litellm_tier())

    with structlog.testing.capture_logs() as logs, pytest.raises(RetryableTransient):
        await node({}, config)

    assert len(logs) == 1
    assert logs[0]["event"] == "node_failed"
    assert logs[0]["log_level"] == "error"
    assert logs[0]["bucket"] == "RetryableTransient"


# ---------------------------------------------------------------------------
# AC-5 — Exactly one CostTracker.record call per successful invocation
# ---------------------------------------------------------------------------


async def test_emits_exactly_one_cost_record_per_successful_invocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-5: one record per successful invocation; tier is stamped on it."""
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _FakeLiteLLMAdapter)

    node = tiered_node(tier="planner", prompt_fn=_prompt_fn, node_name="llm")
    config = _build_config(tier_registry=_litellm_tier())

    await node({}, config)

    tracker: CostTracker = config["_tracker"]
    # Private attribute probe — fine for a unit test that asserts the
    # single-write invariant explicitly.
    entries = tracker._entries["run-1"]  # noqa: SLF001
    assert len(entries) == 1
    assert entries[0].cost_usd == pytest.approx(0.00042)
    # Tier annotation is the TieredNode's responsibility so by_tier works.
    assert entries[0].tier == "planner"


async def test_no_cost_record_on_failed_invocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-5 corollary: failed invocations do not record a ledger entry."""
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _RaisingLiteLLMAdapter)

    node = tiered_node(tier="planner", prompt_fn=_prompt_fn, node_name="llm")
    config = _build_config(tier_registry=_litellm_tier())

    with pytest.raises(RetryableTransient):
        await node({}, config)

    tracker: CostTracker = config["_tracker"]
    assert tracker._entries.get("run-1", []) == []  # noqa: SLF001


async def test_budget_breach_emits_exactly_one_failure_log_and_raises_non_retryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Budget breach via ``CostTrackingCallback`` still emits the single log.

    Covers the edge case where ``cost_callback.on_node_complete`` raises
    :class:`NonRetryable` (per architecture §8.5) — the AC-4 invariant
    must hold even when the failure originates in the cost callback
    rather than the provider adapter.
    """
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _FakeLiteLLMAdapter)

    node = tiered_node(tier="planner", prompt_fn=_prompt_fn, node_name="llm")
    tracker = CostTracker()
    callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=0.0)
    config = {
        "configurable": {
            "tier_registry": _litellm_tier(),
            "cost_callback": callback,
            "run_id": "run-1",
        }
    }

    with (
        structlog.testing.capture_logs() as logs,
        pytest.raises(NonRetryable),
    ):
        await node({}, config)

    assert len(logs) == 1
    assert logs[0]["event"] == "node_failed"
    assert logs[0]["bucket"] == "NonRetryable"


# ---------------------------------------------------------------------------
# Exception classification (spec test + NonRetryable pairing)
# ---------------------------------------------------------------------------


async def test_litellm_rate_limit_error_raises_retryable_transient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec test: adapter raises ``litellm.RateLimitError`` → node raises
    ``RetryableTransient``."""
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _RaisingLiteLLMAdapter)

    node = tiered_node(tier="planner", prompt_fn=_prompt_fn, node_name="llm")
    config = _build_config(tier_registry=_litellm_tier())

    with pytest.raises(RetryableTransient):
        await node({}, config)


async def test_litellm_bad_request_error_raises_non_retryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-transient LiteLLM exceptions route through the NonRetryable bucket."""
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _BadRequestLiteLLMAdapter)

    node = tiered_node(tier="planner", prompt_fn=_prompt_fn, node_name="llm")
    config = _build_config(tier_registry=_litellm_tier())

    with pytest.raises(NonRetryable):
        await node({}, config)


# ---------------------------------------------------------------------------
# Carry-over M2-T07-ISS-01 — clear last_exception on success
# ---------------------------------------------------------------------------


async def test_success_path_clears_stale_last_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Carry-over: success path returns ``last_exception=None`` so
    ``RetryingEdge`` does not re-fire on stale data from a prior retry.
    """
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _FakeLiteLLMAdapter)

    node = tiered_node(tier="planner", prompt_fn=_prompt_fn, node_name="llm")
    config = _build_config(tier_registry=_litellm_tier())
    state = {"last_exception": RetryableTransient("stale from last turn")}

    out = await node(state, config)

    assert "last_exception" in out
    assert out["last_exception"] is None


# ---------------------------------------------------------------------------
# Configuration / registry contracts
# ---------------------------------------------------------------------------


async def test_missing_configurable_raises_non_retryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No config at all (or missing required keys) → NonRetryable with a
    clear message, never a silent retry loop on KeyError."""
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _FakeLiteLLMAdapter)

    node = tiered_node(tier="planner", prompt_fn=_prompt_fn, node_name="llm")

    with pytest.raises(NonRetryable):
        await node({}, None)


async def test_unknown_tier_raises_non_retryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Asking for a tier that isn't in the registry is a configuration error."""
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _FakeLiteLLMAdapter)

    node = tiered_node(tier="not_a_real_tier", prompt_fn=_prompt_fn, node_name="llm")
    config = _build_config(tier_registry=_litellm_tier())

    with pytest.raises(NonRetryable):
        await node({}, config)


# ---------------------------------------------------------------------------
# AC-1 — node shape (sanity)
# ---------------------------------------------------------------------------


async def test_node_returns_a_dict_with_output_key_keyed_by_node_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-1: node returns a dict; raw text lands under ``f"{node_name}_output"``."""
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _FakeLiteLLMAdapter)

    node = tiered_node(tier="planner", prompt_fn=_prompt_fn, node_name="orchestrator")
    config = _build_config(tier_registry=_litellm_tier())

    out = await node({}, config)

    assert isinstance(out, dict)
    assert out["orchestrator_output"] == "fake-text"
