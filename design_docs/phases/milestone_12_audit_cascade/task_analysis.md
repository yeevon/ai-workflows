# M12 Audit Cascade — Task Analysis

**Round:** 3
**Analyzed on:** 2026-04-27
**Specs analyzed:** `task_04_telemetry_role_tag.md` (T01-T03 + T08 already shipped)
**Analyst:** task-analyzer agent

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 0 |
| 🟢 LOW | 7 |
| Total | 7 |

**Stop verdict:** LOW-ONLY

LOW-ONLY — six pre-existing LOWs (TA-LOW-01..06) remain in the spec's `## Carry-over from task analysis` section as `[ ]` checkboxes; one fresh LOW (TA-LOW-07) surfaces a residual stale Option-1/Option-2 reference in §Propagation status. Orchestrator should push TA-LOW-07 into carry-over (or fix inline if mechanical) and exit the loop.

## Verification of round-2 fixes

### M1 — CHANGELOG bullet (round 2 MEDIUM): RESOLVED

The spec's `### CHANGELOG.md` block (lines 152-158) now correctly describes:

- Option 4 mechanism: `tiered_node.py` bullet at line 156 reads "*`role: str = ""` factory kwarg + usage.role stamp before cost_callback.on_node_complete; mirror of existing tier kwarg pattern per Option 4 locked decision*."
- 5 cost.py tests: `tests/primitives/test_cost_by_role.py` is described as "*new, 5 tests*."
- 2 cascade tests: `tests/graph/test_audit_cascade.py` is described as "*extended, 2 new tests*."
- No Option 1 references remain in the CHANGELOG-bullet block.

The `audit_cascade.py` bullet correctly reflects Option 4: "*pass role="author" / role="auditor" at the primary + auditor tiered_node construction sites; the existing _stamp_role_on_success state-channel wrapper is left in place unchanged*." Confirmed against live `audit_cascade.py:282-287` (primary `tiered_node`) and `:317-322` (auditor `tiered_node`); both `_stamp_role_on_success` wrappers at `:288` / `:323` are present and untouched as the spec describes.

### TA-LOW-05 — `tiered_node.py:264-274ish` line citation drift: PUSHED TO CARRY-OVER

Lines 233-235 of the spec contain TA-LOW-05 as a `[ ]` checkbox in `## Carry-over from task analysis` with full Recommendation text matching the round-2 finding. Verified against live source: `tiered_node.py:264-268` is the existing `tier` stamp; `cost_callback.on_node_complete` is at line 274. The new role-stamp block will land between them, pushing the callback call to ~line 280 post-edit. The `:264-274ish` bound is approximate per the carry-over note and acceptable.

### TA-LOW-06 — Out-of-scope ambiguity under Option 4: PUSHED TO CARRY-OVER

Lines 237-239 of the spec contain TA-LOW-06 as a `[ ]` checkbox in `## Carry-over from task analysis` with full Recommendation text matching the round-2 finding. The recommended replacement bullet for §Out of scope line 196 is verbatim in the carry-over Recommendation field, ready for Builder to apply at implement-close time.

## Findings

### 🟢 LOW

#### L1 — TA-LOW-01 (carried forward from round 1)

**Task:** `task_04_telemetry_role_tag.md`
**Issue:** Spec line 218 describes `tiered_node.py:194` line citation drift from round 1; informational note since the round-1 fix application removed the load-bearing reference.
**Recommendation:** No action — already in carry-over with Builder-action note. Builder verifies live source at implement time.
**Push to spec:** Already present (lines 217-219).

#### L2 — TA-LOW-02 (carried forward from round 1)

**Task:** `task_04_telemetry_role_tag.md`
**Issue:** CHANGELOG framing nuance — `### Added` vs `### Changed` for primitive-layer signature change.
**Recommendation:** No action — already in carry-over. Builder picks framing at CHANGELOG-write time.
**Push to spec:** Already present (lines 221-223).

#### L3 — TA-LOW-03 (carried forward from round 1)

