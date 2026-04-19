# Task 08 — SqliteSaver Binding + Smoke Graph

**Status:** 📝 Planned.

## What to Build

Wire LangGraph's built-in `SqliteSaver` to a dedicated DB file (separate from the `Storage` DB — see KDR-009) and exercise the full M2 stack end-to-end with a minimal throwaway graph: `TieredNode → ValidatorNode → HumanGate`, with `CostTrackingCallback` and `RetryingEdge` in the loop. This is an integration test, not a real workflow.

## Deliverables

### `ai_workflows/graph/checkpointer.py`

```python
def build_checkpointer(db_path: Path | None = None) -> SqliteSaver:
    """Create or open a SqliteSaver at ~/.ai-workflows/checkpoints.sqlite (configurable).
    Applies any LangGraph-owned migrations automatically.
    Separate from Storage's DB (KDR-009)."""
```

- Path defaults to `~/.ai-workflows/checkpoints.sqlite`; override via env var `AIW_CHECKPOINT_DB`.
- Never shares a DB file with the `Storage` (run-registry) DB.

### Smoke-test graph

`tests/graph/test_smoke_graph.py`:

- Graph shape: `llm_node → validator → gate → end`.
- `llm_node` uses a stubbed provider (not a real API call).
- Run the graph to the `HumanGate` interrupt.
- Assert the checkpoint row exists in the SqliteSaver DB.
- Resume with a fake gate response; assert graph completes.
- Assert `CostTracker` totals are non-zero.

### Tests

Additional smaller unit tests in `tests/graph/test_checkpointer.py`:

- Custom path honoured.
- Env var override honoured.
- Applied to a plain `StateGraph` compiles without error.

## Acceptance Criteria

- [ ] Checkpointer DB file created at the expected path.
- [ ] Checkpointer DB is separate from the Storage DB on disk.
- [ ] Smoke graph runs to interrupt, checkpoints, and resumes cleanly.
- [ ] `CostTracker` totals reflect the smoke run.
- [ ] `uv run pytest tests/graph/test_smoke_graph.py tests/graph/test_checkpointer.py` green.

## Dependencies

- [Task 03](task_03_tiered_node.md) through [Task 07](task_07_retrying_edge.md).
