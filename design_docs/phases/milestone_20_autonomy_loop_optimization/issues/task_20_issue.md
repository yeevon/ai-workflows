# Task 20 — Carry-over checkbox-cargo-cult catch (extended detection) — Audit Issues

**Source task:** [../task_20_carry_over_checkbox_cargo_cult_extended.md](../task_20_carry_over_checkbox_cargo_cult_extended.md)
**Audited on:** 2026-04-28 (cycle 1 + cycle 2 + cycle 3 re-audits)
**Audit scope:** cycle 1 — Auditor agent prompt (Phase 4 extension), `scripts/orchestration/cargo_cult_detector.py`, hermetic test suite, CHANGELOG, status surfaces. Layer rule, KDR drift, gate re-run, smoke test, no-new-phase-numbering check. Cycle 2 — verify sr-sdet BLOCK B-1 + FIX F-1 + FIX F-2 + advisories A-1/A-2 fixes hold; gates re-run from scratch; no regressions. Cycle 3 — verify sr-dev cycle-2 F-1 guard fix (`_phase4_block` ValueError → `pytest.fail`) holds; gates re-run from scratch; no regressions.
**Status:** ✅ PASS (cycle 3 — sr-dev cycle-2 F-1 guard verified)

## Design-drift check

No drift detected. T20 is an orchestration-infrastructure task: the Auditor agent prompt (`.claude/agents/auditor.md`) and a small Python helper module (`scripts/orchestration/cargo_cult_detector.py`) plus its test (`tests/agents/test_auditor_anti_cargo_cult.py`). Zero modifications to `ai_workflows/` package code (verified via `git status --short` — only `.claude/agents/auditor.md`, `CHANGELOG.md`, two milestone-doc edits, and two new files outside the package).

KDR sweep:
- KDR-002 (MCP server) — untouched.
- KDR-003 (no Anthropic API) — untouched.
- KDR-004 (`TieredNode` + `ValidatorNode`) — untouched.
- KDR-006 (`RetryingEdge`) — untouched.
- KDR-008 (FastMCP) — untouched.
- KDR-009 (`SqliteSaver`) — untouched.
- KDR-013 (user-owned external workflows) — untouched.

Layer rule (`primitives → graph → workflows → surfaces`) preserved: `cargo_cult_detector.py` lives under `scripts/orchestration/` (orchestration tier, outside the package); module docstring explicitly states "no dependency on `ai_workflows/` package"; grep confirms zero `from ai_workflows` / `import ai_workflows` lines.

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| 1. Phase 4 extended with cycle-overlap + rubber-stamp bullets; no new phase numbering | ✅ | `auditor.md` lines 61-63 (diff: +3 bullet items). All headers remain `Phase 1–6` (verified via `grep -n "Phase"`). No "Phase 4.5", no "Phase 7", no "Phase 8". |
| 2. M12-T01 carry-over patch ported from template to live | ✅ | `auditor.md` line 61 — "Carry-over checkbox-cargo-cult" bullet present. Smoke-test grep `carry-over.*checkbox\|carry-over.*diff` returns hits (`test_auditor_md_has_carry_over_cargo_cult_paragraph` passes). |
| 3. Each inspection's failure surface specified (HIGH for missing-diff; MEDIUM for cycle-overlap; MEDIUM for rubber-stamp; no new ADVISORY tier) | ✅ | Bullet 1 specifies "**HIGH** finding"; bullets 2 and 3 each specify "emit **MEDIUM**". Bullet 3 explicitly says "do NOT introduce a new ADVISORY tier" per audit L6. Detector module enforces the same severities (CargoFinding.severity ∈ {"HIGH", "MEDIUM"}). |
| 4. `tests/agents/test_auditor_anti_cargo_cult.py` passes — true-positives + true-negatives | ✅ | 32/32 tests pass (0.04s). True-positives: `test_checkbox_without_diff_fires_high`, `test_cycle_overlap_80_percent_fires_medium`, `test_rubber_stamp_pass_big_diff_no_findings_fires_medium`. True-negatives: `test_checkbox_with_matching_diff_does_not_fire`, `test_cycle_overlap_novel_findings_no_false_positive`, `test_rubber_stamp_legitimate_clean_code_no_false_positive`, plus 5 more counter-example tests. Threshold env-var honored (`test_get_loop_detection_threshold_env_var_honored`, `test_cycle_overlap_uses_env_threshold`). |
| 5. CHANGELOG entry under `[Unreleased]` | ✅ | Line 10: `### Changed — M20 Task 20: Auditor anti-cargo-cult inspections (carry-over diff cross-ref + cycle-N overlap + rubber-stamp detection) (2026-04-28)`. Files-touched + ACs satisfied subsections present. |
| 6. Status surfaces aligned | ✅ | Spec `**Status:** ✅ Done.` (line 3). Milestone README row 133: `✅ Done`. No `tasks/README.md` for M20. No "Done when" checkboxes in milestone README that map specifically to T20. All four-surface checks satisfied. |

