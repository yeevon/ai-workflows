# Task 08 — Gate-output integrity — Audit Issues

**Source task:** [../task_08_gate_output_integrity.md](../task_08_gate_output_integrity.md)
**Audited on:** 2026-04-28 (cycle 1 + cycle 2 re-audit)
**Audit scope:**
- **Cycle 1:** Builder shipped: (a) `.claude/commands/_common/gate_parse_patterns.md`
  (NEW canonical regex source); (b) `## Gate-capture-and-parse convention` section in
  `auto-implement.md` and `clean-implement.md`; (c)
  `tests/orchestrator/test_gate_output_capture.py` and
  `tests/orchestrator/test_auto_clean_stamp_safety.py` (NEW); (d) CHANGELOG entry under
  `[Unreleased]`; (e) status-surface flips on the spec + milestone README task table +
  exit criterion #9. Cycle-1 terminal gate surfaced sr-sdet BLOCK-1 + BLOCK-2.
- **Cycle 2:** Builder fixed sr-sdet BLOCK-1 (added
  `test_failure_footer_zero_exit_is_blocked_by_condition4` exercising Condition 4 with
  `exit_code=0` + matching-regex footer containing `"failed"`; renamed prior misleading
  test) and BLOCK-2 (replaced tautological `test_gate_filename_convention` with a real
  path-derivation test that calls `build_blocked_message`); ADV-1 inline comment added
  to `test_no_gates_stamps`; CHANGELOG cycle-2 sub-entry appended.
**Status:** ✅ PASS (cycle 2)

## Design-drift check

**No drift detected.** T08 is orchestration-infrastructure-only — zero `ai_workflows/`
package files touched (`git diff --name-only HEAD` confirms only `.claude/commands/*`,
`design_docs/phases/...`, `CHANGELOG.md`, plus two new files under
`tests/orchestrator/` and one under `.claude/commands/_common/`). Drift sweep against the
seven load-bearing KDRs (002, 003, 004, 006, 008, 009, 013) is vacuously clean — the
change set is incapable of touching runtime invariants since no runtime code was modified.

Layer rule (`primitives → graph → workflows → surfaces`) preserved: import-linter run
returns `Contracts: 5 kept, 0 broken`.

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| 1. `auto-implement.md` describes gate-capture-and-parse convention | ✅ MET | New `## Gate-capture-and-parse convention (required before AUTO-CLEAN stamp)` section at line 422 references `gate_parse_patterns.md`, mandates `runs/<task>/cycle_<N>/gate_<name>.txt`, lists per-gate footer regex, halt condition with canonical `🚧 BLOCKED` message. |
| 2. `clean-implement.md` matches | ✅ MET | Mirror section at line 297 with same regex table, capture step, halt condition. Wording differs only in "AUTO-CLEAN" → "CLEAN" (correct — clean-implement does not commit). |
| 3. `_common/gate_parse_patterns.md` exists with per-gate regex | ✅ MET | New file, 89 lines, single source of truth. Per-gate regex table covers pytest / ruff / lint-imports; documents capture format, halt condition, extension hooks for task-specific gates. |
| 4. Captured gate outputs land at `runs/<task>/cycle_<N>/gate_<name>.txt` | ✅ MET | Convention specified in both command files + patterns file. `TestCapturePathConvention` parametric test validates filename pattern across pytest/lint-imports/ruff/smoke names; `test_canonical_path_structure` writes a real file at the canonical path. |
| 5. Halt-on-missing-footer surfaces `🚧 BLOCKED: gate <name> output not parseable` | ✅ MET | `build_blocked_message` produces the canonical string; `TestBlockedMessage` validates format. Both command files contain the exact halt message. |
| 6. `tests/orchestrator/test_gate_output_capture.py` passes | ✅ MET | 27 tests pass (8 pytest variants, 6 ruff, 5 lint-imports, 1 unknown gate, 2 BLOCKED message, 5 patterns-file content). All 4 spec-named fixtures present (valid footer, empty, no-footer, exit-code, failure-footer). |
| 7. `tests/orchestrator/test_auto_clean_stamp_safety.py` passes | ✅ MET | 19 tests pass (8 stamp-safety, 5 capture-path, 6 command-file references). All 3 spec-named scenarios present (empty file → halt, all-pass → stamp, one-failure-footer → halt). |
| 8. CHANGELOG.md updated with the prescribed `### Added — M20 Task 08: Gate-output integrity ...` entry | ✅ MET | Entry at line 10 under `[Unreleased]` matches the spec wording verbatim, dated 2026-04-28. |
| 9. Status surfaces flip together | ✅ MET | (a) spec line 3: `Status: ✅ Done (2026-04-28)`; (b) milestone README task table line 131: `✅ Done`; (c) exit criterion #9 line 58: `**[T08 Done — 2026-04-28]**`. No `tasks/README.md` for M20. No "Done when" checkboxes on milestone README beyond the exit criteria themselves (already flipped). |

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

