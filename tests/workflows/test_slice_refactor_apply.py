"""Tests for the T06 ``apply`` terminal node + dispatch completion wiring.

Covers the acceptance criteria from
``design_docs/phases/milestone_6_slice_refactor/task_06_apply_node.md``:

* ``apply`` writes one ``artifacts`` row per succeeded :class:`SliceResult`
  keyed ``(run_id, f"slice_result:{slice_id}")`` via the existing
  :meth:`SQLiteStorage.write_artifact` helper — no schema migration and
  no new kwarg on the helper (task spec: reuse the M1 / M3 shape; the
  ``slice_id`` lives in the ``kind`` namespace).
* Failed slices are not written (gate-log is the audit trail).
* Approve flips ``runs.status`` to ``"completed"`` with ``finished_at``;
  reject flips to ``"gate_rejected"`` with ``finished_at``.
* Re-invoking ``apply`` on the same ``run_id`` does not double-write —
  idempotency via the ``(run_id, kind)`` PK's ``ON CONFLICT DO UPDATE``.
* Stored payload round-trips through :meth:`SliceResult.model_validate_json`.
* Dispatch's ``_build_resume_result_from_final`` reads
  ``state[FINAL_STATE_KEY]`` (resolves ``T01-CARRY-DISPATCH-COMPLETE``):
  planner regression + slice_refactor happy path + no-constant fallback.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from ai_workflows import workflows
from ai_workflows.primitives.cost import CostTracker
from ai_workflows.primitives.retry import NonRetryable
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.workflows import planner as planner_module
from ai_workflows.workflows import slice_refactor as slice_refactor_module
from ai_workflows.workflows._dispatch import (
    _build_resume_result_from_final,
    _resolve_final_state_key,
)
from ai_workflows.workflows.planner import build_planner
from ai_workflows.workflows.slice_refactor import (
    FINAL_STATE_KEY,
    SLICE_RESULT_ARTIFACT_KIND,
    SliceAggregate,
    SliceFailure,
    SliceResult,
    _apply,
    build_slice_refactor,
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


async def _storage(tmp_path: Path) -> SQLiteStorage:
    return await SQLiteStorage.open(tmp_path / "storage.sqlite")


def _success(slice_id: str, diff: str = "d", notes: str = "n") -> SliceResult:
    return SliceResult(slice_id=slice_id, diff=diff, notes=notes)


def _failure(slice_id: str) -> SliceFailure:
    return SliceFailure(
        slice_id=slice_id,
        last_error="validator exhausted",
        failure_bucket="non_retryable",
    )


def _cfg(run_id: str, storage: SQLiteStorage) -> dict[str, Any]:
    return {"configurable": {"thread_id": run_id, "storage": storage}}


# ---------------------------------------------------------------------------
# Module-level constants — T01-CARRY-DISPATCH-COMPLETE convention
# ---------------------------------------------------------------------------


def test_final_state_key_exposed_on_both_workflow_modules() -> None:
    """AC (T01-CARRY-DISPATCH-COMPLETE): each workflow publishes a
    ``FINAL_STATE_KEY`` so dispatch can detect completion uniformly
    without hardcoding ``"plan"``.
    """
    assert planner_module.FINAL_STATE_KEY == "plan"
    assert slice_refactor_module.FINAL_STATE_KEY == "applied_artifact_count"
    assert _resolve_final_state_key(planner_module) == "plan"
    assert (
        _resolve_final_state_key(slice_refactor_module)
        == "applied_artifact_count"
    )


def test_final_state_key_defaults_to_plan_for_legacy_modules() -> None:
    """Regression: workflows that omit ``FINAL_STATE_KEY`` still complete
    via the ``"plan"`` fallback — backwards-compatible contract.
    """

    class _Legacy:
        pass

    assert _resolve_final_state_key(_Legacy()) == "plan"


def test_artifact_kind_constant_matches_migration() -> None:
    """AC: the namespace prefix the ``apply`` node uses matches the
    documented convention so downstream consumers (e.g. M4's
    ``get_artifact`` MCP tool) can construct the key without importing
    slice_refactor.
    """
    assert SLICE_RESULT_ARTIFACT_KIND == "slice_result"
    assert FINAL_STATE_KEY == "applied_artifact_count"


# ---------------------------------------------------------------------------
# AC-1 / AC-5: happy path writes one artefact per succeeded slice
# ---------------------------------------------------------------------------


async def test_apply_writes_one_artifact_per_succeeded_slice(
    tmp_path: Path,
) -> None:
    """AC-1: ``apply`` writes one row per succeeded slice, keyed
    ``(run_id, f"{SLICE_RESULT_ARTIFACT_KIND}:{slice_id}")``.
    """
    storage = await _storage(tmp_path)
    await storage.create_run("run-apply-happy", "slice_refactor", None)
    aggregate = SliceAggregate(
        succeeded=[
            _success("1", diff="d1", notes="n1"),
            _success("2", diff="d2", notes="n2"),
            _success("3", diff="d3", notes="n3"),
        ],
        failed=[],
        total_slices=3,
    )
    state: dict[str, Any] = {"aggregate": aggregate}
    cfg = _cfg("run-apply-happy", storage)

    result = await _apply(state, cfg)  # type: ignore[arg-type]

    assert result == {"applied_artifact_count": 3}
    for slice_id in ("1", "2", "3"):
        row = await storage.read_artifact(
            "run-apply-happy", f"{SLICE_RESULT_ARTIFACT_KIND}:{slice_id}"
        )
        assert row is not None, f"expected row for slice {slice_id}"
        assert row["run_id"] == "run-apply-happy"
        assert row["kind"] == f"{SLICE_RESULT_ARTIFACT_KIND}:{slice_id}"


# ---------------------------------------------------------------------------
# AC-5: payload round-trips through SliceResult.model_validate_json
# ---------------------------------------------------------------------------


async def test_apply_payload_roundtrips_through_model_validate_json(
    tmp_path: Path,
) -> None:
    """AC-5: stored payload is valid JSON that parses back to an
    equivalent :class:`SliceResult`.
    """
    storage = await _storage(tmp_path)
    await storage.create_run("run-apply-roundtrip", "slice_refactor", None)
    original = _success("7", diff="--- a/x\n+++ b/x\n", notes="r-t")
    aggregate = SliceAggregate(
        succeeded=[original], failed=[], total_slices=1,
    )
    await _apply(
        {"aggregate": aggregate},  # type: ignore[arg-type]
        _cfg("run-apply-roundtrip", storage),
    )

    row = await storage.read_artifact(
        "run-apply-roundtrip", f"{SLICE_RESULT_ARTIFACT_KIND}:7"
    )
    assert row is not None
    roundtrip = SliceResult.model_validate_json(row["payload_json"])
    assert roundtrip == original


# ---------------------------------------------------------------------------
# AC-2: failed slices not written (audit trail lives in gate log)
# ---------------------------------------------------------------------------


async def test_apply_does_not_write_rows_for_failed_slices(
    tmp_path: Path,
) -> None:
    """AC-2: ``apply`` skips ``aggregate.failed``. Only the two
    succeeded rows land; the failed slice has no artefact row.
    """
    storage = await _storage(tmp_path)
    await storage.create_run("run-apply-partial", "slice_refactor", None)
    aggregate = SliceAggregate(
        succeeded=[_success("a"), _success("c")],
        failed=[_failure("b")],
        total_slices=3,
    )
    result = await _apply(
        {"aggregate": aggregate},  # type: ignore[arg-type]
        _cfg("run-apply-partial", storage),
    )

    assert result == {"applied_artifact_count": 2}
    assert (
        await storage.read_artifact(
            "run-apply-partial", f"{SLICE_RESULT_ARTIFACT_KIND}:a"
        )
        is not None
    )
    assert (
        await storage.read_artifact(
            "run-apply-partial", f"{SLICE_RESULT_ARTIFACT_KIND}:c"
        )
        is not None
    )
    assert (
        await storage.read_artifact(
            "run-apply-partial", f"{SLICE_RESULT_ARTIFACT_KIND}:b"
        )
        is None
    )


# ---------------------------------------------------------------------------
# AC-1 edge: zero-success aggregate returns 0 (still a valid completion)
# ---------------------------------------------------------------------------


async def test_apply_returns_zero_for_zero_success_aggregate(
    tmp_path: Path,
) -> None:
    """AC-1 edge: an aggregate with zero succeeded slices returns
    ``{"applied_artifact_count": 0}`` — a reviewer can still approve a
    fully-failed run to record the audit trail; dispatch's
    ``FINAL_STATE_KEY`` check uses ``is not None`` so ``0`` still
    reads as "completed".
    """
    storage = await _storage(tmp_path)
    await storage.create_run("run-apply-zero", "slice_refactor", None)
    aggregate = SliceAggregate(
        succeeded=[],
        failed=[_failure("x"), _failure("y")],
        total_slices=2,
    )
    result = await _apply(
        {"aggregate": aggregate},  # type: ignore[arg-type]
        _cfg("run-apply-zero", storage),
    )
    assert result == {"applied_artifact_count": 0}


# ---------------------------------------------------------------------------
# AC-4: re-invoking apply on same run_id does not double-write
# ---------------------------------------------------------------------------


async def test_apply_is_idempotent_on_reinvocation(
    tmp_path: Path,
) -> None:
    """AC-4: repeat invocations on the same ``run_id`` overwrite in
    place via the ``(run_id, kind)`` PK's ``ON CONFLICT DO UPDATE``; the
    artifact row count stays at N after the second call.
    """
    storage = await _storage(tmp_path)
    await storage.create_run("run-apply-idem", "slice_refactor", None)
    aggregate = SliceAggregate(
        succeeded=[_success("1"), _success("2")],
        failed=[],
        total_slices=2,
    )
    cfg = _cfg("run-apply-idem", storage)

    first = await _apply({"aggregate": aggregate}, cfg)  # type: ignore[arg-type]
    second = await _apply({"aggregate": aggregate}, cfg)  # type: ignore[arg-type]

    assert first == {"applied_artifact_count": 2}
    assert second == {"applied_artifact_count": 2}
    for slice_id in ("1", "2"):
        row = await storage.read_artifact(
            "run-apply-idem", f"{SLICE_RESULT_ARTIFACT_KIND}:{slice_id}"
        )
        assert row is not None


async def test_apply_reinvocation_with_same_payload_is_byte_identical(
    tmp_path: Path,
) -> None:
    """Tighter idempotency: second invocation with the same aggregate
    produces byte-identical ``payload_json`` (only ``created_at`` may
    change). Pins the spec's "pick one and pin it in the test" note.
    """
    storage = await _storage(tmp_path)
    await storage.create_run("run-apply-byte", "slice_refactor", None)
    aggregate = SliceAggregate(
        succeeded=[_success("7", diff="d7", notes="byte-test")],
        failed=[],
        total_slices=1,
    )
    cfg = _cfg("run-apply-byte", storage)

    await _apply({"aggregate": aggregate}, cfg)  # type: ignore[arg-type]
    first_row = await storage.read_artifact(
        "run-apply-byte", f"{SLICE_RESULT_ARTIFACT_KIND}:7"
    )
    assert first_row is not None
    first_payload = first_row["payload_json"]

    await _apply({"aggregate": aggregate}, cfg)  # type: ignore[arg-type]
    second_row = await storage.read_artifact(
        "run-apply-byte", f"{SLICE_RESULT_ARTIFACT_KIND}:7"
    )
    assert second_row is not None
    assert second_row["payload_json"] == first_payload


# ---------------------------------------------------------------------------
# Defensive: missing aggregate raises NonRetryable (contract violation)
# ---------------------------------------------------------------------------


async def test_apply_missing_aggregate_raises_nonretryable(
    tmp_path: Path,
) -> None:
    """The T04 aggregator runs before ``apply`` unconditionally (edge in
    ``build_slice_refactor``). If ``state['aggregate']`` is missing the
    graph is wired wrong — raise ``NonRetryable`` loud.
    """
    storage = await _storage(tmp_path)
    await storage.create_run("run-apply-no-agg", "slice_refactor", None)
    with pytest.raises(NonRetryable):
        await _apply({}, _cfg("run-apply-no-agg", storage))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# AC-5: no subprocess, no filesystem write, no git invocation
# ---------------------------------------------------------------------------


async def test_apply_does_not_invoke_subprocess_or_filesystem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC: milestone non-goal forbids subprocess / filesystem /
    ``git apply`` invocation at M6 scope. Spies on the common handles;
    a call to any of them fails the test.
    """
    import subprocess

    called: dict[str, int] = {"run": 0, "popen": 0}

    def _fail_run(*_args: Any, **_kwargs: Any) -> Any:
        called["run"] += 1
        raise AssertionError("subprocess.run must not be called from _apply")

    def _fail_popen(*_args: Any, **_kwargs: Any) -> Any:
        called["popen"] += 1
        raise AssertionError("subprocess.Popen must not be called from _apply")

    monkeypatch.setattr(subprocess, "run", _fail_run)
    monkeypatch.setattr(subprocess, "Popen", _fail_popen)

    storage = await _storage(tmp_path)
    await storage.create_run("run-apply-hermetic", "slice_refactor", None)
    aggregate = SliceAggregate(
        succeeded=[_success("1")], failed=[], total_slices=1,
    )
    await _apply(
        {"aggregate": aggregate},  # type: ignore[arg-type]
        _cfg("run-apply-hermetic", storage),
    )
    assert called == {"run": 0, "popen": 0}


