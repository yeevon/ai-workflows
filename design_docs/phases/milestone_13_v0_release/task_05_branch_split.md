# Task 05 — Branch split: land user-facing release slice on `main`, prune builder artefacts from `main`

**Status:** 📝 Planned (drafted 2026-04-22 after T04 audit closed clean and the operator created + pushed `origin/design_branch`).
**Grounding:** [milestone README §Exit criteria 9 + §Branch model](README.md) · [task_01](task_01_pyproject_polish.md) · [task_02](task_02_name_claim_release_smoke.md) · [task_03](task_03_populate_docs.md) · [task_04](task_04_readme_trim.md) · [T04 audit close](issues/task_04_issue.md).

## What to Build

Execute the two-branch split on `main`. The operator has already created `origin/design_branch` from the pre-T01 `main` tip and pushed the T01–T04 builder work as commit `9560fe2 design branch creation`. T05's job is the reciprocal half on `main`:

1. **Adopt on `main`** the user-facing subset of `9560fe2`.
2. **Delete from `main`** the pre-pivot builder artefacts that have lived on `main` since before the two-branch model existed.
3. **Add on `main`** a `.github/CONTRIBUTING.md` pointing at `design_branch`, and a `tests/test_main_branch_shape.py` invariant test.
4. **Replace** the builder-only-marker placeholder on README line 95 with the actual design-branch GitHub URL (`https://github.com/yeevon/ai-workflows/tree/design_branch`).

**Post-T05 `main` is the release branch.** It ships on PyPI at T07. It is user-facing only — no `design_docs/`, no `CLAUDE.md`, no `.claude/commands/`, no `tests/skill/` (depends on `skill_install.md` under `design_docs/`). It carries the M1–M14 runtime (unchanged) + the T01–T04 release-prep deltas.

**Post-T05 `design_branch` is unchanged** except for this T05 spec file and its audit issue file. All future builder work continues on `design_branch`; user-facing deltas are cherry-picked / merged onto `main` per-task at each subsequent T0N close-out.

## Deliverables

### 1. Adoption onto `main` — user-facing slice from `origin/design_branch`

Files in `9560fe2` that belong on both branches and must land on `main`:

| File | Origin | Contents |
| --- | --- | --- |
| `CHANGELOG.md` | T01–T04 work | `[Unreleased]` block (T01 + T02 + T03 + T04 entries) |
| `README.md` | T04 | trimmed 235 → 109 lines |
| `pyproject.toml` | T01 | `authors`, `urls`, `classifiers`, `keywords`, `tool.hatch.build.targets.wheel.force-include` for `migrations/` |
| `docs/architecture.md` | T03 | user-facing arch overview |
| `docs/writing-a-workflow.md` | T03 | workflow-authoring tutorial |
| `docs/writing-a-graph-primitive.md` | T03 | graph-primitive tutorial (replaces `docs/writing-a-component.md`) |
| `docs/writing-a-component.md` | T03 | **deleted** (renamed → `writing-a-graph-primitive.md`) |
| `tests/docs/__init__.py` | T03 | empty (pytest collection) |
| `tests/docs/test_docs_links.py` | T03 | hermetic link-resolution test |
| `tests/docs/test_readme_shape.py` | T04 | hermetic README shape guard |
| `tests/test_scaffolding.py` | T03 | one-line lockstep rename (component → graph-primitive) |
| `tests/test_wheel_contents.py` | T02 | hermetic wheel-contents test |
| `scripts/release_smoke.sh` | T02 | release smoke shell script |

**Execution:** `git checkout design_branch -- <files>` for each path above. The `docs/writing-a-component.md` deletion is done separately (`git rm docs/writing-a-component.md`).

### 2. Deletions from `main` — pre-pivot builder artefacts

Paths that exist on `main` today (from pre-branch-model history) and are builder-only:

