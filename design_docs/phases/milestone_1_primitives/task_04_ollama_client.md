# Task 04 — OllamaClient Adapter

**Issues:** P-05, P-09

## What to Build

The Ollama adapter for local models (Qwen2.5-Coder, Llama, DeepSeek). Same `LLMClient` protocol as `AnthropicClient`. Cost is always `0.0`.

## Deliverables

### `primitives/llm/ollama.py`

Key behaviors:

**Configurable `base_url`:** Read from `OLLAMA_BASE_URL` env var. Default: value from `tiers.yaml` for the tier (e.g., `http://home-desktop-ip:11434`). When `--profile local` is passed, `tiers.local.yaml` overrides `base_url` to `http://localhost:11434`.

**Cost recording:** Always record `TokenUsage(input_tokens=N, output_tokens=M)` from Ollama's response if available, but set cost to `0.0` in the cost tracker. Exclude from cost aggregations.

**Response normalization:** Ollama's chat completion API follows the OpenAI format. Normalize to `ContentBlock` types. Tool call blocks in Ollama responses (if the model supports them) map to `ToolUseBlock`.

**No prompt caching:** Ollama has no equivalent. Skip silently.

**Connection health check:** On first call, attempt a `GET /api/tags` to verify Ollama is reachable. Raise `OllamaUnavailableError` with the `base_url` in the message if it's not — better than a cryptic connection refused error mid-run.

## Acceptance Criteria

- [ ] `OllamaClient` passes `isinstance(client, LLMClient)` structural check
- [ ] `OLLAMA_BASE_URL` override works correctly
- [ ] Integration test makes a real call to a local Ollama instance (mark `@pytest.mark.integration @pytest.mark.requires_ollama`)
- [ ] `OllamaUnavailableError` raised if Ollama is not reachable
- [ ] Cost logged as `0.0` and flagged `local=True` in the run log

## Dependencies

- Task 02 (shared types)
- Task 11 (tiers loader) — for reading `base_url` from tier config
