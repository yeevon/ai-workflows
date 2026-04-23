# Writing a Workflow

A walkthrough for authoring a new workflow: a Python module that builds a LangGraph `StateGraph`, composes graph-layer primitives, registers by name, and becomes reachable through both the `aiw` CLI and the `aiw-mcp` MCP surface.

If you have not read the [architecture overview](architecture.md) yet, start there — the four-layer model and the KDR-004 pairing rule are assumed below.

## Prerequisites

- `ai-workflows` installed (`uv tool install jmdl-ai-workflows` for a persistent install, or working from a clone with `uv sync`).
- `GEMINI_API_KEY` exported (or set in a cwd-local `.env` — auto-loaded as of 0.1.1) if your workflow routes through a LiteLLM-backed Gemini tier. Get a key at <https://aistudio.google.com/apikey>.
- `ollama serve` reachable at `http://127.0.0.1:11434` (or wherever `OLLAMA_BASE_URL` points) if your workflow uses a Qwen-via-Ollama tier.
- `claude` CLI on `PATH`, logged in via `claude login`, if your workflow routes to an `opus` / `sonnet` / `haiku` tier. No Anthropic API key is ever read (KDR-003) — Claude access is OAuth-only through the CLI subprocess.

## The `StateGraph` shape

A workflow is a zero-argument function that returns a compiled LangGraph `StateGraph`. State is a `TypedDict` or a Pydantic model; fields must be picklable so LangGraph's `SqliteSaver` can checkpoint mid-run.

The smallest useful shape:

1. A single node that reads a field from state.
2. A `TieredNode` that calls an LLM against that field.
3. A `ValidatorNode` that checks the LLM output against a Pydantic schema.
4. An edge from the validator to `END` (or back to retry via `RetryingEdge` on validation failure).

Every `TieredNode` must be followed by a `ValidatorNode` — this is KDR-004, enforced by convention, not by the framework. A workflow that violates the pairing rule is a contract break.

## Where tiers come from

**Tier names are chosen by the workflow author, and their routing is declared in Python — not in the repo-root `tiers.yaml` file.**

The committed [`tiers.yaml`](../tiers.yaml) is a schema-smoke fixture for the `TierRegistry` loader tests, not the authoritative tier binding at runtime. Dispatch (`ai_workflows.workflows._dispatch._resolve_tier_registry`) calls a `<workflow>_tier_registry()` helper that your workflow module exports; the helper returns a `dict[str, TierConfig]` naming the tiers this workflow uses and mapping them to provider routes.

Pattern from the shipped `planner` workflow ([`ai_workflows/workflows/planner.py`](../ai_workflows/workflows/planner.py)):

```python
from ai_workflows.primitives.tiers import (
    ClaudeCodeRoute,
    LiteLLMRoute,
    TierConfig,
)


def planner_tier_registry() -> dict[str, TierConfig]:
    return {
        "planner-explorer": TierConfig(
            name="planner-explorer",
            route=LiteLLMRoute(
                model="ollama/qwen2.5-coder:32b",
                api_base="http://localhost:11434",
            ),
            max_concurrency=1,
            per_call_timeout_s=180,
        ),
        "planner-synth": TierConfig(
            name="planner-synth",
            route=ClaudeCodeRoute(cli_model_flag="opus"),
            max_concurrency=1,
            per_call_timeout_s=300,
        ),
    }
```

Your `TieredNode` references those names:

```python
TieredNode(tier="planner-synth", ...)
```

Rules of thumb:

- **Name the tier by its role in your workflow**, not by the underlying model. `planner-synth`, `slice-worker`, `question-generator` make intent clear; `opus`, `gpt-4` leak the provider into the workflow body.
- **Two route kinds are supported today.** `LiteLLMRoute(model=...)` covers every LiteLLM-supported provider (Gemini, Ollama/Qwen, OpenAI, Anthropic-via-API, Cohere, Bedrock, Azure, ...). `ClaudeCodeRoute(cli_model_flag=...)` covers the OAuth-subprocess Claude Code path (KDR-003 + KDR-007 + KDR-011). Secrets flow through the `${VAR:-default}` env-var expansion the `TierConfig` parser already supports — never literal keys in your registry.
- **The runtime `--tier-override <logical>=<replacement>` flag repoints one tier name to another** of the tiers this workflow declares. It is a peer-level swap within the workflow's registry, not a model-level override. M15 (planned) introduces a `AIW_TIERS_PATH` user-overlay that rebinds tier names at the registry level without editing workflow Python.

## Composing the graph primitives

