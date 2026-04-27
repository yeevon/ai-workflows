# M12 Audit Cascade — Task Analysis

This file carries findings for two specs verified in the same /clean-tasks invocation:

- **§T03 (round 6)** — verification of round-5 fix application (one over the 5-round budget; orchestrator close-out exception).
- **§T08 (round 2)** — verification of round-1 fix application.

T01 + T02 are shipped (✅ Complete 2026-04-27) and are not analyzed here.

---

# T03 (round 6 verification)

**Round:** 6 (one over the standard 5-round budget — orchestrator close-out verification per /clean-tasks Step 4 discretion; round-5 fixes were single-mechanical and orchestrator confidence is high)
**Verified on:** 2026-04-27
**Specs analyzed:** `task_03_workflow_wiring.md`
**Analyst:** task-analyzer agent

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 0 |
| 🟢 LOW | 0 (all 8 LOWs in carry-over) |
| Total | 0 |

**Stop verdict:** LOW-ONLY (8 LOWs already pushed to spec carry-over; orchestrator may exit the loop).

Round 5's single MEDIUM (M1, AC line 318 stale "4 contracts kept") landed mechanically; the two round-5 LOWs (TA-LOW-07 extension; TA-LOW-08 line-citation tightening) were both pushed to the spec's `## Carry-over from task analysis` section. No new findings introduced by round-5 fix application. T03 is implementable as written, modulo T08 closing first per `## Dependencies`.

## Round-5 fix verification

### M1 — AC line 318 contract count (5 not 4) — VERIFIED LANDED

**Live spec line 318:**

> `- [ ] uv run pytest + uv run lint-imports (5 contracts kept — T03 adds no new contract; T02's audit_cascade composes only graph + primitives contract carries forward) + uv run ruff check all clean.`

Matches the round-5 mechanical recommendation byte-for-byte. The Auditor's `uv run lint-imports` invocation will report "Contracts: 5 kept" and the AC will tick correctly.

### TA-LOW-07 extension (positive AND negative side structural assertions) — VERIFIED LANDED

**Live spec lines 373-377:** the carry-over now reads

> Test #5 (`test_planner_subgraph_inherits_planner_module_decision`) references "the cascade primitive's structural marker — see T02's compiled-graph fixture" without enumerating it. Builder will hunt. Test also asserts negative-side ("slice-worker node does NOT have cascade wrapping") but the slice-worker lives inside `_build_slice_branch_subgraph()` — Builder must descend into the per-branch sub-graph for the negative assertion.
> **Recommendation:** Pin both sides:
> - Positive: assert `'planner_explorer_audit_primary' in <planner subgraph>.nodes` (the cascade primitive adds 5 prefixed nodes per `audit_cascade.py:420-424`: `{name}_primary`, `{name}_validator`, `{name}_auditor`, `{name}_verdict`, `{name}_human_gate`).
> - Negative: assert `'slice_worker_audit_primary' not in <slice-branch subgraph>.nodes`. Builder may need a helper to descend into the compiled `slice_branch` sub-graph; cite `_build_slice_branch_subgraph()` at slice_refactor.py:899 as the construction site.

The five-node enumeration matches live `audit_cascade.py:420-424` exactly:
- L420: `g.add_node(f"{name}_primary", primary_node)`
- L421: `g.add_node(f"{name}_validator", validator_wrapped)`
- L422: `g.add_node(f"{name}_auditor", auditor_node)`
- L423: `g.add_node(f"{name}_verdict", verdict_node)`
- L424: `g.add_node(f"{name}_human_gate", gate)`

Both positive and negative-side assertions pinned. Builder has actionable structural markers.

### TA-LOW-08 (line-citation tightening) — VERIFIED LANDED

**Live spec lines 379-381:** new TA-LOW-08 carry-over reads

