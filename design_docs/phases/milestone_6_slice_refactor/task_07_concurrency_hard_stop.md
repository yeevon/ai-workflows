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

## Carry-over from prior audits

- [x] **M6-T03-ISS-01** (🟢 LOW, owner: M6 T07): `graph/retrying_edge.py:118` checks the semantic budget via `retry_counts.get(on_semantic, 0)` — the **routing target** key — while `wrap_with_error_handler` at `graph/error_handler.py:150` bumps `retry_counts` under the **failing node's name**. In the planner + T03 wiring (`on_semantic="<worker>"`, validator wrapped with `node_name="<worker>_validator"`), the edge's budget check always sees `0` for semantic failures originating in the validator — the loop would run forever absent a workaround. T03 resolved AC-5 by escalating `RetryableSemantic → NonRetryable` inside `_slice_worker_validator` on the `max_semantic_attempts - 1`-th prior failure, but the latent pattern remains in `graph/retrying_edge.py` + `graph/validator_node.py`. T07 is the natural owner because it already touches `retrying_edge` / `_non_retryable_failures` semantics for the hard-stop decision. Pick one of two fixes: **(a)** document + test the in-validator escalation as the canonical `ValidatorNode` contract (update `graph/validator_node.py` docstring; add a test that exhausts a stock validator 3× and surfaces `NonRetryable`); or **(b)** teach `retrying_edge` to sum retry-counters across a configurable list of node names, defaulting to `[on_semantic, f"{on_semantic}_validator"]`. Option (a) is lower-blast-radius and matches the T03 pattern; option (b) centralises the budget but widens the edge's API. Source: [issues/task_03_issue.md §LOW-01](issues/task_03_issue.md). ✅ RESOLVED in T07 Builder — picked option (a): stock `validator_node` now escalates `RetryableSemantic → NonRetryable` when `state["_retry_counts"][node_name]` has been bumped `max_attempts - 1` times. Module + function docstrings pin the escalation contract + `node_name` alignment requirement. Pinned by `tests/graph/test_validator_node.py::test_escalation_raises_non_retryable_on_last_allowed_attempt` + `::test_escalation_preserves_retryable_semantic_on_earlier_attempts` + `::test_escalation_reads_counter_under_validator_node_name` + `::test_escalation_works_with_max_attempts_one` + `::test_exhausting_three_attempts_sequence_surfaces_non_retryable`.
- [x] **M6-T04-ISS-01** (🟢 LOW, owner: M6 T07): `_merge_non_retryable_failures` in `ai_workflows/workflows/slice_refactor.py:184-197` uses `max(existing, update)` as its fan-in reducer, which undercounts to `1` across any number of parallel `NonRetryable` branch failures (every failing branch reads the same pre-fan-in value `0` from `wrap_with_error_handler` and writes `1`; `max` collapses them). Today the aggregator bypasses this counter — `_aggregate` reads `slice_results` + `slice_failures` directly — so T04 is unaffected. But `graph/retrying_edge.py:103` uses `state["_non_retryable_failures"] >= 2` for its double-failure short-circuit, which will therefore never fire across fan-out. T07's spec already threads the hard-stop via `len(state["slice_failures"]) >= 2` (the new conditional edge under "Deliverables"), which sidesteps the reducer entirely — so the correct resolution is **(a) docstring-only**: add an explicit note to `_merge_non_retryable_failures` explaining that the counter is only reliable under sequential writes, and cite the `slice_failures` list as the canonical fan-out failure count. T07 already touches this file for the hard-stop wiring, so the fix is a one-line addition. **Do not** switch the reducer to a true sum without its own KDR — that would force a matching delta-write change in `graph/error_handler.py` and affect every workflow. Source: [issues/task_04_issue.md §M6-T04-ISS-01](issues/task_04_issue.md). ✅ RESOLVED in T07 Builder — `_merge_non_retryable_failures` docstring pins the "reliable only under sequential writes" note and cites `slice_failures` (operator.add-reduced) as the canonical fan-out failure count. The new `_route_before_aggregate` edge reads `len(state["slice_failures"]) >= HARD_STOP_FAILURE_THRESHOLD` instead of the `max`-reduced counter. Pinned by `tests/workflows/test_slice_refactor_hard_stop.py::test_route_ignores_non_retryable_failures_counter` + `::test_route_sends_to_hard_stop_on_two_failures`.
