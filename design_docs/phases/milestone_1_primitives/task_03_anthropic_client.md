# Task 03 — AnthropicClient Adapter

**Issues:** P-04, P-09, P-10

## What to Build

The Anthropic adapter. Implements `LLMClient` protocol. Handles prompt caching automatically, normalizes all Anthropic response formats into `ContentBlock` types.

## Deliverables

### `primitives/llm/anthropic.py`

Key behaviors:

**Auto prompt caching:** Mark the last `user`-role system-level message block with `"cache_control": {"type": "ephemeral"}` before sending. Invisible to callers — the adapter applies this internally to the Anthropic API request. Saves ~90% on repeated system prompt tokens in fan-out runs.

**Response normalization:** Translate Anthropic's response format into `Response(content: list[ContentBlock], stop_reason, usage: TokenUsage)`. The raw Anthropic response object never leaves the adapter.

**Connection pooling:** Use a single shared `httpx.AsyncClient` instance per `AnthropicClient` instance. Pass it to the `anthropic.AsyncAnthropic` constructor.

**Auth:** Read `ANTHROPIC_API_KEY` from env. Raise a clear `ConfigurationError` if missing — not a cryptic SDK error.

**Cost tagging:** Every `generate()` call logs to the cost tracker with `run_id`, `workflow_id`, `component`, tier name, and token counts from `TokenUsage`.

## Acceptance Criteria

- [ ] `AnthropicClient` passes `isinstance(client, LLMClient)` structural check
- [ ] Makes a real API call in an integration test (requires `ANTHROPIC_API_KEY` in env — mark test `@pytest.mark.integration`)
- [ ] Cache control block appears in the outgoing request (verify in the integration test via a captured request)
- [ ] All Anthropic response types (text, tool_use, end_turn) normalize correctly to `ContentBlock` types
- [ ] Missing API key raises `ConfigurationError` with a clear message before any network call

## Dependencies

- Task 02 (shared types)
- Task 13 (cost tracker) — can stub cost logging initially, wire fully in Task 13
