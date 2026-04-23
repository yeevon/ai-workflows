# Task 07 — `[0.1.0]` CHANGELOG section + first PyPI publish — Audit Issues

**Source task:** [../task_07_changelog_publish.md](../task_07_changelog_publish.md)
**Audited on:** 2026-04-22 (pre-publish audit; close-out amendment to follow per §Execution step 15)
**Audit scope:** At this pre-publish pass, scope covers the `design_branch`-side work that lands in the step-6 commit — `CHANGELOG.md` `[0.1.0]` block draft + T07 `[Unreleased]` mirror entry, T07 spec file, this issue file. ACs verifiable on `design_branch` alone are graded now; `main`-side work + the destructive `uv publish` + the post-publish live smoke + the `### Published` footer stamping are deferred to the post-publish audit amendment and marked `⏳ pending-<step>` below.
**Status:** ✅ PASS — `jmdl-ai-workflows==0.1.0` is live on pypi.org (`https://pypi.org/project/jmdl-ai-workflows/0.1.0/`); post-publish `uvx --refresh --from jmdl-ai-workflows==0.1.0 aiw version` from `/tmp` prints `0.1.0` against a fresh uvx cache. All 11 ACs ✅. Rename footnote: first `uv publish` on 2026-04-22 was rejected with `400 The name 'ai-workflows' is too similar to an existing project.` Renamed to `jmdl-ai-workflows` (spec §Rename addendum; CHANGELOG `[Unreleased] ### Changed — M13 Task 07: PyPI distribution renamed…`). Zero HIGH findings; zero deferred-to-nice_to_have. Release-commits pair: `main:9fe1898`, `design_branch:2771580`.

---

## Design-drift check

Cross-referenced against [design_docs/architecture.md](../../../architecture.md) and the KDRs the task cites (KDR-002 surface portability, KDR-008 MCP schema public contract):

- **No new dependency.** `pyproject.toml` untouched pre-publish; T07 adds only CHANGELOG + doc edits. Architecture.md §6 dependency list unaffected. ✓
- **No new module.** T07 is CHANGELOG + publish only; `ai_workflows/` byte-identical. `lint-imports` 4/4 contracts kept on `design_branch`. ✓
- **No LLM call added / no Anthropic SDK / no `ANTHROPIC_API_KEY` (KDR-003).** T07 ships no code path; release-smoke on `main` was green at T06 close under the same KDR-003 preservation. ✓
- **No checkpoint / retry / observability change (KDR-006, KDR-007, KDR-009).** None of these surfaces touched. ✓
- **Packaging discipline (KDR-002).** The T07 `uv publish` + post-publish `uvx --from ai-workflows==0.1.0 aiw version` path exercises exactly the KDR-002 "surface portability" contract — the wheel that uploads to PyPI is the same wheel shape the T06 release-smoke green-lit at `main` HEAD `8f1fd8e`. ✓ (Pending step 9 re-run of `scripts/release_smoke.sh` against the T07 CHANGELOG commit to confirm no regression the CHANGELOG edit itself introduced.)
- **MCP schema public contract (KDR-008).** `0.1.0` is the version at which the four MCP tool schemas freeze their shape — `run_workflow`, `resume_run`, `list_runs`, `cancel_run`. The `[0.1.0]` CHANGELOG block lists them under "MCP surfaces" in the `### Added` inventory without overspecifying wire shape (the shape lives in `ai_workflows.mcp` module docstrings + M4 T02 tests, not release notes). ✓

**Verdict:** zero design drift pre-publish. No KDR / architecture.md section violated. Post-publish audit amendment (step 15) will re-verify KDR-002 + KDR-008 against the actual pypi.org-hosted artefact.

---

## Acceptance criteria grading (post-publish close-out)

