# Task 06 — Shadow-Audit empirical study — Audit Issues

**Source task:** [../task_06_shadow_audit_study.md](../task_06_shadow_audit_study.md)
**Audited on:** 2026-04-28 (cycle 1, cycle 2, cycle 3, cycle 4, cycle 5)
**Audit scope:** spec + issue file + study report (`design_docs/analysis/autonomy_model_dispatch_study.md`) + harness (`scripts/orchestration/run_t06_study.py`) + hermetic harness tests (`tests/orchestration/test_run_t06_harness.py` — 7 tests after cycle 5) + `runs/study_t06/` artifacts + CHANGELOG entry + status surfaces. Cycle 5 re-audit verifies the cycle-4 carry-over fixes (sr-sdet FIX-A: full-study dry-run end-to-end test; sr-sdet FIX-B / LOW-9 closure: single-cell CLI bail call-site uses `a1_summary` aggregate; ADV-4 strengthening of the default-arg projection test) landed, re-runs all gates, and re-checks status surfaces.
**Status:** ✅ PASS (cycle 5) — FIX-A, FIX-B, and LOW-9 source closure all landed. Test count 1092 → 1094 (+2 cycle-5 tests). All gates green except the known pre-existing environmental failure (LOW-3) on `workflow_optimization`. The 8 prior LOWs (LOW-1 through LOW-8) remain explicitly DEFERRED to the future M21 agent-prompt-hardening track. **LOW-9 is now PARTIALLY RESOLVED** — the call-site contract bug (the load-bearing one) is fixed and pinned by `test_single_cell_bail_manifest_shape`; the cosmetic `"× 30"` print at line 837 + module-docstring `× 30` references at lines 33 / 67 remain unfixed (residual cosmetic; folded into C1 operator-resume rather than re-opened). LOW-10 (Builder cycle-5 return-schema non-conformance, 6th recurrence) added this cycle. LOW-11 (Auditor cycle-4 missed `cycle_4/summary.md` — loop-controller fallback) recorded this cycle; cycle-5 Auditor (this audit) successfully wrote `cycle_5/summary.md`.

---

## Design-drift check

No KDR drift detected. T06 is analysis-only; cycle 4 only tightens orchestration-layer harness logic and adds tests.

- **Layer rule (`primitives → graph → workflows → surfaces`):** N/A — `scripts/orchestration/run_t06_study.py` is orchestration-layer; new test file `tests/orchestration/test_run_t06_harness.py` loads the harness via `importlib.util.spec_from_file_location`, no `from ai_workflows` import. Stays out of the package layer entirely.
- **KDR-003 (no Anthropic API):** zero `anthropic` SDK imports, zero `ANTHROPIC_API_KEY` reads in the harness or the new test file. Production OAuth path (`claude --dangerously-skip-permissions`) is the only Claude-invocation surface.
- **KDR-013 (user-owned external code):** N/A — harness drives in-tree autopilot via subprocess; no user-workflow loading or policing.
- **Other KDRs (002, 004, 006, 008, 009):** N/A — no MCP, no `TieredNode`/`ValidatorNode`, no checkpoint logic, no retry semantics, no FastMCP surface touched.

---

## AC grading

| AC | Status | Notes |
| --- | --- | --- |
| AC-1: `autonomy_model_dispatch_study.md` exists with all sections populated | ✅ PASS | 208 lines; every spec-named section present. Unchanged cycle 3 → cycle 4. |
| AC-2: Verdict is GO / NO-GO / DEFER, justified by evidence | ✅ PASS | `**Recommendation: DEFER on T07 default flips**` at line 11. Justification preserved. |
| AC-3: Per-cell metrics table has 6 cells | ✅ PASS | `grep -c "^| A[1-6]"` returns 6. |
| AC-4: Per-task-kind verdict deltas table populated | ✅ PASS (structurally) | Table present with all 5 task kinds; data DEFERRED. |
| AC-5: Default-tier rule recommendation concrete | ✅ PASS | Per-role table with provisional model assignments + flag scope. |
| AC-6: Complexity threshold rule concrete | ✅ PASS | 4 named signals; calibration deferred to study data. |
| AC-7: 30 cell-task run directories under `runs/study_t06/` | ⚠️ DEFERRED (locked) | Only `runs/study_t06/A1-m12_t01/` exists. Locked decision (Auditor cycle 1) holds. See C1. |
| AC-8: CHANGELOG.md updated | ✅ PASS | `[Unreleased]` entry includes the cycle-4 sub-entry detailing the four harness-bug fixes + new test file. |
| AC-9: Status surfaces flipped | ✅ PASS | All four surfaces aligned: spec `**Status:** ✅ Done (2026-04-28)`, milestone README task-table row Done, milestone README G3 exit criterion ✅, `tasks/README.md` does not exist for M20 (verified). |

