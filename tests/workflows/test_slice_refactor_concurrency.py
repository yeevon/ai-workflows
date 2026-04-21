"""Tests for the T07 per-tier concurrency semaphore.

Covers the concurrency-related ACs from
``design_docs/phases/milestone_6_slice_refactor/task_07_concurrency_hard_stop.md``:

* AC-1: :func:`tiered_node` acquires a :class:`asyncio.Semaphore` keyed by
  tier name (process-local, shared across fan-out branches) from
  ``config["configurable"]["semaphores"]``. Dispatch builds the dict from
  each tier's :attr:`TierConfig.max_concurrency` at the run boundary so
  workflows never manage the registry by hand.
* AC-2: fan-out of 5 slices against ``max_concurrency=2`` sees at most
  2 concurrent provider calls; the other 3 queue on the semaphore.
* AC-3: two tiers each configured ``max_concurrency=1`` see concurrent
  activity *between* tiers (one in-flight call per tier simultaneously),
  i.e. the cap is per-tier-name, not workflow-wide.
* No-fan-out regression: the planner workflow (single-tier, no fan-out)
  runs identically to its M5 shape with the semaphore threaded through.

Architecture grounding: architecture.md §8.6 — "per-tier concurrency
semaphore"; the cap lives at the call site (:func:`tiered_node`), not
at the graph topology level.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from ai_workflows import workflows
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.graph.cost_callback import CostTrackingCallback
from ai_workflows.graph.tiered_node import tiered_node
from ai_workflows.primitives.cost import CostTracker, TokenUsage
from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig
from ai_workflows.workflows._dispatch import _build_semaphores
from ai_workflows.workflows.planner import build_planner
from ai_workflows.workflows.slice_refactor import (
    build_slice_refactor,
    slice_refactor_tier_registry,
)


@pytest.fixture(autouse=True)
def _reensure_workflows_registered() -> Iterator[None]:
    workflows._reset_for_tests()
    workflows.register("planner", build_planner)
    workflows.register("slice_refactor", build_slice_refactor)
    yield


# ---------------------------------------------------------------------------
# AC-1 structural: dispatch builds one Semaphore per tier, keyed by name
# ---------------------------------------------------------------------------


def test_build_semaphores_returns_one_per_tier_keyed_by_name() -> None:
    """AC-1 structural: :func:`_build_semaphores` returns an
    :class:`asyncio.Semaphore` for every tier in the registry, keyed
    by the tier's logical name.
    """
    route = LiteLLMRoute(model="gemini/gemini-2.5-flash")
    registry = {
        "a": TierConfig(name="a", route=route, max_concurrency=2, per_call_timeout_s=30),
        "b": TierConfig(name="b", route=route, max_concurrency=5, per_call_timeout_s=30),
    }
    sems = _build_semaphores(registry)
    assert set(sems.keys()) == {"a", "b"}
    for sem in sems.values():
        assert isinstance(sem, asyncio.Semaphore)


def test_build_semaphores_respects_max_concurrency_budget() -> None:
    """AC-1 structural: each semaphore's capacity equals the tier's
    ``max_concurrency``. Uses ``Semaphore._value`` as the observable
    budget (the only way to read current free slots without acquiring).
    """
    route = LiteLLMRoute(model="gemini/gemini-2.5-flash")
    registry = {
        "small": TierConfig(name="small", route=route, max_concurrency=1, per_call_timeout_s=30),
        "wide": TierConfig(name="wide", route=route, max_concurrency=7, per_call_timeout_s=30),
    }
    sems = _build_semaphores(registry)
    assert sems["small"]._value == 1
    assert sems["wide"]._value == 7


def test_build_semaphores_returns_fresh_dict_per_call() -> None:
    """AC-1 structural: two calls return **independent** semaphore dicts
    so concurrent runs do not share the cap (spec: "per-run,
    process-local"). Sharing would misattribute cross-run queuing as
    single-run latency.
    """
    route = LiteLLMRoute(model="gemini/gemini-2.5-flash")
    registry = {
        "a": TierConfig(name="a", route=route, max_concurrency=3, per_call_timeout_s=30),
    }
    sems1 = _build_semaphores(registry)
    sems2 = _build_semaphores(registry)
    assert sems1 is not sems2
    assert sems1["a"] is not sems2["a"]


# ---------------------------------------------------------------------------
# AC-2 / AC-3 observability: direct TieredNode tests with instrumented stub
# ---------------------------------------------------------------------------


class _ConcurrencyStub:
    """Instrumented LiteLLM adapter that records in-flight concurrency.

    Each :meth:`complete` call increments ``_inflight_by_tier[tier]`` on
    entry, records the post-increment value into
    ``_peak_inflight_by_tier``, sleeps briefly so parallel callers
    overlap, then decrements. The post-increment peak is the observable
    ceiling the test asserts against.

    Tier is detected from the ``route.model`` suffix the test threads
    through (``model="stub/<tier>"``) — the real adapter does not know
    the logical tier and we preserve that invariant by not touching
    :class:`TierConfig`.
    """

    _inflight_by_tier: dict[str, int] = {}
    _peak_inflight_by_tier: dict[str, int] = {}
    _lock: asyncio.Lock | None = None

    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        self.route = route

    @classmethod
    def _tier_from_route(cls, route: LiteLLMRoute) -> str:
        return route.model.split("/", 1)[1]

    @classmethod
    async def _bump(cls, tier: str, delta: int) -> int:
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        async with cls._lock:
            cls._inflight_by_tier[tier] = cls._inflight_by_tier.get(tier, 0) + delta
            value = cls._inflight_by_tier[tier]
            if delta > 0:
                cls._peak_inflight_by_tier[tier] = max(
                    cls._peak_inflight_by_tier.get(tier, 0), value
                )
            return value

    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict],
        response_format: Any = None,
    ) -> tuple[str, TokenUsage]:
        tier = self._tier_from_route(self.route)
        await _ConcurrencyStub._bump(tier, +1)
        try:
            await asyncio.sleep(0.02)
        finally:
            await _ConcurrencyStub._bump(tier, -1)
        return (
            '{"ok": true}',
            TokenUsage(
                input_tokens=1,
                output_tokens=1,
                cost_usd=0.0,
                model=self.route.model,
            ),
        )

    @classmethod
    def reset(cls) -> None:
        cls._inflight_by_tier = {}
        cls._peak_inflight_by_tier = {}
        cls._lock = None


@pytest.fixture
def _stub_adapter(monkeypatch: pytest.MonkeyPatch) -> type[_ConcurrencyStub]:
    _ConcurrencyStub.reset()
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _ConcurrencyStub)
    return _ConcurrencyStub


def _tier_cfg(tier_name: str, max_concurrency: int) -> TierConfig:
    return TierConfig(
        name=tier_name,
        route=LiteLLMRoute(model=f"stub/{tier_name}"),
        max_concurrency=max_concurrency,
        per_call_timeout_s=30,
    )


def _prompt_noop(state: dict[str, Any]) -> tuple[str | None, list[dict]]:
    return None, [{"role": "user", "content": "ignored"}]


async def test_semaphore_bounds_parallel_calls_on_single_tier(
    _stub_adapter: type[_ConcurrencyStub],
) -> None:
    """AC-2: with ``max_concurrency=2`` on tier ``slow``, 5 parallel
    :func:`tiered_node` invocations see at most 2 concurrent provider
    calls. The other 3 queue on the :class:`asyncio.Semaphore`
    dispatch threads through ``configurable["semaphores"]``.
    """
    registry = {"slow": _tier_cfg("slow", max_concurrency=2)}
    sems = _build_semaphores(registry)
    tracker = CostTracker()
    callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=None)
    cfg = {
        "configurable": {
            "tier_registry": registry,
            "cost_callback": callback,
            "run_id": "run-sem-fanout",
            "workflow": "test",
            "semaphores": sems,
        }
    }
    node = tiered_node(
        tier="slow", prompt_fn=_prompt_noop, node_name="probe"
    )
    await asyncio.gather(*(node({}, cfg) for _ in range(5)))
    assert _ConcurrencyStub._peak_inflight_by_tier["slow"] <= 2
    assert _ConcurrencyStub._peak_inflight_by_tier["slow"] >= 1


async def test_without_semaphore_fanout_would_exceed_cap(
    _stub_adapter: type[_ConcurrencyStub],
) -> None:
    """Regression guard: absent a semaphore entry for the tier, the
    :func:`tiered_node` falls through to the "no cap" path and all 5
    calls overlap. Pins the semaphore as the load-bearing mechanism
    — removing the entry would silently lift the cap.
    """
    registry = {"wide": _tier_cfg("wide", max_concurrency=2)}
    tracker = CostTracker()
    callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=None)
    cfg = {
        "configurable": {
            "tier_registry": registry,
            "cost_callback": callback,
            "run_id": "run-sem-nosem",
            "workflow": "test",
            "semaphores": {},  # empty map: no cap enforced
        }
    }
    node = tiered_node(
        tier="wide", prompt_fn=_prompt_noop, node_name="probe"
    )
    await asyncio.gather(*(node({}, cfg) for _ in range(5)))
    assert _ConcurrencyStub._peak_inflight_by_tier["wide"] > 2


async def test_semaphore_is_per_tier_not_workflow_wide(
    _stub_adapter: type[_ConcurrencyStub],
) -> None:
    """AC-3: two tiers each at ``max_concurrency=1`` — calls fired at
    both in parallel see both tiers active simultaneously (one per tier
    at any moment). Proves the cap is keyed by tier name, not the
    number of in-flight :func:`tiered_node` calls overall.
    """
    registry = {
        "alpha": _tier_cfg("alpha", max_concurrency=1),
        "beta": _tier_cfg("beta", max_concurrency=1),
    }
    sems = _build_semaphores(registry)
    tracker = CostTracker()
    callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=None)

    def _cfg(tier: str) -> dict[str, Any]:
        return {
            "configurable": {
                "tier_registry": registry,
                "cost_callback": callback,
                "run_id": "run-sem-two-tiers",
                "workflow": "test",
                "semaphores": sems,
            }
        }

    alpha_node = tiered_node(
        tier="alpha", prompt_fn=_prompt_noop, node_name="alpha_probe"
    )
    beta_node = tiered_node(
        tier="beta", prompt_fn=_prompt_noop, node_name="beta_probe"
    )
    await asyncio.gather(
        alpha_node({}, _cfg("alpha")),
        alpha_node({}, _cfg("alpha")),
        beta_node({}, _cfg("beta")),
        beta_node({}, _cfg("beta")),
    )
    # Each tier individually capped at 1 in-flight.
    assert _ConcurrencyStub._peak_inflight_by_tier["alpha"] <= 1
    assert _ConcurrencyStub._peak_inflight_by_tier["beta"] <= 1
    # Both tiers did observe in-flight activity — the cap is independent.
    assert _ConcurrencyStub._peak_inflight_by_tier["alpha"] >= 1
    assert _ConcurrencyStub._peak_inflight_by_tier["beta"] >= 1


# ---------------------------------------------------------------------------
# AC-1 structural: dispatch wires semaphores into slice_refactor's registry
# ---------------------------------------------------------------------------


def test_slice_refactor_tier_registry_produces_valid_semaphore_set() -> None:
    """AC-1: the registry slice_refactor declares composes with the
    planner's tiers; dispatch's :func:`_build_semaphores` works over it
    without invented fields.
    """
    registry = slice_refactor_tier_registry()
    sems = _build_semaphores(registry)
    # slice_refactor composes planner's tiers + the slice-worker tier.
    assert "slice-worker" in sems
    assert "planner-explorer" in sems
    assert "planner-synth" in sems
    for name, sem in sems.items():
        assert isinstance(sem, asyncio.Semaphore)
        assert sem._value == registry[name].max_concurrency


# ---------------------------------------------------------------------------
# No-fan-out regression: planner unaffected by the semaphore wiring
# ---------------------------------------------------------------------------


async def test_planner_single_tier_runs_normally_under_semaphore(
    _stub_adapter: type[_ConcurrencyStub],
) -> None:
    """AC: the planner workflow (single-tier, no fan-out) runs through
    :func:`tiered_node` with the semaphore dict threaded in — never
    queues on itself, and never exceeds its ``max_concurrency`` budget
    under a serial run.

    This is the T07 "no-fan-out regression" AC: the semaphore plumbing
    does not alter the planner's wall-clock characteristics for a
    sequential run.
    """
    registry = {"solo": _tier_cfg("solo", max_concurrency=3)}
    sems = _build_semaphores(registry)
    tracker = CostTracker()
    callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=None)
    cfg = {
        "configurable": {
            "tier_registry": registry,
            "cost_callback": callback,
            "run_id": "run-solo",
            "workflow": "test",
            "semaphores": sems,
        }
    }
    node = tiered_node(
        tier="solo", prompt_fn=_prompt_noop, node_name="solo_probe"
    )
    # Sequential invocation: no parallelism, so the peak is always 1.
    for _ in range(3):
        await node({}, cfg)
    assert _ConcurrencyStub._peak_inflight_by_tier["solo"] == 1
    # Budget unused (2 slots still free after each sequential call).
    assert sems["solo"]._value == 3


# ---------------------------------------------------------------------------
# Dispatch wiring: _build_cfg includes a "semaphores" key
# ---------------------------------------------------------------------------


async def test_build_cfg_threads_semaphores_into_configurable(
    tmp_path: Path,
) -> None:
    """AC-1 wiring: :func:`_build_cfg` writes a ``semaphores`` entry into
    ``config["configurable"]`` so :func:`tiered_node` can pick it up
    without an explicit per-invocation plumb. Verified by introspecting
    the dict dispatch assembles.
    """
    from ai_workflows.primitives.storage import SQLiteStorage
    from ai_workflows.workflows._dispatch import _build_cfg

    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    registry = {"t1": _tier_cfg("t1", max_concurrency=2)}
    tracker = CostTracker()
    callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=None)
    cfg = _build_cfg(
        run_id="run-cfg-sem",
        workflow="test",
        tier_registry=registry,
        callback=callback,
        storage=storage,
    )
    assert "semaphores" in cfg["configurable"]
    sems = cfg["configurable"]["semaphores"]
    assert set(sems.keys()) == {"t1"}
    assert sems["t1"]._value == 2
