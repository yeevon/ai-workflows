"""Tests for M7 Task 04 — ``aiw eval capture`` + ``aiw eval run``.

Covers the acceptance criteria pinned by
``design_docs/phases/milestone_7_evals/task_04_cli_surface.md``:

* ``aiw eval run`` deterministic all-pass path → exit 0.
* ``aiw eval run`` with a broken fixture → exit 1.
* Unknown workflow → exit 2.
* ``aiw eval run --live`` without ``AIW_EVAL_LIVE`` / ``AIW_E2E`` → exit 2.
* ``aiw eval capture`` against a non-completed run → exit 2.
* ``aiw eval capture`` against a completed + checkpointed run writes
  fixtures under ``evals/<dataset>/<workflow>/<node>/*.json``.
* ``aiw eval`` sub-group surfaces under ``aiw --help``.

Autouse fixtures mirror the M3 T04 / T06 pattern: stub
``LiteLLMAdapter`` at the tiered-node boundary, redirect default
Storage + checkpointer paths under ``tmp_path``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from ai_workflows import workflows
from ai_workflows.cli import app
from ai_workflows.evals import EvalCase, save_case
from ai_workflows.evals.schemas import EvalTolerance
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.tiers import LiteLLMRoute
from ai_workflows.workflows.planner import (
    ExplorerReport,
    PlannerInput,
    build_planner,
)

_RUNNER = CliRunner()


# ---------------------------------------------------------------------------
# Stub LiteLLM adapter (mirrors tests/cli/test_run.py)
# ---------------------------------------------------------------------------


class _StubLiteLLMAdapter:
    """Scripted LiteLLM-adapter stub so no real HTTP call fires."""

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
            input_tokens=11,
            output_tokens=17,
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
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _StubLiteLLMAdapter)


@pytest.fixture(autouse=True)
def _reensure_planner_registered() -> Iterator[None]:
    """Snapshot + restore the workflow registry around each test.

    Pre-yield: reset and register only ``planner`` so each test starts with
    a known minimal registry. Post-yield: restore the full registry the
    test module saw at import time. Without this restore, any later test
    module that needs ``slice_refactor`` (or any non-``planner`` workflow)
    finds an empty slot — a session-wide pollution that M7-T05 first
    tripped on (``test_slice_refactor_seed_fixtures_replay_green_deterministic``).
    Resolves the M7-T05-ISS-01 carry-over.
    """

    snapshot = dict(workflows._REGISTRY)
    workflows._reset_for_tests()
    workflows.register("planner", build_planner)
    try:
        yield
    finally:
        workflows._reset_for_tests()
        for name, builder in snapshot.items():
            workflows.register(name, builder)


@pytest.fixture(autouse=True)
def _redirect_default_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("AIW_STORAGE_DB", str(tmp_path / "storage.sqlite"))


@pytest.fixture(autouse=True)
def _isolate_evals_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Route ``default_evals_root()`` under ``tmp_path`` for every test."""
    evals_root = tmp_path / "evals"
    monkeypatch.setenv("AIW_EVALS_ROOT", str(evals_root))
    return evals_root


# ---------------------------------------------------------------------------
# Canonical payloads
# ---------------------------------------------------------------------------


def _valid_explorer_json() -> str:
    return json.dumps(
        {
            "summary": "Three-step delivery.",
            "considerations": ["Copy tone", "CTA placement"],
            "assumptions": ["Design system stable"],
        }
    )


def _valid_plan_json() -> str:
    return json.dumps(
        {
            "goal": "Ship the marketing page.",
            "summary": "Three-step delivery of the static hero + CTA page.",
            "steps": [
                {
                    "index": 1,
                    "title": "Draft hero copy",
                    "rationale": "Lock tone before layout.",
                    "actions": ["Sketch headline", "List CTAs"],
                }
            ],
        }
    )


def _seed_planner_script() -> None:
    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
    ]


def _write_explorer_case(
    root: Path,
    *,
    case_id: str,
    expected_output: str,
) -> EvalCase:
    """Drop one explorer-node EvalCase into ``root`` for replay."""

    case = EvalCase(
        case_id=case_id,
        workflow_id="planner",
        node_name="explorer",
        inputs={
            "run_id": "test-seed-run",
            "input": PlannerInput(goal="Ship the marketing page.").model_dump(
                mode="json"
            ),
        },
        expected_output=expected_output,
        output_schema_fqn=(
            f"{ExplorerReport.__module__}.{ExplorerReport.__qualname__}"
        ),
        captured_at=datetime.now(UTC),
        captured_from_run_id="test-seed-run",
        tolerance=EvalTolerance(mode="strict_json"),
    )
    save_case(case, root)
    return case


