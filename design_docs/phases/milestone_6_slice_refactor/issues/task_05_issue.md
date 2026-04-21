# Task 05 — Strict-Review HumanGate Wiring — Audit Issues

**Source task:** [../task_05_strict_review_gate.md](../task_05_strict_review_gate.md)
**Audited on:** 2026-04-20
**Audit scope:** Full project load — task file, milestone README, sibling task files (T01 issue file, T04 issue file, T06 spec for context, T07 spec for carry-over context), `design_docs/architecture.md` (§4.2, §8.3), cited KDRs (KDR-001, KDR-004, KDR-006, KDR-009), `pyproject.toml`, `CHANGELOG.md`, `.github/workflows/ci.yml`, every file claimed in the T05 implementation + its new test file, the `tests/` tree, and the existing `HumanGate` primitive for the strict-review verification AC.
**Status:** ✅ PASS — all ACs satisfied; one 🟢 LOW (M6-T05-ISS-01) noted as future consideration (not blocking) for a structured-payload extension to `human_gate` if a UI surface ever needs programmatic SliceAggregate access. T01-CARRY-DISPATCH-GATE resolved.

## Design-drift check — architecture.md + KDRs

| Check | Result |
| --- | --- |
| New dependency vs [architecture.md §6](../../architecture.md) | ✅ None added. Only imports the existing `human_gate` primitive and module-level helpers. |
| New module / layer vs [architecture.md §3](../../architecture.md) four-layer contract | ✅ Unchanged. All edits live in `workflows/` (slice_refactor, planner, _dispatch). Import-linter: 3 / 3 contracts kept. |
| LLM call added → paired with validator (KDR-004) | ✅ None added. `HumanGate` is not an LLM node. `_apply_stub` makes no LLM call. `_render_review_prompt` is pure-python. |
| Anthropic SDK / `ANTHROPIC_API_KEY` (KDR-003) | ✅ Clean. `grep -rn anthropic\|ANTHROPIC_API_KEY` on the three touched files shows only a docstring asserting the negative in `planner.py`. |
| Checkpoint / resume logic — `SqliteSaver` only (KDR-009) | ✅ No hand-rolled checkpoint writes. The gate primitive delegates to `langgraph.interrupt()` which rides the existing `AsyncSqliteSaver`. |
| Retry logic — three-bucket taxonomy (KDR-006) via `RetryingEdge` | ✅ No retry wiring added. `_route_on_gate_response` raises `NonRetryable` on contract violation, which surfaces through the existing error-handler wrap when applicable (but the gate is not wrapped — see Additions-beyond-spec note). |
| Observability — `StructuredLogger` only | ✅ No new observability surface. Storage audit log (`record_gate` + `record_gate_response`) was already the KDR-001 path. |
| Strict-review no-timeout posture ([architecture.md §8.3](../../architecture.md)) | ✅ Primitive nulls both `timeout_s` and `default_response_on_timeout` in the interrupt payload when `strict_review=True`. Test `test_human_gate_strict_review_nulls_timeout_payload` pins this; the primitive has no timer code to disable beyond the payload values. |
| KDR-001 — LangGraph owns the interrupt | ✅ `human_gate` wraps `langgraph.types.interrupt`; no hand-rolled gate state machine. |

**Drift verdict:** No violations. No nice_to_have.md items touched.

## AC grading

| AC | Status | Evidence |
| --- | --- | --- |
| 1. `HumanGate(strict_review=True)` wired between `aggregate` and `apply` | ✅ | `build_slice_refactor` adds `slice_refactor_review` node (strict_review=True) + `apply` stub between `aggregate` and END. Structural test `test_compiled_graph_has_review_gate_and_apply_nodes` pins both nodes; end-to-end tests exercise the approve and reject paths through the compiled graph. |
| 2. `strict_review=True` verified to disable the 30-minute timeout path (not just push it to infinity) | ✅ | `test_human_gate_strict_review_nulls_timeout_payload` patches `interrupt` and inspects the payload: both `timeout_s` and `default_response_on_timeout` are `None` (not `inf`, not a timer registration). The primitive's async body contains zero timer code — `interrupt(payload)` is the only awaitable call. |
| 3. Approve → `apply`; reject → END with `runs.status == "gate_rejected"` | ✅ | Graph-level: `test_approve_path_routes_through_apply_to_end` + `test_reject_path_routes_directly_to_end` assert the routing. Dispatch-level: `test_dispatch_result_reads_slice_refactor_gate_key_on_reject` asserts `runs.status == "gate_rejected"` + `finished_at` is stamped. |
| 4. Gate payload is the full `SliceAggregate`; prompt formatter shows successes + failures | ✅ | `_render_review_prompt` serialises every field of every :class:`SliceResult` and :class:`SliceFailure`, plus the totals, into the prompt. `test_render_review_prompt_lists_failures_first` asserts failures precede successes, with `last_error` inline. No aggregate field is dropped. See 🟢 M6-T05-ISS-01 below for a future consideration re: structured payload access. |
| 5. Gate audit log lands in `Storage` for both approve and reject | ✅ | `test_gate_audit_log_written_for_approve` + `test_gate_audit_log_written_for_reject` both assert `Storage.get_gate(run_id, "slice_refactor_review")` returns a row with `prompt` populated, `response` matching the resumed value, and `strict_review == 1`. |
| 6. Hermetic tests green | ✅ | Full suite: 425 passed, 2 skipped, 0 failed. New suite alone: 16 passed in 1.70s. No real API calls. |
| 7. `uv run lint-imports` 3 / 3 kept | ✅ | `primitives → graph → workflows → surfaces` all KEPT. 0 broken. |
| 8. `uv run ruff check` clean | ✅ | "All checks passed." |