> Spec line 197 cites `_slice_branch_finalize` "line 869-870" for the existing exception path; live `slice_refactor.py:868` is `exc = state.get("last_exception")`, line 869 is `if exc is None:`, line 870 is `return {}`. Citation is one-off — Builder lands on the early-return branch instead of the exception-read site.
> **Recommendation:** Change "at line 869-870" to "at line 868 (the `state.get('last_exception')` read), with the early-return at line 869-870 the path the new `isinstance(exc, AuditFailure)` branch must precede". Tightens Builder targeting.

Verified live `slice_refactor.py`:
- L868: `exc = state.get("last_exception")`
- L869: `if exc is None:`
- L870: `return {}`

The carry-over correctly identifies the off-by-one citation; the recommendation tightens it without modifying the in-prose §Folding cascade exhaustion citation (left as-is for the Builder to act on at /clean-implement time, per the round-5 push-to-carry-over decision).

## What's structurally sound (round-6 final read)

Verified-and-correct on the post-round-5-fix spec:

- **All round-1..5 fix applications are coherent.** The spec's prescriptive sections (What to Build, Deliverables, Tests, Smoke, Acceptance Criteria) tell one consistent story. The 8 carry-over LOWs are well-scoped, all source-cited, all Recommendation-bearing, and none of them re-open a structural question — they are spec-text fragility items the Builder absorbs at implement time.
- **8 carry-over LOWs (TA-LOW-01 through TA-LOW-08) all present as `[ ]` checkboxes** with Recommendation text. Verified by `grep -c '\*\*TA-LOW-'` returning 8 matches in `task_03_workflow_wiring.md`.
- **Round-5 M1 fix is minimal and surgical.** The substitution updated only the parenthetical inside AC line 318; no other ACs touched, no Deliverables block touched, no test-file rename. The fix matches what the round-5 analysis recommended verbatim.
- **No NEW findings introduced by round-5 fixes.** Walking the spec end-to-end after the M1 substitution + the two LOW additions, no new structural claim, line citation, KDR drift, layer-rule break, or status-surface drift surfaced.
- **KDR re-grade — all 9 KDRs still preserved.** Same as round 5; round-5 fixes touched only AC line 318's parenthetical and the carry-over section, neither of which interacts with any KDR.
- **Layer rule preserved.** Round-5 fixes added zero source-code change; all edits land in `workflows/` layer at /clean-implement time per the spec's deliverables.
- **Status surfaces consistent.** AC line 320 still enumerates spec status, README task table row 03, and README §Exit-criteria bullet 5. README task-table row 03 already carries `📝 Planned (depends on T08)`; README §Exit-criteria bullet 5 is the surface that needs the framing-update at T03 close-out per the propagation status.
- **Dependencies block honoured.** T01 (`a7f3e8f`) and T02 (`fc8ef19`) shown as Met; T08 listed as required predecessor with the explicit "T03 cannot ship until T08 closes" framing at line 326.
- **Round-budget posture.** The orchestrator chose to verify in round 6 (one over the 5-round budget) given the round-5 fixes were single-mechanical and the orchestrator's confidence was high. This verification confirms that judgment was correct — the spec is LOW-ONLY clean.

## Cross-cutting context (T03)

- **Project memory consistent.** No on-hold flag for M12; T01 + T02 shipped 2026-04-27 (`a7f3e8f`, `fc8ef19`); T03 + T08 are the next live tasks. CS300 pivot status per `project_m13_shipped_cs300_next.md` does not block T03.
- **Round-5 → round-6 trajectory.** Round 5's verdict was OPEN with one MEDIUM. Round-5 fix applied mechanically; two LOWs pushed to carry-over. Round 6 verifies the close-out. The /clean-tasks loop on T03 is complete.
- **T08 dependency.** T03 cannot enter /clean-implement until T08 closes per the spec's Dependencies block (line 326). Once T08 lands, the orchestrator's commit-ceremony for T08 also substitutes the T08 commit hash into T03's Dependencies block (per TA-T08-LOW-02), at which point T03 is greenlit for /clean-implement.

