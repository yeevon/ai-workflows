# Task 04 — ValidatorNode Adapter

**Status:** 📝 Planned.

## What to Build

A LangGraph node factory that pairs with any `TieredNode` to enforce KDR-004 ("validator-after-every-LLM-node"). Parses the upstream node's text output against a pydantic schema; on success, writes the parsed object back into state; on failure, raises `RetryableSemantic` with a revision hint the upstream node can consume on the next attempt.

## Deliverables

### `ai_workflows/graph/validator_node.py`

```python
def validator_node(
    *,
    schema: type[BaseModel],
    input_key: str,         # state key holding raw text
    output_key: str,        # state key to write parsed instance
    node_name: str,
    max_attempts: int = 3,
) -> Callable[[GraphState], Awaitable[dict]]:
    """Async LangGraph node. On invocation:
    1. Read raw text from state[input_key].
    2. Try schema.model_validate_json(text).
    3. On success: return {output_key: parsed, f"{input_key}_revision_hint": None}.
    4. On failure: raise RetryableSemantic(reason=..., revision_hint=...).
    """
```

- `revision_hint` is human-readable text built from the pydantic `ValidationError` — this is the contract between validator and upstream LLM node on a semantic retry.
- `max_attempts` is a soft documentation hint; enforcement lives in `RetryingEdge` ([task 07](task_07_retrying_edge.md)).

### Tests

`tests/graph/test_validator_node.py`:

- Happy path: well-formed JSON → parsed instance written to state.
- Schema violation: raises `RetryableSemantic` with a non-empty `revision_hint`.
- Non-JSON text: raises `RetryableSemantic` (not `NonRetryable` — revisable by the LLM).

## Acceptance Criteria

- [ ] Node writes a pydantic instance to state on success.
- [ ] `revision_hint` is populated and references the schema mismatch.
- [ ] No LLM call, no cost record — this node is pure validation.
- [ ] `uv run pytest tests/graph/test_validator_node.py` green.

## Dependencies

- M1 [task 07](../milestone_1_reconciliation/task_07_refit_retry_policy.md) (`RetryableSemantic` exception).
- [Task 03](task_03_tiered_node.md) (conceptual pairing; not an import dep).