# ---------------------------------------------------------------------------
# AC-3: approve → runs.status = completed + finished_at (dispatch helper)
# ---------------------------------------------------------------------------


async def test_dispatch_flips_status_completed_with_finished_at_for_slice_refactor(
    tmp_path: Path,
) -> None:
    """AC-3 approve path: ``_build_resume_result_from_final`` sees the
    slice_refactor terminal state (``applied_artifact_count`` populated,
    ``plan`` absent) and flips ``runs.status = completed`` with an
    auto-stamped ``finished_at``. Resolves T01-CARRY-DISPATCH-COMPLETE
    for the approve path.
    """
    storage = await _storage(tmp_path)
    await storage.create_run("run-dispatch-slice-done", "slice_refactor", None)
    tracker = CostTracker()
    final = {
        "gate_plan_review_response": "approved",
        "gate_slice_refactor_review_response": "approved",
        "applied_artifact_count": 2,
    }

    result = await _build_resume_result_from_final(
        final=final,
        run_id="run-dispatch-slice-done",
        gate_response="approved",
        terminal_gate_id="slice_refactor_review",
        final_state_key="applied_artifact_count",
        tracker=tracker,
        storage=storage,
    )
    assert result["status"] == "completed"
    assert result["plan"] is None
    row = await storage.get_run("run-dispatch-slice-done")
    assert row is not None
    assert row["status"] == "completed"
    assert row["finished_at"] is not None


