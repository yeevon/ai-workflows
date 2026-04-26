# Task 01 — `WorkflowSpec` + step-type taxonomy + custom-step extension hook + `register_workflow` entry point

**Status:** 📝 Planned.
**Grounding:** [milestone README](README.md) · [ADR-0008 §Decision + §Step taxonomy + §Extension model](../../adr/0008_declarative_authoring_surface.md) · [KDR-004 (validator pairing — strengthened to construction invariant for `LLMStep`)](../../architecture.md) · [KDR-013 (external workflow discovery — surface preserved)](../../architecture.md) · [`ai_workflows/workflows/__init__.py`](../../../ai_workflows/workflows/__init__.py) (existing `register()` + `_REGISTRY` the new entry point composes over) · [`ai_workflows/workflows/loader.py`](../../../ai_workflows/workflows/loader.py) (the M16-shipped discovery surface this preserves).

## What to Build

A new module `ai_workflows/workflows/spec.py` containing the data-model layer of the declarative authoring surface: the `WorkflowSpec` pydantic model, the step-type taxonomy (a `Step` base class plus the five built-in step types — `LLMStep`, `ValidateStep`, `GateStep`, `TransformStep`, `FanOutStep`), the custom-step extension hook contract, and the `register_workflow(spec)` entry point. **No graph synthesis yet** — that lands in [Task 02](task_02_compiler.md). T01 ships pure data classes + a thin registration adapter that calls existing `register(name, builder)` once T02's compiler is wired in.

This task is the foundation the rest of M19 builds on. T02 (compiler) consumes `WorkflowSpec` instances; T04 (`summarize` workflow — the in-tree proof point) authors them; T05 + T06 + T07 (docs) teach them.

## Deliverables

### 1. New module `ai_workflows/workflows/spec.py`

Lives in the workflows layer alongside `_dispatch.py` + `__init__.py` + `loader.py`. Imports stdlib + `pydantic` + `ai_workflows.workflows` + `ai_workflows.primitives.retry` (for `RetryPolicy` re-export per Q1). No graph imports (the compiler in T02 owns those); no MCP imports (KDR-008 — spec types stay pydantic-clean and never leak LangGraph types into MCP schemas).

Module docstring cites M19 T01 + ADR-0008 + the four-tier extension model. Public exports:

