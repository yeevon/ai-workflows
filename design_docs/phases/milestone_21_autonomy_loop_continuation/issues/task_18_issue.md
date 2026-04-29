# Task 18 — Worktree-coordinated parallel Builder spawn — Audit Issues

**Source task:** [../task_18_parallel_builder_spawn.md](../task_18_parallel_builder_spawn.md)
**Audited on:** 2026-04-29 (cycle 1) · 2026-04-29 (cycle 2 re-audit)
**Audit scope:** cycle 1 — `.claude/commands/auto-implement.md`, `tests/test_t18_parallel_dispatch.py`, `CHANGELOG.md`, M21 README, T18 spec status flip, TA-LOW-02 carry-over. Cycle 2 — verification of four targeted fixes from cycle 1 terminal-gate bypass (sr-dev FIX-1/2, sr-sdet FIX-1/2).
**Status:** ✅ PASS (cycle 1) · ✅ PASS (cycle 2)

## Pre-flight

- Issue file: created at cycle start (this audit).
- No prior HIGH 🚧 BLOCKED.
- Carry-over from task analysis: TA-LOW-02 (worktree cleanup for empty-diff case) — applied (auto-implement.md Step 1.7 + TC-5).
- Builder out-of-scope edit (drive-by `cs300` README) was reverted by the orchestrator pre-audit; not present in working tree.

## Design-drift check

No drift detected.

- KDR-013 (user-owned external workflow code): unaffected — T18 changes only orchestrator workflow procedure (`.claude/commands/`), no `ai_workflows/` runtime code.
- KDR-002/003/004/006/008/009: not engaged — no LLM call sites, no checkpoint code, no MCP tool surface, no retry/edge code, no provider-SDK touch.
- Layer rule: not engaged — no source imports altered. `lint-imports` reports 5 contracts kept.
- M21 scope note (no runtime code) honoured.

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| AC-1 — auto-implement.md parallel-Builder dispatch path: reads `PARALLEL_ELIGIBLE`, spawns slice-isolated Builders, ≤4 cap, overlap detection. Smoke 1+2 pass. | ✅ MET | Step 1 §"Parallel-Builder dispatch path (T18)" added at lines 361–414. Reads `runs/<task>/meta.json`; branches on `PARALLEL_ELIGIBLE`; spawns Task with `isolation: "worktree"`; explicit "Concurrency cap — ≤4 slices per cycle" sub-step; overlap detection via `git diff --name-only` cross-check emits the exact `🚧 BLOCKED:` string the spec mandates; serial path preserved unchanged. Smoke 1+2 pass. |
| AC-2 — tests/test_t18_parallel_dispatch.py passes (6 test cases). Smoke 3 passes. | ✅ MET | 6 test classes (TC-1..TC-6) covering PARALLEL_ELIGIBLE=true/false, slice cap 5→4, overlap detection (single + multi), worktree cleanup, and telemetry naming. 28 individual tests pass (`uv run pytest tests/test_t18_parallel_dispatch.py -q`: 28 passed in 0.03s). TC-6 includes a smoke that `auto-implement.md` references `builder-slice-` — wires the doc to the test. |
| AC-3 — All CI gates green. Smoke 4 passes. | ✅ MET | `uv run lint-imports` → 5 contracts kept; `uv run ruff check` → All checks passed. Full `uv run pytest -q`: 1435 passed, 10 skipped, 1 pre-existing FAIL (`test_design_docs_absence_on_main`, environmental LOW-3 documented in context brief, predates T18). |
| AC-4 — CHANGELOG updated. Smoke 5 passes. | ✅ MET | Anchor `### Added — M21 Task 18: Worktree-coordinated parallel Builder spawn (2026-04-29)` present under `## [Unreleased]`. Files-touched + ACs-satisfied + TA-LOW-02 line all present. |
| AC-5 — Status surfaces flip together. | ✅ MET | (a) T18 spec `**Status:** ✅ Done.` (was `📝 Stretch.`); (b) M21 README task-pool T18 row → `✅ Done`; (c) `tasks/README.md` does not exist for M21 — surface (c) N/A; (d) M21 README G4 exit criterion updated to `T18 parallel-Builder dispatch landed; T19 orchestrator close-out pending`. |
| TA-LOW-02 — Worktree cleanup for empty-diff case | ✅ MET | auto-implement.md Step 1.7 explicitly: `git worktree remove <worktree-path>` for any slice whose Builder produced no changes; "Do not leave empty-diff worktrees behind" prose. TC-5 (4 tests) verifies the cleanup decision logic. |

## 🔴 HIGH

*None.*

## 🟡 MEDIUM

*None.*