### LOW-1 — Parser implementation lives in the test module rather than a dedicated `scripts/orchestration/` module

The Python mirror of the parse logic (`parse_gate_output`, `build_blocked_message`,
`GATE_PATTERNS`) lives at the top of `tests/orchestrator/test_gate_output_capture.py`
rather than in a dedicated module (e.g. `scripts/orchestration/gate_output_parser.py`).
`test_auto_clean_stamp_safety.py` imports from the test module. This is functional and
the spec did not mandate a particular implementation strategy ("verify the patterns
themselves are exercisable" was the audit guidance), so it is not a violation. However,
co-locating production logic in a test module is mildly idiosyncratic — if a future
orchestrator wants to call this parser at runtime (e.g. as a CLI helper), it would have
to import from `tests/`, which is unconventional.

**Action / Recommendation:** Optional. Defer until a runtime caller materialises (T09
"Task-integrity safeguards" may be one — if it lands, factor the parser into
`scripts/orchestration/gate_output_parser.py` and re-import from both test files). No
issue ID logged because there is no concrete trigger today.

### LOW-2 — `_GATE_PATTERNS_FILE.read_text()` called inside each test method

Minor — every test in `TestGateParsePatternsFile` re-reads the file from disk. Not a
correctness issue (the file is small) but slight test-runtime waste. A class-level
fixture would be more idiomatic.

**Action / Recommendation:** Cosmetic. Apply if anyone else touches the file during
hardening; not worth a dedicated edit.

### LOW-3 — Pre-existing `tests/test_main_branch_shape.py::test_design_docs_absence_on_main` failure on `workflow_optimization` branch

Re-running the full pytest gate from scratch surfaces 1 failure: the main-shape test
that asserts `design_docs/` is absent (only true when on `main`). This is environmental
and unrelated to T08; the audit context brief flagged it as expected. **All other 1140
tests pass.**

**Action / Recommendation:** No-op for T08. Will resolve naturally on the next merge to
`main`. Track environmentally.

### LOW-4 — Builder cycle 1 return-schema non-conformance (recurrence)

Per loop-controller carry-over note, the cycle 1 Builder return text included a
"Planned commit message" preamble + "All gates green" prose before the 3-line schema.
This is the **7th occurrence overall (1st in this task)**. The pattern is now consistent
across two consecutive tasks (T06 cycles 1-5 + T08 cycle 1).

**Action / Recommendation:** Logged here for trend visibility. Owner is the future M21
agent-prompt-hardening track (already opened in M20 T06 issue file Carry-over §C4 per
the loop-controller note). No new propagation needed — the M21 carry-over is the
canonical home. Raw return preserved at `runs/m20_t08/cycle_1/agent_builder_raw_return.txt`.

### LOW-5 — Builder cycle 2 return-schema non-conformance (8th overall recurrence, 2nd in this task)

Cycle 2 Builder return text included an "All three gates green. The 1 failure is the
expected `test_design_docs_absence_on_main` ..." preamble before the 3-line schema (raw
return at `runs/m20_t08/cycle_2/agent_builder_raw_return.txt`). This is the **8th
occurrence overall, 2nd in this task** — the pattern persists task-over-task and
cycle-over-cycle even when the durable work is correct.

**Action / Recommendation:** No new propagation. Owner remains the M21 agent-prompt-
hardening track (M20 T06 Carry-over §C4). Logged here for trend visibility. The
loop-controller invocation explicitly classified this as a tracked LOW recurrence;
durable work landed correctly so no remediation against T08 itself.

### LOW-6 — Auditor cycle 2 cycle-summary write refused by subagent surface (M20 T06 LOW-11 recurrence; 2nd recurrence, 3rd overall)

Per Phase 5 invocation guidance the auditor attempted to write
`runs/m20_t08/cycle_2/summary.md` per `_common/cycle_summary_template.md`. The Write
tool rejected the call with "Subagents should return findings as text, not write report
files." This is the same surface-level constraint that triggered M20 T06 LOW-11 in cycle
1. The cycle-2 summary content is reproduced inline in the audit-return chat for
loop-controller capture.

