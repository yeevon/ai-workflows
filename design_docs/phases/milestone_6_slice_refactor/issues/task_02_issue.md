# Task 02 — Parallel Slice-Worker Pattern — Audit Issues

**Source task:** [../task_02_parallel_slice_worker.md](../task_02_parallel_slice_worker.md)
**Audited on:** 2026-04-20
**Audit scope:** `ai_workflows/workflows/slice_refactor.py`, `ai_workflows/workflows/_dispatch.py`, `ai_workflows/mcp/server.py`, `tests/workflows/test_slice_refactor_fanout.py`, `tests/workflows/test_slice_refactor_planner_subgraph.py`, `tests/mcp/test_cancel_run_inflight.py`, `CHANGELOG.md`, architecture.md §4.3 / §8.6 / §8.7, KDR-001 / KDR-003 / KDR-004 / KDR-006 / KDR-009 / KDR-010, ADR-0002, and every gate command.
**Status:** ✅ PASS — every AC met (one documented spec-deviation on `durability` placement, one spec-sanctioned forward-defer to T03 for the validator pairing). Full gate green (392 passed / 2 skipped; 3 / 3 import contracts kept; ruff clean).

## Design-drift check

Cross-referenced the patch against [architecture.md](../../../architecture.md) §3 / §4.3 / §6 / §8.6 / §8.7 and KDR-001 / 003 / 004 / 006 / 009 / 010.

