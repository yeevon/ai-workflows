# Task 07 — `CHANGELOG.md [0.1.0]` section + first PyPI publish (manual)

**Status:** 🚧 In progress — pre-publish work complete; first `uv publish` rejected 2026-04-22 with `400 The name 'ai-workflows' is too similar to an existing project.` Distribution renamed to `jmdl-ai-workflows` (see §Rename addendum below); publish retry pending.
**Grounding:** [milestone README §Exit-criteria-10 + §Exit-criteria-11](README.md) · [task_06 close](issues/task_06_issue.md) · [release_runbook.md](release_runbook.md) · [scripts/release_smoke.sh](../../../scripts/release_smoke.sh) · [architecture.md §9 KDR-002 (surface portability)](../../architecture.md) · [architecture.md §9 KDR-008 (MCP schema public contract)](../../architecture.md) · [pyproject.toml](../../../pyproject.toml).

## Rename addendum (2026-04-22)

T07's first `uv publish` attempt against real pypi.org returned:

```text
400 The name 'ai-workflows' is too similar to an existing project.
```

No byte was uploaded — pypi.org rejects at metadata-parse before the wheel transfer, so the `0.1.0` slot on the rejected name remains theoretically available (moot for our purposes — we moved off the name). The T02 pre-publish name-availability check (`curl /pypi/ai-workflows/json` → 404) proves exact-name availability but does **not** exercise pypi.org's stricter confusable-name check, which uses normalized-name collision against the full existing-project set. This is the lesson for any future new-name claim: the 404 check alone is necessary but not sufficient.

