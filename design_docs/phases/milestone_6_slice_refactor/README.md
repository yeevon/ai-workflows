# Milestone 6 — `slice_refactor` DAG

**Status:** ✅ Complete (2026-04-20).
**Grounding:** [architecture.md §4.3](../../architecture.md) · [roadmap.md](../../roadmap.md).

## Goal

Ship the canonical use-case workflow: `planner` sub-graph → parallel per-slice workers → per-slice validator → aggregate → strict-review `HumanGate` → apply. Proves LangGraph parallelism, strict-review semantics, and the full artefact lifecycle.

## Exit criteria

1. `ai_workflows.workflows.slice_refactor` exports a `StateGraph` with the shape above.
2. Per-slice worker fan-out runs bounded by the per-provider semaphore from `TierConfig` ([architecture.md §8.6](../../architecture.md)).
3. Strict-review gate holds the run indefinitely; only `aiw resume --gate-response approve|reject` clears it.
4. Double-failure hard-stop works: two distinct per-slice failures abort the run regardless of sibling independence ([architecture.md §8.2](../../architecture.md)).
5. Apply node writes artefacts to `Storage` and the run is marked complete.
6. End-to-end smoke test on a fixture slice list.
7. Gates green.

## Non-goals

- Applying artefacts to a real repo via subprocess (post-M6; treat the `apply` node as writing to `Storage` only here).
- Advanced concurrency tuning beyond the existing `TierConfig` semaphore.

## Key decisions in effect

| Decision | Reference |
| --- | --- |
| Validator after every LLM node | KDR-004 |
| 3-bucket retry taxonomy, graph-level routing | KDR-006 |
| Double-failure hard-stop | [architecture.md §8.2](../../architecture.md) |
| Strict-review no-timeout | [architecture.md §8.3](../../architecture.md) |

## Task order

| # | Task |
| --- | --- |
| 01 | Slice-discovery phase (reuses `planner` sub-graph output as slice list) |
| 02 | Parallel slice-worker node pattern (fan-out + merge) |
| 03 | Per-slice validator wiring |
| 04 | Aggregator node |
| 05 | Strict-review `HumanGate` wiring |
| 06 | `apply` node (writes artefacts to `Storage`) |
| 07 | Concurrency semaphore wiring + double-failure hard-stop test |
| 08 | End-to-end smoke test on fixture slice list |
| 09 | Milestone close-out |

Per-task files generated once M5 closes.

## Outcome (2026-04-20)

Every exit criterion verified end-to-end against real providers. M6 is the first milestone to exercise LangGraph's `Send` fan-out, `operator.add` state reducers, strict-review gates, cross-slice hard-stop semantics, and the per-tier semaphore — contracts from [architecture.md §8.2](../../architecture.md), [§8.3](../../architecture.md), and [§8.6](../../architecture.md) that the single-step M3/M5 planners could not reach.

- **Slice-discovery phase** ([task 01](task_01_slice_discovery.md)) — planner composed as a sub-graph via `build_planner().compile()`; `_slice_list_normalize` converts `PlannerPlan.steps` into the fan-out input list. Module-level `TERMINAL_GATE_ID`, `FINAL_STATE_KEY`, and `initial_state` hooks resolve the `T01-CARRY-DISPATCH-GATE` / `T01-CARRY-DISPATCH-COMPLETE` carry-overs (handled in T05 + T06).
- **Parallel slice-worker pattern** ([task 02](task_02_parallel_slice_worker.md)) — `Send(...)`-based fan-out with an `Annotated[list[SliceResult], operator.add]` reducer on the `slice_results` state key. Compiled with `durability="sync"` threaded through `_dispatch.run_workflow` / `resume_run`. `_ACTIVE_RUNS` task registry + `task.cancel()` wiring in the MCP `cancel_run` tool delivers the **M4 T05** in-flight-cancel carry-over.
- **Per-slice validator wiring** ([task 03](task_03_per_slice_validator.md)) — KDR-004 honoured across every fan-out branch; `_slice_worker_validator` escalates `RetryableSemantic → NonRetryable` on `max_attempts - 1` (resolves `M6-T03-ISS-01` in T07). Per-slice retry state is isolated so a transient failure on slice N does not poison slice M.
- **Aggregator node** ([task 04](task_04_aggregator.md)) — `_aggregate` folds `slice_results` + `slice_failures` into a single `SliceAggregate` for the gate payload. Partial-failure capture works (N-of-M successes with the rest surfaced in `failed`). `_merge_non_retryable_failures` docstring pins the "reliable only under sequential writes" caveat that motivated the T07 routing on `slice_failures` instead of the `max`-reduced counter.
- **Strict-review gate** ([task 05](task_05_strict_review_gate.md)) — first `strict_review=True` use in the codebase; no-timeout semantics verified (`timeout_s` and `default_response_on_timeout` both `None` in the interrupt payload). `_route_on_gate_response` raises `NonRetryable` on missing / bogus responses.
- **Apply node** ([task 06](task_06_apply_node.md)) — `_apply` writes one `artifacts` row per succeeded `SliceResult` via `SQLiteStorage.write_artifact`, keyed `slice_result:<slice_id>`. Reject path writes nothing (gate log is the audit trail). Idempotent on re-invocation via the `(run_id, kind)` PK's `ON CONFLICT DO UPDATE`. No subprocess, no filesystem write — architecture §4.3 "writing to Storage, not to disk" discipline kept.
- **Concurrency semaphore + double-failure hard-stop** ([task 07](task_07_concurrency_hard_stop.md)) — architecture §8.6 proven under fan-out: `_build_semaphores(tier_registry)` builds one `asyncio.Semaphore(max_concurrency)` per tier per run, threaded on `config["configurable"]["semaphores"]` into every `TieredNode` invocation. Per-tier, per-run, process-local. §8.2 hard-stop proven: `_route_before_aggregate` routes to `_hard_stop` when `len(slice_failures) >= 2`, bypassing aggregator + gate + apply. `runs.status = "aborted"` is a new terminal status distinct from `gate_rejected` and `cancelled`.
- **End-to-end smoke** ([task 08](task_08_e2e_smoke.md)) — hermetic sibling (`tests/workflows/test_slice_refactor_e2e.py`, 3 tests, always runs) + `AIW_E2E=1`-gated live sibling (`tests/e2e/test_slice_refactor_smoke.py`) + manual walkthrough ([manual_smoke.md](manual_smoke.md)). Live run recorded in the T09 close-out CHANGELOG entry.
- **Manual verification** — `aiw-mcp` → fresh Claude Code session → `run_workflow(workflow_id="slice_refactor", …)` → approve planner gate → approve strict-review gate → `status="completed"` with a 3-step plan. Full transcript in the T09 close-out CHANGELOG.
- **Green-gate snapshot:** 475 passed + 3 skipped under `uv run pytest` (live-e2e skips without `AIW_E2E=1`); `uv run lint-imports` 3/3 kept (`primitives → graph → workflows → surfaces`); `uv run ruff check` clean.

