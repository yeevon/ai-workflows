# Task 02 — Shared Types

**Issues:** P-01, P-02, P-07, CRIT-05, CRIT-09

## What to Build

Canonical types at `primitives/llm/types.py`. `ContentBlock` is a proper Pydantic v2 discriminated union. `ClientCapabilities` makes adapter capabilities explicit so components never `isinstance()` check.

## Deliverables

### `primitives/llm/types.py`

```python
from typing import Literal, Annotated
from pydantic import BaseModel, Field


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ToolUseBlock(BaseModel):
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict


class ToolResultBlock(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str          # sanitized / processed tool output
    is_error: bool = False


ContentBlock = Annotated[
    TextBlock | ToolUseBlock | ToolResultBlock,
    Field(discriminator="type"),
]


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: list[ContentBlock]


class TokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class Response(BaseModel):
    content: list[ContentBlock]
    stop_reason: str
    usage: TokenUsage


class ClientCapabilities(BaseModel):
    """Capability descriptor returned by every adapter.

    Components check capabilities, never isinstance().
    """
    supports_prompt_caching: bool = False
    supports_parallel_tool_calls: bool = False
    supports_structured_output: bool = False
    supports_thinking: bool = False
    supports_vision: bool = False
    max_context: int
    provider: Literal["anthropic", "openai_compat", "ollama"]
    model: str


class WorkflowDeps(BaseModel):
    """Passed as `deps` to every pydantic-ai Agent.run() call.

    Makes run_id, workflow_id, component available in any tool call
    via RunContext[WorkflowDeps].
    """
    run_id: str
    workflow_id: str
    component: str
    tier: str
    allowed_executables: list[str] = []
    project_root: str
```

## Why Discriminated Union (CRIT-09)

Without `Field(discriminator="type")`, Pydantic v2 tries each variant in order on every block. On a message with 50 tool_use blocks, this means 50 × (try TextBlock, fail, try ToolUseBlock, succeed) = wasted cycles and confusing validation errors. With the discriminator, Pydantic reads `type` once and dispatches directly.

## Why `ClientCapabilities` (CRIT-05)

Anthropic supports prompt caching; Ollama does not. If a `Worker` component wants to know "can I rely on cache?", the answer must come from a capability flag, not `isinstance(client, AnthropicClient)`. The `isinstance` approach forces Components to import from specific adapter modules, breaking the layering.

## Acceptance Criteria

- [ ] Discriminated union dispatches correctly — `Message(content=[{"type":"text", "text":"hi"}])` parses without trying other variants
- [ ] A message with 50 tool_use blocks parses in < 5ms
- [ ] Invalid `type` value raises a clear Pydantic error naming the allowed literals
- [ ] `ClientCapabilities` is serializable to/from JSON for logging

## Dependencies

- Task 01
