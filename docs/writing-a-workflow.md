# Writing a Workflow

A workflow is a `WorkflowSpec` — a pydantic data object that names the workflow, declares its
input/output schemas, and lists an ordered sequence of steps. The framework synthesises the
LangGraph runtime from that description; **you never `import langgraph`**.

For the full four-tier extension model that backs this framing, see
[the architecture overview](architecture.md).

## Prerequisites

- `ai-workflows` installed (`uv tool install jmdl-ai-workflows` for a persistent install, or
  working from a clone with `uv sync`).
- `GEMINI_API_KEY` exported if your workflow uses the Gemini-backed tiers.
- `ollama serve` reachable at `http://127.0.0.1:11434` if your workflow uses the `local_coder`
  tier.
- `claude` CLI on `PATH` (logged in via `claude login`) if your workflow uses the `claude_code`
  tier.

Provider keys are only required at runtime when the workflow actually dispatches an LLM call.
A no-LLM workflow (steps only contain `ValidateStep`, `TransformStep`, or `GateStep`) needs none
of them.

## The `WorkflowSpec` shape

A workflow is a pydantic data object. Every `WorkflowSpec` requires five fields:

| Field | Type | Role |
|---|---|---|
| `name` | `str` | Registry key — used as `workflow_id` in all surfaces |
| `input_schema` | `type[BaseModel]` | Pydantic model describing accepted inputs |
| `output_schema` | `type[BaseModel]` | Pydantic model describing emitted output; **first field** becomes `RunWorkflowOutput.artifact` |
| `steps` | `list[Step]` | Ordered step sequence; must be non-empty |
| `tiers` | `dict[str, TierConfig]` | Workflow-local tier registry (required non-None per locked Q3) |

### Tier registry (`tiers=`)

`WorkflowSpec.tiers` is a required field — pass an empty dict (`tiers={}`) for a no-LLM
workflow. For any workflow that uses `LLMStep`, every `LLMStep.tier` value must appear as a key
in `tiers`. A typo'd tier name raises `ValueError` at registration time:

```
ValueError: LLMStep at index 0 references tier 'planner-syth' but
spec.tiers has {'planner-explorer', 'planner-synth'} — typo?
```

The `tiers` dict uses the same `TierConfig` type as the rest of the framework. The conventional
helper is `<workflow_name>_tier_registry()` — a module-level function that returns the dict.
The prefix must literally match the workflow name so the convention is machine-readable.

```python
# Minimum viable tier registry for a workflow named "my_workflow".
from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig


def my_workflow_tier_registry() -> dict[str, TierConfig]:
    """Return the tier registry for my_workflow."""
    return {
        "my-llm": TierConfig(
            name="my-llm",
            route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
            max_concurrency=4,
            per_call_timeout_s=120,
        ),
    }
```

### Fallback chains

When a route's retry budget exhausts (after `RetryingEdge`'s three-bucket cycle), `TieredNode`
walks the tier's `fallback` list in declaration order, attempting each route against a fresh
retry counter. If all routes fail, it raises `AllFallbacksExhaustedError` carrying a
`attempts: list[TierAttempt]` log for diagnostics.

Declare a fallback chain in `TierConfig.fallback`:

```python
from ai_workflows.primitives.tiers import ClaudeCodeRoute, LiteLLMRoute, TierConfig


def planner_tier_registry() -> dict[str, TierConfig]:
    return {
        "planner-synth": TierConfig(
            name="planner-synth",
            route=ClaudeCodeRoute(cli_model_flag="opus"),
            fallback=[
                ClaudeCodeRoute(cli_model_flag="sonnet"),   # first fallback
                LiteLLMRoute(model="gemini/gemini-2.5-flash"),  # last-resort
            ],
        ),
    }
```

**Semantics:**
- `fallback` is a flat list — no nested fallbacks. `TierConfig` rejects fallback routes that
  carry their own `fallback` field at schema-validation time.
- Cascade triggers *after retry-budget exhaustion*, not on the first error signal. The retry
  budget is the primary correctness surface.
