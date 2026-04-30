"""Tests for the ``slice_refactor`` parallel-slice fan-out (M6 T02).

Covers the T02 acceptance criteria from
``design_docs/phases/milestone_6_slice_refactor/task_02_parallel_slice_worker.md``:

* Fan-out via LangGraph :class:`Send` — one ``slice_worker`` invocation
  per :class:`SliceSpec` (asserted via stub-adapter call log).
* Merge via ``Annotated[list[SliceResult], operator.add]`` reducer —
  ``slice_results`` accumulates one row per worker.
* Single-slice edge case — one worker, one result, same code path.
* ``durability="sync"`` is threaded through the ``ainvoke`` boundary
  by :mod:`ai_workflows.workflows._dispatch` (spec placed the flag on
  ``compile`` but the installed LangGraph version exposes it on
  ``ainvoke`` only — verified via ``inspect.signature``).
* Retry-taxonomy reducers keep the planner sub-graph's sequential
  writes compatible with the new parallel fan-out (regression guard
  for the ``InvalidUpdateError: last_exception`` failure mode).

Every LLM call is stubbed at the adapter level so no real API fires.
"""

from __future__ import annotations

import inspect
import json
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
from ai_workflows.workflows._dispatch import run_workflow as _dispatch_run_workflow
from ai_workflows.workflows.planner import build_planner
from ai_workflows.workflows.slice_refactor import (
    SliceResult,
    build_slice_refactor,
    slice_refactor_tier_registry,
)

# ---------------------------------------------------------------------------
# Stub adapter — same shape as tests/workflows/test_slice_refactor_planner_subgraph.py
# ---------------------------------------------------------------------------


class _StubLiteLLMAdapter:
    """Scripted LiteLLM adapter — mirrors the T01 test stub."""

    script: list[Any] = []
    call_count: int = 0
    worker_slice_ids: list[str] = []

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
        if "Slice id:" in (messages[0].get("content") or ""):
            # Crude parse from the prompt: "Slice id: <id>\n…"
            first_line = messages[0]["content"].splitlines()[0]
            _, _, sid = first_line.partition("Slice id: ")
            _StubLiteLLMAdapter.worker_slice_ids.append(sid.strip())
        if not _StubLiteLLMAdapter.script:
            raise AssertionError("stub script exhausted")
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
        cls.worker_slice_ids = []


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
# Helpers
# ---------------------------------------------------------------------------


def _tier_registry() -> dict[str, TierConfig]:
    """Test-local registry mirroring the production composition shape.

    Routes every tier through the stub adapter's ``LiteLLMRoute`` so
    no real provider call fires. Matches the shape
    :func:`slice_refactor_tier_registry` returns in production
    (planner-explorer + planner-synth + slice-worker), just pointed at
    the stub's model string.
    """
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
            "summary": "Three parallel slices.",
            "considerations": ["Separate modules"],
            "assumptions": ["Green CI"],
        }
    )


def _n_step_plan_json(n: int) -> str:
    steps = [
        {
            "index": i,
            "title": f"Slice {i}",
            "rationale": f"r{i}",
            "actions": [f"action {i}a", f"action {i}b"],
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


def _slice_result_json(slice_id: str) -> str:
    return json.dumps(
        {
            "slice_id": slice_id,
            "diff": f"--- a/m{slice_id}\n+++ b/m{slice_id}",
            "notes": f"completed slice {slice_id}",
        }
    )


# ---------------------------------------------------------------------------
# AC: Fan-out via Send; merge via operator.add reducer
# ---------------------------------------------------------------------------


async def test_three_slice_fanout_invokes_three_workers_and_merges_results(
    tmp_path: Path,
) -> None:
    """AC: 3-slice fixture → 3 worker invocations → 3 :class:`SliceResult`.

    Stubbed script: explorer + planner for the sub-graph, then three
    worker invocations (one per :class:`SliceSpec`). After
    ``resume("approved")`` the outer graph fans out via ``Send``,
    each worker runs once, and ``operator.add`` accumulates the three
    :class:`SliceResult` rows on ``slice_results``.
    """
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_slice_refactor().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0010),
        (_n_step_plan_json(3), 0.0020),
        (_slice_result_json("1"), 0.0030),
        (_slice_result_json("2"), 0.0031),
        (_slice_result_json("3"), 0.0032),
    ]
    cfg, tracker, _storage = await _build_config(tmp_path, "run-three")

    try:
        await app.ainvoke(
            {
                "run_id": "run-three",
                "input": _planner_input(),
            },
            cfg,
        )
        final = await app.ainvoke(Command(resume="approved"), cfg)

        # 2 sub-graph LLM calls + 3 worker calls = 5 total.
        assert _StubLiteLLMAdapter.call_count == 5
        # Each worker received exactly one slice id.
        assert sorted(_StubLiteLLMAdapter.worker_slice_ids) == ["1", "2", "3"]

        slice_results = final["slice_results"]
        assert isinstance(slice_results, list)
        assert len(slice_results) == 3
        for row in slice_results:
            assert isinstance(row, SliceResult)
        assert {r.slice_id for r in slice_results} == {"1", "2", "3"}

        # Cost-rollup spans every LLM call in the run (sub-graph + workers).
        expected = 0.0010 + 0.0020 + 0.0030 + 0.0031 + 0.0032
        assert tracker.total("run-three") == pytest.approx(expected)
    finally:
        await checkpointer.conn.close()


