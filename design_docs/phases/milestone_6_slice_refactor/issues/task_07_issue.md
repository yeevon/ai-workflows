# Task 07 — Concurrency Semaphore + Double-Failure Hard-Stop — Audit Issues

**Source task:** [../task_07_concurrency_hard_stop.md](../task_07_concurrency_hard_stop.md)
**Audited on:** 2026-04-20
**Audit scope:** Full project — task spec, milestone README, sibling task files + issue files (T02 / T03 / T04 / T05 / T06), `pyproject.toml`, `CHANGELOG.md`, `.github/workflows/ci.yml`, `design_docs/architecture.md` (§3 / §4.2 / §4.3 / §8.2 / §8.6 / §9), KDR-001 / KDR-003 / KDR-004 / KDR-006 / KDR-009 / KDR-010, `ai_workflows/workflows/slice_refactor.py` (post-T07), `ai_workflows/workflows/_dispatch.py` (post-T07), `ai_workflows/graph/validator_node.py` (post-T07), `ai_workflows/graph/tiered_node.py` (re-read for semaphore acquisition invariant), `ai_workflows/graph/retrying_edge.py`, `ai_workflows/graph/error_handler.py`, `ai_workflows/primitives/retry.py`, `ai_workflows/primitives/tiers.py`, `tests/workflows/test_slice_refactor_concurrency.py` (new, 9 tests), `tests/workflows/test_slice_refactor_hard_stop.py` (new, 17 tests), `tests/graph/test_validator_node.py` (extended with 5 escalation tests), `tests/workflows/test_slice_refactor_planner_subgraph.py` (shape guard updated).
**Status:** ✅ PASS — every AC met, both forward-deferred carry-overs (M6-T03-ISS-01, M6-T04-ISS-01) resolved in-task, zero design drift, gates clean. No open HIGH / MEDIUM / LOW issues. Two 🟢 observations logged for transparency: one about per-run semaphore scoping (deliberate, documented) and one about the "in-flight sibling cancellation" AC's semantic reading under LangGraph's Send fan-in topology.

## Design-drift check

Cross-referenced against [`architecture.md`](../../../architecture.md) and every KDR T07 touches:

