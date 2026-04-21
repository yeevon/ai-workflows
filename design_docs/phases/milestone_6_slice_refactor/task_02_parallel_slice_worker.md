# Task 02 — Parallel Slice-Worker Pattern

**Status:** 📝 Planned.

## What to Build

Implement the fan-out → per-slice worker → merge pattern in `slice_refactor`. After [T01](task_01_slice_discovery.md)'s `slice_list_normalize` produces `list[SliceSpec]`, fan out one worker invocation per slice via LangGraph's `Send` API; each worker is a `TieredNode` that produces a `SliceResult`; results are merged back into the parent state by a reducer on the `slice_results: Annotated[list[SliceResult], operator.add]` key.

This task also folds in **M4-T05's deferred in-flight `cancel_run` carry-over** (see [milestone README §Carry-over](README.md)) because the compile flags + cancellation wiring sit on the same code path as the parallel fan-out — both are per-run runtime concerns owned by this task's graph build.

Aligns with [architecture.md §4.3](../../architecture.md) (parallel slice workers), [§8.6](../../architecture.md) (concurrency semaphore — consumed here, enforcement tested in [T07](task_07_concurrency_hard_stop.md)), [§8.7](../../architecture.md) (in-flight cancellation), KDR-001 (LangGraph owns parallelism), KDR-009 (sync checkpoint durability).

## Deliverables

### `ai_workflows/workflows/slice_refactor.py` — fan-out + worker + merge

- `SliceResult` pydantic model (co-located): `slice_id: str`, `diff: str`, `notes: str`. Bare-typed per KDR-010 / ADR-0002 — no `Field(min_length/max_length/...)` bounds, `extra="forbid"` retained.
- `slice_worker` — `TieredNode` against a new `slice-worker` logical tier (add to `slice_refactor_tier_registry()`; route at `LiteLLMRoute(model="ollama/qwen2.5-coder:32b")` by default, same shape as the planner explorer tier — Qwen local is the cost-free default, override path ships via the existing tier-override surface from [M5 T04](../milestone_5_multitier_planner/task_04_tier_override_cli.md)).
- Fan-out edge: conditional edge from `slice_list_normalize` returning `[Send("slice_worker", {"slice": s}) for s in state["slice_list"]]`.
- Merge: `slice_results` is an `Annotated[list[SliceResult], operator.add]` state key — LangGraph's built-in list-accumulator reducer. No hand-rolled merge node; merging happens at state-update time.
- Exit fan-out into the aggregator ([T04](task_04_aggregator.md)) — T02 lands the incoming edge as `slice_worker → aggregator`, but the aggregator node itself is a one-line passthrough placeholder until T04.

### Compile flags for durability + cancellation ([architecture.md §8.7](../../architecture.md))

`build_slice_refactor()` compiles the graph with `durability="sync"`:

```python
graph.compile(
    checkpointer=build_checkpointer(),
    durability="sync",
)
```

Rationale: LangGraph's default `"async"` durability can drop the last step's checkpoint on `CancelledError`; `"sync"` guarantees the last-completed-step checkpoint hits SQLite before the cancellation unwinds. This is load-bearing for the cancel-and-immediately-resume path.

### In-flight `cancel_run` wiring (carry-over from M4 T05)

**MCP server** (`ai_workflows/mcp/server.py`) gains a process-local active-task registry:

```python
_ACTIVE_RUNS: dict[str, asyncio.Task] = {}
```

- `run_workflow` tool: wrap the dispatch call in an `asyncio.create_task(...)`, store it under `run_id`, `await` it, pop on completion (success, failure, or cancel).
- `cancel_run` tool: look up the task, call `task.cancel()`, then perform the existing M4 storage-level status flip. If the `run_id` is not in `_ACTIVE_RUNS`, fall back to the M4 storage-only behaviour (the run was already paused at a gate or completed in another process — no in-flight task to cancel).
- The registry is process-local and best-effort; the architectural contract is *"the storage flip is authoritative; the task cancel is a best-effort nicety"*.

