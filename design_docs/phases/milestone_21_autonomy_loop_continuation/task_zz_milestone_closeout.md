# Task ZZ — Milestone Close-out

**Status:** ✅ Done.
**Kind:** Closeout / doc.
**Grounding:** [milestone README](README.md) · all M21 task specs · [M20 ZZ spec](../milestone_20_autonomy_loop_optimization/task_zz_milestone_closeout.md) (close-out pattern) · [M14 T02](../milestone_14_mcp_http/task_02_milestone_closeout.md) · [CLAUDE.md](../../../CLAUDE.md) §Status-surface discipline · `architecture.md` §9 KDRs (drift-check anchors).

## What to Build

Close M21. All Phase E + F tasks have shipped. Phase G status:
- **T17 (spec format extension):** landed or deferred (update accordingly).
- **T18 (parallel Builder spawn):** stretch — landed or deferred to M22 (document explicitly).
- **T19 (orchestrator close-out):** stretch — landed or deferred to M22 (document explicitly).

ZZ is the close-out doc that flips all remaining status surfaces, promotes CHANGELOG entries, verifies the milestone exit criteria (G1–G6), and records the M22 carry-over for any deferred tasks.

**No runtime code change.** If any finding surfaces a runtime code need during close-out, it forks to a new task.

### Phase E summary (for the Outcome section)

- **T10** ✅ — `.claude/agents/_common/non_negotiables.md` + `_common/verification_discipline.md` extracted; all 9 agent frontmatter files reference them.
- **T11** ✅ — CLAUDE.md slimmed from 136 lines to 83 lines (39% reduction); threat-model → `security-reviewer.md`; KDR table → `auditor.md`, `task-analyzer.md`, `architect.md`, `dependency-auditor.md`; each removed section has pointer + 1-paragraph summary in CLAUDE.md.
- **T12** ✅ — Skills extraction pattern locked in `_common/skills_pattern.md`; `dep-audit` Skill extracted as the first live Skill; progressive-disclosure frontmatter shape established for T13–T16.
- **T24** ✅ — MD-file discoverability rubric applied to `agent_docs/` + `.claude/agents/`; `scripts/audit/md_discoverability.py` + CI walk; every file has 3-line summary, `##` anchors, ≤500-token sections.
- **T25** ✅ — `/audit-skills` periodic audit command + `scripts/audit/skills_efficiency.py`; CI walks both audit scripts every PR.
- **T26** ✅ — Two-prompt long-running pattern: `runs/<task>/plan.md` (immutable) + `runs/<task>/progress.md` (cumulative); `agent_docs/long_running_pattern.md`; trigger: opt-in via `**Long-running:** yes` or N>=3 cycles.

### Phase F summary

- **T13** ✅ — `/triage` post-halt diagnosis Skill; `runs/triage/<timestamp>/report.md`; consolidated issue + recommendation + commit context.
- **T14** ✅ — `/check` on-disk vs pushed-state Skill; four-divergence-surface check (local branch, pushed branch, PyPI if opted in).
- **T16** ✅ — `/sweep` ad-hoc reviewer Skill; sr-dev + sr-sdet + security-reviewer in parallel; `runs/sweep/<timestamp>/report.md`.
- **T15** ✅ — `/ship` manual happy-path Skill; host-only; six-step sequence ending in `uv publish`; autonomy-mode guard.

### Phase G summary (to be filled in)

Document what shipped vs. deferred. For each deferred task: name the M22 carry-over condition.

## Deliverables

### 1. Milestone README ([README.md](README.md))

- Flip **Status** to `✅ Complete (<YYYY-MM-DD>)`.
- Append **Outcome** section covering all shipped tasks and DEFER verdicts per the summaries above.
- Fill in **Propagation status**: T18+T19 deferral to M22 if applicable; operator-resume items if any.
- Verify all **Exit criteria** checkboxes:
  - G1: CLAUDE.md ≥ 30% reduction + pointer+anchor discipline. ✅ (at T11)
  - G2: MD-file discoverability completed. ✅ (at T24)
  - G3: At least one productivity command shipped. ✅ (T13 /triage + T14/T15/T16)
  - G4: Spec format extension for per-slice scope. ✅ (at T17) or 📝 Deferred
  - G5: `/audit-skills` + two-prompt pattern. ✅ (at T25 + T26)
  - G6: At least one extraction Skill. ✅ (at T12 dep-audit)

### 2. Roadmap ([roadmap.md](../../../design_docs/roadmap.md))

- Flip the M21 row to `✅ Complete (<YYYY-MM-DD>)`.
- Append a one-line M21 narrative summary after the M20 entry.

### 3. CHANGELOG ([CHANGELOG.md](../../../CHANGELOG.md))

