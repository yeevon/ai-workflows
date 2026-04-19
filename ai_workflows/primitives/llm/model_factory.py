"""Model factory for the LLM primitives layer.

Produced by M1 Task 03. ``build_model()`` maps a tier name to a fully
configured pydantic-ai Model instance, enforcing ``max_retries=0`` on the
underlying SDK client so that our own ``retry_on_rate_limit()`` (Task 10) is
the sole retry authority.

``run_with_cost()`` wraps ``Agent.run()`` and records token usage to the cost
tracker after each call. Tasks 04 (prompt caching) and later workflow layers
build on top of these two entry points.

Provider → pydantic-ai Model mapping
--------------------------------------
* ``anthropic``     → ``AnthropicModel`` via ``AnthropicProvider``
* ``openai_compat`` → ``OpenAIChatModel`` via ``OpenAIProvider`` (DeepSeek,
                       OpenRouter, Gemini via compat endpoint)
* ``ollama``        → ``OpenAIChatModel`` via ``OpenAIProvider`` (Ollama
                       exposes an OpenAI-compatible API)
* ``google``        → ``GoogleModel`` via ``GoogleProvider`` (native SDK)
"""

import os
from typing import TYPE_CHECKING, Any

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import RunUsage

from ai_workflows.primitives.cost import CostTracker
from ai_workflows.primitives.llm.types import ClientCapabilities, TokenUsage, WorkflowDeps
from ai_workflows.primitives.tiers import TierConfig

if TYPE_CHECKING:
    from pydantic_ai import Agent, AgentRunResult


class ConfigurationError(Exception):
    """Raised when a required configuration value is missing or invalid."""


def build_model(
    tier_name: str,
    tiers: dict[str, TierConfig],
    cost_tracker: CostTracker,
) -> tuple[AnthropicModel | OpenAIChatModel | GoogleModel, ClientCapabilities]:
    """Return a configured pydantic-ai Model and its capability descriptor.

    Enforces ``max_retries=0`` on the underlying SDK client. Raises
    ``ConfigurationError`` if the tier is unknown or a required env var is
    absent. The ``cost_tracker`` parameter is accepted now for API stability;
    active wiring happens in ``run_with_cost()``.
    """
    # cost_tracker is reserved: pydantic-ai 1.x exposes no usage-callback hook,
    # so active cost recording happens in run_with_cost(). Accepting the param
    # here keeps the factory signature stable for when a hook lands upstream.
    _ = cost_tracker

    if tier_name not in tiers:
        raise ConfigurationError(f"Unknown tier: {tier_name!r}")

    config = tiers[tier_name]

    if config.provider == "anthropic":
        return _build_anthropic(config)
    if config.provider == "ollama":
        return _build_ollama(config)
    if config.provider == "openai_compat":
        return _build_openai_compat(config)
    if config.provider == "google":
        return _build_google(config)

    raise ConfigurationError(f"Unsupported provider: {config.provider!r}")


async def run_with_cost(
    agent: "Agent",
    prompt: str,
    deps: WorkflowDeps,
    cost_tracker: CostTracker,
) -> "AgentRunResult[Any]":
    """Run an agent and record the resulting LLM cost.

    Calls ``agent.run()``, converts the returned ``Usage`` to our
    ``TokenUsage``, and forwards it to ``cost_tracker.record()``. Returns the
    ``AgentRunResult`` unchanged so callers can still read ``.output``.
    """
    result = await agent.run(prompt, deps=deps)
    await cost_tracker.record(
        run_id=deps.run_id,
        workflow_id=deps.workflow_id,
        component=deps.component,
        tier=deps.tier,
        model=str(agent.model.model_name),
        usage=_convert_usage(result.usage()),
    )
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require_env(var: str) -> str:
    """Return the value of an env var or raise ConfigurationError naming it."""
    value = os.environ.get(var)
    if not value:
        raise ConfigurationError(
            f"Required environment variable {var!r} is not set. "
            f"Export it before starting the workflow."
        )
    return value


def _convert_usage(usage: RunUsage) -> TokenUsage:
    """Convert pydantic-ai's Usage dataclass to our TokenUsage model."""
    return TokenUsage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=usage.cache_read_tokens,
        cache_write_tokens=usage.cache_write_tokens,
    )


def _build_anthropic(config: TierConfig) -> tuple[AnthropicModel, ClientCapabilities]:
    api_key = _require_env(config.api_key_env or "ANTHROPIC_API_KEY")
    client = AsyncAnthropic(api_key=api_key, max_retries=0)
    model = AnthropicModel(config.model, provider=AnthropicProvider(anthropic_client=client))
    caps = ClientCapabilities(
        supports_prompt_caching=True,
        supports_parallel_tool_calls=True,
        supports_structured_output=True,
        supports_thinking=True,
        supports_vision=True,
        max_context=200_000,
        provider="anthropic",
        model=config.model,
    )
    return model, caps


def _build_ollama(config: TierConfig) -> tuple[OpenAIChatModel, ClientCapabilities]:
    base_url = config.base_url or "http://localhost:11434/v1"
    # Ollama doesn't require a real API key; the client still needs a non-empty value.
    client = AsyncOpenAI(api_key="ollama", base_url=base_url, max_retries=0)
    model = OpenAIChatModel(config.model, provider=OpenAIProvider(openai_client=client))
    caps = ClientCapabilities(
        supports_prompt_caching=False,
        supports_parallel_tool_calls=False,
        supports_structured_output=False,
        supports_thinking=False,
        supports_vision=False,
        # Conservative default — actual limit is model-specific.
        max_context=8_192,
        provider="ollama",
        model=config.model,
    )
    return model, caps


def _build_openai_compat(config: TierConfig) -> tuple[OpenAIChatModel, ClientCapabilities]:
    if not config.base_url:
        raise ConfigurationError(
            f"openai_compat tier requires base_url; got None for model {config.model!r}. "
            "Set base_url in tiers.yaml (e.g. https://generativelanguage.googleapis.com/v1beta/openai/)."
        )
    api_key = _require_env(config.api_key_env or "OPENAI_API_KEY")
    client = AsyncOpenAI(api_key=api_key, base_url=config.base_url, max_retries=0)
    model = OpenAIChatModel(config.model, provider=OpenAIProvider(openai_client=client))
    caps = ClientCapabilities(
        supports_prompt_caching=False,
        supports_parallel_tool_calls=True,
        supports_structured_output=True,
        supports_thinking=False,
        # Vision varies by model; conservative default.
        supports_vision=False,
        max_context=128_000,
        provider="openai_compat",
        model=config.model,
    )
    return model, caps


def _build_google(config: TierConfig) -> tuple[GoogleModel, ClientCapabilities]:
    api_key = _require_env(config.api_key_env or "GOOGLE_API_KEY")
    # google-genai's retry_args() maps retry_options=None → stop_after_attempt(1),
    # i.e. one attempt, no retries. GoogleProvider passes no retry_options, so we
    # inherit the "no retry" default. This satisfies CRIT-06 by the SDK default;
    # if google-genai changes that default, test_google_client_retry_is_disabled
    # will catch the regression before it reaches production.
    model = GoogleModel(config.model, provider=GoogleProvider(api_key=api_key))
    caps = ClientCapabilities(
        supports_prompt_caching=False,
        supports_parallel_tool_calls=True,
        supports_structured_output=True,
        supports_thinking=True,
        supports_vision=True,
        max_context=1_000_000,
        provider="google",
        model=config.model,
    )
    return model, caps
