# Milestone 13 — v0.1.0 release + PyPI packaging

**Status:** 📝 Planned (drafted 2026-04-21).
**Grounding:** [roadmap.md](../../roadmap.md) · [architecture.md §6](../../architecture.md) · [pyproject.toml](../../../pyproject.toml) · [M11 README](../milestone_11_gate_review/README.md) (precondition) · [M14 README](../milestone_14_mcp_http/README.md) (precondition).

## Why this milestone exists

M1–M9 landed the runtime surface — four-layer package, LangGraph-native graph primitives, two production workflows, MCP + CLI surfaces, eval harness, Ollama hardening, Claude Code skill packaging. The project has never been exercised as a **distributable package** — every use to date has been from a cloned repo with `uv run aiw …`. A first-time external user (or a second machine of the same user) has no install path short of `git clone`.

The mechanics to flip this are small but real:

1. **`pyproject.toml` is minimal.** No `authors`, no `urls`, no `classifiers`, no `keywords`. PyPI accepts the upload but the listing is unusable for discovery + no repo link for bug reports.
2. **Wheel does not bundle `migrations/`.** [`pyproject.toml:42-43`](../../../pyproject.toml#L42-L43) declares `packages = ["ai_workflows"]` only. First-run `yoyo-migrations` from a `site-packages` install will fail with a missing-migrations-path error. **This is a shipping bug**, not a nice-to-have — the primary install path (`uvx --from ai-workflows aiw run planner …`) cannot complete its first run. Mirrors a known hatchling default (source-layout packages don't sweep sibling dirs); the fix is one `tool.hatch.build.targets.wheel` line.
3. **No external install documentation.** Root `README.md § Getting started` assumes `uv sync` from a clone. There is no "pip install ai-workflows" / "uvx" / "uv tool install" guidance.
4. **No PyPI release flow.** No `uv publish` rehearsal, no dist-smoke, no release notes section in `CHANGELOG.md` (the Keep-a-Changelog template is in place — the `[0.1.0]` section is not).
5. **Claude Code skill install path is git-clone-only.** [`skill_install.md §3`](../milestone_9_skill/skill_install.md) documents Option A (in-repo), Option B (user-level symlink), Option C (plugin — not applicable). A `uvx`-equivalent option for the MCP server + a plain `uv tool install ai-workflows` path for the skill's `aiw-mcp` dependency would make the skill usable on a machine that has never seen this repo.
6. **Repo layout is builder-facing, not user-facing.** `design_docs/` is ~50 markdown files of builder/auditor internals (architecture of record, milestones, audit issue files, nice_to_have.md). An external consumer landing on the GitHub repo sees the builder workflow before they see a getting-started doc — the signal-to-noise ratio on `main` is wrong for a v0 release. The three pre-pivot placeholder files under [`docs/`](../../../docs/) ([architecture.md](../../../docs/architecture.md), [writing-a-component.md](../../../docs/writing-a-component.md), [writing-a-workflow.md](../../../docs/writing-a-workflow.md)) still say *"Placeholder. This document is to be authored by M1 Task 11"* and reference the abandoned **components** vocabulary (pre-LangGraph pivot) — they are wrong on both freshness and terminology.
7. **Root `README.md` is builder-facing.** The "What runs today (post-M9)" section is a ~15-bullet dense narrative of every module M1–M9 touched. Useful during construction; noise at release time. A first-time user wants: what it is, how to install, how to run the first workflow, where to go next.

M13 closes all seven gaps and ships `0.1.0` to PyPI. **No new feature, no new KDR.** Composes over KDR-002 (surface portability) and KDR-008 (MCP schema public contract) unchanged.

## Branch model — `main` (release) + `design` (builder)

The builder/auditor workflow this project was built with is valuable to preserve; it is also not what a first-time user should see. M13 formalises a **two-branch model** so both audiences get the right surface without losing history:

- **`design` branch** — the builder/auditor workflow continues here. Full `design_docs/`, full audit issue files, full CLAUDE.md conventions, full `nice_to_have.md`. This is where `/implement`, `/audit`, `/clean-implement` run. All post-0.1.0 milestone work happens on `design`; the existing main-branch history *is* the design-branch starting point.
- **`main` branch** — the release branch. User-facing only: `ai_workflows/`, `tests/`, `migrations/`, `docs/` (populated), `README.md` (trimmed), `CHANGELOG.md`, `LICENSE`, `pyproject.toml`, `.github/`, `.claude/skills/`. No `design_docs/`. No `CLAUDE.md` builder-mode doc. PyPI publishes from `main`.
- **Merge direction** — design → main, never the other way. User-facing doc edits on `design` propagate to `main` via a release-time cherry-pick or a targeted merge at milestone close-out; builder-only changes (new audit issue files, nice_to_have entries, design_docs edits) stay on `design` only.

The user creates the `design` branch from the current `main` tip **before** T05 deletes `design_docs/` from `main` HEAD. T05 is the branch-split task. T01–T04 happen on `design` and only touch files that will exist on both branches.

## Goal

Publish **`ai-workflows==0.1.0`** to PyPI such that:

```bash
uvx --from ai-workflows aiw run planner --goal 'x' --run-id demo
```

works from a clean machine that has `uv`, `GEMINI_API_KEY`, and the `claude` CLI on PATH — and the Claude Code skill install path covers the `uvx aiw-mcp` mode end-to-end. The `main` branch that a first-time user lands on is trimmed to user-facing content only; the builder/auditor workflow is preserved intact on a `design` branch.

## Exit criteria

1. **`pyproject.toml` polished.** `authors`, `urls.Homepage` + `urls.Repository` + `urls.Issues`, a minimal `classifiers` list (Python 3.12, OS-independent, Development Status :: 3 — Alpha, License :: OSI Approved :: MIT), and `keywords` (langgraph, mcp, ai-workflow, claude-code). No dependency change at M13. Version stays `0.1.0`.
2. **Wheel contents correct.** `uv build` produces a wheel whose contents include both `ai_workflows/` and `migrations/`, and **explicitly exclude** `design_docs/` + `CLAUDE.md` + `.claude/commands/` (builder-mode artefacts, even if they briefly coexist during the branch-split window). `tool.hatch.build.targets.wheel` extended to sweep `migrations/` via `force-include`. Hermetic test: `tests/test_wheel_contents.py` builds the wheel in a `tmp_path`, unzips, asserts `migrations/001_initial.sql` + `migrations/002_reconciliation.sql` are present **and** `design_docs/` / `CLAUDE.md` are absent. Runs in the default hermetic suite — no network.
3. **Clean-venv install smoke.** A new gate-script `scripts/release_smoke.sh` creates a fresh venv outside the repo, installs the built wheel, runs `aiw --help` + `aiw-mcp --help`, runs `aiw run planner --goal 'wheel-smoke' --run-id wheel-smoke --no-wait` against a stubbed provider (or against real Gemini Flash if `GEMINI_API_KEY` + `AIW_E2E=1` are set), and asserts the run row lands in Storage with migrations applied. Script is **not** added to CI at M13 (live providers); it is the manual release-gate script invoked from T06 before `uv publish`. Documented in `design_docs/phases/milestone_13_v0_release/release_runbook.md` (builder-only — does not ship to `main`).
4. **PyPI name claimed.** A `ai-workflows` PyPI name check is performed; if taken, namespace the package (candidates: `aiw-framework`, `ai-workflows-langgraph`, or `<user>-ai-workflows`). Final name decision recorded in T02's spec + `pyproject.toml` `[project].name` + every doc that quotes the name. Changing the package name does *not* change the CLI script names (`aiw`, `aiw-mcp`) — those stay stable.
5. **`docs/` populated.** The three [`docs/`](../../../docs/) placeholder files are rewritten against the actual post-pivot architecture:
   - `docs/architecture.md` — user-facing architecture overview: four-layer model (primitives → graph → workflows → surfaces), LangGraph `StateGraph` as the substrate, MCP as the public surface, KDR summary. Links to `design_docs/architecture.md` *are removed* (the file does not ship on `main`); any grounding reference points to the `design` branch path with a `(builder-only)` note.
   - `docs/writing-a-workflow.md` — tutorial for authoring a new `StateGraph` under `ai_workflows/workflows/` that composes the M2 graph primitives (`TieredNode`, `ValidatorNode`, `HumanGate`), registers via `ai_workflows.workflows.register`, and surfaces through both CLI (`aiw run <name>`) and MCP (`run_workflow`).
   - `docs/writing-a-component.md` — **renamed** to `docs/writing-a-graph-primitive.md` (the "component" term is a pre-pivot artefact; graph primitives is the current vocabulary). Tutorial for authoring a new adapter under `ai_workflows/graph/` over an existing primitive, matching the `TieredNode` / `ValidatorNode` composition pattern.
   Each doc compiles + lints clean, and a new `tests/docs/test_docs_links.py` hermetic test pins that every relative link in `docs/` resolves.
6. **Root `README.md` trimmed.** The "What runs today (post-M9)" section (currently a ~15-bullet dense narrative) is replaced by a three-paragraph overview: (1) what this project is in two sentences, (2) one-paragraph architecture summary pointing at `docs/architecture.md`, (3) one-paragraph install + first-run pointer. The milestone status table stays. The "Next" section is compressed to a single pointer at `design_docs/roadmap.md` on the `design` branch (with a `(builder-only)` note) — no per-milestone narrative on `main`. Post-trim README target: **≤ 150 lines** (currently ~156 without the M13 additions). A new `tests/docs/test_readme_shape.py` hermetic test pins: line count under the cap, presence of *Install* / *Getting started* / *Development* sections, absence of any `design_docs/` link (the `design` branch pointer is the exception, tested explicitly).
7. **Install section added.** `README.md` grows an **Install** section above *Getting started* documenting two paths: (a) **one-shot via `uvx`** (`uvx --from ai-workflows aiw run planner --goal '…' --run-id demo`); (b) **persistent tool install** (`uv tool install ai-workflows`). The *Getting started* section that currently assumes `uv sync` from a clone is preserved below, relabeled **Contributing / from source**, and points at the `design` branch for the full builder workflow.
8. **Skill install doc extended.** [`skill_install.md §2 Install the MCP server`](../milestone_9_skill/skill_install.md) gains an "Option A-bis — via uvx (no clone required)" sub-section: `claude mcp add ai-workflows --scope user -- uvx --from ai-workflows aiw-mcp`. Option A (clone-based) stays primary for contributors; the new option is the user path. `tests/skill/test_doc_links.py` stays green.
9. **Branch split executed.** The `design` branch is created from the `main` tip at M13 kickoff. On `main`, the following are **deleted** (exist only on `design`): `design_docs/`, `CLAUDE.md`, `.claude/commands/`, `scripts/spikes/`, and the builder-mode `release_runbook.md` under `design_docs/phases/milestone_13_v0_release/`. On `main`, these **stay**: `ai_workflows/`, `tests/`, `migrations/`, `evals/`, `docs/`, `README.md`, `CHANGELOG.md`, `LICENSE`, `pyproject.toml`, `uv.lock`, `.github/`, `.gitignore`, `.claude/skills/` (the M9 skill — this *is* user-facing). A new `.github/CONTRIBUTING.md` on `main` explains the two-branch model in one paragraph + links to the `design` branch README. A `tests/test_main_branch_shape.py` hermetic test (runs on both branches) pins the "no design_docs on main" invariant via a `Path` check that **skips** on the `design` branch (env-flag gated: `AIW_BRANCH=design` makes the test assert the inverse).
10. **CHANGELOG `[0.1.0]` release section.** `CHANGELOG.md` gets a `## [0.1.0] — 2026-MM-DD` header above the Keep-a-Changelog template, listing the M1–M9 surfaces as one bulleted inventory under `### Added` (not per-milestone — the release-notes audience does not map to milestones). `## [Unreleased]` stays in place above it for post-0.1.0 work. On `main`, the per-milestone `[M1..M9]` detail blocks the `design` branch carries under `## [Unreleased]` history are *pruned* — the `[0.1.0]` block is the user-facing summary.
11. **First PyPI publish.** `uv publish --token $PYPI_TOKEN` (from a one-shot token, not long-lived credentials) succeeds against pypi.org from the **`main` branch** for the `0.1.0` wheel. A second smoke — `uvx --from ai-workflows==0.1.0 aiw version` against the real PyPI-hosted package — verifies the published artefact resolves. Observation + commit sha baseline recorded in the T07 CHANGELOG close-out block (on both branches).
12. **Gates green on both branches.** `uv run pytest` + `uv run lint-imports` (4 contracts kept — M12's new contract lands at M12 T02, not here) + `uv run ruff check` all clean on both `design` and `main` at T08 close-out. The `design` branch retains its full test surface; `main` retains the same code tests (four-layer package is identical) — only non-code artefacts differ between branches.
13. **M11 + M14 landed before T06.** Two preconditions before the first PyPI upload: (a) the first-time-user gate-review UX (M11 ISS-02 closure) must be in place so the published skill does not hand operators a `plan: null` gate pause; (b) the MCP HTTP transport ([M14](../milestone_14_mcp_http/README.md)) must ship so the first wheel covers browser-origin consumers without requiring a git clone. If either is still open when M13 reaches T06 (release smoke), the milestone **stops and waits**. See §*Dependencies* for rationale.

## Non-goals

- **No new feature.** M13 is packaging-only. The runtime surface is exactly M1–M9 (plus M11's gate-review projection as a precondition).
- **No version bump beyond 0.1.0.** 0.1.x patch-level releases belong to later tasks; 0.2.0 is where M10/M12 consolidate.
- **No CI-gated publish workflow.** Auto-publish-on-tag is a [nice_to_have.md §17+ candidate](../../nice_to_have.md); at M13 the publish is a manual human-in-the-loop step with a one-shot token.
- **No Docker image, no Homebrew tap, no `pipx` doc.** `uvx` + `uv tool install` are the supported install paths at M13. Other channels are post-v0.1.0 forward options.
- **No M10 dependency.** M8's Ollama path is functional; M10 closes design-rationale gaps that do not block first-install usability.
- **No M12 dependency.** The audit cascade is a post-v0.1.0 quality layer; `0.1.0` ships with shape-only validation (KDR-004) which is the contract M1–M9 was built to.
- **No Anthropic API.** KDR-003 preserved across M13.

## Key decisions in effect

| Decision | Reference |
| --- | --- |
| OAuth CLI subprocess is the only Claude transport | KDR-003 |
| MCP tool schemas are the public contract — 0.1.0 freezes the shape | KDR-008 |
| Packaging is portable; skill is packaging-only over the MCP surface | KDR-002 |
| Four-layer import contract holds through the published wheel | architecture.md §3 + import-linter |
| Release notes audience ≠ milestone audience — `CHANGELOG.md` grows a `[0.1.0]` consolidated block above the per-milestone history | project convention (this milestone) |
| Two-branch model — `main` is user-facing, `design` preserves builder workflow; merge direction is `design → main` only | project convention (this milestone) |

## Task order

| # | Task | Kind |
| --- | --- | --- |
| 01 | [pyproject polish + wheel contents fix](task_01_pyproject_polish.md) | code + test |
| 02 | PyPI name claim + clean-venv install smoke + wheel-excludes test | code + test + doc |
| 03 | Populate `docs/` — architecture.md + writing-a-workflow.md + writing-a-graph-primitive.md | doc + test |
| 04 | Trim root `README.md` — collapse "What runs today", add Install section, line-cap + shape tests | doc + test |
| 05 | Branch split — create `design` branch, delete builder artefacts from `main`, add `.github/CONTRIBUTING.md`, branch-shape invariant test | git + doc + test |
| 06 | `skill_install.md` uvx option + release-smoke script | doc + release |
| 07 | CHANGELOG `[0.1.0]` section + first PyPI publish (manual) | doc + release |
| 08 | Milestone close-out | doc |

Per-task spec files land as each predecessor closes (same convention as M10 / M11 / M12). T01 is spec'd below; T02–T08 are written at each predecessor's close-out. The README alone is enough context to start T01.

**Branch at which each task runs.** T01 / T02 / T03 / T04 happen on `design` (the builder branch) — they touch files that exist on both branches and will propagate to `main` at T05's split. T05 is the split itself: it operates on both branches (creates `design`, prunes `main`). T06 / T07 / T08 run on `design` and cherry-pick / merge the user-facing deltas into `main` at each step. Audit issue files always land on `design` under `design_docs/phases/milestone_13_v0_release/issues/`, never on `main`.

## Dependencies

- **M11 (hard).** A first-time PyPI install that walks the skill's gate-pause flow lands on `plan: null` and a non-reviewable gate — the defect ISS-02 named. Shipping `0.1.0` before M11 would publish a broken first-impression UX for the primary documented install path. **If M11 has not landed by T06 kickoff, M13 T06 stops and waits.** T01–T05 can run in parallel with M11 because they touch no `ai_workflows.mcp/` surface.
- **M14 (hard).** The [MCP HTTP transport](../milestone_14_mcp_http/README.md) is a precondition for the v0.1.0 release so the first wheel covers both stdio (Claude Code / Cursor / Zed) and streamable-HTTP (Astro / browser-origin) consumers. Shipping `0.1.0` with stdio-only would force browser-origin integrators to `pip install` from a git tag or wait for a 0.1.x patch — a worse first-impression than delaying the release by one milestone. **If M14 has not landed by T06 kickoff, M13 T06 stops and waits.** T01–T05 can run in parallel with M14 because they touch no `ai_workflows.mcp/` surface either.
- **M10 — none.** Ollama hardening is independent; degraded M8 behaviour is functional and falls back correctly. A post-0.1.0 0.2.x release absorbs M10.
- **M12 — none.** Audit cascade is a quality layer above the 0.1.0 contract.

## Carry-over from prior milestones

- *None at M13 kickoff.* [M9 T04 ISS-02](../milestone_9_skill/issues/task_04_issue.md) is owned by M11 T01, not M13.

## Propagation status

Filled in at audit time. Anticipated forward-deferrals:

- A CI-gated publish-on-tag job — `nice_to_have.md` candidate with trigger "a second maintainer joins" OR "an out-of-band token is mishandled during manual publish". Not ready to promote at M13.
- A `pipx`-equivalent install-doc section — add to `nice_to_have.md` only if a user reports that `uvx` / `uv tool install` is insufficient. Solo-dev default is to skip.
- A Docker image — post-v0.1.0 forward option only; trigger is an integration target that needs a frozen runtime (CI runner, reproducible workshop, etc.).

## Issues

Land under [issues/](issues/) after each task's first audit.