async def test_single_slice_fanout_invokes_one_worker(tmp_path: Path) -> None:
    """Edge: 1-slice fixture → 1 worker invocation → 1 :class:`SliceResult`."""
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_slice_refactor().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0011),
        (_n_step_plan_json(1), 0.0022),
        (_slice_result_json("1"), 0.0033),
    ]
    cfg, tracker, _storage = await _build_config(tmp_path, "run-one")

    try:
        await app.ainvoke(
            {"run_id": "run-one", "input": _planner_input()}, cfg
        )
        final = await app.ainvoke(Command(resume="approved"), cfg)

        assert _StubLiteLLMAdapter.call_count == 3
        assert _StubLiteLLMAdapter.worker_slice_ids == ["1"]
        assert len(final["slice_results"]) == 1
        assert final["slice_results"][0].slice_id == "1"
        assert tracker.total("run-one") == pytest.approx(0.0011 + 0.0022 + 0.0033)
    finally:
        await checkpointer.conn.close()


# ---------------------------------------------------------------------------
# AC: reducer shape — operator.add accumulates across writes
# ---------------------------------------------------------------------------


def test_slice_refactor_state_declares_slice_results_with_add_reducer() -> None:
    """AC: ``slice_results`` carries the ``operator.add`` reducer.

    Spec line: "merge via ``Annotated[list[SliceResult], operator.add]``
    reducer; no hand-rolled merge node." Introspect the TypedDict's
    annotations to pin the reducer without running the graph — that
    way a regression (someone drops the ``Annotated``) is caught even
    if the fan-out tests happen to pass because only one worker runs.
    """
    import operator
    from typing import get_args, get_type_hints

    from ai_workflows.workflows.slice_refactor import SliceRefactorState

    hints = get_type_hints(
        SliceRefactorState, include_extras=True
    )
    slice_results_hint = hints["slice_results"]
    args = get_args(slice_results_hint)
    assert args, "slice_results hint should be Annotated"
    assert operator.add in args, (
        "slice_results must carry operator.add as its reducer "
        "(AC: merge via Annotated[list[SliceResult], operator.add])"
    )


async def test_reducer_accumulates_across_two_fanout_batches(
    tmp_path: Path,
) -> None:
    """AC: reducer accumulation holds across sequential fan-out bursts.

    Simulates the T07 scenario where a semantic-retry rerun of one
    slice re-enters the fan-out without clobbering prior results: we
    drive two :func:`_fan_out_to_workers`-style ``Send`` lists through
    the reducer directly. No LLM calls — purely the channel-reducer
    behaviour guard.
    """
    import operator

    # Simulate sequential reductions: first batch of 2, then batch of 1.
    batch_1 = [
        SliceResult(slice_id="a", diff="d1", notes="n1"),
        SliceResult(slice_id="b", diff="d2", notes="n2"),
    ]
    batch_2 = [SliceResult(slice_id="c", diff="d3", notes="n3")]

    # ``operator.add`` on lists concatenates. LangGraph applies the
    # reducer as ``existing + update`` per write; a sequence of writes
    # reduces to the concatenation.
    merged = operator.add(batch_1, batch_2)
    assert [r.slice_id for r in merged] == ["a", "b", "c"]

    # Starting from an empty existing value, two consecutive adds
    # reproduce the same outcome — the same call shape LangGraph uses
    # under the hood when fan-out writes arrive.
    step1 = operator.add([], batch_1)
    step2 = operator.add(step1, batch_2)
    assert [r.slice_id for r in step2] == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# AC: durability="sync" threaded through dispatch at the ainvoke boundary
