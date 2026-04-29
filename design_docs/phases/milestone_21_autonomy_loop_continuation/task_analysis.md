# M21 Autonomy Loop Continuation — Task Analysis

**Round:** 2 (T24 round 2)
**Analyzed on:** 2026-04-29
**Specs analyzed:**
- `task_10_common_rules_extraction.md` (✅ Complete; commit 2f73143; cross-spec consistency only — locked)
- `task_11_claude_md_slim.md` (✅ Done; commit 012a9d9; cross-spec consistency only — locked)
- `task_24_md_discoverability.md` (📝 Planned; primary analysis target)

**Analyst:** task-analyzer agent

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 0 |
| 🟢 LOW | 3 |
| Total | 3 |

**Stop verdict:** LOW-ONLY

(Zero HIGH, zero MEDIUM. The three LOWs carry over from round 1 — they remain unfixed in the spec because the orchestrator's policy is to push LOWs to the spec's carry-over section on the LOW-ONLY exit, not to round-fix them. The orchestrator should now (a) push L1/L2/L3 to T24's "Carry-over from task analysis" section as TA-LOW-01 / TA-LOW-02 / TA-LOW-03 and (b) exit the loop.)

## Round 1 fixes — verification

All three round-1 MEDIUM fixes landed correctly:

- **M1 (resolved).** `agent_return_schema.md` reference dropped from `task_24_md_discoverability.md` Step 2 final paragraph. Verified: `grep -n "agent_return_schema" task_24_md_discoverability.md` returns no matches. The behaviour-preservation check now correctly names only `_common/non_negotiables.md` and `_common/verification_discipline.md` (the two T10-delivered files actually present under `.claude/agents/_common/`).
- **M2 (resolved).** AC8 (c) at line 140 now reads: *"M21 README §Exit criteria §G2 prose is amended in-place with an explicit partial-satisfaction parenthetical, e.g. `(rubric locked at T24; .claude/agents/*.md and _common/*.md portion satisfied; agent_docs/ portion deferred to T26 — audit script reusable there)`. The parenthetical must name both the satisfied portion and the deferred portion so future readers see the partial coverage immediately."* §Out of scope at line 144 mirrors this with: *"The README §G2 satisfaction parenthetical (AC8 c) makes this partial coverage explicit so the deferred portion is auditable."* Both surfaces now agree.
- **M3 (resolved).** Smoke step 5 (line 106) now opens with `rm -f /tmp/aiw_t24_t10inv.txt`; smoke step 6 (line 115) now opens with `rm -f /tmp/aiw_t24_t11inv.txt`. Stale-artifact false-positive foreclosed for repeated Auditor regression runs.

No regressions introduced by the round-1 edits; cross-spec consistency with the locked T10/T11 specs preserved.

## Findings

### 🔴 HIGH

*None.*

### 🟡 MEDIUM

*None.*

### 🟢 LOW

#### L1 — Smoke step 8 CHANGELOG grep is loose (carried from round 1)

**Task:** `task_24_md_discoverability.md`
**Issue:** `grep -q "M21 Task 24" CHANGELOG.md` matches any mention of the string anywhere — including a body reference inside another task's entry. The established T10/T11 entries use `### Added — M21 Task <NN>:` / `### Changed — M21 Task <NN>:` as the section anchor.
**Recommendation:** Tighten to `grep -qE '^### (Added|Changed) — M21 Task 24:' CHANGELOG.md`.
**Push to spec:** yes — append to T24's "Carry-over from task analysis" section as TA-LOW-01.

#### L2 — Audit script has no CI hookup; will rot silently (carried from round 1)

**Task:** `task_24_md_discoverability.md`
**Issue:** `scripts/audit/md_discoverability.py` is created at T24 and run by the Auditor smoke, but it is not attached to `.github/workflows/ci.yml`. Sections that grow past 500 tokens *after* T24 ships will not regress any gate; only the next person to re-run the smoke notices.
**Recommendation:** Either add a CI step in T24's deliverables (one job invoking `uv run python scripts/audit/md_discoverability.py --check section-budget --target .claude/agents/`) or note the deferral as a forward-deferred follow-up to T25 (periodic skill / scheduled-task efficiency audit). T25 is the natural home.
**Push to spec:** yes — append to T24's "Carry-over from task analysis" section as TA-LOW-02 with the recommendation "deferred to T25 unless T24 Builder elects to add a CI step in-scope."

#### L3 — Rule 5 (one-topic-per-file) is not encoded in the audit script — worth saying so (carried from round 1)

**Task:** `task_24_md_discoverability.md`
**Issue:** AC2 says rule-5 violations are "recorded in the issue file as flagged candidates; refactor only when a clear destination exists." That's fine, but the audit script's `--check` flags only cover rules 1–4 (`summary|section-budget|code-block-len|section-count`). Rule 5 is purely human-judged. Without an explicit note, a Builder may try to encode rule 5 in the script and burn cycles.
**Recommendation:** Add one sentence to §Step 1: "Rule 5 (one topic per file) is human-judged at audit time; the audit script does not attempt to encode it. Baseline-table column for rule 5 is filled in manually."
**Push to spec:** yes — append to T24's "Carry-over from task analysis" section as TA-LOW-03.

## What's structurally sound

- **Round 1 MEDIUMs all resolved cleanly.** Verified inline above; no regressions.
- **T10 invariant holds.** All 9 top-level `.claude/agents/*.md` reference `_common/non_negotiables.md` (verified — grep returns 9). T24 smoke step 5 will pass.
- **T11 invariant holds.** `auditor.md`, `task-analyzer.md`, `architect.md`, `dependency-auditor.md` all carry `## Load-bearing KDRs` (verified — grep returns 4). T24 smoke step 6 will pass.
- **CLAUDE.md slim landed.** Currently 83 lines (T11 satisfaction parenthetical accurate at 39% reduction from 136).
- **`_common/` directory contents match T24's audit scope.** `ls .claude/agents/_common/` returns exactly `non_negotiables.md` and `verification_discipline.md` — the two files T24 names. No third `_common/` file exists at T24 time, so the AC1 "11 audited MD files (9 + 2)" arithmetic holds.
- **Sibling slash-command `_common/` correctly excluded.** `.claude/commands/_common/` exists and contains 8 files (`agent_return_schema.md`, `auditor_context_management.md`, `cycle_summary_template.md`, `effort_table.md`, `gate_parse_patterns.md`, `integrity_checks.md`, `parallel_spawn_pattern.md`, `spawn_prompt_template.md`). T24's rubric scope (line 23) explicitly excludes `.claude/commands/*.md` — no scope leak.
- **Research-brief citation accurate.** T24 spec line 5 cites `research_analysis.md` line 294 — verified, line 294 is exactly `### T24 — MD-file discoverability audit (search-by-section)`.
- **Task-pool row 73 reference accurate.** README line 73 is the T24 row (Status column = `📝 Candidate`), as AC8 (b) claims.
- **`agent_docs/` correctly identified as not-yet-existing.** `ls agent_docs/` returns "no such file or directory" — confirms T24's §Out of scope deferral to T26 is materially correct, not just spec-text.
- **`scripts/audit/` correctly identified as new.** `ls scripts/audit/` returns "no such file or directory" — confirms the script declared in §Deliverables and AC5 is a new-create, not an edit-of-existing.
- **Bash-safety discipline propagated.** T24 smoke avoids `$(...)` and parameter expansion in loops, matching T11's pattern. `_common/verification_discipline.md` line 29 confirms the `## Bash-safety rules (all agents)` section the spec references.
- **Layer rule + KDR cleanliness.** T24 only edits `.claude/agents/*.md`, `_common/*.md`, `scripts/audit/md_discoverability.py`, `issues/task_24_issue.md`, `CHANGELOG.md`, and the M21 README. No `ai_workflows/` touches. No KDR drift. SEMVER-neutral.
- **Status-surface flips enumerated.** AC8 lists three surfaces (spec Status, README task-pool row 73, README §G2 prose) — correct. There is no `tasks/README.md` for M21, so the four-surface checklist applies as three.
- **Cross-spec consistency with T10 / T11.** T10 + T11 are locked. No T24 claim contradicts a T10 / T11 deliverable; T24 explicitly builds on the destination files T10 created and the slimmed CLAUDE.md T11 produced.
- **Rubric is non-trivial.** Manual scan still confirms section-budget violations across `task-analyzer.md` (Phase 2 ≈ 1058 words), `auditor.md` (Propagation status ≈ 428 words), `sr-dev.md` + `sr-sdet.md` (six-lenses sections at 690 / 788 words), `architect.md` (Stop and ask ≈ 417 words). T24 has real work to do.

## Cross-cutting context

- M21 status per project memory `project_autonomy_optimization_followups.md` is **active under autonomy-optimization follow-ups**. T10 + T11 shipped within the last 24h (commits `2f73143` and `012a9d9`); T24 is the next logical task per README §Suggested phasing (Phase E order: T10 → T11 → T24 → T12).
- Phase-E ordering matters: T24 strongly precedes T12 (Skills extraction) per README §Cross-phase dependencies. With round-1 M2 resolved, the §G2 satisfaction parenthetical now correctly names the deferred `agent_docs/` portion, so T12 / T26 inherit a non-misleading exit-criterion record.
- M20 is closed; baseline measurements stable. M21 wins are incremental on top.
- **Locked specs (T10, T11) are not edited.** Cross-spec checks against T10/T11 produced no inconsistencies in either round.
- **LOW-ONLY exit semantics.** Per the orchestrator contract, on LOW-ONLY the three LOWs (L1, L2, L3) push down to T24's "Carry-over from task analysis" section as TA-LOW-01 / TA-LOW-02 / TA-LOW-03. No further round needed; the Builder absorbs them at `/clean-implement` time.
