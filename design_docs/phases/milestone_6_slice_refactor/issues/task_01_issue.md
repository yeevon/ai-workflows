# Task 01 — Slice-Discovery Phase — Audit Issues

**Source task:** [../task_01_slice_discovery.md](../task_01_slice_discovery.md)
**Audited on:** 2026-04-20
**Audit scope:** `ai_workflows/workflows/slice_refactor.py` (new), `ai_workflows/workflows/_dispatch.py` (one-hook extension), `tests/workflows/test_slice_refactor_planner_subgraph.py` (new), CHANGELOG.md (new `[Unreleased]` entry), T05 + T06 spec file carry-over additions; cross-referenced against `design_docs/architecture.md` (§3 layer contract, §4.2 graph-layer adapters, §4.3 workflows layer — slice_refactor shape, §6 external deps, §8.2 error handling, §9 KDRs), `design_docs/adr/0002_bare_typed_response_format_schemas.md`, KDR-001/003/004/006/009/010; sibling workflow module `ai_workflows/workflows/planner.py`; primitive `ai_workflows/primitives/retry.py`; workflows registry `ai_workflows/workflows/__init__.py`.
**Status:** ✅ PASS — no OPEN issues after cycle-2 implement. Two accepted spec deviations (both disclosed in CHANGELOG and approved by the user during Builder-phase scope review).

## Design-drift check

- **New dependency?** None. Imports are entirely from already-adopted deps (`langgraph`, `langchain-core`, `pydantic`) and internal packages. Architecture.md §6 unchanged. ✓
- **New module / layer?** `ai_workflows/workflows/slice_refactor.py` lands in the `workflows/` layer per [architecture.md §4.3](../../../architecture.md) (explicitly named as an expected workflow). Layer-discipline holds: imports only `workflows/__init__.py`, `workflows/planner.py`, and `primitives/retry.py`. `uv run lint-imports` reports 3 / 3 contracts kept. ✓
- **LLM call added?** No. T01 adds zero LLM nodes — `slice_refactor_tier_registry()` returns `{}` because the planner sub-graph brings its own `planner-explorer` / `planner-synth` tiers. KDR-004 validator-pairing N/A. ✓
- **Checkpointer / resume logic?** `planner_subgraph = build_planner().compile()` deliberately compiled *without* a checkpointer so LangGraph shares the parent graph's `AsyncSqliteSaver` at run time — KDR-009 honoured, no hand-rolled checkpoint writes. Verified in practice by `test_resume_clears_subgraph_gate_and_populates_slice_list` (resume through the sub-graph boundary advances into `slice_list_normalize`). ✓
- **Retry logic?** None added. `_slice_list_normalize` raises `NonRetryable` directly (imported from `primitives.retry` — the canonical taxonomy class, KDR-006). No bespoke try/except retry loop. ✓
- **Observability?** Uses existing `StructuredLogger` via the planner sub-graph's tier nodes (confirmed in captured stdout). No external backends pulled in — nice_to_have.md §1/§3/§8 boundary respected. ✓
- **KDR-003 (no Anthropic API):** `test_slice_refactor_module_has_no_anthropic_surface` grep-asserts no `import anthropic` / `from anthropic` / `ANTHROPIC_API_KEY` in the new module. ✓
- **KDR-010 / ADR-0002 (bare-typed `response_format` schemas):** `SliceSpec` carries `id: str` / `description: str` / `acceptance: list[str]` with `extra="forbid"` and **no** `Field(min_length=..., max_length=..., ge=..., le=...)` bounds — leaves the schema usable as a LiteLLM `response_format` if a future worker wants one. `SliceRefactorInput` (caller-input surface) deliberately retains `Field(min_length=1, max_length=4000)` bounds per KDR-010's caller-input carve-out. ✓

**No drift found.** Audit passes design-drift before AC grading.

## AC grading

