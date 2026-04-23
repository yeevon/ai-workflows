# ai-workflows

A framework for building multi-step AI workflows that can plan, execute, validate, and recover from failures. Supports multiple models (Claude, Gemini, Ollama), human approval steps, and resumable runs with persistent state.

A LangGraph-native workflow framework for solo developers. Orchestrates multi-step AI workflows with durable state, multi-provider routing, and deterministic cost accounting across Gemini (via LiteLLM), Qwen (via Ollama), and Claude Code (via OAuth CLI subprocess).

## Status

| Milestone | State |
| --- | --- |
| **M1 — Reconciliation & cleanup** | Complete (2026-04-19) |
| **M2 — Graph-layer adapters + provider drivers** | Complete (2026-04-19) |
| **M3 — First workflow (`planner`, single tier)** | Complete (2026-04-20) |
| **M4 — MCP server (FastMCP)** | Complete (2026-04-20) |
| **M5 — Multi-tier `planner`** | Complete (2026-04-20) |
| **M6 — `slice_refactor` DAG** | Complete (2026-04-20) |
| **M7 — Eval harness** | Complete (2026-04-21) |
| **M8 — Ollama infrastructure** | Complete (2026-04-21) |
| **M9 — Claude Code skill packaging** | Complete (2026-04-21) |
| M10 — Ollama fault-tolerance hardening | Planned |
| **M11 — MCP gate-review surface** | Complete (2026-04-22) |
| M12 — Tiered audit cascade | Planned |
| M13 — v0.1.0 release + PyPI packaging | In progress |
| **M14 — MCP HTTP transport** | Complete (2026-04-22) |

## What it is

`ai-workflows` exposes two surfaces over the same workflow registry: an `aiw` CLI for interactive and scripted use, and an `aiw-mcp` MCP server for Claude Code, Cursor, Zed, and browser-origin consumers (via streamable-HTTP). A workflow is a Python module that builds a LangGraph `StateGraph` composed of graph primitives (`TieredNode`, `ValidatorNode`, `HumanGate`, `RetryingEdge`) and registered by name. There is no hosted control plane and no Anthropic API dependency — Claude access is OAuth-only through the `claude` CLI subprocess.

## Architecture at a glance

Four layers with a one-way dependency direction enforced by `import-linter`:

```text
surfaces        (ai_workflows.cli, ai_workflows.mcp)
    ↓
workflows       (ai_workflows.workflows.*)        — concrete LangGraph StateGraphs
    ↓
graph           (ai_workflows.graph.*)            — LangGraph adapters over primitives
    ↓
primitives      (ai_workflows.primitives.*)       — storage, cost, tiers, providers, retry, logging
```

Full overview in [docs/architecture.md](docs/architecture.md). Tutorials for authoring a new workflow or extending the graph layer live at [docs/writing-a-workflow.md](docs/writing-a-workflow.md) and [docs/writing-a-graph-primitive.md](docs/writing-a-graph-primitive.md).

## Install

Requires Python ≥ 3.12 and [uv](https://github.com/astral-sh/uv).

**One-shot via `uvx`** — no persistent install; every invocation fetches the wheel into a cache:

```bash
uvx --from jmdl-ai-workflows aiw run planner --goal 'Write a release checklist' --run-id demo
```

**Persistent tool install** — puts `aiw` + `aiw-mcp` on `PATH`:

```bash
uv tool install jmdl-ai-workflows
aiw run planner --goal 'Write a release checklist' --run-id demo
```

## Getting started

After installing (either path above), set your Gemini API key and drive a planner run end-to-end:

```bash
export GEMINI_API_KEY=...
aiw run planner --goal 'Write a release checklist' --run-id demo
aiw resume demo --approve
aiw list-runs
```

The planner workflow composes two LLM tiers (Qwen explorer via Ollama + Claude Code Opus synth). If you only want the Gemini path for a smoke, pass `--tier-override planner-synth=planner-explorer` or omit the Ollama + Claude Code prerequisites and stub the `gemini_flash` tier.

## MCP server

Register `aiw-mcp` with any MCP host — Claude Code, Cursor, Zed, or an HTTP client via the streamable-HTTP transport — to drive the same workflows inside-out:

```bash
claude mcp add ai-workflows --scope user -- uvx --from jmdl-ai-workflows aiw-mcp
```

The HTTP transport is opt-in for browser-origin consumers: `aiw-mcp --transport http --port 8080 --cors-origin http://localhost:3000`. Full skill-install walkthrough (builder-only, on design branch).

## Contributing / from source

Clone the repo for development or to modify the framework itself:

```bash
git clone https://github.com/yeevon/ai-workflows.git
cd ai-workflows
uv sync              # install runtime + dev dependencies
uv run aiw version   # prints 0.1.0
```

For the full builder/auditor workflow — task specs, audit issue files, Builder / Auditor mode conventions — switch to the [`design_branch`](https://github.com/yeevon/ai-workflows/tree/design_branch) (builder-only, on design branch).

## Development

Three gates guard every change:

```bash
uv run pytest         # unit + scaffolding tests (hermetic; skips e2e unless AIW_E2E=1)
uv run lint-imports   # four-layer import contract
uv run ruff check     # style + basic correctness
```

## Next

Roadmap + per-milestone task files live at [design_docs/roadmap.md](design_docs/roadmap.md) (builder-only, on design branch).
