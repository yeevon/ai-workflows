# M21 — Task Analysis

**Round:** 5 (T11 round 2)
**Analyzed on:** 2026-04-29
**Specs analyzed:** `task_11_claude_md_slim.md`
**Analyst:** task-analyzer agent

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 0 |
| 🟢 LOW | 3 |
| Total | 3 |

**Stop verdict:** LOW-ONLY

Round-1 H1 (line-budget unsatisfiable) is closed: the spec now lists six moves with a -40 arithmetic delta (136 → 96), an explicit fallback ("one-line tightening on §Repo layout") for the 1-line undershoot vs the ≤ 95 smoke threshold, and the smoke verifies the threshold rather than each move's contribution. Round-1 M1 (bash-safety) is closed: smoke steps 1, 5, 6, 7 now use `awk 'END { exit !(...) }'` instead of `$(...)`, and step 4 is unrolled into four explicit greps. Round-1 M2 is closed: the Sr. SDET ADV-1 cosmetic-edit-to-T10 item is dropped; T10 stays TERMINAL CLEAN. Round-1 M3 is closed: AC9 enumerates three actual surfaces — spec status line, README task-pool row 71, README §Exit criteria §G1 prose — with a matching deliverable bullet for the G1 prose edit.

## Findings

### 🔴 HIGH

*(none)*

### 🟡 MEDIUM

*(none)*

### 🟢 LOW

#### L1 — Move-table line ranges and item counts have minor cosmetic errors

**Task:** `task_11_claude_md_slim.md`
**Issue:** Move 1 cites CLAUDE.md "lines 85–97" but the threat-model section ends at line 94 with the `---` divider on line 96 (line 97 is blank). Move 2 cites "lines 39–50"; actual content spans 38–50 (heading at 38). Move 5 says "10 subagent one-liners" then enumerates 9 names (`task-analyzer`, `builder`, `auditor`, `security-reviewer`, `dependency-auditor`, `architect`, `roadmap-selector`, `sr-dev`, `sr-sdet`); the value 10 appears to count the leading "Subagents:" line. None of these blocks the Builder — the smoke verifies the final line-count regardless of which exact source ranges are excised — but the spec's own arithmetic (-9 for Move 5, citing 10 source lines minus 1 replacement) sits on the inflated count.
**Recommendation:** Builder may correct the cosmetic numbers in Move-table while applying the moves; if not corrected, no functional impact (the smoke verifies the global threshold).
**Push to spec:** yes — append to `## Carry-over from task analysis` in `task_11_claude_md_slim.md`.

#### L2 — Move 1 instruction sequencing for security-reviewer.md is workable but indirect

**Task:** `task_11_claude_md_slim.md`
**Issue:** `.claude/agents/security-reviewer.md` line 21 already carries `## Threat model (read first)` (a stub header). The Move 1 instruction says "append as a `## Threat model` section after the agent's existing system-prompt body. Verify the agent's existing prompt does not already duplicate the content; if it does, replace inline with the moved authoritative version." A hostile reading triggers two passes (append → discover dup → replace). The smoke step 3 grep `^## Threat model` matches both forms.
**Recommendation:** Builder should treat this as "replace the existing `## Threat model (read first)` block (line 21 + body, if any) with the full moved-from-CLAUDE.md threat-model content; rename heading to `## Threat model` (drop the `(read first)` parenthetical) so the section lands once with the canonical title."
**Push to spec:** yes — append to `## Carry-over from task analysis` in `task_11_claude_md_slim.md` as a clarifying note on Move 1.

#### L3 — AC9c amends G1's tautological grep example as a side effect

**Task:** `task_11_claude_md_slim.md`
**Issue:** M21 README §Exit criteria §G1 (line 37) currently says "Test: `wc -l CLAUDE.md` shows ≥ 30% reduction; `grep -c "^## " CLAUDE.md` confirms each removed section has a placeholder summary + anchor link." The grep-count test is tautological (a count of `## ` headings doesn't prove anchor links exist). Since AC9c amends this same prose to record satisfaction, the Builder has an opportunity to either (a) leave the test description alone and just append the satisfaction parenthetical, or (b) replace the tautological test with one of the spec's actual smoke greps (e.g. `grep -q "security-reviewer.md#threat-model" CLAUDE.md`).
**Recommendation:** Builder may either preserve G1 verbatim (minimal-edit) or replace the grep example with one that actually verifies anchor presence — either is acceptable; the satisfaction parenthetical is the load-bearing edit.
**Push to spec:** yes — append to `## Carry-over from task analysis` as a Builder-discretion note on AC9c.

## What's structurally sound

- **Six moves enumerated with line-count math.** -40 net delta closes round-1 H1; ≤ 95 line target is reachable with the explicit `§Repo layout` one-line tightening fallback if the math undershoots by 1–2 lines.
- **Bash-safety in smoke commands.** Steps 1, 5, 6, 7 use `awk 'END { exit !(NR <= 95) }'` and `awk 'END { exit !(NR == 0) }'` patterns instead of `$(...)` substitution; step 4 is unrolled into four explicit greps; no parameter expansion in loop bodies.
- **AC9 enumerates three real surfaces.** Spec `**Status:**` line, M21 README task-pool row 71, M21 README §Exit criteria §G1 prose — all three verified to exist at the cited locations.
- **T10 invariants preserved.** Smoke step 7 verifies the `_common/non_negotiables.md` pointer remains in 9/9 agents after ADV-1 strip + ADV-2 parenthetical restoration. The invariant pointer is currently present in 9/9 (verified inline).
- **ADV-1 + ADV-2 carry-over absorption is bounded and concrete.** The "9 edits" deliverable (spec line 111) is Builder-actionable; smoke step 5 (preamble removed in 9/9) and step 6 (parenthetical restored in 9/9) verify both invariants. Currently 9/9 agents carry the `**No git mutations or publish.**` preamble (verified inline) and 0/9 carry the `(read-only on source code; smoke tests required)` parenthetical (verified inline) — both deltas are real.
- **Move 3 source/replacement math holds.** `_common/verification_discipline.md` already covers code-task + wire-level + real-install rules (verified — sections 1, 2, 3 of that file); the Move 3 collapse of CLAUDE.md lines 131 + 132 (two bullets) into one pointer is consistent with the table's `2 → 1 = -1` arithmetic.
- **No KDR drift, no layer-rule drift, no SEMVER surface change.** T11 is doc-only on `.claude/agents/`, `CLAUDE.md`, M21 README, CHANGELOG; no `ai_workflows/` paths touched, no public-API surface affected, no `nice_to_have.md` adoption.
- **T10 dependency satisfied.** `_common/non_negotiables.md` and `_common/verification_discipline.md` both exist (`ls .claude/agents/_common/` confirms); T10 commit `2f73143` cited.

## Cross-cutting context

- Per project memory `project_autonomy_optimization_followups.md` and `project_m12_autopilot_2026_04_27_checkpoint.md`, M21 follows M20's autonomy-optimization shipment; M20 close-out shipped recently (commit `8c6e8a6` per `git log`). T11 is round 2 of the m21_clean autonomy run; T10 is shipped TERMINAL CLEAN.
- Per memory `feedback_autonomous_mode_boundaries.md`, T11 work happens on `design_branch` under autonomous mode; `task-analyzer` does not commit. This run is read-mostly + write-only-to-`task_analysis.md`, conformant.
- The three LOWs are all Builder-discretion clarifications, not blockers; orchestrator should push them to `## Carry-over from task analysis` per `/clean-tasks` LOW-ONLY exit protocol.