**Action / Recommendation:** Owner is the same M20 T06 LOW-11 follow-up — either (a)
loosen the Write-tool guard for the auditor surface to permit `runs/<task>/cycle_<N>/`
paths, or (b) move cycle-summary emission to the orchestrator (loop-controller writes
the summary based on the auditor's issue-file output). The latter is cleaner per the
"orchestrator owns durable artifacts beyond the issue file" pattern. No new
propagation; M20 T06 already carries this.

## Additions beyond spec — audited and justified

### Custom-gate extension hooks in `gate_parse_patterns.md`

The spec only required the three core gates (pytest / ruff / lint-imports). The Builder
added a `## Extension hooks for task-specific smoke tests` section with an empty
extensible table. **Justified.** The spec's `## Out of scope` clause explicitly notes
"task-specific gates ... are also captured via the same pattern; their footer-line
regex is added to `_common/gate_parse_patterns.md` as the project grows." Documenting
the extension point (rather than waiting for the first new gate to add it ad-hoc)
matches the spec's intent and adds zero coupling.

### `TestUnknownGate` and unknown-gate fail-closed behaviour

Spec did not enumerate "unknown gate name" as a halt condition. Builder added a
defensive branch that treats unrecognised gate names as blocked, with a corresponding
test. **Justified.** Fits the fail-closed posture the spec mandates everywhere else;
prevents a future bug where a typo in a gate name silently parses as "no footer
expected". Costs one if-branch.

## Gate summary

### Cycle 1

| Gate | Command | Result |
| --- | --- | --- |
| pytest | `uv run pytest` | ✅ PASS — 1140 passed, 10 skipped, 22 warnings, 1 known-environmental failure (`tests/test_main_branch_shape.py::test_design_docs_absence_on_main`, LOW-3 above) |
| lint-imports | `uv run lint-imports` | ✅ PASS — 5 contracts kept, 0 broken |
| ruff | `uv run ruff check` | ✅ PASS — `All checks passed!` |
| Spec smoke step 1 | `test -f .claude/commands/_common/gate_parse_patterns.md && echo "patterns OK"` | ✅ PASS — `patterns OK` |
| Spec smoke step 2 | `grep -lE "gate_parse_patterns.md\|gate_<name>.txt" auto-implement.md clean-implement.md \| wc -l` | ✅ PASS — `2` (expected 2) |
| Spec smoke step 3 | `uv run pytest tests/orchestrator/test_gate_output_capture.py tests/orchestrator/test_auto_clean_stamp_safety.py -v` | ✅ PASS — `46 passed in 0.05s` |

### Cycle 2 (re-run from scratch)

| Gate | Command | Result |
| --- | --- | --- |
| pytest | `uv run pytest -q` | ✅ PASS — `1140 passed, 10 skipped, 22 warnings, 1 failed in 42.88s` (the 1 fail is the known-environmental LOW-3) |
| lint-imports | `uv run lint-imports` | ✅ PASS — `Contracts: 5 kept, 0 broken.` |
| ruff | `uv run ruff check` | ✅ PASS — `All checks passed!` |
| T08-specific tests | `uv run pytest tests/orchestrator/test_gate_output_capture.py tests/orchestrator/test_auto_clean_stamp_safety.py -v` | ✅ PASS — `46 passed in 0.06s`. `test_failure_footer_zero_exit_is_blocked_by_condition4` (BLOCK-1 fix) PASSED; `test_failure_footer_nonzero_exit_is_blocked` (renamed) PASSED; parametric `test_gate_filename_convention[pytest|lint-imports|ruff|smoke]` (BLOCK-2 fix) all PASSED |
| BLOCK-1 verification | code-read of `tests/orchestrator/test_gate_output_capture.py:247-263` | ✅ Condition 4 actually exercised: `exit_code=0`, footer `"== 10 passed, 5 failed in 1.0s =="` matches `^=+ \d+ passed`, contains `"failed"`, asserts `result.blocked is True` and `"footer indicates failures" in result.reason` |
| BLOCK-2 verification | code-read of `tests/orchestrator/test_auto_clean_stamp_safety.py:200-218` | ✅ Tautology removed: assertion now derives `expected_path_segment` from `Path("runs") / task_shorthand / f"cycle_{cycle}" / f"gate_{gate_name}.txt"` and verifies `str(expected_path_segment)` is embedded in `build_blocked_message(...)` output — exercises real path-building logic |

## Issue log — cross-task follow-up

| Issue ID | Severity | Status | Owner / next touch point | Notes |
| --- | --- | --- | --- | --- |
| (none HIGH/MEDIUM) | — | — | — | LOW items above; no propagation required |
| Builder return-schema non-conformance (cycle 1, 7th overall) | LOW | DEFERRED | M21 agent-prompt-hardening track (M20 T06 Carry-over §C4) | 7th occurrence overall; no new carry-over file edit needed |
| sr-sdet BLOCK-1 (Condition 4 not exercised) | — | RESOLVED (cycle 2) | — | `test_failure_footer_zero_exit_is_blocked_by_condition4` added with `exit_code=0` + matching-regex footer containing `"failed"`; verified via gate-rerun + code-read |
| sr-sdet BLOCK-2 (path-convention tautology) | — | RESOLVED (cycle 2) | — | `test_gate_filename_convention` now derives expected path via `Path(...)` and checks `build_blocked_message` output contains it |
| sr-sdet ADV-1 (vacuous-pass posture) | — | RESOLVED (cycle 2) | — | Inline `# Intentional: empty gate dict returns True` comment added to `test_no_gates_stamps` |
| Builder return-schema non-conformance (cycle 2, 8th overall, 2nd in this task) | LOW | DEFERRED | M21 agent-prompt-hardening track (M20 T06 Carry-over §C4) | 8th occurrence overall; durable work landed correctly; LOW-5 above |
| Auditor cycle-summary write refused (LOW-11 recurrence, 3rd overall, 2nd recurrence) | LOW | DEFERRED | M20 T06 LOW-11 owner (loosen Write-tool guard, or move summary emission to orchestrator) | LOW-6 above; cycle-2 summary content reproduced inline |

## Deferred to nice_to_have

None.

## Propagation status

No new forward-deferrals from this audit. The Builder return-schema-recurrence trend is
already tracked under M20 T06 issue file's existing Carry-over §C4 (per the
loop-controller note in the audit invocation) — re-propagating to a third location
would duplicate, not add information.