## 🔴 HIGH — none

## 🟡 MEDIUM — none

## 🟢 LOW — none

## Additions beyond spec — audited and justified

- **`run_all_detectors` convenience function** in `cargo_cult_detector.py` — composes all three detectors into a single call. Tested by `test_run_all_detectors_combines_findings` and `test_run_all_detectors_no_prior_issue_skips_cycle_overlap`. Justified: orchestrator-side ergonomics; no scope expansion (still the same three detectors). No coupling cost.
- **`_normalize_carry_over_title` + `_hunk_mentions` helpers** — internal implementation detail of `detect_checkbox_without_diff`. Reasonable factoring; keeps the public function readable.
- **`extract_finding_titles` + `count_diff_lines` exported helpers** — supporting utilities the orchestrator may want to call directly when stitching cycle-summary metrics. Both are unit-tested. No drift cost.

## Gate summary

| Gate | Command | Result |
| --- | --- | --- |
| pytest (full suite) | `uv run pytest -q` | 1206 passed, 10 skipped, 1 failed (pre-existing environmental — `test_main_branch_shape::test_design_docs_absence_on_main`, known LOW-3 on `workflow_optimization` branch) |
| pytest (T20 tests) | `uv run pytest tests/agents/test_auditor_anti_cargo_cult.py -v` | 32 passed in 0.04s |
| lint-imports | `uv run lint-imports` | All 5 contracts kept |
| ruff | `uv run ruff check` | All checks passed |
| Smoke (Phase 4 extensions) | `grep -qE "cycle.overlap\|cycle-N.*overlap\|rubber.stamp\|rubber-stamp" .claude/agents/auditor.md` | OK |
| Smoke (M12-T01 patch live) | `grep -q "carry-over.*checkbox\|carry-over.*diff" .claude/agents/auditor.md` | OK |
| Smoke (anti-cargo-cult tests) | `uv run pytest tests/agents/test_auditor_anti_cargo_cult.py -v` | 32 passed |

## Issue log — cross-task follow-up

None. All ACs satisfied; no findings to log.

## Deferred to nice_to_have

None.

## Propagation status

No forward-deferred items. T20 lands cleanly in cycle 1; cycle 2 re-audit confirms sr-sdet BLOCK + FIX fixes hold.

## Cycle 2 re-audit (2026-04-28)

**Trigger:** sr-sdet BLOCK in cycle 1 (B-1 tautological assertion + F-1 wrong-granularity Phase 4 scope + F-2 missing boundary tests + A-1/A-2 advisories).

### Fix verification

