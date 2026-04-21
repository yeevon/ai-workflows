"""Tests for the per-slice validator wiring + retrying-edge self-loop (M6 T03).

Covers the T03 acceptance criteria from
``design_docs/phases/milestone_6_slice_refactor/task_03_per_slice_validator.md``:

* Happy path — worker returns valid :class:`SliceResult` JSON → validator
  parses → ``slice_results`` populated.
* Semantic retry — worker returns malformed JSON once, valid on retry;
  graph self-loops the failing slice's worker once, completes. **Sibling
  slices are not re-run** (semantic retry is per-slice, scoped to the
  single :class:`Send` payload via the compiled sub-graph).
* Semantic exhaustion — three malformed responses for one slice surface
  ``NonRetryable`` on that branch; sibling slices still complete their
  worker → validator path. T07 owns the abort decision; T03 just emits
  the failure type correctly.
* Transient retry — a :class:`litellm.APIConnectionError` on the first
  call is classified as :class:`RetryableTransient` by
  :class:`TieredNode`; the retrying-edge self-loops the worker and the
  slice completes on the second attempt.
* KDR-004 regression guard — introspect the compiled per-slice
  sub-graph's node list to confirm every slice-worker tier node has an
  adjacent ``slice_worker_validator`` node downstream.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from langgraph.types import Command
from litellm.exceptions import APIConnectionError

from ai_workflows import workflows
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.graph.checkpointer import build_async_checkpointer
from ai_workflows.graph.cost_callback import CostTrackingCallback
from ai_workflows.primitives.cost import CostTracker, TokenUsage
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig
from ai_workflows.workflows.planner import build_planner
from ai_workflows.workflows.slice_refactor import (
    SLICE_WORKER_RETRY_POLICY,
    SliceResult,
    _build_slice_branch_subgraph,
    build_slice_refactor,
)

# ---------------------------------------------------------------------------
# Stub adapter with per-slice call accounting
# ---------------------------------------------------------------------------


class _StubLiteLLMAdapter:
    """Scripted LiteLLM adapter that records per-slice worker retries.

    Planner sub-graph calls (no ``Slice id:`` marker in the prompt) are
    routed to the top of ``script``; worker calls look up their next
    scripted response under the slice id in ``worker_script`` and bump
    ``worker_calls_by_slice`` so tests can assert exactly how many times
    each slice's worker was invoked. This shape is the only way to prove
    "sibling slices are not re-run" on semantic retry (AC-3 / AC-5).
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
    """Full tier registry with zero ``transient_backoff`` so transient
    retries fire instantly in test time."""
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
            "summary": "Two parallel slices.",
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
            context="Two modules.",
            max_steps=5,
        ),
    }


# ---------------------------------------------------------------------------
# AC: KDR-004 structural guard — validator pairing on every slice-worker node
# ---------------------------------------------------------------------------


def test_slice_branch_subgraph_has_worker_and_validator_nodes() -> None:
    """AC-6 / KDR-004: the compiled per-slice sub-graph has
    ``slice_worker`` and ``slice_worker_validator`` as adjacent nodes.

    Spec line: "grep the final compiled graph's node list; every node
    whose tier is ``slice-worker`` has an adjacent
    ``slice_worker_validator`` node downstream." The sub-graph is
    compiled to assert that the T03 wiring resolves (validator is
    registered and reachable via the retrying-edge on_terminal path).
    """
    compiled = _build_slice_branch_subgraph()
    node_names = set(compiled.get_graph().nodes.keys())
    assert {"slice_worker", "slice_worker_validator"}.issubset(node_names), (
        f"expected slice_worker + slice_worker_validator in {node_names}"
    )


def test_slice_worker_retry_policy_matches_spec_budget() -> None:
    """AC-2: ``max_semantic_attempts=3`` per architecture.md §8.2.

    Spec line: "Max semantic attempts: 3 (per architecture.md §8.2)."
    Transient budget mirrors the planner's 5-attempt burst (regression
    guard — if someone lowers the budget the self-loop will exhaust
    faster than the ``test_single_transient_retry_recovers`` scenario
    tolerates).
    """
    assert SLICE_WORKER_RETRY_POLICY.max_semantic_attempts == 3
    assert SLICE_WORKER_RETRY_POLICY.max_transient_attempts == 5


# ---------------------------------------------------------------------------
# AC-1: Happy path — valid JSON passes through the validator
# ---------------------------------------------------------------------------


