# Task 08 — Milestone close-out + 0.3.0 publish ceremony

**Status:** 📝 Planned.
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
- [ ] **AC-5:** CHANGELOG promoted on both branches per Deliverable 4. `design_branch` gets the audit-trail-inclusive M19 release section; `main` gets the user-facing `[0.3.0]` block with Added / Changed / Fixed / Deprecated sub-sections.
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

## Carry-over from task analysis

- [ ] **TA-LOW-05 — CHANGELOG promote convention review** (severity: LOW, source: task_analysis.md round 1)
      T08 Deliverable 4 prescribes `## [M19 v0.3.0 release] - YYYY-MM-DD` for the design_branch CHANGELOG. The actual existing M14 + M16 close-out convention may use a slightly different shape.
      **Recommendation:** Audit `CHANGELOG.md` at implement time for the exact convention used in M14 + M16 close-outs, and follow that pattern; the spec's prescribed shape may need adjustment to match the live file.

- [ ] **TA-LOW-08 — Live-smoke `--max-words 10` against a 17-word input is tight** (severity: LOW, source: task_analysis.md round 3)
      T08 Deliverable 6 live-smoke uses `aiw run summarize --text 'The quick brown fox jumps over the lazy dog. The fox was very fast.' --max-words 10`. The input is 17 words; asking the LLM to summarise to 10 words is tight (the LLM might emit 12 words). Live-smoke is acceptance-soft (verify exit 0 + non-empty output, not strict word-count adherence) so this isn't a blocker.
      **Recommendation:** Expand the input text to a longer paragraph (so a 10-word summary is genuinely a summarisation rather than near-truncation) OR raise `--max-words` to 25. Optional polish; doesn't block landing.