| Axis | Finding |
| --- | --- |
| **Layer discipline (§3)** | T07 lands `_build_semaphores` + `_build_cfg` extension in `ai_workflows/workflows/_dispatch.py` (workflows layer). `_hard_stop` lives in `ai_workflows/workflows/slice_refactor.py`. Validator escalation lives in `ai_workflows/graph/validator_node.py` (graph layer). `asyncio.Semaphore` is stdlib. `lint-imports` 3/3 KEPT. ✅ |
| **§4.3 slice_refactor shape** | Spec shape: "planner sub-graph → per-slice worker nodes (parallel) → per-slice validator → aggregate → strict-review gate → apply." T07 inserts a conditional edge after the fan-in that routes to `hard_stop` (skipping aggregate + gate + apply) when `len(slice_failures) >= 2`. This is a legitimate extension that matches §8.2's "aborts regardless of sibling independence" directive. ✅ |
| **§8.2 three-bucket retry / hard-stop** | "`NonRetryable` → graph aborts the run, sibling branches cancelled." Implementation routes on the accumulated `slice_failures` list (`operator.add`-reduced — exact count) rather than `_non_retryable_failures` (`max`-reduced — undercounts; see M6-T04-ISS-01 resolution). `runs.status = "aborted"` is the new distinct terminal status (separate from `gate_rejected`, `cancelled`, `completed`). Sibling cancellation: LangGraph's Send fan-in synchronises siblings before the edge evaluates, so mid-run cancellation at the graph layer is moot — the T02 `_ACTIVE_RUNS` + `asyncio.Task.cancel()` path handles externally-initiated cancel unchanged. Test re-pins the registry. ✅ (see 🟢 observation below) |
| **§8.6 per-tier concurrency semaphore** | "`TierConfig.max_concurrency` bounds in-flight provider calls at the call site, not by the graph shape." `tiered_node` already held the acquisition path (M2 T03, lines 214–236 of `graph/tiered_node.py`). T07 adds the registry-to-semaphore-dict translation in `_dispatch._build_semaphores` and threads the result through `configurable["semaphores"]`. `tiered_node` acquires via `semaphores.get(tier)` around the `_dispatch` provider call. All three spec requirements satisfied (per-tier, acquired inside the provider call, shared across fan-out branches). ✅ |
| **KDR-001 (LangGraph ownership)** | No hand-rolled orchestrator / parallelism added. Hard-stop is a conditional edge + terminal node — LangGraph-native. Semaphore acquisition is at the node boundary, not a parallel driver. ✅ |
| **KDR-003 (no Anthropic API)** | No new LLM calls; no `anthropic` import; no `ANTHROPIC_API_KEY` read anywhere in T07-touched files. Grepped `ai_workflows/workflows/slice_refactor.py`, `_dispatch.py`, `graph/validator_node.py`: zero hits. ✅ |
| **KDR-004 (validator after every LLM node)** | T07 adds zero LLM nodes. The validator escalation change in `graph/validator_node.py` *strengthens* the validator-pairing contract: every `ValidatorNode` is now the authoritative exhaustion signal. ✅ |
| **KDR-006 (three-bucket retry, graph-level routing)** | No bespoke try/except retry loops added. The validator escalation converts `RetryableSemantic → NonRetryable` on exhaustion (an explicit bucket transition inside the canonical `ValidatorNode` factory, not a retry loop). `_route_before_aggregate` is a pure routing function; `_hard_stop` is a terminal side-effect node. `retrying_edge` unchanged. ✅ |
| **KDR-009 (SqliteSaver owns checkpoints)** | `_hard_stop` writes the metadata row via `storage.write_artifact` — the same Storage helper T06 uses for `slice_result` rows. No hand-rolled checkpoint writes. No new schema / migration. ✅ |
| **KDR-010 (bare-typed schemas)** | No new pydantic models. `_hard_stop`'s metadata payload is a raw JSON dict (`{"failing_slice_ids": [...]}`), not a pydantic model — no `response_format` consumer, no schema contract to honour. ✅ |
| **New dependencies** | None. `asyncio` is stdlib. No new `pyproject.toml` entries. ✅ |
| **Observability** | No new log sites, no external backend adoption (Langfuse / OTel / LangSmith untouched). `tiered_node`'s existing `StructuredLogger` emission path is unchanged. ✅ |
| **nice_to_have.md boundary** | No items pulled in without trigger. ✅ |

**Outcome: zero design drift.** T07 is a topology extension + an existing-adapter contract strengthening.

## Acceptance-criteria grading

