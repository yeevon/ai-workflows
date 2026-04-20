# ADR-0002 — Bare-typed pydantic schemas for LLM `response_format`

**Status:** Accepted (2026-04-20).
**Decision owner:** [M3 Task 07b](../phases/milestone_3_first_workflow/task_07b_planner_schema_simplify.md).
**References:** [architecture.md §4.2](../architecture.md) · [architecture.md §7](../architecture.md) · KDR-004 · KDR-007 · KDR-010.
**Supersedes:** nothing. First codification of a pattern that surfaced empirically during M3 T07a's live e2e.

## Context

M3 Task 07a wired `tiered_node(output_schema=PlannerPlan)` through to
LiteLLM's `response_format=` parameter, which the Gemini provider
translates into a native `responseSchema` on the
`generativelanguage.googleapis.com` call. On the first live retry run
after the initial e2e quota wait cleared, Gemini returned:

```
BadRequestError 400 — "schema produces a constraint that has too many
states for serving"
```

against `PlannerPlan.model_json_schema()`. The schema at the time
carried:

- `PlannerInput.goal: Field(min_length=1, max_length=2000)`
- `PlannerInput.context: Field(default="", max_length=8000)`
- `PlannerInput.max_steps: Field(default=10, ge=1, le=25)`
- `PlannerPlan.steps: Field(min_length=1, max_length=25)`
- `PlannerStep.index: Field(ge=1)`
- `PlannerStep.title: Field(min_length=1, max_length=120)`
- `PlannerStep.rationale: Field(min_length=1, max_length=2000)`
- `PlannerStep.actions: list[str] = Field(min_length=1, max_length=10)`
  with per-item `Field(min_length=1, max_length=500)`

and `model_config = {"extra": "forbid"}` on the outer model.

Gemini's structured-output pathway enforces a **complexity budget**
on the submitted `responseSchema`: a finite-state interpretation of
the combined constraint space. Nested array bounds multiply with
per-item string bounds multiply with integer `ge`/`le` bounds; the
product exceeds Gemini's serving threshold. The schema was valid
JSON Schema, valid pydantic, and would have been accepted by a
provider that ignored the annotations (e.g. OpenAI's structured
output) — but Gemini rejects it at admission time.

Three paths were offered to the user:

- **Path α (surgical):** strip `Field(...)` bounds from the schemas
  Gemini sees. Keep `extra="forbid"` (Gemini handles
  `additionalProperties: false`). Enforce bounds at caller surface
  (`PlannerInput.max_steps`) and via prompt text.
- **Path β (provider switch):** move the planner-synth tier to
  `gemini-2.5-pro`, which has a larger complexity budget.
- **Path γ (defer):** ship T07a without the live-run evidence AC;
  chase the schema question at M5.

User picked α. T07b shipped the schema trim; the live e2e converged
single-shot on both tiers in 11.67s.

This ADR codifies the underlying pattern so that the next LLM-backed
workflow (M5 multi-tier planner or M6 `slice_refactor`) does not
re-discover the wall empirically.

## Decision

**Pydantic models bound for an LLM `response_format` parameter
ship bare-typed.** Concretely:

1. No `Field(min_length=…)` / `Field(max_length=…)` on string or
   list fields that live in a response schema.
2. No `Field(ge=…)` / `Field(le=…)` / `Field(gt=…)` / `Field(lt=…)`
   on numeric fields in a response schema.
3. No per-item bounds on list elements in a response schema (the
   `list[Annotated[str, Field(...)]]` / `conlist(..., min_length=…)`
   shape is banned for response schemas).
4. `extra="forbid"` (closed-world `additionalProperties: false`) is
   **retained** — it is cheap on the budget and is the only thing
   that makes hallucinated keys surface as a `ValidationError` the
   `RetryingEdge` can route on (KDR-004).
5. Type annotations themselves are retained. `str`, `int`, `list[str]`,
   nested pydantic models, `Literal[...]`, `Enum` subclasses — all
   fine. Gemini's budget is about *constraint* state-space, not type
   richness.

**Runtime bounds live at the caller surface.** Concretely:

1. **Input-side pydantic models** (e.g. `PlannerInput`) retain their
   `Field(...)` bounds. These are never sent to an LLM as
   `response_format`; they are validated on the `aiw run` / MCP
   tool-call boundary and their values feed the prompt, not the
   response schema.
2. **Prompt text** enforces bounds the schema no longer expresses
   (e.g. "produce between 1 and `{max_steps}` steps"). The validator
   node paired with the LLM node (KDR-004) runs
   `schema.model_validate_json(response_text)` — type violations
   still raise, but bound violations become prompt-quality concerns,
   surfaced by the workflow's eval harness (M7) rather than by
   runtime parsing.
3. **Post-parse assertions** may be added at the validator node if a
   specific workflow has a hard invariant that must not escape —
   e.g. `assert 1 <= len(plan.steps) <= plan_input.max_steps`. These
   live in the validator, not in the schema.