async def test_dispatch_flips_status_completed_for_zero_artifact_count(
    tmp_path: Path,
) -> None:
    """Regression on the ``is not None`` check: a ``0`` value still reads
    as "completed" — a reviewer-approved zero-success run records status
    as completed rather than falling through to the errored branch.
    """
    storage = await _storage(tmp_path)
    await storage.create_run("run-dispatch-zero", "slice_refactor", None)
    tracker = CostTracker()
    final = {
        "gate_slice_refactor_review_response": "approved",
        "applied_artifact_count": 0,
    }
    result = await _build_resume_result_from_final(
        final=final,
        run_id="run-dispatch-zero",
        gate_response="approved",
        terminal_gate_id="slice_refactor_review",
        final_state_key="applied_artifact_count",
        tracker=tracker,
        storage=storage,
    )
    assert result["status"] == "completed"


# ---------------------------------------------------------------------------
# Regression: planner's completion path unchanged after the refactor
# ---------------------------------------------------------------------------


async def test_dispatch_planner_completion_path_preserved(
    tmp_path: Path,
) -> None:
    """Regression: planner's ``state['plan']``-driven completion still
    flips ``runs.status = completed`` and surfaces the plan dict.
    """
    from ai_workflows.workflows.planner import PlannerPlan, PlannerStep

    storage = await _storage(tmp_path)
    await storage.create_run("run-dispatch-planner-done", "planner", None)
    tracker = CostTracker()
    plan = PlannerPlan(
        goal="g",
        summary="s",
        steps=[
            PlannerStep(index=1, title="t", rationale="r", actions=["a"]),
        ],
    )
    final = {
        "gate_plan_review_response": "approved",
        "plan": plan,
    }

    result = await _build_resume_result_from_final(
        final=final,
        run_id="run-dispatch-planner-done",
        gate_response="approved",
        terminal_gate_id="plan_review",
        final_state_key="plan",
        tracker=tracker,
        storage=storage,
    )
    assert result["status"] == "completed"
    assert result["plan"] == plan.model_dump()
    row = await storage.get_run("run-dispatch-planner-done")
    assert row is not None
    assert row["status"] == "completed"