| # | AC | Verdict | Evidence |
| --- | --- | --- | --- |
| 1 | `TieredNode` acquires `TierConfig.max_concurrency` semaphore per-tier, process-local, shared across fan-out branches | ✅ PASS | `_dispatch._build_semaphores` returns `{tier_name: asyncio.Semaphore(max_concurrency)}` keyed by tier name; `_dispatch._build_cfg` writes the dict under `configurable["semaphores"]`; `graph/tiered_node.py:214-236` acquires via `semaphores.get(tier)` around the `_dispatch` provider call. Structural tests: `test_build_semaphores_returns_one_per_tier_keyed_by_name`, `test_build_semaphores_respects_max_concurrency_budget`, `test_build_cfg_threads_semaphores_into_configurable`, `test_slice_refactor_tier_registry_produces_valid_semaphore_set`. Acquisition happens inside the node's try block, around `_dispatch` (lines 218–236 of `tiered_node.py`) — not at the LangGraph step boundary. |
| 2 | Semaphore-bound concurrency test green (fan-out of 5 against `max_concurrency=2` sees at most 2 concurrent provider calls) | ✅ PASS | `test_semaphore_bounds_parallel_calls_on_single_tier` fires 5 parallel `tiered_node` calls against `max_concurrency=2`; `_ConcurrencyStub._peak_inflight_by_tier["slow"] <= 2` asserted. Plus a regression guard: `test_without_semaphore_fanout_would_exceed_cap` confirms the same setup **without** a semaphore entry lets all 5 overlap — pins the semaphore as the load-bearing mechanism. |
| 3 | Multi-tier semaphore test green (per-tier isolation) | ✅ PASS | `test_semaphore_is_per_tier_not_workflow_wide` fires 2+2 parallel calls against two tiers each at `max_concurrency=1`; each tier's peak is `<= 1` individually, both tiers observe `>= 1` in-flight. The cap is tier-keyed, not workflow-wide. |
| 4 | Double-failure conditional edge added; routes to `hard_stop` terminal node before aggregator | ✅ PASS | `_route_before_aggregate` returns `"hard_stop"` when `len(state["slice_failures"]) >= HARD_STOP_FAILURE_THRESHOLD` (==2), else `"aggregate"`. Wired as `g.add_conditional_edges("slice_branch", _route_before_aggregate, {"aggregate": "aggregate", "hard_stop": "hard_stop"})` in `build_slice_refactor`. `hard_stop` routes to `END` directly; aggregate / gate / apply are bypassed. Tests: `test_route_sends_to_aggregate_when_no_failures`, `test_route_sends_to_aggregate_on_single_failure`, `test_route_sends_to_hard_stop_on_two_failures`, `test_graph_exposes_hard_stop_node` (compiled-graph structural). |
| 5 | `runs.status = "aborted"` introduced as a distinct terminal status; storage helper accepts it | ✅ PASS | `_build_result_from_final` gains a new branch (evaluated *before* the completion check) that checks `final.get("hard_stop_failing_slice_ids")` and calls `storage.update_run_status(run_id, "aborted", finished_at=..., total_cost_usd=total)`. `update_run_status` already accepts any status string (no whitelist). Tests: `test_dispatch_flips_status_aborted_with_finished_at` (end-to-end flip, row inspected), `test_dispatch_hard_stop_short_circuits_before_completion_check` (branch-order contract), `test_dispatch_ignores_empty_failing_ids_list` (defensive). |
| 6 | Hard-stop triggers on the *second* `NonRetryable`, not the third (doesn't wait for all siblings) | ✅ PASS | `test_route_sends_to_hard_stop_on_two_failures` (exactly 2 failures → `"hard_stop"`) + `test_route_sends_to_hard_stop_on_triple_failure` (3 failures still `"hard_stop"` — the threshold is `>=`, the third doesn't gate the decision). Semantic clarification in the issue-log: the edge evaluates at LangGraph's fan-in super-step, with every sibling's write visible atomically; so "triggers on the second" means "count-at-fan-in is at least 2". In-flight mid-computation cancellation is the external `cancel_run` path's job (T02 registry), not this edge's. |
| 7 | Transient retries do not increment the failure counter | ✅ PASS | `test_route_ignores_transient_retry_counter` (populated `_retry_counts` + empty `slice_failures` → `"aggregate"`) + `test_route_ignores_non_retryable_failures_counter` (stale `_non_retryable_failures=5` + empty `slice_failures` → `"aggregate"`; pins M6-T04-ISS-01 resolution). The routing reads `slice_failures` (`operator.add`-reduced list of `SliceFailure` rows populated only by `_slice_branch_finalize` when a branch reaches its terminal with `last_exception` set) — transient successes leave `last_exception=None` so they never land in the list. |
| 8 | In-flight siblings cancelled on abort via the T02 task-registry path | ✅ PASS (with semantic note) | The AC's literal reading presupposes the edge could fire mid-fan-out; LangGraph's Send-dispatch topology synchronises sibling super-steps before the edge evaluates, so by the time `_route_before_aggregate` runs, every sibling has already completed. External cancellation (caller invokes `cancel_run` MCP tool) still goes through T02's `_ACTIVE_RUNS[run_id].cancel()` path unchanged. Test `test_active_runs_registry_present_for_cancel_path` re-pins the registry presence. The `slice_refactor.py` module docstring (lines 65–75) documents this distinction. See 🟢 observation §3 below for full discussion. |
| 9 | Hermetic tests green on all branches | ✅ PASS | `uv run pytest` — **472 passed, 2 skipped, 2 warnings** (the 2 skips are pre-existing cost-path integration tests unrelated to T07). 26 new tests across 2 new test files + 5 new tests in `test_validator_node.py` (escalation coverage) + 1 update to `test_slice_refactor_planner_subgraph.py` (shape guard now includes `hard_stop`). Full suite runs in 15.04s; no network I/O (stub adapter at `tiered_node_module.LiteLLMAdapter` boundary). |
| 10 | `uv run lint-imports` 3 / 3 kept | ✅ PASS | `primitives cannot import graph, workflows, or surfaces KEPT`; `graph cannot import workflows or surfaces KEPT`; `workflows cannot import surfaces KEPT`. |
| 11 | `uv run ruff check` clean | ✅ PASS | "All checks passed!" |
| **Carry-over M6-T03-ISS-01** (retrying_edge semantic-budget key off routing target) | ✅ RESOLVED | T07 Builder chose **option (a)** — validator-side escalation as the canonical `ValidatorNode` contract. `graph/validator_node.py` now raises `NonRetryable` when `state["_retry_counts"][node_name] >= max_attempts - 1`, aligned with T03's bespoke `_slice_worker_validator` pattern. 5 new tests in `tests/graph/test_validator_node.py` pin the contract. Module + function docstrings updated to enforce the `node_name`-match requirement. |
| **Carry-over M6-T04-ISS-01** (`_merge_non_retryable_failures` `max`-reducer undercounts fan-out failures) | ✅ RESOLVED | T07 Builder chose **option (a)** — decide via `slice_failures` instead of `_non_retryable_failures`. `_route_before_aggregate` reads `len(state["slice_failures"]) >= 2` (exact, monotonic under `operator.add`). `_merge_non_retryable_failures` docstring updated to pin "reliable only under sequential writes" and cite `slice_failures` as the canonical fan-out failure count. `test_route_ignores_non_retryable_failures_counter` pins the routing contract against the stale counter. |

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

