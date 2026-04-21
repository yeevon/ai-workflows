# Task 03 — Per-Slice Validator Wiring — Audit Issues

**Source task:** [../task_03_per_slice_validator.md](../task_03_per_slice_validator.md)
**Audited on:** 2026-04-20
**Audit scope:** Full project — task spec, milestone README, sibling task files (T02, T04, T07), pyproject, CHANGELOG, CI gates, architecture.md §4.2 / §4.3 / §8.2, KDR-001 / KDR-004 / KDR-006 / KDR-009 / KDR-010, ADR-0002, `ai_workflows/workflows/slice_refactor.py` (full), `tests/workflows/test_slice_refactor_validator.py` (new), `tests/workflows/test_slice_refactor_planner_subgraph.py` (modified), `tests/workflows/test_slice_refactor_fanout.py` (unchanged), `tests/mcp/test_cancel_run_inflight.py` (unchanged), `ai_workflows/graph/error_handler.py`, `ai_workflows/graph/retrying_edge.py`, `ai_workflows/graph/validator_node.py`, `ai_workflows/graph/tiered_node.py`, `ai_workflows/primitives/retry.py`.
**Status:** ✅ PASS — all ACs satisfied, M6-T02-ISS-01 carry-over RESOLVED, no open HIGH/MEDIUM issues; §LOW-01 (retrying_edge semantic-budget pattern) ✅ RESOLVED in M6 T07 Builder (2026-04-20) via option 1 (validator-side escalation).

## Design-drift check

Cross-check against [architecture.md](../../../architecture.md) and every cited KDR:

