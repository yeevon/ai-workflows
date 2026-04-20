"""Tests for M3 Task 06 — ``aiw list-runs``.

Covers every acceptance criterion from
``design_docs/phases/milestone_3_first_workflow/task_06_cli_list_cost.md``:

* Empty Storage prints the header + ``(no runs)``.
* ``--workflow`` filter returns exactly the matching subset.
* ``--status`` filter works.
* ``--limit`` caps the output.
* Pure-read invariant: row count before vs. after is identical
  (spec AC-3 — no ``INSERT`` / ``UPDATE`` in the Storage SQL issued).
* ``total_cost_usd`` renders as a dollar figure when populated; ``NULL``
  renders as ``—``.

No LLM is involved — ``list-runs`` never opens the checkpointer, so
we do not install the LiteLLM stub the ``aiw run`` / ``aiw resume``
suites do. The default Storage path is still redirected under
``tmp_path`` via ``AIW_STORAGE_DB`` so the tests never touch the real
``~/.ai-workflows/`` file.
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_workflows.cli import app
from ai_workflows.primitives.storage import SQLiteStorage

_RUNNER = CliRunner()


@pytest.fixture(autouse=True)
def _redirect_default_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Route the default Storage path under ``tmp_path``.

    Mirrors the fixture in ``tests/cli/test_run.py`` /
    ``tests/cli/test_resume.py``. ``AIW_CHECKPOINT_DB`` is redirected
    too purely for symmetry — ``list-runs`` never opens the
    checkpointer.
    """
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("AIW_STORAGE_DB", str(tmp_path / "storage.sqlite"))


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_runs(
    db_path: Path,
    specs: list[tuple[str, str, str | None, float | None]],
) -> None:
    """Insert one ``runs`` row per spec tuple.

    Spec tuple is ``(run_id, workflow, terminal_status, total_cost_usd)``.
    ``terminal_status`` may be ``None`` (leave as ``pending``) or a
    status string passed to :meth:`SQLiteStorage.update_run_status` so
    the tests can exercise the ``--status`` filter.

    Adds a short ``await asyncio.sleep(0.01)`` between creates so the
    ``started_at`` column lands with distinct ISO-8601 microseconds —
    without it microsecond collisions break the newest-first ordering
    the ``--limit`` test asserts.
    """
    storage = await SQLiteStorage.open(db_path)
    for i, (run_id, workflow, terminal_status, cost) in enumerate(specs):
        await storage.create_run(run_id, workflow, None)
        if terminal_status is not None or cost is not None:
            await storage.update_run_status(
                run_id,
                terminal_status or "pending",
                total_cost_usd=cost,
            )
        if i < len(specs) - 1:
            await asyncio.sleep(0.01)


async def _row_count(db_path: Path) -> int:
    storage = await SQLiteStorage.open(db_path)
    rows = await storage.list_runs(limit=500)
    return len(rows)


# ---------------------------------------------------------------------------
# AC: empty Storage
# ---------------------------------------------------------------------------


def test_list_runs_empty_prints_header_and_placeholder(tmp_path: Path) -> None:
    """AC: empty Storage prints the header followed by ``(no runs)``."""
    result = _RUNNER.invoke(app, ["list-runs"])
    assert result.exit_code == 0, result.output
    assert "run_id" in result.output
    assert "workflow" in result.output
    assert "status" in result.output
    assert "started_at" in result.output
    assert "cost_usd" in result.output
    assert "(no runs)" in result.output


# ---------------------------------------------------------------------------
# AC: --workflow filter
# ---------------------------------------------------------------------------


def test_list_runs_workflow_filter(tmp_path: Path) -> None:
    """AC: ``--workflow planner`` returns exactly the matching subset."""
    asyncio.run(
        _seed_runs(
            tmp_path / "storage.sqlite",
            [
                ("run-a-planner", "planner", None, None),
                ("run-b-planner", "planner", None, None),
                ("run-c-slice", "slice_refactor", None, None),
            ],
        )
    )

    result = _RUNNER.invoke(app, ["list-runs", "--workflow", "planner"])
    assert result.exit_code == 0, result.output
    assert "run-a-planner" in result.output
    assert "run-b-planner" in result.output
    assert "run-c-slice" not in result.output


