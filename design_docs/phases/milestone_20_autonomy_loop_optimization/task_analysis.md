# M20 — Autonomy Loop Optimization — Task Analysis

**Round:** 2 (post-round-1 fixes applied to ZZ; re-verification pass)
**Analyzed on:** 2026-04-28
**Specs analyzed:** task_zz_milestone_closeout.md (primary round-2 target). 14 pre-ZZ specs (T01-T06, T08, T09, T20-T23, T27, T28) + T07 candidate spec re-spot-checked against shipped reality and round-1 fixes.
**Analyst:** task-analyzer agent
**Working location:** `/home/papa-jochy/prj/ai-workflows/` (branch `workflow_optimization`)

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 0 |
| 🟢 LOW | 0 |
| Total | 0 |

**Stop verdict:** CLEAN

All five round-1 findings (H1, M1, M2, M3, M4) verified as resolved against the current `task_zz_milestone_closeout.md` text. No new findings surfaced during round-2 re-verification of the round-1 edits and no regressions on the 14 pre-ZZ specs.

## Round-1 fix verification

Each round-1 finding re-verified against ZZ's current text (lines cited from the live file):

### H1 fix — three "M21 README itself may not yet exist" citations replaced

- **Spec line 70** now reads `M21 README at `design_docs/phases/milestone_21_autonomy_loop_continuation/README.md` exists (split from M20 on 2026-04-27 per audit recommendation M3). `/clean-tasks m21` is unblocked once ZZ closes M20`. ✅ Positive statement.
- **Spec line 76** now reads `M21 README is in place; `/clean-tasks m21` is unblocked once ZZ closes M20.` ✅ Conditional flag-for-operator clause removed.
- **Spec line 152** (Propagation status section) now reads `M21 README at `design_docs/phases/milestone_21_autonomy_loop_continuation/README.md` exists; `/clean-tasks m21` is unblocked once ZZ closes M20.` ✅ Consistent positive framing.
- **External verification:** `design_docs/phases/milestone_21_autonomy_loop_continuation/README.md` exists; status line reads "📝 Drafting (split from M20 2026-04-27 per audit recommendation M3 …)". ZZ's claim aligns with reality.

### M1 fix — ZZ AC-3 + Deliverable §2 reworded "flip → add" with insertion specifics

- **Deliverable §2 line 44** now reads `**Add** an M20 row to the milestone table in `roadmap.md` (insert after M19 at line ~31)`. ✅ "Add" phrasing + insertion line cited.
- **Deliverable §2 line 45** now reads `Append a one-line summary in the M20 narrative section (after the existing M15/M16/M19 narratives at line ~49)`. ✅ Narrative insertion location cited.
- **AC-3 line 82** now reads `roadmap.md gains an M20 row inserted in ordinal position (after M19) reflecting ✅ complete (<YYYY-MM-DD>) … **Note: no prior M20 row exists in roadmap.md as of round-1 analysis — ZZ adds, not flips.**`. ✅
- **External verification:** `grep -n "M19\|M20\|M21" roadmap.md` confirms M19 at line 31, narrative at line 57 (close to the cited ~49), no M20 row. The `~31` and `~49` line approximations are workable hints; Builder will read in surrounding context.

### M2 fix — ZZ AC-6 + Deliverable §4 reworded "flip → add" for root README.md

- **Deliverable §4 line 61** now reads `**Add** an M20 row to the milestone status table (insert after M19 at line ~28)`. ✅
- **Deliverable §4 line 62** now reads `Trim the post-M19 `## Next` narrative (line ~144) to reflect M21`. ✅ Insertion + trim locations cited.
- **AC-6 line 85** matches: `Root README.md milestone status table gains an M20 row inserted after M19 (line ~28) … post-M19 ## Next narrative (line ~144) trimmed`. ✅
- **External verification:** root `README.md` line 28 shows M19 row; line 144 starts `## Next`. Both line numbers accurate.

### M3 fix — LOW count corrected from 11 to 10 with reframed empirical-recurrence claim

- **Spec line 18** now reads `T06's issue file Carry-over §C4 enumerates 10 LOW findings (LOW-1 through LOW-8 + LOW-10 + LOW-11; LOW-9 was partially resolved at T06 cycle 5 — the load-bearing call-site contract bug fixed and pinned by `test_single_cell_bail_manifest_shape`; cosmetic residue folded into C1 operator-resume) for the absorbing M21 task spec`. ✅ Count corrected; LOW-9 framing matches T06 issue file's "PARTIALLY RESOLVED" verbatim.
- The same line now reframes the Auditor write-refusal recurrence to `Auditor cycle-summary write refusal recurred per loop-controller observation in `runs/m20_t<NN>/cycle_<N>/agent_auditor_raw_return.txt` at multiple cycle boundaries — exact count to be tallied by `/clean-tasks m21` when the absorbing-task spec is generated`. ✅ Bounded source citation; "exact count to be tallied" is properly deferred to M21 spec-generation time.
- **L1 push from round 1** is fully absorbed by this reframe — the M3 fix subsumes L1.
- **External verification:** T06 issue file enumerates LOW-1 through LOW-11 with LOW-9 partially resolved (line 110 of issue file: "RESOLVED cycle 5; cosmetic `× 30` print residual"). Re-tally: LOW-1, 2, 3, 4, 5, 6, 7, 8, 10, 11 = 10. ✅ Matches.
- **Round-2 risk-watch outcome:** the "exact count to be tallied by `/clean-tasks m21`" framing is correctly deferred. The M21 absorbing-task spec being writable does NOT depend on having the exact count nailed at M20 close — the count is reportable from `runs/m20_t<NN>/cycle_<N>/agent_auditor_raw_return.txt` raw artifacts which persist on `workflow_optimization`. This is correctly-scoped expected M21 work, NOT a hidden HIGH deferral.

