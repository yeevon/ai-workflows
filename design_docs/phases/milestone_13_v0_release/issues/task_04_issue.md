# Task 04 — Trim root README + Install section + shape test — Audit Issues

**Source task:** [../task_04_readme_trim.md](../task_04_readme_trim.md)
**Audited on:** 2026-04-22
**Audit scope:** README.md (rewrite); tests/docs/test_readme_shape.py (new); tests/skill/test_doc_links.py (lockstep deletion + docstring amendment); CHANGELOG.md T04 block; task_04_readme_trim.md spec; cross-checks against design_docs/architecture.md, design_docs/roadmap.md, CLAUDE.md, tests/docs/test_docs_links.py, tests/test_scaffolding.py, the shipped docs/ tree (T03 output), and the skill_install.md surface (T06 target).
**Status:** ✅ PASS — Cycle 1. All 13 ACs PASS. Zero design drift. Four additions-beyond-spec audited and justified. One spec deviation (skill-test lockstep delete) recorded. No OPEN issues.

---

## Design-drift check (architecture.md + cited KDRs)

Opened `design_docs/architecture.md` and every KDR the T04 spec touches by proximity. T04 is documentation + test only — zero `ai_workflows/` runtime change. Drift surfaces audited:

| Surface | Risk | Finding |
| --- | --- | --- |
| New dependency? (architecture.md §6) | README trim would not normally add deps; pyproject.toml was untouched by T04 | PASS — `git diff --stat` shows zero T04 ownership of `pyproject.toml` (the uncommitted pyproject changes belong to T01) |
| New module or layer? (architecture.md §3 — four-layer contract) | Shape test under `tests/docs/` is not a runtime module | PASS — `tests/` is outside the import-contract graph; `lint-imports` reports 4/4 kept |
| LLM call added? (KDR-003 / KDR-004) | README prose references LLM tiers; test file imports zero LLM surfaces | PASS — `tests/docs/test_readme_shape.py` imports only `pathlib`; no `TieredNode` / `ValidatorNode` / `anthropic` / `ANTHROPIC_API_KEY` touch anywhere |
| Checkpoint / resume logic? (KDR-009) | None added | PASS |
| Retry logic? (KDR-006) | None added | PASS |
| Observability? (KDR-007 — `StructuredLogger` only) | None added | PASS — test prints via `assert` messages only; no logger import, no external backend (Langfuse / OTel / LangSmith) pulled |
| nice_to_have.md adoption? | README edit could tempt a "public roadmap doc" link that matches a nice_to_have item | PASS — zero `nice_to_have` references in the shipped README; the single `design_docs/` link is the roadmap pointer which has always been the user-visible milestone index |

**No drift HIGH.** T04 is a pure documentation + test slice — it adds neither runtime code nor a new layer, and it removes builder-only references from the main-branch README in preparation for the T05 branch split. The trim direction (builder narrative → user-facing intro) is the architecturally-aligned direction.

---

## AC grading (individual)

