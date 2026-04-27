# Writing a Custom Step Type

A custom step type is a `Step` subclass you author when no built-in step covers your workflow's
need. You implement one method — `execute(state) -> dict` — and slot the result into a
`WorkflowSpec` exactly like a built-in step. The framework compiles it, wires it, and dispatches
through it without you touching LangGraph directly.

This guide covers **Tier 3** of the four-tier extension model:

| Tier | When to use it | Guide |
|---|---|---|
| Tier 1 — compose | Combine built-in steps with default settings | [`writing-a-workflow.md`](writing-a-workflow.md) |
| Tier 2 — parameterise | Tune a built-in step with `prompt_fn`, `retry`, `on_reject` | [`writing-a-workflow.md`](writing-a-workflow.md) |
| **Tier 3 — custom step** | **No built-in covers your need; write a `Step` subclass** | **This guide** |
| Tier 4 — escape hatch | Topology the step list cannot express at all | [`writing-a-graph-primitive.md`](writing-a-graph-primitive.md) |

Start from [`writing-a-workflow.md`](writing-a-workflow.md) if you have not read it — the Tier 1
happy path is the right entry point for most workflows. Come back here when you hit a gap.

## When to write a custom step

**Heuristic:** your workflow needs a primitive the framework doesn't ship.

Common cases where a custom step pays off:

- **HTTP fetch / external API call** — the built-in steps have no network primitive; a
  `WebFetchStep` is a natural Tier 3 author.
- **Custom validators** — schema checks that go beyond pydantic field types (e.g. semantic
  checks against a downstream system, cross-field invariants that span multiple state keys).
- **Parameterisable pure-Python transformations** — `TransformStep(fn=...)` is the right tool
  for a one-off transformation, but if the same transformation appears across multiple workflows
  with different configuration, a custom step type earns its weight as a reusable primitive.

**Counter-indicator:** if the same transformation appears in exactly one workflow, use
`TransformStep(fn=...)` instead. Custom step types earn their weight when parameterisation makes
them reusable across workflows.

**Graduation note:** if your custom step proves useful across two or more workflows (downstream
or in-tree), the framework may absorb it as a built-in in a future minor. Surface it as a
feature request; the framework absorbs patterns with attribution.

## The `Step` base class contract

A custom step is a pydantic model that subclasses `Step`. The base class is frozen
(`model_config = ConfigDict(frozen=True, extra="forbid")`) — step instances are immutable value
objects. Subclasses declare their parameters as pydantic fields.

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
- **Output:** `dict` — state updates the framework merges into the workflow's state. Returning
  `{}` means "no state changes."
- **Async:** the framework awaits the coroutine; a synchronous `def execute()` is not compatible
  with the framework's async runtime.

**The base class default `Step.compile()` wraps `self.execute()` in a single LangGraph node**
(per locked Q4 of ADR-0008) — most custom step authors never need to think about `compile()`.
The framework handles all the LangGraph wiring.

### Advanced — overriding `compile()` directly

When your custom step needs to emit more than a single LangGraph node — fan-out, sub-graph
composition, conditional edges, or any topology the single-node default cannot express — override
`compile()` directly instead of `execute()`. Built-in step types like `LLMStep` and `FanOutStep`
use this path.

The signature is `compile(state_class: type, step_id: str) -> CompiledStep`; you return a
`CompiledStep` dataclass naming the entry/exit node IDs and the nodes/edges your step
contributes.

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

In practice, the upgrade path is rare — most custom step needs are covered by `execute()`. Reach
for the `compile()` override only when the topology genuinely cannot be expressed as a single
node. If you find yourself overriding `compile()` for something that could fit the linear step
list with a different framing, surface a feature request first — the framework may absorb the
pattern as a built-in step type.

## Worked example — `WebFetchStep`

The same example from ADR-0008 §Extension model. Full module-level shape — copy-paste-runnable
in a consumer's environment. Note: `httpx` is not a project dependency; install it separately
(`uv add httpx`). This block requires a network call to run, so it is marked `# doctest: +SKIP`.

```python
# doctest: +SKIP
# Requires: httpx (not a project dependency — uv add httpx)
from typing import Any

import httpx
from pydantic import BaseModel

from ai_workflows.workflows import LLMStep, Step, WorkflowSpec, register_workflow


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


class SummarizeUrlOutput(BaseModel):
    summary: str


# tiers= definition omitted for brevity; see writing-a-workflow.md §Tier registry
# for the TierConfig / LiteLLMRoute shape.  The tier name "summarize-url-llm" here
# is illustrative — it must match a key in the tiers= dict you supply.
register_workflow(WorkflowSpec(
    name="summarize_url",
    input_schema=SummarizeUrlInput,
    output_schema=SummarizeUrlOutput,
    tiers={"summarize-url-llm": ...},   # required non-None per locked Q3
    steps=[
        WebFetchStep(url_field="url", output_field="page_text"),
        LLMStep(
            tier="summarize-url-llm",
            prompt_template="Summarize the following in at most {max_words} words:\n\n{page_text}",
            response_format=SummarizeUrlOutput,
        ),
    ],
))
```

For a doctest-runnable equivalent (no network, no extra dependencies), use a synthetic
`AddOneStep` that operates entirely on stdlib types:

```python
from ai_workflows.workflows import Step


class AddOneStep(Step):
    """Increments a counter in state. Synthetic example for testability."""

    counter_field: str

    async def execute(self, state: dict) -> dict:
        return {self.counter_field: state[self.counter_field] + 1}
```

`AddOneStep` is the example used throughout the testing section below.

## State-channel conventions

Four conventions your `execute()` implementation must follow:

