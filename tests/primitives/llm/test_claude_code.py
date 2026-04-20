"""Tests for M2 Task 02 — ``ai_workflows.primitives.llm.claude_code``.

Covers every acceptance criterion from
[task_02_claude_code_driver.md](../../../design_docs/phases/milestone_2_graph/task_02_claude_code_driver.md):

* AC-1 — ``ClaudeCodeSubprocess.complete()`` returns ``(str, TokenUsage)``
  with ``sub_models`` populated when ``modelUsage`` is present.
* AC-2 — cost computed from ``pricing.yaml`` for the primary row and
  every sub-model row.
* AC-3 — timeouts raise ``subprocess.TimeoutExpired``; non-zero exits
  raise ``subprocess.CalledProcessError``; both bucket correctly via
  ``classify()``.
* AC-4 — no ``ANTHROPIC_API_KEY`` lookup anywhere (KDR-003), verified
  by a grep probe over the driver source.
* AC-5 — this file must pass ``uv run pytest`` (enforced by the
  milestone gate).

The spike (M1 Task 13) pinned the subprocess stubbing approach:
swap ``asyncio.create_subprocess_exec`` for a fake that returns a
canned process object. No live ``claude`` CLI is invoked.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.llm.claude_code import ClaudeCodeSubprocess
from ai_workflows.primitives.retry import (
    NonRetryable,
    RetryableTransient,
    classify,
)
from ai_workflows.primitives.tiers import ClaudeCodeRoute, ModelPricing

# ---------------------------------------------------------------------------
# Pricing fixture — mirrors pricing.yaml with non-zero rates so the test
# can assert the cost math actually runs (the shipped pricing.yaml zeroes
# Claude Max tiers because Max bills by subscription, which would hide
# arithmetic bugs in _compute_cost).
# ---------------------------------------------------------------------------

PRICING: dict[str, ModelPricing] = {
    "claude-opus-4-7": ModelPricing(
        input_per_mtok=15.0,
        output_per_mtok=75.0,
        cache_read_per_mtok=1.5,
        cache_write_per_mtok=18.75,
    ),
    "claude-sonnet-4-6": ModelPricing(
        input_per_mtok=3.0,
        output_per_mtok=15.0,
    ),
    "claude-haiku-4-5-20251001": ModelPricing(
        input_per_mtok=1.0,
        output_per_mtok=5.0,
    ),
}


# ---------------------------------------------------------------------------
# Fake subprocess fixture
# ---------------------------------------------------------------------------


class _FakeProc:
    """Minimal stand-in for ``asyncio.subprocess.Process``.

    Carries a pre-canned ``stdout`` + ``stderr`` + ``returncode`` and
    optionally sleeps for ``communicate_delay_s`` to let the
    ``asyncio.wait_for`` timeout path fire.
    """

    def __init__(
        self,
        *,
        stdout: bytes = b"",
        stderr: bytes = b"",
        returncode: int = 0,
        communicate_delay_s: float = 0.0,
    ) -> None:
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode
        self._delay = communicate_delay_s
        self.received_stdin: bytes | None = None

    async def communicate(self, stdin: bytes | None = None) -> tuple[bytes, bytes]:
        self.received_stdin = stdin
        if self._delay:
            await asyncio.sleep(self._delay)
        return self._stdout, self._stderr

    def kill(self) -> None:  # pragma: no cover — invoked only on the timeout path
        self.returncode = -9

    async def wait(self) -> int:  # pragma: no cover — invoked only on the timeout path
        return self.returncode


def _install_fake_exec(
    monkeypatch: pytest.MonkeyPatch, proc: _FakeProc
) -> dict[str, Any]:
    """Swap ``asyncio.create_subprocess_exec`` for a stub that yields ``proc``.

    Returns a dict captured by the stub so the test can assert on the
    argv that would have been handed to the CLI.
    """
    captured: dict[str, Any] = {}

    async def fake_exec(*args: Any, **kwargs: Any) -> _FakeProc:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    return captured


def _cli_json(
    *,
    result: str = "hello",
    usage: dict[str, Any] | None = None,
    model_usage: dict[str, dict[str, Any]] | None = None,
    is_error: bool = False,
) -> bytes:
    payload: dict[str, Any] = {
        "type": "result",
        "subtype": "success",
        "is_error": is_error,
        "stop_reason": "end_turn",
        "result": result,
    }
    if usage is not None:
        payload["usage"] = usage
    if model_usage is not None:
        payload["modelUsage"] = model_usage
    return json.dumps(payload).encode("utf-8")


# ---------------------------------------------------------------------------
# AC-1 / AC-2 — happy path with modelUsage + pricing
# ---------------------------------------------------------------------------


async def test_complete_returns_text_and_token_usage_with_sub_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-1 + AC-2: primary TokenUsage + sub_models + cost from pricing."""
    stdout = _cli_json(
        result="4",
        usage={
            "input_tokens": 6,
            "output_tokens": 6,
            "cache_creation_input_tokens": 13737,
            "cache_read_input_tokens": 0,
        },
        model_usage={
            "claude-opus-4-7": {
                "inputTokens": 6,
                "outputTokens": 6,
                "cacheReadInputTokens": 0,
                "cacheCreationInputTokens": 13737,
            },
            "claude-haiku-4-5-20251001": {
                "inputTokens": 353,
                "outputTokens": 13,
                "cacheReadInputTokens": 0,
                "cacheCreationInputTokens": 0,
            },
        },
    )
    _install_fake_exec(monkeypatch, _FakeProc(stdout=stdout))

    driver = ClaudeCodeSubprocess(
        route=ClaudeCodeRoute(cli_model_flag="opus"),
        per_call_timeout_s=120,
        pricing=PRICING,
    )

    text, usage = await driver.complete(
        system=None,
        messages=[{"role": "user", "content": "what is 2+2?"}],
    )

    assert text == "4"
    assert isinstance(usage, TokenUsage)
    # Primary entry: opus (matches cli_model_flag "opus" via substring).
    assert usage.model == "claude-opus-4-7"
    assert usage.input_tokens == 6
    assert usage.output_tokens == 6
    assert usage.cache_write_tokens == 13737
    # Cost math: 6 tok input at $15/Mtok + 6 tok output at $75/Mtok +
    # 13737 cache_write at $18.75/Mtok.
    expected_primary_cost = (
        (6 / 1_000_000) * 15.0
        + (6 / 1_000_000) * 75.0
        + (13737 / 1_000_000) * 18.75
    )
    assert usage.cost_usd == pytest.approx(expected_primary_cost)

    # Sub-model: haiku auto-classifier, priced at $1/$5 per Mtok.
    assert len(usage.sub_models) == 1
    sub = usage.sub_models[0]
    assert sub.model == "claude-haiku-4-5-20251001"
    assert sub.input_tokens == 353
    assert sub.output_tokens == 13
    expected_sub_cost = (353 / 1_000_000) * 1.0 + (13 / 1_000_000) * 5.0
    assert sub.cost_usd == pytest.approx(expected_sub_cost)