- `WorkflowSpec` — pydantic model. Fields: `name: str`, `input_schema: type[BaseModel]`, `output_schema: type[BaseModel]`, `steps: list[Step]`, `tiers: dict[str, TierConfig]` (always non-None per locked Q3 — replaces the `<workflow>_tier_registry()` helper for spec-authored workflows; spec is self-contained at registration; legacy fallback path is not available for spec-authored workflows). `extra='forbid'` to fail loudly on typo'd fields.
- `Step` — pydantic `BaseModel` base class with default `compile()` implementation that wraps `self.execute()` (per locked Q4 — see Deliverable 3 for full signature + docstring). Custom-step authors typically implement only `execute(state) -> dict` (the simple Tier 3 path); built-in step types override `compile()` directly when they need bespoke topology (`Send` fan-out, sub-graph composition, conditional edges). The `Step` base is a frozen pydantic model so step instances behave as immutable value objects.
- `LLMStep(Step)` — single tier-routed LLM call with paired validator. Fields: `tier: str`, `prompt_fn: Callable[[dict], tuple[str | None, list[dict]]] | None = None`, `prompt_template: str | None = None`, `response_format: type[BaseModel]`, `retry: RetryPolicy | None = None`. **Exactly one of `prompt_fn` or `prompt_template` must be set** (cross-field validator per locked Q2 with refinement — explicit error message: `"LLMStep requires exactly one of `prompt_fn` (callable) or `prompt_template` (str.format string); got both"` or `"…got neither"`). `prompt_fn` matches the existing codebase contract at `ai_workflows/graph/tiered_node.py:116` and is the path advanced authors use for state-derived prompts. T04's `summarize` workflow uses `prompt_template` (Tier 1 sugar) to demonstrate the simpler shape; `prompt_template` supports **only `str.format()`-style substitution** — no Jinja, no f-string evaluation, no callbacks (intentional; the tiers.yaml drift incident is the cautionary tale). KDR-004 by construction: `response_format` is required, not optional — the type system makes an unvalidated `LLMStep` impossible.
- `ValidateStep(Step)` — schema validator without an LLM call. Fields: `target_field: str` (state-key whose value the validator checks), `schema: type[BaseModel]`.
- `GateStep(Step)` — `HumanGate` pause point. Fields: `id: str`, `prompt: str | None = None` (operator-facing pause message), `on_reject: Literal["retry", "fail"] = "fail"`.
- `TransformStep(Step)` — pure-Python state transformation. Fields: `name: str`, `fn: Callable[[dict], Awaitable[dict]]`. Consumer-provided async callable; the framework wraps it as a plain LangGraph node at compile time.
- `FanOutStep(Step)` — `Send`-pattern parallel dispatch. Fields: `iter_field: str` (state field whose list-value drives the fan-out), `sub_steps: list[Step]` (the per-branch step list — itself a sequence of `Step` instances), `merge_field: str` (state field where per-branch outputs accumulate).
- `RetryPolicy` — **re-exported from `ai_workflows.primitives.retry`** (per locked Q1; the spec API does not invent a parallel surface). Fields: `max_transient_attempts`, `max_semantic_attempts`, `transient_backoff_base_s`, `transient_backoff_max_s` (all bounded with `Field(ge=1)` / `Field(gt=0.0)`). T02's compiler hands the same `RetryPolicy` instance directly to the existing `retrying_edge(policy=...)` factory — zero translation tax at the compile boundary.
- `register_workflow(spec: WorkflowSpec) -> None` — the primary registration entry point. Validates the spec (pydantic does this automatically on construction; this function adds the cross-step + cross-schema invariants — see Deliverable 4) and calls the existing `register(name, builder)` with a builder that defers to T02's compiler.

**T01-only stub for `register_workflow`:** until T02 lands, the builder thunk raises `NotImplementedError("compiler lands in M19 T02")`. T01's tests verify the spec model surface only; the compiler-dependent tests live in T02.

### 2. `ai_workflows/workflows/__init__.py` — re-export the spec surface

Extend `__all__` and add re-exports so external authors import from the package root:

```python
from ai_workflows.primitives.retry import RetryPolicy  # re-export per locked Q1
from ai_workflows.workflows.spec import (
    FanOutStep,
    GateStep,
    LLMStep,
    Step,
    TransformStep,
    ValidateStep,
    WorkflowSpec,
    register_workflow,
)

__all__ = [
    "WorkflowBuilder",
    "register",
    "get",
    "list_workflows",
    "ExternalWorkflowImportError",
    "load_extra_workflow_modules",
    # M19 T01 — declarative authoring surface:
    "WorkflowSpec",
    "Step",
    "LLMStep",
    "ValidateStep",
    "GateStep",
    "TransformStep",
    "FanOutStep",
    "RetryPolicy",      # re-export from primitives.retry, not a new spec class
    "register_workflow",
]
```

The existing M16 + earlier exports stay untouched. The new exports compose over them.

### 3. `Step` base class contract — the custom-step extension hook

Per locked Q4: the base class ships a **default `compile()` implementation that wraps `self.execute()`** in a single LangGraph node. Custom-step authors typically implement only `execute(state) -> dict` (the simple Tier 3 path); built-in step types override `compile()` directly when they need bespoke topology. T01 freezes both surfaces; T02 defines `CompiledStep`.

