"""Tests for M2 Task 01 — ``ai_workflows.primitives.llm.litellm_adapter``.

Covers every acceptance criterion from
[task_01_litellm_adapter.md](../../../design_docs/phases/milestone_2_graph/task_01_litellm_adapter.md):

* AC-1 — ``LiteLLMAdapter.complete()`` returns ``(str, TokenUsage)``
  matching the primitive's schema (happy path).
* AC-2 — ``TokenUsage.cost_usd`` is populated from LiteLLM's
  enrichment when present; the hidden-params fall-back channel also
  flows through.
* AC-3 — ``max_retries=0`` is forwarded to the LiteLLM call site.
* AC-4 — no classification / retry logic inside the adapter;
  ``litellm.RateLimitError`` raised by the underlying call surfaces
  to the caller verbatim.
* AC-5 — this file must pass ``uv run pytest`` (verified in the
  milestone gate).

The task spec pins the stubbing approach: every test swaps
``litellm.acompletion`` out for an ``AsyncMock`` / fake coroutine so
no live provider call is made.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import litellm
import pytest
from pydantic import BaseModel

from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.llm.litellm_adapter import LiteLLMAdapter
from ai_workflows.primitives.tiers import LiteLLMRoute


def _make_response(
    *,
    content: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float | None = None,
    hidden_cost: float | None = None,
) -> SimpleNamespace:
    """Build a minimal LiteLLM-shaped response for the adapter to parse."""
    usage_kwargs: dict[str, Any] = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }
    if cost_usd is not None:
        usage_kwargs["cost_usd"] = cost_usd
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    hidden: dict[str, Any] = {}
    if hidden_cost is not None:
        hidden["response_cost"] = hidden_cost
    return SimpleNamespace(
        choices=[choice],
        usage=SimpleNamespace(**usage_kwargs),
        _hidden_params=hidden,
    )


# ---------------------------------------------------------------------------
# AC-1 — happy path returns (str, TokenUsage)
# ---------------------------------------------------------------------------


async def test_complete_returns_text_and_token_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-1: happy path returns ``(str, TokenUsage)`` with all mapped fields."""
    response = _make_response(
        content="hello world",
        prompt_tokens=12,
        completion_tokens=34,
        cost_usd=0.00042,
    )
    stub = AsyncMock(return_value=response)
    monkeypatch.setattr(litellm, "acompletion", stub)

    adapter = LiteLLMAdapter(
        route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
        per_call_timeout_s=30,
    )

    text, usage = await adapter.complete(
        system="be terse",
        messages=[{"role": "user", "content": "hi"}],
    )

    assert text == "hello world"
    assert isinstance(usage, TokenUsage)
    assert usage.input_tokens == 12
    assert usage.output_tokens == 34
    assert usage.cost_usd == pytest.approx(0.00042)
    assert usage.model == "gemini/gemini-2.5-flash"


async def test_complete_prepends_system_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """System prompt is prepended as a ``{"role": "system"}`` entry when supplied."""
    stub = AsyncMock(
        return_value=_make_response(content="ok", prompt_tokens=1, completion_tokens=1)
    )
    monkeypatch.setattr(litellm, "acompletion", stub)

    adapter = LiteLLMAdapter(
        route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
        per_call_timeout_s=30,
    )
    await adapter.complete(
        system="you are helpful",
        messages=[{"role": "user", "content": "hi"}],
    )

    kwargs = stub.await_args.kwargs
    assert kwargs["messages"][0] == {"role": "system", "content": "you are helpful"}
    assert kwargs["messages"][1] == {"role": "user", "content": "hi"}


async def test_complete_without_system_sends_messages_verbatim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``system=None`` means no synthetic system entry is injected."""
    stub = AsyncMock(
        return_value=_make_response(content="ok", prompt_tokens=1, completion_tokens=1)
    )
    monkeypatch.setattr(litellm, "acompletion", stub)

    adapter = LiteLLMAdapter(
        route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
        per_call_timeout_s=30,
    )
    await adapter.complete(
        system=None,
        messages=[{"role": "user", "content": "hi"}],
    )

    assert stub.await_args.kwargs["messages"] == [{"role": "user", "content": "hi"}]


async def test_complete_forwards_api_base_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ollama routes carry an ``api_base`` and it must reach ``litellm.acompletion``."""
    stub = AsyncMock(
        return_value=_make_response(content="ok", prompt_tokens=1, completion_tokens=1)
    )
    monkeypatch.setattr(litellm, "acompletion", stub)

    adapter = LiteLLMAdapter(
        route=LiteLLMRoute(model="ollama/qwen2.5-coder:32b", api_base="http://localhost:11434"),
        per_call_timeout_s=30,
    )
    await adapter.complete(system=None, messages=[{"role": "user", "content": "hi"}])

    assert stub.await_args.kwargs["api_base"] == "http://localhost:11434"