async def test_complete_forwards_system_prompt_and_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``system`` is forwarded via ``--system-prompt``; messages via stdin."""
    proc = _FakeProc(
        stdout=_cli_json(
            result="ok",
            usage={"input_tokens": 1, "output_tokens": 1},
        )
    )
    captured = _install_fake_exec(monkeypatch, proc)

    driver = ClaudeCodeSubprocess(
        route=ClaudeCodeRoute(cli_model_flag="haiku"),
        per_call_timeout_s=60,
        pricing=PRICING,
    )
    await driver.complete(
        system="Be terse.",
        messages=[{"role": "user", "content": "hello"}],
    )

    argv = list(captured["args"])
    assert argv[0] == "claude"
    assert "--print" in argv
    assert argv[argv.index("--output-format") + 1] == "json"
    assert argv[argv.index("--model") + 1] == "haiku"
    assert argv[argv.index("--tools") + 1] == ""
    assert "--no-session-persistence" in argv
    assert argv[argv.index("--system-prompt") + 1] == "Be terse."
    assert proc.received_stdin == b"hello"


async def test_complete_omits_system_prompt_flag_when_system_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No ``--system-prompt`` flag when the caller passes ``system=None``."""
    proc = _FakeProc(
        stdout=_cli_json(result="ok", usage={"input_tokens": 1, "output_tokens": 1})
    )
    captured = _install_fake_exec(monkeypatch, proc)

    driver = ClaudeCodeSubprocess(
        route=ClaudeCodeRoute(cli_model_flag="haiku"),
        per_call_timeout_s=60,
        pricing=PRICING,
    )
    await driver.complete(system=None, messages=[{"role": "user", "content": "hi"}])

    assert "--system-prompt" not in captured["args"]


