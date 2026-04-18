-- Initial schema placeholder for ai-workflows.
--
-- The real schema (runs, tasks, gates, cost_events, etc.) lands in
-- M1 Task 08 (storage). yoyo-migrations records every applied migration in
-- the auto-managed `_yoyo_migration` table; this 001 file exists so that
-- `yoyo apply` has at least one migration to track from day one and the
-- migrations directory is not empty.
--
-- DO NOT add real DDL here — add a new numbered file (002, 003, …) so the
-- migration history stays linear and replayable.

-- A trivial table just so the migration is non-empty. Task 08 will drop or
-- replace it as part of the first real schema migration.
CREATE TABLE IF NOT EXISTS schema_bootstrap (
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
