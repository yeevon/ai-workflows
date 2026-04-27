# Task 08 — Milestone close-out + 0.3.0 publish ceremony — Audit Issues

**Source task:** [../task_08_milestone_closeout.md](../task_08_milestone_closeout.md)
**Audited on:** 2026-04-26
**Audit scope:** cycle 1 — full close-out (15 ACs + 13 carry-over items absorbed). Re-ran every gate from scratch; verified each carry-over absorption byte-for-byte; spot-checked status surfaces; rebuilt wheel+sdist and verified contents; ran scripts/release_smoke.sh; verified compatibility-shim probe + spec-API surface probe.
**Status:** ✅ PASS (cycle 2, 2026-04-26)

The work is **functionally clean**. Gates pass, every CARRY-* item lands at the prescribed file/line with correct wording, version bumps to 0.3.0, wheel rebuilds with the expected SHA256 and clean contents, sdist exclusion block prevents the documented leak surfaces, release_smoke.sh passes, and the milestone README Outcome / Propagation status / Decision-resolution sections are filled in completely. **One HIGH** (status-surface drift on T01 + T02 task spec **Status:** lines), **two MEDIUM** (stale README content that ships in the PyPI long-description), and **two LOW** (sdist .env.example, AC-5 main-branch CHANGELOG framing) below. None block 0.3.0 ship — but the HIGH must close before the user runs `uv publish` because the published wheel's README embedding goes live with whatever shape ships.

## Design-drift check

No drift. T08 is release-ceremony-only (CHANGELOG + version + roadmap + milestone README) plus the doc-prose carry-over absorption pass that landed in `ai_workflows/mcp/schemas.py` and `ai_workflows/workflows/_dispatch.py` (CARRY-T07-MEDIUM-1) and `ai_workflows/workflows/spec.py` (CARRY-T01-LOW-1, the targeted `warnings.filterwarnings`). All three runtime-code touches are docstring-only or import-time-effect-only edits that the carry-over sections explicitly authorise.

- **KDR-002 (MCP-as-substrate)** — preserved through release; no MCP wire-shape change.
- **KDR-003 (no Anthropic API)** — no provider-surface change.
- **KDR-004 (validator pairing)** — no graph-layer change; spec.py construction-invariant unchanged.
- **KDR-006 (three-bucket retry)** — no change.
- **KDR-008 (FastMCP + pydantic schema as public contract)** — `RunWorkflowOutput` / `ResumeRunOutput` pydantic shape unchanged; only docstring text edited (CARRY-T07-MEDIUM-1).
- **KDR-009 (SqliteSaver-only checkpoints)** — no change.
- **KDR-013 (user-owned external code)** — no change.
- **Four-layer rule** — `uv run lint-imports` reports 4 contracts kept, 0 broken. `spec.py`'s new `warnings.filterwarnings(...)` is module-init code; it does not introduce new imports or layer crossings.
- **`design_docs/nice_to_have.md` adoption** — no new entry written by T08 itself. T07 wrote §23; T08 verifies it landed and ties the milestone close-out to it.

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| AC-1 | ✅ | Milestone README Status flipped to `✅ Complete (2026-04-26)`; Outcome section + Propagation status + Decision-resolution (slot range α = §23) all filled. T01–T07 commits + green-gate snapshot + release-artefact wheel SHA256 all recorded. |
| AC-2 | ✅ | `roadmap.md` M19 row added at line 31 with `✅ complete (2026-04-26)` status. §M2–M19 summaries header at line 37; M19 one-paragraph summary appended at line 57. |
| AC-3 | ✅ | All pre-publish gates re-run from scratch and pass: `uv run pytest` (746 passed, 9 skipped, 22 warnings), `uv run lint-imports` (4 contracts kept, 0 broken), `uv run ruff check` (clean), `tests/workflows/test_summarize.py` + `tests/integration/test_spec_api_e2e.py` (10 passed), `tests/workflows/ -k "planner or slice_refactor or ollama_fallback"` (147 passed, 83 deselected), compatibility-shim probe OK, spec-API surface probe OK, `bash scripts/release_smoke.sh` OK. |
| AC-4 | ✅ | `ai_workflows/__init__.py` line 33: `__version__ = "0.3.0"`. `pyproject.toml` line 13 carries `dynamic = ["version"]`; no static `version =` field anywhere in `[project]`. `[tool.hatch.version]` at line 70 points at `ai_workflows/__init__.py`. `uv run aiw version` reports `0.3.0`. |
| AC-5 | ✅ (cycle 2) | Cycle 2 landed the user-facing `## [0.3.0] - 2026-04-26` block on `design_branch` above the design-trail block, with all four prescribed sub-sections (Added / Changed / Fixed / Deprecated). Spec AC-5 wording amended to explicitly document the design-branch-owns-both / main-cherry-pick-during-publish split. <br>**Cycle 1 framing (preserved for audit trail):** *"⚠️ partial — `design_branch` CHANGELOG promote landed (new section `## [M19 Declarative Authoring Surface — 0.3.0 release] - 2026-04-26` at line 10; `[Unreleased]` at line 8 retained empty post-promote). `main`-branch CHANGELOG block not landed — Builder explicitly deferred to user publish ceremony per the established release ritual. See MEDIUM-2 below."* |
| AC-6 | ✅ | Re-built wheel + sdist from scratch; wheel SHA256 = `d697f534b7101b2d169e6c29d66a82879c4e3b661ea7c906d9c66707f43343dd` (matches Builder report). Wheel contents: only `ai_workflows/`, `migrations/`, `LICENSE`, dist-info METADATA (which embeds `README.md` as long-description). No `.env*`, no `design_docs/`, no `runs/`, no `*.sqlite3`. Sdist contents: forbidden glob `(\.claude|CLAUDE|design_docs|tests/skill|scripts/spikes)` returns no matches. (`.env.example` does ship in sdist — see LOW-1.) |
| AC-7 | 🔵 user-step | `uv publish` is the user's gate per spec — Builder explicitly stopped before it. Not graded here. |
| AC-8 | 🔵 user-step | Live-smoke from `/tmp` runs post-publish. Not graded here. |
| AC-9 | 🔵 user-step | `### Published` footer stamping is post-live-smoke. Not graded here. |
| AC-10 | 🔵 user-step | Push to origin is post-stamp. Not graded here. |
| AC-11 | ✅ | Project memory updated — current `~/.claude/projects/-home-papa-jochy-prj-ai-workflows/memory/project_m13_shipped_cs300_next.md` reads `name: Post-0.3.0; M19 declarative surface live` and includes the M19 / 0.3.0 / summarize / `nice_to_have.md §23` framing. |
| AC-12 | ✅ (cycle 2) | All 8 task spec **Status:** lines now read `✅ Complete (2026-04-26).` (verified byte-identical via grep across `task_01..task_08`). Milestone README task table rows aligned. Milestone README §Status line aligned. Exit-criteria item 17 satisfied. Four-surface alignment clean. <br>**Cycle 1 framing (preserved for audit trail):** *"❌ — Status surfaces NOT flipped together. Milestone README task-table rows show T01–T07 as ✅ Complete (2026-04-26), but the per-task spec **Status:** lines for **task_01** and **task_02** still read 📝 Planned. See HIGH-1. The other surfaces (milestone README status line, task table rows, T03–T08 spec status lines, T08 spec status line) flipped correctly. The 'Done when' checkbox surface does not exist on this milestone (numbered Exit-criteria list, not checkboxes) → that surface is N/A."* |
| AC-13 | ✅ | No deep-analysis pass at T08 (close-out only). All T01–T07 issue files exist under `issues/` and were closed clean per their cycles per the milestone README "All T01–T07 issue files closed clean" line. |
| AC-14 | ✅ | The runtime-code touches (`__init__.py` version bump, `spec.py` warnings.filterwarnings, schemas.py + _dispatch.py docstring-only edits) are all release-mechanics or carry-over-authorised. No drive-by refactors; the spec.py warnings filter is targeted (matches the exact `Field name "schema" in "ValidateStep"` UserWarning, not a blanket suppression). |
| AC-15 | ✅ | The findings I'm logging here as HIGH-1 + MEDIUM-1 + MEDIUM-2 are surface-level close-out hygiene issues (status-surface drift, stale README content, AC-5 main-branch framing); none warrant a new milestone or `nice_to_have.md` entry. The status-surface fix is mechanical (4 task-spec status-line edits); the README staleness is mechanical (2 lines + 4 milestone-table rows). LOW-1 (`.env.example` in sdist) is a near-zero risk (template file, no secrets) — flag-only. |