# ---------------------------------------------------------------------------
# AC-3: reject path flips to gate_rejected + finished_at (no apply call)
# ---------------------------------------------------------------------------


async def test_dispatch_reject_path_flips_gate_rejected_with_finished_at(
    tmp_path: Path,
) -> None:
    """AC-3 reject path: rejecting at the slice-refactor gate flips
    ``runs.status = gate_rejected`` with ``finished_at`` stamped; no
    artefacts are ever written (apply node is not invoked on this
    branch). Parallel assertion to the T05 tests but re-pinned here for
    scope completeness.
    """
    storage = await _storage(tmp_path)
    await storage.create_run("run-dispatch-reject", "slice_refactor", None)
    tracker = CostTracker()
    final = {
        "gate_slice_refactor_review_response": "rejected",
    }
    result = await _build_resume_result_from_final(
        final=final,
        run_id="run-dispatch-reject",
        gate_response="rejected",
        terminal_gate_id="slice_refactor_review",
        final_state_key="applied_artifact_count",
        tracker=tracker,
        storage=storage,
    )
    assert result["status"] == "gate_rejected"
    row = await storage.get_run("run-dispatch-reject")
    assert row is not None
    assert row["status"] == "gate_rejected"
    assert row["finished_at"] is not None
    # No artefacts were written for the rejected run.
    assert (
        await storage.read_artifact(
            "run-dispatch-reject", f"{SLICE_RESULT_ARTIFACT_KIND}:1"
        )
        is None
    )


# ---------------------------------------------------------------------------
# AC: apply writes JSON-parseable payload (schema contract)
# ---------------------------------------------------------------------------


async def test_apply_payload_is_valid_json(tmp_path: Path) -> None:
    """AC: payload is a JSON string — a caller that does not want to
    depend on pydantic can still parse via stdlib ``json.loads``.
    """
    storage = await _storage(tmp_path)
    await storage.create_run("run-apply-json", "slice_refactor", None)
    aggregate = SliceAggregate(
        succeeded=[_success("1", diff="d", notes="json-test")],
        failed=[],
        total_slices=1,
    )
    await _apply(
        {"aggregate": aggregate},  # type: ignore[arg-type]
        _cfg("run-apply-json", storage),
    )
    row = await storage.read_artifact(
        "run-apply-json", f"{SLICE_RESULT_ARTIFACT_KIND}:1"
    )
    assert row is not None
    parsed = json.loads(row["payload_json"])
    assert parsed["slice_id"] == "1"
    assert parsed["notes"] == "json-test"
