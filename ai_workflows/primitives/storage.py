"""SQLite-backed run log with WAL mode and yoyo-managed migrations.

Produced by M1 Task 08 (closes CRIT-10, P-26 … P-31, W-03; introduces the
CRIT-02 ``workflow_dir_hash`` column paired with
:func:`ai_workflows.primitives.workflow_hash.compute_workflow_hash`).

Responsibilities
----------------
* :class:`StorageBackend` — structural protocol every backend (SQLite now;
  cloud backends later) must satisfy. Components and workflows depend on
  this interface, never on ``SQLiteStorage`` directly.
* :class:`SQLiteStorage` — default implementation. Opens a SQLite database
  at ``db_path``, applies any pending migrations from the repo-local
  ``migrations/`` directory via yoyo-migrations, and flips
  ``PRAGMA journal_mode = WAL`` so cost-tracking writes and ``aiw inspect``
  reads can interleave without blocking.

Concurrency model
-----------------
Every write method serialises through a single :class:`asyncio.Lock` so
20 concurrent ``asyncio.gather(log_llm_call(...))`` calls never collide on
the WAL writer. Reads take fresh connections and do not touch the lock.
Blocking ``sqlite3`` calls are pushed to :func:`asyncio.to_thread` so the
event loop stays responsive.

See also
--------
* ``migrations/001_initial.sql`` — the schema applied on first open.
* ``primitives/workflow_hash.py`` — the hash value stored in
  ``runs.workflow_dir_hash`` (CRIT-02).
* ``primitives/cost.py`` — the ``CostTracker`` protocol that Task 09's
  implementation layers on top of this storage.
"""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    """Structural protocol every run-log storage backend must satisfy.

    The SQLite implementation ships in this module; cloud/remote backends
    will live under their own namespace (e.g. ``primitives.storage_cloud``)
    once the M5 multi-tenant story is designed. Higher layers type-hint on
    this protocol so swapping backends is a one-line change in the
    workflow wiring.
    """

    async def create_run(
        self,
        run_id: str,
        workflow_id: str,
        workflow_dir_hash: str,
        budget_cap_usd: float | None,
    ) -> None:
        """Insert a new ``runs`` row in status ``pending``."""
        ...

    async def update_run_status(
        self,
        run_id: str,
        status: str,
        total_cost_usd: float | None = None,
    ) -> None:
        """Update the ``runs.status`` column and optionally total cost."""
        ...

    async def upsert_task(
        self,
        run_id: str,
        task_id: str,
        component: str,
        status: str,
        **kwargs: Any,
    ) -> None:
        """Insert or update a ``tasks`` row keyed by ``(task_id, run_id)``."""
        ...

    async def log_llm_call(self, run_id: str, **fields: Any) -> None:
        """Append one row to ``llm_calls``."""
        ...

    async def log_artifact(
        self,
        run_id: str,
        artifact_type: str,
        file_path: str,
        task_id: str | None = None,
    ) -> None:
        """Append one row to ``artifacts``."""
        ...

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Return the ``runs`` row as a dict, or ``None`` when absent."""
        ...

    async def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent runs, newest first."""
        ...

    async def get_tasks(self, run_id: str) -> list[dict[str, Any]]:
        """Return every ``tasks`` row for a run."""
        ...

    async def get_cost_breakdown(self, run_id: str) -> dict[str, float]:
        """Return ``{component: sum_cost_usd}`` for non-local calls."""
        ...

    async def get_total_cost(self, run_id: str) -> float:
        """Return the USD total for a run, excluding ``is_local=1`` rows."""
        ...

    async def list_llm_calls(self, run_id: str) -> list[dict[str, Any]]:
        """Return every ``llm_calls`` row for a run, oldest-first."""
        ...

    async def get_gate_state(
        self, run_id: str, gate_id: str
    ) -> dict[str, Any] | None:
        """Return the ``human_gate_states`` row, or ``None`` when unseen."""
        ...

    async def update_gate_state(
        self,
        run_id: str,
        gate_id: str,
        status: str,
        decision: str | None = None,
    ) -> None:
        """Upsert a ``human_gate_states`` row."""
        ...