The four building blocks, in order of typical use:

**`TieredNode`** — from [`ai_workflows/graph/tiered_node.py`](../ai_workflows/graph/tiered_node.py). Wraps one LLM call. Takes a `tier` name (whatever your workflow's `<workflow>_tier_registry()` declares), a prompt template, and a Pydantic `response_format` class. At runtime it looks up the tier in the workflow's registry + routes to the right provider adapter — LiteLLM for `LiteLLMRoute`, the OAuth subprocess driver for `ClaudeCodeRoute`.

**`ValidatorNode`** — from [`ai_workflows/graph/validator_node.py`](../ai_workflows/graph/validator_node.py). Takes the LLM output and validates it against a Pydantic schema. On success, writes the validated object to state and routes forward. On failure, routes to a `RetryingEdge` which classifies the failure and decides whether to retry or stop.

**`HumanGate`** — from [`ai_workflows/graph/human_gate.py`](../ai_workflows/graph/human_gate.py). Pauses the run, persists a checkpoint via `SqliteSaver`, and exits with `paused` status. The operator reviews the run's state (via `aiw list-runs` + the MCP `list_runs` tool, plus the gate-pause projection M11 surfaces in `RunWorkflowOutput.gate_context`) and resumes via `aiw resume <run_id> --approve` or the MCP `resume_run` tool.

**`RetryingEdge`** — from [`ai_workflows/graph/retrying_edge.py`](../ai_workflows/graph/retrying_edge.py). Implements the three-bucket retry taxonomy (KDR-006). Transient failures (network, rate limit) retry with backoff. Deterministic failures (schema mismatch) retry up to the bucket cap with the validator's error surfaced into the next prompt. Hard-stop failures (provider outage, auth) fail the run. Do not write your own retry loop — compose `RetryingEdge`.

## Registration

At the bottom of your workflow module, call `ai_workflows.workflows.register(name, builder)`. The name is the string a caller uses to reach the workflow: `aiw run <name>`, or the `workflow` argument to the MCP `run_workflow` tool.

Registration is idempotent under re-import and raises `ValueError` on a name collision with a different builder.

## Worked example — the `echo` workflow

A minimal workflow: take a goal string, send it to a Gemini-backed tier the workflow declares as `echo-responder`, validate the response shape, return the echoed text.

```python
from typing import TypedDict

from pydantic import BaseModel, ConfigDict
from langgraph.graph import END, START, StateGraph

from ai_workflows.graph.tiered_node import TieredNode
from ai_workflows.graph.validator_node import ValidatorNode
from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig
from ai_workflows.workflows import register


class EchoState(TypedDict):
    goal: str
    response: str


class EchoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    echoed: str


def echo_tier_registry() -> dict[str, TierConfig]:
    return {
        "echo-responder": TierConfig(
            name="echo-responder",
            route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
            max_concurrency=1,
        ),
    }


def build() -> StateGraph:
    graph = StateGraph(EchoState)

    graph.add_node(
        "call",
        TieredNode(
            tier="echo-responder",
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

The same workflow is reachable over MCP as `run_workflow(workflow="echo", input={"goal": "hello, world"}, run_id="demo")`.

## Testing a workflow

Use `StubLLMAdapter` from [`ai_workflows/evals/_stub_adapter.py`](../ai_workflows/evals/_stub_adapter.py) to inject deterministic LLM responses without making a real provider call. The adapter records every prompt sent and returns pre-scripted Pydantic objects — LangGraph runs the full state machine, checkpoints, validators, and retry edges end-to-end, but no token is spent.

The test gallery under `tests/workflows/` on the `design` branch (builder-only, on design branch) is the reference for the patterns — one test module per workflow, `StubLLMAdapter` wired through a fixture, real `SQLiteStorage` + real `SqliteSaver` against a `tmp_path` database.

## Surfaces are automatic

Once `register("<name>", build)` fires at module-import time, the workflow is reachable from every surface:

- `aiw run <name> --goal ... --run-id ...` — start a new run.
- `aiw resume <run_id> --approve` — resume a paused run through the next `HumanGate`.
- `aiw list-runs` / `aiw list-runs --workflow <name> --status completed` — query the run registry. Status queries use this command; there is no `get_run_status` tool.
- MCP tools: `run_workflow`, `resume_run`, `list_runs`, `cancel_run` — the four-tool surface; identical semantics over stdio and streamable-HTTP transports.

No per-workflow CLI code to write, no per-workflow MCP schema edit. The `workflows` registry is the single coupling point; every surface reads from it.
