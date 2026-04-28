# Task ZZ — Milestone Close-out

**Status:** 📝 Planned.

**Grounding:** [milestone README](README.md) · [task_06](task_06_shadow_audit_study.md) (DEFER verdict; harness shipped) · [task_07](task_07_dynamic_model_dispatch.md) (blocked on T06 GO/NO-GO; spec exists per /clean-tasks output) · [task_08](task_08_gate_output_integrity.md) · [task_09](task_09_task_integrity_safeguards.md) · [task_20](task_20_carry_over_checkbox_cargo_cult_extended.md) · [task_21](task_21_adaptive_thinking_migration.md) · [task_22](task_22_per_cycle_telemetry.md) · [task_23](task_23_cache_breakpoint_discipline.md) · [task_27](task_27_tool_result_clearing.md) · [task_28](task_28_evaluate_server_side_compaction.md) (DEFER verdict; analysis-only) · [M14 T02](../milestone_14_mcp_http/task_02_milestone_closeout.md) + [M11 T02](../milestone_11_gate_review/task_02_milestone_closeout.md) (close-out patterns to mirror) · [CLAUDE.md](../../../CLAUDE.md) §Status-surface discipline · `architecture.md` §9 KDRs (drift-check anchors).

## What to Build

Close M20. Phases A-D have shipped:

- **Phase A — Compaction quartet + server-side primitive evaluation:** T01 ✅, T02 ✅, T03 ✅, T04 ✅, T28 ✅ (DEFER verdict — `compact_20260112` not reachable through Claude Code Task tool; analysis at `design_docs/analysis/server_side_compaction_evaluation.md`; `nice_to_have.md §24`).
- **Phase B — Parallel terminal gate:** T05 ✅.
- **Phase C — Model-tier rationalization:** T21 ✅, T22 ✅, T06 ✅ (DEFER verdict — methodology designed and harness shipped; full 30-cell empirical study deferred to operator-resume per L5-equivalent bail-out; `runs/study_t06/` structurally present with A1 methodology stub). T07 remains 📝 Candidate, **blocked on T06 producing a non-DEFER verdict**; T07 unblocks when the operator runs `python scripts/orchestration/run_t06_study.py full-study` outside autopilot.
- **Phase D — Defense-in-depth integrity:** T08 ✅, T09 ✅, T20 ✅, T23 ✅ (AC-7 empirical validation deferred to operator-resume per parallel L5-equivalent bail-out; `runs/cache_verification/methodology.md`), T27 ✅ (Path A explicitly rejected per audit H6 — Claude Code Task tool agent frontmatter does not surface `context_management.edits`; client-side simulation only).

ZZ is the close-out doc that flips status surfaces, promotes the CHANGELOG entries, and absorbs the cross-task carry-over (the M21 agent-prompt-hardening absorbing track) into a propagation record. **No runtime code change.** **No new milestone tasks generated** beyond the propagation surface T07 already names.

The single substantive carry-over absorption: the **M21 agent-prompt-hardening track** is the load-bearing forward-deferral. T06's issue file Carry-over §C4 enumerates 10 LOW findings (LOW-1 through LOW-8 + LOW-10 + LOW-11; LOW-9 was partially resolved at T06 cycle 5 — the load-bearing call-site contract bug fixed and pinned by `test_single_cell_bail_manifest_shape`; cosmetic residue folded into C1 operator-resume) for the absorbing M21 task spec. Subsequent tasks (T08 / T09 / T20 / T23 / T27) added at least 6 more LOW recurrences (Builder return-schema non-conformance reached 16+ occurrences across the 6-task autopilot run, well-documented across each task's issue file; Auditor cycle-summary write refusal recurred per loop-controller observation in `runs/m20_t<NN>/cycle_<N>/agent_auditor_raw_return.txt` at multiple cycle boundaries — exact count to be tallied by `/clean-tasks m21` when the absorbing-task spec is generated; Builder pre-stamping "Auditor verdict" / "Locked decision" patterns recurred). ZZ records this as a concrete propagation surface that `/clean-tasks m21` must absorb when the M21 hardening task spec is generated.

T07 (dynamic model dispatch) does **not** ship at M20. T07's spec exists but is gated on T06 producing a non-DEFER verdict (study data populated, GO/NO-GO calibrated). Until the operator runs the harness outside autopilot, T07 stays open; it carries over to M21 only when the operator confirms the study verdict and unblocks the dispatch defaults.

## Deliverables

### 1. Milestone README ([README.md](README.md))

