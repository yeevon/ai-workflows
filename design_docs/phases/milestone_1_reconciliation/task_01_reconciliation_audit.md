# Task 01 — Reconciliation Audit

**Status:** ✅ Landed (2026-04-19). Deliverable: [audit.md](audit.md).

## What to Build

A single audit document that lists every file in `ai_workflows/` and every entry in `pyproject.toml`, tagged **KEEP**, **MODIFY**, or **REMOVE**, each with a one-line reason citing the relevant KDR or [architecture.md](../../architecture.md) section. This document is the plan the remaining M1 tasks execute — every later task consumes at least one row from it.

No code changes in this task.

## Deliverables

### `design_docs/phases/milestone_1_reconciliation/audit.md`

Required sections:

1. **File audit (`ai_workflows/`)** — table columns: `Path | Verdict | Reason | Target task`.
   Walk every `.py` file (and `tiers.yaml`, `pricing.yaml`, `migrations/*.sql` if present).
2. **Dependency audit (`pyproject.toml`)** — table columns: `Dependency | Verdict | Reason | Target task`.
   Cover `[project].dependencies`, `[project.optional-dependencies]`, and `[dependency-groups].dev`.
3. **Test audit (`tests/`)** — same columns. Tests coupled to deleted modules are REMOVE; tests coupled to modified modules are MODIFY.
4. **Migration audit (`migrations/`)** — existing yoyo migrations reviewed; new migration needed for [task 05](task_05_trim_storage.md) called out.
5. **Cross-references** — each `Target task` column points at an existing `task_NN_*.md` in this directory.

## Acceptance Criteria

- [x] Every `.py` file under `ai_workflows/` appears in the file-audit table. _(verified 2026-04-19 cycle 6 — 23 glob entries == 23 rows in audit.md §1.)_
- [x] Every dependency line in `pyproject.toml` appears in the dependency-audit table. _(verified 2026-04-19 cycle 6 — 11 runtime + 1 optional + 5 dev == 17 rows in audit.md §2.)_
- [x] Every KEEP row cites either a KDR or an architecture.md section. _(verified 2026-04-19 cycle 6 — 14/14 rows; typer row citation is weak but literal-passes, tracked as ISS-04 LOW.)_
- [x] Every MODIFY / REMOVE row cites the M1 task that will execute it. _(verified 2026-04-19 cycle 6 — 21 MODIFY + 16 REMOVE, all with `task_NN` links.)_
- [x] No row has a blank `Target task` column except for pure-KEEP items with no follow-on work. _(verified 2026-04-19 cycle 6 — dashes only appear on pure-KEEP rows.)_
- [x] `logfire` specifically has a verdict (it is the load-bearing question for [task 02](task_02_dependency_swap.md)). _(verified 2026-04-19 cycle 6 — logfire>=2.0 → REMOVE → task 02.)_

## Dependencies

- None. This task is the M1 critical-path head.
