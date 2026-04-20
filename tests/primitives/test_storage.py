"""Tests for M1 Task 05 — trimmed SQLite-backed storage layer.

Every acceptance criterion in
[task_05_trim_storage.md](../../design_docs/phases/milestone_1_reconciliation/task_05_trim_storage.md)
has a dedicated test. The migration-rollback test seeds a transient
migrations directory so the production ``migrations/`` tree is never
mutated.
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
# Protocol conformance
# ---------------------------------------------------------------------------


async def test_sqlite_storage_satisfies_storage_backend_protocol(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    assert isinstance(storage, StorageBackend)


def test_sqlite_storage_pre_open_still_satisfies_protocol(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "x.db")
    assert isinstance(storage, StorageBackend)


def test_storage_protocol_only_exposes_the_trimmed_surface() -> None:
    """AC-3: ``StorageBackend`` contains the seven trimmed M1.05 methods.

    Guards against accidental re-introduction of the pre-pivot per-call
    ledger / task / artifact methods as the module evolves. M3 Task 03
    adds ``write_artifact`` / ``read_artifact`` — a JSON-payload surface
    for the first workflow's post-gate artifact node, not the pre-pivot
    per-file artifacts table dropped by 002_reconciliation.
    """
    expected = {
        "create_run",
        "update_run_status",
        "cancel_run",
        "get_run",
        "list_runs",
        "record_gate",
        "record_gate_response",
        "get_gate",
        "write_artifact",
        "read_artifact",
    }
    actual = {
        name
        for name in dir(StorageBackend)
        if not name.startswith("_")
    }
    assert actual == expected


# ---------------------------------------------------------------------------
# Migration application + idempotency (AC-1)
# ---------------------------------------------------------------------------


async def test_first_open_applies_all_migrations(tmp_path: Path) -> None:
    await _open(tmp_path)
    with _raw_connect(tmp_path / "test.db") as conn:
        rows = conn.execute(
            "SELECT migration_id FROM _yoyo_migration ORDER BY migration_id"
        ).fetchall()
    ids = [row["migration_id"] for row in rows]
    assert ids == ["001_initial", "002_reconciliation", "003_artifacts"]


async def test_second_open_is_noop(tmp_path: Path) -> None:
    """AC-1 idempotency clause: reapply on the same DB does nothing."""
    await _open(tmp_path)
    await _open(tmp_path)
    with _raw_connect(tmp_path / "test.db") as conn:
        (count,) = conn.execute("SELECT COUNT(*) FROM _yoyo_migration").fetchone()
    assert count == 3


async def test_reconciliation_drops_legacy_tables(tmp_path: Path) -> None:
    """Legacy checkpoint-adjacent tables stay dropped after 002 + 003.

    003 reintroduces a narrower ``artifacts`` table (``(run_id, kind, payload_json)``)
    for post-gate workflow output, so ``artifacts`` is intentionally absent
    from the "must stay dropped" list.
    """
    await _open(tmp_path)
    with _raw_connect(tmp_path / "test.db") as conn:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    for dropped in ("tasks", "llm_calls", "human_gate_states"):
        assert dropped not in tables, f"{dropped} should have been dropped"
    assert "runs" in tables
    assert "gate_responses" in tables
    assert "artifacts" in tables  # re-added by 003_artifacts.sql (M3 T03)


async def test_reconciliation_drops_workflow_dir_hash_and_profile_columns(
    tmp_path: Path,
) -> None:
    await _open(tmp_path)
    with _raw_connect(tmp_path / "test.db") as conn:
        cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(runs)").fetchall()
        }
    assert "workflow_dir_hash" not in cols
    assert "profile" not in cols
    # The surviving shape must match the task 05 spec exactly.
    expected = {
        "run_id",
        "workflow_id",
        "status",
        "started_at",
        "finished_at",
        "budget_cap_usd",
        "total_cost_usd",
    }
    assert expected <= cols


async def test_reconciliation_creates_gate_responses_with_expected_columns(
    tmp_path: Path,
) -> None:
    await _open(tmp_path)
    with _raw_connect(tmp_path / "test.db") as conn:
        cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(gate_responses)").fetchall()
        }
    expected = {
        "run_id",
        "gate_id",
        "prompt",
        "response",
        "responded_at",
        "strict_review",
    }
    assert expected <= cols


# ---------------------------------------------------------------------------
# WAL mode
# ---------------------------------------------------------------------------


async def test_wal_mode_is_enabled_after_open(tmp_path: Path) -> None:
    await _open(tmp_path)
    with _raw_connect(tmp_path / "test.db") as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


# ---------------------------------------------------------------------------
# create_run / update_run_status / get_run / list_runs
# ---------------------------------------------------------------------------


async def test_create_run_persists_row(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    await storage.create_run(run_id="r1", workflow_id="wf", budget_cap_usd=0.5)
    row = await storage.get_run("r1")
    assert row is not None
    assert row["run_id"] == "r1"
    assert row["workflow_id"] == "wf"
    assert row["status"] == "pending"
    assert row["budget_cap_usd"] == pytest.approx(0.5)


async def test_create_run_accepts_none_budget_cap(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    await storage.create_run(run_id="r1", workflow_id="wf", budget_cap_usd=None)
    row = await storage.get_run("r1")
    assert row is not None
    assert row["budget_cap_usd"] is None


async def test_update_run_status_sets_finished_at_on_terminal_state(
    tmp_path: Path,
) -> None:
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", None)
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
    await storage.create_run("r1", "wf", None)
    await storage.update_run_status("r1", "running")
    row = await storage.get_run("r1")
    assert row is not None
    assert row["status"] == "running"
    assert row["finished_at"] is None


async def test_update_run_status_respects_explicit_finished_at(
    tmp_path: Path,
) -> None:
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", None)
    explicit = "2030-01-01T00:00:00+00:00"
    await storage.update_run_status("r1", "completed", finished_at=explicit)
    row = await storage.get_run("r1")
    assert row is not None
    assert row["finished_at"] == explicit


async def test_get_run_returns_none_when_missing(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    assert await storage.get_run("nope") is None


async def test_list_runs_orders_newest_first(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", None)
    await asyncio.sleep(0.01)
    await storage.create_run("r2", "wf", None)
    runs = await storage.list_runs()
    ids = [row["run_id"] for row in runs]
    assert ids == ["r2", "r1"]


async def test_list_runs_respects_limit(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    for idx in range(5):
        await storage.create_run(f"r{idx}", "wf", None)
    assert len(await storage.list_runs(limit=2)) == 2


async def test_list_runs_status_filter(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", None)
    await storage.create_run("r2", "wf", None)
    await storage.update_run_status("r1", "completed")
    only_completed = await storage.list_runs(status_filter="completed")
    assert [row["run_id"] for row in only_completed] == ["r1"]
    only_pending = await storage.list_runs(status_filter="pending")
    assert [row["run_id"] for row in only_pending] == ["r2"]


# ---------------------------------------------------------------------------
# cancel_run (M4 Task 05)
# ---------------------------------------------------------------------------


async def test_cancel_run_flips_pending_row_to_cancelled(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", None)

    result = await storage.cancel_run("r1")
    assert result == "cancelled"

    row = await storage.get_run("r1")
    assert row is not None
    assert row["status"] == "cancelled"
    assert row["finished_at"] is not None


async def test_cancel_run_is_noop_on_terminal_row(tmp_path: Path) -> None:
    """AC: a row already in a terminal state returns ``already_terminal``."""
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", None)
    await storage.update_run_status("r1", "completed")

    before = await storage.get_run("r1")
    assert before is not None

    result = await storage.cancel_run("r1")
    assert result == "already_terminal"

    after = await storage.get_run("r1")
    assert after is not None
    assert after["status"] == "completed"
    # no side-effect mutation of finished_at / other columns
    assert after["finished_at"] == before["finished_at"]


async def test_cancel_run_idempotent_second_call_is_already_terminal(
    tmp_path: Path,
) -> None:
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", None)
    assert await storage.cancel_run("r1") == "cancelled"
    assert await storage.cancel_run("r1") == "already_terminal"


async def test_cancel_run_raises_on_unknown_run_id(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    with pytest.raises(ValueError, match="no run found"):
        await storage.cancel_run("does-not-exist")


# ---------------------------------------------------------------------------
# Gate log round-trip
# ---------------------------------------------------------------------------


async def test_record_gate_then_record_gate_response_roundtrip(
    tmp_path: Path,
) -> None:
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", None)
    await storage.record_gate(
        run_id="r1",
        gate_id="plan_review",
        prompt="Approve the plan?",
        strict_review=True,
    )
    pending = await storage.get_gate("r1", "plan_review")
    assert pending is not None
    assert pending["prompt"] == "Approve the plan?"
    assert pending["strict_review"] == 1
    assert pending["response"] is None
    assert pending["responded_at"] is None

    await storage.record_gate_response(
        run_id="r1",
        gate_id="plan_review",
        response="approved",
    )
    resolved = await storage.get_gate("r1", "plan_review")
    assert resolved is not None
    assert resolved["response"] == "approved"
    assert resolved["responded_at"] is not None
    # Earlier fields preserved.
    assert resolved["prompt"] == "Approve the plan?"
    assert resolved["strict_review"] == 1


async def test_record_gate_upsert_preserves_identity_on_second_call(
    tmp_path: Path,
) -> None:
    """Re-recording the same gate_id is a safe no-op on prompt/strict_review."""
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", None)
    await storage.record_gate("r1", "g1", "v1", strict_review=False)
    await storage.record_gate("r1", "g1", "v2", strict_review=True)
    row = await storage.get_gate("r1", "g1")
    assert row is not None
    assert row["prompt"] == "v2"
    assert row["strict_review"] == 1


async def test_record_gate_response_noop_when_gate_absent(tmp_path: Path) -> None:
    """Responding without a prior record_gate() call is a no-op row-count-wise."""
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", None)
    await storage.record_gate_response("r1", "g1", "approved")
    assert await storage.get_gate("r1", "g1") is None


async def test_get_gate_returns_none_when_absent(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    assert await storage.get_gate("r1", "g1") is None


async def test_strict_review_false_persists_as_zero(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", None)
    await storage.record_gate("r1", "g1", "p", strict_review=False)
    row = await storage.get_gate("r1", "g1")
    assert row is not None
    assert row["strict_review"] == 0


# ---------------------------------------------------------------------------
# Artifacts (M3 Task 03)
# ---------------------------------------------------------------------------


async def test_write_artifact_round_trip(tmp_path: Path) -> None:
    """M3 T03: ``write_artifact`` persists the JSON payload; ``read_artifact`` returns it."""
    storage = await _open(tmp_path)
    await storage.create_run("r1", "planner", None)
    await storage.write_artifact("r1", "plan", '{"goal": "ship"}')
    row = await storage.read_artifact("r1", "plan")
    assert row is not None
    assert row["run_id"] == "r1"
    assert row["kind"] == "plan"
    assert row["payload_json"] == '{"goal": "ship"}'
    assert row["created_at"] is not None


async def test_read_artifact_returns_none_when_absent(tmp_path: Path) -> None:
    storage = await _open(tmp_path)
    assert await storage.read_artifact("r1", "plan") is None


async def test_write_artifact_upserts_on_repeat(tmp_path: Path) -> None:
    """Re-writing the same ``(run_id, kind)`` pair overwrites the payload."""
    storage = await _open(tmp_path)
    await storage.create_run("r1", "planner", None)
    await storage.write_artifact("r1", "plan", '{"v": 1}')
    await storage.write_artifact("r1", "plan", '{"v": 2}')
    row = await storage.read_artifact("r1", "plan")
    assert row is not None
    assert row["payload_json"] == '{"v": 2}'


# ---------------------------------------------------------------------------
# Migration rollback (AC-2)
# ---------------------------------------------------------------------------


async def test_reconciliation_rollback_restores_pre_pivot_schema(
    tmp_path: Path,
) -> None:
    """AC-2: rolling back 002_reconciliation restores pre-pivot schema shape.

    Seeds a transient migrations directory with copies of the committed
    migration pair, applies both, rolls back 002 via yoyo, and asserts
    that the pre-reconciliation tables and columns return.
    """
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    for name in (
        "001_initial.sql",
        "001_initial.rollback.sql",
        "002_reconciliation.sql",
        "002_reconciliation.rollback.sql",
    ):
        (mig_dir / name).write_text(
            (MIGRATIONS_DIR / name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    db_path = tmp_path / "rollback.db"
    await SQLiteStorage.open(db_path, migrations_dir=mig_dir)

    from yoyo import get_backend, read_migrations
    from yoyo.migrations import MigrationList

    backend = get_backend(f"sqlite:///{db_path}")
    all_migrations = read_migrations(str(mig_dir))
    with backend.lock():
        to_rollback = [
            m for m in backend.to_rollback(all_migrations)
            if m.id == "002_reconciliation"
        ]
        backend.rollback_migrations(MigrationList(to_rollback))

    with _raw_connect(db_path) as conn:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        runs_cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(runs)").fetchall()
        }

    # Pre-pivot tables restored.
    for restored in ("tasks", "artifacts", "llm_calls", "human_gate_states"):
        assert restored in tables, f"{restored} should have been restored"
    # gate_responses dropped by rollback.
    assert "gate_responses" not in tables
    # runs columns restored.
    assert "workflow_dir_hash" in runs_cols
    assert "profile" in runs_cols


# ---------------------------------------------------------------------------
# Concurrent writes
# ---------------------------------------------------------------------------


async def test_twenty_concurrent_record_gate_succeeds(tmp_path: Path) -> None:
    """Write-path lock still serialises concurrent writers after the trim."""
    storage = await _open(tmp_path)
    await storage.create_run("r1", "wf", None)
    await asyncio.gather(
        *[
            storage.record_gate(
                run_id="r1",
                gate_id=f"g{idx}",
                prompt=f"p{idx}",
                strict_review=False,
            )
            for idx in range(20)
        ]
    )
    with _raw_connect(tmp_path / "test.db") as conn:
        (count,) = conn.execute(
            "SELECT COUNT(*) FROM gate_responses WHERE run_id = ?",
            ("r1",),
        ).fetchone()
    assert count == 20


# ---------------------------------------------------------------------------
# initialize idempotency
# ---------------------------------------------------------------------------


async def test_initialize_is_idempotent(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "x.db")
    await storage.initialize()
    await storage.initialize()
    with _raw_connect(tmp_path / "x.db") as conn:
        (count,) = conn.execute("SELECT COUNT(*) FROM _yoyo_migration").fetchone()
    assert count == 3
