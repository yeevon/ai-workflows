# Task 06 — `skill_install.md` uvx option + pre-T07 release smoke — Audit Issues

**Source task:** [../task_06_skill_uvx_release_smoke.md](../task_06_skill_uvx_release_smoke.md)
**Audited on:** 2026-04-22
**Audit scope:** design_branch diff (`skill_install.md` §2 + §3, `release_runbook.md` §5, `CHANGELOG.md`); release-smoke invocation on `main` at `8f1fd8e`; full gate triad on `design_branch`; architecture.md + KDR-002 + KDR-003 cross-check; AC-by-AC grade against the 12 spec ACs; propagation / branch-ref invariants.
**Status:** ✅ PASS — all 12 ACs met; zero design drift; zero open issues. Ready for operator approval + commit.

---

## Design-drift check

Cross-referenced against [design_docs/architecture.md](../../../architecture.md) and the KDRs the task cites:

- **No new dependency.** `pyproject.toml` untouched; the `uvx` install path is a consumer-side invocation of an existing PyPI name (T02 verified name claim) — nothing is pulled into the project's dependency set. Architecture.md §6 dependency list unaffected. ✓
- **No new module / no layer violation.** T06 is docs-only + runbook-log on `design_branch`; `ai_workflows/` byte-identical. `lint-imports` reports 4/4 contracts kept — primitives → graph → workflows → surfaces contract intact. ✓
- **No LLM call added.** T06 ships no code path. `TieredNode` + `ValidatorNode` (KDR-004) pairing not exercised (correctly — nothing to pair). ✓
- **No Anthropic SDK / no `ANTHROPIC_API_KEY` (KDR-003).** `skill_install.md §1`'s "No Anthropic API key required or consulted (KDR-003)" line is preserved byte-identical. `tests/skill/test_doc_links.py::test_skill_install_doc_forbids_anthropic_api` green. ✓
- **No checkpoint / retry / observability change (KDR-006, KDR-007, KDR-009).** None of these surfaces touched. ✓
- **Packaging discipline (KDR-002).** The T06 `uvx --from ai-workflows aiw-mcp` command depends on the T01 + T04 packaging contract (wheel installs the `aiw-mcp` entry point + bundles migrations via the `force-include` hook). The pre-publish release-smoke run on `main` at `8f1fd8e` proved this end-to-end: stage 4 help-smoked `aiw-mcp --help` from the fresh venv; stage 5 applied bundled migrations from the wheel. ✓

**Verdict:** zero design drift. No KDR / architecture.md section violated.

---

## Acceptance criteria grading

| AC | Grade | Evidence |
| --- | --- | --- |
| AC-1 | ✅ PASS | `skill_install.md §2` now carries two H3 sub-headings — `### Option A — clone-based (contributors)` (line 30) and `### Option A-bis — via `uvx` (no clone required)` (line 36). Note: AC-1's text drops the backticks around `uvx` while Deliverable 1's target-state text includes them; builder matched Deliverable 1 (source-of-truth target state). Semantic content identical. |
| AC-2 | ✅ PASS | Option A-bis sub-section contains the registration line `claude mcp add ai-workflows --scope user -- uvx --from ai-workflows aiw-mcp` inside a fenced `bash` block (verified by reading lines 37–39 of the edited file). Orientation prose references `GEMINI_API_KEY` verbatim and points back at `§1` verbatim. Spec-internal drift: spec prescribes "one-sentence note" but its own example body is two sentences; builder reproduced the example verbatim. Content matches spec intent. |
| AC-3 | ✅ PASS | `§3 Install the skill` now opens with the skill-disk-requirement lead-in (a bolded `**Skill install requires the repo on disk**` preamble + the uvx-compatibility clarification). Same spec-internal "one-sentence" label vs multi-sentence body pattern as AC-2; builder reproduced the spec's example body verbatim. |
| AC-4 | ✅ PASS | `git diff` scope on `skill_install.md` is `+14 -2` lines, all inside §2 (lines 26–44 of the edited file) plus one inserted line above §3's first H3 heading. §1 (lines 13–24), §4 (from `## 4. End-to-end smoke`), §5 (from `## 5. HTTP mode`), §6 (from `## 6. Troubleshooting`) are byte-identical in content; line numbers shift by the inserted-lines count but that is unavoidable when inserting content. |
| AC-5 | ✅ PASS | `AIW_BRANCH=design uv run pytest tests/skill/test_doc_links.py -v` reports **4 passed**: `test_skill_install_doc_exists`, `test_skill_install_doc_links_resolve`, `test_skill_install_doc_covers_http_mode`, `test_skill_install_doc_forbids_anthropic_api`. All relative links in `skill_install.md` resolve post-edit. |
| AC-6 | ✅ PASS | `bash scripts/release_smoke.sh` run from `main` at SHA `8f1fd8e` (post-T05 HEAD) exited 0 with six stage headers `[1/6]` … `[6/6]` and the tail `=== OK — release smoke passed ===`. Stage 6 cleanly skipped per the spec's "AIW_E2E=1 is **not** run at T06" directive (env var intentionally unset). Full log at `/tmp/t06_release_smoke.log`. |
| AC-7 | ✅ PASS | `release_runbook.md §5` now carries the T06 log entry with date `2026-04-22`, SHA `8f1fd8e`, branch `main`, result `✅ PASS`, and notes covering (a) the branch-split context, (b) the `main`-only test invariants still holding, (c) the `migrations/001_initial.sql` + `migrations/002_reconciliation.sql` bundling via T01's `force-include` hook, and (d) the unblock signal for T07. Structure matches Deliverables 2 template (date / SHA / branch / result / notes). |
| AC-8 | ✅ PASS | `CHANGELOG.md` on `design_branch` now carries the T06 `[Unreleased]` block *above* the T05 mirror entry (verified: T06 block begins at line 10, T05 mirror block begins at line 48 — T06 precedes T05 chronologically-reversed per Keep-a-Changelog "most recent first" convention). |
| AC-9 | ✅ PASS | `AIW_BRANCH=design uv run pytest` reports **623 passed, 6 skipped** in 23.85s — byte-identical to the T05 close-out baseline. T06 added zero tests (consistent with its doc-only + runbook-log scope); zero regressions. |
| AC-10 | ✅ PASS | `uv run lint-imports` — 4 contracts kept: primitives cannot import graph/workflows/surfaces; graph cannot import workflows/surfaces; workflows cannot import surfaces; evals cannot import surfaces. 0 broken. |
| AC-11 | ✅ PASS | `uv run ruff check` — "All checks passed!". |
| AC-12 | ✅ PASS (by intent) | `main` branch ref unchanged: `git rev-parse main` reports `8f1fd8e` (same SHA the release-smoke was run against) — T06 produced zero commits on `main`. The `git diff main..HEAD -- …` literal reading in the AC text is poorly phrased because it would flag the `CHANGELOG.md` divergence that T05's design-branch mirror block (landed `3c741ce`) already baked in; that divergence is pre-existing, not T06-introduced. Interpreting AC-12 as intent-driven (no T06 commit reaches `main`): ✅. See ADD-2 for the finding classification. |

