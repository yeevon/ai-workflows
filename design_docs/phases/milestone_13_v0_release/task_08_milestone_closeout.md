# Task 08 — Milestone Close-out

**Status:** ✅ Complete (2026-04-22).
**Grounding:** [milestone README](README.md) · [task_07_changelog_publish.md](task_07_changelog_publish.md) · [task_07 audit](issues/task_07_issue.md) · [release_runbook.md](release_runbook.md) · [CLAUDE.md](../../../CLAUDE.md) close-out conventions · [M9 T04](../milestone_9_skill/task_04_milestone_closeout.md) + [M11 T02](../milestone_11_gate_review/task_02_milestone_closeout.md) + [M14 T02](../milestone_14_mcp_http/task_02_milestone_closeout.md) (patterns to mirror).

## What to Build

Close M13. T01–T07 landed clean per their respective audit issue files; `jmdl-ai-workflows==0.1.0` is live on pypi.org and the post-publish live smoke round-tripped (see [T07 audit](issues/task_07_issue.md) for the full AC grid). No deep-analysis pass required — M13 is a packaging milestone with zero runtime-code diff in `ai_workflows/` across any of its seven tasks; the analysis surfaces (provider tiering, graph primitives, MCP schema) all belong to earlier milestones that own their own close-outs.

The close-out is standard milestone flip + CHANGELOG promote:

1. **Milestone README Status** → `✅ Complete` with Outcome section.
2. **Roadmap** → flip M13 row; no summary edit (the M13 summary in §M2–M13 summaries accurately describes what shipped, including the PyPI name rename recorded at T07).
3. **CHANGELOG** → promote the `[Unreleased]` M13 entries on `design_branch` into a new dated `## [M13 v0.1.0 release] - 2026-04-22` section; add a T08 close-out entry at the top. Keep the `main`-side CHANGELOG untouched — the `[0.1.0]` block already carries the user-facing release narrative; M13's builder-mode audit trail does not belong on `main`.
4. **Root README.md milestone table** → flip M13 row on **both branches** from `In progress` to `Complete (2026-04-22)`.

No ADR, no new test, no deep-analysis carry-over. If a follow-up surfaces during close-out, it becomes either (a) a new milestone with its own README + task_01, (b) a `nice_to_have.md` entry, or (c) forward-deferred carry-over onto an existing future milestone — never a drive-by fix.

Mirrors M9 T04 / M11 T02 / M14 T02 close-out muscle memory.

## Deliverables

### 1. Milestone README ([README.md](README.md))

