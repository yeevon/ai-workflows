# Architecture

A one-file orientation for developers new to `ai-workflows`. For the architecture of record used by maintainers, see `design_docs/architecture.md` (builder-only, on design branch).

## What this project is

`ai-workflows` is a LangGraph-native workflow framework. You write a workflow as a Python module that builds a `langgraph.graph.StateGraph`, register it by name, and reach it through two public surfaces: a CLI (`aiw`) and an MCP server (`aiw-mcp`). The framework runs on a laptop with `uv` plus provider keys — there is no external control plane, no Kubernetes, no hosted scheduler.

Providers are Gemini (via LiteLLM, requires `GEMINI_API_KEY`), Ollama (local Qwen models, dispatched by LiteLLM as well), and Claude Code (OAuth CLI subprocess via `ClaudeCodeRoute`). Each workflow declares which providers it touches by composing `LiteLLMRoute` / `ClaudeCodeRoute` records into its `<workflow>_tier_registry()` helper — see the LangGraph substrate section. There is no Anthropic API call anywhere in the codebase. This is KDR-003.

## Four-layer model

The package is split into four subpackages with a strict one-way dependency direction enforced by `import-linter` (run `uv run lint-imports` to check).

| Layer | Subpackage | Role |
| --- | --- | --- |
| `primitives` | [`ai_workflows/primitives/`](../ai_workflows/primitives/) | Storage (SQLite run registry + gate log), cost tracking, provider adapters, tier routing, retry taxonomy, structured logging. |
| `graph` | [`ai_workflows/graph/`](../ai_workflows/graph/) | LangGraph adapters that compose primitives into reusable nodes: `TieredNode`, `ValidatorNode`, `HumanGate`, `RetryingEdge`, `CostTrackingCallback`, the `SqliteSaver` checkpointer wrapper. |
| `workflows` | [`ai_workflows/workflows/`](../ai_workflows/workflows/) | Concrete `StateGraph` definitions that compose graph primitives. One module per workflow. In-package modules self-register by name at import time; downstream consumers register their own modules at startup via `AIW_EXTRA_WORKFLOW_MODULES` or `--workflow-module` (M16 Task 01 / KDR-013). |
| `surfaces` | [`ai_workflows/cli.py`](../ai_workflows/cli.py) + [`ai_workflows/mcp/`](../ai_workflows/mcp/) | The two public entry points. `aiw` for interactive + scripting use, `aiw-mcp` for MCP clients (Claude Code, Cursor, Zed, browser-origin via streamable-HTTP). |

The dependency direction is `primitives → graph → workflows → surfaces`. No layer may import from a higher layer. A `workflows` module may import from `graph` + `primitives`; a `graph` module may import from `primitives` only; `primitives` modules import nothing from the package above them.

## LangGraph substrate

A workflow is a `StateGraph` — a state machine where each node is a Python function that reads + writes a shared state dict. The shape is per-workflow, free-form, and must be picklable so LangGraph's built-in `SqliteSaver` can checkpoint mid-run. State persistence is handled entirely by LangGraph's checkpointer — the framework does not hand-roll checkpoint writes. This is KDR-009.

A workflow author composes four kinds of graph-layer primitives:

- **`TieredNode`** wraps an LLM call and routes it to the requested tier. Tier names are per-workflow — each workflow module exports a `<workflow>_tier_registry()` helper that maps tier names to `TierConfig` records (e.g. the shipped `planner` declares `planner-explorer` → Qwen via Ollama and `planner-synth` → Claude Code Opus via OAuth subprocess). The repo-root `tiers.yaml` is a schema-smoke fixture for `tests/primitives/test_tiers_loader.py`, **not** loaded at dispatch. One node per LLM call.
- **`ValidatorNode`** goes immediately after every `TieredNode`. It validates the LLM output against a Pydantic schema and routes to retry or continue. A workflow that adds a `TieredNode` without a paired `ValidatorNode` is a contract violation — this is KDR-004.
- **`HumanGate`** pauses the run, writes a LangGraph checkpoint, and exits with `paused` status. A human reviews the state, then resumes via `aiw resume <run_id>` or the MCP `resume_run` tool.
- **`RetryingEdge`** is wired between a `ValidatorNode` and the retry target. It classifies failures into three buckets — transient (network / rate limit), deterministic (schema mismatch), or hard-stop (provider outage) — and routes each differently. This is KDR-006. No workflow should hand-roll its own retry loop.

Structured logging via the `StructuredLogger` primitive is the only supported observability backend. External backends (Langfuse, OpenTelemetry, LangSmith) are deferred.

## Public surfaces

Two. Both are thin wrappers over the `workflows` layer.

**`aiw` CLI.** Entry point in [`ai_workflows/cli.py`](../ai_workflows/cli.py). Subcommands include `run <workflow> --goal ... --run-id ...`, `resume <run_id>`, `list-runs`, `cancel <run_id>`, and `eval` for the prompt-regression harness. Built with Typer; arguments map 1:1 to workflow parameters. Both surfaces accept `--workflow-module <dotted>` (repeatable) at the root, composing with the `AIW_EXTRA_WORKFLOW_MODULES` env var to load downstream consumers' workflow modules at startup (M16 Task 01).

**`aiw-mcp` MCP server.** Entry point under [`ai_workflows/mcp/`](../ai_workflows/mcp/). Built with FastMCP (KDR-008); MCP tool schemas derive from Pydantic model signatures. The current tool surface exposes `run_workflow`, `resume_run`, `list_runs`, and `cancel_run` — `list_runs` answers status queries via its `--status` filter. Browser-origin consumers reach the same tools via the streamable-HTTP transport added at M14.

MCP tool schemas are the public contract. The shape of every tool's input + output Pydantic model is part of the semantic-version contract — a schema change is a major-version change. This is KDR-008.

## Key design decisions

The six load-bearing KDRs as of 0.2.0:

| ID | Decision |
| --- | --- |
| KDR-002 | MCP server is the portable inside-out surface; the Claude Code skill is optional packaging, not the substrate. |
| KDR-003 | No Anthropic API. Runtime tiers are Gemini + Qwen; Claude access is OAuth-only via the `claude` CLI subprocess. |
| KDR-004 | Validator-node-after-every-LLM-node is mandatory. Prompting is a schema contract. |
| KDR-008 | FastMCP is the server implementation; tool schemas derive from Pydantic signatures and are the public contract. |
| KDR-009 | LangGraph's built-in `SqliteSaver` owns checkpoint persistence. The primitives `Storage` layer owns run registry + gate log only. |
| KDR-013 | User code is user-owned. Externally-registered workflow modules (M16 Task 01) run in-process with full Python privileges; the framework surfaces import errors but does not lint, test, or sandbox them. In-package workflows cannot be shadowed (register-time collision guard). |

Deep-dives for each KDR live in the builder-facing `design_docs/architecture.md §9` (builder-only, on design branch).

## Where to go next

- **Write your first workflow:** [`docs/writing-a-workflow.md`](writing-a-workflow.md).
- **Register a workflow from a downstream package:** [`docs/writing-a-workflow.md §External workflows from a downstream consumer`](writing-a-workflow.md#external-workflows-from-a-downstream-consumer).
- **Extend the graph layer with a new adapter:** [`docs/writing-a-graph-primitive.md`](writing-a-graph-primitive.md).
- **Install + first run:** the [README](../README.md) Install section.
