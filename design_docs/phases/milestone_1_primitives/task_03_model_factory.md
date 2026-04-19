# Task 03 — Model Factory

**Status:** ✅ Complete (2026-04-18) — see [issues/task_03_issue.md](issues/task_03_issue.md).

**Issues:** P-06, P-09, P-10, CRIT-05, CRIT-06

## What to Build

A factory that, given a tier name, returns a configured `pydantic_ai.Model` instance (or raises `NotImplementedError` for the `claude_code` provider, which lands in M4). We don't write API clients from scratch — pydantic-ai already ships `OpenAIChatModel` and `GoogleModel`. We wrap their construction with:

- API key loading from env vars (tier-specified `api_key_env`)
- `max_retries=0` on every underlying SDK client (CRIT-06)
- `ClientCapabilities` declared per provider
- Wiring to our cost tracker
- Ollama via `OpenAIChatModel` pointing at an Ollama base URL
- `claude_code` tiers (`opus`, `sonnet`, `haiku`) raise `NotImplementedError` — the subprocess launcher is M4 work

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

| Tier provider | pydantic-ai Model | Default tiers | Notes |
| --- | --- | --- | --- |
| `claude_code` | `NotImplementedError` (M4) | `opus`, `sonnet`, `haiku` | Claude Max subscription via `claude` CLI subprocess |
| `openai_compat` | `OpenAIChatModel` | `gemini_flash` | Gemini API last-resort overflow |
| `ollama` | `OpenAIChatModel(base_url=...)` | `local_coder` | Local Qwen, free |
| `google` | `GoogleModel` | (reserved) | Native Google SDK, not in default tiers |
| `anthropic` | `AnthropicModel` | (not used) | Supported in code for third-party deployments; no API key in this project |

### `ClientCapabilities` per Provider

| Provider | caching | parallel tools | structured | thinking | vision | max_context |
| --- | --- | --- | --- | --- | --- | --- |
| `claude_code` (opus/sonnet/haiku) | False* | True | True | True | True | 200_000 |
| `openai_compat` (gemini_flash) | False | True | True | False | False | 128_000 |
| `ollama` (local_coder / Qwen) | False | False | False | False | False | per-model |
| `google` | False | True | True | True | True | 1_000_000 |

\* Prompt caching is an Anthropic API feature, not available via Claude Code CLI.

### `max_retries=0` (CRIT-06)

Every underlying SDK client must have its internal retries disabled. For pydantic-ai models, pass through to the client:

```python
# OpenAI-compat (Gemini overflow, Ollama/Qwen)
from openai import AsyncOpenAI
client = AsyncOpenAI(max_retries=0, base_url=base_url, api_key=api_key)
model = OpenAIChatModel(model_name, openai_client=client)

# claude_code — subprocess launcher, not a pydantic-ai Model; deferred to M4
# google — GoogleModel via GoogleProvider; reserved, not in default tiers
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

- [x] `build_model("gemini", tiers, cost_tracker)` returns `(OpenAIChatModel, capabilities)` with `provider="openai_compat"` — the real overflow tier
- [x] `build_model("local_coder", tiers, cost_tracker)` returns `(OpenAIChatModel, capabilities)` with `base_url` from Ollama config
- [x] Underlying SDK clients have `max_retries=0`
- [x] Integration test with `GEMINI_API_KEY` confirms cost recording fires after an `agent.run()`; Ollama integration test confirms the local path end-to-end
- [x] Missing env var raises `ConfigurationError` naming the variable
- [ ] `build_model` raises `NotImplementedError` for `claude_code` provider (M4 — subprocess launcher not yet implemented)

## Dependencies

- Task 02 (shared types)
- Task 07 (tiers loader) — needs TierConfig model
- Task 09 (cost tracker)