## 🟢 LOW

### LOW-1 — Step 1.6 ("Worktree merge") procedure is hand-wave

**File:** `.claude/commands/auto-implement.md` lines 393–395.

The merge step says "the orchestrator applies them via cherry-pick or merge" without specifying which, with no example command. When T18 first fires for a real multi-slice task, the orchestrator will need to invent the merge mechanism on the spot. This is acceptable given M21 has no real `## Slice scope` task to exercise the path (PARALLEL_ELIGIBLE is always `false` in practice today, per the T17 forward-compat stub note at auto-implement.md line 288). But the first real consumer in M22+ will need a concrete recipe.

**Recommendation:** when T19 or the first multi-slice spec lands, harden Step 1.6 with the actual `git -C <worktree> diff | git apply` (or cherry-pick) recipe — or punt to T19 explicitly. Not blocking now; flag-only.

**Owner:** T19 spec author (or first M22 multi-slice consumer).

## Additions beyond spec — audited and justified

*None.* Builder kept the diff scoped to the four files the spec lists plus the new test file. Out-of-scope `cs300` README edit was reverted by the orchestrator before audit; working tree is clean of drive-by edits.

## Gate summary

| Gate | Command | Result |
| ---- | ------- | ------ |
| Smoke 1 — parallel dispatch markers | `grep -qiE 'PARALLEL_ELIGIBLE\|parallel.dispatch\|isolation.*worktree' .claude/commands/auto-implement.md` | PASS |
| Smoke 2 — concurrency cap markers | `grep -qiE 'cap.*[34]\|[34].*slice\|concurren' .claude/commands/auto-implement.md` | PASS |
| Smoke 3 — T18 tests | `uv run pytest tests/test_t18_parallel_dispatch.py -q` | PASS (28 passed) |
| Smoke 4a — lint-imports | `uv run lint-imports` | PASS (5 contracts kept) |
| Smoke 4b — ruff | `uv run ruff check` | PASS |
| Smoke 5 — CHANGELOG anchor | `grep -qE '^### (Added\|Changed) — M21 Task 18:' CHANGELOG.md` | PASS |
| Full pytest | `uv run pytest -q` | 1435 passed, 10 skipped, 1 FAIL (pre-existing environmental, LOW-3) |

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch point | Status |
| -- | -------- | ------------------------ | ------ |
| M21-T18-ISS-01 | LOW | T19 spec or first M22 multi-slice consumer | OPEN — hand-wave merge recipe in Step 1.6 |

## Deferred to nice_to_have

*None.* T18 itself absorbs the parallel-dispatch primitive; nice_to_have entry for "multi-orchestrator parallelism" remains unchanged (different primitive).

## Propagation status

LOW-1 is forward-flag only; no spec edit required against T19 because T19's existing scope ("orchestrator-owned close-out after parallel-builder merge") naturally subsumes the merge-recipe hardening. If T19 is deferred to M22, the M22 multi-slice consumer task (when authored) inherits LOW-1 as a known cleanup item via this issue file. No carry-over insertion required at this audit.

## Security review (2026-04-29)

### Scope

Changes reviewed: `.claude/commands/auto-implement.md` (procedural documentation only), `tests/test_t18_parallel_dispatch.py` (pure Python, no `ai_workflows/` runtime), `CHANGELOG.md`, `README.md`, T18 spec. No Python library code changed; no new network calls; no new subprocess calls; no new file I/O outside `tempfile`-based tests.

Threat model items assessed: (1) wheel contents, (2) subprocess integrity, (3) external workflow load path, (4) MCP bind address, (5) SQLite paths, (6) subprocess env leakage, (7) logging hygiene, (8) dependency CVEs.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

**ADV-1 — Procedural `git worktree remove <worktree-path>` template uses a literal placeholder**

File: `.claude/commands/auto-implement.md` lines 398–401. Threat model item: #6 (subprocess CWD / env).

The documented Step 1.7 command `git worktree remove <worktree-path>` uses an angle-bracket placeholder that a future orchestrator implementation must substitute at runtime. If the worktree path is ever sourced from user-controlled or externally-written data (e.g., a Builder agent return value injected into a shell string), constructing the command via string concatenation with `shell=True` would create a path-traversal / command-injection vector. This risk is entirely prospective — the current deliverable is prose documentation, not executable code, and today's `PARALLEL_ELIGIBLE` is always `false` in practice. The risk window opens only when an actual orchestrator implements the Step 1.7 shell invocation.

Action: when T19 or an M22 multi-slice consumer implements this step in executable form, the implementer MUST pass the worktree path as a positional argv element (e.g., `subprocess.run(["git", "worktree", "remove", worktree_path], ...)` or equivalent) rather than interpolating into a shell string. The spec prose should be annotated with this constraint at that time.

