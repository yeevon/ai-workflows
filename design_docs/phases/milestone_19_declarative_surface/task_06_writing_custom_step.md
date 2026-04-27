# Task 06 — New `docs/writing-a-custom-step.md` (Tier 3 dedicated guide)

**Status:** ✅ Complete (2026-04-26).
**Grounding:** [milestone README](README.md) · [ADR-0008 §Extension model + §Documentation surface (Tier 3 has its own dedicated guide; load-bearing for downstream consumers extending the framework)](../../adr/0008_declarative_authoring_surface.md) · [KDR-013 (user code is user-owned — applies to custom step types)](../../architecture.md) · [Task 01](task_01_workflow_spec.md) (the `Step` base class this doc teaches authors to subclass; default `compile()` wraps `execute()` per locked Q4) · [Task 02](task_02_compiler.md) (the compiler the custom step's `compile()` method returns to when overridden) · [Task 05](task_05_writing_workflow_rewrite.md) (the Tier 1+2 doc this guide forward-anchors from).

## What to Build

A new doc, `docs/writing-a-custom-step.md`, that teaches Tier 3 of the four-tier extension model: when no built-in step type covers an author's need, they subclass `Step` and slot the custom step into a `WorkflowSpec` like a built-in. **Load-bearing guide for downstream consumers extending the framework** — per the M19 README's identity-level statement, "if you're going down to a deeper tier of complexity, there is a guide that meets you there with worked examples."

This doc's audience is downstream consumers; it is **not** a guide for framework contributors (that's `writing-a-graph-primitive.md`, which T07 realigns). Custom steps are user-owned code (KDR-013) that runs in-process; this guide names that boundary explicitly.

T06 also ships the `compile_step_in_isolation` testing fixture (per locked M4 — commit to shipping it, no Builder hedge) at `ai_workflows/workflows/testing.py`. The fixture is small (~30 lines) and well-bounded; without it, this doc's worked test imports a non-existent fixture which is a self-inflicted AC failure.

## Deliverables

### 1. New doc `docs/writing-a-custom-step.md`

Section structure:

#### Title + intro

- "Writing a Custom Step Type" — title.
- Intro: when to use Tier 3 vs the built-ins (decision framing — "a built-in covers your need" → Tier 1; "you can configure a built-in to do what you need" → Tier 2; "no built-in does what you need" → Tier 3 (this doc); "your topology is genuinely non-standard" → Tier 4 (escape hatch)).
- Link back to `writing-a-workflow.md` for the Tier 1+2 happy path.

#### §When to write a custom step

Heuristic: your workflow needs a primitive the framework doesn't ship. Common cases:

- HTTP fetch / external API call (the `WebFetchStep` example below).
- Custom validators that go beyond pydantic schema checking (e.g. semantic checks against a downstream system).
- Pure-Python transformations the built-in `TransformStep` covers — but if the transformation is parameterizable across multiple workflows, a custom step type is more reusable than a per-workflow `TransformStep` callable.

Counter-indicator: if the same transformation appears once in one workflow, use `TransformStep(fn=...)` instead. Custom step types earn their weight when the parameterization makes them reusable.

Graduation note: if your custom step proves useful across two or more workflows (downstream OR in-tree), the framework may absorb it as a built-in in a future minor. Surface it as a feature request.

#### §The `Step` base class contract

A custom step is a pydantic model that subclasses `Step`. The base class is frozen (`model_config = ConfigDict(frozen=True, extra="forbid")`) — step instances are immutable value objects. Subclasses declare their parameters as pydantic fields.

```python
from ai_workflows.workflows import Step
from pydantic import ConfigDict


class MyCustomStep(Step):
    model_config = ConfigDict(frozen=True, extra="forbid")  # inherited; restating for clarity
    
    # Parameter fields:
    target_field: str
    transformation: str
    
    async def execute(self, state: dict) -> dict:
        # Read from state[self.target_field], compute something,
        # return a dict of state updates.
        ...
```

