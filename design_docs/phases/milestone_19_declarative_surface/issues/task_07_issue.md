# Task 07 — Four-tier framing across `architecture.md`, `README.md`, `writing-a-graph-primitive.md` + KDR table updates + Q5 deferral re-open trigger — Audit Issues

**Source task:** [../task_07_extension_model_propagation.md](../task_07_extension_model_propagation.md)
**Audited on:** 2026-04-26 (cycle 1) · 2026-04-26 (cycle 2 — propagation re-audit)
**Audit scope (cycle 1):** `design_docs/architecture.md` (new §"Extension model" subsection between §7 and §8 + §9 KDR-004/KDR-013 row updates), `README.md` (new "## Extending ai-workflows" section above "## MCP server" + scrub of stale `(builder-only, on design branch)` annotations), `docs/writing-a-graph-primitive.md` (audience-clarification banner + Tier 3 → graph-layer graduation framing + cross-link to `architecture.md §Extension model` + scrub of stale annotations), `docs/writing-a-custom-step.md` (back-link to `architecture.md §Extension model` per T06-LOW-1 carry-over), `design_docs/nice_to_have.md` (new §23 "Spec API extensions for slice_refactor-shape patterns" entry), `CHANGELOG.md` (`### Changed — M19 Task 07` block under `[Unreleased]`), milestone README task table row 07, T07 spec status surface + AC checkboxes + carry-over checkbox. Cross-referenced against ADR-0008 (§Extension model + §Documentation surface — the propagation requirements this task lands), the four-layer rule, the seven load-bearing KDRs, the predecessor T01–T06 issue files (T03 MEDIUM-1 Path A propagation, T03 LOW-3 docstring drift, T05 ADV-SEC-1 design-branch annotation, T06 LOW-1 cross-link absorption). All three gates re-run from scratch (`uv run pytest`, `uv run lint-imports`, `uv run ruff check`). Smoke commands from spec Deliverable 6 re-run from scratch.
**Audit scope (cycle 2):** Propagation-only re-audit. Verified the new `## Carry-over from M19 T07 audit (2026-04-26)` subsection on `task_08_milestone_closeout.md` absorbs all 4 cycle-1 OPEN findings (CARRY-T07-MEDIUM-1 + CARRY-T07-LOW-1 + CARRY-T07-LOW-2 + CARRY-T07-LOW-3) per user-locked option 2; verified T07 cycle 1 deliverables remain intact (no source code or doc surface changes in cycle 2); CHANGELOG entry honest. All three gates re-run from scratch.

**Status:** ✅ PASS (cycle 2 — 2026-04-26). HIGH=0; MEDIUM=0 (cycle-1 MEDIUM-1 RESOLVED-DEFERRED-TO-T08); LOW=0 OPEN (cycle-1 LOW-1/2/3/4 all RESOLVED-DEFERRED-TO-T08). Propagation closed: T08 spec carries the four-item carry-over with concrete actionable references to every load-bearing site cycle-1 named (`schemas.py:91, 178, 183-184`; `_dispatch.py:729, 994, 999, 1093`; `architecture.md:106`; the 3 wrong anchor slugs; the 3 divergent tier tables). T07 cycle 1 deliverables verified intact (architecture.md §Extension model, README.md §Extending ai-workflows, writing-a-graph-primitive.md audience banner, writing-a-custom-step.md back-link, nice_to_have.md §23 entry — all unchanged). Gates: pytest 746 passed / 9 skipped / 24 pre-existing deprecation warnings; lint-imports 4 contracts kept / 0 broken; ruff all checks passed.

**Cycle 1 status (preserved for history):** ⚠️ OPEN (cycle 1 — 2026-04-26). HIGH=0; MEDIUM=1; LOW=4. The MEDIUM is a forward-deferred propagation gap from T03 cycle 2 LOW-3 (class-level docstring prose drift in `mcp/schemas.py` + `_dispatch.py`) that T03 explicitly named T07 as the natural absorption point; T07's spec carry-over did not include it; Builder did not address it because spec didn't list it. The auditor flags it for user direction (re-defer to T07 cycle 2 vs. defer to T08 vs. close as cosmetic). LOWs are: (1) §Extension model section length below spec target (~50–80 lines → shipped 19 lines); (2) anchor slug in Tier 4 cross-links is computed wrong (`#extension-model----extensibility-is-a-first-class-capability` vs. GFM-rendered `#extension-model-extensibility-is-a-first-class-capability`); (3) tier-name capitalization/wording inconsistency across the three tier tables; (4) stale §4.4 line in `architecture.md` referencing `RunWorkflowOutput.plan` / "in-flight draft plan" framing — flagged by T03 cycle 1 audit for T07 absorption; not addressed.

## Design-drift check

**No drift detected.** T07 is doc-only (no code changes). Verified against the seven load-bearing KDRs and the four-layer rule:

| Drift category | Verdict | Evidence |
|---|---|---|
| New dependency | None — no `pyproject.toml` / `uv.lock` changes. | `git diff --stat HEAD` shows only doc + spec/README + CHANGELOG touches. |
| New module / layer / boundary crossing | None — doc-only. `lint-imports` 4 contracts kept, 0 broken (109 dependencies, unchanged). | `uv run lint-imports` re-run from scratch. |
| LLM call added (KDR-004) | None — KDR-004 row updated in `architecture.md §9` to reflect the M19 spec API construction-invariant graduation; ADR-0008 source reference appended. No behavioural change. | `architecture.md:280` shows the appended text + ADR-0008 cite. |
| Checkpoint / resume logic (KDR-009) | None. | No code touched. |
| Retry logic (KDR-006) | None. | No code touched. |
| Observability | None. | No code touched. |
| External workflow loading (KDR-013) | KDR-013 row updated to reflect the M19 boundary shift (specs are *data*; custom step types remain *code*); ADR-0008 source reference appended. Faithful to ADR-0008 §Extension model. | `architecture.md:288` shows the appended text + ADR-0008 cite. |
| Workflow tier names | Unchanged. | `architecture.md §Extension model` does not introduce new tier names. |
| MCP tool surface (KDR-008) | Unchanged — four shipped tools unchanged. | No `mcp/server.py` or `mcp/schemas.py` changes. |
| ADR-0008 §Documentation surface compliance | Partial — see LOW-1 (~50–80 lines target shipped at 19 lines) and AC-9 manual read-through (terminology consistency caveats — see LOW-3 below). All five surfaces are touched as ADR-0008 §Documentation surface table prescribes. | `architecture.md` + `README.md` + `writing-a-graph-primitive.md` + `writing-a-custom-step.md` + `nice_to_have.md` all updated. |