## Carry-over grading

| Carry-over | Status | Evidence |
| --- | --- | --- |
| T01-CARRY-DISPATCH-GATE (MEDIUM, from T01 Builder-phase scope review) — `_dispatch._build_resume_result_from_final` hardcodes `state["gate_plan_review_response"]` | ✅ RESOLVED | Implementation: each workflow module publishes a `TERMINAL_GATE_ID` constant; dispatch calls `_resolve_terminal_gate_id(workflow_module)` and reads `state[f"gate_{terminal_gate_id}_response"]`. Planner publishes `"plan_review"`; slice_refactor publishes `"slice_refactor_review"`. Fallback to the caller's `gate_response` keyword when the constant is absent. Tests pin all three cases: `test_dispatch_result_reads_slice_refactor_gate_key_on_reject` (new path), `test_dispatch_result_preserves_planner_gate_behaviour` (regression), `test_dispatch_result_falls_back_to_gate_response_when_no_constant` (fallback). Source task's issue file (T01) flipped from `DEFERRED` → `✅ RESOLVED`. |

## 🔴 HIGH

*(None.)*

## 🟡 MEDIUM

*(None.)*

## 🟢 LOW

### M6-T05-ISS-01 — HumanGate payload carries a serialised prompt string, not a structured `SliceAggregate` object

`_render_review_prompt(state) -> str` renders every field of the `SliceAggregate` (totals + each :class:`SliceResult` with notes + each :class:`SliceFailure` with `last_error` and `failure_bucket`) into a human-readable multi-line string. The interrupt payload's `prompt` field therefore contains the full aggregate's *content*, but not as a structured Python object — a caller that wanted to programmatically re-render the aggregate in a richer UI would need to either parse the prompt (fragile) or re-hydrate the aggregate via `compiled.aget_state(cfg)`.

