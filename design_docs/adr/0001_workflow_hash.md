# ADR-0001 — Retire `compute_workflow_hash`

**Status:** Accepted (2026-04-19).
**Decision owner:** [M1 Task 10](../phases/milestone_1_reconciliation/task_10_workflow_hash_decision.md).
**References:** [architecture.md §4.1](../architecture.md) · [architecture.md §4.3](../architecture.md) · KDR-005 · KDR-009.
**Supersedes:** pre-pivot CRIT-02 (`ai_workflows/primitives/workflow_hash.py`).

## Context

Pre-pivot, `ai_workflows/primitives/workflow_hash.py` fingerprinted a
workflow *directory* — `workflow.yaml` + `prompts/` + `schemas/` +
`custom_tools.py` — so `aiw resume <run_id>` could refuse to resume a
run whose workflow files had been edited after the checkpoint was
written. The hash was persisted as `runs.workflow_dir_hash` by the
pre-pivot `Storage` schema.

The LangGraph + MCP pivot changed two things that break the premise of
this primitive:

1. **Workflow shape.** Under the new architecture ([§4.3](../architecture.md)),
   a workflow is a *Python module* exporting a built LangGraph
   `StateGraph` (see `ai_workflows.workflows.*`). There is no
   YAML-directory layout to fingerprint. The primitive's file tree
   (`workflow.yaml`, `prompts/`, `schemas/`, `custom_tools.py`) does
   not exist in any real workflow under the new architecture.
2. **Checkpoint ownership.** Per KDR-009 and [§4.1](../architecture.md),
   LangGraph's `SqliteSaver` owns checkpoint persistence. `Storage`
   shrinks to the run registry + gate log, and
   [M1 Task 05](../phases/milestone_1_reconciliation/task_05_trim_storage.md)
   has already dropped `workflow_dir_hash` from the `runs` table
   (migration `002_reconciliation.sql`).

LangGraph's checkpoint key (`thread_id`) encodes *graph-instance
identity*, not source-code identity — so a source-code drift guard is
**not** automatically covered by `SqliteSaver`. A developer who edits
`ai_workflows/workflows/planner.py` between `aiw run` and `aiw resume`
will, in principle, resume against a checkpoint that was written by the
old code. That gap is real. But the shape of a primitive that could
close it for module-based workflows is fundamentally different from the
directory-hashing helper we have today — a future guard would need to
hash Python sources in the import graph, or the resolved `StateGraph`
schema, or the tier config, or some combination — and that design
belongs with M3, when `aiw resume` actually lands, against the real
workflow layout that exists then.

## Decision

**Option B — Remove.** Delete:

- `ai_workflows/primitives/workflow_hash.py`
- `tests/primitives/test_workflow_hash.py`
- The `compute_workflow_hash` import and its consumers in
  `ai_workflows/cli.py` (minimum incision — the broader CLI stub-down
  is owned by [M1 Task 11](../phases/milestone_1_reconciliation/task_11_cli_stub_down.md)).
- The `workflow_hash` reference in
  `ai_workflows/primitives/__init__.py` and
  `ai_workflows/workflows/__init__.py` docstrings.

No migration is added to re-introduce the `workflow_dir_hash` column;
[M1 Task 05](../phases/milestone_1_reconciliation/task_05_trim_storage.md)'s
removal stands.

## Rationale

- **Directory hashing does not fit module-based workflows.** The
  primitive's per-file walk (`workflow.yaml`, `prompts/`, `schemas/`,
  `custom_tools.py`) assumes a filesystem layout that the new
  architecture does not produce. Keeping a primitive whose contract
  does not match the code that would consume it is dead-on-arrival
  code, not a useful starting point.
- **The genuine resume-safety gap is better addressed in M3.** Source-
  code drift between run and resume is real; the right fix needs to
  hash Python sources (or the resolved graph), not YAML. M3 will design
  that primitive against the workflow layout that actually exists when
  `aiw resume` lands, not against the pre-pivot one.
- **Zero current consumer.** The stored hash column is already gone
  (T05). `aiw inspect --workflow-dir` reports "Dir hash" computed
  against a stored `None`, which is degenerate. Removing the entry
  point cleans the CLI signature without losing real behaviour.
- **Deferring is cheap to reverse.** Restoring a drift-detect primitive
  later is a straightforward addition (pure stdlib); prematurely
  keeping the wrong-shaped one is a maintenance debt.

## Consequences

- `from ai_workflows.primitives.workflow_hash import compute_workflow_hash`
  no longer resolves. Any remaining import is a red flag for review.
- `aiw inspect --workflow-dir <path>` is gone; `_render_dir_hash_line`
  and the "Dir hash" line in `_render_inspect` output are gone.
- `aiw resume` no longer mentions a workflow hash in its stub summary.
- The scaffolding tests `test_aiw_help_command` /
  `test_aiw_version_command` continue to pass because cli.py still
  imports cleanly.
- M3 gains an open design question: **does `aiw resume` need a
  source-code drift guard, and if so, against what?** This ADR records
  the question; it does not answer it.
- If M3 concludes the guard is needed, a new primitive —
  `graph_source_hash` or equivalent — lands as a fresh ADR, with
  scope matched to module-based workflows.

## References

- [architecture.md §4.1](../architecture.md) — primitives layer.
- [architecture.md §4.3](../architecture.md) — workflows as Python modules.
- KDR-005 — primitives layer preserved and owned (but owning means
  *reshaping* pre-pivot primitives that no longer fit, not preserving
  them unchanged).
- KDR-009 — LangGraph `SqliteSaver` owns checkpoints; `Storage` shrinks.
- [M1 Task 05](../phases/milestone_1_reconciliation/task_05_trim_storage.md) —
  dropped `workflow_dir_hash` from the `runs` table.
- [M1 Task 10](../phases/milestone_1_reconciliation/task_10_workflow_hash_decision.md) —
  this ADR's source task.
- [M1 Task 11](../phases/milestone_1_reconciliation/task_11_cli_stub_down.md) —
  completes the CLI stub-down that this ADR begins.
