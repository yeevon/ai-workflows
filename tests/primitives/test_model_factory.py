"""Tests for M1 Task 03 — ai_workflows.primitives.llm.model_factory.

Covers all acceptance criteria:
1. build_model("sonnet", ...) → (AnthropicModel, caps) with supports_prompt_caching=True
2. build_model("local_coder", ...) → (OpenAIChatModel, caps) with Ollama base_url
3. Underlying SDK clients have max_retries=0
4. Integration test: cost recording fires after agent.run() (skipped without ANTHROPIC_API_KEY)
5. Missing env var raises ConfigurationError naming the variable
"""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_workflows.primitives.cost import CostTracker
from ai_workflows.primitives.llm.model_factory import ConfigurationError, build_model, run_with_cost
from ai_workflows.primitives.llm.types import TokenUsage, WorkflowDeps
from ai_workflows.primitives.tiers import TierConfig

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SONNET_TIER = TierConfig(
    provider="anthropic",
    model="claude-sonnet-4-6",
    max_tokens=8192,
    temperature=0.1,
)

LOCAL_CODER_TIER = TierConfig(
    provider="ollama",
    model="qwen2.5-coder:32b",
    base_url="http://192.168.1.100:11434/v1",
    max_tokens=8192,
    temperature=0.1,
)

GEMINI_TIER = TierConfig(
    provider="openai_compat",
    model="gemini-2.0-flash",
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    api_key_env="GEMINI_API_KEY",
    max_tokens=8192,
    temperature=0.1,
)

GOOGLE_TIER = TierConfig(
    provider="google",
    model="gemini-2.0-flash",
    api_key_env="GOOGLE_API_KEY",
    max_tokens=8192,
    temperature=0.1,
)


def _null_tracker() -> CostTracker:
    """Return a no-op cost tracker for unit tests that don't need cost recording."""
    tracker = MagicMock(spec=CostTracker)
    tracker.record = AsyncMock(return_value=0.0)
    return tracker