```python
class Step(BaseModel):
    """Base class for workflow step types.
    
    Built-in step types (LLMStep, ValidateStep, GateStep, TransformStep,
    FanOutStep) ship in this module and override ``compile()`` directly
    so they can emit multi-node topologies (Send fan-out, validator
    pairing, sub-graph composition). Custom step types are authored by
    downstream consumers per ADR-0008 §Extension model — Tier 3.
    
    Authoring contract for custom step types:
    
    * **Typical path:** implement ``async execute(state) -> dict``. The
      base class's default ``compile()`` wraps this coroutine in a single
      LangGraph node; the framework handles the wiring.
    * **Advanced path:** override ``compile(state_class, step_id) ->
      CompiledStep`` directly when you need fan-out, sub-graph composition,
      conditional edges, or any topology the single-node default can't
      express. See ``docs/writing-a-custom-step.md`` for the upgrade-path
      example.
    
    ``CompiledStep`` is the dataclass T02's compiler returns from each
    step's ``compile()``: ``(entry_node_id, exit_node_id, nodes, edges)``.
    The compiler stitches ``CompiledStep`` instances end-to-end via START
    + END edges; subclasses never touch StateGraph directly.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    async def execute(self, state: dict) -> dict:
        """Default coroutine custom step types implement.
        
        Override this for the typical Tier 3 path. The base ``compile()``
        wraps the coroutine in a single LangGraph node; subclasses that
        only override ``execute`` get a single-node graph contribution
        with no extra wiring.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must implement execute() (the typical "
            f"Tier 3 path) or override compile() (advanced) — see "
            f"docs/writing-a-custom-step.md"
        )
    
    def compile(self, state_class: type, step_id: str) -> "CompiledStep":
        """Default compile implementation — wraps self.execute() in a single node.
        
        Built-in step types override this to emit multi-node topologies.
        Custom step types subclassing only ``execute`` inherit this default.
        T02 ships the wrapping logic; the signature is the locked public
        contract.
        """
        # Implementation lands in T02; signature locked here.
        ...  # noqa: stub
```

`CompiledStep` is a forward reference; T02 defines the dataclass. The base class default `compile()` body lands in T02 (T01 ships the signature + the `execute()` abstract method only).

### 4. Cross-step + cross-schema spec validation

`register_workflow(spec)` enforces invariants pydantic alone cannot:

- **Workflow name uniqueness** — defers to existing `register()`'s `ValueError` on collision (no new check needed).
- **`LLMStep.tier` references — always-on validation per locked Q3.** Every `LLMStep.tier` value must appear as a key in `spec.tiers`. The validator surfaces a `ValueError` at registration time naming the offending step + tier + the available tiers (e.g. `"LLMStep at index 1 references tier 'planner-syth' but spec.tiers has {'planner-explorer', 'planner-synth'} — typo?"`). No legacy fallback path for spec-authored workflows (`spec.tiers` is required non-None per Deliverable 1).
- **`LLMStep` prompt-source exclusivity per locked Q2 with refinement** — exactly one of `prompt_fn` or `prompt_template` must be set. Both set → `"LLMStep at index N: cannot set both `prompt_fn` and `prompt_template`; choose one"`. Neither set → `"LLMStep at index N: must set exactly one of `prompt_fn` (callable) or `prompt_template` (str.format string)"`. Index N names the step's position in `spec.steps` so the author can locate the offender quickly.
- **`FanOutStep.iter_field` and `merge_field` — best-effort warning per M11 fix.** The check confirms the field name appears on `spec.input_schema`, `spec.output_schema`, or as a producible field from a prior step's `response_format`. If statically unresolvable (a custom step or `TransformStep` may write the field at runtime; the framework cannot statically prove it does), a `UserWarning` surfaces naming the field; the workflow registers anyway.
- **Empty step list** — `spec.steps == []` raises `ValueError`. A workflow with zero steps is incoherent; surface the error at registration time, not at first invocation.

These checks live in `register_workflow()` rather than as pydantic validators on `WorkflowSpec` so they can read the spec as a whole (cross-field invariants are awkward to express in pydantic v2 field validators).

### 5. Tests — `tests/workflows/test_spec.py` (new)

Hermetic. Imports stdlib + `pydantic` + `ai_workflows.workflows` only. Does not exercise the compiler (T02 owns that).