| sr-sdet finding | Severity | Fix applied | Verified |
| --- | --- | --- | --- |
| B-1 — tautological `test_auditor_md_has_carry_over_cargo_cult_paragraph` | BLOCK | `tests/agents/test_auditor_anti_cargo_cult.py:90-96` now asserts `"Carry-over checkbox-cargo-cult" in text` (verbatim canonical phrase) | ✅ Phrase grep returns single hit at `auditor.md:61`; assertion would fail on pre-T20 auditor.md (zero matches confirmed by sr-sdet). |
| F-1 — Phase 4 cycle-overlap test scoped to entire file | FIX | `_phase4_block(text)` helper added at line 62; both Phase 4 grep tests (`test_auditor_phase4_has_cycle_overlap_extension` line 72, `test_auditor_phase4_has_rubber_stamp_detection` line 81) now scope to text between `## Phase 4` and the next `## Phase` heading | ✅ Helper correctly slices text; assertion fires only when terms appear inside Phase 4 block. |
| F-2 — missing 50/51 boundary tests for `detect_rubber_stamp` | FIX | Added `_make_diff_with_n_lines(n)` helper + `test_rubber_stamp_50_lines_does_not_fire` (line 469) + `test_rubber_stamp_51_lines_fires` (line 484) | ✅ Both boundary tests pass; off-by-one on `< 50` vs `<= 50` would now break the suite. |
| A-1 — env-var manual `try/finally` | Advisory | Three threshold tests (lines 129, 136, 142) now use `monkeypatch.setenv` / `monkeypatch.delenv(raising=False)`; `test_cycle_overlap_uses_env_threshold` (line 286) also converted | ✅ No `os.environ.pop` / manual `finally` blocks remain in test file. |
| A-2 — redundant `or` disjunct in rubber-stamp grep | Advisory | Simplified to `assert "rubber-stamp" in phase4.lower()` (line 85) | ✅ Single canonical assertion form. |

### Cycle 2 gate re-run (from scratch)

| Gate | Command | Result |
| --- | --- | --- |
| pytest (T20 tests) | `uv run pytest tests/agents/test_auditor_anti_cargo_cult.py -v` | 34 passed in 0.04s (was 32 in cycle 1; +2 boundary tests from F-2) |
| pytest (full suite) | `uv run pytest -q` | 1208 passed, 10 skipped, 1 failed (pre-existing environmental — `test_main_branch_shape::test_design_docs_absence_on_main`, unchanged from cycle 1; LOW-3 known) |
| lint-imports | `uv run lint-imports` | All 5 contracts kept |
| ruff | `uv run ruff check` | All checks passed |
| Smoke (Phase 4 extensions) | `grep -qE "cycle.overlap\|rubber-stamp" .claude/agents/auditor.md` | OK |
| Smoke (M12-T01 patch live) | `grep -q "Carry-over checkbox-cargo-cult" .claude/agents/auditor.md` | OK (single hit, line 61) |
| Phase numbering check | `grep -nE "## Phase\|Phase 4\.5\|Phase 7\|Phase 8" .claude/agents/auditor.md` | Phases 1–6 only; no 4.5/7/8 |

### Design-drift check (cycle 2)

No drift. Cycle 2 changes are test-file-only edits + a CHANGELOG sub-entry. Zero `ai_workflows/` package touches; layer rule preserved; no KDR surfaces affected.

### Status-surface check (cycle 2)

Re-verified all four surfaces remain aligned:
- Spec `**Status:** ✅ Done.` (task_20_carry_over_checkbox_cargo_cult_extended.md:3) — unchanged.
- Milestone README task table — unchanged.
- No `tasks/README.md` for M20.
- No "Done when" checkboxes specific to T20.

### Cycle 2 verdict

✅ PASS. All three sr-sdet findings (B-1 + F-1 + F-2) are correctly remediated; both advisories (A-1 + A-2) also addressed. Test count went from 32 → 34 (+2 boundary tests). No regressions; pre-existing environmental failure unchanged.

## Cycle 3 re-audit (2026-04-28)

**Trigger:** sr-dev cycle-2 F-1 — `_phase4_block` raised `ValueError` on missing `## Phase 4` heading instead of a clean assertion failure.

### Fix verification

| sr-dev finding | Severity | Fix applied | Verified |
| --- | --- | --- | --- |
| F-1 (cycle 2) — `_phase4_block` unguarded `text.index("## Phase 4")` | FIX | `tests/agents/test_auditor_anti_cargo_cult.py:62-72` now wraps the call in `try/except ValueError` and emits `pytest.fail("auditor.md has no '## Phase 4' heading")` for a legible failure on heading rename | ✅ Helper inspected; the `start = text.index(...)` call is now inside `try`; `except ValueError` calls `pytest.fail(...)`. The existing inner `try/except` for the next-Phase boundary (end-of-file case) is preserved. |

### Cycle 3 gate re-run (from scratch)

