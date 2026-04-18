# Task 02 — Shared Types

**Issues:** P-01, P-02, P-07

## What to Build

The canonical data types that every layer speaks. These are defined once in `primitives/llm/base.py` and imported everywhere. Getting these right is critical — changing them later requires touching every adapter.

## Deliverables

### `primitives/llm/base.py`

```python
from typing import Literal, Protocol
from pydantic import BaseModel


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
    content: str
    is_error: bool = False


ContentBlock = TextBlock | ToolUseBlock | ToolResultBlock


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


class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict  # JSON Schema object


class LLMClient(Protocol):
    async def generate(
        self,
        messages: list[Message],
        *,
        run_id: str,
        workflow_id: str,
        component: str,
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> Response: ...
```

## Notes

- `ContentBlock` is a discriminated union. Pydantic v2 handles this cleanly with `model_validator` or tagged unions.
- `ToolResultBlock` is what adapters produce after a tool call is executed and the result is sanitized. It never carries raw file content directly — only after the sanitizer has processed it.
- `LLMClient` is a `Protocol` (structural subtyping), not a base class. Adapters don't inherit from it — they just implement the method signature.
- `run_id`, `workflow_id`, `component` are required keyword-only args on every `generate()` call. This is the explicit cost-tagging contract.

## Acceptance Criteria

- [ ] All types importable from `ai_workflows.primitives.llm.base`
- [ ] `Message` with mixed content blocks round-trips through Pydantic (serialize → deserialize)
- [ ] `LLMClient` protocol can be used in `isinstance()` structural checks (Protocol + `runtime_checkable`)
- [ ] Unit tests for all model serialization edge cases

## Dependencies

- Task 01 (scaffolding)
