# Task 04 — Multi-Breakpoint Prompt Caching

**Status:** ✅ Complete (2026-04-18) — see [issues/task_04_issue.md](issues/task_04_issue.md)

**Issues:** CRIT-07 (revises P-04)

## What to Build

Anthropic prompt caching strategy using up to 4 breakpoints. Replaces the naive "cache last system block" which fails when that block has templated variables.

## Why This Matters

The original plan: mark the last system message block as cacheable. Problem: if that block contains `{{timestamp}}`, `{{run_id}}`, or any per-call variable, every call has a different hash → 0% cache hit, you still pay cache-write cost every time.

Anthropic's 2026 pattern: cache **stable** prefixes. Tool definitions change rarely. Static system instructions change rarely. Dynamic variables go in the LAST user turn, NEVER in the system prompt.

## Deliverables

### `primitives/llm/caching.py`

```python
def apply_cache_control(
    system_blocks: list[dict],
    tool_definitions: list[dict],
    messages: list[dict],
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Apply cache_control breakpoints per Anthropic 2026 strategy:
      1. Last tool definition block           → ttl=1h
      2. Last system block (must be static!)  → ttl=1h
      3. Conversation history                 → ttl=5m (auto on Anthropic,
                                                         pydantic-ai handles it)

    Precondition (caller's responsibility): system blocks MUST contain no
    per-call variables. Templated variables go in the LAST user message.
    """
```

### Caching Rules Enforced at Adapter

When `AnthropicModel` is used through our factory, the caching wrapper:

1. **Tool definitions** — all `@agent.tool` definitions are gathered by pydantic-ai into the request's `tools` field. We mark the last tool definition with `cache_control: {"type": "ephemeral", "ttl": "1h"}`.
2. **System prompt** — Anthropic's API takes `system` as a list of blocks. We ensure the last system block has `cache_control: {"type": "ephemeral", "ttl": "1h"}`. The system block is the static instructions; per-call context lives elsewhere.
3. **Conversation history** — automatic caching on Anthropic-as-of-2026. No manual breakpoint needed; pydantic-ai passes messages through unchanged.

### Component Contract for Prompt Authors

Prompt authors MUST NOT put `{{variable}}` substitutions in system prompts (used by Workers). Variables go in the user-role prompt only. A prompt-authoring lint (simple regex check) enforces this at workflow load time:

```python
def validate_prompt_template(path: str) -> None:
    """Raise if system prompt contains {{var}} substitutions."""
```

### Validation Test (required, not optional)

```python
async def test_prompt_caching_works():
    """Run the same agent twice. Second call MUST have cache_read_input_tokens > 0."""
    agent = Agent(model=anthropic_sonnet, system_prompt=STATIC_SYSTEM)
    r1 = await agent.run("Hello", deps=deps)
    r2 = await agent.run("Hello again", deps=deps)
    usage2 = r2.usage()
    assert usage2.cache_read_tokens > 0, "caching broken: no cache read on turn 2"
```

This test runs against real Anthropic (integration) — not a mock. If caching silently breaks later (e.g., pydantic-ai changes default behavior, a new Claude version handles cache differently), this test catches it.

## Acceptance Criteria

- [x] Tool definitions carry `cache_control` on the last entry in outgoing request
- [x] System prompt last block carries `cache_control`
- [x] `validate_prompt_template()` flags `{{var}}` in system prompts
- [~] Integration test confirms `cache_read_tokens > 0` on turn 2 of a repeated agent call — test present in suite (`test_integration_prompt_caching_works`) but **permanently N/A for this deployment** (no Anthropic API key; Gemini and Qwen do not support cache_control breakpoints). Test guards the code path for third-party Anthropic deployments.
- [x] Cache read tokens recorded in `TokenUsage` (`_convert_usage` + `run_with_cost` — `aiw inspect` surfacing owned by Task 12)

## Dependencies

- Task 03 (model factory)
