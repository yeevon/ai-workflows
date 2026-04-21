# Task 02 — Capture Helper (`CaptureCallback`)

**Status:** 📝 Planned.
**Grounding:** [milestone README §Exit criteria 2](README.md) · [architecture.md §4.1 — graph layer](../../architecture.md) · [KDR-004](../../architecture.md).

## What to Build

A new graph-layer callback — sibling to [`CostTrackingCallback`](../../../ai_workflows/graph/cost_callback.py) — that hooks into every `TieredNode` invocation during a live workflow run and emits one `EvalCase` JSON fixture per LLM-node call when `AIW_CAPTURE_EVALS=<dataset_name>` is set (or when `config["configurable"]["capture_evals"]` is provided by a caller).

The callback is pure instrumentation: zero effect on the graph's behaviour when the env var / config key is unset. It is not invoked automatically — callers opt in by attaching it at `_dispatch.run_workflow` dispatch time.

## Deliverables

### [ai_workflows/graph/eval_capture_callback.py](../../../ai_workflows/graph/eval_capture_callback.py)

```python
class CaptureCallback(BaseCallbackHandler):
    """LangGraph callback that emits EvalCase fixtures for every LLM-node call.

    Attaches at _dispatch time when AIW_CAPTURE_EVALS is set or when the caller
    threads `capture_evals={"dataset_name": str, "workflow_id": str}` through
    config["configurable"]. Writes one JSON fixture per LLM-node completion
    into <AIW_EVALS_ROOT>/<workflow>/<node>/<case_id>.json via
    ai_workflows.evals.save_case.

    Idempotent on re-capture: if the target path exists, append a monotonic
    suffix (`<case_id>-002.json`) rather than overwriting.
    """

    def __init__(self, dataset_name: str, workflow_id: str, run_id: str, root: Path) -> None: ...

    def on_llm_end(self, response, *, run_id, parent_run_id, tags, **kwargs) -> None:
        # Capture the TieredNode input state (from self._pending_inputs[run_id])
        # + the raw output + the inferred output_schema FQN.
        # Serialize into an EvalCase; call save_case().
        ...
```

Key design points:

- **Input capture:** `on_llm_start` records the `serialized` prompt + input kwargs keyed by `run_id`; `on_llm_end` pairs them up and writes the fixture.
- **Output schema FQN:** when the `TieredNode` was built with `output_schema=<pydantic model>`, the callback records the model's fully-qualified name so T03 replay knows which type to parse against. Falls back to `None` for free-text nodes.
- **case_id generation:** `<workflow_id>-<node_name>-<YYYYMMDD-HHMMSS>-<short_uuid>` — unique, sortable, human-readable.
- **Error surface:** capture failures (e.g., `save_case` raises on disk-full) are logged at `WARNING` via `StructuredLogger` but do not propagate — evaluation must not break a production run.

### [ai_workflows/graph/__init__.py](../../../ai_workflows/graph/__init__.py)

Add `CaptureCallback` to the public export list.

### Dispatch-layer opt-in

[ai_workflows/workflows/_dispatch.py](../../../ai_workflows/workflows/_dispatch.py) — `run_workflow` reads `AIW_CAPTURE_EVALS` (or an incoming `capture_evals` kwarg from CLI/MCP) and, when set, constructs a `CaptureCallback(dataset_name, workflow_id, run_id, root=<AIW_EVALS_ROOT|default>)` and appends it to the existing `callbacks` list attached to `compiled.ainvoke`. **No change** to the default path — unset env var means zero callback attachment, zero overhead.

### Tests

[tests/graph/test_eval_capture_callback.py](../../../tests/graph/test_eval_capture_callback.py):

- `test_callback_writes_fixture_on_llm_end` — fake `on_llm_start` + `on_llm_end` pair; assert fixture JSON written at canonical path; assert `EvalCase` round-trips.
- `test_callback_records_output_schema_fqn` — when `output_schema=ExplorerReport`, the fixture's `output_schema_fqn == "ai_workflows.workflows.planner.ExplorerReport"`.
- `test_callback_handles_free_text_node` — no `output_schema` → fixture's `output_schema_fqn is None` and `expected_output` is the raw string.
- `test_callback_appends_suffix_on_duplicate_case_id` — second write to the same path lands at `<case_id>-002.json`.
- `test_callback_capture_failure_logs_warning_but_does_not_raise` — patch `save_case` to raise; callback swallows and logs.

[tests/workflows/test_dispatch_capture_opt_in.py](../../../tests/workflows/test_dispatch_capture_opt_in.py):

- `test_dispatch_attaches_capture_callback_when_env_set` — `AIW_CAPTURE_EVALS=testsuite` set, `run_workflow` run against a stub adapter, fixture JSON appears under `<tmp_path>/testsuite/...`.
- `test_dispatch_skips_capture_when_env_unset` — default: zero fixtures written, no `CaptureCallback` in `callbacks`.
- `test_capture_does_not_affect_run_result` — approve-path run with capture enabled returns the same `{run_id, status, plan, total_cost_usd}` shape as without capture.

## Acceptance Criteria

- [ ] `CaptureCallback` exported from `ai_workflows.graph`.
- [ ] With `AIW_CAPTURE_EVALS=<name>` set, `aiw run planner --goal '...'` writes one fixture per LLM node invocation to `evals/<name>/planner/<node>/<case_id>.json`. (Confirmed via a unit test that drives `_dispatch.run_workflow` with a stub adapter — no need to hit live providers in this task's gate.)
- [ ] With `AIW_CAPTURE_EVALS` unset, the default path is byte-identical: no fixture directory created, no callback attached, zero extra graph overhead.
- [ ] `save_case` errors are logged, not raised — a run with a broken capture environment still completes normally.
- [ ] KDR-004 unaffected: no `ValidatorNode` wiring changed; no prompt change.
- [ ] Import-linter 4/4 kept (new contract from T01 plus the existing 3).
- [ ] `uv run pytest && uv run lint-imports && uv run ruff check` green.

## Dependencies

- [Task 01](task_01_dataset_schema.md) — `EvalCase` / `save_case` must exist.
- Uses `StructuredLogger` from primitives; uses LangGraph's `BaseCallbackHandler` from the already-declared `langchain-core` / `langgraph` deps — **no new dependency**.

## Out of scope (explicit)

- Replay (T03).
- CLI surface (T04).
- Seed-fixture capture against real providers — that happens under T05 once the capture surface is live.
