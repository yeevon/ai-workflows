# Task 01 — LiteLLM Provider Adapter

**Status:** 📝 Planned.

## What to Build

A thin wrapper around `litellm.completion()` that fulfils the "LiteLLM-backed adapter" role described in [architecture.md §4.1](../../architecture.md). Takes a resolved `LiteLLMRoute` (from M1 [task 06](../milestone_1_reconciliation/task_06_refit_tier_config.md)) plus a prompt and structured-output schema, and returns `(text, TokenUsage)` enriched with LiteLLM's built-in cost data.

## Deliverables

### `ai_workflows/primitives/llm/litellm_adapter.py`

```python
class LiteLLMAdapter:
    def __init__(self, route: LiteLLMRoute, per_call_timeout_s: int): ...

    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict],
        response_format: type[BaseModel] | None = None,
    ) -> tuple[str, TokenUsage]:
        """Call litellm.completion(). Map response.usage.cost_usd → TokenUsage.cost_usd.
        Map response.usage.prompt_tokens / completion_tokens → input_tokens / output_tokens.
        Raise-through any LiteLLM exception; classification happens at TieredNode boundary."""
```

- `response_format` uses LiteLLM's native pydantic-response-format support when supplied.
- `max_retries=0` at the LiteLLM call site — our three-bucket policy runs above it.
- No caching, no fallback (fallback lives at the graph edge, not the adapter).

### Tests

`tests/primitives/llm/test_litellm_adapter.py`:

- Happy path with a stubbed `litellm.acompletion` returning a canned response + usage.
- Usage → `TokenUsage` mapping preserves `input_tokens`, `output_tokens`, `cost_usd`, `model`.
- Exception pass-through (raises `litellm.RateLimitError` → caller sees it verbatim).

## Acceptance Criteria

- [ ] `LiteLLMAdapter.complete()` returns `(str, TokenUsage)` matching the primitive's schema.
- [ ] `TokenUsage.cost_usd` is populated from LiteLLM's enrichment when present.
- [ ] `max_retries=0` verified in a unit test.
- [ ] No classification/retry logic inside the adapter.
- [ ] `uv run pytest tests/primitives/llm/test_litellm_adapter.py` green.

## Dependencies

- M1 [task 02](../milestone_1_reconciliation/task_02_dependency_swap.md) (`litellm` installed).
- M1 [task 06](../milestone_1_reconciliation/task_06_refit_tier_config.md) (`LiteLLMRoute` exists).
- M1 [task 08](../milestone_1_reconciliation/task_08_prune_cost_tracker.md) (`TokenUsage` schema).