# ---------------------------------------------------------------------------
# AC: --status filter
# ---------------------------------------------------------------------------


def test_list_runs_status_filter(tmp_path: Path) -> None:
    """AC: ``--status completed`` returns only the completed row."""
    asyncio.run(
        _seed_runs(
            tmp_path / "storage.sqlite",
            [
                ("run-pending", "planner", None, None),
                ("run-completed", "planner", "completed", 0.0012),
                ("run-rejected", "planner", "gate_rejected", 0.0034),
            ],
        )
    )

    result = _RUNNER.invoke(app, ["list-runs", "--status", "completed"])
    assert result.exit_code == 0, result.output
    assert "run-completed" in result.output
    assert "run-pending" not in result.output
    assert "run-rejected" not in result.output


# ---------------------------------------------------------------------------
# AC: --limit caps rows
# ---------------------------------------------------------------------------


def test_list_runs_limit_caps_rows(tmp_path: Path) -> None:
    """AC: ``--limit 2`` returns exactly two rows, newest first."""
    asyncio.run(
        _seed_runs(
            tmp_path / "storage.sqlite",
            [
                ("run-01-oldest", "planner", None, None),
                ("run-02", "planner", None, None),
                ("run-03", "planner", None, None),
                ("run-04", "planner", None, None),
                ("run-05-newest", "planner", None, None),
            ],
        )
    )

    result = _RUNNER.invoke(app, ["list-runs", "--limit", "2"])
    assert result.exit_code == 0, result.output
    # The two newest rows (05, 04) must appear; the three older rows
    # must not. Asserting absence of the oldest row catches an
    # off-by-one in the ORDER BY direction.
    assert "run-05-newest" in result.output
    assert "run-04" in result.output
    assert "run-01-oldest" not in result.output
    assert "run-02" not in result.output
    assert "run-03" not in result.output


# ---------------------------------------------------------------------------
# AC: pure-read invariant
# ---------------------------------------------------------------------------


def test_list_runs_is_pure_read(tmp_path: Path) -> None:
    """AC: no ``INSERT`` / ``UPDATE`` — row count before == row count after."""
    db_path = tmp_path / "storage.sqlite"
    asyncio.run(
        _seed_runs(
            db_path,
            [
                ("run-one", "planner", None, None),
                ("run-two", "planner", "completed", 0.0005),
            ],
        )
    )
    before = asyncio.run(_row_count(db_path))
    result = _RUNNER.invoke(app, ["list-runs"])
    assert result.exit_code == 0, result.output
    after = asyncio.run(_row_count(db_path))
    assert before == after == 2


# ---------------------------------------------------------------------------
# AC: cost column rendering
# ---------------------------------------------------------------------------


def test_list_runs_cost_column_rendering(tmp_path: Path) -> None:
    """AC: populated ``total_cost_usd`` prints as a dollar figure; NULL is ``—``.

    ``runs.total_cost_usd`` has ``DEFAULT 0.0`` (migration 001) so a
    fresh ``create_run`` never produces ``NULL``. Simulating the spec's
    NULL case — which maps to a pre-migration or manually-inspected
    row — requires a direct ``UPDATE ... SET total_cost_usd = NULL``.
    """
    db_path = tmp_path / "storage.sqlite"
    asyncio.run(
        _seed_runs(
            db_path,
            [
                ("run-cost-null", "planner", None, None),
                ("run-cost-set", "planner", "completed", 0.0033),
            ],
        )
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE runs SET total_cost_usd = NULL WHERE run_id = ?",
            ("run-cost-null",),
        )
        conn.commit()

    result = _RUNNER.invoke(app, ["list-runs"])
    assert result.exit_code == 0, result.output
    assert "$0.0033" in result.output
    assert "—" in result.output
