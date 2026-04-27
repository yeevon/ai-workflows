# Task 02 — `AuditCascadeNode` graph primitive — Audit Issues

**Source task:** [../task_02_audit_cascade_node.md](../task_02_audit_cascade_node.md)
**Audited on:** 2026-04-27 (cycle 1) · re-audited 2026-04-27 (cycle 2) · re-audited 2026-04-27 (cycle 3)
**Audit scope (cycle 1):** Read-only inspection of: `ai_workflows/primitives/retry.py` (AuditFailure + classify extension + _render_audit_feedback), `ai_workflows/graph/audit_cascade.py` (new module), `ai_workflows/graph/retrying_edge.py` (docstring update), `pyproject.toml` (5th import-linter contract), `tests/primitives/test_audit_feedback_template.py` (new), `tests/graph/test_audit_cascade.py` (new), `tests/test_scaffolding.py` (contracts-count assertion update), `CHANGELOG.md`, milestone README task-table + exit-criteria, plus `architecture.md` §3 + §4.2 + §8.2 + §9 (KDR-004/006/009/011) and `error_handler.py` for the wrap_with_error_handler contract. All three gates re-run from scratch.
**Audit scope (cycle 2):** Verified the four cycle-2 spec deltas (TA-LOW-01..04 checkboxes flipped `[ ]` → `[x]`; §Out of scope line 384 `verbatim` → `without source-code edit (the cascade-transcript prompt_fn is HumanGate's documented extension point, not a fork)`); confirmed Builder did not touch source code, tests, CHANGELOG, issue file, or run any forbidden git/publish op; confirmed Locked-decision stamp on MED-01 intact and spec lines 91 + 382 still untouched (deferred to M12 T07); confirmed all 5 LOWs remain DEFERRED-with-owner. All three gates re-run from scratch.
**Audit scope (cycle 3):** Verified the three TEAM-FIX deltas applied in `tests/graph/test_audit_cascade.py` per the cycle-2 Locked team decision: TEAM-FIX-01 degenerate assertion at line 396 replaced with two direct asserts (`Attempts recorded: 2` + `bad shape`); TEAM-FIX-02 `_StubClaudeCodeAdapter` docstring at lines 87-93 corrected (false "shared script" claim removed, accurate "Populated separately from `_StubLiteLLMAdapter`" wording in place); TEAM-FIX-03a test #4 docstring/comments at lines 414-425 rewritten to accurately describe hybrid scenario (auditor fires once on shape-valid third attempt); TEAM-FIX-03b new test `test_cascade_pure_shape_failure_never_invokes_auditor` at lines 463-514 added — exercises in-validator NonRetryable escalation (`validator_node.py:136-142`) under `_POLICY_2`, asserts `_StubClaudeCodeAdapter.calls == 0`. Independently verified `_cascade_gate_prompt_fn` at `audit_cascade.py:708-749` actually emits both the `Attempts recorded: N` substring and the per-`failure_reason` `  - {r}` lines that make TEAM-FIX-01's `bad shape` assertion non-tautological. Confirmed Builder touched ONLY `tests/graph/test_audit_cascade.py` (no source code, no spec, no CHANGELOG, no README, no issue file, no forbidden git/publish op). All three gates re-run from scratch.
**Status:** ✅ PASS — FUNCTIONALLY CLEAN; all 3 TEAM-FIX findings RESOLVED (cycle 3); ready for loop-controller to confirm prior security + dep-audit + sr-dev + sr-sdet verdicts (cycle 2: SHIP / SHIP / FIX-THEN-SHIP-now-resolved / FIX-THEN-SHIP-now-resolved) carry forward (cycle-3 deltas are test-only — source code, dependencies, and ACs unchanged from cycle 2). MED-01 deferred to M12 T07 close-out (Locked decision intact); MED-02 RESOLVED (cycle 2); 5 LOWs all DEFERRED-with-owner.

> **Locked team decision (loop-controller + sr-dev + sr-sdet concur, 2026-04-27):** Three test-quality fixes land in cycle 3:
>
> - **TEAM-FIX-01** (sr-dev + sr-sdet concur) — Replace degenerate assertion at `tests/graph/test_audit_cascade.py:396` (`"author_attempts" not in prompt_text or "Attempts recorded: 2" in prompt_text` is a permanent tautology because `_cascade_gate_prompt_fn` never emits the literal `"author_attempts"`). Fix: replace with two direct assertions — `assert "Attempts recorded: 2" in prompt_text` and `assert "bad shape" in prompt_text` — to give AC-8 (gate prompt carries transcript) real coverage.
>
> - **TEAM-FIX-02** (sr-dev + sr-sdet concur) — Correct `_StubClaudeCodeAdapter` docstring at `tests/graph/test_audit_cascade.py:87-90`. The current docstring claims `script` is shared with `_StubLiteLLMAdapter`; they are independent class-level attributes populated independently per test. Replace with accurate description of the separate auditor-path script.
>
> - **TEAM-FIX-03** (sr-sdet) — Test #4 (`test_cascade_validator_failure_routes_back_to_primary_not_auditor`) docstring claims auditor `calls == 0` but the actual assertion is `== 1` (auditor fires on the third shape-valid attempt). Spec's test #4 + AC-9 call for the pure-exhaustion scenario (primary always shape-invalid, auditor never invoked). Fix: (a) correct the existing test's docstring/comments to accurately describe what it asserts (validator-failure short-circuits auditor on the failing attempt; auditor only fires on the shape-valid third attempt), AND (b) add a companion test `test_cascade_pure_shape_failure_never_invokes_auditor` for the pure-exhaustion path where every primary attempt fails shape and `_StubClaudeCodeAdapter.calls == 0`.
>
> Auditor concurs (cycle 2 verdict was ✅ PASS modulo team gate); none of the three FIX findings conflict with KDRs, none expand scope beyond the existing test files, none defer work to a non-existent task. Cycle 3 is test-touch only — no source code or spec changes expected.

## Design-drift check

Cross-referenced every change against the seven load-bearing KDRs and the four-layer rule.

| KDR / Rule | Drift? | Notes |
| --- | --- | --- |
| KDR-002 (MCP portable surface) | No | T02 is graph-layer only; no MCP edits. |
| KDR-003 (no Anthropic API) | No | `grep -rn anthropic\|ANTHROPIC_API_KEY` over `audit_cascade.py` + `retry.py` returns zero hits. Tree-wide guardrail (`tests/workflows/test_slice_refactor_e2e.py::test_kdr_003_no_anthropic_in_production_tree`) walks `rglob("*.py")` and passes. |
| KDR-004 (validator after every LLM node) | No | Cascade wires `tiered_node(primary) → validator_node(shape) → tiered_node(auditor) → verdict_node` — validator is paired with primary; auditor's `output_schema=AuditVerdict` carries pydantic shape pairing. |
| KDR-006 (three-bucket retry taxonomy) | No (with caveat) | `AuditFailure` subclasses `RetryableSemantic`; no new bucket added. The two-line `classify()` extension preserves the three-bucket return space (still `RetryableTransient` / `RetryableSemantic` / `NonRetryable`); pre-classified bucket instances now route to their own type rather than falling through to `NonRetryable`. See M12-T02-MED-01 — this fixes a spec internal contradiction; it does not break KDR-006. |
| KDR-008 (FastMCP public contract) | No | No MCP tool added at T02. |
| KDR-009 (LangGraph SqliteSaver owns checkpointing) | No | Cascade transcript lives in graph state; no new persistence table. Smoke test composes against `build_async_checkpointer`. |
| KDR-011 (tiered audit cascade) | No | T02 is the foundational cascade primitive; behavioural surface (verdict raises `AuditFailure` → `RetryingEdge` re-fires primary with rendered feedback → `HumanGate(strict_review=True)` on exhaustion) matches the KDR's spec exactly. |
| KDR-013 (user-owned external code) | N/A | No external loader changes. |
| Four-layer rule | No | `audit_cascade.py` imports only from `graph/*` + `primitives/*`. New 5th import-linter contract (`audit_cascade composes only graph + primitives`) explicitly forbids `workflows`/`cli`/`mcp`. `lint-imports` reports `5 contracts kept`. |