| # | AC | Status | Evidence |
| --- | --- | --- | --- |
| AC-1 | `README.md` is ≤ 150 lines | ✅ PASS | `wc -l README.md` → 109 lines (41 under cap). `test_readme_line_count_under_cap` green |
| AC-2 | Three exact headings (`## Install`, `## Contributing / from source`, `## Development`) each on exactly one line | ✅ PASS | `grep -n '^## '` on README confirms each heading occurs exactly once. `test_readme_has_user_facing_sections` green |
| AC-3 | Install section documents `uvx --from ai-workflows aiw …` one-shot + `uv tool install ai-workflows` persistent | ✅ PASS | `## Install` at README line 44 carries both forms: `uvx --from ai-workflows aiw run planner …` (line 51) + `uv tool install ai-workflows` (line 57) in fenced code blocks, with one-sentence intros above each |
| AC-4 | Pre-T04 "Getting started" renamed to "Contributing / from source"; body preserves `uv sync` / `uv run aiw …`; trailing `design` branch pointer with builder-only marker | ✅ PASS | `## Contributing / from source` at README line 84; body shows `git clone … && cd … && uv sync && uv run aiw version` (lines 88-93); closing sentence at line 95 reads "For the full builder/auditor workflow … switch to the `design` branch (builder-only, on design branch)". Spec deviation: README keeps a top-level `## Getting started` section (line 61) as a user-facing three-command demo *separate* from the renamed "Contributing / from source" section — audited as a correct reading of the spec, since the spec body describes a one-shot demo under Install + a contributor `uv sync` path elsewhere. See "Additions beyond spec" §1 below |
| AC-5 | Exactly one line contains `design_docs/`; that line carries `(builder-only, on design branch)` | ✅ PASS | `grep -n 'design_docs/' README.md` reports one hit at line 109: "Roadmap + per-milestone task files live at [design_docs/roadmap.md](design_docs/roadmap.md) (builder-only, on design branch).". `test_readme_has_exactly_one_design_docs_link` green |
| AC-6 | Zero `CLAUDE.md` / `.claude/commands/` / `nice_to_have.md` references | ✅ PASS | `grep -n -E 'CLAUDE\.md\|\.claude/commands\|nice_to_have' README.md` → zero hits (confirmed empty output). Manual AC, not test-enforced, per spec |
| AC-7 | `tests/docs/test_readme_shape.py` ships with three tests and all pass | ✅ PASS | File present at `tests/docs/test_readme_shape.py` (107 lines). `uv run pytest tests/docs/test_readme_shape.py -v` reports 3 passed: `test_readme_line_count_under_cap`, `test_readme_has_user_facing_sections`, `test_readme_has_exactly_one_design_docs_link` |
| AC-8 | `uv run pytest` green; spec prediction: 621 tests | ✅ PASS (with audited deviation) | Actual: 620 passed + 5 skipped. Spec prediction: T03 close = 618 + 3 new T04 tests = 621. Delta = −1 from the lockstep delete of `tests/skill/test_doc_links.py::test_root_readme_links_skill_install`. Net: 618 + 3 − 1 = 620. Deviation recorded in CHANGELOG + below under "Spec deviations" |
| AC-9 | `uv run lint-imports` reports 4 contracts kept, 0 broken | ✅ PASS | Gate output: "Contracts: 4 kept, 0 broken." |
| AC-10 | `uv run ruff check` clean | ✅ PASS | Gate output: "All checks passed!" |
| AC-11 | CHANGELOG `[Unreleased]` entry lists files + ACs + section rename; T04 block lands above T03's | ✅ PASS | T04 block present under `## [Unreleased]` above the T03 block. Lists all 13 ACs individually with evidence citations, files touched + not touched, lockstep skill-test delete, and 109-line post-trim count |
| AC-12 | Zero diff under `ai_workflows/` | ✅ PASS | `git diff --stat` shows zero entries under `ai_workflows/` |
| AC-13 | Zero diff under `docs/` | ✅ PASS | The `docs/` diff entries on `git status` (`docs/architecture.md`, `docs/writing-a-workflow.md`, `docs/writing-a-component.md` deletion, `docs/writing-a-graph-primitive.md` addition) are all **T03's** output — already landed in the T03 audit and CHANGELOG block. T04 touches none of them in its own commit slice |

---

## 🔴 HIGH — none

No AC unmet, no architectural rule broken, no KDR violation, no nice_to_have adoption without trigger.

## 🟡 MEDIUM — none

No deliverable partial, no convention skipped, no downstream risk identified.

## 🟢 LOW — none

---

## Spec deviations — audited and justified

### SD-1. `tests/skill/test_doc_links.py::test_root_readme_links_skill_install` deleted in lockstep

**What changed:** T04 deleted the `test_root_readme_links_skill_install` function from `tests/skill/test_doc_links.py`. The test was a pin from M9 T03 AC-2, asserting the root `README.md` contains a link to `design_docs/phases/milestone_9_skill/skill_install.md`.