**Resolution.** Renamed `[project].name` from `ai-workflows` to `jmdl-ai-workflows` (author's initials-prefixed; `jmdl-ai-workflows/json` returned 404 at 2026-04-22 21:44 UTC). What changed:

- `pyproject.toml [project].name = "jmdl-ai-workflows"`.
- Every user-facing install snippet on `main` + `design_branch` — `uvx --from jmdl-ai-workflows`, `uv tool install jmdl-ai-workflows`.
- CHANGELOG `[0.1.0]` block's `### Published` footer — `https://pypi.org/project/jmdl-ai-workflows/0.1.0/` + wheel filename `jmdl_ai_workflows-0.1.0-py3-none-any.whl`.
- Wheel-discovery glob in `scripts/release_smoke.sh:51` + `tests/test_wheel_contents.py:64` loosened from the literal `ai_workflows-*.whl` to `*.whl`; one-wheel assertion preserved.
- `uv.lock` regenerated.

What did **not** change:

- Python module name (`ai_workflows` — import paths unchanged; LangGraph adapters, primitives, tests keep importing `from ai_workflows.X`).
- Entry points (`aiw`, `aiw-mcp` unchanged — PyPI distribution name is independent of console-script names).
- MCP server name in `claude mcp add ai-workflows --scope user -- ...` (user-local identifier; unrelated to PyPI).
- GitHub repository URL (`github.com/yeevon/ai-workflows`).
- Storage conventions (`~/.ai-workflows/` user-data directory).

**References to read as post-rename.** Every `ai-workflows` occurrence below in the §Deliverables / §Execution protocol / §Acceptance criteria sections that is either (a) a `uvx --from …` / `uv tool install …` install snippet or (b) a `pypi.org/project/…/` URL should be read as `jmdl-ai-workflows` / `jmdl-ai-workflows` respectively. Other `ai-workflows` references (module name, MCP server name, repo URL, `.claude/skills/ai-workflows/` path) are unaffected.

**Status of the publish retry.** Pre-publish re-smoke against the rename commit pair (`main` → `56cedd5`, `design_branch` → `146c9fe`) green; full gate passes (`uv run pytest` → 610 passed, 9 skipped; `uv run lint-imports` → 4 contracts kept; `uv run ruff check` → clean). `uv publish jmdl_ai_workflows-0.1.0-py3-none-any.whl` is the next irreversible action.

## What to Build

T07 is the one-shot irreversible moment M13 has been building toward. Three deliverables composed into one atomic release:

1. **`CHANGELOG.md [0.1.0]` release section** — a consolidated user-facing summary of every surface M1–M9 (plus the M11 gate-review and M14 HTTP-transport preconditions) landed, replacing the per-milestone `[Unreleased]` block audience-mismatch called out in exit-criterion 10. Lands on **both** branches with different content on each (see §Branch-specific CHANGELOG shapes).
2. **`uv publish --token $PYPI_TOKEN` from `main`** — the first upload of the `ai-workflows==0.1.0` wheel to pypi.org. Runs **after** the `[0.1.0]` block on `main` is committed so the wheel's `CHANGELOG.md` carries the release-notes narrative a first-time PyPI visitor reads.
3. **Post-publish `uvx --from ai-workflows==0.1.0 aiw version` live smoke + CHANGELOG close-out stamping** — from a clean venv resolved against real pypi.org, prove the published wheel is installable + the `aiw` entry point resolves; record the pypi.org artefact URL + SHA256 digest + published wheel filename + the publish-side commit SHA back into the CHANGELOG `[0.1.0]` block on **both** branches under a `**Published:**` footer.

**Irreversibility.** Once `uv publish` uploads a given `name + version` pair, pypi.org **never** accepts a re-upload of the same pair — even after `pip install --force-reinstall` rehearsals on the publisher side. A bad publish forces a bump to `0.1.0.post1` (`post`-release) or `0.1.1` (patch), never a re-attempt. This shapes the execution protocol: every rehearsable step (CHANGELOG edits, build, hermetic release-smoke, dry-run metadata-only twine check) runs **before** the destructive `uv publish` call, and the operator gets a hard-stop checkpoint with the final plan before the upload.

**Branch execution model.** T07 is the first M13 task that commits on **both** branches. Previous tasks (T01–T04 pre-split on `design_branch`; T05 split itself; T06 on `design_branch` only) kept `main`'s git history clean. T07 breaks that pattern deliberately: the `[0.1.0]` block must land on `main` because the wheel that uploads to PyPI is built from `main`, and PyPI reads `CHANGELOG.md` via the `pyproject.toml` long-description pointer (or at minimum via repo browsing on the Homepage URL). Two forward commits: one on `main` (CHANGELOG + publish), one on `design_branch` (CHANGELOG mirror + audit + spec + close-out).

## Deliverables

### 1. `CHANGELOG.md [0.1.0]` release section — both branches

#### Branch-specific CHANGELOG shapes

**On `main` (the release branch).** The `[0.1.0]` block is the **user-facing release summary**. The pre-T07 `main` `CHANGELOG.md` carries a single `## [Unreleased]` block with the M13 T05 mirror entry (dated 2026-04-22). At T07 close-out on `main`:

- **Insert the `## [0.1.0] — 2026-04-22` block** directly **below** `## [Unreleased]` and **above** the T05 mirror entry, so chronological reverse-order is preserved: `Unreleased` (still in place for post-0.1.0 work) → `[0.1.0] — 2026-04-22` (the consolidated release) → `Unreleased` history that gets absorbed into `[0.1.0]`.
- **Absorb the M13 T05 block** into the `[0.1.0]` block (the user-facing release summary subsumes the branch-split narrative) — delete the free-standing T05 `### Changed — M13 Task 05 …` block from `main` only. The `design_branch` retains the full audit trail.
- **Structure:** a `### Added` sub-heading listing the surfaces below as one bulleted inventory (not per-milestone — per exit-criterion 10 directive).

  ```markdown
  ## [0.1.0] — 2026-04-22

  First public release. Ships the packaged runtime + CLI + MCP surface that
  milestones M1–M9 built, plus M11's gate-review projection and M14's
  streamable-HTTP transport which are preconditions for a usable first-install
  experience.

  ### Added

  - **Four-layer package** (`ai_workflows/`) — `primitives` (storage, cost,
    tiers, providers, retry, structured logging), `graph` (LangGraph adapters:
    `TieredNode`, `ValidatorNode`, `HumanGate`, `CostTrackingCallback`,
    `RetryingEdge`, SQLite checkpointer), `workflows` (the `planner` and
    `slice_refactor` `StateGraph`s), and the two user-facing surfaces: `cli`
    (`aiw run`, `aiw resume`, `aiw list-runs`, `aiw version`) and `mcp`
    (`aiw-mcp` with four MCP tools: `run_workflow`, `resume_run`,
    `list_runs`, `cancel_run`). Import-linter contract enforces the layer
    direction.
  - **Provider tiering** — Gemini Flash (orchestrator / implementer /
    `gemini_flash` tiers via `GEMINI_API_KEY` + LiteLLM), Qwen2.5-Coder via
    Ollama (`local_coder` tier), Claude Code OAuth subprocess (`planner-synth`
    tier). No Anthropic API (KDR-003).
  - **Ollama hardening** — circuit breaker + three-bucket retry taxonomy
    (transient / retriable / fatal) + fallback-gate pause on tier
    unavailability (M8).
  - **Claude Code skill** — `.claude/skills/ai-workflows/` ships a
    first-class skill the Claude Code IDE auto-discovers. M11 T01 added the
    plan + gate_context projection at the plan-review pause so operators
    receive a reviewable artefact (not `plan: null`).
  - **MCP surfaces** — stdio (Claude Code / Cursor / Zed) via
    `claude mcp add ai-workflows --scope user -- uvx --from ai-workflows
    aiw-mcp`; streamable-HTTP (Astro / browser-origin consumers) via
    `aiw-mcp --transport http --host 127.0.0.1 --port 8000`. Identical
    schema across transports (FastMCP + pydantic).
  - **Install paths** — `uvx --from ai-workflows aiw run planner …` for
    one-shot invocations; `uv tool install ai-workflows` for persistent
    installs; `git clone` for contributors.
  - **Documentation** — user-facing `docs/architecture.md`,
    `docs/writing-a-workflow.md`, and `docs/writing-a-graph-primitive.md`
    cover the four-layer model, authoring a new workflow, and authoring a
    new graph primitive respectively. `README.md` ships a trimmed three-
    paragraph overview + Install section + Getting started pointer.
  - **Storage** — SQLite via `yoyo-migrations` (`migrations/001_initial.sql`,
    `migrations/002_reconciliation.sql`). Migrations are bundled in the
    wheel via `[tool.hatch.build.targets.wheel.force-include]` (T01).
  - **Branch model** — `main` is the user-facing release branch; the
    builder/auditor workflow (`design_docs/`, `CLAUDE.md`,
    `.claude/commands/`) lives on `design_branch`. Contributing guide
    at `.github/CONTRIBUTING.md`.

  ### Published

  - **PyPI:** https://pypi.org/project/ai-workflows/0.1.0/
  - **Wheel:** `ai_workflows-0.1.0-py3-none-any.whl`
  - **SHA256:** `<filled-in-post-publish>`
  - **Publish-side commit:** `<main-sha-after-changelog-commit>` (the
    commit that produced the wheel `uv publish` uploaded).
  - **Pre-publish release-smoke:** `scripts/release_smoke.sh` green from
    `main` at `8f1fd8e` (T06 close-out) and from the publish-side
    commit itself (see T07 audit §Gate summary).
  ```

  The `### Published` footer lines marked `<filled-in-post-publish>` stay as literal placeholders in the pre-publish commit; the T07 post-publish amendment commit (step 11 of §Execution protocol) replaces them with real values.

**On `design_branch` (the builder branch).** The full audit history stays intact — no block deletion. At T07 close-out on `design_branch`:

- **Prepend a new `## [0.1.0] — 2026-04-22` block** above the existing `## [Unreleased]` block's T06 entry, using **the same body** as the `main`-side `[0.1.0]` block for the `### Added` inventory.
- **Keep the T06 + T05 + T04 + T03 + T02 + T01 `### Changed/Added — M13 Task NN …` entries intact** under `## [Unreleased]` (builder-side audit trail).
- **Add a T07-specific mirror block** under `## [Unreleased]`, above the T06 entry, describing the `design_branch`-side footprint: CHANGELOG mirror landed, audit file written, spec drafted.

#### Decision on content of the `### Added` inventory

The inventory lists **user-visible surfaces**, not milestones or internal modules. Rationale: a first-time PyPI visitor reading `[0.1.0]` wants to know "what can I do with this?", not "what builder-mode sub-tasks produced it?". Milestone numbers (M1–M14) are preserved in `design_docs/roadmap.md` on `design_branch`; they do not belong in the `main`-side release notes.

### 2. `uv publish` from `main` — pre-flight + upload + retention

#### Pre-flight (must all pass before the destructive step)

1. **Branch:** `git rev-parse --abbrev-ref HEAD` → `main`.
2. **Working tree:** `git status --short` empty.
3. **Last commit:** `git log -1 --oneline` matches the commit T07's `[0.1.0]` CHANGELOG block landed on (this is the commit whose artefact will be uploaded).
4. **Token:** `echo $UV_PUBLISH_TOKEN | head -c 10` echoes a `pypi-AgEI…` prefix (T07 operator will `set -a && source .env && set +a` before step 4 per prior `.env` precedent — the pattern already used for `GEMINI_API_KEY`). Alternative env var names: `PYPI_TOKEN` (then `export UV_PUBLISH_TOKEN=$PYPI_TOKEN`) — `uv publish` reads `UV_PUBLISH_TOKEN` by default.
5. **`uv` version:** `uv --version` resolves. (The T06 smoke already exercised this; T07 treats it as non-blocking.)
6. **Release smoke:** `bash scripts/release_smoke.sh` from the `main` HEAD of the CHANGELOG commit (step 3) exits 0 with `=== OK — release smoke passed ===`. T06 ran the smoke at `8f1fd8e`; T07 re-runs it **against the new commit** (the `[0.1.0]` CHANGELOG commit is a post-T06 HEAD on `main`) to catch any `pyproject.toml` or wheel-build regression the CHANGELOG commit itself might have introduced. Log the second smoke's outcome in `release_runbook.md §5` alongside T06's entry.
7. **Wheel-contents hermetic test** (no network): `AIW_BRANCH=main uv run pytest tests/test_wheel_contents.py -v` on `main` passes. This is the pre-flight proof that the wheel being uploaded contains `migrations/001_initial.sql` + `migrations/002_reconciliation.sql` and **excludes** `design_docs/` + `CLAUDE.md` + `.claude/commands/`.
8. **pypi.org name + version check.** `uv pip index versions ai-workflows --index https://pypi.org/simple/` returns either "no versions available" (first upload, expected) or a versions list **not including** `0.1.0` (would indicate a previous publish — T07 stops and we patch-bump instead).
9. **Final operator confirmation.** The Builder prints `git log -1 --oneline`, the wheel filename about to be uploaded, and the `[0.1.0]` CHANGELOG block verbatim, then **stops and waits for operator "proceed"**. No `uv publish` runs without this confirmation.

#### Upload

```bash
uv publish --token "$UV_PUBLISH_TOKEN"
```

One call. No retries — if upload fails (network, 4xx from pypi.org, token invalidation, name-squat race), the Builder stops and surfaces the error. The failure modes break down as:

- **Token invalid / expired / wrong scope** → operator rotates token, re-runs from pre-flight.
- **Name claimed by another project between T02's verification and T07's upload** → M13 stops; ADR on package-name strategy; T02 + downstream doc edits re-run with new name.
- **Network transient** → operator retries `uv publish` directly; the CHANGELOG commit + wheel build does not need redoing.
- **pypi.org returns 5xx** → wait and retry; status page check at https://status.python.org/.
- **Version already published** (shouldn't happen post-step 8 but guarded anyway) → stop; patch-bump to `0.1.0.post1` + re-run T07 from deliverable 1.

#### Retention

The built wheel `dist/ai_workflows-0.1.0-py3-none-any.whl` is intentionally **not** gitignored — `dist/` already is. Post-upload, the builder captures:

- SHA256 digest: `sha256sum dist/ai_workflows-0.1.0-py3-none-any.whl | cut -d' ' -f1`.
- Wheel filename: literal string `ai_workflows-0.1.0-py3-none-any.whl`.
- pypi.org artefact URL: `https://pypi.org/project/ai-workflows/0.1.0/`.
- Publish-side commit: `git rev-parse HEAD` on `main` (the CHANGELOG commit SHA).

These four values land in the `### Published` CHANGELOG footer on both branches in deliverable 3's amendment commit.

### 3. Post-publish live smoke + CHANGELOG close-out stamping

#### Live smoke (against real pypi.org)

From a **fresh shell** with no repo-local Python on PATH (to ensure the test hits the real PyPI-hosted wheel, not a locally-cached build artefact), run:

```bash
cd /tmp
uvx --from ai-workflows==0.1.0 aiw version
```

Expected stdout: `0.1.0` (single line). Any of the following constitute failure:

- Exit code ≠ 0 → investigate whether `uv` cache pinned a stale index; `rm -rf ~/.cache/uv` and retry once.
- Stdout ≠ `0.1.0` → the published wheel disagrees with its declared version; stop and investigate `pyproject.toml`/`ai_workflows.__init__.py` consistency (shouldn't happen — pre-flight step 7 proved the wheel before upload).
- Network timeout against pypi.org → retry once after 60s; if persists, mark as yellow in the close-out log and move on (the wheel is published; the smoke's role is a soft confirmation, not a gate — the upload succeeded per the 200-response from `uv publish`).

This smoke is **deliberately minimal** — one entry-point, one version print. The full `aiw run planner --goal '…'` path is not re-exercised here (that's T06's release-smoke scope, run pre-publish). Rationale: the entry-point + version resolution proves pypi.org's CDN has propagated the upload and `uvx`-fetch works end-to-end. Running a full planner workflow here would burn a real Gemini Flash call for marginal additional signal.

#### CHANGELOG close-out stamping (amendment commits)

After the live smoke passes:

- **On `main`:** one new commit titled `M13 T07 — fill [0.1.0] Published footer with pypi.org artefact`. Edits `CHANGELOG.md` `### Published` footer only, replacing the four `<filled-in-post-publish>` placeholders with the real values captured in deliverable 2's Retention step.
- **On `design_branch`:** cherry-pick the `main`-side amendment commit so the `[0.1.0]` block's `### Published` footer is byte-identical on both branches. (Cherry-pick is clean because the `[0.1.0]` block lands on both branches in the pre-publish commit pair; the amendment only touches the `### Published` footer lines.)

### 4. Audit issue file — `design_branch` only

Per standard T0N convention: `design_docs/phases/milestone_13_v0_release/issues/task_07_issue.md`. Structure mirrors T06's issue file: status line, design-drift check, AC-by-AC grade (11 ACs below), Additions-beyond-spec section, Gate summary table (must include the pre-flight release-smoke + the wheel-contents hermetic test + the post-publish live smoke + both-branch CHANGELOG shape), HIGH/MEDIUM/LOW sections (expected empty for a clean close), Deferred-to-nice_to_have (expected empty), Propagation status.

### 5. Release-runbook §5 second smoke log entry

Append a second log entry to `release_runbook.md §5` for the T07 pre-publish smoke (distinct from the T06 entry). Record: date, SHA (the T07 `[0.1.0]` CHANGELOG commit), branch `main`, result, notes. The T06 entry stays in place above it — chronological order preserved.

## Acceptance Criteria

- [ ] AC-1: `CHANGELOG.md` on `main` carries the `## [0.1.0] — 2026-04-22` block directly below `## [Unreleased]`, with the `### Added` user-surface inventory per Deliverable 1 §Branch-specific CHANGELOG shapes.
- [ ] AC-2: `CHANGELOG.md` on `main` has the pre-T07 M13 T05 `### Changed — M13 Task 05 …` block absorbed into the `[0.1.0]` block (removed from its free-standing location).
- [ ] AC-3: `CHANGELOG.md` on `design_branch` carries the `## [0.1.0] — 2026-04-22` block with byte-identical `### Added` content to `main`'s block (diff only acceptable on the free-standing T04/T05/T06 `[Unreleased]` builder entries `main` lacks).
- [ ] AC-4: `CHANGELOG.md` on `design_branch` preserves the T05 + T06 free-standing `### Changed/Added — M13 Task NN …` entries under `## [Unreleased]` and adds a new T07 design-branch mirror entry above the T06 entry.
- [ ] AC-5: `bash scripts/release_smoke.sh` run from `main` at the T07 CHANGELOG commit (post-8f1fd8e) exits 0 with the `=== OK — release smoke passed ===` tail. Outcome logged in `release_runbook.md §5` as a second entry (below the T06 2026-04-22 entry).
- [ ] AC-6: `AIW_BRANCH=main uv run pytest tests/test_wheel_contents.py -v` on `main` passes — wheel contains `migrations/001_initial.sql` + `migrations/002_reconciliation.sql` and excludes `design_docs/` + `CLAUDE.md` + `.claude/commands/`.
- [ ] AC-7: `uv publish --token "$UV_PUBLISH_TOKEN"` succeeds against real pypi.org for `ai_workflows-0.1.0-py3-none-any.whl`. Proof: `https://pypi.org/project/ai-workflows/0.1.0/` resolves to the project page and the wheel is listed under its Downloads.
- [ ] AC-8: Post-publish live smoke `uvx --from ai-workflows==0.1.0 aiw version` run from a shell outside the repo directory (`cd /tmp`) prints exactly `0.1.0` on stdout and exits 0.
- [ ] AC-9: The `### Published` footer in the `[0.1.0]` CHANGELOG block on both branches carries the four captured values — pypi.org URL, wheel filename, SHA256 digest, publish-side commit SHA. The amendment commit on `main` is cherry-picked to `design_branch` so the footer is byte-identical.
- [ ] AC-10: `uv run pytest` + `uv run lint-imports` + `uv run ruff check` green on **both** branches post-T07. Design_branch uses `AIW_BRANCH=design uv run pytest`; `main` uses `AIW_BRANCH=main uv run pytest` (or unset — `main` is the default). Test counts: `design_branch` 623 passed + 6 skipped (unchanged from T06 close); `main` matches its T05 close baseline.
- [ ] AC-11: Zero unexpected files on either branch post-T07. On `main`: CHANGELOG.md touched twice (pre-publish + Published-footer amendment). On `design_branch`: CHANGELOG.md touched, `release_runbook.md §5` appended, `task_07_changelog_publish.md` + `issues/task_07_issue.md` added. No `ai_workflows/` / `pyproject.toml` / test-tree edits on either branch.

## Dependencies

- **T06 complete + clean** (✅ landed 2026-04-22, commit `3e3f6c1` on `design_branch` — T06 audit closed with 12/12 ACs PASS; zero open issues; pre-publish release-smoke logged green from `main` at `8f1fd8e`).
- **`PYPI_TOKEN` or `UV_PUBLISH_TOKEN`** exported in the operator's shell at T07 step 4. Source: pypi.org → Account Settings → API tokens → "Add API token" with scope "Entire account" (project-scoped token not yet creatable because the project doesn't exist on pypi.org pre-T07). Already provisioned in `/home/papa-jochy/prj/ai-workflows/.env` as `PYPI_TOKEN`; `.env` is gitignored and has never been committed.
- **Post-T07 token rotation (recommended).** Revoke the account-wide token immediately after T07 closes. Create a new project-scoped token for post-0.1.0 publishes. This is standard PyPI hygiene, not T07 scope.

## Out of scope (explicit)

- **No `ai_workflows/` change.** T07 is CHANGELOG + publish only.
- **No `pyproject.toml` change.** Version `0.1.0` is already set; the T01 + T02 + T04 packaging polish is in place.
- **No test additions.** Existing `tests/test_wheel_contents.py` + `tests/test_main_branch_shape.py` + `tests/skill/test_doc_links.py` (design_branch) cover the T07 surface.
- **No CI-gated publish workflow.** Manual publish with one-shot token per milestone exit-criterion 11; auto-publish-on-tag is a `nice_to_have.md` §17+ candidate.
- **No `0.1.0.post1` patch pre-bumped.** T07 publishes `0.1.0` and stops. Any post-release defect triggers a separate milestone with its own task flow.
- **No `TestPyPI` dry-run.** The T06 release-smoke + T07 pre-flight wheel-contents test + T07 pre-flight release-smoke re-run cover every regression the TestPyPI rehearsal would catch, without consuming the test-index.pypi.org name-space or introducing dry-run-vs-real divergence.
- **No live-provider `AIW_E2E=1` re-run.** T06's hermetic release-smoke + T07's `uvx --from ai-workflows==0.1.0 aiw version` post-publish smoke together cover "installable + entry-point resolves"; running a full planner workflow as part of T07 burns a real Gemini Flash call for marginal signal.
- **No mass-backfill of `main` CHANGELOG history.** The `[0.1.0]` block is the **first** user-facing entry on `main` — prior per-milestone builder entries live on `design_branch` only by design.

## Execution protocol

T07 is the most destructive task in M13; the protocol leans on operator-approval pauses at every irreversible step:

1. **Draft the `[0.1.0]` block** (this spec's Deliverable 1 body) on `design_branch` in `CHANGELOG.md`. Keep `### Published` footer with the four `<filled-in-post-publish>` placeholders literal.
2. **Run gates on `design_branch`:** `AIW_BRANCH=design uv run pytest` + `uv run lint-imports` + `uv run ruff check`. All three must be green.
3. **Prepend T07 design-branch mirror entry** above the T06 `[Unreleased]` entry on `design_branch` CHANGELOG.
4. **Write the audit issue file** at `design_docs/phases/milestone_13_v0_release/issues/task_07_issue.md` — pre-publish AC-1 through AC-6, AC-10, AC-11 graded; AC-7, AC-8, AC-9 marked `⏳ pending-publish`.
5. **Operator pause 1.** Show the operator `git diff --stat` + `git status` on `design_branch`. Stop and wait for "proceed".
6. **On "proceed": commit + push on `design_branch`.** Single commit titled `M13 T07 — [0.1.0] CHANGELOG block + audit file (pre-publish)`. Push.
7. **Switch to `main`.** Cherry-pick the `[0.1.0]` CHANGELOG block from `design_branch` onto `main`'s CHANGELOG.md (applying the absorb-T05-block edit per Deliverable 1).
8. **Run gates on `main`:** `uv run pytest` + `uv run lint-imports` + `uv run ruff check`. All three must be green.
9. **Pre-flight checks.** Run the 8 pre-flight checks from Deliverable 2. If any fails, stop and surface. Run `bash scripts/release_smoke.sh`; record outcome in `release_runbook.md §5` on `design_branch` (separate edit, appended to T06's §5 entry — the `main`-side `release_runbook.md` does not exist; this edit lives on `design_branch` only).
10. **Operator pause 2 — the destructive gate.** Print `git log -1 --oneline` on `main`, the wheel filename `ai_workflows-0.1.0-py3-none-any.whl`, the SHA256 of the pre-built wheel, and the `[0.1.0]` CHANGELOG block verbatim. **Stop and wait for "proceed with publish".** No `uv publish` without this confirmation.
11. **On "proceed with publish": run `uv publish --token "$UV_PUBLISH_TOKEN"`.** Capture the pypi.org URL, wheel filename, SHA256, and publish-side commit SHA.
12. **Post-publish live smoke.** `cd /tmp && uvx --from ai-workflows==0.1.0 aiw version`. Assert stdout `0.1.0`.
13. **Amendment commit on `main`.** Replace the four `<filled-in-post-publish>` placeholders in the `[0.1.0]` `### Published` footer with the captured values. Commit titled `M13 T07 — fill [0.1.0] Published footer with pypi.org artefact`. Push.
14. **Cherry-pick to `design_branch`.** `git checkout design_branch && git cherry-pick <main-amendment-sha>`. Gates should pass byte-identically (the cherry-pick only touches CHANGELOG footer lines). Push.
15. **Close the audit file.** On `design_branch`, flip AC-7, AC-8, AC-9 from `⏳ pending-publish` to ✅ PASS with the captured artefact values in-line. Commit titled `M13 T07 — audit close-out with post-publish artefact values`. Push.
16. **Report to operator:** pypi.org URL, wheel filename, SHA256, both-branch commit SHAs, close-out audit file link.

**No step 11 without step 10's "proceed with publish".** Every other step is reversible (`git reset`, re-edit, re-commit); step 11 is the irreversible one.

## Propagation status

Filled in at audit time. Anticipated forward-deferrals:

- **Post-T07 token rotation** — not forward-deferred (no future task owns it); surfaced to operator as a post-close recommendation in the T07 audit file's `## Post-close operator actions` section.
- **CI-gated publish-on-tag job** — `nice_to_have.md §17+` candidate; trigger hasn't fired (solo dev, no mishandled-token incident). Record in T07 audit under `## Deferred to nice_to_have`.

## Carry-over from prior audits

None at T07 drafting. T06 audit closed with 12/12 ACs PASS and zero forward-deferrals.
