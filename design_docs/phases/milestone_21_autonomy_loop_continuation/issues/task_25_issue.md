# Task 25 — Periodic skill / scheduled-task efficiency audit — Audit Issues

**Source task:** [../task_25_periodic_skill_audit.md](../task_25_periodic_skill_audit.md)
**Audited on:** 2026-04-29
**Audit scope:** Builder cycle 1 — `scripts/audit/skills_efficiency.py` (new, 164 lines), `.claude/commands/audit-skills.md` (new), `.claude/skills/{ai-workflows,dep-audit}/SKILL.md` frontmatter additions, `.github/workflows/ci.yml` step, `tests/test_t25_skills_efficiency.py` (new, 19 tests), CHANGELOG, T24 issue file deferral closure, status surfaces (spec line 3, README row 75, README §G5 audit-prompt half).
**Status:** ✅ PASS (cycle 1 / 1)

## Auditor verdict (cycle 1)

Re-ran every smoke step and gate from scratch against pre-task SHA `2e21021..HEAD`. All nine smoke steps PASS. T25 unit tests = 19/19 (Builder report cited 18; on-disk = 19). Full pytest suite under `AIW_BRANCH=design` = 1328 passed / 7 skipped (no regressions; the apparent `tests/test_main_branch_shape.py::test_design_docs_absence_on_main` failure on `workflow_optimization` without the env var is a pre-existing branch-shape sentinel, not a T25 regression — same disposition as T24 cycle 1). `lint-imports` clean (5 contracts kept, 0 broken). `ruff check` clean. CI step wired (md_discoverability against `.claude/agents/` + `agent_docs/`, skills_efficiency against `.claude/skills/`). Both existing Skills carry `allowed-tools: Bash` frontmatter on line 4. Audit script is 164 lines (well under the 200-line budget). Slash command body has all four required `##` anchors (Inputs, Procedure, Outputs, Return schema). T10 invariant = 9/9, T24 invariant zero-exit. CHANGELOG anchor present.

## Design-drift check