- Promote all M21 `[Unreleased]` entries into a new dated section `## [M21 Autonomy Loop Continuation] - <YYYY-MM-DD>`.
- Add a ZZ close-out entry at the top of the new section: shipped tasks, DEFER verdicts on T18+T19 (if applicable), autopilot baseline summary (cycles, commits, token estimates).

### 4. Root README.md

- Flip M21 row from `Planned` to `Complete (<YYYY-MM-DD>)`.
- Update `## Next` section to name the next planned milestone after M21.

### 5. Architecture.md

- **No new KDRs at M21** (per README §Non-goals). One-line edit only if any `scripts/` addition from Phase G warrants a §4 or §6 mention. If none: record "no architecture.md change" in the audit log.

### 6. M22 propagation surface (if T18/T19 deferred)

If T18/T19 were not implemented in M21:
- Add entries to `design_docs/nice_to_have.md` under a new heading `## Parallel-Builders (T18/T19 M21 defer)`: trigger condition = "T17 adopted on ≥ 5 tasks AND operator requests parallel dispatch".
- ZZ issue file records the deferred scope.

## Acceptance criteria

1. **AC-1:** Milestone README Status → `✅ Complete (<YYYY-MM-DD>)`; Outcome section covers all shipped tasks + DEFER verdicts + autopilot baseline.
2. **AC-2:** All 6 exit criteria (G1–G6) verified in README; each noted as ✅ or 📝 Deferred with carry-over.
3. **AC-3:** `roadmap.md` M21 row flipped to `✅ Complete` with one-line narrative.
4. **AC-4:** `CHANGELOG.md` has dated M21 section with all Unreleased entries promoted + ZZ entry.
5. **AC-5:** Top-of-file `[Unreleased]` section in CHANGELOG retained (non-M21 entries preserved).
6. **AC-6:** Root `README.md` M21 row flipped + `## Next` updated.
7. **AC-7:** Status surfaces flip together: ZZ spec Status; M21 README task-pool ZZ row; M21 README exit-criteria checkboxes.
8. **AC-8:** No runtime code change in `ai_workflows/` during ZZ.
9. **AC-9:** If T18/T19 deferred: `nice_to_have.md` entries added with trigger condition.
10. **AC-10:** `uv run pytest` green; `uv run lint-imports` green; `uv run ruff check` green.

## Smoke test (Auditor runs)

```bash
# Status surfaces
grep -q "✅ Complete" design_docs/phases/milestone_21_autonomy_loop_continuation/README.md && echo "milestone README status OK"
grep -qE "M21.*complete|Complete.*M21" design_docs/roadmap.md && echo "roadmap M21 OK"
grep -q "M21 Autonomy Loop Continuation" CHANGELOG.md && echo "CHANGELOG dated section OK"

# Zero ai_workflows/ diff in ZZ commit
test "$(git log -1 --name-only --pretty=format: HEAD | grep -c '^ai_workflows/')" -eq 0 && echo "no ai_workflows/ diff"

# Gates green
uv run lint-imports >/dev/null && echo "lint-imports green"
uv run ruff check >/dev/null && echo "ruff green"
uv run pytest -q
```

## Out of scope

- **Any runtime code change.** ZZ is doc + CHANGELOG + README + roadmap. Any runtime finding forks to a new task.
- **Implementing T18/T19** inside ZZ. If deferred, they go to M22; ZZ only records the deferral.
- **New tasks** beyond the M22 propagation surface.
- **Adopting `nice_to_have.md` items** beyond the T18/T19 deferral entry if applicable.

## Dependencies

- **T17 Done or Deferred** — Phase G must reach a decision point before ZZ.
- **T18/T19 Done or Deferred** — explicit disposition required.

## Carry-over from prior milestones

- **M20 T07 dynamic model dispatch** — carries if still BLOCKED on T06 GO/NO-GO.
- **M20 T06/T23 operator-resume** — passes through; ZZ records status.

## Carry-over from prior audits

*None at draft time.*

## Carry-over from task analysis

- [x] **TA-LOW-04 — nice_to_have.md slot pre-allocation for T18/T19 deferral** (severity: LOW, source: task_analysis.md round 20) — N/A: T18 + T19 shipped in M21 (operator authorized). No nice_to_have.md entry needed.
      ZZ AC-9 + T18/T19 defer-to-M22 condition both reference adding entries to `design_docs/nice_to_have.md`. As of 2026-04-29 (round-20 analysis), the next free slot is `## 25.`
      **Recommendation:** If T18/T19 defer to M22, ZZ Builder targets `nice_to_have.md` slot `## 25. Parallel-Builders foundation (T18/T19 from M21)`. Re-verify the slot number at ZZ time (another task may have claimed it first).