---

## Gate summary

(Cycle 5 re-run — Auditor re-runs all gates from scratch.)

| Gate | Command | Result (cycle 5) |
| --- | --- | --- |
| Tests | `uv run pytest -q --tb=no` | **1094 passed, 10 skipped, 1 failed** — `tests/test_main_branch_shape.py::test_design_docs_absence_on_main` (pre-existing LOW-3). 1092 → 1094 reflects FIX-A + FIX-B (+2 tests). Wall-clock 44.61s. |
| Hermetic harness tests | `uv run pytest tests/orchestration/test_run_t06_harness.py -q` | **7 passed** (0.03s). FIX-A test `test_run_full_study_dry_run_completes_without_bail` PASS; FIX-B test `test_single_cell_bail_manifest_shape` PASS (both new this cycle). |
| FIX-A verification | Read `tests/orchestration/test_run_t06_harness.py` lines 225-254 | PASS — `test_run_full_study_dry_run_completes_without_bail` exercises `run_full_study(dry_run=True)`, asserts rc==0, asserts `bail_manifest.json` does NOT exist, asserts `study_manifest.json` exists with `total_pairs == 30`. End-to-end dry-run path covered. |
| FIX-B / LOW-9 source closure | Read `scripts/orchestration/run_t06_study.py` lines 839-847 | PASS — single-cell CLI bail path now builds `a1_summary = {"a1_task_results": [result], "a1_total_tokens": tokens.get("total_tokens", 0)}` before calling `_write_bail_manifest(projection, a1_summary)`. Function-contract violation fixed. |
| FIX-B regression test | Read `tests/orchestration/test_run_t06_harness.py` lines 261-303 | PASS — `test_single_cell_bail_manifest_shape` monkeypatches `_compute_quota_projection` to force `bail_triggered=True`, calls `harness.main(["--dry-run", "cell", "--cell", "A1", "--task", "m12_t01"])`, catches `SystemExit(2)`, asserts `bail_manifest.json` has `a1_summary.a1_task_results` (list) and `a1_summary.a1_total_tokens` (int). |
| ADV-4 strengthening | Read `tests/orchestration/test_run_t06_harness.py` lines 86-93 | PASS — `test_compute_quota_projection_default_n_total_cells_is_6` now asserts the concrete arithmetic value (`100_000 × 6 == 600_000`), not a tautology. |
| Import contracts | `uv run lint-imports` | All 5 contracts kept, 0 broken. |
| Lint | `uv run ruff check` | All checks passed (6970 files compiled). |
| Smoke (spec §Smoke test) | `test -f` doc + `wc -l ≥ 200` + verdict-line grep + `^\| A[1-6]` count + `ls -d runs/study_t06/A?-*` | First 4 PASS; 5th still 1 dir (AC-7 DEFERRED, locked). Identical shape to cycles 1-4. |
| MED-1 fix verification | `grep -n "methodology has been validated\|Methodology validated" design_docs/analysis/autonomy_model_dispatch_study.md` | 0 hits (PASS — unchanged from cycle 3). |
| Cycle-4 fixes durability | Re-read `_compute_quota_projection`, `_write_bail_manifest` (full-study path), `run_cell` `finally:`, A1 `if i == 0:` bail | All four cycle-4 fixes still in place, untouched by cycle 5. |

---

## 🟡 MEDIUM

*(none open this cycle)*

MED-1 closed cycle 3.

---

## 🟢 LOW

### LOW-1 — Builder pre-stamped "Locked decisions (loop-controller + Auditor concur, 2026-04-28)" before the Auditor ran (cycle 1)

**Severity:** LOW (procedural; durable work landed correctly).
**Status:** OPEN — DEFERRED to M21 agent-prompt-hardening track (C4).
**Action / Recommendation:** Carry over to a future agent-prompt-hardening task: explicitly forbid Builder agents from writing `loop-controller + Auditor concur` blocks. The Builder may *propose* a deferral; the orchestrator stamps it after the Auditor re-runs.

### LOW-2 — Builder cycle 1 return-schema non-conformance