1. **Read from `state[<field>]`.** Field names should match what your `input_schema`,
   `output_schema`, or upstream steps declare.
2. **Write a dict of updates.** The framework merges the returned dict into LangGraph state;
   existing keys you did not include are untouched. Returning `{}` is valid — it means "no
   state changes at this step."
3. **Don't mutate `state` directly.** It's a LangGraph reducer; mutating the dict in place may
   not propagate to subsequent nodes. Always return a new dict with the updates.
4. **Don't reach for framework-internal keys.** Keys prefixed with `_mid_run_` (e.g.
   `_mid_run_tier_overrides`) are framework-managed. Similarly, `last_exception`,
   `_retry_counts`, and `_non_retryable_failures` belong to the retry machinery. Custom steps
   should not read or write these keys.

## Testing your custom step

### Unit testing with `compile_step_in_isolation`

The framework ships `compile_step_in_isolation` in `ai_workflows/workflows/testing.py` (per
locked M4 — ships as part of M19 T06). It compiles a single `Step` instance into a one-node
`StateGraph`, runs it against an initial state dict, and returns the final state:

```python
import pytest
from ai_workflows.workflows.testing import compile_step_in_isolation


class AddOneStep:  # doctest: +SKIP
    ...  # defined above


@pytest.mark.asyncio
async def test_add_one_step() -> None:
    step = AddOneStep(counter_field="n")
    result = await compile_step_in_isolation(step, initial_state={"n": 0})
    assert result["n"] == 1
```

The fixture intentionally omits a `SqliteSaver` checkpointer — it is a unit-testing primitive,
not a full dispatch round-trip. For persistence round-trips, use the full dispatch path with a
`tmp_path`-redirected SQLite DB (see `tests/workflows/test_summarize.py` for the pattern).

### Testing `WebFetchStep` with a mock HTTP client

For steps that do I/O, inject a mock at the I/O boundary and call `execute()` directly — no
need for the full isolation fixture:

```python
import pytest
from ai_workflows.workflows.testing import compile_step_in_isolation


@pytest.mark.asyncio
async def test_web_fetch_step(httpx_mock) -> None:  # doctest: +SKIP
    """Smoke-test WebFetchStep without compiling a full workflow."""
    httpx_mock.add_response(url="https://example.com", text="Hello, world.")

    step = WebFetchStep(url_field="url", output_field="body")
    state_in = {"url": "https://example.com"}
    state_updates = await step.execute(state_in)

    assert state_updates == {"body": "Hello, world."}
```

### Integration testing with `StubLLMAdapter`

For workflows that mix a custom step with built-in `LLMStep`s, use `StubLLMAdapter` to stub
the LLM tier and the full dispatch path:

```python
# doctest: +SKIP
import pytest
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.evals._stub_adapter import StubLLMAdapter


@pytest.fixture(autouse=True)
def stub_llm(monkeypatch):
    """Replace the LiteLLM adapter so no real provider call fires."""
    StubLLMAdapter.arm(expected_output='{"summary": "stubbed summary"}')
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", StubLLMAdapter)
    yield StubLLMAdapter
    StubLLMAdapter.disarm()
```

See `tests/workflows/test_summarize.py` for the complete 5-test hermetic suite demonstrating
this pattern against the `summarize` workflow.

## Graduation hints — when your custom step is ripe for promotion

Three signals that a custom step should be promoted to a built-in step type or a graph
primitive:

1. **You're using it in two or more workflows.** Reusability across workflows is the primary
   signal. A step that is copy-pasted into a second workflow is a pattern the framework should
   absorb.
2. **Downstream consumers are copying-and-pasting your step.** A pattern that propagates by
   copy-paste is one the framework should absorb with proper documentation and tests.
3. **The step's wiring (not just its behaviour) is reusable.** If two workflows want a similar
   step but with different inner logic — e.g. "an LLM call followed by an aggregator node" — the
   wiring pattern may belong as a graph primitive (Tier 4), not a built-in step type. See
   [`writing-a-graph-primitive.md`](writing-a-graph-primitive.md) for the graph-layer extension
   path.

When you hit a graduation signal, surface the pattern as a feature request on the ai-workflows
repo. The framework absorbs patterns with attribution.

## User-owned code boundary

Custom steps run in-process with full Python privileges. **KDR-013 applies**: ai-workflows
surfaces import errors, validation errors at registration time, and runtime errors during
execution — but it does not lint, test, or sandbox the code inside your `execute()` method. You
own the security and correctness surface.

This boundary is identical to the one **ADR-0007** records for the M16 external-workflow loader:
dotted-path imports run user code; the framework does not police it. A custom step type authored
by a downstream consumer is no different from an external workflow module in this respect — it
runs with the same privileges and the same lack of sandboxing.

The practical implication: if your custom step calls a third-party API, manages credentials, or
performs file I/O, the security of those operations is yours to own.

## Pointers to adjacent tiers

- **Tier 1 + Tier 2 (compose / parameterise built-ins)** — [`writing-a-workflow.md`](writing-a-workflow.md).
  The happy path; revisit if your custom step's parameterisation can be expressed as a built-in
  step configuration instead.
- **Tier 4 (escape to LangGraph directly)** — [`writing-a-graph-primitive.md`](writing-a-graph-primitive.md).
  When even the `compile()` override in Tier 3 cannot express your topology — typically
  non-standard control-flow patterns that the linear step list cannot describe.
- **Full four-tier extension model** — [`design_docs/architecture.md` §Extension model](../design_docs/architecture.md#extension-model----extensibility-is-a-first-class-capability) (builder-only, on design branch).
  The architecture-of-record for the extension framing: tier definitions, out-of-scope guidance
  for graph-layer primitives, and the graduation path from custom step to built-in.
