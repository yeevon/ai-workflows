# Writing a Workflow

A walkthrough for authoring a new workflow: a Python module that builds a LangGraph `StateGraph`, composes graph-layer primitives, registers by name, and becomes reachable through both the `aiw` CLI and the `aiw-mcp` MCP surface.

If you have not read the [architecture overview](architecture.md) yet, start there — the four-layer model and the KDR-004 pairing rule are assumed below.

## Prerequisites

- `ai-workflows` installed (`uv tool install jmdl-ai-workflows` for a persistent install, or working from a clone with `uv sync`).
- `GEMINI_API_KEY` exported if your workflow uses the Gemini-backed tiers (`orchestrator`, `implementer`, `gemini_flash`).
- `ollama serve` reachable at `http://127.0.0.1:11434` if your workflow uses the `local_coder` tier.
- `claude` CLI on `PATH` (logged in via `claude login`) if your workflow uses the `claude_code` tier.

## The `StateGraph` shape

A workflow is a zero-argument function that returns a compiled LangGraph `StateGraph`. State is a `TypedDict` or a Pydantic model; fields must be picklable so LangGraph's `SqliteSaver` can checkpoint mid-run.

The smallest useful shape:

1. A single node that reads a field from state.
2. A `TieredNode` that calls an LLM against that field.
3. A `ValidatorNode` that checks the LLM output against a Pydantic schema.
4. An edge from the validator to `END` (or back to retry via `RetryingEdge` on validation failure).

Every `TieredNode` must be followed by a `ValidatorNode` — this is KDR-004, enforced by convention, not by the framework. A workflow that violates the pairing rule is a contract break.

## Composing the graph primitives

The four building blocks, in order of typical use:

**`TieredNode`** — from [`ai_workflows/graph/tiered_node.py`](../ai_workflows/graph/tiered_node.py). Wraps one LLM call. Takes a `tier` name (one of `orchestrator`, `implementer`, `gemini_flash`, `local_coder`, `claude_code`), a prompt template, and a Pydantic `response_format` class. At runtime it routes to the right provider adapter — Gemini via LiteLLM, Ollama via the local HTTP API, or Claude Code via the OAuth CLI subprocess.

**`ValidatorNode`** — from [`ai_workflows/graph/validator_node.py`](../ai_workflows/graph/validator_node.py). Takes the LLM output and validates it against a Pydantic schema. On success, writes the validated object to state and routes forward. On failure, routes to a `RetryingEdge` which classifies the failure and decides whether to retry or stop.

**`HumanGate`** — from [`ai_workflows/graph/human_gate.py`](../ai_workflows/graph/human_gate.py). Pauses the run, persists a checkpoint via `SqliteSaver`, and exits with `paused` status. The operator reviews the run's state (via `aiw list-runs` + the run's state dump) and resumes via `aiw resume <run_id> --approve` or the MCP `resume_run` tool.

**`RetryingEdge`** — from [`ai_workflows/graph/retrying_edge.py`](../ai_workflows/graph/retrying_edge.py). Implements the three-bucket retry taxonomy (KDR-006). Transient failures (network, rate limit) retry with backoff. Deterministic failures (schema mismatch) retry up to the bucket cap with the validator's error surfaced into the next prompt. Hard-stop failures (provider outage, auth) fail the run. Do not write your own retry loop — compose `RetryingEdge`.

## Registration

At the bottom of your workflow module, call `ai_workflows.workflows.register(name, builder)`. The name is the string a caller uses to reach the workflow: `aiw run <name>`, or the `workflow_id` argument to the MCP `run_workflow` tool.

Registration is idempotent under re-import and raises `ValueError` on a name collision with a different builder.

## Worked example — the `echo` workflow

A minimal workflow: take a goal string, send it to the `gemini_flash` tier, validate the response shape, return the echoed text.

```python
from typing import TypedDict

from pydantic import BaseModel, ConfigDict
from langgraph.graph import END, START, StateGraph

from ai_workflows.graph.tiered_node import TieredNode
from ai_workflows.graph.validator_node import ValidatorNode
from ai_workflows.workflows import register


class EchoState(TypedDict):
    goal: str
    response: str


class EchoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    echoed: str


def build() -> StateGraph:
    graph = StateGraph(EchoState)

    graph.add_node(
        "call",
        TieredNode(
            tier="gemini_flash",
            prompt_template="Echo this back verbatim: {goal}",
            response_format=EchoResponse,
        ),
    )
    graph.add_node(
        "validate",
        ValidatorNode(response_format=EchoResponse),
    )

    graph.add_edge(START, "call")
    graph.add_edge("call", "validate")
    graph.add_edge("validate", END)

    return graph.compile()


register("echo", build)
```