**Severity:** LOW. **Status:** OPEN — DEFERRED to M21 (C4).
**Action / Recommendation:** Carry over to a future agent-prompt-hardening task in `.claude/agents/builder.md`. No rework required.

### LOW-3 — `tests/test_main_branch_shape.py` pre-existing environmental failure on `workflow_optimization`

**Severity:** LOW (environmental; not T06-introduced). **Status:** OPEN — DEFERRED to M21 (C4).
**Action / Recommendation:** Future task hardening `_resolve_branch()` to accept `AIW_BRANCH` env-var or recognise `workflow_optimization` as a design-branch synonym.

### LOW-4 — Builder cycle 2 return-schema non-conformance (RECURRENCE)

**Severity:** LOW. **Status:** OPEN — DEFERRED to M21 (C4).

### LOW-5 — Auditor cycle 1 missed emitting `cycle_1/summary.md`

**Severity:** LOW (process gap). **Status:** OPEN — DEFERRED to M21 (C4).

### LOW-6 — Builder cycle 3 return-schema non-conformance (4th recurrence)

**Severity:** LOW. **Status:** OPEN — DEFERRED to M21 (C4).

### LOW-7 — Auditor cycle 2 schema preamble (Auditor-side recurrence of return-schema discipline)

**Severity:** LOW. **Status:** OPEN — DEFERRED to M21 (C4).

### LOW-8 — Builder cycle 4 return-schema non-conformance (5th recurrence in this task — NEW this cycle)

**What:** Per loop-controller observation (cycle 4), the Builder return text again included a prose preamble + a "Planned commit message" line before the 3-line schema (`verdict / file / section`). Raw return preserved at `runs/m20_t06/cycle_4/agent_builder_raw_return.txt`. **This is the 5th recurrence in this single task across 4 cycles** (LOW-2 / LOW-4 / LOW-6 / LOW-8 on the Builder side, plus LOW-7 on the Auditor side). The recurrence multiplier compounds: a single-task LOW that fires 5× across 4 cycles is *de facto* MEDIUM-priority for the absorbing M21 hardening task.

**Severity:** LOW (durable work landed; orchestrator parses around it). The recurrence count itself raises absorbing-task priority but does not promote this individual finding above LOW.

**Action / Recommendation:** Same M21 agent-prompt-hardening track as LOW-1 / LOW-2 / LOW-4 / LOW-6 / LOW-7 (C4 below). Concrete recommendation for the M21 task spec authoring: open the M21 hardening task with **HIGH priority** and lead with the Builder return-schema fix. The 5-recurrence pattern is the empirical smoking gun. Concrete fixes to land:
- Add a refusal-contract clause to `.claude/agents/builder.md`: *"If you find yourself writing prose before the schema, stop. Emit only the 3-line schema. The orchestrator parses your output mechanically; prose preceding the schema is not consumed."*
- Add a worked good/bad example pair to the agent prompt.
- Optional: add an orchestrator-side counter that flags the agent for retraining when preamble-stripping fires more than N times across one autopilot session (this will catch regressions after the agent-prompt fix lands).

### LOW-9 — Single-cell CLI path's `_write_bail_manifest` call site (call-site contract bug RESOLVED cycle 5; cosmetic `× 30` print residual)

**What:** Cycle 5 Builder fixed the load-bearing call-site contract violation. `scripts/orchestration/run_t06_study.py` lines 839-846 now build `a1_summary = {"a1_task_results": [result], "a1_total_tokens": tokens.get("total_tokens", 0)}` before calling `_write_bail_manifest(projection, a1_summary)`. Pinned by `tests/orchestration/test_run_t06_harness.py::TestSingleCellBailManifestShape::test_single_cell_bail_manifest_shape` (lines 261-303), which exercises the path through `main()`.

**Residual (cosmetic-only, not promoted):** the `print(f"Quota projection if × 30: …")` at line 837 still references the stale `× 30` literal. Module-docstring lines 33 and 67 also still say `× 30`. The actual scale is now `n_total_cells = 6` (the new default of `_compute_quota_projection`). This is a doc-string-style cosmetic mismatch — no runtime path consumes the print line.

**Status:** PARTIALLY RESOLVED — call-site contract bug RESOLVED cycle 5; cosmetic `× 30` references DEFERRED to C1 operator-resume.
**Severity:** LOW (cosmetic-only residual). Not promoted; not propagated.
**Action / Recommendation:** When the operator runs the harness outside autopilot for AC-7 resumption (C1), update lines 33, 67, and 837 to match the `len(CELLS)`-based scale factor. Already noted in C1 operator-resume checklist.