async def test_complete_flattens_multiple_messages_into_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Multi-turn message lists collapse to a single stdin blob."""
    proc = _FakeProc(
        stdout=_cli_json(result="ok", usage={"input_tokens": 1, "output_tokens": 1})
    )
    _install_fake_exec(monkeypatch, proc)

    driver = ClaudeCodeSubprocess(
        route=ClaudeCodeRoute(cli_model_flag="haiku"),
        per_call_timeout_s=60,
        pricing=PRICING,
    )
    await driver.complete(
        system=None,
        messages=[
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "ack"},
            {"role": "user", "content": "second"},
        ],
    )
    assert proc.received_stdin == b"first\n\nack\n\nsecond"


async def test_complete_falls_back_to_top_level_usage_when_modelusage_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Older CLI versions may omit ``modelUsage``; driver still emits TokenUsage."""
    stdout = _cli_json(
        result="4",
        usage={"input_tokens": 10, "output_tokens": 20},
        model_usage=None,
    )
    _install_fake_exec(monkeypatch, _FakeProc(stdout=stdout))

    driver = ClaudeCodeSubprocess(
        route=ClaudeCodeRoute(cli_model_flag="haiku"),
        per_call_timeout_s=60,
        pricing=PRICING,
    )
    _text, usage = await driver.complete(
        system=None, messages=[{"role": "user", "content": "hi"}]
    )
    # No modelUsage → model defaults to the cli_model_flag alias; pricing
    # lookup misses (alias not in table) → cost_usd stays at 0.0.
    assert usage.model == "haiku"
    assert usage.input_tokens == 10
    assert usage.output_tokens == 20
    assert usage.sub_models == []
    assert usage.cost_usd == 0.0


async def test_complete_handles_full_model_id_in_cli_model_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``cli_model_flag`` set to a full model ID resolves to an exact match."""
    stdout = _cli_json(
        result="ok",
        usage={"input_tokens": 6, "output_tokens": 6},
        model_usage={
            "claude-opus-4-7": {
                "inputTokens": 6,
                "outputTokens": 6,
                "cacheReadInputTokens": 0,
                "cacheCreationInputTokens": 0,
            }
        },
    )
    _install_fake_exec(monkeypatch, _FakeProc(stdout=stdout))

    driver = ClaudeCodeSubprocess(
        route=ClaudeCodeRoute(cli_model_flag="claude-opus-4-7"),
        per_call_timeout_s=60,
        pricing=PRICING,
    )
    _text, usage = await driver.complete(
        system=None, messages=[{"role": "user", "content": "hi"}]
    )
    assert usage.model == "claude-opus-4-7"
    assert usage.sub_models == []


# ---------------------------------------------------------------------------
# AC-3 — timeout + non-zero exit routing via classify()
# ---------------------------------------------------------------------------


async def test_timeout_raises_timeoutexpired_bucketed_transient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-3: per-call timeout raises ``subprocess.TimeoutExpired``."""
    proc = _FakeProc(communicate_delay_s=5.0, stdout=b"", stderr=b"")
    _install_fake_exec(monkeypatch, proc)

    driver = ClaudeCodeSubprocess(
        route=ClaudeCodeRoute(cli_model_flag="haiku"),
        per_call_timeout_s=0,  # 0-second window → wait_for fires immediately
        pricing=PRICING,
    )
    with pytest.raises(subprocess.TimeoutExpired) as excinfo:
        await driver.complete(system=None, messages=[{"role": "user", "content": "hi"}])
    assert classify(excinfo.value) is RetryableTransient


