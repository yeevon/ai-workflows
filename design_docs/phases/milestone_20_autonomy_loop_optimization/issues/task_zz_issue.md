# M20 Task ZZ — Milestone Close-out — Issue File / Audit Log

**Task:** ZZ — Milestone Close-out
**Status:** PASS (Builder cycle 2)
**Date:** 2026-04-28

## Cycle 2 re-audit (2026-04-28)

**Verdict:** PASS. Doc-only fixes applied cleanly; gates green; no regressions; no new findings.

**Fixes verified:**
- FIX-1 (`roadmap.md:59`) — M19 declarative-surface paste removed; narrative now M20-specific (compaction quartet T01–T04, parallel gate T05, adaptive thinking T21, telemetry T22, integrity T08/T09/T20/T23/T27, study harness T06 DEFER, server-side eval T28 DEFER, T07 deferred to M21). PASS.
- ADV-1 (`CHANGELOG.md:25-27`) — T01=1eb67e3, T02=aef31c3, T03=48ed494 filled. PASS.
- ADV-2 (`roadmap.md:38`) — section header `## M2–M20 summaries`. PASS.

**Gates re-run from scratch:**
- `uv run pytest` → 1293 passed / 10 skipped / 1 known LOW-3 environmental fail (`test_design_docs_absence_on_main`, expected on `workflow_optimization` per AC-11).
- `uv run lint-imports` → 5 contracts kept, 0 broken (unchanged).
- `uv run ruff check` → All checks passed.
- `git log -1 --name-only HEAD -- ai_workflows/` → 0 files (AC-14 holds).

**Phase 1 design-drift:** none. Cycle 2 touched only `roadmap.md` + `CHANGELOG.md` (doc-only). No KDR boundary impact; no architecture.md edit required.

**AC re-grade:** all 16 ACs remain PASS (AC-3 + AC-4 narrative fidelity strengthened by FIX-1 + ADV-1).

**Loop-controller observation forwarded:** Builder cycle-2 return-schema non-conformance (17th overall). LOW-2 pattern recurrence incremented; already enumerated in §M21 Propagation Surface — no new finding.

**Auditor cycle-summary write refusal recurrence:** harness refused write to `runs/m20_tzz/cycle_2/summary.md` ("Subagents should return findings as text, not write report files"). Confirms LOW-5 pattern for this cycle; cycle-2 summary captured inline above per issue-file fallback policy. M21 absorbing-task scope unchanged.

---

---

## AC Evaluation

| AC | Description | Status |
|---|---|---|
| AC-1 | Milestone README Status flipped; Outcome section covers T01–T05, T06 (DEFER), T07 (BLOCKED), T08, T09, T20, T21, T22, T23 (AC-7 deferred), T27 (Path A rejected), T28 (DEFER) with autopilot-baseline summary | PASS |
| AC-2 | Propagation status section names M21 hardening track, T07 unblock condition, T06 + T23 operator-resume, T28 nice_to_have entry | PASS |
| AC-3 | roadmap.md gains M20 row (after M19) + one-line narrative summary | PASS |
| AC-4 | CHANGELOG has dated `## [M20 Autonomy Loop Optimization] - 2026-04-28` section with all M20 entries promoted + ZZ close-out entry citing commit shas + DEFER verdicts + T07 BLOCKED + M21 hardening surface + autopilot baseline smoke | PASS |
| AC-5 | `[Unreleased]` section retained at top of CHANGELOG (M20 entries promoted out; non-M20 entries preserved) | PASS |
| AC-6 | Root README.md gains M20 row after M19; §Next narrative updated to reflect M21 as next milestone | PASS |
| AC-7 | Status surfaces flipped together: ZZ spec Status line ✅ Done; milestone README ZZ task-pool row ✅ Done; milestone README §Exit-criteria ZZ checkbox satisfied; tasks/README.md — M20 does NOT have a tasks/README.md (confirmed: no such file in milestone_20_autonomy_loop_optimization/) | PASS |
| AC-8 | No `ai_workflows/` runtime code change in ZZ (doc-only close-out) | PASS |
| AC-9 | Autopilot-baseline smoke recorded in CHANGELOG ZZ entry: iter1–iter6 artifacts cited + 6 task commits (T06 d76f93f, T08 0dd91f4, T09 8e572dc, T20 851274f, T23 b39efbf, T27 a266996) + cumulative-token estimate (~3.5M) | PASS |
| AC-10 | Green-gate snapshot recorded in CHANGELOG ZZ entry: pytest count, lint-imports 5-contract status, ruff clean; LOW-3 environmental noted | PASS |
| AC-11 | `uv run pytest` green (modulo LOW-3 environmental fail) — 1293 passed, 1 known fail | PASS |
| AC-12 | `uv run lint-imports` reports 5 contracts (unchanged from pre-ZZ) | PASS |
| AC-13 | `uv run ruff check` clean | PASS |
| AC-14 | Zero `ai_workflows/` package-code diff in ZZ — doc/CHANGELOG/README/roadmap only | PASS |
| AC-15 | M21 propagation surface recorded in issue file and milestone README Propagation status section | PASS |
| AC-16 | T07 status-surface coordination: spec status line stays `📝 Planned. Gated on T06's GO verdict.` (no edit needed — already canonical); milestone README T07 row updated from `📝 Candidate (gated on T06)` to `📝 Planned (gated on T06)`; ZZ Outcome uses canonical phrasing | PASS |