**No drift detected.** The `classify()` extension is a defensible fix to a spec contradiction (graded MEDIUM under M12-T02-MED-01).

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| 1. `retry.py` exports `AuditFailure` (`RetryableSemantic` subclass); `__all__` includes it; `_render_audit_feedback` template matches spec literal | ✅ Met | `AuditFailure` declared at retry.py:146, in `__all__` at line 60-67. `_render_audit_feedback` body matches the spec literal exactly; pinned by `test_audit_feedback_template_full_shape`. |
| 2. `classify(AuditFailure(...)) is RetryableSemantic` — no edit to `classify()` required | ⚠️ Met but spec wrong | `classify()` was extended (two lines) — see M12-T02-MED-01. Builder explicitly surfaced the deviation. The AC is functionally satisfied (`test_audit_failure_is_retryable_semantic` passes); the *spec* claim that no edit was required is internally contradictory and the Builder picked the correct minimal resolution. |
| 3. `audit_cascade.py` exports `audit_cascade_node` factory + `AuditVerdict`; returns `CompiledStateGraph` composable in outer | ✅ Met | `__all__ = ["AuditVerdict", "audit_cascade_node"]` at line 66; factory returns `g.compile()`; composability pinned by `test_cascade_returns_compiled_state_graph_composable_in_outer`. |
| 4. Sub-graph wires primary → validator → auditor → verdict; verdict raises AuditFailure on `passed=False`; RetryingEdge routes back via `on_semantic` | ✅ Met | Wiring matches spec §Sub-graph wiring exactly (audit_cascade.py:420-447). Verdict node raises `AuditFailure` at line 695. `_decide_after_verdict` routes RetryableSemantic-bucket exceptions to `f"{name}_primary"` while under budget. Pinned by `test_cascade_re_fires_with_audit_feedback_in_revision_hint`. |
| 5. Re-prompt template byte-equal to spec literal | ✅ Met | `_render_audit_feedback` produces the exact `<orig>\n\n<audit-feedback>\nReasons:\n- r1\n- r2\nSuggested approach: try X\n</audit-feedback>\n\n<ctx>` literal from the spec. Pinned by `test_audit_feedback_template_full_shape`. |
| 6. `cascade_transcript` populated across attempts; survives via SqliteSaver (no new table) | ✅ Met | Transcript dict written by verdict node on success path (line 698-703). On failure path the transcript is attached to `AuditFailure.cascade_transcript` and re-merged on the next cycle by `_audit_verdict_node` (line 660-668). Surface confirmed by tests #2 (length-2 after re-fire) and #3 (length-2 after exhaustion). No new persistence table. |
| 7. `cascade_role` stamped by each cascade sub-node (`author`/`auditor`/`verdict`) | ✅ Met | `_stamp_role_on_success` wraps primary (`role="author"`, line 226) and auditor (`role="auditor"`, line 261); verdict node returns `cascade_role="verdict"` (line 701). Final `cascade_role` is `"verdict"` (last writer); pinned by `test_cascade_role_tags_stamped_on_state`. |
| 8. Exhaustion routes to strict `HumanGate(strict_review=True)` carrying transcript | ✅ Met | `human_gate(..., strict_review=True)` at line 295. Test #3 asserts `interrupt_payload["strict_review"] is True` and the transcript is rendered into the gate prompt by `_cascade_gate_prompt_fn`. Both transcript-source paths covered (state['cascade_transcript'] OR exc.cascade_transcript). |
| 9. Validator shape failure short-circuits the auditor | ✅ Met | `test_cascade_validator_failure_routes_back_to_primary_not_auditor` asserts `_StubClaudeCodeAdapter.calls` length is 1 (only the shape-valid attempt) after 3 primary attempts. The `_decide_after_validator` wrapper additionally intercepts `NonRetryable` (in-validator escalation) and routes to gate rather than forward to auditor — defensive correctness. |
| 10. No `workflows/` / `mcp/` / `evals/` / `pricing.yaml` diff | ✅ Met | git status shows only the spec'd files touched. No workflow integration, no MCP tool, no eval fixtures, no pricing.yaml change. |
| 11. New 5th import-linter contract scoped to audit_cascade; lint-imports reports `5 contracts kept` | ✅ Met | Contract added at pyproject.toml:194-202. Re-run `uv run lint-imports`: `Contracts: 5 kept, 0 broken`. |
| 12. KDR-003 guardrails pass (existing tree-wide test covers new module) | ✅ Met | `test_kdr_003_no_anthropic_in_production_tree` walks `rglob("*.py")` and passes; covers `audit_cascade.py` automatically. |
| 13. `pytest` + `lint-imports` (5 contracts) + `ruff check` all clean | ✅ Met | Re-run from scratch: pytest 770 passed / 9 skipped / 28 warnings; lint-imports 5/5 KEPT; ruff All checks passed. |
| 14. CHANGELOG entry under `[Unreleased]` with files + ACs + KDR citations | ✅ Met | CHANGELOG.md:10-54 — citations for KDR-004 / KDR-006 / KDR-011, files-touched list, ACs satisfied, deviation explicitly called out. |
| 15. Smoke test exercises wire-level cascade via `tiered_node` + `validator_node` + `wrap_with_error_handler` (only LLM dispatch stubbed) | ✅ Met | `test_cascade_pass_through` invokes the compiled cascade end-to-end through real `tiered_node` / `validator_node` / `wrap_with_error_handler` / `retrying_edge` / `human_gate`. Only `LiteLLMAdapter` and `ClaudeCodeSubprocess` are monkey-patched. Re-run in isolation: PASSED in 1.12s. |
| 16. Status surfaces flipped together (spec Status, README task-table row 02, exit-criteria 2/3/4/11/12) | ✅ Met | Spec line 3 `**Status:** ✅ Complete (2026-04-27)`. README task-table row 02 `✅ Complete (2026-04-27)`. Exit-criteria bullets 2, 3, 4, 11, 12 each prefixed `✅ (T02 complete 2026-04-27)`. Bullets 5/6/7/8/9/10 correctly remain unflipped (those land at T03–T07). No `tasks/README.md` for M12. |

## Carry-over from task analysis (TA-LOW-01..04) grading

| Carry-over | Status | Notes |
| --- | ------ | ----- |
| TA-LOW-01 — Drop `(drafted 2026-04-27)` parenthetical from Status line | ✅ Met (cycle 2) | Cycle 1: Status flipped from `📝 Planned (drafted 2026-04-27)` to `✅ Complete (2026-04-27)` (parenthetical now means "completion date"). Cycle 2: checkbox `[x]` ticked at spec line 403. |
| TA-LOW-02 — Replace `HumanGate verbatim` phrasing in §Out of scope | ✅ Met (cycle 2) | Spec line 384 now reads `T02 reuses HumanGate(strict_review=True) without source-code edit (the cascade-transcript prompt_fn is HumanGate's documented extension point, not a fork)`. Checkbox `[x]` ticked at spec line 407. |
| TA-LOW-03 — Sketch test #5's outer-graph state schema | ✅ Met (cycle 2) | Implementation includes `_OuterState` TypedDict in `tests/graph/test_audit_cascade.py:541-558` covering all required channels. Cycle 2: checkbox `[x]` ticked at spec line 411. |
| TA-LOW-04 — Sketch `_default_primary_original` helper body in §Internal node block | ✅ Met (cycle 2) | Implementation at `audit_cascade.py:591-606` matches the recommended body exactly: `(system or "") + "\n\n" + "\n".join(m.get("content", "") for m in messages)`. Test #2's byte-equal assertion validates the join shape. Cycle 2: checkbox `[x]` ticked at spec line 415. |

All four carry-overs RESOLVED at cycle 2 — see M12-T02-MED-02 (now CLOSED).

## 🔴 HIGH

*None.*

## 🟡 MEDIUM

### M12-T02-MED-01 — Spec internal contradiction: `classify()` "no edit needed" claim vs AC-2

**Where:** Spec line 91 (`No edit to classify() — AuditFailure is structurally a RetryableSemantic`) + line 382 (`No classify() taxonomy edit`) **vs** AC-2 (`classify(AuditFailure(...)) is RetryableSemantic`).