**Scope of applicability.** The pattern applies to every pydantic
model passed as `output_schema=` to `tiered_node(...)` (i.e. every
model that becomes a LiteLLM `response_format`). MCP tool I/O models
([architecture.md §7](../architecture.md)) are **not** subject to
this rule — those are public-contract schemas bound by FastMCP for
JSON-RPC input validation; they never cross into `response_format`.

## Rationale

- **Provider portability is the architectural value at stake.**
  KDR-007 puts LiteLLM at the unified-adapter seam precisely so that
  the runtime can swap between Gemini, Qwen/Ollama, and any future
  provider without workflow changes. A schema pattern that happens
  to work on one provider's structured-output budget but breaks on
  another is an anti-portability pattern. Bare-typed schemas are the
  strictly lower-complexity choice; every provider that accepts the
  rich version accepts the bare one.
- **The validator-after-every-LLM-node rule (KDR-004) already owns
  semantic enforcement.** Bounds in the response schema are a
  defense-in-depth signal, not a primary enforcement point. Moving
  them to the validator / prompt / caller-input surface consolidates
  enforcement at the layer that was already going to parse the model
  output anyway.
- **Bounds in response schemas have perverse retry dynamics.** When
  a bound-violating response triggers a semantic retry, the model
  has to re-infer the bound from the schema on each pass. Prompt-
  expressed bounds ("1 to 25 steps") are more legible to the model
  than an embedded `maxItems: 25` that the provider may or may not
  surface in the error it returns. Semantic-retry budgets (KDR-006)
  are better spent on true hallucinations than on bound-guessing.
- **`extra="forbid"` is retained because its cost is negligible.**
  `additionalProperties: false` adds one boolean to the schema and
  surfaces hallucinated top-level keys (e.g. a wrapping
  `"disclaimer"` field) as a `ValidationError` the `RetryingEdge`
  routes as `RetryableSemantic`. Every provider tested accepts it;
  removing it would lose the single most useful closed-world signal.
- **The pattern is reversible per-provider if a workflow demands
  rich bounds.** A future tier-config option could carry a
  per-provider `strip_response_schema_bounds` flag driven by the
  provider's known budget. But that is a workflow-level complication
  introduced only when a concrete workflow needs it. Until then, the
  cheaper default is bare-typed everywhere.

## Consequences

- **Builder rule (enforced at audit).** Every Builder who writes a
  pydantic model that will become `response_format` (i.e. passed to
  `tiered_node(output_schema=...)`) ships it bare-typed. Auditor
  confirms via the design-drift check. Counter-example repo fixture
  sitting in [tests/workflows/test_planner_schemas.py](../../tests/workflows/test_planner_schemas.py)
  (`test_plannerplan_json_schema_has_no_state_space_bounds`) pins
  the pattern for the planner workflow; sibling workflows add the
  equivalent test for their own response models.
- **KDR-010 lands in [architecture.md §9](../architecture.md)** with
  this ADR cited as its source.
- **KDR-004 (validator after every LLM node) gains a sharper
  boundary.** The validator is the only layer responsible for
  semantic enforcement; the schema's job narrows to *shape*
  (closed-world type tree) and nothing more.
- **M5 multi-tier planner and M6 `slice_refactor` start from this
  pattern.** Neither milestone will re-discover the Gemini wall on a
  fresh workflow. Each workflow's response-model tests include the
  bare-typed assertion.
- **Eval harness (M7) inherits responsibility** for catching
  regression where a prompt-expressed bound drifts (e.g. the planner
  starts emitting 40-step plans because the prompt wording weakened).
  The eval harness is the right surface for bound-quality signals;
  the schema is not.
- **No migration.** T07b already performed the trim for the planner;
  M1/M2 primitives carry no response-schema models (they predate
  structured output being wired). `CostTracker`, `Storage`, and
  `TieredNode` signatures are unaffected.

## References

- [architecture.md §4.2](../architecture.md) — graph-layer adapters
  (`TieredNode`, `ValidatorNode`, `RetryingEdge`).
- [architecture.md §6](../architecture.md) — LiteLLM as unified
  provider adapter (KDR-007).
- [architecture.md §7](../architecture.md) — boundaries and contracts.
- [architecture.md §8.2](../architecture.md) — error handling / the
  three-bucket retry taxonomy (KDR-006) that the validator feeds.
- KDR-004 — validator-node-after-every-LLM-node.
- KDR-007 — LiteLLM is the unified adapter.
- KDR-010 — this ADR's codified form in the KDR index.
- [M3 Task 07a](../phases/milestone_3_first_workflow/task_07a_planner_structured_output.md)
  — the live-path wiring that surfaced the complexity-budget wall.
- [M3 Task 07b](../phases/milestone_3_first_workflow/task_07b_planner_schema_simplify.md)
  — the schema trim that closed the wall and supplied this ADR's
  evidence.
- [M3 Task 07a issue file](../phases/milestone_3_first_workflow/issues/task_07a_issue.md)
  — full α/β/γ trade-off analysis.