# ---------------------------------------------------------------------------


def test_dispatch_threads_durability_sync_through_ainvoke() -> None:
    """AC (spec-location-correction): ``durability="sync"`` is on
    ``CompiledStateGraph.ainvoke``, not :meth:`StateGraph.compile`.

    Verified via ``inspect.signature`` so a future LangGraph upgrade
    that moves the flag to ``compile`` will surface via this test
    rather than silently drifting.
    """
    from langgraph.graph import StateGraph
    from langgraph.graph.state import CompiledStateGraph

    compile_params = set(inspect.signature(StateGraph.compile).parameters)
    ainvoke_params = set(inspect.signature(CompiledStateGraph.ainvoke).parameters)

    assert "durability" not in compile_params, (
        "LangGraph moved durability to compile — revisit _dispatch threading"
    )
    assert "durability" in ainvoke_params

    # Confirm dispatch actually sets the kwarg at the ainvoke call
    # site — grep the source (hermetic, no graph run required).
    dispatch_src = (
        Path(__file__).resolve().parents[2]
        / "ai_workflows"
        / "workflows"
        / "_dispatch.py"
    ).read_text(encoding="utf-8")
    # Both ainvoke calls (run path + resume path) should carry sync.
    assert dispatch_src.count('durability="sync"') >= 2


def test_slice_refactor_tier_registry_composes_planner_tiers() -> None:
    """AC: ``slice-worker`` registered; planner tiers composed in.

    Dispatch only reads ``<workflow>_tier_registry()``; the planner
    sub-graph at runtime needs ``planner-explorer`` / ``planner-synth``
    to be resolvable from the same mapping. Composition lives in this
    helper at the module level so production dispatch picks up all
    tiers without dispatch knowing about the composition.

    M12 Task 01 adds ``auditor-sonnet`` and ``auditor-opus`` to the
    planner registry; they propagate here automatically via composition.
    """
    reg = slice_refactor_tier_registry()
    assert set(reg.keys()) == {
        "planner-explorer",
        "planner-synth",
        "slice-worker",
        "auditor-sonnet",
        "auditor-opus",
    }
    slice_worker = reg["slice-worker"]
    assert isinstance(slice_worker.route, LiteLLMRoute)
    assert slice_worker.route.model == "ollama/qwen2.5-coder:32b"


# ---------------------------------------------------------------------------
# Regression: retry-taxonomy reducers keep the sub-graph happy under fan-out
# ---------------------------------------------------------------------------


def test_merge_last_exception_prefers_non_none() -> None:
    """Reducer contract: a worker's success-None does not overwrite a
    sibling's failure-exception.
    """
    from ai_workflows.primitives.retry import NonRetryable
    from ai_workflows.workflows.slice_refactor import _merge_last_exception

    exc = NonRetryable("boom")
    assert _merge_last_exception(None, None) is None
    assert _merge_last_exception(None, exc) is exc
    assert _merge_last_exception(exc, None) is exc
    # Most-recent non-None wins on collision.
    exc2 = NonRetryable("boom2")
    assert _merge_last_exception(exc, exc2) is exc2


def test_merge_retry_counts_shallow_merges() -> None:
    from ai_workflows.workflows.slice_refactor import _merge_retry_counts

    assert _merge_retry_counts(None, None) == {}
    assert _merge_retry_counts({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}
    # Same-key collision: last-wins (update overrides existing).
    assert _merge_retry_counts({"a": 1}, {"a": 3}) == {"a": 3}


def test_merge_non_retryable_failures_uses_max() -> None:
    from ai_workflows.workflows.slice_refactor import (
        _merge_non_retryable_failures,
    )

    assert _merge_non_retryable_failures(None, None) == 0
    assert _merge_non_retryable_failures(0, 1) == 1
    # Parallel bursts of three failing workers each reporting ``prev+1``
    # should not double-count: reducer stays at the single-failure
    # watermark rather than summing.
    assert _merge_non_retryable_failures(1, 1) == 1


# ---------------------------------------------------------------------------
# Helpers (module-local because the planner input factory already in T01
# test file is not shared)
# ---------------------------------------------------------------------------


def _planner_input() -> Any:
    from ai_workflows.workflows.planner import PlannerInput

    return PlannerInput(
        goal="Split the monolith.", context=None, max_steps=5
    )


# Keep the dispatch symbol referenced so its import is not dead code on CI
# (verifies the helper is still there after any dispatch refactor).
_ = _dispatch_run_workflow