**Why it was necessary:** T04 AC-5 requires *exactly one* `design_docs/` reference in the README, and that reference must be the roadmap pointer with the builder-only marker. The M9 pin is incompatible — keeping both the roadmap pointer AND the skill_install link would violate AC-5; keeping only the skill_install link would violate AC-5 (different target); keeping only the roadmap pointer (the T04 design) violates the M9 pin. The M9 pin predates the T05 branch-split plan, so T04's AC-5 supersedes M9's AC-2 for the main-branch README.

**Why this is a legitimate supersession and not a silent scope expansion:** the skill install surface does not disappear — it moves to T06 (uvx one-shot skill install) on a different entry path under the `design` branch pruning plan. M9's walk-through still exists unchanged at `design_docs/phases/milestone_9_skill/skill_install.md`; only the *main-branch README link to it* is removed.

**Mitigation:** the deleted test function's rationale is recorded verbatim in the module docstring of `tests/skill/test_doc_links.py` (amended in place, not replaced by a `_v2`). Same lockstep-sibling-test pattern that T03 used when renaming `docs/writing-a-component.md → docs/writing-a-graph-primitive.md` required a one-line edit to `tests/test_scaffolding.py`'s parametrised scaffolding set.

**Audit verdict:** justified and well-documented. The deletion is the smallest change that restores internal consistency between M9 T03 AC-2 and M13 T04 AC-5 in the post-branch-split world. No silent scope growth.

---

## Additions beyond spec — audited and justified

### ABS-1. README keeps a separate `## Getting started` section in addition to the renamed `## Contributing / from source`

**What was added:** README ships with both a `## Getting started` block (line 61, a three-command demo: `export GEMINI_API_KEY`, `aiw run planner`, `aiw resume`, `aiw list-runs`) and a `## Contributing / from source` block (line 84, the `uv sync` + `uv run aiw version` contributor path). The T04 spec's target structure §6 describes "Getting started — kept as a short block under Install" and §8 describes "Contributing / from source — renamed from 'Getting started'". The literal reading "rename Getting started to Contributing / from source" collides with "keep a Getting started block under Install", so the shipped README took the natural interpretation: the Install / Getting started demo flow (the user-facing onboarding) stays, the old uv-sync-from-clone section (the contributor onboarding) gets the new "Contributing / from source" name.

**Why this is a correct reading:** the spec target structure calls out both sections explicitly (§6 + §8), with different purposes (post-install demo vs from-source workflow). A strict "delete Getting started entirely and rename the uv-sync section" reading would leave a PyPI user with no post-install demo path, which contradicts the spec's own §6 description. The shipped README keeps both — `## Getting started` for post-install demo, `## Contributing / from source` for from-source contributors.

**Audit verdict:** justified. Both sections are load-bearing for the two documented install paths (`uvx` / `uv tool install` need a Getting started; `uv sync` from clone needs a Contributing section). The AC-2 heading pin (`## Install`, `## Contributing / from source`, `## Development`) is respected; the additional `## Getting started` is neither pinned nor forbidden.

### ABS-2. Three-marker coverage in README beyond the single AC-5-required marker

**What was added:** README contains three `(builder-only, on design branch)` markers (lines 82, 95, 109), not just the one AC-5 requires on the `design_docs/roadmap.md` link.

**Why this is a correct addition:** the two extra markers cover (a) the skill-install walkthrough pointer in `## MCP server` (line 82 — T06 will move this to the uvx form), and (b) the `design` branch pointer in `## Contributing / from source` (line 95 — T05 will replace with the GitHub URL). Both are explicitly called out in the spec's target structure §7 and §8 as placeholders awaiting T05 / T06. The markers make it unambiguous to a PyPI user which links are main-branch-live vs design-branch-only.

**Audit verdict:** justified. Matches the spec's §7 + §8 placeholder guidance. Zero shape-test risk because the `test_readme_has_exactly_one_design_docs_link` test only counts `design_docs/` substrings, not `(builder-only, on design branch)` markers.

### ABS-3. `tests/skill/test_doc_links.py` module docstring amendment

**What was added:** the module docstring now carries an "M13 T04 note" block explaining why `test_root_readme_links_skill_install` was deleted (M9 T03 AC-2 supersession by T04 AC-5). The original docstring only covered the M9 T03 scope.