**ADV-2 — `exec_module` on a sibling test file is an unusual import pattern**

File: `tests/test_t18_parallel_dispatch.py` lines 32–34. Threat model item: #1 (wheel contents — test-time only).

`_spec_t17.loader.exec_module(_t17)` dynamically executes the neighbouring test file as a module at import time. This is a test-internal pattern, entirely absent from the wheel (tests are not packaged). It is not a security defect, but it means any future injection into `test_t17_spec_format.py` would silently execute under T18's test run. This is only relevant if the repo is treated as an untrusted workspace, which is outside the threat model. No action required; noted for awareness.

### Verdict: SHIP

No runtime library code changed. Wheel contents unaffected (`.claude/` and `tests/` are not packaged). No subprocess calls added to the library. All documented shell examples use argv-style invocations (`git worktree remove <worktree-path>`) rather than shell-string concatenation; the prospective injection risk in ADV-1 is advisory and pre-implementation-only. Both advisory items are below the blocking threshold for this project's threat model.

---

## Sr. Dev review (2026-04-29)

**Files reviewed:** `.claude/commands/auto-implement.md` (parallel-Builder dispatch path, lines 361–438), `tests/test_t18_parallel_dispatch.py`
**Skipped (out of scope):** `CHANGELOG.md`, `design_docs/phases/milestone_21_autonomy_loop_continuation/README.md`, `design_docs/phases/milestone_21_autonomy_loop_continuation/task_18_parallel_builder_spawn.md`
**Verdict:** FIX-THEN-SHIP

### BLOCK — must-fix before commit

None.

### FIX — fix-then-ship

**FIX-1 — Step 5 `git diff --name-only` does not surface worktree-isolated changes** (`.claude/commands/auto-implement.md` line 383, lens: hidden bugs that pass tests)

Step 5 instructs the orchestrator to run `git diff --name-only` in the main working tree to find overlap. Because each Builder slice runs with `isolation: "worktree"`, its changes live in a separate git worktree. At the moment Step 5 fires, the main working tree has no pending changes from any slice (Step 6 has not merged them yet). Running `git diff --name-only` here returns an empty list — the bash command is a no-op for the worktree isolation model.

The prose one sentence later correctly identifies the right source: "If any file appears in multiple slices' **Builder reports**." The bash code block contradicts that and, when a real orchestrator follows it literally, defeats the overlap check entirely.

**Action:** Remove the misleading `git diff --name-only` code block from Step 5. Replace it with: "Cross-check the files-touched lists from each Builder's report. For a git-level check, use `git -C <worktree-path> diff --name-only HEAD` per worktree — not `git diff --name-only` in the main tree." The `detect_overlap` helper in the test file correctly operates on report-text, so the test logic is sound; only the procedural example command needs correction. This fix should land before the first real `PARALLEL_ELIGIBLE=true` task fires.

---

**FIX-2 — Step 7 asserts non-empty-diff worktrees are cleaned up "automatically" — they are not** (`.claude/commands/auto-implement.md` lines 402–403, lens: hidden bugs that pass tests)

Step 7 states: "Worktrees with actual changes are cleaned up **automatically** after the merge in step 6." Step 6 contains no `git worktree remove` call for non-empty-diff worktrees, and there is no git or framework mechanism that removes worktrees automatically post-merge. An orchestrator following Steps 6–7 literally will leave non-empty-diff worktrees on disk indefinitely — `git worktree list` accumulates stale entries, and `git worktree prune` does not remove worktrees that still have an on-disk directory.

**Action:** Either (a) add an explicit `git worktree remove <worktree-path>` at the end of Step 6 for each successfully-merged worktree, or (b) consolidate Steps 6–7: after the merge, run `git worktree remove <worktree-path>` for every slice worktree (empty-diff and merged). Option (b) eliminates the split. Also add a TC-5 counterpart test asserting that a worktree with `has_changes=True` and status `merged` is also scheduled for removal — `plan_worktree_cleanup` currently only returns empty-diff worktrees for removal, leaving the merged-but-not-removed path untested.

---

### Advisory — track but not blocking

**ADV-1 — `detect_overlap` third claimant message names only the first owner, not the immediate predecessor** (`tests/test_t18_parallel_dispatch.py` lines 86–98, lens: simplification)