| Gate | Command | Result |
| --- | --- | --- |
| pytest (T20 tests) | `uv run pytest tests/agents/test_auditor_anti_cargo_cult.py -v` | 34 passed in 0.04s (unchanged from cycle 2 — no test count delta; guard only changes failure mode) |
| pytest (full suite) | `uv run pytest -q` | 1208 passed, 10 skipped, 1 failed (pre-existing environmental — `test_main_branch_shape::test_design_docs_absence_on_main`, unchanged from cycles 1+2; LOW-3 known) |
| lint-imports | `uv run lint-imports` | All 5 contracts kept |
| ruff | `uv run ruff check` | All checks passed |
| Smoke (Phase 4 extensions) | `grep -qE "cycle.overlap\|rubber-stamp" .claude/agents/auditor.md` | OK |
| Smoke (M12-T01 patch live) | `grep -q "Carry-over checkbox-cargo-cult" .claude/agents/auditor.md` | OK |
| Phase numbering check | `grep -nE "## Phase" .claude/agents/auditor.md` | Phases 1–6 only (1, 2, 3, 4, 5, 5a, 5b, 6); no 4.5/7/8 |

### Design-drift check (cycle 3)

No drift. Cycle 3 is a single-helper test-file edit (lines 62-72) plus a CHANGELOG sub-entry. Zero `ai_workflows/` package touches; layer rule preserved; no KDR surfaces affected.

### Status-surface check (cycle 3)

Re-verified all four surfaces remain aligned (unchanged from cycle 2): spec `**Status:** ✅ Done.` (line 3), milestone README row, no `tasks/README.md` for M20, no T20-specific "Done when" checkboxes.

### Cycle 3 verdict

✅ PASS. sr-dev cycle-2 F-1 guard fix is correctly applied; descriptive `pytest.fail(...)` replaces bare `ValueError` traceback for the missing-Phase-4-heading failure mode. No test count change (34 → 34); no regressions; pre-existing environmental failure unchanged.

### Loop-controller carry-over (cycle 3)

- **Builder cycle 3 return-schema non-conformance (LOW recurrence — 12th overall, 3rd in this task).** Treat as DEFERRED-LOW per the standing M21 agent-prompt-hardening track. Not a T20 finding — task scope is the Auditor prompt extension, not Builder return-schema discipline.

### Loop-controller carry-over (cycle 2)

- **Builder cycle 2 return-schema non-conformance (LOW recurrence — 11th overall, 2nd in this task).** Treat as DEFERRED-LOW per the standing M21 agent-prompt-hardening track. Not a T20 finding — task scope is the Auditor prompt extension, not Builder return-schema discipline.

## Sr. Dev review (2026-04-28)

**Files reviewed:**
- `scripts/orchestration/cargo_cult_detector.py` (NEW)
- `tests/agents/test_auditor_anti_cargo_cult.py` (NEW)
- `.claude/agents/auditor.md` (Phase 4 extended)
- `CHANGELOG.md`, milestone README, task spec (status surfaces)

**Skipped (out of scope):** none
**Verdict:** SHIP

### BLOCK — must-fix before commit

None.

### FIX — fix-then-ship

None.

### Advisory — track but not blocking

**A1 — `_STOP_WORDS` frozenset reconstructed on every call**
`scripts/orchestration/cargo_cult_detector.py:153`
Lens: Simplification / hidden cost. `_STOP_WORDS` is allocated inside `_hunk_mentions`, which is called per carry-over item. Not a bug (frozenset is immutable), but the frozenset is rebuilt each call.
Action: Promote to module level alongside `_CHECKED_BOX_RE`, `_FINDING_TITLE_RE`, `_DIFF_LINE_RE`.

**A2 — `prior_issue_text` contract: `None` vs `""` discrepancy**
`scripts/orchestration/cargo_cult_detector.py:361`
Lens: Comment/docstring drift + falsy-check idiom. Guard `if prior_issue_text:` treats `""` as "skip" but docstring says `None` means cycle 1. `detect_cycle_overlap` handles empty prior titles correctly (`[]`), so the semantics are accidentally correct but surprising.
Action: Change `if prior_issue_text:` to `if prior_issue_text is not None:` to align with the typed `str | None` signature.