**Why this is a correct addition:** silent deletion of a test function with no docstring trail would make the lockstep edit archaeologically opaque. The amendment records the supersession reasoning inline so a future auditor or `git blame` reader has a one-file trail.

**Audit verdict:** justified. Zero test behaviour change; pure prose addition documenting the lockstep-edit rationale.

### ABS-4. `_read_readme_lines()` helper in the shape test

**What was added:** the shape test defines a `_read_readme_lines()` helper that reads `README.md` and returns `.splitlines()`. Spec deliverable §2 describes three test functions without prescribing a helper.

**Why this is a correct addition:** all three tests read the README and split by newline. Without the helper, the pattern repeats 3×, which is noise. The helper is a 2-line private function and makes the three test bodies one-liners for the "read" step.

**Audit verdict:** justified. Standard DRY refactor for shared fixture-like access; zero new public surface.

---

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 620 passed, 5 skipped, 2 warnings in 20.75s |
| `uv run pytest tests/docs/test_readme_shape.py -v` | ✅ 3 passed (all three T04 shape tests green) |
| `uv run lint-imports` | ✅ 4 contracts kept, 0 broken |
| `uv run ruff check` | ✅ All checks passed |
| `wc -l README.md` | ✅ 109 lines (target ≤ 150; 41 lines under cap) |
| `grep -c 'design_docs/' README.md` | ✅ 1 (matches AC-5) |
| `grep -c 'CLAUDE\.md\\|\\.claude/commands\\|nice_to_have\\.md' README.md` | ✅ 0 (matches AC-6) |

---

## Files touched (T04 ownership)

- `README.md` — rewrite 235 → 109 lines.
- `tests/docs/test_readme_shape.py` — new, 3 tests, 107 lines.
- `tests/skill/test_doc_links.py` — one test function deleted (lockstep) + module docstring amended in place.
- `CHANGELOG.md` — T04 `[Unreleased]` block added above T03.
- `design_docs/phases/milestone_13_v0_release/task_04_readme_trim.md` — new (drafted at T04 kickoff).
- `design_docs/phases/milestone_13_v0_release/issues/task_04_issue.md` — new (this file).

## Files NOT touched by T04

- `ai_workflows/` — zero diff (AC-12).
- `docs/` — zero T04-owned diff (AC-13); the uncommitted `docs/*` changes in `git status` are T03's output.
- `pyproject.toml` — T01 owns the metadata; T04 adds no dep.
- `design_docs/phases/milestone_9_skill/skill_install.md` — T06 owns the uvx option.
- `scripts/release_smoke.sh` — T02 owns the release smoke.

---

## Issue log — cross-task follow-up

No OPEN issues from T04. Anticipated forward-deferrals remain unchanged from the spec's §Propagation status (both are future-task-owned, not T04 deferrals):

- **T05-owned.** Replace the `design` branch placeholder phrase in README.md line 95 with the actual GitHub branch URL once the `design` branch is created.
- **T06-owned.** Cross-check the MCP server registration command in README.md line 79 against the final `skill_install.md` uvx option wording and align if the form differs.

Neither is a T04 deferral — both are spec-acknowledged future work on surfaces T04 intentionally leaves as placeholders. They land as carry-over on T05 / T06 at their drafting time (not now — their specs don't exist yet).

---

## Deferred to nice_to_have

None. No T04 finding maps to an item in `design_docs/nice_to_have.md`.

---

## Propagation status

No forward-deferred items from this audit. The two anticipated placeholders in README (design-branch URL, MCP server command form) are spec-acknowledged future work and will be picked up by the T05 and T06 Builders from their own specs when those are drafted; no carry-over section on a future task is needed from this audit.

---

## Cycle status

**Cycle 1/10 — CLEAN.** All 13 ACs PASS individually. Zero design drift. Zero HIGH / MEDIUM / LOW issues. Four additions-beyond-spec and one spec deviation (the skill-test lockstep delete) audited and justified. Gates green. T04 ready for handoff to T05 (branch split — requires human action: create `design` branch from `main` tip before pruning builder artefacts on `main`).