No drift detected. Task is autonomy-infra only (`.claude/`, `scripts/audit/`, `.github/`, `tests/`, `design_docs/`). No `ai_workflows/` package code modified. No KDR-relevant patterns introduced. No `nice_to_have.md` adoption. M21 scope-note (KDR drift checks apply) honoured — none of the seven load-bearing KDRs (002/003/004/006/008/009/013) is touched. Audit script imports only stdlib (`argparse`, `re`, `sys`, `pathlib`); no `anthropic` SDK, no LiteLLM, no provider code.

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| AC1: skills_efficiency.py exists, two CI-gated --check flags + all-aggregate, exits 1 on findings, exits 0 on clean, ≤200 lines | ✅ met | 164 lines (`awk 'END {print NR}'`); both checks + aggregate exit 0 against live; synthetic violation paths exit 1 with "Rule N FAIL" output; invalid-target exits 2. |
| AC2: audit-skills.md exists with four required ## section anchors | ✅ met | All four anchors present (smoke step 9). |
| AC2b: Both existing Skills carry `allowed-tools:` frontmatter | ✅ met | `ai-workflows/SKILL.md:4` and `dep-audit/SKILL.md:4` both `allowed-tools: Bash`. |
| AC3: CI workflow wires both audit scripts | ✅ met | `.github/workflows/ci.yml:38-42` runs md_discoverability against `.claude/agents/` + `agent_docs/` and skills_efficiency against `.claude/skills/`. |
| AC4: tests/test_t25_skills_efficiency.py exists, covers all checks + all-aggregate, exits 0 | ✅ met | 19 tests, all passing in 0.72s. Covers existence, line-count, importability, invalid-target, live-skills (3 paths), synthetic-violation rule fires (both rules), synthetic-clean rule passes (both rules), allowed-tools ok-path, single-tool no-false-positive, AC2b live frontmatter (both Skills), AC2 anchors, AC3 CI wiring (both scripts), AC7 CHANGELOG anchor. |
| AC5: T24 issue file's TA-LOW-02 marked RESOLVED with reference to T25 commit | ✅ met | T24 issue file §M21-T24-ISS-01 (line 94) reads "Status: RESOLVED at T25 — `scripts/audit/md_discoverability.py --check section-budget --target .claude/agents/` and `--target agent_docs/` are now wired in `.github/workflows/ci.yml` (M21 Task 25 commit)." Cycle commit not yet landed (autonomy-mode close-out happens at orchestrator commit step); SHA fold-in occurs at `/auto-implement` close. |
| AC6: T10 invariant held (smoke step 5 = 9) | ✅ met | 9/9 agents reference `_common/non_negotiables.md`. |
| AC7: T24 invariant held (smoke step 6 zero-exit) | ✅ met | `md_discoverability.py --check section-budget --target .claude/agents/` exits 0; "OK: section-budget — all 12 file(s) pass". |
| AC8: CHANGELOG.md updated under [Unreleased] | ✅ met | `### Added — M21 Task 25:` anchor on CHANGELOG.md:10. |
| AC9a: T25 spec Status → ✅ Done | ✅ met | spec line 3. |
| AC9b: M21 README task row 75 Status → ✅ Done | ✅ met | README row 75 final column. |
| AC9c: M21 README §G5 audit-prompt half amended in-place | ✅ met | README line 41 carries both T25 satisfaction parenthetical (`(satisfied at T25; /audit-skills + scripts/audit/skills_efficiency.py landed; CI walks both audit scripts every PR)`) and the existing T26 two-prompt half (`(satisfied at T26; pattern locked, agent_docs/ created)`). T26's lane preserved per spec. |
| Carry-over TA-LOW-01 (awk pattern) | ✅ met | Spec smoke step 8 uses `awk 'END { exit !(NR <= 200) }' …`. Test file uses `len(lines) <= 200` (pure Python equivalent). |
| Carry-over TA-LOW-02 (operator-only heuristics implementation choice) | ✅ met | Builder elected slash-command-prose-only — no Python implementation in skills_efficiency.py for tool-roundtrips/file-rereads. Documented in audit-skills.md §Procedure Steps 2–3. Per TA-LOW-02 recommendation, no unit-test coverage required. |
| Carry-over TA-LOW-03 (screenshot-overuse framing) | ✅ met | Audit-script module docstring (lines 6–10) documents the choice to generalize the adjacency regex to `text-extraction\|parse\|extract\|read.*text` instead of Anthropic's `get_page_text` tool name verbatim. |
| Cross-spec deferral T24 TA-LOW-02 (CI hookup for md_discoverability.py) | ✅ met | T24 issue file §M21-T24-ISS-01 marked RESOLVED at T25 (line 94). |
| Cross-spec deferral T12 §Out of scope (CI gate for Skill discovery / well-formedness) | ✅ met | `missing-tool-decl` heuristic + Step 3 CI integration provide the well-formedness gate. Documented in this issue file §Cross-spec deferrals closed. |

## Cross-spec deferrals closed

### T24 TA-LOW-02 — CI hookup for scripts/audit/md_discoverability.py
**Status: RESOLVED at T25.** `scripts/audit/md_discoverability.py --check section-budget` now runs in `.github/workflows/ci.yml:40-41` against both `.claude/agents/` and `agent_docs/`. T24 issue file §M21-T24-ISS-01 updated to RESOLVED.

### T12 §Out of scope — CI gate for Skill discovery / well-formedness
**Status: RESOLVED at T25.** The `missing-tool-decl` check in `scripts/audit/skills_efficiency.py` provides the well-formedness gate; `--check all` runs in CI on every PR via `.github/workflows/ci.yml:42`.

## Carry-over disposition (from task spec)

- **TA-LOW-01** (smoke-step 8 awk pattern): Applied. Smoke step 8 spec text uses `awk 'END { exit !(NR <= 200) }' scripts/audit/skills_efficiency.py`; test file uses `len(lines) <= 200` (pure-Python equivalent — no Bash command-substitution risk).
- **TA-LOW-02** (operator-only heuristics implementation choice): Builder chose slash-command-prose-only for `tool-roundtrips` and `file-rereads`. Spec recommendation said either choice acceptable; no unit-test coverage required for prose-only path. Documented in `.claude/commands/audit-skills.md` §Procedure Steps 2 + 3.
- **TA-LOW-03** (`screenshot-overuse` framing): Builder generalized the adjacency regex to `text-extraction\|parse\|extract\|read.*text` rather than the Anthropic Computer Use tool name `get_page_text` verbatim. Documented in `scripts/audit/skills_efficiency.py` module docstring lines 6–10.

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

