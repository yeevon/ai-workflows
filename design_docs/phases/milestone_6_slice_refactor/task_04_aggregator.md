# Task 04 — Aggregator Node

**Status:** 📝 Planned.

## What to Build

Replace [T02](task_02_parallel_slice_worker.md)'s placeholder aggregator with the real merge semantics: collect all validated `SliceResult` rows from the fan-out reducer, produce a single `SliceAggregate` summary object, and hand off to [T05](task_05_strict_review_gate.md)'s strict-review gate. No LLM call — the aggregator is pure-function synthesis over the validated per-slice outputs.

Partial-failure handling: if any slice surfaced `NonRetryable` after [T03](task_03_per_slice_validator.md)'s semantic-retry exhaustion, the aggregator records which slices failed without discarding the successful rows. The double-failure hard-stop ([architecture.md §8.2](../../architecture.md)) is enforced separately in [T07](task_07_concurrency_hard_stop.md); T04 only captures the partial state faithfully.

Aligns with [architecture.md §4.3](../../architecture.md) (aggregate → strict-review → apply), [§8.2](../../architecture.md) (failure posture), KDR-001 (LangGraph-native merge).

## Deliverables

### `ai_workflows/workflows/slice_refactor.py` — aggregator node

```python
class SliceAggregate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    succeeded: list[SliceResult]
    failed: list[SliceFailure]   # (slice_id, last_error_message)
    total_slices: int

def aggregate(state: SliceRefactorState) -> dict[str, SliceAggregate]:
    successes = state["slice_results"]
    failures = state.get("slice_failures", [])
    return {"aggregate": SliceAggregate(
        succeeded=successes,
        failed=failures,
        total_slices=len(successes) + len(failures),
    )}
```

- `SliceFailure` pydantic model (co-located): `slice_id: str`, `last_error: str`, `failure_bucket: Literal["retryable_semantic", "non_retryable"]`.
- `aggregate` is a plain Python function registered as a node — no `TieredNode`, no validator (KDR-004 does not apply; there is no LLM call).
- State extension: `slice_failures: Annotated[list[SliceFailure], operator.add]` added to `SliceRefactorState`. Failing branches in the fan-out emit a `SliceFailure` into this key instead of a `SliceResult` into `slice_results`.
- The error-handler wrap around the worker→validator pair (from [T03](task_03_per_slice_validator.md)'s `NonRetryable` surfacing) converts exhausted slices into `SliceFailure` rows. If T03 did not already wire this conversion, T04 owns it — the aggregator needs the failure rows in state, not as unhandled exceptions.

### Tests

`tests/workflows/test_slice_refactor_aggregator.py` (new):

- All-success: 3 slices, all pass validator → `aggregate.succeeded` has 3 rows, `aggregate.failed` is `[]`, `total_slices == 3`.
- All-failure: 3 slices, all exhaust semantic retries → `aggregate.succeeded == []`, `aggregate.failed` has 3 rows with populated `last_error`. (The run still reaches the aggregator — the double-failure hard-stop is [T07](task_07_concurrency_hard_stop.md)'s call; T04 exercises only the shape.)
- Partial failure: 2 success + 1 failure → both lists populated correctly, `total_slices == 3`.
- Ordering: `succeeded` and `failed` orderings are stable (or explicitly order-independent — pin one in the test).
- `SliceAggregate` is bare-typed per KDR-010 / ADR-0002 — `extra="forbid"` set, no `Field(min_length/...)` bounds.

## Acceptance Criteria

- [ ] `SliceAggregate` and `SliceFailure` pydantic models co-located in `slice_refactor.py`, bare-typed.
- [ ] `aggregate` node is a pure function, no LLM call, no validator.
- [ ] `slice_failures` state key populated by exhausted slices via the worker→validator error handler.
- [ ] Hermetic tests cover all-success, all-failure, partial-failure.
- [ ] `uv run lint-imports` 3 / 3 kept.
- [ ] `uv run ruff check` clean.

## Dependencies

- [Task 02](task_02_parallel_slice_worker.md) — fan-out + reducer + `slice_results` key.
- [Task 03](task_03_per_slice_validator.md) — per-slice validator emits `NonRetryable` on exhaustion.
