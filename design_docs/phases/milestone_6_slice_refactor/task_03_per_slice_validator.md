# Task 03 — Per-Slice Validator Wiring

**Status:** 📝 Planned.

## What to Build

Pair every `slice_worker` fan-out invocation with a `ValidatorNode` per **KDR-004** (validator-after-every-LLM-node is mandatory). [T02](task_02_parallel_slice_worker.md) landed the worker fan-out; T03 adds the validator and the semantic-retry self-loop edge, matching the planner's `TieredNode → ValidatorNode → retrying_edge` pattern at [`planner.py`](../../../ai_workflows/workflows/planner.py).

Aligns with [architecture.md §4.2](../../architecture.md) (`ValidatorNode` contract), [§8.2](../../architecture.md) (three-bucket retry), KDR-004, KDR-006.

## Deliverables

### `ai_workflows/workflows/slice_refactor.py` — validator wiring

For each fan-out branch, the shape becomes:

```
Send("slice_worker", …) → slice_worker → slice_worker_validator → aggregator
                                 ↑__________________________________|
                                 (on_semantic="slice_worker", max 3 retries)
```

- `slice_worker_validator` — `ValidatorNode(output_schema=SliceResult)`. Parses the worker's raw text output against the bare-typed `SliceResult` schema from [T02](task_02_parallel_slice_worker.md); raises `ModelRetry` with revision guidance on parse failure.
- `retrying_edge` on the validator: `on_semantic="slice_worker"` self-loops back to the worker with the `ModelRetry` message appended to the prompt; `on_transient="slice_worker"` handles bubble-up LiteLLM transient retries. Max semantic attempts: 3 (per [architecture.md §8.2](../../architecture.md)).
- Hard-stop handoff: after 3 failed semantic retries, the validator emits `NonRetryable`; the graph's `wrap_with_error_handler` catches it and escalates (the double-failure hard-stop logic lives in [T07](task_07_concurrency_hard_stop.md); T03 just emits the failure type correctly).

### Fan-out / fan-in boundary with the validator

LangGraph's `Send` dispatches each slice into the *worker → validator* pair individually; the reducer on `slice_results: Annotated[list[SliceResult], operator.add]` receives the validator's output (not the raw worker output). Confirm the validator's state-update shape writes into `slice_results`, not a separate key. If LangGraph forces a different reducer placement for fan-out-with-validator, document the exact topology.

### Tests

`tests/workflows/test_slice_refactor_validator.py` (new):

- Happy path: worker returns valid `SliceResult` JSON → validator passes through → `slice_results` populated correctly.
- Semantic retry: worker returns malformed JSON on first call, valid on second — graph self-loops the specific slice's worker once and completes. **Assert that sibling slices are not re-run** (semantic retry is per-slice, not per-fan-out-batch).
- Semantic retry exhaustion: worker returns malformed JSON on all 3 attempts → one slice surfaces `NonRetryable` — sibling slices still complete their worker→validator path. The double-failure abort decision is [T07](task_07_concurrency_hard_stop.md)'s scope; T03 asserts the single-slice failure surfaces correctly.
- Transient retry: worker raises `APIConnectionError` once → `retrying_edge`'s `on_transient` self-loops the worker with backoff; slice completes on the second attempt. Sibling slices unaffected.
- Validator KDR-004 regression guard: grep the final compiled graph's node list; every node whose tier is `slice-worker` has an adjacent `slice_worker_validator` node downstream.

## Acceptance Criteria

- [ ] Every `slice_worker` Send invocation is paired with a `slice_worker_validator` downstream (KDR-004).
- [ ] `retrying_edge(on_semantic="slice_worker", on_transient="slice_worker")` wired with max 3 semantic attempts.
- [ ] Per-slice semantic retry does not re-run sibling slices.
- [ ] Per-slice transient retry does not re-run sibling slices.
- [ ] Semantic-exhaustion on one slice surfaces `NonRetryable`; sibling slices still complete (T07 decides abort vs continue).
- [ ] `SliceResult` schema is bare-typed per KDR-010 / ADR-0002 (already landed in T02; re-audit).
- [ ] Hermetic tests green.
- [ ] `uv run lint-imports` 3 / 3 kept.
- [ ] `uv run ruff check` clean.

## Dependencies

- [Task 02](task_02_parallel_slice_worker.md) — fan-out + worker + reducer wired.

## Carry-over from prior audits

- [x] **M6-T02-ISS-01** (🟢 LOW, owner: M6 T03 — ✅ RESOLVED): T02's compound `_build_slice_worker_node._composed` with the inline `SliceResult.model_validate_json` parse is gone. Reverted exactly per the four-step plan: (1) inline parse and the `slice_results: [parsed]` write removed from the worker path; (2) `slice_worker` is now a plain `tiered_node(tier="slice-worker", output_schema=SliceResult, node_name="slice_worker")` that writes `slice_worker_output` only; (3) a new bespoke `_slice_worker_validator` downstream parses the raw text and writes `slice_results: [parsed]` in the reducer-compatible list shape; (4) `retrying_edge(on_semantic="slice_worker", on_transient="slice_worker", on_terminal=END/validator, policy=SLICE_WORKER_RETRY_POLICY)` wired with `max_semantic_attempts=3` (verified by `test_slice_worker_retry_policy_matches_spec_budget`). The `slice_worker_output` channel-scoping re-examination resolved differently than the issue anticipated: instead of `Annotated[dict[str, str], operator.or_]` keyed by `slice_id`, the channel lives only on the new `SliceBranchState` (the per-slice sub-graph's TypedDict) — LangGraph propagates sub-graph keys back to the parent **only** when declared on both sides, so scoping it to the branch state avoids the cross-branch collision entirely without a keyed reducer. The stock `validator_node` factory is not reused here because its fixed `{output_key: parsed}` shape would write a bare `SliceResult` into `slice_results`, bypassing the `operator.add` reducer contract; a bespoke shim preserves the raise/revise semantics. Source: [issues/task_02_issue.md §M6-T02-ISS-01](issues/task_02_issue.md).