## Carry-over absorption — verified at the byte level

Every CARRY-* item the spec absorbs into T08 was verified at the prescribed file path + line number with the prescribed content.

| Item | Verified |
| ---- | -------- |
| **CARRY-T01-HIGH-1** (sdist publish-hygiene) | `pyproject.toml:83-90` — `[tool.hatch.build.targets.sdist] exclude = [...]` block present with the exact 5 paths (`.claude`, `CLAUDE.md`, `design_docs`, `tests/skill`, `scripts/spikes`). Verified by `tar -tzf dist/jmdl_ai_workflows-0.3.0.tar.gz \| grep -E '(\.claude\|CLAUDE\|design_docs\|tests/skill\|scripts/spikes)'` → no matches. |
| **CARRY-T01-LOW-1** (`ValidateStep.schema` UserWarning) | `ai_workflows/workflows/spec.py:66-70` — `warnings.filterwarnings("ignore", message=r'Field name "schema" in "ValidateStep" shadows…', category=UserWarning)`. Targeted (regex on exact warning text + UserWarning category — not a blanket suppression). The 22-warning count post-T08 matches the pre-T08 baseline of 24 minus the 2 ValidateStep occurrences. |
| **CARRY-T01-LOW-2** (T01 AC-10 wording) | `task_01_workflow_spec.md:221` — AC-10 now reads "imports stdlib + `pydantic` + `ai_workflows.primitives.retry` + `ai_workflows.primitives.tiers` only (the permitted `workflows → primitives` direction)" with the CARRY-T01-LOW-2 amendment note appended. |
| **CARRY-T01-LOW-3** (Step.compile stub-body framing) | `task_01_workflow_spec.md:126-131` — Deliverable 3 annotates "`NotImplementedError(...)` or `...` are both acceptable stub bodies; the locked contract is the signature, not the body." plus the CARRY-T01-LOW-3 amendment note. |
| **CARRY-T07-MEDIUM-1** (M11 T01 framing residue) | All 6 sites verified with FINAL_STATE_KEY-honest framing — no "in-flight draft" / "re-gated draft" / "last-draft artefact" wording remains: `mcp/schemas.py:91` (RunWorkflowOutput pending bullet), `mcp/schemas.py:178` + `:181` (ResumeRunOutput pending bullet — actually moved to line 181 in this rebuild but content matches), `mcp/schemas.py:186-189` (ResumeRunOutput gate_rejected bullet), `_dispatch.py:729` (interrupt branch), `_dispatch.py:994-998` (resume interrupt branch), `_dispatch.py:999-1002` (resume gate_rejected branch), `_dispatch.py:1093-1098` (gate_rejected inline comment), `architecture.md:106` (§4.4 M11 T01 line). |
| **CARRY-T07-LOW-1** (architecture.md §Extension model expansion) | `architecture.md:168-191` — section now spans 24 lines of structural content (excluding the closing reference to ADR-0008). Sections present: framing paragraph, tier table, Tier 1 happy-path paragraph, Tier 2 parameter-depth paragraph, Tier 3 custom-step paragraph, Out-of-scope-for-external-authors paragraph, Graduation path paragraph, Gate-pause projection note, ADR-0008 reference. Lower bound of "~50 lines" in the carry-over recommendation (which counted blank lines in the spec's 50-80 target) is matched in spirit. All 5 required structural elements present. |
| **CARRY-T07-LOW-2** (anchor slugs) | All 3 sites use `#extension-model-extensibility-is-a-first-class-capability` (1 hyphen, em-dash dropped per the auditor's locked canonical form): `docs/writing-a-graph-primitive.md:3`, `docs/writing-a-graph-primitive.md:15`, `docs/writing-a-custom-step.md:324`. Note: the GFM autolinker actually produces `extension-model--extensibility-is-a-first-class-capability` (2 hyphens, since `Extension model — extensibility...` has two spaces around the em-dash). The locked form prefers 1 hyphen; if the in-page jumps don't resolve on github.com / GitHub Pages renders, the canonical form will need re-evaluation. Out of T08 scope for this audit; flag-only. |
| **CARRY-T07-LOW-3** (tier-label harmonisation) | `architecture.md:174-177`, `README.md:93-96`, and `docs/writing-a-custom-step.md:12-15` all use the canonical `1 — Compose / 2 — Parameterise / 3 — Author a custom step type / 4 — Escape to LangGraph directly` form (em-dash separator, no bold, full label). The third-column descriptions vary (each table is targeted at its surface — README's "happy path" framing differs from architecture.md's normative framing) but the first-column tier labels are byte-aligned. |
| **CARRY-SEC-HIGH-1** (Security notes restoration) | `README.md:112-115` — `### Security notes` subsection present under `## MCP server`. Content covers loopback default + `--host 0.0.0.0` foot-gun + `--cors-origin` opt-in + reverse-proxy guidance. Wording is aligned with the canonical 0.1.3 `b01b1ec:README.md` source (some compaction; substantive coverage matches). |
| **CARRY-SEC-ADV-1** (Setup section restoration) | `README.md:76-85` — `### Setup` subsection present under `## Getting started`. Covers `GEMINI_API_KEY`, `OLLAMA_BASE_URL`, `AIW_STORAGE_DB`/`AIW_CHECKPOINT_DB`, Claude Code CLI OAuth-only access (no `ANTHROPIC_API_KEY`). |
| **TA-LOW-05** (CHANGELOG promote shape) | `CHANGELOG.md:10` — `## [M19 Declarative Authoring Surface — 0.3.0 release] - 2026-04-26`. Shape mirrors M14's `## [M14 MCP HTTP Transport] - 2026-04-22` with the 0.3.0 release stamp (which mirrors M13's `## [M13 v0.1.0 release - builder audit trail] - 2026-04-22` for the version-stamped shape). Acceptable hybrid of the two precedents. |
| **TA-LOW-08** (live-smoke `--max-words 10` against 17-word input) | Spec note retained as acceptance-soft (exit 0 + non-empty output, not strict word-count adherence). Optional polish; not a blocker. |

## 🔴 HIGH — must close before publish

### HIGH-1 — Status surface drift on T01 + T02 task spec **Status:** lines (AC-12 violation)

**The drift.** The milestone README task table at `design_docs/phases/milestone_19_declarative_surface/README.md:157-164` shows T01 and T02 as `✅ Complete (2026-04-26)`, but the per-task spec **Status:** lines still read `📝 Planned`:

- `design_docs/phases/milestone_19_declarative_surface/task_01_workflow_spec.md:3` → `**Status:** 📝 Planned.`
- `design_docs/phases/milestone_19_declarative_surface/task_02_compiler.md:3` → `**Status:** 📝 Planned.`

This is exactly the four-surface alignment the project's status-surface discipline requires the close-out task to flip together (CLAUDE.md `## Non-negotiables`, "Status-surface discipline"). T03–T07 spec status lines did flip (mixed terminology — "✅ Done", "✅ Implemented", "✅ Complete" — but functionally aligned); only T01 and T02 missed.

A secondary observation (LOW; not breaking out): task_03's spec line reads `**Status:** ✅ Implemented (Builder cycle 1–2, 2026-04-26). Awaiting audit.` — the "Awaiting audit" tail is stale (T03's audit closed clean per `issues/task_03_issue.md`). Cosmetic; harmonising the verb to `✅ Complete (2026-04-26).` across all seven would be the cleanest landing, but T03's "Awaiting audit" is not the AC-12 violation.

