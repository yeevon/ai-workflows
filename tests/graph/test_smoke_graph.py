"""Smoke-test LangGraph for M2 Task 08.

Wires every M2 graph-layer adapter together end-to-end:

    START → llm (tiered_node + error_handler wrapper)
         → decide_after_llm (retrying_edge)
         → validator (validator_node + error_handler wrapper)
         → decide_after_validator (retrying_edge)
         → gate (human_gate)
         → END

The graph is invoked under LangGraph's ``AsyncSqliteSaver`` (built via
:func:`build_async_checkpointer` — required because every M2 node
adapter is async and LangGraph rejects ``.ainvoke`` against the sync
:class:`SqliteSaver`), paused at :func:`interrupt`, and resumed with
``Command(resume=...)`` — exactly the §4.2 / §8.3 shape the
architecture calls out for KDR-009.

Scope
-----
* Happy path — LLM returns valid JSON, validator parses, gate pauses
  and resumes, graph terminates with cost-tracker totals non-zero.
* SqliteSaver DB row exists after the interrupt (filesystem + ``conn``
  probe so we verify LangGraph actually persisted to disk, not just
  memory).
* Carry-over M2-T07-ISS-01 — raised
  :class:`RetryableTransient` from the LLM node lands in
  ``state['last_exception']`` with ``state['_retry_counts']['llm']``
  incremented; on the successful next pass the
  :func:`tiered_node` clears ``last_exception`` to ``None`` so
  ``retrying_edge`` does not re-fire on stale data;
  ``state['_non_retryable_failures']`` stays at ``0`` through a
  transient burst.
* Exhausted retry budget routes through ``on_terminal`` — pins the
  retry-edge boundary against the wrapper's counters.

Every LLM call is stubbed at the adapter level (``_StubLiteLLMAdapter``)
so no real API hits fire. The SqliteSaver database is pinned to a
``tmp_path`` location per test so parallel runs do not collide.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypedDict

import litellm
import pytest
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from pydantic import BaseModel

from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.graph.checkpointer import build_async_checkpointer
from ai_workflows.graph.cost_callback import CostTrackingCallback
from ai_workflows.graph.error_handler import wrap_with_error_handler
from ai_workflows.graph.human_gate import human_gate
from ai_workflows.graph.retrying_edge import retrying_edge
from ai_workflows.graph.tiered_node import tiered_node
from ai_workflows.graph.validator_node import validator_node
from ai_workflows.primitives.cost import CostTracker, TokenUsage
from ai_workflows.primitives.retry import RetryPolicy
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig

# ---------------------------------------------------------------------------
# Graph state + schema
# ---------------------------------------------------------------------------


class Answer(BaseModel):
    """Schema the validator parses the LLM's raw text against."""

    text: str


class SmokeState(TypedDict, total=False):
    """State carried through the smoke graph.

    Keys under this schema:

    * ``run_id`` — thread / run identifier.
    * ``llm_output`` — raw text from the LLM tier node.
    * ``llm_output_revision_hint`` — cleared by the validator on success.
    * ``answer`` — validated ``Answer`` instance.
    * ``gate_review_response`` — human response captured by the gate.
    * ``last_exception`` — the T07 retry-edge classified-exception slot.
    * ``_retry_counts`` — per-node attempt counter (KDR-006).
    * ``_non_retryable_failures`` — run-scoped :class:`NonRetryable` count.
    """

    run_id: str
    llm_output: str
    llm_output_revision_hint: Any
    answer: Answer
    gate_review_response: str
    last_exception: Any
    _retry_counts: dict[str, int]
    _non_retryable_failures: int


# ---------------------------------------------------------------------------
# Stub LiteLLM adapter — controls failure / success without hitting a real API
# ---------------------------------------------------------------------------


class _StubLiteLLMAdapter:
    """Adapter-shaped stub with a class-level script of responses.

    ``script`` is a list of ``Exception`` instances or ``(text, cost)``
    tuples. Each ``complete`` call pops the head of the list: an
    :class:`Exception` is re-raised, a tuple is returned as the provider
    output. Class-level so ``monkeypatch.setattr`` on the module swaps
    in the stub for every instantiation.
    """

    script: list[Any] = []
    call_count: int = 0

    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        self.route = route

    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict],
        response_format: Any = None,
    ) -> tuple[str, TokenUsage]:
        _StubLiteLLMAdapter.call_count += 1
        if not _StubLiteLLMAdapter.script:
            raise AssertionError("stub script exhausted")
        head = _StubLiteLLMAdapter.script.pop(0)
        if isinstance(head, BaseException):
            raise head
        text, cost = head
        return text, TokenUsage(
            input_tokens=5,
            output_tokens=7,
            cost_usd=cost,
            model=self.route.model,
        )

    @classmethod
    def reset(cls) -> None:
        cls.script = []
        cls.call_count = 0


