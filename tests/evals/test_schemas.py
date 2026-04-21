"""Schema-level tests for the M7 Task 01 eval substrate."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ai_workflows.evals import EvalCase, EvalSuite, EvalTolerance


def _make_case(
    *,
    case_id: str = "planner-happy-01",
    workflow_id: str = "planner",
    node_name: str = "explorer",
    tolerance: EvalTolerance | None = None,
) -> EvalCase:
    return EvalCase(
        case_id=case_id,
        workflow_id=workflow_id,
        node_name=node_name,
        inputs={"goal": "write a checklist"},
        expected_output={"summary": "checklist", "notes": "free text"},
        output_schema_fqn="ai_workflows.workflows.planner.ExplorerReport",
        tolerance=tolerance or EvalTolerance(),
        captured_at=datetime(2026, 4, 21, 12, 0, tzinfo=UTC),
        captured_from_run_id="run-001",
    )


def test_eval_case_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        EvalCase(
            case_id="x",
            workflow_id="planner",
            node_name="explorer",
            inputs={},
            expected_output={},
            captured_at=datetime(2026, 4, 21, tzinfo=UTC),
            unknown_field="bad",  # type: ignore[call-arg]
        )


def test_eval_case_is_frozen() -> None:
    case = _make_case()
    with pytest.raises(ValidationError):
        case.case_id = "mutated"  # type: ignore[misc]


def test_eval_case_serialization_round_trip() -> None:
    tolerance = EvalTolerance(
        mode="strict_json",
        field_overrides={"summary": "substring", "notes": "regex"},
    )
    case = _make_case(tolerance=tolerance)
    raw = case.model_dump_json()
    restored = EvalCase.model_validate_json(raw)
    assert restored == case
    assert restored.tolerance.field_overrides == {
        "summary": "substring",
        "notes": "regex",
    }


def test_eval_tolerance_defaults_to_strict_json_with_no_overrides() -> None:
    tolerance = EvalTolerance()
    assert tolerance.mode == "strict_json"
    assert tolerance.field_overrides == {}


def test_eval_tolerance_rejects_unknown_mode() -> None:
    with pytest.raises(ValidationError):
        EvalTolerance(mode="fuzzy")  # type: ignore[arg-type]


def test_eval_tolerance_rejects_unknown_field_override_mode() -> None:
    with pytest.raises(ValidationError):
        EvalTolerance(field_overrides={"summary": "fuzzy"})  # type: ignore[arg-type,dict-item]


def test_eval_suite_empty_cases_allowed() -> None:
    suite = EvalSuite(workflow_id="planner")
    assert suite.cases == ()


def test_eval_suite_rejects_mismatched_workflow_id() -> None:
    case = _make_case(workflow_id="planner")
    with pytest.raises(ValidationError):
        EvalSuite(workflow_id="slice_refactor", cases=(case,))


def test_eval_suite_accepts_multiple_cases_under_same_workflow() -> None:
    case_a = _make_case(case_id="a", node_name="explorer")
    case_b = _make_case(case_id="b", node_name="synth")
    suite = EvalSuite(workflow_id="planner", cases=(case_a, case_b))
    assert len(suite.cases) == 2
    assert {c.node_name for c in suite.cases} == {"explorer", "synth"}
