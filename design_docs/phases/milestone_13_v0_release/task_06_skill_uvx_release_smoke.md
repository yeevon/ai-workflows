# Task 06 — `skill_install.md` uvx option + pre-T07 release smoke invocation

**Status:** 📝 Planned (drafted 2026-04-22 after T05 audit closed clean and branch split landed on main as `8f1fd8e`).
**Grounding:** [milestone README §Exit-criteria-3 + §Exit-criteria-8](README.md) · [task_05 close](issues/task_05_issue.md) · [skill_install.md §2](../milestone_9_skill/skill_install.md) · [release_runbook.md](release_runbook.md) · [scripts/release_smoke.sh](../../../scripts/release_smoke.sh).

## What to Build

Two small, orthogonal deliverables that together unblock T07 (the first PyPI publish):

1. **`skill_install.md §2` rewrite** — add the `uvx` install option for the MCP server. Post-T06, a first-time user who has never cloned the repo can register `aiw-mcp` with Claude Code directly from PyPI. The existing clone-based Option A stays as the contributor path.
2. **Manual pre-publish release-smoke invocation** — run `bash scripts/release_smoke.sh` from `main` against the latest post-T05 commit. Record the outcome in `release_runbook.md` under a new `## 5. Release smoke invocation log` section so T07 has an up-to-date "last known good" reference before publishing `0.1.0` to PyPI.

T06 is **design_branch-only** for the doc change (`skill_install.md` lives under `design_docs/`). The release-smoke run itself happens from `main` (per `release_runbook.md §2` pre-flight step 1 — "release branch must be `main`"); the run outcome lands on `design_branch` in `release_runbook.md`.

## Deliverables

### 1. [`design_docs/phases/milestone_9_skill/skill_install.md`](../milestone_9_skill/skill_install.md) — §2 rewrite

**Current state.** §2 is a one-paragraph redirect at `../milestone_4_mcp/mcp_setup.md`. It has no sub-headings; it names the clone-based `uv run aiw-mcp` form without pairing it with the uvx alternative.

**Target state.** §2 has two sub-headings, each ~5 lines:

- **Option A — clone-based (contributors)** — the existing flow, with the existing redirect at `mcp_setup.md`.
- **Option A-bis — via `uvx` (no clone required)** — new sub-section. One code block + one sentence of orientation. The registration line is:

  ```bash
  claude mcp add ai-workflows --scope user -- uvx --from ai-workflows aiw-mcp
  ```

  One-sentence note: "No repo clone needed — `uvx` fetches the latest `ai-workflows` wheel into its cache on first invocation and every Claude Code session reuses it. `GEMINI_API_KEY` still needs to be exported in the shell that launches Claude Code (see §1)."

**§3 intro addendum.** Existing §3 (Install the skill) covers Option A (in-repo) + Option B (user-level symlink) + Option C (plugin, deferred). Post-T06, add a one-sentence lead-in to §3:

> **Skill install requires the repo on disk** — Options A and B below both assume `.claude/skills/ai-workflows/SKILL.md` resolves to a local file. If you took §2's Option A-bis (uvx, no clone) for the MCP server, you can still use Option B below after a one-time `git clone` just to own the skill directory; the MCP subprocess side remains uvx-driven.

The existing Option A / B / C bodies are unchanged — only the §3 intro grows one sentence.

**§1, §4, §5, §6 unchanged.** Prerequisites, E2E smoke, HTTP mode, troubleshooting all survive the T06 edit byte-identical.

### 2. Manual release-smoke invocation + log entry in [`release_runbook.md`](release_runbook.md)

**Invocation context.** Run from the local working tree on `main` branch at post-T05 HEAD. The goal is to prove the wheel that T07 will upload is installable + runnable on a clean venv before the upload happens — the exact gate `release_runbook.md §1` prescribes.

**Execution steps.**

