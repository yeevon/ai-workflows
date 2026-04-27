"""Regression tests for M19 Task 03 — result-shape artefact-field correctness.

Spec: design_docs/phases/milestone_19_declarative_surface/task_03_result_shape.md
Deliverable 5: five hermetic tests pinning the corrected artefact-surfacing
behaviour introduced by the M19 T03 migration.

Each test registers a stub workflow whose state graph terminates immediately
(no LLM calls) and asserts that both ``artifact`` (canonical) and ``plan``
(deprecated alias) are populated correctly in the dispatch result dict.

Relationship to other modules
------------------------------
* :mod:`ai_workflows.workflows._dispatch` — the five call sites under test
  (``_build_result_from_final`` and ``_build_resume_result_from_final``).
* :mod:`ai_workflows.mcp.schemas` — ``RunWorkflowOutput.artifact`` /
  ``ResumeRunOutput.artifact`` schema rename exercised indirectly through
  the result dict shape.
* :mod:`ai_workflows.workflows` — ``register`` / ``_reset_for_tests`` for
  stub-workflow registration.
"""

from __future__ import annotations

import sys
import types
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from langgraph.graph import StateGraph

from ai_workflows import workflows
from ai_workflows.workflows._dispatch import resume_run, run_workflow

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_registry() -> Iterator[None]:
    """Isolate registry state — clear before and after each test."""
    workflows._reset_for_tests()
    yield
    workflows._reset_for_tests()


@pytest.fixture(autouse=True)
def _redirect_db_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect SQLite files to a temp dir so tests don't touch the real DB."""
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("AIW_STORAGE_DB", str(tmp_path / "storage.sqlite"))


# ---------------------------------------------------------------------------
# Stub workflow helpers
# ---------------------------------------------------------------------------