The `execute(state) -> dict` coroutine is the **typical Tier 3 contract**:
- **Input:** `state: dict` — the LangGraph state at this step's position in the workflow.
- **Output:** `dict` — state updates the framework merges into the workflow's state. Returning `{}` means "no state changes."
- **Async:** the framework awaits the coroutine; synchronous `def execute()` doesn't fit the framework's async runtime.

**The base class default `Step.compile()` wraps `self.execute()` in a single LangGraph node** (per locked Q4) — most custom step authors never need to think about `compile()`. The framework handles the wiring.

##### §Advanced — overriding `compile()` directly

When your custom step needs to emit more than a single LangGraph node — fan-out, sub-graph composition, conditional edges, or any topology the single-node default can't express — override `compile()` directly instead of `execute()`. Built-in step types like `LLMStep` and `FanOutStep` use this path. The signature is `compile(state_class: type, step_id: str) -> CompiledStep`; you return a `CompiledStep` dataclass naming the entry/exit node IDs and the nodes/edges your step contributes.

```python
from ai_workflows.workflows import Step
from ai_workflows.workflows._compiler import CompiledStep, GraphEdge


class MyFanOutStep(Step):
    """Custom step that emits a parallel fan-out via Send."""
    iter_field: str
    sub_step: Step

    def compile(self, state_class: type, step_id: str) -> CompiledStep:
        # ... build dispatch + sub-graph + merge nodes ...
        return CompiledStep(
            entry_node_id=f"{step_id}_dispatch",
            exit_node_id=f"{step_id}_merge",
            nodes=[...],
            edges=[...],
        )
```

In practice, the upgrade path is rare — most custom step needs are covered by `execute()`. Reach for `compile()` override only when the topology genuinely cannot be expressed as a single node. If you find yourself overriding `compile()` for something that could fit the linear step list with a different framing, surface a feature request first — the framework may absorb the pattern as a built-in step type.

#### §Worked example — `WebFetchStep`

The same example from ADR-0008 §Extension model. Full module-level shape — copy-paste-runnable. Note: the `httpx` import requires `httpx` installed in the consumer's environment; this snippet is **doctest-skip** (`# doctest: +SKIP`) since it would require a network call to verify.

```python
# doctest: +SKIP
from typing import Any
from ai_workflows.workflows import Step, register_workflow, WorkflowSpec, LLMStep
from pydantic import BaseModel
import httpx


class WebFetchStep(Step):
    """Fetches a URL and stores the response body in state."""
    url_field: str            # state field holding the URL
    output_field: str         # state field to write the response body to

    async def execute(self, state: dict) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            response = await client.get(state[self.url_field])
            response.raise_for_status()
        return {self.output_field: response.text}


class SummarizeUrlInput(BaseModel):
    url: str
    max_words: int


class SummarizeOutput(BaseModel):
    summary: str


register_workflow(WorkflowSpec(
    name="summarize_url",
    input_schema=SummarizeUrlInput,
    output_schema=SummarizeOutput,
    tiers={"planner-explorer": ...},   # required non-None per locked Q3
    steps=[
        WebFetchStep(url_field="url", output_field="page_text"),
        LLMStep(
            tier="planner-explorer",
            prompt_template="Summarize the following in at most {max_words} words:\n\n{page_text}",
            response_format=SummarizeOutput,
        ),
    ],
))
```

For a doctest-runnable equivalent (no network), the doc additionally shows a synthetic `AddOneStep` example using stdlib only:

```python
from ai_workflows.workflows import Step


class AddOneStep(Step):
    """Increments a counter in state. Synthetic example for testability."""
    counter_field: str

    async def execute(self, state: dict) -> dict:
        return {self.counter_field: state[self.counter_field] + 1}
```

#### §State-channel conventions

