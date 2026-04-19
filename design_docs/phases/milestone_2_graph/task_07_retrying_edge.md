# Task 07 — RetryingEdge

**Status:** 📝 Planned.

## What to Build

A conditional-edge helper that inspects the most recently raised exception in state and routes the graph by the 3-bucket taxonomy from KDR-006:

- `RetryableTransient` → self-loop with exponential backoff, capped at `max_transient_attempts`.
- `RetryableSemantic` → loop back to the paired LLM node carrying the `revision_hint`, capped at `max_semantic_attempts`.
- `NonRetryable` → either terminal failure, or continue sibling-independent branches (double-failure hard-stop honoured).

## Deliverables

### `ai_workflows/graph/retrying_edge.py`

```python
def retrying_edge(
    *,
    on_transient: str,    # node name to self-loop to
    on_semantic: str,     # node name (LLM node) to re-invoke with revision hint
    on_terminal: str,     # "__end__" or a cleanup node
    policy: RetryPolicy,
) -> Callable[[GraphState], str]:
    """Return the next node name based on state['last_exception'] classification.
    Track attempt counts in state[f"_retry_counts"][node_name].
    Enforce max_transient_attempts / max_semantic_attempts; on exhaustion, escalate to NonRetryable path.
    Enforce double-failure hard-stop: if state['_non_retryable_failures'] >= 2, route to on_terminal."""
```

- Exception classification is done upstream (by `TieredNode` or `ValidatorNode`); this function only reads the classified exception.
- Backoff is implemented in the *target* self-loop node (an `asyncio.sleep` wrapper); not in the edge.

### Tests

`tests/graph/test_retrying_edge.py`:

- Transient → routes to `on_transient` until `max_transient_attempts`, then to `on_terminal`.
- Semantic → routes to `on_semantic` with `revision_hint` preserved; exhaustion → `on_terminal`.
- Non-retryable → routes to `on_terminal`.
- Double failure: second `NonRetryable` triggers `on_terminal` regardless of sibling state.

## Acceptance Criteria

- [ ] All three buckets routed correctly.
- [ ] Attempt counters live in state (durable across checkpoint resume).
- [ ] Double-failure hard-stop covered by a test.
- [ ] `uv run pytest tests/graph/test_retrying_edge.py` green.

## Dependencies

- M1 [task 07](../milestone_1_reconciliation/task_07_refit_retry_policy.md) (taxonomy + `RetryPolicy`).
- [Task 03](task_03_tiered_node.md), [Task 04](task_04_validator_node.md) (raising sites).