**Task:** `task_04_telemetry_role_tag.md`
**Issue:** Test #6 verdict-node assumption is now verified against live `_audit_verdict_node` source (no LLM dispatch); informational note for Builder awareness.
**Recommendation:** No action — already in carry-over. Verified independently this round: `audit_cascade.py:714-810` `_audit_verdict_node` only calls `AuditVerdict.model_validate_json`; no LLM dispatch. Test count assertion would catch a future regression.
**Push to spec:** Already present (lines 225-227).

#### L4 — TA-LOW-04 (carried forward from round 1)

**Task:** `task_04_telemetry_role_tag.md`
**Issue:** Forward-deferral note has no T05 spec to land on yet; tracked-but-pending in carry-over.
**Recommendation:** No action — already in carry-over. T05 spec drafting (post-T04 close) picks this up via `/clean-tasks`.
**Push to spec:** Already present (lines 229-231).

#### L5 — TA-LOW-05 (carried forward from round 2)

**Task:** `task_04_telemetry_role_tag.md`
**Issue:** `tiered_node.py:264-274ish` line citation drift on the inserted role-stamp block.
**Recommendation:** No action — already in carry-over with full Recommendation text. Builder confirms inserted block lands between `:264-268` and `:274` in live source.
**Push to spec:** Already present (lines 233-235).

#### L6 — TA-LOW-06 (carried forward from round 2)

**Task:** `task_04_telemetry_role_tag.md`
**Issue:** §"Out of scope" bullet wording is now ambiguous under Option 4 (the `tiered_node` factory signature DOES change, even though the cascade-primitive `audit_cascade_node` signature does not).
**Recommendation:** No action — already in carry-over with verbatim replacement text for §Out of scope line 196. Builder applies at implement-close time.
**Push to spec:** Already present (lines 237-239).

#### L7 — Stale Option-1/Option-2 reference in §Propagation status (NEW this round)

**Task:** `task_04_telemetry_role_tag.md`
**Location:** Lines 200-205 (§Propagation status), specifically line 204.
**Issue:** The first anticipated forward-deferral bullet at line 204 reads: *"If the role-stamp ordering issue (cascade primitive writes `cascade_role` AFTER the LLM call) requires Option 2 (`RunnableConfig.configurable` plumbing) instead of Option 1 (entry-side write), the cascade primitive's API surface grows a `cascade_role` configurable key — surface as a forward-deferral to T07 close-out for documentation in ADR-0004."* Under Option 4 (locked 2026-04-27 — see lines 122-128), the role tag is closure-bound at construction time on `tiered_node` and does NOT depend on `state['cascade_role']` ordering. The Option-1-vs-Option-2 forward-deferral scenario is logically moot. The bullet is dead text post-Option-4 lock.

This is not a Builder-blocker — the Builder will simply not surface this forward-deferral at audit close because the scenario does not arise — but it is residual cruft from round-1 hypotheticals that the round-2 fix application missed (the M1 fix focused on the CHANGELOG bullet and §Out of scope, not on §Propagation status).

**Recommendation:** Either (a) delete the line-204 bullet entirely (cleanest — Option 4 makes the scenario impossible) and leave the second bullet about T05's `by_role` aggregation in place, or (b) reword to reflect Option 4: *"Under Option 4 (factory-time role binding), no role-stamp ordering issue exists — the role is closure-bound at cascade construction time. Bullet retained as a record of the round-1 hypothetical that Option 4 obviated."* Option (a) is cleaner.

**Apply this fix:**
old_string:
```
- If the role-stamp ordering issue (cascade primitive writes `cascade_role` AFTER the LLM call) requires Option 2 (`RunnableConfig.configurable` plumbing) instead of Option 1 (entry-side write), the cascade primitive's API surface grows a `cascade_role` configurable key — surface as a forward-deferral to T07 close-out for documentation in ADR-0004.
- If T05's standalone `run_audit_cascade` MCP tool needs to surface `by_role` aggregation in its output schema, that wiring lands at T05 — surface as a carry-over to T05's spec at draft time.
```
new_string:
```
- If T05's standalone `run_audit_cascade` MCP tool needs to surface `by_role` aggregation in its output schema, that wiring lands at T05 — surface as a carry-over to T05's spec at draft time.
```
**Push to spec:** Yes — append as TA-LOW-07 in `## Carry-over from task analysis` if orchestrator prefers carry-over over inline fix. Inline fix is also acceptable (mechanical text deletion).