When file `shared.py` is touched by slices A, B, C in order, the function emits "A and B" then "A and C". The violation count is correct, but "A and C" misrepresents the B-vs-C relationship in the conflict chain. Not blocking — the BLOCKED string is always emitted and the file name is always present. A `seen` dict mapping file to list of all claimants would produce cleaner messages ("modified by A, B, C") if this path ever needs human triage. Consider for T19 if the merge-recipe step needs accurate conflict attribution.

**ADV-2 — TC-5 fixtures use hardcoded `/tmp/...` paths on an in-memory helper** (`tests/test_t18_parallel_dispatch.py` lines 327–356, lens: comment/docstring drift)

`plan_worktree_cleanup` never touches disk (it is a dict-filter), but the test fixtures pass literal `/tmp/wt-slice-A` strings, creating a false suggestion of filesystem involvement. Using abstract keys like `"wt-slice-A"` would make the test intent clearer. Low cost to fix in the same edit as FIX-2.

**ADV-3 — `importlib` dynamic import of T17 helpers couples test files at the path level** (`tests/test_t18_parallel_dispatch.py` lines 31–38, lens: premature abstraction)

The T17 helpers are imported via `importlib.util.spec_from_file_location` — fragile if `test_t17_spec_format.py` is renamed. The idiomatic fix is to extract shared helpers into `tests/helpers/` or a `conftest.py`. Advisory for the current two-file scope; becomes a FIX if a third consumer appears (T19).

### What passed review (one-line per lens)

- Hidden bugs: FIX-1 (misleading `git diff --name-only` in Step 5 is a no-op under worktree isolation) and FIX-2 (non-empty-diff worktrees not explicitly removed post-merge); no other hidden bugs found.
- Defensive-code creep: none — `read_parallel_eligible` correctly defaults False for missing file (genuine boundary condition at cycle start).
- Idiom alignment: test file structure matches sibling `tests/test_t1*.py` modules; no structlog/asyncio drift; no `ai_workflows/` imports introduced.
- Premature abstraction: none at task scope; ADV-3 notes a future extraction trigger.
- Comment / docstring drift: module docstring cites task and T17 relationship per convention; inline comments match the "why non-obvious" bar.
- Simplification: ADV-1 (three-claimant message), ADV-2 (/tmp key aesthetics) noted; no blocking simplification debt.

---

## Sr. SDET review (2026-04-29)

**Test files reviewed:** `tests/test_t18_parallel_dispatch.py`
**Skipped (out of scope):** `tests/test_t17_spec_format.py` (imported helper source, not modified by T18)
**Verdict:** FIX-THEN-SHIP

### BLOCK — tests pass for the wrong reason

None. No test asserts something true while production code is wrong. There is no executable production code changed by T18; the subject under test is a Markdown procedure document. The structural consequence is captured in FIX-1 below.

### FIX — fix-then-ship

#### FIX-1 — Three helper-function contracts have no doc-anchor assertion; constant drift is undetected

**Lens:** 2 (coverage gap — spec-doc contract not pinned by any test).

**Files:** `tests/test_t18_parallel_dispatch.py:TestSliceCap` (lines 234–260), `tests/test_t18_parallel_dispatch.py:TestOverlapDetection` (lines 267–313), `tests/test_t18_parallel_dispatch.py:TestWorktreeCleanup` (lines 319–356).

**Situation:** Five helper functions are defined in the test module itself and tested against string fixtures. Because no `ai_workflows/` runtime code was changed, this is the only viable approach. However, the tests prove the helpers are internally consistent, not that `auto-implement.md` matches the helper logic. Today TC-6 has exactly one doc-anchor: `test_auto_implement_md_uses_builder_slice_naming` (line 385) greps the doc for `"builder-slice-"`. Three other helper contracts lack corresponding anchors:

- `_MAX_PARALLEL_SLICES = 4` (line 44): if someone edits the doc to say "cap at 3" and forgets to update the constant, `TestSliceCap` still passes.
- `detect_overlap` BLOCKED string prefix: TC-4 asserts helper output starts with `"🚧 BLOCKED:"` but does not verify this exact string appears in `auto-implement.md` lines 388–390 (where the spec mandates it verbatim).
- `plan_worktree_cleanup` empty-diff path: TC-5 verifies the filter logic but does not assert `"git worktree remove"` and `"empty-diff"` appear in `auto-implement.md`.

**Action:** Add three doc-anchor assertions (one per gap). Recommended placement: a single `TestDocAnchors` class that reads `auto-implement.md` once and runs the three assertions:

1. `assert re.search(r'≤4|cap.*4|4.*slice', content, re.IGNORECASE)` — pins the concurrency-cap constant.
2. `assert "🚧 BLOCKED: parallel-Builder overlap detected" in content` — pins the exact BLOCKED prefix the spec mandates.
3. `assert "git worktree remove" in content and "empty-diff" in content` (or two separate assertions) — pins the worktree cleanup step.

