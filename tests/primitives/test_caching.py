"""Tests for M1 Task 04 — ai_workflows.primitives.llm.caching.

Covers acceptance criteria:

1. Last tool definition carries ``cache_control`` in the outgoing request
2. Last system block carries ``cache_control``
3. ``validate_prompt_template()`` flags ``{{var}}`` in system prompts
4. Cache read tokens recorded in :class:`TokenUsage` (so ``aiw inspect``
   can surface them in Task 12)

Note: AC-4 live integration test (cache_read_tokens > 0 on turn 2) is
permanently N/A — this deployment uses Gemini + Qwen (no Anthropic API),
and neither provider supports cache_control breakpoints.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_workflows.primitives.llm.caching import (
    PromptTemplateError,
    apply_cache_control,
    build_cache_settings,
    validate_prompt_template,
)
from ai_workflows.primitives.llm.model_factory import build_model, run_with_cost
from ai_workflows.primitives.llm.types import ClientCapabilities, TokenUsage, WorkflowDeps
from ai_workflows.primitives.tiers import TierConfig

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ANTHROPIC_CAPS = ClientCapabilities(
    supports_prompt_caching=True,
    supports_parallel_tool_calls=True,
    supports_structured_output=True,
    supports_thinking=True,
    supports_vision=True,
    max_context=200_000,
    provider="anthropic",
    model="claude-sonnet-4-6",
)

OLLAMA_CAPS = ClientCapabilities(
    supports_prompt_caching=False,
    max_context=8_192,
    provider="ollama",
    model="llama3.2",
)

SONNET_TIER = TierConfig(
    provider="anthropic",
    model="claude-sonnet-4-6",
    max_tokens=8192,
    temperature=0.1,
)


def _null_tracker():
    tracker = MagicMock()
    tracker.record = AsyncMock(return_value=0.0)
    return tracker


# ---------------------------------------------------------------------------
# AC-1 + AC-2: apply_cache_control marks last tool def and last system block
# ---------------------------------------------------------------------------


def test_apply_cache_control_marks_last_tool_definition():
    tools = [
        {"name": "read_file", "description": "r", "input_schema": {}},
        {"name": "write_file", "description": "w", "input_schema": {}},
    ]
    _, new_tools, _ = apply_cache_control([], tools, [])

    assert "cache_control" not in new_tools[0]
    assert new_tools[-1]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}


def test_apply_cache_control_marks_last_system_block():
    system = [
        {"type": "text", "text": "You are an assistant."},
        {"type": "text", "text": "Follow the rules below."},
    ]
    new_system, _, _ = apply_cache_control(system, [], [])

    assert "cache_control" not in new_system[0]
    assert new_system[-1]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}


def test_apply_cache_control_leaves_messages_unchanged():
    msgs = [{"role": "user", "content": "hello"}]
    _, _, new_msgs = apply_cache_control([], [], msgs)

    assert new_msgs == msgs
    # Returned list is a deep copy — safe to mutate.
    new_msgs[0]["content"] = "mutated"
    assert msgs[0]["content"] == "hello"


def test_apply_cache_control_does_not_mutate_inputs():
    system = [{"type": "text", "text": "static"}]
    tools = [{"name": "a", "description": "", "input_schema": {}}]
    apply_cache_control(system, tools, [])

    assert "cache_control" not in system[0]
    assert "cache_control" not in tools[0]


def test_apply_cache_control_handles_empty_inputs():
    s, t, m = apply_cache_control([], [], [])
    assert (s, t, m) == ([], [], [])


def test_apply_cache_control_respects_5m_ttl():
    system = [{"type": "text", "text": "static"}]
    tools = [{"name": "a", "description": "", "input_schema": {}}]
    new_system, new_tools, _ = apply_cache_control(system, tools, [], ttl="5m")

    assert new_system[-1]["cache_control"] == {"type": "ephemeral", "ttl": "5m"}
    assert new_tools[-1]["cache_control"] == {"type": "ephemeral", "ttl": "5m"}


# ---------------------------------------------------------------------------
# build_cache_settings: returns AnthropicModelSettings iff caps support caching
# ---------------------------------------------------------------------------


def test_build_cache_settings_for_anthropic_sets_both_breakpoints():
    settings = build_cache_settings(ANTHROPIC_CAPS)

    assert settings is not None
    assert settings["anthropic_cache_instructions"] == "1h"
    assert settings["anthropic_cache_tool_definitions"] == "1h"


def test_build_cache_settings_for_non_caching_provider_returns_none():
    assert build_cache_settings(OLLAMA_CAPS) is None


def test_build_cache_settings_5m_ttl_override():
    settings = build_cache_settings(ANTHROPIC_CAPS, ttl="5m")

    assert settings is not None
    assert settings["anthropic_cache_instructions"] == "5m"
    assert settings["anthropic_cache_tool_definitions"] == "5m"


def test_build_cache_settings_pairs_with_build_model(monkeypatch):
    """AC-1+AC-2 wiring: build_model → caps → build_cache_settings produces
    the settings object a caller would hand to ``Agent(model_settings=...)``.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    _, caps = build_model("sonnet", {"sonnet": SONNET_TIER}, _null_tracker())

    settings = build_cache_settings(caps)
    assert settings is not None
    assert settings["anthropic_cache_instructions"] == "1h"
    assert settings["anthropic_cache_tool_definitions"] == "1h"


