# Task 04 — Aggregator Node — Audit Issues

**Source task:** [../task_04_aggregator.md](../task_04_aggregator.md)
**Audited on:** 2026-04-20
**Audit scope:** `ai_workflows/workflows/slice_refactor.py` (aggregator +
`SliceFailure` / `SliceAggregate` models + `slice_branch_finalize` sub-graph
node + state-channel extensions + graph-wiring changes),
`tests/workflows/test_slice_refactor_aggregator.py` (11 new tests),
`CHANGELOG.md` entry, sibling issue files for T02 / T03,
`design_docs/architecture.md` §4.2 / §4.3 / §8.2 / §9, KDR-001 / 004 / 006 /
009 / 010 grounding.
**Status:** ✅ PASS — every AC met, gates green, zero design drift. No
OPEN issues. 🟢 LOW M6-T04-ISS-01 forward-deferred to M6 T07; ✅ RESOLVED
in M6 T07 Builder (2026-04-20) via option 1 (`len(slice_failures) >= 2`
routing + reducer docstring note).

## Design-drift check

Cross-referenced against [`architecture.md`](../../../architecture.md):

- **New dependency?** None. T04 adds no imports to `pyproject.toml`. The
  module-local imports stay within the KDR-allowed set (pydantic v2,
  LangGraph, `ai_workflows.primitives` + `ai_workflows.graph`).
- **New module / layer?** No. Edits land on the existing
  `ai_workflows.workflows.slice_refactor` module, which already owns the
  outer DAG per §4.3.
- **LLM call added?** No. The aggregator is pure synthesis over
  reducer-accumulated state; `slice_branch_finalize` is equally pure.
  KDR-004 correctly not applied — no `TieredNode` wrap, no
  `ValidatorNode` pairing required. Spec explicitly codifies this.
- **Checkpoint / resume logic?** No change. `_build_slice_branch_subgraph`
  continues to compile the sub-graph without a checkpointer; the parent's
  `AsyncSqliteSaver` is shared at run time per KDR-009.
- **Retry logic?** No bespoke try/except added. The one code path that
  reads the retry classification (`_slice_branch_finalize`) uses
  `isinstance(exc, RetryableSemantic)` purely to set the
  `failure_bucket` Literal — no retry decision. The `retrying_edge`
  `on_terminal` re-target from `END` to `slice_branch_finalize` stays
  within KDR-006's three-bucket routing.
- **Observability?** No new backends, no Langfuse / OTel / LangSmith
  imports.

**Outcome: no design drift.** T04 is a pure pydantic + state-reducer
extension that fits inside the existing four-layer contract.

## AC grading

| # | Acceptance criterion | Verdict |
| - | --- | --- |
| 1 | `SliceAggregate` + `SliceFailure` co-located in `slice_refactor.py`, bare-typed | ✅ PASS |
| 2 | `aggregate` node is a pure function, no LLM call, no validator | ✅ PASS |
| 3 | `slice_failures` populated by exhausted slices via worker→validator error handler | ✅ PASS |
| 4 | Hermetic tests cover all-success, all-failure, partial-failure | ✅ PASS |
| 5 | `uv run lint-imports` 3 / 3 kept | ✅ PASS |
| 6 | `uv run ruff check` clean | ✅ PASS |

### AC 1 — bare-typed, co-located models
Both `SliceFailure` and `SliceAggregate` are declared in
`ai_workflows/workflows/slice_refactor.py` adjacent to `SliceResult`.
Both set `model_config = ConfigDict(extra="forbid")` with no
`Field(min_length=…)` / `ge=` / `le=` bounds on any field. Verified by
`test_slice_aggregate_is_bare_typed` and
`test_slice_failure_is_bare_typed`, which introspect every field via
`model_fields` and assert none carries a numeric bound.
`failure_bucket: Literal["retryable_semantic", "non_retryable"]`
matches the spec's literal-type verbatim.

### AC 2 — pure-function aggregator
`_aggregate` is a synchronous Python function — verified by
`test_aggregate_is_plain_sync_function` asserting
`inspect.iscoroutinefunction(_aggregate) is False`. It is registered
on the outer graph as `g.add_node("aggregate", _aggregate)` (no
`tiered_node`, no `wrap_with_error_handler`, no paired validator
node). `test_aggregate_builds_slice_aggregate_from_state_only`
drives it directly with an in-memory state dict and asserts the
returned `SliceAggregate` has the expected `succeeded` / `failed` /
`total_slices` shape without any external calls.