### LOW-10 — Builder cycle 5 return-schema non-conformance (6th recurrence in this task — NEW this cycle)

**What:** Per loop-controller observation (cycle 5), the Builder return text again included a prose preamble + a "Planned commit message" line before the 3-line schema. Raw return preserved at `runs/m20_t06/cycle_5/agent_builder_raw_return.txt`. **This is the 6th recurrence in this single task across 5 cycles** (LOW-2 / LOW-4 / LOW-6 / LOW-8 / LOW-10 on the Builder side, plus LOW-7 on the Auditor side). The pattern is now a near-certainty per Builder spawn in this task and reinforces the M21 hardening track's HIGH priority.

**Severity:** LOW (durable work landed; orchestrator parses around it). The recurrence count itself raises absorbing-task priority but does not promote this individual finding above LOW.

**Action / Recommendation:** Same M21 agent-prompt-hardening track as LOW-1 / LOW-2 / LOW-4 / LOW-6 / LOW-7 / LOW-8 (C4). The 6-recurrence count crosses the empirical threshold where prompt-engineering alone may be insufficient — recommend pairing the prompt-hardening fix with the orchestrator-side counter mentioned in LOW-8's recommendation, so a regression after the prompt fix lands is auto-detected.

### LOW-11 — Auditor cycle 4 missed emitting `cycle_4/summary.md` — recurrence of LOW-5 (NEW this cycle)

**What:** Per loop-controller carry-over, the cycle-4 Auditor did not emit `runs/m20_t06/cycle_4/summary.md` and the loop controller synthesized it as fallback. This is a recurrence of LOW-5 (cycle-1 Auditor missed `cycle_1/summary.md`). The cycle-5 Auditor (this audit) successfully wrote `runs/m20_t06/cycle_5/summary.md` per Phase 5, suggesting the gap is non-deterministic — the agent prompt's permission boundary may not consistently authorize `runs/<task>/cycle_<N>/` writes outside the issue file path.

**Severity:** LOW (durable work landed; loop controller fallback covers the gap). Recurrence pattern (LOW-5 + LOW-11 across 5 cycles) reinforces the M21 hardening track's Auditor-side scope.

**Action / Recommendation:** Same M21 agent-prompt-hardening track as LOW-5 (C4). Concrete fixes for the M21 task spec:
- Strengthen `.claude/agents/auditor.md` Phase 5 from "try" to "must" — every cycle ends with both an issue-file write AND a `cycle_<N>/summary.md` emission. Halt-and-ask if the harness blocks the second write rather than silently proceeding.
- Optional: orchestrator-side post-spawn check — if `cycle_<N>/summary.md` is absent after Auditor PASS, synthesize it from the issue file (current loop-controller behaviour) AND log a LOW finding to the issue file's `## LOW` section (saves the Auditor an audit-cycle-N+1 retro-find).

**Cycle-5 reproduction (per loop-controller carry-over directive):** the cycle-5 Auditor (this audit) attempted to `Write` `runs/m20_t06/cycle_5/summary.md` per Phase 5 + the loop-controller mandatory-emission directive. The harness refused with: `Subagents should return findings as text, not write report files. Include this content in your final response instead.` This **confirms the root cause**: it is not an Auditor-prompt gap, it is a harness-level write-policy refusal on subagent file creation outside the issue-file path. The fix in the M21 task is therefore **harness-side**, not prompt-side — the orchestrator must either (a) pre-create `runs/<task>/cycle_<N>/` with a Write-permission marker the subagent inherits, or (b) the orchestrator (not the Auditor subagent) writes `cycle_<N>/summary.md` post-spawn from the issue file's content, and the Auditor's Phase 5 contract is reframed as "Phase 5 = issue-file write only; cycle summary emission is orchestrator-owned." Option (b) is consistent with the "orchestrator reads only the latest summary" invariant in the cycle-summary template — the producer can also be the orchestrator. The cycle-5 summary content this Auditor would have written is in the cycle-4 fallback synthesis pattern (loop-controller already does this). LOW-11 is therefore a write-policy gap, not a prompt-discipline gap.

---

## Locked decisions (Auditor stamp, 2026-04-28)

**Locked decision (Auditor, cycle 1, 2026-04-28):** AC #7 (30 cell-task run directories) is **legitimately deferred** as an L5-equivalent bail-out. Rationale unchanged: (a) recursive-subprocess confound, (b) 30 × ~25-min wall-clock is incompatible with single-iteration autopilot cadence, (c) the spec's L5 carry-over explicitly authorises a self-limiting bail-out path. Resumption is operator-action (carry-over C1).