**Subgraph cancellation verification** — `slice_refactor` composes the `planner` sub-graph (T01). Add a hermetic test that explicitly exercises [langgraph#5682](https://github.com/langchain-ai/langgraph/issues/5682): start a `slice_refactor` run, cancel it while the sub-graph is mid-execution (before the gate), assert the sub-graph's `TieredNode` receives the `CancelledError` (not "keeps running until its own interrupt"). If the current LangGraph version does not propagate subgraph cancellation correctly, document the version gap in a comment + issue-file note; do **not** hand-roll a propagation shim.

**ToolNode guard** — T02's workers do **not** use `ToolNode` (they are plain `TieredNode` calls). Document this explicitly in the module docstring: *"No `ToolNode` usage in M6; [langgraph#6726](https://github.com/langchain-ai/langgraph/issues/6726) (mid-tool-call cancel leaves `AIMessage.tool_calls` unpaired with `ToolMessage`) is not reachable from this workflow's code path."* If a future task adds `ToolNode`, it owns the guard.

**SQLite write race** — cancelled task's final checkpoint write vs an immediate re-run on the same `thread_id`: SQLite's single-writer lock serialises them; the re-run retries on `database is locked` (LangGraph's `SqliteSaver` already handles this). Test: launch a cancellation immediately followed by a resume on the same `run_id` and assert the resume completes without a `database is locked` surfacing to the caller.

### Tests

`tests/workflows/test_slice_refactor_fanout.py` (new):

- Hermetic happy path: 3-slice fixture → 3 worker invocations (asserted via stub adapter call log) → `slice_results` state has 3 rows in the original slice order (or any stable order — pin whichever LangGraph provides).
- Single-slice edge case: 1-slice fixture → 1 worker invocation → `slice_results` has 1 row.
- Reducer shape: two fan-out batches in sequence do not clobber — `operator.add` accumulates correctly.
- `durability="sync"` compile — snapshot the compiled graph's checkpointer config and assert the flag is set (or the equivalent introspection LangGraph exposes).

`tests/mcp/test_cancel_run_inflight.py` (new):

- Start a `slice_refactor` run via the MCP `run_workflow` tool in-process; stub workers sleep for a few hundred ms; call `cancel_run(run_id)`; assert (a) `runs.status == "cancelled"`, (b) the `asyncio.Task` is cancelled (`task.cancelled() is True`), (c) the checkpointer has a row for the last-completed step (not an empty checkpoint — verifies `durability="sync"` did its job).
- Subgraph-mid-execution cancel: cancel while inside the planner sub-graph; assert the sub-graph unwinds.
- `cancel_run` for an unknown `run_id` in `_ACTIVE_RUNS` falls back to the M4 storage-flip path cleanly (no `KeyError`).
- Resume-after-cancel refused: `resume_run(cancelled_id)` surfaces the M4 `ResumePreconditionError` → `ToolError` path.
- Immediate resume on same `thread_id` after cancel completes without surfacing `database is locked` to the caller.

## Acceptance Criteria

- [ ] `SliceSpec → SliceResult` worker tier registered; `slice-worker` routes to Qwen via Ollama by default.
- [ ] Fan-out via LangGraph `Send`; merge via `Annotated[list[SliceResult], operator.add]` reducer; no hand-rolled merge node.
- [ ] `build_slice_refactor()` compiles with `durability="sync"`.
- [ ] MCP server maintains a process-local `_ACTIVE_RUNS: dict[str, asyncio.Task]`; `cancel_run` calls `task.cancel()` then performs the M4 storage flip; unknown `run_id` falls back cleanly.
- [ ] Subgraph-mid-execution cancel test green; langgraph#5682 verification documented in the test or issue file.
- [ ] ToolNode-absence documented in the module docstring (langgraph#6726 not reachable).
- [ ] Cancel-then-immediate-resume test green (SQLite single-writer race handled by LangGraph's built-in retry; no caller-visible `database is locked`).
- [ ] Fan-out tests green (3-slice, 1-slice, reducer accumulation).
- [ ] `uv run pytest` green on the full suite (no regressions).
- [ ] `uv run lint-imports` 3 / 3 kept.
- [ ] `uv run ruff check` clean.

## Dependencies

- [Task 01](task_01_slice_discovery.md) — `slice_list` state key populated.
- [M5](../milestone_5_multitier_planner/README.md) — tier-override surface exists at both CLI and MCP; `slice-worker` downshift routes through the same plumbing.

## Carry-over from prior audits

- [ ] **M4-T05-CARRY / in-flight `cancel_run`** (owner: M6 T02): process-local `dict[run_id, asyncio.Task]` in MCP server; `task.cancel()` + M4 storage flip; `durability="sync"` graph compile; subgraph cancellation verified against langgraph#5682; ToolNode absence documented (langgraph#6726 not reachable); SQLite single-writer race accepted (LangGraph's built-in retry on `database is locked`). Source: [milestone README carry-over section](README.md), [architecture.md §8.7](../../architecture.md).