**A3 — `sys.path.insert` in test instead of `pyproject.toml` pythonpath**
`tests/agents/test_auditor_anti_cargo_cult.py:37`
Lens: Idiom alignment. Only test file in suite that mutates `sys.path` at import time.
Action: Add `pythonpath = ["."]` to `[tool.pytest.ini_options]` in `pyproject.toml` and remove the `sys.path.insert` line.

### What passed review (one-line per lens)

- Hidden bugs: None. `SequenceMatcher` call, threshold comparisons, and boundary conditions all correct per spec.
- Defensive-code creep: env-var fallback on out-of-range values is at a real system boundary — acceptable.
- Idiom alignment: Module-level regexes, `@dataclass` value object, orchestration-tier placement all correct. One `sys.path` outlier (A3).
- Premature abstraction: `run_all_detectors` and exported helpers have real callers; no over-abstraction.
- Comment/docstring drift: All public symbols documented; minor `prior_issue_text` contract gap (A2).
- Simplification: `_STOP_WORDS` promotion (A1); all other patterns idiomatic.

## Sr. Dev review (2026-04-28) — cycle 2 re-review

**Files reviewed:** `tests/agents/test_auditor_anti_cargo_cult.py` (cycle-2 delta only — verbatim phrase check, `_phase4_block` helper, 50/51 boundary tests, monkeypatch refactor)
**Skipped (out of scope):** `scripts/orchestration/cargo_cult_detector.py` (unchanged in cycle 2); cycle-1 advisories A1/A2/A3 (not cycle-2 scope)
**Verdict:** FIX-THEN-SHIP

### BLOCK — must-fix before commit

None.

### FIX — fix-then-ship

**F-1 — `_phase4_block` raises `ValueError` on missing heading instead of a clean assertion failure**
`tests/agents/test_auditor_anti_cargo_cult.py:64`
Lens: Hidden bugs that pass tests.
`_phase4_block` calls `text.index("## Phase 4")` with no surrounding `try/except`. The inner `except ValueError` at line 67 only handles the missing-next-`## Phase` case (end-of-file). If "## Phase 4" is absent (e.g. after a Phase-rename refactor in `auditor.md`), the call at line 64 raises `ValueError` and both `test_auditor_phase4_has_cycle_overlap_extension` and `test_auditor_phase4_has_rubber_stamp_detection` crash with a traceback rather than a clean `AssertionError` with the descriptive message. All current tests pass because Phase 4 exists, so this is a silent failure mode the suite does not cover.
Action: Wrap the `text.index("## Phase 4")` call in a `pytest.fail(...)` guard or a `try/except ValueError` that calls `pytest.fail("auditor.md has no '## Phase 4' heading")`, so a heading-rename surfaces as a legible test failure rather than an unhandled exception.

### Advisory — track but not blocking

None new in cycle 2. Prior cycle-1 advisories A1/A2/A3 remain open (tracked in cycle-1 Sr. Dev review section above).

### What passed review (one-line per lens)

- Hidden bugs: F-1 — `_phase4_block` unguarded `str.index` raises on missing heading.
- Defensive-code creep: none; monkeypatch refactor removed the manual try/finally per A-1 recommendation.
- Idiom alignment: monkeypatch usage now matches project standard; verbatim phrase assertion is tighter than keyword scan.
- Premature abstraction: `_make_diff_with_n_lines` is a single-purpose test helper used by exactly two boundary tests — acceptable.
- Comment/docstring drift: `_phase4_block` docstring is accurate; `_make_diff_with_n_lines` has an inline comment explaining the exclusion rationale.

---

## Sr. Dev review (2026-04-28) — cycle 3 re-review

**Files reviewed:** `tests/agents/test_auditor_anti_cargo_cult.py` (one-line guard fix only)
**Skipped (out of scope):** none
**Verdict:** SHIP

### F-1 cycle-3 fix confirmed

`tests/agents/test_auditor_anti_cargo_cult.py:64-67` — `_phase4_block` first `try/except ValueError` now calls `pytest.fail("auditor.md has no '## Phase 4' heading")` instead of propagating `ValueError` bare. The second `try/except ValueError` at lines 68-71 (end-of-block sentinel, fallback `end = len(text)`) is correctly preserved — that branch is a legitimate fallback, not defensive creep.

No new issues introduced.

### What passed review (one-line per lens)

