"""Canonical shared types for the LLM primitives layer.

Produced by M1 Task 02. All higher layers (components, workflows) import
from this module; they never define their own message/response types.

Key design choices
------------------
* ``ContentBlock`` is a discriminated union (``Field(discriminator="type")``),
  not a plain ``Union``. Pydantic v2 reads the ``type`` field once and
  dispatches directly — no trial-and-error across variants.
* ``ClientCapabilities`` makes adapter feature flags explicit so components
  never ``isinstance()``-check the underlying SDK client.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class TextBlock(BaseModel):
    """A plain-text content block."""

    type: Literal["text"] = "text"
    text: str


class ToolUseBlock(BaseModel):
    """A request from the model to invoke a tool."""

    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict


class ToolResultBlock(BaseModel):
    """The sanitised/processed result of a tool call."""

    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str
    is_error: bool = False


ContentBlock = Annotated[
    TextBlock | ToolUseBlock | ToolResultBlock,
    Field(discriminator="type"),
]


class Message(BaseModel):
    """A single turn in a conversation — user or assistant."""

    role: Literal["user", "assistant"]
    content: list[ContentBlock]


class TokenUsage(BaseModel):
    """Token counts returned by the provider after each call."""

    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class Response(BaseModel):
    """The normalised response returned by any model adapter."""

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
    provider: Literal["claude_code", "anthropic", "openai_compat", "ollama", "google"]
    # claude_code   → Claude Max subscription via `claude` CLI (opus/sonnet/haiku);
    #                 subprocess launcher lands in M4.
    # anthropic     → direct Anthropic API (third-party deployments; unused here).
    # openai_compat → Gemini API last-resort overflow (gemini_flash).
    # ollama        → local Qwen (local_coder).
    # google        → native Google SDK (reserved, not in default tiers).
    model: str


class WorkflowDeps(BaseModel):
    """Passed as ``deps`` to every pydantic-ai ``Agent.run()`` call.

    Makes run_id, workflow_id, and component available in any tool call
    via ``RunContext[WorkflowDeps]``.
    """

    run_id: str
    workflow_id: str
    component: str
    tier: str
    allowed_executables: list[str] = []
    project_root: str