@pytest.fixture(autouse=True)
def _reset_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install the stub adapter and clear the script on every test."""
    _StubLiteLLMAdapter.reset()
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _StubLiteLLMAdapter)


# ---------------------------------------------------------------------------
# Graph factory + config builder
# ---------------------------------------------------------------------------


def _prompt_fn(_state: Mapping[str, Any]) -> tuple[str | None, list[dict]]:
    return ("sys", [{"role": "user", "content": "respond as JSON Answer"}])


def _tier_registry() -> dict[str, TierConfig]:
    return {
        "planner": TierConfig(
            name="planner",
            route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
            max_concurrency=1,
            per_call_timeout_s=30,
        )
    }


def _build_graph(checkpointer: Any) -> Any:
    """Compile the M2 smoke graph under the supplied checkpointer."""
    llm = wrap_with_error_handler(
        tiered_node(tier="planner", prompt_fn=_prompt_fn, node_name="llm"),
        node_name="llm",
    )
    validator = wrap_with_error_handler(
        validator_node(
            schema=Answer,
            input_key="llm_output",
            output_key="answer",
            node_name="validator",
        ),
        node_name="validator",
    )
    gate = human_gate(
        gate_id="review",
        prompt_fn=lambda s: f"approve answer: {s['answer'].text}",
    )

    policy = RetryPolicy(max_transient_attempts=3, max_semantic_attempts=3)
    decide_after_llm = retrying_edge(
        on_transient="llm",
        on_semantic="llm",
        on_terminal="validator",
        policy=policy,
    )
    decide_after_validator = retrying_edge(
        on_transient="llm",
        on_semantic="llm",
        on_terminal="gate",
        policy=policy,
    )

    g: StateGraph = StateGraph(SmokeState)
    g.add_node("llm", llm)
    g.add_node("validator", validator)
    g.add_node("gate", gate)
    g.add_edge(START, "llm")
    g.add_conditional_edges("llm", decide_after_llm, ["llm", "validator"])
    g.add_conditional_edges(
        "validator", decide_after_validator, ["llm", "gate"]
    )
    g.add_edge("gate", END)

    return g.compile(checkpointer=checkpointer)


async def _build_config(
    tmp_path: Path, run_id: str, budget_cap_usd: float | None = None
) -> tuple[dict[str, Any], CostTracker, SQLiteStorage]:
    """Build a LangGraph config with storage + cost callback attached."""
    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await storage.create_run(run_id, "smoke", budget_cap_usd)
    tracker = CostTracker()
    callback = CostTrackingCallback(
        cost_tracker=tracker, budget_cap_usd=budget_cap_usd
    )
    cfg = {
        "configurable": {
            "thread_id": run_id,
            "run_id": run_id,
            "tier_registry": _tier_registry(),
            "cost_callback": callback,
            "storage": storage,
        }
    }
    return cfg, tracker, storage


# ---------------------------------------------------------------------------
# AC — happy path runs to interrupt, checkpoint lands on disk, resume completes
# ---------------------------------------------------------------------------


async def test_smoke_graph_runs_to_interrupt_and_checkpoints(
    tmp_path: Path,
) -> None:
    """AC-1 + AC-2: pause at ``HumanGate``; the row exists on disk."""
    checkpoint_path = tmp_path / "checkpoints.sqlite"
    checkpointer = await build_async_checkpointer(checkpoint_path)
    app = _build_graph(checkpointer)

    _StubLiteLLMAdapter.script = [('{"text": "hello"}', 0.0005)]
    cfg, tracker, storage = await _build_config(tmp_path, "run-happy")

    try:
        paused = await app.ainvoke({"run_id": "run-happy"}, cfg)
        assert "__interrupt__" in paused

        # AC-1 — checkpoint file exists on disk at the path we asked for.
        assert checkpoint_path.exists()

        # AC-2 — a row in the SqliteSaver `checkpoints` table names this
        # thread_id so a resume can rehydrate it.
        probe = sqlite3.connect(str(checkpoint_path))
        try:
            row = probe.execute(
                "SELECT thread_id FROM checkpoints WHERE thread_id = ?",
                ("run-happy",),
            ).fetchone()
        finally:
            probe.close()
        assert row is not None, "no checkpoint row written for thread_id"

        # Validator ran before the gate, so the parsed Answer is on the
        # paused state (AC structural sanity for KDR-004 pairing).
        assert paused["answer"].text == "hello"
    finally:
        await checkpointer.conn.close()
        # Storage writes are under an asyncio.Lock; release the handle.
        del storage


async def test_smoke_graph_resumes_after_interrupt_and_completes(
    tmp_path: Path,
) -> None:
    """AC: ``Command(resume=...)`` rehydrates from the checkpoint and finishes."""
    checkpoint_path = tmp_path / "checkpoints.sqlite"
    checkpointer = await build_async_checkpointer(checkpoint_path)
    app = _build_graph(checkpointer)

    _StubLiteLLMAdapter.script = [('{"text": "pong"}', 0.0004)]
    cfg, tracker, storage = await _build_config(tmp_path, "run-resume")

    try:
        await app.ainvoke({"run_id": "run-resume"}, cfg)
        final = await app.ainvoke(Command(resume="approved"), cfg)

        assert final["gate_review_response"] == "approved"
        assert final["answer"].text == "pong"

        # Gate persistence round-tripped to Storage (sanity, not a new AC).
        gate_row = await storage.get_gate("run-resume", "review")
        assert gate_row is not None
        assert gate_row["response"] == "approved"
    finally:
        await checkpointer.conn.close()
        del storage


async def test_smoke_graph_cost_tracker_totals_non_zero(tmp_path: Path) -> None:
    """AC: ``CostTracker`` totals reflect the smoke run (sum > 0)."""
    checkpointer = await build_async_checkpointer(tmp_path / "checkpoints.sqlite")
    app = _build_graph(checkpointer)

    _StubLiteLLMAdapter.script = [('{"text": "cost"}', 0.0017)]
    cfg, tracker, storage = await _build_config(tmp_path, "run-cost")

    try:
        await app.ainvoke({"run_id": "run-cost"}, cfg)
        await app.ainvoke(Command(resume="ok"), cfg)

        total = tracker.total("run-cost")
        assert total > 0
        assert total == pytest.approx(0.0017)
    finally:
        await checkpointer.conn.close()
        del storage


# ---------------------------------------------------------------------------
# Carry-over M2-T07-ISS-01 — retry loop exercised end-to-end
# ---------------------------------------------------------------------------


async def test_transient_retry_routes_correctly_and_clears_on_success(
    tmp_path: Path,
) -> None:
    """Carry-over: bucket exception → state update → retry → cleared on success.

    Pins every piece the T07 audit asked T08 to exercise:

    * A ``RetryableTransient`` raised from ``TieredNode`` lands in
      ``state['last_exception']`` (via ``wrap_with_error_handler``).
    * ``state['_retry_counts']['llm']`` increments from 0 → 1.
    * ``state['_non_retryable_failures']`` stays at 0 for a transient.
    * ``retrying_edge`` routes the retry back to ``llm``.
    * On the successful next pass ``tiered_node`` returns
      ``last_exception=None`` so the edge does not re-fire on stale
      data — ``retrying_edge`` then routes forward to ``validator`` →
      ``gate``.
    """
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = _build_graph(checkpointer)

    _StubLiteLLMAdapter.script = [
        litellm.RateLimitError("429", llm_provider="gemini", model="g"),
        ('{"text": "second-try"}', 0.0009),
    ]
    cfg, tracker, storage = await _build_config(tmp_path, "run-retry")

    try:
        paused = await app.ainvoke({"run_id": "run-retry"}, cfg)
        final = await app.ainvoke(Command(resume="approved"), cfg)

        # LLM was invoked twice — once to fail, once to succeed.
        assert _StubLiteLLMAdapter.call_count == 2

        # Retry-counter bumped exactly once, failure counter stayed at 0.
        assert paused["_retry_counts"] == {"llm": 1}
        assert paused.get("_non_retryable_failures", 0) == 0

        # Successful pass cleared last_exception so the edge forwards.
        assert paused.get("last_exception") is None
        assert paused["answer"].text == "second-try"

        # Gate resumed cleanly.
        assert final["gate_review_response"] == "approved"

        # Cost totals reflect the successful call (the failure recorded 0).
        assert tracker.total("run-retry") == pytest.approx(0.0009)
    finally:
        await checkpointer.conn.close()
        del storage


async def test_exhausted_transient_budget_routes_to_on_terminal(
    tmp_path: Path,
) -> None:
    """Retry budget exhausted → ``retrying_edge`` routes forward, not looping.

    The edge treats ``on_terminal`` as "continue forward" in the smoke
    graph wiring (``llm → validator``), so once ``_retry_counts['llm']``
    hits ``max_transient_attempts`` the retry edge stops self-looping
    and lets the validator raise against the missing ``llm_output``.
    We assert the call count is capped at ``max_transient_attempts``
    so the retry budget isn't accidentally infinite.
    """
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = _build_graph(checkpointer)

    _StubLiteLLMAdapter.script = [
        litellm.RateLimitError("429", llm_provider="gemini", model="g"),
        litellm.RateLimitError("429", llm_provider="gemini", model="g"),
        litellm.RateLimitError("429", llm_provider="gemini", model="g"),
        litellm.RateLimitError("429", llm_provider="gemini", model="g"),
    ]
    cfg, tracker, storage = await _build_config(tmp_path, "run-exhaust")

    try:
        with pytest.raises(KeyError):
            # Once the retry budget is exhausted the validator runs
            # without an ``llm_output`` — that KeyError is the
            # "fail-forward" signal T07 documents. The retry loop itself
            # is hard-capped, which is what we actually assert.
            await app.ainvoke({"run_id": "run-exhaust"}, cfg)

        assert _StubLiteLLMAdapter.call_count == 3  # max_transient_attempts
    finally:
        await checkpointer.conn.close()
        del storage