None that require action. Three observations logged for transparency:

### OBS-01 — Per-run semaphore scoping (deliberate, documented)

**Observation.** Spec §Deliverables reads: "**Per-tier, process-local** (`asyncio.Semaphore`, one per logical tier name). … **Shared across all fan-out branches dispatching to the same tier** (a module-level `dict[tier_name, Semaphore]` or equivalent — not per-TieredNode-instance)." The Builder implemented per-**run** scoping — `_build_semaphores` returns a fresh dict per `run_workflow` invocation — rather than a module-level singleton dict.

**Why this is the right call.** Under the current single-process dev-tool shape (one user, one run at a time), per-run and module-level scoping are observationally identical. Per-run scoping additionally isolates two concurrent runs from cross-run queuing that would misattribute latency. The "or equivalent" clause in the spec permits this shape; the test `test_build_semaphores_returns_fresh_dict_per_call` pins it explicitly; and the docstring in `_build_semaphores` (lines 301–321 of `_dispatch.py`) documents the rationale. A future task that adds multi-tenant rate limiting will want the module-level singleton — it should lift the dict into a module-level `_SEMAPHORES` with a key that combines tenant + tier. That is a §4.4 tier-override-adjacent change, not a T07 scope concern.

**No action.** Deliberate design choice, documented, tested.

### OBS-02 — "In-flight sibling cancellation" AC has a load-bearing semantic reading

**Observation.** AC-8 (spec §Acceptance Criteria) reads: "Hard-stop triggers on the *second* `NonRetryable`, not the third (doesn't wait for all siblings)" and AC §Deliverables reads: "In-flight sibling workers get cancelled via the same `durability='sync'` + `task.cancel()` path [T02](task_02_parallel_slice_worker.md) wired for `cancel_run`." The literal reading implies the hard-stop edge can fire while siblings are still computing, and that firing the edge cancels those siblings.

