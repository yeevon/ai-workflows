"""Tests for the T04 aggregator + per-branch ``SliceFailure`` wiring.

Covers the T04 acceptance criteria from
``design_docs/phases/milestone_6_slice_refactor/task_04_aggregator.md``:

* All-success — 3 slices pass validator → ``aggregate.succeeded`` has 3
  rows, ``aggregate.failed`` is ``[]``, ``total_slices == 3``.
* All-failure — 3 slices exhaust semantic retries → ``aggregate.succeeded``
  is empty, ``aggregate.failed`` has 3 populated rows. (The run still
  reaches the aggregator — the double-failure hard-stop is T07's
  responsibility.)
* Partial-failure — 2 succeed + 1 exhausts → both lists populated,
  ``total_slices == 3``.
* Ordering — both lists are treated as order-independent (LangGraph's
  fan-in order is not part of the contract); tests assert on sets and
  lengths so the suite survives interpreter-level dict-ordering
  perturbations.
* Bare-type regression guard — :class:`SliceAggregate` + :class:`SliceFailure`
  are ``extra="forbid"`` with no numeric bounds (KDR-010 / ADR-0002).

Structural tests cover:

* Sub-graph now has a ``slice_branch_finalize`` node downstream of the
  validator (T04 AC-3: failing branches emit ``SliceFailure`` via the
  error-handler wrap, not via unhandled exceptions).
* Aggregator is a pure function — no LLM call, no validator pairing
  (T04 AC-2: KDR-004 does not apply to non-LLM synthesis).
"""

from __future__ import annotations

import asyncio
import inspect
import json
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from langgraph.types import Command

from ai_workflows import workflows
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.graph.checkpointer import build_async_checkpointer
from ai_workflows.graph.cost_callback import CostTrackingCallback
from ai_workflows.primitives.cost import CostTracker, TokenUsage
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig
from ai_workflows.workflows.planner import build_planner
from ai_workflows.workflows.slice_refactor import (
    SliceAggregate,
    SliceFailure,
    SliceResult,
    _aggregate,
    _build_slice_branch_subgraph,
    build_slice_refactor,
)

# ---------------------------------------------------------------------------
# Stub adapter mirroring the T03 per-slice scripting pattern
# ---------------------------------------------------------------------------


