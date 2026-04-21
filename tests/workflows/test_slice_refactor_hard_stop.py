"""Tests for the T07 double-failure hard-stop.

Covers the hard-stop ACs from
``design_docs/phases/milestone_6_slice_refactor/task_07_concurrency_hard_stop.md``:

* AC-4: conditional edge routes to ``hard_stop`` when
  ``len(state["slice_failures"]) >= HARD_STOP_FAILURE_THRESHOLD``;
  aggregate + gate + apply are skipped.
* AC-5: a new ``runs.status = "aborted"`` terminal status (distinct from
  ``"gate_rejected"`` / ``"cancelled"``). Dispatch's
  :func:`_build_result_from_final` flips the row with ``finished_at``.
* AC-6: hard-stop triggers on the *second* non-retryable failure, not
  the third — this is an invariant of the fan-in edge (the edge fires
  exactly once per super-step with all sibling writes visible; the
  assertion is that a 3-failure fan-in still routes to ``hard_stop``).
* AC-7: transient-only retries do **not** bump the failure list — only
  exhausted-retry branches land in ``slice_failures``.
* AC-8: hard-stop writes a ``hard_stop_metadata`` artefact enumerating
  the failing slice ids.

Architectural note on "in-flight sibling cancellation": LangGraph
synchronises parent super-steps on Send fan-in, so by the time
``_route_before_aggregate`` evaluates, every sibling has already
completed. The T02 ``_ACTIVE_RUNS`` + :meth:`asyncio.Task.cancel`
path handles *externally-initiated* cancellation (``cancel_run`` MCP
tool); that path is re-pinned here via a registry presence check.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from ai_workflows import workflows
from ai_workflows.primitives.cost import CostTracker
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.workflows._dispatch import _build_result_from_final
from ai_workflows.workflows.planner import build_planner
from ai_workflows.workflows.slice_refactor import (
    HARD_STOP_FAILURE_THRESHOLD,
    HARD_STOP_METADATA_ARTIFACT_KIND,
    SliceFailure,
    SliceResult,
    _hard_stop,
    _route_before_aggregate,
    build_slice_refactor,
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


async def _storage(tmp_path: Path) -> SQLiteStorage:
    return await SQLiteStorage.open(tmp_path / "storage.sqlite")


def _failure(slice_id: str) -> SliceFailure:
    return SliceFailure(
        slice_id=slice_id,
        last_error="exhausted",
        failure_bucket="non_retryable",
    )


def _success(slice_id: str) -> SliceResult:
    return SliceResult(slice_id=slice_id, diff=f"d{slice_id}", notes=f"n{slice_id}")


def _cfg(run_id: str, storage: SQLiteStorage) -> dict[str, Any]:
    return {"configurable": {"thread_id": run_id, "storage": storage}}


# ---------------------------------------------------------------------------
# Constants — AC-4 / AC-5 namespace pinning
# ---------------------------------------------------------------------------


def test_hard_stop_threshold_is_two() -> None:
    """AC-4: threshold is ``2`` — architecture.md §8.2 verbatim ("two
    non-retryable failures abort the run").
    """
    assert HARD_STOP_FAILURE_THRESHOLD == 2


def test_hard_stop_metadata_kind_is_namespaced() -> None:
    """AC-8: the metadata artefact uses a stable ``kind`` so downstream
    readers (e.g. a future post-mortem MCP tool) can look it up by
    constant without importing slice_refactor internals.
    """
    assert HARD_STOP_METADATA_ARTIFACT_KIND == "hard_stop_metadata"


# ---------------------------------------------------------------------------
# AC-4: the conditional edge routes by slice_failures length
# ---------------------------------------------------------------------------


def test_route_sends_to_aggregate_when_no_failures() -> None:
    """AC-4: empty failure list → normal aggregate path."""
    assert _route_before_aggregate({}) == "aggregate"
    assert _route_before_aggregate({"slice_failures": []}) == "aggregate"


def test_route_sends_to_aggregate_on_single_failure() -> None:
    """AC-4: one failure is still below the double-failure threshold;
    the aggregator runs so the reviewer can approve a partial run."""
    state = {"slice_failures": [_failure("1")]}
    assert _route_before_aggregate(state) == "aggregate"


def test_route_sends_to_hard_stop_on_two_failures() -> None:
    """AC-4 / AC-6: the second non-retryable failure triggers hard-stop.
    The edge fires at fan-in with all sibling writes visible, so the
    "second failure" semantics are a count-at-fan-in assertion.
    """
    state = {"slice_failures": [_failure("1"), _failure("2")]}
    assert _route_before_aggregate(state) == "hard_stop"


def test_route_sends_to_hard_stop_on_triple_failure() -> None:
    """AC-6 edge: a triple-failure fan-in still routes to hard-stop
    (the threshold is ``>= 2``, not ``== 2``); the aggregator + gate
    are skipped as soon as the count crosses the threshold.
    """
    state = {
        "slice_failures": [_failure("1"), _failure("2"), _failure("3")],
    }
    assert _route_before_aggregate(state) == "hard_stop"


def test_route_ignores_successful_slices() -> None:
    """AC-7: the routing decision is independent of ``slice_results``;
    only the failure list matters. A run with 3 successes and 1 failure
    still routes to aggregate (below threshold); a run with 1 success
    and 2 failures routes to hard-stop (threshold met).
    """
    mixed_below = {
        "slice_results": [_success("a"), _success("b"), _success("c")],
        "slice_failures": [_failure("d")],
    }
    assert _route_before_aggregate(mixed_below) == "aggregate"

    mixed_at_threshold = {
        "slice_results": [_success("a")],
        "slice_failures": [_failure("b"), _failure("c")],
    }
    assert _route_before_aggregate(mixed_at_threshold) == "hard_stop"


# ---------------------------------------------------------------------------
# AC-7: transient retries do not increment the counter
# ---------------------------------------------------------------------------


def test_route_ignores_transient_retry_counter() -> None:
    """AC-7: transient retries that eventually succeed never land in
    ``slice_failures``. A state with a populated ``_retry_counts``
    (workers that retried once and then succeeded) but no
    ``slice_failures`` routes to aggregate — the hard-stop edge reads
    only the failure list.
    """
    state = {
        "_retry_counts": {"slice_worker": 2},
        "_non_retryable_failures": 0,
        "slice_failures": [],
    }
    assert _route_before_aggregate(state) == "aggregate"


def test_route_ignores_non_retryable_failures_counter() -> None:
    """AC-7 / M6-T04-ISS-01 resolution: the hard-stop decision reads
    ``slice_failures`` (``operator.add``-reduced, exact count), **not**
    ``_non_retryable_failures`` (``max``-reduced, undercounts parallel
    writes). A state with a stale counter but no failures still routes
    to aggregate.
    """
    state = {
        "_non_retryable_failures": 5,  # would falsely trigger if read
        "slice_failures": [],
    }
    assert _route_before_aggregate(state) == "aggregate"


# ---------------------------------------------------------------------------
# AC-8: _hard_stop writes the metadata artefact
# ---------------------------------------------------------------------------


async def test_hard_stop_writes_metadata_artefact(tmp_path: Path) -> None:
    """AC-8: ``_hard_stop`` writes one ``artifacts`` row keyed
    ``(run_id, HARD_STOP_METADATA_ARTIFACT_KIND)`` with a JSON payload
    that enumerates every failing slice id.
    """
    storage = await _storage(tmp_path)
    await storage.create_run("run-hard-stop-meta", "slice_refactor", None)
    state = {
        "slice_failures": [_failure("alpha"), _failure("beta")],
    }
    out = await _hard_stop(state, _cfg("run-hard-stop-meta", storage))  # type: ignore[arg-type]

    assert out == {"hard_stop_failing_slice_ids": ["alpha", "beta"]}
    row = await storage.read_artifact(
        "run-hard-stop-meta", HARD_STOP_METADATA_ARTIFACT_KIND
    )
    assert row is not None
    payload = json.loads(row["payload_json"])
    assert payload == {"failing_slice_ids": ["alpha", "beta"]}


async def test_hard_stop_artefact_is_idempotent_on_reinvocation(
    tmp_path: Path,
) -> None:
    """AC-8: re-invoking ``_hard_stop`` on the same ``run_id`` overwrites
    the existing row via the ``(run_id, kind)`` PK's
    ``ON CONFLICT DO UPDATE`` — one row per run, regardless of how many
    times the node fires (e.g. under a resume-after-crash replay).
    """
    storage = await _storage(tmp_path)
    await storage.create_run("run-hard-stop-idem", "slice_refactor", None)
    state = {"slice_failures": [_failure("x"), _failure("y")]}
    cfg = _cfg("run-hard-stop-idem", storage)

    await _hard_stop(state, cfg)  # type: ignore[arg-type]
    await _hard_stop(state, cfg)  # type: ignore[arg-type]

    row = await storage.read_artifact(
        "run-hard-stop-idem", HARD_STOP_METADATA_ARTIFACT_KIND
    )
    assert row is not None
    payload = json.loads(row["payload_json"])
    assert payload == {"failing_slice_ids": ["x", "y"]}


async def test_hard_stop_preserves_order_from_slice_failures(
    tmp_path: Path,
) -> None:
    """AC-8: ``_hard_stop`` echoes the fan-in order of
    ``slice_failures`` into its metadata payload, giving a stable
    post-mortem trail.
    """
    storage = await _storage(tmp_path)
    await storage.create_run("run-hard-stop-order", "slice_refactor", None)
    state = {
        "slice_failures": [_failure("c"), _failure("a"), _failure("b")],
    }
    await _hard_stop(state, _cfg("run-hard-stop-order", storage))  # type: ignore[arg-type]
    row = await storage.read_artifact(
        "run-hard-stop-order", HARD_STOP_METADATA_ARTIFACT_KIND
    )
    assert row is not None
    payload = json.loads(row["payload_json"])
    assert payload["failing_slice_ids"] == ["c", "a", "b"]


# ---------------------------------------------------------------------------
# AC-5: dispatch flips runs.status = "aborted" with finished_at
# ---------------------------------------------------------------------------


async def test_dispatch_flips_status_aborted_with_finished_at(
    tmp_path: Path,
) -> None:
    """AC-5: :func:`_build_result_from_final` flips
    ``runs.status = "aborted"`` with ``finished_at`` stamped and returns
    ``status="aborted"`` + a descriptive ``error`` enumerating the
    failing slice ids.
    """
    storage = await _storage(tmp_path)
    await storage.create_run("run-hard-stop-dispatch", "slice_refactor", None)
    tracker = CostTracker()
    final = {
        "hard_stop_failing_slice_ids": ["alpha", "beta"],
        "slice_failures": [_failure("alpha"), _failure("beta")],
    }
    result = await _build_result_from_final(
        final=final,
        run_id="run-hard-stop-dispatch",
        final_state_key="applied_artifact_count",
        tracker=tracker,
        storage=storage,
    )
    assert result["status"] == "aborted"
    assert result["awaiting"] is None
    assert result["plan"] is None
    assert result["error"]
    assert "alpha" in result["error"]
    assert "beta" in result["error"]
    assert "hard-stop" in result["error"]

    row = await storage.get_run("run-hard-stop-dispatch")
    assert row is not None
    assert row["status"] == "aborted"
    assert row["finished_at"] is not None


async def test_dispatch_hard_stop_short_circuits_before_completion_check(
    tmp_path: Path,
) -> None:
    """AC-5 ordering: the hard-stop branch is evaluated **before** the
    ``final_state_key is not None`` completion branch. A
    ``hard_stop_failing_slice_ids``-populated state must not falsely
    report as "completed" even if the state also carries an
    ``applied_artifact_count`` (defensive — the graph cannot produce
    that shape today, but the branch order is a contract).
    """
    storage = await _storage(tmp_path)
    await storage.create_run("run-hs-contract", "slice_refactor", None)
    tracker = CostTracker()
    final = {
        "hard_stop_failing_slice_ids": ["q"],  # populated → aborted
        "applied_artifact_count": 0,  # would read as completed if order reversed
    }
    result = await _build_result_from_final(
        final=final,
        run_id="run-hs-contract",
        final_state_key="applied_artifact_count",
        tracker=tracker,
        storage=storage,
    )
    assert result["status"] == "aborted"


async def test_dispatch_ignores_empty_failing_ids_list(tmp_path: Path) -> None:
    """AC-5: an empty ``hard_stop_failing_slice_ids`` list is treated
    as absence — the state did not hit the hard-stop branch — and the
    normal completion path applies. Defensive: guards against a
    future writer that seeds the key with ``[]`` before the node fires.
    """
    storage = await _storage(tmp_path)
    await storage.create_run("run-hs-empty", "slice_refactor", None)
    tracker = CostTracker()
    final = {
        "hard_stop_failing_slice_ids": [],
        "applied_artifact_count": 1,
    }
    result = await _build_result_from_final(
        final=final,
        run_id="run-hs-empty",
        final_state_key="applied_artifact_count",
        tracker=tracker,
        storage=storage,
    )
    assert result["status"] == "completed"


# ---------------------------------------------------------------------------
# Graph wiring: hard_stop node exists and is reachable
# ---------------------------------------------------------------------------


def test_graph_exposes_hard_stop_node() -> None:
    """AC-4 structural: the compiled graph has a ``hard_stop`` node;
    regression guard against a future refactor removing the edge.
    """
    compiled = build_slice_refactor().compile()
    node_names = set(compiled.get_graph().nodes.keys())
    assert "hard_stop" in node_names


# ---------------------------------------------------------------------------
# In-flight external cancellation: T02 _ACTIVE_RUNS registry still wired
# ---------------------------------------------------------------------------


def test_active_runs_registry_present_for_cancel_path() -> None:
    """The T07 spec's "in-flight sibling cancellation" path is inherited
    from T02: externally-initiated ``cancel_run`` fires
    :meth:`asyncio.Task.cancel` on the registry entry. Hard-stop itself
    runs *after* LangGraph's Send fan-in, so sibling tasks have
    already completed by the time ``_route_before_aggregate`` fires.
    This test re-pins the T02 registry presence so a refactor that
    drops it would be caught here rather than at M8 time.
    """
    from ai_workflows.mcp import server as mcp_server

    assert hasattr(mcp_server, "_ACTIVE_RUNS")
    assert isinstance(mcp_server._ACTIVE_RUNS, dict)