- **Read from `state[<field>]`.** Field names should match what your input_schema, output_schema, or upstream steps declare.
- **Write a dict of updates.** The framework merges the returned dict into LangGraph state; existing keys are overwritten.
- **Don't mutate `state` directly.** It's a LangGraph reducer; mutation may not propagate. Return a new dict.
- **Don't reach for framework-internal keys.** Keys prefixed with `_mid_run_` are framework-managed (Ollama-fallback overlay, retry state); custom steps shouldn't touch them.

#### §Testing your custom step

The framework provides spec-compilation fixtures so you can unit-test a custom step in isolation:

```python
import pytest
from ai_workflows.workflows.testing import compile_step_in_isolation


@pytest.mark.asyncio
async def test_web_fetch_step(httpx_mock):
    """Smoke-test WebFetchStep without compiling a full workflow."""
    httpx_mock.add_response(url="https://example.com", text="Hello, world.")
    
    step = WebFetchStep(url_field="url", output_field="body")
    state_in = {"url": "https://example.com"}
    state_updates = await step.execute(state_in)
    
    assert state_updates == {"body": "Hello, world."}
```

Or full-workflow integration testing using `StubLLMAdapter` for any `LLMStep` in the spec:

```python
from ai_workflows.evals._stub_adapter import StubLLMAdapter

@pytest.mark.asyncio
async def test_summarize_url_workflow_round_trips(stub_llm: StubLLMAdapter, httpx_mock):
    """End-to-end round-trip with a custom step + stubbed LLM."""
    ...
```

The `compile_step_in_isolation` and `stub_llm` fixtures are framework-provided. **T06 ships `compile_step_in_isolation` as part of this task** (per locked M4 — no Builder hedge): it lives in `ai_workflows/workflows/testing.py`, is exported through `ai_workflows.workflows.testing`, has its own docstring + at least one test in `tests/workflows/test_testing_fixtures.py`, and is layer-rule-compliant. Approximate cost: ~30 lines in the fixture module + ~20 lines of fixture tests.

#### §Graduation hints — when your custom step is ripe for promotion

Three signals that a custom step should be promoted to a built-in or a graph primitive:

1. **You're using it in two or more workflows.** Reusability across workflows is the primary signal.
2. **Downstream consumers are copying-and-pasting your step into their workflows.** A pattern that propagates by copy-paste is one the framework should absorb.
3. **The step's wiring (not just its behaviour) is reusable.** If two workflows want a similar step but with different inner logic — e.g. "an LLM call followed by an aggregator" — the wiring may belong as a graph primitive (Tier 4), not a built-in step. See [`writing-a-graph-primitive.md`](writing-a-graph-primitive.md) for the graph-layer extension path.

When you hit a graduation signal, surface the pattern as a feature request on the ai-workflows repo. The framework absorbs it with attribution.

#### §User-owned code boundary

Custom steps run in-process with full Python privileges. KDR-013 applies: ai-workflows surfaces import errors, validation errors at registration time, and runtime errors during execution — but it does not lint, test, or sandbox your custom step's code. You own the security and correctness surface of the code inside `execute()`.

This boundary is identical to the one ADR-0007 records for the M16 external-workflow loader: dotted-path imports run user code; the framework does not police it.

#### §Pointers to adjacent tiers

- **Tier 1 + Tier 2 (compose / parameterise built-ins)** — [`writing-a-workflow.md`](writing-a-workflow.md). The happy path; revisit if your custom step's parameterisation can be expressed as a built-in step config instead.
- **Tier 4 (escape to LangGraph directly)** — [`writing-a-graph-primitive.md`](writing-a-graph-primitive.md). When your topology is genuinely non-standard.

### 2. Doctest-compilable code snippets

Same requirement as T05. Every executable code block in the doc compiles cleanly. The `WebFetchStep` worked example uses `# doctest: +SKIP` because it requires `httpx` + a network call; the synthetic `AddOneStep` example is doctest-runnable as the substitute.

### 3. Cross-reference verification