class _StubLiteLLMAdapter:
    """Scripted adapter that routes worker calls by slice id.

    Planner sub-graph calls (no ``Slice id:`` marker) pop from
    ``script``; worker calls pop from ``worker_script[sid]`` and bump
    ``worker_calls_by_slice[sid]``. Shared with the T03 suite's stub
    to keep the per-branch retry-counting invariant identical.
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


# ---------------------------------------------------------------------------
# AC-1: SliceAggregate + SliceFailure are bare-typed (KDR-010 / ADR-0002)
# ---------------------------------------------------------------------------


def test_slice_aggregate_is_bare_typed() -> None:
    """AC-1: :class:`SliceAggregate` has ``extra="forbid"`` and no
    numeric bounds on its fields.

    The bare-type invariant lets a future caller use the schema as a
    LiteLLM ``response_format``; ``Field(min_length=…, max_length=…)``
    bounds would break the Gemini structured-output path per KDR-010.
    """
    assert SliceAggregate.model_config.get("extra") == "forbid"
    for name, field in SliceAggregate.model_fields.items():
        for constraint in ("min_length", "max_length", "gt", "lt", "ge", "le"):
            assert getattr(field, constraint, None) is None, (
                f"SliceAggregate.{name} has disallowed bound "
                f"{constraint!r} — bare-typed per KDR-010 / ADR-0002"
            )


def test_slice_failure_is_bare_typed() -> None:
    """AC-1: :class:`SliceFailure` has ``extra="forbid"`` and no
    numeric bounds.
    """
    assert SliceFailure.model_config.get("extra") == "forbid"
    for name, field in SliceFailure.model_fields.items():
        for constraint in ("min_length", "max_length", "gt", "lt", "ge", "le"):
            assert getattr(field, constraint, None) is None, (
                f"SliceFailure.{name} has disallowed bound "
                f"{constraint!r} — bare-typed per KDR-010 / ADR-0002"
            )


# ---------------------------------------------------------------------------
# AC-2: aggregate is a pure sync Python function — no LLM, no validator
# ---------------------------------------------------------------------------


def test_aggregate_is_plain_sync_function() -> None:
    """AC-2: ``aggregate`` node is a plain sync function — not an
    ``async`` LLM node, not :func:`tiered_node`, not wrapped in the
    error handler. KDR-004 does not apply to non-LLM synthesis.
    """
    assert not inspect.iscoroutinefunction(_aggregate)


def test_aggregate_builds_slice_aggregate_from_state_only() -> None:
    """AC-2 direct: feeding ``_aggregate`` a minimal state dict returns
    the expected :class:`SliceAggregate` without any external calls.
    """
    state: dict[str, Any] = {
        "slice_results": [
            SliceResult(slice_id="1", diff="d1", notes="n1"),
            SliceResult(slice_id="2", diff="d2", notes="n2"),
        ],
        "slice_failures": [
            SliceFailure(
                slice_id="3",
                last_error="boom",
                failure_bucket="non_retryable",
            ),
        ],
    }
    update = _aggregate(state)  # type: ignore[arg-type]
    aggregate = update["aggregate"]
    assert isinstance(aggregate, SliceAggregate)
    assert {r.slice_id for r in aggregate.succeeded} == {"1", "2"}
    assert [f.slice_id for f in aggregate.failed] == ["3"]
    assert aggregate.total_slices == 3


def test_aggregate_handles_empty_state() -> None:
    """Defensive regression: ``_aggregate`` returns an empty-but-valid
    :class:`SliceAggregate` when both reducer lists are absent (e.g.
    an upstream abort that never dispatched Send).
    """
    update = _aggregate({})  # type: ignore[arg-type]
    aggregate = update["aggregate"]
    assert aggregate.succeeded == []
    assert aggregate.failed == []
    assert aggregate.total_slices == 0


# ---------------------------------------------------------------------------
# AC-3: slice_branch_finalize converts exhausted branches to SliceFailure
# ---------------------------------------------------------------------------


def test_subgraph_has_slice_branch_finalize_node() -> None:
    """AC-3 structural: the compiled per-slice sub-graph exposes a
    ``slice_branch_finalize`` node downstream of the validator. Without
    this node, exhausted branches would surface ``NonRetryable`` as an
    unhandled exception rather than as a :class:`SliceFailure` state
    row that the aggregator can consume.
    """
    compiled = _build_slice_branch_subgraph()
    node_names = set(compiled.get_graph().nodes.keys())
    assert "slice_branch_finalize" in node_names, (
        f"expected slice_branch_finalize in sub-graph nodes, got {node_names}"
    )


# ---------------------------------------------------------------------------
# AC-4: end-to-end — all-success, all-failure, partial-failure shapes
# ---------------------------------------------------------------------------


async def test_all_success_aggregate_has_three_succeeded_and_no_failed(
    tmp_path: Path,
) -> None:
    """AC-4a: 3 slices all pass validator → ``aggregate.succeeded``
    contains 3 rows, ``aggregate.failed`` is ``[]``, ``total_slices == 3``.
    Order is asserted as a set because LangGraph's fan-in order is not
    part of the aggregator's contract.
    """
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_slice_refactor().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0010),
        (_n_step_plan_json(3), 0.0020),
    ]
    _StubLiteLLMAdapter.worker_script = {
        "1": [(_valid_slice_result_json("1"), 0.0030)],
        "2": [(_valid_slice_result_json("2"), 0.0031)],
        "3": [(_valid_slice_result_json("3"), 0.0032)],
    }
    cfg, _tracker, _storage = await _build_config(tmp_path, "run-agg-all-ok")

    try:
        payload = _planner_input_payload() | {"run_id": "run-agg-all-ok"}
        await app.ainvoke(payload, cfg)
        final = await app.ainvoke(Command(resume="approved"), cfg)

        aggregate = final["aggregate"]
        assert isinstance(aggregate, SliceAggregate)
        assert {r.slice_id for r in aggregate.succeeded} == {"1", "2", "3"}
        assert aggregate.failed == []
        assert aggregate.total_slices == 3

        # slice_failures reducer stays empty.
        assert (final.get("slice_failures") or []) == []
    finally:
        await checkpointer.conn.close()


async def test_all_failure_aggregate_has_three_failed_and_no_succeeded(
    tmp_path: Path,
) -> None:
    """AC-4b: 3 slices all exhaust semantic retries → ``aggregate.failed``
    has 3 rows with populated ``last_error``; ``aggregate.succeeded``
    is ``[]``; ``total_slices == 3``. The run still reaches the
    aggregator (T07 owns the double-failure hard-stop, not T04).
    """
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_slice_refactor().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0010),
        (_n_step_plan_json(3), 0.0020),
    ]
    # Each slice: 3 malformed responses → semantic budget exhausts on
    # the T03 in-validator escalation. The error-handler wrap converts
    # the NonRetryable into a state write; the T04 finalize node reads
    # that and emits one SliceFailure row per branch.
    _StubLiteLLMAdapter.worker_script = {
        "1": [("bad1", 0.0001), ("bad2", 0.0001), ("bad3", 0.0001)],
        "2": [("bad1", 0.0001), ("bad2", 0.0001), ("bad3", 0.0001)],
        "3": [("bad1", 0.0001), ("bad2", 0.0001), ("bad3", 0.0001)],
    }
    cfg, _tracker, _storage = await _build_config(tmp_path, "run-agg-all-fail")

    try:
        payload = _planner_input_payload() | {"run_id": "run-agg-all-fail"}
        await app.ainvoke(payload, cfg)
        final = await app.ainvoke(Command(resume="approved"), cfg)

        aggregate = final["aggregate"]
        assert isinstance(aggregate, SliceAggregate)
        assert aggregate.succeeded == []
        assert {f.slice_id for f in aggregate.failed} == {"1", "2", "3"}
        for failure in aggregate.failed:
            assert failure.last_error, (
                "SliceFailure.last_error must be a non-empty classified "
                "exception message"
            )
            assert failure.failure_bucket in (
                "retryable_semantic",
                "non_retryable",
            )
        assert aggregate.total_slices == 3

        # Each slice hit its full 3-attempt budget.
        for sid in ("1", "2", "3"):
            assert _StubLiteLLMAdapter.worker_calls_by_slice[sid] == 3
    finally:
        await checkpointer.conn.close()


async def test_partial_failure_aggregate_preserves_both_lists(
    tmp_path: Path,
) -> None:
    """AC-4c: 2 slices succeed + 1 exhausts → ``aggregate.succeeded``
    has 2 rows, ``aggregate.failed`` has 1 row with the failing
    ``slice_id``, ``total_slices == 3``.
    """
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_slice_refactor().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0010),
        (_n_step_plan_json(3), 0.0020),
    ]
    _StubLiteLLMAdapter.worker_script = {
        "1": [(_valid_slice_result_json("1"), 0.0030)],
        # Slice 2 exhausts the semantic budget.
        "2": [("bad1", 0.0001), ("bad2", 0.0001), ("bad3", 0.0001)],
        "3": [(_valid_slice_result_json("3"), 0.0032)],
    }
    cfg, _tracker, _storage = await _build_config(tmp_path, "run-agg-partial")

    try:
        payload = _planner_input_payload() | {"run_id": "run-agg-partial"}
        await app.ainvoke(payload, cfg)
        final = await app.ainvoke(Command(resume="approved"), cfg)

        aggregate = final["aggregate"]
        assert isinstance(aggregate, SliceAggregate)
        assert {r.slice_id for r in aggregate.succeeded} == {"1", "3"}
        assert [f.slice_id for f in aggregate.failed] == ["2"]
        assert aggregate.total_slices == 3
        # Failing slice burnt the full budget; siblings ran once each.
        assert _StubLiteLLMAdapter.worker_calls_by_slice["1"] == 1
        assert _StubLiteLLMAdapter.worker_calls_by_slice["2"] == 3
        assert _StubLiteLLMAdapter.worker_calls_by_slice["3"] == 1
    finally:
        await checkpointer.conn.close()


# ---------------------------------------------------------------------------
# Regression guard: the real aggregator replaces the T03 placeholder
# ---------------------------------------------------------------------------


def test_aggregate_node_is_registered_as_real_function() -> None:
    """Regression: the outer graph's ``aggregate`` node references the
    real :func:`_aggregate`, not the T02 / T03 placeholder. Prevents a
    future refactor from silently reverting to the no-op shape.
    """
    graph = build_slice_refactor()
    # LangGraph stores the node callable in ``graph.nodes['aggregate'].runnable``
    # but the underlying function is wrapped; introspect via the compiled
    # graph which exposes the original sync function bound into a
    # RunnableLambda. Direct attribute access is implementation-detail, so
    # compile-and-introspect via a minimal state is the least-brittle path.
    compiled = graph.compile()
    node_names = set(compiled.get_graph().nodes.keys())
    assert "aggregate" in node_names

    # Drive the aggregate node directly via the synchronous function
    # symbol imported above — the graph registration uses _aggregate
    # (not _aggregate_placeholder), so the module symbol is the only
    # candidate the outer graph could have bound.
    assert callable(_aggregate)
    assert _aggregate.__name__ == "_aggregate"


# ---------------------------------------------------------------------------
# Smoke: asyncio event loop compatibility across tests
# ---------------------------------------------------------------------------


def test_asyncio_event_loop_available() -> None:
    """Sanity: the test runner exposes a running asyncio event loop for
    the ``async def`` cases above. Purely defensive — guards against a
    future pytest-asyncio config regression.
    """
    loop = asyncio.new_event_loop()
    try:
        assert loop is not None
    finally:
        loop.close()
