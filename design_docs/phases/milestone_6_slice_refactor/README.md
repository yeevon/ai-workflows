# Milestone 6 — `slice_refactor` DAG

**Status:** 📝 Planned. Starts once [M5](../milestone_5_multitier_planner/README.md) closes clean.
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

## Issues

Land under [issues/](issues/).

## Carry-over from prior milestones

- [ ] **M4 T05 — in-flight `cancel_run` (MEDIUM, owner: M6 — natural fit: task 02 parallel slice-worker, or a dedicated cancellation task if the wiring grows).**
  M4 ships `cancel_run` as a storage-level flip only ([architecture.md §8.7](../../architecture.md) — covers the "cancel a paused-at-gate run" case, which is the dominant planner use). M6 is the first milestone where a run's in-flight wall-clock time (parallel per-slice workers, minutes-not-seconds) makes mid-run abort a real UX requirement. Scope when M6 opens:
  - MCP server holds a process-local `dict[run_id, asyncio.Task]` for active runs; `cancel_run` looks the task up and calls `task.cancel()` alongside the existing storage status flip.
  - Compiled graph runs with `durability="sync"` so the last-completed-step checkpoint is on disk before the `CancelledError` propagates.
  - Verify subgraph cancellation against [langgraph#5682](https://github.com/langchain-ai/langgraph/issues/5682) — the parent-cancels-but-subgraph-ReAct-keeps-running case; `slice_refactor` composes the `planner` sub-graph so this path is live.
  - Any `ToolNode`-using worker guards against [langgraph#6726](https://github.com/langchain-ai/langgraph/issues/6726) (mid-tool-call cancel leaves `AIMessage.tool_calls` unpaired with a `ToolMessage`; next LLM call fails `INVALID_CHAT_HISTORY`).
  - SQLite single-writer race between cancelled-task's final write and an immediate re-run on the same `thread_id` is acceptable (retry on `database is locked`).
  Source: [architecture.md §8.7](../../architecture.md) · M4 T05 spec (generated at M4 start).
