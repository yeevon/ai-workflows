"""Retry taxonomy — the single retry authority for the whole framework.

Produced by M1 Task 10 (P-36, P-40, P-41, CRIT-06, CRIT-08; revises P-37).

Three error classes, three different strategies
-----------------------------------------------
* **Retryable Transient** — network and rate-limit errors. Exponential
  backoff + jitter, bounded by ``max_attempts``. This module owns that
  retry loop. SDK clients are always constructed with ``max_retries=0``
  (CRIT-06) so :func:`retry_on_rate_limit` is the *only* place a request
  gets retried.
* **Retryable Semantic** — the LLM returned text that does not match the
  expected structured output. Handled by raising
  :class:`pydantic_ai.ModelRetry` from inside a tool callable or an
  ``@agent.output_validator`` hook; pydantic-ai feeds the error back as
  a new turn and lets the model try again. Bounded by the Agent's
  ``max_retries`` setting (kept low — typically 3). This module does not
  implement semantic retry; it only documents and tests the integration
  pattern.
* **Non-Retryable** — auth, bad request, configuration, security, and
  budget errors surface directly to the caller with no retry at any
  layer. :func:`is_retryable_transient` returns ``False`` for these.

Classification keys off HTTP status code and a small whitelist of SDK
exception types. We treat both the ``anthropic`` and ``openai`` SDK
variants as retryable because the project's default tiers drive Gemini
through the OpenAI-compatible endpoint (see memory:
``project_provider_strategy``). Without the openai branch the retry
layer would silently no-op on the primary runtime path.

See also
--------
* ``primitives/llm/model_factory.py`` — every SDK client is built with
  ``max_retries=0`` so this module stays the sole retry authority.
* ``primitives/tiers.py`` — ``TierConfig.max_retries`` holds the per-tier
  budget for our retry layer; callers pass it in as ``max_attempts``.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable

import structlog
from anthropic import (
    APIConnectionError as AnthropicAPIConnectionError,
)
from anthropic import (
    APIStatusError as AnthropicAPIStatusError,
)
from anthropic import (
    RateLimitError as AnthropicRateLimitError,
)
from openai import (
    APIConnectionError as OpenAIAPIConnectionError,
)
from openai import (
    APIStatusError as OpenAIAPIStatusError,
)
from openai import (
    RateLimitError as OpenAIRateLimitError,
)

logger = structlog.get_logger(__name__)

RETRYABLE_STATUS: frozenset[int] = frozenset({429, 529, 500, 502, 503})
"""HTTP status codes we treat as retryable transient failures.

429 — rate limit; 529 — Anthropic ``overloaded_error``; 500/502/503 —
server-side transient. 504 is intentionally excluded: it signals an
upstream deadline miss, and retrying blindly tends to make an already
overloaded backend worse. Clients that need 504 handling should bubble
it as a timeout.
"""

_RETRYABLE_RATE_LIMIT_TYPES: tuple[type[Exception], ...] = (
    AnthropicRateLimitError,
    OpenAIRateLimitError,
)
_RETRYABLE_CONNECTION_TYPES: tuple[type[Exception], ...] = (
    AnthropicAPIConnectionError,
    OpenAIAPIConnectionError,
)
_RETRYABLE_STATUS_TYPES: tuple[type[Exception], ...] = (
    AnthropicAPIStatusError,
    OpenAIAPIStatusError,
)


def is_retryable_transient(exc: Exception) -> bool:
    """Return ``True`` if ``exc`` is a network-level or rate-limit failure.

    The classification is intentionally narrow. Anything that is not a
    known-transient SDK exception (or an ``APIStatusError`` whose HTTP
    status is in :data:`RETRYABLE_STATUS`) falls through to ``False`` and
    surfaces to the caller on the first attempt — auth, validation,
    configuration, security, and budget errors must never trigger a
    retry.

    The check runs ``isinstance`` against both ``anthropic`` and
    ``openai`` SDK exception classes so the retry layer behaves
    uniformly across every provider wired by the Task 03 model factory.
    """
    if isinstance(exc, _RETRYABLE_CONNECTION_TYPES):
        return True
    if isinstance(exc, _RETRYABLE_RATE_LIMIT_TYPES):
        return True
    if isinstance(exc, _RETRYABLE_STATUS_TYPES):
        return exc.status_code in RETRYABLE_STATUS
    return False


async def retry_on_rate_limit[T](
    fn: Callable[..., Awaitable[T]],
    *args: object,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    **kwargs: object,
) -> T:
    """Run ``fn`` with exponential backoff + jitter on transient failures.

    Parameters
    ----------
    fn:
        An async callable. Usually ``agent.run`` or a thin wrapper around
        it, but anything awaitable works.
    max_attempts:
        Total number of attempts (not retries). ``max_attempts=3`` means
        one initial call plus up to two retries. Callers that want the
        per-tier budget pass ``tier_config.max_retries`` here.
    base_delay:
        Seconds used as the base of the backoff curve. Delay for attempt
        ``n`` (0-indexed) is ``base_delay * 2**n + uniform(0, 1)``; the
        uniform term is the jitter.

    Notes
    -----
    * Non-transient errors re-raise on the first attempt — no sleep, no
      log noise, no swallowed stack trace.
    * The last attempt re-raises rather than sleeping. Sleeping after
      the final try would delay the failure without changing the
      outcome.
    * Every retry emits a structured ``retry.transient`` WARNING with
      the attempt number, the sleep duration, and the exception type
      name. The log line is how M1 Task 11 (logging) + M3 (OTel) users
      see retry behaviour in the run timeline.
    """
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be >= 1, got {max_attempts!r}")

    for attempt in range(max_attempts):
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:
            is_last = attempt == max_attempts - 1
            if not is_retryable_transient(exc) or is_last:
                raise
            delay = base_delay * (2**attempt) + random.uniform(0, 1)
            logger.warning(
                "retry.transient",
                attempt=attempt + 1,
                max_attempts=max_attempts,
                delay=delay,
                error_type=type(exc).__name__,
            )
            await asyncio.sleep(delay)

    # Unreachable: the loop either returns, raises a non-transient error,
    # or raises the last transient error on the final attempt.
    raise RuntimeError("retry_on_rate_limit exited the loop without returning or raising")
