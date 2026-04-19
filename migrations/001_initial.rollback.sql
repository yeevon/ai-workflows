-- Rollback for 001_initial.sql. yoyo-migrations reverses the statement
-- order automatically, so we list the drops in the same logical order as
-- the creates — yoyo will execute them bottom-up.

DROP INDEX idx_tasks_run_status;

DROP INDEX idx_llm_calls_run;

DROP TABLE human_gate_states;

DROP TABLE artifacts;

DROP TABLE llm_calls;

DROP TABLE tasks;

DROP TABLE runs;