1. `git checkout main` (the release branch).
2. `git status --short` — empty (T05 landed cleanly).
3. `git log -1 --oneline` — record the SHA being smoked (expected: `8f1fd8e` or a later T06-owned cherry-pick if one lands).
4. `which uv` — resolves.
5. `bash scripts/release_smoke.sh` — expect six `[N/6]` stage headers ending in `=== OK — release smoke passed ===`. Do **not** run the `AIW_E2E=1` live-provider stage at T06; T07 owns the post-publish live validation.
6. Record the run outcome (pass/fail, SHA, date, observations) in `release_runbook.md` under a new `## 5. Release smoke invocation log` section.

**Log-entry structure** (new §5 in `release_runbook.md`):

```markdown
## 5. Release smoke invocation log

A rolling log of every pre-publish smoke run. Keep chronological — most recent at the bottom. Each entry has: date, SHA, branch, stages pass/fail, any notable observations.

### YYYY-MM-DD — M13 T06 pre-publish smoke
- **SHA:** <main-HEAD-sha>
- **Branch:** main
- **Result:** ✅ PASS (stages 1–5) / ❌ FAIL at stage N (details below)
- **Notes:** <observations — e.g. "first invocation after post-T05 branch split; migrations applied from wheel-bundled `migrations/001_initial.sql` + `002_reconciliation.sql`.">
```

**Failure handling.** If a stage fails, the T06 Builder stops and surfaces the failure to the operator. No automated fix: the failure modes (broken entry point, missing `force-include`, dependency drift) are spec-level regressions that need targeted patches — either on `design_branch` (if the fix applies to builder surfaces) or on `main` (if it applies to the shipped wheel). The spec-level fix goes in before T06 closes, and T06 re-runs the smoke to confirm green.

### 3. `CHANGELOG.md` on `design_branch` — T06 entry

Under `## [Unreleased]`, prepend above the T05 mirror block:

```markdown
### Changed — M13 Task 06: skill_install.md uvx option + pre-publish release-smoke run (YYYY-MM-DD)

Adds the "Option A-bis — via uvx (no clone required)" sub-section to
`design_docs/phases/milestone_9_skill/skill_install.md §2` and logs
the T06 pre-publish `scripts/release_smoke.sh` run against `main`
HEAD `<sha>` in `release_runbook.md §5`.

**Files touched (design_branch only):**
- `design_docs/phases/milestone_9_skill/skill_install.md` — §2
  rewritten with Option A + Option A-bis sub-headings; §3 intro
  grows a one-sentence skill-disk-requirement note.
- `design_docs/phases/milestone_13_v0_release/release_runbook.md` — new
  §5 "Release smoke invocation log" with the T06 entry.
- `design_docs/phases/milestone_13_v0_release/task_06_skill_uvx_release_smoke.md`
  — spec drafted at T06 kickoff.
- `design_docs/phases/milestone_13_v0_release/issues/task_06_issue.md`
  — audit file.
- `CHANGELOG.md` — this entry.

**Not touched:** `ai_workflows/` (no runtime change);
`pyproject.toml` (no dep); `main` branch (skill_install.md is
design_branch-only; README.md `## MCP server` on main already carries
the uvx command from T04 so no cherry-pick is needed).
```

**No `main`-side CHANGELOG entry at T06** — `main` has no corresponding file edit (`skill_install.md` does not ship there, and `release_runbook.md` does not ship there). T08 milestone close-out stamps the T06 landing into the milestone README on `design_branch` but does not reach into `main`.

## Acceptance Criteria

- [ ] AC-1: `skill_install.md §2` contains two H3 sub-headings — `### Option A — clone-based (contributors)` and `### Option A-bis — via uvx (no clone required)`.
- [ ] AC-2: `skill_install.md §2` Option A-bis sub-section contains exactly the registration line `claude mcp add ai-workflows --scope user -- uvx --from ai-workflows aiw-mcp` inside a fenced `bash` code block, plus a one-sentence orientation note that references `GEMINI_API_KEY` and points back at §1.
- [ ] AC-3: `skill_install.md §3` intro carries the one-sentence skill-disk-requirement lead-in (see §Deliverables 1).
- [ ] AC-4: `skill_install.md §1, §4, §5, §6` are byte-identical to the pre-T06 state. Verified by `git diff --stat` scope containing only the §2 + §3 lines.
- [ ] AC-5: `tests/skill/test_doc_links.py` on `design_branch` stays green. `skill_install.md` still resolves every relative link post-edit; the `test_skill_install_doc_exists` + `test_skill_install_doc_links_resolve` + `test_skill_install_doc_covers_http_mode` + `test_skill_install_doc_forbids_anthropic_api` tests all pass.
- [ ] AC-6: `bash scripts/release_smoke.sh` run from `main` at post-T05 HEAD exits 0 with the six-stage "`=== OK — release smoke passed ===`" tail. `AIW_E2E=1` stage is **not** run at T06.
- [ ] AC-7: `release_runbook.md §5` contains the T06 log entry with date + SHA + branch + result + notes per the structure in §Deliverables 2.
- [ ] AC-8: `CHANGELOG.md` on `design_branch` carries the T06 `[Unreleased]` block above the T05 mirror entry.
- [ ] AC-9: `uv run pytest` on `design_branch` (`AIW_BRANCH=design`) reports the same 623 passed + 6 skipped as T05 close (T06 adds zero tests — it is a doc-only + runbook-log task).
- [ ] AC-10: `uv run lint-imports` on `design_branch` — 4 contracts kept.
- [ ] AC-11: `uv run ruff check` on `design_branch` — clean.
- [ ] AC-12: Zero diff on `main`. `git diff main..HEAD -- $(git ls-tree -r --name-only main)` shows no `main`-shipped file touched by T06. (Exception: if the release-smoke exposes a regression on `main`, the fix lands as a separate commit cherry-picked onto both branches — see §Failure handling.)