Tests share a `conftest.py` fixture that calls `ai_workflows.workflows._reset_for_tests()` (existing helper at `__init__.py:118`) before each test — registry isolation hygiene.

- `test_workflow_spec_minimum_shape_constructs` — `WorkflowSpec(name="x", input_schema=FooIn, output_schema=FooOut, steps=[ValidateStep(target_field="y", schema=FooOut)], tiers={})` constructs without error. (Note `tiers={}` — required non-None per Q3; empty dict is acceptable for a no-LLM workflow.)
- `test_llm_step_requires_response_format` — `LLMStep(tier="t", prompt_template="p")` raises `ValidationError` (response_format is required; KDR-004 by construction).
- `test_llm_step_requires_exactly_one_prompt_source_both_set` — `LLMStep(tier="t", prompt_fn=lambda s: ("", []), prompt_template="p", response_format=Foo)` raises `ValidationError` with message containing `"cannot set both"`.
- `test_llm_step_requires_exactly_one_prompt_source_neither_set` — `LLMStep(tier="t", response_format=Foo)` raises `ValidationError` with message containing `"must set exactly one"`.
- `test_step_base_class_execute_raises_when_unimplemented` — direct `Step()` instance's `.execute(state)` raises `NotImplementedError` with a message pointing at `docs/writing-a-custom-step.md`.
- `test_custom_step_subclass_with_only_execute_works` — define a local `class MyStep(Step): payload: str` with `async def execute(self, state): return {"out": self.payload}`; instantiate; assert `MyStep(payload="hi")` is a valid `Step` and that the default `compile()` would wrap it (full compile-path test lives in T02).
- `test_register_workflow_empty_steps_raises` — `register_workflow(WorkflowSpec(name="x", input_schema=Foo, output_schema=Bar, steps=[], tiers={}))` raises `ValueError`.
- `test_register_workflow_unknown_tier_raises_with_typo_message` — Q3 refinement test: `tiers={"planner-explorer": ..., "planner-synth": ...}` paired with a step `LLMStep(tier="planner-syth", ...)` (typo). `register_workflow(spec)` raises `ValueError` whose message includes the offending tier name `'planner-syth'` and the available tier set `{'planner-explorer', 'planner-synth'}`. Pins the registration-time-typo-detection contract.
- `test_register_workflow_collision_raises` — register two specs with the same name; second call raises (defers to existing `register()`'s `ValueError`).
- `test_register_workflow_calls_underlying_register` — register a spec, assert `workflows.list_workflows()` contains the name. Builder thunk raises `NotImplementedError` if invoked (T01 stub); registration itself succeeds.
- `test_fan_out_step_unresolvable_iter_field_warns_not_raises` — `FanOutStep(iter_field="missing", sub_steps=[...], merge_field="agg")` in a spec where `missing` doesn't appear on either schema or as a prior-step output — `register_workflow` emits a `UserWarning` and registers; does not raise.
- `test_custom_step_frozen` — `MyStep(payload="hi").payload = "x"` raises `ValidationError` (frozen=True invariant).

### 6. Smoke verification (Auditor runs)

```bash
uv run pytest tests/workflows/test_spec.py -v
uv run python -c "
from ai_workflows.workflows import (
    WorkflowSpec, LLMStep, ValidateStep, GateStep,
    TransformStep, FanOutStep, Step, register_workflow,
)
from ai_workflows.primitives.retry import RetryPolicy   # primitives, re-exported through workflows package per Q1
from pydantic import BaseModel

class FooIn(BaseModel):
    x: int

class FooOut(BaseModel):
    y: str

spec = WorkflowSpec(
    name='smoke_t01',
    input_schema=FooIn,
    output_schema=FooOut,
    steps=[ValidateStep(target_field='y', schema=FooOut)],
    tiers={},   # required non-None per locked Q3; empty dict OK for no-LLM workflow
)
register_workflow(spec)
from ai_workflows.workflows import list_workflows
assert 'smoke_t01' in list_workflows()
print('T01 smoke OK')
"
```

The `python -c` block exercises the public-import surface end-to-end against a minimal spec. Auditor expects `T01 smoke OK` on stdout, exit 0.

### 7. CHANGELOG

Under `[Unreleased]` on both branches:

```markdown
### Added — M19 Task 01: WorkflowSpec + step-type taxonomy + register_workflow entry point (YYYY-MM-DD)
- `ai_workflows/workflows/spec.py` — `WorkflowSpec` pydantic model + `Step` base + built-in step types (`LLMStep`, `ValidateStep`, `GateStep`, `TransformStep`, `FanOutStep`) + `register_workflow`.
- `ai_workflows/workflows/__init__.py` re-exports the spec surface alongside `RetryPolicy` (re-exported from `ai_workflows.primitives.retry` per locked Q1; the spec API does not invent a parallel retry surface). Existing M16 surface preserved.
- `tests/workflows/test_spec.py` — hermetic tests covering the data-model surface (per Deliverable 5: spec-construction invariants, `LLMStep` prompt-source exclusivity, `Step.execute` default behaviour, `register_workflow` cross-step validation including the typo-detection contract from Q3 refinement).
- ADR-0008 (declarative authoring surface) status remains Accepted; M19 T01 is the data-model precursor; T02 (compiler) follows.
```

## Acceptance Criteria

- [ ] **AC-1:** `ai_workflows/workflows/spec.py` exists with all public types listed in Deliverable 1. Each model carries `model_config = ConfigDict(frozen=True, extra="forbid")` (or equivalent for non-step models) so unknown fields and post-construction mutation both fail loudly. `RetryPolicy` is re-exported from `ai_workflows.primitives.retry` (not redefined in `spec.py`) per locked Q1.
- [ ] **AC-2:** `LLMStep` requires `response_format` — KDR-004 enforced by the type system. `LLMStep(tier="t", response_format=Foo)` (no prompt source) raises `ValidationError` per the prompt-source-exclusivity check; `LLMStep(tier="t", prompt_fn=fn, prompt_template="p", response_format=Foo)` (both set) also raises. Tests `test_llm_step_requires_exactly_one_prompt_source_*` cover both paths with explicit error-message strings.
- [ ] **AC-3:** `Step` base class default `compile()` wraps `self.execute()` (per locked Q4); custom-step authors typically implement only `execute(state) -> dict` and inherit the wrapping. Direct `Step()` (un-overridden) `.execute()` raises `NotImplementedError` pointing at `docs/writing-a-custom-step.md` (T06 lands the doc; the message is forward-compatible with that path). Built-in step types override `compile()` directly; the base default is never invoked for `LLMStep` / `ValidateStep` / `GateStep` / `TransformStep` / `FanOutStep`.
- [ ] **AC-4:** `register_workflow(spec)` validates cross-step invariants (Deliverable 4): empty step list, unknown tier reference (typo-detection per Q3 refinement; error message names the offending tier + available tier set), prompt-source exclusivity (Q2 with refinement), `FanOutStep` field-resolvability warning (M11 fix), name collision via underlying `register()`. Each invariant has a corresponding test in `test_spec.py`.
- [ ] **AC-5:** `register_workflow(spec)` calls the existing `register(name, builder)` so the workflow appears in `list_workflows()` after registration. The builder thunk raises `NotImplementedError("compiler lands in M19 T02")` if invoked at T01 time — registration succeeds, dispatch fails until T02 lands.
- [ ] **AC-6:** `tests/workflows/test_spec.py` exists with the 8 tests listed in Deliverable 5; all green; runs in <1s wall-clock (hermetic, no LangGraph imports, no provider calls).
- [ ] **AC-7:** Smoke verification in Deliverable 6 passes — `python -c` block prints `T01 smoke OK` and exits 0.
- [ ] **AC-8:** `ai_workflows/workflows/__init__.py` re-exports the new surface alongside M16's surface; `__all__` lists every public spec name. Existing imports (`register`, `get`, `list_workflows`, `ExternalWorkflowImportError`, `load_extra_workflow_modules`) unaffected.
- [ ] **AC-9:** Module docstring on `spec.py` cites M19 T01, ADR-0008, KDR-004 (response_format invariance), KDR-013 (existing discovery surface preserved), and the four-tier extension model. Public class docstrings cite their step-type's role + the audience (built-in vs. consumer-extension via subclass).
- [ ] **AC-10:** Layer rule preserved — `uv run lint-imports` reports 4 contracts kept, 0 broken. `spec.py` imports stdlib + `pydantic` + `ai_workflows.workflows` only; no graph or primitives imports.
- [ ] **AC-11:** Gates green on both branches. `uv run pytest`, `uv run lint-imports`, `uv run ruff check`.
- [ ] **AC-12:** CHANGELOG entry under `[Unreleased]` matches Deliverable 7.

## Dependencies

- **ADR-0008 (declarative authoring surface) — locked precondition (2026-04-26).** This task is the data-model execution of the ADR.
- **No precondition on T02 (compiler).** T01 ships pure data classes; T02 consumes them.
- **No precondition on T03 (artifact bug fix).** T03 lives in `_dispatch.py`; T01 lives in the new `spec.py` and the registry. The two are independent.

## Out of scope (explicit)

- **No compiler.** Spec → `StateGraph` synthesis is M19 T02. T01's `register_workflow` builder thunk is intentionally a stub.
- **No port of in-tree workflows.** Planner port is M19 T04. The slice_refactor port is **deferred** (per M19 README §Decisions Q5; slice_refactor stays on the `register(name, build_fn)` escape hatch in M19; re-open trigger documented in T07).
- **No documentation.** `docs/writing-a-workflow.md` rewrite is M19 T05; new `docs/writing-a-custom-step.md` is M19 T06; architecture.md updates are M19 T07.
- **No new step types beyond the five built-ins.** The five built-ins (`LLMStep`, `ValidateStep`, `GateStep`, `TransformStep`, `FanOutStep`) are the M19 baseline. The decision to defer slice_refactor (which would have stress-tested the taxonomy with `wrap_with_error_handler`, Ollama-fallback overlay, hard-stop terminal, conditional edges, sub-graph composition) means M19 doesn't extend the taxonomy. Future minors absorb new step types as the second-external-workflow forcing function fires.
- **No removal of `register(name, build_fn)`.** The escape hatch is preserved per ADR-0008. T01 adds a parallel registration entry point; it does not replace the existing one. slice_refactor's existing builder registration stays untouched.
- **No YAML/JSON spec loader.** Pydantic models only. `register_workflow_from_yaml(path)` is a deferred surface (parking-lot per the M19 README's propagation status).
- **No tier-overlay (M15) interaction.** `WorkflowSpec.tiers` is a workflow-local registry; M15's user-overlay merge is a separate surface.
- **No new cost surface.** The spec API does not introduce per-step cost reporting, per-call cost replay, or any surface beyond the existing `runs.total_cost_usd` (per the surface-review observation that M19 should inherit the cost surface and stop). Per-call cost replay is forward-deferred per `nice_to_have.md §9` with its existing triggers.
- **Spec types stay pydantic-clean — no LangGraph leakage to MCP schemas.** `WorkflowSpec`, `Step`, and the built-in step types are pydantic models with stdlib + `pydantic` + `ai_workflows.primitives.retry` imports only. Compiled `StateGraph` artefacts live behind T02's `_compiler.py` boundary; they never appear in the MCP schemas (KDR-008 — pydantic schemas are the public contract).

## Carry-over from prior milestones

*None.* This task starts from M16-shipped surface (the existing `register()` registry) + ADR-0008.

## Carry-over from task analysis

*Empty at task generation. Populated by `/clean-tasks` if any LOWs surface during the analyzer loop, and by `/clean-implement`'s audit cycle later.*
