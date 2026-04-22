"""Tests for M8 Task 02 — :mod:`ai_workflows.primitives.circuit_breaker`.

Pins the 8 acceptance criteria called out by the task spec. Uses an
injected ``time_source`` callable to manipulate the cooldown clock —
no real sleeps, no new dev dependency.
"""

from __future__ import annotations

import asyncio
import io
import logging
from typing import Any

import pytest
import structlog

from ai_workflows.primitives import CircuitBreaker, CircuitOpen, CircuitState


class _FakeClock:
    """Monotonic clock the tests can advance explicitly."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> _FakeClock:
    return _FakeClock()


@pytest.fixture
def log_records() -> list[dict[str, Any]]:
    """Capture structlog records emitted by the circuit-breaker logger.

    Returns a list populated in-order with every event dict the logger
    emits during the test. Resets structlog afterwards so subsequent
    tests start from a clean configuration.
    """
    records: list[dict[str, Any]] = []

    def _collect(_logger: Any, _method: str, event_dict: dict[str, Any]) -> str:
        records.append(dict(event_dict))
        return ""

    structlog.configure(
        processors=[_collect],
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        logger_factory=structlog.PrintLoggerFactory(file=io.StringIO()),
        cache_logger_on_first_use=False,
    )
    yield records
    structlog.reset_defaults()


async def test_starts_closed() -> None:
    breaker = CircuitBreaker(tier="local_coder")

    assert breaker.state is CircuitState.CLOSED
    assert await breaker.allow() is True


async def test_trips_open_after_threshold_failures() -> None:
    breaker = CircuitBreaker(tier="local_coder", trip_threshold=3)

    for _ in range(3):
        await breaker.record_failure(reason="timeout")

    assert breaker.state is CircuitState.OPEN
    assert await breaker.allow() is False


async def test_success_resets_counter_mid_streak() -> None:
    breaker = CircuitBreaker(tier="local_coder", trip_threshold=3)

    await breaker.record_failure(reason="timeout")
    await breaker.record_failure(reason="timeout")
    await breaker.record_success()
    await breaker.record_failure(reason="timeout")

    assert breaker.state is CircuitState.CLOSED
    # counter must have been zeroed — otherwise the fourth failure above
    # would have tripped (threshold=3 w/ cumulative counting).
    assert await breaker.allow() is True


async def test_half_open_after_cooldown(clock: _FakeClock) -> None:
    breaker = CircuitBreaker(
        tier="local_coder",
        trip_threshold=3,
        cooldown_s=60.0,
        time_source=clock,
    )

    for _ in range(3):
        await breaker.record_failure(reason="timeout")
    assert breaker.state is CircuitState.OPEN

    clock.advance(61.0)

    assert await breaker.allow() is True
    assert breaker.state is CircuitState.HALF_OPEN
    # Single-probe semantics: next allow() returns False until record_*.
    assert await breaker.allow() is False


async def test_half_open_success_closes(clock: _FakeClock) -> None:
    breaker = CircuitBreaker(
        tier="local_coder",
        trip_threshold=3,
        cooldown_s=60.0,
        time_source=clock,
    )
    for _ in range(3):
        await breaker.record_failure(reason="timeout")
    clock.advance(61.0)
    await breaker.allow()
    assert breaker.state is CircuitState.HALF_OPEN

    await breaker.record_success()

    assert breaker.state is CircuitState.CLOSED
    assert await breaker.allow() is True


async def test_half_open_failure_reopens(clock: _FakeClock) -> None:
    breaker = CircuitBreaker(
        tier="local_coder",
        trip_threshold=3,
        cooldown_s=60.0,
        time_source=clock,
    )
    for _ in range(3):
        await breaker.record_failure(reason="timeout")
    clock.advance(61.0)
    await breaker.allow()
    assert breaker.state is CircuitState.HALF_OPEN

    await breaker.record_failure(reason="connection_refused")

    assert breaker.state is CircuitState.OPEN
    # cooldown clock resets — a fresh 60s window must elapse.
    assert await breaker.allow() is False
    clock.advance(30.0)
    assert await breaker.allow() is False
    clock.advance(31.0)
    assert await breaker.allow() is True


async def test_concurrent_branches_do_not_double_trip(
    log_records: list[dict[str, Any]],
) -> None:
    breaker = CircuitBreaker(tier="local_coder", trip_threshold=3)

    await asyncio.gather(
        *(breaker.record_failure(reason="timeout") for _ in range(10))
    )

    assert breaker.state is CircuitState.OPEN
    transitions = [r for r in log_records if r.get("event") == "circuit_state"]
    assert len(transitions) == 1, (
        f"expected exactly one CLOSED→OPEN transition log, got {transitions!r}"
    )
    assert transitions[0]["from"] == "closed"
    assert transitions[0]["to"] == "open"


async def test_last_reason_survives_trip() -> None:
    breaker = CircuitBreaker(tier="local_coder", trip_threshold=3)

    await breaker.record_failure(reason="timeout")
    await breaker.record_failure(reason="http_503")
    await breaker.record_failure(reason="connection_refused")

    assert breaker.state is CircuitState.OPEN
    assert breaker.last_reason == "connection_refused"

    exc = CircuitOpen(tier=breaker.tier, last_reason=breaker.last_reason)
    assert exc.tier == "local_coder"
    assert exc.last_reason == "connection_refused"
    assert "local_coder" in str(exc)
    assert "connection_refused" in str(exc)
