# Task 01 — Reconciliation Audit

**Status:** 📝 Planned.

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

- [ ] Every `.py` file under `ai_workflows/` appears in the file-audit table.
- [ ] Every dependency line in `pyproject.toml` appears in the dependency-audit table.
- [ ] Every KEEP row cites either a KDR or an architecture.md section.
- [ ] Every MODIFY / REMOVE row cites the M1 task that will execute it.
- [ ] No row has a blank `Target task` column except for pure-KEEP items with no follow-on work.
- [ ] `logfire` specifically has a verdict (it is the load-bearing question for [task 02](task_02_dependency_swap.md)).

## Dependencies

- None. This task is the M1 critical-path head.
