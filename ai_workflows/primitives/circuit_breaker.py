"""Process-local circuit-breaker state machine (M8 Task 02).

Grounding: [architecture.md §8.4](../../design_docs/architecture.md),
[KDR-006](../../design_docs/architecture.md).

`CircuitBreaker` is consulted by :class:`ai_workflows.graph.TieredNode`
(M8 Task 04) before every Ollama-routed provider call. After
``trip_threshold`` consecutive failures within a cooldown window the
breaker flips CLOSED → OPEN and :meth:`allow` short-circuits without
waiting for a per-call timeout — the workflow layer reads that signal
and routes to the M8 Task 03 fallback :class:`HumanGate`.

Design notes
------------
* **Process-local, not Storage-backed.** Matches M6's ``_ACTIVE_RUNS``
  registry: the breaker resets on process boot. Persisting the breaker
  across restarts would require a new migration + coordination with
  ``cancel_run`` for M8's modest incremental scope; out of scope per
  T02's spec §"Out of scope".
* **Per-tier, shared across runs.** One process, one breaker per tier.
  The slice_refactor parallel fan-out (M6) shares its semaphore at the
  same granularity, so the convention is consistent.
* **Counter alignment with KDR-006.** Default ``trip_threshold=3``
  matches the three-bucket taxonomy's default ``max_transient_attempts``
  — one exhausted :class:`ai_workflows.graph.RetryingEdge` loop on a
  given call (i.e. three consecutive transient failures) is enough to
  trip the breaker.
* **Time source injection.** Tests pass a stub ``time_source`` to
  advance the clock without real sleeps; production callers let the
  default :func:`time.monotonic` run.

Relationship to sibling modules
-------------------------------
* :mod:`ai_workflows.primitives.llm.ollama_health` (M8 T01) — the
  probe's :class:`HealthResult.reason` vocabulary (``connection_refused``,
  ``timeout``, ``http_<status>``, ``error:<type>``) is the same
  classification surface :meth:`record_failure` stamps into
  :attr:`last_reason`, so a tripped breaker carries a reason string an
  operator can cross-reference against a manual probe.
* :mod:`ai_workflows.graph.tiered_node` (M8 T04) — consumer. Calls
  :meth:`allow` / :meth:`record_success` / :meth:`record_failure`
  around every LiteLLM Ollama call.
* :mod:`ai_workflows.graph.ollama_fallback_gate` (M8 T03) — reads
  :attr:`last_reason` verbatim when rendering the fallback prompt.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from enum import StrEnum

import structlog

__all__ = ["CircuitBreaker", "CircuitOpen", "CircuitState"]


_logger = structlog.get_logger("ai_workflows.circuit_breaker")


class CircuitState(StrEnum):
    """Circuit-breaker state machine.

    * ``CLOSED`` — normal operation; :meth:`CircuitBreaker.allow` returns ``True``.
    * ``OPEN`` — tripped; :meth:`CircuitBreaker.allow` returns ``False``
      until the cooldown elapses.
    * ``HALF_OPEN`` — cooldown elapsed; a single probe call is permitted.
      Its outcome (via :meth:`CircuitBreaker.record_success` /
      :meth:`CircuitBreaker.record_failure`) decides whether to close or
      re-open the breaker.
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpen(Exception):
    """Raised by callers that prefer to raise rather than branch on :meth:`CircuitBreaker.allow`.

    Carries the breaker's ``tier`` name and ``last_reason`` so the
    workflow layer (M8 Task 03 fallback gate) can render the prompt
    without re-probing.
    """

    def __init__(self, *, tier: str, last_reason: str) -> None:
        self.tier = tier
        self.last_reason = last_reason
        super().__init__(
            f"circuit open for tier={tier!r} last_reason={last_reason!r}"
        )


