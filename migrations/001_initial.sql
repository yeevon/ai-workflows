-- Initial schema for the ai-workflows run log.
--
-- Produced by M1 Task 08 (replaces the Task 01 bootstrap placeholder).
-- yoyo-migrations records application state in the auto-managed
-- `_yoyo_migration` table. Companion rollback statements live in
-- `001_initial.rollback.sql`.
--
-- Tables
-- ------
-- runs              One row per `aiw run` invocation. `workflow_dir_hash`
--                   (CRIT-02) is the SHA-256 digest of the workflow
--                   directory at run start — Task 12 `aiw resume` refuses
--                   to resume when the current directory's hash differs.
-- tasks             One row per `(task_id, run_id)` pair. Composite PK
--                   prevents two runs from colliding on shared task ids.
-- llm_calls         One row per LLM call — Task 09 writes these; Task 11's
--                   inspect command reads them. `is_escalation` tags retry
--                   escalations (C-21); `is_local` excludes the row from
--                   cost aggregations.
-- artifacts         File paths of intermediate outputs written to
--                   `~/.ai-workflows/runs/<run_id>/`.
-- human_gate_states One row per `(run_id, gate_id)` HumanGate state row.
--                   Resume reads this table to skip already-decided gates.

CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    workflow_dir_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    profile TEXT,
    total_cost_usd REAL DEFAULT 0.0,
    budget_cap_usd REAL
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
    is_escalation INTEGER DEFAULT 0,
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