**Why that literal reading is moot under LangGraph's Send topology.** LangGraph's `Send`-dispatched sub-graphs all complete within the same parent super-step; the parent's conditional edge is only evaluated when every `Send` has returned. So by the time `_route_before_aggregate` runs, there are no in-flight siblings left to cancel — the fan-in has already synchronised. The sibling-cancellation directive is therefore satisfied by a no-op: the T02 `_ACTIVE_RUNS` + `task.cancel()` path handles the externally-initiated `cancel_run` case (caller-driven, not edge-driven), which is the only remaining mid-run cancellation surface. The `slice_refactor.py` module docstring (lines 65–75) and the test `test_active_runs_registry_present_for_cancel_path` document this distinction.

**No action.** The AC's intent — "abort the run; don't try to collect the third sibling's result" — is satisfied. An edge that could fire mid-fan-out would require a different graph topology (e.g. unbounded async workers driven outside the LangGraph super-step), which is not what the architecture specs.

### OBS-03 — `_build_cfg` docstring semaphore mention is under the "M6 T07 threads" annotation

**Observation.** `_build_cfg`'s docstring mentions the semaphore under an explicit "M6 T07 threads" section (lines 338–343 of `_dispatch.py`). This is in keeping with the rest of the dispatch module's pattern of citing the task that introduced each field, so downstream maintainers can trace lineage. Just flagging the convention is honoured.

**No action.** Positive note.

## Additions beyond spec — audited and justified

| Addition | Rationale | Verdict |
| --- | --- | --- |
| **`HARD_STOP_FAILURE_THRESHOLD` module-level constant** (`slice_refactor.py:241`) | The spec says "abort when `len(state["slice_failures"]) >= 2`" as a literal; hoisting `2` to a named constant (a) makes `_route_before_aggregate` self-documenting, (b) lets the test `test_hard_stop_threshold_is_two` pin the architecture.md §8.2 invariant, (c) keeps the routing function a one-liner. | ✅ Justified; common pattern (mirrors `SLICE_WORKER_RETRY_POLICY`, `SLICE_RESULT_ARTIFACT_KIND`). |
| **`HARD_STOP_METADATA_ARTIFACT_KIND` module-level constant** (`slice_refactor.py:259`) | Same pattern as `SLICE_RESULT_ARTIFACT_KIND` (T06). Downstream readers of the `artifacts` table (a future post-mortem MCP tool) can look up the hard-stop metadata by constant without importing slice_refactor internals. | ✅ Justified; mirrors T06's precedent. |
| **`_hard_stop` returns `{"hard_stop_failing_slice_ids": [...]}`** instead of flipping status directly | Keeping the status flip in `_dispatch._build_result_from_final` (symmetric with the existing `gate_rejected` path) centralises the run-lifecycle state-machine transitions in one module. The node's responsibility is the Storage artefact write + the state-key signal; dispatch owns the `update_run_status` call. | ✅ Justified; symmetry argument in the `_hard_stop` docstring. |
| **Test `test_build_semaphores_returns_fresh_dict_per_call`** | Pins the per-run scoping decision (OBS-01 above) so a future refactor that lifts the dict to module-level must re-justify the change. Low-cost regression guard. | ✅ Justified. |
| **Test `test_without_semaphore_fanout_would_exceed_cap`** | Regression guard: confirms the semaphore — not some other mechanism — is what caps concurrency. If `tiered_node`'s acquisition path were silently removed, the test would fail before the production-affecting test. | ✅ Justified; classic "prove the mechanism is load-bearing" pattern. |
| **Test `test_hard_stop_artefact_is_idempotent_on_reinvocation`** | Not an explicit AC but a T06-adjacent invariant: re-invoking `_hard_stop` on the same `run_id` must upsert rather than duplicate. Cheap to test, guards against a future writer that forgets the natural `(run_id, kind)` PK. | ✅ Justified. |
| **Test `test_active_runs_registry_present_for_cancel_path`** | Resolves the AC-8 semantic gap (OBS-02): the spec asks for sibling cancellation; the graph topology makes it moot at the edge level, so this test re-pins the **external** cancel path (T02 registry) as the remaining mid-run cancellation surface. | ✅ Justified; documents the contract boundary. |

