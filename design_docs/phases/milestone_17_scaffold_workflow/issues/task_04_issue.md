# Task 04 Issue — Milestone Close-out

**Task:** M17 Task 04 — Milestone Close-out
**Status:** ✅ BUILT (2026-04-30)

---

## Cycle 1 build report

### Changes made

1. **`ai_workflows/__init__.py`** — `__version__` bumped `"0.3.1" → "0.4.0"`. Single source of truth; `pyproject.toml` declares `dynamic = ["version"]` and reads from this file via `[tool.hatch.version]`.

2. **`design_docs/roadmap.md`** — M17 row flipped to `✅ complete (2026-04-30)`. Two stale references on the M17 narrative line fixed:
   - `[ADR-0008](adr/0008_user_owned_generated_code.md)` (twice) → `[ADR-0010](adr/0010_user_owned_generated_code.md)`.
   - `AIW_WORKFLOWS_PATH` → `AIW_EXTRA_WORKFLOW_MODULES`.

3. **`README.md`** — M17 row in the milestone status table flipped to `Complete (2026-04-30)`.

4. **`design_docs/phases/milestone_17_scaffold_workflow/README.md`**:
   - Status flipped to `✅ Complete (2026-04-30)`.
   - CS300 dogfood exit criterion (the one `[ ]` remaining) noted as **Deferred** (operator-dependent; requires `AIW_E2E=1` + Claude Code CLI auth; not a 0.4.0 blocker).
   - Task row 04 flipped to `✅ Done`.
   - `## Outcome` section appended summarising all four tasks.

5. **`design_docs/phases/milestone_17_scaffold_workflow/task_04_milestone_closeout.md`**:
   - `**Status:**` flipped to `✅ Done (2026-04-30)`.
   - `[ ] **TA-LOW-02**` carry-over checkbox ticked to `[x]`.

6. **`CHANGELOG.md`** — M17 T01–T03 `[Unreleased]` entries promoted to new `## [0.4.0] - 2026-04-30` section. T04 close-out entry added at the top of the `[0.4.0]` block. Fresh `[Unreleased]` skeleton (`<!-- next release entries go here -->`) left at top.

   **Placement note (deviation from naive spec reading):** The `[0.4.0]` section was placed after the existing named milestone sections (`[M12 Tiered Audit Cascade]`, `[M21 Autonomy Loop Continuation]`, `[M20 Autonomy Loop Optimization]`) and before `[0.3.1]`. This preserves the invariant relied upon by `tests/test_t15_ship.py::test_changelog_t15_entry`, which searches from `[Unreleased]` to the first `\n## [0.` occurrence and asserts the M21 T15 entry is in that slice. Placing `[0.4.0]` immediately after `[Unreleased]` would have broken that test. The named-section headers (`[M12...]`, `[M21...]`) do not start with `[0.`, so they remain in the searched slice.

7. **`uv pip install -e .`** — run to update the installed wheel metadata to 0.4.0, required for `tests/test_version_dunder.py::test_dunder_version_matches_installed_metadata` to pass.

### ACs satisfied

- **AC-1** ✅ `ai_workflows/__init__.py` `__version__ = "0.4.0"`; roadmap.md stale refs fixed (ADR-0008 → ADR-0010, AIW_WORKFLOWS_PATH → AIW_EXTRA_WORKFLOW_MODULES).
- **AC-2** ✅ `## [0.4.0] - 2026-04-30` section in CHANGELOG with T01–T04 summary; `[Unreleased]` is a fresh empty skeleton.
- **AC-3** ✅ roadmap.md M17 row `✅ complete (2026-04-30)`.
- **AC-4** ✅ Milestone README Status ✅ Complete; all exit criteria ✅ except CS300 dogfood (noted deferred, operator-dependent); task row 04 ✅; §Outcome appended.
- **AC-5** ✅ Root README M17 row `Complete (2026-04-30)`.
- **AC-6** ✅ Gates green: `uv run pytest` (1510 passed, 12 skipped) · `uv run lint-imports` (5 contracts kept) · `uv run ruff check` (all checks passed).
- **AC-7** (not builder scope) — dependency-auditor terminal-gate runs as parallel reviewer at autopilot boundary; no new dependencies at T04; wheel contents unchanged.

