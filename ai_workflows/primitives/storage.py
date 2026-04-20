"""SQLite-backed run registry and gate-response log.

Trimmed by M1 Task 05 per KDR-009 and
[architecture.md §4.1](../../design_docs/architecture.md): `Storage` now
owns only the run registry and the gate-response log. Every
checkpoint-adjacent surface that existed on the pre-pivot storage
layer — `tasks`, `artifacts`, `llm_calls`, `human_gate_states`,
`workflow_dir_hash` — moves to LangGraph's `SqliteSaver` (KDR-009), the
in-memory `CostTracker` aggregate prepared by M1 Task 08, and (for the
`workflow_dir_hash` fate) the ADR produced by M1 Task 10. The schema
reshape lands in the paired `migrations/002_reconciliation.sql`
migration + rollback.

M3 Task 03 reintroduces a narrower :class:`artifacts` surface via
``migrations/003_artifacts.sql``: a ``(run_id, kind)``-keyed JSON payload
row written by the first workflow's post-gate ``_artifact_node``. This
is NOT a rehydration of the pre-pivot per-file artifacts table — payloads
are JSON strings the workflow already produced, so checkpoint state still
belongs to LangGraph's ``SqliteSaver``.

Responsibilities
----------------
* :class:`StorageBackend` — structural protocol every backend (SQLite
  now; cloud backends later) must satisfy. Reduced to the seven methods
  listed in
  [task_05_trim_storage.md](../../design_docs/phases/milestone_1_reconciliation/task_05_trim_storage.md);
  M3 Task 03 adds ``write_artifact`` / ``read_artifact`` on top of that
  trimmed surface.
* :class:`SQLiteStorage` — default implementation. Opens a SQLite
  database at ``db_path``, applies pending migrations from the
  repo-local ``migrations/`` directory via yoyo-migrations, and flips
  ``PRAGMA journal_mode = WAL`` so writes and ``aiw inspect`` reads can
  interleave without blocking.

Concurrency model
-----------------
Every write method serialises through a single :class:`asyncio.Lock`.
Reads take fresh connections and do not touch the lock. Blocking
``sqlite3`` calls are pushed to :func:`asyncio.to_thread` so the event
loop stays responsive.

See also
--------
* ``migrations/001_initial.sql`` — the pre-pivot schema.
* ``migrations/002_reconciliation.sql`` — the trim landed by this task.
* ``primitives/cost.py`` — the ``CostTracker`` surface that M1 Task 08
  refits on top of this storage (in-memory aggregate, no
  per-call SQL row).
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

#: Env var a caller can set to redirect the default storage path. Mirrors
#: the ``AIW_CHECKPOINT_DB`` convention in ``graph/checkpointer.py`` so
#: the two DB files share one override pattern. Consulted only by
#: :func:`default_storage_path` when its explicit argument is ``None``.
AIW_STORAGE_DB_ENV = "AIW_STORAGE_DB"

#: Default on-disk location for the run registry + gate log.
#: Distinct from ``DEFAULT_CHECKPOINT_PATH`` per KDR-009 (Storage and the
#: LangGraph checkpoint saver never share a file).
DEFAULT_STORAGE_PATH = Path.home() / ".ai-workflows" / "storage.sqlite"


def default_storage_path(db_path: str | Path | None = None) -> Path:
    """Resolve and prepare the on-disk path for :class:`SQLiteStorage`.

    Path resolution (in order of precedence):

    1. Explicit ``db_path`` argument if non-``None``.
    2. ``AIW_STORAGE_DB`` env var if set.
    3. ``~/.ai-workflows/storage.sqlite``.

    The parent directory is created lazily so the first invocation on a
    fresh machine does not require manual setup — mirrors the
    ``_prepare_path`` behaviour in ``graph/checkpointer.py``. Added in
    M3 Task 04 so the CLI / MCP surfaces can open Storage with the same
    default handling the checkpointer already has.
    """
    if db_path is not None:
        resolved = Path(db_path).expanduser()
    else:
        env_override = os.environ.get(AIW_STORAGE_DB_ENV)
        resolved = (
            Path(env_override).expanduser() if env_override else DEFAULT_STORAGE_PATH
        )
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


@runtime_checkable
class StorageBackend(Protocol):
    """Structural protocol every run-log storage backend must satisfy.

    The seven methods below are the full surface after M1 Task 05: run
    registry (create / update / get / list) plus the gate log (record
    gate, record response, get gate).
    """

    async def create_run(
        self,
        run_id: str,
        workflow_id: str,
        budget_cap_usd: float | None,
    ) -> None:
        """Insert a new ``runs`` row in status ``pending``."""
        ...

    async def update_run_status(
        self,
        run_id: str,
        status: str,
        finished_at: str | None = None,
        total_cost_usd: float | None = None,
    ) -> None:
        """Update the ``runs.status`` column and optional finished_at / total cost."""
        ...

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Return the ``runs`` row as a dict, or ``None`` when absent."""
        ...

    async def list_runs(
        self,
        limit: int = 50,
        status_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return the most recent runs, newest first. Optional status filter."""
        ...

    async def record_gate(
        self,
        run_id: str,
        gate_id: str,
        prompt: str,
        strict_review: bool,
    ) -> None:
        """Insert a pending ``gate_responses`` row (response + responded_at null)."""
        ...

    async def record_gate_response(
        self,
        run_id: str,
        gate_id: str,
        response: str,
    ) -> None:
        """Stamp an already-recorded gate with its response and ``responded_at``."""
        ...

    async def get_gate(
        self,
        run_id: str,
        gate_id: str,
    ) -> dict[str, Any] | None:
        """Return the ``gate_responses`` row, or ``None`` when unseen."""
        ...

    async def write_artifact(
        self,
        run_id: str,
        kind: str,
        payload_json: str,
    ) -> None:
        """Upsert a workflow artifact row keyed by ``(run_id, kind)``.

        Added in M3 Task 03 for the first workflow's post-gate
        artifact-persistence node. Not a reintroduction of the pre-pivot
        per-file ``artifacts`` surface — payloads are JSON strings the
        workflow already produced, and checkpoint state still lives in
        LangGraph's ``SqliteSaver`` (KDR-009).
        """
        ...

    async def read_artifact(
        self,
        run_id: str,
        kind: str,
    ) -> dict[str, Any] | None:
        """Return the ``artifacts`` row, or ``None`` when absent."""
        ...


def _default_migrations_dir() -> Path:
    """Return the repo-root ``migrations/`` directory.

    Tests override this via the ``migrations_dir`` kwarg on
    :meth:`SQLiteStorage.__init__`.
    """
    return Path(__file__).resolve().parent.parent.parent / "migrations"


def _utcnow() -> str:
    """Return the current UTC timestamp in ISO 8601 format."""
    return datetime.now(UTC).isoformat()


def _row_to_dict(cursor: sqlite3.Cursor, row: sqlite3.Row) -> dict[str, Any]:
    """Convert a ``sqlite3.Row`` into a plain dict using the cursor description."""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


class SQLiteStorage:
    """SQLite-backed :class:`StorageBackend` with WAL mode and yoyo migrations.

    Use :meth:`open` as the async factory — it builds the instance,
    applies migrations, and flips WAL in a single awaitable. The raw
    constructor is kept sync so tests that only need a path (e.g. the
    protocol-conformance check) can skip the async hop.
    """

    def __init__(
        self,
        db_path: str | Path,
        *,
        migrations_dir: str | Path | None = None,
    ) -> None:
        self._db_path = str(Path(db_path).expanduser())
        self._migrations_dir = str(
            Path(migrations_dir).expanduser()
            if migrations_dir is not None
            else _default_migrations_dir()
        )
        self._write_lock = asyncio.Lock()
        self._initialized = False

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    @classmethod
    async def open(
        cls,
        db_path: str | Path,
        *,
        migrations_dir: str | Path | None = None,
    ) -> SQLiteStorage:
        """Build, migrate, and enable WAL. Returns a ready-to-use instance."""
        storage = cls(db_path, migrations_dir=migrations_dir)
        await storage.initialize()
        return storage

    async def initialize(self) -> None:
        """Apply pending migrations and enable WAL mode (idempotent)."""
        if self._initialized:
            return
        await self._apply_migrations()
        await self._enable_wal()
        self._initialized = True

    async def _apply_migrations(self) -> None:
        """Run yoyo-migrations against the DB."""
        await asyncio.to_thread(self._apply_migrations_sync)

    def _apply_migrations_sync(self) -> None:
        from yoyo import get_backend, read_migrations

        backend = get_backend(f"sqlite:///{self._db_path}")
        migrations = read_migrations(self._migrations_dir)
        with backend.lock():
            backend.apply_migrations(backend.to_apply(migrations))

    async def _enable_wal(self) -> None:
        """PRAGMA journal_mode = WAL."""
        await asyncio.to_thread(self._enable_wal_sync)

    def _enable_wal_sync(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")

    # ------------------------------------------------------------------
    # Connection helper
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Return a fresh connection with foreign keys + row-as-dict enabled."""
        conn = sqlite3.connect(self._db_path, timeout=30.0)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    async def create_run(
        self,
        run_id: str,
        workflow_id: str,
        budget_cap_usd: float | None,
    ) -> None:
        """Insert a new ``runs`` row in status ``pending``."""
        await self._run_write(
            self._create_run_sync,
            run_id,
            workflow_id,
            budget_cap_usd,
        )

    def _create_run_sync(
        self,
        run_id: str,
        workflow_id: str,
        budget_cap_usd: float | None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, workflow_id, status, started_at, budget_cap_usd
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    workflow_id,
                    "pending",
                    _utcnow(),
                    budget_cap_usd,
                ),
            )
            conn.commit()

    async def update_run_status(
        self,
        run_id: str,
        status: str,
        finished_at: str | None = None,
        total_cost_usd: float | None = None,
    ) -> None:
        """Update the run status; auto-populate ``finished_at`` on terminal states.

        If ``finished_at`` is passed explicitly it overrides the
        auto-stamp. Non-terminal statuses without an explicit
        ``finished_at`` leave the column untouched.
        """
        await self._run_write(
            self._update_run_status_sync,
            run_id,
            status,
            finished_at,
            total_cost_usd,
        )

    def _update_run_status_sync(
        self,
        run_id: str,
        status: str,
        finished_at: str | None,
        total_cost_usd: float | None,
    ) -> None:
        stamped_finished = finished_at
        if stamped_finished is None and status in {"completed", "failed"}:
            stamped_finished = _utcnow()
        with self._connect() as conn:
            if total_cost_usd is not None and stamped_finished is not None:
                conn.execute(
                    "UPDATE runs SET status = ?, total_cost_usd = ?, finished_at = ? "
                    "WHERE run_id = ?",
                    (status, total_cost_usd, stamped_finished, run_id),
                )
            elif total_cost_usd is not None:
                conn.execute(
                    "UPDATE runs SET status = ?, total_cost_usd = ? WHERE run_id = ?",
                    (status, total_cost_usd, run_id),
                )
            elif stamped_finished is not None:
                conn.execute(
                    "UPDATE runs SET status = ?, finished_at = ? WHERE run_id = ?",
                    (status, stamped_finished, run_id),
                )
            else:
                conn.execute(
                    "UPDATE runs SET status = ? WHERE run_id = ?",
                    (status, run_id),
                )
            conn.commit()

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Return the run row as a dict, or ``None`` when absent."""
        return await asyncio.to_thread(self._get_run_sync, run_id)

    def _get_run_sync(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            cursor = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            return _row_to_dict(cursor, row)

    async def list_runs(
        self,
        limit: int = 50,
        status_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return the most recent runs, newest first (ordered by ``started_at``)."""
        return await asyncio.to_thread(self._list_runs_sync, limit, status_filter)

    def _list_runs_sync(
        self,
        limit: int,
        status_filter: str | None,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if status_filter is not None:
                cursor = conn.execute(
                    "SELECT * FROM runs WHERE status = ? "
                    "ORDER BY started_at DESC LIMIT ?",
                    (status_filter, limit),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?",
                    (limit,),
                )
            return [_row_to_dict(cursor, row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Gates
    # ------------------------------------------------------------------

    async def record_gate(
        self,
        run_id: str,
        gate_id: str,
        prompt: str,
        strict_review: bool,
    ) -> None:
        """Insert a pending ``gate_responses`` row (response + responded_at null)."""
        await self._run_write(
            self._record_gate_sync,
            run_id,
            gate_id,
            prompt,
            strict_review,
        )

    def _record_gate_sync(
        self,
        run_id: str,
        gate_id: str,
        prompt: str,
        strict_review: bool,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO gate_responses (
                    run_id, gate_id, prompt, response, responded_at, strict_review
                ) VALUES (?, ?, ?, NULL, NULL, ?)
                ON CONFLICT(run_id, gate_id) DO UPDATE SET
                    prompt        = excluded.prompt,
                    strict_review = excluded.strict_review
                """,
                (run_id, gate_id, prompt, int(bool(strict_review))),
            )
            conn.commit()

    async def record_gate_response(
        self,
        run_id: str,
        gate_id: str,
        response: str,
    ) -> None:
        """Stamp an already-recorded gate with its response and ``responded_at``."""
        await self._run_write(
            self._record_gate_response_sync,
            run_id,
            gate_id,
            response,
        )

    def _record_gate_response_sync(
        self,
        run_id: str,
        gate_id: str,
        response: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE gate_responses SET response = ?, responded_at = ? "
                "WHERE run_id = ? AND gate_id = ?",
                (response, _utcnow(), run_id, gate_id),
            )
            conn.commit()

    async def get_gate(
        self,
        run_id: str,
        gate_id: str,
    ) -> dict[str, Any] | None:
        """Return the ``gate_responses`` row, or ``None`` when unseen."""
        return await asyncio.to_thread(self._get_gate_sync, run_id, gate_id)

    def _get_gate_sync(
        self,
        run_id: str,
        gate_id: str,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM gate_responses WHERE run_id = ? AND gate_id = ?",
                (run_id, gate_id),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return _row_to_dict(cursor, row)

    # ------------------------------------------------------------------
    # Artifacts (M3 Task 03)
    # ------------------------------------------------------------------

    async def write_artifact(
        self,
        run_id: str,
        kind: str,
        payload_json: str,
    ) -> None:
        """Upsert the ``(run_id, kind)`` artifact row with the JSON payload."""
        await self._run_write(
            self._write_artifact_sync,
            run_id,
            kind,
            payload_json,
        )

    def _write_artifact_sync(
        self,
        run_id: str,
        kind: str,
        payload_json: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO artifacts (run_id, kind, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(run_id, kind) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    created_at   = excluded.created_at
                """,
                (run_id, kind, payload_json, _utcnow()),
            )
            conn.commit()

    async def read_artifact(
        self,
        run_id: str,
        kind: str,
    ) -> dict[str, Any] | None:
        """Return the ``artifacts`` row, or ``None`` when absent."""
        return await asyncio.to_thread(self._read_artifact_sync, run_id, kind)

    def _read_artifact_sync(
        self,
        run_id: str,
        kind: str,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM artifacts WHERE run_id = ? AND kind = ?",
                (run_id, kind),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return _row_to_dict(cursor, row)

    # ------------------------------------------------------------------
    # Write-path lock helper
    # ------------------------------------------------------------------

    async def _run_write(self, fn: Any, *args: Any) -> None:
        """Run a blocking write under the asyncio lock + a worker thread."""
        async with self._write_lock:
            await asyncio.to_thread(fn, *args)
