"""Tests for the ``slice_refactor`` workflow's slice-discovery phase (M6 T01).

Covers the T01 acceptance criteria from
``design_docs/phases/milestone_6_slice_refactor/task_01_slice_discovery.md``:

* Registry: ``workflows.get("slice_refactor")`` resolves to
  :func:`build_slice_refactor` after import.
* Hermetic pause-at-gate: stubbed LLM adapter drives the planner
  sub-graph to its plan-review ``HumanGate``; the outer
  ``slice_refactor`` run pauses at that gate and returns a parseable
  :class:`PlannerPlan` on outer state.
* Resume-through-sub-graph: ``Command(resume="approved")`` clears the
  planner's gate and the outer graph advances through
  ``slice_list_normalize`` — the final state has a non-empty
  ``slice_list``.
* Normalization shape: a 3-step :class:`PlannerPlan` yields 3
  :class:`SliceSpec` rows; fields mapped field-for-field.
* Empty plan: a plan with zero steps raises :class:`NonRetryable`
  (KDR-006 bucket; T01 AC-4).
* Dispatch ``initial_state`` hook: ``_build_initial_state`` routes
  through :func:`slice_refactor.initial_state` when present and
  constructs a :class:`PlannerInput` for the sub-graph.

Every LLM call is stubbed at the adapter level so no real API fires.
"""

from __future__ import annotations

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
from ai_workflows.primitives.retry import NonRetryable
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig
from ai_workflows.workflows._dispatch import _build_initial_state
from ai_workflows.workflows.planner import (
    PlannerInput,
    PlannerPlan,
    build_planner,
)
from ai_workflows.workflows.slice_refactor import (
    SliceRefactorInput,
    SliceSpec,
    _slice_list_normalize,
    build_slice_refactor,
    initial_state,
)

# ---------------------------------------------------------------------------
# Stub LiteLLM adapter — mirrors tests/workflows/test_planner_graph.py
# ---------------------------------------------------------------------------


class _StubLiteLLMAdapter:
    """Scripted LiteLLM-adapter stub for the planner sub-graph."""

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
            input_tokens=9,
            output_tokens=13,
            cost_usd=cost,
            model=self.route.model,
        )

    @classmethod
    def reset(cls) -> None:
        cls.script = []
        cls.call_count = 0


@pytest.fixture(autouse=True)
def _reset_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    _StubLiteLLMAdapter.reset()
    monkeypatch.setattr(
        tiered_node_module, "LiteLLMAdapter", _StubLiteLLMAdapter
    )


@pytest.fixture(autouse=True)
def _reensure_workflows_registered() -> Iterator[None]:
    """Re-register both workflows on every test (sibling test files reset)."""
    workflows._reset_for_tests()
    workflows.register("planner", build_planner)
    workflows.register("slice_refactor", build_slice_refactor)
    yield


# ---------------------------------------------------------------------------
# Helpers — tier registry, config, fixture JSON
# ---------------------------------------------------------------------------


def _tier_registry() -> dict[str, TierConfig]:
    return {
        "planner-explorer": TierConfig(
            name="planner-explorer",
            route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
            max_concurrency=2,
            per_call_timeout_s=60,
        ),
        "planner-synth": TierConfig(
            name="planner-synth",
            route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
            max_concurrency=2,
            per_call_timeout_s=90,
        ),
        "slice-worker": TierConfig(
            name="slice-worker",
            route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
            max_concurrency=2,
            per_call_timeout_s=60,
        ),
    }


def _valid_slice_result_json(slice_id: str) -> str:
    return json.dumps(
        {
            "slice_id": slice_id,
            "diff": f"--- a/{slice_id}\n+++ b/{slice_id}\n@@ noop",
            "notes": f"Stubbed slice {slice_id} output.",
        }
    )


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
            "summary": "Three-slice refactor breaks the monolith cleanly.",
            "considerations": ["Import cycles", "Test scope"],
            "assumptions": ["CI remains green"],
        }
    )


def _three_step_plan_json() -> str:
    return json.dumps(
        {
            "goal": "Split the monolith.",
            "summary": "Three parallelisable slices.",
            "steps": [
                {
                    "index": 1,
                    "title": "Extract auth module",
                    "rationale": "Clearest seam; no shared state.",
                    "actions": ["Move files", "Update imports"],
                },
                {
                    "index": 2,
                    "title": "Extract billing module",
                    "rationale": "Isolated by feature flag.",
                    "actions": ["Move files", "Wire feature flag"],
                },
                {
                    "index": 3,
                    "title": "Extract notifications",
                    "rationale": "Leaf dependency.",
                    "actions": ["Move files", "Update consumers"],
                },
            ],
        }
    )


def _slice_refactor_input() -> PlannerInput:
    return PlannerInput(
        goal="Split the monolith.",
        context="Three top-level modules.",
        max_steps=5,
    )


# ---------------------------------------------------------------------------
# Registry + dispatch hook
# ---------------------------------------------------------------------------


