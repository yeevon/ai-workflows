# Task 06 — CostTrackingCallback

**Status:** 📝 Planned.

## What to Build

A LangGraph callback (or graph-wide hook, depending on the LangGraph API idiom at implementation time) that routes `TokenUsage` records from provider calls into `CostTracker.record(run_id, usage)`, and checks the per-run budget cap after every node.

## Deliverables

### `ai_workflows/graph/cost_callback.py`

```python
class CostTrackingCallback:
    def __init__(self, cost_tracker: CostTracker, budget_cap_usd: float | None): ...

    def on_node_complete(self, run_id: str, node_name: str, usage: TokenUsage) -> None:
        """Record and enforce budget."""
        self._tracker.record(run_id, usage)
        if self._cap is not None:
            self._tracker.check_budget(run_id, self._cap)  # raises NonRetryable on overage
```

- Surface is explicit (`on_node_complete`) rather than hooking internal LangGraph events — this keeps the boundary cleanly unit-testable.
- `TieredNode` ([task 03](task_03_tiered_node.md)) is the single invoker.
- Budget overage raises `NonRetryable` per M1 [task 07](../milestone_1_reconciliation/task_07_refit_retry_policy.md) — the graph aborts.

### Tests

`tests/graph/test_cost_callback.py`:

- Records usage through to `CostTracker`.
- Budget cap exceeded → raises `NonRetryable`.
- No cap → never raises regardless of spend.

## Acceptance Criteria

- [ ] Every `TieredNode` invocation results in exactly one `record` + one `check_budget` (when cap set).
- [ ] Budget enforcement uses the `NonRetryable` from [architecture.md §8.2](../../architecture.md).
- [ ] `uv run pytest tests/graph/test_cost_callback.py` green.

## Dependencies

- M1 [task 08](../milestone_1_reconciliation/task_08_prune_cost_tracker.md) (`CostTracker`).
- M1 [task 07](../milestone_1_reconciliation/task_07_refit_retry_policy.md) (`NonRetryable`).
