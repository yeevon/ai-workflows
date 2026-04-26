# ADR-0008 — Declarative authoring surface for external workflows

**Status:** Accepted (2026-04-26).
**Decision owner:** [M19 README](../phases/milestone_19_declarative_surface/README.md) + tasks (forthcoming; this ADR drafted before M19's task breakout per project discipline that load-bearing surface decisions are ADR-first).
**References:** [ADR-0007 (user-owned code contract for external workflow modules)](0007_user_owned_code_contract.md) — the discovery surface this ADR composes over · [KDR-013](../architecture.md) — restated under this ADR (the boundary shifts; the principle holds) · [KDR-004 (validator pairing)](../architecture.md) — strengthened from convention to construction invariant · [M16 README](../phases/milestone_16_external_workflows/README.md) — the surface this ADR partially supersedes for external authors · CS-300 pre-flight smoke report 2026-04-25 (the trigger; delivered out-of-band) · in-conversation hostile re-read 2026-04-26 (12-finding contract-surface inventory).

## Context

[M16 Task 01](../phases/milestone_16_external_workflows/task_01_external_workflow_modules.md) shipped at `0.2.0` (2026-04-24). [ADR-0007](0007_user_owned_code_contract.md) records the discovery contract: a downstream consumer registers a workflow module via dotted Python path (`AIW_EXTRA_WORKFLOW_MODULES` or `--workflow-module`), and the module's top-level `register("name", build_fn)` call lands the workflow in the registry. `build_fn` returns a LangGraph `StateGraph`.

CS-300 (the first downstream consumer) ran a pre-flight smoke against `jmdl-ai-workflows==0.2.0` on 2026-04-25 to verify that a stub `cs300.workflows.question_gen` round-trips end-to-end through `aiw-mcp`. The smoke succeeded after **four iterations**, each iteration a contract gap CS-300 had to discover by reading framework source:

1. The MCP `run_workflow` tool wraps args under `{"payload": {...}}` per FastMCP convention — undocumented.
2. External workflow modules must export an `initial_state(run_id, inputs) -> dict` callable (or a class literally named `PlannerInput`) — undocumented.
3. `build_fn` must return the **uncompiled** `StateGraph`; dispatch calls `.compile(checkpointer=...)` itself — undocumented; the in-tree `docs/writing-a-workflow.md` worked example *contradicts* this rule.
4. An optional `FINAL_STATE_KEY` constant controls completion detection but the response field that surfaces the artefact is hardcoded to `final.get("plan")` regardless — a real bug that silently drops the artefact for any workflow whose terminal key isn't `"plan"`.

A 2026-04-26 hostile re-read of the full contract surface widened the inventory to **12 distinct findings**: 2 runtime bugs, 2 doc-vs-source contradictions, 5 documentation gaps (`initial_state`, `FINAL_STATE_KEY`, `TERMINAL_GATE_ID`, FastMCP `payload` wrapping, `capture_evals` MCP asymmetry), 1 public-API name leak (`RunWorkflowOutput.plan` bakes the `planner` workflow's terminal-artefact name into the schema for every external workflow), and 2 cross-reference-rot items.

The patch path was scoped as M18 (drafted 2026-04-26, then withdrawn — see "Rejected alternatives" below): a 5-task milestone documenting every hook + fixing the artefact bug + renaming `plan` → `artifact` with a deprecation alias. Drafting M18 surfaced the load-bearing concern this ADR addresses:

> **Even after the M18 patches, the authoring surface remains ~25 lines of LangGraph mechanics for "call a thing, return a thing."** TypedDict state class + builder function + node functions + START/END wiring + `initial_state` hook + `FINAL_STATE_KEY` constant + register call + (optional) tier-registry helper. The consumer is being asked to be a LangGraph author — not a workflow author.

The framework's positioning ("a declarative LangGraph composition layer for orchestration workflows") is incoherent with that contract: if the consumer's primary skill is LangGraph, what does the framework add beyond `register(name, build_fn)` discovery and an MCP wrapper? The user's framing in conversation, and the framing this ADR adopts: *having consumers deal with LangGraph directly makes the framework feel pointless.*

Two tensions shape the decision:

1. **What is the unit of authoring?** A LangGraph `StateGraph` (status quo) vs. a declarative spec object the framework compiles into a `StateGraph` (proposed).
2. **What does "user-owned code" mean post-decision?** ADR-0007 declared workflow modules are user code; this ADR shifts that boundary because workflow *specs* are data, not code.

## Decision

### The primary external authoring surface is declarative

External workflow authors write a `WorkflowSpec` — a pydantic data object that declares the workflow's name, input schema, output schema, and an ordered list of `Step` instances composed from framework-provided step types. The framework owns the `StateGraph`-synthesis at registration time.

```python
# What an external author actually writes — no LangGraph anywhere:
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
    steps=[
        LLMStep(
            tier="planner-explorer",
            prompt_template="Summarize the following text in at most {max_words} words:\n\n{text}",
            response_format=SummarizeOutput,
        ),
    ],
))
```

The consumer never imports `langgraph`, never instantiates `StateGraph`, never wires `START`/`END`/edges, never authors `initial_state` / `FINAL_STATE_KEY` / `TERMINAL_GATE_ID` constants. Those are framework concerns and become invisible.

### Step taxonomy — first-class framework primitives

The shipped step types cover the orchestration shapes the framework already supports through its graph-layer primitives. Each step type compiles to one or more LangGraph nodes + the edges connecting them.

| Step type | Compiles to | Purpose |
|---|---|---|
| `LLMStep` | `TieredNode` + paired `ValidatorNode` (KDR-004 by construction) + `RetryingEdge` (KDR-006) | Single tier-routed LLM call with validated response. The most common shape. |
| `ValidateStep` | `ValidatorNode` standalone | Pydantic validation of state without an LLM call (e.g. validating a transformation's output). |
| `GateStep` | `HumanGate` | Pause-and-resume point with persisted checkpoint. Names the gate ID; framework owns the wire-up. |
| `TransformStep` | Plain LangGraph node wrapping a consumer-provided async callable | Pure-Python state transformations the consumer authors. The escape hatch within the declarative surface. |
| `FanOutStep` | `Send`-pattern parallel dispatch + sub-spec compilation | The `slice_refactor` parallel-branch shape. Sub-spec is itself a `WorkflowSpec` (or a sub-step list). |

### Extension model — extensibility is a first-class capability

The framework's value proposition is **not** "use the steps we ship and stay inside the lines." It is **"engage at the right level of complexity for your workflow, and we meet you there with a guide."** Extension and customisation are core features, not fallbacks. Authors progress through four tiers as their needs grow; each tier has a dedicated guide that teaches it with worked examples, and the framework promises that descending a tier never forces the author to reverse-engineer the framework source.

| Tier | What the author does | Worked example |
|---|---|---|
| **1 — Compose** | Combine built-in step types into a `WorkflowSpec`. The declarative happy path. | The `summarize` example earlier in this ADR. |
| **2 — Parameterise** | Configure built-in steps: retry policy, validator override, gate-rejection behaviour, tier choice. | `LLMStep(tier="planner-synth", retry=RetryPolicy(transient_max=5, deterministic_max=2))`. |
| **3 — Author a custom step type** | Subclass the framework's `Step` base when no built-in covers the need. The custom step is user-owned Python (KDR-013) but composes with built-ins indistinguishably from the framework's own step types. | The `WebFetchStep` example below. |
| **4 — Escape to LangGraph** | Drop to `register(name, build_fn)` and author the `StateGraph` directly. Reserved for genuinely non-standard topologies (dynamic edge conditions, novel control flow, experimental graph shapes the linear step list cannot express). | The current M16-shipped surface, preserved unchanged. |

**Tier 3 worked example** — the load-bearing path for downstream consumers extending the framework:

```python
from ai_workflows.workflows import Step, register_workflow, WorkflowSpec, LLMStep
import httpx


class WebFetchStep(Step):
    """Fetches a URL and stores the response body in state."""
    url_field: str            # state field holding the URL
    output_field: str         # state field to write the response body to

    async def execute(self, state: dict) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(state[self.url_field])
            response.raise_for_status()
        return {self.output_field: response.text}


register_workflow(WorkflowSpec(
    name="summarize_url",
    input_schema=SummarizeUrlInput,                          # pydantic, defined elsewhere
    output_schema=SummarizeOutput,
    steps=[
        WebFetchStep(url_field="url", output_field="page_text"),
        LLMStep(
            tier="planner-explorer",
            prompt_template="Summarize the following:\n\n{page_text}",
            response_format=SummarizeOutput,
        ),
    ],
))
```

The custom step is a pydantic model subclassing `Step`; it provides an `execute(state) -> dict` coroutine, the framework compiles it into the `StateGraph` like any built-in. Consumers compose custom and built-in steps freely — the compiler does not distinguish between them.

**Out of scope for external authors: graph-layer primitives.** `TieredNode`, `ValidatorNode`, `HumanGate`, `RetryingEdge`, the cost-tracking callback, and the `SqliteSaver` checkpointer are framework-internal. Extending them externally would dissolve the four-layer rule (`primitives → graph → workflows → surfaces`). External needs at this depth route through Tier 3 (wrap the behaviour in a custom step) or surface as feature requests; only framework contributors author new graph-layer primitives, and they do so through `docs/writing-a-graph-primitive.md`.

**Graduation path — Tier 3 → built-in step type, or Tier 3 → graph primitive.** When a custom step pattern proves broadly useful — appearing in two or more downstream workflows or in-tree workflows — the framework absorbs it as a built-in step in a future minor. When the underlying *wiring* (not just the step semantics) is reusable across step types, it graduates to the graph layer per the heuristic in `docs/writing-a-graph-primitive.md`. This graduation pattern is the framework's organic-growth mechanism; external authors get rewarded for surfacing useful patterns by not having to maintain them forever.

### Documentation surface — every tier has a guide, and a strongly-referenced entry point

Extensibility-as-a-core-capability is only credible if the docs meet authors wherever they enter. M19's documentation deliverable is **non-skippable**: each tier gets a dedicated guide with worked examples (not just reference material), and the framework's identity-level docs (`README.md`, `architecture.md`) make the four-tier extension model visible from the front page.

| Surface | Tier coverage | M19 disposition |
|---|---|---|
| [`docs/writing-a-workflow.md`](../../docs/writing-a-workflow.md) | Tier 1 + Tier 2 | Rewritten declarative-first; teaches `WorkflowSpec` composition + step parameterisation; brief Tier 3 mention with link to the custom-step guide; brief Tier 4 mention with link to the graph-primitive guide for the "you've outgrown the spec" exit. |
| `docs/writing-a-custom-step.md` (new in M19) | Tier 3 | Dedicated guide for authoring custom step types. `Step` base class contract, `execute` coroutine, state-channel conventions, testing patterns (the framework provides a fixture for compiling-a-spec-in-isolation), graduation hints (when a custom step pattern is ripe for promotion to a built-in or a graph primitive). The load-bearing guide for downstream extension. |
| [`docs/writing-a-graph-primitive.md`](../../docs/writing-a-graph-primitive.md) | Tier 4 + framework-internal extension | Existing doc; aligned with the four-tier framing in M19. The "if a wiring pattern appears in 2+ workflows, promote" heuristic restated as the Tier 3 → graph-layer graduation path. Audience is framework contributors (not external consumers); doc makes that audience explicit. |
| [`design_docs/architecture.md`](../../design_docs/architecture.md) | All tiers | New §"Extension model" subsection (~one page) makes the four-tier framing part of the architecture-of-record. KDR table updated where extension semantics shift load-bearing rules (KDR-004 by-construction-not-convention; KDR-013 boundary shift). |
| [`README.md`](../../README.md) | All tiers (entry point only) | "Extending ai-workflows" section near the top of the README with one-paragraph framing per tier and a strong pointer table to each guide. Extensibility surfaced as a core value proposition, not buried under "advanced usage." |

Each guide must include at least one worked example end-to-end (not a fragment); each guide must compile under `uv run pytest --doctest-modules` if it contains executable snippets; each guide must cross-reference the adjacent tiers so authors landing at the wrong level can find the right one in one click.

The framework's promise: **if you're going down to a deeper tier of complexity, there is a guide that meets you there with worked examples.** A doc gap at any tier is a regression on the framework's value proposition.

### Retry, validation, and gate composition become spec configuration

The current authoring surface requires manual wiring of `RetryingEdge` (KDR-006), `ValidatorNode` (KDR-004), and `HumanGate` (KDR-009). Under this ADR, those become step-configuration fields:

- `LLMStep(retry=RetryPolicy(...))` — three-bucket retry semantics preserved internally; consumer chooses the policy, not the wiring.
- `LLMStep(response_format=PydanticModel)` — validator is automatically paired by the compiler. Authors *cannot* write an unvalidated `LLMStep` through the spec API; KDR-004 graduates from convention-enforced-by-review to invariant-enforced-by-construction.
- `GateStep(id="...", on_reject=...)` — gate behaviour parameterised on the step, not on graph topology.

### `register(name, build_fn)` becomes the documented escape hatch

The current Python-builder API is preserved for advanced workflows whose graph topology the step taxonomy can't express (custom edge conditions, non-trivial control flow, experimental graph shapes). It is documented honestly as the advanced path — *not* as the recommended starting point. New external authors are pointed at `register_workflow(WorkflowSpec)`; the escape-hatch surface keeps its existing tests and behaviour.

This means the framework ships **two registration entry points** post-M19:

- `register_workflow(spec: WorkflowSpec)` — primary. Compiles spec → `StateGraph` → underlying `register(name, build_fn)`.
- `register(name, builder)` — escape hatch. Unchanged from today.

Both populate the same `_REGISTRY`; downstream surfaces (CLI, MCP) cannot tell them apart.

## Rejected alternatives

### Stay LangGraph-native, document the contract better (the M18 path)

Drafted as M18 on 2026-04-26: 5 tasks documenting every hook (`initial_state`, `FINAL_STATE_KEY`, `TERMINAL_GATE_ID`, `<workflow>_tier_registry`), fixing the artefact-loss bug, renaming `RunWorkflowOutput.plan` → `artifact` with a deprecation alias. Withdrawn on the same day.

Rejected because comprehensive docs don't change the underlying problem: the consumer is doing LangGraph orchestration work for which the framework adds no marginal value. Every doc-task in M18 (`docs/writing-a-workflow.md` rewrite, new `docs/external-workflow-contract.md`) would teach a contract this ADR deprecates. The M18 artefact-loss bug fix (T01) is folded into M19 as a precursor task; the rest of M18 is obsoleted.

**Re-opens if:** the declarative surface proves insufficient for a class of workflows we discover only post-M19. Falling back to "document the heavy path well" remains feasible.

### `register_simple(name, fn)` thin helper

Discussed in conversation as B-narrow / B-wide variants. A thin wrapper that takes a plain async function and synthesizes the single-node StateGraph + `initial_state` + `FINAL_STATE_KEY`.

Rejected because:

- B-narrow (no LLM wiring) saves boilerplate but loses framework value: the consumer calls LLMs directly outside the framework, bypassing tier routing, validation, retry classification, and cost tracking. The framework is reduced to checkpointing + run registry + MCP wrapping.
- B-wide (with `tier=` / `prompt_template=` / `output_model=` parameters) is closer but is fundamentally still inside the "Python-builder-with-helpers" frame. The contract is flatter, not different in shape.
- Neither addresses the identity concern: the framework is still a wrapper over LangGraph from the consumer's perspective.

**Re-opens if:** the declarative spec API turns out to be over-engineered for the long tail of workflows that are genuinely "call one LLM and return." A `register_simple` could land cheaply as sugar over the spec API.

### Class-based DSL (`class QuestionGen(Workflow): ...`)

A pattern common in some frameworks (Prefect, Airflow). Rejected because:

- Pydantic data classes are more inspectable, more serializable (a future YAML/JSON layer is trivial), and align with the existing `RunWorkflowInput`/`RunWorkflowOutput` schemas the MCP surface uses.
- Class-based DSLs require consumers to learn an inheritance idiom (which methods are hooks, which are concrete, what the metaclass enforces). Pydantic models require none of that.
- LangGraph's `StateGraph` is itself imperative-builder-style — wrapping it in a class hierarchy would compose oddly.

**Re-opens if:** consumers ask for the discoverability that class-based APIs offer (IDE autocomplete on workflow methods, `dir()`-based introspection). Pydantic specs already satisfy most of that through field discovery.

### YAML/JSON-only declarative surface

Tempting because it appears even more declarative than a Python pydantic model. Rejected because:

- Custom step types need Python (the consumer's callable must run in-process). YAML can't describe them; the surface would split into "spec-in-YAML for simple cases, Python for custom steps" — two authoring paths instead of one.
- Pydantic specs are *already* serializable to YAML/JSON. A future `register_workflow_from_yaml(path)` layer can land cheaply on top of this ADR if a consumer surfaces the use case.
- IDE support (autocomplete, type checking) is far better for pydantic models than for YAML.

**Re-opens if:** a consumer surfaces a non-Python authoring environment (e.g. a no-code tool emitting workflow specs). Composes over this ADR cleanly.

### Defer entirely — ship M18 patches as 0.2.1, design declarative surface in 0.4.0+

Rejected because:

- M18's documentation tasks would teach a contract this ADR deprecates. Wasted user trust + migration cost when the deprecation lands.
- CS-300 is the active downstream consumer; the longer the heavy contract is the documented path, the more migration work piles up when the declarative surface lands.
- The framework is being positioned (in `README.md`, in pitch material) as a declarative orchestration layer. Shipping the declarative surface late means the positioning is aspirational for that long.

The M18 artefact-loss bug fix (T01) is real correctness work; it folds into M19 as a precursor task rather than shipping standalone. M18 directory is obsoleted.

**Re-opens if:** M19 turns out to take longer than expected and the artefact-loss bug starts affecting real downstream consumers (currently latent — only triggers for workflows with `FINAL_STATE_KEY != "plan"`, and CS-300 is mid-prototype with no production exposure). Cherry-picking T01 to a 0.2.1 hotfix remains cheap.

### Replace LangGraph entirely with a custom orchestrator

The most aggressive option — make `WorkflowSpec` the runtime model with no LangGraph underneath. Rejected because:

- LangGraph supplies SqliteSaver / checkpoint / resume / interrupt / Send-pattern fan-out — all load-bearing for the framework. Re-implementing that surface would be a multi-milestone undertaking with no marginal value.
- KDR-009 commits to LangGraph's `SqliteSaver` for checkpoints. Replacing the orchestrator dissolves that KDR.
- The compile-from-spec-to-StateGraph layer is the right boundary: declarative authoring on top, LangGraph battle-tested orchestration underneath, no leakage in either direction.

**Re-opens if:** LangGraph's roadmap or licensing changes incompatibly. Not on any current radar.

## Consequences

- **Framework identity becomes coherent.** ai-workflows is a declarative orchestration surface; LangGraph is an internal implementation detail of the compile step. Marketing positioning, documentation framing, and the actual consumer experience align.
- **In-tree workflows must port to the declarative surface as M19 proof points.** `planner` (the simpler one — two-phase explorer/synth) and `slice_refactor` (the harder one — parallel fan-out, gate composition, retry tuning) both rewrite as `WorkflowSpec` instances. This stress-tests the spec for sufficiency: if `slice_refactor` cannot be expressed in the spec API, the step taxonomy is incomplete and the gap is identified before external consumers hit it.
- **Two registration entry points coexist.** Authors choose `register_workflow(spec)` (primary) or `register(name, builder)` (escape hatch). Both populate `_REGISTRY`. Downstream surfaces are unaffected; tests for both paths run side by side.
- **KDR-004 graduates from convention to construction invariant.** `LLMStep`-with-`response_format` always pairs validation; consumers cannot author an unvalidated LLM call through the spec. The escape hatch retains the convention-enforced-by-review status quo.
- **KDR-006 (three-bucket retry) becomes step-config.** Retry policies become structured fields on `LLMStep`. The `RetryingEdge` mechanism is preserved internally; consumers stop wiring it manually.
- **KDR-009 (SqliteSaver checkpoints) unchanged.** The compiled `StateGraph` underneath uses LangGraph's `SqliteSaver` exactly as today. Spec authors are oblivious to checkpointing.
- **KDR-013 ("user code is user-owned") restated, scope shifted.** Workflow specs are *data* — no Python privileges to worry about. Custom step types are *code* — still user-owned, still surfaced-not-policed. The risk boundary moves: data-by-default, code-when-customizing. ADR-0007's "framework does not lint, test, or sandbox imported user modules" applies to the custom-step extension hook only post-M19.
- **`RunWorkflowOutput` schema redesigned.** The `plan` field name leaks the planner's domain. M19 renames to `artifact` (the rename M18 was originally going to ship); the deprecation-alias decision moves to M19's scope. Hardcoded `final.get("plan")` → `final.get(final_state_key)` (the M18 T01 bug fix) lands as a precursor task in M19.
- **`docs/writing-a-workflow.md` rewrites declarative-first.** Heavy-path content moves to a single "advanced authoring (escape hatch)" subsection. New `docs/external-workflow-contract.md` becomes the canonical reference for spec authors.
- **Migration window for any pre-M19 external consumers.** None known — CS-300 is the only downstream consumer and is still pre-production. M19 ships with a CHANGELOG `### Changed` entry naming the new primary surface; the escape hatch absorbs anyone who shipped against the M16 contract.
- **M18 obsoleted.** The `design_docs/phases/milestone_18_workflow_contract/` README is sunk cost beyond T01's bug-fix framing, which folds into M19. The M18 directory's disposition (delete vs. archive vs. leave for the conversation log) is a post-ADR housekeeping decision.

## Implementation pointers

- New module: `ai_workflows/workflows/spec.py` — `WorkflowSpec`, step-type taxonomy (`Step` base + `LLMStep` / `ValidateStep` / `GateStep` / `TransformStep` / `FanOutStep`), `register_workflow` entry point, custom-step extension hook contract.
- New module: `ai_workflows/workflows/_compiler.py` — spec → `StateGraph` synthesis. Owns the wiring previously asked of consumers (state class derivation, START/END edges, `initial_state` hook synthesis, `FINAL_STATE_KEY` resolution).
- Migration: `ai_workflows/workflows/planner.py` and `ai_workflows/workflows/slice_refactor.py` rewritten as `WorkflowSpec` instances. Existing module-level public exports preserved as compatibility shims for the in-tree surface.
- Bug fix (folded from M18 T01): `ai_workflows/workflows/_dispatch.py` lines 721, 781, 977, 1034, 1048 — `final.get("plan")` → `final.get(final_state_key)`. Hermetic regression test: external workflow with `FINAL_STATE_KEY = "questions"` round-trips its terminal artefact through the response field.
- Schema rename (folded from M18): `ai_workflows/mcp/schemas.py` — `RunWorkflowOutput.artifact` (canonical) + `plan` (deprecation alias surfacing the same value through the 0.2.x line; removal target 1.0).
- Tests: `tests/workflows/test_spec.py` (spec model + step types), `tests/workflows/test_compiler.py` (synthesis correctness), `tests/workflows/test_planner_spec_migration.py` + `test_slice_refactor_spec_migration.py` (proof points). Existing `tests/workflows/test_planner.py` + `test_slice_refactor.py` rerun against the migrated workflows; behavioural equivalence is the migration acceptance criterion.
- Documentation surface (non-skippable; the four-tier extension model must be visible across all five surfaces — see §"Documentation surface" above for the full disposition table):
  - `docs/writing-a-workflow.md` — rewritten declarative-first; teaches Tier 1 (compose) + Tier 2 (parameterise); cross-links to Tier 3 + Tier 4 guides for authors who outgrow the happy path.
  - `docs/writing-a-custom-step.md` — **new in M19.** Tier 3 dedicated guide. `Step` base class contract, `execute` coroutine, state-channel conventions, testing patterns + framework-provided spec-compilation fixtures, graduation hints. Load-bearing guide for downstream consumers extending the framework.
  - `docs/writing-a-graph-primitive.md` — existing; aligned with Tier 4 + framework-internal-extension framing in M19. Audience clarified as framework contributors. Existing "promote when pattern appears in 2+ workflows" heuristic restated as the Tier 3 → graph-layer graduation path.
  - `design_docs/architecture.md` — new §"Extension model" subsection; KDR-004 + KDR-013 row updates reflecting strengthened/shifted contracts.
  - `README.md` — new "Extending ai-workflows" section near the top with one-paragraph framing per tier and pointer table to each guide; extensibility surfaced as a core value proposition.
  - `ai_workflows/workflows/__init__.py` module docstring — updated to reflect the dual registration entry points (`register_workflow` primary, `register` escape hatch) and link to the four-tier model in `architecture.md`.
- ADR cross-references: ADR-0007 status updated to "Accepted (discovery surface — composes with ADR-0008's authoring surface)"; the dotted-path discovery contract is preserved verbatim — only the *what* the consumer registers changes, not *how* discovery finds the registration.
- KDR table in `architecture.md §9` — KDR-004 + KDR-006 + KDR-013 rows updated to reflect the strengthened/shifted contracts.
