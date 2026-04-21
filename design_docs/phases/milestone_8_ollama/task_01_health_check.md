# Task 01 — `OllamaHealthCheck` Probe Primitive

**Status:** 📝 Planned.
**Grounding:** [milestone README §Exit criteria 1](README.md) · [architecture.md §8.4](../../architecture.md) · [KDR-007](../../architecture.md).

## What to Build

Single-shot HTTP probe of an Ollama endpoint that returns a typed
`HealthResult`. This task lands the **probe primitive only** — no
scheduler, no callbacks, no `TieredNode` integration, no circuit
breaker. Downstream consumers arrive in T02 (circuit breaker reads the
same exception surface) and T03 (fallback gate renders the probe
result in its prompt).

The probe uses the already-bundled `httpx` (pulled in transitively via
`litellm`) — no new dependency. Queries Ollama's `/api/tags` endpoint
(cheap, unauthenticated, returns 200 + JSON when the daemon is up).

## Deliverables

### [ai_workflows/primitives/llm/ollama_health.py](../../../ai_workflows/primitives/llm/ollama_health.py)

```python
class HealthResult(BaseModel):
    """Outcome of a single Ollama probe.

    Passed to CircuitBreaker.record_* (T02) and rendered in the
    fallback gate prompt (T03). Bare-typed per KDR-010.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    is_healthy: bool
    endpoint: str           # the URL probed, e.g. "http://localhost:11434"
    latency_ms: float | None  # None on failure
    reason: str             # short human-readable; "ok" on success


async def probe_ollama(
    *,
    endpoint: str = "http://localhost:11434",
    timeout_s: float = 2.0,
) -> HealthResult:
    """GET <endpoint>/api/tags with a hard wall-clock timeout.

    Classification:
      * HTTP 200 + parseable JSON → is_healthy=True, reason="ok".
      * httpx.ConnectError         → is_healthy=False, reason="connection_refused".
      * httpx.ReadTimeout          → is_healthy=False, reason="timeout".
      * non-2xx status              → is_healthy=False, reason=f"http_{status}".
      * other exceptions            → is_healthy=False, reason=f"error:{type}".

    Never raises — callers treat HealthResult.is_healthy as the signal.
    """
```

Endpoint resolution convention (documented in the module docstring):

- Default `http://localhost:11434` matches Ollama's out-of-box listener.
- Callers that pin a non-default endpoint via `LiteLLMRoute.api_base`
  should pass the same string. T04's `TieredNode` integration forwards
  `route.api_base or "http://localhost:11434"`.

### [ai_workflows/primitives/llm/__init__.py](../../../ai_workflows/primitives/llm/__init__.py)

Export `HealthResult` and `probe_ollama` alongside the existing
`LiteLLMAdapter` / `ClaudeCodeSubprocess` exports.

### Tests

[tests/primitives/llm/test_ollama_health.py](../../../tests/primitives/llm/test_ollama_health.py):

- `test_probe_reports_healthy_on_200` — stubbed `httpx.AsyncClient.get`
  returns 200 + `{"models": [...]}`; assert `is_healthy=True`,
  `reason="ok"`, `latency_ms` is a non-negative float.
- `test_probe_reports_unhealthy_on_connect_error` — stub raises
  `httpx.ConnectError`; assert `is_healthy=False`,
  `reason="connection_refused"`, `latency_ms is None`.
- `test_probe_reports_unhealthy_on_timeout` — stub raises
  `httpx.ReadTimeout`; assert `reason="timeout"`.
- `test_probe_reports_unhealthy_on_non_2xx` — stub returns 503;
  assert `reason="http_503"`.
- `test_probe_swallows_arbitrary_exceptions` — stub raises
  `RuntimeError("boom")`; assert `is_healthy=False`,
  `reason="error:RuntimeError"`, **no exception propagates**.
- `test_probe_respects_timeout_s` — stub sleeps 5s, `timeout_s=0.1`;
  assert probe returns with `reason="timeout"` within 1s wall-clock.

No live-network test — the probe is pure I/O wrapping and is tested
with `httpx` stubs. Live probing is exercised at T05 via the E2E
degraded-mode test.

## Acceptance Criteria

- [ ] `from ai_workflows.primitives.llm import HealthResult, probe_ollama` works.
- [ ] `HealthResult` is a pydantic v2 model with `extra="forbid"` and
      `frozen=True`, bare-typed per KDR-010.
- [ ] `probe_ollama` never propagates an exception — all failure modes
      return a `HealthResult` with `is_healthy=False` and a stable
      `reason` string matching the mapping above.
- [ ] Every listed test passes under `uv run pytest tests/primitives/llm/test_ollama_health.py`.
- [ ] `uv run lint-imports` still reports **4 contracts kept**
      (no new layer edges introduced — probe is primitives-layer).
- [ ] `uv run ruff check` clean.
- [ ] No new runtime dependency (`httpx` already present via `litellm`).

## Dependencies

- M7 close-out (four-contract import-linter baseline is in place).

## Out of scope (explicit)

- Any periodic / scheduled probing. (Deferred — the project's failure
  signal is per-call failure in `TieredNode`, not an ambient poller.
  Promoted to [nice_to_have.md](../../nice_to_have.md) if a later
  milestone surfaces a need.)
- Circuit breaker state. (T02.)
- Fallback `HumanGate`. (T03.)
- `TieredNode` integration. (T04.)
- CLI surface (e.g. `aiw doctor`). (Not on the M8 punch list; revisit
  at M9+ if operational need surfaces.)