- Cost attribution is truthful — every attempted route (primary + each fallback) logs its
  `TokenUsage`. `CostTracker.total(run_id)` reflects the aggregate.
- The `ValidatorNode` downstream of an `LLMStep` runs unchanged: it always validates the
  final successful route's output. Semantic-validation failure is a primary-route concern and
  does *not* trigger the cascade.

See [`docs/tiers.example.yaml`](tiers.example.yaml) for a YAML-syntax schema reference.
See [ADR-0006](https://github.com/yeevon/ai-workflows/blob/design_branch/design_docs/adr/0006_tier_fallback_cascade_semantics.md) (builder-only, on design branch) for the design
rationale and rejected alternatives.

### Minimum viable spec

A one-step no-LLM workflow — validates a field, returns immediately:

```python
from pydantic import BaseModel
from ai_workflows.workflows import WorkflowSpec, ValidateStep, register_workflow


class EchoInput(BaseModel):
    text: str


class EchoOutput(BaseModel):
    text: str


register_workflow(WorkflowSpec(
    name="echo_validate",
    input_schema=EchoInput,
    output_schema=EchoOutput,
    tiers={},  # no LLM calls
    steps=[
        ValidateStep(target_field="text", schema=EchoOutput),
    ],
))
```

## Scaffolding a workflow

`scaffold_workflow` (M17) is an alternative entry point for authors who prefer to describe a
workflow in plain English rather than writing a `WorkflowSpec` by hand. The scaffold takes a
natural-language goal and produces a `.py` file containing a `WorkflowSpec` definition plus a
`register_workflow(spec)` call — the same shape as the §Minimum viable spec example above.

### What the scaffold produces

The output is a standalone Python module ready for the M16 external-module load path:

```bash
aiw run-scaffold \
  --goal "generate exam questions from a textbook chapter" \
  --target ~/my-workflows/question_gen.py

# After approval at the HumanGate, the file is written.
# Load it via AIW_EXTRA_WORKFLOW_MODULES (module stem = file stem, no .py):
PYTHONPATH=~/my-workflows \
  AIW_EXTRA_WORKFLOW_MODULES=question_gen \
  aiw run question_gen \
    --input chapter_text="Chapter 4 content here" \
    --input num_questions=10
```

### Validator scope and ownership

The scaffold validates two things only (KDR-004 + ADR-0010):

1. `spec_python` parses as valid Python.
2. The parsed AST contains at least one `register_workflow(...)` call.

No `ruff`, no `pytest`, no `import-linter` is run on the generated artefact. The `HumanGate`
that precedes the write is a **user-review gate** — "here is what I'll write to disk; approve
to save or reject to retry with different guidance." The user is the reviewer; ai-workflows
does not certify code quality.

From the moment the file is written to disk, it is **user-owned**. The user edits, tests, and
maintains it independently of the framework. See
[ADR-0010](https://github.com/yeevon/ai-workflows/blob/design_branch/design_docs/adr/0010_user_owned_generated_code.md) (builder-only, on design branch) for the full risk-ownership
framing.

### Full CLI walkthrough

See
[`design_docs/phases/milestone_9_skill/skill_install.md` §Generating your own workflow](https://github.com/yeevon/ai-workflows/blob/design_branch/design_docs/phases/milestone_9_skill/skill_install.md#7-generating-your-own-workflow) (builder-only, on design branch)
for the end-to-end walkthrough: invocation, gate review, approve/reject, write path,
`AIW_EXTRA_WORKFLOW_MODULES` handoff, and iteration guidance.

### Reserved field names

The framework writes several keys into graph state during dispatch. **Do not use these names as
fields in your `input_schema` or `output_schema`**:

| Reserved name | Written by |
|---|---|
| `run_id` | Dispatch — set before `input_schema` fields are merged |
| `last_exception` | RetryingEdge / error handler |
| `_retry_counts` | RetryingEdge |
| `_non_retryable_failures` | RetryingEdge |
| `_mid_run_tier_overrides` | Tier-overlay mechanism |
| `_ollama_fallback_fired` | Ollama fallback gate |

If your `input_schema` declares a field named `run_id`, the framework-generated run ID will be
overwritten by the user-supplied value; `last_exception` and the `_`-prefixed keys use
`setdefault()` protection so they are not overwritten, but the intent (framework owns those
slots) should still be honoured. Declaring any of these names in your schema is a logic error
that the framework cannot detect at registration time.

## Built-in step types

The five step types cover the most common orchestration patterns. Pick the one that matches your
need; combine them in `steps=[]`.

### `LLMStep` — tier-routed LLM call with paired validator

**Role:** call an LLM tier, validate the response against a pydantic schema, retry on failure.
KDR-004 (validator pairing) is enforced _by construction_: `response_format` is required, so an
unvalidated LLM step cannot be expressed.

**Constructor:**

```python
LLMStep(
    tier="<tier-name>",          # must be a key in WorkflowSpec.tiers
    prompt_template="...",       # Tier 1 sugar — str.format()-style template
    # or:
    prompt_fn=my_callable,       # Tier 2 — callable(state) -> (system, messages)
    response_format=MySchema,    # required; pydantic BaseModel subclass
    retry=RetryPolicy(...),      # optional; defaults to RetryPolicy()
)
```

Exactly one of `prompt_template` or `prompt_fn` must be set:
- Both set → `ValidationError: "cannot set both"`
- Neither set → `ValidationError: "must set exactly one of prompt_fn (callable) or prompt_template (str.format string)"`

**Tier 2 hooks:** `retry=RetryPolicy(...)` parameterises the retry budget (transient cap,
semantic cap, backoff). `tier=` routes to a different provider. `prompt_fn=` replaces the
template with a full prompt builder.

#### `prompt_template` Tier 1 sugar

`prompt_template` is a plain `str.format()` template. Placeholders like `{field_name}` are
substituted from the current graph state at invocation time using `template.format(**state)`.
Only `str.format()`-style substitution is supported — no Jinja, no f-string evaluation,
no callbacks.

**Example:**

```python
LLMStep(
    tier="my-llm",
    prompt_template="Summarize in at most {max_words} words:\n\n{text}",
    response_format=SummarizeOutput,
)
```

**Brace-escaping caveat (security advisory ADV-2).** Because the template is rendered with
`str.format(**state)`, an end-user who controls the value of `text` (or any other state field
named in the template) can inject `str.format`-style placeholders. For example, if a user
supplies `text="{summary}"`, the rendered prompt will contain whatever is currently in
`state["summary"]` (possibly `None`) — producing a confusing prompt. Worst case is LLM
confusion; the result is sent to the LLM provider only, not to any path-traversal-capable
surface.

Mitigations:
- To include a literal brace in your template, double it: `{{` and `}}`.
- If end-user-controlled field values may contain `{`-style syntax, switch to the `prompt_fn=`
  Tier 2 path — the callable receives raw state and constructs the prompt explicitly, so
  escaping is fully under your control.

#### `prompt_fn` Tier 2 advanced path

`prompt_fn` is a callable `(state: dict) -> tuple[str | None, list[dict]]` that returns
`(system_prompt, messages)`. Use this when the prompt is state-derived — multi-turn context,
conditionally-built message lists, or whenever user-controlled values may contain format syntax.

```python
def my_prompt(state: dict) -> tuple[str | None, list[dict]]:
    system = "You are a helpful summariser."
    messages = [{"role": "user", "content": f"Summarize: {state['text']!r}"}]
    return system, messages


LLMStep(tier="my-llm", prompt_fn=my_prompt, response_format=SummarizeOutput)
```

### `ValidateStep` — schema validation without an LLM call

**Role:** validate a state field against a pydantic schema. Use this after a `TransformStep`
or custom step to assert the produced value matches an expected shape.

**Constructor:**

```python
ValidateStep(
    target_field="my_field",  # state key to validate
    schema=MySchema,          # pydantic BaseModel subclass
)
```

**Tier 2 hooks:** none — `ValidateStep` is a pure validation primitive.

**Example:**

```python
ValidateStep(target_field="summary", schema=SummarizeOutput)
```

### `GateStep` — human-gate pause point

**Role:** pause the run for operator review. The framework persists a `SqliteSaver` checkpoint;
the operator reviews state via `aiw list-runs` and resumes with `aiw resume <run_id>` (default
gate response is `approved`) or `aiw resume <run_id> --gate-response approved` for the explicit
form, or the MCP `resume_run` tool.

**Constructor:**

```python
GateStep(
    id="review-gate",           # gate identifier surfaced in aiw resume
    prompt="Please review.",    # optional operator-facing message
    on_reject="fail",           # "fail" (default) or "retry"
)
```

**Tier 2 hooks:** `on_reject="retry"` loops back to the preceding LLM step on rejection.
`on_reject="fail"` (default) terminates the run.

**Example:**

```python
GateStep(id="final-review", prompt="Approve the summary before saving?")
```

### `TransformStep` — pure-Python state transformation

**Role:** reshape state deterministically without an LLM call. The callable receives the full
graph state and returns a dict of updated fields.

**Constructor:**

```python
TransformStep(
    name="my-transform",          # used as the LangGraph node identifier
    fn=my_async_callable,         # async (state: dict) -> dict
)
```

**Tier 2 hooks:** `name=` controls the node ID in the compiled graph — useful when you have
multiple `TransformStep`s and need predictable node names in checkpoints.

**Example:**

```python
async def truncate_summary(state: dict) -> dict:
    return {"summary": state["summary"][:200]}


TransformStep(name="truncate", fn=truncate_summary)
```

### `FanOutStep` — `Send`-pattern parallel dispatch

**Role:** run a sub-step sequence once per element of a list-valued state field. Per-branch
outputs accumulate under `merge_field`.

**Constructor:**

```python
FanOutStep(
    iter_field="items",         # list-valued state key that drives the fan-out
    sub_steps=[...],            # per-branch Step sequence
    merge_field="results",      # accumulation target
)
```

**Tier 2 hooks:** `sub_steps=` can contain any built-in step type including `LLMStep`.

**Example:**

```python
FanOutStep(
    iter_field="chunks",
    sub_steps=[
        LLMStep(tier="my-llm", prompt_template="Summarize: {chunk}", response_format=ChunkSummary),
    ],
    merge_field="chunk_summaries",
)
```

## Worked example — the `summarize` workflow

The code below is **the literal source** of
[`ai_workflows/workflows/summarize.py`](../ai_workflows/workflows/summarize.py) (T04 ships the
file; this doc cites it). When the workflow changes, this doc changes; they are kept in lockstep.

This example exercises Tier 1 (`prompt_template` sugar) and Tier 2 (`retry=RetryPolicy(...)`
parameterisation). The `ValidateStep` is included to illustrate syntactic composition; in this
exact configuration where its `schema` matches the upstream `LLMStep.response_format`, it is a
runtime no-op (the `LLMStep`'s paired validator already validated at the LLM call site).

```python
from __future__ import annotations

from pydantic import BaseModel

from ai_workflows.workflows import (
    LLMStep,
    RetryPolicy,  # re-exported from ai_workflows.primitives.retry per locked Q1
    ValidateStep,
    WorkflowSpec,
    register_workflow,
)
from ai_workflows.workflows.summarize_tiers import summarize_tier_registry
# (For brevity the tier-registry helper lives in a sibling ``summarize_tiers.py`` module;
# downstream authors can keep it inline as shown in §Tier registry above.)


class SummarizeInput(BaseModel):
    """Input schema — the user's text + how aggressively to summarise."""

    text: str
    max_words: int


class SummarizeOutput(BaseModel):
    """Output schema — the LLM's summary.

    First field (``summary``) is the workflow's terminal artefact
    (``FINAL_STATE_KEY``). Per M19 T03: ``RunWorkflowOutput.artifact``
    will contain ``{"summary": "..."}`` after a completed dispatch.
    """

    summary: str


_SPEC = WorkflowSpec(
    name="summarize",
    input_schema=SummarizeInput,
    output_schema=SummarizeOutput,
    tiers=summarize_tier_registry(),
    steps=[
        LLMStep(
            tier="summarize-llm",
            prompt_template=(
                "Summarize the following text in at most {max_words} words. "
                "Respond with a JSON object matching the SummarizeOutput schema.\n\n"
                "Text:\n{text}"
            ),
            response_format=SummarizeOutput,
            retry=RetryPolicy(
                max_transient_attempts=3,
                max_semantic_attempts=2,
                transient_backoff_base_s=0.5,
                transient_backoff_max_s=4.0,
            ),
        ),
        ValidateStep(  # illustrative; runtime no-op when schema == upstream LLMStep.response_format
            target_field="summary",
            schema=SummarizeOutput,
        ),
    ],
)
"""Declarative spec for the summarize workflow.

``LLMStep`` exercises ``prompt_template`` Tier 1 sugar (locked Q2).
``ValidateStep`` is illustrative; in this exact configuration where its
``schema`` matches the upstream ``LLMStep.response_format``, it is a
runtime no-op (the LLMStep's paired validator already validated). The
composition is shown for syntactic illustration only. The
``RetryPolicy`` parameterisation uses the primitives' field names per
locked Q1.
"""


register_workflow(_SPEC)
```

The first field of `SummarizeOutput` is `summary`; the framework uses that as the
`FINAL_STATE_KEY` and surfaces it as `RunWorkflowOutput.artifact` after a completed dispatch.

## Running your workflow

### CLI

Once `register_workflow` fires at import time, the workflow is reachable from both surfaces. For
the `summarize` workflow:

```bash
# Pass inputs as KEY=VALUE pairs — repeatable, one per input field:
aiw run summarize --input text="LangGraph is a library for building stateful agents." \
                  --input max_words=20 \
                  --run-id sm-1
```

The `--input` flag accepts any field declared in the workflow's `input_schema`. Pydantic
coerces string values to the declared types (e.g. `"20"` → `int`). Fields with defaults are
optional; required fields without a value raise `BadParameter` immediately.

Introspect a workflow's inputs before running:

```bash
aiw show-inputs summarize
# Output:
#   - text (str, required)
#   - max_words (int, required)
```

### MCP

The `run_workflow` MCP tool wraps all arguments under a `payload` key — this is FastMCP's
convention. Every MCP call must use this wrapper:

```python
# Using fastmcp.Client (async):
import asyncio
from fastmcp import Client

async def run_summarize():
    async with Client("aiw-mcp") as client:
        result = await client.call_tool(
            "run_workflow",
            {
                "payload": {
                    "workflow_id": "summarize",
                    "inputs": {"text": "LangGraph is a library.", "max_words": 20},
                    "run_id": "sm-mcp-1",
                }
            },
        )
        return result
```

The `payload` wrapper is required — omitting it causes FastMCP to reject the call with a
schema-validation error. This was the first integration gap CS-300 hit in pre-flight smoke
testing (2026-04-25); it is now documented here.

Over the HTTP transport (`aiw-mcp --transport http --port 8080`), the same `payload` wrapper
applies in the POST body.

### Reading the response

The workflow's terminal artefact is surfaced as **`result.artifact`** — the first field of the
`output_schema` pydantic model:

```python
# result.artifact is the terminal artefact dict:
print(result.artifact)
# {"summary": "LangGraph builds stateful agents."}

# result.plan is a deprecated alias for result.artifact.
# Preserved for backward compatibility through the 0.2.x line;
# removal target 1.0. Read result.artifact in new code.
```

Both `artifact` and `plan` are present on every response through 0.2.x. They point to the same
value. `plan` will be removed at 1.0; migrate to `artifact` now.

### Surfaces are automatic

Once registered, the workflow is reachable from every surface without per-workflow code:

- `aiw run <name> --input KEY=VALUE ...` — start a new run.
- `aiw resume <run_id>` — resume a paused run through a `GateStep` (default: `approved`). Pass
  `--gate-response rejected` to reject. Short form: `-r approved`.
- `aiw list-runs` / `aiw list-runs --workflow <name> --status completed` — query the run
  registry.
- Cancellation: at 0.2.x, cancellation is available via the MCP `cancel_run` tool only — use
  the `aiw-mcp` server and call `cancel_run(run_id=...)`. CLI cancellation (`aiw cancel`) is not
  implemented at this version.
- MCP tools: `run_workflow`, `resume_run`, `list_runs`, `cancel_run` — identical semantics
  over the MCP surface.

## When you need more — pointers to deeper tiers

The five built-in step types cover the most common orchestration shapes. When they are not
enough:

**Tier 3 — Custom step types** (when no built-in covers your need): Subclass `Step` and
implement `execute(state) -> dict` for the typical path, then slot your custom step into
`WorkflowSpec.steps` like a built-in. No `import langgraph` required.

Upgrade path within Tier 3: if your custom step needs to fan out, compose a sub-graph, or emit
conditional edges, override `compile(state_class, step_id) -> CompiledStep` directly instead of
`execute()` — that gives you the full bespoke-topology surface the built-ins use internally.

See [`docs/writing-a-custom-step.md`](writing-a-custom-step.md) for the full guide, including
the `compile()` upgrade-path worked example and the `compile_step_in_isolation` testing fixture.

**Tier 4 — Escape to LangGraph directly** (when even Tier 3's `compile()` override cannot
express your topology — typically non-standard control flow patterns that the linear step list
cannot describe): The `register(name, build_fn)` API is preserved for this. See
[`docs/writing-a-graph-primitive.md`](writing-a-graph-primitive.md) and the §Escape hatch
section below.

## External workflows from a downstream consumer

A consumer of the published `jmdl-ai-workflows` wheel registers their own workflow modules
without forking the package. Two discovery surfaces, both honoured by `aiw` and `aiw-mcp`:

1. **`AIW_EXTRA_WORKFLOW_MODULES`** — comma-separated dotted Python module paths.
2. **`--workflow-module <dotted>`** — repeatable CLI flag on both commands; composes with the
   env var (env entries import first, then CLI entries).

Each entry is imported via `importlib.import_module(...)` at startup; the module's top-level
`register_workflow(spec)` call (or `register(name, build_fn)` for Tier 4) lands the workflow
in the shared registry. The module must already be importable via the running interpreter's
`sys.path` — the typical layout is a pip-installable package, editable or otherwise.

See [ADR-0007](https://github.com/yeevon/ai-workflows/blob/design_branch/design_docs/adr/0007_user_owned_code_contract.md) (builder-only, on design branch) for the discovery contract and
[ADR-0008](https://github.com/yeevon/ai-workflows/blob/design_branch/design_docs/adr/0008_declarative_authoring_surface.md) (builder-only, on design branch) for the authoring-surface decision.

### Minimum module shape

```python
# cs300/workflows/question_gen.py
from pydantic import BaseModel

from ai_workflows.workflows import WorkflowSpec, LLMStep, ValidateStep, register_workflow
from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig


class QuestionGenInput(BaseModel):
    chapter_text: str
    num_questions: int


class QuestionGenOutput(BaseModel):
    questions: list[str]


def question_gen_tier_registry() -> dict[str, TierConfig]:
    """Return the tier registry for the question_gen workflow.

    The prefix ``question_gen_`` must literally match the workflow name
    ``question_gen`` — this is the convention the framework uses to find
    the helper at startup when needed.
    """
    return {
        "question-gen-llm": TierConfig(
            name="question-gen-llm",
            route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
            max_concurrency=4,
            per_call_timeout_s=120,
        ),
    }


register_workflow(WorkflowSpec(
    name="question_gen",
    input_schema=QuestionGenInput,
    output_schema=QuestionGenOutput,
    tiers=question_gen_tier_registry(),
    steps=[
        LLMStep(
            tier="question-gen-llm",
            prompt_template=(
                "Generate exactly {num_questions} questions about the following text.\n\n"
                "{chapter_text}"
            ),
            response_format=QuestionGenOutput,
        ),
        ValidateStep(target_field="questions", schema=QuestionGenOutput),
    ],
))
```

### Worked example — the CS-300 shape

```bash
# Your own package, editable-installed into the same environment as ai-workflows:
uv pip install -e .

# Run via env var:
AIW_EXTRA_WORKFLOW_MODULES=cs300.workflows.question_gen \
  aiw run question_gen --input chapter_text="Chapter 4 content here" \
                       --input num_questions=10 \
                       --run-id qg-1

# Or serve via MCP HTTP for an Astro / React / Vue frontend:
AIW_EXTRA_WORKFLOW_MODULES=cs300.workflows.question_gen,cs300.workflows.grade \
  aiw-mcp --transport http --port 8080 --cors-origin http://localhost:4321

# Or use the CLI flag instead of the env var:
aiw --workflow-module cs300.workflows.question_gen run question_gen \
    --input chapter_text="..." --input num_questions=5
```

### Failure mode

If any module named in the env var or flag fails to import, startup aborts with
`ExternalWorkflowImportError` (a subclass of `ImportError`) naming the dotted path and the
chained cause. Earlier entries in the list have already executed their top-level registration
side effects by the time a later entry raises — Python's import system does not roll back
partial loads, and the framework does not fake atomicity.

### User-owned code

Imported modules run in-process with full Python privileges. The framework surfaces import
errors but does not lint, test, or sandbox user code — that is the user's risk surface, not
ai-workflows' (see [ADR-0007](https://github.com/yeevon/ai-workflows/blob/design_branch/design_docs/adr/0007_user_owned_code_contract.md) (builder-only, on design branch)). Name collisions with shipped workflows are caught by the
existing registration re-binding check and fail loudly.

Entry-point discovery (PEP 621 `[project.entry-points.'ai_workflows.workflows']`) is a future
layer on top of this one; it is not currently implemented. The trigger would be a consumer
wanting to ship their workflows as a distributable pip package.

## Escape hatch — when the spec API isn't enough

The `register(name, build_fn)` API is preserved for workflows with non-standard topologies that
the linear step list cannot express — conditional routing, multiple terminal nodes, or
sub-graph composition patterns not covered by the five built-in step types.

Most workflows do not need the escape hatch. If you find yourself reaching for it, ask first
whether the pattern can be expressed as a custom step type (`Step` subclass with `compile()`
override — Tier 3). Custom step types compose with the spec API and do not require touching
LangGraph directly. See [`docs/writing-a-custom-step.md`](writing-a-custom-step.md) for the
`compile()` upgrade-path example.

If the pattern genuinely requires a hand-authored `StateGraph`, use the escape hatch:

```python
from langgraph.graph import StateGraph
from ai_workflows.workflows import register


def build_my_workflow() -> StateGraph:
    ...  # your StateGraph definition — return uncompiled


register("my_workflow", build_my_workflow)
```

See [`docs/writing-a-graph-primitive.md`](writing-a-graph-primitive.md) for the graph-layer
extension guide (audience: framework contributors or authors with genuinely non-standard
topologies).

## Testing your workflow

Use `StubLLMAdapter` from
[`ai_workflows/evals/_stub_adapter.py`](../ai_workflows/evals/_stub_adapter.py) to inject
deterministic LLM responses without a real provider call. The adapter records every prompt sent
and returns pre-scripted pydantic objects — LangGraph runs the full state machine, checkpoints,
validators, and retry edges end-to-end, but no token is spent.

```python
# Example test fixture pattern (hermetic — no provider calls):
import pytest
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.evals._stub_adapter import StubLLMAdapter


@pytest.fixture(autouse=True)
def stub_llm(monkeypatch):
    """Replace the LiteLLM adapter at the import site so no real provider call fires."""
    StubLLMAdapter.arm(expected_output='{"summary": "stubbed"}')
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", StubLLMAdapter)
    yield StubLLMAdapter
    StubLLMAdapter.disarm()
```

The framework also provides spec-compilation fixtures for unit-testing individual steps in
isolation — `compile_step_in_isolation` ships as part of T06's
`ai_workflows/workflows/testing.py` (see [`docs/writing-a-custom-step.md`](writing-a-custom-step.md)
for the testing-patterns section once T06 lands).

See `tests/workflows/test_summarize.py` for a complete 5-test hermetic suite demonstrating the
`StubLLMAdapter` pattern against the `summarize` workflow: registration, compilation,
round-trip dispatch, retry policy, and error handling.