## Verdict

**LOW-ONLY — 0 HIGH, 0 MEDIUM, 8 LOW (all in carry-over).** Round-5 fixes verified landed cleanly with no new findings introduced. Orchestrator may exit the /clean-tasks loop on T03 and proceed to T08 cleanup → T08 ship → T03 ship sequence.

---

# T08 (round 2 verification)

**Round:** 2 of 5
**Verified on:** 2026-04-27
**Specs analyzed:** `task_08_audit_cascade_skip_terminal_gate.md`
**Analyst:** task-analyzer agent

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 0 |
| 🟢 LOW | 0 (both LOWs in carry-over) |
| Total | 0 |

**Stop verdict:** LOW-ONLY (2 LOWs already pushed to spec carry-over; orchestrator may exit the loop).

Round 1's HIGH (H1, missing destination-list bullet), MEDIUM (M1, gate-line citation), and MEDIUM (M2, test-count claim) all landed mechanically. The two round-1 LOWs (TA-T08-LOW-01 positional test number; TA-T08-LOW-02 T03 dependency-block hash substitution) are pushed to T08's `## Carry-over from task analysis` section. No new findings introduced by round-1 fix application. T08 is implementable as written.

## Round-1 fix verification

### H1 — `add_conditional_edges` destination-list bullet — VERIFIED LANDED

**Live spec lines 56-62:** the new third bullet (line 60) reads

> `audit_cascade.py:433-437` + `:443-447` (the two `add_conditional_edges` destination-list literals) — the `f"{name}_human_gate"` member must be omitted from the destination list when `skip_terminal_gate=True` (LangGraph compile-time validates that every destination-list member is a registered node; an unregistered destination raises at compile). The after-validator list becomes `[f"{name}_primary", f"{name}_auditor", END]` (END added because `_decide_after_validator` now returns `END` on the `NonRetryable` path under the new mode); the after-verdict list becomes `[f"{name}_primary", END]`.

