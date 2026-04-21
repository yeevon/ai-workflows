"""Storage-helper tests for the M7 Task 01 eval substrate."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ai_workflows.evals import (
    EvalCase,
    EvalSuite,
    default_evals_root,
    fixture_path,
    load_case,
    load_suite,
    save_case,
)


def _case(**overrides: object) -> EvalCase:
    defaults: dict[str, object] = {
        "case_id": "planner-happy-01",
        "workflow_id": "planner",
        "node_name": "explorer",
        "inputs": {"goal": "hello"},
        "expected_output": {"summary": "ok", "notes": "raw"},
        "output_schema_fqn": "ai_workflows.workflows.planner.ExplorerReport",
        "captured_at": datetime(2026, 4, 21, 12, 0, tzinfo=UTC),
        "captured_from_run_id": "run-001",
    }
    defaults.update(overrides)
    return EvalCase(**defaults)  # type: ignore[arg-type]


def test_fixture_path_matches_canonical_layout(tmp_path: Path) -> None:
    path = fixture_path(tmp_path, "planner", "explorer", "happy-01")
    assert path == tmp_path / "planner" / "explorer" / "happy-01.json"


def test_save_case_writes_canonical_path(tmp_path: Path) -> None:
    case = _case()
    written = save_case(case, tmp_path)
    assert written == tmp_path / "planner" / "explorer" / "planner-happy-01.json"
    assert written.exists()
    reloaded = load_case(written)
    assert reloaded == case


def test_save_case_refuses_overwrite_by_default(tmp_path: Path) -> None:
    case = _case()
    save_case(case, tmp_path)
    with pytest.raises(FileExistsError):
        save_case(case, tmp_path)


def test_save_case_overwrite_flag_allows_replacement(tmp_path: Path) -> None:
    case_a = _case(metadata={"rev": "1"})
    save_case(case_a, tmp_path)
    case_b = _case(metadata={"rev": "2"})
    path = save_case(case_b, tmp_path, overwrite=True)
    reloaded = load_case(path)
    assert reloaded.metadata == {"rev": "2"}


def test_load_suite_aggregates_nested_cases(tmp_path: Path) -> None:
    cases = [
        _case(case_id="explorer-01", node_name="explorer"),
        _case(case_id="explorer-02", node_name="explorer"),
        _case(case_id="synth-01", node_name="synth"),
    ]
    for case in cases:
        save_case(case, tmp_path)
    suite = load_suite("planner", tmp_path)
    assert isinstance(suite, EvalSuite)
    assert suite.workflow_id == "planner"
    assert len(suite.cases) == 3
    assert {c.case_id for c in suite.cases} == {"explorer-01", "explorer-02", "synth-01"}


def test_load_suite_ignores_non_json_files(tmp_path: Path) -> None:
    case = _case()
    save_case(case, tmp_path)
    stray = tmp_path / "planner" / "README.md"
    stray.write_text("# notes", encoding="utf-8")
    suite = load_suite("planner", tmp_path)
    assert len(suite.cases) == 1


def test_load_suite_missing_workflow_returns_empty(tmp_path: Path) -> None:
    suite = load_suite("nonexistent", tmp_path)
    assert suite.workflow_id == "nonexistent"
    assert suite.cases == ()


def test_default_evals_root_honours_env_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIW_EVALS_ROOT", str(tmp_path))
    assert default_evals_root() == tmp_path


def test_default_evals_root_unset_uses_relative_evals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AIW_EVALS_ROOT", raising=False)
    assert default_evals_root() == Path("evals")


def test_round_trip_preserves_tolerance_overrides(tmp_path: Path) -> None:
    from ai_workflows.evals import EvalTolerance

    tolerance = EvalTolerance(
        mode="strict_json",
        field_overrides={"summary": "substring", "notes": "regex"},
    )
    case = _case(tolerance=tolerance)
    path = save_case(case, tmp_path)
    reloaded = load_case(path)
    assert reloaded.tolerance == tolerance