**M21-T25-ISS-01 (LOW)** — Issue-file count mismatch in Builder report. Builder report (and CHANGELOG line 12) said the test file contains "18 tests"; on-disk pytest discovery shows **19 tests passing**. Not a behavioral discrepancy (the suite is more thorough, not less), but the Builder cycle's quoted count drifted from the artifact. Same flavour of count-discrepancy was logged in T24 cycle 1 as M21-T24-ISS-03 (Builder cited 240 lines for a 149-line script). Pattern is the same: Builder composes AC notes from memory rather than from the artefact. Owner: standing Builder discipline reminder; no per-task action. Action / Recommendation: Builder should `wc -l` / pytest-discover before composing AC count claims; the count is non-load-bearing here (AC4 says "covers all four checks + the all-aggregate path", not "exactly N tests"), so no edits required to ship.

## Additions beyond spec — audited and justified

- `tests/test_t25_skills_efficiency.py` includes one test beyond what the spec literally requires (the `test_missing_tool_decl_ok_when_only_one_tool` no-false-positive guard at line 250-272). Justified — the spec specifically tightened the `missing-tool-decl` heuristic at Step 1 to "only count tool-name occurrences inside fenced code blocks or at the start of bullets" precisely to avoid false positives against documentation prose; the no-false-positive test directly guards that tightening. In scope.
- Audit script defines a hardcoded `_TOOL_NAMES` list at lines 33-37 covering Anthropic-tool-name canonical surfaces (`Read`, `Write`, `Edit`, `Bash`, `ToolSearch`, `WebFetch`, `Screenshot`) plus the four MCP tools (`run_workflow`, `resume_run`, `list_runs`, `cancel_run`). Justified — the spec calls for a heuristic, and a heuristic needs a concrete tool-name surface to detect. The MCP-tool inclusion is correct (KDR-008 contract) and the Anthropic-tool surface matches what real Skills would invoke.

## Gate summary

| Gate | Command | Result |
| ---- | ------- | ------ |
| pytest (full, with branch env) | `AIW_BRANCH=design uv run pytest -q` | PASS — 1328 passed, 7 skipped, 22 warnings |
| pytest (T25 unit suite) | `uv run pytest tests/test_t25_skills_efficiency.py -q` | PASS — 19/19 in 0.72s |
| lint-imports | `uv run lint-imports` | PASS — 5 contracts kept, 0 broken |
| ruff | `uv run ruff check` | PASS — All checks passed |
| smoke 1 (script + slash command exist) | `test -f scripts/audit/skills_efficiency.py && test -f .claude/commands/audit-skills.md` | PASS |
| smoke 2 (each --check flag against live skills) | three `uv run python scripts/audit/skills_efficiency.py --check {screenshot-overuse|missing-tool-decl|all} --target .claude/skills/` invocations | PASS — all three exit 0 ("all 3 skill file(s) pass") |
| smoke 2b (existing-Skill frontmatter) | `grep -qE '^allowed-tools:' .claude/skills/{ai-workflows,dep-audit}/SKILL.md` | PASS — both files |
| smoke 3 (CI step wired) | `grep -qE 'scripts/audit/{md_discoverability,skills_efficiency}\.py' .github/workflows/ci.yml` | PASS — both grep'd |
| smoke 4 (test file passes) | `uv run pytest tests/test_t25_skills_efficiency.py -q` | PASS — 19/19 |
| smoke 5 (T10 invariant) | `grep -lF '_common/non_negotiables.md' .claude/agents/*.md \| count` | PASS — 9/9 |
| smoke 6 (T24 invariant) | `uv run python scripts/audit/md_discoverability.py --check section-budget --target .claude/agents/` | PASS — exit 0, "all 12 file(s) pass" |
| smoke 7 (CHANGELOG anchor) | `grep -qE '^### (Added\|Changed) — M21 Task 25:' CHANGELOG.md` | PASS — line 10 |
| smoke 8 (audit-script line budget) | `awk 'END { exit !(NR <= 200) }' scripts/audit/skills_efficiency.py` | PASS — 164 ≤ 200 |
| smoke 9 (slash-command anchors) | `grep -E '^## (Inputs\|Procedure\|Outputs\|Return schema)' .claude/commands/audit-skills.md` | PASS — all four printed |