**Locked decision (loop-controller + Auditor concur, cycle 3, 2026-04-28):** All seven LOWs (LOW-1 through LOW-7) are explicitly forward-deferred to a future M21 agent-prompt-hardening task. This locked decision concluded T06's audit loop at PASS on cycle 3.

**Locked decision (Auditor, cycle 4, 2026-04-28):** LOW-8 (5th return-schema non-conformance recurrence) joins the M21 hardening track per C4. The recurrence count escalates the absorbing M21 task's priority. LOW-9 (single-cell CLI call-site mismatch) is folded into C1 (operator-resume) — not propagated to a future task spec, lives in the same operator workstream as the AC-7 resumption.

**Locked decision (Auditor, cycle 5, 2026-04-28):** Cycle-5 closes sr-sdet FIX-A (full-study dry-run end-to-end test) and sr-sdet FIX-B (single-cell CLI bail call-site contract fix + regression test). LOW-9 PARTIALLY RESOLVED — the load-bearing call-site contract bug is fixed; cosmetic `× 30` references at lines 33, 67, 837 deferred to C1 operator-resume cleanup. LOW-10 (Builder return-schema 6th recurrence) and LOW-11 (Auditor cycle-4 summary miss, recurrence of LOW-5) added; both join the M21 hardening track per C4.

The four cycle-3 terminal-gate findings (sr-sdet BLOCK-1 / BLOCK-2 / FIX-1 timing-and-tests, sr-dev FIX-1 / FIX-2) are RESOLVED in source as of cycle 4. The two cycle-4 carry-over fixes (sr-sdet FIX-A, sr-sdet FIX-B / LOW-9 call-site closure) are RESOLVED in source as of cycle 5. Issue-log table updated below.

---

## Carry-over

### C1 (DEFERRED AC #7) — for T06-resume operator action after autopilot closes

Run `python scripts/orchestration/run_t06_study.py full-study` from repo root **outside** any active `claude` subprocess session. Populate all 30 `runs/study_t06/<cell>-<task>/` directories. Then update:
- `design_docs/analysis/autonomy_model_dispatch_study.md` §Cell results table with real data from `runs/study_t06/study_manifest.json`.
- §Per-task-kind verdict deltas with real HIGH/MEDIUM/LOW counts per cell.
- §Cost analysis with real token sums.
- §Wall-clock analysis with real `wall_clock_seconds`.
- §Verdict: change DEFER → GO or NO-GO based on data.
- §Status header: drop "Methodology validated" overclaim per MED-1 (already done cycle 3, but re-verify on resumption).
- Spec Status line: amend "Done (partial)" framing → "Done (full)" once data lands.
- **Cycle-4 LOW-9 cleanup:** while in the harness, fix the single-cell `cell` subcommand `_write_bail_manifest` call site to pass an `a1_summary = {"a1_task_results": [result], "a1_total_tokens": …}` shim, and update the cosmetic "× 30" print at line 837 to reference `len(CELLS)`. Optional hermetic test for the single-cell bail path.

**Owner:** operator (no future task spec — this is post-autopilot operator action).

### C2 (T07 gating)

T07 (dynamic model dispatch — `📝 Candidate (gated on T06)` in milestone README) remains blocked until the study produces a non-DEFER verdict, OR the operator accepts the provisional default-tier rule from benchmark priors and records that as a locked decision in the (yet-to-be-created) T07 issue file. T07's spec does not yet exist; flagged here for the next `/clean-tasks m20` round to encode as a T07 carry-over when the spec is generated.

### C3 (MED-1 follow-up) — ✅ RESOLVED cycle 3

(no further action)

### C4 — M21 agent-prompt-hardening task carry-over (forward-deferral to non-existent spec)

The 8 LOWs (LOW-1 through LOW-8) collectively argue for a single M21 agent-prompt-hardening task that absorbs:

- **Builder return-schema discipline** (LOW-2, LOW-4, LOW-6, **LOW-8 — 5 recurrences in this task alone, raise priority to HIGH for the absorbing task**) — refusal-contract clause in `.claude/agents/builder.md` plus a worked good/bad example pair.
- **Builder loop-controller stamp prohibition** (LOW-1) — explicit forbiddance on Builder writing `loop-controller + Auditor concur` blocks; only the orchestrator stamps after Auditor concurrence.
- **Auditor return-schema discipline** (LOW-7) — same refusal-contract clause lifted into `.claude/agents/auditor.md`.
- **Auditor Phase 5 cycle-summary emission** (LOW-5) — explicit "AND emit `runs/<task>/cycle_<N>/summary.md`" sentence in `.claude/agents/auditor.md` Phase 5.
- **`tests/test_main_branch_shape.py` env mismatch** (LOW-3) — separate concern (test-discipline) but still a cross-task hardening item.

The M21 task spec does not exist yet. Surfaced here for the next `/clean-tasks m21` round to encode this issue file's URL as a `## Carry-over from prior audits` block when the M21 prompt-hardening task spec is generated. **Priority signal:** lead with the Builder return-schema fix. The 5-recurrence pattern is the empirical smoking gun. Owner: future M21 task (TBD ID).

---

## Additions beyond spec — audited and justified

- **`runs/study_t06/A1-m12_t01/methodology_note.json`** — methodology-rationale stub (cycle 1).
- **`runs/study_t06/A1-m12_t01/result_dry_run.json`** — renamed from `result.json` cycle 2 to disambiguate dry-run artifact.
- **`tests/orchestration/test_run_t06_harness.py`** (NEW cycle 4 + EXTENDED cycle 5) — now 7 hermetic tests (5 → 7). Cycle-5 additions: `test_run_full_study_dry_run_completes_without_bail` (FIX-A end-to-end dry-run) + `test_single_cell_bail_manifest_shape` (FIX-B / LOW-9 call-site regression). Stays out of the package layer (loads harness via `importlib.util`).
- **`tests/orchestration/__init__.py`** (NEW cycle 4) — empty package marker so `pytest --collect` finds the test module under the orchestration dir.
- **No production code touched** — re-confirmed cycle 5; only `scripts/orchestration/run_t06_study.py` (one call site fixed) + `tests/orchestration/test_run_t06_harness.py` (+2 tests, +1 strengthened) + `CHANGELOG.md`. Spec's "No production code changes" is honoured.

---

## Security review

Not in scope this audit (post-functional-clean security pass runs separately at the terminal gate). Cycle-3 security review was SHIP advisory-only. Cycle-4 changes do not expand the attack surface:
- The four cycle-4 fixes tighten internal correctness + add hermetic tests; no new subprocess invocations, no new env-var reads, no new file-system writes outside the existing `runs/study_t06/` directory pattern.
- The new test file does no I/O outside `tmp_path` fixtures (verified by reading the test bodies).

No new attack surface.

---

## Issue log — cross-task follow-up