# ---------------------------------------------------------------------------
# `aiw eval` help surface
# ---------------------------------------------------------------------------


def test_eval_help_lists_capture_and_run() -> None:
    """AC-4: the ``eval`` sub-group surfaces both subcommands."""

    result = _RUNNER.invoke(app, ["eval", "--help"])
    assert result.exit_code == 0, result.output
    assert "capture" in result.output
    assert "run" in result.output


def test_root_help_lists_eval_sub_group() -> None:
    """AC-4 companion: ``aiw --help`` includes ``eval``."""

    result = _RUNNER.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "eval" in result.output


# ---------------------------------------------------------------------------
# `aiw eval run`
# ---------------------------------------------------------------------------


def test_eval_run_all_pass_exit_zero(tmp_path: Path) -> None:
    """AC-2: a passing fixture suite in deterministic mode exits 0."""

    evals_root = tmp_path / "evals"
    _write_explorer_case(
        evals_root,
        case_id="planner-explorer-happy-01",
        expected_output=_valid_explorer_json(),
    )

    result = _RUNNER.invoke(app, ["eval", "run", "planner"])
    assert result.exit_code == 0, result.output
    assert "1 passed" in result.output
    assert "0 failed" in result.output
    assert "[PASS]" in result.output


def test_eval_run_any_fail_exit_one(tmp_path: Path) -> None:
    """AC-2: a broken fixture in deterministic mode exits 1."""

    evals_root = tmp_path / "evals"
    # Expected output is valid JSON but the *actual* node output differs:
    # we force drift by seeding ``expected_output`` that no longer matches
    # what the stub would render. The stub returns expected_output
    # verbatim — so to force a mismatch we use a different schema in the
    # tolerance compare step by seeding an expected_output JSON that fails
    # the stricter schema validation. Simpler: a fixture referencing an
    # unknown node name — guaranteed fail per T03 AC-5.
    broken = EvalCase(
        case_id="planner-explorer-broken-01",
        workflow_id="planner",
        node_name="nonexistent_node",
        inputs={
            "run_id": "test-seed-run",
            "input": PlannerInput(goal="Ship it.").model_dump(mode="json"),
        },
        expected_output=_valid_explorer_json(),
        output_schema_fqn=None,
        captured_at=datetime.now(UTC),
        captured_from_run_id="test-seed-run",
    )
    save_case(broken, evals_root)

    result = _RUNNER.invoke(app, ["eval", "run", "planner"])
    assert result.exit_code == 1, result.output
    assert "[FAIL]" in result.output
    assert "1 failed" in result.output


def test_eval_run_unknown_workflow_exits_two() -> None:
    """AC-2: unknown workflow id exits 2 with a readable error."""

    result = _RUNNER.invoke(app, ["eval", "run", "bogus_workflow"])
    assert result.exit_code == 2, result.output
    assert "unknown workflow" in result.output
    assert "bogus_workflow" in result.output


