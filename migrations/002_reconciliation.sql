-- Reconciliation migration for M1 Task 05.
--
-- Produced by M1 Task 05 (trim Storage to run registry + gate log) per
-- KDR-009 and design_docs/architecture.md §4.1: LangGraph's `SqliteSaver`
-- owns every checkpoint blob, so the pre-pivot `tasks` / `artifacts` /
-- `llm_calls` / `human_gate_states` tables are dropped here. The
-- `workflow_dir_hash` and `profile` columns on `runs` are dropped with
-- them; `workflow_dir_hash`'s fate is decided by ADR-0001 under M1 Task 10
-- (see pre-build amendment AUD-05-01 in
-- design_docs/phases/milestone_1_reconciliation/issues/task_05_issue.md).
--
-- The `gate_responses` table replaces the pre-pivot `human_gate_states`
-- shape so the gate log carries prompt, response, strict_review, and a
-- single `responded_at` timestamp that is stamped on reply instead of
-- split across `rendered_at` / `resolved_at`.
--
-- SQLite >= 3.35 is required for `ALTER TABLE ... DROP COLUMN`; the
-- project's minimum Python is 3.13 which bundles SQLite 3.45+.

DROP TABLE IF EXISTS human_gate_states;

DROP TABLE IF EXISTS artifacts;

DROP TABLE IF EXISTS llm_calls;

DROP TABLE IF EXISTS tasks;

ALTER TABLE runs DROP COLUMN profile;

ALTER TABLE runs DROP COLUMN workflow_dir_hash;

CREATE TABLE gate_responses (
    run_id TEXT NOT NULL,
    gate_id TEXT NOT NULL,
    prompt TEXT NOT NULL,
    response TEXT,
    responded_at TEXT,
    strict_review INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (run_id, gate_id)
);