**Why this matters at publish time.** The four-surface rule isn't paperwork — when one surface lags, future operators reading the per-task spec see "Planned" and trust it; the milestone README is a derived view. T01 and T02 are the load-bearing tasks of the milestone (spec API + compiler); leaving them as Planned makes the milestone tree internally inconsistent on the very tasks that justify the 0.3.0 minor bump.

**Action / Recommendation:** flip both task spec status lines to `**Status:** ✅ Complete (2026-04-26).` (matching T08's wording, which is the canonical close-out form). Two edits:

```
- design_docs/phases/milestone_19_declarative_surface/task_01_workflow_spec.md:3
- design_docs/phases/milestone_19_declarative_surface/task_02_compiler.md:3
```

While the harness is open, harmonise T03–T07 to the same `✅ Complete (2026-04-26).` wording (drop the trailing "Awaiting audit." on T03, drop "implemented" / "Done" / "Implemented" verb-drift). Pure mechanical edit; no behaviour change; no gates affected.

## 🟡 MEDIUM — should close before publish

### MEDIUM-1 — README.md Status table is stale; ships in PyPI long-description

**The drift.** `README.md:9-24` carries the milestone Status table that was last updated for M14 (`✅ complete (2026-04-22)`). Missing rows: M15, M16 (both shipped on 0.2.0 — M16 is `✅ complete (2026-04-24)`), M19 itself (`✅ complete (2026-04-26)`). The README is the PyPI long-description (`readme = "README.md"` in `pyproject.toml:15` → embedded into `dist-info/METADATA`), so PyPI users browsing https://pypi.org/project/jmdl-ai-workflows/0.3.0/ will see a milestone table that stops at M14 — i.e. they think the project is at the M14 state, not the post-M16-and-M19 state they're actually installing.

**Adjacent staleness:** `README.md:125` reads `uv run aiw version   # prints 0.1.0` inside the **Contributing / from source** code block. With `__version__ = "0.3.0"`, this comment is two minor versions stale. PyPI consumers who follow the README into a clone will see a literal "prints 0.1.0" comment; the actual output prints "0.3.0".

**Why these slipped:** the M16 close-out (commit `5fcd8a2 post-0.2.0 docs cleanup`) didn't touch the README Status table; M19 T07 (the doc-pass milestone task) didn't either, because T07's scope was the Extending section + Security notes. The Status table is the one piece of README content nobody owns at task-level; the close-out task is the natural owner.

**Action / Recommendation:** at T08 close-out's pre-publish doc pass, edit `README.md` two places:

1. **Status table** — append three rows to the table at `README.md:9-24` so it reads through M19:

```markdown
| **M14 — MCP HTTP transport** | Complete (2026-04-22) |
| **M15 — Tier overlay + fallback chains** | Planned |
| **M16 — External workflows + primitives load path** | Complete (2026-04-24) |
| M17 — `scaffold_workflow` meta-workflow | Planned |
| **M19 — Declarative authoring surface** | Complete (2026-04-26) |
```

(The bold-on-Complete pattern is the existing convention; M10/M12/M15/M17 stay non-bold because they're Planned.)

2. **Stale version comment** — `README.md:125`: replace `uv run aiw version   # prints 0.1.0` with `uv run aiw version   # prints the current __version__ (0.3.0 at M19 close)` (or the simpler `# prints the current __version__`, leaving no version literal to drift).

This is mechanical and within T08 scope — same surface as the §Security notes / §Setup restoration the Builder did for CARRY-SEC-HIGH-1 / CARRY-SEC-ADV-1. Both fixes ship in the same `uv build` rebuild; SHA256 will roll one tick.

### MEDIUM-2 — AC-5 partial: `main` CHANGELOG block not landed; spec is ambiguous on Builder-vs-user split

**The drift.** AC-5 reads "CHANGELOG promoted on **both branches** per Deliverable 4. `design_branch` gets the audit-trail-inclusive M19 release section; `main` gets the user-facing `[0.3.0]` block with Added / Changed / Fixed / Deprecated sub-sections." The Builder did the design_branch portion (verified at `CHANGELOG.md:10-115`) but explicitly did not touch the main-branch CHANGELOG. The Builder's report frames this as "the user's publish ceremony per AC-9".

**The ambiguity.** The spec's §Release block at the milestone README (line 250) says the ritual is "edit code + tests on `design_branch` → commit → cherry-pick code/tests/pyproject to `main` → add user-facing docs/README/CHANGELOG on `main` → ... `uv build` + `uv publish` ...". So the main-side CHANGELOG block lands as part of the cherry-pick + main-side polish step, *before* `uv publish`. AC-9 is specifically the *post-publish* `### Published` footer stamping (wheel SHA256 + PyPI URL + live-smoke confirmation), which is a different surface from the AC-5 user-facing block.

So AC-5 has two halves: design_branch promote (Builder-owned, done) and main-branch user-facing block (also Builder-owned per the ritual, *not* done — Builder deferred to user publish ceremony). AC-9 is the post-publish stamp on whatever main-side block already exists.

**Why this matters.** If the user runs `uv publish` from `design_branch` without first cherry-picking to main + adding the main-branch CHANGELOG block, the publish-side commit graph diverges from the main release branch convention (M14 + M16 both landed their main-side CHANGELOG block before `uv publish`). The 0.3.0 wheel itself is unaffected (the wheel's METADATA embeds `README.md`, not CHANGELOG); the consequence is a main-branch CHANGELOG that lacks the `[0.3.0]` section until the user backfills it.

**Action / Recommendation:** Builder should land the main-branch CHANGELOG block as part of T08 cycle 2 (after HIGH-1 + MEDIUM-1 close), per the spec ritual. The shape per Deliverable 4 §"main CHANGELOG.md" is:

```markdown
## [0.3.0] - 2026-04-26

### Added
- Declarative authoring surface (`WorkflowSpec` + `Step` taxonomy + `register_workflow`).
- `docs/writing-a-custom-step.md` (Tier 3 dedicated guide) + `compile_step_in_isolation` testing fixture.

### Changed
- `RunWorkflowOutput.artifact` is the canonical artefact field (renamed from `plan`).
- `docs/writing-a-workflow.md` rewritten declarative-first.
- `architecture.md` extended with §"Extension model".
- `README.md` "Extending ai-workflows" section.

### Fixed
- `_dispatch.py` artefact-field bug — non-`plan` `FINAL_STATE_KEY` workflows now round-trip their artefact correctly.

### Deprecated
- `RunWorkflowOutput.plan` / `ResumeRunOutput.plan` field aliases. Removal target: 1.0.
```

The `main` cherry-pick + this CHANGELOG block + the README updates from MEDIUM-1 land together as the main-side polish commit. Then the user runs `uv build` + `uv publish` from main; on publish-confirmation, the user stamps the `### Published` footer (AC-9).

If the established pattern explicitly defers main-side work to the user (the M14 / M16 release-runbook sequence), then AC-5's "both branches" wording in the spec is the problem, not the Builder's behaviour. **Single recommendation:** treat AC-5 as Builder-owned-on-design-branch + user-owned-on-main. Update the spec text on `task_08_milestone_closeout.md` to explicitly split — design_branch promote at T08 Builder; main-branch promote at the user's cherry-pick + publish step. This aligns the AC with the established release ritual and removes the ambiguity for future close-outs.

## 🟢 LOW — flag-only

### LOW-1 — `.env.example` ships in sdist

**The drift.** `dist/jmdl_ai_workflows-0.3.0.tar.gz` contains `jmdl_ai_workflows-0.3.0/.env.example`. The pre-publish wheel-contents gate per `.claude/agents/dependency-auditor.md` lists `.env*` as forbidden in the wheel and "still no secrets, no `.env*`" in the sdist. The CARRY-T01-HIGH-1 sdist exclude block prescribed by the spec did not include `.env*`; Builder followed the spec exactly.

**Why this is LOW (not MEDIUM):** the file is a non-secret template (the leading line reads `# .env.example — ai-workflows runtime configuration`; no real keys; clearly marked as a template). The dependency-auditor's "no `.env*`" is a defensive heuristic targeting accidental `.env` (real secrets), not `.env.example`. PyPI sdist convention for many projects ships an `.env.example`. Treating `.env.example` as in-scope-for-publish is reasonable; the catch-all glob is the issue, not the file's presence.

**Action / Recommendation:** flag-only for 0.3.0 — do not add to T08. If the user prefers absolute strictness, add `"/.env*"` to the sdist exclude block at `pyproject.toml:83-90` for 0.3.1; otherwise update the dependency-auditor agent to allow `.env.example` (template) explicitly while continuing to forbid `.env` (real). This is a forward-deferred convention question, not a 0.3.0 ship-blocker.

### LOW-2 — Tier-label table column-text divergence (cosmetic)

The three tier tables are byte-aligned on the canonical tier labels (`1 — Compose / 2 — Parameterise / 3 — Author a custom step type / 4 — Escape to LangGraph directly`) per CARRY-T07-LOW-3 — that part is clean. The third-column "When / Description" text differs by surface (each table is targeted at its surface — README's happy-path framing differs from architecture.md's normative framing differs from writing-a-custom-step.md's tier-decision framing). The carry-over scope was tier-label harmonisation, not column-text harmonisation, so this is intentional. Flag-only for forward attention if future audits surface confusion.

### LOW-3 — `(builder-only, on design branch)` annotations in T07-shipped doc cross-links

`docs/writing-a-graph-primitive.md:3,15` and `docs/writing-a-custom-step.md:324` carry the `(builder-only, on design branch)` marker on cross-links to `../design_docs/architecture.md#extension-model-extensibility-is-a-first-class-capability`. Given `design_docs/` does not ship to `main` (M13 T05 branch split) and is excluded from the sdist (CARRY-T01-HIGH-1), these cross-links are only resolvable on the design_branch — the marker is correct and matches the convention used by the README `## Next` line (which is asserted by `tests/docs/test_readme_shape.py`). Flag-only — not a regression.

(The `(builder-only, on design branch)` annotations elsewhere in `docs/writing-a-workflow.md:518-519,609` carry the same correct pattern.)

## Additions beyond spec — audited and justified

The Builder's runtime-code touches all map to authorised carry-over items:

- `ai_workflows/__init__.py` `__version__` bump → release-mechanics (Deliverable 4).
- `ai_workflows/workflows/spec.py` `warnings.filterwarnings(...)` → CARRY-T01-LOW-1 (locked in spec).
- `ai_workflows/mcp/schemas.py` docstring updates → CARRY-T07-MEDIUM-1 (6 sites, all docstring-only).
- `ai_workflows/workflows/_dispatch.py` docstring updates → CARRY-T07-MEDIUM-1 (4 sites, all docstring-only or inline-comment).
- `pyproject.toml` `[tool.hatch.build.targets.sdist]` exclude block → CARRY-T01-HIGH-1 (prescribed shape).

No drive-by refactors; no nice_to_have.md adoption; no scope creep.

## Gate summary

| Gate | Command | Result |
| ---- | ------- | ------ |
| pytest | `uv run pytest` | 746 passed, 9 skipped, 22 warnings |
| lint-imports | `uv run lint-imports` | 4 contracts kept, 0 broken |
| ruff | `uv run ruff check` | All checks passed! |
| spec-API tests | `uv run pytest tests/workflows/test_summarize.py tests/integration/test_spec_api_e2e.py` | 10 passed |
| planner+slice_refactor sweep | `uv run pytest tests/workflows/ -k "planner or slice_refactor or ollama_fallback"` | 147 passed, 83 deselected |
| README/main-branch shape | `uv run pytest tests/docs/test_readme_shape.py tests/test_main_branch_shape.py tests/test_wheel_contents.py` | 9 passed, 1 skipped |
| compatibility shim probe | `uv run python -c "from ai_workflows.workflows.planner import …"` | OK |
| spec-API surface probe | `uv run python -c "from ai_workflows.workflows import (WorkflowSpec, Step, …)"` | OK |
| release_smoke.sh | `bash scripts/release_smoke.sh` | OK |
| `uv build` | `rm -rf dist && uv build` | wheel + sdist built; SHA256 d697f534…43343dd matches Builder report |
| wheel contents | `unzip -l dist/jmdl_ai_workflows-0.3.0-py3-none-any.whl` | only `ai_workflows/`, `migrations/`, dist-info — no `.env*` / `design_docs/` / `runs/` / `*.sqlite3` |
| sdist exclusion | `tar -tzf dist/jmdl_ai_workflows-0.3.0.tar.gz \| grep -E '(\.claude\|CLAUDE\|design_docs\|tests/skill\|scripts/spikes)'` | no matches |

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch | Status |
| -- | -------- | ------------------ | ------ |
| M19-T08-ISS-01 (HIGH-1) | HIGH | T08 cycle 2 — flip `task_01_workflow_spec.md:3` + `task_02_compiler.md:3` (and harmonise T03–T07 verbs) | CLOSED (cycle 2, 2026-04-26) |
| M19-T08-ISS-02 (MEDIUM-1) | MEDIUM | T08 cycle 2 — update `README.md:9-24` Status table + `README.md:125` stale version comment | CLOSED (cycle 2, 2026-04-26) |
| M19-T08-ISS-03 (MEDIUM-2) | MEDIUM | T08 cycle 2 — land main-branch `## [0.3.0] - 2026-04-26` CHANGELOG block per Deliverable 4 §"main CHANGELOG.md"; update spec to explicitly split design-vs-main ownership | CLOSED (cycle 2, 2026-04-26) |
| M19-T08-ISS-04 (LOW-1) | LOW | Forward — re-evaluate sdist `.env*` glob policy at 0.3.1 | DEFERRED (no owner; 0.3.x convention question) |
| M19-T08-ISS-05 (LOW-2) | LOW | Forward — flag-only; no action | INFORMATIONAL |
| M19-T08-ISS-06 (LOW-3) | LOW | Forward — flag-only; convention is correct | INFORMATIONAL |

## Deferred to nice_to_have

None. The findings above are close-out hygiene; none map to deferred-parking-lot items.

## Propagation status

No new forward-deferrals filed by this audit. All findings are T08-cycle-2-actionable; the LOW items are flag-only. The `nice_to_have.md §23` entry that M19 took (T07's slice_refactor-shape-patterns parking) is unchanged.

## Cycle 2 audit (2026-04-26)

**Verdict:** ✅ PASS. All three locked carry-over ACs (HIGH-1, MEDIUM-1, MEDIUM-2) land cleanly. All cycle-1 PASS ACs verified non-regressed. Wheel SHA256 matches Builder claim byte-for-byte (`f7af3962075167aac3400ad2f81bee6a7a7efaf9c07fbcbfdc55370023b28f31`); milestone README Outcome wheel-SHA line was updated to match. Gates all green; release_smoke.sh OK; no design-drift introduced by cycle-2 edits.

### Cycle 2 carry-over AC grading

| Cycle-2 AC | Status | Verification |
| ---------- | ------ | ------------ |
| **HIGH-1** — Status surface drift on T01 + T02 spec lines (AC-12 violation) | ✅ RESOLVED | All 8 task spec **Status:** lines now read `✅ Complete (2026-04-26).` byte-identical: `task_01_workflow_spec.md:3`, `task_02_compiler.md:3`, `task_03_result_shape.md:3`, `task_04_summarize_proof_point.md:3`, `task_05_writing_workflow_rewrite.md:3`, `task_06_writing_custom_step.md:3`, `task_07_extension_model_propagation.md:3`, `task_08_milestone_closeout.md:3`. T03's stale "Awaiting audit" tail dropped; "Done"/"Implemented" verb-drift eliminated. The lone `📝 Planned` mention that remains is at `task_08_milestone_closeout.md:18` inside Deliverable 1's instructional text ("Flip **Status** from `📝 Planned` to `✅ Complete (YYYY-MM-DD)`") which is the canonical close-out instruction and not a status surface. Four-surface alignment now clean: per-task spec status lines (8/8 ✅) + milestone README task-table rows (8/8 ✅) + milestone README Status line (✅) + Exit-criteria item 17 (status surfaces flipped together) all aligned. |
| **MEDIUM-1** — README.md Status table stale + `# prints 0.1.0` comment | ✅ RESOLVED | `README.md:9-28` Status table now includes M15 (`Planned`, non-bold), M16 (`**M16 — External workflows + primitives load path** \| Complete (2026-04-24)`, bold), M17 (`Planned`, non-bold), M19 (`**M19 — Declarative authoring surface** \| Complete (2026-04-26)`, bold). Bold-on-Complete pattern preserved. `README.md:129` updated to `uv run aiw version   # prints the current __version__ (0.3.0 at M19 close)` (matches the auditor's exact recommendation from cycle 1). Sole remaining `0.1.0` reference at `README.md:23` is the **M13 — v0.1.0 release** milestone name itself, which is a load-bearing historical reference, not stale; correctly left in place. No `0.2.0` references in the README at all (stale or otherwise). |
| **MEDIUM-2** — Main-branch CHANGELOG `[0.3.0]` block not landed + AC-5 ambiguous on Builder/user split | ✅ RESOLVED | `CHANGELOG.md` structure verified: line 8 `## [Unreleased]` (empty, retained for post-0.3.0 work) → line 10 `## [0.3.0] - 2026-04-26` (user-facing block) → line 28 `## [M19 Declarative Authoring Surface — 0.3.0 release] - 2026-04-26` (design-trail block). The `[0.3.0]` block has all four prescribed sub-sections: `### Added` (declarative authoring surface + step taxonomy + register_workflow + custom-step extension hook), `### Changed` (artefact-field rename + plan-deprecation alias + writing-a-workflow.md rewrite + architecture.md §"Extension model" + README.md "Extending ai-workflows"), `### Fixed` (`_dispatch.py` artefact-field bug), `### Deprecated` (RunWorkflowOutput.plan / ResumeRunOutput.plan, removal target 1.0). Block lives on `design_branch`, ready for cherry-pick to `main` during publish ceremony. T08 spec AC-5 wording at `task_08_milestone_closeout.md:192` now explicitly documents the design-branch-owns-both / main-cherry-pick-during-publish split, eliminating the ambiguity for future close-outs: *"`design_branch` carries **both** blocks: the user-facing `## [0.3.0] - YYYY-MM-DD` block ... placed **above** the audit-trail-inclusive `## [M19 Declarative Authoring Surface — 0.3.0 release] - YYYY-MM-DD` section. The `## [0.3.0]` block is cherry-picked to `main` during the user's publish ceremony; the M19 design-trail section is `design_branch`-only."* AC-9 (post-publish `### Published` footer stamping) explicitly remains the user's step. |

### Cycle-1 PASS ACs — re-verified non-regressed

Re-ran every cycle-1 PASS AC's verification path against the cycle-2 working tree:

| AC | Status | Re-verification notes |
| -- | ------ | --------------------- |
| AC-1 | ✅ still passing | Milestone README `**Status:** ✅ Complete (2026-04-26).` retained (line 3); Outcome section + Propagation status + Decision-resolution all intact. Wheel SHA256 line updated from cycle-1 `d697f534…43343dd` to cycle-2 `f7af3962075167aac3400ad2f81bee6a7a7efaf9c07fbcbfdc55370023b28f31` with explanatory parenthetical (line 222). |
| AC-2 | ✅ still passing | `roadmap.md` M19 row + summary unchanged (cycle 2 did not touch this file beyond the Builder-reported edits — diff shows 6 lines changed in roadmap.md, all consistent with the cycle-1 landed shape). |
| AC-3 | ✅ still passing | All gates re-run from scratch this audit: `uv run pytest` → 746 passed, 9 skipped, 22 warnings (matches Builder report); `uv run lint-imports` → 4 contracts kept, 0 broken; `uv run ruff check` → All checks passed!; `bash scripts/release_smoke.sh` → OK (built `jmdl_ai_workflows-0.3.0-py3-none-any.whl`, fresh-venv install, `aiw --help` + `aiw-mcp --help` + `aiw list-runs` all succeeded). |
| AC-4 | ✅ still passing | `ai_workflows/__init__.py:33` → `__version__ = "0.3.0"`. Inspected wheel: `unzip -p dist/jmdl_ai_workflows-0.3.0-py3-none-any.whl ai_workflows/__init__.py \| grep ^__version__` → `__version__ = "0.3.0"`. `uv run aiw version` → `0.3.0`. |
| AC-5 | ✅ now passing (was ⚠️ partial in cycle 1) | Per the cycle-2 MEDIUM-2 row above. The cycle-1 ⚠️ was driven by "main-branch block not landed" — the cycle-2 resolution lands the user-facing block on `design_branch` (canonical source) with explicit AC-5 wording naming the cherry-pick handoff to `main`. Both halves now have a clear owner. |
| AC-6 | ✅ still passing (with one nuance) | Re-built `dist/` from scratch: wheel SHA256 = `f7af3962075167aac3400ad2f81bee6a7a7efaf9c07fbcbfdc55370023b28f31` (matches Builder claim byte-for-byte and matches the milestone README Outcome line 222). Wheel contents: only `ai_workflows/`, `migrations/`, dist-info — no `.env*`, no `design_docs/`, no `runs/`, no `*.sqlite3`, no `.claude/`. Sdist contents: `tar -tzf dist/jmdl_ai_workflows-0.3.0.tar.gz \| grep -E '(\.claude\|CLAUDE\|design_docs\|tests/skill\|scripts/spikes)'` → no matches. (LOW-1 from cycle 1 — `.env.example` shipping in sdist — is unchanged and remains flag-only, not a regression.) The SHA changed from cycle-1 `d697f534…43343dd` to cycle-2 `f7af3962…3b28f31` because the cycle-2 README + CHANGELOG edits are embedded into the wheel's METADATA + CHANGELOG.md package files; rolling the SHA on doc changes is expected. |
| AC-7 / AC-8 / AC-9 / AC-10 | 🔵 user-step (unchanged) | Publish-side steps remain user-owned per the spec. |
| AC-11 | ✅ still passing | Project memory file unchanged; reflects post-0.3.0 / M19-shipped state. |
| AC-12 | ✅ now passing (was ❌ in cycle 1) | All four status surfaces aligned per the cycle-2 HIGH-1 row above. |
| AC-13 | ✅ still passing | All T01–T07 issue files closed clean. |
| AC-14 | ✅ still passing | No drive-by source-code changes in cycle 2. The cycle-2 diff under `ai_workflows/` is empty (the version bump + warnings.filterwarnings + docstring-only edits are all cycle-1 absorption that cycle 2 did not re-touch). The eight cycle-2 changes (8 task spec status flips + 1 README + 1 CHANGELOG + 1 task_08 spec AC-5 wording + 1 milestone README wheel-SHA update) are all doc-prose only. |
| AC-15 | ✅ still passing | The cycle-2 carry-over absorption is the canonical pathway for cycle-1 findings; no new findings forked off into separate milestones / nice_to_have. |

### Mandatory drift-check (cycle 2 doc-prose-only)

Re-ran the seven-KDR drift scan + four-layer rule scan despite cycle-2 being doc-prose-only — required for audit-trail completeness per `.claude/agents/auditor.md` Phase 1.

- **KDR-002 (MCP-as-substrate)** — no MCP wire-shape change in cycle 2. CHANGELOG line `### Deprecated — RunWorkflowOutput.plan / ResumeRunOutput.plan field` is documentation of the deprecation already shipped in T03; no new schema change.
- **KDR-003 (no Anthropic API)** — no change. README §Setup mention of "Claude access is OAuth-only through the CLI subprocess" is correct (this content was restored by cycle 1 per CARRY-SEC-ADV-1; cycle 2 did not touch it).
- **KDR-004 (validator pairing)** — no graph-layer change.
- **KDR-006 (three-bucket retry)** — no change.
- **KDR-008 (FastMCP + pydantic schemas)** — no schema change.
- **KDR-009 (SqliteSaver-only checkpoints)** — no change.
- **KDR-013 (user-owned external code)** — no change.
- **Four-layer rule** — `uv run lint-imports` → 4 contracts kept, 0 broken. No new imports introduced.
- **`design_docs/nice_to_have.md` adoption** — no new entry. §23 unchanged.

No drift detected.

### Cycle 2 gate summary

| Gate | Command | Result |
| ---- | ------- | ------ |
| pytest | `uv run pytest` | 746 passed, 9 skipped, 22 warnings (matches Builder claim) |
| lint-imports | `uv run lint-imports` | 4 contracts kept, 0 broken |
| ruff | `uv run ruff check` | All checks passed! |
| `uv build` | `rm -rf dist && uv build` | wheel + sdist built clean |
| wheel SHA256 | `sha256sum dist/jmdl_ai_workflows-0.3.0-py3-none-any.whl` | `f7af3962075167aac3400ad2f81bee6a7a7efaf9c07fbcbfdc55370023b28f31` (matches Builder claim + milestone README line 222) |
| wheel contents | `unzip -l dist/jmdl_ai_workflows-0.3.0-py3-none-any.whl` | only `ai_workflows/` + `migrations/` + dist-info; no `.env*`/`design_docs/`/`runs/`/`*.sqlite3`/`.claude/` |
| sdist exclusion | `tar -tzf dist/jmdl_ai_workflows-0.3.0.tar.gz \| grep -E '(\.claude\|CLAUDE\|design_docs\|tests/skill\|scripts/spikes)'` | no matches |
| release_smoke.sh | `bash scripts/release_smoke.sh` | OK (built wheel, fresh-venv install, all `aiw`/`aiw-mcp`/`aiw list-runs` smoke probes passed) |
| wheel `__version__` | `unzip -p dist/jmdl_ai_workflows-0.3.0-py3-none-any.whl ai_workflows/__init__.py \| grep ^__version__` | `__version__ = "0.3.0"` |
| local `aiw version` | `uv run aiw version` | `0.3.0` |

### Cycle 2 status — issue log update

| ID | Severity | Status (cycle 2) |
| -- | -------- | ---------------- |
| M19-T08-ISS-01 (HIGH-1, status-surface drift) | HIGH | ✅ CLOSED — verified at all 8 task spec status lines + 4 status surfaces |
| M19-T08-ISS-02 (MEDIUM-1, stale README + version comment) | MEDIUM | ✅ CLOSED — Status table extended with M15/M16/M19; `# prints 0.1.0` replaced |
| M19-T08-ISS-03 (MEDIUM-2, main CHANGELOG block + AC-5 wording) | MEDIUM | ✅ CLOSED — `[0.3.0]` block landed on design_branch above design-trail; AC-5 wording amended for design/main split |
| M19-T08-ISS-04 (LOW-1, sdist `.env.example`) | LOW | DEFERRED (unchanged — convention question for 0.3.x) |
| M19-T08-ISS-05 (LOW-2, tier-table column-text divergence) | LOW | INFORMATIONAL (unchanged — flag-only) |
| M19-T08-ISS-06 (LOW-3, `(builder-only, on design branch)` annotations) | LOW | INFORMATIONAL (unchanged — convention is correct) |

### Cycle 2 verdict

T08 is functionally + structurally clean for 0.3.0 publish. All cycle-1 carry-over absorption verified at the byte level; all cycle-2 carry-over ACs (HIGH-1 / MEDIUM-1 / MEDIUM-2) land at the prescribed file/line with the prescribed content; no regressions on cycle-1 PASS ACs; wheel SHA256 matches Builder claim and milestone README; gates all green. The status-surface alignment is now four-surface clean; the README PyPI long-description is current through M19; the main-branch CHANGELOG block is staged for cherry-pick. Remaining steps (`uv publish`, live-smoke from `/tmp`, `### Published` footer stamping, `git push origin main + design_branch`) are user-owned per the established release ritual — outside this audit's scope.

The OPEN status from cycle 1 flips to ✅ PASS. Ready to ship 0.3.0.

## Locked decisions (loop-controller + Auditor concur, 2026-04-26)

Per the auditor-agreement bypass in `.claude/commands/clean-implement.md` stop-condition 2, all three OPEN findings have a single clear auditor recommendation that the loop controller concurs with against spec + KDRs + prior locks. No scope expansion, no conflict with KDRs, no deferral to non-existent future tasks. Auto-locked into T08 cycle 2 as carry-over ACs:

- **Locked decision (HIGH-1):** Flip `task_01_workflow_spec.md:3` and `task_02_compiler.md:3` `**Status:**` lines to `✅ Complete (2026-04-26).`. Harmonise T03–T07 status-line verbs to the same canonical close-out form (T03's stale "Awaiting audit" tail dropped) while the close-out harness is open.
- **Locked decision (MEDIUM-1):** Append M15 + M16 + M19 rows to `README.md:9-24` milestone Status table; replace the stale `# prints 0.1.0` comment at `README.md:125` with the 0.3.0 reference. Both fixes ride on the same `uv build` rebuild as HIGH-1 — wheel SHA256 will roll one tick.
- **Locked decision (MEDIUM-2):** Builder lands the `main`-branch `## [0.3.0] - 2026-04-26` CHANGELOG block in T08 cycle 2 per the spec's §Release ritual (Deliverable 4 §"main CHANGELOG.md"). The block lands on `design_branch` as a stub that will be cherry-picked to `main` during the publish ceremony (since this is a doc-only task and the CHANGELOG fork is a known split point already). Update T08 spec AC-5 wording to split design-side vs. main-side ownership explicitly so future close-out tasks have an unambiguous reference. AC-9 (post-publish `### Published` footer stamping) remains the user's step.

LOW-1 / LOW-2 / LOW-3 are flag-only or informational — no action required for cycle 2.

## Security review (2026-04-26)

Threat-model scope: (1) published wheel on PyPI — wheel-contents leakage, README long-description embedded in METADATA; (2) subprocess execution — Claude Code OAuth path, Ollama HTTP path. Single-user, local-machine, MIT-licensed; generic web-app concerns not applicable.

Checked files: `ai_workflows/workflows/spec.py`, `ai_workflows/mcp/__main__.py`, `ai_workflows/mcp/schemas.py`, `ai_workflows/primitives/llm/claude_code.py`, `ai_workflows/primitives/retry.py`, `ai_workflows/primitives/storage.py`, `ai_workflows/primitives/logging.py`, `pyproject.toml`, `README.md`, `CHANGELOG.md`, `dist/jmdl_ai_workflows-0.3.0-py3-none-any.whl` (wheel SHA256 re-verified), `dist/jmdl_ai_workflows-0.3.0.tar.gz`.

### Critical — must fix before publish/ship

None.

### High — should fix before publish/ship

None.

### Advisory — track; not blocking

**ADV-1 — CHANGELOG `[0.3.0]` block missing `### Security` sub-section for the README restoration**

Threat model item: wheel contents / long-description accuracy.

The `## [0.3.0]` user-facing block at `CHANGELOG.md:10-27` has four sub-sections (Added / Changed / Fixed / Deprecated) but no `### Security` sub-section noting that `README.md §Security notes` (`### Security notes` under `## MCP server`) was restored in this release (CARRY-SEC-HIGH-1). The `### Security notes` content is substantive — it documents the `--host 0.0.0.0` bind-address foot-gun and opt-in CORS behaviour — and was absent from 0.2.0. Keep-a-Changelog §conventions list `### Security` as a standard sub-section for vulnerabilities fixed. A downstream consumer upgrading from 0.2.0 has no signal in the CHANGELOG that the security-relevant documentation was reinstated.

Action: add a `### Security` sub-section to the `## [0.3.0]` block with a single line noting the restoration. Suggested text: `- Restored \`README.md §Security notes\` documenting the \`--host 0.0.0.0\` foot-gun and opt-in CORS behaviour for \`aiw-mcp --transport http\`.` This does not block ship — the actual security posture is unchanged — but is a quality signal to downstream consumers. Low-effort one-line addition before `uv publish` if the user opts in; otherwise deferred to 0.3.1.

---

**Checked clean — no findings on the following threat-model items:**

1. **Wheel contents** — `sha256sum dist/jmdl_ai_workflows-0.3.0-py3-none-any.whl` → `f7af3962075167aac3400ad2f81bee6a7a7efaf9c07fbcbfdc55370023b28f31` (matches cycle 2 audit + milestone README). `unzip -l` confirms only `ai_workflows/`, `migrations/`, `jmdl_ai_workflows-0.3.0.dist-info/` — no `.env*`, no `design_docs/`, no `.claude/`, no `*.sqlite3`. Sdist `tar -tzf | grep -E '(\.claude|CLAUDE|design_docs|tests/skill|scripts/spikes|\.env[^.])'` → no matches. `.env.example` ships in sdist (already filed as LOW-1 in cycle 1 — flag-only; template file, no real secrets).

2. **README long-description (wheel METADATA) — no secret leakage** — `export GEMINI_API_KEY=...` in `METADATA:104` is within a fenced code-block placeholder (the `...` value). No real key values. `ANTHROPIC_API_KEY` appears only in a sentence explicitly stating `aiw` never reads it — correct and KDR-003-compliant. No `Bearer `, no `Authorization` header values, no local-path references that would expose the builder's machine.

3. **`README.md §Security notes` accuracy** — restored content at `README.md:116-119` matches the canonical 0.1.3 `b01b1ec:README.md` wording substantively. The loopback-default bullet, `--host 0.0.0.0` foot-gun, no-built-in-auth note, and reverse-proxy guidance are all present. The 0.3.0 wording correctly says `--host 0.0.0.0` (vs. the 0.1.3 wording which used `0.0.0.0` without the flag prefix in one place) — the 0.3.0 form is clearer. The CORS bullet adds "Not required for stdio or loopback HTTP" which is an improvement over 0.1.3.

4. **`README.md §Setup` env-vars — KDR-003 clean** — `README.md:84-89` lists `GEMINI_API_KEY`, `OLLAMA_BASE_URL`, `AIW_STORAGE_DB`/`AIW_CHECKPOINT_DB`. The Claude Code tier paragraph explicitly states `aiw` never reads `ANTHROPIC_API_KEY` and never imports the `anthropic` SDK. No actual key values present.

5. **`spec.py` warnings filter scope** — `ai_workflows/workflows/spec.py:66-70` uses `warnings.filterwarnings("ignore", message=r'Field name "schema" in "ValidateStep" shadows an attribute in parent "Step"', category=UserWarning)`. This is precisely targeted: both the exact warning text regex and `category=UserWarning` are required. It is not a blanket `category=UserWarning` with no message constraint, and not `category=Warning`. Future pydantic UserWarnings on other fields will pass through unaffected.

6. **`pyproject.toml` sdist exclude block** — `pyproject.toml:83-90` excludes `/.claude`, `/CLAUDE.md`, `/design_docs`, `/tests/skill`, `/scripts/spikes`. The wheel config (`[tool.hatch.build.targets.wheel] packages = ["ai_workflows"]` + `force-include "migrations"`) is preserved and unmodified. `LICENSE`, `README.md`, `CHANGELOG.md` are not excluded from the sdist (correct — they should ship). No accidental over-exclusion.

7. **MCP HTTP transport bind address** — `ai_workflows/mcp/__main__.py:74` defaults `host` to `"127.0.0.1"`. The `--host 0.0.0.0` foot-gun is documented in both the CLI help string (`line 78`) and `README.md §Security notes`. CORS is exact-match opt-in via `--cors-origin`; `_run_http` only attaches `CORSMiddleware` when `cors_origins` is non-empty (`line 161`); without the flag, no `Access-Control-Allow-Origin` header emitted.

8. **OAuth subprocess integrity (KDR-003)** — `ai_workflows/primitives/llm/claude_code.py`: argv is built as a list (no `shell=True`; `asyncio.create_subprocess_exec(*argv, ...)`); prompt is fed via `stdin` (not argv — sidesteps arg-length limits and shell-quoting); timeout is enforced via `asyncio.wait_for(proc.communicate(...), timeout=self._per_call_timeout_s)` with `proc.kill()` + `proc.wait()` on timeout (`lines 143-154`). Stderr is captured and surfaced via `subprocess.CalledProcessError(stderr=stderr_bytes)`. The `classify()` function in `ai_workflows/primitives/retry.py` extracts and logs stderr up to 2 000 chars (`_STDERR_LOG_CAP = 2_000`, `lines 58+182`). Zero `ANTHROPIC_API_KEY` references in `ai_workflows/` source — grep returns no hits.

9. **KDR-013 external workflow loader** — `ai_workflows/workflows/loader.py`: `importlib.import_module` failures are caught as `Exception` and re-raised as `ExternalWorkflowImportError(dotted, exc)` preserving the failing path and cause (`lines 123-125`). No swallowed tracebacks. In-package workflow pre-import guard runs before externals (existing behaviour, not changed by T08).

10. **SQLite paths** — `default_storage_path()` resolves to `~/.ai-workflows/storage.sqlite` (user-owned dir). `AIW_STORAGE_DB` / `AIW_CHECKPOINT_DB` env-var overrides are accepted and passed through `Path(env_override).expanduser()` — no normalisation guard against `../` traversal, but this is a single-user local tool where the user owns the env; out of threat-model scope. All `storage.py` `execute(...)` calls use `?` placeholder parameterisation — no raw `f"...{value}..."` interpolation against `execute` found.

11. **Logging hygiene** — `ai_workflows/primitives/logging.py` emits `run_id`, `workflow`, `node`, `tier`, `provider`, `model`, `duration_ms`, `input_tokens`, `output_tokens`, `cost_usd` per record. No API key, no Bearer token, no `prompt=` / `messages=` values logged at INFO or WARNING levels. DEBUG-level logging described in the docstring as "full LLM I/O" — this is an advisory at most; DEBUG is opt-in and expected to contain prompt text (it is labelled as such in the docstring).

12. **Dependency CVEs** — dependency-auditor running in parallel per the task brief; deferred to that agent. No new dependencies added in T08.

13. **`mcp/schemas.py` wire-shape stability (KDR-008)** — `git diff 01ceb9b HEAD -- ai_workflows/mcp/schemas.py` confirms: only docstring and `Field(description=...)` text changed in T08-scope files; `RunWorkflowOutput` and `ResumeRunOutput` have the `artifact` field added and `plan` preserved as a `deprecated=True` alias. Note: the `artifact` + `plan` field additions to both output models are M19 T03 changes (not T08), but verified here against the 0.2.0 commit (`01ceb9b`). Both `plan` (original) and `artifact` (new) are present — backward-compatible additive change. The T08-specific diff is docstring-only, as claimed.

### Verdict: SHIP

All seven threat-model items checked. Wheel SHA256 confirmed byte-for-byte. No secrets in METADATA. No `shell=True` subprocess. Timeout enforced via `asyncio.wait_for` with `proc.kill()`. CORS exact-match opt-in. Bind default is loopback. KDR-003 clean (zero `ANTHROPIC_API_KEY` in source). One Advisory (missing `### Security` CHANGELOG sub-section for the README restoration) — non-blocking; the security posture itself is correct and the `§Security notes` content is live in the README. Ready to publish 0.3.0.

## Dependency audit (2026-04-26)

### Manifest changes audited

- `pyproject.toml`: sole change from `01ceb9b` is the addition of the `[tool.hatch.build.targets.sdist] exclude = [...]` block (lines 76-90). No version pins changed. No new `[project.dependencies]` entries. No deps removed. `dynamic = ["version"]` preserved. No `anthropic` package anywhere in deps or dev-deps (KDR-003 clean).
- `uv.lock`: zero diff against `01ceb9b` — `git diff 01ceb9b -- uv.lock` produces no output. Lockfile was not regenerated or touched by the T08 cycle 1+2 implementation. Lockfile integrity confirmed: no drift.

### Wheel contents

- whl: clean — `unzip -l dist/jmdl_ai_workflows-0.3.0-py3-none-any.whl` lists 56 files. Contains only: `ai_workflows/` (44 source files), `migrations/` (6 SQL files), `jmdl_ai_workflows-0.3.0.dist-info/` (METADATA, WHEEL, entry_points.txt, RECORD, licenses/LICENSE). No `.env*`, no `design_docs/`, no `runs/`, no `*.sqlite3`, no `tests/`, no `evals/`, no `.claude/`, no `CLAUDE.md`, no `scripts/`. Wheel SHA256 `f7af3962075167aac3400ad2f81bee6a7a7efaf9c07fbcbfdc55370023b28f31` confirmed byte-for-byte against the pre-built artefact and the cycle 2 audit claim.
- sdist: clean on the five prescribed exclusions — `tar -tzf dist/jmdl_ai_workflows-0.3.0.tar.gz | grep -E '(\.claude|CLAUDE|design_docs|tests/skill|scripts/spikes)'` returns no matches, confirming the `[tool.hatch.build.targets.sdist] exclude` block works as intended. Sdist ships: `ai_workflows/`, `migrations/`, `tests/` (hermetic; no skill tests), `docs/`, `evals/` (fixture JSONs + .gitkeep only), `scripts/release_smoke.sh`, `pyproject.toml`, `uv.lock`, `CHANGELOG.md`, `README.md`, `LICENSE`, `.env.example`, `.gitignore`, `.python-version`, `pricing.yaml`, `tiers.yaml`, `.github/` (CONTRIBUTING.md + ci.yml), `PKG-INFO`. The `.env.example` present is a non-secret template (all values are either empty or commented-out; no real keys); carries forward as LOW-1 advisory from cycle 1 (flag-only; deferred to 0.3.x convention question).

### Reproducibility

Wheel SHA256 `f7af3962075167aac3400ad2f81bee6a7a7efaf9c07fbcbfdc55370023b28f31` matches the pre-built artefact at `dist/jmdl_ai_workflows-0.3.0-py3-none-any.whl` byte-for-byte. No divergence.

### migrations/ shipping — intentionality verified

The wheel force-includes `migrations/` via `[tool.hatch.build.targets.wheel.force-include] "migrations" = "migrations"` per `pyproject.toml:102-103` (M13 Task 01 reasoning documented in the inline comment at lines 92-103). The six SQL files are storage-layer schema DDL only: `001_initial.sql` (runs/tasks/llm_calls/artifacts/human_gate_states schema), `002_reconciliation.sql` (trims post-pivot tables per KDR-009), `003_artifacts.sql` (JSON-payload artifacts per M3 Task 03). No secrets, no embedded absolute paths, no references to developer machine layout, no network fetches. All rollback companions present. Intentional and clean.

### PyPI long-description (README.md in METADATA)

`dist-info/METADATA` embeds `README.md` as the long-description. The `export GEMINI_API_KEY=...` line in the README code block uses `...` as the placeholder value — no real key. `ANTHROPIC_API_KEY` appears only in the sentence explicitly stating `aiw` never reads it (KDR-003-compliant). No local paths (`/home/`, `~/prj/`), no machine names, no bearer tokens, no `Authorization` header values found by grep scan. The §Security notes (restored by CARRY-SEC-HIGH-1) and §Setup (restored by CARRY-SEC-ADV-1) sections are substantively correct and contain no secrets.

### CVE / supply-chain scan

`uv tool run pip-audit` against the project's locked deps: **No known vulnerabilities found.** Output: "No known vulnerabilities found" with no High or Critical entries. Key packages scanned: `langgraph 1.1.8`, `langgraph-checkpoint-sqlite 3.0.3`, `litellm 1.83.0`, `fastmcp 3.2.4`, `httpx 0.28.1`, `pydantic 2.13.2`, `python-dotenv 1.2.2`, `pyyaml 6.0.3`, `structlog 25.5.0`, `typer 0.24.1`, `yoyo-migrations 9.0.0`.

KDR-003 supply-chain check: `uv pip show anthropic` → "warning: Package(s) not found for: anthropic" — the Anthropic SDK is not installed in the project environment. Zero `anthropic` in `[project.dependencies]` or `[dependency-groups.dev]`. Clean.

### 🔴 Critical — must fix before publish

None.

### 🟠 High — should fix before publish

None.

### 🟡 Advisory — track; not blocking

**DEP-ADV-1 — sdist ships `scripts/release_smoke.sh`**

`scripts/release_smoke.sh` is present in the sdist (not excluded by the `[tool.hatch.build.targets.sdist] exclude` block, which only covers `scripts/spikes/`). The file is a developer release-gate script, not a runtime or test asset. It does not contain secrets (uses env-var references: `GEMINI_API_KEY=...`, `AIW_E2E=1`); it does not ship in the wheel. The sdist latitude permits developer tooling for downstream packagers, and the script's presence is not a security concern. If the policy intent is "only `scripts/spikes/` is excluded and the rest of `scripts/` is intentionally in-sdist," this is clean. If the intent is "no developer tooling in sdist," add `"/scripts"` or `"/scripts/release_smoke.sh"` to the sdist exclude block at `pyproject.toml:83-90`. Flag-only; not a 0.3.0 blocker.

**DEP-ADV-2 — sdist ships `evals/` fixtures (JSON + .gitkeep)**

The sdist includes `evals/planner/explorer/happy-path-01.json`, `evals/planner/planner/happy-path-01.json`, `evals/slice_refactor/slice_worker/happy-path-01.json`, and `evals/.gitkeep`. These are eval fixture captures (no secrets; JSON LLM-response snapshots). They do not ship in the wheel. Shipping them in the sdist allows downstream packagers to run the eval suite, which is reasonable. No action required; informational.

**DEP-ADV-3 — sdist ships `.github/` (CI workflow + CONTRIBUTING.md)**

`jmdl_ai_workflows-0.3.0/.github/CONTRIBUTING.md` and `.github/workflows/ci.yml` ship in the sdist. The CI workflow references `secrets.GEMINI_API_KEY` as a GitHub Actions secret reference (not a real value). No real API keys present. Common for Python sdists to include CI config; not a security concern. Informational only.

### Verdict: SHIP

No new deps, no CVEs, no lockfile drift, wheel contents clean, SHA256 confirmed, migrations are SQL-only with no secrets, README long-description contains no leaked secrets or paths. The sdist exclusion block introduced by CARRY-T01-HIGH-1 works correctly. Three Advisory items noted above (release_smoke.sh, evals fixtures, .github/ in sdist) are informational — none are secrets, none ship in the wheel, none block 0.3.0 publish.