### AC 3 — `slice_failures` populated via error-handler path
New `_slice_branch_finalize` node sits on the sub-graph's terminal
path (`retrying_edge.on_terminal = "slice_branch_finalize"`; previously
routed to `END`). It reads `state["last_exception"]` — written by
`wrap_with_error_handler` on any `RetryableTransient` /
`RetryableSemantic` / `NonRetryable` classification — and emits one
`SliceFailure` row into `slice_failures`. Happy-path branches
(`last_exception is None` after the worker's success clear) return
`{}` so the reducer receives no contribution.
`test_subgraph_has_slice_branch_finalize_node` guards against a
future removal of this node.
`test_all_failure_aggregate_has_three_failed_and_no_succeeded`
exercises the end-to-end path: 3 branches each burn their full
3-attempt semantic budget via the T03 in-validator escalation →
`aggregate.failed` carries 3 `SliceFailure` rows with populated
`last_error` strings.

### AC 4 — hermetic test coverage
`tests/workflows/test_slice_refactor_aggregator.py` ships 11 tests.
The three end-to-end scenarios the spec calls out:

- **All-success**
  (`test_all_success_aggregate_has_three_succeeded_and_no_failed`):
  3 slices pass validator → `aggregate.succeeded` set equals
  `{"1", "2", "3"}`, `aggregate.failed == []`, `total_slices == 3`,
  `slice_failures` reducer stays empty.
- **All-failure**
  (`test_all_failure_aggregate_has_three_failed_and_no_succeeded`):
  3 slices all exhaust → `aggregate.succeeded == []`,
  `{f.slice_id for f in aggregate.failed} == {"1", "2", "3"}`,
  every failure carries a non-empty `last_error` and a
  spec-allowed `failure_bucket`.
- **Partial failure**
  (`test_partial_failure_aggregate_preserves_both_lists`):
  2 successes + 1 exhaustion → `succeeded` set `{"1", "3"}`,
  `failed` list `["2"]`, `total_slices == 3`. Per-slice
  `worker_calls_by_slice` confirms siblings ran once each while the
  failing slice burnt its full 3-attempt budget.

Stubs mirror the T03 suite's per-slice routing pattern so the
"siblings not re-run on retry" invariant from T03 stays green in the
T04 shape.

### AC 5 — `uv run lint-imports`
3 / 3 contracts kept (output captured in Gate summary). No new
cross-layer imports.

### AC 6 — `uv run ruff check`
Clean. One SIM108 hint was addressed by refactoring the
`failure_bucket` assignment to a ternary (preserving the multi-case
comment as a preceding block). One I001 hint on the test file was
auto-fixed.

## 🔴 HIGH
None.

## 🟡 MEDIUM
None.

## 🟢 LOW

### M6-T04-ISS-01 — `_non_retryable_failures` uses `max`-reducer; will undercount fan-in failures when T07 wires the hard-stop (🟢 LOW — ✅ RESOLVED in M6 T07 Builder 2026-04-20)
**Finding.** `_merge_non_retryable_failures`
(`ai_workflows/workflows/slice_refactor.py:184-197`, landed in T02 and
retained by T03 / T04) reduces parallel branch writes via `max` rather
than a true sum. Each failing branch's `wrap_with_error_handler` writes
`_non_retryable_failures: prev_scalar + 1` to its branch-scoped state;
LangGraph then reduces N of those writes onto the parent channel with
`max(existing_or_0, update_or_0)`. With N failing branches, the parent
sees `_non_retryable_failures == 1` — not N — because every branch read
the same pre-fan-in value `0` and wrote `1`. The existing T02 docstring
acknowledges "max so a single burst of parallel failures reports the
higher watermark rather than double-counting"; what the docstring does
*not* acknowledge is that this *also* undercounts to `1` across any
number of parallel `NonRetryable` failures.

T04 does not trigger this — the aggregator reads `slice_results` +
`slice_failures` directly, bypassing `_non_retryable_failures`
entirely. The failure surfaces at T07, where the double-failure
hard-stop decides on `state["_non_retryable_failures"] >= 2`
([architecture.md §8.2](../../../architecture.md)) — the check will
read `1` and never fire under parallel fan-out, defeating the hard-stop
guarantee the test plan explicitly calls out:

> **Triple failure (all slices fail):** same abort path — aborts at the
> second failure, doesn't wait for the third.

**Action (owner: M6 T07).** Pick one:

1. **Decide via `slice_failures` instead of `_non_retryable_failures`.**
   `_aggregate` already sees every branch's `SliceFailure`; T07's
   conditional edge can short-circuit on
   `len(state["slice_failures"]) >= 2` before the aggregator runs. This
   is the path the T07 spec's "Deliverables" section already codes
   (`len(state["slice_failures"]) >= 2`), so it requires **zero
   changes to the reducer** — the spec is already internally consistent
   and this issue becomes a docstring fix.
2. **Fix the reducer to sum (with dedup).** Replace `max` with
   `existing + update` keyed on a per-branch delta (each branch writes
   exactly `+1`, not `prev + 1`), so fan-in genuinely sums. Requires a
   matching change in `wrap_with_error_handler` to write the delta
   rather than the absolute successor — blast radius extends into
   `graph/error_handler.py` and affects every workflow, not just M6.

**Recommended:** option 1 (lower blast radius, matches T07 spec verbatim,
means T07 only needs to add one docstring line in `slice_refactor.py`
explaining why `_non_retryable_failures` is intentionally unreliable
under fan-out). Option 2 is a cross-workflow reducer change and should
not be attempted inside T07's scope without its own KDR.

**Resolution — ✅ RESOLVED in M6 T07 Builder (2026-04-20).** T07 picked
**option 1** (decide via `slice_failures` instead of
`_non_retryable_failures`). Concrete landed changes:

- `_merge_non_retryable_failures` docstring now explicitly notes the
  counter is reliable only under sequential writes and cites
  `slice_failures` (`operator.add`-reduced) as the canonical fan-out
  failure count. No reducer swap; the scalar counter remains useful for
  the planner (single-writer sequential path) and does not mislead
  future readers in the fan-out context.
- New `_route_before_aggregate` conditional edge (outer graph) reads
  `len(state["slice_failures"]) >= HARD_STOP_FAILURE_THRESHOLD` (== 2)
  and routes to the `hard_stop` terminal node before the aggregator
  runs. Siblings already completed by the time this edge fires
  (LangGraph synchronises `Send` fan-in before the join); in-flight
  cancel is handled by T02's `_ACTIVE_RUNS` + `task.cancel()` path.
- `_hard_stop` node writes a `hard_stop_metadata` artefact to Storage
  (failing slice IDs + timestamp) and `_dispatch.run_workflow` flips
  `runs.status = "aborted"` with `finished_at` stamped.

**Pinning tests:**
- `tests/workflows/test_slice_refactor_hard_stop.py::test_route_ignores_non_retryable_failures_counter`
  (asserts the route reads `slice_failures`, not the broken counter).
- `tests/workflows/test_slice_refactor_hard_stop.py::test_route_sends_to_hard_stop_on_two_failures`
  (positive path).
- Plus 15 more in the same file covering triple-failure, routing order,
  artefact idempotency, status flip, graph shape.

Option 2 (cross-workflow reducer swap) was intentionally NOT taken —
would have required a matching delta-write change in
`graph/error_handler.py` and touched every workflow, not just M6.

## Additions beyond spec — audited and justified

### Addition — `aggregate: SliceAggregate` state key on `SliceRefactorState`
**Why it's justified.** The spec shows `aggregate` writing
`{"aggregate": SliceAggregate(...)}` into the return dict but does not
explicitly list `aggregate` as a state-key addition. For LangGraph to
route that write back onto the parent state (and for T05's
strict-review gate to read the aggregate), the channel has to be
declared on `SliceRefactorState` with a scalar type. Added as a
bare `SliceAggregate` (no reducer) because only the single aggregator
node writes it — no fan-out. Downstream T05 / T06 are direct readers.
**Net:** a 1-line state-schema extension that makes the spec's return
shape wire correctly.

### Addition — `SliceBranchState.slice_failures` channel
**Why it's justified.** The `SliceBranchState` TypedDict needs
`slice_failures: Annotated[list[SliceFailure], operator.add]` declared
for LangGraph's sub-graph-to-parent propagation to carry the branch's
failure write back to the parent's reducer (the T03 lesson —
"LangGraph propagates sub-graph keys back to the parent only when the
parent declares the same channel"). Without this declaration, the
branch's `slice_branch_finalize` write would land on the branch state
and silently not reach the parent. Directly implements AC-3.

### Addition — `_slice_branch_finalize` node
**Why it's justified.** The T04 spec calls it out explicitly as the
T04 owner's deliverable:

> The error-handler wrap around the worker→validator pair (from T03's
> NonRetryable surfacing) converts exhausted slices into SliceFailure
> rows. **If T03 did not already wire this conversion, T04 owns it**
> — the aggregator needs the failure rows in state, not as unhandled
> exceptions.

T03 did not wire a per-branch conversion — it merely surfaced the
`NonRetryable` classification onto the branch's `last_exception`.
`_slice_branch_finalize` reads that, emits the `SliceFailure` row,
and keeps happy-path branches as no-ops. This is the T04 owner's
scope by the spec's own handoff language.

### Addition — `retrying_edge.on_terminal = "slice_branch_finalize"` (re-target from `END`)
**Why it's justified.** Required by the above — the finalize node has
to be reachable from both the happy path (where validator returns
`slice_results`) and the exhausted path (where `last_exception` is
NonRetryable). Routing both through the same node keeps the sub-graph
terminal unconditional (single `add_edge(slice_branch_finalize, END)`)
and avoids a second conditional edge.

### Addition — 2 bare-type regression-guard tests
**Why it's justified.** T04 introduces two new pydantic models; the
project's KDR-010 / ADR-0002 invariant has to hold for both. Each
model gets one introspection test that walks every field and asserts
no numeric bound is set. Mirrors the M5 T02 pattern for
`ExplorerReport` / `PlannerPlan` regression guards.

### Addition — `test_aggregate_node_is_registered_as_real_function`
**Why it's justified.** Guards against a future refactor silently
reverting the outer graph's `aggregate` node back to a no-op
placeholder (the T02 / T03 shape). Introspects the compiled graph's
node list and confirms the `_aggregate` symbol is the bound callable.
Low-cost, high-value against drift.

### Addition — `test_aggregate_handles_empty_state` defensive regression
**Why it's justified.** Not strictly an AC, but the aggregator must
not crash on a state dict missing both reducer channels (e.g. a future
abort path that skips the fan-out entirely and routes directly to
`aggregate`). Asserts an empty `SliceAggregate(succeeded=[], failed=[],
total_slices=0)` comes back. Cost: three lines of test.

### Addition — `test_asyncio_event_loop_available`
**Why it's justified.** Pure defensive regression guard — protects the
suite against a future `pytest-asyncio` config regression that would
silently skip every `async def` test. Three lines; no coupling to T04
scope. **Net:** low-value but also zero maintenance cost; keep.

## Gate summary

| Gate | Result |
| - | - |
| `uv run pytest` | **409 passed, 2 skipped, 2 warnings in 13.45s** — 11 new T04 tests added on top of the 398-test T03 baseline; zero regressions across the 12 pre-existing test modules. |
| `uv run lint-imports` | **3 / 3 contracts kept** — `primitives cannot import graph, workflows, or surfaces KEPT`; `graph cannot import workflows or surfaces KEPT`; `workflows cannot import surfaces KEPT`. |
| `uv run ruff check` | **All checks passed!** |

## Issue log — cross-task follow-up

| ID | Severity | Status | Owner / next touch point | One-line |
| --- | --- | --- | --- | --- |
| M6-T04-ISS-01 | 🟢 LOW | ✅ RESOLVED (M6 T07 Builder, 2026-04-20) | — | Option 1 landed: `_route_before_aggregate` reads `len(slice_failures) >= 2`; `_merge_non_retryable_failures` docstring updated; pinned by 2 dedicated + 15 adjacent hard-stop tests. |

## Propagation status

- [x] M6-T04-ISS-01 → `design_docs/phases/milestone_6_slice_refactor/task_07_concurrency_hard_stop.md` — carry-over appended **and resolved** in T07 Builder (2026-04-20). T07's carry-over checkbox ticked with ✅ RESOLVED annotation citing test names.

## Deferred to `nice_to_have`

None.