---

## architecture.md — No change (AC spec §5)

No §4 sub-bullet or §6 dep-table row required updating to acknowledge the
`scripts/orchestration/` family. These are autonomy tooling artefacts, not runtime package
components. Architecture §4 covers `ai_workflows/` layers only; §6 covers runtime
external dependencies. The `scripts/orchestration/` directory is not a published package
surface and does not belong in the architecture reference.

---

## tasks/README.md — Confirmed absent

M20 does not have a `tasks/README.md` file under
`design_docs/phases/milestone_20_autonomy_loop_optimization/`. AC-7 status-surface
discipline does not require one.

---

## M21 Propagation Surface

The M21 agent-prompt-hardening absorbing task is not yet specced. M21 README exists at
`design_docs/phases/milestone_21_autonomy_loop_continuation/README.md`. `/clean-tasks m21`
is unblocked now that M20 closes.

### Absorbing-task scope (from T06 §C4 + subsequent task recurrences)

**T06 §C4 LOW roster (10 LOWs):**
- LOW-1: Builder pre-stamps "Auditor verdict: PASS/BLOCK" text in its own report body
- LOW-2: Builder return-schema non-conformance (prose body instead of 3-line schema)
- LOW-3: test_design_docs_absence_on_main environmental failure on workflow_optimization branch
- LOW-4: Builder pre-stamps "Locked decision (loop-controller + Auditor concur, YYYY-MM-DD)" block
- LOW-5: Auditor cycle-summary write refusal — Auditor returns 3-line schema without emitting cycle_N/summary.md
- LOW-6: sr-dev tools-list missing `Write` tool (agents with file-write capability need Write in their tools declaration)
- LOW-7: Builder output budget creep — Builder routinely exceeds the 4K output budget directive
- LOW-8: Orchestrator reads Auditor's raw 3-line return instead of the cycle summary for context carry-forward
- LOW-10: Builder narrates gate execution in report body instead of citing captured output path
- LOW-11 (reframe): Harness write-policy + orchestrator-owned post-spawn summary write rather than just agent-prompt discipline — the correct fix is the orchestrator writes the summary from the Auditor's structured output, not a prompt instruction to the Auditor

**Empirical recurrence across 6 tasks (6-iteration autopilot run):**
- Builder return-schema non-conformance (LOW-2 pattern): 16+ occurrences across T06, T08, T09, T20, T23, T27
- Auditor cycle-summary write refusal (LOW-5 pattern): multiple cycle boundaries per loop-controller observation in `runs/m20_t<NN>/cycle_<N>/agent_auditor_raw_return.txt`
- Builder pre-stamp "Auditor verdict" (LOW-1 pattern): recurring across multiple tasks
- Builder pre-stamp "Locked decision" (LOW-4 pattern): recurring across multiple tasks

**Priority: HIGH.** Empirical recurrence data (16+ violations across 6 tasks) is the smoking gun for the M21 task priority.

**Framing reframe (LOW-11):** The load-bearing fix is "harness write-policy + orchestrator-owned post-spawn summary write" — the orchestrator should write the cycle summary from the Auditor's structured output, not instruct the Auditor to write it via prompt. This is an architectural fix, not a prompt-discipline fix.