async def test_non_zero_exit_raises_calledprocesserror_bucketed_nonretryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-3: non-zero exit raises ``subprocess.CalledProcessError``."""
    _install_fake_exec(
        monkeypatch,
        _FakeProc(
            stdout=b"",
            stderr=b"error: unknown option '--max-tokens'",
            returncode=1,
        ),
    )
    driver = ClaudeCodeSubprocess(
        route=ClaudeCodeRoute(cli_model_flag="haiku"),
        per_call_timeout_s=60,
        pricing=PRICING,
    )
    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        await driver.complete(system=None, messages=[{"role": "user", "content": "hi"}])
    assert classify(excinfo.value) is NonRetryable
    assert excinfo.value.returncode == 1
    assert b"unknown option" in (excinfo.value.stderr or b"")


async def test_is_error_true_raises_calledprocesserror_bucketed_nonretryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI responses with ``is_error: true`` are treated as NonRetryable.

    Per M1 Task 13 spike: the CLI's ``is_error`` field is the truth-
    bearing signal even when the exit code is 0 on some failure paths.
    """
    stdout = _cli_json(
        result="There's an issue with the selected model...",
        usage={"input_tokens": 1, "output_tokens": 1},
        is_error=True,
    )
    _install_fake_exec(monkeypatch, _FakeProc(stdout=stdout, returncode=0))

    driver = ClaudeCodeSubprocess(
        route=ClaudeCodeRoute(cli_model_flag="haiku"),
        per_call_timeout_s=60,
        pricing=PRICING,
    )
    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        await driver.complete(system=None, messages=[{"role": "user", "content": "hi"}])
    assert classify(excinfo.value) is NonRetryable


# ---------------------------------------------------------------------------
# AC-4 — no ANTHROPIC_API_KEY / anthropic-SDK reference (KDR-003)
# ---------------------------------------------------------------------------


def test_no_anthropic_api_key_reference_in_driver_source() -> None:
    """AC-4 (KDR-003): the driver must never read ``ANTHROPIC_API_KEY``."""
    source = Path(__file__).resolve().parents[3] / (
        "ai_workflows/primitives/llm/claude_code.py"
    )
    body = source.read_text()
    assert "ANTHROPIC_API_KEY" not in body
    assert "from anthropic" not in body
    assert "import anthropic" not in body


# ---------------------------------------------------------------------------
# response_format parity
# ---------------------------------------------------------------------------


async def test_response_format_is_accepted_and_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``response_format`` is accepted for API parity but not forwarded."""
    from pydantic import BaseModel

    class Answer(BaseModel):
        value: str

    proc = _FakeProc(
        stdout=_cli_json(
            result='{"value": "ok"}',
            usage={"input_tokens": 1, "output_tokens": 1},
        )
    )
    captured = _install_fake_exec(monkeypatch, proc)

    driver = ClaudeCodeSubprocess(
        route=ClaudeCodeRoute(cli_model_flag="haiku"),
        per_call_timeout_s=60,
        pricing=PRICING,
    )
    text, _usage = await driver.complete(
        system=None,
        messages=[{"role": "user", "content": "hi"}],
        response_format=Answer,
    )
    # Text is returned verbatim; response_format does not influence argv.
    assert text == '{"value": "ok"}'
    argv = list(captured["args"])
    assert "--response-format" not in argv
    assert "--output-schema" not in argv