def _make_stub_module(
    *,
    workflow_name: str,
    final_state_key: str,
    artefact_value: Any,
    terminal_gate_id: str | None = None,
) -> types.ModuleType:
    """Return a minimal fake module that dispatch can drive through
    :func:`_import_workflow_module`.

    The produced ``StateGraph`` has a single node that writes
    ``artefact_value`` directly to ``final_state_key`` and then
    completes — no LLM, no gate.
    """
    mod = types.ModuleType(f"_stub_{workflow_name}")
    mod.FINAL_STATE_KEY = final_state_key  # type: ignore[attr-defined]
    if terminal_gate_id is not None:
        mod.TERMINAL_GATE_ID = terminal_gate_id  # type: ignore[attr-defined]

    # initial_state hook so dispatch does not need PlannerInput
    def initial_state(run_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        return {"run_id": run_id, final_state_key: None}

    mod.initial_state = initial_state  # type: ignore[attr-defined]

    # State type — plain dict (StateGraph accepts a TypedDict class or a
    # plain dict as the state schema; using dict[str, Any] directly is the
    # simplest portable path)
    def build() -> StateGraph:
        graph: StateGraph = StateGraph(dict)

        async def terminal_node(state: dict) -> dict:
            return {final_state_key: artefact_value}

        graph.add_node("terminal", terminal_node)
        graph.set_entry_point("terminal")
        graph.set_finish_point("terminal")
        return graph

    mod.build = build  # type: ignore[attr-defined]
    # no tier registry (empty → no LLM calls needed)
    return mod


def _register_stub(
    workflow_name: str,
    mod: types.ModuleType,
) -> None:
    """Register the stub builder and plant the module in sys.modules so
    :func:`_import_workflow_module` resolves it without a real import."""
    sys.modules[f"_stub_{workflow_name}"] = mod

    def builder() -> StateGraph:
        return mod.build()  # type: ignore[attr-defined]

    builder.__module__ = mod.__name__
    workflows.register(workflow_name, builder)


# ---------------------------------------------------------------------------
# Test 1 — external workflow artefact round-trips via ``artifact`` field
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_external_workflow_artifact_round_trips_via_artifact_field() -> None:
    """AC Deliverable 5.1 — ``result["artifact"]`` carries the workflow's terminal
    artefact for a workflow with ``FINAL_STATE_KEY = "questions"``.

    Before M19 T03 this field was absent / populated from the wrong state
    key; the fix reads ``final.get(final_state_key)`` at all five call sites.
    """
    questions_value = {"q1": "What is scope?", "q2": "Who owns delivery?"}
    mod = _make_stub_module(
        workflow_name="question_gen",
        final_state_key="questions",
        artefact_value=questions_value,
    )
    _register_stub("question_gen", mod)

    result = await run_workflow(
        workflow="question_gen",
        inputs={},
        run_id="test-qgen-01",
    )

    assert result["status"] == "completed", result
    assert result["artifact"] == questions_value, (
        f"artifact field missing or wrong: {result}"
    )


# ---------------------------------------------------------------------------
# Test 2 — deprecated ``plan`` alias is populated alongside ``artifact``
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_external_workflow_artifact_also_surfaces_via_plan_alias() -> None:
    """AC Deliverable 5.2 — ``result["plan"] == result["artifact"]`` (alias populated).

    Backward-compatibility for 0.2.0 callers reading ``result["plan"]``
    must not break even when ``FINAL_STATE_KEY != "plan"``.
    """
    questions_value = {"q1": "What is scope?", "q2": "Who owns delivery?"}
    mod = _make_stub_module(
        workflow_name="question_gen_alias",
        final_state_key="questions",
        artefact_value=questions_value,
    )
    _register_stub("question_gen_alias", mod)

    result = await run_workflow(
        workflow="question_gen_alias",
        inputs={},
        run_id="test-qgen-alias-01",
    )

    assert result["status"] == "completed", result
    assert result["plan"] == result["artifact"], (
        f"plan alias does not match artifact: plan={result['plan']!r} "
        f"artifact={result['artifact']!r}"
    )
    assert result["plan"] == questions_value


# ---------------------------------------------------------------------------
# Test 3 — in-tree planner-shaped workflow (FINAL_STATE_KEY = "plan")
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_in_tree_planner_unchanged_artifact_path() -> None:
    """AC Deliverable 5.3 — ``FINAL_STATE_KEY = "plan"`` workflows still work.

    Pins the escape-hatch behaviour for the in-tree planner workflow
    which stays on ``FINAL_STATE_KEY = "plan"``.  Both fields are
    populated and equal.
    """
    plan_value = {"goal": "Ship it.", "steps": [{"index": 1, "title": "Draft"}]}
    mod = _make_stub_module(
        workflow_name="stub_planner",
        final_state_key="plan",
        artefact_value=plan_value,
    )
    _register_stub("stub_planner", mod)

    result = await run_workflow(
        workflow="stub_planner",
        inputs={},
        run_id="test-stub-planner-01",
    )

    assert result["status"] == "completed", result
    assert result["artifact"] == plan_value
    assert result["plan"] == result["artifact"]


# ---------------------------------------------------------------------------
# Test 4 — resume path populates both fields
# ---------------------------------------------------------------------------


def _make_gated_stub_module(
    workflow_name: str,
    final_state_key: str,
    artefact_value: Any,
    gate_id: str = "review",
) -> types.ModuleType:
    """Return a stub module whose graph pauses at a HumanGate then completes."""
    from ai_workflows.graph.human_gate import human_gate

    mod = types.ModuleType(f"_stub_{workflow_name}")
    mod.FINAL_STATE_KEY = final_state_key  # type: ignore[attr-defined]
    mod.TERMINAL_GATE_ID = gate_id  # type: ignore[attr-defined]

    def initial_state(run_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        return {
            "run_id": run_id,
            final_state_key: None,
            f"gate_{gate_id}_response": None,
        }

    mod.initial_state = initial_state  # type: ignore[attr-defined]

    def build() -> StateGraph:
        graph: StateGraph = StateGraph(dict)

        # gate node — pauses via interrupt
        gate_node = human_gate(
            gate_id=gate_id,
            prompt_fn=lambda state: "Please review.",
            strict_review=False,
        )
        graph.add_node("gate", gate_node)

        # completion node — writes the artefact
        async def complete_node(state: dict) -> dict:
            return {final_state_key: artefact_value}

        graph.add_node("complete", complete_node)

        graph.set_entry_point("gate")
        graph.add_edge("gate", "complete")
        graph.set_finish_point("complete")
        return graph

    mod.build = build  # type: ignore[attr-defined]
    return mod


@pytest.mark.asyncio
async def test_resume_path_populates_both_fields(tmp_path: Path) -> None:
    """AC Deliverable 5.4 — resume path populates both ``artifact`` and ``plan``.

    Pauses a stub run at a HumanGate, then resumes with ``"approved"``.
    Asserts the resume response carries both fields populated.
    """
    artefact = {"answer": 42}
    gate_id = "review"
    mod = _make_gated_stub_module(
        workflow_name="gated_wf",
        final_state_key="result",
        artefact_value=artefact,
        gate_id=gate_id,
    )
    _register_stub("gated_wf", mod)

    # First dispatch — should pause at the gate
    run_result = await run_workflow(
        workflow="gated_wf",
        inputs={},
        run_id="test-resume-01",
    )
    assert run_result["status"] == "pending", (
        f"expected pending, got: {run_result}"
    )
    assert run_result["awaiting"] == "gate"

    # Resume with approval
    resume_result = await resume_run(
        run_id="test-resume-01",
        gate_response="approved",
    )
    assert resume_result["status"] == "completed", (
        f"expected completed, got: {resume_result}"
    )
    assert resume_result["artifact"] == artefact, (
        f"artifact missing in resume result: {resume_result}"
    )
    assert resume_result["plan"] == resume_result["artifact"], (
        f"plan alias mismatch in resume result: {resume_result}"
    )


# ---------------------------------------------------------------------------
# Test 5 — error path emits None for both fields
# ---------------------------------------------------------------------------


def _make_error_stub_module(workflow_name: str) -> types.ModuleType:
    """Return a stub module whose graph raises an exception mid-run."""
    mod = types.ModuleType(f"_stub_{workflow_name}")
    mod.FINAL_STATE_KEY = "result"  # type: ignore[attr-defined]

    def initial_state(run_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        return {"run_id": run_id, "result": None}

    mod.initial_state = initial_state  # type: ignore[attr-defined]

    def build() -> StateGraph:
        graph: StateGraph = StateGraph(dict)

        async def raising_node(state: dict) -> dict:
            raise RuntimeError("deliberate error for test_error_path")

        graph.add_node("bad", raising_node)
        graph.set_entry_point("bad")
        graph.set_finish_point("bad")
        return graph

    mod.build = build  # type: ignore[attr-defined]
    return mod


@pytest.mark.asyncio
async def test_error_path_emits_none_for_both_fields() -> None:
    """AC Deliverable 5.5 — errored response has ``artifact: None`` and ``plan: None``.

    Lockstep behaviour across every error path is required so callers can
    safely read either field without a ``KeyError`` on the errored branch.
    """
    mod = _make_error_stub_module("error_wf")
    _register_stub("error_wf", mod)

    result = await run_workflow(
        workflow="error_wf",
        inputs={},
        run_id="test-error-01",
    )

    assert result["status"] == "errored", (
        f"expected errored, got: {result}"
    )
    assert "artifact" in result, "artifact key missing from errored result"
    assert "plan" in result, "plan key missing from errored result"
    assert result["artifact"] is None, (
        f"artifact should be None on error path, got: {result['artifact']!r}"
    )
    assert result["plan"] is None, (
        f"plan should be None on error path, got: {result['plan']!r}"
    )
