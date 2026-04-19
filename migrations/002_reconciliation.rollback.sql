-- Rollback for 002_reconciliation.sql. yoyo-migrations reverses the
-- statement order automatically, so we list the operations in the same
-- logical order as the forward migration — yoyo executes them bottom-up.
--
-- Restores the pre-reconciliation schema: re-creates `tasks`,
-- `artifacts`, `llm_calls`, `human_gate_states` and the two matching
-- indexes, re-adds the dropped `runs` columns (`profile`,
-- `workflow_dir_hash`), and drops the new `gate_responses` table.
--
-- Matches the M1 Task 05 AC: "`down` migration rolls the schema back to
-- the pre-reconciliation state."

DROP TABLE gate_responses;

ALTER TABLE runs ADD COLUMN workflow_dir_hash TEXT;

ALTER TABLE runs ADD COLUMN profile TEXT;

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
