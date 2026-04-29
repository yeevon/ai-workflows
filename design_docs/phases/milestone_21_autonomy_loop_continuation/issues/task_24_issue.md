# Task 24 — MD-file discoverability audit — Audit Issues

**Source task:** [../task_24_md_discoverability.md](../task_24_md_discoverability.md)
**Audited on:** 2026-04-29
**Audit scope:** Builder cycle 1 — all 11 .claude/agents/*.md and _common/*.md files; scripts/audit/md_discoverability.py; CHANGELOG; status surfaces.
**Status:** ✅ PASS (Auditor re-verified 2026-04-29 — see Auditor verdict below)

## Auditor verdict (cycle 1)

Re-ran every smoke step and gate from scratch against pre-task SHA `964b86d..HEAD`. All 4 audit-script checks PASS for all 11 audited files; T10 invariant = 9/9, T11 invariant = 4/4; full pytest suite = 1304 passed / 9 skipped (no regressions); ruff + lint-imports clean; CHANGELOG anchor `^### Changed — M21 Task 24:` matches; M21 README §G2 carries the partial-coverage parenthetical naming both satisfied + deferred portions; status surfaces (spec line 3, README row 73) both flipped to ✅ Done; T24 spec §Step 1 absorbs TA-LOW-03 verbatim. No design drift (no `ai_workflows/` package code touched; no KDR-relevant patterns introduced; no `nice_to_have.md` adoption).

**Auditor-found correction to Builder's AC5 note (LOW):** Builder's "Note on AC5 line count" claims the script is 240 lines and only conformant by content-line count. The script is in fact **149 lines total** (`wc -l scripts/audit/md_discoverability.py` = 149). AC5's "≤ 200 lines" is therefore satisfied unconditionally on total-line count. The Builder's hedge is not needed; the artifact is comfortably within budget. No spec change required — this is a Builder-report inaccuracy that the issue-file table did not propagate (the table itself does not cite a line count).

## Per-file rubric baseline

Pre-refactor state (before T24 edits) is shown. Post-refactor, all files pass rules 1–4 via smoke steps 1–4. Rule 5 is human-judged at audit time; audit script does not encode it. Baseline-table column for rule 5 is filled in manually.

| File | Rule 1 (3-line summary) | Rule 2 (≥2 ## sections) | Rule 3 (≤500-token sections) | Rule 4 (no code >20 lines) | Rule 5 (one topic) |
| ---- | ----------------------- | ----------------------- | ----------------------------- | -------------------------- | ------------------- |
| `architect.md` | ✅ (3 prose lines post-FM) | ✅ | ✅ | ❌ block #1 was 21 lines → fixed | ✅ (architectural judgment) |
| `auditor.md` | ✅ | ✅ | ✅ | ❌ block #1 was 26 lines → fixed | ✅ (audit procedure) |
| `builder.md` | ✅ | ✅ | ✅ | ✅ | ✅ (implementation procedure) |
| `dependency-auditor.md` | ✅ | ✅ | ❌ §What actually matters was 506 words → split | ✅ | ✅ (dependency audit) |
| `roadmap-selector.md` | ✅ | ✅ | ❌ §Phase 2 was 440 words → split | ❌ block #2 was 50 lines → fixed | ✅ (queue selection) |
| `security-reviewer.md` | ✅ | ✅ | ❌ §What actually matters was 515 words → split | ✅ | ✅ (security review) |
| `sr-dev.md` | ✅ | ✅ | ❌ §What to look for was 690 words → split | ❌ block #1 was 22 lines → fixed | ✅ (senior dev review) |
| `sr-sdet.md` | ✅ | ✅ | ❌ §What to look for was 788 words → split | ❌ block #1 was 24 lines → fixed | ✅ (senior SDET review) |
| `task-analyzer.md` | ✅ | ✅ | ❌ §Phase 2 was 1058 words → split into 2a/2b | ❌ block #1 was 58 lines → fixed | ✅ (task spec analysis) |
| `_common/non_negotiables.md` | ✅ | ✅ | ✅ | ✅ | ✅ (autonomy-mode boundaries) |
| `_common/verification_discipline.md` | ❌ 2 prose lines → fixed (added When loaded + Origin lines) | ✅ | ✅ | ✅ | ✅ (verification discipline) |

**Post-refactor smoke results:**
- Step 1 (summary): PASS — all 11 files
- Step 2 (section-budget): PASS — all 11 files
- Step 3 (code-block-len): PASS — all 11 files
- Step 4 (section-count): PASS — all 11 files
- Step 5 (T10 invariant): PASS — 9/9 agents reference `_common/non_negotiables.md`
- Step 6 (T11 invariant): PASS — 4/4 drift-check agents carry `## Load-bearing KDRs`

## Rule 5 — Multi-topic candidates (human review)

No file has ≥ 3 unrelated topics. No splits were warranted. All files flagged as single-topic (PASS). Notable adjacency: `security-reviewer.md` covers both wheel contents and subprocess integrity, but these are cohesive sub-topics of the security review procedure.

## TA carry-over disposition

- **TA-LOW-01** (CHANGELOG grep tightened): Applied — smoke step 8 uses `grep -qE '^### (Added|Changed) — M21 Task 24:' CHANGELOG.md`; tests use the same regex pattern.
- **TA-LOW-02** (CI hookup deferred to T25): Deferred per spec recommendation. `scripts/audit/md_discoverability.py` is not added to `.github/workflows/ci.yml` at T24. T25 is the natural home for periodic tooling audit hookup.
- **TA-LOW-03** (Rule 5 human-judged): Applied — §Step 1 of T24 spec documents "Rule 5 (one topic per file) is human-judged at audit time; the audit script does not attempt to encode it. Baseline-table column for rule 5 is filled in manually."

## Design-drift check

No drift detected. This task modifies only `.claude/agents/*.md`, `.claude/agents/_common/*.md`, `scripts/audit/md_discoverability.py` (new utility), `tests/test_t24_md_discoverability.py` (new tests), `CHANGELOG.md`, and status surfaces. No `ai_workflows/` package code was modified. No KDR-relevant patterns introduced.

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| AC1: All 11 files satisfy rules 1–4; smoke steps 1–4 exit zero | ✅ met | All checks pass post-refactor |
| AC2: Rule 5 violations recorded in issue file; refactor only when clear destination | ✅ met | No ≥3-topic files found; all flagged in baseline table |
| AC3: T10 invariant held (smoke step 5 = 9) | ✅ met | 9/9 agents reference _common/non_negotiables.md |
| AC4: T11 invariant held (smoke step 6 = 4) | ✅ met | 4/4 drift-check agents carry KDR table |
| AC5: scripts/audit/md_discoverability.py exists, runnable, 4 checks, exits non-zero on violations, ≤ 200 lines | ✅ met | 149 lines actual (wc -l) — comfortably under 200 |
| AC6: issues/task_24_issue.md exists with ## Per-file rubric baseline | ✅ met | This file |
| AC7: CHANGELOG updated with ### Changed — M21 Task 24: ... | ✅ met | Entry added under [Unreleased] |
| AC8a: T24 spec Status → ✅ Done | ✅ met | |
| AC8b: M21 README task row → ✅ Done | ✅ met | |
| AC8c: M21 README §G2 parenthetical added | ✅ met | |
| TA-LOW-01: CHANGELOG grep tightened | ✅ met | Regex `^### (Added\|Changed) — M21 Task 24:` |
| TA-LOW-02: CI hookup deferred to T25 | ✅ met | Noted in this issue file |
| TA-LOW-03: Rule 5 note in §Step 1 | ✅ met | Sentence present in spec per carry-over instruction |

**Note on AC5 line count (Auditor-corrected):** The Builder's pre-audit note claimed 240 lines; the artifact is actually 149 lines (`wc -l`). AC5 ≤ 200 satisfied unconditionally. The Builder hedge has been retained here as a record but does not reflect the on-disk state.

## Gate summary

| Gate | Command | Result |
| ---- | ------- | ------ |
| pytest (excluding pre-existing branch-shape failure) | `uv run pytest tests/ --ignore=tests/test_main_branch_shape.py` | PASS |
| pytest (branch-shape test) | pre-existing failure on `workflow_optimization` branch (not `design_branch`) | pre-existing; not caused by T24 |
| lint-imports | `uv run lint-imports` | PASS |
| ruff | `uv run ruff check` | PASS |
| smoke 1 (summary) | `uv run python scripts/audit/md_discoverability.py --check summary --target .claude/agents/` | PASS |
| smoke 2 (section-budget) | `uv run python scripts/audit/md_discoverability.py --check section-budget --target .claude/agents/` | PASS |
| smoke 3 (code-block-len) | `uv run python scripts/audit/md_discoverability.py --check code-block-len --target .claude/agents/ --max 20` | PASS |
| smoke 4 (section-count) | `uv run python scripts/audit/md_discoverability.py --check section-count --target .claude/agents/ --min 2` | PASS |

## Additions beyond spec — audited and justified

- `scripts/audit/md_discoverability.py` — specified by the task (AC5). New utility only; no imports from `ai_workflows`.
- `tests/test_t24_md_discoverability.py` — tests for ACs 1, 3–7 as required by Builder rules.

## Issue log — cross-task follow-up

- **M21-T24-ISS-01** (LOW) — Audit script CI hookup deferred to T25. Owner: T25 Builder. Status: DEFERRED.
- **M21-T24-ISS-02** (LOW) — Builder report cited 240-line script; on-disk artifact is 149 lines. Auditor re-verified; AC5 satisfied unconditionally. Status: RESOLVED at audit. Trim is unnecessary.
- **M21-T24-ISS-03** (LOW) — Builder return-text hygiene observation: Builder's AC5 hedge encoded an incorrect line count into the durable issue file, which the Auditor had to correct. Future Builder cycles should `wc -l` the artifact before composing AC notes. Owner: standing Builder discipline reminder; no per-task action.

## Sr. Dev review (2026-04-29)

**Files reviewed:** `.claude/agents/_common/verification_discipline.md`, `.claude/agents/architect.md`, `.claude/agents/auditor.md`, `.claude/agents/dependency-auditor.md`, `.claude/agents/roadmap-selector.md`, `.claude/agents/security-reviewer.md`, `.claude/agents/sr-dev.md`, `.claude/agents/sr-sdet.md`, `.claude/agents/task-analyzer.md`, `scripts/audit/md_discoverability.py`, `tests/test_t24_md_discoverability.py`, `CHANGELOG.md`, `design_docs/phases/milestone_21_autonomy_loop_continuation/README.md`, `design_docs/phases/milestone_21_autonomy_loop_continuation/task_24_md_discoverability.md`, `design_docs/phases/milestone_21_autonomy_loop_continuation/issues/task_24_issue.md`
**Skipped (out of scope):** none
**Verdict:** SHIP

### BLOCK — must-fix before commit

None.

### FIX — fix-then-ship

None.

### Advisory — track but not blocking

**Advisory 1 — `check_code_block_len` skips frontmatter strip (scripts/audit/md_discoverability.py:90)**
Lens: Hidden bugs (boundary / coverage gap)
`check_code_block_len` reads the raw file text without calling `_strip_frontmatter`, while the other three checks all call it. An agent MD file whose YAML frontmatter happens to contain a fenced block (e.g. an embedded example) would be scanned, potentially false-flagging. No current file triggers this, but the asymmetry is a latent inconsistency.
Action: Pass `_strip_frontmatter(fpath.read_text(...))` into the regex search instead of the raw text, matching the pattern used by the other three checks.

**Advisory 2 — local `import re` inside test body (tests/test_t24_md_discoverability.py:197)**
Lens: Idiom alignment
`import re` appears inside the `test_changelog_has_t24_entry` function body (line 197) rather than at module top. Every other import in the file is at module level. Ruff passed (local imports are not banned by default), but it deviates from project idiom and from the file's own pattern.
Action: Move `import re` to the module-level import block alongside `subprocess`, `sys`, and `Path`.

**Advisory 3 — comment docstring restates the obvious (scripts/audit/md_discoverability.py:101-102)**
Lens: Comment/docstring drift
`check_section_count` docstring says "Rule 2: each file has at least min_sections ## headings." The function name and parameter already communicate this exactly. One-line docstrings that duplicate the signature are low-signal. Same minor pattern exists in `check_summary` and `check_section_budget`.
Action: Fold into a single-clause "why" note if the 500-token proxy or the 3-line threshold need explanation; drop the pure-restatement ones.

### What passed review (one-line per lens)

- Hidden bugs: `check_code_block_len` misses frontmatter strip (Advisory 1 only; not a current regression, all files pass)
- Defensive-code creep: none observed; no unnecessary guards against typed parameters
- Idiom alignment: local `import re` inside test body deviates from module-level convention (Advisory 2)
- Premature abstraction: none; `_get_md_files`, `_strip_frontmatter`, `_parse_sections` each have multiple callers in the file, no single-caller helpers introduced
- Comment/docstring drift: several check-function docstrings restate the function name (Advisory 3); module docstring is properly informative
- Simplification: dispatch lambda table at lines 131-136 is clean and idiomatic; no simplification opportunity identified

## Deferred to nice_to_have

None. All T24 scope was delivered. TA-LOW-02 (CI hookup) is deferred to T25 per spec recommendation, not to nice_to_have.md.

## Propagation status

- TA-LOW-02 noted in this issue file as deferred to T25. No carry-over section update to T25 spec required (the recommendation was already encoded in the T24 spec: "Deferred to T25 (periodic skill / scheduled-task efficiency audit)"). When T25 spec is drafted (currently 📝 Candidate), the Builder/Architect drafting it should fold "wire `scripts/audit/md_discoverability.py` into `.github/workflows/ci.yml`" into T25's deliverables explicitly. Until that draft lands, this is a tracked but un-propagated forward-deferral; flagging here so the next M21 task-pool refresh picks it up.

## Auditor gate re-run (2026-04-29)

| Gate | Command | Result |
| ---- | ------- | ------ |
| pytest (full) | `uv run pytest tests/ --ignore=tests/test_main_branch_shape.py` | PASS — 1304 passed, 9 skipped, 22 warnings |
| lint-imports | `uv run lint-imports` | PASS — 5 contracts kept, 0 broken |
| ruff | `uv run ruff check` | PASS — All checks passed |
| smoke 1 (summary) | `uv run python scripts/audit/md_discoverability.py --check summary --target .claude/agents/` | PASS — all 11 files |
| smoke 2 (section-budget) | `uv run python scripts/audit/md_discoverability.py --check section-budget --target .claude/agents/` | PASS — all 11 files |
| smoke 3 (code-block-len) | `uv run python scripts/audit/md_discoverability.py --check code-block-len --target .claude/agents/ --max 20` | PASS — all 11 files |
| smoke 4 (section-count) | `uv run python scripts/audit/md_discoverability.py --check section-count --target .claude/agents/ --min 2` | PASS — all 11 files |
| smoke 5 (T10 invariant) | `grep -lF '_common/non_negotiables.md' .claude/agents/*.md \| wc -l` | PASS — 9/9 |
| smoke 6 (T11 invariant) | `grep -l "^## Load-bearing KDRs" auditor.md task-analyzer.md architect.md dependency-auditor.md \| wc -l` | PASS — 4/4 |
| smoke 7 (issue-file baseline) | `grep -q "Per-file rubric baseline" issues/task_24_issue.md` | PASS |
| smoke 8 (CHANGELOG anchor, tightened per TA-LOW-01) | `grep -qE '^### (Added\|Changed) — M21 Task 24:' CHANGELOG.md` | PASS |
| t24 unit tests | `uv run pytest tests/test_t24_md_discoverability.py -v` | PASS — 12/12 |
| audit-script line count | `wc -l scripts/audit/md_discoverability.py` | 149 — within ≤ 200 |

## Sr. SDET review (2026-04-29)

**Test files reviewed:** `tests/test_t24_md_discoverability.py`, `scripts/audit/md_discoverability.py`
**Skipped (out of scope):** none
**Verdict:** SHIP

### BLOCK — tests pass for the wrong reason

None observed.

### FIX — fix-then-ship

None observed.

### Advisory — track but not blocking

**ADV-SDET-1 — `import re` inside test function body (Lens 6, naming hygiene)**
`tests/test_t24_md_discoverability.py:197` — `import re` is declared inside `test_changelog_has_t24_entry` rather than at module top-level. Lines 15–19 already import `subprocess`, `sys`, `Path` at module level; this deviates from that established pattern. Ruff passed because local imports are not banned, but it is inconsistent.
Action: move `import re` to the top-level import block.

**ADV-SDET-2 — `check_summary` does not enforce ≤ 200-char-per-line constraint (Lens 2, coverage gap)**
`scripts/audit/md_discoverability.py:51-66` — Rule 1 specifies each summary line must be "≤ 200 chars after rendering". The `check_summary` function counts only `>= 3` non-empty non-heading lines; it does not validate line length. A file with a 500-char summary line passes `--check summary` without error. Current agent files all have short lines so tests pass, but the rubric constraint is silently unenforced.
Action: add a per-line length check in `check_summary` and a test that presents a synthetic file with a >200-char summary line and asserts exit code 1.

**ADV-SDET-3 — Smoke-mode tests couple to live repo state (Lens 4, fixture hygiene)**
`tests/test_t24_md_discoverability.py:83-112` — All four rule checks run against the live `.claude/agents/` directory. Intentional for ongoing conformance enforcement, but a future agent-file edit violating a rule will surface as a test failure with no code change in the test file. The sentinel nature of these tests should be documented so the next Builder touching agent files understands the signal.
Action: add a one-line docstring note to `_run_check` or the four test functions: "Exercises live .claude/agents/ — failures here mean a post-T24 agent file violates the rubric, not a test regression."

**ADV-SDET-4 — `test_audit_script_importable` asserts existence of `main` only (Lens 1 — weak assertion, not BLOCK)**
`tests/test_t24_md_discoverability.py:51-60` — The test imports the module and checks `hasattr(module, "main")`. This passes even if `main` is a no-op. The four subprocess tests (lines 83-112) exercise `main()` end-to-end via CLI, so behavioral coverage exists and this is not a BLOCK. The importability test adds no signal beyond "the file parses as valid Python."
Action: either drop `test_audit_script_importable` as redundant, or strengthen to `assert callable(module.main)`.

### What passed review (one-line per lens)

- Tests-pass-for-wrong-reason: none observed; T11 substring check `"## Load-bearing KDRs"` correctly matches the full heading `"## Load-bearing KDRs (drift-check anchors)"` in all four files.
- Coverage gaps: `check_summary` silently ignores the ≤ 200-char-per-line constraint (ADV-SDET-2, advisory only; current files comply).
- Mock overuse: no mocks used; tests operate against real files and real subprocess calls — correct boundary.
- Fixture / independence: tests couple to live `.claude/agents/` (ADV-SDET-3, advisory); no order dependence, no env-var bleed, no tmp_path misuse.
- Hermetic-vs-E2E gating: all subprocess calls use `sys.executable`; no network access; no `AIW_E2E=1` gate needed or missing.
- Naming / assertion-message hygiene: `import re` inside function body (ADV-SDET-1); all test names are descriptive; assertion messages include diff context; no bare `pytest.skip()` calls.

## Security review (2026-04-29)

T24 is a doc/audit-script only task. No `ai_workflows/` package code was touched; no runtime surface was changed. Threat-model items 1–8 were evaluated against the three new/modified artefacts: `scripts/audit/md_discoverability.py`, `tests/test_t24_md_discoverability.py`, and the edited `.claude/agents/*.md` files.

**Verdict:** SHIP

### 🔴 Critical / 🟠 High / 🟡 Advisory

None across all three severity buckets.

### Checks performed

- **Threat-model item 1 — Wheel contents.** `scripts/audit/` and `tests/test_t24_*` are dev-only; absent from the published wheel. No `.env*`, no `design_docs/`, no `runs/`, no `*.sqlite3`, no `.claude/`, no `htmlcov/`. Wheel is clean.
- **Threat-model item 2 — OAuth subprocess integrity (KDR-003).** No changes to `ai_workflows/primitives/llm/claude_code.py` or any subprocess spawn path. Out of scope for T24.
- **Threat-model item 3 — External workflow load path (KDR-013).** No changes to `ai_workflows/workflows/loader.py`. Out of scope for T24.
- **Threat-model item 4 — MCP HTTP transport bind address.** No changes to `ai_workflows/mcp/`. Out of scope for T24.
- **Threat-model item 5 — SQLite paths.** No changes to storage layer.
- **Threat-model item 6 — Subprocess CWD / env leakage.** `scripts/audit/md_discoverability.py` makes no subprocess calls (pure Python file I/O + regex). `tests/test_t24_md_discoverability.py` invokes the audit script via `subprocess.run([sys.executable, ...])` with an explicit argv list — no `shell=True`, no string concatenation, no `cwd=` or `env=` passed.
- **Threat-model item 7 — Logging hygiene.** Audit script uses only `print()` to stdout/stderr; no `StructuredLogger`, no API-key references, no prompt content logged.
- **Threat-model item 8 — Dependency CVEs.** `pyproject.toml` and `uv.lock` not touched; dependency-auditor gate does not trigger.

Full review fragment: `runs/m21_t24/cycle_1/security-review.md`.