## Dependencies

- **T05 complete + clean** (✅ landed 2026-04-22, commit `8f1fd8e` on `main` + `3c741ce` on `design_branch`).
- **No external dependency.**

## Out of scope (explicit)

- **No `ai_workflows/` change.** T06 is docs + manual release-gate invocation only.
- **No test additions.** `tests/skill/test_doc_links.py` already pins `skill_install.md` link integrity — T06 only has to keep it green.
- **No PyPI publish.** T07's scope.
- **No `AIW_E2E=1` live-provider smoke.** T07 owns the post-publish `uvx --from ai-workflows==0.1.0 aiw version` live round-trip; T06's smoke stays hermetic.
- **No cherry-pick onto `main`.** `skill_install.md` is design_branch-only; `release_runbook.md` is design_branch-only. `main`'s `README.md:79` already carries the uvx command form from T04 — unchanged by T06.
- **No `skill_install.md` Option C (plugin) change.** T02-in-M9 gated Option C on triggers that have not fired; T06 does not re-open it.
- **No pypi.org name-claim re-check.** T02 verified the name; T06 does not re-probe pypi.org.

## Execution protocol

Same "operator approval before push" discipline as T05 (less destructive, but still ships a release-gate artefact):

1. Apply the `skill_install.md` §2 + §3 edit on `design_branch`.
2. Switch to `main` (clean working tree expected post-T05).
3. Run `bash scripts/release_smoke.sh` from the repo root. Capture the full output.
4. Switch back to `design_branch`. Append the log entry to `release_runbook.md §5`.
5. Prepend the T06 CHANGELOG block on `design_branch`.
6. Run the three gates on `design_branch`: `AIW_BRANCH=design uv run pytest` + `uv run lint-imports` + `uv run ruff check`.
7. Write the audit issue file at `design_docs/phases/milestone_13_v0_release/issues/task_06_issue.md`.
8. Show the operator the final `git diff --stat` + `git status` on `design_branch`. **Stop and wait for "proceed"** before the commit.
9. On operator's "proceed": single commit on `design_branch` titled `M13 T06 — skill_install.md uvx option + pre-T07 release smoke`. Push.

## Propagation status

Filled in at audit time. Anticipated forward-deferrals: none. T06 is a doc-only + one-shot manual-invocation task; T07 does its own pre-publish smoke check.

## Carry-over from prior audits

None at T06 drafting. The T05 audit closed with zero forward-deferrals.