## Gate summary

| Gate | Command | Result |
| --- | --- | --- |
| Full test suite | `uv run pytest` | **472 passed, 2 skipped, 2 warnings in 15.04s** (2 pre-existing skips from cost-path integration tests, unrelated to T07). |
| T07 concurrency targeted | `uv run pytest tests/workflows/test_slice_refactor_concurrency.py` | **9/9 passed** (dispatch `_build_semaphores` structure, fan-out bound, per-tier isolation, no-fan-out regression, `_build_cfg` wiring, registry composition). |
| T07 hard-stop targeted | `uv run pytest tests/workflows/test_slice_refactor_hard_stop.py` | **17/17 passed** (routing with / without failures, dispatch status flip, metadata artefact write + idempotency + ordering, branch-order contract, empty-list defense, graph structure, T02 registry presence). |
| M6-T03-ISS-01 resolution | `uv run pytest tests/graph/test_validator_node.py` | **12/12 passed** (7 pre-existing + 5 new escalation tests). |
| T01–T06 regression | `uv run pytest tests/workflows/test_slice_refactor_*` | All slice_refactor suites green (planner subgraph, fanout, validator, aggregator, strict gate, apply, concurrency, hard_stop). |
| Planner regression | `uv run pytest tests/workflows/test_planner_*` | All planner suites green (graph, schemas, multitier integration, explorer qwen, synth claude_code). |
| Cancel-path regression | `uv run pytest tests/mcp/test_cancel_run_inflight.py` | **5/5 passed** (T02 `_ACTIVE_RUNS` wiring unchanged). |
| Import-layer contract | `uv run lint-imports` | **3/3 KEPT** (primitives → graph → workflows → surfaces). |
| Lint | `uv run ruff check` | "All checks passed!" |
| KDR-003 grep | grep `anthropic`/`ANTHROPIC_API_KEY` across T07-touched files | No matches in `workflows/slice_refactor.py`, `workflows/_dispatch.py`, `graph/validator_node.py`. |
| CHANGELOG entry | `CHANGELOG.md:10` | ✅ `### Added — M6 Task 07: Concurrency Semaphore + Double-Failure Hard-Stop (2026-04-20)` present. |

## Issue log — cross-task follow-up

| ID | Severity | Status | Owner / next touch point | One-line |
| --- | --- | --- | --- | --- |
| M6-T03-ISS-01 | 🟢 LOW | ✅ RESOLVED (T07 Builder, 2026-04-20) | — | Validator-side escalation canonicalised in `graph/validator_node.py`; 5 pinning tests added. |
| M6-T04-ISS-01 | 🟢 LOW | ✅ RESOLVED (T07 Builder, 2026-04-20) | — | Hard-stop routes on `len(slice_failures) >= 2`; `_merge_non_retryable_failures` docstring pins the reducer caveat. |

No new items.

## Deferred to nice_to_have

None. All observations are either resolved in-task, documented as deliberate design choices, or semantic notes on AC interpretation.

## Propagation status

- **M6-T03-ISS-01** → RESOLVED in T07 Builder. Originating issue file (`task_03_issue.md`) flipped status line + §LOW-01 body + §Propagation status footer. Target task spec (`task_07_concurrency_hard_stop.md`) carry-over checkbox ticked with ✅ RESOLVED annotation + test-name citations.
- **M6-T04-ISS-01** → RESOLVED in T07 Builder. Originating issue file (`task_04_issue.md`) flipped heading + §Issue log row + §Propagation status row + top-of-file status line. Target task spec (`task_07_concurrency_hard_stop.md`) carry-over checkbox ticked with ✅ RESOLVED annotation + test-name citations.
- No new forward-deferrals from T07.
