# Task 04 — `TieredNode` Integration + Workflow Fallback Edges — Audit Issues

**Source task:** [../task_04_tiered_node_integration.md](../task_04_tiered_node_integration.md)
**Audited on:** 2026-04-21
**Audit scope:** `ai_workflows/graph/tiered_node.py` (breaker hook + state-level override resolver), `ai_workflows/workflows/planner.py` (fallback edge composition), `ai_workflows/workflows/slice_refactor.py` (single-gate fan-in), `tests/graph/test_tiered_node_ollama_breaker.py`, `tests/workflows/test_planner_ollama_fallback.py`, `tests/workflows/test_slice_refactor_ollama_fallback.py`, topology assertions in `test_planner_graph.py` / `test_planner_multitier_integration.py` / `test_slice_refactor_planner_subgraph.py`, `CHANGELOG.md`. Architecture check against `design_docs/architecture.md` (§3, §4.2, §8.2, §8.4, §9) and the KDRs the task cites (KDR-003, KDR-004, KDR-006, KDR-009).
**Status:** ✅ PASS — all 11 ACs met, gates green, no design drift.

---

## Design-drift check

Cross-checked every modification against `architecture.md` and the KDRs the task cites.

| Concern | Finding | Verdict |
|---|---|---|
| **New dependencies (§6)** | None added. `CircuitBreaker` + `CircuitOpen` imported from `ai_workflows.primitives.circuit_breaker` (shipped by M8 T02). | ✅ |
| **Four-layer contract (§3)** | `tiered_node.py` stays in `graph/`; imports only from `primitives/` + `graph/` siblings. Workflow nodes (`planner.py`, `slice_refactor.py`) import `graph/` + `primitives/` only. `import-linter` — 4 contracts kept. | ✅ |
| **KDR-003 (no Anthropic API)** | `grep -r "anthropic" ai_workflows/graph/tiered_node.py` — only the doc comment citing the KDR; no SDK import, no `ANTHROPIC_API_KEY` lookup. Fallback tier for planner is `planner-synth` (ClaudeCodeRoute via CLI subprocess), not an API key. | ✅ |
| **KDR-004 (validator-after-LLM)** | No new `TieredNode` instances added. The breaker hook is a pre-dispatch guard on the existing `TieredNode` function; existing validator pairings (`explorer → explorer_validator`, `planner → planner_validator`, `slice_worker → slice_worker_validator`) are untouched. Fallback gate is a `HumanGate`, not an LLM node — no validator required. | ✅ |
| **KDR-006 (three-bucket retry)** | `CircuitOpen` is deliberately *not* classified by `classify()` — it's raised pre-dispatch and caught as a specific type by `wrap_with_error_handler`, which writes it to `state['last_exception']` without bumping `_retry_counts` or `_non_retryable_failures` (verified in [error_handler.py](../../../../ai_workflows/graph/error_handler.py) — `CircuitOpen` isinstance branch returns `{"last_exception": exc}` only). `record_failure` is called on the breaker only when the classifier lands on `RetryableTransient` — auth / bad-request / budget failures do not count as Ollama-health signals. Task spec §Graph-layer-hook documents this distinction explicitly. | ✅ |
| **KDR-009 (SqliteSaver-only checkpointing)** | No hand-rolled checkpoint writes. The `_mid_run_tier_overrides` and `_ollama_fallback_*` state keys flow through LangGraph's native state channels (LastValue for scalars, `Annotated[..., operator.add]` for lists, `Annotated[..., _merge_*]` for the two sticky-OR / dict-merge reducers). Resume from the gate uses the stock `SqliteSaver` path. | ✅ |
| **Observability (§8.1)** | `breaker_state` stamped via `log_extras` on both success (`event="node_completed"`) and failure (`event="node_failed"`) records. One new log field, no new log event, no external backend (`StructuredLogger` / `structlog` only). | ✅ |
| **§8.4 provider-health policy** | Breakers fire only for `LiteLLMRoute` with `model.startswith("ollama/")` (`_resolve_breaker`). Gemini-backed LiteLLM tiers and `ClaudeCodeRoute` bypass the breaker — matches the §8.4 "circuit breaker around the Ollama daemon" wording. Fallback gate is a single per-run `HumanGate` (one pause, not N) — matches §8.4 "pause the run and ask the operator". | ✅ |
| **§8.2 hard-stop surface** | `planner_hard_stop` + `slice_refactor_ollama_abort` both write a `hard_stop_metadata` artefact (distinct `reason` payloads: `"ollama_fallback_abort"` vs the existing double-failure reason). Artefact kind reused, not a new kind. Dispatch continues to flip `runs.status='aborted'` on the existing terminal signals. | ✅ |