### Operator-resume actions

| Action | Location | Trigger |
|---|---|---|
| T06 full study | `python scripts/orchestration/run_t06_study.py full-study` | Outside autopilot; requires multi-day wall-clock |
| T23 empirical cache-hit validation | Per `runs/cache_verification/methodology.md` | Outside autopilot; requires stable-session TTL conditions |
| T07 unblock | Confirm T06 GO/NO-GO verdict, then `/clean-implement m20 t07` | After T06 study produces non-DEFER verdict |

---

## Builder return-schema recurrences (AC-15 empirical record)

The 6-task autopilot run (T06, T08, T09, T20, T23, T27) documented 16+ Builder return-schema
non-conformance events across the 6 tasks. Per-task issue files carry the individual cycle
records. This issue file summarises the milestone-level pattern:

- Every task in the autopilot run experienced at least 1 cycle where the Builder returned
  a prose summary instead of the hard 3-line schema (verdict / file / section).
- T06 had the highest cycle count (5 cycles) and the most schema violations.
- The pattern is consistent across all 6 tasks, indicating a systematic prompt-discipline
  failure that survives per-task carry-over LOWs — a harness-level fix is required.
- The M21 absorbing task must address this at the harness write-policy level (LOW-11 reframe),
  not solely via prompt instruction reinforcement.

---

## Findings

None (doc-only close-out; no code changes; all gates green).

---

## Carry-over from prior audits

None (this is the close-out task; carry-over goes forward to M21 via the Propagation status
section in the milestone README and the M21 absorbing-task scope above).

---

## Sr. Dev review (2026-04-28)

**Files reviewed:** `design_docs/phases/milestone_20_autonomy_loop_optimization/README.md`, `design_docs/phases/milestone_20_autonomy_loop_optimization/task_zz_milestone_closeout.md`, `design_docs/roadmap.md`, `README.md`, `CHANGELOG.md`, `issues/task_zz_issue.md`
**Skipped (out of scope):** `ai_workflows/` (no runtime changes; confirmed by AC-14 and git log)
**Verdict:** FIX-THEN-SHIP

### 🔴 BLOCK — must-fix before commit

None.

### 🟠 FIX — fix-then-ship

**[roadmap.md:59 — wrong-content paste in M20 narrative]**

The M20 narrative entry in `roadmap.md` line 59 contains M19 declarative-surface content verbatim — `WorkflowSpec`, `register_workflow(WorkflowSpec)`, `LLMStep`/`ValidateStep`/`GateStep`/`TransformStep`/`FanOutStep`, `_compiler.py`, artefact-loss bug fix in `_dispatch.py`, `summarize` workflow, `docs/writing-a-workflow.md` rewrite, `ADR-0008`, `KDR-013` boundary shift — none of which are M20 deliverables. The spec (§Deliverables 2) states the M20 narrative should be "shipped 11 of 13 candidate tasks (T01-T06, T08, T09, T20, T21, T22, T23, T27, T28). T07 deferred to M21. T28 verdict DEFER. T06 verdict DEFER." The current text is a copy-paste of M19's narrative with M20 shipping metadata prepended, making roadmap.md a misleading record of what M20 actually delivered.

Action: Replace the M20 narrative body (from "Introduces the `WorkflowSpec`…" to "…4 lint contracts kept.") with the M20-specific one-liner the spec prescribes. The M19 narrative two lines above (line 58) already correctly records those M19 deliverables.

### 🟡 Advisory — track but not blocking

**[CHANGELOG.md:21-35 — T01/T02/T03 commit SHAs absent]**

The spec (AC-4, AC-9) asks the ZZ CHANGELOG entry to cite every shipped-task commit SHA. T04 (7caecbd), T05 (bd27945), T21 (628b975), T22 (426c7fb), T28 (21c37ba), T06 (d76f93f), T08 (0dd91f4), T09 (8e572dc), T20 (851274f), T23 (b39efbf), T27 (a266996) are cited. T01 (1eb67e3), T02 (aef31c3), T03 (48ed494) are listed as "commit pre-autopilot" with no SHA. The git log confirms these SHAs exist. Not a correctness bug — a spec-alignment gap. Advisory: fill in 1eb67e3 / aef31c3 / 48ed494 to make the CHANGELOG entry self-contained.

