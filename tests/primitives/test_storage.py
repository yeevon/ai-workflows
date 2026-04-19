"""Tests for M1 Task 08 — SQLite-backed storage layer.

Every acceptance criterion in ``task_08_storage.md`` has a dedicated test.
The migration-rollback test writes a transient ``002_tmp.sql`` file into a
separate migrations directory so the production ``migrations/`` tree is
never mutated.
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest

from ai_workflows.primitives.storage import SQLiteStorage, StorageBackend

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "migrations"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _open(tmp_path: Path, filename: str = "test.db") -> SQLiteStorage:
    return await SQLiteStorage.open(tmp_path / filename)


def _raw_connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Protocol conformance (AC-1)
# ---------------------------------------------------------------------------


async def test_sqlite_storage_satisfies_storage_backend_protocol(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    assert isinstance(storage, StorageBackend)


def test_sqlite_storage_pre_open_still_satisfies_protocol(tmp_path: Path) -> None:
    # Pre-initialisation instance also satisfies the structural protocol —
    # the methods exist on the class, not on a post-init wrapper.
    storage = SQLiteStorage(tmp_path / "x.db")
    assert isinstance(storage, StorageBackend)


# ---------------------------------------------------------------------------
# Migration application + dedupe (AC-2)
# ---------------------------------------------------------------------------


async def test_first_open_applies_001_initial(tmp_path: Path) -> None:
    await _open(tmp_path)
    with _raw_connect(tmp_path / "test.db") as conn:
        rows = conn.execute(
            "SELECT migration_id FROM _yoyo_migration"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["migration_id"] == "001_initial"


async def test_second_open_is_noop(tmp_path: Path) -> None:
    await _open(tmp_path)
    await _open(tmp_path)
    with _raw_connect(tmp_path / "test.db") as conn:
        rows = conn.execute("SELECT migration_id FROM _yoyo_migration").fetchall()
    assert len(rows) == 1


async def test_first_open_creates_every_schema_table(tmp_path: Path) -> None:
    await _open(tmp_path)
    with _raw_connect(tmp_path / "test.db") as conn:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    required = {"runs", "tasks", "llm_calls", "artifacts", "human_gate_states"}
    assert required <= tables


async def test_first_open_creates_required_indexes(tmp_path: Path) -> None:
    await _open(tmp_path)
    with _raw_connect(tmp_path / "test.db") as conn:
        names = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
    assert "idx_llm_calls_run" in names
    assert "idx_tasks_run_status" in names


# ---------------------------------------------------------------------------
# WAL mode (AC-3)
# ---------------------------------------------------------------------------


async def test_wal_mode_is_enabled_after_open(tmp_path: Path) -> None:
    await _open(tmp_path)
    with _raw_connect(tmp_path / "test.db") as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


# ---------------------------------------------------------------------------
# create_run requires workflow_dir_hash (AC-4)
# ---------------------------------------------------------------------------


async def test_create_run_rejects_none_workflow_dir_hash(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    with pytest.raises(ValueError, match="workflow_dir_hash"):
        await storage.create_run(
            run_id="r1",
            workflow_id="wf",
            workflow_dir_hash=None,  # type: ignore[arg-type]
            budget_cap_usd=1.0,
        )


async def test_create_run_rejects_empty_workflow_dir_hash(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    with pytest.raises(ValueError, match="workflow_dir_hash"):
        await storage.create_run(
            run_id="r1",
            workflow_id="wf",
            workflow_dir_hash="",
            budget_cap_usd=1.0,
        )


async def test_create_run_persists_workflow_dir_hash(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    await storage.create_run(
        run_id="r1",
        workflow_id="wf",
        workflow_dir_hash="a" * 64,
        budget_cap_usd=0.5,
    )
    row = await storage.get_run("r1")
    assert row is not None
    assert row["workflow_dir_hash"] == "a" * 64
    assert row["status"] == "pending"
    assert row["workflow_id"] == "wf"
    assert row["budget_cap_usd"] == pytest.approx(0.5)


async def test_create_run_accepts_none_budget_cap(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    await storage.create_run(
        run_id="r1",
        workflow_id="wf",
        workflow_dir_hash="h",
        budget_cap_usd=None,
    )
    row = await storage.get_run("r1")
    assert row is not None
    assert row["budget_cap_usd"] is None


# ---------------------------------------------------------------------------
# Run status updates
# ---------------------------------------------------------------------------


async def test_update_run_status_sets_finished_at_on_terminal_state(
    tmp_path: Path,
) -> None:
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", "h", None)
    await storage.update_run_status("r1", "completed", total_cost_usd=1.23)
    row = await storage.get_run("r1")
    assert row is not None
    assert row["status"] == "completed"
    assert row["total_cost_usd"] == pytest.approx(1.23)
    assert row["finished_at"] is not None


async def test_update_run_status_leaves_finished_at_null_for_non_terminal(
    tmp_path: Path,
) -> None:
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", "h", None)
    await storage.update_run_status("r1", "running")
    row = await storage.get_run("r1")
    assert row is not None
    assert row["status"] == "running"
    assert row["finished_at"] is None


# ---------------------------------------------------------------------------
# get_run / list_runs
# ---------------------------------------------------------------------------


async def test_get_run_returns_none_when_missing(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    assert await storage.get_run("nope") is None


async def test_list_runs_orders_newest_first(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", "h", None)
    # Small sleep so started_at is distinguishable; SQLite ISO strings sort
    # lexicographically and are microsecond-precise in our clock.
    await asyncio.sleep(0.01)
    await storage.create_run("r2", "wf", "h", None)
    runs = await storage.list_runs()
    ids = [row["run_id"] for row in runs]
    assert ids == ["r2", "r1"]


async def test_list_runs_respects_limit(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    for idx in range(5):
        await storage.create_run(f"r{idx}", "wf", "h", None)
    assert len(await storage.list_runs(limit=2)) == 2


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


async def test_upsert_task_inserts_then_updates(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", "h", None)
    started = "2026-01-01T00:00:00+00:00"
    finished = "2026-01-01T00:05:00+00:00"
    await storage.upsert_task("r1", "t1", "worker", "pending", started_at=started)
    await storage.upsert_task("r1", "t1", "worker", "completed", finished_at=finished)
    rows = await storage.get_tasks("r1")
    assert len(rows) == 1
    assert rows[0]["status"] == "completed"
    assert rows[0]["started_at"] == started
    assert rows[0]["finished_at"] == finished


async def test_upsert_task_rejects_unknown_kwargs(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", "h", None)
    with pytest.raises(TypeError, match="unexpected kwargs"):
        await storage.upsert_task("r1", "t1", "worker", "pending", notes="x")


async def test_get_tasks_is_scoped_to_run(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", "h", None)
    await storage.create_run("r2", "wf", "h", None)
    await storage.upsert_task("r1", "t1", "worker", "done")
    await storage.upsert_task("r2", "t2", "worker", "done")
    r1_tasks = await storage.get_tasks("r1")
    assert {row["task_id"] for row in r1_tasks} == {"t1"}


# ---------------------------------------------------------------------------
# LLM call logging + cost aggregation (AC-5)
# ---------------------------------------------------------------------------


async def test_get_total_cost_excludes_is_local_rows(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", "h", None)
    await storage.log_llm_call(
        "r1", workflow_id="wf", component="worker", tier="sonnet",
        model="claude-sonnet-4-6", cost_usd=0.10, is_local=False,
    )
    await storage.log_llm_call(
        "r1", workflow_id="wf", component="worker", tier="local_coder",
        model="qwen", cost_usd=0.05, is_local=True,
    )
    await storage.log_llm_call(
        "r1", workflow_id="wf", component="worker", tier="gemini_flash",
        model="gemini-flash", cost_usd=0.03, is_local=False,
    )
    total = await storage.get_total_cost("r1")
    assert total == pytest.approx(0.13)


async def test_get_total_cost_is_zero_when_only_local_calls(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", "h", None)
    await storage.log_llm_call(
        "r1", workflow_id="wf", component="worker", tier="local_coder",
        model="qwen", cost_usd=0.0, is_local=True,
    )
    assert await storage.get_total_cost("r1") == 0.0


async def test_get_total_cost_is_zero_when_no_rows(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", "h", None)
    assert await storage.get_total_cost("r1") == 0.0


async def test_get_cost_breakdown_groups_by_component_excluding_local(
    tmp_path: Path,
) -> None:
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", "h", None)
    await storage.log_llm_call(
        "r1", workflow_id="wf", component="worker", tier="sonnet",
        model="m", cost_usd=0.10, is_local=False,
    )
    await storage.log_llm_call(
        "r1", workflow_id="wf", component="worker", tier="sonnet",
        model="m", cost_usd=0.05, is_local=False,
    )
    await storage.log_llm_call(
        "r1", workflow_id="wf", component="validator", tier="haiku",
        model="m", cost_usd=0.02, is_local=False,
    )
    await storage.log_llm_call(
        "r1", workflow_id="wf", component="worker", tier="local_coder",
        model="qwen", cost_usd=99.0, is_local=True,
    )
    breakdown = await storage.get_cost_breakdown("r1")
    assert breakdown == {"worker": pytest.approx(0.15), "validator": pytest.approx(0.02)}


async def test_log_llm_call_stores_is_escalation_flag(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", "h", None)
    await storage.log_llm_call(
        "r1", workflow_id="wf", component="worker", tier="opus",
        model="m", cost_usd=0.0, is_escalation=True,
    )
    with _raw_connect(tmp_path / "test.db") as conn:
        rows = conn.execute("SELECT is_escalation FROM llm_calls").fetchall()
    assert rows[0]["is_escalation"] == 1


async def test_log_llm_call_rejects_unknown_kwargs(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", "h", None)
    with pytest.raises(TypeError, match="unexpected kwargs"):
        await storage.log_llm_call(
            "r1", workflow_id="wf", component="worker", tier="t", model="m",
            cost_usd=0.0, not_a_column=1,
        )


async def test_log_llm_call_auto_populates_called_at(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", "h", None)
    await storage.log_llm_call(
        "r1", workflow_id="wf", component="worker", tier="t", model="m",
        cost_usd=0.0,
    )
    with _raw_connect(tmp_path / "test.db") as conn:
        row = conn.execute("SELECT called_at FROM llm_calls").fetchone()
    assert row["called_at"] is not None


# ---------------------------------------------------------------------------
# Migration rollback (AC-6)
# ---------------------------------------------------------------------------


async def test_migration_rollback_reverts_schema(tmp_path: Path) -> None:
    """Apply 002, roll it back, confirm the schema reverts cleanly.

    Uses a transient migrations directory seeded with the committed
    ``001_initial.sql`` plus rollback so the production ``migrations/``
    tree is never touched. ``002_tmp.sql`` adds a table and column; the
    rollback drops both.
    """
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_initial.sql").write_text(
        (MIGRATIONS_DIR / "001_initial.sql").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (mig_dir / "001_initial.rollback.sql").write_text(
        (MIGRATIONS_DIR / "001_initial.rollback.sql").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (mig_dir / "002_tmp.sql").write_text("CREATE TABLE tmp_probe (id INTEGER);\n")
    (mig_dir / "002_tmp.rollback.sql").write_text("DROP TABLE tmp_probe;\n")

    db_path = tmp_path / "rollback.db"
    await SQLiteStorage.open(db_path, migrations_dir=mig_dir)

    # Schema before rollback includes tmp_probe.
    with _raw_connect(db_path) as conn:
        names = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "tmp_probe" in names

    # Roll back 002 only via yoyo's API; 001 stays applied.
    from yoyo import get_backend, read_migrations

    backend = get_backend(f"sqlite:///{db_path}")
    all_migrations = read_migrations(str(mig_dir))
    with backend.lock():
        to_rollback = [m for m in backend.to_rollback(all_migrations) if m.id == "002_tmp"]
        from yoyo.migrations import MigrationList

        backend.rollback_migrations(MigrationList(to_rollback))

    with _raw_connect(db_path) as conn:
        names_after = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "tmp_probe" not in names_after
    # 001's tables are still there.
    assert "runs" in names_after
    assert "llm_calls" in names_after


# ---------------------------------------------------------------------------
# Concurrent writes (AC-7)
# ---------------------------------------------------------------------------


async def test_twenty_concurrent_log_llm_call_succeeds(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", "h", None)
    await asyncio.gather(
        *[
            storage.log_llm_call(
                "r1",
                workflow_id="wf",
                component="worker",
                tier="sonnet",
                model="m",
                cost_usd=0.01,
                is_local=False,
            )
            for _ in range(20)
        ]
    )
    total = await storage.get_total_cost("r1")
    assert total == pytest.approx(0.20)
    with _raw_connect(tmp_path / "test.db") as conn:
        (count,) = conn.execute("SELECT COUNT(*) FROM llm_calls").fetchone()
    assert count == 20


# ---------------------------------------------------------------------------
# Artifacts + gates (coverage beyond ACs)
# ---------------------------------------------------------------------------


async def test_log_artifact_persists_row(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", "h", None)
    await storage.log_artifact("r1", "patch", "/tmp/foo.patch", task_id="t1")
    with _raw_connect(tmp_path / "test.db") as conn:
        row = conn.execute(
            "SELECT run_id, task_id, artifact_type, file_path FROM artifacts"
        ).fetchone()
    assert row["run_id"] == "r1"
    assert row["task_id"] == "t1"
    assert row["artifact_type"] == "patch"
    assert row["file_path"] == "/tmp/foo.patch"


async def test_update_gate_state_upsert_preserves_rendered_at(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", "h", None)
    await storage.update_gate_state("r1", "g1", "pending")
    first = await storage.get_gate_state("r1", "g1")
    assert first is not None
    original_rendered = first["rendered_at"]
    await asyncio.sleep(0.01)
    await storage.update_gate_state("r1", "g1", "approved", decision="go")
    second = await storage.get_gate_state("r1", "g1")
    assert second is not None
    assert second["status"] == "approved"
    assert second["decision"] == "go"
    assert second["rendered_at"] == original_rendered
    assert second["resolved_at"] is not None


async def test_get_gate_state_returns_none_when_absent(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    assert await storage.get_gate_state("r1", "g1") is None


# ---------------------------------------------------------------------------
# initialize idempotency
# ---------------------------------------------------------------------------


async def test_initialize_is_idempotent(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "x.db")
    await storage.initialize()
    await storage.initialize()
    with _raw_connect(tmp_path / "x.db") as conn:
        (count,) = conn.execute("SELECT COUNT(*) FROM _yoyo_migration").fetchone()
    assert count == 1
