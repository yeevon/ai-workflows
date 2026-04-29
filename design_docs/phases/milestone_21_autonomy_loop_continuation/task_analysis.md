# M21 — Task Analysis

**Round:** 20
**Analyzed on:** 2026-04-29
**Specs analyzed:** task_17_spec_format_extension.md, task_18_parallel_builder_spawn.md, task_19_orchestrator_closeout.md, task_zz_milestone_closeout.md
**Analyst:** task-analyzer agent

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 0 |
| 🟢 LOW | 4 |
| Total | 4 |

**Stop verdict:** LOW-ONLY

## Findings

### 🟢 LOW

#### L1 — T17 smoke step 7 hard-pin to 9 agent files duplicates T15-style brittleness

**Task:** task_17_spec_format_extension.md
**Issue:** Smoke step 7 (`wc -l | awk '{ exit !($1 == 9) }'`) hard-pins the agent count to exactly 9. Prior tasks T13/T14/T15/T16 used the same pattern, but the M21 carry-over discipline already absorbed `TA-LOW-01 (accepted: agent count hard-pin at 9 for sibling parity)` for T15. T17 inherits the same trade-off — fine for sibling parity, but worth pre-acknowledging in carry-over so the Builder doesn't re-litigate.
**Recommendation:** Note in Carry-over from task analysis: "Agent count hard-pin at 9 kept for sibling parity with T13–T16; future agent-roster changes will sweep all sibling smokes."
**Push to spec:** yes — append to T17 "Carry-over from task analysis" section.

#### L2 — T18 worktree-cleanup AC-5 is asserted but no procedure step describes it

**Task:** task_18_parallel_builder_spawn.md
**Issue:** Step 1's procedure documents dispatch + overlap detection + cherry-pick, but does not document worktree cleanup when a slice produces no changes (test case 5). The Builder will need to add the cleanup step to satisfy AC-5; the spec leaves the exact shape (e.g. `git worktree remove`) as an implementation detail. Acceptable for a stretch task but worth flagging.
**Recommendation:** When T18 leaves stretch and is implemented, the Builder should add an explicit "If worktree diff is empty, run `git worktree remove <path>`" line in Step 1.
**Push to spec:** yes — append to T18 "Carry-over from task analysis": "Builder: add explicit worktree-cleanup-on-empty-diff procedure step under Step 1 to satisfy AC-5 / test 5."

#### L3 — T19 acceptance-criteria count mismatch with test count

**Task:** task_19_orchestrator_closeout.md
**Issue:** AC-1 covers smoke 1+2 (post-parallel merge + commit annotation). Step 3 (status-surface flips) has no dedicated AC — it is asserted as documentation only. Test 3 ("Status surfaces flip once (not N times)") therefore exercises behavior with no matching AC. Not a bug; a doc-task asymmetry the Auditor may flag at audit time.
**Recommendation:** Either add AC-2-bis "Status-surface single-flip discipline documented in §Step 3" or mark test 3 as covering AC-1 (status-flip is part of the close-out flow). Builder's choice at implement time.
**Push to spec:** yes — append to T19 "Carry-over from task analysis": "Test 3 (status-surface single-flip) has no dedicated AC; Builder picks: add an AC or fold the assertion into AC-1's coverage. Document the choice in the issue file."

#### L4 — T17/T18/T19 sibling specs do not pre-allocate `nice_to_have.md` slot numbers

**Task:** task_zz_milestone_closeout.md
**Issue:** ZZ AC-9 + T18/T19 defer-to-M22 condition both reference adding entries to `design_docs/nice_to_have.md` under heading `## Parallel-Builders (T18/T19 M21 defer)`. Current `nice_to_have.md` ends at `## 24. Server-side compaction via compact_20260112`. The next free slot is `## 25.` — none of the specs name this slot, leaving the ZZ Builder to compute it at close-out time. Low risk (only one milestone defers at a time) but explicit slot-claim avoids the M10-style slot-drift the Analyzer historically flags.
**Recommendation:** ZZ should claim slot `## 25. Parallel-Builders foundation (T18/T19 from M21)` if the deferral fires; the spec can note this as a target slot rather than a binding allocation.
**Push to spec:** yes — append to ZZ "Carry-over from task analysis": "If T18/T19 defer to M22, target `nice_to_have.md` slot is `## 25.` (next free as of 2026-04-29 round-20 analysis). Re-verify at ZZ time."

