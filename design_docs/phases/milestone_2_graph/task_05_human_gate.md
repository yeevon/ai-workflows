# Task 05 — HumanGate Adapter

**Status:** 📝 Planned.

## What to Build

A LangGraph node factory that wraps `langgraph.interrupt()` with the strict-review semantics described in [architecture.md §8.3](../../architecture.md), and persists gate prompt + response in `Storage` via the trimmed protocol from M1 [task 05](../milestone_1_reconciliation/task_05_trim_storage.md).

## Deliverables

### `ai_workflows/graph/human_gate.py`

```python
def human_gate(
    *,
    gate_id: str,
    prompt_fn: Callable[[GraphState], str],
    strict_review: bool = False,
    timeout_s: int | None = 1800,  # ignored if strict_review=True
    default_response_on_timeout: str = "abort",
) -> Callable[[GraphState], Awaitable[dict]]:
    """Async LangGraph node that:
    1. Renders prompt via prompt_fn(state).
    2. Calls Storage.record_gate(run_id, gate_id, prompt, strict_review).
    3. Invokes langgraph.interrupt() with the prompt payload.
    4. On resume: receives response via LangGraph's interrupt-return mechanism.
    5. Calls Storage.record_gate_response(run_id, gate_id, response).
    6. Writes {f"gate_{gate_id}_response": response} into state.
    """
```

- `strict_review=True`: no timeout; `interrupt()` waits indefinitely.
- `strict_review=False`: LangGraph-level timeout configured on the graph; on expiry, `default_response_on_timeout` is applied.
- Storage writes use the protocol from M1 [task 05](../milestone_1_reconciliation/task_05_trim_storage.md). No new schema.

### Tests

`tests/graph/test_human_gate.py`:

- `interrupt()` is invoked exactly once per execution.
- `Storage.record_gate` called with `strict_review` flag preserved.
- Resumption writes the response key into state.
- With `strict_review=True`, timeout does not expire (test asserts via shorter `timeout_s` being ignored).

## Acceptance Criteria

- [ ] Gate prompt and response round-trip through `Storage`.
- [ ] `strict_review=True` disables timeout enforcement.
- [ ] Node integrates with a LangGraph `StateGraph` checkpointed by `SqliteSaver` ([task 08](task_08_checkpointer.md) covers the smoke test).
- [ ] `uv run pytest tests/graph/test_human_gate.py` green.

## Dependencies

- M1 [task 05](../milestone_1_reconciliation/task_05_trim_storage.md) (gate-log protocol).