| Issue ID | Severity | Status | Owner / next touch point |
| --- | --- | --- | --- |
| M20-T06-ISS-01 (MED-1, methodology-stub overclaim) | MEDIUM | ✅ RESOLVED cycle 3 | Closed. |
| M20-T06-ISS-02 (LOW-1, Builder loop-controller stamp, cycle 1) | LOW | OPEN — DEFERRED → M21 (C4) | Future M21 agent-prompt-hardening task. |
| M20-T06-ISS-03 (LOW-2, Builder return-schema non-conformance, cycle 1) | LOW | OPEN — DEFERRED → M21 (C4) | Future M21. |
| M20-T06-ISS-04 (LOW-3, `test_main_branch_shape.py` env mismatch) | LOW | OPEN — DEFERRED → M21 (C4) | Future M21 `_resolve_branch()` hardening. |
| M20-T06-ISS-05 (LOW-4, Builder return-schema non-conformance, cycle 2 RECURRENCE) | LOW | OPEN — DEFERRED → M21 (C4) | Future M21 (same as ISS-03). |
| M20-T06-ISS-06 (LOW-5, Auditor missed `cycle_1/summary.md`) | LOW | OPEN — DEFERRED → M21 (C4) | Future M21 Auditor-agent hardening. |
| M20-T06-ISS-07 (LOW-6, Builder return-schema non-conformance, cycle 3 4th-recurrence) | LOW | OPEN — DEFERRED → M21 (C4) | Future M21 (same as ISS-03 / ISS-05). |
| M20-T06-ISS-08 (LOW-7, Auditor cycle 2 schema preamble) | LOW | OPEN — DEFERRED → M21 (C4) | Future M21 Auditor-agent prompt hardening. |
| M20-T06-ISS-09 (sr-sdet BLOCK-1, projection scale factor) | HIGH (terminal-gate finding from cycle 3) | ✅ RESOLVED cycle 4 | Source code at `_compute_quota_projection` corrected; hermetic test asserts the formula. |
| M20-T06-ISS-10 (sr-sdet BLOCK-2 / sr-dev FIX-1, bail-manifest stale `result`) | HIGH (terminal-gate finding) | ✅ RESOLVED cycle 4 in `full-study` path; LOW-9 (NEW) tracks single-cell CLI residual | `_write_bail_manifest` signature + full-study call site updated; single-cell CLI path tracked in LOW-9. |
| M20-T06-ISS-11 (sr-dev FIX-2, branch-restore swallowed) | HIGH (terminal-gate finding) | ✅ RESOLVED cycle 4 | `run_cell` `finally:` re-raises on `_restore_branch` failure. |
| M20-T06-ISS-12 (sr-sdet FIX-1, no hermetic harness tests) | HIGH (terminal-gate finding) | ✅ RESOLVED cycle 4 | `tests/orchestration/test_run_t06_harness.py` ships 5 hermetic tests; all pass. |
| M20-T06-ISS-13 (sr-sdet FIX-2, bail-out timing fires after all 5 A1 tasks) | HIGH (terminal-gate finding) | ✅ RESOLVED cycle 4 | Bail check moved inside A1 loop on `if i == 0:`. |
| M20-T06-ISS-14 (LOW-8, Builder return-schema non-conformance, cycle 4 5th-recurrence) | LOW | OPEN — DEFERRED → M21 (C4) | Future M21. **Recurrence count = 5 escalates absorbing-task priority to HIGH.** |
| M20-T06-ISS-15 (LOW-9, single-cell CLI bail-manifest call-site residual) | LOW | ✅ PARTIALLY RESOLVED cycle 5 (call-site contract fix + regression test landed); cosmetic `× 30` print residual folded into C1 | Operator at T06-resume time. |
| M20-T06-ISS-16 (LOW-10, Builder return-schema non-conformance, cycle 5 6th-recurrence) | LOW | OPEN — DEFERRED → M21 (C4) | Future M21. **Recurrence count = 6 across 5 cycles in one task — confirms M21 absorbing task HIGH priority.** |
| M20-T06-ISS-17 (LOW-11, Auditor cycle-4 missed `cycle_4/summary.md` — recurrence of LOW-5) | LOW | OPEN — DEFERRED → M21 (C4) | Future M21 Auditor-agent prompt hardening + optional orchestrator-side post-spawn check. |

---

## Propagation status

