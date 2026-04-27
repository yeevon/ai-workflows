# Task 02 — Spec → `StateGraph` compiler

**Status:** ✅ Complete (2026-04-26).
**Grounding:** [milestone README](README.md) · [ADR-0008 §Decision + §Step taxonomy](../../adr/0008_declarative_authoring_surface.md) · [Task 01](task_01_workflow_spec.md) (the data-model layer this task consumes) · [KDR-004 (validator pairing — by construction)](../../architecture.md) · [KDR-006 (three-bucket retry via `RetryingEdge`)](../../architecture.md) · [KDR-009 (LangGraph `SqliteSaver` checkpoints — preserved)](../../architecture.md) · [`ai_workflows/graph/tiered_node.py`](../../../ai_workflows/graph/tiered_node.py) (compiled `LLMStep` wraps this) · [`ai_workflows/graph/validator_node.py`](../../../ai_workflows/graph/validator_node.py) (paired with every `LLMStep`) · [`ai_workflows/graph/human_gate.py`](../../../ai_workflows/graph/human_gate.py) (compiled `GateStep` wraps this) · [`ai_workflows/graph/retrying_edge.py`](../../../ai_workflows/graph/retrying_edge.py) (compiled retry policy) · [`ai_workflows/workflows/_dispatch.py:540-602`](../../../ai_workflows/workflows/_dispatch.py#L540-L602) (the compile site that hands the synthesized `StateGraph` to LangGraph).

## What to Build

A new module `ai_workflows/workflows/_compiler.py` that walks a [`WorkflowSpec`](task_01_workflow_spec.md) and synthesizes the LangGraph `StateGraph` the framework hands to dispatch. Owns every piece of LangGraph wiring previously asked of consumers: state-class derivation from `input_schema` ⊕ `output_schema`, START/END edges, `initial_state` hook synthesis from the input schema, `FINAL_STATE_KEY` resolution from the output schema's first non-input field, and validator pairing on every `LLMStep` (KDR-004 by construction).

T02 wires the M19 T01 stub builder thunk to a real implementation: `register_workflow(spec)` calls `register(spec.name, lambda: _compile_spec(spec))` so the existing dispatch surface (`_dispatch._import_workflow_module`, `_run_workflow`) consumes spec-authored workflows identically to `register(name, build_fn)` workflows. The compiler emits standard LangGraph artefacts; nothing in the runtime changes.

## Deliverables

### 1. New module `ai_workflows/workflows/_compiler.py`

Lives in the workflows layer. Imports stdlib + `pydantic` + `langgraph` + `ai_workflows.graph.*` + `ai_workflows.workflows.spec`. The `graph` imports are why this is a compiler concern, not a `spec.py` concern (per layer rule, `spec.py` stays graph-free).

Module docstring cites M19 T02 + ADR-0008 + KDR-004/006/009. Public surface:

- `compile_spec(spec: WorkflowSpec) -> Callable[[], StateGraph]` — returns a zero-argument builder that, when called, synthesizes the `StateGraph`. Matches the `WorkflowBuilder` type the existing `register(name, builder)` surface expects so dispatch's `builder().compile(checkpointer=...)` call (`_dispatch.py:554`) works unchanged.
- `CompiledStep` — dataclass returned by `Step.compile(...)`. Fields: `entry_node_id: str`, `exit_node_id: str`, `nodes: list[tuple[str, Callable]]`, `edges: list[GraphEdge]`. Internal-ish (used by step-type implementations); exported so custom-step authors can build their own `CompiledStep` instances at Tier 3.
- `GraphEdge` — dataclass naming a single edge: `source: str`, `target: str | Literal["END"]`, `condition: Callable | None = None`. Used by `CompiledStep` to declare the per-step edge contributions; the compiler stitches them together.

The compiler walks the step list in order:

1. Allocate a unique node ID per step (`step_<idx>_<step_type_name>`).
2. Call `step.compile(state_class, step_id=...)` on each step. The step returns its `CompiledStep` (entry node + exit node + the node + edge contributions).
3. Stitch: `START → step_0.entry`, then for each consecutive pair `step_n.exit → step_{n+1}.entry`, finally `step_{N-1}.exit → END`.
4. Validate KDR-004: every `LLMStep`-emitted node has a downstream `ValidatorNode` before any non-validator node consumes its output. The compiler checks this invariant by inspection — an `LLMStep`'s `compile()` returns a `CompiledStep` with two nodes (the LLM call + the validator) and an edge between them; the compiler asserts the structure rather than trusting the step.

### 2. Step-type `compile()` implementations

Each built-in step's `compile()` returns a `CompiledStep`:

#### `LLMStep.compile(state_class, step_id) -> CompiledStep`

Emits two LangGraph nodes + the validator edge:

- `<step_id>_call` — `TieredNode` instance configured via the existing factory in `ai_workflows/graph/tiered_node.py:116`, which takes `prompt_fn: Callable[[GraphState], tuple[str | None, list[dict]]]` (not a string template — locked Q2 plumbing). The compiler resolves the prompt source from the spec:
  - If `self.prompt_fn is not None` → pass it through as-is.
  - If `self.prompt_template is not None` → synthesize a `prompt_fn` that reads state field values and runs `self.prompt_template.format(**state)`. The synthesized function returns `(rendered_template, [])` (no chat history); explicit "Tier 1 sugar" path. Documents the synthesis in T05's `writing-a-workflow.md` rewrite.
  - Cross-field invariant ensures exactly one is set (T01 §Deliverable 4).
- `<step_id>_validate` — `ValidatorNode` instance configured with `response_format=self.response_format`.

Edges: `<step_id>_call → <step_id>_validate` (unconditional). If `self.retry is not None`, wrap with the existing `retrying_edge` factory in `ai_workflows/graph/retrying_edge.py` — pass `self.retry` (an instance of `ai_workflows.primitives.retry.RetryPolicy` per locked Q1; no translation tax). The factory composes the three-bucket semantics (KDR-006) using `policy.max_transient_attempts` + `policy.max_semantic_attempts` + the backoff fields. Validator-failure routes back to `<step_id>_call` for semantic retry; transient retries handled by the existing wrap; hard-stop terminates.

`CompiledStep.entry_node_id = "<step_id>_call"`, `exit_node_id = "<step_id>_validate"`.

#### `ValidateStep.compile(state_class, step_id) -> CompiledStep`

Single `ValidatorNode` configured against `self.schema` reading `state[self.target_field]`. No retry edge (semantic validation; a failure here is a workflow logic bug, not a transient one). On failure, the workflow errors via the existing `_dispatch._extract_error_message` path. `entry == exit == "<step_id>_validate"`.

#### `GateStep.compile(state_class, step_id) -> CompiledStep`

Single `HumanGate` node configured with `gate_id=self.id`, `prompt=self.prompt`, `on_reject=self.on_reject`. Compiler additionally writes a `TERMINAL_GATE_ID` module-level constant on the synthesized workflow if the gate is the last step (preserves the existing dispatch's `_resolve_terminal_gate_id` behaviour). `entry == exit == "<step_id>_gate"`.

#### `TransformStep.compile(state_class, step_id) -> CompiledStep`

Wraps `self.fn` as a plain LangGraph node named `<step_id>_<self.name>`. The compiler does not inspect `self.fn`'s body; KDR-013's "user code is user-owned" applies (TransformStep is the in-spec equivalent of a custom step). `entry == exit == "<step_id>_<name>"`.

#### `FanOutStep.compile(state_class, step_id) -> CompiledStep`

The hardest case. Emits:

- A dispatch node that reads `state[self.iter_field]` and emits one `Send` per element (the LangGraph parallel-fan-out pattern; KDR-009-compatible).
- A sub-graph compiled from `self.sub_steps` — the sub-graph is itself a chain of `CompiledStep`s, but its state class is derived from the per-element type of `iter_field` (the list element's pydantic model). The sub-graph's exit writes its result into `state[self.merge_field]` via a reducer (the M8 / slice_refactor pattern — `Annotated[list[X], <append-reducer>]`).
- A merge node that waits for all branches and propagates state forward.

`entry == "<step_id>_dispatch"`, `exit == "<step_id>_merge"`.

**Scope note (Q5 deferral):** the M19 README originally framed T05's slice_refactor port as the step-taxonomy completeness gate, but the slice_refactor port is **deferred** per locked Q5. T02's `FanOutStep` synthesis ships the basic Send-pattern + sub-spec + merge-reducer shape; the M8/M10 fault-tolerance overlay (`_mid_run_tier_overrides` carry, ollama-fallback gate, hard-stop terminal, conditional routing) is not in M19's scope. Future taxonomy extensions land when a second external workflow with conditional routing or sub-graph composition wants to use the spec API (the documented re-open trigger).

### 3. State class derivation

The compiler synthesizes the workflow's state TypedDict from `spec.input_schema` ⊕ `spec.output_schema`. Algorithm:

1. Collect all field names from `input_schema.model_fields` and `output_schema.model_fields`.
2. For each field name, the type annotation comes from whichever schema declares it (output_schema wins on collision so the workflow's terminal artefact type is correct).
3. Add framework-internal state keys: `run_id: str`, plus any `_mid_run_*` keys the framework writes during dispatch (e.g. `_ollama_fallback_fired` from the M8 / M10 surface — preserved verbatim so the existing `_route_after_fallback_dispatch_slice` shape continues to work).
4. Synthesize a `TypedDict` named `<spec.name.title()>State` via `typing.TypedDict`'s functional form.

The state class is held as a closure inside the builder thunk, not exported, so each spec's compile produces a fresh state class per `register_workflow` call.

### 4. `initial_state` hook synthesis

The compiler emits an `initial_state(run_id, inputs) -> dict` callable on the synthesized workflow module, satisfying the existing `_dispatch._build_initial_state` resolution order (M6 T01 convention). Implementation:

```python
def initial_state(run_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
    parsed_input = spec.input_schema(**inputs)
    state: dict[str, Any] = {"run_id": run_id}
    state.update(parsed_input.model_dump())
    # Initialize output-schema fields to None so the FINAL_STATE_KEY check
    # in _dispatch._build_result_from_final correctly detects "not yet set"
    # versus "set by the workflow."
    for field_name in spec.output_schema.model_fields:
        state.setdefault(field_name, None)
    return state
```

### 5. `FINAL_STATE_KEY` resolution

The compiler emits a `FINAL_STATE_KEY` module-level constant on the synthesized module. Resolution: the **first** field name declared in `spec.output_schema.model_fields` (insertion order — pydantic v2 preserves this). If `output_schema` has no fields, raise at registration time (an output-schema-less workflow is incoherent — the framework can't tell when it's done).

This composes with M19 T03's bug fix — once T03 lands, `_dispatch.py` reads `final.get(FINAL_STATE_KEY)` for both completion detection and response-field surfacing, so the spec author's chosen artefact field flows through correctly.

### 6. `register_workflow(spec)` finalisation in `spec.py`

Replace T01's stub builder thunk in `register_workflow` with the real one:

```python
def register_workflow(spec: WorkflowSpec) -> None:
    _validate_spec(spec)  # T01 cross-step invariants
    from ai_workflows.workflows._compiler import compile_spec
    builder = compile_spec(spec)
    register(spec.name, builder)
```

The compiler module is imported lazily inside the function so importing `spec.py` at module-load time doesn't pull in `ai_workflows.graph.*` — the layer rule remains satisfied for callers that only need the spec data classes (e.g. introspection tooling, future YAML loaders).

### 7. Tests — `tests/workflows/test_compiler.py` (new)

Hermetic. Uses the existing `StubLLMAdapter` pattern (see `ai_workflows/evals/_stub_adapter.py`) so the synthesized `StateGraph` runs end-to-end without any provider call.

- `test_compile_minimal_validate_only_spec` — `WorkflowSpec` with one `ValidateStep` compiles to a runnable graph; invoking it via `_dispatch.run_workflow` round-trips through `RunWorkflowOutput.artifact` (T03's renamed field). Asserts the validator runs and the workflow terminates.
- `test_compile_llm_step_pairs_validator_by_construction` — `WorkflowSpec` with one `LLMStep`; assert the compiled `CompiledStep` has two nodes (the call + the validator) and one edge between them. KDR-004 invariant.
- `test_compile_llm_step_with_retry_wires_retrying_edge` — `LLMStep(retry=RetryPolicy(max_semantic_attempts=2, max_transient_attempts=3, transient_backoff_base_s=0.1, transient_backoff_max_s=1.0))` (primitives' RetryPolicy fields per locked Q1) compiles with `retrying_edge(...)` factory from the validator back to the call on semantic failure. Stub LLM emits an invalid response twice then a valid one; assert retry budget consumed correctly.
- `test_compile_llm_step_with_prompt_template_synthesizes_prompt_fn` — `LLMStep(tier="t", prompt_template="hello {goal}", response_format=Foo)` (Tier 1 sugar path per Q2) compiles with a synthesised `prompt_fn` that runs `str.format(**state)` against the template. Stub state with `{"goal": "world"}` produces a TieredNode call whose rendered prompt is `"hello world"`.
- `test_compile_llm_step_with_prompt_fn_passes_through` — `LLMStep(prompt_fn=fn, ...)` (advanced path matching the existing codebase contract) compiles with `prompt_fn=fn` passed verbatim to `tiered_node()`. No template synthesis; no `str.format` involved.
- `test_compile_gate_step_emits_terminal_gate_id` — `WorkflowSpec` ending in a `GateStep`; assert the synthesized module has `TERMINAL_GATE_ID` matching the gate's id. Resume path test rides on this.
- `test_compile_transform_step_runs_callable` — `WorkflowSpec` with a `TransformStep` whose callable writes a sentinel value into state; assert the sentinel surfaces in the response.
- `test_compile_fan_out_step_dispatches_per_element` — `WorkflowSpec` with `FanOutStep` whose `iter_field` holds a 3-element list; assert the sub-graph runs three times and the merged output has 3 entries. Exercises the `Send`-pattern wiring.
- `test_compile_unknown_field_in_fan_out_iter_field_warns` — `FanOutStep(iter_field="missing")` not statically resolvable to either schema or a prior-step `response_format`; assert `register_workflow` emits a `UserWarning` naming the field and registers the workflow anyway (M11 best-effort framing per T01 Deliverable 4). At dispatch time, the missing key surfaces as a runtime error from LangGraph; no registration-time block.
- `test_compile_state_class_merges_input_and_output_schemas` — assert the synthesized state class has every field from both schemas; output-schema field types win on collision.
- `test_compile_initial_state_hook_signature` — assert the synthesized `initial_state(run_id, inputs)` returns a dict with `run_id` + all input fields populated + all output fields initialized to `None`.
- `test_compile_final_state_key_is_first_output_field` — assert the synthesized `FINAL_STATE_KEY` matches the first field of `output_schema`.
- `test_compile_empty_output_schema_raises` — `output_schema` with no fields; `register_workflow` raises.

### 8. Smoke verification (Auditor runs)

```bash
uv run pytest tests/workflows/test_compiler.py -v

# End-to-end smoke: register a spec, dispatch it via the existing aiw run path
# using the StubLLMAdapter so no provider call fires.
uv run pytest tests/workflows/test_compiler.py::test_compile_minimal_validate_only_spec -v
```

The end-to-end smoke is one of the test cases (it exercises `_dispatch.run_workflow` against a compiled spec). Auditor expects all tests green; combined runtime <2s wall-clock.

### 9. CHANGELOG

Under `[Unreleased]` on both branches:

```markdown
### Added — M19 Task 02: Spec → StateGraph compiler (YYYY-MM-DD)
- `ai_workflows/workflows/_compiler.py` — `compile_spec(spec)` synthesizes the LangGraph `StateGraph` from a `WorkflowSpec`. Owns state-class derivation, START/END wiring, `initial_state` hook, `FINAL_STATE_KEY` resolution, and validator pairing on every `LLMStep` (KDR-004 by construction).
- Each built-in step type (`LLMStep`, `ValidateStep`, `GateStep`, `TransformStep`, `FanOutStep`) implements `Step.compile(state_class, step_id)` returning a `CompiledStep` (entry/exit node ids + node + edge contributions).
- `register_workflow(spec)` now wires the compiler — registration produces a runnable workflow without any consumer-side LangGraph code.
- `tests/workflows/test_compiler.py` — hermetic tests covering each step type + cross-step invariants (per Deliverable 7).
```

## Acceptance Criteria

- [ ] **AC-1:** `ai_workflows/workflows/_compiler.py` exists with `compile_spec(spec) -> Callable[[], StateGraph]`, `CompiledStep` dataclass, and `GraphEdge` dataclass.
- [ ] **AC-2:** Every built-in step type implements `Step.compile(state_class, step_id) -> CompiledStep` returning a non-empty node + edge contribution.
- [ ] **AC-3:** KDR-004 enforced by construction. `LLMStep.compile` returns a `CompiledStep` with two nodes (call + validator) and an edge between them; the compiler asserts this invariant by structure inspection. Unit test `test_compile_llm_step_pairs_validator_by_construction` proves it.
- [ ] **AC-4:** KDR-006 retry semantics preserved. `LLMStep(retry=RetryPolicy(...))` compiles with a `RetryingEdge` matching the policy. Three-bucket taxonomy (transient / deterministic / hard-stop) preserved internally. Test `test_compile_llm_step_with_retry_wires_retrying_edge` exercises a deterministic-retry round-trip.
- [ ] **AC-5:** KDR-009 preserved. The synthesized `StateGraph` compiles via `builder().compile(checkpointer=...)` in `_dispatch.run_workflow:554` without modification — the compiler emits a standard LangGraph artefact, not a custom one. Existing `SqliteSaver` checkpoint/resume semantics ride on top unchanged.
- [ ] **AC-6:** State class derivation merges `input_schema` and `output_schema`; output-schema field types win on collision. `run_id` and any `_mid_run_*` framework keys preserved. Test `test_compile_state_class_merges_input_and_output_schemas`.
- [ ] **AC-7:** `initial_state(run_id, inputs)` synthesized correctly — instantiates `input_schema` from inputs, populates output-schema fields with `None`. Test `test_compile_initial_state_hook_signature`.
- [ ] **AC-8:** `FINAL_STATE_KEY` resolved as the first field of `output_schema`. Empty output schema raises at registration time. Tests `test_compile_final_state_key_is_first_output_field` + `test_compile_empty_output_schema_raises`.
- [ ] **AC-9:** `FanOutStep` compiles correctly — dispatch node emits `Send` per element, sub-graph runs per branch, merge node accumulates. Test `test_compile_fan_out_step_dispatches_per_element` exercises a 3-element fan-out end-to-end.
- [ ] **AC-10:** `register_workflow(spec)` wires the compiler — registration produces a runnable workflow that succeeds when dispatched via `_dispatch.run_workflow` against a stub LLM adapter. Test `test_compile_minimal_validate_only_spec` is the end-to-end smoke.
- [ ] **AC-11:** Layer rule preserved — `uv run lint-imports` reports 4 contracts kept, 0 broken. `_compiler.py` imports `ai_workflows.graph.*` as expected (the layer rule allows workflows → graph). The lazy import inside `register_workflow` keeps `spec.py` graph-free for callers that only need the data model.
- [ ] **AC-12:** All tests in `tests/workflows/test_compiler.py` green. Combined runtime <2s wall-clock (hermetic, stub LLM, no provider calls).
- [ ] **AC-13:** Existing tests stay green — zero regression. The compiler is additive; `register(name, builder)` workflows continue to work unchanged.
- [ ] **AC-14:** Module docstring on `_compiler.py` cites M19 T02, ADR-0008, KDR-004/006/009. Public class/function docstrings cite their role + the spec-API context.
- [ ] **AC-15:** CHANGELOG entry under `[Unreleased]` matches Deliverable 9.
- [ ] **AC-16:** Gates green on both branches. `uv run pytest`, `uv run lint-imports`, `uv run ruff check`.

## Dependencies

- **Task 01 (`WorkflowSpec` + step taxonomy)** — precondition. T02 consumes the spec data model T01 ships.
- **No precondition on T03 (artifact bug fix).** T02's tests assert the compiler emits the correct `FINAL_STATE_KEY`; T03 fixes how dispatch reads that key. The two compose cleanly: T02 + T03 together enable an external workflow with `FINAL_STATE_KEY != "plan"` to round-trip its artefact (T04's `summarize` workflow verifies this composition end-to-end — `summarize`'s `FINAL_STATE_KEY = "summary"` is a non-`plan` field; T03's bug fix is what makes the round-trip through `RunWorkflowOutput.artifact` work).

## Out of scope (explicit)

- **No port of in-tree workflows.** T04 (`summarize` workflow ship) consumes T02's compiler. Both planner and slice_refactor ports deferred per locked Q5 + H2; both stay on the existing `register(name, build_fn)` escape hatch.
- **No new built-in step types beyond the five from T01.** Future taxonomy extensions land when a second external workflow with conditional routing or sub-graph composition wants to use the spec API (the locked Q5 re-open trigger).
- **No graph-layer changes.** `TieredNode`, `ValidatorNode`, `HumanGate`, `RetryingEdge` are unchanged. The compiler composes existing primitives; it does not alter them.
- **No changes to `_dispatch.run_workflow` or sibling functions.** The compiler emits a standard LangGraph builder; dispatch consumes it via the existing `builder().compile(checkpointer=...)` call site.
- **No documentation work.** T05 + T06 + T07 own the docs.
- **No removal of `register(name, build_fn)`.** The escape hatch is preserved; the compiler is additive.
- **No M15 (tier overlay) interaction.** `WorkflowSpec.tiers` is workflow-local; M15's user-overlay merge is separate.

## Carry-over from prior milestones

*None.* Builds on M16 + ADR-0008 + M19 T01.

## Carry-over from task analysis

- [ ] **TA-LOW-07 — "deterministic" terminology drift** (severity: LOW, source: task_analysis.md round 2)
      Earlier draft of T02 used "deterministic retry" terminology in places (left over from an early `RetryPolicy(deterministic_max=...)` field name before locked Q1 reused primitives' `RetryPolicy`). The primitives' field name is `max_semantic_attempts` (not `deterministic_max`); audit T02 at implement time for any remaining "deterministic" terminology that should align with `max_semantic_attempts` framing.

- [ ] **TA-LOW-10 — Straggler `_dispatch._run_workflow` reference at line 10** (severity: LOW, source: task_analysis.md round 5)
      Line 10's parenthetical list-item `(`_dispatch._import_workflow_module`, `_run_workflow`)` slipped past the round-4 sed (which targeted only `_dispatch._run_workflow` substrings). The actual exported function is `run_workflow` (no leading underscore on the function; the underscore is on the `_dispatch` module name). Builder self-corrects against the canonical `_dispatch.run_workflow` references elsewhere in this spec; mechanical edit at implement time updates this reference to match.