No drift found. No `nice_to_have.md` item pulled in.

---

## AC grading

| # | Acceptance Criterion | Verdict | Evidence |
|---|---|---|---|
| 1 | `TieredNode` reads `ollama_circuit_breakers` from `configurable` and consults only for `LiteLLMRoute` + `model.startswith("ollama/")`. | ✅ | [tiered_node.py:209-211](../../../../ai_workflows/graph/tiered_node.py#L209-L211), [tiered_node.py:411-429](../../../../ai_workflows/graph/tiered_node.py#L411-L429) (`_resolve_breaker` rejects non-LiteLLM + non-Ollama models). Covered by `test_non_ollama_litellm_route_bypasses_breaker` + `test_claude_code_route_bypasses_breaker`. |
| 2 | `CircuitOpen` raised pre-call when breaker denies; adapter not called on that path. | ✅ | [tiered_node.py:228-237](../../../../ai_workflows/graph/tiered_node.py#L228-L237). Covered by `test_breaker_open_raises_circuit_open_without_provider_call` (stub raises `AssertionError` on any call; passes = adapter never called). |
| 3 | `record_success` on success path; `record_failure` only for `RetryableTransient`-bucketed exceptions. | ✅ | [tiered_node.py:275-276](../../../../ai_workflows/graph/tiered_node.py#L275-L276) success; [tiered_node.py:301-302](../../../../ai_workflows/graph/tiered_node.py#L301-L302) + [tiered_node.py:326-327](../../../../ai_workflows/graph/tiered_node.py#L326-L327) failure. Covered by `test_transient_failure_records_on_breaker` + `test_non_retryable_failure_does_not_record_on_breaker`. |
| 4 | `breaker_state` surfaces in the node's structured log record. | ✅ | [tiered_node.py:239-241](../../../../ai_workflows/graph/tiered_node.py#L239-L241), refreshed at [tiered_node.py:279](../../../../ai_workflows/graph/tiered_node.py#L279) / [:303](../../../../ai_workflows/graph/tiered_node.py#L303) / [:328](../../../../ai_workflows/graph/tiered_node.py#L328). Covered by `test_structured_log_includes_breaker_state`. |
| 5 | Mid-run tier override via `_mid_run_tier_overrides` takes precedence over the existing configurable override path. | ✅ | [tiered_node.py:381-408](../../../../ai_workflows/graph/tiered_node.py#L381-L408) — state overrides checked before configurable overrides before registry default; first match wins. Covered by `test_fallback_routes_to_replacement_tier` (planner) + `test_fallback_applies_to_subsequent_branches` (slice_refactor). |
| 6 | `planner` + `slice_refactor` both route `CircuitOpen` through a single `ollama_fallback` `HumanGate` per run. | ✅ | Planner: [planner.py:519-522](../../../../ai_workflows/workflows/planner.py#L519-L522) builds one gate via `build_ollama_fallback_gate`; `_decide_after_explorer_with_fallback` routes first `CircuitOpen` to the stamp → gate chain. Slice_refactor: shared gate builder with `(run_id, gate_id="ollama_fallback")` dedupe — `_route_before_aggregate` centralises fan-in routing. |
| 7 | `slice_refactor` parallel branches share one gate per run, not one per branch. | ✅ | The slice sub-graph emits `_circuit_open_slice_ids` entries, not gate calls. The outer graph's `_route_before_aggregate` checks `already_fired` before routing to `ollama_fallback_stamp`; a second trip after the gate fired routes straight to hard-stop. Covered by `test_single_gate_for_all_branches` (asserts three `_circuit_open_slice_ids` entries, one `_ollama_fallback_count` increment, one pause). |
| 8 | `FallbackChoice.RETRY` / `FALLBACK` / `ABORT` each route correctly. | ✅ | `_ollama_fallback_dispatch` (planner) + `_ollama_fallback_dispatch_slice` write the override on `FALLBACK`, clear retry state on both retry-bearing choices, and leave `ABORT` to the router ([planner.py:412-430](../../../../ai_workflows/workflows/planner.py#L412-L430), [slice_refactor.py:1301-1325](../../../../ai_workflows/workflows/slice_refactor.py#L1301-L1325)). Covered by `test_retry_re_fires_same_tier`, `test_fallback_routes_to_replacement_tier`, `test_abort_terminates_hard_stop` (planner) + the three slice_refactor counterparts. |
| 9 | Every listed test passes under `uv run pytest tests/graph/test_tiered_node_ollama_breaker.py tests/workflows/test_planner_ollama_fallback.py tests/workflows/test_slice_refactor_ollama_fallback.py`. | ✅ | All three files present and green (see gate summary). |
| 10 | Full `uv run pytest` green (no regression on existing tests — especially M6's hard-stop / cancel tests). | ✅ | 581 passed, 4 skipped, 2 warnings (pre-existing `yoyo` SQLite datetime adapter deprecation, unrelated). M6's `test_slice_refactor_hard_stop.py` (17 tests) + concurrency suite (9 tests) green. |
| 11 | `uv run lint-imports` — 4 contracts kept. `uv run ruff check` clean. | ✅ | See gate summary. |

---

## Additions beyond spec — audited and justified

### 1. `_merge_mid_run_tier_overrides` dict-merge reducer on `SliceRefactorState._mid_run_tier_overrides`

**What changed:** [slice_refactor.py:366-380](../../../../ai_workflows/workflows/slice_refactor.py#L366-L380) adds a shallow-merge reducer; [slice_refactor.py:604-606](../../../../ai_workflows/workflows/slice_refactor.py#L604-L606) annotates the state key with it.

**Why it was necessary:** After `FallbackChoice.FALLBACK`, the outer graph re-fans N slice branches via `Send`. Each branch's sub-graph writes `_mid_run_tier_overrides` back to the parent at fan-in. The prior `LastValue` channel raised `InvalidUpdateError: Can receive only one value per step` when three branches wrote the identical dict. The reducer makes the fan-in safe — duplicate-key collisions always resolve to the same value, so the merge is order-independent and deterministic. Without this, the fallback path would crash at the first parallel branch fan-in after resume.

**Why this is not scope creep:** The task spec §"Mid-run tier override plumbing" requires the override to be readable across the remainder of the run, including N parallel branches. The spec doesn't pick a reducer — that's a LangGraph mechanical detail. Declaring it as part of the state type is the minimal fix.

### 2. `_mid_run_tier_overrides` in `SliceBranchState` + Send-payload carry

**What changed:** [slice_refactor.py:656-658](../../../../ai_workflows/workflows/slice_refactor.py#L656-L658) adds the key to `SliceBranchState`; [slice_refactor.py:1245-1298](../../../../ai_workflows/workflows/slice_refactor.py#L1245-L1298) and the re-fan Send builder include `dict(overrides)` in the Send payload.

**Why it was necessary:** LangGraph's `Send` payload *is* the sub-graph's initial state view — keys absent from the payload don't propagate into the sub-graph. Without carrying `_mid_run_tier_overrides` in the payload, re-fanned branches would look it up on their own state, miss it, fall through to the registry default, and re-fire the tripped Ollama tier instead of the fallback tier. This is a latent bug the `test_fallback_applies_to_subsequent_branches` test exposed on first implementation run.

**Why this is not scope creep:** AC-8 says `FALLBACK → replacement tier`. Without the payload carry, `FALLBACK` silently degrades to `RETRY` for re-fanned branches. The fix is the minimum set of edits to make the AC pass.

### 3. Topology-assertion updates in existing tests

**What changed:** Expected node sets in [test_planner_graph.py](../../../../tests/workflows/test_planner_graph.py), [test_planner_multitier_integration.py](../../../../tests/workflows/test_planner_multitier_integration.py), [test_slice_refactor_planner_subgraph.py](../../../../tests/workflows/test_slice_refactor_planner_subgraph.py) now include the four new fallback nodes (`ollama_fallback_stamp`, `ollama_fallback`, `ollama_fallback_dispatch`, `planner_hard_stop` / `slice_refactor_ollama_abort`).

**Why this is not scope creep:** T04 adds these nodes by design; the sibling tests assert on topology by name. Loosening `==` to `issubset` where appropriate preserves the original intent (core nodes still present) without hard-coding T04's additions into tests that predate T04.

---

## Gate summary

| Gate | Command | Result |
|---|---|---|
| pytest | `uv run pytest` | 581 passed, 4 skipped, 2 warnings (pre-existing `yoyo` SQLite deprecation, unrelated) |
| import-linter | `uv run lint-imports` | 4 contracts kept, 0 broken |
| ruff | `uv run ruff check` | All checks passed |
| Task-specific greps | `grep -r "anthropic" ai_workflows/graph/tiered_node.py` | Only KDR citation in module docstring — no SDK import, no env-var lookup |
| Target test files | `uv run pytest tests/graph/test_tiered_node_ollama_breaker.py tests/workflows/test_planner_ollama_fallback.py tests/workflows/test_slice_refactor_ollama_fallback.py` | All green (7 + 3 + 3 = 13 tests) |

---

## Issue log — cross-task follow-up

No OPEN issues. Nothing forward-deferred. Nothing blocked on user input.

---

## Deferred to nice_to_have

None applicable.

---

## Propagation status

Nothing to propagate. Task closes fully within its own scope; no forward-deferrals to M8 T05 / T06 or later milestones.