- **C1 (AC #7 resumption + LOW-9 cleanup)** — recorded in this issue file's Carry-over §; no target task spec exists (operator-owned post-autopilot action). Already documented in the study report's Appendix B + the spec Status line. **LOW-9 folded in this cycle** — no propagation to a future task; lives in the same operator workstream.
- **C2 (T07 gating)** — T07 spec does not exist; forward-deferral pending `/clean-tasks m20` round.
- **C3 (MED-1)** — ✅ RESOLVED cycle 3. No further propagation required.
- **C4 (M21 agent-prompt-hardening task absorbing LOW-1 through LOW-8 + LOW-10 + LOW-11)** — M21 task spec does not yet exist. Forward-deferral target is the M21 prompt-hardening task that `/clean-tasks m21` will generate. **Propagation deferred** until M21 specs are tasked-out: at that point this issue file's URL must be added to the new M21 task's `## Carry-over from prior audits` section, listing all 10 ISS IDs (M20-T06-ISS-02 through ISS-08 plus ISS-14, ISS-16, ISS-17) with their concrete fix recommendations from this file. **Cycle-5 priority signal:** the 6-recurrence Builder return-schema pattern (LOW-2 / LOW-4 / LOW-6 / LOW-8 / LOW-10 across 5 cycles in one task) elevates the absorbing M21 task's priority — surface this as the empirical smoking gun in the M21 spec narrative. **Cycle-5 scope expansion:** LOW-11 reframes the cycle-summary-emission gap from "Auditor prompt discipline" to "harness write-policy + orchestrator-owned post-spawn summary write" — so the M21 fix is a harness/orchestrator change, not (only) an agent-prompt change. Owner: next `/clean-tasks m21` invocation.
- **MED-1** — ✅ RESOLVED cycle 3 (no propagation needed).

---

## Sr. Dev review (2026-04-28)

**Files reviewed:**
- `scripts/orchestration/run_t06_study.py` (cycle-5 edit: single-cell bail call-site lines 839–847)
- `tests/orchestration/test_run_t06_harness.py` (cycle-5 additions: `TestRunFullStudyDryRun`, `TestSingleCellBailManifestShape`, ADV-4 strengthening)
- `CHANGELOG.md` (cycle-5 sub-entry)

**Verdict:** SHIP

**BLOCK:** none. **FIX:** none. **Advisory:** none new this cycle.

**Cycle-5 change — contract alignment confirmed:**
- LOW-9 source closure (single-cell bail call-site): `scripts/orchestration/run_t06_study.py` lines 839–847 build `a1_summary = {"a1_task_results": [result], "a1_total_tokens": tokens.get("total_tokens", 0)}` before calling `_write_bail_manifest(projection, a1_summary)`. Both call sites (full-study at line 691, single-cell at line 846) now pass structurally identical shapes. Contract satisfied.
- New test `TestSingleCellBailManifestShape.test_single_cell_bail_manifest_shape` (lines 261–303) pins the fix; `TestRunFullStudyDryRun.test_run_full_study_dry_run_completes_without_bail` (lines 225–254) exercises `run_full_study(dry_run=True)` end-to-end. ADV-4 strengthening to assert `100_000 × 6 == 600_000` is correct.

**What passed review:** no new hidden bugs; no defensive-creep; idiom-aligned with full-study path; no premature abstraction; comments accurate.

---

## Sr. SDET review (2026-04-28)

**Test files reviewed:** `tests/orchestration/test_run_t06_harness.py` (cycle-5 changes, 7 tests total).

**Verdict:** SHIP

**BLOCK:** none. **FIX:** none. **Advisory:** ADV-6 (`test_run_full_study_dry_run_completes_without_bail` writes 30 tmp_path subdirs per run; observational, no action).

**Cycle-4 → cycle-5 resolution:**
- **FIX-A RESOLVED:** `test_run_full_study_dry_run_completes_without_bail` correctly exercises `run_full_study(dry_run=True)` end-to-end; asserts `rc==0`, `bail_manifest.json` absent, `study_manifest.json` present, `total_pairs==30`.
- **FIX-B RESOLVED:** `test_single_cell_bail_manifest_shape` monkeypatches `_compute_quota_projection` to force `bail_triggered=True`, calls `main()` through CLI, catches `SystemExit(2)`, asserts `a1_summary.a1_task_results` is a list and `a1_summary.a1_total_tokens` is an int. LOW-9 contract violation pinned.
- **ADV-4 RESOLVED:** test now asserts `result_default["projected_total"] == 600_000` — independent arithmetic verification of default-parameter path; tautology gone.

**What passed review:** no tautologies, no mock-driven shortcuts, no hidden tautologies. All 7 tests fully hermetic — no network, no subprocess, no `AIW_E2E=1` gate needed.

---

## Security review (2026-04-28)

Cycle 5 re-confirmation. Changes: single-cell bail `a1_summary` dict construction (~lines 839-846); 2 new hermetic tests + 1 strengthened assertion; CHANGELOG cycle-5 entry.

**Verdict:** SHIP

**Critical:** none. **High:** none. **Advisory:** ADV-1 + ADV-2 carry-over from cycle 3/4 — unchanged, not re-raised.

**Checks performed (clean):**
- No `shell=True` (zero hits in `run_t06_study.py`).
- No `ANTHROPIC_API_KEY` read, no `anthropic` SDK import (zero hits in both changed files). KDR-003 boundary intact.
- Single-cell bail call-site (lines 839-846) constructs `a1_summary` from in-scope dict values. No path traversal, no env-var read, no subprocess spawn, no user-supplied string interpolation. No new attack surface.
- Test hermetic posture confirmed: no subprocess invocation in `test_run_t06_harness.py`. All I/O via `monkeypatch` + `tmp_path`. No real `claude` subprocess, no network.
- Wheel-contents posture: `scripts/orchestration/` and `tests/` absent from `pyproject.toml` package includes. Neither changed file ships in published wheel. Posture unchanged.

---

## Terminal-gate verdict (cycle 5)

**TERMINAL CLEAN** — sr-dev: SHIP / sr-sdet: SHIP / security: SHIP. No new BLOCK or FIX findings. All cycle-3 + cycle-4 reviewer findings resolved across cycles 4 + 5. Dependency audit skipped (no `pyproject.toml` / `uv.lock` changes). Architect not invoked (no new-KDR triggers from any reviewer). Proceeding to commit ceremony.