The T05 spec AC-4 text reads: "Gate payload is the full `SliceAggregate`; prompt formatter shows successes + failures." Under a loose reading this is satisfied (the aggregate's content is fully present in the prompt); under a strict literal reading the payload should carry a structured `aggregate` key. The current code matches the planner's pattern (its `prompt_fn` also returns a string; its payload has no `PlannerPlan` object), so raising the bar for slice_refactor would fork the primitive's contract. Not blocking for T05 given:

1. Both surface callers (CLI `aiw resume`, MCP `resume_run`) never reshape the interrupt payload — they consume the Storage-logged `prompt` string, which carries the same content.
2. The only observed consumer of a structured aggregate post-gate is the `apply` node (T06), which reads `state["aggregate"]` directly — it doesn't need the aggregate on the interrupt payload.
3. Adding a `payload_extra_fn` kwarg to `human_gate` would widen the primitive's API surface; the spec explicitly said "Scope it narrowly — do not refactor the gate surface" (albeit in the context of the `strict_review` verification).

**Action / Recommendation:** Park as a future consideration. If a UI consumer of the interrupt payload ever needs programmatic SliceAggregate access (e.g. an MCP tool returning the aggregate to the caller before resume), extend `human_gate` with an optional `payload_extra_fn: Callable[[GraphState], dict[str, Any]]` whose return dict merges into the interrupt payload. Land under the future task that introduces that UI consumer; do not open a bare "extend human_gate" refactor task now.

## Additions beyond spec — audited and justified

### 1. `TERMINAL_GATE_ID` module-level constants on both workflows

**What was added:** `TERMINAL_GATE_ID = "slice_refactor_review"` on `slice_refactor.py` and `TERMINAL_GATE_ID = "plan_review"` on `planner.py`.

**Why justified:** The T01-CARRY-DISPATCH-GATE carry-over explicitly listed two resolution options: inspect the final state for any `gate_*_response` key, or have each workflow module expose a `RESUME_GATE_ID`-style constant. The Builder chose the constant approach because it is (a) lowest blast radius — no ambiguity when a workflow has multiple `gate_*_response` keys on final state (slice_refactor does: one from the planner sub-graph, one from its own review gate); (b) self-documenting at each workflow module; and (c) a convention pattern that future workflows follow trivially. The carry-over text authorises this directly.

### 2. `_resolve_terminal_gate_id` helper in `_dispatch.py`

**What was added:** A 1-line `getattr(module, "TERMINAL_GATE_ID", None)` helper.

**Why justified:** Mirrors the existing `_resolve_tier_registry` / `_build_initial_state` pattern — dispatch exposes a narrow `_resolve_*` helper per workflow-level convention hook. Keeping the lookup in a helper (rather than inline inside `resume_run`) makes it unit-testable; `test_terminal_gate_id_constant_is_exposed` exercises the helper directly for both workflow modules.

### 3. `_apply_stub` placeholder in `slice_refactor.py`

**What was added:** An `async def _apply_stub(state, config) -> dict[str, Any]: return {}` node body.

**Why justified:** T05's AC-1 requires the gate to route to `"apply"` on approve. Without a concrete `apply` node on the graph, the conditional edge's `{"apply": "apply", ...}` target cannot resolve (LangGraph would raise at compile time). The stub's docstring flags T06 as the owner of the real body and pins the signature `(state, config) → dict[str, Any]` T06 will adopt, so replacing it is a no-rewire change. Alternative considered and rejected: route approve directly to `END` in T05 (no `apply` node). Rejected because the spec's structural AC says "approve → `apply`" — not "approve → END pending T06".

### 4. `gate_slice_refactor_review_response: str` added to `SliceRefactorState`

**What was added:** One new key on the parent TypedDict.

**Why justified:** The `human_gate` primitive writes its response to `f"gate_{gate_id}_response"` on state. LangGraph propagates sub-graph writes to the parent only when the parent declares the same channel — since the review gate runs on the parent graph (not a sub-graph), the parent must declare the channel for `_route_on_gate_response` to read it back. Scalar `str` channel, no reducer needed.

## Gate summary

| Gate | Command | Result |
| --- | --- | --- |
| Unit + integration tests | `uv run pytest` | ✅ 425 passed, 2 skipped, 2 pre-existing warnings |
| T05 suite alone | `uv run pytest tests/workflows/test_slice_refactor_strict_gate.py` | ✅ 16 passed |
| Layer enforcement | `uv run lint-imports` | ✅ 3 contracts kept, 0 broken |
| Style + import-order | `uv run ruff check` | ✅ All checks passed |
| KDR-003 grep (Anthropic) | `grep -rn anthropic\|ANTHROPIC_API_KEY` on touched files | ✅ Only a docstring-negative hit in planner.py |

## Issue log — cross-task follow-up

| ID | Severity | Description | Owner / next touch point |
| --- | --- | --- | --- |
| M6-T05-ISS-01 | 🟢 LOW (future consideration) | `human_gate` interrupt payload carries the prompt as a serialised string rather than a structured `SliceAggregate` object. Current behaviour matches the planner's pattern and surfaces the full aggregate *content* through the `prompt` + Storage `record_gate` log. | Park. Promote to a task only when a UI consumer of the interrupt payload needs programmatic aggregate access. No forward-deferral to M6 T06–T09; T06's `apply` reads `state["aggregate"]` directly. |
| T01-CARRY-DISPATCH-GATE | ✅ RESOLVED (M6 T05 Builder, 2026-04-20) | Dispatch's `_build_resume_result_from_final` hardcoded planner's `gate_plan_review_response` key. | Fixed by `TERMINAL_GATE_ID` constant on each workflow module + `_resolve_terminal_gate_id` helper in dispatch. T01 issue file already flipped. |

## Deferred to nice_to_have

*(None.)* T05's surface area is entirely within architecture.md §4.2 / §8.3 and KDR-001 scope; nothing in the implementation or test set touches a nice_to_have.md item. The 🟢 LOW noted above is a forward-looking consideration, not a nice_to_have promotion.

## Propagation status

No forward-deferrals from this audit. M6-T05-ISS-01 is a future-consideration note; T06–T09 do not depend on it. T01-CARRY-DISPATCH-GATE closed in-cycle — T01 issue file updated.
