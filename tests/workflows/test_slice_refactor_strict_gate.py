"""Tests for the T05 strict-review ``HumanGate`` wiring.

Covers the T05 acceptance criteria from
``design_docs/phases/milestone_6_slice_refactor/task_05_strict_review_gate.md``:

* Gate is wired between ``aggregate`` and ``apply`` with
  ``strict_review=True`` (structural + payload-shape assertions).
* Approve path — resuming with ``"approved"`` routes through the T05
  ``apply`` stub and lands at END.
* Reject path — resuming with ``"rejected"`` short-circuits to END;
  :mod:`_dispatch`'s ``_build_resume_result_from_final`` flips
  ``runs.status = gate_rejected`` and stamps ``finished_at``.
* Invalid response — the routing function raises
  :class:`NonRetryable` so a broken caller surfaces the contract
  violation loud (architecture.md §8.3 strict-review posture).
* Gate payload shape — ``SliceAggregate`` fields survive through the
  prompt and the interrupt payload.
* Gate audit log — ``Storage.get_gate`` returns a row with the rendered
  prompt + resumed response after approve or reject.
* Dispatch fix (T01-CARRY-DISPATCH-GATE) — ``_build_resume_result_from_final``
  reads the workflow-specific ``gate_{TERMINAL_GATE_ID}_response`` key
  instead of hardcoding the planner's id.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from langgraph.types import Command

from ai_workflows import workflows
from ai_workflows.graph import human_gate as human_gate_module
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.graph.checkpointer import build_async_checkpointer
from ai_workflows.graph.cost_callback import CostTrackingCallback
from ai_workflows.primitives.cost import CostTracker, TokenUsage
from ai_workflows.primitives.retry import NonRetryable
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig
from ai_workflows.workflows import planner as planner_module
from ai_workflows.workflows import slice_refactor as slice_refactor_module
from ai_workflows.workflows._dispatch import (
    _build_resume_result_from_final,
    _resolve_terminal_gate_id,
)
from ai_workflows.workflows.planner import build_planner
from ai_workflows.workflows.slice_refactor import (
    TERMINAL_GATE_ID,
    SliceAggregate,
    SliceFailure,
    SliceResult,
    _render_review_prompt,
    _route_on_gate_response,
    build_slice_refactor,
)

# ---------------------------------------------------------------------------
# Stub adapter mirroring the T04 per-slice scripting pattern
# ---------------------------------------------------------------------------


class _StubLiteLLMAdapter:
    """Scripted adapter that routes worker calls by slice id.

    Planner sub-graph calls (no ``Slice id:`` marker) pop from ``script``;
    worker calls pop from ``worker_script[sid]``.
    """

    script: list[Any] = []
    call_count: int = 0
    worker_script: dict[str, list[Any]] = {}
    worker_calls_by_slice: dict[str, int] = {}

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
        content = messages[0].get("content") or ""
        if "Slice id:" in content:
            first_line = content.splitlines()[0]
            _, _, sid = first_line.partition("Slice id: ")
            sid = sid.strip()
            _StubLiteLLMAdapter.worker_calls_by_slice[sid] = (
                _StubLiteLLMAdapter.worker_calls_by_slice.get(sid, 0) + 1
            )
            per_slice = _StubLiteLLMAdapter.worker_script.get(sid)
            if not per_slice:
                raise AssertionError(
                    f"stub worker script exhausted for slice {sid!r}"
                )
            head = per_slice.pop(0)
        else:
            if not _StubLiteLLMAdapter.script:
                raise AssertionError("stub planner script exhausted")
            head = _StubLiteLLMAdapter.script.pop(0)

        if isinstance(head, BaseException):
            raise head
        text, cost = head
        return text, TokenUsage(
            input_tokens=7,
            output_tokens=11,
            cost_usd=cost,
            model=self.route.model,
        )

    @classmethod
    def reset(cls) -> None:
        cls.script = []
        cls.call_count = 0
        cls.worker_script = {}
        cls.worker_calls_by_slice = defaultdict(int)


@pytest.fixture(autouse=True)
def _reset_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    _StubLiteLLMAdapter.reset()
    monkeypatch.setattr(
        tiered_node_module, "LiteLLMAdapter", _StubLiteLLMAdapter
    )


@pytest.fixture(autouse=True)
def _reensure_workflows_registered() -> Iterator[None]:
    workflows._reset_for_tests()
    workflows.register("planner", build_planner)
    workflows.register("slice_refactor", build_slice_refactor)
    yield


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _tier_registry() -> dict[str, TierConfig]:
    route = LiteLLMRoute(model="gemini/gemini-2.5-flash")
    return {
        "planner-explorer": TierConfig(
            name="planner-explorer",
            route=route,
            max_concurrency=2,
            per_call_timeout_s=60,
        ),
        "planner-synth": TierConfig(
            name="planner-synth",
            route=route,
            max_concurrency=2,
            per_call_timeout_s=90,
        ),
        "slice-worker": TierConfig(
            name="slice-worker",
            route=route,
            max_concurrency=4,
            per_call_timeout_s=60,
        ),
    }


async def _build_config(
    tmp_path: Path, run_id: str
) -> tuple[dict[str, Any], CostTracker, SQLiteStorage]:
    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await storage.create_run(run_id, "slice_refactor", None)
    tracker = CostTracker()
    callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=None)
    cfg = {
        "configurable": {
            "thread_id": run_id,
            "run_id": run_id,
            "tier_registry": _tier_registry(),
            "cost_callback": callback,
            "storage": storage,
            "workflow": "slice_refactor",
        }
    }
    return cfg, tracker, storage


def _valid_explorer_json() -> str:
    return json.dumps(
        {
            "summary": "Parallel slices.",
            "considerations": ["Isolated modules"],
            "assumptions": ["Green CI"],
        }
    )


def _n_step_plan_json(n: int) -> str:
    steps = [
        {
            "index": i,
            "title": f"Slice {i}",
            "rationale": f"r{i}",
            "actions": [f"act {i}"],
        }
        for i in range(1, n + 1)
    ]
    return json.dumps(
        {
            "goal": "Split the monolith.",
            "summary": f"{n} parallel slices.",
            "steps": steps,
        }
    )


def _valid_slice_result_json(slice_id: str) -> str:
    return json.dumps(
        {
            "slice_id": slice_id,
            "diff": f"--- a/s{slice_id}\n+++ b/s{slice_id}",
            "notes": f"completed slice {slice_id}",
        }
    )


def _planner_input_payload() -> dict[str, Any]:
    from ai_workflows.workflows.planner import PlannerInput

    return {
        "run_id": "placeholder",
        "input": PlannerInput(
            goal="Split the monolith.",
            context="Three modules.",
            max_steps=5,
        ),
    }


def _toy_aggregate() -> SliceAggregate:
    return SliceAggregate(
        succeeded=[
            SliceResult(slice_id="1", diff="d1", notes="first slice body"),
            SliceResult(slice_id="3", diff="d3", notes="third slice body"),
        ],
        failed=[
            SliceFailure(
                slice_id="2",
                last_error="validator exhausted",
                failure_bucket="non_retryable",
            ),
        ],
        total_slices=3,
    )


# ---------------------------------------------------------------------------
# AC: strict_review=True primitive disables the timeout path
# ---------------------------------------------------------------------------


async def test_human_gate_strict_review_nulls_timeout_payload(
    tmp_path: Path,
) -> None:
    """AC: ``strict_review=True`` sets both ``timeout_s`` and
    ``default_response_on_timeout`` to ``None`` in the interrupt
    payload — the node itself never starts a timer
    (architecture.md §8.3). Verified at the primitive level so T05's
    strict-review invariant holds regardless of the workflow that wires
    it.
    """
    captured: dict[str, Any] = {}

    def _fake_interrupt(payload: dict[str, Any]) -> str:
        captured.update(payload)
        return "approved"

    # Patch interrupt so the node returns immediately with a canned
    # response — we only need to inspect the payload shape.
    import ai_workflows.graph.human_gate as hg

    original = hg.interrupt
    hg.interrupt = _fake_interrupt  # type: ignore[assignment]
    try:
        gate = human_gate_module.human_gate(
            gate_id="slice_refactor_review",
            prompt_fn=lambda _state: "test prompt",
            strict_review=True,
        )
        storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
        await storage.create_run("run-strict", "slice_refactor", None)
        cfg = {"configurable": {"storage": storage}}
        await gate({"run_id": "run-strict"}, cfg)
    finally:
        hg.interrupt = original  # type: ignore[assignment]

    assert captured["strict_review"] is True
    assert captured["timeout_s"] is None
    assert captured["default_response_on_timeout"] is None


# ---------------------------------------------------------------------------
# AC: compiled graph exposes slice_refactor_review + apply nodes
# ---------------------------------------------------------------------------


def test_compiled_graph_has_review_gate_and_apply_nodes() -> None:
    """AC-1 structural: the T05 wiring adds ``slice_refactor_review``
    (strict-review gate) and ``apply`` (T06 stub) nodes between
    ``aggregate`` and ``END``. Without both nodes the approve/reject
    routing cannot resolve.
    """
    compiled = build_slice_refactor().compile()
    names = set(compiled.get_graph().nodes.keys())
    assert "slice_refactor_review" in names, (
        f"missing strict-review gate node, got {names}"
    )
    assert "apply" in names, f"missing apply terminal node, got {names}"
    assert "aggregate" in names


def test_terminal_gate_id_constant_is_exposed() -> None:
    """T01-CARRY-DISPATCH-GATE resolution: both workflow modules publish
    ``TERMINAL_GATE_ID`` so dispatch can discover the gate-response key
    uniformly (``f"gate_{TERMINAL_GATE_ID}_response"``).
    """
    assert slice_refactor_module.TERMINAL_GATE_ID == "slice_refactor_review"
    assert planner_module.TERMINAL_GATE_ID == "plan_review"
    # Dispatch resolver returns the constant for both modules.
    assert (
        _resolve_terminal_gate_id(slice_refactor_module)
        == "slice_refactor_review"
    )
    assert _resolve_terminal_gate_id(planner_module) == "plan_review"


# ---------------------------------------------------------------------------
# AC: _render_review_prompt produces the right shape
# ---------------------------------------------------------------------------


def test_render_review_prompt_lists_failures_first() -> None:
    """AC: prompt lists failures before successes, with ``last_error``
    inline on each failure line. Header includes the summary counts.
    """
    state = {"aggregate": _toy_aggregate()}
    prompt = _render_review_prompt(state)  # type: ignore[arg-type]
    lines = prompt.splitlines()
    # Header mentions total + split.
    assert "3 slices" in lines[0]
    assert "2 succeeded" in lines[0]
    assert "1 failed" in lines[0]
    # Failure section precedes success section.
    failure_line_idx = next(
        i for i, line in enumerate(lines) if "slice 2" in line
    )
    success_line_idx = next(
        i for i, line in enumerate(lines) if "slice 1" in line
    )
    assert failure_line_idx < success_line_idx
    # Failure line carries the error string verbatim.
    assert "validator exhausted" in lines[failure_line_idx]
    assert "non_retryable" in lines[failure_line_idx]
    # Success line carries the notes excerpt.
    assert "first slice body" in lines[success_line_idx]


def test_render_review_prompt_handles_missing_aggregate() -> None:
    """Defensive: formatter does not crash when ``aggregate`` is absent."""
    prompt = _render_review_prompt({})  # type: ignore[arg-type]
    assert "no aggregate available" in prompt


# ---------------------------------------------------------------------------
# AC: _route_on_gate_response routes approve/reject, raises NonRetryable
# ---------------------------------------------------------------------------


def test_route_on_gate_response_approved() -> None:
    """AC-1: ``"approved"`` routes to ``"apply"`` (edge dict key)."""
    state = {"gate_slice_refactor_review_response": "approved"}
    assert _route_on_gate_response(state) == "apply"  # type: ignore[arg-type]


def test_route_on_gate_response_rejected() -> None:
    """AC-1: ``"rejected"`` routes to ``"END"`` (edge dict key)."""
    state = {"gate_slice_refactor_review_response": "rejected"}
    assert _route_on_gate_response(state) == "END"  # type: ignore[arg-type]


def test_route_on_gate_response_missing_raises_nonretryable() -> None:
    """AC: a missing or unrecognised gate response raises
    :class:`NonRetryable` — strict-review contract violation.
    """
    with pytest.raises(NonRetryable):
        _route_on_gate_response({})  # type: ignore[arg-type]
    with pytest.raises(NonRetryable):
        _route_on_gate_response(
            {"gate_slice_refactor_review_response": "bogus"}
        )  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# AC: end-to-end approve path drives the graph through `apply`
# ---------------------------------------------------------------------------


async def test_approve_path_routes_through_apply_to_end(
    tmp_path: Path,
) -> None:
    """AC: approve at the ``slice_refactor_review`` gate routes the
    graph through ``apply`` (T05 stub) and terminates. ``final`` state
    carries the gate-response slot set to ``"approved"``.
    """
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_slice_refactor().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0010),
        (_n_step_plan_json(2), 0.0020),
    ]
    _StubLiteLLMAdapter.worker_script = {
        "1": [(_valid_slice_result_json("1"), 0.0030)],
        "2": [(_valid_slice_result_json("2"), 0.0031)],
    }
    cfg, _tracker, _storage = await _build_config(
        tmp_path, "run-gate-approve"
    )

    try:
        # First invoke: flows through planner → pauses at plan_review gate.
        payload = _planner_input_payload() | {"run_id": "run-gate-approve"}
        intermediate = await app.ainvoke(payload, cfg)
        assert "__interrupt__" in intermediate, (
            "expected planner's plan_review gate interrupt"
        )

        # Approve planner gate: flows through fan-out → aggregate →
        # pauses at slice_refactor_review gate.
        paused = await app.ainvoke(Command(resume="approved"), cfg)
        assert "__interrupt__" in paused, (
            "expected slice_refactor_review gate interrupt"
        )
        interrupt_payload = paused["__interrupt__"][0].value
        assert interrupt_payload["gate_id"] == "slice_refactor_review"
        assert interrupt_payload["strict_review"] is True
        assert interrupt_payload["timeout_s"] is None

        # Approve review gate: graph flows through apply → END.
        final = await app.ainvoke(Command(resume="approved"), cfg)
        assert "__interrupt__" not in final
        assert (
            final.get("gate_slice_refactor_review_response") == "approved"
        )
    finally:
        await checkpointer.conn.close()


async def test_reject_path_routes_directly_to_end(tmp_path: Path) -> None:
    """AC: reject at ``slice_refactor_review`` terminates without
    invoking ``apply``. ``final`` state carries the gate-response slot
    set to ``"rejected"``; the aggregate is still populated (so a caller
    reading final state can diagnose the rejected output).
    """
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_slice_refactor().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0010),
        (_n_step_plan_json(2), 0.0020),
    ]
    _StubLiteLLMAdapter.worker_script = {
        "1": [(_valid_slice_result_json("1"), 0.0030)],
        "2": [(_valid_slice_result_json("2"), 0.0031)],
    }
    cfg, _tracker, _storage = await _build_config(tmp_path, "run-gate-reject")

    try:
        payload = _planner_input_payload() | {"run_id": "run-gate-reject"}
        await app.ainvoke(payload, cfg)
        paused = await app.ainvoke(Command(resume="approved"), cfg)
        assert "__interrupt__" in paused

        final = await app.ainvoke(Command(resume="rejected"), cfg)
        assert "__interrupt__" not in final
        assert (
            final.get("gate_slice_refactor_review_response") == "rejected"
        )
        # Aggregate still present for caller diagnosis.
        assert isinstance(final.get("aggregate"), SliceAggregate)
    finally:
        await checkpointer.conn.close()


# ---------------------------------------------------------------------------
# AC: gate audit log lands for both approve and reject
# ---------------------------------------------------------------------------


async def test_gate_audit_log_written_for_approve(tmp_path: Path) -> None:
    """AC: ``Storage.record_gate`` + ``record_gate_response`` fire for
    the strict-review gate; ``Storage.get_gate`` returns the rendered
    prompt and the resumed response.
    """
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_slice_refactor().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0010),
        (_n_step_plan_json(2), 0.0020),
    ]
    _StubLiteLLMAdapter.worker_script = {
        "1": [(_valid_slice_result_json("1"), 0.0030)],
        "2": [(_valid_slice_result_json("2"), 0.0031)],
    }
    cfg, _tracker, storage = await _build_config(tmp_path, "run-audit-ok")

    try:
        payload = _planner_input_payload() | {"run_id": "run-audit-ok"}
        await app.ainvoke(payload, cfg)
        await app.ainvoke(Command(resume="approved"), cfg)  # planner gate
        await app.ainvoke(Command(resume="approved"), cfg)  # review gate

        row = await storage.get_gate("run-audit-ok", "slice_refactor_review")
        assert row is not None
        assert row["response"] == "approved"
        assert row["prompt"]
        assert "slices" in row["prompt"]
        assert row["strict_review"] == 1
    finally:
        await checkpointer.conn.close()


async def test_gate_audit_log_written_for_reject(tmp_path: Path) -> None:
    """AC: reject path also writes the gate-response row."""
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_slice_refactor().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0010),
        (_n_step_plan_json(2), 0.0020),
    ]
    _StubLiteLLMAdapter.worker_script = {
        "1": [(_valid_slice_result_json("1"), 0.0030)],
        "2": [(_valid_slice_result_json("2"), 0.0031)],
    }
    cfg, _tracker, storage = await _build_config(tmp_path, "run-audit-reject")

    try:
        payload = _planner_input_payload() | {"run_id": "run-audit-reject"}
        await app.ainvoke(payload, cfg)
        await app.ainvoke(Command(resume="approved"), cfg)
        await app.ainvoke(Command(resume="rejected"), cfg)

        row = await storage.get_gate(
            "run-audit-reject", "slice_refactor_review"
        )
        assert row is not None
        assert row["response"] == "rejected"
        assert row["strict_review"] == 1
    finally:
        await checkpointer.conn.close()


# ---------------------------------------------------------------------------
# T01-CARRY-DISPATCH-GATE: _build_resume_result_from_final is workflow-aware
# ---------------------------------------------------------------------------


async def test_dispatch_result_reads_slice_refactor_gate_key_on_reject(
    tmp_path: Path,
) -> None:
    """T01-CARRY-DISPATCH-GATE: the resume result helper reads
    ``state["gate_slice_refactor_review_response"]`` (via the workflow
    module's ``TERMINAL_GATE_ID`` constant) rather than hardcoding the
    planner's ``gate_plan_review_response``. Reject at the slice gate
    flips ``runs.status = gate_rejected``.
    """
    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await storage.create_run("run-dispatch-reject", "slice_refactor", None)
    tracker = CostTracker()

    # Mimic a final state where the planner gate was approved (so that
    # key says "approved") but the slice-refactor review gate was
    # rejected. The pre-fix dispatch would have read the planner key and
    # declared the run completed; the post-fix dispatch must read the
    # slice-refactor key and declare it gate_rejected.
    final = {
        "gate_plan_review_response": "approved",
        "gate_slice_refactor_review_response": "rejected",
        "aggregate": _toy_aggregate(),
    }

    result = await _build_resume_result_from_final(
        final=final,
        run_id="run-dispatch-reject",
        gate_response="rejected",
        terminal_gate_id="slice_refactor_review",
        tracker=tracker,
        storage=storage,
    )
    assert result["status"] == "gate_rejected"
    row = await storage.get_run("run-dispatch-reject")
    assert row is not None
    assert row["status"] == "gate_rejected"
    assert row["finished_at"] is not None


async def test_dispatch_result_preserves_planner_gate_behaviour(
    tmp_path: Path,
) -> None:
    """Regression: the refactor must not regress the planner workflow —
    with ``terminal_gate_id="plan_review"``, a ``gate_plan_review_response
    == "rejected"`` state still flips to ``gate_rejected``.
    """
    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await storage.create_run("run-planner-reject", "planner", None)
    tracker = CostTracker()

    final = {"gate_plan_review_response": "rejected"}
    result = await _build_resume_result_from_final(
        final=final,
        run_id="run-planner-reject",
        gate_response="rejected",
        terminal_gate_id="plan_review",
        tracker=tracker,
        storage=storage,
    )
    assert result["status"] == "gate_rejected"


async def test_dispatch_result_falls_back_to_gate_response_when_no_constant(
    tmp_path: Path,
) -> None:
    """Regression: workflows that omit ``TERMINAL_GATE_ID`` still work —
    dispatch falls back to the caller-supplied ``gate_response``.
    """
    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await storage.create_run("run-no-constant", "planner", None)
    tracker = CostTracker()

    result = await _build_resume_result_from_final(
        final={},
        run_id="run-no-constant",
        gate_response="rejected",
        terminal_gate_id=None,
        tracker=tracker,
        storage=storage,
    )
    assert result["status"] == "gate_rejected"


# ---------------------------------------------------------------------------
# Sanity: TERMINAL_GATE_ID is wired into the compiled gate's payload
# ---------------------------------------------------------------------------


async def test_interrupt_payload_uses_terminal_gate_id(
    tmp_path: Path,
) -> None:
    """AC: the ``__interrupt__`` payload the caller receives carries
    ``gate_id == TERMINAL_GATE_ID`` so the resume surface knows which
    gate it is answering.
    """
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_slice_refactor().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0010),
        (_n_step_plan_json(2), 0.0020),
    ]
    _StubLiteLLMAdapter.worker_script = {
        "1": [(_valid_slice_result_json("1"), 0.0030)],
        "2": [(_valid_slice_result_json("2"), 0.0031)],
    }
    cfg, _tracker, _storage = await _build_config(
        tmp_path, "run-gate-payload"
    )

    try:
        payload = _planner_input_payload() | {"run_id": "run-gate-payload"}
        await app.ainvoke(payload, cfg)
        paused = await app.ainvoke(Command(resume="approved"), cfg)

        interrupt = paused["__interrupt__"][0].value
        assert interrupt["gate_id"] == TERMINAL_GATE_ID
        assert interrupt["strict_review"] is True
    finally:
        await checkpointer.conn.close()