- `design_docs/` — entire tree (~50 files: architecture of record, roadmap, ADRs, per-milestone READMEs, task specs, audit issue files, nice_to_have.md, archive/, analysis/).
- `CLAUDE.md` — repo-root Builder/Auditor conventions.
- `.claude/commands/` — slash-command definitions (`implement.md`, `audit.md`, `clean-implement.md`).
- `tests/skill/` — entire directory. Depends on `design_docs/phases/milestone_9_skill/skill_install.md` (deleted with the `design_docs/` tree above). Keeping the suite green would require keeping `skill_install.md` on `main`, which violates the builder-only boundary. The skill itself (`.claude/skills/`) is user-facing and **stays** — only the `tests/skill/` test suite that pins the builder-only walk-through is pruned.
- `scripts/spikes/` — if present. Builder-only exploratory scripts (milestone README §9 lists it explicitly).

**Execution:** `git rm -r <path>` for each.

**Kept on `main`** (do not touch): `ai_workflows/`, `migrations/`, `evals/`, `tests/` (minus `tests/skill/`), `.claude/skills/` (the M9 user-facing skill — ships with the wheel), `.github/`, `.gitignore`, `LICENSE`, `uv.lock`.

### 3. New files on `main`

#### 3a. `.github/CONTRIBUTING.md`

One paragraph + one link + one note. Exact shape:

```markdown
# Contributing to ai-workflows

Development happens on the **`design`** branch. `main` is the release branch
— only user-facing surfaces land here (source, tests, `docs/`, `README.md`,
`CHANGELOG.md`, packaging metadata). The builder/auditor workflow, task
specs, audit issue files, ADRs, and architecture of record live on the
[`design` branch](https://github.com/yeevon/ai-workflows/tree/design_branch).

Clone, switch to `design`, and follow the Builder / Auditor mode conventions
in [`CLAUDE.md`](https://github.com/yeevon/ai-workflows/blob/design_branch/CLAUDE.md).

> **PR direction:** `design → main`, per-task at milestone close-out. Never
> the reverse — `main` must not accumulate builder artefacts.
```

#### 3b. `tests/test_main_branch_shape.py`

Hermetic branch-invariant test. Pins the "no `design_docs/`, no `CLAUDE.md`, no `.claude/commands/` on `main`" boundary. Env-flag-gated inversion so the same test runs green on both branches:

- If `os.environ.get("AIW_BRANCH") == "design"`: assert `design_docs/` **exists** (inverse — catches accidental deletion on design branch).
- Otherwise (main, CI default): assert `design_docs/` / `CLAUDE.md` / `.claude/commands/` / `tests/skill/` are **absent**.

Also asserts `.github/CONTRIBUTING.md` exists unconditionally (lives on both branches).

Three test functions:

- `test_design_docs_absence_on_main` — gated on `AIW_BRANCH != "design"`.
- `test_design_docs_presence_on_design_branch` — gated on `AIW_BRANCH == "design"`; marked `skip` otherwise.
- `test_contributing_md_exists_everywhere` — unconditional, asserts `.github/CONTRIBUTING.md` is present and non-empty.

### 4. README line 95 placeholder → actual URL

[`README.md:95`](../../../README.md) currently reads:

> For the full builder/auditor workflow — task specs, audit issue files, Builder / Auditor mode conventions — switch to the `design` branch (builder-only, on design branch).

Replace with:

> For the full builder/auditor workflow — task specs, audit issue files, Builder / Auditor mode conventions — switch to the [`design` branch](https://github.com/yeevon/ai-workflows/tree/design_branch) (builder-only, on design branch).

One-line edit on `main` (the T04 placeholder was left pending T05 by spec agreement — see T04 spec §Out of scope). The `(builder-only, on design branch)` marker stays on the line so `test_readme_has_exactly_one_design_docs_link` continues to treat the single surviving `design_docs/` line (the roadmap pointer) as the only `design_docs/` match — this new link is `tree/design_branch`, not `design_docs/`, so AC-5 is unaffected.

### 5. `CHANGELOG.md` on `main` — T05 entry

Prepend to `## [Unreleased]`:

```markdown
### Changed — M13 Task 05: branch split — `main` becomes release branch; builder artefacts pruned (YYYY-MM-DD)

Closes M13 exit criterion §9. `main` is now the user-facing release
branch; `design_branch` carries the builder/auditor workflow.

- Deleted from `main`: `design_docs/` (entire tree), `CLAUDE.md`,
  `.claude/commands/`, `tests/skill/` (depends on deleted
  `skill_install.md`).
- Added on `main`: `.github/CONTRIBUTING.md` (one-paragraph pointer at
  `design_branch`), `tests/test_main_branch_shape.py` (branch-invariant
  test with `AIW_BRANCH=design` inversion).
- `README.md:95` placeholder replaced with the actual
  `design_branch` GitHub URL.
- T01–T04 release-prep deltas adopted onto `main` from
  `origin/design_branch@9560fe2`.

All runtime code (`ai_workflows/`) is unchanged. All runtime tests
(`tests/` minus the deleted `tests/skill/` suite) run green on `main`.

**Files touched (on `main`):** see summary above.
**Not touched:** `ai_workflows/`, `migrations/`, `evals/`, `tests/` (except
`tests/skill/` deletion), `.claude/skills/`, `.github/` (except new
`CONTRIBUTING.md`), `LICENSE`, `uv.lock`.
```

The `design_branch` CHANGELOG gets a mirror entry with "Not touched on `design_branch`: everything except this spec file + its audit issue file and the CHANGELOG mirror entry itself" so the audit trail exists on both branches.

## Acceptance Criteria

- [ ] AC-1: `main` does **not** contain `design_docs/`, `CLAUDE.md`, `.claude/commands/`, or `tests/skill/`. Verified via `git ls-tree -r --name-only main | grep -E '^(design_docs/|CLAUDE\\.md$|\\.claude/commands/|tests/skill/)'` → empty.
- [ ] AC-2: `main` contains the T01–T04 user-facing slice: `CHANGELOG.md` with `[Unreleased]` blocks for T01–T04; `README.md` at 109 lines; `pyproject.toml` with `authors` + `urls` + `classifiers` + `keywords` + `force-include`; `docs/architecture.md` / `docs/writing-a-workflow.md` / `docs/writing-a-graph-primitive.md`; `tests/docs/test_docs_links.py` + `tests/docs/test_readme_shape.py` + `tests/test_wheel_contents.py`; `scripts/release_smoke.sh`.
- [ ] AC-3: `main` contains `.github/CONTRIBUTING.md` with the one-paragraph design-branch pointer and the PR-direction note.
- [ ] AC-4: `main` contains `tests/test_main_branch_shape.py` with three test functions (`test_design_docs_absence_on_main`, `test_design_docs_presence_on_design_branch` with `skip` on non-design branches, `test_contributing_md_exists_everywhere`).
- [ ] AC-5: `README.md:95` on `main` carries the actual `design_branch` URL (`https://github.com/yeevon/ai-workflows/tree/design_branch`) + the `(builder-only, on design branch)` marker.
- [ ] AC-6: `uv run pytest` on `main` green. Expected count: 620 (T04 close) + 3 new shape tests (minus the 5 `tests/skill/` tests deleted) = **618**. Spec confirms the delta so cycles match the math.
- [ ] AC-7: `uv run lint-imports` on `main` green — 4 contracts kept.
- [ ] AC-8: `uv run ruff check` on `main` clean.
- [ ] AC-9: `uv run pytest` on `design_branch` green. Expected count: 620 (unchanged). T05 adds no test to `design_branch` except the invariant test (which lands on both). Delta: +3 on `design_branch` too = **623**.
- [ ] AC-10: `tests/test_main_branch_shape.py` runs green on **both** branches (the `AIW_BRANCH` env-flag inversion is the mechanism).
- [ ] AC-11: CHANGELOG `[Unreleased]` T05 block lands on both branches (at `main` it's above the T04 block; on `design_branch` it's prepended with a one-line "mirror of main" note).
- [ ] AC-12: This spec file (`task_05_branch_split.md`) lands on `design_branch` only. It does **not** ship to `main` (lives under `design_docs/`, which `main` does not contain).
- [ ] AC-13: The audit issue file (`issues/task_05_issue.md`) lands on `design_branch` only. Same reason.
- [ ] AC-14: No runtime behaviour change. `ai_workflows/` is byte-identical on both branches after T05.

## Dependencies

- **T04 complete + clean** (✅ landed + audit-closed 2026-04-22).
- **`origin/design_branch` exists** (✅ created by the operator before T05 drafting).
- **No external dependency.**

## Out of scope (explicit)

- **No `ai_workflows/` change.** T05 is git topology + doc-shape only.
- **No `docs/` edit.** T03 shipped that tree; it propagates to `main` via the `git checkout design_branch --` adoption step, unchanged.
- **No new CI job.** The existing `uv run pytest` + `lint-imports` + `ruff check` gates cover `main` automatically once the branch is the tracked default.
- **No PyPI publish.** T07's scope.
- **No `skill_install.md` uvx option.** T06's scope on `design_branch`. After T06, the uvx option + command wording get cherry-picked onto `main` along with any `README.md § MCP server` adjustments.
- **No milestone close-out.** T08's scope.
- **No force-push.** T05 creates a regular commit on `main`; no history rewrite.
- **No `git reset --hard` on `main`.** The branch-split adoption is done via forward commits, not via `reset`. The operator's pre-T05 `git` state on `main` (at `e6113e1`) is the base; T05 lands one new commit on top.

## Execution protocol

Because T05 is destructive on `main` (~50 files deleted), the Builder executes as follows and **pauses** before pushing:

1. Check out `main` locally. Verify clean working tree (`git status` empty).
2. Verify `origin/main` HEAD matches the local `main` HEAD (`git fetch && git log origin/main..main` empty, `git log main..origin/main` empty).
3. Apply the deletions: `git rm -r design_docs/ CLAUDE.md .claude/commands/ tests/skill/ scripts/spikes/` (skip any path that does not exist — `scripts/spikes/` may not).
4. Apply the adoptions: `git checkout design_branch -- <file-list-from-deliverables-table>`. Delete `docs/writing-a-component.md` if it comes back (it is deleted on `design_branch`, so the checkout should not re-introduce it — verify after).
5. Add the new files: write `.github/CONTRIBUTING.md` + `tests/test_main_branch_shape.py`.
6. Edit `README.md:95` (replace placeholder with URL).
7. Prepend CHANGELOG T05 block above T04's `[Unreleased]` entries.
8. Run the three gates locally: `uv run pytest`, `uv run lint-imports`, `uv run ruff check`. Fix anything red before proceeding.
9. Show the full `git diff --stat` + `git status` to the operator. **Stop and wait for "proceed"** before the commit.
10. On operator's "proceed": single commit on `main` titled `M13 T05 — branch split: user-facing release slice on main (KDR-002)`. Push to `origin/main`.
11. Switch back to `design_branch`. Add this spec file + the audit issue file + a mirror CHANGELOG entry. Commit on `design_branch` titled `M13 T05 spec + branch-split close-out on design branch`. Push.

**The commit on `main` is the point of no return on the PR-direction discipline.** Merging `main` back into `design_branch` at any later time would re-introduce deletions on `design_branch`. The merge direction is `design → main` only; at release time the cherry-pick is file-scoped. CLAUDE.md "non-negotiables" + milestone README §Branch model make this explicit.

## Propagation status

Filled in at audit time. Anticipated forward-deferrals:

- **T06-owned.** `skill_install.md §2` gets the "Option A-bis — via uvx (no clone required)" sub-section. Lives on `design_branch` under `design_docs/phases/milestone_9_skill/skill_install.md`. The file stays on `design_branch` only — `main` never sees it (same reason `tests/skill/` is deleted on `main` at T05).
- **T06-owned.** Any README.md `## MCP server` wording change to reflect the finalized uvx command is cherry-picked onto `main` at T06 close-out, not here.

Both are T06-owned; nothing on T05 carries forward.

## Carry-over from prior audits

None at T05 drafting. The T04 audit closed with zero forward-deferrals.
