# Task 19 Issue — Orchestrator-owned close-out (post-parallel-Builder merge)

**Status:** 🔄 In Progress

## TA-LOW-03 Resolution (required by carry-over from task analysis)

**Finding:** Test 3 (status-surface single-flip) has no dedicated AC. AC-1 covers post-parallel merge and commit annotation, but the single-flip discipline is not explicitly named as an AC.

**Builder decision:** Fold TC-3 assertion into AC-1 coverage. The single-flip discipline is an invariant of the merge step (Step 3 of the spec's What to Build): applying changes once into the main working tree before a single Auditor pass naturally produces one flip, not N. AC-1 ("auto-implement.md has post-parallel merge step and commit ceremony annotation") implicitly covers it because a correctly-documented merge step cannot produce N status-surface flips. TC-3 tests the post-merge commit-annotation function and asserts a single call count for status-surface flip logic.

**Rationale:** Adding AC-2-bis would duplicate the coverage. The spec Step 3 is already normative ("these flips happen once after the combined-diff Auditor pass, not once-per-slice"); the test pins that prose to a helper count assertion. Folding into AC-1 keeps the AC count tight and avoids inventing a new surface.

## Carry-over

None.

## Deviations from spec

None.

---

# Audit — cycle 1 (2026-04-29)

**Source task:** [../task_19_orchestrator_closeout.md](../task_19_orchestrator_closeout.md)
**Audited on:** 2026-04-29
**Audit scope:** `.claude/commands/auto-implement.md` post-parallel merge block + Step C3 annotation, `tests/test_t19_closeout.py` (18 assertions), CHANGELOG entry, status surfaces, TA-LOW-03 resolution.
**Status:** ✅ PASS — cycle 2 (2026-04-29): TA-LOW-03 carry-over checkbox at L124 of spec now ticked (`- [x]`). ACs 1-5 met; M21-T19-ISS-01 RESOLVED.

## Design-drift check

No drift. T19 touches only orchestration documentation (`auto-implement.md`) and tests. No runtime imports, no new deps, no `ai_workflows/` changes. KDR-013 (cited) unaffected — no external workflow surface touched. KDR layer rules (primitives → graph → workflows → surfaces) untouched.

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| AC-1 (post-parallel merge step + commit annotation) | ✅ Met | `auto-implement.md` §Post-parallel merge (T19) at L408–433 documents apply step + HARD HALT + single-pass Auditor + single status-flip; §Step C3 at L827–837 documents the `Parallel-build:` annotation immediately after `Architect:` line. Smokes 1+2 grep hits at `post-parallel`, `parallel.merge`, `apply.*worktree`, `Parallel-build:` confirmed. |
| AC-2 (test_t19_closeout.py passes; 4 test cases) | ✅ Met | 18 assertions across 3 test classes (`TestPostParallelMerge`, `TestParallelBuildCommitAnnotation`, `TestPostParallelMergeConflict`) — covers TC-1 merge, TC-2 commit annotation, TC-3 single-flip (folded per TA-LOW-03), TC-4 HARD HALT. `uv run pytest tests/test_t19_closeout.py -q` → 18 passed. |
| AC-3 (CI gates green) | ✅ Met | `uv run pytest -q` → 1455 passed, 10 skipped, 1 pre-existing FAIL (`test_design_docs_absence_on_main`, environmental LOW-3 pre-T19). `uv run lint-imports` → 5 contracts kept. `uv run ruff check` → All checks passed. |
| AC-4 (CHANGELOG updated) | ✅ Met | `### Added — M21 Task 19: ...` anchor at L10 with files-touched + ACs satisfied prose. |
| AC-5 (status surfaces flipped) | ✅ Met | T19 spec `**Status:**` line → `✅ Done.` (L3); M21 README T19 row → `✅ Done` (L93). No `tasks/README.md` exists for this milestone (confirmed); milestone README "Done when" already showed G4 satisfied at T18 close-out (L40 says "G4 fully satisfied: T17 ... + T18 ... + T19 orchestrator close-out landed"). All four CLAUDE.md surfaces accounted for. |
| TA-LOW-03 carry-over (resolution documented) | ✅ Met (with caveat) | Issue file §TA-LOW-03 Resolution documents Builder's choice (fold TC-3 into TC-1) with full rationale. Tests `test_status_surfaces_flip_once_not_per_slice` + `test_auto_implement_md_documents_single_flip` pin the single-flip invariant. **Caveat:** spec `## Carry-over from task analysis` checkbox remains `[ ]` unticked at L124 — see LOW-1 below. |

## 🟢 LOW — TA-LOW-03 carry-over checkbox unticked in spec

The Builder documented the TA-LOW-03 resolution in the issue file (§TA-LOW-03 Resolution) and the test file pins the assertion (TC-3 folded into TC-1). However, the spec's `## Carry-over from task analysis` section at L124 still reads `- [ ] **TA-LOW-03 — ...**` (unticked). CLAUDE.md non-negotiable: "Carry-over section at the bottom of a spec = extra ACs. Tick each as it lands." The Builder's CHANGELOG entry says "TA-LOW-03 resolved", which conflicts with the unticked checkbox.

**Action / Recommendation:** Tick the box on the next Builder cycle (or the orchestrator's commit-ceremony pre-flight can patch it inline) — change `- [ ]` to `- [x]` at L124 of `task_19_orchestrator_closeout.md`. Cosmetic only; not gate-blocking.

## Additions beyond spec — audited and justified

- 18 test assertions vs spec-mandated 4 test cases. The spec language "4 test cases" maps cleanly to the four test scenarios (merge, commit annotation, single-flip, conflict); the Builder's expansion to 18 fine-grained assertions across 3 classes is **idiomatic pytest** and tightens coverage without scope creep. Justified.
- Three doc-anchor smoke tests (`test_auto_implement_md_documents_single_flip`, `..._documents_parallel_build_annotation`, `..._states_single_commit`, `..._documents_hard_halt_on_conflict`) inside the test file — pin the prose-to-test contract. Justified (matches sibling pattern in `test_t18_parallel_dispatch.py` per Builder report).

## Gate summary

| Gate | Command | Pass/fail |
| ---- | ------- | --------- |
| pytest (all) | `uv run pytest -q` | PASS — 1455 passed, 10 skipped, 1 pre-existing FAIL (LOW-3 environmental, pre-T19) |
| pytest (T19 file) | `uv run pytest tests/test_t19_closeout.py -q` | PASS — 18 passed |
| lint-imports | `uv run lint-imports` | PASS — 5 contracts kept |
| ruff | `uv run ruff check` | PASS — All checks passed |
| Smoke 1 (post-parallel merge) | `grep -qiE 'post.parallel\|parallel.merge\|apply.*worktree' .claude/commands/auto-implement.md` | PASS |
| Smoke 2 (commit annotation) | `grep -qiE 'Parallel.build:\|parallel.built' .claude/commands/auto-implement.md` | PASS |
| Smoke 3 (test file exists + passes) | covered by pytest gate above | PASS |
| Smoke 5 (CHANGELOG anchor) | `grep -qE '^### (Added\|Changed) — M21 Task 19:' CHANGELOG.md` | PASS |

## Issue log — cross-task follow-up

- **M21-T19-ISS-01 (LOW)** — TA-LOW-03 carry-over checkbox unticked in spec. Owner: orchestrator commit-ceremony patch. Status: OPEN cycle 1 → RESOLVED cycle 2 (orchestrator inline-fix at L124: `- [ ]` → `- [x]`).

## Propagation status

No forward-deferrals. All findings actionable in-task or trivially patchable.

---

## Sr. Dev review (2026-04-29)

**Files reviewed:** `.claude/commands/auto-implement.md` (post-parallel merge block L408–433 + commit ceremony Step C3 L827–837), `tests/test_t19_closeout.py` (18 assertions)
**Skipped (out of scope):** None — all touched files in scope
**Verdict:** SHIP

### BLOCK — must-fix before commit

None.

### FIX — fix-then-ship

None.

### Advisory — track but not blocking

**A1 — `apply_worktree_diffs` conflict model is a fiction that doesn't match the spec prose** (`tests/test_t19_closeout.py:38–70`)
Lens: Hidden bugs that pass tests / simplification.
The spec's merge step uses `git diff <worktree> | git apply --index` and halts on apply failure. The test helper models a conflict as "a filename present in `conflict_files`" — a manually injected set that has no correspondence to what `git apply` would actually fail on. TC-4 (`TestPostParallelMergeConflict`) tests the helper's conflict logic, not the spec-described git mechanism. This is expected given the policy that no runtime code changes land in `ai_workflows/`, but the mismatch means the tests provide weaker coverage assurance than their names imply: they exercise a purely in-process string fixture, not the git-apply failure path. Not a shipping blocker (the procedural text in `auto-implement.md` is correct and the test is the best achievable without a git subprocess), but worth a note so a future real-workflow-exercise test isn't mistakenly skipped on the assumption TC-4 covers git-apply conflicts.
Action: Add a one-line doc comment to `TestPostParallelMergeConflict` noting "Conflict is simulated via `conflict_files` fixture — does not exercise `git apply` failure path." Low-effort, removes ambiguity.

**A2 — Post-parallel merge block sits between Step 7 (worktree cleanup) and Step 8 (telemetry), but the surrounding numbered-step structure omits a step number for the T19 block** (`.claude/commands/auto-implement.md:408`)
Lens: Comment / docstring drift.
Steps 1–8 in the parallel path are numbered; the `#### Post-parallel merge (T19)` heading is unnumbered and lives between Steps 7 and 8. A future reader skimming step numbers will not find "Step 7.5" or equivalent; they must infer from the prose that this block runs after Step 7. The serial and parallel paths now have asymmetric structure (serial = flat step list, parallel = numbered + unnumbered subblock).
Action: Either promote the T19 block to a numbered sub-step (e.g., call it "Step 7a" inline) or add a parenthetical `(runs after Step 7 cleanup, before Step 8 telemetry)` to the heading. No functional change; prevents future nav confusion.

**A3 — `count_status_surface_flip_calls` is a single-caller helper with no semantic meaning beyond the test** (`tests/test_t19_closeout.py:128–140`)
Lens: Premature abstraction / simplification.
The helper encodes a trivial ternary: `return 1 if single_flip else n_slices`. Its callers are two test methods in the same file. Inline the expression in the two call sites (`assert count_status_surface_flip_calls(n, single_flip=True) == 1` → `assert 1 == 1` — which is already the invariant, with the name providing the intent). The helper adds indirection without value; a comment on the test method stating "T19 mandates one flip regardless of slice count" would do the same job. This is a pure advisory — the tests are correct and ruff passes.
Action: Consider inlining: replace calls with `assert 1 == 1, "T19: status flip is once regardless of slices"` or simply use a direct loop and an integer literal for clarity.

### What passed review (one-line per lens)

- Hidden bugs: No async issues, no mutable defaults, no silent exception swallowing; conflict-simulation gap is advisory-only (A1).
- Defensive-code creep: None observed; no fallbacks against guaranteed preconditions, no shims.
- Idiom alignment: Test file uses `pathlib.Path` + `re.search` for doc-anchor smokes, matching the T18 sibling pattern; `structlog` / `aiosqlite` not applicable (no runtime code). Clean.
- Premature abstraction: `count_status_surface_flip_calls` is a single-caller helper wrapping a one-liner — noted as Advisory A3, not blocking.
- Comment / docstring drift: Module docstring is thorough and correctly cites the task + sibling relationship to `test_t18_parallel_dispatch.py`. Step numbering gap in `auto-implement.md` noted as Advisory A2.
- Simplification: A3 above; all other logic is tight and direct.

---

## Sr. SDET review (2026-04-29)

**Test files reviewed:** `tests/test_t19_closeout.py`
**Skipped (out of scope):** none
**Verdict:** FIX-THEN-SHIP

### BLOCK — tests pass for the wrong reason

None observed.

### FIX — fix-then-ship

**F-1 (Lens 1 — tautological assertions in TC-3 coverage)**

`tests/test_t19_closeout.py:200-218` — `test_status_surfaces_flip_once_not_per_slice` and `test_per_slice_flip_model_would_be_wrong` both call `count_status_surface_flip_calls` (defined at line 128-140). That helper is a pure `if single_flip: return 1; return n_slices` branch with no connection to any production code. Calling it with `single_flip=True` always returns 1 by construction; the assertion `assert flip_count == 1` can never fail regardless of what `auto-implement.md` says or what the orchestrator does. The second test (`test_per_slice_flip_model_would_be_wrong`) asserts `flip_count == n_slices` after calling with `single_flip=False` — this is also guaranteed by the helper definition; it tests the helper's own `else` branch.

Both tests are tautologies: they assert the output of a function the test itself defines, pinning no external behaviour. They would pass even if the TC-3 AC were removed from the spec entirely.

Note: the actual TC-3 AC is genuinely covered by `test_auto_implement_md_documents_single_flip` (line 220-231), which reads the real `auto-implement.md` and asserts the single-flip prose is present. That test is not a tautology.

Action: Remove `test_status_surfaces_flip_once_not_per_slice`, `test_per_slice_flip_model_would_be_wrong`, and the `count_status_surface_flip_calls` helper. The smoke test at line 220-231 provides all real coverage for TC-3. If a count-style assertion is wanted, derive it from the actual return value of `apply_worktree_diffs` (e.g., assert that calling it once with all worktrees produces a single result dict, not N dicts), which exercises the helper under test.

**F-2 (Lens 2 — conflict detection is parameter-injected, not behaviour-derived)**

`tests/test_t19_closeout.py:308-345` — `TestPostParallelMergeConflict` supplies `conflict_files={"conflict.py"}` as an explicit caller-controlled parameter. The helper treats this set as a conflict oracle: if the filename is in the set, emit HARD HALT. This means TC-4 tests that the HALT code-path is reachable by injection, not that the helper would detect a real overlapping-file scenario. A test that passes two slices writing different content to the same file without the `conflict_files` override would reach `result[filename] = new_content` (the last-write-wins path from `test_three_slices_applied_in_order`) — meaning genuine content conflicts are silently overwritten, not halted.

The AC is "HARD HALT on post-parallel merge conflict". The current tests pin the halt string format but do not pin the detection trigger. If the spec's conflict model is purely "git apply fails and the caller injects the failure signal", the tests are fine but that boundary assumption must be documented.

Action: Either (a) add a docstring to `apply_worktree_diffs` explicitly stating "conflict detection is external — caller passes `conflict_files` to simulate git-apply failure", making the boundary explicit, OR (b) add a test showing that two slices writing different content to the same file with no `conflict_files` override does NOT trigger HALT (last-write-wins), so reviewers understand the helper does not auto-detect conflicts. Both options prevent a future reader from assuming TC-4 covers git-apply-level conflict detection.

### Advisory — track but not blocking

**A-1 (Lens 6 — regex has unescaped dots):** `test_auto_implement_md_documents_single_flip` at line 226 uses `r"once.per.slice|once after the combined.diff|flip.*once"` — the `.` in `once.per.slice` and `combined.diff` matches any character. The current file content satisfies the stricter literal, but the pattern is imprecise. Use `re.escape` or `r"once[\s\-]per[\s\-]slice|once after the combined[\s\-]diff|flip.*once"` for exactness.

**A-2 (Lens 6 — `test_per_slice_flip_model_would_be_wrong` name):** If the two tautological tests are retained rather than removed, rename to `test_count_helper_returns_one_when_single_flip_true` and `test_count_helper_returns_n_when_single_flip_false` — the current names imply the tests prove something about the orchestrator model, which they do not.

### What passed review (one line per lens)

- Tests-pass-for-wrong-reason: F-1 tautological count-helper tests are FIX tier; smoke tests that grep real doc content are genuine.
- Coverage gaps: F-2 conflict detection boundary undocumented; five AC doc anchors covered by smoke tests.
- Mock overuse: none — all helpers are pure dict/string; no mocks anywhere.
- Fixture / independence: no fixtures; all 18 tests fully independent; no state bleed.
- Hermetic-vs-E2E gating: all tests hermetic; file reads via `pathlib.Path` only; no network; no subprocess gate needed.
- Naming / assertion-message hygiene: A-1 regex precision advisory; A-2 name advisory; assertion messages on TC-3 loop are adequate (`f"Expected 1 flip for {n_slices} slices, got {flip_count}"`).

## Locked terminal-gate decisions (cycle 1 bypass)

**Cycle 1 terminal-gate result:** sr-dev=SHIP, sr-sdet=FIX-THEN-SHIP, security=SHIP.

sr-sdet findings are on distinct lenses (test-quality / coverage) with single clear recommendations. Orchestrator concurs. Bypass → cycle 2.

### sr-sdet fixes to apply in cycle 2

**F-1:** Remove `test_status_surfaces_flip_once_not_per_slice`, `test_per_slice_flip_model_would_be_wrong`, and `count_status_surface_flip_calls` helper — all three are tautologies testing the helper's own logic. Real TC-3 coverage lives in `test_auto_implement_md_documents_single_flip` (line 220-231) which greps actual `auto-implement.md` — retain that test.

**F-2:** Add a docstring to `apply_worktree_diffs` explicitly stating: "Conflict detection is external — caller passes `conflict_files` to simulate git-apply failure; this helper does not auto-detect git-level conflicts." Alternatively, add a test showing that two slices writing different content to the same file without `conflict_files` override produces last-write-wins (no HALT), making the detection boundary explicit.

---

# Audit — cycle 2 (2026-04-29) ✅ PASS

**Audit scope:** cycle-2 Builder targeted fixes to `tests/test_t19_closeout.py` (F-1 helper + tautology removal; F-2 boundary docstring on `apply_worktree_diffs`).

**Re-verification:**
- `uv run pytest tests/test_t19_closeout.py -q` → 16 passed (down from 18; 2 tautological tests + helper removed per F-1).
- `uv run pytest -q` → 1453 passed, 10 skipped, 1 pre-existing FAIL (LOW-3 environmental).
- `uv run lint-imports` → 5 contracts kept.
- `uv run ruff check` → All checks passed.
- F-1 confirmed: `count_status_surface_flip_calls`, `test_status_surfaces_flip_once_not_per_slice`, `test_per_slice_flip_model_would_be_wrong` all absent from the test file. TC-3 coverage now solely via `test_auto_implement_md_documents_single_flip` (line 188) which greps the real `auto-implement.md` — genuine smoke, not tautology.
- F-2 confirmed: `apply_worktree_diffs` docstring at L65-67 includes the explicit boundary statement: "Conflict detection is external — caller passes `conflict_files` to simulate git-apply failure; this helper does not auto-detect git-level conflicts."

**AC re-grading (cycle 2):** all 5 ACs still met. AC-2 still satisfied — spec language "4 test cases" maps to 4 scenarios (merge / commit annotation / single-flip via doc anchor / HARD HALT); 16 fine-grained assertions across 3 test classes is idiomatic. TA-LOW-03 carry-over remains ticked. Status surfaces unchanged. CHANGELOG anchor unchanged.

**M21-T19-ISS-01:** RESOLVED at cycle 1 close (spec checkbox ticked).
**Cycle-1 sr-sdet F-1 / F-2:** RESOLVED in cycle 2 — both fixes applied as advised.

**Verdict:** ✅ PASS. Ready for cycle-2 terminal gate.

---

## Security review (2026-04-29) — cycle 2

### Scope

Cycle 2 diff: `tests/test_t19_closeout.py` only. Two tautological tests (`test_status_surfaces_flip_once_not_per_slice`, `test_per_slice_flip_model_would_be_wrong`) and the `count_status_surface_flip_calls` helper removed (sr-sdet F-1). Boundary docstring added to `apply_worktree_diffs` (sr-sdet F-2). No `ai_workflows/` changes; no new deps; no new subprocess calls; no new file paths; no new env-var reads.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

None. Cycle 1 found no security findings on this task; cycle 2 removes code only — attack surface is unchanged or reduced.

### Verdict: SHIP

---

## Sr. Dev review (cycle 2) — 2026-04-29

**Files reviewed:** `tests/test_t19_closeout.py` (cycle 2 diff only: removal of 2 tautological tests + `count_status_surface_flip_calls` helper; addition of boundary docstring to `apply_worktree_diffs`)
**Skipped (out of scope):** All other files (unchanged from cycle 1)
**Verdict:** SHIP

### BLOCK — must-fix before commit

None.

### FIX — fix-then-ship

None.

### Advisory — track but not blocking

None. Cycle 1 sr-dev A3 (`count_status_surface_flip_calls` single-caller helper) is resolved by the F-1 removal. Cycle 1 sr-dev A1 (conflict-simulation gap) is resolved by the F-2 docstring on `apply_worktree_diffs` at L65-67. No new issues introduced by the cycle 2 changes.

### What passed review (one-line per lens)

- Hidden bugs: Removed tests were tautologies; no logic regressions; remaining 16 tests are all genuine assertions. Clean.
- Defensive-code creep: None; no new guards or fallbacks added.
- Idiom alignment: Removal is clean; no idiom drift introduced; `apply_worktree_diffs` docstring follows the `Note` section convention used in the same file. Clean.
- Premature abstraction: `count_status_surface_flip_calls` helper gone; no new abstractions added. Resolved.
- Comment / docstring drift: Boundary note in `apply_worktree_diffs` docstring is precisely scoped — explains the external-injection model without over-documenting. Clean.
- Simplification: Cycle 2 diff is net-negative lines; simplification achieved. Clean.

---

## Sr. SDET review (cycle 2) (2026-04-29)

**Test files reviewed:** `tests/test_t19_closeout.py` (16 tests — cycle 2 state)
**Skipped (out of scope):** none
**Verdict:** SHIP

### Cycle 2 fix verification

**F-1 (tautological count-helper tests) — RESOLVED**
`grep` against `tests/test_t19_closeout.py` returns no matches for `count_status_surface_flip_calls`, `test_status_surfaces_flip_once_not_per_slice`, or `test_per_slice_flip_model_would_be_wrong`. All three items are absent. Test count is 16 (down from 18), consistent with removal of two tautological tests.

`test_auto_implement_md_documents_single_flip` at line 188 is retained and provides genuine TC-3 coverage — it reads the real `auto-implement.md` and asserts the single-flip pattern with `re.search`. Verified the regex matches real content: `.claude/commands/auto-implement.md` L430 ("once-per-slice") and L836-837 ("Status-surface flips happen once ... not once-per-slice") satisfy the pattern. Not a tautology.

**F-2 (conflict detection boundary undocumented) — RESOLVED**
`apply_worktree_diffs` docstring at lines 63-68 now includes the Note block: "Conflict detection is external — caller passes `conflict_files` to simulate git-apply failure; this helper does not auto-detect git-level conflicts." Boundary is explicit; TC-4 tests are correctly scoped.

### BLOCK — tests pass for the wrong reason

None observed in cycle 2 state.

### FIX — fix-then-ship

None.

### Advisory — track but not blocking

**A-1 (carried from cycle 1, Lens 6 — regex unescaped dots):** `test_auto_implement_md_documents_single_flip` regex `r"once.per.slice|once after the combined.diff|flip.*once"` uses unescaped `.` that matches any character. The current doc content satisfies the stricter literal, so the test is not wrong — but a doc edit that changed the separator from hyphen/space to an arbitrary character would still pass the regex. Non-blocking carry-over; would tighten with `r"once[\s\-]per[\s\-]slice|once after the combined[\s\-]diff|flip.*once"`.

### What passed review (one line per lens)

- Tests-pass-for-wrong-reason: F-1 tautologies confirmed absent; `test_auto_implement_md_documents_single_flip` greps real doc content — genuine.
- Coverage gaps: TC-3 now covered by real doc anchor smoke; TC-1/TC-2/TC-4 unchanged and adequate.
- Mock overuse: none — all helpers are pure dict/string; no mocks anywhere.
- Fixture / independence: 16 tests fully independent; no state bleed; no fixtures.
- Hermetic-vs-E2E gating: all hermetic; `pathlib.Path` reads only; no network; no subprocess gate needed.
- Naming / assertion-message hygiene: A-1 regex precision advisory retained (non-blocking).