# ---------------------------------------------------------------------------
# AC-3: validate_prompt_template flags {{var}} in system prompts
# ---------------------------------------------------------------------------


def test_validate_prompt_template_rejects_template_variable(tmp_path: Path):
    prompt = tmp_path / "system.md"
    prompt.write_text("You are a senior engineer. The run id is {{run_id}}.", encoding="utf-8")

    with pytest.raises(PromptTemplateError) as exc_info:
        validate_prompt_template(prompt)

    msg = str(exc_info.value)
    assert "run_id" in msg
    assert str(prompt) in msg


def test_validate_prompt_template_rejects_dotted_variable(tmp_path: Path):
    prompt = tmp_path / "system.md"
    prompt.write_text("Context: {{deps.workflow_id}}.", encoding="utf-8")

    with pytest.raises(PromptTemplateError) as exc_info:
        validate_prompt_template(prompt)
    assert "deps.workflow_id" in str(exc_info.value)


def test_validate_prompt_template_lists_all_offending_variables(tmp_path: Path):
    prompt = tmp_path / "system.md"
    prompt.write_text(
        "Timestamp: {{timestamp}}. Run: {{run_id}}. Repeat {{timestamp}}.",
        encoding="utf-8",
    )
    with pytest.raises(PromptTemplateError) as exc_info:
        validate_prompt_template(prompt)

    msg = str(exc_info.value)
    assert "timestamp" in msg
    assert "run_id" in msg


def test_validate_prompt_template_accepts_static_prompt(tmp_path: Path):
    prompt = tmp_path / "system.md"
    prompt.write_text(
        "You are a senior software engineer. Follow the rules. No variables here.",
        encoding="utf-8",
    )
    # Should not raise.
    validate_prompt_template(prompt)


def test_validate_prompt_template_ignores_single_brace(tmp_path: Path):
    """A single {brace} is not a template substitution — only {{ double }}."""
    prompt = tmp_path / "system.md"
    prompt.write_text("Use Python's f-string syntax like f'{name}'.", encoding="utf-8")
    validate_prompt_template(prompt)


def test_validate_prompt_template_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        validate_prompt_template(tmp_path / "does_not_exist.md")


def test_validate_prompt_template_accepts_str_path(tmp_path: Path):
    prompt = tmp_path / "system.md"
    prompt.write_text("Static prompt.", encoding="utf-8")
    # Accepts plain str path (not just Path).
    validate_prompt_template(str(prompt))


# ---------------------------------------------------------------------------
# AC-5: TokenUsage captures cache_read_tokens / cache_write_tokens so
#       Task 12's `aiw inspect` can surface them. Verified end-to-end at the
#       factory level: _convert_usage populates the two fields.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_with_cost_forwards_cache_tokens_to_tracker():
    from pydantic_ai.usage import RunUsage

    tracker = _null_tracker()
    deps = WorkflowDeps(
        run_id="run-1",
        workflow_id="wf-1",
        component="worker",
        tier="sonnet",
        project_root="/tmp",
    )

    usage = RunUsage(
        input_tokens=100,
        output_tokens=20,
        cache_read_tokens=4_096,
        cache_write_tokens=0,
    )
    mock_result = MagicMock()
    mock_result.usage.return_value = usage

    mock_agent = MagicMock()
    mock_agent.run = AsyncMock(return_value=mock_result)
    mock_agent.model.model_name = "claude-sonnet-4-6"

    await run_with_cost(mock_agent, "hello again", deps, tracker)

    forwarded: TokenUsage = tracker.record.call_args.kwargs["usage"]
    assert forwarded.cache_read_tokens == 4_096
    assert forwarded.cache_write_tokens == 0


# AC-4 integration test (cache_read_tokens > 0 on turn 2) is permanently N/A
# for this deployment: no Anthropic API key available. Gemini and Qwen do not
# support cache_control breakpoints. The helpers (apply_cache_control,
# build_cache_settings) are implemented and unit-tested for third-party
# Anthropic deployments.
