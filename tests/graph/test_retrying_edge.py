"""Tests for ``ai_workflows.graph.retrying_edge`` (M2 Task 07).

Cover every AC from
[task_07_retrying_edge.md](../../design_docs/phases/milestone_2_graph/task_07_retrying_edge.md):
all three buckets route correctly, attempt counters live in state
(durable across a checkpoint resume), and the double-failure hard-stop
forces ``on_terminal`` regardless of the current bucket.
"""

from __future__ import annotations

from typing import Any

from ai_workflows.graph.retrying_edge import retrying_edge
from ai_workflows.primitives.retry import (
    NonRetryable,
    RetryableSemantic,
    RetryableTransient,
    RetryPolicy,
)

_ON_TRANSIENT = "llm"
_ON_SEMANTIC = "llm"
_ON_TERMINAL = "__end__"


def _edge(policy: RetryPolicy | None = None):
    """Factory helper pinning the three destination names under test."""
    return retrying_edge(
        on_transient=_ON_TRANSIENT,
        on_semantic=_ON_SEMANTIC,
        on_terminal=_ON_TERMINAL,
        policy=policy or RetryPolicy(),
    )


def _state(**overrides: Any) -> dict[str, Any]:
    """Build a state dict with sensible defaults for the counters."""
    base: dict[str, Any] = {
        "last_exception": None,
        "_retry_counts": {},
        "_non_retryable_failures": 0,
    }
    base.update(overrides)
    return base


def test_transient_routes_to_on_transient_until_max_then_terminal() -> None:
    """AC-1 (transient bucket) — routes until attempts hit cap, then terminal."""
    policy = RetryPolicy(max_transient_attempts=3)
    edge = _edge(policy)

    for attempts_so_far in range(policy.max_transient_attempts):
        state = _state(
            last_exception=RetryableTransient("blip"),
            _retry_counts={_ON_TRANSIENT: attempts_so_far},
        )
        assert edge(state) == _ON_TRANSIENT

    exhausted = _state(
        last_exception=RetryableTransient("blip"),
        _retry_counts={_ON_TRANSIENT: policy.max_transient_attempts},
    )
    assert edge(exhausted) == _ON_TERMINAL


def test_semantic_routes_to_on_semantic_and_preserves_revision_hint() -> None:
    """AC-1 (semantic bucket) — routes to LLM node with hint intact."""
    edge = _edge()
    hint = "field `tier` must be one of {planner, implementer, ...}"
    exc = RetryableSemantic(reason="schema miss", revision_hint=hint)
    state = _state(last_exception=exc)

    assert edge(state) == _ON_SEMANTIC
    # Pure-routing edge must not touch the exception instance.
    assert state["last_exception"] is exc
    assert state["last_exception"].revision_hint == hint


def test_semantic_exhaustion_routes_to_terminal() -> None:
    """AC-1 (semantic bucket) — exhausted attempts escalate to terminal."""
    policy = RetryPolicy(max_semantic_attempts=3)
    edge = _edge(policy)

    state = _state(
        last_exception=RetryableSemantic(reason="bad", revision_hint="try again"),
        _retry_counts={_ON_SEMANTIC: policy.max_semantic_attempts},
    )
    assert edge(state) == _ON_TERMINAL


def test_non_retryable_routes_to_terminal() -> None:
    """AC-1 (non-retryable bucket) — always terminal."""
    edge = _edge()
    state = _state(last_exception=NonRetryable("auth failed"))
    assert edge(state) == _ON_TERMINAL


def test_double_non_retryable_failure_forces_terminal_even_for_transient() -> None:
    """AC-3 — a second NonRetryable hard-stops the run regardless of sibling state.

    If the run already has two non-retryable failures logged, even a
    transient exception (which would otherwise self-loop) must route to
    the terminal path per architecture §8.2.
    """
    edge = _edge()
    state = _state(
        last_exception=RetryableTransient("would normally retry"),
        _retry_counts={_ON_TRANSIENT: 0},
        _non_retryable_failures=2,
    )
    assert edge(state) == _ON_TERMINAL


def test_attempt_counters_are_read_from_state_so_they_survive_resume() -> None:
    """AC-2 — counters live in state (durable across checkpoint resume).

    Simulates a resume by building a fresh edge instance and a fresh
    state dict carrying the pre-pause counter values; the edge's
    decision must depend solely on those state values, never on any
    hidden internal counter.
    """
    policy = RetryPolicy(max_transient_attempts=3)
    pre_pause = _state(
        last_exception=RetryableTransient("blip"),
        _retry_counts={_ON_TRANSIENT: 2},
    )
    assert _edge(policy)(pre_pause) == _ON_TRANSIENT

    # New process / fresh closure, same state → same decision.
    resumed = dict(pre_pause)
    assert _edge(policy)(resumed) == _ON_TRANSIENT

    # One more attempt taken before the next firing hits the cap.
    exhausted = _state(
        last_exception=RetryableTransient("blip"),
        _retry_counts={_ON_TRANSIENT: 3},
    )
    assert _edge(policy)(exhausted) == _ON_TERMINAL


def test_missing_last_exception_defensively_routes_to_terminal() -> None:
    """No classified exception in state → defensive terminal, never a silent self-loop."""
    edge = _edge()
    assert edge(_state()) == _ON_TERMINAL


def test_unknown_exception_type_is_treated_as_terminal() -> None:
    """Anything outside the three buckets routes to terminal — no silent retry."""
    edge = _edge()
    state = _state(last_exception=ValueError("not classified"))
    assert edge(state) == _ON_TERMINAL


def test_distinct_on_transient_and_on_semantic_destinations_are_respected() -> None:
    """Caller can wire different destinations per bucket — each counter is keyed by name."""
    edge = retrying_edge(
        on_transient="retry_transient",
        on_semantic="retry_semantic",
        on_terminal="__end__",
        policy=RetryPolicy(max_transient_attempts=2, max_semantic_attempts=2),
    )

    transient_state = _state(
        last_exception=RetryableTransient("blip"),
        _retry_counts={"retry_transient": 1, "retry_semantic": 5},
    )
    assert edge(transient_state) == "retry_transient"

    semantic_state = _state(
        last_exception=RetryableSemantic(reason="bad", revision_hint="fix"),
        _retry_counts={"retry_transient": 5, "retry_semantic": 1},
    )
    assert edge(semantic_state) == "retry_semantic"
