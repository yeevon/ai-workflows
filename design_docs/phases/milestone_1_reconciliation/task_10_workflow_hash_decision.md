# Task 10 — `workflow_hash` Decision + ADR

**Status:** 📝 Planned.

## What to Build

Decide whether `ai_workflows/primitives/workflow_hash.py` still carries weight under LangGraph's checkpoint-driven resume model (KDR-009). Document the decision as an ADR under `design_docs/adr/` regardless of outcome.

## Background

Pre-pivot, `workflow_hash` fingerprinted the workflow directory so `aiw resume` could refuse to resume against a mutated workflow definition. Under the new architecture, LangGraph's checkpoint keys encode graph-instance identity, and the graph is constructed in-process from the workflow module — a directory-level content hash may or may not still add value.

## Deliverables

### One of:

**Option A — Keep.** The helper stays. The ADR explains:

- The resume-safety hole LangGraph's checkpoint key does *not* close (e.g. pure-Python graph module edits between checkpoint and resume).
- Where the hash is consumed (M3+ task pointer).
- Cost: negligible; it is a pure stdlib hash.

**Option B — Remove.** Delete the module and its tests. The ADR explains:

- LangGraph's checkpoint schema is deemed sufficient.
- The M3 resume path will rely on LangGraph's built-in guards.

### ADR file

`design_docs/adr/0001_workflow_hash.md` with sections: Context, Decision, Consequences, References (KDR-009, architecture §4.1, this task).

## Acceptance Criteria

- [ ] ADR exists and states the outcome unambiguously.
- [ ] If Option B: `ai_workflows/primitives/workflow_hash.py` and its test file are deleted, and the module is removed from any `__init__.py` re-exports.
- [ ] If Option A: a one-line docstring links to the ADR; no behaviour change.
- [ ] `uv run pytest` green.

## Dependencies

- [Task 05](task_05_trim_storage.md) — `Storage` no longer carries `workflow_dir_hash` in `runs` table; the decision here determines whether we reintroduce it elsewhere or drop it outright.