**[roadmap.md:38 — section header says "M2–M19 summaries" after M20 row added]**

The section header at line 38 of `roadmap.md` reads `## M2–M19 summaries` but the section now contains an M20 summary at line 59. Once the FIX above is applied and the M20 narrative is correct, the header should read `## M2–M20 summaries` for accuracy. Trivial doc hygiene.

### What passed review (one-line per lens)

- Hidden bugs: none — ZZ is doc-only; no runtime code path touched.
- Defensive-code creep: not applicable — no code changes.
- Idiom alignment: all status-surface flips follow established close-out patterns (M14 T02, M11 T02).
- Premature abstraction: not applicable — doc-only.
- Comment / docstring drift: none observed; no module docstrings affected.
- Simplification: commit SHA trail in CHANGELOG is complete for the autopilot-run tasks; T01–T03 pre-autopilot SHAs are the only gap (see Advisory above).

---

## Security review (2026-04-28)

**Scope:** Doc-only close-out. Files reviewed: `CHANGELOG.md` (ZZ entry + M20 section), `README.md`, `design_docs/roadmap.md`, `design_docs/phases/milestone_20_autonomy_loop_optimization/README.md`, `design_docs/phases/milestone_20_autonomy_loop_optimization/task_zz_milestone_closeout.md` (status flip only), `design_docs/phases/milestone_20_autonomy_loop_optimization/issues/task_zz_issue.md`. No `ai_workflows/` code change.

### 1. Credential / secret leakage in touched docs

No `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` real value, `PYPI_TOKEN`, `Bearer`, or `Authorization` literal found in any touched doc. `GEMINI_API_KEY=...` in `README.md:73` is an existing placeholder, not a real value. `PYPI_TOKEN` does not appear in any touched file. No `.env` block with real values in any changed doc.

### 2. KDR citation accuracy

The CHANGELOG ZZ entry contains no KDR citations (doc-only close-out; none required). The M20 README Outcome section cites `context_management.edits` surface mismatch for T27 Path A rejection — this matches the T27 audit H6 finding and does not loosen any KDR boundary. No KDR numbers appear in the roadmap or root README additions. No loosening of KDR-003, KDR-004, KDR-006, KDR-008, KDR-009, or KDR-013 detected.

### 3. Wheel-contents posture

None of the touched files ship in the wheel. `pyproject.toml` excludes `/design_docs` (line 87). `CHANGELOG.md` and root `README.md` are already excluded from `ai_workflows/` package contents by package layout (only `ai_workflows/` directory contents ship). The ZZ close-out does not add any new file under `ai_workflows/`. No regression to wheel-contents posture.

### 4. Path A rejection — no walk-back detected

`design_docs/phases/milestone_20_autonomy_loop_optimization/README.md` line 210: "Path A explicitly rejected per audit H6." CHANGELOG M20 ZZ entry line 33: "T27 (auditor input-volume rotation trigger; Path A rejected)." CHANGELOG M20 T27 entry: "Path A rejected per audit H6 — Claude Code Task tool does not expose context_management.edits." The close-out narrative consistently preserves the rejection. No walk-back or softening language detected.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

