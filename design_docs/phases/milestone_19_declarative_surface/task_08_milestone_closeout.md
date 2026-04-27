# Task 08 — Milestone close-out + 0.3.0 publish ceremony

**Status:** ✅ Complete (2026-04-26).
**Grounding:** [milestone README](README.md) · [ADR-0008](../../adr/0008_declarative_authoring_surface.md) · [KDR-002 (MCP-as-substrate — preserved through release)](../../architecture.md) · Tasks 01–07 (the deliverables this close-out promotes) · [release_runbook.md](../milestone_13_v0_release/release_runbook.md) (the established release pattern) · [M16 Task 01 close-out](../milestone_16_external_workflows/task_01_external_workflow_modules.md) (most recent minor; M19 mirrors its release ritual) · [`CHANGELOG.md`](../../../CHANGELOG.md) (the file being promoted) · [`pyproject.toml`](../../../pyproject.toml) (the version field being bumped).

## What to Build

Close M19. T01–T07 landed clean per their respective audit issue files; the declarative authoring surface is shipped (T01 + T02), the artefact-loss bug is fixed (T03), the new `summarize` workflow ships as the in-tree spec-API proof point (T04 — both planner and slice_refactor ports deferred per locked H2 + Q5; `aiw run --input KEY=VALUE` extension landed per locked H1), the documentation surface (5 docs across T05's `writing-a-workflow.md` + T06's new `writing-a-custom-step.md` + T07's `writing-a-graph-primitive.md` alignment + `architecture.md` extension model + `README.md` extending section) is in place. T08 is the standard milestone flip + CHANGELOG promote + 0.3.0 publish ceremony following the established release pattern from M13 / M14 / M16.

The release is **0.3.0 minor bump** (per ADR-0008 §Consequences + M19 README §Release): the introduction of a new primary authoring surface (`register_workflow(WorkflowSpec)`) + the repositioning of the existing one (`register(name, build_fn)`) as the documented escape hatch is substantial enough to warrant the bump even though both APIs coexist. The artefact-field bug fix + `plan` deprecation alias compose into the same release.

## Deliverables

### 1. Milestone README close-out flip

[milestone README](README.md):

- Flip **Status** from `📝 Planned` to `✅ Complete (YYYY-MM-DD)`.
- Append an **Outcome** section summarising:
  - T01–T07 summary (one-line each) with landing commits.
  - Release artefact: `jmdl-ai-workflows==0.3.0` on pypi.org with SHA256 + publish-side commit.
  - Two-branch model: `main:<sha>`, `design_branch:<sha>` (pre-T08 tips, then post-T08 tips).
  - Green-gate snapshot: `uv run pytest`, `uv run lint-imports` (4 contracts kept — no new layer at M19), `uv run ruff check`.
  - Spec-API proof-point result: T04 shipped `summarize` as the in-tree workflow validating the spec API end-to-end through both surfaces. Both planner and slice_refactor ports are deferred (locked Q5 + locked H2 — both have the M8/M10 fault-tolerance overlay; one combined re-open trigger captured in `nice_to_have.md` per T07 Deliverable 5). The original five built-ins (`LLMStep`, `ValidateStep`, `GateStep`, `TransformStep`, `FanOutStep`) covered `summarize` without taxonomy extension.
- Fill in **Propagation status** — name the release commits, record any forward-deferrals + `nice_to_have.md` entries written, confirm any next milestones triggered by M19's findings.
- Resolve M19 README §Decisions Q1 (slot range α): record the actual `nice_to_have.md` slot range M19 took (verify at close-out time by re-grep). M10's T05 picks up after this range when M10 thaws.

### 2. Roadmap

[`design_docs/roadmap.md`](../../roadmap.md):

- Flip M19 row Status to `✅ complete (YYYY-MM-DD)`.
- Add or update the M19 row in §M2–M19 summaries with a one-paragraph summary of what shipped (declarative surface + bug fix + doc rewrite + 0.3.0 release).
- M10 + M15 + M17 rows unchanged (still pending their respective triggers).

### 3. Pre-publish gates (run before any version bump)

```bash
# All gates green on both branches:
uv run pytest
uv run lint-imports
uv run ruff check

# M19 spec API proof — summarize workflow + integration tests pass:
uv run pytest tests/workflows/test_summarize.py -v
uv run pytest tests/integration/test_spec_api_e2e.py -v

# Both deferred-port escape hatches still work (planner + slice_refactor unchanged):
uv run pytest tests/workflows/ -k planner -v
uv run pytest tests/workflows/ -k slice_refactor -v
uv run pytest tests/workflows/ -k ollama_fallback -v

# Compatibility shim probe — every pre-M19 in-tree caller still works:
uv run python -c "
from ai_workflows.workflows.planner import build_planner, FINAL_STATE_KEY, TERMINAL_GATE_ID
from ai_workflows.workflows.slice_refactor import build_slice_refactor, FINAL_STATE_KEY as SR_FSK
assert FINAL_STATE_KEY == 'plan'
assert TERMINAL_GATE_ID == 'plan_review'
assert SR_FSK == 'applied_artifact_count'
print('M19 close-out compatibility shim probe OK')
"

# Spec-API surface probe — register_workflow + every step type importable:
uv run python -c "
from ai_workflows.workflows import (
    WorkflowSpec, Step, LLMStep, ValidateStep, GateStep, TransformStep,
    FanOutStep, RetryPolicy, register_workflow,
)
print('M19 close-out spec-API surface probe OK')
"

# release_smoke.sh — existing pre-publish smoke runs the wheel-build + import checks:
bash scripts/release_smoke.sh
```

All probes must pass before the version bump in §4.

### 4. Version bump + CHANGELOG promote

`ai_workflows/__init__.py` is the **single source of truth** for the package version (per the 0.1.2 dynamic-version pivot — `pyproject.toml` declares `dynamic = ["version"]` and reads `__version__` via hatchling). Bump `__version__ = "0.2.0"` → `__version__ = "0.3.0"`. **Do not** add a static `version =` field to `pyproject.toml`; that would either duplicate the source-of-truth or break hatchling's dynamic version resolution.

`CHANGELOG.md` on **both branches** (mirror entries — design_branch's entries are the source; main gets a user-facing subset):

Promote the `[Unreleased]` M19 entries (T01 → T08) into a new dated section. Two CHANGELOG shapes per the project convention:

#### `design_branch` CHANGELOG.md
- New `## [M19 v0.3.0 release] - YYYY-MM-DD` section with all M19 T01–T07 entries promoted from `[Unreleased]`.
- Add a T08 close-out entry at the top of the new section:
  - Reference M19 README Outcome section.
  - Record the green-gate snapshot.
  - Record the release-commits pair: `main:<sha>`, `design_branch:<sha>`.
- Top-of-file `[Unreleased]` section retained (empty post-promote; ready for post-0.3.0 work).

#### `main` CHANGELOG.md
- New `## [0.3.0] - YYYY-MM-DD` section with the user-facing subset of M19's changes (filter out audit-trail framing; keep the user-observable behaviour changes).
- Sections under `## [0.3.0]`:
  - `### Added` — declarative authoring surface (`WorkflowSpec` + step taxonomy + `register_workflow` + custom-step extension hook).
  - `### Changed` — `RunWorkflowOutput.artifact` is the canonical artefact field; `plan` deprecated alias preserved through 0.2.x line; `docs/writing-a-workflow.md` rewritten declarative-first; `architecture.md` extended with §"Extension model"; `README.md` "Extending ai-workflows" section.
  - `### Fixed` — `_dispatch.py` artefact-field bug (composes with the rename — non-`plan` `FINAL_STATE_KEY` workflows now round-trip their artefact correctly).
  - `### Deprecated` — `RunWorkflowOutput.plan` / `ResumeRunOutput.plan` field. Removal target: 1.0.

### 5. `uv build` + `uv publish`

```bash
uv build
uv publish
```

The `uv build` artifacts (`dist/jmdl_ai_workflows-0.3.0-py3-none-any.whl` + `dist/jmdl_ai_workflows-0.3.0.tar.gz`) must pass wheel-contents inspection per the [pre-publish dependency-auditor gate](../../../.claude/agents/dependency-auditor.md):

```bash
unzip -l dist/jmdl_ai_workflows-0.3.0-py3-none-any.whl
# Expected: only ai_workflows/, LICENSE, README.md, CHANGELOG.md
# Forbidden: .env*, design_docs/, runs/, *.sqlite3, builder-mode artefacts
```

### 6. Post-publish live smoke from `/tmp`

After publish + CDN propagation:

```bash
cd /tmp
uv cache clean jmdl-ai-workflows
uvx --refresh --from jmdl-ai-workflows==0.3.0 aiw version
# Expected: 0.3.0

# Spec API live-smoke:
uvx --refresh --from jmdl-ai-workflows==0.3.0 python -c "
from ai_workflows.workflows import (
    WorkflowSpec, LLMStep, ValidateStep, register_workflow,
)
print('0.3.0 live smoke OK')
"

# Backward compatibility live-smoke:
uvx --refresh --from jmdl-ai-workflows==0.3.0 python -c "
from ai_workflows.workflows.planner import build_planner, FINAL_STATE_KEY
assert FINAL_STATE_KEY == 'plan'
print('0.3.0 backward compat live smoke OK')
"

# Real-Gemini live-smoke for the summarize workflow (post-publish only;
# requires GEMINI_API_KEY in the operator's environment). This is the
# load-bearing real-provider proof per H2 framing — the M19 spec API
# successfully drives a real LLM call end-to-end through aiw run:
GEMINI_API_KEY="$GEMINI_API_KEY" uvx --refresh --from jmdl-ai-workflows==0.3.0 \
  aiw run summarize --text 'The quick brown fox jumps over the lazy dog. The fox was very fast.' \
                    --max-words 10 --run-id smry-live-0.3.0
# Expected: exit 0; stdout contains a summary of the input; total_cost_usd >= 0.
```

The `uv cache clean` + `--refresh` pattern is the established mitigation for uvx's sticky cache (per the M13 / M16 close-out pattern; documented in the project memory `project_m13_shipped_cs300_next.md`).

### 7. Stamp `### Published` footer on `main`

After live-smoke confirms 0.3.0 is reachable + behaves correctly, stamp the `### Published` footer on `main`'s CHANGELOG entry:

```markdown
## [0.3.0] - YYYY-MM-DD

<existing release content>

### Published
- Wheel SHA256: `<hash>`
- PyPI URL: https://pypi.org/project/jmdl-ai-workflows/0.3.0/
- Live-smoke verified from /tmp on YYYY-MM-DD.
```

### 8. Push both branches to origin

```bash
git push origin main
git push origin design_branch
```

### 9. Project memory update

Update `~/.claude/projects/-home-papa-jochy-prj-ai-workflows/memory/project_m13_shipped_cs300_next.md` (or write a fresh memory file) reflecting:

- 0.3.0 released; M19 declarative authoring surface is live.
- M18 obsoleted (folded into M19 T03).
- M10 still on hold; thawing trigger unchanged (CS-300 trigger).
- M15 + M16-deferred + M17 still spec'd, not started.
- Next likely return trigger: CS-300 hits something else from the live 0.3.0 surface, or an unrelated milestone surfaces.

## Acceptance Criteria

- [ ] **AC-1:** Milestone README Status flipped to `✅ Complete (YYYY-MM-DD)`. Outcome section + Propagation status + Decision-resolution (slot range record) per Deliverable 1.
- [ ] **AC-2:** `roadmap.md` M19 row updated with complete status + close-out date + one-paragraph summary in §M2–M19 summaries.
- [ ] **AC-3:** Pre-publish gates pass per Deliverable 3 — pytest, lint-imports, ruff, summarize test sweep (`tests/workflows/test_summarize.py`), spec-API integration test sweep (`tests/integration/test_spec_api_e2e.py`), planner test suite (`-k planner`), slice_refactor test suite (`-k slice_refactor`; verifies the deferred-port escape-hatch path still works), Ollama-fallback test suite (`-k ollama_fallback`), compatibility shim probe, spec-API surface probe, release_smoke.sh.
- [ ] **AC-4:** `ai_workflows/__init__.py` `__version__` bumped to "0.3.0" (single source of truth; `pyproject.toml` declares `dynamic = ["version"]` and reads from `__init__.py`). No static `version =` field added to `pyproject.toml`.
- [ ] **AC-5:** CHANGELOG promoted on `design_branch` per Deliverable 4. `design_branch` carries **both** blocks: the user-facing `## [0.3.0] - YYYY-MM-DD` block (Added / Changed / Fixed / Deprecated sub-sections) placed **above** the audit-trail-inclusive `## [M19 Declarative Authoring Surface — 0.3.0 release] - YYYY-MM-DD` section. The `## [0.3.0]` block is cherry-picked to `main` during the user's publish ceremony; the M19 design-trail section is `design_branch`-only. AC-9 is the post-publish `### Published` footer stamp on whatever `main`-side block exists — that remains a user-owned step.
- [ ] **AC-6:** `uv build` produces clean wheel + sdist; wheel-contents inspection per Deliverable 5 confirms only the four expected paths (ai_workflows/, LICENSE, README.md, CHANGELOG.md) — no `.env*` / `design_docs/` / `runs/` / `*.sqlite3`.
- [ ] **AC-7:** `uv publish` succeeds; PyPI shows the 0.3.0 release.
- [ ] **AC-8:** Live-smoke from `/tmp` passes per Deliverable 6 — `aiw version` reports 0.3.0; spec-API import probe + backward-compat import probe both succeed.
- [ ] **AC-9:** `### Published` footer stamped on `main` CHANGELOG with wheel SHA256 + PyPI URL.
- [ ] **AC-10:** Both branches pushed to origin.
- [ ] **AC-11:** Project memory updated per Deliverable 9.
- [ ] **AC-12:** Status surfaces flipped together at close-out — milestone README status line, milestone README task table rows (T01–T07 all show as Complete), milestone README "Done when" checkboxes (every exit criterion ticked).
- [ ] **AC-13:** No deep-analysis pass required at T08 (close-out only). All T01–T07 audit issue files closed clean per their own audit cycles.
- [ ] **AC-14:** No drive-by changes. T08 is doc-only + CHANGELOG-only + release-mechanics. Zero runtime-code diff in `ai_workflows/` (per the M13 T08 close-out pattern).
- [ ] **AC-15:** If any finding surfaces during close-out (e.g. a `ruff` warning, a CHANGELOG inconsistency, a wheel-contents anomaly), it forks to a new milestone / `nice_to_have.md` / carry-over per CLAUDE.md close-out conventions — not absorbed into T08 as a drive-by fix.

## Dependencies

- **Tasks 01–07** — all complete and audited clean.
- **Wheel-contents pre-publish gate** — non-skippable per CLAUDE.md `## Non-negotiables`. The dependency-auditor agent reviews the wheel before publish.
- **No deep-analysis pass.** M19 is a packaging milestone at T08; the runtime-code surface diffs all belong to T01–T04's audit cycles.

## Out of scope (explicit)

- **No runtime code change in `ai_workflows/`.** T08 is doc + CHANGELOG + release mechanics only.
- **No new tests.** Test surface is established by T01–T04.
- **No new ADRs.** ADR-0008 is the load-bearing decision; no follow-up ADR is needed for close-out.
- **No M10 thaw work.** M10 stays on hold; M19 close-out's `nice_to_have.md` slot allocation lands ahead of M10's planned range (per M19 README §Decisions Q1 = α).
- **No M15 / M17 work.** Those milestones remain on hold per their own forcing functions.

## Carry-over from prior milestones

- **M18 obsolescence record.** ADR-0008 captured the M18 deletion; T08's project-memory update may reference it.
- **M10 status carry-forward.** M10 stays cold; the slot-drift defensive clause in M10 T05 will handle the actual `nice_to_have.md` slot range M19 took.

## Carry-over from M19 T01 audit (2026-04-26)

These four items surfaced in M19 T01's `/clean-implement` cycle 1 audit + security review (see [`issues/task_01_issue.md`](issues/task_01_issue.md)). Each is non-blocking for T01's PASS verdict but must land before the 0.3.0 publish. Folded here so T08's pre-publish ceremony absorbs them.

- [ ] **CARRY-T01-HIGH-1 — sdist publish-hygiene gap (security review HIGH-1).** The `.tar.gz` sdist published at the next PyPI release would leak `.claude/settings.local.json` (operator username + full tool-permission allow-list), `CLAUDE.md`, every `.claude/agents/*.md` system prompt, and the entire `design_docs/` tree. The wheel (`.whl` consumed by `uvx`/`uv tool install`) is clean — only the sdist is affected. **Pre-existing** publish-hygiene gap (not introduced by M19 T01); affects every PyPI publish from this repo.
      **Action at T08 Deliverable 4 (Pre-publish step, before `uv build`):** add a `[tool.hatch.build.targets.sdist]` block to `pyproject.toml` excluding the leak surfaces. Concrete shape:
      ```toml
      [tool.hatch.build.targets.sdist]
      exclude = [
          "/.claude",
          "/CLAUDE.md",
          "/design_docs",
          "/tests/skill",
          "/scripts/spikes",
      ]
      ```
      **Verify after `uv build`:** `tar -tzf dist/jmdl_ai_workflows-0.3.0.tar.gz | grep -E '(\.claude|CLAUDE|design_docs|tests/skill|scripts/spikes)'` returns no matches. Add this to T08's existing wheel-contents inspection step (Deliverable 5) — currently inspects the wheel only; extend to inspect the sdist as well.

- [ ] **CARRY-T01-LOW-1 — `ValidateStep.schema` field-shadowing pydantic UserWarning.** Importing `ai_workflows.workflows.spec` emits `UserWarning: Field name "schema" in "ValidateStep" shadows an attribute in parent "Step"`. Cosmetic — the field works correctly; tests are green; the warning is one-time-per-process.
      **Decision needed at T08:** rename the field (cleaner — aligns with `WorkflowSpec.input_schema` / `output_schema` naming) OR suppress the warning (one-line `warnings.filterwarnings(...)` at `spec.py` module top; preserves the Q1-locked field name).
      **Recommendation:** suppress at T08 (cheaper than a rename that would propagate through T05's worked example + T06's docs + downstream-consumer-facing API). Land the suppression as part of T08's pre-publish polish pass; document the choice in the T08 Outcome record.

- [ ] **CARRY-T01-LOW-2 — T01 spec internal inconsistency: AC-10 wording vs Deliverable 1 imports.** AC-10 reads *"`spec.py` imports stdlib + `pydantic` + `ai_workflows.workflows` only; no graph or primitives imports."* But Deliverable 1 explicitly requires `primitives.retry` (for `RetryPolicy` re-export per Q1) and `primitives.tiers` (for `TierConfig` typing on `WorkflowSpec.tiers`). The four-layer rule allows `workflows → primitives` so the imports are correct; AC-10's wording is more restrictive than the architecture.
      **Action at T08 Deliverable 1 (Milestone README close-out flip):** edit `task_01_workflow_spec.md` AC-10 to read *"Layer rule preserved — `uv run lint-imports` reports 4 contracts kept, 0 broken. `spec.py` imports stdlib + `pydantic` + `ai_workflows.primitives.retry` + `ai_workflows.primitives.tiers` only (the permitted `workflows → primitives` direction); no graph or surface imports."* This aligns AC-10 with Deliverable 1 + the four-layer rule. Pure spec amendment; no source-code change.

- [ ] **CARRY-T01-LOW-3 — `Step.compile()` body framing in T01 spec.** Spec Deliverable 3 shows the stub body as `...  # noqa: stub`; Builder shipped `raise NotImplementedError("...lands in M19 T02 (_compiler.py)...")` instead. Builder's choice is **better** (a typed-return method with `Ellipsis` body silently returns `None` if invoked; `NotImplementedError` produces a diagnostic failure) but the spec text doesn't sanction the deviation.
      **Action at T08 Deliverable 1:** edit `task_01_workflow_spec.md` Deliverable 3 to annotate the stub-body shape — *"`NotImplementedError(...)` or `...` are both acceptable; the locked contract is the signature, not the body."* No source-code change required.

## Carry-over from M19 T07 audit (2026-04-26)

These four items surfaced in M19 T07's cycle 1 audit (see [`issues/task_07_issue.md`](issues/task_07_issue.md)). User locked option 2 (defer to T08) for MEDIUM-1 and chose to bundle LOW-1 + LOW-2 + LOW-3 into the same T08 carry-over. All four items are non-blocking for T07's PASS verdict but must be addressed during T08's doc-pass before the 0.3.0 publish. Items are mechanical doc-prose edits; no behaviour change; verify gates green after each touch.

- [ ] **CARRY-T07-MEDIUM-1 — Class-level + function-level docstring prose drift (M11 T01 framing residue).**
      Sources: T03 cycle 2 LOW-3 + T03 cycle 1 §4.4 doc drift. Both forward-deferred to T07; T07 spec carry-over did not include them; T07 cycle 1 audit re-deferred to T08 per locked option 2.
      **Action at T08 release-ceremony doc pass (before `uv build`):** mechanical search-and-replace pass updating these 6 sites:
      - `ai_workflows/mcp/schemas.py:91` (class-level docstring on `RunWorkflowOutput.plan` legacy alias).
      - `ai_workflows/mcp/schemas.py:178, 183-184` (`ResumeRunOutput.plan` + the two `plan_at_pause` lines).
      - `ai_workflows/workflows/_dispatch.py:729, 994, 999, 1093` (function-level docstrings on `_build_result_from_final` / `_build_resume_result_from_final`).
      - `design_docs/architecture.md:106` (the §4.4 M11 T01 line: *"`RunWorkflowOutput.plan` / `ResumeRunOutput.plan` carry the in-flight draft plan..."*).
      Replace M11 T01 framing ("in-flight draft" / "re-gated draft" / "last-draft artefact") with the post-T03 honest framing: "follows `FINAL_STATE_KEY`; may be `None` at gate-pause for workflows whose `FINAL_STATE_KEY` channel is empty pre-gate." Composes with the T07-shipped §"Extension model" gate-pause projection note in architecture.md.
      One-line search-and-replace touches; no behaviour change. Verify gates green after each touch.

- [ ] **CARRY-T07-LOW-1 — `architecture.md §"Extension model"` shipped at 19 lines vs. spec's ~50-80 line target.**
      Source: T07 cycle 1 audit LOW-1.
      **Action at T08 doc pass:** optional polish — expand the §"Extension model" section closer to spec target by adding examples, more detailed framing of the four-tier promise, deeper elaboration of the graduation pattern. Per T07 issue file's recommendation: "Total expansion ~25-30 lines, taking the section to ~50 lines (lower bound of the spec target)." All 5 required structural elements are already present at 19 lines (framing + tier table + out-of-scope + graduation + ADR-0008 ref + gate-pause note); the expansion is depth, not new content. Mark optional — Builder discretion at T08 implement time.

- [ ] **CARRY-T07-LOW-2 — Anchor slugs in 3 cross-links to `architecture.md §"Extension model"` computed wrong.**
      Source: T07 cycle 1 audit LOW-2.
      3 sites use `#extension-model----extensibility-is-a-first-class-capability` (4 hyphens; wrong); GFM renders the actual section heading as `#extension-model-extensibility-is-a-first-class-capability` (1 hyphen; em-dash dropped). File-level link resolves; in-page jump broken.
      Sites:
      - `docs/writing-a-graph-primitive.md:3` (audience banner)
      - `docs/writing-a-graph-primitive.md:15` (lead paragraph in §When to write a new graph primitive)
      - `docs/writing-a-custom-step.md:324` (Pointers to adjacent tiers — T06-LOW-1 absorption)
      **Action at T08 doc pass:** 3 one-line edits replacing the wrong anchor with the GFM-rendered slug. Mechanical search-and-replace.

- [ ] **CARRY-T07-LOW-3 — Tier-label format diverges across 3 tier tables.**
      Source: T07 cycle 1 audit LOW-3.
      3 tier tables show the same 4 tiers with divergent display labels:
      - `design_docs/architecture.md:174-177` — `1 — Compose / 2 — Parameterise / 3 — Author a custom step type / 4 — Escape to LangGraph directly`
      - `README.md:82-85` — `**1. Compose** / **2. Parameterise** / **3. Author a custom step type** / **4. Escape to LangGraph directly**`
      - `docs/writing-a-custom-step.md:12-15` (T06-shipped) — `Tier 1 — compose / Tier 2 — parameterise / Tier 3 — author a custom step / Tier 4 — escape hatch`
      Pick canonical form + align all three. Auditor's recommended canonical: architecture.md's `1 — Compose / 2 — Parameterise / 3 — Author a custom step type / 4 — Escape to LangGraph directly` (no bold; em-dash separator; full label).
      **Action at T08 doc pass:** harmonize the 3 tier tables to a single canonical format. Mechanical edits.

## Carry-over from M19 T07 security review (2026-04-26)

These items surfaced in M19 T07's security gate (see [`issues/task_07_issue.md`](issues/task_07_issue.md) §Security review). Verdict was FIX-THEN-SHIP — T07's own diff is clean; SEC-HIGH-1 is a pre-existing regression from M16 T01 that this doc-touching task surfaced. Natural owner is T08 pre-publish.

- [ ] **CARRY-SEC-HIGH-1 — Restore `README.md §Security notes` subsection (PyPI long-description surface).**
      Source: T07 security review SEC-HIGH-1.
      The `### Security notes` subsection (present in 0.1.3 release `b01b1ec` and the 0.2.0 release-prep commit `e3607a9`) was dropped at M16 T01 (`01ceb9b`) and is absent from the current committed HEAD. The threat model (§4 MCP HTTP transport bind address) explicitly requires this content: the `--host 0.0.0.0` foot-gun documentation + `--cors-origin` opt-in framing. The default is safe (loopback) and no docs actively teach `--host 0.0.0.0`, so this is a "could-be-better" gap on the PyPI README rather than an active mislead — but it must close before 0.3.0 ships.
      **Action at T08 release-ceremony doc pass (before `uv build`):** restore a one-paragraph `### Security notes` subsection under `## MCP server` (or its post-T07 equivalent location) covering: (1) `aiw-mcp` defaults to loopback (`127.0.0.1`); (2) `--host 0.0.0.0` exposes the server to every process on the host and to the LAN with no built-in auth (use only behind a reverse proxy that adds auth); (3) `--cors-origin` is opt-in and not required for stdio or loopback HTTP. Source the canonical wording from the 0.1.3 README at commit `b01b1ec` (verifiable via `git show b01b1ec:README.md`). Verify the restored section after running `uv build` + the wheel-contents check.

- [ ] **CARRY-SEC-ADV-1 — (Optional) Restore `README.md §Setup` env-var + Claude OAuth guidance.**
      Source: T07 security review SEC-ADV-1 (advisory; not blocking).
      The `## Setup` section with environment variable / Claude OAuth subprocess guidance was also dropped at M16 T01. Less urgent than SEC-HIGH-1 (no foot-gun documented) but its restoration alongside CARRY-SEC-HIGH-1 makes the README coherent again.
      **Action at T08 doc pass:** optional restoration alongside CARRY-SEC-HIGH-1. Builder discretion at T08 implement time.

## Carry-over from task analysis

## Carry-over from task analysis

- [ ] **TA-LOW-05 — CHANGELOG promote convention review** (severity: LOW, source: task_analysis.md round 1)
      T08 Deliverable 4 prescribes `## [M19 v0.3.0 release] - YYYY-MM-DD` for the design_branch CHANGELOG. The actual existing M14 + M16 close-out convention may use a slightly different shape.
      **Recommendation:** Audit `CHANGELOG.md` at implement time for the exact convention used in M14 + M16 close-outs, and follow that pattern; the spec's prescribed shape may need adjustment to match the live file.

- [ ] **TA-LOW-08 — Live-smoke `--max-words 10` against a 17-word input is tight** (severity: LOW, source: task_analysis.md round 3)
      T08 Deliverable 6 live-smoke uses `aiw run summarize --text 'The quick brown fox jumps over the lazy dog. The fox was very fast.' --max-words 10`. The input is 17 words; asking the LLM to summarise to 10 words is tight (the LLM might emit 12 words). Live-smoke is acceptance-soft (verify exit 0 + non-empty output, not strict word-count adherence) so this isn't a blocker.
      **Recommendation:** Expand the input text to a longer paragraph (so a 10-word summary is genuinely a summarisation rather than near-truncation) OR raise `--max-words` to 25. Optional polish; doesn't block landing.