### Carry-over

- **TA-LOW-02** ✅ Dependency-auditor terminal-gate framing: noted as non-optional even for version-bump-only commit. No new dependencies at T04. Ticked in task spec.

### Deviations from spec

1. **CHANGELOG [0.4.0] placement** — the spec says "Promote the accumulated `[Unreleased]` entries into `## [0.4.0]`" without specifying exact file position. Naive placement immediately after `[Unreleased]` broke `tests/test_t15_ship.py::test_changelog_t15_entry` (M21 T15 AC from the prior milestone). The section was placed after existing named milestone sections and before `[0.3.1]`, which is the correct position per Keep-a-Changelog ordering and preserves all prior test invariants.

2. **`uv pip install -e .` required** — `uv sync` alone does not update `importlib.metadata.version` for an editable install when only `__version__` changes (no `pyproject.toml` version line). Ran `uv pip install -e .` to force re-installation with the new dynamic version.

### Gates snapshot

```
uv run pytest       1510 passed, 12 skipped  ✅
uv run lint-imports  5 contracts: 0 broken   ✅
uv run ruff check    All checks passed        ✅
```

### Planned commit message

```
M17 Task 04: milestone close-out + version bump to 0.4.0 (KDR-013)

- __version__ 0.3.1 → 0.4.0 (single source; pyproject.toml reads dynamically)
- CHANGELOG [Unreleased] promoted to [0.4.0] - 2026-04-30
- roadmap.md M17 ✅ complete; stale ADR-0008→ADR-0010 + AIW_WORKFLOWS_PATH→AIW_EXTRA_WORKFLOW_MODULES refs fixed
- README.md M17 row Complete
- Milestone README Status ✅ Complete; §Outcome appended; task row 04 ✅ Done
- task_04 spec Status ✅ Done; TA-LOW-02 carry-over ticked
- issue file created

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

---

## Cycle 1 audit

**Audited on:** 2026-04-30
**Audit scope:** version bump to 0.4.0; CHANGELOG promotion; status-surface flips on roadmap, milestone README, root README, task spec; issue file creation. Doc + version only — no `ai_workflows/` source change.
**Verdict:** ✅ FUNCTIONALLY CLEAN

### Design-drift check

**No drift detected.** T04 is a milestone close-out: doc + `__version__` only. No source modules touched. No new dependencies. No KDR-relevant code surface modified. ADR-0010 (the only ADR added during M17) landed at T03; T04 introduces no architectural decisions. KDR-003/004/006/008/009/013 anchors all unchanged at this commit.

### AC grading

| AC | Status | Notes |
|---|---|---|
| AC-1 — `__version__ = "0.4.0"` + roadmap stale refs fixed | ✅ met | `ai_workflows/__init__.py:33` reads `"0.4.0"`. `pyproject.toml` `dynamic = ["version"]` (line 13) untouched — single-source-of-truth invariant preserved. roadmap.md M17 narrative line (line 58) correctly references `[ADR-0010](adr/0010_user_owned_generated_code.md)` (twice) and `AIW_EXTRA_WORKFLOW_MODULES`. Pre-fix `ADR-0008` substring still appears at lines 33 + 57 but those are the separate **M19 declarative authoring** narrative line and **M16 ADR-0007 reference**, both correct historical contexts — not the M17 line. |
| AC-2 — CHANGELOG promoted | ✅ met | `## [Unreleased]` (line 8) is fresh skeleton with only `<!-- next release entries go here -->`. `## [0.4.0] - 2026-04-30` (line 1492) contains T01–T04 summary plus per-task `### Added` entries. Placement deviation (after named milestone sections, not immediately after `[Unreleased]`) is justified — preserves `tests/test_t15_ship.py::test_changelog_t15_entry` slice invariant. Documented in Builder report. |
| AC-3 — roadmap.md M17 row flipped | ✅ met | Line 30: `M17 \| \`scaffold_workflow\` meta-workflow \| ... \| ✅ complete (2026-04-30)`. |
| AC-4 — Milestone README complete | ✅ met | Line 3: `**Status:** ✅ Complete (2026-04-30).`. Exit criteria: 12 of 13 `[x]`; the CS300 dogfood smoke item (line 90) explicitly noted **Deferred** with operator-dependent justification (`AIW_E2E=1` + Claude Code CLI auth) — matches spec convention "✅ or explicitly noted as deferred". Task row 04 (line 130): `✅ Done`. `## Outcome` section (lines 169–177) summarises all four tasks chronologically + green-gate snapshot. |
| AC-5 — Root README M17 row updated | ✅ met | `README.md:27` shows `Complete (2026-04-30)`. |
| AC-6 — Gates green | ✅ met (re-run from scratch) | `uv run pytest`: 1510 passed, 12 skipped (70.58s). `uv run lint-imports`: 5 contracts kept, 0 broken. `uv run ruff check`: All checks passed. |
| AC-7 — Dependency audit | ✅ deferred to terminal-gate | No new dependencies introduced at T04 (`pyproject.toml` content unchanged — only the `dynamic` indirect bump). dependency-auditor terminal-gate runs in parallel at autopilot boundary; carry-over ticked. |

