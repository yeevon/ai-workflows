# Task 10 — Retry Taxonomy

**Issues:** P-36, P-40, P-41, CRIT-06, CRIT-08 (revises P-37)

## What to Build

Three-class error taxonomy, not a single retry flag. Preserves the explicit-utility style but covers the real cases seen in production.

## Error Classes

### Class 1 — Retryable Transient

Network-level and rate-limit errors. Backoff + jitter, max 3 attempts. Our single authority — SDK retries are disabled (CRIT-06).

- HTTP 429 (rate limit)
- HTTP 529 (overloaded)
- HTTP 500, 502, 503 (server transient)
- `APIConnectionError` (network)
- Anthropic `overloaded_error`

Handled by `retry_on_rate_limit()`.

### Class 2 — Retryable Semantic (ModelRetry)

Tool output validation failures. The LLM asked for something structured, we got text that doesn't fit. Pydantic AI's `ModelRetry` pattern: raise from a tool, pydantic-ai feeds the error message back to the model as a turn, model tries again. Bounded by max_turns.

- Pydantic validation error on tool output
- Structured output schema mismatch
- JSON parse failure on expected JSON output

Handled by raising `ModelRetry("explain what went wrong")` from inside the tool callable or output validator. pydantic-ai handles the turn-feed automatically.

### Class 3 — Non-Retryable

Fail immediately with clear error.

- HTTP 401, 403 (auth)
- HTTP 400 Anthropic `invalid_request_error` (prompt too long, unsupported feature)
- `ConfigurationError` (missing env var, unknown tier)
- `SecurityError`, `ExecutableNotAllowedError`, `BudgetExceeded`

These surface directly to the caller — no retry at any layer.

## Deliverables

### `primitives/retry.py`

```python
from anthropic import RateLimitError, APIStatusError, APIConnectionError
import random, asyncio

RETRYABLE_STATUS = {429, 529, 500, 502, 503}

def is_retryable_transient(exc: Exception) -> bool:
    if isinstance(exc, APIConnectionError):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code in RETRYABLE_STATUS
    if isinstance(exc, RateLimitError):
        return True
    return False


async def retry_on_rate_limit(
    fn: Callable[..., Awaitable[T]],
    *args,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    **kwargs,
) -> T:
    for attempt in range(max_attempts):
        try:
            return await fn(*args, **kwargs)
        except Exception as e:
            if not is_retryable_transient(e) or attempt == max_attempts - 1:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            log.warning(
                "retry_transient",
                attempt=attempt + 1,
                delay=delay,
                error_type=type(e).__name__,
            )
            await asyncio.sleep(delay)
```

### ModelRetry Usage Pattern

Inside a tool or output validator:

```python
from pydantic_ai import ModelRetry
from pydantic import ValidationError

@agent.output_validator
async def validate_plan(ctx: RunContext[WorkflowDeps], output: str) -> Plan:
    try:
        return Plan.model_validate_json(output)
    except ValidationError as e:
        raise ModelRetry(
            f"Your output did not match the Plan schema. "
            f"Validation errors: {e}. Produce valid JSON matching the schema."
        )
```

pydantic-ai catches `ModelRetry`, appends an error message as a turn, and re-invokes the model. Bounded by Agent's default `max_retries` setting (which we set to a low number, e.g. 3).

## Acceptance Criteria

- [ ] `is_retryable_transient()` returns True for 429, 529, 500, APIConnectionError
- [ ] `is_retryable_transient()` returns False for 400, 401, ConfigurationError
- [ ] `retry_on_rate_limit()` retries transient errors up to `max_attempts`
- [ ] Non-transient errors raise on first attempt (no retry delay)
- [ ] Jitter is present (two consecutive retry delays should not be identical)
- [ ] WARNING logged on each retry with attempt number and error type
- [ ] `ModelRetry` integration test: inject a ValidationError in an output validator, confirm model gets a second chance

## Dependencies

- Task 02 (types)
- Task 11 (logging)