def test_eval_run_live_requires_both_env_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-3: ``--live`` without BOTH env vars exits 2 with a clear message."""

    # Neither set.
    monkeypatch.delenv("AIW_EVAL_LIVE", raising=False)
    monkeypatch.delenv("AIW_E2E", raising=False)
    result = _RUNNER.invoke(app, ["eval", "run", "planner", "--live"])
    assert result.exit_code == 2, result.output
    assert "AIW_EVAL_LIVE" in result.output

    # Only one half set — still exit 2.
    monkeypatch.setenv("AIW_EVAL_LIVE", "1")
    monkeypatch.delenv("AIW_E2E", raising=False)
    result = _RUNNER.invoke(app, ["eval", "run", "planner", "--live"])
    assert result.exit_code == 2, result.output
    assert "AIW_E2E" in result.output


def test_eval_run_dataset_scopes_suite_load(tmp_path: Path) -> None:
    """``--dataset <name>`` only loads cases under that dataset sub-tree."""

    evals_root = tmp_path / "evals"

    # Write a passing case under the target dataset.
    _write_explorer_case(
        evals_root / "scoped_dataset",
        case_id="planner-explorer-scoped-01",
        expected_output=_valid_explorer_json(),
    )

    # Write a BROKEN case under an unrelated dataset — if the dataset
    # flag is ignored the scoped run will fail because this one is
    # picked up too.
    broken = EvalCase(
        case_id="other-dataset-broken",
        workflow_id="planner",
        node_name="nonexistent_node",
        inputs={"run_id": "x", "input": {"goal": "x"}},
        expected_output="{}",
        output_schema_fqn=None,
        captured_at=datetime.now(UTC),
        captured_from_run_id="x",
    )
    save_case(broken, evals_root / "other_dataset")

    result = _RUNNER.invoke(
        app, ["eval", "run", "planner", "--dataset", "scoped_dataset"]
    )
    assert result.exit_code == 0, result.output
    assert "1 passed" in result.output


def test_eval_run_empty_suite_exits_one(tmp_path: Path) -> None:
    """Empty suite is treated as a fail (exit 1) — an empty suite means no signal."""

    # No fixtures written.
    result = _RUNNER.invoke(app, ["eval", "run", "planner"])
    assert result.exit_code == 1, result.output
    assert "no eval cases" in result.output


# ---------------------------------------------------------------------------
# `aiw eval capture`
# ---------------------------------------------------------------------------


def test_eval_capture_requires_completed_run(tmp_path: Path) -> None:
    """AC-1: capture exits 2 on a non-completed run_id."""

    # Seed a pending run via direct storage write, with no checkpoint behind it.
    import asyncio

    from ai_workflows.primitives.storage import SQLiteStorage

    async def _seed() -> None:
        storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
        await storage.create_run(
            run_id="run-pending-01",
            workflow_id="planner",
            budget_cap_usd=None,
        )

    asyncio.run(_seed())

    result = _RUNNER.invoke(
        app,
        [
            "eval",
            "capture",
            "--run-id",
            "run-pending-01",
            "--dataset",
            "testsuite",
        ],
    )
    assert result.exit_code == 2, result.output
    assert "run-pending-01" in result.output


def test_eval_capture_unknown_run_exits_two() -> None:
    """Capture exits 2 when the run_id has no matching ``runs`` row."""

    result = _RUNNER.invoke(
        app,
        [
            "eval",
            "capture",
            "--run-id",
            "does-not-exist",
            "--dataset",
            "testsuite",
        ],
    )
    assert result.exit_code == 2, result.output
    assert "does-not-exist" in result.output


def test_eval_capture_writes_fixtures_under_dataset_path(
    tmp_path: Path,
) -> None:
    """AC-1 happy path: capture of a completed run writes fixtures per LLM node."""

    # Drive planner run → gate → resume to produce a completed +
    # checkpointed run. Reuses the full dispatch chain so the checkpointed
    # state matches production shape.
    _seed_planner_script()
    run_result = _RUNNER.invoke(
        app,
        [
            "run",
            "planner",
            "--goal",
            "Ship the marketing page.",
            "--run-id",
            "run-for-capture-01",
        ],
    )
    assert run_result.exit_code == 0, run_result.output

    resume_result = _RUNNER.invoke(
        app,
        [
            "resume",
            "run-for-capture-01",
            "--gate-response",
            "approved",
        ],
    )
    assert resume_result.exit_code == 0, resume_result.output

    # Capture under a fresh dataset directory.
    output_root = tmp_path / "captured"
    capture_result = _RUNNER.invoke(
        app,
        [
            "eval",
            "capture",
            "--run-id",
            "run-for-capture-01",
            "--dataset",
            "captured-seed",
            "--output-root",
            str(output_root),
        ],
    )
    assert capture_result.exit_code == 0, capture_result.output

    explorer_dir = output_root / "captured-seed" / "planner" / "explorer"
    synth_dir = output_root / "captured-seed" / "planner" / "planner"
    explorer_fixtures = list(explorer_dir.glob("*.json"))
    synth_fixtures = list(synth_dir.glob("*.json"))

    assert len(explorer_fixtures) == 1, (
        f"expected one explorer fixture, got {explorer_fixtures}"
    )
    assert len(synth_fixtures) == 1, (
        f"expected one synth fixture, got {synth_fixtures}"
    )

    # Fixtures round-trip as EvalCase and provenance back to the run id.
    explorer_case = EvalCase.model_validate_json(
        explorer_fixtures[0].read_text(encoding="utf-8")
    )
    assert explorer_case.workflow_id == "planner"
    assert explorer_case.node_name == "explorer"
    assert explorer_case.captured_from_run_id == "run-for-capture-01"
    assert explorer_case.expected_output == _valid_explorer_json()

    synth_case = EvalCase.model_validate_json(
        synth_fixtures[0].read_text(encoding="utf-8")
    )
    assert synth_case.node_name == "planner"
    assert synth_case.expected_output == _valid_plan_json()
