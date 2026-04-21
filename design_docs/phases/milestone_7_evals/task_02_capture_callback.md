# Task 02 — Capture Helper (`CaptureCallback`)

**Status:** 📝 Planned.
**Grounding:** [milestone README §Exit criteria 2](README.md) · [architecture.md §4.1 — graph layer](../../architecture.md) · [KDR-004](../../architecture.md).

> **Amendment 2026-04-21 (M7-T02-ISS-01).** Task-doc placement corrected to match **milestone README exit criterion 1** and the architecture.md §3 layer contract: `CaptureCallback` lives at `ai_workflows/evals/capture_callback.py` (not `ai_workflows/graph/eval_capture_callback.py`). A `graph/` module doing this job would have to import `EvalCase` + `save_case` from `ai_workflows.evals`, which is a `graph → evals` edge forbidden by the T01 import-linter contract. The callback is still pure instrumentation over `TieredNode`; the graph layer reads it duck-typed via `config.configurable["eval_capture_callback"]` so no `graph → evals` edge appears. Deliverable section, AC-1, and test-file location below reflect the correction. See [issues/task_02_issue.md](issues/task_02_issue.md).

## What to Build

A new graph-layer callback — sibling to [`CostTrackingCallback`](../../../ai_workflows/graph/cost_callback.py) — that hooks into every `TieredNode` invocation during a live workflow run and emits one `EvalCase` JSON fixture per LLM-node call when `AIW_CAPTURE_EVALS=<dataset_name>` is set (or when `config["configurable"]["capture_evals"]` is provided by a caller).

The callback is pure instrumentation: zero effect on the graph's behaviour when the env var / config key is unset. It is not invoked automatically — callers opt in by attaching it at `_dispatch.run_workflow` dispatch time.

## Deliverables

### [ai_workflows/evals/capture_callback.py](../../../ai_workflows/evals/capture_callback.py)

```python
class CaptureCallback:
    """Callback that writes one EvalCase fixture per successful TieredNode call.

    Sibling of CostTrackingCallback — plain class with a single
    on_node_complete(*, run_id, node_name, inputs, raw_output, output_schema)
    method. Attaches at _dispatch time when AIW_CAPTURE_EVALS is set or when
    the caller passes capture_evals=<dataset> to run_workflow. The graph layer
    reads it duck-typed via config.configurable["eval_capture_callback"] and
    no-ops when absent, so unset default paths stay byte-identical.

    Writes one JSON fixture per LLM-node completion into
    <AIW_EVALS_ROOT>/<dataset>/<workflow>/<node>/<case_id>.json via
    ai_workflows.evals.save_case.

    Idempotent on re-capture: if the target path exists, append a monotonic
    suffix (`<case_id>-002.json`) rather than overwriting.
    """

    def __init__(
        self,
        *,
        dataset_name: str,
        workflow_id: str,
        run_id: str,
        root: Path | None = None,
    ) -> None: ...

    def on_node_complete(
        self,
        *,
        run_id: str,
        node_name: str,
        inputs: dict[str, Any],
        raw_output: str,
        output_schema: type[BaseModel] | None,
    ) -> Path | None:
        # Build EvalCase, resolve a non-colliding path, write the JSON.
        # All exceptions are logged at WARN and swallowed.
        ...
```

Key design points:

- **Callback shape.** Plain class with `on_node_complete(...)`, not a `BaseCallbackHandler` subclass. Matches the `CostTrackingCallback` convention already established in `ai_workflows/graph/cost_callback.py`; LangChain's `on_llm_end` signature does not carry the `output_schema` the T03 replay runner needs.
- **Call site.** `TieredNode` invokes the callback right after `cost_callback.on_node_complete(...)` on the success path. No separate `on_llm_start` bookkeeping is needed — inputs, raw output, and `output_schema` are all in scope at the post-node hook.
- **Output schema FQN:** when the `TieredNode` was built with `output_schema=<pydantic model>`, the callback records the model's fully-qualified name (`f"{schema.__module__}.{schema.__qualname__}"`) via the `output_schema_fqn()` helper exported from `ai_workflows.evals` so T03 replay knows which type to parse against. Falls back to `None` for free-text nodes.
- **case_id generation:** `<workflow_id>-<node_name>-<YYYYMMDD-HHMMSS>-<short_uuid>` — unique, sortable, human-readable.
- **Error surface:** capture failures (e.g., `save_case` raises on disk-full) are logged at `WARNING` via the module logger and do not propagate — evaluation must not break a production run.

