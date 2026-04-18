# Task 12 — Storage Layer

**Issues:** P-26, P-27, P-28, P-29, P-30, P-31

## What to Build

SQLite-backed run log with WAL mode. Stores every LLM call, task state (for checkpoint/resume), and artifact file paths. Defines the `StorageBackend` protocol so a cloud backend can plug in later.

## Deliverables

### `primitives/storage.py`

**Schema (initial migration `migrations/001_initial.sql`):**

```sql
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    workflow_yaml TEXT NOT NULL,      -- snapshot of workflow.yaml
    status TEXT NOT NULL,             -- pending, running, completed, failed
    started_at TEXT NOT NULL,
    finished_at TEXT,
    profile TEXT
);

CREATE TABLE tasks (
    task_id TEXT NOT NULL,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    component TEXT NOT NULL,
    status TEXT NOT NULL,             -- pending, running, completed, failed, incomplete
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
    stop_reason TEXT,
    called_at TEXT NOT NULL
);

CREATE TABLE artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    task_id TEXT,
    artifact_type TEXT NOT NULL,      -- exploration_doc, plan, diff, review_decision
    file_path TEXT NOT NULL,          -- relative to run dir
    created_at TEXT NOT NULL
);

CREATE TABLE human_gate_states (
    run_id TEXT NOT NULL,
    gate_id TEXT NOT NULL,
    status TEXT NOT NULL,             -- pending_review, approved, rejected, timed_out
    rendered_at TEXT,
    resolved_at TEXT,
    decision TEXT,
    PRIMARY KEY (run_id, gate_id)
);
```

**`StorageBackend` protocol:**
```python
class StorageBackend(Protocol):
    async def create_run(self, run_id: str, workflow_id: str, ...) -> None: ...
    async def update_run_status(self, run_id: str, status: str) -> None: ...
    async def upsert_task(self, run_id: str, task_id: str, status: str, ...) -> None: ...
    async def log_llm_call(self, run_id: str, ...) -> None: ...
    async def log_artifact(self, run_id: str, artifact_type: str, file_path: str) -> None: ...
    async def get_run(self, run_id: str) -> dict | None: ...
    async def list_runs(self) -> list[dict]: ...
    async def get_tasks(self, run_id: str) -> list[dict]: ...
    async def get_gate_state(self, run_id: str, gate_id: str) -> dict | None: ...
    async def update_gate_state(self, run_id: str, gate_id: str, status: str, ...) -> None: ...
```

**`SQLiteStorage` implements `StorageBackend`:**
- Opens `~/.ai-workflows/runs.db` (or `AIWORKFLOWS_HOME/runs.db`)
- Enables WAL mode: `PRAGMA journal_mode=WAL`
- Runs pending migrations from `migrations/` on first open
- Creates run artifact directory `~/.ai-workflows/runs/<run_id>/` on `create_run()`

## Acceptance Criteria

- [ ] `SQLiteStorage` passes `isinstance(storage, StorageBackend)` structural check
- [ ] WAL mode confirmed via `PRAGMA journal_mode` query in tests
- [ ] `upsert_task()` is idempotent — calling twice with same status doesn't error
- [ ] `list_runs()` returns runs sorted by `started_at` descending
- [ ] Run artifact directory created at `create_run()`
- [ ] Concurrent async writes don't deadlock (test with `asyncio.gather` of 10 writes)

## Dependencies

- Task 01 (scaffolding — migrations dir)
- Task 15 (logging)