#### FIX-2 — TC-1 duplicates T17 coverage without the round-trip that T18 actually owns

**Lens:** 2 (coverage gap).

**File:** `tests/test_t18_parallel_dispatch.py:TestParallelEligibleTrue` lines 182–193.

`test_spec_with_slice_scope_yields_eligible` (line 182) and `test_parallel_path_produces_multiple_slices` (line 186) call `has_slice_scope_section` and `parse_slice_rows` — functions already covered by `test_t17_spec_format.py`. They add no T18-specific coverage.

The T18-specific gap is the end-to-end path: spec text with `## Slice scope` → `write_meta_json` writes `PARALLEL_ELIGIBLE=true` → `read_parallel_eligible` returns `True`. `test_read_parallel_eligible_true` (line 175) bypasses `write_meta_json` by using a hand-crafted `{"PARALLEL_ELIGIBLE": True}` dict. This round-trip is never exercised.

**Action:** Add a round-trip test, e.g.:

```python
def test_round_trip_spec_to_flag(self, tmp_path: Path) -> None:
    out = write_meta_json(tmp_path, _SPEC_PARALLEL_ELIGIBLE, "abc123", "t99")
    assert read_parallel_eligible(out) is True
```

The two T17-duplicating tests (`test_spec_with_slice_scope_yields_eligible`, `test_parallel_path_produces_multiple_slices`) can be removed or replaced by this round-trip test.

### Advisory — track but not blocking

#### ADV-1 — `tempfile.TemporaryDirectory` used instead of `tmp_path` fixture

**Lens:** 4 (fixture hygiene).

**File:** `tests/test_t18_parallel_dispatch.py` lines 177, 207, 210, 223.

Four tests use `with tempfile.TemporaryDirectory() as tmpdir:` inside the test body. pytest's `tmp_path` fixture is the idiomatic approach (auto-cleanup, `--basetemp` visibility, consistent with project norms). No correctness issue.

**Action:** Convert the four affected tests to accept `tmp_path` as a fixture parameter. Low-cost, consistent with project style.

#### ADV-2 — TC-5 uses `/tmp/...` string literals that look like real filesystem paths

**Lens:** 4 (fixture hygiene / misleading intent).

**File:** `tests/test_t18_parallel_dispatch.py:TestWorktreeCleanup` lines 327–355.

`plan_worktree_cleanup` is a pure dict filter; the keys are never used as filesystem paths by the helper. Using `"/tmp/wt-slice-A"` literals implies filesystem involvement, which could mislead a future maintainer who extends the helper to call `git worktree remove` directly.

**Action:** Use sentinel strings (`"wt-slice-A"`, `"wt-slice-B"`) rather than `/tmp/`-prefixed paths. Matches Sr. Dev ADV-2 finding — low-cost fix in the same edit.

#### ADV-3 — `test_naming_is_one_indexed` and `test_naming_pattern_matches_expected_regex` overlap

**Lens:** 6 (assertion-message hygiene / redundancy).

**File:** `tests/test_t18_parallel_dispatch.py:TestTelemetryNaming` lines 375–383.

`test_naming_is_one_indexed` checks `names[0] == "builder-slice-1"` and `names[-1] == "builder-slice-3"`. `test_naming_pattern_matches_expected_regex` checks all names match `^builder-slice-\d+$`. The regex subsumes the index check. No correctness issue; minor redundancy.

**Action:** Optional merge. Not blocking.

### What passed review (one-line per lens)

- Tests-pass-for-wrong-reason: No test asserts something true while production code is wrong; the structural self-testing issue is a coverage gap (FIX-1), not a wrong-reason pass.
- Coverage gaps: FIX-1 (three helpers lack doc-anchor assertions); FIX-2 (round-trip spec→meta.json→flag gap); all 6 spec TCs structurally present.
- Mock overuse: No mocks used; T17 helpers imported directly; appropriate for a doc-only task.
- Fixture / independence: ADV-1 (tempfile vs tmp_path); ADV-2 (misleading /tmp/ key strings); no order-dependence or test bleed found.
- Hermetic-vs-E2E gating: All 28 tests are fully hermetic (no network, no subprocess, no provider touch); no gating issues.
- Naming / assertion-message hygiene: ADV-3 (minor overlap in TC-6); all class and method names trace to spec TCs.

## Locked terminal-gate decisions (cycle 1 bypass)

**Cycle 1 terminal-gate result:** sr-dev=FIX-THEN-SHIP, sr-sdet=FIX-THEN-SHIP, security-reviewer=SHIP.