async def test_complete_forwards_response_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """``response_format`` is forwarded verbatim for LiteLLM's native pydantic support."""

    class Answer(BaseModel):
        value: str

    stub = AsyncMock(
        return_value=_make_response(content='{"value": "ok"}', prompt_tokens=1, completion_tokens=1)
    )
    monkeypatch.setattr(litellm, "acompletion", stub)

    adapter = LiteLLMAdapter(
        route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
        per_call_timeout_s=30,
    )
    await adapter.complete(
        system=None,
        messages=[{"role": "user", "content": "hi"}],
        response_format=Answer,
    )

    assert stub.await_args.kwargs["response_format"] is Answer


async def test_complete_forwards_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """``per_call_timeout_s`` is passed as LiteLLM's ``timeout`` kwarg."""
    stub = AsyncMock(
        return_value=_make_response(content="ok", prompt_tokens=1, completion_tokens=1)
    )
    monkeypatch.setattr(litellm, "acompletion", stub)

    adapter = LiteLLMAdapter(
        route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
        per_call_timeout_s=17,
    )
    await adapter.complete(system=None, messages=[{"role": "user", "content": "hi"}])

    assert stub.await_args.kwargs["timeout"] == 17


# ---------------------------------------------------------------------------
# AC-2 — cost_usd population
# ---------------------------------------------------------------------------


async def test_cost_usd_populated_from_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-2: when LiteLLM attaches ``cost_usd`` to ``usage``, it flows through."""
    response = _make_response(
        content="hi", prompt_tokens=5, completion_tokens=7, cost_usd=0.0001
    )
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=response))

    adapter = LiteLLMAdapter(
        route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
        per_call_timeout_s=30,
    )
    _, usage = await adapter.complete(system=None, messages=[])
    assert usage.cost_usd == pytest.approx(0.0001)


async def test_cost_usd_falls_back_to_hidden_params(monkeypatch: pytest.MonkeyPatch) -> None:
    """LiteLLM sometimes exposes cost only via ``response._hidden_params``.

    The adapter falls back to ``_hidden_params['response_cost']`` when
    ``usage.cost_usd`` is missing / zero — otherwise Ollama-routed
    calls (which LiteLLM zero-prices on ``usage``) would lose their
    cost signal entirely.
    """
    response = _make_response(
        content="hi", prompt_tokens=5, completion_tokens=7, hidden_cost=0.0002
    )
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=response))

    adapter = LiteLLMAdapter(
        route=LiteLLMRoute(model="ollama/qwen2.5-coder:32b"),
        per_call_timeout_s=30,
    )
    _, usage = await adapter.complete(system=None, messages=[])
    assert usage.cost_usd == pytest.approx(0.0002)


async def test_cost_usd_defaults_to_zero_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Providers that report no cost at all must still yield a valid ``TokenUsage``."""
    response = _make_response(content="hi", prompt_tokens=5, completion_tokens=7)
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=response))

    adapter = LiteLLMAdapter(
        route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
        per_call_timeout_s=30,
    )
    _, usage = await adapter.complete(system=None, messages=[])
    assert usage.cost_usd == 0.0


# ---------------------------------------------------------------------------
# AC-3 — max_retries=0 at the LiteLLM call site
# ---------------------------------------------------------------------------


async def test_max_retries_is_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-3: the adapter must disable LiteLLM's internal retry loop."""
    stub = AsyncMock(
        return_value=_make_response(content="ok", prompt_tokens=1, completion_tokens=1)
    )
    monkeypatch.setattr(litellm, "acompletion", stub)

    adapter = LiteLLMAdapter(
        route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
        per_call_timeout_s=30,
    )
    await adapter.complete(system=None, messages=[{"role": "user", "content": "hi"}])

    assert stub.await_args.kwargs["max_retries"] == 0


# ---------------------------------------------------------------------------
# AC-4 — exception pass-through (no classification / retry inside adapter)
# ---------------------------------------------------------------------------


async def test_rate_limit_error_passes_through(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-4: LiteLLM exceptions surface verbatim; the adapter never catches."""

    async def _raise(**_kwargs: Any) -> Any:
        raise litellm.RateLimitError("429", llm_provider="gemini", model="gemini/gemini-2.5-flash")

    monkeypatch.setattr(litellm, "acompletion", _raise)

    adapter = LiteLLMAdapter(
        route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
        per_call_timeout_s=30,
    )
    with pytest.raises(litellm.RateLimitError):
        await adapter.complete(system=None, messages=[{"role": "user", "content": "hi"}])


async def test_bad_request_error_passes_through(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-retryable LiteLLM errors also pass through unchanged (no swallow, no wrap)."""

    async def _raise(**_kwargs: Any) -> Any:
        raise litellm.BadRequestError(
            "bad", model="gemini/gemini-2.5-flash", llm_provider="gemini"
        )

    monkeypatch.setattr(litellm, "acompletion", _raise)

    adapter = LiteLLMAdapter(
        route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
        per_call_timeout_s=30,
    )
    with pytest.raises(litellm.BadRequestError):
        await adapter.complete(system=None, messages=[{"role": "user", "content": "hi"}])
