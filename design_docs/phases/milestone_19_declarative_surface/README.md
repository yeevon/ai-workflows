# Milestone 19 — Declarative Authoring Surface

**Status:** 📝 Planned (drafted 2026-04-26 against [ADR-0008](../../adr/0008_declarative_authoring_surface.md); `/clean-tasks m19` will deepen each task spec and run the analyzer loop).
**Grounding:** [ADR-0008 — Declarative authoring surface for external workflows](../../adr/0008_declarative_authoring_surface.md) (load-bearing identity decision; this milestone executes it) · [ADR-0007 — User-owned code contract](../../adr/0007_user_owned_code_contract.md) (composes — discovery surface preserved; only the *what* the consumer registers changes) · [architecture.md §3 + §4.3 + §9](../../architecture.md) · [`ai_workflows/workflows/_dispatch.py`](../../../ai_workflows/workflows/_dispatch.py) (the compile site the new compiler hands a `StateGraph` to; also the bug-fix site folded from M18) · [`ai_workflows/workflows/__init__.py`](../../../ai_workflows/workflows/__init__.py) (the registry surface the new entry point composes over) · [`docs/writing-a-workflow.md`](../../../docs/writing-a-workflow.md) (existing author guide; rewrites declarative-first under this milestone) · CS-300 pre-flight smoke 2026-04-25 (the trigger, recorded in ADR-0008 §Context) · in-conversation hostile re-read 2026-04-26 (12-finding contract-surface inventory — folded into ADR-0008's framing).

## Why this milestone exists

[ADR-0008](../../adr/0008_declarative_authoring_surface.md) recorded the decision: the primary external workflow authoring surface becomes **declarative**. Consumers pass a `WorkflowSpec` data object that names the workflow, declares input/output schemas, and lists ordered steps composed from framework-provided step types. The framework synthesizes the LangGraph `StateGraph` at registration time. The current `register(name, build_fn)` API survives as a documented escape hatch for genuinely non-standard topologies.

**Why now:** the M16 + ADR-0007 contract that shipped at 0.2.0 makes external authors *effectively* LangGraph authors, given the framework's documented patterns. CS-300's 2026-04-25 pre-flight smoke surfaced four undocumented hooks plus one runtime bug, and a hostile re-read on 2026-04-26 widened the inventory to 12 findings. The originally-drafted M18 patch path (document the hooks, fix the bug, rename `plan` → `artifact`) was withdrawn on the same day because comprehensive docs don't change the underlying problem: the framework's value proposition disappears when consumers do their own LangGraph wiring. M18 is obsoleted; its T01 (the artefact-loss bug fix) folds into M19 as a precursor.

**The framework's value proposition under this milestone:** a declarative orchestration layer over LangGraph, with extensibility as a first-class capability — *not* a thin import-wrapper. M19 is the milestone where that positioning becomes real.

**Extension is a core feature, not a fallback.** ADR-0008 §"Extension model" makes this normative: authors engage at four progressively-deeper tiers (compose built-in steps → parameterise them → author a custom step type → escape to LangGraph directly), and each tier has a dedicated guide that meets them at that level of complexity. The framework's promise to extending authors is that descending a tier never forces them to reverse-engineer framework source. M19's documentation surface is non-skippable; a doc gap at any tier is a regression on the framework's value proposition.

## What M19 ships

1. **`ai_workflows/workflows/spec.py`** — new module. `WorkflowSpec` pydantic model + step-type taxonomy (`Step` base + `LLMStep` / `ValidateStep` / `GateStep` / `TransformStep` / `FanOutStep`) + custom-step extension hook contract + `register_workflow(spec)` entry point. The data-model layer; no compilation yet.
2. **`ai_workflows/workflows/_compiler.py`** — new module. Spec → `StateGraph` synthesis. Walks a `WorkflowSpec`, synthesises the `StateGraph` (state class derivation from `input_schema` + `output_schema`, START/END wiring, `initial_state` hook synthesis from the input schema, `FINAL_STATE_KEY` resolution from the output schema, validator pairing on every `LLMStep` per KDR-004 by construction). Owns the wiring previously asked of consumers.
3. **Result-shape bug fix + schema rename (folded from M18 T01).** `_dispatch.py` lines 721, 781, 977, 1034, 1048 — `final.get("plan")` → `final.get(final_state_key)` so the response field surfaces the artefact regardless of which state key the workflow names. `RunWorkflowOutput.artifact` + `ResumeRunOutput.artifact` become the canonical artefact-surfacing fields; `plan` field surfaced on the wire alongside `artifact` for backward compatibility through the 0.2.x line, with a `### Deprecated` CHANGELOG notice naming **1.0** as the removal target.
4. **New in-tree `summarize` workflow as the spec-API proof point** ([T04](task_04_summarize_proof_point.md)). [`ai_workflows/workflows/summarize.py`](../../../ai_workflows/workflows/summarize.py) — new in-tree workflow authored against the M19 declarative spec API. `WorkflowSpec` composing `LLMStep` (with `prompt_template` Tier 1 sugar) + `ValidateStep` against `SummarizeOutput`. Sole purpose: prove the spec API compiles + dispatches + checkpoints + surfaces results end-to-end through both `aiw run` and `aiw-mcp run_workflow`. Doubles as the worked-doc example T05 cites — the doc and the workflow share source. The wire-level proof lives in `tests/integration/test_spec_api_e2e.py` (CLI via `CliRunner` + MCP via `fastmcp.Client`, both against `StubLLMAdapter`); real-Gemini live-smoke runs at T08's release ceremony.
5. **In-tree `planner` + `slice_refactor` ports deferred** (locked Q5 + locked H2 — 2026-04-26). Both workflows have the M8/M10 fault-tolerance overlay (`wrap_with_error_handler`, `build_ollama_fallback_gate`, `CircuitOpen`-aware conditional routing, hard-stop terminal node, post-gate artifact storage-write) which T01's five built-in step types cannot express. They stay on their existing `register("planner", build_planner)` and `register("slice_refactor", build_slice_refactor)` escape-hatch registrations through 0.3.x — zero diff to either module under M19. **Combined re-open trigger** (T07 records in `nice_to_have.md`): *"When a second external workflow with conditional routing or sub-graph composition wants to use the spec API, file a milestone proposal for taxonomy extension."* The H2 framing: M19 ships a new in-tree workflow that demonstrates the simplest realistic shape, proves the spec API end-to-end through both surfaces, and preserves the existing complex workflows on the documented escape hatch until external mileage tells us which extensions to add.
6. **`docs/writing-a-workflow.md` rewritten declarative-first.** Tier 1 (compose) + Tier 2 (parameterise) coverage with worked examples. Brief Tier 3 mention with link to the new custom-step guide. Brief Tier 4 mention with link to the graph-primitive guide for the "you've outgrown the spec" exit. The existing "External workflows from a downstream consumer" section becomes the entry point for downstream authors.
7. **`docs/writing-a-custom-step.md`** — new in M19. Tier 3 dedicated guide. `Step` base class contract (both `execute(state) -> dict` typical-path and `compile(state_class, step_id) -> CompiledStep` advanced-override-path per locked Q4 refinement), state-channel conventions, testing patterns (with framework-provided spec-compilation fixtures so authors can unit-test their custom steps without a full graph run — `compile_step_in_isolation` ships per locked M4), graduation hints (when a custom step pattern is ripe for promotion to a built-in or a graph primitive). The load-bearing guide for downstream consumers extending the framework.
8. **`docs/writing-a-graph-primitive.md` aligned with the four-tier framing.** Existing doc; M19 audits its content for consistency with ADR-0008. Audience clarified at the top of the doc as framework contributors (not external consumers). Existing "if a wiring pattern appears in 2+ workflows, promote" heuristic restated as the Tier 3 → graph-layer graduation path.
9. **`design_docs/architecture.md` extended.** New §"Extension model" subsection (~one page) makes the four-tier extension framing part of the architecture-of-record — not buried in an ADR. KDR-004 + KDR-013 rows updated where the spec API shifts contracts (KDR-004 graduates to construction-invariant for spec-authored workflows; KDR-013 boundary shifts to "specs are data, custom step types remain code").
10. **`README.md` "Extending ai-workflows" section.** New section near the top of the README, above the "MCP server" section. One-paragraph framing per tier, pointer table to each tier's guide, identity-level statement that extensibility is core to the framework. Strongly references the four guides.
11. **0.3.0 published.** Minor bump (the introduction of a new primary authoring surface + the repositioning of the existing one as escape hatch is a substantial enough change to warrant the bump even though both APIs coexist). Live smoke from `/tmp` per the established release ritual; `uv cache clean jmdl-ai-workflows` between publish and live smoke.

## Goal

A downstream consumer with no LangGraph experience writes a working workflow against `jmdl-ai-workflows>=0.3.0`, end-to-end, from `docs/writing-a-workflow.md` alone. They never `import langgraph`. When they need a primitive the framework doesn't ship, they author a custom step type from `docs/writing-a-custom-step.md` and slot it into the spec.

```python
# What the entry-tier author writes — Tier 1, the happy path.
# (`summarize_tier_registry()` definition omitted for brevity; see T05's
# worked example for the tier-registry helper shape.)
from ai_workflows.workflows import register_workflow, WorkflowSpec, LLMStep
from pydantic import BaseModel


class SummarizeInput(BaseModel):
    text: str
    max_words: int


class SummarizeOutput(BaseModel):
    summary: str


register_workflow(WorkflowSpec(
    name="summarize",
    input_schema=SummarizeInput,
    output_schema=SummarizeOutput,
    tiers=summarize_tier_registry(),
    steps=[
        LLMStep(
            tier="summarize-llm",
            prompt_template="Summarize the following text in at most {max_words} words:\n\n{text}",
            response_format=SummarizeOutput,
        ),
    ],
))
```

```python
# What the extending author writes — Tier 3, when no built-in covers it:
from ai_workflows.workflows import Step, register_workflow, WorkflowSpec, LLMStep
import httpx


class WebFetchStep(Step):
    """Fetches a URL and stores the response body in state."""
    url_field: str
    output_field: str

    async def execute(self, state: dict) -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.get(state[self.url_field])
            r.raise_for_status()
        return {self.output_field: r.text}


register_workflow(WorkflowSpec(
    name="summarize_url",
    input_schema=SummarizeUrlInput,
    output_schema=SummarizeOutput,
    tiers=summarize_url_tier_registry(),  # definition omitted for brevity; see T05/T06 worked examples
    steps=[
        WebFetchStep(url_field="url", output_field="page_text"),
        LLMStep(
            tier="summarize-llm",
            prompt_template="Summarize:\n\n{page_text}",
            response_format=SummarizeOutput,
        ),
    ],
))
```

Both shapes are derivable from the M19-shipped doc set alone — no `_dispatch.py` source-scan required.

## Exit criteria

1. **`WorkflowSpec` + step taxonomy land** in `ai_workflows/workflows/spec.py`. Public API: `WorkflowSpec`, `Step` (base), `LLMStep`, `ValidateStep`, `GateStep`, `TransformStep`, `FanOutStep`, `register_workflow`. Pydantic-modelled; full type annotations; `extra='forbid'` on every model so unknown fields error loudly.
2. **Compiler synthesizes `StateGraph` from spec** in `ai_workflows/workflows/_compiler.py`. State class derived from `input_schema` ⊕ `output_schema`. `initial_state` hook synthesised from the input schema. `FINAL_STATE_KEY` resolved from the output schema's first field. Validator paired on every `LLMStep` automatically (KDR-004 by construction). Hermetic tests: a `WorkflowSpec` with each step type compiles to a runnable `StateGraph`; spec-with-LLMStep enforces validator pairing.
3. **Result-shape bug fixed.** `_dispatch.py` reads `final.get(final_state_key)` for response surfacing. Hermetic test: external workflow with `FINAL_STATE_KEY = "questions"` round-trips its `questions` artefact through `RunWorkflowOutput.artifact`. In-tree planner unchanged (its `FINAL_STATE_KEY = "plan"` continues to work).
4. **Schema field rename landed.** `RunWorkflowOutput.artifact` + `ResumeRunOutput.artifact` carry the terminal artefact. `plan` field aliased on the wire alongside `artifact`; CHANGELOG `### Deprecated` notice names **1.0** as removal target. Hermetic test: both fields present and equal in the response.
5. **`summarize` workflow + e2e proof + `aiw run --input` extension landed (locked H1 + H2).** New in-tree `ai_workflows/workflows/summarize.py` authored against the spec API (LLMStep + ValidateStep). `aiw run` extended with `--input KEY=VALUE` (repeatable) for arbitrary spec-API workflow inputs; existing planner flags preserved byte-identically. New `tests/workflows/test_summarize.py` (5 hermetic tests) + `tests/integration/test_spec_api_e2e.py` (5 wire-level tests — `--input KVs` path, help-text rendering, planner-flag-conflict-raises, MCP via fastmcp.Client, cross-surface artefact identity). T08 release ceremony adds real-Gemini live-smoke (`aiw run summarize ...` against the published wheel from `/tmp`).
6. **planner + slice_refactor ports deferred** (locked H2 + locked Q5). Both workflows stay on their existing escape-hatch registrations. Combined re-open trigger captured in `nice_to_have.md` per T07's Deliverable 5: a second external workflow with conditional routing or sub-graph composition wanting to use the spec API. Zero diff to `planner.py` or `slice_refactor.py` under M19.
7. **`docs/writing-a-workflow.md` rewritten** declarative-first. Tier 1 + Tier 2 worked examples (the `summarize` shape from §Goal at minimum). Brief Tier 3 + Tier 4 mentions with strong cross-links. Existing in-package author content preserved or migrated under a clearly-marked subsection. doctest-compilable for any executable snippets.
8. **`docs/writing-a-custom-step.md` exists** with at least: `Step` base class contract documented (both `execute` typical-path and `compile` advanced-override-path per locked Q4 refinement); `execute` coroutine signature with state-channel semantics; the `WebFetchStep` worked example end-to-end (doctest-skip) plus a synthetic `AddOneStep` doctest-runnable substitute; testing patterns section showing how to unit-test a custom step against the framework's `compile_step_in_isolation` fixture (per locked M4 — fixture ships as part of T06); graduation-hints section explaining when a custom step is ripe for promotion. doctest-compilable.
9. **`docs/writing-a-graph-primitive.md` aligned.** Audience-clarification banner at top (framework contributors, not external authors). Cross-references the four-tier model in `architecture.md`. Existing content preserved; only audience framing + cross-links updated.
10. **`design_docs/architecture.md` extended.** New §"Extension model" subsection (~one page) describing the four-tier extension framing. KDR-004 + KDR-013 rows in §9 updated with the strengthened/shifted contracts. Cross-links to ADR-0008.
11. **`README.md` extended.** New "Extending ai-workflows" section with one-paragraph framing per tier and a pointer table to each guide. Section placed above "MCP server" section to surface extensibility prominently.
12. **`design_docs/nice_to_have.md` extended** with the "Spec API extensions for slice_refactor-shape patterns" entry capturing the locked Q5 + H2 combined re-open trigger. Slot number recorded at T07 implement time per locked Q1 (M19 takes one slot at the next-free section, currently §23).
13. **All five doc surfaces cross-reference each other** so an author landing at the wrong tier finds the right one in one click. The doc structure makes the four-tier model visible (consistent ordering, consistent terminology).
14. **CHANGELOG entries on both branches.** `### Added` for `WorkflowSpec` + step taxonomy + custom-step extension hook; `### Added` for new `docs/writing-a-custom-step.md` + `compile_step_in_isolation` testing fixture; `### Changed` for `docs/writing-a-workflow.md` declarative-first rewrite + `RunWorkflowOutput`/`ResumeRunOutput` field rename + `architecture.md` extension model section + `README.md` extending section; `### Fixed` for the artefact-field bug; `### Deprecated` for `RunWorkflowOutput.plan` field alias (removal target 1.0).
15. **Gates green on both branches.** `uv run pytest` + `uv run lint-imports` (4 contracts kept — no new layer; `spec.py` and `_compiler.py` live in the workflows layer) + `uv run ruff check`.
16. **0.3.0 published** and live-smoked from `/tmp` per the established release ritual.
17. **Status surfaces flipped together at task close** — per-task spec `**Status:**` line, milestone README task table row, milestone README "Done when" checkboxes — for every task in the table.

## Non-goals

- **No removal of the `register(name, build_fn)` escape hatch.** The current API survives unchanged. Tests for it run side by side with the new spec-API tests. Removal is not on any roadmap; it remains the supported path for genuinely non-standard topologies.
- **No removal of the `plan` field alias** on `RunWorkflowOutput` / `ResumeRunOutput`. The deprecation notice names 1.0 as the target; M19 ships the alias, not the removal.
- **No new graph-layer primitives.** `TieredNode`, `ValidatorNode`, `HumanGate`, `RetryingEdge` are unchanged. The compiler composes existing primitives; it does not introduce new ones. (The slice_refactor port that would have stress-tested the primitives is deferred per locked Q5; no taxonomy-extension pressure surfaces in M19.)
- **No new MCP tools.** The MCP wire surface is unchanged. The registration surface change is invisible at the wire layer (both `register_workflow` and `register` populate the same `_REGISTRY`).
- **No YAML/JSON declarative surface.** Pydantic models only for M19. A future `register_workflow_from_yaml(path)` layer composes cleanly on top of pydantic specs if a use case emerges.
- **No class-based DSL** (`class MyWorkflow(Workflow): ...`). Pydantic data classes only; ADR-0008 §Rejected alternatives records why.
- **No replacement of LangGraph.** `SqliteSaver`, `Send`, `interrupt` semantics — all preserved exactly. The compiler emits standard LangGraph artefacts; nothing in the runtime changes.
- **No Anthropic API.** KDR-003 holds; the spec API does not introduce new provider surfaces.
- **No tier overlay (M15) interaction.** M19 documents the existing `<workflow>_tier_registry()` helper for the escape-hatch path and the equivalent `tiers=` field on `WorkflowSpec` for the declarative path. M15's user-overlay merge semantics remain M15's scope.
- **No M17 (`scaffold_workflow`) interaction.** M17's future scope is "generate workflow source from goals." Post-M19, "generated source" means a `WorkflowSpec`, not a LangGraph `StateGraph` builder. M19 does not pre-build M17; it makes M17's eventual surface easier to author against.
- **No KDR change at the architecture level**, only restatements. KDR-004 + KDR-013 rows are updated; no new KDR is added. ADR-0008 is composed under existing KDRs.
- **No removal of existing CHANGELOG history or ADR archival.** ADR-0007 status updates to "Accepted (discovery surface — composes with ADR-0008's authoring surface)"; the dotted-path discovery surface is preserved verbatim.
- **No `docs/external-workflow-contract.md`.** The reference-page idea from the M18 draft is dropped; the four how-to guides (`writing-a-workflow.md`, `writing-a-custom-step.md`, `writing-a-graph-primitive.md`, plus architecture.md's extension-model subsection) cover the surface. A separate reference page is reconsidered if the how-to guides leave gaps.

## Key decisions in effect

| Decision | Reference |
|---|---|
| Declarative `WorkflowSpec` is the primary external authoring surface | ADR-0008 |
| `register(name, build_fn)` is preserved as the documented escape hatch (Tier 4) | ADR-0008 |
| Extensibility is a core capability, not a fallback — every tier has a guide | ADR-0008 §Extension model + §Documentation surface |
| KDR-004 (validator pairing) becomes a construction invariant for `LLMStep` | ADR-0008 + M19 T01 + T02 |
| KDR-006 (three-bucket retry) becomes a step-config field on `LLMStep` | ADR-0008 + M19 T01 |
| KDR-013 (user code is user-owned) — boundary shifts: specs are data, custom step types are code | ADR-0008 + M19 T07 |
| `RunWorkflowOutput.artifact` is the canonical artefact field; `plan` is a deprecation alias through 0.2.x | ADR-0008 + M19 T03 |
| Documentation surface is non-skippable; a doc gap at any tier is a regression | ADR-0008 §Documentation surface |
| New in-tree `summarize` workflow ships as the spec-API proof point; planner + slice_refactor ports deferred per locked H2 + Q5 (both have the M8/M10 fault-tolerance overlay) | M19 T04 + §Decisions item 4 |
| `MCP wire shape` unchanged | KDR-002 + KDR-008 preserved |

## Task order (provisional — refined by `/clean-tasks`)

| # | Task | Kind | Depends on |
|---|---|---|---|
| 01 | [`WorkflowSpec` + step-type taxonomy + custom-step extension hook + `register_workflow` entry point](task_01_workflow_spec.md) | code + test | — |
| 02 | [Spec → `StateGraph` compiler — synthesises state class, edges, hooks; pairs validators by construction](task_02_compiler.md) | code + test | T01 |
| 03 | [Result-shape correctness: artefact-field bug fix + `plan` → `artifact` rename with deprecation alias (folded from M18 T01)](task_03_result_shape.md) | code + test | — (independent of T01/T02) | ✅ Implemented (2026-04-26) |
| 04 | [Ship `summarize` workflow as in-tree spec-API proof point + wire-level e2e verification](task_04_summarize_proof_point.md) | code + test | T01 + T02 + T03 | ✅ Implemented (2026-04-26) |
| 05 | [Rewrite `docs/writing-a-workflow.md` declarative-first (Tier 1 + Tier 2)](task_05_writing_workflow_rewrite.md) | doc | T01 + T03 |
| 06 | [New `docs/writing-a-custom-step.md` (Tier 3 dedicated guide) + `compile_step_in_isolation` testing fixture](task_06_writing_custom_step.md) | doc + code (fixture) | T01 |
| 07 | [Four-tier framing across `architecture.md`, `README.md`, `writing-a-graph-primitive.md` + KDR table updates + Q5 deferral re-open trigger in `nice_to_have.md`](task_07_extension_model_propagation.md) | doc | T05 + T06 (so the cross-links land) |
| 08 | [Milestone close-out + 0.3.0 publish ceremony](task_08_milestone_closeout.md) | release | T01–T07 |

**Eight tasks** (was nine; the slice_refactor port that would have been T05 is deferred per locked Q5 — see §Decisions item 4). Task 03 (the bug fix + rename) is independent of the spec-API work and can run in parallel with T01/T02. T04 (`summarize` workflow ship + `aiw run --input KEY=VALUE` extension per locked H1) is the in-tree proof point. T05–T07 are the documentation surface; T07 bundles the architecture + README + primitive-doc alignment + the Q5/H2 re-open trigger because the four-tier framing lands consistently across those surfaces at once (per locked Q2).

## Dependencies

- **M16 Task 01 (external workflow module discovery, 0.2.0) — precondition.** The dotted-path discovery surface is preserved by ADR-0008; M19's spec API composes over it. Without M16, there are no external authors to write declarative specs for.
- **ADR-0008 — locked precondition (2026-04-26).** The decision record this milestone executes.
- **M14 (MCP HTTP transport) — composes over.** The wire shape is unchanged; spec API works identically over stdio + HTTP.
- **M10 (Ollama fault-tolerance hardening) — independent and on hold.** M10 is currently spec-clean / pending-implement (per `project_m10_specs_clean_pending_implement.md` memory). M10's planned `nice_to_have.md` slot range was §23–§27 at draft time; per locked Q1 (§Decisions item 1), M19 takes one slot at the next-free section (currently §23 — T07's slice_refactor-shape patterns parking-lot entry); M10's T05 re-greps at thaw and picks the next-free range after M19's one entry lands. M10's existing slot-drift defensive clause covers the small adjustment.
- **M15 (tier overlay) — independent.** M15 introduces user-overlay tier-config semantics; M19 documents the existing `<workflow>_tier_registry()` helper unchanged. M15 lands separately.
- **M17 (scaffold workflow meta-workflow) — independent and forward-shaped by M19.** Post-M19, "generated workflow source" naturally means a `WorkflowSpec`. M17's eventual surface is easier to author against the declarative API; M19 does not pre-build M17.

## Decisions (locked 2026-04-26)

1. **`nice_to_have.md` slot — α.** M19 takes **one slot** (the slice_refactor-shape patterns parking-lot entry from T07 Deliverable 5; the other anticipated forward-deferrals listed in §Propagation status are candidates, not committed M19 entries) at the next-free slot, currently §23. When M10 thaws, its T05 re-greps and picks the next-free slot after M19 lands. M10's existing slot-drift defensive clause handles the small adjustment.
2. **T07 granularity — bundle.** Four-tier framing across `architecture.md` + `README.md` + `writing-a-graph-primitive.md` + `nice_to_have.md` (the Q5 re-open trigger) lands as one coordinated task (T07) to avoid landing a `README.md` pointer before the `architecture.md` section it references exists.
3. **In-tree workflow compatibility shim posture — moot (per H2 lock).** Originally Q3 was about preserving compatibility shims for planner's module-level public exports after porting; under the H2 lock both planner and slice_refactor stay on their existing `register(name, build_fn)` registrations unchanged, so there is nothing to shim. The compatibility-shim discussion re-opens if the locked Q5 + H2 re-open trigger fires and a future milestone ports either workflow.
4. **planner + slice_refactor ports — both deferred (Q5 + H2).** Originally Q5 deferred only slice_refactor on the assumption that planner was the simpler proof point; analyzer round 2 (2026-04-26) revealed planner has the same M8/M10 fault-tolerance overlay (`wrap_with_error_handler`, `build_ollama_fallback_gate`, `CircuitOpen`-aware conditional routing, `planner_hard_stop` terminal, post-gate artifact storage-write — `planner.py:455-682`). T01's five built-in step types cannot express conditional routing or distinct terminal nodes. **Both workflows stay on their existing `register(name, build_fn)` escape-hatch registrations through 0.3.x.** Combined re-open trigger recorded by T07 in `nice_to_have.md`: *"When a second external workflow with conditional routing or sub-graph composition wants to use the spec API, file a milestone proposal for taxonomy extension."* M19's in-tree spec-API proof point is the new `summarize` workflow (T04 — H2 lock) — see item 5 below. The H2 framing: ship a new in-tree workflow that demonstrates the simplest realistic shape rather than fight the existing-workflow ports; one example (`summarize`) proves the spec compiles + dispatches; the existing complex workflows wait for external mileage to surface what taxonomy extensions actually generalise.
5. **Spec-API design choices — locked 2026-04-26 after analyzer round 1:** (Q1) `RetryPolicy` is re-exported from `ai_workflows.primitives.retry` (no parallel spec class). (Q2) `LLMStep` supports both `prompt_fn: Callable[[dict], tuple[str | None, list[dict]]]` (advanced; matches existing codebase contract) and `prompt_template: str` (Tier 1 sugar; `str.format()`-only — no Jinja, no f-string evaluation, no callbacks); cross-field validator with explicit error message ensures exactly one is set. (Q3) `WorkflowSpec.tiers` is required non-None; every `LLMStep.tier` must appear in `spec.tiers` at registration time; typo'd tier names raise with explicit error message naming offending tier + available tier set. (Q4) `Step` base class default `compile()` wraps `self.execute()`; custom-step authors typically implement only `execute(state) -> dict`; the `compile()` upgrade-path is documented in T06 for fan-out / sub-graph / conditional cases.
6. **Smaller decisions:** (M4) `compile_step_in_isolation` testing fixture ships as part of T06 (~30 lines + ~20 lines of fixture tests); no Builder hedge. (M8) Architecture.md §"Extension model" placement is Builder's choice at implement time among three reasonable locations (between §3+§4, between §7+§8, or appended at end-of-document). (M10) If T04's `summarize` workflow surfaces a step-taxonomy gap, **stop and ask the user** — H2 explicitly rejected option γ (extending the taxonomy now); `summarize` is designed to fit inside the five built-ins as-is.

7. **H2 — planner-port unsatisfiability discovered, summarize substituted (analyzer round 2 — 2026-04-26).** Round 2 verified that `planner.py:455-682` has the same M8/M10 fault-tolerance overlay slice_refactor has, making T04's original "port planner" framing unsatisfiable inside T01's five built-in step types. Three options surfaced: α (defer planner port too — no in-tree proof point; spec API ships unproven), β (synthetic in-tree proof point — author a new minimal workflow that uses only the spec API), γ (extend taxonomy now — undo Q5, expand scope substantially). **Locked β with refinements:** ship `summarize` (not `echo` — genuinely useful, exercises `LLMStep` + `ValidateStep`, doubles as T05's worked-doc example) under `ai_workflows/workflows/summarize.py` (not `tests/` — the dogfood claim only holds if it's a real shipped workflow). T04's deliverable shape: new `summarize.py` + new `tests/workflows/test_summarize.py` (5 hermetic tests via `StubLLMAdapter`) + new `tests/integration/test_spec_api_e2e.py` (originally 2 wire-level tests — CLI via `CliRunner` + MCP via `fastmcp.Client`; expanded to 5 tests post-locked-H1 to also cover the new `--input KEY=VALUE` path, help-text rendering, and planner-flag-conflict-raises). The wire-level proof through both surfaces is load-bearing — α was rejected because shipping a brand-new authoring surface with no wire-level integration test = first external user becomes the integration test. γ was rejected because the M8/M10 overlay items are not general patterns (they're framework-specific provider-failure handling); promoting them to built-in step types would bake provider concerns into the public taxonomy and ship 0.3.0 with primitives external consumers don't use. The `summarize` framing keeps M19 honest: the spec API is proven against a new workflow that demonstrates the simplest realistic shape; planner + slice_refactor wait for the locked Q5 + H2 re-open trigger.

