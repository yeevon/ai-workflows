-- Artifacts table for M3 Task 03 (first workflow — `planner`).
--
-- The pre-pivot `artifacts` table was dropped by 002_reconciliation.sql
-- alongside the rest of the checkpoint-adjacent surface (tasks, llm_calls,
-- human_gate_states) per KDR-009. M3 Task 03 reintroduces a narrower
-- artifacts surface: a `(run_id, kind)`-keyed JSON-payload row that the
-- `planner` workflow's terminal `_artifact_node` writes after the
-- HumanGate has cleared. This is NOT a re-hydration of the pre-pivot
-- `file_path`-indexed artifacts shape — it only persists workflow output
-- payloads so the MCP surface (M4) can read them back by
-- `(run_id, kind)`. Checkpoint state still belongs to LangGraph's
-- SqliteSaver (KDR-009); this table is strictly post-gate output.

CREATE TABLE artifacts (
    run_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (run_id, kind)
);