## What's structurally sound

- **Layer rule + KDR drift:** All four specs explicitly affirm "No runtime code changes in `ai_workflows/`" per M21 scope note. None of them touches the `primitives/graph/workflows/surfaces` boundary, the seven load-bearing KDRs, or any MCP / Anthropic-API / validator-pairing / RetryingEdge / FastMCP / SqliteSaver / external-workflow surface. KDR drift is structurally avoided.
- **Cross-spec dependency chain:** T17 → T18 → T19 ordering is correctly declared on both sides. T18 names T17 as prerequisite; T19 names T17 + T18 as prerequisites. ZZ depends on "T17 Done or Deferred" and "T18/T19 Done or Deferred" — explicit disposition required, not silent skip.
- **Stretch-goal defer-to-M22:** Both T18 and T19 carry an explicit `## Defer-to-M22 condition (explicit)` section naming the trigger ("T17 adopted on ≥ 5 tasks AND operator requests parallel dispatch"). ZZ AC-9 hooks the deferral into `nice_to_have.md` correctly.
- **Status-surface discipline:** Each spec's final AC enumerates the spec Status flip + the M21 README task-pool row flip. ZZ AC-7 covers ZZ's own row + the exit-criteria checkboxes. The M21 README confirms there is no `tasks/README.md` — surface (c) of the four-surface rule is correctly omitted.
- **Reference verification:** All cited file paths exist (`.claude/commands/clean-tasks.md` Phase 1, `.claude/commands/auto-implement.md` §Functional loop / §Project setup / §Commit ceremony Step C3). No broken cross-references found.
- **T10 + T24 invariant preservation:** T17 smoke steps 7+8 explicitly check that the 9/9 `_common/non_negotiables.md` reference holds and that `.claude/agents/` still passes the section-budget rubric. Confirmed via dry-run: both pass at HEAD.
- **CHANGELOG framing:** All three code-touching specs use `### Added — M21 Task NN: …` consistent with the M21 entries already promoted in CHANGELOG (T10–T16, T24–T26 all use `### Added` or `### Changed` per actual scope).
- **Round 19 fixes held:** Phase E + F specs (T10–T16, T24–T26) that hardened across rounds 1–19 are all `✅ Done` and not in scope for round 20. Their landing rows in the README task-pool match the spec Status lines.

## Cross-cutting context

- **Phase G is a foundation phase, not a parallelism rollout.** T17 is the only in-scope task; T18+T19 are explicitly stretch with defer-to-M22 carry-over already wired into ZZ. The specs correctly model this: T17 lands the format and the gate stub; T18+T19 are dormant code paths until the trigger fires.
- **No `nice_to_have.md` adoption inside M21 scope.** ZZ AC-9 only adds an entry under the deferral condition (T18/T19 not implemented). This matches CLAUDE.md "No `nice_to_have.md` adoption beyond what M20's threads already cover" and the M21 README §Non-goals.
- **Version impact:** None. All four specs touch `.claude/commands/`, `.claude/agents/_common/`, `tests/`, `design_docs/`, `CHANGELOG.md`. No `pyproject.toml`, no `ai_workflows/__init__.py`, no `__all__` change, no MCP schema change. SEMVER unaffected.
- **Project memory:** `project_m21_autopilot_2026_04_29_checkpoint.md` notes M21 autopilot paused mid-T15 cycle 1; T15 has since shipped (commit `5639cc5`). No memory note flags T17/T18/T19/ZZ as paused or pending external trigger.
- **Round-20 disposition:** LOW-ONLY → orchestrator pushes the four LOW carry-overs into the listed spec sections and exits the loop.