**[design_docs/roadmap.md:59 — M19 content verbatim in M20 narrative — doc integrity, not a security issue]**
Threat-model item: Wheel contents / long_description integrity (not a credential leak, but a factual error in a file that is part of the published wheel's long_description path). `roadmap.md` itself is not included in the wheel, but the misleading record is worth noting as a doc-quality issue (already filed as FIX-THEN-SHIP by sr-dev above). No security impact.

### Verdict: SHIP

---

## Sr. SDET review (2026-04-28)

**Test files reviewed:** None — ZZ is doc-only (no tests added or modified).
**Skipped (out of scope):** All in-scope test files from prior M20 tasks (T01–T28); reviewed only in ZZ-lens capacity (test-claim accuracy, methodology stub presence, gate stability).
**Verdict:** SHIP

### What this review covered (ZZ-lens only)

**Lens 2 — Test-claim accuracy in the close-out narrative:**

- `CHANGELOG.md` line 67 states "1293 passed, 10 skipped, 1 pre-existing environmental fail".
- `issues/task_zz_issue.md` AC-11 records "1293 passed, 1 known fail".
- Verified: `uv run pytest` (two independent runs) confirms 1293 passed / 10 skipped / 1 known fail (LOW-3 `test_design_docs_absence_on_main`). Claims are accurate.
- Collected count (1304) differs from passed count (1293): delta is 10 skipped + 1 known-fail = 11, which checks out (1304 − 10 − 1 = 1293). Arithmetic correct.
- A transient flake in `tests/mcp/test_cancel_run_inflight.py::test_cancel_run_aborts_in_flight_task_and_flips_storage` appeared in run 1 and disappeared in run 2; test passes cleanly in isolation. Noted as advisory below.

**Lens 3 — Methodology stubs present and structurally honest:**

- `runs/study_t06/A1-m12_t01/methodology_note.json` — present; accurately describes NOT_RUN status with explicit rationale; `bail_triggered: false` note is honest ("Cannot project from zero; DEFER is based on operational-practicality reasoning"). No false claims of execution.
- `runs/cache_verification/methodology.md` — present; contains a complete operator runbook with prerequisite check, step-by-step harness invocation, exit-code table, and result-recording template. No false claims of empirical validation having occurred. Deferral rationale is precise (recursive-subprocess confound + TTL fragility + telemetry attribution conflict).
- Both stubs accurately represent deferred status — close-out narrative does not over-claim.

**Lenses 1, 4, 5, 6 — Tests pass for wrong reason / Mock overuse / Fixture hygiene / Hermetic gating / Naming hygiene:**

Not applicable; ZZ introduced no test code.

---

### 🟡 Advisory — track but not blocking

**Advisory-1 — transient flake in `tests/mcp/test_cancel_run_inflight.py`.**
`test_cancel_run_aborts_in_flight_task_and_flips_storage` failed in the first full-suite run but passed cleanly in the second run and in isolation. This suggests ordering-sensitive async teardown (likely a shared aiosqlite connection or asyncio event-loop residue leaking from an earlier test). ZZ did not introduce this file; the flake is a pre-existing condition on `workflow_optimization`. Action for M21 absorbing-task: investigate shared state between cancel-inflight tests and whatever runs immediately before them in full-suite order. Lens: Fixture / independence.

---

### What passed review (one-line per lens)

- Tests-pass-for-wrong-reason: N/A — no test code in ZZ.
- Coverage gaps: N/A — doc-only close-out; Auditor confirmed all AC gates green.
- Mock overuse: N/A — no test code in ZZ.
- Fixture / independence: one transient flake noted as advisory; not a ZZ regression.
- Hermetic-vs-E2E gating: no new tests; prior-milestone gating not re-audited.
- Naming / assertion-message hygiene: N/A — no test code in ZZ.
- Test-claim accuracy: PASS — 1293 passed / 10 skipped / 1 known fail confirmed by two independent runs; methodology stubs accurately represent NOT_RUN / DEFERRED status.

---

## Sr. Dev review (2026-04-28) — cycle 2 re-confirmation

**Files reviewed:** `design_docs/roadmap.md`, `CHANGELOG.md`
**Skipped (out of scope):** all other in-scope files (unchanged from cycle 1)
**Verdict:** SHIP

### Fix verification

**FIX-1 confirmed** (`design_docs/roadmap.md:59`): M19 paste-content removed. The M20 narrative now reads as the correct M20-specific one-liner describing the autonomy loop optimization deliverables. The M19 narrative at line 58 remains intact and correct.

**ADV-1 confirmed** (`CHANGELOG.md:25-27`): T01 SHA (1eb67e3), T02 SHA (aef31c3), T03 SHA (48ed494) filled in. CHANGELOG entry is now self-contained.

**ADV-2 confirmed** (`design_docs/roadmap.md:38`): Section header updated to `## M2–M20 summaries`. No residual "M2–M19" text remains.

### 🔴 BLOCK — must-fix before commit

None.

### 🟠 FIX — fix-then-ship

None.

### 🟡 Advisory — track but not blocking

None new. Cycle-1 advisory items fully resolved.

### What passed review (one-line per lens)

- Hidden bugs: N/A — doc-only; no runtime code path.
- Defensive-code creep: N/A — no code changes.
- Idiom alignment: N/A — no code changes.
- Premature abstraction: N/A — no code changes.
- Comment / docstring drift: N/A — no module docstrings affected.
- Simplification: N/A — no code changes.