- Flip **Status** from `📝 Planned (drafted 2026-04-21)` to `✅ Complete (2026-04-22)`.
- Append an **Outcome** section summarising:
  - T01–T07 summary (one-line each) with landing commits.
  - Release artefact: `jmdl-ai-workflows==0.1.0` on pypi.org, SHA256 `1087075fb90d3ae9e760366620f118e37eb4325264cc1c96133c1acc1def6fa8`, publish-side commit `main:56cedd5`.
  - PyPI name rename footnote — first upload of `ai-workflows` rejected with `400 The name 'ai-workflows' is too similar to an existing project`; renamed to `jmdl-ai-workflows` (author's initials prefix). Full decision trail in [task_07 §Rename addendum](task_07_changelog_publish.md#rename-addendum-2026-04-22).
  - Two-branch model in effect: `main:9fe1898`, `design_branch:6cd43e6` (pre-T08 tips).
  - Green-gate snapshot: `uv run pytest`, `uv run lint-imports` (**4 contracts kept** — no new layer contract at M13), `uv run ruff check`.
- Keep the **Carry-over from prior milestones** section intact (currently: *None*).
- Fill in **Propagation status** — name the release commits, record that no finding was forward-deferred and no `nice_to_have.md` entry was generated, confirm that M10 + M12 remain as the next load-bearing milestones post-M13.

### 2. Roadmap ([roadmap.md](../../roadmap.md))

- Flip M13 row `Status` from `planned (depends on M11 + M14 — both complete; unblocked)` to `✅ complete (2026-04-22)`.
- No other changes — the M13 summary in §M2–M13 summaries accurately describes what shipped.

### 3. CHANGELOG ([CHANGELOG.md](../../../CHANGELOG.md)) — `design_branch` only

- Promote the six existing `[Unreleased]` M13 entries (T01 → T07 pre-publish + T07 rename + T07 Published footer-stamp) into a new dated section `## [M13 v0.1.0 release] - 2026-04-22`.
- Keep the top-of-file `[Unreleased]` section intact (empty post-promote; ready for post-0.1.0 work).
- Add a T08 close-out entry at the top of the new dated section:
  - Reference M13 README Outcome section.
  - Record the green-gate snapshot (test count, lint-imports contracts, ruff status) on both branches.
  - Record the release-commits pair: `main:9fe1898`, `design_branch:6cd43e6`.
  - Note: zero CHANGELOG change on `main` at T08 — the `[0.1.0]` block there already carries the user-facing release narrative.

### 4. Root README.md (both branches)

- Flip the M13 row in the milestone status table from `M13 — v0.1.0 release + PyPI packaging | In progress` to `**M13 — v0.1.0 release + PyPI packaging** | Complete (2026-04-22)`.
- No other changes — the table is already current for M11 / M14 and the post-T04 trimmed README shape is unchanged at close-out.

## Acceptance Criteria

- [x] AC-1: Milestone README Status flipped to `✅ Complete (2026-04-22)`; Outcome section covers T01–T07 with the release artefact + rename footnote + green-gate snapshot; Propagation status section filled in.
- [x] AC-2: `roadmap.md` M13 row reflects the complete status with the close-out date.
- [x] AC-3: `CHANGELOG.md` on `design_branch` has a dated `[M13 v0.1.0 release] - 2026-04-22` section with all six `[Unreleased]` M13 entries promoted + a T08 close-out entry at the top; the top-of-file `[Unreleased]` section retained (empty).
- [x] AC-4: `CHANGELOG.md` on `main` is **unchanged** at T08 (the `[0.1.0]` block already carries the user-facing release narrative; M13's builder-mode audit trail does not belong on `main`).
- [x] AC-5: Root `README.md` milestone table row for M13 updated to `Complete (2026-04-22)` on **both** branches.
- [x] AC-6: `uv run pytest` green on both branches (main: 610 + 9 skipped; design_branch: 623 + 6 skipped — T07 baseline unchanged).
- [x] AC-7: `uv run lint-imports` reports 4 contracts kept, 0 broken on both branches (no new layer contract at M13).
- [x] AC-8: `uv run ruff check` clean on both branches.
- [x] AC-9: Zero runtime-code diff in `ai_workflows/` during T08 (all deliverables land under `design_docs/`, `CHANGELOG.md`, and the root `README.md` milestone table).
- [x] AC-10: T08 close-out commits:
  - `design_branch`: one commit covering milestone README Outcome + roadmap flip + CHANGELOG promote + root README table flip.
  - `main`: one commit (cherry-pick) covering the root README table flip.

## Dependencies

- T07 complete and audited clean (✅ landed 2026-04-22; `jmdl-ai-workflows==0.1.0` live on pypi.org).
- No deep-analysis pass required (packaging-only milestone; zero runtime-code surface at any M13 task).

## Out of scope (explicit)

- Any runtime code change in `ai_workflows/`. T08 is doc-only.
- Any new test. The `tests/test_main_branch_shape.py` + `tests/docs/` + `tests/test_wheel_contents.py` invariants that landed at T04 / T05 are the M13 test surface; T08 changes nothing.
- Any CHANGELOG edit on `main`. The `[0.1.0]` block there is frozen post-publish; T08 absorbs the builder-mode audit trail on `design_branch` only.
- Any propagation to a future milestone. If a finding surfaces during close-out, it forks to a new milestone / `nice_to_have.md` / carry-over per CLAUDE.md close-out conventions.

## Propagation status

- **No forward-deferral to future milestones.** M13 closes with zero open findings; T01–T07 audit issue files are all 🟡/✅ closed per their grading tables.
- **No `nice_to_have.md` entries generated.** M13's scope was packaging-only; no architectural observation surfaced during T08 that warranted a new deferral.
- **Next load-bearing milestones:** M10 (Ollama fault-tolerance hardening) and M12 (Tiered audit cascade) remain on the roadmap. Neither blocks a patch-level 0.1.x release; both target the 0.2.0 consolidation.