class CircuitBreaker:
    """Per-tier circuit-breaker state machine, process-local.

    Thread / task safety: every public coroutine is guarded by an
    :class:`asyncio.Lock` so the three parallel ``slice-worker``
    branches in ``slice_refactor`` cannot race the consecutive-failure
    counter.

    Parameters
    ----------
    tier:
        Logical tier name (e.g. ``"local_coder"``). Stamped into
        :class:`CircuitOpen` and surfaced in structured log lines.
    trip_threshold:
        Consecutive failures that flip CLOSED → OPEN. Default ``3`` —
        see module docstring for the KDR-006 alignment rationale.
    cooldown_s:
        Wall-clock seconds the breaker stays OPEN before transitioning
        to HALF_OPEN. Default ``60.0``.
    time_source:
        Callable returning seconds. Defaults to :func:`time.monotonic`;
        tests inject a stub to advance the clock deterministically.
    """

    def __init__(
        self,
        *,
        tier: str,
        trip_threshold: int = 3,
        cooldown_s: float = 60.0,
        time_source: Callable[[], float] = time.monotonic,
    ) -> None:
        self._tier = tier
        self._trip_threshold = trip_threshold
        self._cooldown_s = cooldown_s
        self._now = time_source

        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float | None = None
        self._last_reason = ""
        self._half_open_probe_in_flight = False
        self._lock = asyncio.Lock()

    @property
    def tier(self) -> str:
        """Tier name this breaker guards."""
        return self._tier

    @property
    def state(self) -> CircuitState:
        """Current state. Reads are not lock-guarded — a stale read is
        harmless because callers must still go through :meth:`allow`."""
        return self._state

    @property
    def last_reason(self) -> str:
        """Reason string from the most recent :meth:`record_failure`
        call. Empty string on a freshly constructed breaker."""
        return self._last_reason

    async def allow(self) -> bool:
        """Return ``True`` iff a call is permitted.

        In CLOSED, always ``True``. In OPEN, ``True`` once the cooldown
        has elapsed (transitioning the breaker to HALF_OPEN) — otherwise
        ``False``. In HALF_OPEN, only the **first** caller that asks
        receives ``True``; subsequent callers see ``False`` until
        :meth:`record_success` or :meth:`record_failure` resolves the
        in-flight probe.
        """
        async with self._lock:
            if self._state is CircuitState.CLOSED:
                return True

            if self._state is CircuitState.OPEN:
                if self._cooldown_elapsed():
                    self._transition(CircuitState.HALF_OPEN, reason="cooldown_elapsed")
                    self._half_open_probe_in_flight = True
                    return True
                _logger.debug(
                    "circuit_short_circuit",
                    tier=self._tier,
                    state=self._state.value,
                )
                return False

            if self._half_open_probe_in_flight:
                _logger.debug(
                    "circuit_short_circuit",
                    tier=self._tier,
                    state=self._state.value,
                )
                return False
            self._half_open_probe_in_flight = True
            return True

    async def record_success(self) -> None:
        """Record a successful call. Zeroes the counter and transitions
        any non-CLOSED state back to CLOSED."""
        async with self._lock:
            self._consecutive_failures = 0
            self._half_open_probe_in_flight = False
            if self._state is not CircuitState.CLOSED:
                self._transition(CircuitState.CLOSED, reason="success")
                self._opened_at = None

    async def record_failure(self, *, reason: str) -> None:
        """Record a failed call.

        Increments the consecutive-failure counter; flips to OPEN once
        the threshold is reached or when a HALF_OPEN probe fails (in
        which case the cooldown clock resets)."""
        async with self._lock:
            self._last_reason = reason
            self._half_open_probe_in_flight = False

            if self._state is CircuitState.HALF_OPEN:
                self._transition(CircuitState.OPEN, reason=reason)
                self._opened_at = self._now()
                return

            self._consecutive_failures += 1
            if (
                self._state is CircuitState.CLOSED
                and self._consecutive_failures >= self._trip_threshold
            ):
                self._transition(CircuitState.OPEN, reason=reason)
                self._opened_at = self._now()

    def _cooldown_elapsed(self) -> bool:
        if self._opened_at is None:
            return True
        return (self._now() - self._opened_at) >= self._cooldown_s

    def _transition(self, to_state: CircuitState, *, reason: str) -> None:
        from_state = self._state
        self._state = to_state
        _logger.info(
            "circuit_state",
            tier=self._tier,
            **{"from": from_state.value, "to": to_state.value},
            reason=reason,
        )