| AC | Status | Evidence |
| --- | --- | --- |
| AC-1 `slice_refactor` module + `build_slice_refactor()` compiling against `AsyncSqliteSaver` | ✅ | `ai_workflows/workflows/slice_refactor.py` exports `build_slice_refactor()`; `test_build_slice_refactor_compiles_against_async_sqlite_saver` pins the compile. `test_build_slice_refactor_has_two_outer_nodes` pins the T01 shape (`planner_subgraph` + `slice_list_normalize`). |
| AC-2 Planner composed as sub-graph; pauses + resumes cleanly | ✅ | `test_slice_refactor_pauses_at_planner_subgraph_gate` asserts the outer run returns `__interrupt__` with `gate_id == "plan_review"` (i.e. the sub-graph's gate propagates through the outer boundary). `test_resume_clears_subgraph_gate_and_populates_slice_list` asserts `Command(resume="approved")` clears the gate and the outer state carries a populated `slice_list` — which is only possible if the sub-graph's writes merged onto the outer state via the matching channel names declared on `SliceRefactorState`. |
| AC-3 `slice_list_normalize` maps `plan.steps` → `list[SliceSpec]` 1:1 | ✅ | `test_slice_list_normalize_maps_steps_one_to_one` pins the mapping shape; `test_resume_clears_subgraph_gate_and_populates_slice_list` asserts field-for-field (`id` from `index`, `description` from `title`, `acceptance` from `actions`) on a 3-step plan. |
| AC-4 Empty plan → `NonRetryable` | ✅ | `test_slice_list_normalize_empty_plan_raises_nonretryable` pins the bucket. `test_slice_list_normalize_missing_plan_raises_nonretryable` adds the defence-in-depth case for missing-plan-key. |
| AC-5 `slice_refactor` registered + dispatches via `_dispatch.run_workflow` | ✅ (with accepted deviation) | `test_slice_refactor_registered_under_existing_dispatch` pins the registry entry. `test_initial_state_hook_constructs_planner_input_for_subgraph` pins the dispatch shim. **Deviation:** the spec said "no dispatch-layer changes required; verify in the Builder's first read" — verification showed `_build_initial_state` hardcoded `getattr(module, "PlannerInput", None)`, which cannot dispatch any workflow that does not export `PlannerInput` under that exact name. The Builder surfaced three options during Builder-phase scope review; the user chose option B (convention hook), which landed as a strictly-additive, backwards-compatible extension to `_build_initial_state`. The planner workflow's surface behaviour is unchanged (planner does not expose `initial_state`, so the legacy fallback path runs unchanged). Documented in CHANGELOG under "Deviations from spec." |
| AC-6 Hermetic tests green | ✅ | 12 new tests pass; full suite = **378 passed, 2 skipped** (the two skipped are the existing `AIW_E2E=1`-gated smoke tests, unrelated to T01). |
| AC-7 `uv run lint-imports` 3 / 3 kept | ✅ | Re-verified during audit gate sweep. |
| AC-8 `uv run ruff check` clean | ✅ | Re-verified during audit gate sweep ("All checks passed!"). |

## 🔴 HIGH

*(None.)*

## 🟡 MEDIUM

*(None.)*

## 🟢 LOW

*(None OPEN.)*

### LOW-1 — Outer-boundary cost-rollup assertion missing in pause / resume tests — ✅ RESOLVED (cycle 2)

**What:** T01's dependency section cites M5 Task 03 as "sub-graph retry + cost-rollup paths already exercised inside the planner; T01 exercises them at the outer graph boundary for the first time." The first-pass tests did not assert `tracker.total(run_id)` against the expected sum.

**Resolution (cycle 2):** Added `assert tracker.total(...) == pytest.approx(0.0033)` to both `test_slice_refactor_pauses_at_planner_subgraph_gate` (pause path) and `test_resume_clears_subgraph_gate_and_populates_slice_list` (resume path), pinning that the sub-graph's `CostTrackingCallback` writes through the parent's config (= cost-rollup crosses the sub-graph boundary cleanly). 0.0012 + 0.0021 = 0.0033 for the two stubbed LLM calls. Tests remain green (12/12).

## Additions beyond spec — audited and justified

1. **`SliceRefactorInput` class (spec did not require it).** Spec's state sketch had a flat `goal: str`; the actual T01 deliverable adds `SliceRefactorInput` (bounded `goal` / `context` / `max_steps`) alongside `SliceSpec`. **Justification:** dispatch passes caller inputs as a plain dict through the MCP / CLI surface; without a pydantic class on the slice_refactor side, validation would happen inside the planner sub-graph via `PlannerInput(**inputs)` and a caller passing `max_steps=26` would get a schema error attributed to the planner's surface rather than slice_refactor's. The class also leaves an evolution path open for slice-specific fields (`slice_count_cap`, etc.) without breaking the planner's contract. Documented in CHANGELOG.
2. **`SliceRefactorState` keys mirror the planner's channels directly instead of a spec-sketched `planner_plan: PlannerPlan | None`.** Spec's TypedDict sketch renamed the planner's `plan` channel to `planner_plan` for outer-state clarity. This is **incompatible with LangGraph's state-channel semantics**: a sub-graph's writes only propagate onto the parent's state when channel names match on both sides. Using `planner_plan` on the parent and `plan` on the sub-graph would surface an empty outer state — the resume test would fail. The implementation declares every planner state key the sub-graph writes (`plan`, `explorer_report`, `planner_output`, gate-response slots, retry-taxonomy slots) verbatim on `SliceRefactorState` so propagation works. Documented in CHANGELOG under "Deviations from spec."
3. **`initial_state(run_id, inputs)` convention hook in `slice_refactor.py` + matching extension to `_dispatch._build_initial_state`.** Already covered under AC-5 above — accepted deviation with user approval during Builder-phase scope review. Forward-propagates to T05 (`T01-CARRY-DISPATCH-GATE`) and T06 (`T01-CARRY-DISPATCH-COMPLETE`); see Propagation status below.

## Gate summary

| Gate | Status | Output |
| --- | --- | --- |
| `uv run pytest` | ✅ | 378 passed, 2 skipped, 2 warnings (both warnings are `yoyo` pre-existing deprecations; the 2 skipped are unrelated E2E smokes) |
| `uv run lint-imports` | ✅ | 3 / 3 contracts kept (primitives isolation, graph-cannot-import-workflows-or-surfaces, workflows-cannot-import-surfaces) |
| `uv run ruff check` | ✅ | All checks passed! |

## Issue log — cross-task follow-up

| ID | Severity | Description | Owner / next touch point |
| --- | --- | --- | --- |
| M6-T01-ISS-01 | ✅ RESOLVED (cycle 2) | Cost-rollup assertion missing in pause + resume tests. | Resolved in cycle-2 implement — `assert tracker.total(...) == pytest.approx(0.0033)` added to both tests. |
| T01-CARRY-DISPATCH-GATE | ✅ RESOLVED (M6 T05 Builder, 2026-04-20) | `_dispatch._build_resume_result_from_final` hardcoded `state["gate_plan_review_response"]` when deciding approve/reject — planner's `gate_id` leaked into dispatch. | Resolved in M6 T05 Builder — each workflow module publishes a `TERMINAL_GATE_ID` constant; dispatch reads `state[f"gate_{TERMINAL_GATE_ID}_response"]` via new `_resolve_terminal_gate_id` helper. Planner publishes `"plan_review"`; slice_refactor publishes `"slice_refactor_review"`. Workflows without the constant fall back to the caller-supplied `gate_response`. |
| T01-CARRY-DISPATCH-COMPLETE | ✅ RESOLVED (M6 T06 Builder, 2026-04-20) | `_dispatch._build_result_from_final` + `_build_resume_result_from_final` hardcoded `state["plan"]` as the "completed" signal. | Resolved in M6 T06 Builder — each workflow module publishes a `FINAL_STATE_KEY` constant; dispatch reads `state[FINAL_STATE_KEY]` via new `_resolve_final_state_key` helper. Planner publishes `"plan"`; slice_refactor publishes `"applied_artifact_count"` (populated by the T06 `_apply` node's terminal return). Workflows without the constant fall back to `"plan"`. |

## Deferred to nice_to_have

*(None.)* T01's surface area is entirely within the architecture's planned M6 scope; nothing in the implementation or test set touches a nice_to_have.md item.

## Propagation status

Forward-deferred items from this audit:

- **T01-CARRY-DISPATCH-GATE** → [task_05_strict_review_gate.md](../task_05_strict_review_gate.md) — ✅ RESOLVED in M6 T05 Builder (2026-04-20). Dispatch now reads the gate-response key from the workflow module's `TERMINAL_GATE_ID` constant (planner → `"plan_review"`, slice_refactor → `"slice_refactor_review"`). Test coverage at [tests/workflows/test_slice_refactor_strict_gate.py](../../../tests/workflows/test_slice_refactor_strict_gate.py) pins both the new slice_refactor path and the planner regression.
- **T01-CARRY-DISPATCH-COMPLETE** → [task_06_apply_node.md](../task_06_apply_node.md) — ✅ RESOLVED in M6 T06 Builder (2026-04-20). Dispatch now reads the completion signal from the workflow module's `FINAL_STATE_KEY` constant (planner → `"plan"`, slice_refactor → `"applied_artifact_count"`). Test coverage at [tests/workflows/test_slice_refactor_apply.py](../../../tests/workflows/test_slice_refactor_apply.py) pins both the slice_refactor completion path and the planner regression.

Both carry-overs were landed on the target task files during the T01 Builder phase (pre-audit); this footer closes the propagation loop.