| AC | Grade | Evidence |
| --- | --- | --- |
| AC-1 | ✅ PASS | `CHANGELOG.md` on `main` carries the `## [0.1.0] — 2026-04-22` block with the full `### Added` inventory + `### Published` footer. Landed in three commits: `00968cc` (block created, T01-T05 builder entries absorbed), `56cedd5` (rename cherry-pick), `9fe1898` (footer stamped post-publish). |
| AC-2 | ✅ PASS | `main`'s `[Unreleased]` was emptied of the T01-T05 per-task entries by `00968cc` — diff shows -391 / +60 on `CHANGELOG.md` for that commit. Only `[Unreleased]` + `[0.1.0]` + historical `[MNN …]` blocks remain on `main`. |
| AC-3 | ✅ PASS | `design_branch` `[0.1.0]` block body is byte-identical to `main`'s on the `### Added` inventory. Diff check: `git show main:CHANGELOG.md` vs `git show design_branch:CHANGELOG.md` for the `[0.1.0]` block body produces zero diff lines on the `### Added` bullets (the `### Published` footer is also byte-identical post `2771580` cherry-pick). |
| AC-4 | ✅ PASS | `CHANGELOG.md` on `design_branch` preserves the T01–T06 free-standing entries under `## [Unreleased]` byte-identical. T07 design-branch mirror entry + rename entry are above them. |
| AC-5 | ✅ PASS | `scripts/release_smoke.sh` logged twice in `release_runbook.md §5`: 2026-04-22 T06 pre-publish at `main` `8f1fd8e` (original entry) + 2026-04-22 T07 post-rename pre-publish at `main` `56cedd5` / `design_branch` `146c9fe` (rename entry). Both green, all six stage headers emitted. |
| AC-6 | ✅ PASS | Full gate green on both branches: `uv run pytest` → `main` 610 passed + 9 skipped; `design_branch` 623 passed + 6 skipped. `uv run lint-imports` → 4 contracts kept. `uv run ruff check` → clean. |
| AC-7 | ✅ PASS | `uv publish dist/jmdl_ai_workflows-0.1.0-py3-none-any.whl` returned 200; `curl /pypi/jmdl-ai-workflows/0.1.0/json` returns 200. Project page at `https://pypi.org/project/jmdl-ai-workflows/0.1.0/` resolves. **Caveat:** first attempt under name `ai-workflows` returned 400 similarity-reject; rename to `jmdl-ai-workflows` documented in spec §Rename addendum. |
| AC-8 | ✅ PASS | `cd /tmp && uvx --refresh --from jmdl-ai-workflows==0.1.0 aiw version` printed `0.1.0` (stdout). `uv` resolved 122 packages into a fresh cache against real pypi.org and the `aiw` entry point ran successfully. |
| AC-9 | ✅ PASS | `### Published` footer on both branches carries: PyPI URL `https://pypi.org/project/jmdl-ai-workflows/0.1.0/`, wheel `jmdl_ai_workflows-0.1.0-py3-none-any.whl`, SHA256 `1087075fb90d3ae9e760366620f118e37eb4325264cc1c96133c1acc1def6fa8`, publish-side commit `56cedd5`, pre-publish smoke log reference, post-publish live-smoke line. Stamped by `main:9fe1898` / `design_branch:2771580` (cherry-pick). |
| AC-10 | ✅ PASS | Gate green on both branches per AC-6; no runtime-code regression from the rename (pytest + lint-imports + ruff all green). |
| AC-11 | ✅ PASS | Final diff scope: `main` touched `pyproject.toml`, `README.md`, `CHANGELOG.md`, `docs/writing-a-workflow.md`, `scripts/release_smoke.sh`, `tests/test_wheel_contents.py`, `uv.lock`. `design_branch` additionally touched `design_docs/phases/milestone_9_skill/skill_install.md`, `design_docs/phases/milestone_13_v0_release/release_runbook.md`, `design_docs/phases/milestone_13_v0_release/task_07_changelog_publish.md`, `design_docs/phases/milestone_13_v0_release/issues/task_07_issue.md`. No `ai_workflows/` runtime-code edits on either branch ✓. |

**Carry-over from prior audits (none):** T06 audit closed with zero forward-deferrals; T07 spec §"Carry-over from prior audits" confirms.

---

## 🔴 HIGH

*None at pre-publish pass.*

---

## 🟡 MEDIUM

*None at pre-publish pass.*

---

## 🟢 LOW

### LOW-1: Spec-internal phrasing "above the T06 entry" for the `[0.1.0]` block placement on `design_branch`