## Status-surface integrity

All four surfaces flipped together at audit close:
- (a) T25 spec **Status:** line — `✅ Done.` (spec line 3) ✅
- (b) M21 README task table row 75 — `✅ Done` (README line 75 final column) ✅
- (c) `tasks/README.md` — N/A (M21 has no separate `tasks/README.md`; per non-negotiables the surface only applies "if the milestone has one") ✅
- (d) M21 README §G5 audit-prompt half — amended in-place with `(satisfied at T25; /audit-skills + scripts/audit/skills_efficiency.py landed; CI walks both audit scripts every PR)` parenthetical (README line 41) ✅. T26 two-prompt half preserved untouched, per spec note "Do NOT amend the two-prompt half (that was T26's lane)".

## Issue log — cross-task follow-up

- **M21-T25-ISS-01** (LOW) — Builder-report test-count drift (cited 18; on-disk 19). RESOLVED at audit; no action. Standing Builder discipline reminder pattern (sibling of M21-T24-ISS-03).

## Deferred to nice_to_have

None. T25 closed two prior cross-spec deferrals (T24 TA-LOW-02 + T12 §Out of scope). No new deferrals open.

## Propagation status

No forward-deferrals to propagate. Cross-spec inbound deferrals closed:
- T24 TA-LOW-02 → T24 issue file §M21-T24-ISS-01 marked RESOLVED at T25.
- T12 §Out of scope → closed via `missing-tool-decl` heuristic + CI step; documented in this issue file §Cross-spec deferrals closed.

## Sr. SDET review (2026-04-29)

**Test files reviewed:** `tests/test_t25_skills_efficiency.py` (19 tests)
**Skipped (out of scope):** none
**Verdict:** SHIP

### BLOCK — tests pass for the wrong reason

None observed.

### FIX — fix-then-ship

None.

### Advisory — track but not blocking

**ADV-01 (Lens 2 — coverage gap, `\bimage\b` trigger path)**
`tests/test_t25_skills_efficiency.py` — no test exercises the `\bimage\b` branch of `_SCREENSHOT_IMG_RE` (line 46 of `scripts/audit/skills_efficiency.py`).

The spec states the rule fires on "mentions of `screenshot` or `image` without an adjacent text-extraction reference." The two keywords share the same code path in `check_screenshot_overuse` (lines 98-107), so the existing `test_screenshot_overuse_fires_on_violation` test does exercise the function. However, `image` is a higher false-positive risk word (common English) than `screenshot`, and the adjacency suppression logic (`_screenshot_has_adjacent_text_extraction`) is never verified specifically for `image`-triggered matches.

Action: add a synthetic-fixture test that writes a SKILL.md containing `image` (without a text-extraction adjacency reference) and asserts `exit 1` + `Rule 1 FAIL`. Optionally add a second synthetic fixture where `image` appears adjacent to `parse` and asserts `exit 0`. Neither is blocking because the current live skills contain no `image` occurrences and the code path is shared.

**ADV-02 (Lens 6 — test naming nit)**
`tests/test_t25_skills_efficiency.py:79` — `test_audit_script_importable` asserts `callable(getattr(module, "main", None))`. The assertion checks presence and callability of `main`, which is correct for the AC ("importable as a Python module"), but the test name says "importable" when what's really being verified is "importable AND has a callable main". The name is slightly underselling. Not a behavior concern.

Action: consider renaming to `test_audit_script_importable_and_has_main_callable` for clarity; no behavior change required.

**ADV-03 (Lens 2 — edge case: target is an existing file, not a directory)**
`tests/test_t25_skills_efficiency.py:96` — `test_invalid_target_exits_2` passes a non-existent path to trigger exit 2. The script's guard is `not args.target.is_dir()` (line 139), which also catches the case where `--target` is an existing *file* (not a directory). No test covers that edge case. Low risk since the CI step hard-codes `.claude/skills/` which is always a directory, but the path is exercisable in operator use.

Action: add a test parametrized over (non-existent path, existing-file path) to fully document the exit-2 contract; advisory only.

