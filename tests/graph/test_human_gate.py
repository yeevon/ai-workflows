"""Tests for ``ai_workflows.graph.human_gate`` (M2 Task 05).

Cover every AC from
[task_05_human_gate.md](../../design_docs/phases/milestone_2_graph/task_05_human_gate.md):
gate-prompt / response round-trip through ``Storage``, ``strict_review=True``
disables timeout enforcement, resumption writes the response key into
state, and one-interrupt-per-execution. A full ``SQLiteStorage`` round
trip is included to pin the gate-log persistence AC against the M1
Task 05 protocol, not just the in-memory stub.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict
from unittest.mock import patch

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from ai_workflows.graph.human_gate import human_gate
from ai_workflows.primitives.storage import SQLiteStorage


class _State(TypedDict, total=False):
    run_id: str
    payload: str
    gate_demo_response: str
    gate_strict_response: str
    gate_nowait_response: str
    gate_solo_response: str
    gate_resume_response: str
    gate_full_response: str


class _StubStorage:
    """In-memory fake mirroring ``StorageBackend``'s gate methods."""

    def __init__(self) -> None:
        self.record_gate_calls: list[tuple[str, str, str, bool]] = []
        self.record_gate_response_calls: list[tuple[str, str, str]] = []

    async def record_gate(
        self,
        run_id: str,
        gate_id: str,
        prompt: str,
        strict_review: bool,
    ) -> None:
        self.record_gate_calls.append((run_id, gate_id, prompt, strict_review))

    async def record_gate_response(
        self,
        run_id: str,
        gate_id: str,
        response: str,
    ) -> None:
        self.record_gate_response_calls.append((run_id, gate_id, response))


def _build_graph(node: Any) -> Any:
    """Compile a one-node graph with an in-memory checkpointer."""
    g: StateGraph = StateGraph(_State)
    g.add_node("gate", node)
    g.add_edge(START, "gate")
    g.add_edge("gate", END)
    return g.compile(checkpointer=MemorySaver())


async def test_gate_round_trips_prompt_and_response_through_storage() -> None:
    storage = _StubStorage()
    node = human_gate(
        gate_id="demo",
        prompt_fn=lambda s: f"approve payload: {s['payload']}",
    )
    app = _build_graph(node)
    cfg = {"configurable": {"thread_id": "r1", "storage": storage}}

    paused = await app.ainvoke({"run_id": "r1", "payload": "x"}, cfg)
    assert "__interrupt__" in paused
    assert storage.record_gate_calls == [("r1", "demo", "approve payload: x", False)]
    assert storage.record_gate_response_calls == []

    final = await app.ainvoke(Command(resume="approved"), cfg)

    assert final["gate_demo_response"] == "approved"
    assert ("r1", "demo", "approved") in storage.record_gate_response_calls


async def test_record_gate_preserves_strict_review_flag() -> None:
    storage = _StubStorage()
    node = human_gate(
        gate_id="strict",
        prompt_fn=lambda s: "review",
        strict_review=True,
    )
    app = _build_graph(node)
    cfg = {"configurable": {"thread_id": "r2", "storage": storage}}

    await app.ainvoke({"run_id": "r2"}, cfg)

    assert storage.record_gate_calls, "record_gate was never called"
    assert all(call[3] is True for call in storage.record_gate_calls)


async def test_strict_review_zeros_out_timeout_in_interrupt_payload() -> None:
    """``strict_review=True`` must blank the timeout fields even if a
    short ``timeout_s`` is passed — that is how the factory signals to
    the surface that no timer should fire."""
    storage = _StubStorage()
    node = human_gate(
        gate_id="nowait",
        prompt_fn=lambda s: "review",
        strict_review=True,
        timeout_s=1,
        default_response_on_timeout="abort",
    )

    captured: dict[str, Any] = {}

    def _fake_interrupt(payload: Any) -> str:
        captured["payload"] = payload
        return "approved"

    with patch("ai_workflows.graph.human_gate.interrupt", _fake_interrupt):
        app = _build_graph(node)
        cfg = {"configurable": {"thread_id": "r3", "storage": storage}}
        await app.ainvoke({"run_id": "r3"}, cfg)

    assert captured["payload"]["strict_review"] is True
    assert captured["payload"]["timeout_s"] is None
    assert captured["payload"]["default_response_on_timeout"] is None


async def test_non_strict_review_forwards_timeout_fields() -> None:
    """Complement of the strict-review test: the timeout config must be
    visible to the surface when the gate isn't strict."""
    storage = _StubStorage()
    node = human_gate(
        gate_id="nowait",
        prompt_fn=lambda s: "review",
        strict_review=False,
        timeout_s=42,
        default_response_on_timeout="deny",
    )

    captured: dict[str, Any] = {}

    def _fake_interrupt(payload: Any) -> str:
        captured["payload"] = payload
        return "ok"

    with patch("ai_workflows.graph.human_gate.interrupt", _fake_interrupt):
        app = _build_graph(node)
        cfg = {"configurable": {"thread_id": "r3b", "storage": storage}}
        await app.ainvoke({"run_id": "r3b"}, cfg)

    assert captured["payload"]["strict_review"] is False
    assert captured["payload"]["timeout_s"] == 42
    assert captured["payload"]["default_response_on_timeout"] == "deny"


async def test_interrupt_is_invoked_exactly_once_per_execution() -> None:
    """A single resume path must pause exactly once."""
    storage = _StubStorage()
    node = human_gate(
        gate_id="solo",
        prompt_fn=lambda s: "review",
    )

    count = 0

    def _count_interrupt(payload: Any) -> str:
        nonlocal count
        count += 1
        return "approved"

    with patch("ai_workflows.graph.human_gate.interrupt", _count_interrupt):
        app = _build_graph(node)
        cfg = {"configurable": {"thread_id": "r4", "storage": storage}}
        await app.ainvoke({"run_id": "r4"}, cfg)

    assert count == 1


async def test_resumption_writes_response_key_into_state() -> None:
    storage = _StubStorage()
    node = human_gate(
        gate_id="resume",
        prompt_fn=lambda s: "review",
    )
    app = _build_graph(node)
    cfg = {"configurable": {"thread_id": "r5", "storage": storage}}

    paused = await app.ainvoke({"run_id": "r5"}, cfg)
    assert "gate_resume_response" not in paused

    final = await app.ainvoke(Command(resume="rejected"), cfg)

    assert final["gate_resume_response"] == "rejected"


async def test_full_sqlite_storage_round_trip(tmp_path: Path) -> None:
    """Integration check: gate row lands in SQLite under the real
    ``StorageBackend`` protocol so AC-1 is pinned against the live
    schema, not just the stub."""
    storage = await SQLiteStorage.open(tmp_path / "gates.db")
    await storage.create_run("r6", "wf", None)

    node = human_gate(
        gate_id="full",
        prompt_fn=lambda s: "review this",
        strict_review=False,
    )
    app = _build_graph(node)
    cfg = {"configurable": {"thread_id": "r6", "storage": storage}}

    await app.ainvoke({"run_id": "r6"}, cfg)
    final = await app.ainvoke(Command(resume="approved"), cfg)

    assert final["gate_full_response"] == "approved"
    row = await storage.get_gate("r6", "full")
    assert row is not None
    assert row["prompt"] == "review this"
    assert row["response"] == "approved"
    assert row["strict_review"] == 0