The T07 spec Deliverable 1 §Branch-specific CHANGELOG shapes (`design_branch` half) says "Prepend a new `## [0.1.0] — 2026-04-22` block above the existing `## [Unreleased]` block's T06 entry". Read literally, this would place `[0.1.0]` **inside** `[Unreleased]` (structurally invalid for Keep-a-Changelog). The builder resolved the ambiguity by placing `[0.1.0]` at the natural Keep-a-Changelog position — directly above the first per-milestone historical block (`## [M14 MCP HTTP Transport] - 2026-04-22`), below all `[Unreleased]` content.

**Action / Recommendation:** no change required at T07 close. If a future CHANGELOG-format spec tightens this, the edit is a two-line re-placement. Record as audit-log note only — content and semantic intent are preserved.

---

## Additions beyond spec — audited and justified

### ADD-1: `### Published` footer includes a `**Pre-publish release-smoke:**` line citing both T06 and T07 smoke entries

**What:** The `[0.1.0]` block's `### Published` footer ends with a line that cites both the T06 pre-publish smoke at SHA `8f1fd8e` AND the T07 publish-side commit's smoke re-run. The spec's Deliverable 1 body lists four captured values (PyPI URL, wheel filename, SHA256, publish-side commit) and the smoke-citation line is a fifth.

**Why it's justified:** The `release_runbook.md §3` stage-by-stage failure guide marks stage 5 (migrations-from-wheel) as "most likely regression site". Carrying the two smoke-run SHAs forward into the user-visible CHANGELOG gives a future operator auditing a defect on `0.1.0` a two-hop trail back to "last known good wheel builds" without having to spelunk `release_runbook.md`. Zero scope creep; strengthens the regression-detection audit trail.

**Verdict:** accept.

---

## Gate summary (pre-publish)

| Gate | Command | Result |
| --- | --- | --- |
| pytest (design) | `AIW_BRANCH=design uv run pytest -q` | ✅ 623 passed + 6 skipped (unchanged from T06 close baseline) |
| lint-imports | `uv run lint-imports` | ✅ 4 contracts kept, 0 broken |
| ruff | `uv run ruff check` | ✅ All checks passed |
| release-smoke (T07 re-run) | `bash scripts/release_smoke.sh` from `main` at T07 CHANGELOG commit | ⏳ step-9 |
| wheel-contents (main) | `AIW_BRANCH=main uv run pytest tests/test_wheel_contents.py -v` from `main` | ⏳ step-8 |
| uv publish | `uv publish --token "$UV_PUBLISH_TOKEN"` from `main` | ⏳ step-11 (destructive; operator pause 2) |
| post-publish live smoke | `uvx --from ai-workflows==0.1.0 aiw version` from `/tmp` | ⏳ step-12 |

---

## Issue log — cross-task follow-up

*None at pre-publish pass.*

M13-T07-ISS-01 (pre-open, LOW) — design-branch `[0.1.0]` placement ambiguity documented under LOW-1. Will close at step 15.

---

## Deferred to nice_to_have

- **CI-gated publish-on-tag job.** `nice_to_have.md §17+` candidate. Trigger: "a second maintainer joins" OR "an out-of-band token is mishandled during manual publish". Neither has fired — T07 keeps the manual flow. Re-evaluate after the third `0.1.x` patch release.

---

## Post-close operator actions

To be surfaced after step 16 (close-out report):

- **Rotate `PYPI_TOKEN`.** The current token is account-wide-scoped (project-scoped tokens are not creatable pre-first-upload). Revoke on pypi.org → Account Settings → API tokens. Create a new project-scoped token for post-0.1.0 publishes. This is standard PyPI hygiene, not T07 scope, but the audit surfaces it so the operator doesn't forget.
- **Optional: rotate `GEMINI_API_KEY`.** The key value is in the conversation transcript (via the earlier `grep` on `.env` during T07 kickoff). Local-only `.jsonl` storage is trusted per operator direction; rotation is operator-optional.

---

## Propagation status

- **Forward-deferrals to future tasks:** none at pre-publish pass.
- **Carry-over into sibling milestone tasks:** none — T08 (milestone close-out) gets the T07 outcome via the CHANGELOG + audit file, not via carry-over.
- **Target-task spec files amended:** none pre-publish.

The post-publish audit amendment (step 15) will re-verify propagation state after the destructive work lands.
