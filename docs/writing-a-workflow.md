# Writing a Workflow

A walkthrough for authoring a new workflow: a Python module that builds a LangGraph `StateGraph`, composes graph-layer primitives, registers by name, and becomes reachable through both the `aiw` CLI and the `aiw-mcp` MCP surface.

If you have not read the [architecture overview](architecture.md) yet, start there — the four-layer model and the KDR-004 pairing rule are assumed below.

## Prerequisites

- `ai-workflows` installed (`uv tool install ai-workflows` for a persistent install, or working from a clone with `uv sync`).
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