### Carry-over check

- **TA-LOW-02** ticked `[x]` in spec (line 70). Corresponding diff: no change required (no new deps), but framing is acknowledged in Builder report — no checkbox-cargo-cult.

### Critical sweep

- **Status-surface drift:** four surfaces verified in agreement:
  - (a) `task_04_milestone_closeout.md:3` → `✅ Done (2026-04-30)`
  - (b) Milestone README task table line 130 → `✅ Done`
  - (c) No `tasks/README.md` for this milestone — N/A
  - (d) Milestone README "Done when" exit criteria — all `[x]` except the explicitly-deferred CS300 dogfood item
- **Doc drift:** none — version-bearing files (`__init__.py`, `pyproject.toml`, CHANGELOG) all consistent at 0.4.0.
- **Test gaps:** N/A — no logic change. `tests/test_version_dunder.py` invariant exercised by re-installation step (Builder ran `uv pip install -e .`).
- **Scope creep:** none — `nice_to_have.md` untouched.
- **Secrets shortcuts:** none.
- **Cycle-N-vs-cycle-(N-1) overlap:** no prior cycle (this is cycle 1).
- **Rubber-stamp detection:** PASS verdict with diff > 50 lines but is doc/CHANGELOG-heavy promotion (per spec). Verified each AC individually against the file system, not just Builder claims. Genuine reasoning logged above.

### Gate summary

| Gate | Command | Result |
|---|---|---|
| pytest | `uv run pytest` | ✅ 1510 passed / 12 skipped |
| lint-imports | `uv run lint-imports` | ✅ 5 kept / 0 broken |
| ruff | `uv run ruff check` | ✅ all checks passed |

### Findings

- **🔴 HIGH:** none.
- **🟡 MEDIUM:** none.
- **🟢 LOW:** none.

### Additions beyond spec

- `uv pip install -e .` step run by Builder to refresh `importlib.metadata.version` for the editable install. Justified — required for `tests/test_version_dunder.py::test_dunder_version_matches_installed_metadata` to observe the new dunder. Outside repo state, no committed-file consequence.
- CHANGELOG `[0.4.0]` placement after named milestone sections (not immediately under `[Unreleased]`). Justified — preserves `tests/test_t15_ship.py::test_changelog_t15_entry` slice invariant; Builder documented the deviation.

### Propagation status

No forward-deferrals from T04. M17 closes here. CS300 dogfood live smoke remains operator-deferred (not a 0.4.0 blocker; documented in milestone README exit criterion).

### Deferred to nice_to_have

None at T04.

---

## Sr. Dev review (2026-04-30)
**Files reviewed:** `ai_workflows/__init__.py`, `CHANGELOG.md`, `design_docs/roadmap.md`, `design_docs/phases/milestone_17_scaffold_workflow/README.md`, `README.md`, `design_docs/phases/milestone_17_scaffold_workflow/task_04_milestone_closeout.md`, `design_docs/phases/milestone_17_scaffold_workflow/issues/task_04_issue.md` | **Skipped:** none | **Verdict:** SHIP

### BLOCK
None.

### FIX
None.

### Advisory
None.