- Hidden bugs: F-1 fix is correct and complete; no new bugs introduced.
- Defensive-code creep: second `try/except` fallback is intentional and correct; not creep.
- Idiom alignment: `pytest.fail` is the project-standard idiom for test-setup assertions in helpers.
- Premature abstraction: none; single-line change, no new abstractions.
- Comment/docstring drift: `_phase4_block` docstring unchanged; still accurate.
- Simplification: fix is already minimal — one-line replacement, no simplification opportunity.
- Simplification: 50/51 boundary tests are clean; no over-engineering observed.

## Loop-controller carry-over observations

- **Builder cycle 1 return-schema non-conformance (LOW recurrence — 10th overall, 1st in this task).** Noted by loop controller: cycle 1 Builder return text included a "Planned commit message" block + "All smoke tests pass" prose before the 3-line schema. Tracked under the M21 agent-prompt-hardening track per the orchestrator's standing DEFERRED-LOW pattern. Raw return at `runs/m20_t20/cycle_1/agent_builder_raw_return.txt`. Not a T20 finding — task scope is the Auditor prompt extension, not the Builder agent's return-schema discipline.

## Sr. SDET review (2026-04-28)

**Test files reviewed:** `tests/agents/test_auditor_anti_cargo_cult.py` (NEW), `scripts/orchestration/cargo_cult_detector.py` (NEW)
**Skipped (out of scope):** none
**Verdict:** BLOCK

### BLOCK — tests pass for the wrong reason

**Finding B-1** `tests/agents/test_auditor_anti_cargo_cult.py:79-92` — Lens 1 (tautological assertion)

`test_auditor_md_has_carry_over_cargo_cult_paragraph` is supposed to verify AC-2: the M12-T01 carry-over checkbox-cargo-cult patch was ported from template to the live `auditor.md`. The assertion checks:

```python
has_cargo = (
    "carry-over" in text.lower() and (
        "checkbox" in text.lower()
        or "diff" in text.lower()
    )
)
```

Both halves were already satisfied in the pre-T20 `auditor.md`:

- "carry-over" appears in the frontmatter description (line 3: "…carry-over sections may be written…").
- "diff" appears at line 20 ("You load the full task scope, not the diff") — unrelated to the M12-T01 patch.

This test would have passed on the pre-task version of `auditor.md` before the patch was ported. It is a tautology: it proves the document uses the English words "carry-over" and "diff," not that the specific "Carry-over checkbox-cargo-cult" patch paragraph is present.

The Auditor issue file (AC-2 row) cites `test_auditor_md_has_carry_over_cargo_cult_paragraph passes` as evidence AC-2 is met — but the test does not actually verify the patch was ported.

**Source line the AC was supposed to pin:** `.claude/agents/auditor.md` line 61 — the "Carry-over checkbox-cargo-cult" bullet paragraph.

**Action:** Replace the broad keyword scan with an assertion that checks for the canonical patch phrase verbatim (which is unique in the file):

```python
assert "Carry-over checkbox-cargo-cult" in text, (
    "auditor.md must contain the 'Carry-over checkbox-cargo-cult' paragraph (M12-T01 patch)"
)
```

This assertion would have failed on the pre-T20 `auditor.md` (grep confirmed zero matches) and passes on the post-T20 version (line 61 confirmed). The broader keyword scan can be kept as a secondary fallback comment but must not be the only assertion.

### FIX — fix-then-ship

**Finding F-1** `tests/agents/test_auditor_anti_cargo_cult.py:63-68` — Lens 1 (wrong granularity, weak scope)

`test_auditor_phase4_has_cycle_overlap_extension` scans the entire `auditor.md` for `"cycle" in text.lower() and "overlap" in text.lower()`. Both words could appear outside Phase 4. The test name implies Phase 4 specificity that the assertion does not enforce. Future edits that move the cycle-overlap bullet out of Phase 4 would leave this test green while AC-1 ("Phase 4 extended…no new phase numbering") is violated.

**Action:** Scope the assertion to the Phase 4 text slice. Read text between the `## Phase 4` heading and the next `## Phase` heading (a short slice), then check for "cycle" and "overlap" within that slice.

