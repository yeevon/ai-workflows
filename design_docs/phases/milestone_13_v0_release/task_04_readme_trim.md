# Task 04 — Trim root `README.md` + add Install section + shape tests

**Status:** 📝 Planned (drafted 2026-04-22 after T03 audit closed clean).
**Grounding:** [milestone README §Exit criteria 6 + 7](README.md#L53-L54) · [task_03 close](task_03_populate_docs.md) · [docs/architecture.md](../../../docs/architecture.md) (T03 shipped — this task's primary outbound link) · [CLAUDE.md](../../../CLAUDE.md).

## What to Build

A rewrite of the repo-root `README.md` plus a new hermetic shape test. Three deliverables, all closing two M13 exit criteria (§6 README trim + §7 Install section) without touching any `ai_workflows/` runtime code.

1. **Trim [`README.md`](../../../README.md)** from 235 lines (current) to ≤ 150 lines. Replace the ~117-line "What runs today (post-M14)" + M11 / M14 narrative blocks with a three-paragraph overview. Milestone status table stays. "Next" section collapses to a single pointer at `design_docs/roadmap.md` with a `(builder-only, on design branch)` marker. **Post-trim README contains zero `design_docs/…` links except one** — the roadmap pointer in the Next section. Every reference to `design_docs/architecture.md`, `design_docs/adr/…`, `design_docs/phases/…`, `design_docs/analysis/…` is replaced by a link into the shipped `docs/` tree (populated at T03) or elided entirely. `CLAUDE.md` links are removed (builder-only; survives on design branch).
2. **Add an Install section to the README** above Getting started. Documents two paths:
    - **One-shot via `uvx`** — `uvx --from ai-workflows aiw run planner --goal '…' --run-id demo`.
    - **Persistent tool install** — `uv tool install ai-workflows` → `aiw run planner …`.
   The existing *Getting started* section (`uv sync` from clone) is **renamed to "Contributing / from source"** and preserved below the new Install section. A one-sentence pointer at the bottom of that section reads "For the full builder/auditor workflow, see the [`design` branch](<design-branch-link-to-be-added-by-T05>) (builder-only, on design branch)." — T05 adds the explicit branch URL; T04 leaves a placeholder since the `design` branch does not exist yet.
3. **Add [`tests/docs/test_readme_shape.py`](../../../tests/docs/test_readme_shape.py)** — hermetic shape guard. Three assertions: (a) README is ≤ 150 lines; (b) README contains the three user-facing section headings (`## Install`, `## Contributing / from source`, `## Development`); (c) README contains **exactly one** `design_docs/…` link (the roadmap pointer in Next) — every other line that contains a `design_docs/` substring is a shape violation and is flagged.

## Deliverables

### 1. [`README.md`](../../../README.md) — user-facing rewrite

**Target structure (top-to-bottom):**

1. **Title + one-paragraph hook (2 sentences).** What the project is, who it is for. No milestone list, no "post-M14" narrative, no KDR references at the top.
2. **Milestone status table** — kept as-is from the current README (9 completed + 4 planned milestones — M10/M12/M13/M14 states). This is the one builder-visibility concession the public README keeps; it answers "is this project actively maintained?" without a clone. The table itself references no `design_docs/` paths; the "see roadmap" pointer lives in §Next below.
3. **What it is** — one paragraph. LangGraph-native workflow framework, two public surfaces (`aiw` CLI + `aiw-mcp` MCP server), runs on a laptop with `uv` + provider keys. No Anthropic API (brief KDR-003 note; no linked citation — users are not expected to look up KDRs).
4. **Architecture at a glance** — one paragraph + the existing ASCII `surfaces → workflows → graph → primitives` box. Link to [`docs/architecture.md`](../../../docs/architecture.md) for the full overview (T03 deliverable). **No link into `design_docs/`.**
5. **Install** — new section, per §Deliverables 2. Two code blocks (`uvx` one-shot + `uv tool install`). Short — 10-15 lines.
6. **Getting started** — kept as a short block under Install. Shows `aiw run planner … --goal '…' --run-id demo` + `aiw resume demo --approve` + `aiw list-runs`. The three-command flow that currently lives in the README. Provider-env reminder (`GEMINI_API_KEY`) stays.
7. **MCP server** — kept as a short block. Registration example (`claude mcp add ai-workflows --scope user -- uvx --from ai-workflows aiw-mcp` — the uvx form, T06 finalises the wording). Points at [skill_install.md](<to-be-populated-post-T06>) **which is builder-only**; T04 uses a placeholder text "(builder-only, on design branch)" since the user-facing install path for the skill lands at T06.
8. **Contributing / from source** — **renamed from "Getting started"** in the current README. Documents the `uv sync` + `uv run aiw …` path for contributors who clone. One-sentence pointer at the bottom: "For the full builder/auditor workflow, see the `design` branch (builder-only, on design branch)."
9. **Development** — three-command gate block (`uv run pytest` / `uv run lint-imports` / `uv run ruff check`). Trim the post-M14 snapshot prose; the test count drifts per task and is not load-bearing user info. Keep the gate list; drop the narrative.
10. **Next** — **single pointer line**: "Roadmap + per-milestone task files live at [`design_docs/roadmap.md`](design_docs/roadmap.md) (builder-only, on design branch)." Three-milestone M10/M12/M13 narrative from the current README (lines 233-235) is **deleted** entirely.

**Content to delete outright (current line ranges as of 2026-04-22):**

- Lines 5-7: explicit `design_docs/…` links (architecture, roadmap, analysis). Architecture link moves to §Architecture (pointing at `docs/architecture.md` instead); roadmap stays only in §Next with the builder-only marker; analysis link is dropped entirely (deep grounding, not user-facing).
- Lines 28-120: the three dense paragraphs covering M1-M9, M11, M14 milestone narratives. Replace with the 1-paragraph "What it is" + 1-paragraph "Architecture" rewrites.
- Lines 122-140: "What runs today (post-M14)" bullet list. The individual capability bullets live better in `docs/architecture.md` (already shipped at T03) + `docs/writing-a-workflow.md` (already shipped). Delete from README.
- Lines 156-163: "Key design decisions" bullet list. Users read the KDR summary in `docs/architecture.md §Key design decisions` (shipped at T03). Delete from README.
- Lines 165-183: "Project layout" code block + `CLAUDE.md` pointer. Users read `docs/architecture.md §Four-layer model` for the layered layout; the repo-layout tree is builder-visibility only. Delete from README.
- Lines 219-227: "Workflow conventions" block with `.claude/commands/…` links. Builder-only. Delete from README.
- Lines 229-235: the three-milestone "Next" prose. Replace with the single roadmap pointer.

**Post-trim target line count: ≤ 150.** Hermetic shape test enforces. Current 235 → target ≤ 150 means removing ~85 lines net — achievable by the deletion list above (~150 lines deleted, ~65 lines of replacement narrative added).

### 2. [`tests/docs/test_readme_shape.py`](../../../tests/docs/test_readme_shape.py) — hermetic shape guard

New test file under the existing `tests/docs/` directory (created at T03). Module docstring cites M13 T04 and the §6 + §7 exit criteria it closes.

**Contract.**

Three test functions:

- `test_readme_line_count_under_cap` — reads `README.md`, counts lines, asserts `len(lines) <= 150`. Failure message includes the actual line count so the operator knows how far over.
- `test_readme_has_user_facing_sections` — reads `README.md`, asserts the literal strings `"## Install"`, `"## Contributing / from source"`, and `"## Development"` each appear on exactly one line. Pinned to the literal heading form to block silent rename drift.
- `test_readme_has_exactly_one_design_docs_link` — reads `README.md` line-by-line, counts lines that contain the substring `design_docs/`. Asserts exactly one such line (the roadmap pointer in §Next). Every other match is flagged with file path + line number + line content. Rationale: post-T05 branch split, any `design_docs/…` reference on `main` is a broken link — enforcement here blocks silent drift during the branch-split window.

**Builder-only-marker tolerance.** The one allowed `design_docs/roadmap.md` link **must** carry the `(builder-only, on design branch)` marker on the same line. The test checks both — count exactly 1 AND the surviving link is marked. Inherits the marker discipline from T03's `tests/docs/test_docs_links.py`.

**Not composed over `tests/docs/test_docs_links.py`.** That test scans `docs/*.md`; this one scans the repo-root `README.md`. Two different roots, two different scopes. Keep separate.

### 3. [`CHANGELOG.md`](../../../CHANGELOG.md)

Under `## [Unreleased]`, append a new `### Changed — M13 Task 04: trim root README + add Install section + shape test (YYYY-MM-DD)` block **above** the T03 entry.

Covers:

- README trimmed from 235 → ≤ 150 lines (actual post-trim count listed).
- Install section added with the two documented install paths.
- Getting started → Contributing / from source rename.
- Next section collapsed to single roadmap pointer with builder-only marker.
- Three new hermetic tests under `tests/docs/test_readme_shape.py`.
- Files touched list.
- **Not touched:** `ai_workflows/` (AC-10); `pyproject.toml` (no new dep); the `design` branch (T05's scope); `skill_install.md` (T06's scope).

## Acceptance Criteria

- [ ] AC-1: `README.md` is ≤ 150 lines (verified via `wc -l` + enforced by `test_readme_line_count_under_cap`).
- [ ] AC-2: `README.md` contains the exact headings `## Install`, `## Contributing / from source`, `## Development` — each on exactly one line.
- [ ] AC-3: `README.md` contains the **Install** section with both `uvx --from ai-workflows aiw run planner …` (one-shot) and `uv tool install ai-workflows` (persistent) as documented paths in prose + code blocks.
- [ ] AC-4: The pre-T04 "Getting started" section is **renamed** to "Contributing / from source"; its body preserves the `uv sync` + `uv run aiw …` flow for contributors; it ends with a one-sentence `design` branch pointer carrying the `(builder-only, on design branch)` marker.
- [ ] AC-5: `README.md` contains **exactly one** line with the substring `design_docs/` — the roadmap pointer in `## Next`. That line carries the `(builder-only, on design branch)` marker. Enforced by `test_readme_has_exactly_one_design_docs_link`.
- [ ] AC-6: `README.md` contains **zero** lines with the substrings `CLAUDE.md`, `.claude/commands/`, or `nice_to_have.md`. (Relaxed — not a test-enforced AC; inspected manually. The `design_docs/` count test is the primary invariant; the others are manual builder-only cleanups and a future drift in either direction is acceptable as long as the line count + section headings stay intact.)
- [ ] AC-7: `tests/docs/test_readme_shape.py` ships with three tests (`test_readme_line_count_under_cap`, `test_readme_has_user_facing_sections`, `test_readme_has_exactly_one_design_docs_link`). All three pass against the shipped README.
- [ ] AC-8: `uv run pytest` green. Test count: 618 (T03) + 3 new shape tests = **621**.
- [ ] AC-9: `uv run lint-imports` reports 4 contracts kept, 0 broken. T04 adds no layer contract.
- [ ] AC-10: `uv run ruff check` clean. T04 touches no runtime Python; new test file lints clean.
- [ ] AC-11: CHANGELOG `[Unreleased]` entry lists files + ACs + the section rename. T04 block lands above T03's.
- [ ] AC-12: Zero diff under `ai_workflows/`. T04 is documentation + test only.
- [ ] AC-13: Zero diff under `docs/`. T03 already shipped that tree; T04 does not touch it.

## Dependencies

- **T03 complete and clean** (✅ landed 2026-04-22, Cycle 1 of `/clean-implement`). T04's README links into `docs/architecture.md` which landed at T03. Without T03, the README trim would point at a pre-pivot placeholder.
- **No external dependency.** No new package, no new CI job.

## Out of scope (explicit)

- **No runtime code change.** `ai_workflows/` is not touched.
- **No `docs/` edit.** T03 shipped that tree.
- **No branch split.** T05 creates the `design` branch and prunes `main`; T04 leaves the `design` branch pointer as a placeholder sentence (the actual URL is T05's to fill in when the branch exists). T04 runs on `main` (where the current builder workflow lives — the branch split itself hasn't happened yet, so `main` is both the builder branch and the future release branch at T04 time).
- **No `skill_install.md` uvx extension.** T06's scope.
- **No PyPI publish.** T07's scope.
- **No `.github/CONTRIBUTING.md`.** T05's scope — it lands with the branch split.
- **No `pyproject.toml` edit.** T01 landed the metadata.
- **No `design_docs/architecture.md` edit.** That doc stays on the `design` branch as the architecture of record; T04 just removes the user-facing README's references to it.

## Propagation status

Filled in at audit time. Anticipated forward-deferrals:

- **T05 fills the `design` branch URL** in the Contributing section pointer sentence (T04 ships a placeholder phrase; T05 replaces with the actual GitHub URL once the branch exists).
- **T06 finalises the MCP server registration wording** in the MCP section (T04 ships `claude mcp add … uvx --from ai-workflows aiw-mcp` as the working example; T06 cross-checks against `skill_install.md` and aligns the exact form).

Neither is T04-owned; the carry-over goes on T05 / T06 specs at their drafting time (after T04 close-out).
