# Task 07 — Four-tier framing across `architecture.md`, `README.md`, `writing-a-graph-primitive.md` + KDR table updates + Q5 deferral re-open trigger

**Status:** ✅ Implemented (2026-04-26).
**Grounding:** [milestone README](README.md) · [ADR-0008 §Extension model + §Documentation surface (the propagation requirements this task lands)](../../adr/0008_declarative_authoring_surface.md) · [KDR-004 (validator pairing — strengthened to construction invariant; KDR table row update)](../../architecture.md) · [KDR-013 (user code is user-owned — boundary shifts; KDR table row update)](../../architecture.md) · [Task 05](task_05_writing_workflow_rewrite.md) (Tier 1+2 doc; cross-linked from `architecture.md §Extension model` + `README.md`) · [Task 06](task_06_writing_custom_step.md) (Tier 3 doc; cross-linked) · [`design_docs/architecture.md`](../../architecture.md) (the architecture-of-record being extended) · [`README.md`](../../../README.md) (the project entry point being extended) · [`docs/writing-a-graph-primitive.md`](../../../docs/writing-a-graph-primitive.md) (the existing Tier 4 doc being aligned) · [`design_docs/nice_to_have.md`](../../nice_to_have.md) (the parking lot where the Q5 slice_refactor-port re-open trigger lands).

## What to Build

A coordinated update across **four** documentation surfaces that bring the four-tier extension model into load-bearing visibility plus the M19 README §Decisions Q5 deferral re-open trigger:

1. **`design_docs/architecture.md`** — new §"Extension model" subsection (~one page) makes the four-tier framing part of the architecture-of-record. KDR-004 + KDR-013 rows in §9 updated to reflect the strengthened/shifted contracts.
2. **`README.md`** — new "Extending ai-workflows" section near the top (above "MCP server") with one-paragraph framing per tier and a strong pointer table to each tier's guide. Extensibility surfaced as a core value proposition.
3. **`docs/writing-a-graph-primitive.md`** — existing doc; M19 audits its content for consistency with ADR-0008's framing. Audience clarified as framework contributors (not external consumers). Existing "if a wiring pattern appears in 2+ workflows, promote" heuristic restated as the Tier 3 → graph-layer graduation path.
4. **`design_docs/nice_to_have.md`** — new parking-lot entry for "Spec API extensions for slice_refactor-shape patterns" with the explicit re-open trigger from M19 §Decisions Q5: *"When a second external workflow with conditional routing or sub-graph composition wants to use the spec API, file a milestone proposal for taxonomy extension."* This is the missing piece that makes the deferral honest.

These four updates land as one task because the four-tier framing is one coherent edit landing across the doc surface (per the M19 README §Decisions Q2 — bundle, not split). The task's atomic acceptance is "all four surfaces consistently teach the four-tier model + the KDR table reflects the shifts + the deferral re-open trigger is recorded with the rest of the parking lot."

## Deliverables

### 1. `design_docs/architecture.md` — new §"Extension model" subsection

Insert a new top-level subsection (~one page, ~50–80 lines of markdown) that captures the four-tier extension model as part of the architecture-of-record. **Placement guidance** (revised per M8 fix — the original draft cited a non-existent gap between §4 and §6 since §5 "Runtime data flow" is taken): place either between §3 (Layered structure) and §4 (Components) — the four-tier model maps onto the layer structure conceptually — or between §7 (Boundaries and contracts) and §8 (Cross-cutting concerns), or as a top-level §"Extension model" appended at end-of-document. **Not as §4.5** — Extension model is not a sub-concern of Components. Builder picks the placement at implement time based on what fits the current cross-references with the least disruption.

Section structure:

#### §X.Y Extension model — extensibility is a first-class capability

**Framing paragraph:** ai-workflows is a declarative orchestration layer over LangGraph. Authors of external workflows engage at four progressively-deeper tiers; each tier has a dedicated guide that teaches it with worked examples. Descending a tier never forces an author to reverse-engineer framework source.

**Tier table:**

