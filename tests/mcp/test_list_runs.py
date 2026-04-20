"""Tests for M4 Task 04 — `list_runs` MCP tool.

Covers the T04 acceptance criteria:

* Empty storage returns ``[]``.
* ``workflow`` and ``status`` filters compose with AND via
  :meth:`SQLiteStorage.list_runs`.
* ``limit`` caps the result and returns newest rows first.
* Pure-read invariant: row count before and after the call is
  identical (the tool issues no INSERT / UPDATE).
* ``RunSummary.total_cost_usd`` round-trips populated floats and
  ``NULL`` → ``None``.
* :class:`RunSummary` field names match the dict keys
  :meth:`SQLiteStorage.list_runs` returns (pinned against the schema).

Parity with :mod:`tests/cli/test_list_runs.py` keeps both surfaces on
one contract (M4 T04 AC "MCP + CLI parity").
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from ai_workflows.mcp import build_server
from ai_workflows.mcp.schemas import ListRunsInput, RunSummary
from ai_workflows.primitives.storage import SQLiteStorage


@pytest.fixture(autouse=True)
def _redirect_default_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("AIW_STORAGE_DB", str(tmp_path / "storage.sqlite"))


async def _seed_run(
    db_path: Path,
    run_id: str,
    workflow: str = "planner",
    status: str | None = None,
    total_cost_usd: float | None = None,
) -> None:
    storage = await SQLiteStorage.open(db_path)
    await storage.create_run(run_id, workflow, None)
    if status is not None:
        await storage.update_run_status(
            run_id, status, total_cost_usd=total_cost_usd
        )
    elif total_cost_usd is not None:
        # create_run defaults to status="pending"; only touch cost if asked.
        await storage.update_run_status(
            run_id, "pending", total_cost_usd=total_cost_usd
        )


def _row_count(db_path: Path) -> int:
    with sqlite3.connect(str(db_path)) as conn:
        return conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]


@pytest.mark.asyncio
async def test_list_runs_empty_returns_empty_list(tmp_path: Path) -> None:
    # Open storage once so migrations land; no rows seeded.
    await SQLiteStorage.open(tmp_path / "storage.sqlite")
    server = build_server()
    tool = await server.get_tool("list_runs")
    result = await tool.fn(ListRunsInput())
    assert result == []


@pytest.mark.asyncio
async def test_list_runs_workflow_filter_is_exact_match(tmp_path: Path) -> None:
    db = tmp_path / "storage.sqlite"
    await _seed_run(db, "r-planner-a", workflow="planner")
    await _seed_run(db, "r-planner-b", workflow="planner")
    await _seed_run(db, "r-other", workflow="slice_refactor")

    server = build_server()
    tool = await server.get_tool("list_runs")
    result = await tool.fn(ListRunsInput(workflow="planner"))

    assert {r.run_id for r in result} == {"r-planner-a", "r-planner-b"}
    assert all(r.workflow_id == "planner" for r in result)


@pytest.mark.asyncio
async def test_list_runs_status_filter_is_exact_match(tmp_path: Path) -> None:
    db = tmp_path / "storage.sqlite"
    await _seed_run(db, "r-pending")  # stays pending
    await _seed_run(db, "r-completed", status="completed", total_cost_usd=0.01)
    await _seed_run(db, "r-rejected", status="gate_rejected", total_cost_usd=0.02)

    server = build_server()
    tool = await server.get_tool("list_runs")
    result = await tool.fn(ListRunsInput(status="completed"))

    assert [r.run_id for r in result] == ["r-completed"]
    assert result[0].status == "completed"


@pytest.mark.asyncio
async def test_list_runs_limit_caps_and_orders_newest_first(
    tmp_path: Path,
) -> None:
    db = tmp_path / "storage.sqlite"
    # Rows seeded in temporal order — later create_run → later started_at.
    for i in range(5):
        await _seed_run(db, f"r-{i}")

    server = build_server()
    tool = await server.get_tool("list_runs")
    result = await tool.fn(ListRunsInput(limit=2))

    assert len(result) == 2
    # Newest first: the last two seeded (r-4, r-3).
    assert [r.run_id for r in result] == ["r-4", "r-3"]


@pytest.mark.asyncio
async def test_list_runs_is_pure_read(tmp_path: Path) -> None:
    """Spec AC: the tool never writes — row count stable across calls."""
    db = tmp_path / "storage.sqlite"
    await _seed_run(db, "r-a")
    await _seed_run(db, "r-b")

    count_before = _row_count(db)
    server = build_server()
    tool = await server.get_tool("list_runs")
    await tool.fn(ListRunsInput())
    count_after = _row_count(db)
    assert count_before == count_after == 2


@pytest.mark.asyncio
async def test_list_runs_total_cost_usd_round_trips(tmp_path: Path) -> None:
    """Populated cost round-trips as a float; ``NULL`` round-trips as ``None``.

    The ``runs.total_cost_usd`` column has ``DEFAULT 0.0`` (migration
    001) so a ``create_run`` alone never yields ``NULL``. The NULL case
    — which maps to a pre-migration or manually-inspected row — is
    forced here with a direct ``UPDATE … SET total_cost_usd = NULL``
    (same approach as :mod:`tests/cli/test_list_runs.py`).
    """
    db = tmp_path / "storage.sqlite"
    await _seed_run(db, "r-cost", total_cost_usd=0.0033)
    await _seed_run(db, "r-null")

    with sqlite3.connect(str(db)) as conn:
        conn.execute(
            "UPDATE runs SET total_cost_usd = NULL WHERE run_id = ?",
            ("r-null",),
        )
        conn.commit()

    server = build_server()
    tool = await server.get_tool("list_runs")
    result = await tool.fn(ListRunsInput(limit=50))
    by_id = {r.run_id: r for r in result}
    assert by_id["r-cost"].total_cost_usd == pytest.approx(0.0033)
    assert by_id["r-null"].total_cost_usd is None


@pytest.mark.asyncio
async def test_run_summary_field_names_match_storage_row_keys(
    tmp_path: Path,
) -> None:
    """Pins the contract the tool body relies on: `RunSummary(**row)` works.

    A silent rename on either side (``SQLiteStorage.list_runs`` returning
    ``workflow`` instead of ``workflow_id``, or a schema refactor on
    :class:`RunSummary`) would make the construction raise or drop data
    silently. This test asserts the dict keys Storage returns are a
    superset of the RunSummary field names that are declared non-optional,
    so every required field has a source.
    """
    db = tmp_path / "storage.sqlite"
    await _seed_run(db, "r-keycheck", workflow="planner")
    storage = await SQLiteStorage.open(db)
    rows = await storage.list_runs(limit=1)
    assert rows, "seed failed"
    storage_keys = set(rows[0].keys())

    summary_fields = set(RunSummary.model_fields.keys())
    required_summary_fields = {
        name
        for name, f in RunSummary.model_fields.items()
        if f.is_required()
    }
    assert required_summary_fields.issubset(storage_keys), (
        f"missing Storage keys for required RunSummary fields: "
        f"{required_summary_fields - storage_keys}"
    )
    # Explicitly check the exact field names the spec calls out so a
    # rename is caught even if the field becomes optional.
    assert summary_fields == {
        "run_id",
        "workflow_id",
        "status",
        "started_at",
        "finished_at",
        "total_cost_usd",
    }
