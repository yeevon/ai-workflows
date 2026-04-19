# Task 10 — `workflow_hash` Decision + ADR — Pre-build Audit Amendments

**Source task:** [../task_10_workflow_hash_decision.md](../task_10_workflow_hash_decision.md)
**Source audit:** [../audit.md](../audit.md) (produced by [M1 Task 01](../task_01_reconciliation_audit.md))
**Created on:** 2026-04-19
**Status:** 📋 PENDING BUILDER — gates not yet run; this file encodes pre-build amendments only.

## Why this file exists

Task files `task_02`…`task_13` were drafted **before** the reconciliation audit ran. Per [CLAUDE.md](../../../../CLAUDE.md) Builder conventions, this file is the bridge to the [audit.md](../audit.md) source of truth.

## Required reading order for Builder

1. [../../../architecture.md](../../../architecture.md) — especially KDR-009 / §4.1.
2. [../audit.md](../audit.md) — authoritative source. Rows targeting `task 10` apply here.
3. [../task_10_workflow_hash_decision.md](../task_10_workflow_hash_decision.md) — deliverables + ACs.
4. This file — amendments.
5. If audit and task disagree, **raise the conflict before implementing** per CLAUDE.md Builder conventions.

## Rows from audit.md this task must execute

### DECIDE (Option A = Keep / Option B = Remove, via ADR-0001)

| Path | Audit verdict | Fate |
| --- | --- | --- |
| `ai_workflows/primitives/workflow_hash.py` | DECIDE | Kept as-is (A) or deleted (B) per ADR outcome. |
| `tests/primitives/test_workflow_hash.py` | DECIDE | Fate tied to the module — kept (A) or deleted (B). |

## Known amendments vs. task spec

- **Scope boundary with [task 05](../task_05_trim_storage.md).** Task 05's migration already drops the `workflow_dir_hash` column from the `runs` table. If this task's ADR picks **Option A (Keep)**, this task owns the migration that re-adds the column (or documents the alternative storage location). Do not amend [task_05](../task_05_trim_storage.md)'s migration — add a new `migrations/00N_workflow_hash_column.sql` owned by this task.
- **If Option B (Remove):**
  - Delete `ai_workflows/primitives/workflow_hash.py` AND `tests/primitives/test_workflow_hash.py`.
  - Ensure `ai_workflows/primitives/__init__.py` (already touched in [task 03](../task_03_remove_llm_substrate.md)) does not re-export `compute_workflow_hash`.
  - Remove any `from ai_workflows.primitives.workflow_hash import …` import in [`ai_workflows/cli.py`](../../../../ai_workflows/cli.py) (likely already gone after [task 11](../task_11_cli_stub_down.md) stub-down, but verify).
- **ADR location.** `design_docs/adr/0001_workflow_hash.md` (task spec already names this). The ADR must cite KDR-009 explicitly.

## Carry-over from prior audits

_None._

## Propagation status

Post-build audit will overwrite this file with implementation findings.
