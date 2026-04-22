"""Ollama health-probe primitive (M8 Task 01).

Grounding: [architecture.md §8.4](../../../design_docs/architecture.md),
[KDR-007](../../../design_docs/architecture.md).

Single-shot HTTP probe of an Ollama daemon's ``/api/tags`` endpoint.
Returns a typed :class:`HealthResult`; never raises. Downstream consumers:

* M8 Task 02 (:mod:`ai_workflows.primitives.circuit_breaker`) — the
  breaker's ``last_reason`` mirrors the ``HealthResult.reason`` strings
  emitted here so a tripped circuit carries the same classification
  vocabulary an operator sees from a manual probe.
* M8 Task 03 (:mod:`ai_workflows.graph.ollama_fallback_gate`) — the
  fallback gate prompt renders the last recorded reason verbatim.
* M8 Task 04 (:mod:`ai_workflows.graph.tiered_node`) — not a direct
  consumer; ``TieredNode``'s mid-run health signal is the classified
  exception from :func:`ai_workflows.primitives.retry.classify`, not a
  per-call probe (out-of-scope per this task's spec, §"Out of scope").

Endpoint resolution convention
------------------------------
Callers that pin a non-default endpoint via
:attr:`ai_workflows.primitives.tiers.LiteLLMRoute.api_base` should
forward the same string here. The default ``http://localhost:11434``
matches Ollama's out-of-box listener.

Scope discipline
----------------
* **Never raises.** Every failure mode is mapped to a
  :class:`HealthResult` with ``is_healthy=False`` and a stable ``reason``
  string. This keeps the probe safe to call from timers, CLI
  diagnostics, and gate-prompt renderers without each caller needing
  a bespoke try/except.
* **One-shot.** No periodic polling, no shared client, no connection
  reuse — per §"Out of scope" in
  :doc:`/design_docs/phases/milestone_8_ollama/task_01_health_check`.
"""

from __future__ import annotations

import asyncio
import time

import httpx
from pydantic import BaseModel, ConfigDict

__all__ = ["HealthResult", "probe_ollama"]


class HealthResult(BaseModel):
    """Outcome of a single Ollama probe.

    Bare-typed per KDR-010 / ADR-0002 — no ``Field(min/max/ge/le)``
    bounds. Consumed by the M8 circuit breaker and fallback gate.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    is_healthy: bool
    endpoint: str
    latency_ms: float | None
    reason: str


async def probe_ollama(
    *,
    endpoint: str = "http://localhost:11434",
    timeout_s: float = 2.0,
) -> HealthResult:
    """GET ``<endpoint>/api/tags`` with a hard wall-clock timeout.

    Never raises. The full classification matrix is fixed so downstream
    consumers (circuit breaker, fallback gate) can rely on a stable
    vocabulary:

    * HTTP 200 + response body returned → ``is_healthy=True, reason="ok"``.
    * :class:`httpx.TimeoutException` or :class:`asyncio.TimeoutError`
      → ``is_healthy=False, reason="timeout"``.
    * :class:`httpx.ConnectError` → ``is_healthy=False, reason="connection_refused"``.
    * Non-2xx HTTP status → ``is_healthy=False, reason=f"http_{status}"``.
    * Any other exception → ``is_healthy=False, reason=f"error:{type(exc).__name__}"``.

    Parameters
    ----------
    endpoint:
        Base URL of the Ollama HTTP listener. Defaults to
        ``http://localhost:11434``.
    timeout_s:
        Wall-clock seconds permitted for the probe. The outer
        :func:`asyncio.wait_for` ensures the call returns within this
        budget even if the underlying client stalls.
    """
    started_at = time.monotonic()
    url = f"{endpoint.rstrip('/')}/api/tags"

    try:
        async with httpx.AsyncClient() as client:
            response = await asyncio.wait_for(
                client.get(url), timeout=timeout_s
            )
    except (TimeoutError, httpx.TimeoutException):
        return HealthResult(
            is_healthy=False,
            endpoint=endpoint,
            latency_ms=None,
            reason="timeout",
        )
    except httpx.ConnectError:
        return HealthResult(
            is_healthy=False,
            endpoint=endpoint,
            latency_ms=None,
            reason="connection_refused",
        )
    except Exception as exc:  # noqa: BLE001 — probe swallows by design
        return HealthResult(
            is_healthy=False,
            endpoint=endpoint,
            latency_ms=None,
            reason=f"error:{type(exc).__name__}",
        )

    latency_ms = (time.monotonic() - started_at) * 1000.0

    if response.status_code != 200:
        return HealthResult(
            is_healthy=False,
            endpoint=endpoint,
            latency_ms=latency_ms,
            reason=f"http_{response.status_code}",
        )

    return HealthResult(
        is_healthy=True,
        endpoint=endpoint,
        latency_ms=latency_ms,
        reason="ok",
    )
