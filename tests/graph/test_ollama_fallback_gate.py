"""Tests for M8 Task 03 — :mod:`ai_workflows.graph.ollama_fallback_gate`.

Pins the 5 tests called out by the task spec (prompt rendering,
strict-review payload, response parsing, unknown-response default,
storage round-trip) plus two parse-coverage sub-tests for the other two
canonical values.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict
from unittest.mock import patch

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from ai_workflows.graph import FallbackChoice, build_ollama_fallback_gate
from ai_workflows.graph.ollama_fallback_gate import (
    FALLBACK_DECISION_STATE_KEY,
    FALLBACK_GATE_ID,
    parse_fallback_choice,
    render_ollama_fallback_prompt,
)


class _State(TypedDict, total=False):
    run_id: str
    _ollama_fallback_reason: str
    _ollama_fallback_count: int
    ollama_fallback_decision: FallbackChoice
    gate_ollama_fallback_response: str


class _StubStorage:
    def __init__(self) -> None:
        self.record_gate_calls: list[tuple[str, str, str, bool]] = []
        self.record_gate_response_calls: list[tuple[str, str, str]] = []

    async def record_gate(
        self, run_id: str, gate_id: str, prompt: str, strict_review: bool
    ) -> None:
        self.record_gate_calls.append((run_id, gate_id, prompt, strict_review))

    async def record_gate_response(
        self, run_id: str, gate_id: str, response: str
    ) -> None:
        self.record_gate_response_calls.append((run_id, gate_id, response))


def _build_graph(node: Any) -> Any:
    g: StateGraph = StateGraph(_State)
    g.add_node("gate", node)
    g.add_edge(START, "gate")
    g.add_edge("gate", END)
    return g.compile(checkpointer=MemorySaver())


def test_gate_prompt_renders_tier_reason_and_fallback() -> None:
    state: _State = {
        "run_id": "r1",
        "_ollama_fallback_reason": "timeout",
        "_ollama_fallback_count": 3,
    }

    rendered = render_ollama_fallback_prompt(
        state, tier_name="local_coder", fallback_tier="gemini_flash"
    )

    assert "local_coder" in rendered
    assert "timeout" in rendered
    assert "3" in rendered
    assert "gemini_flash" in rendered
    assert "[retry]" in rendered
    assert "[fallback]" in rendered
    assert "[abort]" in rendered


async def test_gate_is_strict_review() -> None:
    storage = _StubStorage()
    node = build_ollama_fallback_gate(
        tier_name="local_coder", fallback_tier="gemini_flash"
    )

    captured: dict[str, Any] = {}

    def _fake_interrupt(payload: Any) -> str:
        captured["payload"] = payload
        return "retry"

    with patch(
        "ai_workflows.graph.ollama_fallback_gate.interrupt", _fake_interrupt
    ):
        app = _build_graph(node)
        cfg = {"configurable": {"thread_id": "r1", "storage": storage}}
        await app.ainvoke(
            {
                "run_id": "r1",
                "_ollama_fallback_reason": "timeout",
                "_ollama_fallback_count": 3,
            },
            cfg,
        )

    assert captured["payload"]["strict_review"] is True
    assert captured["payload"]["timeout_s"] is None
    assert captured["payload"]["default_response_on_timeout"] is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("retry", FallbackChoice.RETRY),
        ("RETRY", FallbackChoice.RETRY),
        ("  Retry  ", FallbackChoice.RETRY),
        ("fallback", FallbackChoice.FALLBACK),
        ("FALLBACK", FallbackChoice.FALLBACK),
        ("abort", FallbackChoice.ABORT),
        ("ABORT", FallbackChoice.ABORT),
    ],
)
def test_response_parses_canonical_values(
    raw: str, expected: FallbackChoice
) -> None:
    assert parse_fallback_choice(raw) is expected


def test_unknown_response_defaults_to_retry(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="ai_workflows.graph.ollama_fallback_gate"):
        choice = parse_fallback_choice("maybe?")

    assert choice is FallbackChoice.RETRY
    assert any(
        "ollama_fallback_unknown_response" in record.getMessage()
        for record in caplog.records
    )


async def test_gate_persists_via_storage_protocol() -> None:
    storage = _StubStorage()
    node = build_ollama_fallback_gate(
        tier_name="local_coder", fallback_tier="gemini_flash"
    )
    app = _build_graph(node)
    cfg = {"configurable": {"thread_id": "r1", "storage": storage}}

    paused = await app.ainvoke(
        {
            "run_id": "r1",
            "_ollama_fallback_reason": "connection_refused",
            "_ollama_fallback_count": 3,
        },
        cfg,
    )
    assert "__interrupt__" in paused
    assert len(storage.record_gate_calls) == 1
    call = storage.record_gate_calls[0]
    assert call[0] == "r1"
    assert call[1] == FALLBACK_GATE_ID
    assert "local_coder" in call[2]
    assert "connection_refused" in call[2]
    assert call[3] is True
    assert storage.record_gate_response_calls == []

    final = await app.ainvoke(Command(resume="FALLBACK"), cfg)

    assert final[FALLBACK_DECISION_STATE_KEY] is FallbackChoice.FALLBACK
    assert storage.record_gate_response_calls == [
        ("r1", FALLBACK_GATE_ID, FallbackChoice.FALLBACK.value)
    ]


async def test_unknown_resume_produces_retry_decision() -> None:
    storage = _StubStorage()
    node = build_ollama_fallback_gate(
        tier_name="local_coder", fallback_tier="gemini_flash"
    )
    app = _build_graph(node)
    cfg = {"configurable": {"thread_id": "r2", "storage": storage}}

    await app.ainvoke(
        {
            "run_id": "r2",
            "_ollama_fallback_reason": "timeout",
            "_ollama_fallback_count": 5,
        },
        cfg,
    )
    final = await app.ainvoke(Command(resume="what"), cfg)

    assert final[FALLBACK_DECISION_STATE_KEY] is FallbackChoice.RETRY
    # persisted value is the enum value, not the user's raw typo
    assert storage.record_gate_response_calls == [
        ("r2", FALLBACK_GATE_ID, FallbackChoice.RETRY.value)
    ]