Both FIX-THEN-SHIP findings are on distinct lenses (sr-dev: procedural text quality in auto-implement.md; sr-sdet: test coverage gaps). Per lens-specialisation bypass rule: single clear recommendations, orchestrator concurs → stamp and re-loop.

### sr-dev fixes to apply in cycle 2

**FIX-1 (doc):** Remove misleading `git diff --name-only` bash block from Step 5 (main working tree has no changes yet under worktree isolation). Replace with: cross-check files-touched lists from Builder reports; for a git-level check use `git -C <worktree-path> diff --name-only HEAD` per worktree.

**FIX-2 (doc + test):** Add explicit `git worktree remove <worktree-path>` at the end of Step 6 for each successfully-merged worktree (currently says "automatically" — incorrect). Add test asserting non-empty-diff+merged worktrees are also cleaned up.

### sr-sdet fixes to apply in cycle 2

**FIX-1 (test):** Add `TestDocAnchors` class with three assertions reading `auto-implement.md`:
  1. Concurrency-cap pin (≤4)
  2. `🚧 BLOCKED: parallel-Builder overlap detected` verbatim
  3. `git worktree remove` + `empty-diff` both present

**FIX-2 (test):** Add round-trip test `test_round_trip_spec_to_flag` (spec text → `write_meta_json` → `read_parallel_eligible` returns True). Remove/replace the two T17-duplicating tests (`test_spec_with_slice_scope_yields_eligible`, `test_parallel_path_produces_multiple_slices`).

---

## Cycle 2 re-audit (2026-04-29)

**Verdict:** ✅ PASS — all four targeted fixes verified; no regressions; all 5 ACs still satisfied.

### Fix verification

| Fix | Verification | Result |
| --- | ------------ | ------ |
| sr-dev FIX-1 — Step 5 misleading `git diff --name-only` block removed | `auto-implement.md` lines 380–385: bash code block replaced with corrective prose; `grep -n "git diff --name-only" .claude/commands/auto-implement.md` returns only line 384 (the corrective sentence) and line 771 (unrelated existing Auditor cycle-N spawn). The misleading bash block in Step 5 is gone. | ✅ APPLIED |
| sr-dev FIX-2 — Step 6/7 explicit `git worktree remove` for both cases | `auto-implement.md` Step 6 (lines 394–400) ends with explicit `git worktree remove <worktree-path>` after merge; Step 7 (lines 402–406) explicitly covers BOTH empty-diff AND merged cases. "Automatically" wording is gone. | ✅ APPLIED |
| sr-sdet FIX-1 — `TestDocAnchors` class with 3 doc-anchor assertions | `tests/test_t18_parallel_dispatch.py` line 395: `TestDocAnchors` class present with `test_concurrency_cap_documented` (regex `≤4\|cap.*4\|4.*slice`), `test_blocked_prefix_present_verbatim` (exact string `🚧 BLOCKED: parallel-Builder overlap detected`), `test_worktree_cleanup_documented` (`git worktree remove` + `empty-diff`). All three assertions are sound and match the spec mandates. | ✅ APPLIED |
| sr-sdet FIX-2 — Round-trip test added; T17-duplicates removed | `test_round_trip_spec_to_flag` present at line 182 (uses `tmp_path` fixture; round-trip `write_meta_json` → `read_parallel_eligible`). Grep for `test_spec_with_slice_scope_yields_eligible` and `test_parallel_path_produces_multiple_slices` returns no hits — both T17-duplicating tests removed. | ✅ APPLIED |

### Gate re-run (cycle 2, from scratch)

| Gate | Command | Result |
| ---- | ------- | ------ |
| T18 tests | `uv run pytest tests/test_t18_parallel_dispatch.py -q` | ✅ 30 passed (was 28 in cycle 1; net +2 = +3 TestDocAnchors + 1 round-trip - 2 T17-duplicates) |
| Full pytest | `uv run pytest -q` | ✅ 1437 passed, 10 skipped, 1 pre-existing FAIL (`test_design_docs_absence_on_main`, environmental LOW-3, predates T18) |
| lint-imports | `uv run lint-imports` | ✅ 5 contracts kept, 0 broken |
| ruff | `uv run ruff check` | ✅ All checks passed |

### AC re-verification (cycle 2)