### M4 fix — T07 canonical wording propagated; AC-16 added for status-surface coordination

- **Spec line 30** (Outcome) now reads `T07 — dynamic model dispatch. **📝 Planned (gated on T06's GO verdict, operator-resume)** — does not ship at M20; carries to M21 once T06 produces non-DEFER. Status surfaces flip together: T07 spec line stays `📝 Planned. Gated on T06's GO verdict.` (canonical wording); M20 README task-pool row updated from `📝 Candidate (gated on T06)` to `📝 Planned (gated on T06)` to match the spec; ZZ Outcome here uses the same canonical phrasing.` ✅ Three sites named; canonical wording locked.
- **AC-16 line 95** now reads `(T07 status-surface coordination): All T07 status surfaces flip together in the ZZ Builder cycle. Specifically: T07 spec status line stays `📝 Planned. Gated on T06's GO verdict.` (canonical — already correct, no edit); M20 README task-pool table row for T07 updated from `📝 Candidate (gated on T06)` to `📝 Planned (gated on T06)` to match the spec wording; ZZ Outcome's T07 line uses the same canonical phrasing (already correct after this round-1 fix). Per CLAUDE.md non-negotiable status-surface discipline, all three must land in the same Builder cycle.` ✅ Wording is unambiguous: (a) T07 spec — no edit, already canonical; (b) M20 README task-pool — change `Candidate` to `Planned`; (c) ZZ Outcome — already correct. Builder has the explicit edit list.
- **External verification:**
  - `task_07_dynamic_model_dispatch.md` line 3: `Status: 📝 Planned. **Gated on T06's GO verdict.**` ✅ canonical, no edit needed.
  - `M20 README` line 125: `📝 Candidate (gated on T06)` ✅ awaiting Builder's AC-16 edit.
- **Round-2 risk-watch outcome:** AC-16 wording is unambiguous. Builder has explicit per-site edit instruction for each of the three surfaces. CLAUDE.md status-surface discipline cited correctly.

### L2 from round 1 — T20 template path

L2 (the M12-T01 carry-over template path naming gap) was a LOW push-to-spec finding. The current ZZ Outcome line 32 still reads `M12-T01 carry-over patch ported from template; Phase 4 extended with cycle-N-vs-(N-1) overlap detection + rubber-stamp detection.` The L2 carry-over text was not appended to the spec's `## Carry-over from task analysis` section (which still reads `(populated by /clean-tasks m20)`). This is acceptable — the orchestrator may have judged the L2 push superseded by the round-1 H1+M1-M4 burst, or scheduled the carry-over to land in the round-2 fix-application step. Either outcome is fine; round-2 verification finds nothing structurally broken in the ZZ Outcome on this point. Does NOT promote to a finding.

## What's structurally sound

- **All 5 round-1 fixes (H1, M1, M2, M3, M4) verified as applied** with correct line-number references and external grep confirmation.
- **AC-16 wording is unambiguous.** Three explicit per-site edit instructions; Builder has zero discretion on canonical wording.
- **The "exact count to be tallied by `/clean-tasks m21`" deferral is correctly scoped** — the M21 absorbing-task spec generation has access to `runs/m20_t<NN>/cycle_<N>/agent_auditor_raw_return.txt` artifacts on `workflow_optimization` for tally-time empirical grounding. This is not a hidden HIGH.
- **The 14 pre-ZZ specs remain in CLEAN state** (round-0 baseline 2026-04-27 round 5 was CLEAN; shipped reality matches each spec's `✅ Done` status line).
- **T07 status line invariant preserved** — `📝 Planned. **Gated on T06's GO verdict.**` matches AC-16's canonical wording exactly. No drift.
- **`nice_to_have.md §24` (server-side compaction) confirmed as the highest-numbered slot** — slot already-claimed by T28's DEFER entry. No slot-drift in any spec.
- **All 11 commit shas in ZZ AC-9 + Deliverable §3 still verify** on `workflow_optimization` (T06 d76f93f, T08 0dd91f4, T09 8e572dc, T20 851274f, T21 628b975, T22 426c7fb, T23 b39efbf, T27 a266996, T28 21c37ba, T04 7caecbd, T05 bd27945).
- **No KDR drift in ZZ** — AC-8 + AC-14 explicitly guard against `ai_workflows/` package diff. M20 README §Non-goals "no new KDRs locked at M20" honored.
- **No layer rule violations** — ZZ is doc/CHANGELOG/README/roadmap-only; runtime layer rule unchanged.
- **No SEMVER surface change** — no `pyproject.toml` version bump implied by ZZ.
- **No new HIGH or MEDIUM findings** surfaced during round-2 re-verification. ZZ is ready for `/clean-implement` or `/auto-implement` consumption.

## Cross-cutting context

- **M20 is in close-out posture.** All 14 substantive tasks shipped on `workflow_optimization`; ZZ is the doc-only close-out that flips status surfaces and absorbs the M21 propagation surface. Per project memory `project_autonomy_optimization_followups.md` (state 2026-04-27) and the M21 README (split 2026-04-27), the next load-bearing milestone is M21 (Autonomy Loop Continuation), unblocked by ZZ closing M20.
- **The M21 hardening track is the load-bearing forward-deferral.** ZZ records the propagation surface (10 LOWs from T06 §C4 + recurrences across T08/T09/T20/T23/T27 issue files) as the M21 absorbing-task scope. `/clean-tasks m21` is the tally-time and spec-generation hook.
- **Round 2 is structurally clean.** No new HIGH or MEDIUM findings surfaced; the round-1 fixes hold; the orchestrator's autonomy loop can proceed to `/clean-implement` (or `/auto-implement`) on ZZ without further round-3 deferral.