Save as `ai_workflows/workflows/echo.py`. Run it:

```bash
aiw run echo --goal 'hello, world' --run-id demo
```

The same workflow is reachable over MCP as `run_workflow(workflow_id="echo", goal="hello, world", run_id="demo")`.

## Testing a workflow

Use `StubLLMAdapter` from [`ai_workflows/evals/_stub_adapter.py`](../ai_workflows/evals/_stub_adapter.py) to inject deterministic LLM responses without making a real provider call. The adapter records every prompt sent and returns pre-scripted Pydantic objects — LangGraph runs the full state machine, checkpoints, validators, and retry edges end-to-end, but no token is spent.

The test gallery under `tests/workflows/` on the `design` branch (builder-only, on design branch) is the reference for the patterns — one test module per workflow, `StubLLMAdapter` wired through a fixture, real `SQLiteStorage` + real `SqliteSaver` against a `tmp_path` database.

## Surfaces are automatic

Once `register("<name>", build)` fires at module-import time, the workflow is reachable from every surface:

- `aiw run <name> --goal ... --run-id ...` — start a new run.
- `aiw resume <run_id> --approve` — resume a paused run through the next `HumanGate`.
- `aiw list-runs` / `aiw list-runs --workflow <name> --status completed` — query the run registry.
- `aiw cancel <run_id>` — mark a run cancelled.
- MCP tools: `run_workflow`, `resume_run`, `list_runs`, `cancel_run`, `get_run_status` — identical semantics over the MCP surface.

No per-workflow CLI code to write, no per-workflow MCP schema edit. The `workflows` registry is the single coupling point; every surface reads from it.

## External workflows from a downstream consumer

A consumer of the published `jmdl-ai-workflows` wheel can register their own workflow modules without forking the package. Two surfaces, both honoured by `aiw` and `aiw-mcp`:

1. **`AIW_EXTRA_WORKFLOW_MODULES`** — comma-separated dotted Python module paths.
2. **`--workflow-module <dotted>`** — repeatable CLI flag on both commands; composes with the env var (env entries import first, then CLI entries).

Each entry is imported via `importlib.import_module(...)` at startup; the module's top-level `register("name", build)` call lands the workflow in the shared registry. The module must already be importable via the running interpreter's `sys.path` — the typical layout is a pip-installable package, editable or otherwise.

### Minimum module shape

```python
# cs300/workflows/question_gen.py

from langgraph.graph import StateGraph

from ai_workflows.workflows import register


def build() -> StateGraph:
    ...  # your StateGraph definition


def question_gen_tier_registry() -> dict:
    """Optional. Return {tier_name: TierConfig, ...} for any LLM tiers
    the workflow dispatches. Omit the helper if the workflow makes no
    LLM calls."""
    return {}


register("question_gen", build)
```

### Worked example — the CS-300 shape

```bash
# Your own package, editable-installed into the same environment as ai-workflows:
uv pip install -e .

# Run via env var:
AIW_EXTRA_WORKFLOW_MODULES=cs300.workflows.question_gen \
  aiw run question_gen --goal 'write 10 questions about chapter 4' --run-id qg-1

# Or serve via MCP HTTP for an Astro / React / Vue frontend:
AIW_EXTRA_WORKFLOW_MODULES=cs300.workflows.question_gen,cs300.workflows.grade \
  aiw-mcp --transport http --port 8080 --cors-origin http://localhost:4321

# Or use the CLI flag instead of the env var:
aiw --workflow-module cs300.workflows.question_gen run question_gen --goal '...'
```

### Failure mode

If any module named in the env var or flag fails to import, startup aborts with `ExternalWorkflowImportError` (a subclass of `ImportError`) naming the dotted path and the chained cause. Earlier entries in the list have already executed their top-level `register()` side effects by the time a later entry raises — Python's import system does not roll back partial loads, and the framework does not fake atomicity. In practice this is the same semantic Python itself uses for `from pkg import a, b, c` with a broken `b`.

### User-owned code

Imported modules run in-process with full Python privileges. The framework surfaces import errors but does not lint, test, or sandbox user code — that is the user's risk surface, not ai-workflows' (see [ADR-0007](https://github.com/yeevon/ai-workflows/blob/design_branch/design_docs/adr/0007_user_owned_code_contract.md) on the builder branch). Name collisions with shipped workflows are caught by the existing `register()` re-binding check and fail loudly.

Entry-point discovery (PEP 621 `[project.entry-points.'ai_workflows.workflows']`) is a future layer on top of this one; it is not currently implemented. The trigger would be a consumer wanting to ship their workflows as a distributable pip package.