### What passed review (one line per lens)

- Tests-pass-for-wrong-reason: none observed — synthetic violation fixtures are substantive (fenced-block tool detection, adjacency suppression, exit codes all verified against real script behavior).
- Coverage gaps: two advisory gaps noted (ADV-01 `\bimage\b` branch; ADV-03 file-as-target edge case); both within the same code path as covered branches and non-blocking.
- Mock overuse: no mocks used; all tests invoke the audit script via `subprocess.run(sys.executable, ...)` against real `tmp_path` fixtures or the live repo. Correct boundary.
- Fixture / independence: `tmp_path` fixtures are pytest-managed, no order dependence, no module-level mutation, no env-var leaks.
- Hermetic-vs-E2E gating: all 19 tests are fully hermetic (local Python subprocess + local file reads); no `AIW_E2E=1` gate needed or missing.
- Naming / assertion-message hygiene: all assertions carry descriptive failure messages; test names are readable (ADV-02 is a minor nit on one test name).

## Sr. Dev review (2026-04-29)

**Files reviewed:** `scripts/audit/skills_efficiency.py` (164 lines), `.claude/commands/audit-skills.md`, `tests/test_t25_skills_efficiency.py`, `.claude/skills/ai-workflows/SKILL.md`, `.claude/skills/dep-audit/SKILL.md`, `.github/workflows/ci.yml`, `CHANGELOG.md`, M21 README, T25 spec, T24 issue file.
**Skipped (out of scope):** None.
**Verdict:** SHIP

### BLOCK — must-fix before commit

None.

### FIX — fix-then-ship

None.

### Advisory — track but not blocking

**ADV-01 — Defensive-code creep: redundant `is_dir()` guard in `_get_skill_files`**
`scripts/audit/skills_efficiency.py:79` — `_get_skill_files` opens with `if not target.is_dir(): return []`, but `main()` already gates on that condition at line 139 and returns exit 2 before calling `_get_skill_files`. The inner guard is dead code for the CLI path and would only matter if someone called `_get_skill_files` directly from a non-existent directory. Since this is a standalone script with no external callers, the inner guard is defensive-code against a scenario that cannot happen through the script's only entry point.
Action: consider removing the `if not target.is_dir(): return []` guard from `_get_skill_files` (or keep it and add a comment explaining it guards direct-import callers). Not a blocker — no behavioral change either way.

**ADV-02 — Comment drift: `main()` docstring is type-info only**
`scripts/audit/skills_efficiency.py:127` — `"""Entry point for the skills efficiency audit script."""` is implicit from the function name `main` and the `if __name__ == "__main__"` block. The module docstring (lines 1–24) already fully documents the script's purpose and spec-API. The `main()` docstring adds no *why* that isn't already in the module docstring or the signature.
Action: one line noting the exit-code contract (`"""CLI entry point; returns exit code (0/1/2)."""`) would be more useful, or drop it. Advisory only.

**ADV-03 — Simplification: `_tools_in_fenced_blocks` inner loop is a list comprehension candidate**
`scripts/audit/skills_efficiency.py:51-55` — the inner loop iterates `_TOOL_NAMES` with a `re.search` per tool per block. Readable as-is, but a set comprehension would be slightly more idiomatic and avoid the intermediate `for tool in` body.
Action: `found.update(t for t in _TOOL_NAMES if re.search(r"\b" + re.escape(t) + r"\b", block))` per block. Not a blocker; inline suggestion only.

### What passed review (one-line per lens)

- Hidden bugs: none observed — regex patterns tested against edge cases (word boundaries, lazy fenced-block match, frontmatter absence), all correct.
- Defensive-code creep: minor (ADV-01 above — one dead guard in `_get_skill_files`); not wide enough to block.
- Idiom alignment: clean — stdlib-only imports, no `ai_workflows` dependency, structlog/logging untouched (script is pre-import-linter scope), T24 pattern faithfully mirrored.
- Premature abstraction: none — no new base classes, mixins, or single-caller helpers introduced beyond what the spec called for.
- Comment / docstring drift: minor (ADV-02 above — `main()` docstring); module-level docstring is exemplary and cites task + TA-LOW-03 decision.
- Simplification: minor (ADV-03 above — inner loop); current form is readable and not wrong.