Cross-checks against live `audit_cascade.py`:
- L433-437 — after-validator `add_conditional_edges` destination list: live `[f"{name}_primary", f"{name}_auditor", f"{name}_human_gate"]` at L436. Spec correctly says: under skip-true mode, omit `f"{name}_human_gate"` and add `END`. The "END added" rationale (because `_decide_after_validator` now returns END on the NonRetryable path) matches the routing-function changes spec'd at lines 67-72.
- L443-447 — after-verdict `add_conditional_edges` destination list: live `[f"{name}_primary", f"{name}_human_gate", END]` at L446. Spec correctly says: under skip-true mode, omit `f"{name}_human_gate"`. END stays (it's already there in the default destination list at L446 as the success path). Result: `[f"{name}_primary", END]` — matches.

The Builder now has the complete spec for the conditional-edge destination updates; the previously-missed compile-time failure mode is closed. The recommended sub-assertion in test #2 is implicitly enforced by LangGraph's compile-time validation (a graph with an unregistered destination won't compile, so the existing `f"{name}_human_gate" not in compiled.nodes` assertion in test #2 cannot pass without the destination-list edits being correct).

### M1 — Gate-line citation (424 + 448, not 447-448) — VERIFIED LANDED

**Live spec line 59:** now reads

> `audit_cascade.py:424` (gate `add_node` call) + `audit_cascade.py:448` (gate edge to END) — both wrap in `if not skip_terminal_gate:` so the gate node is neither registered nor edged when the new mode is active.

Cross-checks against live `audit_cascade.py`:
- L424: `g.add_node(f"{name}_human_gate", gate)` — gate node addition. Confirmed.
- L448: `g.add_edge(f"{name}_human_gate", END)` — gate edge to END. Confirmed.

Builder will land directly on the right edits without a search-and-find cycle.

### M2 — Test count claim (separate-file distinction) — VERIFIED LANDED

**Live spec line 97:** now reads

> The test count for `tests/graph/test_audit_cascade.py` grows from 7 → 11 cascade tests in this file (+4 from T08). The 5 audit-feedback-template tests at `tests/primitives/test_audit_feedback_template.py` are unaffected — that's a separate file.

Cross-checks against the live test files:
- `tests/graph/test_audit_cascade.py` carries 7 cascade tests (`test_cascade_pass_through`, `test_cascade_re_fires_with_audit_feedback_in_revision_hint`, `test_cascade_exhausts_retries_routes_to_strict_human_gate`, `test_cascade_validator_failure_routes_back_to_primary_not_auditor`, `test_cascade_pure_shape_failure_never_invokes_auditor`, `test_cascade_returns_compiled_state_graph_composable_in_outer`, `test_cascade_role_tags_stamped_on_state`). T08 adds 4 → 11. Matches.
- `tests/primitives/test_audit_feedback_template.py` carries 5 template tests (`test_audit_feedback_template_full_shape`, `test_audit_feedback_template_empty_reasons`, `test_audit_feedback_template_no_suggested_approach`, `test_audit_failure_revision_hint_byte_equal_to_expected_template`, `test_audit_failure_is_retryable_semantic`). The "separate file" distinction is correct.

A reader landing on `tests/graph/test_audit_cascade.py` after T08 ships will see 11 cascade tests, matching the spec's claim.

### TA-T08-LOW-01 + TA-T08-LOW-02 — VERIFIED PUSHED TO CARRY-OVER

**Live spec line 158-166:** carry-over section now contains

> - [ ] **TA-T08-LOW-01 — Test #2 cross-reference uses positional number that drifts** (severity: LOW, source: task_analysis.md round 1 L1)
>       Test #4 in T08's spec mirrors an existing `tests/graph/test_audit_cascade.py` test by name (`test_cascade_pure_shape_failure_never_invokes_auditor`) — already corrected during round-1 fix application; the original positional citation ("test 7") drifted from the live file's order (test #5 by position). The test name is canonical; positional references should be avoided.
>       **Recommendation:** Builder should avoid positional test references in any new docstrings or comments referencing this test; use the test name only.
>
> - [ ] **TA-T08-LOW-02 — T03 dependency-block hash substitution at T08 close** (severity: LOW, source: task_analysis.md round 1 L2)
>       When T08 closes (commit lands on `design_branch`), the autopilot orchestrator's commit-ceremony for T08 must edit `task_03_workflow_wiring.md` `## Dependencies` block to replace the placeholder text *"Spec at `task_08_audit_cascade_skip_terminal_gate.md` (drafted 2026-04-27 after round-4 H1 arbitration)."* with `Met: T08 shipped at <commit-hash>.` matching the T01 / T02 conventions on the same lines. Without this, T03's audit cycle would read a stale "spec drafted" annotation instead of "Met: T08 shipped at <hash>" and may flag the dependency as unsatisfied.
>       **Recommendation:** Add to T08's commit-ceremony close-out: after `git commit` lands the T08 implementation, the orchestrator runs an inline `Edit` on `task_03_workflow_wiring.md` to substitute the T08 hash, and includes that edit in the same commit (NOT a separate commit — keeps the T03/T08 bidirectional reference atomic).

Both LOWs preserved with full Recommendation text, both source-cited to round-1 analysis.

## What's structurally sound (round-2 final read)

Verified-and-correct on the post-round-1-fix T08 spec:

- **All round-1 fix applications are coherent.** Sub-graph wiring change section (lines 56-77) now reads as a complete three-bullet specification: gate node addition (424+448 conditional-wrap), destination-list updates (433-437 + 443-447 conditional-omit + END-add for after-validator), routing-function changes (END returns under skip-true). A Builder implementing the spec literally will produce a graph that compiles under both modes.
- **2 carry-over LOWs (TA-T08-LOW-01, TA-T08-LOW-02) all present as `[ ]` checkboxes.** Verified by `grep -c '\*\*TA-T08-LOW-'` returning 2 matches in `task_08_audit_cascade_skip_terminal_gate.md`.
- **No NEW findings introduced by round-1 fixes.** Walking the spec end-to-end after the H1 bullet insertion + the two MEDIUM citation/count corrections + the two LOW carry-over additions, no new structural claim, line citation, KDR drift, layer-rule break, or status-surface drift surfaced.
- **The "Why this task exists" historical paragraph (line 8) still cites `audit_cascade.py:292-296 + :447-448`.** This is in the historical narration of round-4 H1 (`The cascade primitive (T02 shipped at fc8ef19) hard-wires its terminal human_gate at audit_cascade.py:292-296 + :447-448`). Live verification: `audit_cascade.py:292-296` is the `human_gate(...)` constructor call (correct); `audit_cascade.py:448` is the gate edge to END (the `447-448` range straddles the closing `)` of the unrelated `add_conditional_edges` at L443-447 plus the gate edge at L448, which is a literal description of "the gate-edge area" and is not used as a Builder targeting citation). The prescriptive spec sections all carry the corrected citations from the round-1 fixes; this historical paragraph is narrative-only and does not need a tightening pass. Not a finding.
- **KDR re-grade — all 9 KDRs still preserved.** Same as round 1; round-1 fixes were all spec-text edits with no semantic shift. KDR-006 (RetryingEdge taxonomy) and KDR-011 (cascade primitive contract) explicitly preserved per AC + CHANGELOG.
- **Layer rule preserved.** All edits land in `ai_workflows/graph/audit_cascade.py` (graph layer); no upward imports.
- **Status surfaces consistent.** AC line 130 enumerates the two surfaces (per-task spec status, README task table row 08); no exit-criteria bullet for T08 since it's a sequencing exception per the spec's framing. Verified README row 08 carries `📝 Planned (T03 prerequisite — drafted 2026-04-27 after T03 round-4 H1 arbitration; ships before T03)`.
- **Dependencies block honoured.** Lists T02 only with `Met: T02 shipped at fc8ef19`. Matches T03's Dependencies-block citation convention.

## Cross-cutting context (T08)

- **Project memory consistent.** No on-hold flag for M12; T08 is freshly drafted as a T03 prerequisite. CS300 pivot status doesn't block T08.
- **Round-1 → round-2 trajectory.** Round 1's verdict was OPEN with 1 HIGH + 2 MEDIUM + 2 LOW. All round-1 fixes applied mechanically; both LOWs pushed to carry-over. Round 2 verifies the close-out. The /clean-tasks loop on T08 is complete.
- **T08 → T03 sequence.** With both T08 (this round) and T03 (round 6) at LOW-ONLY, the orchestrator's pipeline is: exit /clean-tasks for both → /auto-implement T08 → on T08 commit close, orchestrator substitutes T08 hash into T03's Dependencies block (per TA-T08-LOW-02) → /auto-implement T03. Both should land within autonomy budget.

## Verdict

**LOW-ONLY — 0 HIGH, 0 MEDIUM, 2 LOW (all in carry-over).** Round-1 fixes verified landed cleanly with no new findings introduced. Orchestrator may exit the /clean-tasks loop on T08 and proceed to /auto-implement T08.

---

# Combined verdict

- **T03 round 6:** LOW-ONLY (8 LOWs in carry-over, no HIGH or MEDIUM). /clean-tasks loop closes.
- **T08 round 2:** LOW-ONLY (2 LOWs in carry-over, no HIGH or MEDIUM). /clean-tasks loop closes.

Both specs are implementable as written. Sequencing per T03's `## Dependencies`: T08 ships first (via /auto-implement), then T03 ships after T08's commit-ceremony substitutes the T08 hash into T03's Dependencies block.