def test_slice_refactor_registered_under_existing_dispatch() -> None:
    """AC: ``workflows.get("slice_refactor")`` resolves after module import."""
    assert workflows.get("slice_refactor") is build_slice_refactor


def test_initial_state_hook_constructs_planner_input_for_subgraph() -> None:
    """AC-5 / M6 T01 option B: ``_build_initial_state`` routes through
    ``slice_refactor.initial_state`` and produces a :class:`PlannerInput`
    on the ``input`` channel the planner sub-graph reads on entry.
    """
    from ai_workflows.workflows import slice_refactor as module

    state = _build_initial_state(
        module,
        "run-hook",
        {"goal": "Split the monolith.", "context": None, "max_steps": 5},
    )
    assert state["run_id"] == "run-hook"
    assert isinstance(state["input"], PlannerInput)
    assert state["input"].goal == "Split the monolith."


def test_initial_state_hook_direct_call_shape() -> None:
    """Convention hook returns the exact shape dispatch expects."""
    state = initial_state("run-direct", {"goal": "g", "max_steps": 3})
    assert state["run_id"] == "run-direct"
    assert isinstance(state["input"], PlannerInput)
    assert state["input"].max_steps == 3


def test_slice_refactor_input_bounds_mirror_planner_input() -> None:
    """``SliceRefactorInput`` reuses the planner's goal/context/max_steps bounds."""
    sri = SliceRefactorInput(goal="x", max_steps=10)
    assert sri.goal == "x"
    assert sri.max_steps == 10
    with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError
        SliceRefactorInput(goal="", max_steps=10)  # min_length=1
    with pytest.raises(Exception):  # noqa: B017
        SliceRefactorInput(goal="x", max_steps=26)  # le=25


# ---------------------------------------------------------------------------
# Hermetic pause-at-gate + resume-through-sub-graph
# ---------------------------------------------------------------------------


async def test_slice_refactor_pauses_at_planner_subgraph_gate(
    tmp_path: Path,
) -> None:
    """AC-2: outer ``slice_refactor`` run pauses at the planner's
    plan-review :class:`HumanGate`.

    The interrupt fires **inside** the planner sub-graph. Per LangGraph's
    state-channel semantics the sub-graph's per-node writes are not
    merged onto the parent's state dict until the sub-graph node itself
    completes — so ``paused["plan"]`` is *not* populated while the
    sub-graph is suspended. The parent observes only ``__interrupt__``
    plus the keys it explicitly wrote (``run_id`` / ``input``). The plan
    does materialize on the outer state once the gate clears and the
    sub-graph finishes — that path is asserted in the resume test.
    """
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_slice_refactor().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_three_step_plan_json(), 0.0021),
    ]
    cfg, tracker, storage = await _build_config(tmp_path, "run-pause")

    try:
        paused = await app.ainvoke(
            {"run_id": "run-pause", "input": _slice_refactor_input()}, cfg
        )
        assert "__interrupt__" in paused
        interrupts = paused["__interrupt__"]
        assert len(interrupts) == 1
        # The interrupt surfaces the planner's plan-review gate — this is
        # the sub-graph's HumanGate fired through the outer graph.
        assert interrupts[0].value["gate_id"] == "plan_review"
        # slice_list must NOT be populated yet — normalize runs post-gate.
        assert not paused.get("slice_list")
        # Both stubbed LLM calls fired exactly once inside the sub-graph.
        assert _StubLiteLLMAdapter.call_count == 2
        # Cost-rollup crosses the sub-graph boundary: the sub-graph's
        # ``CostTrackingCallback`` writes through the parent's config, so
        # the outer tracker sees the sum of both stubbed calls
        # (0.0012 + 0.0021 = 0.0033). Dependency from T01 spec: M5 T03
        # exercised cost-rollup inside the planner; T01 exercises it at
        # the outer graph boundary for the first time.
        assert tracker.total("run-pause") == pytest.approx(0.0033)
    finally:
        await checkpointer.conn.close()
        del storage


async def test_resume_clears_subgraph_gate_and_populates_slice_list(
    tmp_path: Path,
) -> None:
    """AC-2 / AC-3: resume with ``"approved"`` clears the planner's gate and
    advances into ``slice_list_normalize``; ``slice_list`` has one
    :class:`SliceSpec` per :class:`PlannerStep`, field-for-field.
    """
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_slice_refactor().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_three_step_plan_json(), 0.0021),
        (_valid_slice_result_json("1"), 0.0001),
        (_valid_slice_result_json("2"), 0.0001),
        (_valid_slice_result_json("3"), 0.0001),
    ]
    cfg, tracker, storage = await _build_config(tmp_path, "run-resume")

    try:
        await app.ainvoke(
            {"run_id": "run-resume", "input": _slice_refactor_input()}, cfg
        )
        final = await app.ainvoke(Command(resume="approved"), cfg)
        assert final["gate_plan_review_response"] == "approved"
        # Cost-rollup spans the full run including the T03 per-slice
        # worker→validator pairs: 0.0012 (explorer) + 0.0021 (planner)
        # + 3 × 0.0001 (one slice-worker stub per Send fan-out branch) =
        # 0.0036. normalize + the validator are pure-Python so they add
        # nothing.
        assert tracker.total("run-resume") == pytest.approx(0.0036)

        slice_list = final["slice_list"]
        assert isinstance(slice_list, list)
        assert len(slice_list) == 3
        for spec in slice_list:
            assert isinstance(spec, SliceSpec)

        # Field-for-field 1:1 mapping: step.index → str(id);
        # step.title → description; step.actions → acceptance.
        assert [s.id for s in slice_list] == ["1", "2", "3"]
        assert slice_list[0].description == "Extract auth module"
        assert slice_list[1].description == "Extract billing module"
        assert slice_list[2].description == "Extract notifications"
        assert slice_list[0].acceptance == ["Move files", "Update imports"]
        assert slice_list[2].acceptance == ["Move files", "Update consumers"]
    finally:
        await checkpointer.conn.close()
        del storage


