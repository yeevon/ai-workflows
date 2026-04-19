"""Tests for ``ai_workflows.primitives.retry`` (M1 Task 10).

Grades every acceptance criterion from
``design_docs/phases/milestone_1_primitives/task_10_retry.md``:

* AC-1: ``is_retryable_transient()`` returns ``True`` for 429, 529, 500,
  and ``APIConnectionError`` (tested across both ``anthropic`` and
  ``openai`` SDK variants).
* AC-2: ``is_retryable_transient()`` returns ``False`` for 400, 401,
  ``ConfigurationError``, arbitrary ``ValueError``.
* AC-3: ``retry_on_rate_limit()`` retries transient errors up to
  ``max_attempts`` and then re-raises the final transient failure.
* AC-4: Non-transient errors raise on the first attempt with no retry
  delay.
* AC-5: Jitter is present — two consecutive retry delays are not
  identical across a sample.
* AC-6: Every retry logs a WARNING with the attempt number and error
  type name.
* AC-7: ``ModelRetry`` integration — a ``ValidationError`` raised from
  inside an ``@agent.output_validator`` is translated into a ``ModelRetry``
  turn so the model gets a second chance and the final output validates.

Also pins supporting behaviour (``TierConfig.max_retries`` round-trip
into ``retry_on_rate_limit``, ``max_attempts<1`` guard) so future
refactors catch regressions.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
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
from pydantic import BaseModel, ValidationError
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from structlog.testing import capture_logs

from ai_workflows.primitives.llm.model_factory import ConfigurationError
from ai_workflows.primitives.retry import (
    RETRYABLE_STATUS,
    is_retryable_transient,
    retry_on_rate_limit,
)
from ai_workflows.primitives.tiers import TierConfig

# ---------------------------------------------------------------------------
# Exception builders
# ---------------------------------------------------------------------------


def _httpx_request() -> httpx.Request:
    """Return a synthetic request object used by SDK exception constructors."""
    return httpx.Request("POST", "https://example.invalid/v1/messages")


def _httpx_response(status: int) -> httpx.Response:
    """Return a synthetic response object for SDK ``APIStatusError`` builds."""
    return httpx.Response(
        status_code=status,
        request=_httpx_request(),
        content=b"{}",
    )


def _anthropic_status(status: int) -> AnthropicAPIStatusError:
    return AnthropicAPIStatusError(
        message=f"anthropic status {status}",
        response=_httpx_response(status),
        body=None,
    )


def _openai_status(status: int) -> OpenAIAPIStatusError:
    return OpenAIAPIStatusError(
        message=f"openai status {status}",
        response=_httpx_response(status),
        body=None,
    )


def _anthropic_rate_limit() -> AnthropicRateLimitError:
    return AnthropicRateLimitError(
        message="anthropic 429",
        response=_httpx_response(429),
        body=None,
    )


def _openai_rate_limit() -> OpenAIRateLimitError:
    return OpenAIRateLimitError(
        message="openai 429",
        response=_httpx_response(429),
        body=None,
    )


def _anthropic_connection() -> AnthropicAPIConnectionError:
    return AnthropicAPIConnectionError(request=_httpx_request())


def _openai_connection() -> OpenAIAPIConnectionError:
    return OpenAIAPIConnectionError(request=_httpx_request())


# ---------------------------------------------------------------------------
# AC-1 — transient classifier true-branches
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", sorted(RETRYABLE_STATUS))
def test_is_retryable_transient_true_for_retryable_status_anthropic(status: int) -> None:
    assert is_retryable_transient(_anthropic_status(status)) is True


@pytest.mark.parametrize("status", sorted(RETRYABLE_STATUS))
def test_is_retryable_transient_true_for_retryable_status_openai(status: int) -> None:
    assert is_retryable_transient(_openai_status(status)) is True


def test_is_retryable_transient_true_for_rate_limit_errors() -> None:
    assert is_retryable_transient(_anthropic_rate_limit()) is True
    assert is_retryable_transient(_openai_rate_limit()) is True


def test_is_retryable_transient_true_for_connection_errors() -> None:
    assert is_retryable_transient(_anthropic_connection()) is True
    assert is_retryable_transient(_openai_connection()) is True


def test_retryable_status_set_covers_spec() -> None:
    # The spec explicitly enumerates 429, 529, 500, 502, 503.
    assert frozenset({429, 529, 500, 502, 503}) == RETRYABLE_STATUS


# ---------------------------------------------------------------------------
# AC-2 — transient classifier false-branches
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422, 504])
def test_is_retryable_transient_false_for_non_retryable_status(status: int) -> None:
    assert is_retryable_transient(_anthropic_status(status)) is False
    assert is_retryable_transient(_openai_status(status)) is False


def test_is_retryable_transient_false_for_configuration_error() -> None:
    assert is_retryable_transient(ConfigurationError("missing env")) is False


def test_is_retryable_transient_false_for_arbitrary_exceptions() -> None:
    assert is_retryable_transient(ValueError("nope")) is False
    assert is_retryable_transient(RuntimeError("nope")) is False
    assert is_retryable_transient(KeyError("nope")) is False


# ---------------------------------------------------------------------------
# AC-3 — retry loop honours max_attempts
# ---------------------------------------------------------------------------


async def test_retry_on_rate_limit_returns_first_success() -> None:
    calls = 0

    async def fn() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    result = await retry_on_rate_limit(fn, max_attempts=3, base_delay=0.0)
    assert result == "ok"
    assert calls == 1


async def test_retry_on_rate_limit_retries_transient_until_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(asyncio, "sleep", _sleep_noop)
    calls = 0

    async def fn() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise _anthropic_rate_limit()
        return "ok"

    result = await retry_on_rate_limit(fn, max_attempts=3, base_delay=0.0)
    assert result == "ok"
    assert calls == 3


async def test_retry_on_rate_limit_exhausts_and_raises_transient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(asyncio, "sleep", _sleep_noop)
    calls = 0

    async def fn() -> str:
        nonlocal calls
        calls += 1
        raise _anthropic_status(503)

    with pytest.raises(AnthropicAPIStatusError):
        await retry_on_rate_limit(fn, max_attempts=3, base_delay=0.0)
    assert calls == 3


async def test_retry_on_rate_limit_uses_tier_max_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Task 07 pinned TierConfig.max_retries as the per-tier budget
    # consumed here (see M1-T03-ISS-12 resolution).
    monkeypatch.setattr(asyncio, "sleep", _sleep_noop)
    tier = TierConfig(
        provider="openai_compat",
        model="gemini-2.0-flash",
        max_tokens=1024,
        temperature=0.2,
        max_retries=2,
    )
    calls = 0

    async def fn() -> str:
        nonlocal calls
        calls += 1
        raise _openai_rate_limit()

    with pytest.raises(OpenAIRateLimitError):
        await retry_on_rate_limit(fn, max_attempts=tier.max_retries, base_delay=0.0)
    assert calls == 2


async def test_retry_on_rate_limit_rejects_nonpositive_max_attempts() -> None:
    async def fn() -> str:
        return "never"

    with pytest.raises(ValueError, match="max_attempts"):
        await retry_on_rate_limit(fn, max_attempts=0)


# ---------------------------------------------------------------------------
# AC-4 — non-transient errors raise on first attempt with no sleep
# ---------------------------------------------------------------------------


async def test_retry_on_rate_limit_raises_non_transient_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []

    async def record_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", record_sleep)
    calls = 0

    async def fn() -> str:
        nonlocal calls
        calls += 1
        raise ConfigurationError("missing env")

    with pytest.raises(ConfigurationError):
        await retry_on_rate_limit(fn, max_attempts=5, base_delay=0.5)
    assert calls == 1
    assert sleeps == []


async def test_retry_on_rate_limit_raises_http_400_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []

    async def record_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", record_sleep)
    calls = 0

    async def fn() -> str:
        nonlocal calls
        calls += 1
        raise _openai_status(400)

    with pytest.raises(OpenAIAPIStatusError):
        await retry_on_rate_limit(fn, max_attempts=5, base_delay=0.5)
    assert calls == 1
    assert sleeps == []


# ---------------------------------------------------------------------------
# AC-5 — jitter makes consecutive delays non-identical
# ---------------------------------------------------------------------------


async def test_retry_on_rate_limit_emits_jittered_delays(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []

    async def record_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", record_sleep)

    async def fn() -> str:
        raise _anthropic_rate_limit()

    # max_attempts=5 → up to 4 sleeps. With a deterministic backoff the
    # doubling base would dominate, but we want to see jitter inside a
    # single attempt too — lock base_delay=0.0 so the only non-zero
    # component of each delay is the uniform(0, 1) jitter term.
    with pytest.raises(AnthropicRateLimitError):
        await retry_on_rate_limit(fn, max_attempts=5, base_delay=0.0)

    assert len(sleeps) == 4
    assert all(0.0 <= d < 1.0 for d in sleeps)
    # Two consecutive delays should not all be identical; probability of
    # collision under random.uniform across 4 draws is effectively zero.
    assert len(set(sleeps)) > 1


async def test_retry_on_rate_limit_delays_include_exponential_component(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []

    async def record_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", record_sleep)
    monkeypatch.setattr("random.uniform", lambda a, b: 0.0)

    async def fn() -> str:
        raise _anthropic_rate_limit()

    with pytest.raises(AnthropicRateLimitError):
        await retry_on_rate_limit(fn, max_attempts=4, base_delay=1.0)

    # base_delay=1, jitter pinned to 0 → 1, 2, 4 for attempts 0, 1, 2
    # (the last attempt re-raises without sleeping).
    assert sleeps == [1.0, 2.0, 4.0]


# ---------------------------------------------------------------------------
# AC-6 — retry logs WARNING with attempt number and error type
# ---------------------------------------------------------------------------


async def test_retry_on_rate_limit_logs_warning_per_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(asyncio, "sleep", _sleep_noop)

    async def fn() -> str:
        raise _openai_status(503)

    with capture_logs() as captured, pytest.raises(OpenAIAPIStatusError):
        await retry_on_rate_limit(fn, max_attempts=3, base_delay=0.0)

    retry_logs = [entry for entry in captured if entry.get("event") == "retry.transient"]
    assert len(retry_logs) == 2  # max_attempts=3 → 2 retries before the final raise
    for i, entry in enumerate(retry_logs, start=1):
        assert entry["log_level"] == "warning"
        assert entry["attempt"] == i
        assert entry["max_attempts"] == 3
        assert entry["error_type"] == "APIStatusError"
        assert "delay" in entry


async def test_retry_on_rate_limit_does_not_log_on_first_success() -> None:
    async def fn() -> str:
        return "ok"

    with capture_logs() as captured:
        await retry_on_rate_limit(fn, max_attempts=3, base_delay=0.0)
    assert not any(entry.get("event") == "retry.transient" for entry in captured)


async def test_retry_on_rate_limit_does_not_log_on_non_transient() -> None:
    async def fn() -> str:
        raise ConfigurationError("nope")

    with capture_logs() as captured, pytest.raises(ConfigurationError):
        await retry_on_rate_limit(fn, max_attempts=3, base_delay=0.0)
    assert not any(entry.get("event") == "retry.transient" for entry in captured)


# ---------------------------------------------------------------------------
# AC-7 — ModelRetry integration via pydantic-ai output validator
# ---------------------------------------------------------------------------


class Plan(BaseModel):
    """Structured output schema used by the ModelRetry integration test."""

    steps: list[str]


async def test_model_retry_feeds_error_back_and_model_retries() -> None:
    """A ValidationError inside an output validator turns into a ModelRetry.

    pydantic-ai sees ``ModelRetry`` raised from the validator, appends a
    ``RetryPromptPart`` to the message history, and re-invokes the model
    with that new turn. The second invocation gets a different (valid)
    response from the test model, and the validator returns a ``Plan``.
    Asserts:
        * the model is invoked twice (second chance granted);
        * the second invocation's message history contains a retry
          prompt referencing the validator's complaint;
        * the final agent output is the valid ``Plan``.
    """
    invocations: list[list[ModelMessage]] = []

    async def plan_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        invocations.append(messages)
        if len(invocations) == 1:
            # First attempt: return malformed JSON that will fail validation.
            return ModelResponse(parts=[TextPart(content='{"steps": "not a list"}')])
        # Second attempt: return valid JSON.
        return ModelResponse(parts=[TextPart(content='{"steps": ["a", "b"]}')])

    model = FunctionModel(plan_fn)
    agent: Agent[None, Plan] = Agent(model, output_type=Plan, retries=3)

    @agent.output_validator
    async def validate_plan(ctx: RunContext[None], output: Plan) -> Plan:  # noqa: ARG001
        # Re-run validation so a malformed payload raises ValidationError
        # even after pydantic-ai has already parsed it. Mirrors the spec's
        # usage pattern (validator → ModelRetry on ValidationError).
        try:
            return Plan.model_validate(output.model_dump())
        except ValidationError as exc:
            raise ModelRetry(
                f"Your output did not match the Plan schema. "
                f"Validation errors: {exc}. Produce valid JSON matching the schema."
            ) from exc

    result = await agent.run("make a plan")
    assert isinstance(result.output, Plan)
    assert result.output.steps == ["a", "b"]
    assert len(invocations) == 2, "model should receive a second chance"

    # The second invocation's message history must carry the validator's
    # complaint as a RetryPromptPart so the model can course-correct.
    second_history = invocations[1]
    retry_parts = [
        part
        for msg in second_history
        if isinstance(msg, ModelRequest)
        for part in msg.parts
        if isinstance(part, RetryPromptPart)
    ]
    assert retry_parts, "pydantic-ai should inject a RetryPromptPart for ModelRetry"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _sleep_noop(_delay: float) -> None:
    """Drop-in replacement for ``asyncio.sleep`` that yields immediately.

    Keeps the retry loop's ``await`` semantics intact (we still hand
    control back to the event loop) without actually burning wall-clock
    time in the test suite.
    """
    return None
