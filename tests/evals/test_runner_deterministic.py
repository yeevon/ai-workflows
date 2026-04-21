"""Deterministic-mode tests for :class:`EvalRunner` (M7 Task 03).

Replay against the ``planner`` workflow with a :class:`StubLLMAdapter`
standing in for every tier. Each test seeds an in-memory :class:`EvalCase`,
runs the suite, and asserts on the resulting :class:`EvalResult`. The
stub path never hits a live provider so these tests are hermetic.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from ai_workflows.evals import (
    EvalCase,
    EvalRunner,
    EvalSuite,
)
from ai_workflows.workflows import planner as planner_module
from ai_workflows.workflows.planner import (
    ExplorerReport,
    PlannerInput,
    _explorer_prompt,
)


def _valid_explorer_output() -> str:
    return json.dumps(
        {
            "summary": "three-step delivery",
            "considerations": ["tone", "cta"],
            "assumptions": ["design stable"],
        }
    )


def _explorer_case(**overrides: Any) -> EvalCase:
    base: dict[str, Any] = {
        "case_id": "planner-explorer-case-001",
        "workflow_id": "planner",
        "node_name": "explorer",
        "inputs": {
            "run_id": "original-run",
            "input": PlannerInput(goal="ship marketing page").model_dump(
                mode="json"
            ),
        },
        "expected_output": _valid_explorer_output(),
        "output_schema_fqn": (
            f"{ExplorerReport.__module__}.{ExplorerReport.__qualname__}"
        ),
        "captured_at": datetime.now(UTC),
        "captured_from_run_id": "original-run",
    }
    base.update(overrides)
    return EvalCase(**base)


@pytest.mark.asyncio
async def test_deterministic_replay_passes_on_captured_output() -> None:
    """AC-1: passing fixture → :class:`EvalReport` with zero failures."""

    suite = EvalSuite(workflow_id="planner", cases=(_explorer_case(),))
    runner = EvalRunner(mode="deterministic")

    report = await runner.run(suite)

    assert report.mode == "deterministic"
    assert report.suite_workflow_id == "planner"
    assert report.pass_count == 1
    assert report.fail_count == 0
    assert report.results[0].error is None
    assert report.results[0].diff == ""


@pytest.mark.asyncio
async def test_deterministic_replay_fails_on_prompt_template_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-2 (code-side drift): mutating the prompt raises → ``EvalResult.error``.

    Monkey-patches the planner module's ``_explorer_prompt`` so the
    renderer raises ``KeyError`` on a missing state key — exactly the
    failure mode an incompatible prompt-template edit would surface.
    """

    def _broken_prompt(state: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
        # Reference a state key that never exists — simulates a
        # template edit that renamed / removed a field.
        del state["input"].max_steps  # force attribute access then blow up
        return "system", [{"role": "user", "content": state["nope"]}]

    monkeypatch.setattr(planner_module, "_explorer_prompt", _broken_prompt)

    # Rebuild planner so the patched prompt_fn is bound into the graph.
    # (build_planner closes over _explorer_prompt at call time.)
    suite = EvalSuite(workflow_id="planner", cases=(_explorer_case(),))
    runner = EvalRunner(mode="deterministic")

    report = await runner.run(suite)

    assert report.fail_count == 1
    assert report.pass_count == 0
    result = report.results[0]
    assert result.passed is False
    assert result.error is not None
    assert "nope" in result.error or "KeyError" in result.error


@pytest.mark.asyncio
async def test_deterministic_replay_fails_on_schema_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-2 (schema drift): a narrower validator rejects previously-valid output.

    Swap ``ExplorerReport`` in the planner module for a stricter
    local subclass that requires a field the captured output lacks.
    The paired ``ValidatorNode`` raises; the wrap_with_error_handler
    captures it; the runner surfaces it as
    :attr:`EvalResult.error`.
    """

    from pydantic import BaseModel, ConfigDict, Field

    class _StricterExplorerReport(BaseModel):
        model_config = ConfigDict(extra="forbid", frozen=True)

        summary: str
        considerations: list[str]
        assumptions: list[str] = Field(default_factory=list)
        required_extra_field: str  # new required field not in fixture

    # Patch both the class the validator parses against AND the class
    # the tiered_node hands to response_format. Capture's fqn still
    # points at the original name, which is fine — replay uses the
    # live graph which picks up the patched class.
    monkeypatch.setattr(planner_module, "ExplorerReport", _StricterExplorerReport)

    suite = EvalSuite(workflow_id="planner", cases=(_explorer_case(),))
    runner = EvalRunner(mode="deterministic")

    report = await runner.run(suite)

    assert report.fail_count == 1
    result = report.results[0]
    assert result.passed is False
    assert result.error is not None
    # The validation failure must surface — either as a retryable
    # semantic (first attempt) or non-retryable (exhaustion). Both
    # are acceptable — the point is the error is non-empty and
    # references the missing field.
    assert (
        "required_extra_field" in result.error
        or "ExplorerReport" in result.error
        or "validation" in result.error.lower()
    )


@pytest.mark.asyncio
async def test_missing_case_for_fired_node_raises_loudly() -> None:
    """AC-5: suite referencing an unknown node surfaces ``error``, no silent pass.

    Seed a case whose ``node_name`` is not in the ``planner``
    workflow's graph. The runner detects the mismatch before invoke
    and returns an :class:`EvalResult` with ``error=...``.
    """

    orphan = _explorer_case(
        case_id="planner-missing-node",
        node_name="nonexistent_node",
    )
    suite = EvalSuite(workflow_id="planner", cases=(orphan,))
    runner = EvalRunner(mode="deterministic")

    report = await runner.run(suite)

    assert report.fail_count == 1
    result = report.results[0]
    assert result.passed is False
    assert result.error is not None
    assert "nonexistent_node" in result.error


@pytest.mark.asyncio
async def test_summary_lines_report_pass_and_fail_counts() -> None:
    """:meth:`EvalReport.summary_lines` renders a human-readable report."""

    passing = _explorer_case(case_id="case-pass")
    failing = _explorer_case(
        case_id="case-fail", node_name="nonexistent_node"
    )
    suite = EvalSuite(workflow_id="planner", cases=(passing, failing))
    runner = EvalRunner(mode="deterministic")

    report = await runner.run(suite)
    lines = report.summary_lines()

    # Header + 2 per-case lines.
    assert len(lines) == 3
    assert "1 passed" in lines[0]
    assert "1 failed" in lines[0]
    assert any("[PASS]" in line and "case-pass" in line for line in lines[1:])
    assert any("[FAIL]" in line and "case-fail" in line for line in lines[1:])


@pytest.mark.asyncio
async def test_explorer_prompt_symbol_exists_for_template_drift_test() -> None:
    """Pin the precondition used by the prompt-template-drift test.

    If the planner ever renames ``_explorer_prompt``, the drift test
    would silently stop monkey-patching. This guard flags that the
    moment it happens.
    """

    assert callable(_explorer_prompt)


def test_resolve_node_scope_walks_into_compiled_subgraphs() -> None:
    """M7-T05: runner resolves nodes wired inside compiled sub-graphs.

    ``slice_refactor`` wraps ``slice_worker`` + ``slice_worker_validator``
    inside the compiled ``slice_branch`` sub-graph — neither node name
    appears in ``build_slice_refactor().nodes``. The runner must walk
    each top-level runnable's ``.builder`` to find them, and must
    return the *sub-graph's* state schema (``SliceBranchState``) for
    the replay graph construction.

    Regression guard against the T03 flat-node-lookup gap that T05
    surfaces (``_EvalCaseError: case references node 'slice_worker'
    which is not registered in workflow 'slice_refactor'``).
    """

    from ai_workflows.evals.runner import (
        _node_exists_anywhere,
        _resolve_node_scope,
    )
    from ai_workflows.workflows.slice_refactor import (
        SliceBranchState,
        build_slice_refactor,
    )

    graph = build_slice_refactor()

    # Sanity: the node is not at the top level.
    assert "slice_worker" not in graph.nodes
    assert "slice_worker_validator" not in graph.nodes

    # It IS reachable via sub-graph walk.
    assert _node_exists_anywhere(graph, "slice_worker") is True
    resolution = _resolve_node_scope(
        graph, "slice_worker", "slice_worker_validator"
    )
    assert resolution is not None
    state_schema, target_spec, validator_spec = resolution
    assert state_schema is SliceBranchState
    assert target_spec.runnable is not None
    assert validator_spec.runnable is not None


def test_resolve_node_scope_returns_none_on_missing_validator() -> None:
    """Missing paired validator → ``None`` (caller maps to _EvalCaseError).

    Guards the KDR-004 pairing contract: even if the target node is
    found (top-level or sub-graph), a missing validator in the same
    scope must not silently drop into a validator-less replay.
    """

    from ai_workflows.evals.runner import _resolve_node_scope
    from ai_workflows.workflows.planner import build_planner

    graph = build_planner()
    # explorer is at the top level with a paired validator — but ask
    # for a non-existent validator name to trip the pair check.
    resolution = _resolve_node_scope(graph, "explorer", "nonexistent_validator")
    assert resolution is None