The §Extension model placement (between §7 and §8 — the Builder's choice of three options the spec offered) is sound: it sits next to §7 "Boundaries and contracts" (the contract surface) and before §8 "Cross-cutting concerns" (the operational surface). The four-tier model is conceptually a contract surface, not a cross-cutting one. No disruption to prior cross-references.

## AC grading

| AC | Status | Notes |
|---|---|---|
| AC-1 — `architecture.md §"Extension model"` subsection (~50–80 lines) with framing + tier table + out-of-scope + graduation + ADR-0008 ref | ⚠️ MET-WITH-CAVEAT | All five required structural elements present (framing paragraph at line 170; tier table 4 rows at lines 172–177; out-of-scope paragraph at line 179; graduation paragraph at line 181; ADR-0008 reference at line 185). **However, length is 19 lines vs. the spec-prescribed "~50–80 lines"** — see LOW-1. The shipped section is dense but structurally complete. AC-1 graded MET because every required element is present and identifiable; the length-target deviation is captured as LOW-1 separately. |
| AC-2 — `architecture.md §9` KDR-004 + KDR-013 rows updated; source column adds ADR-0008 | ✅ MET | KDR-004 row at line 280 has the M19 construction-invariant paragraph appended; source column reads `· [ADR-0008](adr/0008_declarative_authoring_surface.md)`. KDR-013 row at line 288 has the boundary-shift paragraph appended; source column reads `· [ADR-0008](adr/0008_declarative_authoring_surface.md)`. Both rows preserve the original text in front. Verified by direct `Read` of `architecture.md`. |
| AC-3 — No new KDR added | ✅ MET | KDR table grid runs KDR-001 → KDR-013 (KDR-012 was dropped pre-shipping; not introduced by T07). No new row added. ADR-0008 is composed under existing KDRs per the ADR's own §Decision. |
| AC-4 — `README.md §"Extending ai-workflows"` above `## MCP server`; framing + tier table; every link resolves | ✅ MET | Section header at `README.md:76`; placed above `## MCP server` at line 89 (verified by section ordering grep). Framing paragraph at line 78 includes "ai-workflows is a declarative orchestration layer; extension is a first-class capability." Tier table has 4 rows with `When` + `Guide` columns; all four guide links resolve to existing files (`docs/writing-a-workflow.md`, `docs/writing-a-custom-step.md`, `docs/writing-a-graph-primitive.md`). Closing line at 87 includes "The framework's promise: descending a tier never forces you to reverse-engineer framework source." Verbatim match to spec Deliverable 3. |
| AC-5 — `writing-a-graph-primitive.md` audience-clarification banner | ✅ MET | Banner at line 3 begins `> **Audience:** This guide is for **framework contributors** authoring new graph-layer primitives — not for downstream consumers.` Cross-links to `writing-a-workflow.md` (Tier 1+2) + `writing-a-custom-step.md` (Tier 3) + reference to `architecture.md §Extension model`. Spec Deliverable 4 verbatim text matched. |
| AC-6 — Tier 3 → graph-layer graduation path framing + cross-link to `architecture.md §Extension model` | ⚠️ MET-WITH-CAVEAT | "Tier 3 → graph-layer graduation path" framing landed as the lead paragraph in §When to write a new graph primitive (line 11). Cross-link to `architecture.md §Extension model` added at lines 3 + 15. Existing 2+ workflows heuristic preserved at line 13. **However, the anchor slug used in the cross-links is wrong** — see LOW-2. AC-6's explicit text only requires the cross-link to be added; the anchor-correctness defect is a downstream link-resolution issue. AC graded MET because the link IS added; LOW-2 captures the anchor mis-computation. |
| AC-7 — Cross-references audited; stale `(builder-only, on design branch)` annotations on main-tree items scrubbed | ⚠️ MET-WITH-CAVEAT | Confirmed by direct diff inspection: scrubs in `README.md` line 86 (`(builder-only, on design branch)` annotation removed from the HTTP transport line) + line 112 (`design branch` → `design_branch` adjustment, marker removed); and in `docs/writing-a-graph-primitive.md` lines 4, 92, 107 (3 stale annotations on items now in the main tree scrubbed). Single remaining `(builder-only, on design branch)` annotation in README is on the `design_docs/roadmap.md` link (line 126) — correct per the `tests/docs/test_readme_shape.py` invariant requiring the marker on the sole `design_docs/` reference. **However, in `docs/writing-a-graph-primitive.md` lines 3 + 15, the new cross-link to `architecture.md §Extension model` carries the marker — but the link is to `../design_docs/architecture.md`, which IS a builder-only target per the M13 T03 test, so the marker is correctly present.** Scrubbing scope honored. |
| AC-8 — Smoke verification passes; every referenced file exists | ✅ MET | All six smoke commands re-run from scratch; outputs reproduce spec expectations: `grep -n "^## .*Extension model"` returns line 168; `grep -n "M19 spec API\|ADR-0008"` returns lines 185, 280, 288; `grep -n "^## Extending ai-workflows"` returns line 76 of README; `grep -n "Audience:"` returns line 3 of writing-a-graph-primitive.md; all 6 file-existence probes return `OK`. |
| AC-9 — Manual read-through confirms four-tier framing consistent across all surfaces | ⚠️ MET-WITH-CAVEAT | The four-tier numbering (1/2/3/4) is consistent across all four surfaces (architecture.md, README.md, writing-a-graph-primitive.md, writing-a-custom-step.md). Step-type names (`LLMStep`, `ValidateStep`, `GateStep`, `TransformStep`, `FanOutStep`) are consistent. "Extensibility is a first-class capability" framing present in architecture.md + README.md (verbatim from spec) + ADR-0008 §Extension model. **Tier-name capitalization/wording diverges across surfaces** — see LOW-3. The divergence is cosmetic but real: architecture.md uses `1 — Compose / 2 — Parameterise / 3 — Author a custom step type / 4 — Escape to LangGraph directly`; README uses `**1. Compose** / **2. Parameterise** / **3. Author a custom step type** / **4. Escape to LangGraph directly**`; writing-a-custom-step.md (T06-shipped) uses `Tier 1 — compose / Tier 2 — parameterise / Tier 3 — custom step / Tier 4 — escape hatch` (lowercase + abbreviated). AC graded MET because the Tier *numbers* and *step-type* names are consistent; the *display labels* drift is captured as LOW-3. |
| AC-10 — Existing content unchanged outside the new sections / row updates | ✅ MET | `git diff HEAD -- design_docs/architecture.md` confirms changes scoped exactly to (a) new §Extension model insertion between line 167 ←→ §8 (line 187), and (b) KDR-004 row at 280 + KDR-013 row at 288. No other architecture.md content modified. `git diff HEAD -- README.md` confirms (a) new §Extending insertion between Getting started and §MCP server, and (b) two scrub edits per AC-7 (line 86 HTTP-transport caveat + line 112 design-branch wording). `git diff HEAD -- docs/writing-a-graph-primitive.md` confirms audience banner + lead paragraph + cross-link + 3 scrub edits — content otherwise untouched. |
| AC-11 — `nice_to_have.md` §23 entry; slot recorded in issue; re-open trigger matches spec verbatim | ✅ MET | Entry exists at `nice_to_have.md:537–553` under `## 23. Spec API extensions for slice_refactor-shape patterns`. Slot §23 confirmed as next-free at audit time (the file's current numbering is 1–7, 9–22, then 23 — §8 is a pre-existing legacy gap not introduced by T07). Status line at 539: "Deferred at M19 (2026-04-26) per ADR-0008 + M19 README §Decisions Q5." Re-open trigger language at line 551 matches spec Deliverable 5 verbatim ("When a **second** external workflow ... wants to use the spec API"). "What does NOT trigger a re-open" framing at line 553. `gate_review_payload_field` candidate at line 547 (per T03 MEDIUM-1 Path A carry-over). All five "What this would extend" bullets present + the gate_review_payload_field 6th bullet. **Slot drift verified clean:** §23 was the next-free slot at Q5 lock per M19 README §Decisions Q1, and it remains §23 at T07 implement time (no other tasks took it between 2026-04-26 lock and 2026-04-26 implement — same day). |
| AC-12 — Gates green | ✅ MET | All three gates re-run from scratch and verified independently of the Builder report. `uv run pytest`: 746 passed, 9 skipped, 24 warnings (24 = pre-existing `result.plan` deprecation warnings on the M19 T03 alias; not new). `uv run lint-imports`: 4 contracts kept, 0 broken (109 dependencies analyzed, unchanged from T06 cycle 1). `uv run ruff check`: All checks passed. **Gate integrity verdict:** all Builder-claimed pass/fail outcomes verified independently. No gate the Builder reported passing now fails. |
| AC-13 — CHANGELOG entry under `[Unreleased]` per Deliverable 7 | ✅ MET | `### Changed — M19 Task 07: four-tier extension model propagated across architecture + README + primitive doc + nice_to_have re-open trigger (2026-04-26)` block at `CHANGELOG.md:10–58` under `[Unreleased]`. Keep-a-Changelog vocabulary (`### Changed`). KDR citations (KDR-004 + KDR-013) at line 57. Each touched file enumerated; carry-over ACs satisfied (T03-MEDIUM-1 Path A + T06-ISS-LOW-1 + M18-R1/R2) explicitly cited at lines 49–53. |

### Carry-over AC grading

| Carry-over | Status | Notes |
|---|---|---|
| M19-T06-ISS-LOW-1 — Add `architecture.md §Extension model` back-link to `docs/writing-a-custom-step.md` | ⚠️ MET-WITH-CAVEAT | Back-link added at line 324 of `docs/writing-a-custom-step.md` in §Pointers to adjacent tiers (the natural placement the carry-over named). Builder marker `(builder-only, on design branch)` correctly applied per `tests/docs/test_docs_links.py` invariant for `../design_docs/` links. **However, the anchor in the link uses the same wrong slug as the writing-a-graph-primitive.md cross-links** — `#extension-model----extensibility-is-a-first-class-capability` (4 hyphens) vs. the GFM-rendered `#extension-model-extensibility-is-a-first-class-capability` (1 hyphen between every word, em-dash dropped). The carry-over text also said `#extension-model` literally — neither the abbreviated nor the verbose form is what GFM will actually render. See LOW-2 for the full anchor analysis. Carry-over checkbox correctly flipped to `[x]` in T07 spec. |

## 🔴 HIGH

*None.* The four-tier extension framing is propagated across architecture + README + primitive doc + custom-step doc + nice_to_have. Every spec Deliverable lands. Gates green. KDRs preserved. ADR-0008 §Documentation surface table satisfied at the structural level. No KDR drift.

## 🟡 MEDIUM

### MEDIUM-1 — T03 cycle 2 LOW-3 (class-level docstring prose drift) flagged for T07 absorption; T07 spec carry-over did not include it; Builder did not address it

**Where:** `ai_workflows/mcp/schemas.py:91, 178, 183-184`; `ai_workflows/workflows/_dispatch.py:729, 994, 999, 1093` — class-level + function-level docstring prose still references "in-flight draft" / "re-gated draft" / "last-draft artefact" / "in-flight draft plan" framing from M11 T01.

**What.** T03 cycle 2 audit (`task_03_issue.md:167–184`) explicitly named T07's documentation pass as the natural absorption point for this prose drift:

> Action / Recommendation. Absorb into T07's documentation pass (existing carry-over already covers the documentation surface; extending it to source-tree docstrings is a one-line addition). Specifically, when T07 updates `architecture.md §"Extension model"` to note that gate-pause projection follows `FINAL_STATE_KEY`, also touch up `mcp/schemas.py:91, 178, 183-184` + `_dispatch.py:729` class/function docstring prose to align with the same framing.

T07's spec `## Carry-over from prior audits` section only contains M19-T06-ISS-LOW-1 — the T03 LOW-3 absorption was not propagated to T07's spec. Builder strictly followed the T07 spec as written; this is a propagation gap upstream, not a Builder failure. The T07 spec's `## Carry-over from prior milestones` line 202 covers T03 MEDIUM-1 Path A (the architecture.md gate-pause projection note + the nice_to_have.md `gate_review_payload_field` candidate — both addressed by Builder), but does NOT cover T03 LOW-3 (the source-tree docstring prose).

**Why MEDIUM not HIGH.** The MCP wire-surface contract (field descriptions surfaced via `model_json_schema()`) was already corrected in T03 cycle 2 LOW-1 fix. The class-level docstring prose is reader-facing internal documentation, not surfaced over the wire. The drift is honest-but-incomplete: "carries the in-flight draft" is true *when* the workflow's `FINAL_STATE_KEY` channel is populated by an upstream node before the gate fires; it's stale for `slice_refactor` whose `FINAL_STATE_KEY = "applied_artifact_count"` is `None` at gate time. Internal docstring drift only — not a contract issue. But T03 LOW-3 was OPEN at T07 implement time and explicitly named T07 as the natural absorption point.

**Why not LOW.** The T03 audit explicitly recommended T07 absorption, the propagation channel (carry-over section) failed, and the issue persists across two task close-outs without resolution. The auditor's role is to surface the propagation gap rather than silently roll it forward.

**Companion item — `architecture.md §4.4` line 106 stale framing.** T03 cycle 1 audit (`task_03_issue.md:54`) flagged the same drift in the architecture.md §4.4 M11 T01 line: *"`RunWorkflowOutput.plan` / `ResumeRunOutput.plan` carry the in-flight draft plan at `status='pending', awaiting='gate'`"*. T03's own framing: *"T07 ('Four-tier framing across architecture.md') is the natural owner for the rename update; the semantic-weakening is a separate concern (see MEDIUM-1). The spec explicitly defers docs to T05/T07, so doc drift here is **not** a T03 finding — flagged for T07's audit."* Same propagation gap: T07 spec did not include this as carry-over; Builder did not touch line 106 (and AC-10 says architecture.md content unchanged outside §"Extension model" + §9 KDR rows — so Builder honored the spec strictly). Combine into the same MEDIUM-1 finding because the root cause is identical (T03 forward-deferred to T07; T07 spec did not absorb).

**Action / Recommendation.** **Stop and ask the user.** Three options:

1. **Re-defer to T07 cycle 2** — extend the spec's `## Carry-over from prior audits` section with both items (T03 LOW-3 docstring prose + T03 cycle 1 §4.4 line drift), spawn a Builder cycle 2 to land both touches, then re-audit. Cleanest but loops T07.
2. **Re-defer to T08** — fold both items into T08's milestone close-out scope (which already touches `architecture.md §4.4` minor cleanup territory). Defers the work to the release task.
3. **Close as cosmetic** — accept that the prose drift is internal-only and non-load-bearing now that LOW-1 fixed the wire-surface descriptions. Update T03's issue file LOW-3 status from OPEN to RESOLVED-WONTFIX.

The auditor recommends option (2) — T08 is already a ceremony task touching the full surface for release; folding two one-line cleanup edits into it is the smallest scope. The work is mechanical (search-and-replace on "in-flight draft"/"re-gated draft"/"last-draft artefact" with `FINAL_STATE_KEY`-following framing). Per the auditor protocol's "If the fix is unclear (two reasonable options, crosses milestones, needs spec change) — stop and ask the user before finalising," this MEDIUM is paused on user direction.

**Owner (proposed):** M19 T08 — milestone close-out + 0.3.0 publish ceremony. Carry-over text to add to T08 spec if user concurs:

> **M19-T03-LOW-3 + T03-cycle-1 §4.4 doc-drift residue — class-level + function-level docstring prose carrying M11 T01 framing** (severity: LOW-aggregate-promoted-to-MEDIUM-on-second-deferral, source: [M19 T03 issue file](issues/task_03_issue.md) + [M19 T07 issue file](issues/task_07_issue.md))
> When closing M19 + cutting 0.3.0, do a mechanical doc-prose cleanup pass: in `ai_workflows/mcp/schemas.py:91, 178, 183-184` + `ai_workflows/workflows/_dispatch.py:729, 994, 999, 1093` + `design_docs/architecture.md:106` (the §4.4 gate-review-projection bullet), update class-level + function-level docstring prose so it reads as "follows `FINAL_STATE_KEY`; may be `None` at gate-pause for workflows whose `FINAL_STATE_KEY` channel is empty pre-gate" rather than the M11 T01 "in-flight draft" / "re-gated draft" / "last-draft artefact" framing. Composes with the architecture.md §"Extension model" framing T07 already shipped (the gate-pause projection note at lines 183 of architecture.md). One-line touches; no behaviour change; verify gates green after each touch.

## 🟢 LOW

### LOW-1 — `architecture.md §"Extension model"` shipped at 19 lines vs. spec-prescribed "~50–80 lines / ~one page"

**Where:** `design_docs/architecture.md:168–186` (the new §Extension model subsection).

**What.** Spec Deliverable 1 explicitly states: *"Insert a new top-level subsection (~one page, ~50–80 lines of markdown) that captures the four-tier extension model as part of the architecture-of-record."* AC-1 reiterates: *"`design_docs/architecture.md` has a new §"Extension model" subsection (~50–80 lines)."* ADR-0008 §Documentation surface (line 140) reiterates: *"New §"Extension model" subsection (~one page)."*

The shipped section is 19 lines (verified by `awk`/`sed` line-count from heading to the next `## 8.` boundary). All five required structural elements are present (framing paragraph, tier table, out-of-scope paragraph, graduation paragraph, gate-pause projection note + ADR-0008 reference). The Builder report also mentions "~35 lines" — even the Builder's own count is below spec target.

**Why LOW not MEDIUM.** Structural completeness is met (every required element present and identifiable). The "~50–80 lines" is a guidance target, not a hard contract — the spec's "**~** one page" framing acknowledges the imprecision. Density vs. length is a tradeoff; the shipped section is dense but functional. Reading it end-to-end, the four-tier model is conveyed clearly. No content is missing.

That said: the spec target of "~50–80 lines / ~one page" was load-bearing per ADR-0008 §Documentation surface ("Extensibility-as-a-core-capability is only credible if the docs meet authors wherever they enter") and reiterated three separate times across spec + ADR + AC. The shipped section is materially below that target.

**Action / Recommendation.** Optional T07 cycle 2 polish — expand the §Extension model section closer to the spec target by adding:

1. **One worked-example sketch per tier** (~5 lines each) — e.g., "Tier 1: a workflow author writes `register_workflow(WorkflowSpec(name='summarize', ..., steps=[LLMStep(...)]))` — they never `import langgraph`. Tier 2: ... Tier 3: ... Tier 4: ..."
2. **Cross-references to specific KDRs** (~2–3 lines) — e.g., "Tier 1's `LLMStep.response_format` requirement enforces KDR-004 by construction; Tier 3's `Step.execute()` runs in-process per KDR-013."
3. **Brief framing of the `summarize` workflow as the spec-API proof point** (~2 lines) — the in-tree workflow exemplifying Tier 1 + Tier 2.

Total expansion ~25–30 lines, taking the section to ~50 lines (lower bound of the spec target). Alternatively: defer the expansion to T08 and accept the dense-but-complete intermediate state. **Owner:** T07 (cycle 2 optional polish) or T08 (milestone close-out doc pass). **Not propagated** — narrowly-scoped to T07's own deliverable. Asked of user as part of MEDIUM-1's resolution path.

### LOW-2 — Cross-link anchor slugs to `architecture.md §Extension model` are computed wrong

**Where:**
- `docs/writing-a-graph-primitive.md:3` (audience banner)
- `docs/writing-a-graph-primitive.md:15` (lead paragraph in §When to write a new graph primitive)
- `docs/writing-a-custom-step.md:324` (Pointers to adjacent tiers — T06-LOW-1 absorption)

**What.** All three cross-links use the anchor `#extension-model----extensibility-is-a-first-class-capability` (4 consecutive hyphens). The actual GitHub-Flavoured-Markdown slug for the heading `## Extension model — extensibility is a first-class capability` is `#extension-model-extensibility-is-a-first-class-capability` (1 hyphen between every word, em-dash dropped). Verified via Python regex matching GFM's slug rules: `re.sub(r'[^\w\s-]', '', heading.lower())` then `re.sub(r'\s+', '-', ...)` → em-dash is non-word/non-space/non-hyphen and is removed; consecutive spaces collapsed to single hyphens.

The T06-LOW-1 carry-over text on T07 spec named the anchor as `#extension-model` (literal, abbreviated). Neither the abbreviated nor the verbose-with-4-hyphens form will navigate correctly on GitHub's renderer.

**Why LOW.** The link still resolves at the file-existence level (`tests/docs/test_docs_links.py` only file-checks, not anchor-checks; anchor validation is `nice_to_have` per the link checker docstring). Renders on GitHub as a working file link, just lands at the top of the file rather than at the §Extension model section. Cosmetic / navigation concern.

The cross-link still composes the four-tier framing (the doc tells readers "see the §Extension model" and the link works at file level); only the in-page jump is broken. A reader following the link lands at line 1 of architecture.md and scrolls; they find §Extension model without major friction.

**Action / Recommendation.** Replace the three anchors with the GFM-rendered slug:

```diff
-#extension-model----extensibility-is-a-first-class-capability
+#extension-model-extensibility-is-a-first-class-capability
```

Three one-line edits across two files. Mechanical search-and-replace; safe to land at next-touch (T07 cycle 2 if MEDIUM-1 triggers a re-cycle; or T08 close-out doc pass; or directly via fix-forward on the `design_branch`). **Not propagated** — narrowly-scoped to T07's own deliverables. **Owner:** This task (cycle 2 if any other work surfaces) or T08.

### LOW-3 — Tier-name capitalization/wording inconsistency across the three tier tables

**Where:**
- `design_docs/architecture.md:174–177` (the new §Extension model tier table)
- `README.md:82–85` (the new §Extending ai-workflows tier table)
- `docs/writing-a-custom-step.md:12–15` (T06-shipped tier-decision table)

**What.** The four-tier framing displays differently across the three tables:

| Surface | Tier 1 label | Tier 2 label | Tier 3 label | Tier 4 label |
|---|---|---|---|---|
| architecture.md | `1 — Compose` | `2 — Parameterise` | `3 — Author a custom step type` | `4 — Escape to LangGraph directly` |
| README.md | `**1. Compose**` | `**2. Parameterise**` | `**3. Author a custom step type**` | `**4. Escape to LangGraph directly**` |
| writing-a-custom-step.md | `Tier 1 — compose` | `Tier 2 — parameterise` | `**Tier 3 — custom step**` | `Tier 4 — escape hatch` |

Tier numbers are consistent (1/2/3/4 throughout); step-type names (`LLMStep`, etc.) are consistent. But:

- Tier-label format diverges (`1 — Compose` vs. `**1. Compose**` vs. `Tier 1 — compose`).
- Tier-3 label diverges (`Author a custom step type` vs. `**Author a custom step type**` vs. `**custom step**` (T06-shipped, abbreviated)).
- Tier-4 label diverges (`Escape to LangGraph directly` vs. `**Escape to LangGraph directly**` vs. `escape hatch` (T06-shipped, abbreviated)).
- Capitalization of the verb/noun varies (`Compose` vs. `compose`; `Parameterise` vs. `parameterise`).

**Why LOW.** The semantic mapping is unambiguous (any reader can match `Tier 3 — custom step` to `Tier 3 — Author a custom step type` to `**3. Author a custom step type**`). Tier numbers are the load-bearing identifier; labels are descriptive shorthand. T06's table predates T07 and shipped first; T07's spec did not require synchronizing T06's table to a canonical form. ADR-0008's own §Extension model section (line 80–127) uses yet a fourth label form (`Tier 1 — Compose existing step types`).

The drift becomes meaningful only if a reader cross-references three tables side-by-side and notices the inconsistency — for the typical "I'm at the wrong tier; click the link to the right one" navigation, the consistency is sufficient.

**Action / Recommendation.** Pick one canonical form and align the three tables. Recommended canonical form: architecture.md's `1 — Compose / 2 — Parameterise / 3 — Author a custom step type / 4 — Escape to LangGraph directly` (no bold; em-dash separator; full label). Update README.md (drop the `**` bold + `.`-separator; harmonize) and writing-a-custom-step.md (capitalize + lengthen the labels).

**Or** — accept the diversity as functional (each surface has its own tone: README is a user-facing pitch, architecture.md is contract-of-record, writing-a-custom-step.md is a Tier-3-author guide), document the three forms as "load-bearing variation" in a one-line note in each surface, and close LOW-3 as WONTFIX.

**Owner:** T07 cycle 2 (if MEDIUM-1 triggers a re-cycle) or T08 close-out doc pass. **Not propagated** — narrowly-scoped to the M19 documentation surface; can be folded into the same touch as LOW-1 / LOW-2 / MEDIUM-1.

### LOW-4 — `architecture.md §4.4` line 106 stale `RunWorkflowOutput.plan` / "in-flight draft plan" framing

**Where:** `design_docs/architecture.md:106` — the §4.4 MCP server gate-review projection bullet.

**What.** Line 106 reads:

> *(Gate-review projection, M11) — `RunWorkflowOutput.plan` / `ResumeRunOutput.plan` carry the in-flight draft plan at `status="pending", awaiting="gate"`, not only on `status="completed"`. Closes the M9 T04 live-smoke finding that an operator at a HumanGate had nothing to review. No new tool; surface shape unchanged.*

This line is stale on three counts:
1. Field rename `plan` → `artifact` (M19 T03) — line should say `RunWorkflowOutput.artifact` / `ResumeRunOutput.artifact`.
2. "In-flight draft plan" framing weakened post-T03 — for workflows whose `FINAL_STATE_KEY` channel is empty at gate time (e.g., `slice_refactor`'s `applied_artifact_count`), the value is `None`, not the in-flight draft (per locked Path A).
3. The new `architecture.md §Extension model` gate-pause projection note (line 183) IS the corrected framing; the §4.4 bullet now contradicts the §Extension model bullet.

T03 cycle 1 audit explicitly flagged this for T07's audit (see `task_03_issue.md:54`). The Builder did not address it because (a) T07 spec carry-over did not include it, and (b) AC-10 explicitly states "Existing content in `architecture.md` unchanged outside §"Extension model" + §9 KDR rows" — the Builder strictly honored the AC.

**Why LOW.** The §Extension model gate-pause projection note (line 183) IS the corrected framing and is now the authoritative source. The §4.4 line is a pre-existing stale bullet that contradicts it but does not actively mislead (a reader navigating to architecture.md sees both bullets; the §Extension model framing is more recent and load-bearing). Surface-level conflict, not contract conflict.

**Why not part of MEDIUM-1.** Combined with MEDIUM-1 above. LOW-4 is the architecture.md flavor of the same propagation gap (T03 forward-deferred to T07; T07 spec did not absorb). Captured as separate LOW for traceability — the resolution is the same as MEDIUM-1's resolution path (re-defer to T07 cycle 2 / T08 / close as cosmetic).

**Action / Recommendation.** Same as MEDIUM-1's resolution path. If user picks option (1) re-defer to T07 cycle 2: extend AC-10's exemption list to include "§4.4 gate-review-projection bullet rename `plan` → `artifact`" + the prose alignment. If option (2) defer to T08: fold into the same close-out cleanup pass. If option (3) close as cosmetic: update T03's issue file accordingly. **Owner:** Same as MEDIUM-1.

## Additions beyond spec — audited and justified

| Addition | Justification | Verdict |
|---|---|---|
| Gate-pause projection note in `architecture.md §Extension model` (line 183) | Spec Deliverable 1 + T07 spec line 202 (the carry-over from T03 MEDIUM-1 Path A) explicitly required this. Builder shipped it per the carry-over. Composes with the §Extension model section's framing (the projection note is one of five required structural elements). | ✅ Justified — required by carry-over, not addition-beyond-spec |
| `gate_review_payload_field` knob candidate as bullet 6 of `nice_to_have.md §23` | Spec Deliverable 5 referenced "the explicit re-open trigger from M19 §Decisions Q5"; T07 spec line 202 (T03 MEDIUM-1 Path A carry-over) added "if a downstream consumer files a request for configurable gate-pause projection, ... `gate_review_payload_field` knob on `WorkflowSpec` or equivalent." Builder shipped this as the 6th bullet. Composes with the existing 5 bullets the spec listed. | ✅ Justified — required by carry-over |
| Single-surface scrub of `(builder-only, on design branch)` annotations from `README.md:86, 112` and `writing-a-graph-primitive.md` (3 sites) | Spec AC-7 explicitly required this. Total 5 scrubs (2 in README + 3 in primitive doc) match the Builder's claim. | ✅ Justified — required by AC-7 |
| Back-link added to `docs/writing-a-custom-step.md` line 324 (in §Pointers to adjacent tiers) | T07 spec `## Carry-over from prior audits` (M19-T06-ISS-LOW-1) explicitly required this. Builder shipped exactly the back-link the carry-over specified, in the natural placement the carry-over named. | ✅ Justified — required by carry-over |
| §Extension model placement between §7 and §8 (one of three options the spec listed) | Spec Deliverable 1 explicitly authorised this placement. Composes cleanly: §Extension model sits next to §7 "Boundaries and contracts" (the contract surface) and before §8 "Cross-cutting concerns" (the operational surface). The four-tier model is a contract surface. | ✅ Justified — Builder choice within spec-authorised options |

No additions beyond spec that introduce coupling / scope creep / `nice_to_have.md` adoption. No invented direction.

## Gate summary

| Gate | Command | Result |
|---|---|---|
| Pytest | `uv run pytest` | ✅ 746 passed, 9 skipped, 24 warnings (24 = pre-existing `result.plan` deprecation warnings on M19 T03 alias; not new) |
| Layer rule | `uv run lint-imports` | ✅ 4 contracts kept, 0 broken (109 dependencies; unchanged from T06 cycle 1) |
| Ruff | `uv run ruff check` | ✅ All checks passed |
| Spec smoke 1 — Extension model heading present | `grep -n "^## .*Extension model\|^### .*Extension model" design_docs/architecture.md` | ✅ returns line 168 |
| Spec smoke 2 — KDR rows updated | `grep -n "M19 spec API\|ADR-0008" design_docs/architecture.md` | ✅ returns lines 185, 280, 288 |
| Spec smoke 3 — README extending section | `grep -n "^## Extending ai-workflows" README.md` | ✅ returns line 76 |
| Spec smoke 4 — primitive doc audience banner | `grep -n "Audience:" docs/writing-a-graph-primitive.md` | ✅ returns line 3 |
| Spec smoke 5 — Tier 3 graduation framing | `grep -n "Tier 3 → graph-layer graduation" docs/writing-a-graph-primitive.md` | ✅ returns line 11 |
| Spec smoke 6 — file existence loop | `for path in design_docs/architecture.md README.md docs/writing-a-workflow.md docs/writing-a-custom-step.md docs/writing-a-graph-primitive.md design_docs/adr/0008_declarative_authoring_surface.md; do test -f "$path"; done` | ✅ all 6 paths exist |
| Doc cross-link checker | `uv run pytest tests/docs/test_docs_links.py -v` | ✅ 3 passed |
| Doc snippet/structure tests | `uv run pytest tests/docs/ -v` | ✅ 48 passed |
| README shape tests (line cap + design_docs marker) | implicit in `uv run pytest` | ✅ 3 passed (README is 126 lines / cap 150; one `design_docs/` reference with marker) |
| Slot drift verification — §23 free at T07 implement time | `grep -n "^## " design_docs/nice_to_have.md` | ✅ §22 → §23 (next-free); no taken slot competing |
| GFM anchor slug computation (LOW-2 evidence) | Python `re` simulation of GFM slug rules | ❌ Cross-link anchors miscomputed — captured as LOW-2 |
| §Extension model section line count (LOW-1 evidence) | `awk '/^## Extension model/,/^## 8\./' \| wc -l` | ⚠️ 19 lines vs. spec target ~50–80 — captured as LOW-1 |

**Gate integrity verdict:** All Builder-claimed pass/fail outcomes verified independently. No gate the Builder reported passing now fails. The Builder's section-count claim (~35 lines) is also off — actual count is 19 lines. Captured as a Builder-report-discrepancy note within LOW-1.

## Status-surface integrity

| Surface | Required state | Actual state | Verdict |
|---|---|---|---|
| Per-task spec `**Status:**` line | ✅ Implemented (2026-04-26) | ✅ Implemented (2026-04-26) | ✅ |
| Milestone README task table row 07 | ✅ Implemented (2026-04-26) | ✅ Implemented (2026-04-26) | ✅ |
| `tasks/README.md` row | n/a (file does not exist for M19) | n/a | ✅ |
| Milestone README "Done when" / Exit criteria items 9 + 10 + 11 + 12 (T07's deliverables) | Items 9–12 are numbered Exit criteria, not `[ ]`/`[x]` checkboxes — text describes T07's deliverables; all four now satisfied by the Builder's diff | text correctly corresponds to landed behaviour | ✅ |
| AC-1 through AC-13 checkboxes in spec | AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-10, AC-11, AC-12, AC-13 marked `[x]`; AC-9 `[ ]` (Auditor's responsibility per spec) | matches | ✅ |
| Carry-over checkbox (M19-T06-ISS-LOW-1) | `[x]` — flipped by Builder | matches | ✅ |

All surfaces flipped correctly. AC-9 left unchecked is correct per spec ("Manual read-through (Auditor's responsibility)") — the Auditor grades AC-9 in this issue file (graded MET-WITH-CAVEAT above; LOW-3 captures the tier-name capitalization drift).

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch point | Status |
|---|---|---|---|
| M19-T07-ISS-MEDIUM-1 | MEDIUM | T08 (CARRY-T07-MEDIUM-1) | RESOLVED-DEFERRED-TO-T08 2026-04-26 (cycle 2). User locked option 2; T08 spec `## Carry-over from M19 T07 audit (2026-04-26)` absorbs the work with all 6 load-bearing site references intact (schemas.py:91/178/183-184; _dispatch.py:729/994/999/1093; architecture.md:106). Will flip to RESOLVED (commit sha) when T08's release-ceremony doc pass closes the carry-over. |
| M19-T07-ISS-LOW-1 | LOW | T08 (CARRY-T07-LOW-1) | RESOLVED-DEFERRED-TO-T08 2026-04-26 (cycle 2). User-bundled with MEDIUM-1 per locked option 2. T08 carry-over names the recommended ~25-30 line expansion target + the optional-polish framing. |
| M19-T07-ISS-LOW-2 | LOW | T08 (CARRY-T07-LOW-2) | RESOLVED-DEFERRED-TO-T08 2026-04-26 (cycle 2). User-bundled with MEDIUM-1 per locked option 2. T08 carry-over names the 3 sites + the GFM-rendered slug to swap in. |
| M19-T07-ISS-LOW-3 | LOW | T08 (CARRY-T07-LOW-3) | RESOLVED-DEFERRED-TO-T08 2026-04-26 (cycle 2). User-bundled with MEDIUM-1 per locked option 2. T08 carry-over names the 3 tier-table sites + the recommended canonical format (architecture.md's `1 — Compose / 2 — Parameterise / 3 — Author a custom step type / 4 — Escape to LangGraph directly`). |
| M19-T07-ISS-LOW-4 | LOW | T08 (folded into CARRY-T07-MEDIUM-1) | RESOLVED-DEFERRED-TO-T08 2026-04-26 (cycle 2). LOW-4 is the architecture.md flavour of the same M11 T01 prose-drift propagation gap as MEDIUM-1; T08 carry-over CARRY-T07-MEDIUM-1 explicitly names `architecture.md:106` among its 6 sites, so the LOW-4 work composes with the MEDIUM-1 fix. |

## Deferred to nice_to_have

*None directly from this audit.* `gate_review_payload_field` knob already captured as bullet 6 of `nice_to_have.md §23` (per T03 MEDIUM-1 Path A carry-over Builder absorbed). No new parking-lot candidates surfaced.

## Propagation status

### Cycle 1 (2026-04-26)

- **M19-T07-ISS-MEDIUM-1 + M19-T07-ISS-LOW-4 (combined) → user direction needed.** The auditor recommends T08 (milestone close-out + 0.3.0 publish) as the natural absorption point — T08 already touches the full architecture / docs surface for release ceremony, and the work is mechanical doc-prose cleanup. **Not propagated yet** — pending user choice between (1) re-defer to T07 cycle 2, (2) defer to T08, (3) close as cosmetic. Per auditor protocol "If the fix is unclear (two reasonable options, crosses milestones, needs spec change) — stop and ask the user before finalising." Auditor has surfaced the gap; user picks the resolution path.

- **M19-T06-ISS-LOW-1 (T06 carry-over absorbed by T07) → RESOLVED at T07.** Back-link added to `docs/writing-a-custom-step.md:324` per the T06 issue file's spec. Anchor slug computed wrong (LOW-2 above) but the file-level link resolves and the carry-over checkbox correctly flipped.

- **T03 MEDIUM-1 Path A (gate-pause projection note + `gate_review_payload_field` candidate) → RESOLVED at T07.** Architecture.md §Extension model line 183 has the projection note; nice_to_have.md §23 has the `gate_review_payload_field` candidate (bullet 6). Both deliverables landed.

- **M18 R1 + R2 (cross-reference rot scrubs in main-tree items) → RESOLVED at T07.** 5 stale `(builder-only, on design branch)` annotations scrubbed (2 in README, 3 in writing-a-graph-primitive.md). Verified by direct diff inspection.

### Cycle-1 close-out summary

T07 cycle 1 lands the four-tier framing across architecture.md + README.md + writing-a-graph-primitive.md + writing-a-custom-step.md + nice_to_have.md per spec Deliverables 1–7. AC-1 through AC-13 all met or met-with-caveat. Three predecessor carry-overs (T06-LOW-1, T03 MEDIUM-1, M18 R1/R2) correctly absorbed. Two predecessor forward-deferrals (T03 LOW-3 docstring prose drift + T03 cycle-1 §4.4 doc drift) NOT absorbed because T07 spec carry-over did not include them — surfaced as MEDIUM-1 / LOW-4 for user direction. Issue file flips to **`⚠️ OPEN`**: HIGH=0, MEDIUM=1 (pending user direction on resolution path), LOW=4 (all narrowly scoped to T07's documentation surface; can be folded into the same touch as MEDIUM-1 resolution).

The MEDIUM-1 + LOW-4 finding is structurally important because it represents a propagation gap that has now persisted across two task close-outs (T03 cycle 2 → T07). The auditor's role is to surface this rather than silently let it roll forward to a third deferral; left unaddressed, the M11 T01 prose drift becomes the kind of doc gap ADR-0008 §Documentation surface explicitly warns against ("a doc gap at any tier is a regression on the framework's value proposition").

LOW-1 (section length below spec target) and LOW-3 (tier-label drift across surfaces) are independent of the propagation gap — they are surface-quality issues on T07's own deliverables. LOW-2 (anchor slug computation) is a mechanical defect with a one-line fix.

If the user selects option (2) defer to T08 for MEDIUM-1 + LOW-4, the auditor will:
- Append a carry-over entry to T08's spec naming `M19-T07-ISS-MEDIUM-1` + `M19-T07-ISS-LOW-4` with the recommended doc-prose cleanup edits enumerated.
- Update this issue file's Propagation status section to confirm T08 carry-over landed.
- Flip this issue file from `⚠️ OPEN` to `✅ PASS` (the LOWs are non-blocking polish that can also fold into T08).

Awaiting user direction.

### Cycle 2 (2026-04-26 — propagation re-audit)

User locked option 2 (defer to T08) for MEDIUM-1 + bundled LOW-1 / LOW-2 / LOW-3 into the same T08 carry-over. Builder cycle 2 was scoped to a single propagation edit + the CHANGELOG entry documenting it. Re-audit verifies:

- **CARRY-T07-MEDIUM-1 → propagated to T08.** `task_08_milestone_closeout.md:255-263` carries `CARRY-T07-MEDIUM-1` with all 6 load-bearing sites named verbatim (`mcp/schemas.py:91`; `mcp/schemas.py:178, 183-184`; `_dispatch.py:729, 994, 999, 1093`; `architecture.md:106`) plus the concrete search-and-replace pattern (M11 T01 framing → post-T03 honest framing keyed on `FINAL_STATE_KEY` projection). Composes with the T07-shipped §"Extension model" gate-pause projection note. Folds in M19-T07-ISS-LOW-4 (the architecture.md:106 site is explicitly listed) — no separate LOW-4 line needed; LOW-4's resolution is structurally the same edit. **Status flipped: RESOLVED-DEFERRED-TO-T08 2026-04-26.**

- **CARRY-T07-LOW-1 → propagated to T08.** `task_08_milestone_closeout.md:265-267` carries `CARRY-T07-LOW-1` with the file path + line range (~19 lines current → ~50 lines lower-bound spec target via ~25-30 line expansion) + the optional-polish framing the cycle-1 audit recommended. **Status flipped: RESOLVED-DEFERRED-TO-T08 2026-04-26.**

- **CARRY-T07-LOW-2 → propagated to T08.** `task_08_milestone_closeout.md:269-276` carries `CARRY-T07-LOW-2` with all 3 sites named (`writing-a-graph-primitive.md:3`, `:15`; `writing-a-custom-step.md:324`) plus the wrong-slug → GFM-correct-slug swap-in (`#extension-model----extensibility-is-a-first-class-capability` → `#extension-model-extensibility-is-a-first-class-capability`). **Status flipped: RESOLVED-DEFERRED-TO-T08 2026-04-26.**

- **CARRY-T07-LOW-3 → propagated to T08.** `task_08_milestone_closeout.md:278-285` carries `CARRY-T07-LOW-3` with all 3 tier-table sites named (`architecture.md:174-177`; `README.md:82-85`; `writing-a-custom-step.md:12-15`) plus the recommended canonical format (architecture.md's no-bold em-dash full-label form). **Status flipped: RESOLVED-DEFERRED-TO-T08 2026-04-26.**

### Cycle-2 close-out summary

Cycle 2 was scoped to a single propagation edit + a CHANGELOG entry. Builder honoured the scope strictly:

- **Files modified (cycle-2-scope):** `task_08_milestone_closeout.md` (new T07 carry-over subsection at lines 251-285 — 4 items per cycle-1 prescriptions); `CHANGELOG.md` (new `### Added — M19 Task 07 cycle 2` block at lines 10-21 under `[Unreleased]`, honest framing — claims only that propagation landed, does NOT claim the docstring drift was fixed).
- **Files NOT modified in cycle 2 (verified by `git diff HEAD --stat`):** `ai_workflows/` (zero source-code change); `docs/` (the cycle-1 deliverables remain unchanged from their cycle-1 state); `architecture.md` / `README.md` / `nice_to_have.md` / milestone README (only cycle-1 deliverables remain). Confirmed by spot-check of `## Extension model` heading at architecture.md:168, `## Extending ai-workflows` at README.md:76, `Audience:` banner at writing-a-graph-primitive.md:3, `## 23.` at nice_to_have.md:537 — all intact from cycle 1.
- **Structural-shape match.** The new `## Carry-over from M19 T07 audit (2026-04-26)` subsection mirrors the existing `## Carry-over from M19 T01 audit (2026-04-26)` subsection's shape: heading + intro paragraph + 4 unchecked checkboxes (one per item) + bold ID + structured action / source / sites / replacement-pattern bullets per item. T08 close-out absorbs both T01 + T07 carry-overs symmetrically.
- **CHANGELOG honesty.** Builder's `### Added — M19 Task 07 cycle 2` block correctly frames the cycle-2 change as a propagation cycle ("No source code or doc surface changes; pure propagation cycle"). Does not claim the underlying findings were fixed — only that the carry-over was added to T08. Composes with the existing `### Changed — M19 Task 07` cycle-1 block beneath it.
- **Gates re-run from scratch.** `uv run pytest`: 746 passed, 9 skipped, 24 warnings (24 = pre-existing `result.plan` deprecation warnings — unchanged). `uv run lint-imports`: 4 contracts kept, 0 broken (109 dependencies — unchanged from cycle 1). `uv run ruff check`: All checks passed. No regression.
- **Existing 13 ACs + 1 carry-over AC still PASS / MET-WITH-CAVEAT.** No grade changes from cycle 1; cycle 2 was propagation-only, so the surface-quality caveats on AC-1/AC-6/AC-7/AC-9 + the carry-over LOW-1 caveat persist but are now all formally deferred to T08 rather than OPEN-on-T07.
- **Status surfaces unchanged.** T07 spec `**Status:**` still ✅ Implemented (2026-04-26); milestone README task table row 07 still ✅ Implemented; AC checkboxes still ticked. Cycle 2 did not touch status surfaces (none required updating — T07's PASS verdict was not in dispute).

**Issue file flips from `⚠️ OPEN` to `✅ PASS`.** All 5 cycle-1 OPEN findings (1 MEDIUM + 4 LOWs) are now RESOLVED-DEFERRED-TO-T08 with concrete actionable carry-over entries the T08 Builder will tick on implement. Cycle-1 audit history preserved verbatim above; cycle-2 verdict appended without rewrite. Per auditor protocol: cycle-2 close-out flips RESOLVED-DEFERRED → RESOLVED (commit sha) when T08's release-ceremony doc pass closes the carry-over. Until then, the propagation channel is closed and the T08 Builder is set up to land the work as part of the 0.3.0 release ceremony's pre-publish doc pass.

## Security review (2026-04-26)

**Scope.** T07 is doc-only (no source code under `ai_workflows/` changed, `pyproject.toml` and `uv.lock` untouched). Review is scoped to: (1) the new documentation surfaces teaching downstream consumers unsafe patterns; (2) KDR-003 / OAuth subprocess framing accuracy; (3) the `nice_to_have.md §23` re-open gate adequacy; (4) the `architecture.md §Extension model` + KDR-013 user-owned-code boundary accuracy; (5) the `README.md §Extending ai-workflows` section for MCP-server-exposure misdirection; (6) pre-existing Security notes loss on the README surface.

### Checked items (clean)

**KDR-003 accuracy.** All three new documentation surfaces accurately describe the OAuth-only Claude access model. `README.md:28` reads "Claude access is OAuth-only through the `claude` CLI subprocess." `docs/writing-a-graph-primitive.md:104` adds a KDR-003 self-check reminder: "the module does not import `anthropic` and does not read `ANTHROPIC_API_KEY`." No new doc surface introduces `ANTHROPIC_API_KEY` or implies direct API usage. No `ANTHROPIC_API_KEY` grep hit in `ai_workflows/` source (zero hits confirmed). KDR-003 boundary accurately communicated.

**User-owned-code boundary framing.** `docs/writing-a-custom-step.md §User-owned code boundary` (lines 301-314) explicitly states: "Custom steps run in-process with full Python privileges. KDR-013 applies: ai-workflows surfaces import errors ... but it does not lint, test, or sandbox the code inside your `execute()` method. You own the security and correctness surface." The architecture.md KDR-013 row (line 288) states: "The framework continues to surface — not police — custom step type implementations." No sandboxing is implied anywhere; the boundary is accurately and honestly framed.

**`nice_to_have.md §23` re-open gate.** The re-open trigger at line 551 reads: "When a **second** external workflow ... with conditional routing or sub-graph composition wants to use the spec API." Line 553 explicitly lists what does NOT trigger a re-open: "A single workflow ... cosmetic preference for declarative authoring over the escape hatch; future minor releases." The gate is two-sided (positive trigger + explicit non-triggers) and concrete enough that a future drive-by adoption would need to override it explicitly. No bypass vector in the framing.

**Credential handling in new docs.** `README.md:68` shows `export GEMINI_API_KEY=...` (ellipsis placeholder only; no real value). `docs/writing-a-custom-step.md:313-314` says "if your custom step calls a third-party API, manages credentials, or performs file I/O, the security of those operations is yours to own" — correct framing, no misleading credential-handling advice. No sample `.env` block with real values anywhere in the modified files.

**MCP server exposure in `README.md §Extending ai-workflows`.** The new section contains no MCP server invocation, no `--host` flag, no network exposure guidance. It is limited to the tier table and the "descending a tier" promise. No new unsafe MCP-exposure pattern introduced.

**Subprocess safety in new docs.** Neither the new `README.md` section nor the `architecture.md §Extension model` contains subprocess invocations, `shell=True` patterns, or guidance that would steer a user toward unsafe subprocess construction.

**Wheel contents (informational).** The `dist/` wheel is `jmdl_ai_workflows-0.2.0` (pre-existing, not rebuilt by T07). T07 is doc-only with no source changes; no new wheel was produced. Pre-publish wheel check for the next release (0.3.0 / T08) is the appropriate gate. The `migrations/` directory is present in the existing wheel — confirmed intentional (runtime schema bootstrap, not build artefact).

**`architecture.md §Extension model` placement and framing.** The section (lines 168-185) accurately describes the four tiers, the graph-layer out-of-scope boundary, and the graduation path. It references KDR-013 inline ("Custom step is user-owned Python (KDR-013)") and does not over-promise framework safety properties. The gate-pause projection note (line 183) correctly points to `design_docs/nice_to_have.md §23` for the re-open trigger rather than implying the feature exists.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

**SEC-HIGH-1 — `README.md §Security notes` section removed by M16 T01; not restored by T07; absent from the PyPI-published README surface.**

**Where:** `README.md` — the `### Security notes` subsection present in the 0.1.3 release (`b01b1ec`) and the 0.2.0 release-prep commit (`e3607a9`) was dropped at M16 T01 (`01ceb9b`). It is absent from the current committed HEAD and from the T07 working-tree diff. The threat model (§4 MCP HTTP transport bind address) explicitly requires: "The `--host 0.0.0.0` foot-gun is documented (per 0.1.3 README §Security notes — verify still present after edits to README)."

**What was lost.** The 0.2.0 release-prep README contained:

```markdown
### Security notes

- **Loopback default** — `aiw-mcp --transport http` binds to `127.0.0.1`; unreachable from other machines.
  `--host 0.0.0.0` exposes the server to every process on the host and to the LAN. `aiw-mcp` has no built-in
  auth; the bind address is the only access boundary. Only pass `0.0.0.0` on a machine you own every process
  on, and put a reverse proxy in front if you need TLS.
- **CORS is opt-in, exact-match** — `--cors-origin <url>` adds one origin; without any flags the server emits
  no `Access-Control-Allow-Origin` header (same-origin only).
```

**Why High, not Critical.** The foot-gun warning is present in the `aiw-mcp --help` output (the `--host` option's help text reads "Loopback default; pass 0.0.0.0 only if you own every process on the host"). The runtime default is correctly `127.0.0.1`. A downstream consumer who reads only `--help` gets the warning. The README absence means a user reading the PyPI page or the GitHub README surface does not see the warning before trying the HTTP transport. Given that the MCP HTTP example in the README (`aiw-mcp --transport http --port 8080 --cors-origin http://localhost:3000`) does not show `--host` at all, a user may not realise the flag exists or that the default differs from what they would get on a remote server.

**Why not Critical.** The default is safe (loopback). No documentation actively teaches `--host 0.0.0.0`. The risk is an uninformed user who reads the README example, adds `--host` on their own, and does not notice the lack of auth. This is a "could be better" gap on the PyPI-published README, not an active mislead.

**Threat model item.** §4 MCP HTTP transport bind address — "The `--host 0.0.0.0` foot-gun is documented (per 0.1.3 README §Security notes — verify still present after edits to README)."

**Action.** Restore the `### Security notes` subsection under `## MCP server` in `README.md`. The exact text from the 0.2.0 release-prep commit is the correct restoration target. This is a one-paragraph addition; T08 is the natural owner (milestone close-out + 0.3.0 publish ceremony is the last gate before next PyPI publish). Add to the T08 carry-over alongside the existing CARRY-T07-* items.

**Owner:** T08 — fold into the pre-publish README check. Add to T08 `task_08_milestone_closeout.md` carry-over as `CARRY-SEC-HIGH-1`.

### 🟡 Advisory — track; not blocking

**SEC-ADV-1 — README `## Getting started` section drops the `## Setup` section (GEMINI_API_KEY, OLLAMA_BASE_URL, .env auto-load, Claude Code OAuth setup pointer); all credential / env-var guidance is now absent from the README surface.**

**Where:** `README.md` — the `## Setup` section (present through `e3607a9`) was dropped at M16 T01. What remains is `export GEMINI_API_KEY=...` on line 68 with no surrounding context.

**Why Advisory not High.** The dropped section was primarily usability documentation (where to get the key, `.env` auto-load, OLLAMA_BASE_URL default) rather than security-critical guidance. The KDR-003 framing ("no ANTHROPIC_API_KEY; Claude access is OAuth-only") remains in `README.md:28`. The setup guidance's security-relevant content (the Claude Code OAuth setup pointer + the "aiw never reads ANTHROPIC_API_KEY" statement) was partially absorbed into line 28.

**What is now missing that matters (privacy/usability, not hard security).** The `.env` example block that the 0.1.3 `## Setup` section contained showed `GEMINI_API_KEY=your-key-here` (placeholder). Its absence means there is no explicit sample `.env` for a new user to reference, which is more a UX gap than a security gap. No real API key was ever in the README.

**Threat model item.** §1 Wheel contents — `.env`-shape leakage in `long_description` (the README IS the PyPI long description): "Any sample `.env` block in README must use placeholders only — no real values." The missing `.env` block is no longer present to check; if it were restored it would need to use placeholders, which the historical version did correctly.

**Action.** Either restore the `## Setup` section or add a brief env-var reference table in its place. Not blocking publish. Track as T08 doc-pass item or WONTFIX if the leaner README structure is intentional.

**Owner:** T08 — note as optional restoration alongside CARRY-SEC-HIGH-1.

### Verdict: FIX-THEN-SHIP

SEC-HIGH-1 (README `### Security notes` section dropped, `--host 0.0.0.0` foot-gun undocumented on the PyPI README surface) must be restored before the next PyPI publish. The fix is one paragraph; the natural owner is T08 pre-publish. No blocking issue exists at the current working-tree state (T07's own diff is clean), but the SEC-HIGH-1 gap must be closed before 0.3.0 ships.

### Final status: ✅ T07 SHIPPABLE (user-locked 2026-04-26 — option 2: accept pre-existing-regression framing)

User chose to defer SEC-HIGH-1 + SEC-ADV-1 to T08 rather than re-loop T07 cycle 3. Rationale: T07's own diff is clean; the gap is a pre-existing M16 T01 regression that T07's README touch surfaced rather than introduced; the natural owner is T08's pre-publish doc pass before `uv build` for 0.3.0; this matches the M19 forward-deferral pattern (option 2) established across T03/T04/T05/T07 cycle 1.

Both items are propagated as carry-over in `task_08_milestone_closeout.md` §"Carry-over from M19 T07 security review (2026-04-26)":
- `CARRY-SEC-HIGH-1` — restore `### Security notes` subsection (must close before 0.3.0 publish).
- `CARRY-SEC-ADV-1` — optional `## Setup` restoration alongside CARRY-SEC-HIGH-1 (advisory).

T07 considered fully closed for commit + push purposes. T08 owns the close-before-publish gate.
