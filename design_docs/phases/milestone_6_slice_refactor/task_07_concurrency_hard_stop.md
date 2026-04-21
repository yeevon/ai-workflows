# Task 07 — Concurrency Semaphore + Double-Failure Hard-Stop

**Status:** 📝 Planned.

## What to Build

Prove the two cross-cutting runtime contracts that `slice_refactor`'s parallel fan-out is the first workflow to exercise:

1. **Per-tier concurrency semaphore** ([architecture.md §8.6](../../architecture.md)) — `TierConfig.max_concurrency` bounds in-flight provider calls at the call site, not by the graph shape. With a fan-out of N slices against a tier configured `max_concurrency=k`, the provider sees at most `k` overlapping calls.
2. **Double-failure hard-stop** ([architecture.md §8.2](../../architecture.md)) — if two distinct nodes fail `NonRetryable` in the same run, the graph aborts regardless of sibling independence. [T02](task_02_parallel_slice_worker.md) / [T03](task_03_per_slice_validator.md) land the per-slice failure plumbing; T07 adds the cross-slice counter and the abort trigger.

Scope is verification + one small piece of wiring (the failure counter). The semaphore implementation itself lives in the existing `TieredNode` / `TierConfig` stack from M2 — if that stack does not already honour `max_concurrency` at the call site, T07 owns the audit + fix.

Aligns with [architecture.md §8.2](../../architecture.md), [§8.6](../../architecture.md), KDR-006 (three-bucket retry surfaces the failure types the hard-stop counts).

## Deliverables

### Semaphore verification + fix if needed

Audit `TieredNode.__call__` (`ai_workflows/graph/tiered_node.py`) and `TierConfig.max_concurrency` (`ai_workflows/primitives/tiers.py:93`). The semaphore must be:

- **Per-tier, process-local** (`asyncio.Semaphore`, one per logical tier name).
- **Acquired inside the TieredNode's provider call** (so fan-out actually bounds the provider, not the LangGraph step).
- **Shared across all fan-out branches dispatching to the same tier** (a module-level `dict[tier_name, Semaphore]` or equivalent — not per-TieredNode-instance).

If the current implementation does not satisfy all three, T07 owns the fix. Do not over-scope: keep the change to `TieredNode` / `TierConfig` — no new primitives, no new graph-layer adapter.

### `ai_workflows/workflows/slice_refactor.py` — hard-stop failure counter

Extend `SliceRefactorState`:

```python
slice_failures: Annotated[list[SliceFailure], operator.add]  # already added in T04
```

Add a conditional edge that checks `len(state["slice_failures"]) >= 2` **before** the aggregator runs; if true, route to a `hard_stop` terminal node that:

1. Flips `runs.status = "aborted"` (new status value, distinct from `gate_rejected` and `cancelled`).
2. Stamps `finished_at`.
3. Records the two failing slice IDs in the run's metadata (reuse the existing `Storage.set_run_metadata` or equivalent helper; do not invent a new table).

The hard-stop abort **does not** wait for all siblings — the architecture's language is explicit: "*the graph aborts regardless of sibling independence*". In-flight sibling workers get cancelled via the same `durability="sync"` + `task.cancel()` path [T02](task_02_parallel_slice_worker.md) wired for `cancel_run`.

### Tests

`tests/workflows/test_slice_refactor_concurrency.py` (new):

- **Semaphore bound:** tier configured `max_concurrency=2`; fan out 5 slices; assert the stub provider's max concurrent in-flight call count is 2 (use a counter + sleep in the stub). The other 3 are queued on the semaphore.
- **Semaphore is per-tier:** two tiers each at `max_concurrency=1`; fan out to both; both tiers see concurrent activity simultaneously (one call each in-flight at any moment).
- **No-fan-out regression:** planner workflow (single-tier, no fan-out) unaffected by the semaphore — runs to completion with the same wall-clock characteristics as M5.

`tests/workflows/test_slice_refactor_hard_stop.py` (new):

- **Single failure:** 3 slices, 1 exhausts semantic retries → aggregator runs, `SliceAggregate` has 2 successes + 1 failure, strict-review gate fires with the partial aggregate.
- **Double failure:** 3 slices, 2 exhaust semantic retries → graph aborts **before** aggregator; `runs.status == "aborted"`; `finished_at` stamped; failing slice IDs recorded; no gate invocation; no `apply` invocation.
- **Triple failure (all slices fail):** same abort path — aborts at the second failure, doesn't wait for the third.
- **In-flight sibling cancellation:** on abort, any still-running sibling worker's `asyncio.Task` is cancelled (reuses the T02 registry + `task.cancel()` path).
- **Transient retries do not count:** a slice that succeeds after a transient retry is not a `NonRetryable`; the counter only increments on `NonRetryable` failures from the validator's semantic-exhaustion or the worker's non-retryable taxonomy.

## Acceptance Criteria

- [ ] `TieredNode` acquires `TierConfig.max_concurrency` semaphore per-tier, process-local, shared across fan-out branches.
- [ ] Semaphore-bound concurrency test green (fan-out of 5 against `max_concurrency=2` sees at most 2 concurrent provider calls).
- [ ] Multi-tier semaphore test green (per-tier isolation).
- [ ] Double-failure conditional edge added; routes to `hard_stop` terminal node before aggregator.
- [ ] `runs.status = "aborted"` introduced as a distinct terminal status; storage helper accepts it.
- [ ] Hard-stop triggers on the *second* `NonRetryable`, not the third (doesn't wait for all siblings).
- [ ] Transient retries do not increment the failure counter.
- [ ] In-flight siblings cancelled on abort via the T02 task-registry path.
- [ ] Hermetic tests green on all branches.
- [ ] `uv run lint-imports` 3 / 3 kept.
- [ ] `uv run ruff check` clean.

## Dependencies

- [Task 02](task_02_parallel_slice_worker.md) — `durability="sync"` compile + `_ACTIVE_RUNS` task registry.
- [Task 03](task_03_per_slice_validator.md) — per-slice `NonRetryable` surfacing.
- [Task 04](task_04_aggregator.md) — `slice_failures` state key.
- [Task 05](task_05_strict_review_gate.md) — gate fires only when hard-stop did not; edge ordering matters.