## Issues

Land under [issues/](issues/). Every M6 task issue file closed `✅ PASS`; three forward-deferred carry-overs resolved and flipped `DEFERRED → RESOLVED` in their originating issue files: `M6-T02-ISS-01` (inline-parse revert + channel scoping, resolved in T03 Builder — originating file flipped during T09 close-out audit), `M6-T03-ISS-01` (retrying-edge semantic-budget pattern, resolved in T07 Builder), and `M6-T04-ISS-01` (`_non_retryable_failures` reducer undercount, resolved in T07 Builder).

## Carry-over from prior milestones

- [x] **M4 T05 — in-flight `cancel_run` (MEDIUM, owner: [task 02](task_02_parallel_slice_worker.md)).** ✅ RESOLVED (landed in [task 02](task_02_parallel_slice_worker.md)). M6 T02 wired the `_ACTIVE_RUNS` process-local task registry in `ai_workflows/mcp/server.py`; `cancel_run` looks the task up and calls `task.cancel()` alongside the existing storage status flip. Graph compiled with `durability="sync"` so the last-completed-step checkpoint is on disk before `CancelledError` propagates. Sub-graph cancellation verified against the parent-cancels-but-subgraph-keeps-running case (`slice_refactor` composes the `planner` sub-graph, so the path is live). Original description retained below for audit trail.
  M4 ships `cancel_run` as a storage-level flip only ([architecture.md §8.7](../../architecture.md) — covers the "cancel a paused-at-gate run" case, which is the dominant planner use). M6 is the first milestone where a run's in-flight wall-clock time (parallel per-slice workers, minutes-not-seconds) makes mid-run abort a real UX requirement. [Task 02](task_02_parallel_slice_worker.md) owns the wiring because the compile flag + task-registry + subgraph-cancellation guards sit on the same code path as the parallel fan-out. Scope landed there:
  - MCP server holds a process-local `dict[run_id, asyncio.Task]` for active runs; `cancel_run` looks the task up and calls `task.cancel()` alongside the existing storage status flip.
  - Compiled graph runs with `durability="sync"` so the last-completed-step checkpoint is on disk before the `CancelledError` propagates.
  - Verify subgraph cancellation against [langgraph#5682](https://github.com/langchain-ai/langgraph/issues/5682) — the parent-cancels-but-subgraph-ReAct-keeps-running case; `slice_refactor` composes the `planner` sub-graph so this path is live.
  - Any `ToolNode`-using worker guards against [langgraph#6726](https://github.com/langchain-ai/langgraph/issues/6726) (mid-tool-call cancel leaves `AIMessage.tool_calls` unpaired with a `ToolMessage`; next LLM call fails `INVALID_CHAT_HISTORY`).
  - SQLite single-writer race between cancelled-task's final write and an immediate re-run on the same `thread_id` is acceptable (retry on `database is locked`).
  Source: [architecture.md §8.7](../../architecture.md) · M4 T05 spec (generated at M4 start).