---

## Sr. Dev review (2026-04-28)

**Files reviewed (cycle-2 delta):** `tests/orchestrator/test_gate_output_capture.py` (new Condition-4 test + renamed prior test); `tests/orchestrator/test_auto_clean_stamp_safety.py` (tautological assertion replaced; ADV-1 comment added).

**Verdict:** SHIP. **BLOCK:** none. **FIX:** none. **Advisory:** none new.

ADV-1 from cycle 1 resolved — `test_failure_footer_zero_exit_is_blocked_by_condition4` correctly exercises Condition 4 via a footer satisfying `^=+ \d+ passed` AND containing "failed", with `exit_code=0`. ADV-2 (vacuous-pass comment) addressed. ADV-3 (parser logic in test module) deferred per prior decision; no new signal.

---

## Sr. SDET review (2026-04-28) — cycle 2 re-review

**Test files reviewed:** `tests/orchestrator/test_gate_output_capture.py`, `tests/orchestrator/test_auto_clean_stamp_safety.py`.

**Verdict:** SHIP.

**BLOCK-1 resolution — confirmed.** `test_failure_footer_zero_exit_is_blocked_by_condition4` (line 247) uses `exit_code=0` and footer `"== 10 passed, 5 failed in 1.0s =="`; the footer regex matches, line contains "failed", driving execution to Condition 4. Asserts `result.blocked is True` and `"footer indicates failures" in result.reason` — both load-bearing. The prior misleading `test_footer_with_failures_is_blocked` was renamed to `test_failure_footer_nonzero_exit_is_blocked`.

**BLOCK-2 resolution — confirmed.** `test_gate_filename_convention` (lines 200-218) calls `build_blocked_message` and asserts `Path("runs") / task_shorthand / f"cycle_{cycle}" / f"gate_{gate_name}.txt"` appears in the message. Real path-building exercised.

**ADV-1 resolution — confirmed.** Inline comment documenting intentional vacuous-pass behaviour added.

---

## Security review (2026-04-28)

Cycle 2 re-confirmation. Test refactors only — no new production code, no new subprocess calls, no new env handling, no new shell ops.

**Verdict:** SHIP.

**Checks performed (clean):** No `shell=True`, no `ANTHROPIC_API_KEY` / `anthropic` SDK access (KDR-003 boundary intact), all tests hermetic (stdlib + pytest `tmp_path` fixtures only; no `AIW_E2E` opt-in, no subprocess spawns), wheel contents unchanged.

**Critical:** none. **High:** none. **Advisory:** none new.

---

## Terminal-gate verdict (cycle 2)

**TERMINAL CLEAN** — sr-dev: SHIP / sr-sdet: SHIP / security: SHIP. All cycle-1 BLOCK + advisory findings resolved. Dependency audit skipped (no `pyproject.toml` / `uv.lock` changes). Architect not invoked (no new-KDR triggers from any reviewer). Proceeding to commit ceremony.