## What's structurally sound

- M1 fix verified: CHANGELOG bullet correctly describes Option 4 mechanism, 5 cost.py tests, 2 cascade tests; no residual Option 1 references in the CHANGELOG block.
- TA-LOW-05 + TA-LOW-06 verified: present as `[ ]` checkboxes in `## Carry-over from task analysis` with full Recommendation text from round-2 findings.
- Live source citations all verified this round:
  - `cost.py`: `class TokenUsage` at line 66, `class CostTracker` at line 93, `by_tier` at line 116, `by_model` at line 125, `_roll_cost` at line 156. Spec citations accurate.
  - `tiered_node.py:264-268`: existing `tier` stamp confirmed; `cost_callback.on_node_complete` at line 274. Insertion point for the role stamp is unambiguous.
  - `audit_cascade.py:282-287` (primary `tiered_node`) and `:317-322` (auditor `tiered_node`): construction sites confirmed; `_stamp_role_on_success` wrappers at `:288` (`role="author"`) and `:323` (`role="auditor"`) present and consistent with the spec's "leave in place unchanged" plan.
  - `_audit_verdict_node` (`audit_cascade.py:714+`): pure parse step (`AuditVerdict.model_validate_json` at line 749); no LLM dispatch. Test #6's exact-2-records assertion is structurally sound.
- KDR drift check: spec preserves KDR-002 (no MCP-substrate change), KDR-003 (no Anthropic SDK), KDR-004 (validator pairing untouched), KDR-006 (no bespoke retry), KDR-008 (no MCP schema change), KDR-009 (no checkpoint changes), KDR-013 (no external-workflow scope), KDR-011 (telemetry surface explicitly cited as the goal), KDR-014 (explicitly addressed at line 128 — `role` is primitive-layer factory kwarg, not a quality knob).
- Layer rule respected: `primitives → graph` direction only (`TokenUsage` / `CostTracker` in `primitives/cost.py`; `tiered_node` + `audit_cascade` in `graph/`; cascade calls into `tiered_node` which is a `graph`-internal call). No upward imports.
- SEMVER: backward-compatible additive change (new `role: str = ""` kwarg with default; new `by_role` method; new `TokenUsage.role` field with default). No breaking change. `### Added` framing under `## [Unreleased]` is correct.
- Status surfaces: spec AC line 178 names all three surfaces (spec status line, milestone README task-table row 04 status column, milestone README §Exit-criteria bullet 6) — verified against milestone README line 67 (Kind = `code + test`, Status = `📝 Planned`). No status-surface mismatch.
- Cross-task dependencies: T01 / T02 / T03 / T08 cited as shipped (ship hashes at lines 182-185); spec correctly identifies the cascade-construction sites that depend on T03's primary + auditor `tiered_node` calls.
- Wire-level smoke test (`test_cascade_records_role_tagged_token_usage_per_step`) named in AC at line 177 and described in §Deliverables at line 144 — invokes compiled cascade end-to-end through real `tiered_node` + real `cost_callback`. Satisfies CLAUDE.md non-inferential code-task verification rule.

## Cross-cutting context

- Per project memory `project_m13_shipped_cs300_next.md`: post-0.2.0 + CS300 pivot active. M12 is being hardened ahead of CS300's return trigger; the current `/clean-tasks` cycle is preparing T04 for autonomous-mode `/auto-implement` consumption.
- Per memory `feedback_autonomous_mode_boundaries.md`: T04 implement will run under `/auto-implement` in the Docker sandbox; the orchestrator will commit + push to `design_branch` only. T04's primitive-layer signature change (`tiered_node` gains `role: str = ""`) is backward-compatible and safe for unattended autonomy.
- L7 is the kind of residual cruft typical after a multi-round /clean-tasks loop with a user-arbitrated decision (Option 4 locked) — fix-application focused on the headline issue (M1 — CHANGELOG bullet) and on the explicitly-flagged round-2 LOWs (L1 → §Out of scope; L2 → carry-over note), but missed the secondary §Propagation status bullet that was also Option-1/Option-2-framed. This is the kind of finding a third verification pass naturally surfaces.