- Flip the top-of-file **Status** from `📝 Drafting (revised 2026-04-27 …)` to `✅ Complete (<YYYY-MM-DD>)`.
- Append an **Outcome** section summarising:
  - **T01-T05** — return-value schema (T01); input prune (T02); in-task cycle compaction (T03); cross-task iteration compaction (T04); parallel terminal gate (T05). All shipped Phase A + B; structural foundation for the autonomy loop's compaction substrate. Telemetry records under `runs/<task>/cycle_<N>/<agent>.usage.json`.
  - **T06** — Shadow-Audit empirical study. **DEFER verdict.** Methodology designed; data collection deferred to operator-resume. Harness `scripts/orchestration/run_t06_study.py` (791 lines) reproducibly drives the 6-cell × 5-task matrix; bail-out check fires after first A1 task pair (spec L5 wording). Hermetic harness tests (7) cover projection arithmetic, bail-manifest aggregate shape, dry-run end-to-end, single-cell CLI bail contract. Per-cell measurements deferred to `runs/study_t06/<cell>-<task>/` populated by operator outside autopilot.
  - **T07** — dynamic model dispatch. **📝 Planned (gated on T06's GO verdict, operator-resume)** — does not ship at M20; carries to M21 once T06 produces non-DEFER. Status surfaces flip together: T07 spec line stays `📝 Planned. Gated on T06's GO verdict.` (canonical wording); M20 README task-pool row updated from `📝 Candidate (gated on T06)` to `📝 Planned (gated on T06)` to match the spec; ZZ Outcome here uses the same canonical phrasing.
  - **T08-T09** — gate-output integrity (T08); task-integrity safeguards (T09). Defense-in-depth pre-AUTO-CLEAN ceremony shipped. T08's `_common/gate_parse_patterns.md` is the single source of truth for gate-footer regex; T09's `_common/integrity_checks.md` is the canonical reference for the three pre-stamp checks.
  - **T20** — Auditor anti-cargo-cult inspections. M12-T01 carry-over patch ported from template; Phase 4 extended with cycle-N-vs-(N-1) overlap detection + rubber-stamp detection. `scripts/orchestration/cargo_cult_detector.py` + 50/51 boundary tests.
  - **T21-T22** — adaptive-thinking migration (T21) eliminated every `thinking: max` literal; per-cycle telemetry (T22) records `cache_read_input_tokens` / `cache_creation_input_tokens` / `input_tokens` / `output_tokens` per agent invocation under `runs/<task>/cycle_<N>/<agent>.usage.json`.
  - **T23** — cache-breakpoint discipline. **AC-7 empirical validation deferred** (L5-equivalent bail-out parallel to T06's). Stable-prefix-discipline section added to `_common/spawn_prompt_template.md`; 2-call verification harness `scripts/orchestration/cache_verify.py` with hermetic tests; methodology stub at `runs/cache_verification/methodology.md` for operator-resume.
  - **T27** — Auditor input-volume rotation trigger (client-side simulation of `clear_tool_uses_20250919`). **Path A explicitly rejected per audit H6** — Claude Code Task tool agent frontmatter does not surface `context_management.edits` (verified across all 9 existing agents — frontmatter accepts only `name`/`description`/`tools`/`model`). Threshold tunable via `AIW_AUDITOR_ROTATION_THRESHOLD` (60K default).
  - **T28** — server-side compaction evaluation. **DEFER verdict** (2026-04-28). Surface mismatch — Claude Code Task tool does not expose `context_management.edits`; analysis at `design_docs/analysis/server_side_compaction_evaluation.md`; recorded under `nice_to_have.md §24` for re-open if Anthropic / Claude Code surface evolves.
  - **Manual verification** (autopilot baseline): the 6-task autopilot run on 2026-04-28 from pre-flight (`AIW_AUTONOMY_SANDBOX=1`, branch `workflow_optimization`) through the close-out ZZ commit. Total cycles: 15+ across 6 tasks. Total agent invocations: ~70+. Cumulative tokens: ~3.5M (per `runs/autopilot-20260428T153748Z-iter*-shipped.md` aggregates).
  - **Green-gate snapshot:** `uv run pytest` (1293+ passed; 1 pre-existing environmental failure on `test_design_docs_absence_on_main` per LOW-3 — out of T20 close-out scope; tracked as M21 absorbing-task carry-over), `uv run lint-imports` (5 contracts kept), `uv run ruff check` (all clean).
- Keep the **Carry-over from prior milestones** section intact.
- Fill in **Propagation status** — name the M21 hardening track, the T07 unblock condition, the T06 + T23 operator-resume action, the T28 nice_to_have entry.

### 2. Roadmap ([roadmap.md](../../roadmap.md))

- **Add** an M20 row to the milestone table in `roadmap.md` (insert after M19 at line ~31). Status: `✅ complete (<YYYY-MM-DD>)`. (No prior M20 row existed in roadmap.md as of round-1 analysis — ZZ adds, not flips.)
- Append a one-line summary in the M20 narrative section (after the existing M15/M16/M19 narratives at line ~49): shipped 11 of 13 candidate tasks (T01-T06, T08, T09, T20, T21, T22, T23, T27, T28). T07 deferred to M21 (blocked on T06 GO/NO-GO operator-resume). T28 verdict DEFER (surface mismatch). T06 verdict DEFER (operator-resume).

### 3. CHANGELOG ([CHANGELOG.md](../../../CHANGELOG.md))

- Promote every M20 `[Unreleased]` entry into a new dated section `## [M20 Autonomy Loop Optimization] - <YYYY-MM-DD>`.
- Keep the top-of-file `[Unreleased]` section intact.
- Add a ZZ close-out entry at the top of the new dated section. Record:
  - The 11 shipped tasks (cite each commit sha: T06 d76f93f, T08 0dd91f4, T09 8e572dc, T20 851274f, T21 628b975, T22 426c7fb, T23 b39efbf, T27 a266996, T28 21c37ba, T04 7caecbd, T05 bd27945, plus T01-T03 from earlier in the autopilot run).
  - The DEFER verdicts on T06 + T23 + T28 with their respective rationales.
  - The T07 BLOCKED status with the unblock condition.
  - The M21 hardening track absorption surface.
  - The autopilot baseline manual smoke (cumulative-tokens + cycle-count + commit-sha trail per `runs/autopilot-20260428T153748Z-iter*-shipped.md`).
  - The 5-contract `lint-imports` snapshot confirming no new layer contracts landed at M20 (M20 is orchestration-infrastructure; runtime layer rule unchanged).

### 4. Root [README.md](../../../README.md)

- **Add** an M20 row to the milestone status table (insert after M19 at line ~28). State: `Complete (<YYYY-MM-DD>)`. (No prior M20 row existed in root README.md as of round-1 analysis — ZZ adds, not flips.)
- Trim the post-M19 `## Next` narrative (line ~144) to reflect M21 (Autonomy Loop Continuation) as the next planned milestone. M20 exits the planned list.

### 5. Architecture.md ([architecture.md](../../architecture.md))

**No KDR addition at M20** (per the M20 README §Non-goals: "No new KDRs locked at M20"). One-line edit only if a §4 sub-bullet or §6 dep-table row needs to acknowledge the M20 orchestration-infrastructure surface (e.g., `scripts/orchestration/` family — `telemetry.py`, `run_t06_study.py`, `cache_verify.py`, `cargo_cult_detector.py`, `auditor_rotation.py`). If no edit is needed, ZZ records "no architecture.md change" in the audit log; do not invent an architectural surface where none belongs.

### 6. M21 propagation surface

The M21 agent-prompt-hardening absorbing task does NOT yet exist. M21 README at `design_docs/phases/milestone_21_autonomy_loop_continuation/README.md` exists (split from M20 on 2026-04-27 per audit recommendation M3). `/clean-tasks m21` is unblocked once ZZ closes M20 — at that point the operator runs `/clean-tasks m21` to generate the absorbing-task spec. ZZ records the propagation surface for `/clean-tasks m21` to pick up:

- All 17+ LOW findings from M20 T06 issue file Carry-over §C4 (Builder return-schema non-conformance, Auditor cycle-summary write refusal, Builder pre-stamp "Auditor verdict" pattern, Builder pre-stamp "Locked decision" pattern, sr-dev tools-list missing `Write`, etc.).
- The empirical recurrence count (16+ Builder schema violations across 6 tasks in 6 iterations) as the smoking-gun signal for M21 task priority HIGH.
- The framing reframe from cycle 5 (LOW-11 reframe): "harness write-policy + orchestrator-owned post-spawn summary write" rather than just agent-prompt discipline.

M21 README is in place; `/clean-tasks m21` is unblocked once ZZ closes M20.

## Acceptance Criteria

1. **AC-1:** Milestone README Status flipped to `✅ Complete (<YYYY-MM-DD>)`; Outcome section covers T01-T05 + T06 (DEFER) + T07 (BLOCKED) + T08 + T09 + T20 + T21 + T22 + T23 (AC-7 deferred) + T27 (Path A rejected) + T28 (DEFER) with the manual-verification autopilot-baseline summary.
2. **AC-2:** Milestone README Propagation status section names: M21 hardening track absorption surface, T07 unblock condition, T06 + T23 operator-resume action, T28 nice_to_have entry.
3. **AC-3:** `roadmap.md` gains an M20 row inserted in ordinal position (after M19) reflecting `✅ complete (<YYYY-MM-DD>)` with the one-line narrative summary appended to the post-M19 narrative section. **Note: no prior M20 row exists in roadmap.md as of round-1 analysis — ZZ adds, not flips.**
4. **AC-4:** `CHANGELOG.md` has a dated `## [M20 Autonomy Loop Optimization] - <YYYY-MM-DD>` section with all M20 `[Unreleased]` entries promoted + ZZ close-out entry at the top citing every shipped task commit sha + DEFER verdicts + T07 BLOCKED + M21 hardening absorption surface + autopilot baseline manual smoke.
5. **AC-5:** Top-of-file `[Unreleased]` section in CHANGELOG retained (any non-M20 unreleased entries preserved; M20 entries promoted out).
6. **AC-6:** Root `README.md` milestone status table gains an M20 row inserted after M19 (line ~28) with state `Complete (<YYYY-MM-DD>)`; post-M19 `## Next` narrative (line ~144) trimmed to reflect M21 as next planned milestone. **Note: no prior M20 row exists — ZZ adds, not flips.**
7. **AC-7:** Status surfaces flip together (CLAUDE.md non-negotiable): per-task spec ZZ Status line; milestone README task-pool ZZ row; milestone README §Exit-criteria checkboxes the close-out satisfies; tasks/README.md row if M20 has one (verify; M20 does NOT have a tasks/README.md per existing absence — record this in the audit log).
8. **AC-8:** No runtime code change in `ai_workflows/` during ZZ (ZZ is doc-only close-out; if any finding requires runtime code, it forks to a new task — none anticipated).
9. **AC-9:** Manual autopilot-baseline smoke recorded in CHANGELOG ZZ entry: cite `runs/autopilot-20260428T153748Z-iter1-shipped.md` through `runs/autopilot-20260428T153748Z-iter6-shipped.md` (6 iterations) plus the 6 commit shas (T06 d76f93f, T08 0dd91f4, T09 8e572dc, T20 851274f, T23 b39efbf, T27 a266996) and the cumulative-token estimate (~3.5M).
10. **AC-10:** Green-gate snapshot recorded in CHANGELOG ZZ entry: `uv run pytest` count, `uv run lint-imports` 5-contract status, `uv run ruff check` clean. Pre-existing `test_main_branch_shape::test_design_docs_absence_on_main` environmental fail on `workflow_optimization` is the known LOW-3, expected (out of ZZ scope).
11. **AC-11:** `uv run pytest` green (modulo the LOW-3 environmental fail).
12. **AC-12:** `uv run lint-imports` reports the same contract count as before M20 (no new layer contracts at M20 — orchestration infrastructure does not touch the package layer rule).
13. **AC-13:** `uv run ruff check` clean.
14. **AC-14:** Zero `ai_workflows/` package-code diff in the ZZ commit (ZZ is doc/CHANGELOG/README/roadmap only). The audit log records `git diff --name-only HEAD~1..HEAD -- ai_workflows/` returns empty.
15. **AC-15:** M21 propagation surface recorded in this issue file (or in the milestone README's Propagation status section): name the absorbing-task scope (Builder return-schema discipline + Auditor cycle-summary emission + Builder pre-stamp pattern catches + sr-dev `Write`-tool gap), name the empirical-recurrence count (16+ across 6 tasks), name the operator-resume actions for T06 + T23 + T07.
16. **AC-16 (T07 status-surface coordination):** All T07 status surfaces flip together in the ZZ Builder cycle. Specifically: T07 spec status line stays `📝 Planned. Gated on T06's GO verdict.` (canonical — already correct, no edit); M20 README task-pool table row for T07 updated from `📝 Candidate (gated on T06)` to `📝 Planned (gated on T06)` to match the spec wording; ZZ Outcome's T07 line uses the same canonical phrasing (already correct after this round-1 fix). Per CLAUDE.md non-negotiable status-surface discipline, all three must land in the same Builder cycle.

## Smoke test (Auditor runs)

```bash
# Verify status surfaces flipped
grep -q "✅ Complete" design_docs/phases/milestone_20_autonomy_loop_optimization/README.md && echo "milestone README status OK"
grep -q "M20.*complete\|Complete (.*M20" design_docs/roadmap.md && echo "roadmap status OK"
grep -q "M20 Autonomy Loop Optimization" CHANGELOG.md && echo "changelog dated section OK"

# Verify ZZ close-out entry in CHANGELOG cites all 6 shipped task commits
grep -qE "d76f93f|0dd91f4|8e572dc|851274f|b39efbf|a266996" CHANGELOG.md && echo "commit shas cited"

# Verify zero ai_workflows/ diff in the ZZ commit
test "$(git log -1 --name-only --pretty=format: HEAD | grep -c '^ai_workflows/')" -eq 0 && echo "no ai_workflows/ diff"

# Verify gates green (modulo LOW-3 environmental)
uv run lint-imports >/dev/null && echo "lint-imports green"
uv run ruff check >/dev/null && echo "ruff green"
```

## Out of scope (explicit)

- **Any runtime code change in `ai_workflows/`.** ZZ is doc + CHANGELOG + README + roadmap. If a finding surfaced in close-out requires runtime code, fork to a new task (none anticipated — every shipped M20 task already absorbed its findings at audit time).
- **New tasks** beyond the M21 propagation surface ZZ records. The M21 absorbing task is generated by `/clean-tasks m21` when the operator runs that command; ZZ does not generate it.
- **Promoting any DEFER verdict to GO/NO-GO.** T06, T23, T28 stay DEFER. The operator resumes outside autopilot per their respective methodology stubs.
- **Implementing T07.** T07 stays BLOCKED until T06 produces non-DEFER. ZZ does not unblock T07.
- **Adopting items from `nice_to_have.md`.** T28's nice_to_have §24 entry stays deferred. ZZ does not promote it.
- **Authentication, TLS, rate-limiting** — none of these are M20 surfaces; remain trigger-gated per prior milestones (M14's Propagation status).
- **Cross-milestone cargo-cult detection** — out of scope per T20's spec (already-deferred to a future M21+ task; not a ZZ concern).

## Dependencies

- T01 ✅, T02 ✅, T03 ✅, T04 ✅ (Phase A compaction quartet shipped).
- T05 ✅ (Phase B parallel terminal gate shipped).
- T06 ✅ (DEFER verdict shipped — close-out absorbs).
- T08 ✅, T09 ✅, T20 ✅, T23 ✅ (AC-7 deferred), T27 ✅ (Path A rejected) (Phase D safeguards shipped).
- T21 ✅, T22 ✅ (Phase C foundational shipped).
- T28 ✅ (DEFER verdict shipped — close-out absorbs).
- T07 — blocked on T06 GO/NO-GO; close-out records the unblock condition; does not depend on T07 shipping.

## Carry-over from prior milestones

*None.*

## Carry-over from task analysis

(populated by `/clean-tasks m20`)

## Carry-over from prior audits

(populated by `/clean-implement` audit cycles)

## Propagation status

Filled in at audit time. Anticipated:

- **M21 agent-prompt-hardening absorbing task** — not yet specced. M21 README at `design_docs/phases/milestone_21_autonomy_loop_continuation/README.md` exists; `/clean-tasks m21` is unblocked once ZZ closes M20. Surface enumerated in T06's issue file Carry-over §C4 + every subsequent M20 task's issue file. Empirical recurrence: 16+ Builder return-schema violations across 6 tasks in 6 autopilot iterations. Trigger: operator runs `/clean-tasks m21` once M20 close-out lands.
- **T07 dynamic model dispatch** — carries to M21. Unblocks when operator runs `python scripts/orchestration/run_t06_study.py full-study` outside autopilot AND T06 verdict flips from DEFER to GO/NO-GO.
- **T06 30-cell empirical study** — operator-resume per `runs/study_t06/A1-m12_t01/methodology_note.json`. Outside autopilot.
- **T23 cache-verification empirical** — operator-resume per `runs/cache_verification/methodology.md`. Outside autopilot.
- **T28 nice_to_have §24** — re-open trigger documented; stays deferred.
- **No new milestone generated by ZZ.** M21 (Autonomy Loop Continuation) is the next load-bearing milestone after M20 closes; M21's task-out happens via `/clean-tasks m21`, not via ZZ.
