"""Unit tests for :class:`CaptureCallback` (M7 Task 02)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import structlog
from pydantic import BaseModel, ConfigDict

from ai_workflows.evals import CaptureCallback, EvalCase, output_schema_fqn


class _FakeSchema(BaseModel):
    """Stand-in for a workflow's output_schema (tests only)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    summary: str


def _make_callback(tmp_path: Path, **overrides: Any) -> CaptureCallback:
    defaults: dict[str, Any] = {
        "dataset_name": "testsuite",
        "workflow_id": "planner",
        "run_id": "run-001",
        "root": tmp_path / "testsuite",
    }
    defaults.update(overrides)
    return CaptureCallback(**defaults)


def test_on_node_complete_writes_fixture(tmp_path: Path) -> None:
    callback = _make_callback(tmp_path)
    path = callback.on_node_complete(
        run_id="run-001",
        node_name="explorer",
        inputs={"goal": "write a checklist"},
        raw_output='{"summary": "ok"}',
        output_schema=_FakeSchema,
    )
    assert path is not None
    assert path.exists()
    assert path.parent == tmp_path / "testsuite" / "planner" / "explorer"
    reloaded = EvalCase.model_validate_json(path.read_text(encoding="utf-8"))
    assert reloaded.workflow_id == "planner"
    assert reloaded.node_name == "explorer"
    assert reloaded.captured_from_run_id == "run-001"
    assert reloaded.inputs == {"goal": "write a checklist"}
    assert reloaded.expected_output == '{"summary": "ok"}'
    assert reloaded.output_schema_fqn == (
        "tests.evals.test_capture_callback._FakeSchema"
    )


def test_records_output_schema_fqn_for_known_schema() -> None:
    assert (
        output_schema_fqn(_FakeSchema)
        == "tests.evals.test_capture_callback._FakeSchema"
    )


def test_records_none_schema_fqn_for_free_text_node(tmp_path: Path) -> None:
    callback = _make_callback(tmp_path)
    path = callback.on_node_complete(
        run_id="run-001",
        node_name="freeform",
        inputs={"prompt": "hi"},
        raw_output="hello back",
        output_schema=None,
    )
    assert path is not None
    case = EvalCase.model_validate_json(path.read_text(encoding="utf-8"))
    assert case.output_schema_fqn is None
    assert case.expected_output == "hello back"


def test_appends_numeric_suffix_on_duplicate_case_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    callback = _make_callback(tmp_path)
    # Pin uuid.uuid4 so we get deterministic case_ids that collide.
    import uuid

    class _FrozenUUID:
        hex = "deadbeefcafebabeaaaaaaaaaaaaaaaa"

    monkeypatch.setattr(uuid, "uuid4", lambda: _FrozenUUID())
    # Pin datetime so the timestamp portion of the case_id stays stable.
    from datetime import UTC, datetime

    import ai_workflows.evals.capture_callback as mod

    frozen = datetime(2026, 4, 21, 12, 0, 0, tzinfo=UTC)

    class _FrozenDT:
        @staticmethod
        def now(tz: Any = UTC) -> datetime:
            return frozen

    monkeypatch.setattr(mod, "datetime", _FrozenDT)

    path_a = callback.on_node_complete(
        run_id="run-001",
        node_name="explorer",
        inputs={"goal": "x"},
        raw_output="first",
        output_schema=None,
    )
    path_b = callback.on_node_complete(
        run_id="run-001",
        node_name="explorer",
        inputs={"goal": "x"},
        raw_output="second",
        output_schema=None,
    )
    assert path_a is not None
    assert path_b is not None
    assert path_a != path_b
    assert path_b.name.endswith("-002.json")


def test_capture_failure_logs_warning_but_does_not_raise(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A disk-write failure emits a structlog warning + returns None.

    0.1.3 patch: pre-patch this module logged via stdlib `logging` and the
    test asserted against `caplog`. The 0.1.3 observability fix switched
    the logger to structlog (KDR observability discipline); the assertion
    now uses `structlog.testing.capture_logs`. Event name also changed
    from free-text ``"eval capture failed"`` to snake-case
    ``"eval_capture_failed"`` matching the structlog convention used
    elsewhere in the package.
    """
    callback = _make_callback(tmp_path)

    def _boom(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("disk full")

    import ai_workflows.evals.capture_callback as mod

    monkeypatch.setattr(mod, "fixture_path", _boom)

    with structlog.testing.capture_logs() as captured:
        result = callback.on_node_complete(
            run_id="run-001",
            node_name="explorer",
            inputs={"goal": "x"},
            raw_output="noop",
            output_schema=None,
        )
    assert result is None
    assert any(
        event.get("event") == "eval_capture_failed"
        and event.get("log_level") == "warning"
        for event in captured
    )


def test_root_defaults_to_evals_root_slash_dataset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIW_EVALS_ROOT", str(tmp_path))
    callback = CaptureCallback(
        dataset_name="mydataset",
        workflow_id="planner",
        run_id="run-001",
    )
    assert callback.root == tmp_path / "mydataset"


def test_normalizes_pydantic_inputs(tmp_path: Path) -> None:
    class _Input(BaseModel):
        model_config = ConfigDict(extra="forbid", frozen=True)

        goal: str
        budget_cap_usd: float | None

    callback = _make_callback(tmp_path)
    inp = _Input(goal="go", budget_cap_usd=1.0)
    path = callback.on_node_complete(
        run_id="run-001",
        node_name="explorer",
        inputs={"input": inp, "run_id": "run-001"},
        raw_output="ok",
        output_schema=None,
    )
    assert path is not None
    case = EvalCase.model_validate_json(path.read_text(encoding="utf-8"))
    assert case.inputs["input"] == {"goal": "go", "budget_cap_usd": 1.0}
    assert case.inputs["run_id"] == "run-001"
