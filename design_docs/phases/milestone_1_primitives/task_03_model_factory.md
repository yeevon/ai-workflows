# Task 03 — Model Factory

**Status:** ✅ Complete (2026-04-18) — see [issues/task_03_issue.md](issues/task_03_issue.md).

**Issues:** P-06, P-09, P-10, CRIT-05, CRIT-06

## What to Build

A factory that, given a tier name, returns a configured `pydantic_ai.Model` instance. We don't write Anthropic/OpenAI/Ollama clients from scratch — pydantic-ai already ships `AnthropicModel`, `OpenAIModel`, and `GoogleModel`. We wrap their construction with:

- API key loading from env vars (tier-specified `api_key_env`)
- `max_retries=0` on every underlying SDK client (CRIT-06)
- `ClientCapabilities` declared per provider
- Wiring to our cost tracker
- Ollama via `OpenAIModel` pointing at an Ollama base URL

## Deliverables

### `primitives/llm/model_factory.py`

```python
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.models.google import GoogleModel

def build_model(
    tier_name: str,
    tiers: dict[str, TierConfig],
    cost_tracker: CostTracker,
) -> tuple[Model, ClientCapabilities]:
    """
    Return a configured pydantic-ai Model and its capability descriptor.

    - Sets max_retries=0 on underlying SDK client
    - Wires cost tracking hook via pydantic-ai's usage callback
    - Ollama tier → OpenAIModel with Ollama base_url
    """
```

### Provider → Model Mapping

| Tier provider | pydantic-ai Model | Notes |
| --- | --- | --- |
| `anthropic` | `AnthropicModel` | native |
| `openai_compat` | `OpenAIModel` | for DeepSeek, OpenRouter |
| `google` / `gemini` | `GoogleModel` (or `OpenAIModel` via compat endpoint) | pick native if available |
| `ollama` | `OpenAIModel(base_url=...)` | Ollama exposes OpenAI-compatible API |

### `ClientCapabilities` per Provider

| Provider | caching | parallel tools | structured | thinking | vision | max_context |
| --- | --- | --- | --- | --- | --- | --- |
| `anthropic` (Opus/Sonnet/Haiku) | True | True | True | True | True | 200_000 |
| `openai_compat` (DeepSeek, OpenRouter) | False | True | True | False | varies | 128_000 |
| `google` / `gemini-flash` | False | True | True | True | True | 1_000_000 |
| `ollama` | False | varies by model | False | False | False | per-model |

### `max_retries=0` (CRIT-06)

Every underlying SDK client must have its internal retries disabled. For pydantic-ai models, pass through to the client:

```python
# Anthropic
from anthropic import AsyncAnthropic
client = AsyncAnthropic(max_retries=0)
model = AnthropicModel(model_name, anthropic_client=client)

# OpenAI-compat (including Ollama)
from openai import AsyncOpenAI
client = AsyncOpenAI(max_retries=0, base_url=base_url, api_key=api_key)
model = OpenAIModel(model_name, openai_client=client)
```

Our `retry_on_rate_limit()` (task 10) is the single authority. Without this, 3 (SDK) × 3 (ours) = 9 amplified retries on 429, doubling rate-limit pressure.

### Cost Tracking Hook

Pydantic-ai's `Agent.run()` returns a result with `.usage()` (token counts). We wrap this in a thin helper:

```python
async def run_with_cost(
    agent: Agent,
    prompt: str,
    deps: WorkflowDeps,
    cost_tracker: CostTracker,
) -> AgentRunResult:
    result = await agent.run(prompt, deps=deps)
    await cost_tracker.record(
        run_id=deps.run_id,
        workflow_id=deps.workflow_id,
        component=deps.component,
        tier=deps.tier,
        model=agent.model.model_name,
        usage=_convert_usage(result.usage()),
    )
    return result
```

## Acceptance Criteria

- [x] `build_model("sonnet", tiers, cost_tracker)` returns `(AnthropicModel, capabilities)` with `supports_prompt_caching=True`
- [x] `build_model("local_coder", tiers, cost_tracker)` returns `(OpenAIModel, capabilities)` with `base_url` from Ollama config
- [x] Underlying SDK clients have `max_retries=0` (verify via `client._client.max_retries` or equivalent)
- [x] Integration test with a real provider key (Gemini via `openai_compat` or Anthropic) confirms cost recording fires after an `agent.run()`; a parallel Ollama integration test confirms the local path end-to-end
- [x] Missing env var raises `ConfigurationError` naming the variable

## Dependencies

- Task 02 (shared types)
- Task 07 (tiers loader) — needs TierConfig model
- Task 09 (cost tracker)