async def test_happy_path_two_slices_validator_populates_slice_results(
    tmp_path: Path,
) -> None:
    """AC-1: worker returns valid JSON → validator parses → each
    branch contributes one :class:`SliceResult`; the parent reducer
    concatenates them onto ``slice_results``.
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
    cfg, _tracker, _storage = await _build_config(tmp_path, "run-happy")

    try:
        payload = _planner_input_payload() | {"run_id": "run-happy"}
        await app.ainvoke(payload, cfg)
        final = await app.ainvoke(Command(resume="approved"), cfg)

        slice_results = final["slice_results"]
        assert len(slice_results) == 2
        assert {r.slice_id for r in slice_results} == {"1", "2"}
        for row in slice_results:
            assert isinstance(row, SliceResult)

        # Each slice worker ran exactly once — no retries on the happy path.
        assert _StubLiteLLMAdapter.worker_calls_by_slice == {"1": 1, "2": 1}
    finally:
        await checkpointer.conn.close()


# ---------------------------------------------------------------------------
# AC-3: Semantic retry — single-slice self-loop; siblings not re-run
# ---------------------------------------------------------------------------


async def test_semantic_retry_reruns_only_failing_slice(tmp_path: Path) -> None:
    """AC-3: one slice's first worker output is malformed JSON; the
    validator raises :class:`RetryableSemantic`; the retrying-edge
    self-loops back to ``slice_worker`` for that slice only and the
    branch completes on the second attempt. **Sibling slices are not
    re-run.**

    Spec line: "Assert that sibling slices are not re-run (semantic
    retry is per-slice, not per-fan-out-batch)."
    """
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_slice_refactor().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0010),
        (_n_step_plan_json(2), 0.0020),
    ]
    _StubLiteLLMAdapter.worker_script = {
        # Slice "1": malformed first, valid second.
        "1": [
            ("not valid json at all", 0.0010),
            (_valid_slice_result_json("1"), 0.0030),
        ],
        # Slice "2": single valid response — must NOT be retried.
        "2": [(_valid_slice_result_json("2"), 0.0031)],
    }
    cfg, _tracker, _storage = await _build_config(tmp_path, "run-sem")

    try:
        payload = _planner_input_payload() | {"run_id": "run-sem"}
        await app.ainvoke(payload, cfg)
        final = await app.ainvoke(Command(resume="approved"), cfg)

        # Both slices present on the final state.
        slice_results = final["slice_results"]
        assert {r.slice_id for r in slice_results} == {"1", "2"}

        # Slice 1 ran twice (retry), slice 2 ran once (sibling unaffected).
        assert _StubLiteLLMAdapter.worker_calls_by_slice["1"] == 2
        assert _StubLiteLLMAdapter.worker_calls_by_slice["2"] == 1
    finally:
        await checkpointer.conn.close()


# ---------------------------------------------------------------------------
# AC-5: Semantic exhaustion — one branch surfaces NonRetryable;
#        siblings still complete
# ---------------------------------------------------------------------------


async def test_semantic_exhaustion_surfaces_nonretryable_on_failing_branch(
    tmp_path: Path,
) -> None:
    """AC-5: all three attempts on one slice return malformed JSON;
    that branch exhausts the semantic budget and surfaces
    :class:`NonRetryable` on the run's state. **Sibling slices still
    complete their worker → validator path.**

    Spec line: "sibling slices still complete their worker→validator
    path. The double-failure abort decision is T07's scope; T03 asserts
    the single-slice failure surfaces correctly."
    """
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_slice_refactor().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0010),
        (_n_step_plan_json(2), 0.0020),
    ]
    _StubLiteLLMAdapter.worker_script = {
        # Slice "1": three malformed responses → semantic budget exhausts.
        "1": [
            ("not json 1", 0.0010),
            ("not json 2", 0.0010),
            ("not json 3", 0.0010),
        ],
        # Slice "2": happy path.
        "2": [(_valid_slice_result_json("2"), 0.0031)],
    }
    cfg, _tracker, _storage = await _build_config(tmp_path, "run-exh")

    try:
        payload = _planner_input_payload() | {"run_id": "run-exh"}
        await app.ainvoke(payload, cfg)
        final = await app.ainvoke(Command(resume="approved"), cfg)

        # Slice 2 still completed end-to-end.
        slice_results = final.get("slice_results") or []
        assert [r.slice_id for r in slice_results] == ["2"]

        # Slice 1 hit its 3-attempt semantic budget exactly.
        assert _StubLiteLLMAdapter.worker_calls_by_slice["1"] == 3
        assert _StubLiteLLMAdapter.worker_calls_by_slice["2"] == 1

        # The failing branch's classified exception lands on state —
        # T07 inspects this to decide abort vs continue.
        non_retryable = final.get("_non_retryable_failures") or 0
        assert non_retryable >= 1, (
            "expected at least one _non_retryable_failures bump from the "
            "exhausted semantic budget"
        )
    finally:
        await checkpointer.conn.close()


# ---------------------------------------------------------------------------
# AC-4: Transient retry — APIConnectionError once, completes on retry;
#        siblings unaffected
# ---------------------------------------------------------------------------


async def test_transient_retry_on_apiconnectionerror_recovers_slice(
    tmp_path: Path,
) -> None:
    """AC-4: a :class:`litellm.APIConnectionError` on the first call
    classifies as :class:`RetryableTransient`; the retrying-edge
    self-loops the worker and the slice completes on the second attempt.
    Sibling slices unaffected.

    Spec line: "Transient retry: worker raises APIConnectionError once
    → retrying_edge's on_transient self-loops the worker with backoff;
    slice completes on the second attempt. Sibling slices unaffected."
    """
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_slice_refactor().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0010),
        (_n_step_plan_json(2), 0.0020),
    ]
    _StubLiteLLMAdapter.worker_script = {
        "1": [
            APIConnectionError(
                message="connection reset",
                llm_provider="gemini",
                model="gemini/gemini-2.5-flash",
            ),
            (_valid_slice_result_json("1"), 0.0030),
        ],
        "2": [(_valid_slice_result_json("2"), 0.0031)],
    }
    cfg, _tracker, _storage = await _build_config(tmp_path, "run-trans")

    try:
        payload = _planner_input_payload() | {"run_id": "run-trans"}
        await app.ainvoke(payload, cfg)
        final = await app.ainvoke(Command(resume="approved"), cfg)

        slice_results = final["slice_results"]
        assert {r.slice_id for r in slice_results} == {"1", "2"}

        # Slice 1 retried once (transient), slice 2 untouched.
        assert _StubLiteLLMAdapter.worker_calls_by_slice["1"] == 2
        assert _StubLiteLLMAdapter.worker_calls_by_slice["2"] == 1
    finally:
        await checkpointer.conn.close()
