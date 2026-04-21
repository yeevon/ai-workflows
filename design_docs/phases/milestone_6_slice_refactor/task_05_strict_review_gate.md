# Task 05 — Strict-Review HumanGate Wiring

**Status:** 📝 Planned.

## What to Build

Add a `HumanGate(strict_review=True)` between [T04](task_04_aggregator.md)'s `aggregate` node and [T06](task_06_apply_node.md)'s `apply` node. Gate payload is the full `SliceAggregate` (succeeded + failed + total); gate response is `approve | reject`. Strict-review semantics per [architecture.md §8.3](../../architecture.md): no timeout, the gate holds the run indefinitely, and only an explicit `resume_run(run_id, gate_response)` clears it.

The planner's review gate was `strict_review=False` (30-minute default). This is the first workflow in the codebase to wire `strict_review=True`; verify the `HumanGate` primitive's `strict_review` flag actually disables the timeout path (no-op rather than "timeout = None").

Aligns with [architecture.md §8.3](../../architecture.md) (strict-review no-timeout), [§4.2](../../architecture.md) (`HumanGate` wraps `langgraph.interrupt()`), KDR-001.

## Deliverables

### `ai_workflows/workflows/slice_refactor.py` — strict-review gate

```python
review_gate = human_gate(
    node_id="slice_refactor_review",
    prompt_fn=_render_review_prompt,     # formats SliceAggregate into a reviewable prompt
    strict_review=True,
)
graph.add_edge("aggregate", "slice_refactor_review")
graph.add_conditional_edges(
    "slice_refactor_review",
    _route_on_gate_response,              # approve → "apply", reject → "END"
    {"apply": "apply", "END": END},
)
```

- `_render_review_prompt` — pure function formatting `state["aggregate"]` into the human-reviewable prompt. Keep it terse: one-line per slice with status + summary; failures listed first with `last_error`. No LLM call.
- `_route_on_gate_response` — inspects the resumed state's gate response; `"approve"` → `apply`, `"reject"` → graph END (run is marked `gate_rejected`, no artefacts written). Invalid / missing gate response → `NonRetryable` (contract violation; callers cannot produce this state without bypassing the MCP / CLI resume path).
- Reject path: on `"reject"`, the run's final status in `runs.status` is `gate_rejected` (distinct from `completed` and `cancelled`). Storage row update happens at the terminal node, not inside the gate.

### `HumanGate(strict_review=True)` primitive verification

Before extending the primitive, **read [`ai_workflows/graph/human_gate.py`](../../../ai_workflows/graph/human_gate.py)** and confirm:

1. `strict_review=True` genuinely disables the timeout path (not "sets timeout to infinity" — the latter is not equivalent if the timeout machinery still runs).
2. The gate persists the prompt and the resumed response in `Storage` regardless of the `strict_review` flag (gate audit log).

If the primitive does not already honour `strict_review=True` correctly, T05 owns the fix. Scope it narrowly — do not refactor the gate surface.

### Tests

`tests/workflows/test_slice_refactor_strict_gate.py` (new):

- Gate holds indefinitely: run reaches gate, checkpointer persists, no timeout fires after a simulated long wait (test uses a monotonic-clock stub; real wall-clock waits are out of scope).
- Approve path: `aiw resume <run_id> --gate-response approve` (or MCP `resume_run(... gate_response="approve")`) advances into `apply`.
- Reject path: `--gate-response reject` routes to END; `runs.status` is set to `gate_rejected`; no `apply` invocation.
- Missing gate response: resume without `gate_response` surfaces the existing M4 `ResumePreconditionError` / `ToolError` path.
- Gate payload shape: the interrupt payload surfaced to the caller is the full `SliceAggregate` (asserted via the stub-host-facing resume flow).
- Gate audit log: after approve or reject, `Storage`'s gate-response log row has `prompt` + `response` populated.

## Acceptance Criteria

- [ ] `HumanGate(strict_review=True)` wired between `aggregate` and `apply`.
- [ ] `strict_review=True` verified to disable the 30-minute timeout path (not just push it to infinity).
- [ ] Approve → `apply`; reject → END with `runs.status == "gate_rejected"`.
- [ ] Gate payload is the full `SliceAggregate`; prompt formatter shows successes + failures.
- [ ] Gate audit log lands in `Storage` for both approve and reject.
- [ ] Hermetic tests green.
- [ ] `uv run lint-imports` 3 / 3 kept.
- [ ] `uv run ruff check` clean.

## Dependencies

- [Task 04](task_04_aggregator.md) — `aggregate` node populates `SliceAggregate`.
- [M3 Task 04](../milestone_3_first_workflow/task_04_human_gate.md) — `HumanGate` primitive already landed; T05 may extend the `strict_review=True` branch.

## Carry-over from prior audits

- [ ] **T01-CARRY-DISPATCH-GATE** (MEDIUM, from T01 Builder-phase scope review 2026-04-20): [`_dispatch._build_resume_result_from_final`](../../../ai_workflows/workflows/_dispatch.py) hardcodes `state["gate_plan_review_response"]` when deciding approve/reject — that's the planner's gate_id leaking into dispatch. T05's new `slice_refactor_review` gate writes to `state["gate_slice_refactor_review_response"]`. Dispatch needs to discover the relevant gate key (options: inspect the final state for any `gate_*_response` key, or have each workflow module expose a `RESUME_GATE_ID` constant). Scope here is the minimum change that makes the approve/reject flow work for slice_refactor's strict-review gate without regressing the planner's.