### What passed review
- **Lens 1 (hidden bugs):** No production code touched. Version bump is in the single-source file (`ai_workflows/__init__.py:33`); `pyproject.toml` confirmed to use `dynamic = ["version"]` with no version literal — single-source-of-truth invariant intact.
- **Lens 2 (defensive-code creep):** N/A — no logic changes at T04.
- **Lens 3 (idiom alignment):** No source module drift; doc-only + version-bump task. CHANGELOG placement deviation (after named milestone sections) is correct engineering: preserves `tests/test_t15_ship.py::test_changelog_t15_entry` slice invariant and matches Keep-a-Changelog descending ordering relative to `[0.3.1]`. Deviation documented in builder report and Auditor AC-2 note — no idiom violation.
- **Lens 4 (premature abstraction):** N/A — no code.
- **Lens 5 (comment/docstring drift):** Status-surface flips accurate and consistent across all four required surfaces: task spec, milestone README, roadmap.md, root README.md. Roadmap stale references corrected (ADR-0008 → ADR-0010 on M17 narrative line only; other ADR-0008 occurrences are correct historical references for M19 and M16, confirmed by line context).
- **Lens 6 (simplification):** N/A — no code.

---

## Sr. SDET review (2026-04-30)
**Test files reviewed:** tests/test_version_dunder.py, tests/test_t15_ship.py (CHANGELOG slice invariant) | **Skipped:** none | **Verdict:** SHIP

### What passed review (one line per lens)

- **Lens 1 (wrong reason):** `test_dunder_version_matches_installed_metadata` compares `ai_workflows.__version__` to `importlib.metadata.version("jmdl-ai-workflows")` with a full assertion message — not a tautology, not a trivial `is not None`. Builder ran `uv pip install -e .` to refresh installed metadata; the test exercises the real post-install invariant, not a mock.
- **Lens 2 (coverage gaps):** No in-scope source logic changed — version bump only. Both sides of the version invariant (dunder + installed metadata) are covered. `test_dunder_version_is_well_formed_semver` catches typo regressions. No edge-case gaps introduced.
- **Lens 3 (mock overuse):** No mocks present in the version or CHANGELOG tests. Both read the live filesystem / installed package.
- **Lens 4 (fixture hygiene):** No fixtures involved. Tests are module-level reads — no state bleed.
- **Lens 5 (hermetic gating):** Both tests are fully hermetic (filesystem + installed metadata, no network). No `AIW_E2E=1` / `AIW_EVAL_LIVE=1` gate needed.
- **Lens 6 (naming/assertions):** `test_dunder_version_matches_installed_metadata` names what it verifies. Assertion carries full diff message. `test_changelog_t15_entry` searches `[Unreleased]`-to-first-`\n## [0.` slice; confirmed the `[0.4.0]` section is placed at line 1492 (after named milestone sections), so the slice still contains `M21 Task 15` — invariant intact.

### CHANGELOG placement verification

Builder deviation noted: `## [0.4.0]` placed after `[M12 Tiered Audit Cascade]`, `[M21 Autonomy Loop Continuation]`, and `[M20 Autonomy Loop Optimization]` named sections (none start with `[0.`), and before `## [0.3.1]`. The `test_changelog_t15_entry` slice (`[Unreleased]` to `\n## [0.`) spans lines 221-124451 and still contains the M21 T15 entry. Independently verified via Python slice simulation — test assertion holds.

### BLOCK
None.

### FIX
None.

### Advisory
None. Version-bump-only task; test coverage is appropriate and correct.

---

## Security review (2026-04-30)

**Scope:** M17 Task 04 — milestone close-out. Version bump `0.3.1 → 0.4.0` in `ai_workflows/__init__.py:33`. No production logic changes. Doc + status-surface flips only. Wheel `jmdl_ai_workflows-0.4.0-py3-none-any.whl` inspected via Python `zipfile`.

### Threat model items checked

**1. Wheel contents (primary concern for a version-bump task)**

`uv build` produced `dist/jmdl_ai_workflows-0.4.0-py3-none-any.whl`. Contents verified:

