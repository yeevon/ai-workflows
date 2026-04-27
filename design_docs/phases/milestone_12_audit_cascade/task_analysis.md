# milestone_12_audit_cascade — Task Analysis

**Round:** 3 (T02)
**Analyzed on:** 2026-04-27
**Specs analyzed:** `task_02_audit_cascade_node.md`
**Analyst:** task-analyzer agent

T01 closed 2026-04-27 (✅ Complete; issue file at `issues/task_01_issue.md`); not re-analyzed.
T03–T07 specs do not yet exist per the milestone README's `T02–T07 written at each predecessor's close-out` policy; intentionally absent.

This is the third analysis round on T02. Round-2 verdict was OPEN (0 HIGH, 1 MEDIUM, 5 LOW); orchestrator applied the single MEDIUM fix (M1 — added §Counter-sharing contract block under §Sub-graph wiring; pinned test #3 scenario to pure-audit-failure-only). Round 3 verifies the round-2 MEDIUM fix landed correctly + re-grades the 5 LOWs + hostile re-reads for any new issues introduced by round-2 edits.

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 0 |
| 🟢 LOW | 4 |
| Total | 4 |

**Stop verdict:** LOW-ONLY

(Per the orchestrator contract: zero HIGH and zero MEDIUM with LOW findings only → orchestrator pushes LOWs to spec carry-over and exits the loop. Phase 3 will append the four LOWs to T02's `## Carry-over from task analysis` section.)

## Round-2 fix verification

The round-2 MEDIUM fix (M1 — shared retry counter contract clarification) was hostile-re-read against the live codebase and the spec. It landed correctly:

