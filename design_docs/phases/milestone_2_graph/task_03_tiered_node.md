# Task 03 — TieredNode Adapter

**Status:** 📝 Planned.

## What to Build

A LangGraph-compatible node factory: given a tier name, a prompt-building function, and an optional output schema, it returns a node function that resolves the tier, picks the right provider driver (LiteLLM vs Claude Code), executes the call, records cost, emits a structured log, and classifies any exception via the 3-bucket taxonomy.

## Deliverables

### `ai_workflows/graph/tiered_node.py`

```python
def tiered_node(
    *,
    tier: str,
    prompt_fn: Callable[[GraphState], tuple[str | None, list[dict]]],
    output_schema: type[BaseModel] | None = None,
    node_name: str,
) -> Callable[[GraphState], Awaitable[dict]]:
    """Returns an async LangGraph node. On invocation:
    1. Resolve tier via TierRegistry.
    2. Dispatch to LiteLLMAdapter or ClaudeCodeSubprocess by route.kind.
    3. Call .complete(...).
    4. CostTrackingCallback.on_node_complete(run_id, node_name, usage).
    5. StructuredLogger.emit(run_id, node_name, tier, provider, model, duration_ms, tokens, cost).
    6. On exception: classify() → raise typed bucket.
    """
```

- Tier registry is injected via LangGraph config (no module-level globals).
- Per-provider semaphore comes from `TierConfig.max_concurrency`; enforced inside the node function.
- Does *not* swallow exceptions — classification happens; the typed exception propagates so `RetryingEdge` can route.

### Tests

`tests/graph/test_tiered_node.py`:

- Dispatch to LiteLLM path with a stub adapter → asserts correct provider selected.
- Dispatch to Claude Code path with a stub driver → asserts correct provider selected.
- Semaphore enforces `max_concurrency=1`: two concurrent invocations serialise.
- Exception classification: adapter raises `litellm.RateLimitError` → node raises `RetryableTransient`.

## Acceptance Criteria

- [ ] Node is a standard LangGraph node (plain `async def`, takes state, returns dict).
- [ ] Both provider paths covered by tests.
- [ ] Semaphore respected.
- [ ] Emits exactly one structured log record per invocation.
- [ ] Emits exactly one `CostTracker.record` call per invocation.
- [ ] `uv run pytest tests/graph/test_tiered_node.py` green.

## Dependencies

- [Task 01](task_01_litellm_adapter.md), [Task 02](task_02_claude_code_driver.md).
- M1 [task 06](../milestone_1_reconciliation/task_06_refit_tier_config.md), [task 07](../milestone_1_reconciliation/task_07_refit_retry_policy.md), [task 09](../milestone_1_reconciliation/task_09_logger_sanity.md).
