# Architecture

A one-file orientation for developers new to `ai-workflows`. For the architecture of record used by maintainers, see `design_docs/architecture.md` (builder-only, on design branch).

## What this project is

`ai-workflows` is a LangGraph-native workflow framework. You write a workflow as a Python module that builds a `langgraph.graph.StateGraph`, register it by name, and reach it through two public surfaces: a CLI (`aiw`) and an MCP server (`aiw-mcp`). The framework runs on a laptop with `uv` plus provider keys — there is no external control plane, no Kubernetes, no hosted scheduler.

Providers are Gemini (via LiteLLM; `GEMINI_API_KEY`), Ollama (local Qwen models for the `local_coder` tier), and Claude Code (OAuth CLI subprocess for the `claude_code` tier). There is no Anthropic API call anywhere in the codebase — the Claude path is OAuth-only via the `claude` CLI subprocess. This is KDR-003.

## Four-layer model

The package is split into four subpackages with a strict one-way dependency direction enforced by `import-linter` (run `uv run lint-imports` to check).

| Layer | Subpackage | Role |
| --- | --- | --- |
| `primitives` | [`ai_workflows/primitives/`](../ai_workflows/primitives/) | Storage (SQLite run registry + gate log), cost tracking, provider adapters, tier routing, retry taxonomy, structured logging. |
| `graph` | [`ai_workflows/graph/`](../ai_workflows/graph/) | LangGraph adapters that compose primitives into reusable nodes: `TieredNode`, `ValidatorNode`, `HumanGate`, `RetryingEdge`, `CostTrackingCallback`, the `SqliteSaver` checkpointer wrapper. |
| `workflows` | [`ai_workflows/workflows/`](../ai_workflows/workflows/) | Concrete `StateGraph` definitions that compose graph primitives. One module per workflow. Each module self-registers by name at import time. |
| `surfaces` | [`ai_workflows/cli.py`](../ai_workflows/cli.py) + [`ai_workflows/mcp/`](../ai_workflows/mcp/) | The two public entry points. `aiw` for interactive + scripting use, `aiw-mcp` for MCP clients (Claude Code, Cursor, Zed, browser-origin via streamable-HTTP). |

The dependency direction is `primitives → graph → workflows → surfaces`. No layer may import from a higher layer. A `workflows` module may import from `graph` + `primitives`; a `graph` module may import from `primitives` only; `primitives` modules import nothing from the package above them.

## LangGraph substrate

A workflow is a `StateGraph` — a state machine where each node is a Python function that reads + writes a shared state dict. The shape is per-workflow, free-form, and must be picklable so LangGraph's built-in `SqliteSaver` can checkpoint mid-run. State persistence is handled entirely by LangGraph's checkpointer — the framework does not hand-roll checkpoint writes. This is KDR-009.

A workflow author composes four kinds of graph-layer primitives:

- **`TieredNode`** wraps an LLM call and routes it to the requested tier (`orchestrator`, `implementer`, or `gemini_flash` for Gemini; `local_coder` for Ollama; `claude_code` for the OAuth CLI subprocess). One node per LLM call.
- **`ValidatorNode`** goes immediately after every `TieredNode`. It validates the LLM output against a Pydantic schema and routes to retry or continue. A workflow that adds a `TieredNode` without a paired `ValidatorNode` is a contract violation — this is KDR-004.
- **`HumanGate`** pauses the run, writes a LangGraph checkpoint, and exits with `paused` status. A human reviews the state, then resumes via `aiw resume <run_id>` or the MCP `resume_run` tool.
- **`RetryingEdge`** is wired between a `ValidatorNode` and the retry target. It classifies failures into three buckets — transient (network / rate limit), deterministic (schema mismatch), or hard-stop (provider outage) — and routes each differently. This is KDR-006. No workflow should hand-roll its own retry loop.

Structured logging via the `StructuredLogger` primitive is the only supported observability backend at v0.1.0. External backends (Langfuse, OpenTelemetry, LangSmith) are deferred.

## Public surfaces

Two. Both are thin wrappers over the `workflows` layer.

**`aiw` CLI.** Entry point in [`ai_workflows/cli.py`](../ai_workflows/cli.py). Subcommands include `run <workflow> --goal ... --run-id ...`, `resume <run_id>`, `list-runs`, `cancel <run_id>`, and `eval` for the prompt-regression harness. Built with Typer; arguments map 1:1 to workflow parameters.

**`aiw-mcp` MCP server.** Entry point under [`ai_workflows/mcp/`](../ai_workflows/mcp/). Built with FastMCP (KDR-008); MCP tool schemas derive from Pydantic model signatures. The v0.1.0 tool surface exposes `run_workflow`, `resume_run`, `list_runs`, `cancel_run`, and `get_run_status`. Browser-origin consumers reach the same tools via the streamable-HTTP transport added at M14.

MCP tool schemas are the public contract. The shape of every tool's input + output Pydantic model at v0.1.0 is part of the semantic-version contract — a schema change is a major-version change. This is KDR-008.

## Key design decisions

The five KDRs load-bearing at v0.1.0:

| ID | Decision |
| --- | --- |
| KDR-002 | MCP server is the portable inside-out surface; the Claude Code skill is optional packaging, not the substrate. |
| KDR-003 | No Anthropic API. Runtime tiers are Gemini + Qwen; Claude access is OAuth-only via the `claude` CLI subprocess. |
| KDR-004 | Validator-node-after-every-LLM-node is mandatory. Prompting is a schema contract. |
| KDR-008 | FastMCP is the server implementation; tool schemas derive from Pydantic signatures and are the public v0.1.0 contract. |
| KDR-009 | LangGraph's built-in `SqliteSaver` owns checkpoint persistence. The primitives `Storage` layer owns run registry + gate log only. |

Deep-dives for each KDR live in the builder-facing `design_docs/architecture.md §9` (builder-only, on design branch).

## Where to go next

- **Write your first workflow:** [`docs/writing-a-workflow.md`](writing-a-workflow.md).
- **Extend the graph layer with a new adapter:** [`docs/writing-a-graph-primitive.md`](writing-a-graph-primitive.md).
- **Install + first run:** the [README](../README.md) Install section.