**Finding F-2** Missing boundary tests for `detect_rubber_stamp` diff-line threshold — Lens 2 (boundary condition)

The detector fires when `diff_lines > 50`. The test suite has `test_rubber_stamp_small_diff_does_not_fire` (2 lines) and `test_rubber_stamp_pass_big_diff_no_findings_fires_medium` (110 lines). There is no test at exactly 50 lines (must NOT fire) and 51 lines (must fire). An off-by-one change to `<= diff_line_threshold` vs `< diff_line_threshold` would be undetected.

**Action:** Add two boundary tests (or a parametrized case):
- diff of exactly 50 added/removed lines + PASS + 0 findings → `findings == []`
- diff of exactly 51 added/removed lines + PASS + 0 findings → `len(findings) == 1`

### Advisory — track but not blocking

**A-1** `tests/agents/test_auditor_anti_cargo_cult.py:125-160` — Lens 4: env-var tests use manual `os.environ.pop/del` in try/finally rather than `monkeypatch.setenv/delenv`. Safe but inconsistent with the project's standard fixture pattern. Convert to `monkeypatch`.

**A-2** `tests/agents/test_auditor_anti_cargo_cult.py:74` — Lens 6: assertion `"rubber" in text.lower() or "rubber-stamp" in text.lower()` has a dead branch — "rubber-stamp" is a substring of "rubber" match. Simplify to `assert "rubber-stamp" in text.lower()`.

### What passed review (one-line per lens)

- Tests-pass-for-wrong-reason: B-1 (tautological AC-2 assertion); F-1 (insufficient Phase 4 scope in overlap test).
- Coverage gaps: F-2 — boundary condition at diff-line threshold 50/51 unverified.
- Mock overuse: none — all tests exercise real module functions with synthetic string fixtures; no mocks used.
- Fixture / independence: env-var tests use manual try/finally (safe, advisory per A-1); no order dependence or module-state bleed observed.
- Hermetic-vs-E2E gating: all tests are hermetic; no network access; no AIW_E2E gate needed or missing.
- Naming / assertion-message hygiene: A-2 (redundant disjunct); test names are otherwise descriptive and specific.

## Sr. SDET review (2026-04-28) — cycle 2 re-review

**Test files reviewed:** `tests/agents/test_auditor_anti_cargo_cult.py` (cycle-2 delta: verbatim phrase check, `_phase4_block` helper, 50/51 boundary tests, monkeypatch refactor)
**Skipped (out of scope):** none
**Verdict:** SHIP

### B-1 resolution confirmed

`tests/agents/test_auditor_anti_cargo_cult.py:90-96`

`test_auditor_md_has_carry_over_cargo_cult_paragraph` now asserts the verbatim canonical phrase:

```python
assert "Carry-over checkbox-cargo-cult" in text
```

`.claude/agents/auditor.md:61` contains the phrase exactly once. The pre-T20 `auditor.md` had no such phrase — "carry-over" appeared only in the frontmatter description and "diff" only at line 20 (unrelated). Deleting the Phase 4 patch paragraph from `auditor.md` would cause this test to fail. B-1 is fully resolved; the tautology is eliminated.

### F-1 resolution confirmed

`tests/agents/test_auditor_anti_cargo_cult.py:62-69` (`_phase4_block` helper)
`tests/agents/test_auditor_anti_cargo_cult.py:72-87` (both Phase 4 grep tests)

`_phase4_block` slices file text between `## Phase 4` and the next `## Phase` heading. `auditor.md` has Phase 1–6 headings; the helper bounds lines 49–64 (Phase 4 only). Moving cycle-overlap or rubber-stamp bullets to Phase 1 or Phase 6 would yield a slice that excludes those terms, failing both assertions. F-1 is fully resolved.

Note: `_phase4_block` calls `text.index("## Phase 4")` with no guard for a missing heading; if Phase 4 were renamed, both Phase 4 tests would crash with `ValueError` rather than a legible `AssertionError`. This is the sr-dev cycle-2 F-1 finding; it is a test-robustness advisory for sr-sdet purposes (does not affect any passing test today) and is noted here for completeness. Not a new sr-sdet BLOCK or FIX.

### F-2 resolution confirmed

`tests/agents/test_auditor_anti_cargo_cult.py:461-496`