## Carry-over from prior milestones

- **M18 T01 (artefact-loss bug fix + `plan` → `artifact` rename) folded into M19 T03.** ADR-0008 records the fold-in; M18 directory deleted 2026-04-26. No further M18 carry-over.
- **No carry-over from M16 (closed cleanly at 0.2.0) or M10 (still on hold; specs clean per `project_m10_specs_clean_pending_implement.md` memory).**

## Propagation status

Filled in at audit time. Anticipated forward-deferrals:

- **Spec API extensions for slice_refactor-shape patterns** — `nice_to_have.md` entry written by T07. Trigger: a second external workflow with conditional routing or sub-graph composition wants to use the spec API. (See §Decisions item 4 for the full re-open trigger language.)
- **`register_workflow_from_yaml(path)`** — `nice_to_have.md` candidate. Trigger: a consumer surfaces a non-Python authoring environment (no-code tool, declarative-config-only deployment).
- **M17 (`scaffold_workflow`) onto spec API** — captured under M17's existing scope; M19 ships the surface M17 will eventually generate against.
- **`capture_evals` on MCP `RunWorkflowInput`** — `nice_to_have.md` candidate carried forward from the M18 draft. Trigger: a downstream MCP consumer asks for eval capture from the MCP surface (CS-300 currently uses CLI for this).
- **`plan` field alias removal at 1.0** — captured in CHANGELOG `### Deprecated` notice; one-time triggered by the 1.0 release.
- **Custom-step graduation candidates** — T04's `summarize` workflow only uses built-in step types (`LLMStep` + `ValidateStep`); no custom step types are authored in M19. Post-M19, any custom step type a downstream consumer (or a future in-tree workflow) authors that proves usable across more than one workflow lands as a built-in in a future minor per ADR-0008's graduation pattern.

## Issues

Land under [issues/](issues/) after each task's first audit.

## Release

**0.3.0 minor bump.** The introduction of a new primary authoring surface (`register_workflow(WorkflowSpec)`) + the repositioning of the existing one (`register(name, build_fn)`) as the documented escape hatch is substantial enough to warrant the bump even though both APIs coexist. The artefact-field bug fix + `plan` field deprecation alias compose into the same release.

The release ritual mirrors 0.2.0: edit code + tests on `design_branch` → commit → cherry-pick code/tests/pyproject to `main` → add user-facing docs/README/CHANGELOG on `main` → `uv run pytest` + `uv run lint-imports` + `uv run ruff check` → `bash scripts/release_smoke.sh` → `uv build` + `uv publish` → poll simple-index for CDN propagation → live smoke from `/tmp` (`uvx --refresh --from jmdl-ai-workflows==0.3.0 aiw version`) → stamp `### Published` footer on `main` → push both branches. `uv cache clean jmdl-ai-workflows` between publish and live smoke per the established uvx-cache mitigation.
