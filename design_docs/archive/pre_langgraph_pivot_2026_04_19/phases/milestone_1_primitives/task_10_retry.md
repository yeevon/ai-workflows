# Task 10 — Retry Taxonomy

**Status:** ✅ Complete (2026-04-19)

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

- [x] `is_retryable_transient()` returns True for 429, 529, 500, APIConnectionError
  — pinned by `tests/primitives/test_retry.py::test_is_retryable_transient_true_for_retryable_status_anthropic`,
  `::test_is_retryable_transient_true_for_retryable_status_openai`,
  `::test_is_retryable_transient_true_for_rate_limit_errors`,
  `::test_is_retryable_transient_true_for_connection_errors`.
- [x] `is_retryable_transient()` returns False for 400, 401, ConfigurationError
  — pinned by `::test_is_retryable_transient_false_for_non_retryable_status`
  (400, 401, 403, 404, 422, 504), `::test_is_retryable_transient_false_for_configuration_error`,
  `::test_is_retryable_transient_false_for_arbitrary_exceptions`.
- [x] `retry_on_rate_limit()` retries transient errors up to `max_attempts`
  — `::test_retry_on_rate_limit_retries_transient_until_success`,
  `::test_retry_on_rate_limit_exhausts_and_raises_transient`,
  `::test_retry_on_rate_limit_uses_tier_max_retries` (feeds
  `TierConfig.max_retries` through as `max_attempts`).
- [x] Non-transient errors raise on first attempt (no retry delay)
  — `::test_retry_on_rate_limit_raises_non_transient_immediately`,
  `::test_retry_on_rate_limit_raises_http_400_immediately`
  (both patch `asyncio.sleep` and assert zero sleep calls).
- [x] Jitter is present (two consecutive retry delays should not be identical)
  — `::test_retry_on_rate_limit_emits_jittered_delays` asserts
  `len(set(sleeps)) > 1` with `base_delay=0.0`, and
  `::test_retry_on_rate_limit_delays_include_exponential_component`
  pins the exponential component by stubbing `random.uniform`.
- [x] WARNING logged on each retry with attempt number and error type
  — `::test_retry_on_rate_limit_logs_warning_per_retry` asserts event
  name `retry.transient`, log level `warning`, and fields `attempt` /
  `max_attempts` / `delay` / `error_type`. Negative coverage:
  `::test_retry_on_rate_limit_does_not_log_on_first_success`,
  `::test_retry_on_rate_limit_does_not_log_on_non_transient`.
- [x] `ModelRetry` integration test: inject a ValidationError in an output validator, confirm model gets a second chance
  — `::test_model_retry_feeds_error_back_and_model_retries` uses
  `pydantic_ai.models.function.FunctionModel`: call 1 returns malformed
  JSON, the `@agent.output_validator` raises `ModelRetry` from the
  `ValidationError`, and call 2 receives a `RetryPromptPart` in its
  message history before returning valid JSON that the validator
  accepts.

## Dependencies

- Task 02 (types)
- Task 11 (logging)