| AC | Cycle 2 status | Notes |
| -- | -------------- | ----- |
| AC-1 — auto-implement.md parallel dispatch path | ✅ STILL MET | Step 5 overlap-detection prose now correctly directs to per-worktree diff; Step 6/7 cleanup is explicit. Smoke 1+2 still pass. |
| AC-2 — T18 tests pass (was 6 cases / 28 tests; now 6 + TestDocAnchors / 30 tests) | ✅ STILL MET | 30 passed; new TestDocAnchors class adds 3 assertions; round-trip test replaces 2 T17-duplicates. |
| AC-3 — All CI gates green | ✅ STILL MET | lint-imports 5/5, ruff clean, full pytest 1437 passed (+2 vs cycle 1), 1 pre-existing FAIL unchanged. |
| AC-4 — CHANGELOG updated | ✅ STILL MET | Anchor unchanged from cycle 1; cycle-2 fixes are doc/test refinements within the same task scope. |
| AC-5 — Status surfaces flip together | ✅ STILL MET | Spec `**Status:** ✅ Done.`; M21 README task-pool T18 row → `✅ Done`; G4 exit criterion landed in cycle 1; no surface drift in cycle 2. |
| TA-LOW-02 — Worktree cleanup for empty-diff case | ✅ STILL MET (strengthened) | Step 7 now explicitly covers BOTH empty-diff AND merged cleanup; new TestDocAnchors `test_worktree_cleanup_documented` pins this in CI. |

### LOW-1 status

LOW-1 (Step 1.6 hand-wave merge recipe) — UNCHANGED. Cycle 2 fixes addressed the empty-diff/merged cleanup mechanics (Step 6 now has the `git worktree remove` call), but the actual merge mechanism ("cherry-pick or merge") is still abstract. This was forward-flagged to T19 / first M22 multi-slice consumer; that disposition stands.

### Critical sweep (cycle 2)

- ACs that look met but aren't: none — all four fixes land cleanly with concrete file/line/test evidence.
- Silently skipped deliverables: none.
- Additions beyond spec: none — cycle 2 diff is scoped to the four files the cycle-2 plan named.
- Test gaps: closed by FIX-1 doc-anchors and FIX-2 round-trip.
- Doc drift: none — `auto-implement.md` updates are internally consistent; CHANGELOG anchor still accurate (same task).
- Status-surface drift: none — all 4 surfaces still aligned from cycle 1.
- Gate integrity: all gates re-run from scratch; the Builder's claimed counts match (1437 passed vs claimed 1437; 30 vs claimed 30).
- Architecture drift Phase 1 missed: none — pure procedure-doc + test edits, no `ai_workflows/` runtime touch.

### Verdict

✅ PASS — cycle 2 close-out. T18 ready to land.

---

## Security review (cycle 2) (2026-04-29)

### Scope

Cycle 2 diff reviewed: `.claude/commands/auto-implement.md` Step 5/6/7 worktree command corrections (misleading `git diff --name-only` block replaced with corrective prose; explicit `git worktree remove` added for both empty-diff and merged cases). `tests/test_t18_parallel_dispatch.py`: `TestDocAnchors` class added (3 doc-anchor assertions), `test_round_trip_spec_to_flag` added, two T17-duplicating tests removed. No changes to `ai_workflows/` runtime code, no new subprocess calls, no new network access, no new file I/O outside tests.

Threat model items assessed: (1) wheel contents, (2) subprocess integrity, (3) external workflow load path, (4) MCP bind address, (5) SQLite paths, (6) subprocess env leakage, (7) logging hygiene, (8) dependency CVEs.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

None. The ADV-1 from cycle 1 (prospective injection risk when `git worktree remove <worktree-path>` is eventually implemented in executable form) is unchanged in character — the Step 6/7 fix adds the command as prose documentation only, not executable code. The constraint stands: when an orchestrator implements this step in code, the worktree path must be passed as a positional argv element, not interpolated into a shell string. No new advisory items introduced by cycle 2 changes.

The `TestDocAnchors` class in `tests/test_t18_parallel_dispatch.py` reads `auto-implement.md` at test time (filesystem read, no subprocess, no network). No security implications.

### Verdict: SHIP

Cycle 2 changes are pure documentation corrections and test additions. Wheel contents unaffected (`.claude/` and `tests/` are not packaged). No subprocess calls added to the library. No credentials, API keys, or sensitive values introduced. Security profile is identical to cycle 1.

---

## Sr. Dev review (cycle 2) — 2026-04-29

**Files reviewed:** `.claude/commands/auto-implement.md` (Step 5/6/7, lines 380–406), `tests/test_t18_parallel_dispatch.py` (TestDocAnchors lines 395–433, test_round_trip_spec_to_flag line 182, TC-5 TestWorktreeCleanup)
**Skipped (out of scope):** `CHANGELOG.md`, milestone README, task spec status surface
**Verdict:** SHIP

### BLOCK — must-fix before commit

None.

### FIX — fix-then-ship