| Axis | Finding |
| --- | --- |
| **Layer discipline** (§3) | `slice_refactor.py` lives in `workflows/`; it imports `graph.tiered_node`, `graph.retrying_edge`, `graph.error_handler`, and `primitives.retry` / `primitives.tiers` / sibling workflow `workflows.planner`. No upward leak. `lint-imports` 3/3 kept. ✅ |
| **§4.2 ValidatorNode contract** | "Paired with any LLM node; parses output against a pydantic schema; raises `ModelRetry` with revision guidance on parse failure; passes through on success." The bespoke `_slice_worker_validator` matches: parses `SliceResult`, raises `RetryableSemantic` with a formatted `revision_hint`, passes through on success. Deviation from reusing `graph.validator_node.validator_node`: the stock factory writes `{output_key: parsed}` — would write a bare `SliceResult` into the reducer-backed `slice_results` channel and bypass the `operator.add` list contract. Documented in the module docstring. ✅ |
| **§4.3 slice_refactor shape** | "planner sub-graph → per-slice worker nodes (parallel) → per-slice validator → aggregate → strict-review gate → apply." T03 lands the per-slice validator via a compiled per-slice sub-graph (`slice_branch`) that internalises the worker→validator pair. This is functionally identical to a separate `slice_worker_validator` parent-graph node for the purpose of the architecture contract, and architecturally **superior** for retry scoping: a `Send`-dispatched parent-graph validator would share retry state across branches, undermining AC-3 / AC-4. Sub-graph state is per-`Send`, so semantic/transient retries scope to the failing slice. ✅ |
| **§8.2 three-bucket retry** | "`RetryableSemantic` → ValidatorNode raises ModelRetry; LangGraph re-invokes the LLM node with revision guidance. Max 3 attempts then escalate to non-retryable." Matched verbatim: `_slice_worker_validator` raises `RetryableSemantic` on a revisable failure; on the final allowed attempt it escalates to `NonRetryable` (the project's `ModelRetry`-equivalent bucket-escalation pattern). `SLICE_WORKER_RETRY_POLICY.max_semantic_attempts = 3` asserted by `test_slice_worker_retry_policy_matches_spec_budget`. ✅ |
| **KDR-001 (LangGraph ownership)** | T03 adds no hand-rolled orchestrator — the per-slice sub-graph is a LangGraph `StateGraph.compile()`; retry routing is `retrying_edge` (a `graph/` layer adapter). ✅ |
| **KDR-003 (no Anthropic API)** | Grepped `slice_refactor.py` and new test: no `anthropic` import, no `ANTHROPIC_API_KEY` read. `slice-worker` tier routes to Ollama Qwen via LiteLLM (T02). ✅ |
| **KDR-004 (validator after every LLM node)** | Every `slice_worker` (`TieredNode` tier=`slice-worker`) has an adjacent `slice_worker_validator` downstream in the compiled `slice_branch` sub-graph. Structural guard: `test_slice_branch_subgraph_has_worker_and_validator_nodes`. ✅ |
| **KDR-006 (three-bucket retry, graph-level routing)** | Routing uses `retrying_edge` — the three-bucket dispatch lives in `graph/retrying_edge.py`, not hand-rolled. The validator's internal semantic→NonRetryable escalation is an explicit bucket transition, not a bespoke retry loop. No `try/except` retry loops in `slice_refactor.py`. ✅ |
| **KDR-009 (SqliteSaver owns checkpoints)** | `_build_slice_branch_subgraph()` compiles without a checkpointer; parent `build_slice_refactor()` also compiles without a checkpointer (the caller — `_dispatch.run_workflow` — attaches `AsyncSqliteSaver` at compile time). Sub-graphs inherit the parent's checkpointer per LangGraph's semantics. No hand-rolled checkpoint writes. ✅ |
| **KDR-010 / ADR-0002 (bare-typed response_format schemas)** | `SliceResult` carries three bare field annotations (`slice_id: str`, `diff: str`, `notes: str`) plus `model_config = ConfigDict(extra="forbid")`. No `Field(min_length=…/max_length=…/ge=…/le=…)` bounds. Re-audited this audit cycle; T02 landed the shape and T03 did not regress it. ✅ |
| **New dependencies** | None. `litellm.exceptions.APIConnectionError` is imported by the new test only; `litellm` is already pinned in `pyproject.toml` §dependencies under the T02-era install. No change to `architecture.md §6`. ✅ |
| **Observability** | Workflow-layer code emits structured logs only through `TieredNode`'s existing `StructuredLogger` call; no new log sites, no external backend adoption. `nice_to_have.md §§` on Langfuse/OTel/LangSmith untouched. ✅ |
| **nice_to_have.md boundary** | No `nice_to_have.md` item pulled in without trigger. The Instructor / pydantic-ai option called out in §4.2 remains deferred (the bespoke validator is the spec-sanctioned path). ✅ |

No design drift. ✅

## Acceptance-criteria grading

| # | AC | Verdict | Evidence |
| --- | --- | --- | --- |
| AC-1 | Every `slice_worker` Send invocation paired with `slice_worker_validator` downstream (KDR-004) | ✅ PASS | `slice_branch` sub-graph has both nodes registered + edge-wired. `test_slice_branch_subgraph_has_worker_and_validator_nodes` asserts both names present in the compiled sub-graph. |
| AC-2 | `retrying_edge(on_semantic="slice_worker", on_transient="slice_worker")` wired with max 3 semantic attempts | ✅ PASS | `_build_slice_branch_subgraph` wires two `retrying_edge` instances (after worker + after validator) both using `on_semantic="slice_worker"` / `on_transient="slice_worker"` with `policy=SLICE_WORKER_RETRY_POLICY`. `test_slice_worker_retry_policy_matches_spec_budget` asserts `max_semantic_attempts == 3`. |
| AC-3 | Per-slice semantic retry does not re-run sibling slices | ✅ PASS | `test_semantic_retry_reruns_only_failing_slice` stubs slice 1 to fail once + succeed; slice 2 to succeed; asserts `worker_calls_by_slice == {"1": 2, "2": 1}`. Sub-graph-scoped state is the structural guarantee. |
| AC-4 | Per-slice transient retry does not re-run sibling slices | ✅ PASS | `test_transient_retry_on_apiconnectionerror_recovers_slice` raises `APIConnectionError` on slice 1's first call; asserts `worker_calls_by_slice == {"1": 2, "2": 1}` and final state populated both slices. |
| AC-5 | Semantic-exhaustion on one slice surfaces `NonRetryable`; sibling slices still complete (T07 decides abort vs continue) | ✅ PASS | `test_semantic_exhaustion_surfaces_nonretryable_on_failing_branch` drives slice 1 to 3 malformed responses; asserts slice 1 worker runs exactly 3 times, slice 2 worker runs exactly 1 time, `slice_results` contains only slice 2, and `_non_retryable_failures >= 1` (the `NonRetryable` escalation reaches the wrap's counter bump). |
| AC-6 | `SliceResult` bare-typed per KDR-010 / ADR-0002 (already T02; re-audit) | ✅ PASS | Re-read `SliceResult`: no `Field(...)` bounds on any field; `extra="forbid"` retained. |
| AC-7 | Hermetic tests green | ✅ PASS | `uv run pytest`: 398 passed, 2 skipped (0.95s → 12.45s on repeat), zero network I/O (stub adapter at `tiered_node_module.LiteLLMAdapter` boundary). |
| AC-8 | `uv run lint-imports` 3/3 kept | ✅ PASS | All three contracts (`primitives` cannot import graph/workflows/surfaces; `graph` cannot import workflows/surfaces; `workflows` cannot import surfaces) reported KEPT. |
| AC-9 | `uv run ruff check` clean | ✅ PASS | "All checks passed!" after `--fix` auto-sorted one import in the new test file (safe, idempotent, no semantic change). |
| Carry-over M6-T02-ISS-01 (inline-parse revert + channel-scoping re-examination) | ✅ RESOLVED | Spec's task_03_per_slice_validator.md §Carry-over from prior audits now ticked; see evidence below under §Carry-over. |

## 🔴 HIGH — none

## 🟡 MEDIUM — none

## 🟢 LOW

### LOW-01 — Retrying_edge semantic-budget check keys off routing target, not failing-node counter — latent in planner, surfaced-and-worked-around in T03

**Finding.** `graph/retrying_edge.py:118` checks `retry_counts.get(on_semantic, 0) >= policy.max_semantic_attempts` using the **routing target** as the dict key (`"slice_worker"`), while `wrap_with_error_handler` at `graph/error_handler.py:150` bumps the counter under the **failing node's name** (`"slice_worker_validator"`). Net effect: the edge's semantic-budget check never sees the validator's failures, and — absent an in-validator escalation — the semantic loop would run indefinitely on a stuck-invalid provider.

T03 works around this by escalating `RetryableSemantic → NonRetryable` **inside** `_slice_worker_validator` on the final allowed attempt, keyed off `state['_retry_counts']['slice_worker_validator']`. This resolves the AC-5 contract but leaves the pattern latent elsewhere. The planner exhibits the identical wiring (`planner.py:309–313`, `planner.py:321–326`) with no in-validator escalation; in practice a stochastic Gemini/Opus call does not produce 3 invalid JSONs in a row so exhaustion is never hit, but a pathological provider or future provider-stub test could loop forever.

**Severity — LOW.** Not a T03 blocker (ACs met, escalation works correctly via the in-validator path). Classified LOW because it's a latent issue in the `graph/` layer that T07 or a future general-retry-hardening task will be in a better position to fix — a graph-layer fix touches planner retry semantics and should land with planner-retry tests alongside.

**Action — ✅ RESOLVED in M6 T07 Builder (2026-04-20).** T07 picked **option 1** (validator-side escalation as the canonical `ValidatorNode` contract), matching the T03 bespoke pattern and keeping `graph/retrying_edge.py` API untouched.

Concrete landed changes:

- **`ai_workflows/graph/validator_node.py`** — added `_retry_counts[node_name] >= max_attempts - 1` check inside the factory's `_node` closure; on exhaustion it raises `NonRetryable` (previously would have looped raising `RetryableSemantic` forever). Module docstring + function docstring pin the `node_name` alignment requirement (must match the `wrap_with_error_handler` key) and the escalation contract.
- **`tests/graph/test_validator_node.py`** — 5 new tests: `test_escalation_raises_non_retryable_on_last_allowed_attempt`, `test_escalation_preserves_retryable_semantic_on_earlier_attempts`, `test_escalation_reads_counter_under_validator_node_name` (keys are disjoint — counter under `on_semantic` target does NOT trigger), `test_escalation_works_with_max_attempts_one`, `test_exhausting_three_attempts_sequence_surfaces_non_retryable`.

Net effect: planner's `explorer_validator` / `planner_validator` + slice_refactor's bespoke `_slice_worker_validator` all converge on the same "escalate on last allowed attempt" contract. The retrying_edge target-key check remains correct for its primary role (LLM-node semantic-attempt budget keyed off `on_semantic`), and the validator owns the authoritative exhaustion signal.

**Not** a `nice_to_have.md` item — this was a correctness nit in an existing graph-layer adapter, not a new capability.

## Additions beyond spec — audited and justified

| Addition | Rationale | Verdict |
| --- | --- | --- |
| **Bespoke `_slice_worker_validator` instead of `graph.validator_node.validator_node`** | Stock factory writes `{output_key: parsed}` as a **bare** `SliceResult`, but `slice_results` is reducer-backed (`Annotated[list[SliceResult], operator.add]`) and receives **list** updates. A bespoke shim writes the one-element list without muddling the stock factory's contract; stock factory is unchanged for the planner's use. | ✅ Justified in module docstring + CHANGELOG. |
| **Local duplicate of `_format_revision_hint` (renamed `_format_slice_result_hint`)** | The stock formatter is underscore-private to `graph.validator_node`. Cross-module use would either require promoting a private helper to public graph-layer API (adds surface for one caller) or importing the private symbol (breaks the intended encapsulation). 12-line duplication is cheaper than either option. | ✅ Justified in docstring. |
| **Upstream-failure passthrough in validator** (`if text is None: return {}`) | Defensive — if the worker raises `NonRetryable` so `slice_worker_output` is never written, the validator becomes a no-op (last_exception already carries the failure, retrying_edge routes terminal). Prevents `KeyError` on a legitimate upstream-failure path (surfaced by the resume test when slice-worker tier is missing from the registry). | ✅ Justified; behavior documented in the validator's docstring. |
| **`SliceBranchState` TypedDict** | Required by LangGraph: a compiled sub-graph must declare its own state schema. `run_id` deliberately omitted (read from `config['configurable']` — avoids cross-branch `InvalidUpdateError`); retry-taxonomy slots declared scalar (single-writer within a branch). | ✅ Fitness-for-purpose; matches LangGraph convention. |
| **`SLICE_WORKER_RETRY_POLICY` module-level constant** | Mirrors planner's `PLANNER_RETRY_POLICY`; lets tests introspect the budget without reaching into `_build_slice_branch_subgraph`'s closure. `max_transient_attempts=5` carries the planner's rationale verbatim. | ✅ Consistent with sibling workflow; pinned by test. |
| **Send payload no longer carries `run_id`; parent state no longer declares `slice`** | Fixes a latent `InvalidUpdateError` that fires once N ≥ 2 `Send`s return to the parent (N scalar writes to the same key). Uses the fact that `RunnableConfig` propagates into sub-graph invocations by default, so `run_id` flows via config instead. | ✅ Load-bearing correctness fix, documented in module docstring and `_fan_out_to_workers` docstring. |
| **T02-resume test now scripts 3 worker responses + adds `slice-worker` tier** | The test drove resume past the gate — fan-out now exercises the new worker→validator sub-graph. Without worker stubs, the sub-graph would exhaust its AssertionError path. The `0.0036` cost-rollup assertion extends the T01 `0.0033` expectation by `3 × 0.0001`. | ✅ Shape-correct; existing AC-3 (slice_list populated) still asserted. |

## Gate summary

| Gate | Command | Result |
| --- | --- | --- |
| Full test suite | `uv run pytest` | **398 passed, 2 skipped** (2 pre-existing skips from cost-path integration tests unrelated to T03). |
| T03 targeted | `uv run pytest tests/workflows/test_slice_refactor_validator.py` | **6/6 passed.** |
| T02 regression | `uv run pytest tests/workflows/test_slice_refactor_fanout.py` | **9/9 passed** (no drift on T02 ACs despite the compound→sub-graph refactor). |
| T01 regression | `uv run pytest tests/workflows/test_slice_refactor_planner_subgraph.py` | **12/12 passed** (includes the updated shape guard + resume stubs). |
| Cancel-path regression | `uv run pytest tests/mcp/test_cancel_run_inflight.py` | **5/5 passed** (T02 carry-over of M4 T05 in-flight cancel wiring still green — important because T03 changed the fan-out target). |
| Import-layer contract | `uv run lint-imports` | **3/3 kept** (primitives → graph → workflows → surfaces). |
| Lint | `uv run ruff check` | **All checks passed!** after one auto-fix (import sort on the new test file — safe). |
| KDR-003 grep | `grep -rn 'anthropic\|ANTHROPIC_API_KEY' ai_workflows/workflows/slice_refactor.py` | No matches. |
| KDR-004 structural | `test_slice_branch_subgraph_has_worker_and_validator_nodes` | PASS (both node names present in compiled sub-graph). |

## Carry-over

### M6-T02-ISS-01 — Inline-parse shortcut + channel-scoping re-examination (🟢 LOW, owner: M6 T03) — ✅ RESOLVED

Verified against the four-step plan in T02's issue file:

1. **"Drop the inline parse and the direct `slice_results: [parsed]` write from `_build_slice_worker_node._composed`"** — `_build_slice_worker_node` is *gone*; replaced by `_build_slice_branch_subgraph` + a plain `tiered_node(...node_name="slice_worker")` inside it. No inline parse anywhere. ✅
2. **"Split `slice_worker` back into a plain `tiered_node(tier='slice-worker', output_schema=SliceResult, node_name='slice_worker')` that writes `slice_worker_output` only"** — done, exactly that signature at `slice_refactor.py` (inside `_build_slice_branch_subgraph`). ✅
3. **"Add a `slice_worker_validator` ValidatorNode(output_schema=SliceResult) downstream that writes `slice_results`"** — bespoke shim (justified above) with the same contract: writes `{slice_results: [parsed], slice_worker_output_revision_hint: None}` on success, raises `RetryableSemantic`/`NonRetryable` on failure. ✅
4. **"Wire `retrying_edge(on_semantic='slice_worker', on_transient='slice_worker')` with `max_semantic_attempts=3`"** — two `retrying_edge` instances wired in `_build_slice_branch_subgraph`; `SLICE_WORKER_RETRY_POLICY.max_semantic_attempts == 3` asserted. ✅

Channel-scoping extra directive: **"re-examine the `slice_worker_output` scalar state channel — if Send doesn't scope it per-branch, switch to `Annotated[dict[str, str], operator.or_]` keyed by `slice_id`."**

Resolution differed (acceptably): `slice_worker_output` lives on `SliceBranchState` only. LangGraph propagates sub-graph state keys back to the parent only when declared on both sides, so scoping-to-branch-only avoids the cross-branch collision entirely without a keyed reducer. This is a simpler and more orthogonal fix than the `operator.or_` option T02's issue suggested; the `operator.or_` path would also work but would widen the parent's state surface for no benefit. Documented in `SliceBranchState`'s docstring. ✅

## Deferred to nice_to_have

None. LOW-01 is a graph-layer correctness observation deferred to T07, not a nice_to_have capability.

## Propagation status

- **M6-T02-ISS-01** → RESOLVED in-task (no further target needed; was owned by T03). Task-03 spec's carry-over item flipped to ✅.
- **M6-T03-ISS-01 (LOW-01)** → ✅ RESOLVED in M6 T07 Builder (2026-04-20). Option 1 (validator-side escalation) landed in `ai_workflows/graph/validator_node.py`; pinned by 5 new tests in `tests/graph/test_validator_node.py`. Carry-over entry on T07 spec ticked.
