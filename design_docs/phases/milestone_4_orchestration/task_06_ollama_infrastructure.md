# Task 06 — Ollama Operational Infrastructure (NEW)

**Issues:** IMP-06, SD-03

## What to Build

The operational wrapping around `OllamaClient` that was deferred from M1. Startup health check, explicit network-error handling, circuit breaker with automatic fallback to Haiku.

## Why Here and Not M1

M1 kept the Ollama adapter simple — it just works when Ollama is reachable. The operational complexity (health checks, fallback, LAN-vs-cloud retry backoff) was deferred because it distracted from core framework work and your M1-M3 workflows default to cloud.

In M4, `slice_refactor` may run exploration across large repos where Qwen-on-home-desktop is genuinely cheaper than Haiku-in-cloud. This is when reliability matters.

## Deliverables

### Startup Health Check

When a workflow uses a tier with `provider: ollama`, at run start:

```python
async def ollama_health_check(base_url: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{base_url}/api/tags")
            r.raise_for_status()
    except httpx.HTTPError as e:
        raise OllamaUnavailableError(
            f"Ollama not reachable at {base_url}. "
            f"If Ollama is at home, check VPN connection. "
            f"Use --profile local to route to localhost, "
            f"or edit workflow.yaml to use 'haiku' tier instead."
        ) from e
```

Fails fast with a specific, actionable error — not a cryptic connection error mid-run.

### Circuit Breaker

Track consecutive failures per provider:

```python
class ProviderCircuitBreaker:
    def __init__(self, failure_threshold: int = 3, reset_after: float = 60.0): ...
    async def record_failure(self, provider: str) -> None: ...
    async def record_success(self, provider: str) -> None: ...
    def is_open(self, provider: str) -> bool:
        """True if circuit is open (too many recent failures)."""
```

When the breaker opens on Ollama: subsequent calls do not hit Ollama. They either raise or fall back to a cloud tier (see below).

### Automatic Haiku Fallback

Workflow YAML can declare fallback tiers:

```yaml
components:
  explore:
    type: worker
    tier: local_coder
    fallback_tier: haiku        # on circuit-open or ConnectionError, use haiku
    # ...
```

When fallback triggers:

1. Log a WARNING — "Ollama unreachable, falling back to haiku for this call"
2. Record the fallback event in `llm_calls` table with `is_fallback=1`
3. Rebuild the Agent with the fallback tier's Model
4. Continue the workflow

### Schema Addition

```sql
-- migrations/004_ollama_fallback.sql
ALTER TABLE llm_calls ADD COLUMN is_fallback INTEGER DEFAULT 0;
```

### LAN vs Cloud Retry Backoff

Update `retry_on_rate_limit()` to take a `base_delay` from the tier config:

```yaml
local_coder:
  provider: ollama
  max_retries: 2          # fewer attempts on LAN
  retry_base_delay: 0.5   # shorter backoff
haiku:
  provider: anthropic
  max_retries: 3          # standard for cloud
  retry_base_delay: 1.0
```

Prevents long waits when Ollama is simply down (should fail fast to trigger fallback).

### Pause vs Fallback Semantics

Two failure modes for Ollama:

- **Immediate fallback** (default) — ConnectionError → use `fallback_tier` automatically, log it
- **Pause and prompt** (opt-in via `on_network_failure: pause`) — run pauses, user gets a prompt to retry, switch tier, or abort. Useful for work-laptop runs where you notice the VPN dropped.

Default: immediate fallback. `on_network_failure: pause` is per-component opt-in.

## Acceptance Criteria

- [ ] Workflow with Ollama tier and unreachable Ollama fails at startup with `OllamaUnavailableError` — not mid-run
- [ ] Circuit breaker opens after 3 consecutive failures
- [ ] Fallback tier is used when circuit is open, logged with `is_fallback=1`
- [ ] `aiw inspect` shows fallback events distinctly
- [ ] LAN tiers use shorter retry delays than cloud tiers
- [ ] `on_network_failure: pause` produces an interactive prompt instead of auto-fallback

## Dependencies

- M1 Task 10 (retry)
- M1 Task 08 (storage — migration system)
- M4 Task 04 (HumanGate — for pause-and-prompt pattern)