**Carry-over from prior audits (none):** T05 audit closed with zero forward-deferrals; T06 spec §"Carry-over from prior audits" explicitly confirms "None at T06 drafting". Nothing to tick off.

---

## 🔴 HIGH

*None.*

---

## 🟡 MEDIUM

*None.*

---

## 🟢 LOW

### LOW-1: Spec-internal "one-sentence note" labels describe multi-sentence bodies

The spec prescribes Deliverable 1's Option A-bis orientation note as "One-sentence note:" and the §3 lead-in as "a one-sentence lead-in to §3", but both example bodies span two or three sentences separated by periods. The builder reproduced the spec's example bodies verbatim (the correct call — Deliverable text is more specific than the AC label). Semantic content matches spec intent; no user-visible regression.

**Action / Recommendation:** no change required at T06 close. If a future spec revision tightens the note labels, the builder who lands that task rewrites the prose to match. Record as audit-log note only.

---

## Additions beyond spec — audited and justified

### ADD-1: `release_runbook.md §5` T06 entry notes include migrations-bundle provenance detail

**What:** The T06 log entry's "Notes" field calls out that stage 5 applied `migrations/001_initial.sql` + `migrations/002_reconciliation.sql` via the T01 `force-include` hook. The spec's example body only required "date, SHA, branch, stages pass/fail, any notable observations".

**Why it's justified:** The migrations-from-wheel stage is explicitly flagged as the "most likely regression site" in `release_runbook.md §3` (stage 5 row of the failure-guide table). Recording the concrete bundled migration filenames in the first log entry sets the precedent that future smoke-run entries can regression-check against (e.g. "migrations bundled: 001 + 002" → next release with a new migration should mention "001 + 002 + 003"). Zero scope creep; strengthens the runbook's regression-detection value.

**Verdict:** accept.

### ADD-2: AC-12 reinterpretation documented in the audit rather than flagged as a spec bug

**What:** AC-12's literal text — `git diff main..HEAD -- $(git ls-tree -r --name-only main)` shows no `main`-shipped file touched by T06 — would flag the `CHANGELOG.md` design-branch divergence as a violation. But the divergence is pre-existing (T05's mirror block landed `3c741ce` on `design_branch` only) and the T06 spec's Deliverable 3 explicitly sanctions "No `main`-side CHANGELOG entry at T06".

**Why it's justified:** The AC is self-contradictory between its literal form and the spec's own Deliverable 3 directive; the AC clearly intends "no T06 commit lands on main" (verified: `main` stays at `8f1fd8e`). Rather than grade AC-12 as ❌ FAIL on a spec-language bug, the audit documents the reinterpretation. A future spec-cleanup task (post-M13) should tighten AC-12's wording.

**Verdict:** accept as audit-documented reinterpretation.

---

## Gate summary

| Gate | Command | Result |
| --- | --- | --- |
| pytest | `AIW_BRANCH=design uv run pytest -q` | ✅ 623 passed + 6 skipped (== T05 close baseline) |
| lint-imports | `uv run lint-imports` | ✅ 4 contracts kept, 0 broken |
| ruff | `uv run ruff check` | ✅ All checks passed |
| release-smoke | `bash scripts/release_smoke.sh` (run from `main` at `8f1fd8e`) | ✅ 6/6 stages (stage 6 skipped intentionally); tail `=== OK — release smoke passed ===` |
| skill doc-links | `AIW_BRANCH=design uv run pytest tests/skill/test_doc_links.py -v` | ✅ 4/4 passed |
| branch-ref invariant | `git rev-parse main` vs post-T05 HEAD | ✅ `8f1fd8e` unchanged |

---

## Issue log — cross-task follow-up

*None.* T06 closes clean with zero forward-deferrals.

M13-T06-ISS-01 (closed, LOW) — spec-internal "one-sentence note" label inconsistency documented under LOW-1. No action needed at close-time.

---

## Deferred to nice_to_have

*None.*

---

## Propagation status

- **Forward-deferrals to future tasks:** none.
- **Carry-over into sibling milestone tasks:** none.
- **Target-task spec files amended:** none.

T06 is a standalone doc-only + runbook-log task; T07's pre-publish checks re-run the release smoke from its own working tree, so no T06-owned carry-over is needed in the T07 spec.
