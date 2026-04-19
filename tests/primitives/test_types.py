"""Tests for M1 Task 02 — ai_workflows.primitives.llm.types.

Covers all four acceptance criteria:
1. Discriminated union dispatches correctly.
2. 50 tool_use blocks parse in < 5 ms.
3. Invalid ``type`` raises a clear Pydantic ValidationError.
4. ClientCapabilities round-trips through JSON.
"""

import time

import pytest
from pydantic import ValidationError

from ai_workflows.primitives.llm.types import (
    ClientCapabilities,
    Message,
    Response,
    TextBlock,
    TokenUsage,
    ToolResultBlock,
    ToolUseBlock,
    WorkflowDeps,
)

# ---------------------------------------------------------------------------
# AC-1: discriminated union dispatches correctly
# ---------------------------------------------------------------------------


def test_message_parses_text_block_from_dict():
    msg = Message(content=[{"type": "text", "text": "hi"}], role="user")
    assert len(msg.content) == 1
    block = msg.content[0]
    assert isinstance(block, TextBlock)
    assert block.text == "hi"


def test_message_parses_tool_use_block_from_dict():
    msg = Message(
        role="assistant",
        content=[{"type": "tool_use", "id": "t1", "name": "search", "input": {"q": "x"}}],
    )
    block = msg.content[0]
    assert isinstance(block, ToolUseBlock)
    assert block.name == "search"


def test_message_parses_tool_result_block_from_dict():
    msg = Message(
        role="user",
        content=[{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}],
    )
    block = msg.content[0]
    assert isinstance(block, ToolResultBlock)
    assert block.tool_use_id == "t1"
    assert block.is_error is False


def test_message_parses_mixed_content():
    msg = Message(
        role="user",
        content=[
            {"type": "text", "text": "see result"},
            {"type": "tool_result", "tool_use_id": "t2", "content": "done", "is_error": False},
        ],
    )
    assert isinstance(msg.content[0], TextBlock)
    assert isinstance(msg.content[1], ToolResultBlock)


# ---------------------------------------------------------------------------
# AC-2: 50 tool_use blocks parse in < 5 ms
# ---------------------------------------------------------------------------


def test_fifty_tool_use_blocks_parse_quickly():
    blocks = [
        {"type": "tool_use", "id": f"t{i}", "name": "fn", "input": {"k": i}}
        for i in range(50)
    ]
    start = time.perf_counter()
    msg = Message(role="assistant", content=blocks)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert len(msg.content) == 50
    # Spec target is 5 ms; 25 ms cap (5× headroom) absorbs noisy shared CI
    # runners while still catching a real regression — if the discriminator
    # were missing, Pydantic would try each variant and blow past 25 ms.
    assert elapsed_ms < 25, f"Parsing took {elapsed_ms:.2f} ms — discriminator not working?"


# ---------------------------------------------------------------------------
# AC-3: invalid type raises a clear Pydantic error
# ---------------------------------------------------------------------------


def test_invalid_type_raises_validation_error():
    with pytest.raises(ValidationError) as exc_info:
        Message(role="user", content=[{"type": "audio", "data": "..."}])
    err_str = str(exc_info.value)
    # Pydantic names ALL allowed literals in the error message; require all three
    # so this test fails if the discriminated union is ever replaced with a plain Union
    assert "text" in err_str and "tool_use" in err_str and "tool_result" in err_str


def test_invalid_type_error_names_discriminator_field():
    with pytest.raises(ValidationError) as exc_info:
        Message(role="user", content=[{"type": "bogus"}])
    # The error must reference the discriminator field
    assert "type" in str(exc_info.value)


# ---------------------------------------------------------------------------
# AC-4: ClientCapabilities round-trips through JSON
# ---------------------------------------------------------------------------


def test_client_capabilities_serializes_to_json():
    caps = ClientCapabilities(
        supports_prompt_caching=True,
        max_context=200_000,
        provider="anthropic",
        model="claude-opus-4-7",
    )
    json_str = caps.model_dump_json()
    assert "anthropic" in json_str
    assert "claude-opus-4-7" in json_str


def test_client_capabilities_roundtrips_json():
    caps = ClientCapabilities(
        supports_vision=True,
        supports_thinking=True,
        max_context=128_000,
        provider="openai_compat",
        model="gpt-4o",
    )
    caps2 = ClientCapabilities.model_validate_json(caps.model_dump_json())
    assert caps2 == caps


def test_client_capabilities_roundtrips_dict():
    caps = ClientCapabilities(
        max_context=32_768,
        provider="ollama",
        model="llama3.2",
    )
    caps2 = ClientCapabilities.model_validate(caps.model_dump())
    assert caps2 == caps


def test_client_capabilities_google_provider_roundtrips():
    # google is a distinct provider (not openai_compat) because Gemini Flash
    # exposes a 1M-token context window that must be reflected in max_context.
    caps = ClientCapabilities(
        max_context=1_000_000,
        provider="google",
        model="gemini-2.0-flash",
        supports_vision=True,
    )
    caps2 = ClientCapabilities.model_validate_json(caps.model_dump_json())
    assert caps2 == caps
    assert caps2.provider == "google"


def test_client_capabilities_claude_code_provider_roundtrips():
    # claude_code is the Claude Max CLI tier (opus/sonnet/haiku). Prompt caching
    # is an Anthropic API feature and is NOT exposed via the CLI, so the flag is
    # False even though the underlying model would support it on the raw API.
    caps = ClientCapabilities(
        max_context=200_000,
        provider="claude_code",
        model="claude-opus-4-7",
        supports_parallel_tool_calls=True,
        supports_structured_output=True,
        supports_thinking=True,
        supports_vision=True,
    )
    caps2 = ClientCapabilities.model_validate_json(caps.model_dump_json())
    assert caps2 == caps
    assert caps2.provider == "claude_code"
    assert caps2.supports_prompt_caching is False


# ---------------------------------------------------------------------------
# Structural / import sanity
# ---------------------------------------------------------------------------


def test_all_types_importable():
    for cls in (
        TextBlock,
        ToolUseBlock,
        ToolResultBlock,
        Message,
        TokenUsage,
        Response,
        ClientCapabilities,
        WorkflowDeps,
    ):
        assert cls is not None


def test_token_usage_defaults():
    u = TokenUsage(input_tokens=10, output_tokens=5)
    assert u.cache_read_tokens == 0
    assert u.cache_write_tokens == 0


def test_workflow_deps_defaults():
    deps = WorkflowDeps(
        run_id="r1",
        workflow_id="w1",
        component="worker",
        tier="tier1",
        project_root="/tmp",
    )
    assert deps.allowed_executables == []


def test_response_model():
    r = Response(
        content=[TextBlock(text="hello")],
        stop_reason="end_turn",
        usage=TokenUsage(input_tokens=5, output_tokens=3),
    )
    assert r.stop_reason == "end_turn"
    assert isinstance(r.content[0], TextBlock)
