# Task 01 — Slice-Discovery Phase

**Status:** 📝 Planned.

## What to Build

Stand up `ai_workflows.workflows.slice_refactor` as a new LangGraph `StateGraph` module and wire its first phase: compose the `planner` workflow as a sub-graph so `slice_refactor` starts with `START → planner_subgraph → slice_list_normalize`. The planner already returns a validated `PlannerPlan` with `steps: list[PlannerStep]` — T01 normalizes those steps into the `slice_list` state key that T02's fan-out will consume. No new LLM call; this is topology + state plumbing only.

The planner sub-graph includes its own plan-review `HumanGate`. That gate must propagate cleanly through the sub-graph boundary — a resume of a `slice_refactor` run paused at the planner's gate must clear that gate and then continue into `slice_refactor`, not the bare planner surface. Verify against LangGraph's documented sub-graph interrupt propagation; if the propagation surface requires explicit wiring, land it here.

Aligns with [architecture.md §4.3](../../architecture.md) (planner as reusable sub-graph), KDR-001 (LangGraph owns composition), KDR-009 (checkpointer delegated).

## Deliverables

### `ai_workflows/workflows/slice_refactor.py` (new)

```python
class SliceRefactorState(TypedDict):
    goal: str
    planner_plan: PlannerPlan | None   # populated by planner sub-graph
    slice_list: list[SliceSpec]        # T01 output
    # later tasks extend with: slice_results, aggregate, gate_response, applied_artifacts
```

- `SliceSpec` — new pydantic model co-located with the workflow: `id: str`, `description: str`, `acceptance: list[str]`. Derived from `PlannerStep`; keeps the slice contract local to the workflow instead of re-using `PlannerStep` directly (the planner's step shape is an LLM-output concern; slices are a worker-input concern — they evolve separately).
- `build_slice_refactor()` factory mirrors `build_planner()`: returns a compiled `StateGraph[SliceRefactorState]`.
- Compose the planner via `graph.add_node("planner", build_planner())` — LangGraph supports compiled-graph-as-node directly. Pipe `state.goal` in; capture `planner_plan` out.
- `slice_list_normalize` is a pure-function node (no LLM): maps `planner_plan.steps` → `list[SliceSpec]` 1:1 for this task. Deduplication / re-grouping is out of scope.
- Register the workflow in the `workflows` registry (same shape the planner uses at [`ai_workflows/workflows/__init__.py`](../../../ai_workflows/workflows/__init__.py)). `aiw run slice_refactor` must resolve to this factory via the existing dispatch path — no CLI changes needed if the registry is the only indirection.

### Sub-graph gate propagation verification

The planner's `HumanGate` fires `langgraph.interrupt(...)`. When executed as a sub-graph, the parent graph inherits the interrupt; `aiw run slice_refactor --goal '…'` must pause at the planner's plan-review gate, and `aiw resume <run_id> --approve` must clear it and continue into `slice_list_normalize`. If LangGraph's current subgraph-interrupt behaviour requires an explicit `node_key` or `parent_config` plumb, document the exact line in the builder.

### Tests

`tests/workflows/test_slice_refactor_planner_subgraph.py` (new):

- Hermetic: stub both planner tiers; `build_slice_refactor()` runs `START → planner sub-graph → gate`. Returns the interrupt payload with a parseable `PlannerPlan`.
- Resume: `aiw resume --approve` (or equivalent `Command(resume=...)`) clears the planner's gate and advances into `slice_list_normalize`; state contains a non-empty `slice_list`.
- Slice normalization shape: a `PlannerPlan` with 3 steps produces exactly 3 `SliceSpec` rows, preserving `id` / `description` / `acceptance` field-for-field.
- Empty plan (`steps == []`) is surfaced as a `NonRetryable` error — a plan with zero slices is a logic error, not a no-op (the apply node would have nothing to write; fail loud).
- Registry check: `workflows.registry.get("slice_refactor")` returns the compiled graph.

## Acceptance Criteria

- [ ] `ai_workflows.workflows.slice_refactor` module exists with `build_slice_refactor()` exporting a compiled `StateGraph[SliceRefactorState]`.
- [ ] Planner composed as sub-graph; `slice_refactor` run pauses at the planner's gate and resumes cleanly.
- [ ] `slice_list_normalize` maps `PlannerPlan.steps` → `list[SliceSpec]` 1:1.
- [ ] Empty plan → `NonRetryable` error.
- [ ] `slice_refactor` registered in the workflows registry; `aiw run slice_refactor --goal '…'` dispatches via the existing `_dispatch.run_workflow` path (no dispatch-layer changes required; verify in the Builder's first read).
- [ ] Hermetic tests green.
- [ ] `uv run lint-imports` 3 / 3 kept.
- [ ] `uv run ruff check` clean.

## Dependencies

- [Milestone 5](../milestone_5_multitier_planner/README.md) — planner sub-graph is multi-tier as shipped; T01 composes the finished planner, no tier changes.
- [M5 Task 03](../milestone_5_multitier_planner/task_03_subgraph_composition.md) — sub-graph retry + cost-rollup paths already exercised inside the planner; T01 exercises them at the outer graph boundary for the first time.