# ---------------------------------------------------------------------------
# Pure-function normalize node — empty + happy shape
# ---------------------------------------------------------------------------


def test_slice_list_normalize_maps_steps_one_to_one() -> None:
    """AC-3: the normalize node is a pure 1:1 mapping from ``plan.steps``."""
    plan = PlannerPlan.model_validate_json(_three_step_plan_json())
    out = _slice_list_normalize({"plan": plan}, {"configurable": {}})  # type: ignore[arg-type]
    assert set(out.keys()) == {"slice_list"}
    assert [s.id for s in out["slice_list"]] == ["1", "2", "3"]


def test_slice_list_normalize_empty_plan_raises_nonretryable() -> None:
    """AC-4: a plan with ``steps == []`` fails loud as :class:`NonRetryable`."""
    empty_plan = PlannerPlan(
        goal="Nothing to do.",
        summary="No steps.",
        steps=[],
    )
    with pytest.raises(NonRetryable):
        _slice_list_normalize({"plan": empty_plan}, {"configurable": {}})  # type: ignore[arg-type]


def test_slice_list_normalize_missing_plan_raises_nonretryable() -> None:
    """Defence-in-depth: ``state['plan']`` missing → :class:`NonRetryable`."""
    with pytest.raises(NonRetryable):
        _slice_list_normalize({}, {"configurable": {}})  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Build / compile — sanity that the graph structure is the T01 shape
# ---------------------------------------------------------------------------


def test_build_slice_refactor_has_expected_outer_nodes() -> None:
    """Shape-regression guard: outer graph has the T01–T07 node set.

    T01 landed ``planner_subgraph`` + ``slice_list_normalize``. T02
    extended the graph with a compound fan-out target ``slice_worker``
    and a placeholder ``aggregate`` join node. T03 reverts T02's inline-
    parse shortcut and splits the compound node into a per-slice
    sub-graph (``slice_worker`` + ``slice_worker_validator`` with a
    retrying-edge self-loop) registered on the parent graph as a single
    compiled sub-graph node named ``slice_branch``. The internal
    ``slice_worker`` / ``slice_worker_validator`` nodes live on the
    sub-graph's node list, not on the parent's. T04 replaces
    ``aggregate``'s body. T05 adds the strict-review
    ``slice_refactor_review`` ``HumanGate`` node and the ``apply``
    terminal (T06 stub in T05). T07 adds ``hard_stop`` — a terminal
    node reached via the conditional edge from ``slice_branch`` when
    ``len(state["slice_failures"]) >= 2`` (architecture.md §8.2).
    """
    g = build_slice_refactor()
    assert set(g.nodes) == {
        "planner_subgraph",
        "slice_list_normalize",
        "slice_branch",
        "aggregate",
        "slice_refactor_review",
        "apply",
        "hard_stop",
        # M8 T04 fallback-gate surface — four new parent-level nodes.
        "ollama_fallback_stamp",
        "ollama_fallback",
        "ollama_fallback_dispatch",
        "slice_refactor_ollama_abort",
    }


async def test_build_slice_refactor_compiles_against_async_sqlite_saver(
    tmp_path: Path,
) -> None:
    """AC-1: ``build_slice_refactor()`` compiles under ``AsyncSqliteSaver``."""
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    try:
        app = build_slice_refactor().compile(checkpointer=checkpointer)
        assert app is not None
    finally:
        await checkpointer.conn.close()


# ---------------------------------------------------------------------------
# KDR-003 grep — no Anthropic surface in slice_refactor.py
# ---------------------------------------------------------------------------


def test_slice_refactor_module_has_no_anthropic_surface() -> None:
    """KDR-003: no ``import anthropic`` / ``ANTHROPIC_API_KEY`` lookup."""
    source = (
        Path(__file__).resolve().parent.parent.parent
        / "ai_workflows"
        / "workflows"
        / "slice_refactor.py"
    ).read_text(encoding="utf-8")
    for forbidden in ("import anthropic", "from anthropic", "ANTHROPIC_API_KEY"):
        assert forbidden not in source, (
            f"KDR-003 violated: {forbidden!r} appears in slice_refactor.py"
        )