### [ai_workflows/evals/__init__.py](../../../ai_workflows/evals/__init__.py)

Add `CaptureCallback` and `output_schema_fqn` to the public export list.

### Dispatch-layer opt-in

[ai_workflows/workflows/_dispatch.py](../../../ai_workflows/workflows/_dispatch.py) — `run_workflow` reads `AIW_CAPTURE_EVALS` (or an incoming `capture_evals` kwarg from CLI/MCP) and, when set, constructs a `CaptureCallback(dataset_name, workflow_id, run_id, root=<AIW_EVALS_ROOT|default>)` and appends it to the existing `callbacks` list attached to `compiled.ainvoke`. **No change** to the default path — unset env var means zero callback attachment, zero overhead.

### Tests

[tests/evals/test_capture_callback.py](../../../tests/evals/test_capture_callback.py) (test file moved to match the callback's corrected placement under `evals/`):

- `test_on_node_complete_writes_fixture` — direct call into `on_node_complete(...)`; assert fixture JSON written at canonical path `<root>/<workflow>/<node>/<case_id>.json`; assert `EvalCase` round-trips.
- `test_records_output_schema_fqn_for_known_schema` — with a pydantic `output_schema`, `output_schema_fqn()` returns `f"{module}.{qualname}"`.
- `test_records_none_schema_fqn_for_free_text_node` — no `output_schema` → fixture's `output_schema_fqn is None` and `expected_output` is the raw string.
- `test_appends_numeric_suffix_on_duplicate_case_id` — second write to the same path lands at `<case_id>-002.json` (deterministic via pinned `uuid.uuid4` + `datetime.now`).
- `test_capture_failure_logs_warning_but_does_not_raise` — patch `fixture_path` to raise; callback swallows and logs.
- `test_root_defaults_to_evals_root_slash_dataset` — `AIW_EVALS_ROOT` honoured; default root = `<AIW_EVALS_ROOT>/<dataset_name>`.
- `test_normalizes_pydantic_inputs` — pydantic `*Input` leaves in the state dict are dumped via `model_dump(mode="json")`.

[tests/workflows/test_dispatch_capture_opt_in.py](../../../tests/workflows/test_dispatch_capture_opt_in.py):

- `test_dispatch_attaches_capture_callback_when_env_set` — `AIW_CAPTURE_EVALS=testsuite` set, `run_workflow` run against a stub adapter, fixture JSON appears under `<tmp_path>/testsuite/...`.
- `test_dispatch_skips_capture_when_env_unset` — default: zero fixtures written, no `CaptureCallback` in `callbacks`.
- `test_capture_does_not_affect_run_result` — approve-path run with capture enabled returns the same `{run_id, status, plan, total_cost_usd}` shape as without capture.

## Acceptance Criteria

- [ ] `CaptureCallback` exported from `ai_workflows.evals` (matches milestone README exit criterion 1; amended 2026-04-21 per M7-T02-ISS-01).
- [ ] With `AIW_CAPTURE_EVALS=<name>` set, `aiw run planner --goal '...'` writes one fixture per LLM node invocation to `evals/<name>/planner/<node>/<case_id>.json`. (Confirmed via a unit test that drives `_dispatch.run_workflow` with a stub adapter — no need to hit live providers in this task's gate.)
- [ ] With `AIW_CAPTURE_EVALS` unset, the default path is byte-identical: no fixture directory created, no callback attached, zero extra graph overhead.
- [ ] `save_case` errors are logged, not raised — a run with a broken capture environment still completes normally.
- [ ] KDR-004 unaffected: no `ValidatorNode` wiring changed; no prompt change.
- [ ] Import-linter 4/4 kept (new contract from T01 plus the existing 3).
- [ ] `uv run pytest && uv run lint-imports && uv run ruff check` green.

## Dependencies

- [Task 01](task_01_dataset_schema.md) — `EvalCase` / `save_case` must exist.
- Uses std `logging.getLogger(__name__)` for the capture-failure WARN surface (matches the sibling `CostTrackingCallback` pattern); does not subclass `BaseCallbackHandler`. **No new dependency.**

## Out of scope (explicit)

- Replay (T03).
- CLI surface (T04).
- Seed-fixture capture against real providers — that happens under T05 once the capture surface is live.
