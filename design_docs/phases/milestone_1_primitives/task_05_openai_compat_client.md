# Task 05 — OpenAICompatClient Adapter

**Issues:** P-06, P-09

## What to Build

A single adapter for OpenAI-compatible APIs: OpenRouter, DeepSeek API, Gemini Flash (via compat layer). Each provider has quirks — the adapter handles them via a per-provider config section in `tiers.yaml`.

## Deliverables

### `primitives/llm/openai_compat.py`

Key behaviors:

**Provider config in `tiers.yaml`:** Each compat tier declares `provider: openai_compat`, `base_url`, and optionally a `quirks` block:
```yaml
gemini_flash:
  provider: openai_compat
  model: gemini-2.0-flash
  base_url: "https://generativelanguage.googleapis.com/v1beta/openai/"
  api_key_env: GEMINI_API_KEY
  max_tokens: 8192
```

**Quirk handling:** OpenAI compat providers differ in:
- Tool call format (some use `function`, some `tool_calls`)
- Token count field names in responses
- Whether streaming is supported (irrelevant for MVP but note it)

Normalize all of these to the standard `ContentBlock` types.

**Auth:** Each compat tier declares its own `api_key_env` field. Read the specified env var. Raise `ConfigurationError` with the env var name if missing.

**No prompt caching:** No compat provider supports Anthropic-style caching. Skip silently.

## Open Questions (resolve at implementation)

- P-06: Does one adapter cleanly handle all three providers, or do edge cases warrant sub-adapters? Build for one adapter first and extract sub-adapters only if needed.

## Acceptance Criteria

- [ ] `OpenAICompatClient` passes `isinstance(client, LLMClient)` structural check
- [ ] Integration test with at least one real compat provider (mark `@pytest.mark.integration`)
- [ ] Tool call responses normalize to `ToolUseBlock` correctly
- [ ] Missing API key raises `ConfigurationError` with the correct env var name

## Dependencies

- Task 02 (shared types)
- Task 11 (tiers loader)