def _tiers(**overrides) -> dict[str, TierConfig]:
    base = {
        "sonnet": SONNET_TIER,
        "local_coder": LOCAL_CODER_TIER,
        "gemini": GEMINI_TIER,
        "google_native": GOOGLE_TIER,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# AC-1: build_model("sonnet") returns AnthropicModel + caching capability
# ---------------------------------------------------------------------------


def test_build_anthropic_model_returns_correct_type(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    from pydantic_ai.models.anthropic import AnthropicModel

    model, caps = build_model("sonnet", _tiers(), _null_tracker())

    assert isinstance(model, AnthropicModel)
    assert caps.supports_prompt_caching is True
    assert caps.provider == "anthropic"
    assert caps.model == "claude-sonnet-4-6"


def test_anthropic_capabilities_flags(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    _, caps = build_model("sonnet", _tiers(), _null_tracker())

    assert caps.supports_parallel_tool_calls is True
    assert caps.supports_structured_output is True
    assert caps.supports_thinking is True
    assert caps.supports_vision is True
    assert caps.max_context == 200_000


# ---------------------------------------------------------------------------
# AC-2: build_model("local_coder") returns OpenAIChatModel + Ollama base_url
# ---------------------------------------------------------------------------


def test_build_ollama_model_returns_correct_type():
    from pydantic_ai.models.openai import OpenAIChatModel

    model, caps = build_model("local_coder", _tiers(), _null_tracker())

    assert isinstance(model, OpenAIChatModel)
    assert caps.provider == "ollama"
    assert caps.model == "qwen2.5-coder:32b"


def test_build_ollama_base_url_from_config():
    model, _ = build_model("local_coder", _tiers(), _null_tracker())
    # The base_url is stored on the underlying OpenAI async client
    assert "192.168.1.100" in str(model.provider.client.base_url)


def test_ollama_capabilities_flags():
    _, caps = build_model("local_coder", _tiers(), _null_tracker())

    assert caps.supports_prompt_caching is False
    assert caps.supports_parallel_tool_calls is False
    assert caps.supports_structured_output is False
    assert caps.supports_thinking is False
    assert caps.supports_vision is False


# ---------------------------------------------------------------------------
# AC-3: Underlying SDK clients have max_retries=0
# ---------------------------------------------------------------------------


def test_anthropic_client_max_retries_is_zero(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    model, _ = build_model("sonnet", _tiers(), _null_tracker())
    assert model.provider.client.max_retries == 0


def test_ollama_client_max_retries_is_zero():
    model, _ = build_model("local_coder", _tiers(), _null_tracker())
    assert model.provider.client.max_retries == 0


def test_openai_compat_client_max_retries_is_zero(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gm-test")
    model, _ = build_model("gemini", _tiers(), _null_tracker())
    assert model.provider.client.max_retries == 0


# ---------------------------------------------------------------------------
# AC-5: Missing env var raises ConfigurationError naming the variable
# ---------------------------------------------------------------------------


def test_missing_anthropic_key_raises_configuration_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ConfigurationError) as exc_info:
        build_model("sonnet", _tiers(), _null_tracker())
    assert "ANTHROPIC_API_KEY" in str(exc_info.value)


def test_missing_custom_api_key_env_names_var(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ConfigurationError) as exc_info:
        build_model("gemini", _tiers(), _null_tracker())
    assert "GEMINI_API_KEY" in str(exc_info.value)


def test_unknown_tier_raises_configuration_error():
    with pytest.raises(ConfigurationError) as exc_info:
        build_model("does_not_exist", _tiers(), _null_tracker())
    assert "does_not_exist" in str(exc_info.value)


# ---------------------------------------------------------------------------
# run_with_cost: cost_tracker.record() is called with correct args
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_with_cost_calls_record():
    tracker = _null_tracker()
    deps = WorkflowDeps(
        run_id="run-1",
        workflow_id="wf-1",
        component="worker",
        tier="sonnet",
        project_root="/tmp",
    )

    from pydantic_ai.usage import RunUsage

    mock_result = MagicMock()
    mock_result.usage.return_value = RunUsage(input_tokens=10, output_tokens=5)

    mock_agent = MagicMock()
    mock_agent.run = AsyncMock(return_value=mock_result)
    mock_agent.model.model_name = "claude-sonnet-4-6"

    result = await run_with_cost(mock_agent, "hello", deps, tracker)

    assert result is mock_result
    tracker.record.assert_awaited_once()
    call_kwargs = tracker.record.call_args.kwargs
    assert call_kwargs["run_id"] == "run-1"
    assert call_kwargs["workflow_id"] == "wf-1"
    assert call_kwargs["component"] == "worker"
    assert call_kwargs["tier"] == "sonnet"
    assert call_kwargs["model"] == "claude-sonnet-4-6"
    assert isinstance(call_kwargs["usage"], TokenUsage)
    assert call_kwargs["usage"].input_tokens == 10
    assert call_kwargs["usage"].output_tokens == 5


# ---------------------------------------------------------------------------
# AC-4: Integration test — real Anthropic call records cost (skip if no key)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping live integration test",
)
async def test_integration_cost_recorded_after_real_agent_run():
    """Verify cost_tracker.record() fires with non-zero token counts on a real call."""
    from pydantic_ai import Agent

    tiers = {"sonnet": SONNET_TIER}
    tracker = _null_tracker()

    model, _ = build_model("sonnet", tiers, tracker)
    agent = Agent(model, output_type=str)
    deps = WorkflowDeps(
        run_id="int-run-1",
        workflow_id="int-wf-1",
        component="test",
        tier="sonnet",
        project_root="/tmp",
    )

    result = await run_with_cost(agent, "Say 'ok' and nothing else.", deps, tracker)

    assert result is not None
    tracker.record.assert_awaited_once()
    call_kwargs = tracker.record.call_args.kwargs
    assert call_kwargs["usage"].input_tokens > 0
    assert call_kwargs["usage"].output_tokens > 0