- **§Counter-sharing contract block exists.** Spec lines 220–234. Block is positioned correctly between §Sub-graph wiring's edge-wiring section (ending line 218) and §Internal node block (starting line 235), as the round-2 fix prescription required.
- **Block names the design intent explicitly.** Line 222 states "shared semantic budget against the primary's `policy.max_semantic_attempts`" — load-bearing for any future Builder/Auditor reading the §Sub-graph wiring section. The intent (audit-fail + shape-fail share the budget) is no longer inferential.
- **Worked example arithmetic verified against `validator_node.py:135-142`.** Spec line 226–229 trace:
  - Cycle 1: AuditFailure → counter=1. Verified `error_handler.py:170-178` bumps `_retry_counts[node_name]` from 0 to 1.
  - Cycle 2: prior_failures=1, max_attempts=3, `1 >= 3-1` → False. Verified `validator_node.py:136` reads `prior_failures = retry_counts.get(node_name, 0)` BEFORE the failure increment, and `136` is `if prior_failures >= max_attempts - 1`. With prior_failures=1 (read from state which was bumped to 1 by Cycle 1's verdict-wrap), the comparison `1 >= 2` is False → raises RetryableSemantic. Counter bumps to 2 via `_failure_state_update` at error_handler.py:170-178. ✅
  - Cycle 3: prior_failures=2, `2 >= 3-1` → True → escalates to NonRetryable. Counter bumps to 3 (the NonRetryable also goes through _failure_state_update). retrying_edge then routes via `on_terminal` because: (a) `_non_retryable_failures = 1 < 2` so the hard-stop check at retrying_edge.py:103 is False; (b) `isinstance(exc, NonRetryable)` doesn't match either RetryableTransient or RetryableSemantic at retrying_edge.py:112,117, so falls through to `return on_terminal` at retrying_edge.py:122. ✅
- **Pure-audit-failure-only claim verified.** Spec line 231: "reaches the human_gate after exactly `max_semantic_attempts` primary attempts." Traced for `max_semantic_attempts=2` (test #3 setting):
  - Cycle 1: primary → validator(passes shape) → auditor → verdict raises AuditFailure. Counter bumps to 1. retrying_edge: `retry_counts["{name}_primary"]=1 >= 2`? False → routes to on_semantic (back to primary). ✅
  - Cycle 2: primary → validator(passes shape) → auditor → verdict raises AuditFailure. Counter bumps to 2. retrying_edge: `2 >= 2`? True → routes to on_terminal (HumanGate). ✅
  - Total: 2 primary attempts, then human_gate. Matches spec's "after exactly `max_semantic_attempts` primary attempts" claim. ✅
- **Test #3 pinned to pure-audit-failure-only.** Spec line 342 reads "**pure-audit-failure-only scenario** (no shape failures interleaved — primary always returns shape-valid output, auditor always returns `passed=False`)." The cross-reference to §Counter-sharing contract is present in the test description ("the shared counter (§Counter-sharing contract) burns one slot per audit-failure, and exhaustion routes via the verdict-node's retrying_edge on `on_terminal` after `max_semantic_attempts`"). The budget arithmetic is now unambiguous to any Builder reading test #3.
- **Test #4 cross-referenced.** Spec line 233: "A pure-shape-failure-only sequence (auditor never invoked, see test #4) also reaches the in-validator `NonRetryable` escalation on the same cycle. Test #4 pins this — auditor adapter call count is 0." This forward-reference correctly anchors the validator-only path against the test that pins it.

The round-2 fix is internally consistent, factually correct against the live codebase, and resolves the M1 ambiguity cleanly. No new findings introduced by the round-2 edits.

## Re-evaluation of round-2 LOW findings

- **L1 (`Status` parenthetical drift).** Still LOW; cosmetic only. Round-2 did not edit the Status line. Push to spec carry-over in Phase 3.
- **L2 (`HumanGate verbatim` phrasing).** Still LOW; phrasing-only. Round-2 did not edit §Out of scope. Push to spec carry-over in Phase 3.
- **L3 (M12-T01-ISS-03 propagation).** **Re-graded to RESOLVED.** Re-read T01 issue file line 134 — the T01 audit explicitly closed ISS-03 with "No spec edit required" and "Self-resolves at T02 cycle 1 when `AuditCascadeNode` first invokes the auditor tier." Per CLAUDE.md "Propagation discipline" only forward-deferred items requiring action need to appear in the target spec; ISS-03 was closed-on-self-resolution at T01, not forward-deferred. Round-2 L3 was an over-read of the T01 issue file. Drop from carry-over push.
- **L4 (Test #5 outer-graph state schema underspecified).** Still LOW. Round-2 did not edit test #5. Push to spec carry-over in Phase 3.
- **L5 (`_default_primary_original` helper sketch).** Still LOW. Round-2 did not edit the §Internal node block helper sketch. Push to spec carry-over in Phase 3.

Net change: 5 LOWs → 4 LOWs (L3 resolved on re-read).

## Findings

### 🔴 HIGH

*None.*

### 🟡 MEDIUM

*None.* Round-2 M1 fix verified clean.

### 🟢 LOW

#### L1 (carried from round 1) — `**Status:**` parenthetical drift

**Task:** `task_02_audit_cascade_node.md`
**Issue:** Spec line 3 has `**Status:** 📝 Planned (drafted 2026-04-27).` while milestone README task table row 02 (line 65 of README) uses `📝 Planned` only. Cosmetic; close-out flips both to `✅ Complete (YYYY-MM-DD)` together so no real surface drift at close.
**Recommendation:** Optional drop of the `(drafted 2026-04-27)` parenthetical for uniformity with README task-table row format.
**Push to spec:** yes — append: *"Optional: drop the `(drafted 2026-04-27)` parenthetical from `**Status:**` line for uniformity with the README task-table row format. Cosmetic only — does not affect close-out flip."*

#### L2 (carried from round 1) — `HumanGate verbatim` phrasing in §Out of scope

**Task:** `task_02_audit_cascade_node.md`
**Location:** spec line 384 ("No HumanGate edit. T02 reuses HumanGate(strict_review=True) verbatim").
**Issue:** "Verbatim" is technically true but a pedant could read it as "no behavioural customization at all." The cascade *does* supply a custom `prompt_fn` for the cascade-transcript renderer — that's `human_gate.py:52`'s documented extension point.
**Recommendation:** Replace "verbatim" with "without source-code edit"; clarifies that the `prompt_fn` injection is the documented extension point.
**Push to spec:** yes — append: *"Optional: in §Out of scope, replace `reuses HumanGate(strict_review=True) verbatim` with `reuses HumanGate(strict_review=True) without source-code edit (the cascade-transcript prompt_fn is HumanGate's documented extension point, not a fork)`."*

#### L3 (carried from round 1) — Test #5 outer-graph state schema underspecified

**Task:** `task_02_audit_cascade_node.md`
**Location:** spec line 344 (test #5 description).
**Issue:** "instantiate `audit_cascade_node(...)`; add it as a single node to a minimal outer `StateGraph(state_schema=...)`; compile; invoke." The outer state schema is unspecified. The four `<name>_*` channels are pinned at lines 280–283 which the Builder can copy in, but the test still needs `run_id`, `last_exception`, `_retry_counts`, `_non_retryable_failures`, `cascade_role`, `cascade_transcript` plus the four cascade-internal keys.
**Recommendation:** Sketch the minimum schema in the test description, or reference `tests/graph/test_tiered_node.py`'s `_build_config` shape as the template.
**Push to spec:** yes — append: *"In test #5 (`test_cascade_returns_compiled_state_graph_composable_in_outer`), name the minimum outer-graph state schema fields the Builder needs: `run_id`, `last_exception`, `_retry_counts`, `_non_retryable_failures`, `cascade_role`, `cascade_transcript`, plus the four cascade-internal keys (`<name>_primary_output`, `<name>_primary_parsed`, `<name>_auditor_output`, `<name>_audit_verdict`). Or reference `tests/graph/test_tiered_node.py:_build_config` shape as the template."*

#### L4 (carried from round 2) — `_default_primary_original` helper named in §Internal node block but never defined

**Task:** `task_02_audit_cascade_node.md`
**Location:** spec lines 263 + 268 (verdict-node block references `_default_primary_original(state, primary_prompt_fn)` as the fallback when `cascade_context_fn` is None).
**Issue:** The §Internal node block correctly added by the round-1 M5 fix references a helper `_default_primary_original` whose body shape is described in prose ("re-calls `primary_prompt_fn(state)` and joins the (system, messages) tuple into a single rendered string — same shape as the primary's first invocation prompt") but with no signature, no body sketch, and no explicit return-shape pin. The exact join shape (delimiter between system and messages, JSON-encoding vs. plain concatenation, treatment of role-tagged message dicts) is left to Builder discretion. Test #2's byte-equal assertion against `_render_audit_feedback(...)` will lock the cascade's first revision_hint shape, but the Builder will need to know what `primary_original` rendered to in order to construct the expected literal.
**Recommendation:** Add a one-paragraph sketch of `_default_primary_original`'s body shape. Suggested shape: `system, messages = primary_prompt_fn(state); return (system or "") + "\n\n" + "\n".join(m.get("content", "") for m in messages)`. Or pin a less-opinionated shape (e.g. `repr((system, messages))`) and let the test #2 byte-equal assertion drive whatever shape the Builder picks. Either way, the spec should not leave the join shape unwritten.
**Push to spec:** yes — append: *"In §Internal node block, sketch `_default_primary_original(state, primary_prompt_fn)`'s body. Suggested shape: `system, messages = primary_prompt_fn(state); return (system or '') + '\n\n' + '\n'.join(m.get('content', '') for m in messages)`. Pin whichever shape — test #2's byte-equal assertion against `_render_audit_feedback(...)` will lock the cascade's first revision_hint shape, and the Builder will need to know what `primary_original` rendered to in order to construct the expected literal."*

## What's structurally sound

Round-3 hostile re-read confirms the round-1 + round-2 fixes plus all prior structural verifications hold up. Specifically re-verified this round:

- **§Counter-sharing contract block is internally consistent and codebase-accurate.** Worked example traced step-by-step against `validator_node.py:135-142`, `error_handler.py:128-130,170-178`, `retrying_edge.py:103,112,117-122`. The off-by-one between in-validator escalation (`prior_failures >= max_attempts - 1`) and retrying_edge's bucket-budget check (`retry_counts >= max_semantic_attempts`) is correctly handled — they fire on different cycles for different paths but converge on the same human_gate exit either way.
- **Pure-audit-failure-only test #3 budget arithmetic verified.** With `max_semantic_attempts=2`, the cascade reaches human_gate after exactly 2 primary attempts via the retrying_edge's `on_semantic` budget check (the in-validator escalation never fires since the validator never sees a shape-invalid output in this scenario).
- **Pure-shape-failure-only test #4 budget arithmetic verified.** Validator's in-validator escalation fires on the second consecutive shape-failure cycle (assuming `max_attempts=2`), routing to NonRetryable → retrying_edge `on_terminal` → human_gate. Auditor adapter call count is 0 throughout. The cross-reference at line 233 correctly anchors this scenario.
- **Layer rule honoured (re-verified).** `audit_cascade.py` imports stay within `graph/` + `primitives/`. Spec lines 100–110 list the imports; zero workflow / surface imports. The new 5th import-linter contract at lines 303–312 pins this against drift.
- **KDR-003 honoured.** No `anthropic` SDK import anywhere in the spec; no `ANTHROPIC_API_KEY` read; tree-wide grep at `tests/workflows/test_slice_refactor_e2e.py:test_kdr_003_no_anthropic_in_production_tree` covers the new module automatically.
- **KDR-004 honoured.** Validator pairing for the primary half of the cascade (line 213). Auditor half is also a TieredNode that produces structured output the verdict node parses against the AuditVerdict schema — pseudo-validator coverage via the verdict node's parse step.
- **KDR-006 honoured.** `AuditFailure` as `RetryableSemantic` subclass; no `classify()` edit needed. Three-bucket taxonomy preserved.
- **KDR-008 honoured.** No MCP tool schema change at T02 (the `run_audit_cascade` MCP tool lands at T05). No public-contract version bump implied.
- **KDR-009 honoured.** `cascade_transcript` is a state channel surviving via LangGraph's checkpointer; no new persistence table.
- **KDR-011 honoured.** Re-prompt template renders `failure_reasons` + `suggested_approach` into `revision_hint`; pinned by `test_audit_feedback_template_full_shape` test #1.
- **KDR-013 not implicated** — no externally-loaded user code in T02.
- **SEMVER stance.** T02 is purely additive: new exception class (`AuditFailure`), new module (`graph/audit_cascade.py`), new factory (`audit_cascade_node`), new pydantic model (`AuditVerdict`), one new import-linter contract. Zero backward-incompatible change to existing public surface. Patch-bump-compatible.
- **Status-surface AC complete.** Spec line 368 enumerates all four required surfaces (per-task spec Status, README task-order row 02, README §Exit-criteria bullets 2/3/4 + 11 + 12; no `tasks/README.md` for M12). Matches CLAUDE.md status-surface discipline.
- **Smoke test names a wire-level path** (line 367): `test_cascade_pass_through` invokes the compiled cascade end-to-end through the same `tiered_node` + `validator_node` adapters production code uses; only the LLM dispatch is stubbed. CLAUDE.md non-inferential rule satisfied.
- **Test #5 reference verified.** `_FakeLiteLLMAdapter` exists at `tests/graph/test_tiered_node.py:104`; `_FakeClaudeCodeAdapter` exists at line 172 (verified via grep). The monkey-patch pattern still applies.
- **`nice_to_have.md` slot range checked.** Highest-numbered section is **§23** (verified via grep). T02 surfaces no new deferred items beyond what the milestone README and T01 issue file already track. No slot-drift risk this round.
- **T01 issue file ISS-03 closure.** Re-read T01 issue file line 134 — ISS-03 was closed at T01 with "No spec edit required" / "Self-resolves at T02 cycle 1." T02 carry-over need not include it.

## Cross-cutting context

- **Project-memory state.** Per `MEMORY.md` and `project_m13_shipped_cs300_next.md`, ai-workflows is in CS300 hold-mode for M10 / M15 / M17. M12 is not on hold — proactive spec hardening is happening now. T02 will be ready for `/clean-implement` (or `/auto-implement` since `AIW_AUTONOMY_SANDBOX=1` per the Docker container) when the M12 go-ahead fires.
- **0.3.1 is live; 0.3.0 yanked.** T02 is graph-layer additive (one new module, one new exception) — no SEMVER break, but `audit_cascade_node` becomes importable via `ai_workflows.graph` at next minor bump.
- **Round-2 fix was the last MEDIUM-severity issue.** All HIGHs cleared at round 1; the single round-2 MEDIUM is verified clean at round 3. The remaining four LOWs are all push-to-carry-over class (cosmetic / phrasing / sketchable-by-Builder); none block implementation.
- **Round-3 verdict triggers Phase 3 (carry-over push + exit).** The orchestrator should now (a) write the four LOWs above into T02's `## Carry-over from task analysis` section as discrete bullets (each with the `Push to spec` text already prepared above), and (b) exit the loop with verdict LOW-ONLY. T02 spec is hardened and ready for `/auto-implement` when M12 goes live.
- **ADR-0004 stale-framing list still has two items** (auditor tier landing site + import-linter contract sentence) — both deferred to M12 T07 docs sweep. Round-1 M3 fix correctly captured this in the spec's propagation-status section.

## Verdict

`Round 3 — LOW-ONLY (4 LOW)`. The round-2 MEDIUM (M1 — shared retry counter contract) is verified clean against the live codebase. The §Counter-sharing block is internally consistent and the worked-example arithmetic traces correctly through `validator_node.py:135-142` + `error_handler.py:170-178` + `retrying_edge.py:103,112,117-122`. Test #3 is correctly pinned to pure-audit-failure-only with cross-reference to §Counter-sharing. Four LOWs remain (L1 + L2 cosmetic/phrasing carried unchanged from round 1; L3 test #5 schema sketch carried unchanged; L4 `_default_primary_original` helper sketch carried unchanged from round 2's L5). One round-2 LOW (round-2 L3 / M12-T01-ISS-03 propagation) was re-graded to RESOLVED on re-read of the T01 issue file (which explicitly closed ISS-03 at T01 with "No spec edit required"). Phase 3 should push the four remaining LOWs to T02's `## Carry-over from task analysis` section and exit the loop.