def _default_migrations_dir() -> Path:
    """Return the repo-root ``migrations/`` directory.

    The package is run from source during M1; P-21 (shipping migrations as
    package data via ``importlib.resources``) is still open. Tests override
    this via the ``migrations_dir`` kwarg on :meth:`SQLiteStorage.__init__`.
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

    Use :meth:`open` as the async factory — it builds the instance, applies
    migrations, and flips WAL in a single awaitable. The raw constructor is
    kept sync so tests that only need a path (e.g. the protocol-conformance
    check) can skip the async hop.

    Example
    -------
    >>> storage = await SQLiteStorage.open("~/.ai-workflows/runs.db")
    >>> await storage.create_run(
    ...     run_id="r1",
    ...     workflow_id="wf",
    ...     workflow_dir_hash="abc123...",
    ...     budget_cap_usd=5.0,
    ... )
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
        # Serialises every write so concurrent ``log_llm_call`` invocations
        # never collide on the WAL writer. Reads are unguarded.
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
        # Imported lazily so the primitives layer stays importable in
        # environments where yoyo is not yet installed (e.g. doc builds).
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
        workflow_dir_hash: str,
        budget_cap_usd: float | None,
    ) -> None:
        """Insert a new ``runs`` row.

        ``workflow_dir_hash`` must be a non-empty string — ``None`` or ``""``
        raises :class:`ValueError` before hitting the DB so callers see the
        Python-level error message (the SQLite ``NOT NULL`` would otherwise
        surface as an ``IntegrityError``).
        """
        if workflow_dir_hash is None or workflow_dir_hash == "":
            raise ValueError("workflow_dir_hash is required and must be non-empty")
        await self._run_write(
            self._create_run_sync,
            run_id,
            workflow_id,
            workflow_dir_hash,
            budget_cap_usd,
        )

    def _create_run_sync(
        self,
        run_id: str,
        workflow_id: str,
        workflow_dir_hash: str,
        budget_cap_usd: float | None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, workflow_id, workflow_dir_hash, status,
                    started_at, budget_cap_usd
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    workflow_id,
                    workflow_dir_hash,
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
        total_cost_usd: float | None = None,
    ) -> None:
        """Update the run status; populate ``finished_at`` on terminal states."""
        await self._run_write(self._update_run_status_sync, run_id, status, total_cost_usd)

    def _update_run_status_sync(
        self,
        run_id: str,
        status: str,
        total_cost_usd: float | None,
    ) -> None:
        finished_at = _utcnow() if status in {"completed", "failed"} else None
        with self._connect() as conn:
            if total_cost_usd is not None and finished_at is not None:
                conn.execute(
                    "UPDATE runs SET status = ?, total_cost_usd = ?, finished_at = ? "
                    "WHERE run_id = ?",
                    (status, total_cost_usd, finished_at, run_id),
                )
            elif total_cost_usd is not None:
                conn.execute(
                    "UPDATE runs SET status = ?, total_cost_usd = ? WHERE run_id = ?",
                    (status, total_cost_usd, run_id),
                )
            elif finished_at is not None:
                conn.execute(
                    "UPDATE runs SET status = ?, finished_at = ? WHERE run_id = ?",
                    (status, finished_at, run_id),
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

    async def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent runs, newest first (ordered by ``started_at``)."""
        return await asyncio.to_thread(self._list_runs_sync, limit)

    def _list_runs_sync(self, limit: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            )
            return [_row_to_dict(cursor, row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    async def upsert_task(
        self,
        run_id: str,
        task_id: str,
        component: str,
        status: str,
        **kwargs: Any,
    ) -> None:
        """Insert or update a ``(task_id, run_id)`` row.

        Accepted kwargs: ``started_at``, ``finished_at``, ``failure_reason``.
        Unknown kwargs raise :class:`TypeError` rather than silently being
        dropped — a typo in a caller should fail loudly.
        """
        allowed = {"started_at", "finished_at", "failure_reason"}
        unknown = set(kwargs) - allowed
        if unknown:
            raise TypeError(f"upsert_task got unexpected kwargs: {sorted(unknown)}")
        await self._run_write(
            self._upsert_task_sync,
            run_id,
            task_id,
            component,
            status,
            kwargs,
        )

    def _upsert_task_sync(
        self,
        run_id: str,
        task_id: str,
        component: str,
        status: str,
        extra: dict[str, Any],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks (task_id, run_id, component, status,
                                   started_at, finished_at, failure_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id, run_id) DO UPDATE SET
                    component      = excluded.component,
                    status         = excluded.status,
                    started_at     = COALESCE(excluded.started_at,     tasks.started_at),
                    finished_at    = COALESCE(excluded.finished_at,    tasks.finished_at),
                    failure_reason = COALESCE(excluded.failure_reason, tasks.failure_reason)
                """,
                (
                    task_id,
                    run_id,
                    component,
                    status,
                    extra.get("started_at"),
                    extra.get("finished_at"),
                    extra.get("failure_reason"),
                ),
            )
            conn.commit()

    async def get_tasks(self, run_id: str) -> list[dict[str, Any]]:
        """Return every task row for a run, ordered by insertion."""
        return await asyncio.to_thread(self._get_tasks_sync, run_id)

    def _get_tasks_sync(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM tasks WHERE run_id = ? ORDER BY rowid",
                (run_id,),
            )
            return [_row_to_dict(cursor, row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # LLM calls
    # ------------------------------------------------------------------

    _LLM_COLUMNS = (
        "task_id",
        "workflow_id",
        "component",
        "tier",
        "model",
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
        "cost_usd",
        "is_local",
        "is_escalation",
        "stop_reason",
        "called_at",
    )

    async def log_llm_call(self, run_id: str, **fields: Any) -> None:
        """Append one ``llm_calls`` row.

        Accepts any subset of the documented columns as kwargs; unknown
        kwargs raise :class:`TypeError`. ``called_at`` defaults to now;
        ``is_local`` and ``is_escalation`` coerce ``bool`` → 0/1 so callers
        can pass Python booleans without thinking about SQLite's TEXT-vs-INT
        quirks.
        """
        unknown = set(fields) - set(self._LLM_COLUMNS)
        if unknown:
            raise TypeError(f"log_llm_call got unexpected kwargs: {sorted(unknown)}")
        fields.setdefault("called_at", _utcnow())
        if "is_local" in fields:
            fields["is_local"] = int(bool(fields["is_local"]))
        if "is_escalation" in fields:
            fields["is_escalation"] = int(bool(fields["is_escalation"]))
        await self._run_write(self._log_llm_call_sync, run_id, fields)

    def _log_llm_call_sync(self, run_id: str, fields: dict[str, Any]) -> None:
        columns = ["run_id", *self._LLM_COLUMNS]
        values = [run_id, *[fields.get(col) for col in self._LLM_COLUMNS]]
        placeholders = ",".join("?" * len(columns))
        with self._connect() as conn:
            conn.execute(
                f"INSERT INTO llm_calls ({','.join(columns)}) VALUES ({placeholders})",
                values,
            )
            conn.commit()

    async def get_cost_breakdown(self, run_id: str) -> dict[str, float]:
        """Return ``{component: sum(cost_usd)}`` excluding local rows.

        Used by the Task 09 CostTracker for budget-cap enforcement and by
        Task 12 ``aiw inspect`` for the per-component breakdown.
        """
        return await asyncio.to_thread(self._get_cost_breakdown_sync, run_id)

    def _get_cost_breakdown_sync(self, run_id: str) -> dict[str, float]:
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT component, COALESCE(SUM(cost_usd), 0.0) AS total "
                "FROM llm_calls WHERE run_id = ? AND is_local = 0 "
                "GROUP BY component",
                (run_id,),
            )
            return {row["component"]: float(row["total"]) for row in cursor.fetchall()}

    async def get_total_cost(self, run_id: str) -> float:
        """Return the sum of ``cost_usd`` for this run, excluding local calls.

        CRIT-03: paired with ``runs.budget_cap_usd``, Task 09 uses this to
        short-circuit before making a call that would cross the cap.
        """
        return await asyncio.to_thread(self._get_total_cost_sync, run_id)

    def _get_total_cost_sync(self, run_id: str) -> float:
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0.0) FROM llm_calls "
                "WHERE run_id = ? AND is_local = 0",
                (run_id,),
            )
            (total,) = cursor.fetchone()
            return float(total)

    async def list_llm_calls(self, run_id: str) -> list[dict[str, Any]]:
        """Return every ``llm_calls`` row for a run, oldest-first.

        Used by Task 12 ``aiw inspect`` to render the per-call usage table
        (including ``cache_read_tokens`` / ``cache_write_tokens`` — see
        carry-over ``M1-T04-ISS-01``) and the total call count.
        """
        return await asyncio.to_thread(self._list_llm_calls_sync, run_id)

    def _list_llm_calls_sync(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM llm_calls WHERE run_id = ? ORDER BY id",
                (run_id,),
            )
            return [_row_to_dict(cursor, row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Artifacts
    # ------------------------------------------------------------------

    async def log_artifact(
        self,
        run_id: str,
        artifact_type: str,
        file_path: str,
        task_id: str | None = None,
    ) -> None:
        """Append one row to ``artifacts``."""
        await self._run_write(
            self._log_artifact_sync, run_id, artifact_type, file_path, task_id
        )

    def _log_artifact_sync(
        self,
        run_id: str,
        artifact_type: str,
        file_path: str,
        task_id: str | None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO artifacts (run_id, task_id, artifact_type, file_path, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (run_id, task_id, artifact_type, file_path, _utcnow()),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Human gates
    # ------------------------------------------------------------------

    async def get_gate_state(
        self, run_id: str, gate_id: str
    ) -> dict[str, Any] | None:
        """Return the ``human_gate_states`` row, or ``None`` when unseen."""
        return await asyncio.to_thread(self._get_gate_state_sync, run_id, gate_id)

    def _get_gate_state_sync(
        self, run_id: str, gate_id: str
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM human_gate_states WHERE run_id = ? AND gate_id = ?",
                (run_id, gate_id),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return _row_to_dict(cursor, row)

    async def update_gate_state(
        self,
        run_id: str,
        gate_id: str,
        status: str,
        decision: str | None = None,
    ) -> None:
        """Upsert a ``human_gate_states`` row.

        ``rendered_at`` is set the first time the gate is written;
        ``resolved_at`` is set whenever ``status`` reaches a terminal state
        (``approved``, ``rejected``). Existing timestamps are preserved by
        ``COALESCE`` so a second write doesn't overwrite the first rendering.
        """
        await self._run_write(
            self._update_gate_state_sync, run_id, gate_id, status, decision
        )

    def _update_gate_state_sync(
        self,
        run_id: str,
        gate_id: str,
        status: str,
        decision: str | None,
    ) -> None:
        now = _utcnow()
        resolved_at = now if status in {"approved", "rejected"} else None
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO human_gate_states (
                    run_id, gate_id, status, rendered_at, resolved_at, decision
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, gate_id) DO UPDATE SET
                    status      = excluded.status,
                    rendered_at = COALESCE(human_gate_states.rendered_at, excluded.rendered_at),
                    resolved_at = COALESCE(excluded.resolved_at, human_gate_states.resolved_at),
                    decision    = COALESCE(excluded.decision,    human_gate_states.decision)
                """,
                (run_id, gate_id, status, now, resolved_at, decision),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Write-path lock helper
    # ------------------------------------------------------------------

    async def _run_write(self, fn: Any, *args: Any) -> None:
        """Run a blocking write under the asyncio lock + a worker thread."""
        async with self._write_lock:
            await asyncio.to_thread(fn, *args)
