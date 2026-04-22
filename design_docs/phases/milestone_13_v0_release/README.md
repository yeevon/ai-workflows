# Milestone 13 — v0.1.0 release + PyPI packaging

**Status:** 📝 Planned (drafted 2026-04-21).
**Grounding:** [roadmap.md](../../roadmap.md) · [architecture.md §6](../../architecture.md) · [pyproject.toml](../../../pyproject.toml) · [M11 README](../milestone_11_gate_review/README.md) (precondition).

## Why this milestone exists

M1–M9 landed the runtime surface — four-layer package, LangGraph-native graph primitives, two production workflows, MCP + CLI surfaces, eval harness, Ollama hardening, Claude Code skill packaging. The project has never been exercised as a **distributable package** — every use to date has been from a cloned repo with `uv run aiw …`. A first-time external user (or a second machine of the same user) has no install path short of `git clone`.

The mechanics to flip this are small but real:

1. **`pyproject.toml` is minimal.** No `authors`, no `urls`, no `classifiers`, no `keywords`. PyPI accepts the upload but the listing is unusable for discovery + no repo link for bug reports.
2. **Wheel does not bundle `migrations/`.** [`pyproject.toml:42-43`](../../../pyproject.toml#L42-L43) declares `packages = ["ai_workflows"]` only. First-run `yoyo-migrations` from a `site-packages` install will fail with a missing-migrations-path error. **This is a shipping bug**, not a nice-to-have — the primary install path (`uvx --from ai-workflows aiw run planner …`) cannot complete its first run. Mirrors a known hatchling default (source-layout packages don't sweep sibling dirs); the fix is one `tool.hatch.build.targets.wheel` line.
3. **No external install documentation.** Root `README.md § Getting started` assumes `uv sync` from a clone. There is no "pip install ai-workflows" / "uvx" / "uv tool install" guidance.
4. **No PyPI release flow.** No `uv publish` rehearsal, no dist-smoke, no release notes section in `CHANGELOG.md` (the Keep-a-Changelog template is in place — the `[0.1.0]` section is not).
5. **Claude Code skill install path is git-clone-only.** [`skill_install.md §3`](../milestone_9_skill/skill_install.md) documents Option A (in-repo), Option B (user-level symlink), Option C (plugin — not applicable). A `uvx`-equivalent option for the MCP server + a plain `uv tool install ai-workflows` path for the skill's `aiw-mcp` dependency would make the skill usable on a machine that has never seen this repo.

M13 is the smallest milestone that closes all five gaps and ships `0.1.0` to PyPI. **No new feature, no new KDR.** Composes over KDR-002 (surface portability) and KDR-008 (MCP schema public contract) unchanged.

## Goal

Publish **`ai-workflows==0.1.0`** to PyPI such that:

```bash
uvx --from ai-workflows aiw run planner --goal 'x' --run-id demo
```

works from a clean machine that has `uv`, `GEMINI_API_KEY`, and the `claude` CLI on PATH — and the Claude Code skill install path covers the `uvx aiw-mcp` mode end-to-end.

## Exit criteria

1. **`pyproject.toml` polished.** `authors`, `urls.Homepage` + `urls.Repository` + `urls.Issues`, a minimal `classifiers` list (Python 3.12, OS-independent, Development Status :: 3 — Alpha, License :: OSI Approved :: MIT), and `keywords` (langgraph, mcp, ai-workflow, claude-code). No dependency change at M13. Version stays `0.1.0`.
2. **Wheel contents correct.** `uv build` produces a wheel whose contents include both `ai_workflows/` and `migrations/`. `tool.hatch.build.targets.wheel` extended to sweep `migrations/` (either via a new `packages` entry or `force-include`). Hermetic test: `tests/test_wheel_contents.py` builds the wheel in a `tmp_path`, unzips, asserts `migrations/001_initial.sql` + `migrations/002_reconciliation.sql` are present in the archive. Runs in the default hermetic suite — no network.
3. **Clean-venv install smoke.** A new gate-script `scripts/release_smoke.sh` creates a fresh venv outside the repo, installs the built wheel, runs `aiw --help` + `aiw-mcp --help`, runs `aiw run planner --goal 'wheel-smoke' --run-id wheel-smoke --no-wait` against a stubbed provider (or against real Gemini Flash if `GEMINI_API_KEY` + `AIW_E2E=1` are set), and asserts the run row lands in Storage with migrations applied. Script is **not** added to CI at M13 (live providers); it is the manual release-gate script invoked from T04 before `uv publish`. Documented in `design_docs/phases/milestone_13_v0_release/release_runbook.md`.
4. **PyPI name claimed.** A `ai-workflows` PyPI name check is performed; if taken, namespace the package (candidates: `aiw-framework`, `ai-workflows-langgraph`, or `<user>-ai-workflows`). Final name decision recorded in T02's spec + `pyproject.toml` `[project].name` + every doc that quotes the name. Changing the package name does *not* change the CLI script names (`aiw`, `aiw-mcp`) — those stay stable.
5. **README install section.** Root `README.md § Getting started` grows a pre-`uv sync` "Install from PyPI" sub-section documenting three paths:
   - **One-shot (recommended):** `uvx --from ai-workflows aiw run planner …` (no permanent install).
   - **Persistent tool install:** `uv tool install ai-workflows` then `aiw run planner …`.
   - **Existing clone (contributors):** the current `uv sync` flow stays as the second heading.
6. **Skill install doc extended.** [`skill_install.md §2 Install the MCP server`](../milestone_9_skill/skill_install.md) gains an "Option A-bis — via uvx (no clone required)" sub-section: `claude mcp add ai-workflows --scope user -- uvx --from ai-workflows aiw-mcp`. Option A (clone-based) stays primary for contributors; the new option is the user path. `tests/skill/test_doc_links.py` stays green.
7. **CHANGELOG `[0.1.0]` release section.** `CHANGELOG.md` gets a `## [0.1.0] — 2026-MM-DD` header above the Keep-a-Changelog template, listing the M1–M9 surfaces as one bulleted inventory under `### Added` (not per-milestone — the release-notes audience does not map to milestones). `## [Unreleased]` stays in place above it for post-0.1.0 work.
8. **First PyPI publish.** `uv publish --token $PYPI_TOKEN` (from a one-shot token, not long-lived credentials) succeeds against pypi.org for the `0.1.0` wheel. A second smoke — `uvx --from ai-workflows==0.1.0 aiw version` against the real PyPI-hosted package — verifies the published artefact resolves. Observation + commit sha baseline recorded in the T04 CHANGELOG close-out block.
9. **Gates green.** `uv run pytest` + `uv run lint-imports` (4 contracts kept — M12's new contract lands at M12 T02, not here) + `uv run ruff check` all clean at T05 close-out.
10. **M11 landed before T04.** The first-time-user gate-review UX (ISS-02 closure) must be in place before the first PyPI upload. If M11 is still open when M13 reaches T04, the milestone **stops and waits** rather than shipping a broken first-install experience. See §*Dependencies* for rationale.

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

## Task order

| # | Task | Kind |
| --- | --- | --- |
| 01 | [pyproject polish + wheel contents fix](task_01_pyproject_polish.md) | code + test |
| 02 | PyPI name claim + clean-venv install smoke | code + test + doc |
| 03 | README install section + skill_install.md uvx option | doc + test |
| 04 | CHANGELOG `[0.1.0]` section + first PyPI publish (manual) | doc + release |
| 05 | Milestone close-out | doc |

Per-task spec files land as each predecessor closes (same convention as M10 / M11 / M12). T01 is spec'd below; T02–T05 are written at each predecessor's close-out. The README alone is enough context to start T01.

## Dependencies

- **M11 (hard).** A first-time PyPI install that walks the skill's gate-pause flow lands on `plan: null` and a non-reviewable gate — the defect ISS-02 named. Shipping `0.1.0` before M11 would publish a broken first-impression UX for the primary documented install path. **If M11 has not landed by T04 kickoff, M13 T04 stops and waits.** T01–T03 can run in parallel with M11 because they touch no `ai_workflows.mcp/` surface.
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