Every internal link audited at implement time:
- `writing-a-workflow.md` (T05's rewrite) — must exist before this doc ships.
- `writing-a-graph-primitive.md` (T07's alignment) — must exist before this doc ships.
- `architecture.md §Extension model` (T07's new subsection) — must exist before this doc ships.
- ADR-0007 + ADR-0008 — exist.

### 4. Smoke verification (Auditor runs)

```bash
# Doctest-compile every code block:
uv run pytest --doctest-modules docs/writing-a-custom-step.md

# Verify the doc exists with all the named sections:
test -f docs/writing-a-custom-step.md
grep -E '^## §' docs/writing-a-custom-step.md  # confirm section structure

# T06 ships `compile_step_in_isolation` per locked M4 — smoke-test it:
uv run python -c "
from ai_workflows.workflows.testing import compile_step_in_isolation
print('T06 testing fixture smoke OK')
"
```

### 5. CHANGELOG

Under `[Unreleased]` on both branches:

```markdown
### Added — M19 Task 06: docs/writing-a-custom-step.md (Tier 3 dedicated guide) + compile_step_in_isolation testing fixture (YYYY-MM-DD)
- New guide for downstream consumers extending the framework via custom step types. `Step` base class contract, `execute(state) -> dict` coroutine (typical path), `compile()` override (advanced upgrade path per locked Q4 refinement), state-channel conventions, testing patterns, graduation hints, KDR-013 user-owned-code boundary.
- New testing fixture: `ai_workflows/workflows/testing.py::compile_step_in_isolation` (per locked M4) — compiles a single `Step` instance into a one-node `StateGraph` for isolated unit testing without a full workflow run.
- Worked example: `WebFetchStep` end-to-end (mirrors ADR-0008 §Extension model) plus a synthetic doctest-runnable `AddOneStep` substitute.
```

## Acceptance Criteria

- [x] **AC-1:** `docs/writing-a-custom-step.md` exists with the section structure from Deliverable 1 (Title / When to write / `Step` base class contract / Worked example / State-channel conventions / Testing / Graduation hints / User-owned code boundary / Pointers to adjacent tiers). The base-class contract section covers both `execute()` (typical Tier 3 path) AND the `compile()` upgrade path (per locked Q4 refinement) for fan-out / sub-graph / conditional cases.
- [x] **AC-2:** Worked `WebFetchStep` example present, end-to-end (the full module from Deliverable 1's §Worked example) marked `# doctest: +SKIP`. Synthetic `AddOneStep` example present and doctest-runnable.
- [x] **AC-3:** §`Step` base class contract documents the `execute(state) -> dict` coroutine signature with input/output semantics + the `compile(state_class, step_id) -> CompiledStep` advanced override. Frozen-model + extra='forbid' invariants stated. Default `Step.compile()` wrapping `self.execute()` (per locked Q4) explicitly documented.
- [x] **AC-4:** §State-channel conventions enumerates the four conventions (read via state[<field>], write a dict of updates, don't mutate, don't reach for `_mid_run_*` framework keys).
- [x] **AC-5:** §Testing section provides at least one worked test example using `compile_step_in_isolation` fixture (per locked M4 — the fixture ships as part of T06). The fixture is documented inline.
- [x] **AC-6:** §Graduation hints names the three signals (reused across workflows, copy-paste-propagation, reusable wiring → graph primitive). Cross-link to `writing-a-graph-primitive.md` for the Tier 4 graduation path.
- [x] **AC-7:** §User-owned code boundary cites KDR-013 + ADR-0007's privacy framing applied to custom steps.
- [x] **AC-8:** §Pointers to adjacent tiers cross-links to T05's `writing-a-workflow.md` (Tier 1+2) and T07-aligned `writing-a-graph-primitive.md` (Tier 4). Every link verified resolvable.
- [x] **AC-9:** Doctest verification (Deliverable 4) passes. Every executable code block in the doc compiles cleanly (skipped blocks marked `# doctest: +SKIP` with rationale comment).
- [x] **AC-10:** `compile_step_in_isolation` fixture ships as part of T06 (per locked M4): lives in `ai_workflows/workflows/testing.py`, exports through `ai_workflows.workflows.testing`, has a docstring, has at least one test in `tests/workflows/test_testing_fixtures.py`, and is layer-rule-compliant.
- [x] **AC-11:** CHANGELOG entry under `[Unreleased]` per Deliverable 5.
- [x] **AC-12:** Gates green on both branches. `uv run pytest`, `uv run lint-imports`, `uv run ruff check`.

## Dependencies

- **Task 01 (`WorkflowSpec` + step taxonomy)** — precondition. Custom steps subclass T01's `Step` base class.
- **Task 02 (compiler)** — soft precondition. The doc's testing examples assume T02's compiler is wired.
- **Forward-anchored by Task 05** — T05's `writing-a-workflow.md` cross-links to this doc; both must ship in the same release.
- **Forward-anchors Task 07** — this doc cross-links to `writing-a-graph-primitive.md` (T07-aligned) and `architecture.md §Extension model` (T07-introduced); T07 must land before this doc ships.

## Out of scope (explicit)

- **No `writing-a-graph-primitive.md` work.** T07 owns alignment of that existing doc.
- **No `writing-a-workflow.md` work.** T05 owns it.
- **No architecture.md or README.md changes.** T07.
- **No new step types beyond what T01 ships.** This doc teaches authoring custom step types; if a built-in is needed, it lands in T01.
- **No spec-API changes.** T01 + T02 own the spec API surface; T06 documents what they ship.

## Carry-over from prior milestones

*None.* Builds on M19 T01 + T02.

## Carry-over from task analysis

- [x] **TA-LOW-04 — `WebFetchStep` worked example skips doctest** (severity: LOW, source: task_analysis.md round 1)
      The `WebFetchStep` example imports `httpx` (not a project dependency) and would require a network call. Resolved in this draft by marking the block `# doctest: +SKIP` and providing a synthetic `AddOneStep` doctest-runnable substitute. Verify the implementation lands the skip marker correctly + the AddOneStep substitute exists.

- [x] **TA-LOW-09 — `WebFetchStep` worked example tier name reuses `planner-explorer`** (severity: LOW, source: task_analysis.md round 3)
      The `WebFetchStep` doctest-skip example uses `tiers={"planner-explorer": ...}` and `tier="planner-explorer"`. `planner-explorer` is the in-tree planner workflow's Ollama-Qwen-routed tier; semantically wrong as the recommended tier choice for a generic web-fetch + summarize workflow. The illustrative example would teach a confusing pattern.
      **Recommendation:** At implement time, switch the tier name in T06 §Worked example to a generic name — e.g. `summarize-url-llm` — that doesn't borrow an in-tree planner tier label. Add a one-line framing comment noting the `tiers={"summarize-url-llm": ...}` is illustrative; the actual `TierConfig` definition is omitted for brevity (point at T05's worked example or T04's `summarize_tiers.py` for the concrete shape). Doctest-skip block; safe to land at audit time as part of the implement pass.

## Carry-over from prior audits

- [x] **M19-T05-ISS-MED-2 — Overwrite the `docs/writing-a-custom-step.md` stub wholesale** (severity: MEDIUM, source: [M19 T05 issue file](issues/task_05_issue.md))
      T05 created an 11-line placeholder forward-anchor at `docs/writing-a-custom-step.md` so the cross-link from `writing-a-workflow.md` resolves under the existing link-checker (`tests/docs/test_docs_links.py`). The stub contains only a "Note: This guide ships with M19 Task 06" forward-anchor and a pair of cross-links back to `writing-a-workflow.md` + `writing-a-graph-primitive.md`. **T06 must `Write` the file (overwrite the stub completely), not `Edit` it** — `Edit` would leave the placeholder note at the top of the final guide. T06 Auditor: confirm no stub vestiges (search for the literal phrase "This guide ships with M19 Task 06") remain in the final file.