**Finding:** At HEAD (pre-Builder), `classify()` had no `isinstance(exc, RetryableSemantic)` branch — its fall-through returned `NonRetryable` for everything not matching LiteLLM/subprocess types. Therefore `classify(AuditFailure(...)) is RetryableSemantic` was unsatisfiable without an edit. The spec claimed the existing classifier's `isinstance` mapping already handled the case; it did not.

**Builder's resolution:** Added a two-line extension at retry.py:267-270:
```python
if isinstance(exc, RetryableSemantic):
    return RetryableSemantic
if isinstance(exc, RetryableTransient):
    return RetryableTransient
```

**Auditor verdict on the resolution:**
- The extension preserves KDR-006's three-bucket taxonomy (no new bucket; only existing bucket return values).
- The extension is idempotent for pre-classified instances — it does not retroactively re-classify legitimate `NonRetryable` cases (LiteLLM `BadRequestError` etc. are caught by the earlier `_LITELLM_NON_RETRYABLE` branch).
- The extension does not affect pydantic `ValidationError` (still `NonRetryable` via fall-through; module docstring's invariant preserved).
- The extension is the minimal correct fix.

**Severity:** MEDIUM (spec defect — author claimed a property of `classify()` that was demonstrably false; the AC could not be satisfied without code change). The Builder picked the right resolution.

**Action / Recommendation:** Update the spec's `## Out of scope` line 382 from `**No classify() taxonomy edit.**` to `**No classify() taxonomy edit beyond an idempotent pre-classified pass-through.** AuditFailure rides the existing RetryableSemantic bucket via subclassing; classify() returns the same bucket type when handed any pre-classified instance.` Also update spec line 91 similarly. Cross-reference the change in CHANGELOG (already done — line 21-22 documents the extension). Owner: this issue file (audit cycle), no carry-over needed since the deviation is already implemented and documented; the spec edit is a docs-only follow-up (M12 T07 close-out is a natural home).

> **Locked decision (loop-controller + Auditor concur, 2026-04-27):** The two-line `classify()` extension at `retry.py:267-270` is the correct minimal fix to a spec defect — AC-2 (`classify(AuditFailure(...)) is RetryableSemantic`) was unsatisfiable without it because `classify()`'s pre-Builder fall-through returned `NonRetryable` for any exception not matching the LiteLLM/subprocess tuples. Auditor verifies: (a) extension preserves three-bucket taxonomy (KDR-006 intact), (b) idempotent for pre-classified instances (does not retroactively re-classify legitimate `NonRetryable` cases), (c) does not affect pydantic `ValidationError` (still falls through to `NonRetryable`). Spec text amendment (lines 91 + 382 of the T02 spec) deferred to M12 T07 close-out alongside the existing ADR-0004 stale-framing items (M12-T01-ISS-02 + ADR-0004 §Consequences line 54). No cycle-2 Builder action required for MED-01.

### M12-T02-MED-02 — Carry-over from task analysis not ticked despite implicit handling — ✅ RESOLVED (cycle 2)

**Where:** Spec lines 401-417, four `[ ]` checkboxes for TA-LOW-01..04.

**Cycle 1 finding:** Per CLAUDE.md "Carry-over section at the bottom of a spec = extra ACs. Tick each as it lands." The Builder addressed three of the four LOWs implicitly (TA-LOW-01 by Status flip, TA-LOW-03 by implementation, TA-LOW-04 by implementation) but did not tick the checkboxes. TA-LOW-02 (text replacement in §Out of scope) was not addressed at all. None of the four checkboxes flipped to `[x]`.

**Severity:** MEDIUM (status-surface drift — the status of these ACs is not visible from the spec).

**Cycle 2 resolution (2026-04-27):** Builder applied four spec edits as directed:
- TA-LOW-01 checkbox at spec line 403 flipped `[ ]` → `[x]`.
- TA-LOW-02 checkbox at spec line 407 flipped `[ ]` → `[x]`; §Out of scope line 384 replaced from `T02 reuses HumanGate(strict_review=True) verbatim.` → `T02 reuses HumanGate(strict_review=True) without source-code edit (the cascade-transcript prompt_fn is HumanGate's documented extension point, not a fork).`
- TA-LOW-03 checkbox at spec line 411 flipped `[ ]` → `[x]`.
- TA-LOW-04 checkbox at spec line 415 flipped `[ ]` → `[x]`.

Auditor verified: all four `[x]` checkboxes present in spec; line-384 text replacement byte-exact to the cycle-1 recommendation; no other spec edits, no source-code touch, no issue-file touch by Builder, no forbidden git/publish op. Status-surface drift cleared.

**Action / Recommendation:** None remaining. Closed.

## 🟢 LOW

### M12-T02-LOW-01 — `_failure_state_update` cross-module import (leading-underscore symbol)

**Where:** `audit_cascade.py:53` imports `_failure_state_update` (a leading-underscore module-private symbol) from `error_handler.py`.

**Finding:** Convention says leading-underscore symbols are not re-exported / not imported by sibling modules. The Builder reused `_failure_state_update` to keep transcript-preservation logic identical to the standard error wrapper; the alternative (duplicating the dict-shape construction) would risk drift if the wrapper's shape ever changes.

**Severity:** LOW (justified-but-noisy — the reuse is correct, but the underscore on the imported symbol signals an architectural invariant that's now fuzzier).

**Action / Recommendation:** Two options — (a) rename `_failure_state_update` to `failure_state_update` (drop the underscore, add to `__all__` in error_handler.py) and update the import, OR (b) leave as-is and add a docstring sentence in `_wrap_verdict_with_transcript` noting the deliberate cross-module reach into a private symbol. Option (a) is cleaner; option (b) is lower-disruption. Owner: M12 T03 builder (since T03 will likely also need this pattern when wiring the workflow-level cascade) or M12 T07 close-out. Either way, a one-touch change.

### M12-T02-LOW-02 — LangGraph type-annotation pickiness warning

**Where:** `audit_cascade.py:423` — `g.add_node(f"{name}_verdict", verdict_node)` — emits at run-time `UserWarning: The 'config' parameter should be typed as 'RunnableConfig' or 'RunnableConfig | None', not 'RunnableConfig | None'.`

**Finding:** LangGraph's introspection treats `RunnableConfig | None` (PEP 604 union syntax) differently from `Optional[RunnableConfig]` in some path. Cosmetic warning; behaviour unchanged.

**Severity:** LOW (cosmetic; harmless).

**Action / Recommendation:** Either annotate `config` as `RunnableConfig` (no `| None` — defaults to `None` at runtime stays valid) on the inner `_wrapped` of `_wrap_verdict_with_transcript` and `_stamp_role_on_success`, OR add a `# noqa` / filterwarnings on this specific UserWarning. Lowest-disruption option is to drop the `| None` from the annotation since `config` defaults to `None` anyway. Owner: M12 T03 builder (touches the same wrappers when wiring workflow-level cascade) or post-hoc cleanup.

### M12-T02-LOW-03 — `_DynamicState` TypedDict regenerated per call

**Where:** `audit_cascade.py:393-417` — `TypedDict` constructed dynamically inside `audit_cascade_node()` for each cascade instance.

**Finding:** Constructing a `TypedDict` at runtime is unusual and harmless, but each call to `audit_cascade_node` creates a new type object. For the M12 use case (one cascade per workflow call site, called once per workflow build) this is fine. If T03's wiring ends up calling `audit_cascade_node` inside a hot path (e.g. per-slice), the per-call `TypedDict` creation is a minor inefficiency.

**Severity:** LOW (forward-looking flag; not a current issue).

**Action / Recommendation:** Note in M12 T03 spec that `audit_cascade_node` should be called at workflow build time (once per cascade site), not at runtime per slice. Owner: M12 T03 spec author.

### M12-T02-LOW-04 — Test #2's `_render_audit_feedback` direct import

**Where:** `tests/primitives/test_audit_feedback_template.py:24` and `tests/graph/test_audit_cascade.py:335` both import `_render_audit_feedback` (module-private) directly with `# type: ignore[attr-defined]`.

**Finding:** Spec sanctions this for the template-shape contract test (test #1 in `test_audit_feedback_template.py`); the Builder also used it inside the wire-level test #2 in `test_audit_cascade.py` to construct the expected literal for the byte-equal assertion. The spec actually permits this on test #2 (`assert against the helper's output for the same args`).

**Severity:** LOW (acknowledged by spec; documenting for posterity).

**Action / Recommendation:** None required. If a future refactor renames `_render_audit_feedback`, both test files break — that's the intended drift signal. No action.

### M12-T02-LOW-05 — Auditor counter is separate from primary counter (spec inconsistency)

**Where:** Spec §Sub-graph wiring line 207 says auditor is wrapped with `node_name=f"{name}_auditor"` (separate counter); spec §Counter-sharing contract line 222 says "validator + verdict + primary all bump the same `_retry_counts[f"{name}_primary"]` key" (silent on the auditor). Implementation matches spec §Sub-graph wiring (auditor uses separate `f"{name}_auditor"` counter).

**Finding:** Reading both sections together, the auditor is *also* part of the cascade but its budget is tracked separately. This is the right behaviour (auditor failures shouldn't burn the primary's budget), but the §Counter-sharing contract section is incomplete — it should say "validator + verdict + primary share one counter; auditor has its own."

**Severity:** LOW (spec ambiguity caught and resolved correctly by Builder; doc polish).

**Action / Recommendation:** Update spec §Counter-sharing contract to mention the auditor's separate counter. Owner: M12 T07 close-out (single ADR-0004/T02 spec amendment).

## Additions beyond spec — audited and justified

| Addition | Justification | Verdict |
| --- | --- | --- |
| `_wrap_verdict_with_transcript` custom error-handler wrapper | Required because `wrap_with_error_handler` discards non-exception state writes on raise — the verdict node's `cascade_transcript` write would be lost on failure cycles. The wrapper merges `exc.cascade_transcript` into the failure-state dict so transcript accumulation survives across retry cycles. | ✅ Justified — necessary for spec §Counter-sharing contract + AC-6 (transcript populated across attempts). |
| `_decide_after_verdict` custom edge function | The stock `retrying_edge` cannot distinguish "verdict success" from "verdict semantic-budget exhaustion" because both map to `on_terminal`. A custom edge that returns `END` on success and `human_gate` on exhaustion is required. | ✅ Justified — alternative would require a sentinel state channel; custom edge is simpler. |
| `_decide_after_validator` wrapper around `retrying_edge` | The stock `retrying_edge` would forward `NonRetryable` (from in-validator escalation) to `on_terminal=auditor`, which would audit a shape-invalid primary. The wrapper intercepts `NonRetryable` and routes to `human_gate` directly. | ✅ Justified — defensive correctness for the spec's pure-shape-failure-only sequence (test #4). |
| `cascade_transcript` attached as attribute on `AuditFailure` (not in `__init__` signature) | Required because the verdict node must accumulate the transcript across cycles, but the `AuditFailure.__init__` signature in the spec does not accept a transcript parameter. Attaching post-construction (line 694) is a pragmatic compromise. | ✅ Justified but worth noting — alternative would be to extend `AuditFailure.__init__` to accept transcript; spec signature was pinned, so attribute attachment was the lower-disruption path. |
| Dynamic `TypedDict` per call to `audit_cascade_node` | Required because LangGraph's `StateGraph(dict)` doesn't accumulate state across nodes — `TypedDict` does. Channels are name-prefixed at runtime so the schema is per-instance. | ✅ Justified — see M12-T02-LOW-03 for the forward-looking flag. |
| `tests/test_scaffolding.py` updated to assert `len(contracts) == 5` + `audit_cascade` name match | Natural corollary of adding the 5th contract — keeps the test infrastructure aligned with the live contract count. The assertion shape mirrors existing tests (substring matching). | ✅ Justified — Builder explicitly flagged this; assertion shape correct. |

## Gate summary

| Gate | Command | Result |
| ---- | ------- | ------ |
| pytest | `uv run pytest -q` | 770 passed / 9 skipped / 28 warnings — PASS |
| import-linter | `uv run lint-imports` | `Contracts: 5 kept, 0 broken` — PASS |
| ruff | `uv run ruff check` | All checks passed — PASS |
| Smoke (wire-level) | `uv run pytest tests/graph/test_audit_cascade.py::test_cascade_pass_through -v` | PASSED in 1.12s — confirms cascade end-to-end through real `tiered_node`+`validator_node`+`wrap_with_error_handler`+`retrying_edge`+`human_gate` (only `LiteLLMAdapter`/`ClaudeCodeSubprocess` stubbed) — PASS |
| KDR-003 guardrail | `uv run pytest tests/workflows/test_slice_refactor_e2e.py::test_kdr_003_no_anthropic_in_production_tree` | PASS — covers `audit_cascade.py` via `rglob("*.py")` |

All gates green from scratch.

**Cycle 2 gate re-run (2026-04-27):**

| Gate | Command | Result |
| ---- | ------- | ------ |
| pytest | `uv run pytest -q` | 770 passed / 9 skipped / 28 warnings — PASS (identical to cycle 1; consistent with no-source-code-changed Builder report) |
| import-linter | `uv run lint-imports` | `Contracts: 5 kept, 0 broken` — PASS |
| ruff | `uv run ruff check` | All checks passed — PASS |

No gate-integrity drift. Builder's cycle-2 report aligned with re-run results.

**Cycle 3 gate re-run (2026-04-27):**

| Gate | Command | Result |
| ---- | ------- | ------ |
| pytest | `uv run pytest -q` | **771 passed** / 9 skipped / 29 warnings — PASS (+1 net new test from TEAM-FIX-03b; expected delta) |
| import-linter | `uv run lint-imports` | `Contracts: 5 kept, 0 broken` — PASS |
| ruff | `uv run ruff check` | All checks passed — PASS |
| smoke (wire-level) | `uv run pytest tests/graph/test_audit_cascade.py -v` | 7 passed (was 6) — PASS |
| TEAM-FIX-03b targeted | `uv run pytest tests/graph/test_audit_cascade.py::test_cascade_pure_shape_failure_never_invokes_auditor -v` | PASSED in 1.18s — confirms in-validator NonRetryable escalation routes via `_decide_after_validator` to `human_gate`, never reaches auditor (`_StubClaudeCodeAdapter.calls == 0`) |

No gate-integrity drift. Builder's cycle-3 report (test-touch only, +1 test, gates green) aligned with re-run results.

## Cycle 3 TEAM-FIX verification (per cycle-2 Locked team decision)

| Finding | Resolution | Auditor verification | Status |
| --- | --- | --- | --- |
| TEAM-FIX-01 (degenerate `or` assertion at line 396) | Two direct asserts at `test_audit_cascade.py:397-398`: `assert "Attempts recorded: 2" in prompt_text` and `assert "bad shape" in prompt_text` | Independently inspected `_cascade_gate_prompt_fn` (`audit_cascade.py:708-749`): line 733 emits `Attempts recorded: {n}`; line 741 emits `  - {r}` per failure reason. With `_AUDIT_FAIL_JSON.failure_reasons=["bad shape"]`, the rendered prompt contains the literal `bad shape`. Both assertions are non-tautological and provide AC-8 enforcement. Targeted test re-run (test 3) PASSED. | ✅ RESOLVED |
| TEAM-FIX-02 (false "shared with `_StubLiteLLMAdapter`" docstring at lines 87-90) | Docstring at `test_audit_cascade.py:87-93` rewritten: now reads "auditor-tier path. Holds an independent class-level `script` ... Populated separately from `_StubLiteLLMAdapter` ...; the two adapters do not share state." | Inspected lines 87-93: false "shared" claim removed; new wording accurately describes the independent FIFO list and the explicit non-sharing of state. | ✅ RESOLVED |
| TEAM-FIX-03a (test #4 docstring claimed "0 calls" but asserted "1 call") | Docstring at `test_audit_cascade.py:414-425` rewritten: now reads "Hybrid scenario: ... on attempt 3 the primary returns shape-valid output, the validator passes, and the auditor is invoked exactly once (and passes)." Inline comment at line 454: `# Auditor fired only once (only on the shape-valid third attempt).` Final assertion at line 455 unchanged: `assert len(_StubClaudeCodeAdapter.calls) == 1`. | Inspected lines 414-455: docstring + comments + assertions are now consistent. The hybrid scenario is correctly described. | ✅ RESOLVED |
| TEAM-FIX-03b (missing pure-exhaustion AC-9 test) | New test `test_cascade_pure_shape_failure_never_invokes_auditor` added at `test_audit_cascade.py:463-514`. Primary script returns invalid JSON twice (`_POLICY_2.max_semantic_attempts=2`); auditor script empty; asserts `__interrupt__` present, `len(_StubLiteLLMAdapter.calls) == 2`, `len(_StubClaudeCodeAdapter.calls) == 0`. | Verified the test correctly exercises the in-validator escalation path: with `prior_failures=1, max_attempts=2`, `1 >= 2-1=1 → True`, validator raises `NonRetryable` (`validator_node.py:136-142`); `_decide_after_validator` (`audit_cascade.py:322-334`) intercepts `NonRetryable` and routes to `f"{name}_human_gate"` directly, bypassing the auditor. Empty auditor script provides defense-in-depth — if cascade ever reached the auditor, the stub would raise `AssertionError("stub script exhausted (claude)")`. The test passes only because the cascade short-circuits the auditor before reaching it. AC-9's pure-exhaustion variant now pinned. | ✅ RESOLVED |

All three TEAM-FIX findings (and the 03b add-on) are RESOLVED in cycle 3. No new findings surfaced; no spec drift; no source code touched.

## Issue log — cross-task follow-up

| ID | Severity | Owner / Next touch point | Status |
| -- | -------- | ------------------------ | ------ |
| M12-T02-MED-01 | MEDIUM | M12 T07 close-out (ADR-0004 + spec amendment) — update spec lines 91 + 382 to acknowledge the idempotent pre-classified pass-through | DEFERRED (Locked decision stamped 2026-04-27; cycle 2 verified spec lines 91 + 382 still untouched per Locked decision) |
| M12-T02-MED-02 | MEDIUM | Builder (cycle 2) — tick TA-LOW-01/02/03/04 checkboxes; apply TA-LOW-02 text replacement to spec line 384 | ✅ RESOLVED (cycle 2 — all four spec edits applied + verified) |
| M12-T02-LOW-01 | LOW | M12 T07 close-out — rename `_failure_state_update` → `failure_state_update` (export it) | DEFERRED (owner: M12 T07) |
| M12-T02-LOW-02 | LOW | M12 T03 builder (will touch same wrappers when wiring workflows) — drop `\| None` from `config` annotations on `_wrapped` inner functions | DEFERRED (owner: M12 T03) |
| M12-T02-LOW-03 | LOW | M12 T03 spec author — note `audit_cascade_node` is build-time, not runtime | DEFERRED (owner: M12 T03) |
| M12-T02-LOW-04 | LOW | None required | NO ACTION |
| M12-T02-LOW-05 | LOW | M12 T07 close-out — update spec §Counter-sharing contract to mention auditor's separate counter | DEFERRED (owner: M12 T07) |

## Deferred to nice_to_have

*None.* No findings naturally map to `nice_to_have.md` items.

## Propagation status

Forward-deferrals to add as `## Carry-over from prior audits` on the target task spec(s):

- **M12 T03** (`task_03_workflow_wiring.md`) — when this spec is drafted at T02 close-out, include the following carry-over:
  - **M12-T02-LOW-02** — When wiring workflow-level cascades, drop `RunnableConfig | None` annotations on the cascade wrappers' inner functions to silence LangGraph's `UserWarning` (`audit_cascade.py:478`, `audit_cascade.py:533`).
  - **M12-T02-LOW-03** — Document that `audit_cascade_node()` should be called at workflow build time, not per runtime invocation (e.g. per slice in `slice_refactor`).

- **M12 T07** (close-out) — when this spec is drafted, include:
  - **M12-T02-MED-01** — Spec amendment: update spec lines 91 + 382 to acknowledge the idempotent pre-classified pass-through extension to `classify()`. Cross-reference the live `retry.py:267-270` block.
  - **M12-T02-LOW-01** — Code refactor: rename `_failure_state_update` → `failure_state_update` (drop underscore, add to `error_handler.py` `__all__`); update the cross-module import in `audit_cascade.py:53`.
  - **M12-T02-LOW-05** — Spec polish: §Counter-sharing contract to mention the auditor's separate counter alongside the primary/validator/verdict shared key.
  - Plus the existing T01 deferrals (ADR-0004 §Decision item 1 stale framing, ADR-0004 §Consequences line 54 superseded).

T03 and T07 specs do not yet exist (spec'd at predecessor close-out per milestone README convention). The Builder for T03 / T07 will see these carry-over items in their spec at draft time. Status here flips from `DEFERRED` → `RESOLVED (commit sha)` on each subsequent re-audit.

---

**Status:** ✅ PASS — FUNCTIONALLY CLEAN, ready for security gate. Cycle 2 (2026-04-27): MED-02 RESOLVED (all four TA-LOW carry-overs `[x]` ticked + TA-LOW-02 text replacement applied to spec line 384); MED-01 carries Locked decision deferred to M12 T07 close-out (spec lines 91 + 382 stay untouched until then; the live `classify()` extension is correct + KDR-006 preserved); 5 LOWs all DEFERRED-with-owner (M12-T02-LOW-01/05 → M12 T07; LOW-02/03 → M12 T03; LOW-04 NO ACTION). All three gates green from scratch (pytest 770/9, lint-imports 5/5, ruff clean). No new findings in cycle 2. Builder's cycle-2 report (4 spec edits, no source-code touch, no forbidden git/publish op) verified accurate.

**Cycle 3 close (2026-04-27):** All 3 TEAM-FIX findings from the cycle-2 Locked team decision RESOLVED in `tests/graph/test_audit_cascade.py` (test-touch-only diff): TEAM-FIX-01 degenerate `or`-assertion replaced with two direct asserts (line 397-398; both substrings independently verified to appear in `_cascade_gate_prompt_fn` output); TEAM-FIX-02 `_StubClaudeCodeAdapter` docstring corrected (false "shared script" claim removed); TEAM-FIX-03a test #4 docstring/comments rewritten to accurately describe hybrid scenario; TEAM-FIX-03b new test `test_cascade_pure_shape_failure_never_invokes_auditor` added pinning AC-9's pure-exhaustion variant (`_StubClaudeCodeAdapter.calls == 0`). All three gates green from scratch (**pytest 771/9** — net +1 test, lint-imports 5/5, ruff clean); seven cascade tests pass individually. No new findings; no source code touched; no spec/CHANGELOG/README/issue-file edits by Builder; no forbidden git/publish op. Open issues unchanged from cycle 2: MED-01 deferred to M12 T07 (Locked decision intact); MED-02 RESOLVED (cycle 2); 5 LOWs DEFERRED-with-owner. Cycle-2 SHIP verdicts from security-reviewer + dependency-auditor stand (cycle-3 deltas are test-only — no source/dep change). Cycle-2 sr-dev FIX-THEN-SHIP and sr-sdet FIX-THEN-SHIP verdicts are now satisfied (their three FIX findings are the resolved TEAM-FIX-01/02/03 above) — both teams' Advisory items remain DEFERRED-with-owner per cycle 2.

## Security review (2026-04-27)

**Scope:** `ai_workflows/graph/audit_cascade.py` (new, ~750 lines), `ai_workflows/primitives/retry.py` (`AuditFailure` + `_render_audit_feedback` + `classify()` extension), `pyproject.toml` (5th import-linter contract), test files in `tests/`.

### Checked items (threat model rebased to T02 diff)

**1. KDR-003 boundary — no ANTHROPIC_API_KEY / anthropic SDK**

`grep -rn "ANTHROPIC_API_KEY" ai_workflows/` — zero hits. `grep -rn "import anthropic\|from anthropic" ai_workflows/graph/audit_cascade.py ai_workflows/primitives/retry.py` — zero hits. `audit_cascade.py` reaches only `graph/*` and `primitives/*` imports; the new 5th import-linter contract (`audit_cascade composes only graph + primitives`) explicitly forbids `workflows/cli/mcp` imports and is verified at lint-imports time. KDR-003 boundary intact.

**2. OAuth subprocess integrity — no new subprocess spawn**

`audit_cascade.py` introduces no subprocess spawn of its own. It composes existing `tiered_node` calls which route through `ClaudeCodeSubprocess` (already audited). `ClaudeCodeSubprocess.complete()` uses `asyncio.create_subprocess_exec(*argv, ...)` — argv is a list (no `shell=True`). Timeout is `asyncio.wait_for(..., timeout=self._per_call_timeout_s)` — signal-based, not a watchdog. Stderr is captured to `asyncio.subprocess.PIPE` and surfaced via `subprocess.CalledProcessError(stderr=stderr_bytes)` which `retry.py:classify()` logs (capped at 2000 chars). The T02 diff adds no new subprocess invocation path.

**3. Prompt-injection robustness — `_render_audit_feedback` template**

`_render_audit_feedback` (retry.py:106-143) interpolates four caller-supplied strings — `primary_original`, `failure_reasons`, `suggested_approach`, and `primary_context` — into the re-prompt template using an XML-like `<audit-feedback>` delimiter. In the single-user local threat model the auditor output originates from the user's own LLM; there is no untrusted network source. The delimiter `</audit-feedback>` appearing inside an auditor `failure_reasons` or `suggested_approach` value would close the block early in a string-search sense, but LLM context windows are not XML parsers — the primary LLM reads the entire blob verbatim. No structural injection risk in the local threat model. Advisory note below for documentation completeness.

**4. Cascade transcript — sensitive data exposure**

`cascade_transcript` accumulates raw primary LLM outputs (`author_attempts`) and parsed `AuditVerdict` instances (`auditor_verdicts`) into LangGraph state, persisted via `SqliteSaver` per KDR-009. This is no new exposure class: existing primary outputs are already checkpointed. The cascade adds transcript length, not a new category of data. No API keys, OAuth tokens, or env-var values are written into the transcript by T02 code. The `_cascade_gate_prompt_fn` renders the transcript for the HumanGate but does not log it — no extra log exposure path.

**5. pyproject.toml diff scope**

Confirmed: the only T02 edit to `pyproject.toml` is the 5th `[[tool.importlinter.contracts]]` block (lines 194-202). `[project.dependencies]`, `[dependency-groups.dev]`, `dynamic = ["version"]`, `[tool.hatch.build.targets.wheel]`, `[tool.hatch.build.targets.wheel.force-include]`, and `[tool.hatch.build.targets.sdist]` are all unchanged. The wheel-contents security boundary is intact.

**6. Wheel-contents impact**

The 0.3.1 wheel in `dist/` was built before T02 landed (does not contain `ai_workflows/graph/audit_cascade.py` — expected, T02 not yet released). Structural check: `[tool.hatch.build.targets.wheel].packages = ["ai_workflows"]` means the next build will include `ai_workflows/graph/audit_cascade.py` (correct — it is package code). Test files (`tests/primitives/test_audit_feedback_template.py`, `tests/graph/test_audit_cascade.py`) are in `tests/` which is excluded from the wheel by the `packages` boundary. No `.env*`, design_docs, or other sensitive artefacts introduced. Wheel-contents posture unchanged.

**7. Logging hygiene**

`audit_cascade.py` contains no `structlog` / `_LOG` calls — zero logging in the new module. `retry.py` logging (stderr excerpt, capped at 2000 chars) predates T02 and was already reviewed at 0.1.3. The T02 extension to `classify()` adds no new log emit. No API keys, auth headers, or prompt payloads are logged by T02 code.

**8. SQLite paths / SQL injection**

T02 introduces no new SQLite access and no `aiosqlite.execute()` calls. Cascade transcript lives in LangGraph graph state / `SqliteSaver`, not in the storage layer. No raw f-string SQL interpolation introduced.

---

### Critical — must fix before publish/ship

*None.*

### High — should fix before publish/ship

*None.*

### Advisory — track; not blocking

**SEC-ADV-01 — Prompt-injection delimiter collision in `_render_audit_feedback`**

Where: `ai_workflows/primitives/retry.py:106-143` — the `<audit-feedback>` / `</audit-feedback>` XML-like delimiter is embedded verbatim in failure-reason text without escaping.

Threat-model item: Wheel item 1 (indirectly — future downstream consumers building cascades with externally-sourced auditor prompts). Within the current single-user local deployment this is not exploitable: the auditor is the user's own LLM operating on the user's own data, and the primary LLM reads the block verbatim rather than parsing it structurally. If a future downstream consumer routes auditor verdicts from a shared/external source, the delimiter could be confused. No action required for current threat model; flag for consideration at M12 T06 or later when external auditor sources are possible.

Action: No code change required now. If T06 introduces external auditor result ingestion (e.g. from a tool call or API endpoint), add delimiter-escaping or switch to a format that does not rely on substring matching (e.g. a JSON wrapper). Document in the T06 spec.

---

### Verdict: SHIP

## Sr. Dev review (2026-04-27)


**Files reviewed:** `ai_workflows/graph/audit_cascade.py` (new, ~750 lines), `ai_workflows/primitives/retry.py` (AuditFailure + _render_audit_feedback + classify() extension), `ai_workflows/graph/retrying_edge.py` (docstring update), `ai_workflows/graph/error_handler.py` (referenced via `_failure_state_update` cross-module import), `tests/graph/test_audit_cascade.py` (new), `tests/primitives/test_audit_feedback_template.py` (new), `pyproject.toml` (5th import-linter contract)
**Skipped (out of scope):** None — all files in the task union were read.
**Verdict:** FIX-THEN-SHIP

### BLOCK — must-fix before commit

None.

### FIX — fix-then-ship

#### SR-DEV-FIX-01 — Test 3 assertion is trivially true; hides any future regression in gate-prompt generation

**Lens:** Hidden bugs that pass tests (degenerate assertion form)

**Where:** `tests/graph/test_audit_cascade.py:396`

```python
assert "author_attempts" not in prompt_text or "Attempts recorded: 2" in prompt_text
```

The first disjunct (`"author_attempts" not in prompt_text`) is permanently True: `_cascade_gate_prompt_fn` never emits the literal string `"author_attempts"` in its output. Because `True or anything` is `True` in Python, this assertion is a no-op — it passes unconditionally regardless of what `prompt_text` contains, including an empty string. The spec AC-8 requires "The HumanGate carries `author_attempts` + `auditor_verdicts`" in its prompt payload, but this assertion provides zero coverage for that requirement.

Reproduction shape: mutate `_cascade_gate_prompt_fn` to return a fixed string `"exhausted"` (no transcript content). Test 3 still passes.

**Action:** Replace the degenerate disjunction with two direct assertions:
```python
assert "Attempts recorded: 2" in prompt_text
assert "bad shape" in prompt_text  # failure_reason from _AUDIT_FAIL_JSON present in prompt
```

This is a single-clear-recommendation fix with no scope expansion. The Auditor-agreement bypass shape applies.

#### SR-DEV-FIX-02 — `_StubClaudeCodeAdapter` class docstring is factually wrong (misleading, not cosmetic)

**Lens:** Comment / docstring drift (factually incorrect, causes reader confusion about test isolation)

**Where:** `tests/graph/test_audit_cascade.py:87-89`

The docstring for `_StubClaudeCodeAdapter` states:

> "script is shared with `_StubLiteLLMAdapter` so both primary (LiteLLM) and auditor (Claude) pulls from the same ordered script."

This is factually incorrect. `_StubClaudeCodeAdapter.script` and `_StubLiteLLMAdapter.script` are **two separate class-level attributes**. Every test populates them independently (e.g., test 1: `_StubLiteLLMAdapter.script = [(_PRIMARY_JSON, 0.001)]` and separately `_StubClaudeCodeAdapter.script = [(_AUDIT_PASS_JSON, 0.0)]`). The `_reset_stubs` fixture resets them independently. A reader expecting a single shared list would misunderstand the stub design and write incorrect scripts for future tests (expecting that one `script` list drives both adapters).

**Action:** Replace the docstring with the accurate description:
```
Scriptable ClaudeCodeSubprocess stub.

``script`` is a list of (text, cost) tuples or Exception instances
specific to the auditor (Claude Code) path; separate from
``_StubLiteLLMAdapter.script`` which drives the primary (LiteLLM) path.
Each ``complete`` call pops the head of this list.
```

This is a single-clear-recommendation fix with no scope expansion.

### Advisory — track but not blocking

#### SR-DEV-ADV-01 — Defensive `result.get("last_exception") is None` check in `_stamp_role_on_success` against a contract guarantee

**Lens:** Defensive-code creep

**Where:** `ai_workflows/graph/audit_cascade.py:536` and `ai_workflows/graph/audit_cascade.py:546`

Both `_wrapped_with_config` and `_wrapped_state_only` inside `_stamp_role_on_success` check `result.get("last_exception") is None` to decide whether to inject `cascade_role`. The inner node is always `tiered_node`, whose contract guarantees it either returns `{"last_exception": None, ...}` (success) or raises (never returns a dict with `last_exception` set to a non-None value). On the failure path the exception propagates through `_stamp_role_on_success` (which has no `except` clause), so the function body is only ever reached on the success path where `last_exception is None` is always true.

**Recommendation:** The check could be removed and replaced with an unconditional merge `return {**result, "cascade_role": role}`. However given the function is ~10 lines and the check costs nothing, downgrade to Advisory; no code change required. If `_stamp_role_on_success` is ever generalised to wrap nodes other than `tiered_node`, the check would be wrong (not all nodes set `last_exception` on the success return dict).

#### SR-DEV-ADV-02 — `_CascadeState` static TypedDict is dead documentation code

**Lens:** Simplification / comment drift

**Where:** `ai_workflows/graph/audit_cascade.py:85-120`

`_CascadeState` is defined as a static TypedDict with the `audit_cascade_*` prefixed channel names (for the default `name="audit_cascade"` case). It is never used as a state schema argument to `StateGraph` — the dynamic `_DynamicState` (constructed at line 393 inside `audit_cascade_node`) is used instead. `_CascadeState` is effectively orphaned documentation.

**Recommendation:** Either (a) remove `_CascadeState` and add a module-level comment explaining that the dynamic TypedDict captures the per-call schema, or (b) add a `# documentation only — not used as StateGraph schema` comment to `_CascadeState` to signal its intent. Option (a) is cleaner. Owner: M12 T07 close-out.

#### SR-DEV-ADV-03 — `_render_audit_feedback` silent coercion of empty-string `suggested_approach`

**Lens:** Hidden bugs that pass tests (edge case undocumented, not a current bug)

**Where:** `ai_workflows/primitives/retry.py:135`

```python
suggested = suggested_approach or "(none)"
```

An empty string `""` evaluates as falsy in Python, so `suggested_approach=""` renders `"(none)"` — identical to `None`. This is intentional (an empty suggestion is meaningless) but is not documented in the function's docstring. If an auditor LLM returns `"suggested_approach": ""` in its JSON, the rendered re-prompt will silently say `"Suggested approach: (none)"` rather than "Suggested approach: " (empty). This is almost certainly the correct behavior but could confuse a future developer debugging why the suggestion didn't propagate.

**Recommendation:** Add a one-line note to `_render_audit_feedback`'s docstring: "Empty string `suggested_approach` is coerced to `\"(none)\"` via the same `or` as `None`." No code change required.

### What passed review (one-line per lens)

- Hidden bugs: SR-DEV-FIX-01 (degenerate test assertion hides gate-prompt regression); SR-DEV-ADV-03 (empty-string suggested_approach edge case, Advisory)
- Defensive-code creep: SR-DEV-ADV-01 (unnecessary `last_exception is None` guard in `_stamp_role_on_success`, Advisory)
- Idiom alignment: No drift observed. `structlog.get_logger(__name__)` not used in `audit_cascade.py` (module has no logging — consistent with zero-logging design noted in security review). Layer discipline confirmed by lint-imports.
- Premature abstraction: None observed. Each helper (`_wrap_verdict_with_transcript`, `_decide_after_verdict`, `_decide_after_validator`, `_stamp_role_on_success`) earns its keep with a justified single caller. No new base class or mixin introduced.
- Comment / docstring drift: SR-DEV-FIX-02 (factually wrong docstring in `_StubClaudeCodeAdapter`); SR-DEV-ADV-02 (`_CascadeState` orphaned documentation TypedDict, Advisory)
- Simplification: The `_decide_after_verdict` custom edge could potentially re-use the base `retrying_edge` result for the transient/semantic cases and only add the `exc is None → END` branch, but the current form is explicit and readable. No simplification recommended.

## Dependency audit (2026-04-27)

### Manifest changes audited

- `pyproject.toml`: single change — new `[[tool.importlinter.contracts]]` block (lines 194–202) scoped to `ai_workflows.graph.audit_cascade`, forbidding imports from `workflows`, `cli`, and `mcp`. This is the 5th import-linter contract. Verified via `git diff HEAD pyproject.toml`: no `[project.dependencies]` change, no `[project.optional-dependencies]` change, no `[project.scripts]` change, no `dynamic`/version change, no `[tool.hatch.build.targets.*]` change, no `[tool.hatch.build.targets.wheel.force-include]` change, no `[tool.hatch.build.targets.sdist]` change.
- `uv.lock`: NOT touched. `git diff HEAD uv.lock` returns empty. No new transitive dependency added; lockfile integrity intact.

### Wheel contents (pre-publish run — 2026-04-27)

Built `dist/jmdl_ai_workflows-0.3.1-py3-none-any.whl` and `dist/jmdl_ai_workflows-0.3.1.tar.gz` via `uv build`.

- **whl:** CLEAN. Wheel contains only `ai_workflows/` package files (including newly-added `ai_workflows/graph/audit_cascade.py`), `migrations/` (force-included per M13 T01 config), and `jmdl_ai_workflows-0.3.1.dist-info/` (metadata, LICENSE). No `.env*`, no `design_docs/`, no `runs/`, no `*.sqlite3`, no `tests/`, no `.claude/`, no `CLAUDE.md`, no `htmlcov/`, no `.coverage`. `[tool.hatch.build.targets.wheel].packages = ["ai_workflows"]` boundary is intact; `audit_cascade.py` correctly lands in the wheel as package code; test files remain in `tests/` and are excluded.
- **sdist:** ADVISORY-ONLY. The sdist contains `.env.example` (not `.env` — example config, no secrets), `runs/.gitkeep`, `evals/` fixtures, `scripts/`, `Dockerfile`, `docker-compose.yml`, `uv.lock`, and test files. These are standard sdist latitude for downstream packagers. No `.env` (secret-bearing), no `design_docs/`, no `.claude/`, no `CLAUDE.md` — the `[tool.hatch.build.targets.sdist].exclude` block is intact and was not touched by the T02 diff. The sdist `exclude` block correctly covers `/.claude`, `/CLAUDE.md`, `/design_docs`, `/tests/skill`, `/scripts/spikes`.

### CVE / supply-chain posture

No new dependency was added. The CVE and supply-chain surface is unchanged from the prior audit (security review completed in the same cycle above, confirmed zero new deps). No typosquat, abandonment, license-drift, or ownership-change check is required — no new package crossed the boundary.

### 🔴 Critical — must fix before publish

None.

### 🟠 High — should fix before publish

None.

### 🟡 Advisory — track; not blocking

**DEP-ADV-01 — Sdist contains `.env.example`**

Where: `jmdl_ai_workflows-0.3.1/` sdist root.

Finding: `.env.example` ships in the sdist. This is the example/template config file (no secrets — it documents variable names only). It does not contain `PYPI_TOKEN`, API keys, or OAuth material. The real `.env` is gitignored and not present. Standard sdist practice; `.env.example` is useful context for downstream packagers.

Action: None required for current content. If `.env.example` ever gains real values (tokens, keys), promote to HIGH immediately and add it to the sdist `exclude` list. Monitor at each release.

### Verdict: SHIP

## Sr. SDET review (2026-04-27)

**Test files reviewed:**
- `tests/primitives/test_audit_feedback_template.py` (new, 5 tests)
- `tests/graph/test_audit_cascade.py` (new, 6 wire-level tests)
- `tests/test_scaffolding.py` (extended — 5th contract count + name assertion)

**Skipped (out of scope):** `tests/workflows/test_slice_refactor_fanout.py` — touched during cycle 1 but no T02 ACs map to it; out of scope for this review.

**Verdict:** FIX-THEN-SHIP

---

### BLOCK — tests pass for the wrong reason

None.

---

### FIX — fix-then-ship

#### SDET-FIX-01 — Test 3 assertion at line 396 is a permanent tautology (concur with SR-DEV-FIX-01)

**Lens:** Tests that pass for the wrong reason — tautological assertion.

**Where:** `tests/graph/test_audit_cascade.py:396`

```python
assert "author_attempts" not in prompt_text or "Attempts recorded: 2" in prompt_text
```

Independent verification: `_cascade_gate_prompt_fn` (`audit_cascade.py:708-749`) never emits the literal string `"author_attempts"` anywhere in its rendered output. The function emits `"Attempts recorded: N"`, `"Cascade 'ac' exhausted retry budget."`, `"--- Attempt N ---"`, `"Primary output:"`, and `"Verdict: passed=..."` — none is the literal `"author_attempts"`. Therefore the first disjunct `"author_attempts" not in prompt_text` is permanently `True`, and the full `or`-expression is unconditionally `True` regardless of `prompt_text` content (including an empty string).

**AC pinned by this test:** AC-8 — "Exhaustion routes to strict `HumanGate(strict_review=True)` whose prompt payload carries `author_attempts` + `auditor_verdicts`." The current line provides zero enforcement. A regression in `_cascade_gate_prompt_fn` that returns an empty string or strips the transcript entirely would leave this assertion passing.

**Action / Recommendation:** Replace the degenerate disjunction with two direct assertions that actually pin the gate-prompt content:
```python
assert "Attempts recorded: 2" in prompt_text
assert "bad shape" in prompt_text  # failure_reason from _AUDIT_FAIL_JSON present in rendered prompt
```

---

#### SDET-FIX-02 — `_StubClaudeCodeAdapter` docstring is factually wrong (concur with SR-DEV-FIX-02)

**Lens:** Comment / docstring drift — misleads about test isolation and stub design.

**Where:** `tests/graph/test_audit_cascade.py:87-90`

The docstring states `"script is shared with _StubLiteLLMAdapter so both primary (LiteLLM) and auditor (Claude) pulls from the same ordered script."` This is factually incorrect. `_StubClaudeCodeAdapter.script` and `_StubLiteLLMAdapter.script` are independent class-level lists. Every test populates them separately and the `_reset_stubs` fixture resets them independently. A developer expecting a shared pool would write incorrect scripts for future tests that combine primary and auditor responses in a single interleaved list.

**Action / Recommendation:** Replace the docstring with:
```
Scriptable ClaudeCodeSubprocess stub.

``script`` is a list of (text, cost) tuples or Exception instances
specific to the auditor (Claude Code) path; separate from
``_StubLiteLLMAdapter.script`` which drives the primary (LiteLLM) path.
Each ``complete`` call pops the head of this list.
```

---

#### SDET-FIX-03 — Test 4 docstring/comments contradict its actual assertions; AC-9 pure-exhaustion case uncovered

**Lens:** Tests that pass for the wrong reason — the test verifies a weaker property than the AC specifies; the docstring makes a false claim.

**Where:** `tests/graph/test_audit_cascade.py:409-446`

The test docstring states `"auditor adapter was called 0 times (validator short-circuits it)"`. The spec's test #4 description (spec line 343) reads: `"Assert: auditor adapter was called 0 times after 2 primary attempts (validator failed both)"`. Neither is true of the actual test:

- The primary script has THREE entries (two invalid, one shape-valid `_PRIMARY_JSON`).
- The auditor script has ONE entry (`_AUDIT_PASS_JSON`).
- The final assertion is `assert len(_StubClaudeCodeAdapter.calls) == 1` — auditor called once.
- The inline comment at line 445 says `# Auditor fired only once (only on the shape-valid attempt)`.

The test implements a hybrid scenario (shape-fail twice, then shape-pass on attempt 3 which reaches the auditor). This is a valid and useful test, but it is not the test the spec or docstring describe. The weaker property covered — "auditor is not called during shape-failure loops" — is observable only because the first two attempts go to the auditor zero times, and the third succeeds and does invoke the auditor. There is no assertion that covers the pure-exhaustion case where shape-validation fails all `max_semantic_attempts` times and the auditor call count stays zero throughout.

**AC-9 coverage gap:** AC-9 says "Validator shape failure short-circuits the auditor." The existing test exercises this partially (auditor not called on failing attempts), but the case where shape-failures exhaust the budget and the cascade routes to the HumanGate with `auditor_calls == 0` (the pure-exhaustion variant) is not pinned.

**Action / Recommendation (pick one):**

- Option A (preferred, additive): Fix the test 4 docstring and comments to accurately state "auditor fires once on the shape-valid third attempt; not fired on invalid attempts." Add a second test `test_cascade_validator_exhaustion_routes_to_gate_without_invoking_auditor` where the primary always returns invalid JSON for `policy.max_semantic_attempts` cycles, the cascade routes to the HumanGate, and `assert len(_StubClaudeCodeAdapter.calls) == 0`.
- Option B (minimal): Rewrite test 4 to the pure-exhaustion scenario matching the spec and docstring (primary always invalid, auditor never invoked, cascade routes to gate). Add a separate test for the "shape-fail then shape-pass" hybrid the current test exercises.

---

### Advisory — track but not blocking

#### SDET-ADV-01 — Test 6 only verifies final `cascade_role` state; "author" and "auditor" stamp intermediates not directly confirmed

**Lens:** Coverage gap — AC-7 partially verified.

**Where:** `tests/graph/test_audit_cascade.py:491-533`

AC-7 says `cascade_role` is stamped by each cascade sub-node (`"author"` / `"auditor"` / `"verdict"`). Test 6 asserts only `final.get("cascade_role") == "verdict"` (the last writer's value). The `captured_roles` list records the role as seen by the primary prompt_fn at call time — it captures the value *before* the primary node writes `"author"` to state, so it cannot confirm the `"author"` or `"auditor"` stamps were ever written. The test is effectively a duplicate of test 1's final-state `cascade_role` assertion.

The `"author"` and `"auditor"` stamps are transient within a single `ainvoke` (the verdict node overwrites them), making them unobservable from a final-state assertion. The stamps are covered by code inspection (`_stamp_role_on_success` wrapper is invoked on each non-exception return), but the test name `test_cascade_role_tags_stamped_on_state` oversells what is actually verified.

**Recommendation:** Either (a) rename to `test_cascade_final_role_state_is_verdict_on_success_path` to accurately describe what the assertion covers, or (b) add a custom auditor `prompt_fn` that captures `state.get("cascade_role")` at auditor-call time and verify it equals `"author"` (the primary's stamp, visible when the auditor runs). Advisory — not blocking.

---

### What passed review (one-line per lens)

- Tests-pass-for-wrong-reason: SDET-FIX-01 (line 396 tautological `or` — AC-8 coverage is zero; confirmed by source inspection of `_cascade_gate_prompt_fn` output shape).
- Coverage gaps: SDET-FIX-03 (test 4 docstring/assertions contradict; pure-zero-auditor-call scenario for AC-9 not pinned); SDET-ADV-01 (test 6 only checks final `cascade_role`, not intermediate "author"/"auditor" stamps).
- Mock overuse: None observed. Stubs are correctly spec-typed class-level scriptable fakes. Real `tiered_node`, `validator_node`, `wrap_with_error_handler`, `retrying_edge`, `human_gate`, `SQLiteStorage`, and `build_async_checkpointer` all execute. Only LLM dispatch is stubbed.
- Fixture / independence: `_reset_stubs` is `autouse=True` and correctly resets both stub classes. All tests use distinct `run_id` strings and distinct SQLite files via `tmp_path`. No order dependence observed. `monkeypatch` scope is per-test default. No `conftest.py` autouse surprise.
- Hermetic-vs-E2E gating: All 11 test functions (6 cascade + 5 template) are hermetic. No network calls, no subprocess, no `AIW_E2E` gate needed or missing. Clean.
- Naming / assertion-message hygiene: SDET-FIX-02 (factually wrong `_StubClaudeCodeAdapter` docstring); SDET-FIX-03 (test 4 docstring says "0 calls" but test asserts 1); SDET-ADV-01 (test 6 name oversells coverage). Test 1–3, 5 names are descriptive and accurate.
