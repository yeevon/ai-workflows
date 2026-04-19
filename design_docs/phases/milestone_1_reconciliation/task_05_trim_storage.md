# Task 05 — Trim Storage to Run Registry + Gate Log

**Status:** 📝 Planned.

## What to Build

Shrink `ai_workflows/primitives/storage.py` and its schema to only the responsibilities [architecture.md §4.1](../../architecture.md) assigns to `Storage`: the run registry and the gate-response log. Everything checkpoint-related is handed off to LangGraph's built-in `SqliteSaver` (KDR-009).

## Deliverables

### Schema changes

New yoyo migration `migrations/00N_reconciliation.sql` (N chosen to follow the highest existing) that:

- Drops columns or tables that existed only to support pre-pivot checkpoint semantics — the [task 01 audit](task_01_reconciliation_audit.md) names them exactly. Typical candidates: `tasks`, `artifacts`, `llm_calls` (the per-call ledger moves under `CostTracker`'s responsibility and is re-decided in [task 08](task_08_prune_cost_tracker.md)).
- Ensures a `gate_responses` table exists with at least `run_id`, `gate_id`, `prompt`, `response`, `responded_at`, `strict_review` (bool).
- Leaves `runs` with: `run_id`, `workflow_id`, `status`, `started_at`, `finished_at`, `budget_cap_usd`, `total_cost_usd`.

Provide a matching `down` migration (yoyo rollback path).

### Code changes

`ai_workflows/primitives/storage.py`:

- Protocol surface reduced to:
  - `create_run(run_id, workflow_id, budget_cap_usd) -> None`
  - `update_run_status(run_id, status, finished_at?, total_cost_usd?) -> None`
  - `get_run(run_id) -> dict | None`
  - `list_runs(limit=50, filter?) -> list[dict]`
  - `record_gate(run_id, gate_id, prompt, strict_review) -> None`
  - `record_gate_response(run_id, gate_id, response) -> None`
  - `get_gate(run_id, gate_id) -> dict | None`
- All checkpoint-adjacent methods deleted (`upsert_task`, `log_llm_call`, `log_artifact`, `get_tasks`, etc.).

### Test updates

`tests/primitives/test_storage.py`:

- Remove assertions covering dropped tables/methods.
- Add assertions covering gate-log read/write round-trip.
- Add assertion that migrations apply idempotently on a fresh DB.

## Acceptance Criteria

- [ ] New migration applies on a fresh DB and is idempotent on reapply.
- [ ] `down` migration rolls the schema back to the pre-reconciliation state.
- [ ] `Storage` protocol contains only the methods listed above.
- [ ] `uv run pytest tests/primitives/test_storage.py` green.
- [ ] `uv run pytest` green overall.
- [ ] `grep -r "log_llm_call\|upsert_task\|log_artifact" ai_workflows/ tests/` returns zero matches (or only matches inside the migration SQL).

## Dependencies

- [Task 03](task_03_remove_llm_substrate.md) — `log_llm_call` consumers removed upstream.
- Coordinate with [Task 08](task_08_prune_cost_tracker.md): if `CostTracker` keeps an in-process per-call ledger, it may add its own table here in a follow-on migration. Scope boundary: M1.05 drops the legacy table; M1.08 adds a replacement only if required by [architecture.md §4.1](../../architecture.md).
