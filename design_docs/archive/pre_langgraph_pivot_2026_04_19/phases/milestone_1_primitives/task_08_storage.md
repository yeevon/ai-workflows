# Task 08 — Storage Layer

**Status:** ✅ Complete (2026-04-19) — see [issues/task_08_issue.md](issues/task_08_issue.md).

**Issues:** P-26, P-28, P-29, P-30, P-31, CRIT-02, CRIT-10 (revises P-27)

## What to Build

SQLite-backed run log with WAL mode. `yoyo-migrations` for schema evolution (replaces manual SQL). Adds `workflow_dir_hash` column for resume safety. Defines `StorageBackend` protocol for future cloud backends.

## Deliverables

### `migrations/001_initial.sql` (yoyo-migrations format)

```sql
-- yoyo
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    workflow_dir_hash TEXT NOT NULL,     -- CRIT-02: content hash at run start
    status TEXT NOT NULL,                 -- pending | running | completed | failed
    started_at TEXT NOT NULL,
    finished_at TEXT,
    profile TEXT,
    total_cost_usd REAL DEFAULT 0.0,
    budget_cap_usd REAL                   -- CRIT-03: max_run_cost_usd from workflow config
);

CREATE TABLE tasks (
    task_id TEXT NOT NULL,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    component TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    failure_reason TEXT,
    PRIMARY KEY (task_id, run_id)
);

CREATE TABLE llm_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    task_id TEXT,
    workflow_id TEXT NOT NULL,
    component TEXT NOT NULL,
    tier TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cache_read_tokens INTEGER DEFAULT 0,
    cache_write_tokens INTEGER DEFAULT 0,
    cost_usd REAL,
    is_local INTEGER DEFAULT 0,
    is_escalation INTEGER DEFAULT 0,     -- C-21: tag escalation retries
    stop_reason TEXT,
    called_at TEXT NOT NULL
);

CREATE TABLE artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    task_id TEXT,
    artifact_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE human_gate_states (
    run_id TEXT NOT NULL,
    gate_id TEXT NOT NULL,
    status TEXT NOT NULL,
    rendered_at TEXT,
    resolved_at TEXT,
    decision TEXT,
    PRIMARY KEY (run_id, gate_id)
);

CREATE INDEX idx_llm_calls_run ON llm_calls(run_id);
CREATE INDEX idx_tasks_run_status ON tasks(run_id, status);
```

### `primitives/storage.py`

```python
class StorageBackend(Protocol):
    async def create_run(self, run_id: str, workflow_id: str, workflow_dir_hash: str, budget_cap_usd: float | None) -> None: ...
    async def update_run_status(self, run_id: str, status: str, total_cost_usd: float | None = None) -> None: ...
    async def upsert_task(self, run_id: str, task_id: str, component: str, status: str, **kwargs) -> None: ...
    async def log_llm_call(self, run_id: str, **fields) -> None: ...
    async def log_artifact(self, run_id: str, artifact_type: str, file_path: str, task_id: str | None = None) -> None: ...
    async def get_run(self, run_id: str) -> dict | None: ...
    async def list_runs(self, limit: int = 50) -> list[dict]: ...
    async def get_tasks(self, run_id: str) -> list[dict]: ...
    async def get_cost_breakdown(self, run_id: str) -> dict[str, float]: ...  # by component
    async def get_total_cost(self, run_id: str) -> float: ...  # excludes local
    async def get_gate_state(self, run_id: str, gate_id: str) -> dict | None: ...
    async def update_gate_state(self, run_id: str, gate_id: str, status: str, decision: str | None = None) -> None: ...


class SQLiteStorage:  # implements StorageBackend
    def __init__(self, db_path: str): ...

    async def _apply_migrations(self) -> None:
        """Run yoyo-migrations against the DB at startup."""

    async def _enable_wal(self) -> None:
        """PRAGMA journal_mode = WAL."""
```

### `yoyo-migrations` Integration

On `SQLiteStorage.__init__()`:
1. Open DB connection
2. `PRAGMA journal_mode = WAL`
3. Apply pending migrations via yoyo:

```python
from yoyo import read_migrations, get_backend
backend = get_backend(f"sqlite:///{db_path}")
migrations = read_migrations("migrations/")
with backend.lock():
    backend.apply_migrations(backend.to_apply(migrations))
```

This gives you:
- `_yoyo_migration` version table (created automatically)
- Rollback paths for each migration
- Up and down scripts supported
- No manual version tracking

## Acceptance Criteria

- [x] `SQLiteStorage` passes `isinstance(storage, StorageBackend)` structural check
- [x] First open applies `001_initial.sql`, second open does nothing (yoyo deduplicates)
- [x] WAL mode confirmed via `PRAGMA journal_mode` query
- [x] `create_run()` requires `workflow_dir_hash` — no null allowed
- [x] `get_total_cost()` excludes rows where `is_local=1`
- [x] Migration rollback works (test by creating 002, rolling back, confirming schema reverts)
- [x] Concurrent writes via `asyncio.gather` of 20 `log_llm_call()` calls succeed

## Dependencies

- Task 01 (migrations dir exists)