None. Both cycle 1 FIX findings are cleanly resolved:

- FIX-1: Step 5 bash block removed; replaced with per-worktree `git -C <worktree-path> diff --name-only HEAD` prose. The misleading main-tree command is gone.
- FIX-2: Step 6 ends with explicit `git worktree remove <worktree-path>` for merged worktrees. Step 7 now covers both cases (empty-diff and merged) with explicit commands and no "automatically" claim.

### Advisory — track but not blocking

**ADV-1 — `plan_worktree_cleanup` helper scope-limited to empty-diff paths; no merged-path counterpart tested** (`tests/test_t18_parallel_dispatch.py` line 118, lens: simplification)

The helper filters for `not has_changes` and its docstring (line 116) correctly notes merged-case cleanup lives in Step 6 of the doc. TC-5 has no test asserting that a `has_changes=True` + merged worktree is also cleaned up; that path is exercised only via `test_worktree_cleanup_documented` in TestDocAnchors. Not a bug — the helper was intentionally scope-limited. No action required now; flag-only for any future extension of `plan_worktree_cleanup` to the merged-path case.

### What passed review (one-line per lens)

- Hidden bugs: none — Step 5 fix is correct; Step 6/7 now cover all worktree states without gaps or contradictions.
- Defensive-code creep: none — `_load_auto_implement()` reads a real file at a guaranteed path; no defensive guards around a fixture that can't be absent in CI.
- Idiom alignment: `TestDocAnchors` matches the doc-anchor pattern established by `test_auto_implement_md_uses_builder_slice_naming` in TC-6; `tmp_path` fixture used for the round-trip test, consistent with project norm.
- Premature abstraction: none — `_load_auto_implement()` has three callers within the class; extraction is justified.
- Comment / docstring drift: `plan_worktree_cleanup` docstring (line 116) remains accurate after Step 6 update; no drift.
- Simplification: `TestDocAnchors._load_auto_implement()` reads once per test method (not cached); acceptable for a 3-call class with negligible I/O.

---

## Sr. SDET review (cycle 2) (2026-04-29)

**Test files reviewed:** `tests/test_t18_parallel_dispatch.py` (cycle 2 delta: `TestDocAnchors` class lines 395–433, `test_round_trip_spec_to_flag` line 182, removal of `test_spec_with_slice_scope_yields_eligible` + `test_parallel_path_produces_multiple_slices`)
**Skipped (out of scope):** cycle 1 findings FIX-1 and FIX-2 (resolved per locked terminal-gate decisions); `tests/test_t17_spec_format.py` (not modified by cycle 2)
**Verdict:** SHIP

### BLOCK — tests pass for the wrong reason

None.

### FIX — fix-then-ship

None.

### Advisory — track but not blocking

None introduced by cycle 2 delta. Cycle 1 ADV-1 through ADV-3 carry forward unchanged.

### What passed review (one-line per lens)

- Tests-pass-for-wrong-reason: `TestDocAnchors` assertions are non-vacuous — each anchored string (`≤4` at auto-implement.md line 368, `🚧 BLOCKED: parallel-Builder overlap detected` verbatim at line 389, `git worktree remove` at lines 399/404/405 and `empty-diff` at lines 402/404) is genuinely present in the doc; all three assertions would catch real constant or wording drift; none are tautologies.
- Coverage gaps: `test_round_trip_spec_to_flag` exercises the complete `write_meta_json` (`has_slice_scope_section` branch on `_SPEC_PARALLEL_ELIGIBLE`) → `read_parallel_eligible` path that the hand-crafted-dict test bypassed in cycle 1; gap is closed. The two removed tests were pure T17 duplicates with no T18-specific assertions; their removal introduces no coverage regression (T17 still covers `has_slice_scope_section` and `parse_slice_rows` directly).
- Mock overuse: no mocks used in cycle 2 delta; `tmp_path` fixture used correctly in `test_round_trip_spec_to_flag` — idiomatic upgrade from `tempfile.TemporaryDirectory` in sibling tests; addresses cycle 1 ADV-1.
- Fixture / independence: `TestDocAnchors._load_auto_implement()` is a pure filesystem read on a path derived from `__file__`; no shared mutable state; no order-dependence introduced; three separate test methods each call it independently with no cross-test side-effects.
- Hermetic-vs-E2E gating: all 30 tests remain fully hermetic; `TestDocAnchors` reads a local repo file, no network, no subprocess invocations.
- Naming / assertion-message hygiene: `test_round_trip_spec_to_flag` names the exact path under test; all three `TestDocAnchors` method names describe the specific doc contract being pinned; each assertion includes a failure message quoting the expected string for debuggability.
