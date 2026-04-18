# Task 06 — Tool Sanitizer

**Issues:** X-07

## What to Build

A pure function that processes every tool result before it enters the LLM message history. Protects against prompt injection from user-controlled file content and external data sources. Especially important for local models (Qwen) which are more susceptible.

## Deliverables

### `primitives/tools/sanitizer.py`

```python
def sanitize_tool_output(raw_output: str, tool_name: str) -> str:
    """
    Strip or flag prompt injection patterns from tool output.
    Returns cleaned string safe to include in a ToolResultBlock.
    """
    ...
```

**Injection patterns to detect and strip:**
- `IGNORE PREVIOUS INSTRUCTIONS` (case-insensitive)
- `YOU ARE NOW` / `YOU ARE A` (role reassignment)
- `SYSTEM:` prefix injection attempts
- `<|im_start|>`, `<|im_end|>` and similar model-specific control tokens
- `[INST]`, `<<SYS>>` and Llama-style special tokens
- Repeated instruction blocks that mirror the system prompt structure

**When a pattern is detected:**
- Replace the matched span with `[SANITIZED]`
- Log a `structlog` warning with `tool_name`, the matched pattern type, and the first 100 chars of the matched span
- Do NOT raise an exception — the LLM should still receive the sanitized result

**Integration point:** Every adapter calls `sanitize_tool_output()` on the `content` field of any `ToolResultBlock` before appending it to the message history. This is not optional — it's part of the tool execution contract.

## Acceptance Criteria

- [ ] All listed injection patterns are stripped in unit tests
- [ ] Clean content passes through unmodified
- [ ] Warning logged (verify with `structlog` test capture) when sanitization occurs
- [ ] No exceptions raised on any input — pure function, never fails
- [ ] Performance: sanitization of a 50K-character string completes in < 10ms

## Dependencies

- Task 01 (scaffolding)
- Task 15 (logging) — can stub `structlog` initially