- **New dependencies:** none. No addition to `pyproject.toml` or `[tool.uv]`.
- **Layer discipline:** `ai_workflows/workflows/slice_refactor.py` imports from `ai_workflows.graph.*` and `ai_workflows.primitives.*`; `ai_workflows/workflows/_dispatch.py` was already touching those. `ai_workflows/mcp/server.py` imports only `ai_workflows.workflows._dispatch`, `ai_workflows.workflows`, and `ai_workflows.primitives.*`. `lint-imports` kept 3 / 3. No drift.
- **LLM call added — KDR-004 pairing:** `slice_worker` is a `tiered_node` call composed inline with a `SliceResult.model_validate_json` parse in `_build_slice_worker_node._composed`. A strict reading of KDR-004 (validator-after-every-LLM-node) would flag this as a skipped validator. **However**, the T02 spec itself ([task_02_parallel_slice_worker.md:18](../task_02_parallel_slice_worker.md#L18)) lists `slice_worker` as a `TieredNode` only and the T03 spec ([task_03_per_slice_validator.md:7](../task_03_per_slice_validator.md#L7)) explicitly owns "pair every `slice_worker` fan-out invocation with a `ValidatorNode` per KDR-004". The inline parse is a spec-sanctioned **carry-over into T03** — the worker closure will split into `tiered_node` (raw) + `ValidatorNode` (parsed) with `retrying_edge(on_semantic="slice_worker")`. Logged as **M6-T02-ISS-01 DEFERRED** below; propagated as explicit carry-over on T03's spec.
- **KDR-003 (no Anthropic API):** no `anthropic` import, no `ANTHROPIC_API_KEY` read. Tier registry routes `slice-worker` to `ollama/qwen2.5-coder:32b` via `LiteLLMRoute`; KDR-003 compliant.
- **KDR-006 (three-bucket retry taxonomy):** inline parse failure in `_build_slice_worker_node._composed` raises `NonRetryable`. Semantic-retry self-loop (per KDR-006) is correctly deferred to T03 (which lands `retrying_edge`). The three-bucket taxonomy is not violated today because the inline-parse branch is non-retryable by design (a schema mismatch is a logic error, not a transient one).
- **KDR-009 (SqliteSaver only):** no hand-rolled checkpoint writes; `durability="sync"` is threaded through at the `CompiledStateGraph.ainvoke` boundary. Compliant.
- **KDR-010 / ADR-0002 (bare-typed schemas):** `SliceResult` is bare-typed (`slice_id: str`, `diff: str`, `notes: str`) with `extra="forbid"`. No `Field(min_length/max_length)` bounds. Compliant.
- **architecture.md §4.3:** "`slice_refactor` — outermost DAG: planner sub-graph → per-slice worker nodes (parallel) → per-slice validator → aggregate → strict-review gate → apply". T02's implementation produces the first three segments (planner sub-graph → parallel workers → aggregate placeholder) with the validator deferred to T03 and the strict-review/apply segments deferred to T05/T06. Compliant with the milestone trajectory.
- **architecture.md §8.6 (concurrency):** `TierConfig(slice-worker, max_concurrency=1, per_call_timeout_s=180)` populates the per-provider semaphore slot. The workflow-wide semaphore enforcement is T07's scope; T02 just declares the tier.
- **architecture.md §8.7 (cancellation):** all five bullets covered. (1) `_ACTIVE_RUNS: dict[str, asyncio.Task]` in `ai_workflows/mcp/server.py`. (2) `durability="sync"` threaded at the `ainvoke` boundary (dispatch shim). (3) langgraph#5682 verification test in `tests/mcp/test_cancel_run_inflight.py::test_cancel_during_subgraph_propagates_to_tiered_node`. (4) ToolNode absence documented in the `slice_refactor` module docstring. (5) SQLite single-writer race covered by `tests/mcp/test_cancel_run_inflight.py::test_cancel_then_immediate_resume_does_not_surface_database_locked`.
- **Observability:** no Langfuse / OTel / LangSmith additions. `StructuredLogger` path unchanged.

No drift HIGH issues. Every addition beyond minimal spec is justified inline (parallel-safe retry-slot reducers, durability placement correction, ToolNode absence docstring).

## Acceptance-criteria grading

| AC | Grade | Notes |
| --- | --- | --- |
| 1. `SliceSpec → SliceResult` worker tier registered; `slice-worker` routes to Qwen via Ollama by default. | ✅ PASS | `slice_refactor_tier_registry()` composes planner tiers with `slice-worker → LiteLLMRoute("ollama/qwen2.5-coder:32b", api_base="http://localhost:11434")`. Asserted in `test_slice_refactor_tier_registry_composes_planner_and_slice_worker`. |
| 2. Fan-out via LangGraph `Send`; merge via `Annotated[list[SliceResult], operator.add]` reducer; no hand-rolled merge node. | ✅ PASS | `_fan_out_to_workers` returns `[Send("slice_worker", …) for s in slice_list]`; state annotation `slice_results: Annotated[list[SliceResult], operator.add]`. Asserted in `test_slice_results_reducer_annotation_uses_operator_add` + `test_fan_out_invokes_one_worker_per_slice_and_merges` + `test_operator_add_accumulates_across_sequential_writes`. |
| 3. `build_slice_refactor()` compiles with `durability="sync"`. | ✅ PASS **(spec-deviation, documented)** | LangGraph 1.x exposes `durability` on `CompiledStateGraph.ainvoke`, not on `StateGraph.compile`. Verified via `inspect.signature(StateGraph.compile)` — accepts only `checkpointer / cache / store / interrupt_before / interrupt_after / debug / name`. The flag is threaded through `ai_workflows/workflows/_dispatch.py::run_workflow` + `resume_run` at every `await compiled.ainvoke(...)` site. Regression guard: `test_dispatch_threads_durability_sync_through_ainvoke` pins the assumption that the flag stays on `ainvoke`. Deviation called out in module docstring + CHANGELOG. Functionally equivalent to the spec's literal compile-time wiring (last-completed-step checkpoint still lands in SQLite before `CancelledError` propagates). |
| 4. MCP server `_ACTIVE_RUNS: dict[str, asyncio.Task]`; `cancel_run` calls `task.cancel()` then M4 storage flip; unknown run_id falls back cleanly. | ✅ PASS | Registry defined at [`ai_workflows/mcp/server.py:80`](../../../../ai_workflows/mcp/server.py#L80); `run_workflow` wraps dispatch in `asyncio.create_task` and registers/pops; `cancel_run` calls `task.cancel()` first, then `storage.cancel_run`. Unknown-run fallback asserted in `test_cancel_run_unknown_inflight_falls_back_to_storage_only`. |
| 5. Sub-graph mid-execution cancel test green; langgraph#5682 verification documented. | ✅ PASS | `test_cancel_during_subgraph_propagates_to_tiered_node` waits for `call_count >= 1` (ensures the explorer LLM call is in-flight inside the planner sub-graph) before delivering `inflight_task.cancel()`. Asserts `call_count == 1` post-cancel (sub-graph did not advance past the first LLM node). |
| 6. ToolNode-absence documented in module docstring (langgraph#6726 not reachable). | ✅ PASS | "ToolNode absence" section in the `slice_refactor` module docstring explicitly cites langgraph#6726 and defers any future ToolNode guard to the task that introduces ToolNode. |
| 7. Cancel-then-immediate-resume test green; no caller-visible `database is locked`. | ✅ PASS | `test_cancel_then_immediate_resume_does_not_surface_database_locked` explicitly re-raises `sqlite3.OperationalError` through `pytest.fail` if the race surfaces; `ToolError("cancelled")` is the expected path. |
| 8. Fan-out tests green (3-slice, 1-slice, reducer accumulation). | ✅ PASS | 9 / 9 in `tests/workflows/test_slice_refactor_fanout.py`. 3-slice invokes the adapter 4× (1 explorer + 3 workers); 1-slice invokes 2× (1 explorer + 1 worker); reducer accumulates across sequential writes. |
| 9. `uv run pytest` green on the full suite. | ✅ PASS | 392 passed, 2 skipped, 2 warnings (pre-existing yoyo DeprecationWarning). |
| 10. `uv run lint-imports` 3 / 3 kept. | ✅ PASS | `primitives cannot import graph, workflows, or surfaces KEPT` / `graph cannot import workflows or surfaces KEPT` / `workflows cannot import surfaces KEPT`. |
| 11. `uv run ruff check` clean. | ✅ PASS | `All checks passed!` |

Carry-over ACs (from task spec §"Carry-over from prior audits"):

| Carry-over AC | Grade | Notes |
| --- | --- | --- |
| Process-local `dict[run_id, asyncio.Task]` in MCP server; `task.cancel()` + M4 storage flip. | ✅ PASS | AC-4 above. |
| `durability="sync"` graph wiring. | ✅ PASS **(invoke-boundary, documented)** | AC-3 above. |
| Sub-graph cancellation verified against langgraph#5682. | ✅ PASS | AC-5 above. |
| ToolNode absence documented (langgraph#6726 not reachable). | ✅ PASS | AC-6 above. |
| SQLite single-writer race accepted (LangGraph built-in retry on `database is locked`). | ✅ PASS | AC-7 above. |

## 🔴 HIGH — none

## 🟡 MEDIUM — none (KDR-004 deferral below is **LOW** because T02's spec + T03's spec jointly authorise the split)

## 🟢 LOW — 1 forward-deferred item

### M6-T02-ISS-01 — Inline `SliceResult` parse in `_build_slice_worker_node` is a T02 shortcut; T03 must refactor into `ValidatorNode` + `retrying_edge`

**Status:** ✅ RESOLVED in M6 T03 Builder (2026-04-20). Confirmed in [task_03_issue.md](task_03_issue.md) line 43 (AC grading) + line 98 (dedicated carry-over section). Worker split into `slice_worker` (raw) + `slice_worker_validator` (`ValidatorNode`) + `retrying_edge(on_semantic="slice_worker")` per KDR-004; scalar-channel scoping confirmed under `Send` + per-branch sub-chain.

**Severity:** 🟢 LOW — spec-sanctioned forward-defer. KDR-004 requires a paired `ValidatorNode` after every LLM node; T03's AC-1 already owns that pairing. T02's inline parse exists because T02's AC-2 requires `slice_results` to be populated (for the reducer demonstration) and T02 does not land the validator. The shortcut is isolated to a single closure (`_build_slice_worker_node._composed`) so the T03 refactor is mechanical.

**File:** [`ai_workflows/workflows/slice_refactor.py:345-405`](../../../../ai_workflows/workflows/slice_refactor.py#L345-L405) — `_build_slice_worker_node`.

**Action / Recommendation (M6 T03 Builder):**
1. Drop the inline `SliceResult.model_validate_json(text)` and the `slice_results: [parsed]` write from `_build_slice_worker_node._composed`.
2. Split `slice_worker` back into a plain `tiered_node(tier="slice-worker", output_schema=SliceResult, node_name="slice_worker")` that writes `slice_worker_output` only.
3. Add a sibling `slice_worker_validator` node (a `ValidatorNode(output_schema=SliceResult)`) that reads `slice_worker_output` and writes into `slice_results`.
4. Wire `retrying_edge(on_semantic="slice_worker", on_transient="slice_worker")` with `max_semantic_attempts=3` per architecture.md §8.2.
5. Re-examine the `slice_worker_output` scalar channel: the T02 closure deliberately omitted it from the outer return dict because N parallel workers writing conflicting text values trips `InvalidUpdateError`. After the split, each `Send`'s sub-chain (`worker → validator`) runs sequentially within the per-slice branch, so the raw output only needs to survive the worker→validator hop. Confirm LangGraph's `Send` semantics scope the scalar to the per-branch sub-graph; if not, add an `Annotated[..., _take_last]` reducer or key the per-slice output by `slice_id` (e.g. `slice_worker_output: Annotated[dict[str, str], operator.or_]`).
6. Tests: per T03 spec's §"Tests" block — happy-path reducer, per-slice semantic retry (sibling slices not re-run), per-slice transient retry, semantic-exhaustion surfacing `NonRetryable`, KDR-004 regression grep (every `slice-worker` tier node has a downstream `slice_worker_validator`).

**Propagation:** appended as carry-over on T03's spec below (see Propagation status footer).

## Additions beyond spec — audited and justified

1. **Parallel-safe retry-slot reducers (`_merge_last_exception`, `_merge_retry_counts`, `_merge_non_retryable_failures`).** The T02 spec does not prescribe them, but LangGraph's default last-writer-wins channels raise `InvalidUpdateError: Can receive only one value per step` when N parallel workers all write `{"last_exception": None}` (a `tiered_node` success-path clear from M6 T01 carry-over). Three reducers land on `SliceRefactorState`: prefer-non-None for `last_exception` (a failing worker must not be silently cleared by a sibling's success), shallow-merge-with-max for `_retry_counts` (workers bump disjoint node-name keys under T02 fan-out), and `max` for `_non_retryable_failures` (same-pre-invocation-read-would-inflate logic). Sequential degeneration is documented in each reducer's docstring and asserted in `test_slice_results_reducer_annotation_uses_operator_add` via the `Annotated` introspection.

2. **`slice_worker_output` deliberately omitted from `_build_slice_worker_node._composed`'s outer return dict.** Without the omission, the 3-parallel-worker test blows up with `InvalidUpdateError` on a scalar (non-Annotated) state key. The raw text is consumed in-closure by the inline parse; only `slice_results` (reducer-backed) needs to cross the Send/reduce boundary. Justified inline in the closure body with a 10-line comment explaining the invariant and forward-referencing T03's refactor. Removed once T03 splits the closure (scalar channel lives inside the per-branch sub-chain).

3. **`test_dispatch_threads_durability_sync_through_ainvoke` regression guard.** Asserts via `inspect.signature(CompiledStateGraph.ainvoke)` that `durability` remains a kwarg on `ainvoke`. If a future LangGraph release promotes the flag back to `compile`, this test fails loud and the dispatch shim can be updated. Cheaper than waiting for a cancel-resume regression in CI.

4. **Docstring cross-reference between `_build_slice_worker_node` and `SliceRefactorState`.** Both docstrings forward-reference T03's refactor so a future Builder opening either symbol in isolation sees the plan. No functional impact.

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 392 passed, 2 skipped (`test_cancel_run_inflight.py` alone: 5 / 5; `test_slice_refactor_fanout.py`: 9 / 9; `test_slice_refactor_planner_subgraph.py`: 12 / 12). |
| `uv run lint-imports` | ✅ 3 / 3 contracts kept. |
| `uv run ruff check` | ✅ All checks passed. |
| KDR-003 grep (`anthropic` import / `ANTHROPIC_API_KEY` read) | ✅ None in `slice_refactor.py`, `_dispatch.py`, `mcp/server.py`. |
| KDR-009 grep (hand-rolled checkpoint writes) | ✅ None. All durability goes through LangGraph's `AsyncSqliteSaver` + `durability="sync"`. |
| Architecture.md §8.7 coverage | ✅ All five bullets implemented + tested. |

## Issue log — cross-task follow-up

| ID | Severity | Status | Owner | Description |
| --- | --- | --- | --- | --- |
| M6-T02-ISS-01 | 🟢 LOW | ✅ RESOLVED (M6 T03 Builder, 2026-04-20) | — | Refactor landed in T03: `slice_worker` (raw `tiered_node` writing `slice_worker_output`) + `slice_worker_validator` (`ValidatorNode(output_schema=SliceResult)`) + `retrying_edge(on_semantic="slice_worker")`; scalar channel scoped to per-branch sub-chain per architecture.md §8.2. See [task_03_issue.md](task_03_issue.md) §"Carry-over from prior audits". |

## Deferred to nice_to_have

None triggered by this task.

## Propagation status

| Issue ID | Target | Propagated? |
| --- | --- | --- |
| M6-T02-ISS-01 | `design_docs/phases/milestone_6_slice_refactor/task_03_per_slice_validator.md` → §"Carry-over from prior audits" | ✅ Appended as a carry-over entry, resolved in M6 T03 Builder (2026-04-20), and flipped `DEFERRED → RESOLVED` in this originating file during M6 T09 close-out audit. |
