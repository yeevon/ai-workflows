-- Rollback for 003_artifacts.sql — drops the M3 `artifacts` table so the
-- DB returns to its 002_reconciliation shape (run registry + gate log).

DROP TABLE artifacts;
