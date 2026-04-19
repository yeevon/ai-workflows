# Task 05 — Trim Storage to Run Registry + Gate Log — Pre-build Audit Amendments

**Source task:** [../task_05_trim_storage.md](../task_05_trim_storage.md)
**Source audit:** [../audit.md](../audit.md) (produced by [M1 Task 01](../task_01_reconciliation_audit.md))
**Created on:** 2026-04-19
**Status:** 📋 PENDING BUILDER — gates not yet run; this file encodes pre-build amendments only.

## Why this file exists

Task files `task_02`…`task_13` were drafted **before** the reconciliation audit ran. Per [CLAUDE.md](../../../../CLAUDE.md) Builder conventions, this file is the bridge to the [audit.md](../audit.md) source of truth.

## Required reading order for Builder

1. [../../../architecture.md](../../../architecture.md) — especially KDR-009 / §4.1.
2. [../audit.md](../audit.md) — authoritative source. Rows targeting `task 05` apply here.
3. [../task_05_trim_storage.md](../task_05_trim_storage.md) — deliverables + ACs.
4. This file — amendments.
5. If audit and task disagree, **raise the conflict before implementing** per CLAUDE.md Builder conventions.

## Rows from audit.md this task must execute

### MODIFY

| Path | Reason |
| --- | --- |
| `ai_workflows/primitives/storage.py` | Shrink to run registry + gate log only; all checkpoint-adjacent methods move to LangGraph `SqliteSaver` per KDR-009. |
| `migrations/001_initial.sql` | Declares `tasks`, `artifacts`, `llm_calls`, `human_gate_states`, `workflow_dir_hash` — all pre-pivot scaffolding dropped or replaced. Survives only as history; the reshape lands as a new migration. |
| `migrations/001_initial.rollback.sql` | Same lifecycle as `001_initial.sql`. |
| `tests/primitives/test_storage.py` | Rewrite around the trimmed protocol; add idempotent-migration assertion. |

### ADD

| Path | Reason |
| --- | --- |
| `migrations/00N_reconciliation.sql` (N chosen to follow the highest existing) | Drops the pre-pivot checkpoint columns/tables and ensures the `gate_responses` table exists per task 05 deliverable (KDR-009). |
| `migrations/00N_reconciliation.rollback.sql` | Matching `down` path. |

## Known amendments vs. task spec

- **Aligned.** Task spec already cites KDR-009 and the trimmed protocol is consistent with [architecture.md §4.1](../../../architecture.md).

### 🟢 LOW — AUD-05-01: `workflow_dir_hash` column fate cross-references task 10

**Task spec** §"Schema changes" leaves `runs` with `budget_cap_usd`, `total_cost_usd`, `started_at`, `finished_at`, `status`, `workflow_id`, `run_id` — dropping `workflow_dir_hash`, `profile`.

**Audit** §6 "Deferred items confirmed out of scope" calls out that the `workflow_dir_hash` column's reintroduction (or final removal) depends on [task 10](../task_10_workflow_hash_decision.md)'s ADR outcome.

**Resolution.** Drop the column as part of this task's migration. If task 10's ADR opts for Option A (keep the hash), task 10 owns the migration that re-adds it — not this one. No deviation from the task spec; this is a pointer to prevent accidental recoupling at Builder time.

## Carry-over from prior audits

_None._

## Propagation status

Post-build audit will overwrite this file with implementation findings.
