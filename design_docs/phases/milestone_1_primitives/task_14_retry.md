# Task 14 — Retry Utility

**Issues:** P-36, P-37, P-40, P-41

## What to Build

A single utility function that wraps LLM calls with 429/529 retry logic. Explicit opt-in — no decorators, no magic. Every adapter calls it directly.

## Deliverables

### `primitives/retry.py`

```python
async def retry_on_rate_limit(
    fn: Callable[..., Awaitable[T]],
    *args,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    **kwargs,
) -> T:
    """
    Call fn(*args, **kwargs). On 429 or 529, retry with exponential
    backoff + jitter up to max_attempts times. All other exceptions
    raise immediately without retry.
    """
    for attempt in range(max_attempts):
        try:
            return await fn(*args, **kwargs)
        except RateLimitError as e:
            if attempt == max_attempts - 1:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            log.warning("rate_limit_retry", attempt=attempt + 1, delay=delay)
            await asyncio.sleep(delay)
```

**Error classification:**
- `RateLimitError`: wraps HTTP 429 and 529 from any provider
- All other SDK exceptions propagate immediately: auth errors, validation errors, 500s, network errors

**Usage in adapters:**
```python
response = await retry_on_rate_limit(
    self._anthropic_generate,
    messages,
    run_id=run_id,
    workflow_id=workflow_id,
    component=component,
    max_attempts=self.max_retries,  # from tier config
)
```

**`max_retries` in tier config** (from `tiers.yaml`):
```yaml
sonnet:
  max_retries: 3  # default, overridable per tier
```

## Acceptance Criteria

- [ ] Retries exactly `max_attempts` times on 429, then raises
- [ ] Non-429 errors raise immediately on first attempt (no retry)
- [ ] Delay increases exponentially with jitter (verify delay is > base on second attempt)
- [ ] Warning logged on each retry with attempt number and delay
- [ ] Works correctly with `asyncio.gather` (concurrent retrying tasks don't interfere)

## Dependencies

- Task 15 (logging)