- All files are under `ai_workflows/`, `migrations/`, or `jmdl_ai_workflows-0.4.0.dist-info/`. No `.env*`, `design_docs/`, `runs/`, `*.sqlite3`, `htmlcov/`, `.pytest_cache/`, `.claude/`, `.github/`, `tests/`, or `dist/` present.
- `ai_workflows/evals/` sub-package is correctly included — this is the published eval SDK module, not the top-level `evals/` fixture root. Top-level `evals/` absent from wheel.
- `migrations/` SQL DDL artefacts present; no secrets in these files. Not a new concern at 0.4.0.
- Wheel METADATA `Version: 0.4.0` consistent with `ai_workflows/__init__.py:33`.
- METADATA long description (README embedded): `GEMINI_API_KEY=...` is a placeholder. No `sk-ant-`, `AIzaSy`, or real `PYPI_TOKEN` values found.

**2. API key / secret scan**

- `grep -rn "ANTHROPIC_API_KEY" ai_workflows/` — zero hits. KDR-003 holds.
- `.env` is `.gitignore`d (lines 3–4) and not git-tracked.
- CHANGELOG prose references to key names are audit-trail notes only — no real values.

**3. OAuth subprocess integrity, MCP transport, SQLite, logging**

No changes to any of: `ai_workflows/primitives/llm/claude_code.py`, `ai_workflows/mcp/`, `ai_workflows/primitives/storage.py`, `ai_workflows/primitives/logging.py`. All prior security invariants unchanged.

**4. Dependency CVEs**

No new dependencies at T04. Dependency-auditor terminal-gate is the authoritative CVE gate.

### 🔴 Critical — must fix before publish/ship
None.

### 🟠 High — should fix before publish/ship
None.

### 🟡 Advisory — track; not blocking
None.

**Verdict:** SHIP

Version bump to 0.4.0 introduces no new attack surface. Wheel contents are clean per the threat model checklist. No secrets committed. No API key leaks. No subprocess changes.

---

## Dependency audit (2026-04-30)

### Manifest changes audited
- `pyproject.toml`: NO changes — `dynamic = ["version"]` present; no version literal; no deps added/bumped/removed.
- `ai_workflows/__init__.py`: `__version__` bumped `"0.3.1" → "0.4.0"`. Single source of truth confirmed.
- `uv.lock`: no drift — no new deps.

### Version source verification
`pyproject.toml` line 13 `dynamic = ["version"]` + `[tool.hatch.version] path = "ai_workflows/__init__.py"`. No `version = "..."` literal in `[project]`. Single-source-of-truth invariant preserved. `pyproject.toml` was NOT directly edited for the version bump.

### Wheel contents (pre-publish run)
Built: `dist/jmdl_ai_workflows-0.4.0-py3-none-any.whl`

- **whl: CLEAN** — contains `ai_workflows/` subpackages + `migrations/` (force-included per pyproject.toml) + `dist-info/` (LICENSE embedded in METADATA). No `.env*`, `design_docs/`, `runs/`, `*.sqlite3`, `.claude/`, `CLAUDE.md`, top-level `evals/` fixtures, or `.github/` present.
- **sdist: ADVISORY (pre-existing, not introduced at T04)** — `jmdl_ai_workflows-0.4.0.tar.gz` leaks `jmdl_ai_workflows-0.4.0/.claude/worktrees/agent-a4ae80e60b3022d96/.env.example` (template file, no real secrets — all values empty/commented) despite `/.claude` in `[tool.hatch.build.targets.sdist] exclude`. Root cause: hatchling includes untracked filesystem content in worktrees subdir that the exclusion pattern does not catch. Pre-existing at 0.3.1. Wheel (the uvx/uv-tool-install artefact) is unaffected — PyPI consumers install the wheel, not the sdist.

### CVE scan
`uv tool run pip-audit`: No known vulnerabilities found.

### 🔴 Critical — must fix before publish
None.

### 🟠 High — should fix before publish
None.

### 🟡 Advisory — track; not blocking
- **sdist `.claude/worktrees/` leak (pre-existing)** — `/.claude` sdist exclusion pattern does not catch untracked worktree subdir content. Leaked file is `.env.example` template (no real secrets). Action: add `/.claude/worktrees`, `evals/`, and `runs/` to `[tool.hatch.build.targets.sdist] exclude` in a follow-up task. Not a 0.4.0 wheel blocker — sdist is not the deployed artefact.

### Verdict: SHIP