| Tier | What the author does | Guide |
|---|---|---|
| 1 — Compose | Combine built-in step types into a `WorkflowSpec`. The declarative happy path. | [`docs/writing-a-workflow.md`](../docs/writing-a-workflow.md) |
| 2 — Parameterise | Configure built-in steps: retry policy, validator override, gate-rejection behaviour, tier choice. | [`docs/writing-a-workflow.md`](../docs/writing-a-workflow.md) (same doc — Tier 2 is parameter configuration of Tier 1's step types) |
| 3 — Author a custom step type | Subclass `Step` when no built-in covers the need. Custom step is user-owned Python (KDR-013) but composes with built-ins indistinguishably. | [`docs/writing-a-custom-step.md`](../docs/writing-a-custom-step.md) |
| 4 — Escape to LangGraph directly | Drop to the legacy `register(name, build_fn)` API and author the `StateGraph` directly. Reserved for genuinely non-standard topologies. | [`docs/writing-a-graph-primitive.md`](../docs/writing-a-graph-primitive.md) |

**Out-of-scope-for-external-authors paragraph:** Graph-layer primitives (`TieredNode`, `ValidatorNode`, `HumanGate`, `RetryingEdge`, the cost-tracking callback, the `SqliteSaver` checkpointer) are framework-internal. External extension at this depth dissolves the four-layer rule. Custom needs at this depth route through Tier 3 (wrap the behaviour in a step) or surface as feature requests; only framework contributors author new graph-layer primitives.

**Graduation paragraph:** When a custom step pattern proves broadly useful — appearing in two or more workflows — the framework absorbs it as a built-in step in a future minor. When the underlying *wiring* (not just the step semantics) is reusable across step types, it graduates to the graph layer per the heuristic in `writing-a-graph-primitive.md`. The graduation pattern is the framework's organic-growth mechanism.

**Reference to ADR-0008** — for the rejected alternatives, the consequences, and the documentation propagation requirements.

### 2. `design_docs/architecture.md` §9 — KDR table row updates

Two existing KDR rows are updated to reflect M19's strengthened/shifted contracts:

#### KDR-004 update
**Old:** "Validator-node-after-every-LLM-node is mandatory; prompting is a schema contract."
**New:** "Validator-node-after-every-LLM-node is mandatory; prompting is a schema contract. Under the M19 spec API (ADR-0008), this graduates from convention-enforced-by-review to invariant-enforced-by-construction — `LLMStep` requires `response_format`, and the compiler pairs the validator automatically. The escape-hatch `register(name, build_fn)` API retains the convention-enforced-by-review status quo."
**Source column:** add `· [ADR-0008](adr/0008_declarative_authoring_surface.md)` to the existing analysis-doc reference.

#### KDR-013 update
**Old:** "External workflow module discovery..." (the existing wording from KDR-013 — see line 269 of architecture.md).
**New:** Append a paragraph: "Under the M19 spec API (ADR-0008), the user-owned-code boundary shifts: workflow specs are *data* (no Python privileges to worry about); custom step types remain *code* (still user-owned). The framework continues to surface — not police — custom step type implementations."
**Source column:** add `· [ADR-0008](adr/0008_declarative_authoring_surface.md)` to the existing reference.

No new KDR is added by M19 — ADR-0008 is composed under the existing KDRs (per ADR-0008 §Decision: "no new KDR; ADR-0008 is composed under existing KDRs").

### 3. `README.md` — new "Extending ai-workflows" section

Placement: above the existing "## MCP server" section. New top-level section with one-paragraph framing per tier and a pointer table.

```markdown
## Extending ai-workflows

ai-workflows is a declarative orchestration layer; extension is a first-class capability. Authors engage at four progressively-deeper tiers, each with a dedicated guide:

| Tier | When | Guide |
|---|---|---|
| **1. Compose** | You're combining built-in step types (`LLMStep`, `ValidateStep`, `GateStep`, `TransformStep`, `FanOutStep`) into a workflow. The happy path. | [docs/writing-a-workflow.md](docs/writing-a-workflow.md) |
| **2. Parameterise** | You're configuring built-in steps (retry policy, response format, gate behaviour, tier choice). | [docs/writing-a-workflow.md](docs/writing-a-workflow.md) (same doc) |
| **3. Author a custom step type** | No built-in covers your need. Subclass `Step`; the framework wires your custom step into the graph like a built-in. | [docs/writing-a-custom-step.md](docs/writing-a-custom-step.md) |
| **4. Escape to LangGraph directly** | Your topology is genuinely non-standard (dynamic edge conditions, novel control flow). Use the legacy `register(name, build_fn)` API. | [docs/writing-a-graph-primitive.md](docs/writing-a-graph-primitive.md) |

The framework's promise: descending a tier never forces you to reverse-engineer framework source. If you're at the wrong tier, you'll find pointers to the right one in any guide.
```

The framing prose surfaces "first-class capability" + the framework's promise per ADR-0008 §Documentation surface.

### 4. `docs/writing-a-graph-primitive.md` — alignment updates

The existing doc is 108 lines (audited 2026-04-26). Audience-clarification banner at the top:

```markdown
> **Audience:** This guide is for **framework contributors** authoring new graph-layer primitives — not for downstream consumers. If you're an external workflow author, see [`writing-a-workflow.md`](writing-a-workflow.md) (Tier 1 + Tier 2) and [`writing-a-custom-step.md`](writing-a-custom-step.md) (Tier 3) instead. The four-tier extension model is documented in [`design_docs/architecture.md` §Extension model](../design_docs/architecture.md).
```

Plus inline updates:

- Restate the existing "if the same wiring pattern appears in two or more workflows, promote it to `ai_workflows/graph/`" heuristic (line 9) as the **Tier 3 → graph-layer graduation path**. Same heuristic, new framing — connects to ADR-0008's graduation paragraph.
- Cross-references audited: any `(builder-only, on design branch)` annotations on items now in the main tree are scrubbed. New cross-link to `architecture.md §Extension model` for the Tier 4 framing.
- The doc's content is otherwise unchanged — its existing material on `MaxLatencyNode`, the composition pattern, and the graph-layer contract is correct and survives M19.

### 5. `design_docs/nice_to_have.md` — Q5 deferral re-open trigger

Add a new parking-lot entry capturing the M19 §Decisions Q5 + H2 combined slice_refactor-and-planner-port deferrals. The entry follows the existing nice_to_have.md format (numbered section, "trigger to re-open" bullet, scope notes). Per locked Q1 (M19 takes one slot for this entry; see README §Decisions item 1), the slot is determined at T07 implement time by re-grepping `nice_to_have.md` for the next-free section number (currently §23 at round-3 analysis time).

The entry text:

```markdown
## §<N>. Spec API extensions for slice_refactor-shape patterns

**Status:** Deferred at M19 (2026-04-26) per ADR-0008 + M19 README §Decisions Q5.

**What this would extend:**
- Sub-spec composition step (`SubSpecStep(spec=other_spec)`) — for workflows that compose other registered specs as sub-graphs.
- Conditional routing step (`BranchStep(condition=Callable, branches={...})`) — for workflows whose graph topology depends on runtime state.
- Hard-stop / multi-terminal step types — for workflows with distinct error-terminals beyond the default completion path.
- Mid-run tier override propagation in `FanOutStep` — for fault-tolerance overlays like the M8/M10 Ollama-fallback.
- `wrap_with_error_handler` integration into `LLMStep` — for workflows that need retry-counter bookkeeping + last_exception carry.

**Why deferred:** slice_refactor is the only in-tree workflow that uses these patterns; one example doesn't prove the taxonomy needs the extensions. The risk of premature extension is over-engineering the spec API around one workflow's edge cases; the framework's value is the simpler authoring contract.

**Trigger to re-open:** When a **second** external workflow (downstream consumer OR new in-tree workflow) with conditional routing or sub-graph composition wants to use the spec API. At that point, the second example proves the pattern is reusable, and a new milestone proposal scopes the taxonomy extension. Until then, slice_refactor stays on the existing `register("slice_refactor", build_slice_refactor)` escape hatch (Tier 4) — which is its current shape and continues to work unchanged.

**What does NOT trigger a re-open:** A single workflow (slice_refactor or any other) that wants the extensions; cosmetic preference for declarative authoring over the escape hatch; future minor releases that add other features. The bar is "second forcing function fires" — not "we have time."
```

The Builder re-greps `nice_to_have.md` at T07 implement time and picks the next-free slot number; the entry's section number is recorded in T07's issue file at audit time.

### 6. Smoke verification (Auditor runs)

```bash
# Architecture file structure check:
grep -n "^## .*Extension model\|^### .*Extension model" design_docs/architecture.md

# KDR table updated:
grep -n "M19 spec API\|ADR-0008" design_docs/architecture.md

# README structure check:
grep -n "^## Extending ai-workflows" README.md

# writing-a-graph-primitive.md alignment:
grep -n "Audience:" docs/writing-a-graph-primitive.md
grep -n "Tier 3 → graph-layer graduation" docs/writing-a-graph-primitive.md  # or equivalent phrasing

# Cross-link audit — every reference resolves:
for path in \
  design_docs/architecture.md \
  README.md \
  docs/writing-a-workflow.md \
  docs/writing-a-custom-step.md \
  docs/writing-a-graph-primitive.md \
  design_docs/adr/0008_declarative_authoring_surface.md ; do
  test -f "$path" || { echo "MISSING: $path"; exit 1; }
done

# Gates:
uv run lint-imports
uv run ruff check
```

The smoke verifies structural presence + cross-link resolvability. Manual read-through verifies the framing is consistent across all three surfaces.

### 7. CHANGELOG

Under `[Unreleased]` on both branches:

```markdown
### Changed — M19 Task 07: four-tier extension model propagated across architecture + README + primitive doc + nice_to_have re-open trigger (YYYY-MM-DD)
- `design_docs/architecture.md` — new §"Extension model" subsection (~1 page) makes the four-tier framing part of the architecture-of-record. KDR-004 + KDR-013 rows in §9 updated with the strengthened/shifted contracts under the M19 spec API.
- `README.md` — new "Extending ai-workflows" section near the top with one-paragraph framing per tier and pointer table. Extensibility surfaced as a core value proposition (above the "MCP server" section).
- `docs/writing-a-graph-primitive.md` — audience-clarification banner; existing "promote when pattern appears in 2+ workflows" heuristic restated as the Tier 3 → graph-layer graduation path. Existing content otherwise unchanged.
- `design_docs/nice_to_have.md` — new entry "Spec API extensions for slice_refactor-shape patterns" with explicit re-open trigger (a second external workflow with conditional routing or sub-graph composition; per M19 §Decisions Q5).
```

## Acceptance Criteria

- [x] **AC-1:** `design_docs/architecture.md` has a new §"Extension model" subsection (~50–80 lines) with the framing paragraph + tier table + out-of-scope-for-external-authors paragraph + graduation paragraph + reference to ADR-0008. Placement is consistent with the architecture document's existing structure.
- [x] **AC-2:** `architecture.md §9` KDR table has updated rows for KDR-004 and KDR-013 reflecting the M19 strengthening/shifting per Deliverable 2. Source column references include ADR-0008.
- [x] **AC-3:** No new KDR added (per ADR-0008 §Decision; M19 is composed under existing KDRs).
- [x] **AC-4:** `README.md` has a new "## Extending ai-workflows" section above the "MCP server" section with the framing paragraph + tier table per Deliverable 3. Every link in the table resolves.
- [x] **AC-5:** `docs/writing-a-graph-primitive.md` has an audience-clarification banner at the top naming the framework-contributor audience and pointing external-author readers at the appropriate tier guide.
- [x] **AC-6:** `docs/writing-a-graph-primitive.md`'s "promote when pattern appears in 2+ workflows" heuristic restated as the Tier 3 → graph-layer graduation path. Cross-link to `architecture.md §Extension model` added.
- [x] **AC-7:** Cross-references audited across all three surfaces. Every internal link resolves at implement time. Any outdated "(builder-only, on design branch)" annotations on items now in the main tree are scrubbed.
- [x] **AC-8:** Smoke verification (Deliverable 5) passes — structural presence checks succeed + every referenced file exists.
- [ ] **AC-9:** Manual read-through (Auditor's responsibility) confirms the four-tier framing is consistently applied across architecture + README + primitive doc + the existing T05/T06 guides. Terminology consistent (always "Tier 1 / 2 / 3 / 4"; consistent step-type naming).
- [x] **AC-10:** Existing content in `architecture.md` unchanged outside §"Extension model" + §9 KDR rows. Existing content in `README.md` unchanged outside the new "Extending ai-workflows" section. Existing content in `writing-a-graph-primitive.md` unchanged outside the audience banner + heuristic-restating + cross-link additions.
- [x] **AC-11:** `nice_to_have.md` has the new "Spec API extensions for slice_refactor-shape patterns" entry per Deliverable 5. Slot number recorded in the issue file at audit time. Re-open trigger language matches Deliverable 5 verbatim.
- [x] **AC-12:** Gates green on both branches. `uv run pytest`, `uv run lint-imports`, `uv run ruff check`.
- [x] **AC-13:** CHANGELOG entry under `[Unreleased]` per Deliverable 7.

## Dependencies

- **Task 05 (writing-a-workflow.md rewrite)** — precondition. T07's cross-links to `writing-a-workflow.md` reference the rewritten content.
- **Task 06 (writing-a-custom-step.md)** — precondition. T07's cross-links to `writing-a-custom-step.md` require the doc to exist.
- **No precondition on T01–T04.** T07 documents the architectural shape; the implementation is in T01–T04.

## Out of scope (explicit)

- **No new doc files.** T05 + T06 own those. T07 lands surface updates to existing files (architecture, README, primitive guide, nice_to_have).
- **No new KDRs.** Per ADR-0008 §Decision.
- **No content rewrite of `writing-a-graph-primitive.md` beyond the audience banner + heuristic-restating.** The existing doc is correct for its (now-clarified) audience.
- **No spec API changes.** T01 + T02 own the spec surface.
- **No `architecture.md` changes outside §Extension model + §9 KDR rows.** The architectural-of-record restructuring is a separate concern.

## Carry-over from prior milestones

- **M18 inventory cross-reference rot items** (R1, R2 — design-branch annotations on items in the main tree) — partially resolved here in `writing-a-graph-primitive.md`'s scrubbing pass. T05 covers the rest in `writing-a-workflow.md`.

- **Slice_refactor gate-pause projection now reports `artifact=None` post-T03 (M19 T03 cycle-1 audit MEDIUM-1, locked Path A 2026-04-26).** T03's `final.get("plan")` → `final.get(final_state_key)` migration at the resume-path sites (`_dispatch.py:1031` re-gate, `:1088` gate_rejected, `:1094` completed) honestly reads slice_refactor's `FINAL_STATE_KEY = "applied_artifact_count"` (an int, populated only AFTER the post-gate apply node runs). Pre-T03 the operator at `slice_refactor_review` gate incidentally saw the composed planner's `PlannerPlan` (state["plan"] from the planner sub-graph that runs before the gate); post-T03 they see `artifact=None, plan=None`. M11 T01's "in-flight draft at gate pause" framing was always planner-shaped — slice_refactor's review-gate operator was getting "the planner's plan from 3 nodes ago," which was useful but accidental. The shift is honest. **T07 documentation responsibilities:** (a) `architecture.md §"Extension model"` notes that gate-pause projection follows `FINAL_STATE_KEY`, so workflows whose `FINAL_STATE_KEY` channel is empty at gate time will see `artifact=None` at gate-pause-resume responses; (b) if a downstream consumer files a request for configurable gate-pause projection, that fires the locked Q5+H2 re-open trigger ("a second external workflow with conditional routing or sub-graph composition") — surface as a `nice_to_have.md` candidate (`gate_review_payload_field` knob on `WorkflowSpec` or equivalent).

## Carry-over from task analysis

*Empty at task generation. Populated by `/clean-tasks` if any LOWs surface during the analyzer loop, and by `/clean-implement`'s audit cycle later.*

## Carry-over from prior audits

- [x] **M19-T06-ISS-LOW-1 — Add `architecture.md §Extension model` back-link to `docs/writing-a-custom-step.md`** (severity: LOW, source: [M19 T06 issue file](issues/task_06_issue.md))
      T06 shipped `docs/writing-a-custom-step.md` (Tier 3 dedicated guide) before T07 lands the new `architecture.md §"Extension model"` subsection. Spec Deliverable 3 of T06 expected three cross-link targets — `writing-a-workflow.md`, `writing-a-graph-primitive.md`, and `architecture.md §Extension model` — but the third was intentionally omitted by T06 because the anchor target does not exist yet. T06 cannot reference an anchor T07 hasn't created.
      **What T07 must do:** when landing the new `architecture.md §"Extension model"` subsection (T07 Deliverable 1), also add a back-link from `docs/writing-a-custom-step.md` to `../design_docs/architecture.md#extension-model` (anchor name to match T07's heading slug). The natural placement is in §Pointers to adjacent tiers (after the Tier 4 cross-link), or inline in §When to write a custom step. T07 already cross-touches `architecture.md` + `README.md` + `writing-a-graph-primitive.md`, so adding one cross-link to `writing-a-custom-step.md` is a natural extension of the same coordinated pass. Verify the link resolves under `tests/docs/test_docs_links.py` (which file-checks but not anchor-checks per its current scope; anchor validation is `nice_to_have` per the link checker's docstring).