`detect_rubber_stamp` at `cargo_cult_detector.py:310` uses `diff_lines <= diff_line_threshold` (threshold defaults to 50): fires when lines > 50. `_make_diff_with_n_lines(n)` generates exactly `n` lines each prefixed with `+`, none starting `+++`/`---`, so all `n` are counted. `test_rubber_stamp_50_lines_does_not_fire` (line 469) asserts `findings == []` for n=50; `test_rubber_stamp_51_lines_fires` (line 484) asserts exactly one MEDIUM finding for n=51. An off-by-one to the `<=` operator in source would break one test. F-2 is fully resolved; spec wording "exceeds 50 lines" is correctly modelled.

### No new findings

- Tests-pass-for-wrong-reason: none — B-1 fix eliminates the tautology; F-1 fix closes the wrong-granularity gap.
- Coverage gaps: none — F-2 boundary tests are complete.
- Mock overuse: none — all tests exercise real module functions with synthetic string fixtures.
- Fixture / independence: monkeypatch replaces all manual `os.environ` manipulation per A-1; no order dependence or module-state bleed.
- Hermetic-vs-E2E gating: all tests remain hermetic; no network access; no gate needed.
- Naming / assertion-message hygiene: boundary test names are specific; assertion messages include the triggering condition. A-2 rubber-stamp simplification confirmed at line 85.

## Sr. SDET review (2026-04-28) — cycle 3 re-review

**Test files reviewed:** `tests/agents/test_auditor_anti_cargo_cult.py`
**Skipped (out of scope):** none
**Verdict:** SHIP

### Cycle 3 change scope

The sole change is `tests/agents/test_auditor_anti_cargo_cult.py:67`: the bare `ValueError` propagation on a missing `## Phase 4` heading is replaced with `pytest.fail("auditor.md has no '## Phase 4' heading")`. This is a test-diagnostic improvement only — no assertion logic, no coverage shape, no fixture altered.

### BLOCK-1 regression check

`tests/agents/test_auditor_anti_cargo_cult.py:93-96` — `test_auditor_md_has_carry_over_cargo_cult_paragraph` still asserts `"Carry-over checkbox-cargo-cult" in text` against the live `auditor.md`. No regression; the verbatim phrase remains at `.claude/agents/auditor.md:61`.

### F-1 regression check

`tests/agents/test_auditor_anti_cargo_cult.py:62-72` — `_phase4_block` logic (slice between `## Phase 4` and next `## Phase`) unchanged. Both Phase 4 grep tests (`test_auditor_phase4_has_cycle_overlap_extension`, `test_auditor_phase4_has_rubber_stamp_detection`) still bound to Phase 4 text only. The cycle 3 fix makes the missing-heading failure surface as a legible `pytest.fail` message rather than a `ValueError` traceback — test coverage pins are tighter, not weaker. F-1 fix intact.

### F-2 regression check

`tests/agents/test_auditor_anti_cargo_cult.py:461-496` — `_make_diff_with_n_lines` helper and the n=50 / n=51 boundary tests are untouched. F-2 fix intact.

### No new findings

- Tests-pass-for-wrong-reason: none — cycle 3 touch is a failure-message improvement; no assertion semantics changed.
- Coverage gaps: none — no new code paths; existing boundary coverage preserved.
- Mock overuse: no change; all tests remain mock-free.
- Fixture / independence: no change; no order dependence introduced.
- Hermetic-vs-E2E gating: no change; all tests remain hermetic.
- Naming / assertion-message hygiene: `pytest.fail` message is descriptive and names the trigger to unskip — compliant.

## Security review (2026-04-28)

**Scope:** Cycle 3 delta — `tests/agents/test_auditor_anti_cargo_cult.py` lines 62-72 (`_phase4_block` heading-guard fix). No production code, no `ai_workflows/` package change, no `pyproject.toml` or `uv.lock` change.

All eight threat-model items (wheel contents, OAuth subprocess integrity, external workflow load path, MCP bind address, SQLite paths, subprocess env leakage, logging hygiene, dependency CVEs) are not applicable — the change is test-helper-only with no wheel-shipped code, no subprocess paths, no env reads, and no secrets surface.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

None.

### Verdict: SHIP
