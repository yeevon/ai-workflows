"""Unit tests for :mod:`ai_workflows.graph.error_handler` (M2 Task 08 carry-over
— M2-T07-ISS-01).

The wrapper is the "option (b) state-update wrapper" the T07 audit
assigned to T08. These tests pin its contract against the exact dict
shape the T07 issue specified — so a future change that drifts the
shape (e.g. swaps ``_retry_counts`` for a run-scoped attempt counter,
or forgets to bump ``_non_retryable_failures`` on
:class:`NonRetryable`) fails loudly.

End-to-end exercise of the wrapper in a real graph lives in
``tests/graph/test_smoke_graph.py``; this module focuses on the
wrapper's pure input/output behaviour.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from ai_workflows.graph.error_handler import wrap_with_error_handler
from ai_workflows.primitives.retry import (
    NonRetryable,
    RetryableSemantic,
    RetryableTransient,
)


async def _ok_state_only(state: Mapping[str, Any]) -> dict[str, Any]:
    """Stand-in node that succeeds and accepts ``(state)`` only."""
    return {"ok": True, "input_seen": dict(state)}


async def _ok_state_and_config(
    state: Mapping[str, Any], config: Any = None
) -> dict[str, Any]:
    """Stand-in node that succeeds and accepts ``(state, config)``."""
    return {"ok": True, "config_seen": config}


def _raiser(exc: Exception) -> Any:
    async def _node(state: Mapping[str, Any]) -> dict[str, Any]:
        raise exc

    return _node


async def test_wrapper_returns_node_result_on_success() -> None:
    wrapped = wrap_with_error_handler(_ok_state_only, node_name="n")

    result = await wrapped({"run_id": "r"}, None)

    assert result == {"ok": True, "input_seen": {"run_id": "r"}}


async def test_wrapper_catches_retryable_transient_and_writes_state() -> None:
    exc = RetryableTransient("429")
    wrapped = wrap_with_error_handler(_raiser(exc), node_name="llm")

    result = await wrapped({}, None)

    assert result["last_exception"] is exc
    assert result["_retry_counts"] == {"llm": 1}
    assert result["_non_retryable_failures"] == 0


async def test_wrapper_catches_retryable_semantic_and_writes_state() -> None:
    exc = RetryableSemantic(reason="schema miss", revision_hint="try again")
    wrapped = wrap_with_error_handler(_raiser(exc), node_name="validator")

    result = await wrapped({}, None)

    assert result["last_exception"] is exc
    assert result["_retry_counts"] == {"validator": 1}
    assert result["_non_retryable_failures"] == 0


async def test_wrapper_catches_non_retryable_and_bumps_failure_counter() -> None:
    exc = NonRetryable("budget exceeded")
    wrapped = wrap_with_error_handler(_raiser(exc), node_name="llm")

    result = await wrapped({}, None)

    assert result["last_exception"] is exc
    assert result["_retry_counts"] == {"llm": 1}
    assert result["_non_retryable_failures"] == 1


async def test_wrapper_preserves_other_retry_counts_keys() -> None:
    """Other nodes' counters survive when this node increments its own."""
    wrapped = wrap_with_error_handler(
        _raiser(RetryableTransient("again")), node_name="llm"
    )

    state: dict[str, Any] = {"_retry_counts": {"validator": 2, "llm": 1}}
    result = await wrapped(state, None)

    assert result["_retry_counts"] == {"validator": 2, "llm": 2}


async def test_wrapper_accumulates_non_retryable_failures_across_runs() -> None:
    wrapped = wrap_with_error_handler(
        _raiser(NonRetryable("dead")), node_name="n"
    )
    state: dict[str, Any] = {"_non_retryable_failures": 1}

    result = await wrapped(state, None)

    assert result["_non_retryable_failures"] == 2


async def test_wrapper_forwards_config_when_node_accepts_it() -> None:
    wrapped = wrap_with_error_handler(_ok_state_and_config, node_name="n")

    sentinel = {"configurable": {"marker": object()}}
    result = await wrapped({}, sentinel)

    assert result["config_seen"] is sentinel


async def test_wrapper_skips_config_when_node_rejects_it() -> None:
    """Calling a ``(state)``-only node with a config must not TypeError."""
    wrapped = wrap_with_error_handler(_ok_state_only, node_name="n")

    result = await wrapped({"run_id": "x"}, {"configurable": {"ignored": 1}})

    assert result == {"ok": True, "input_seen": {"run_id": "x"}}


async def test_wrapper_does_not_mutate_incoming_state() -> None:
    """The wrapper must treat state as read-only — LangGraph checkpoints
    may hand it back a snapshot-shared dict."""
    wrapped = wrap_with_error_handler(
        _raiser(RetryableTransient("x")), node_name="llm"
    )
    original_counts = {"validator": 7}
    state: dict[str, Any] = {"_retry_counts": original_counts}

    result = await wrapped(state, None)

    # Result is a fresh dict; the caller's dict is untouched.
    assert state["_retry_counts"] is original_counts
    assert original_counts == {"validator": 7}
    assert result["_retry_counts"] is not original_counts
    assert result["_retry_counts"] == {"validator": 7, "llm": 1}


async def test_wrapper_does_not_trap_unclassified_exceptions() -> None:
    """Only the three buckets are trapped; arbitrary exceptions propagate."""
    wrapped = wrap_with_error_handler(
        _raiser(ValueError("not a bucket")), node_name="n"
    )

    with pytest.raises(ValueError, match="not a bucket"):
        await wrapped({}, None)
