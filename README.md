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
| **M13 — v0.1.0 release + PyPI packaging** | Complete (2026-04-22) |
| **M14 — MCP HTTP transport** | Complete (2026-04-22) |
| M15 — Tier overlay + fallback chains | Planned |
| **M16 — External workflows + primitives load path** | Complete (2026-04-24) |
| M17 — `scaffold_workflow` meta-workflow | Planned |
| **M19 — Declarative authoring surface** | Complete (2026-04-26) |
| **M20 — Autonomy loop optimization** | Complete (2026-04-28) |

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

### Setup

Both `aiw` and `aiw-mcp` auto-load a `.env` from the current working directory at startup (shell-exported values win over `.env`).

**Key env vars:**
- `GEMINI_API_KEY` — required for any workflow using a Gemini tier (most defaults).
- `OLLAMA_BASE_URL` — default `http://localhost:11434`; override if your Ollama daemon listens elsewhere.
- `AIW_STORAGE_DB` / `AIW_CHECKPOINT_DB` — path overrides for the run registry and checkpoint databases (defaults: `~/.ai-workflows/storage.sqlite3` / `~/.ai-workflows/checkpoint.sqlite3`).

**Claude Code tier:** some workflows route to the `claude` CLI via OAuth. Install and authenticate it separately per [Anthropic's setup docs](https://docs.claude.com/en/docs/claude-code/setup). `aiw` never reads `ANTHROPIC_API_KEY` and never imports the `anthropic` SDK — Claude access is OAuth-only through the CLI subprocess.

## Extending ai-workflows

ai-workflows is a declarative orchestration layer; extension is a first-class capability. Authors engage at four progressively-deeper tiers, each with a dedicated guide:

| Tier | When | Guide |
|---|---|---|
| 1 — Compose | You're combining built-in step types (`LLMStep`, `ValidateStep`, `GateStep`, `TransformStep`, `FanOutStep`) into a workflow. The happy path. | [docs/writing-a-workflow.md](docs/writing-a-workflow.md) |
| 2 — Parameterise | You're configuring built-in steps (retry policy, response format, gate behaviour, tier choice). | [docs/writing-a-workflow.md](docs/writing-a-workflow.md) (same doc) |
| 3 — Author a custom step type | No built-in covers your need. Subclass `Step`; the framework wires your custom step into the graph like a built-in. | [docs/writing-a-custom-step.md](docs/writing-a-custom-step.md) |
| 4 — Escape to LangGraph directly | Your topology is genuinely non-standard (dynamic edge conditions, novel control flow). Use the legacy `register(name, build_fn)` API. | [docs/writing-a-graph-primitive.md](docs/writing-a-graph-primitive.md) |

The framework's promise: descending a tier never forces you to reverse-engineer framework source. If you're at the wrong tier, you'll find pointers to the right one in any guide.

## MCP server

Register `aiw-mcp` with any MCP host — Claude Code, Cursor, Zed, or an HTTP client via the streamable-HTTP transport — to drive the same workflows inside-out:

```bash
claude mcp add ai-workflows --scope user -- uvx --from jmdl-ai-workflows aiw-mcp
```

The HTTP transport is opt-in for browser-origin consumers: `aiw-mcp --transport http --port 8080 --cors-origin http://localhost:3000`.

Registering your own workflow modules from a downstream package? `AIW_EXTRA_WORKFLOW_MODULES=pkg.workflows.your_workflow` (or `--workflow-module pkg.workflows.your_workflow`, repeatable) imports them at startup. See [docs/writing-a-workflow.md §External workflows from a downstream consumer](docs/writing-a-workflow.md#external-workflows-from-a-downstream-consumer).

### Security notes

- **Loopback default** — `aiw-mcp --transport http` binds to `127.0.0.1`; unreachable from other machines. `--host 0.0.0.0` exposes the server to every process on the host and to the LAN. `aiw-mcp` has no built-in auth; the bind address is the only access boundary. Only pass `--host 0.0.0.0` on a machine you own every process on, and put a reverse proxy in front if you need TLS.
- **CORS is opt-in, exact-match** — `--cors-origin <url>` adds one origin; without any flags the server emits no `Access-Control-Allow-Origin` header (same-origin only). Not required for stdio or loopback HTTP.

## Contributing / from source

Clone the repo for development or to modify the framework itself:

```bash
git clone https://github.com/yeevon/ai-workflows.git
cd ai-workflows
uv sync              # install runtime + dev dependencies
uv run aiw version   # prints the current __version__ (0.3.0 at M19 close)
```

For the full builder/auditor workflow — task specs, audit issue files, Builder / Auditor mode conventions — switch to the `design_branch`.

## Development

Three gates guard every change:

```bash
uv run pytest         # unit + scaffolding tests (hermetic; skips e2e unless AIW_E2E=1)
uv run lint-imports   # four-layer import contract
uv run ruff check     # style + basic correctness
```

## Next

**M21 — Autonomy Loop Continuation** is the next planned milestone. It absorbs the agent-prompt-hardening track (Builder return-schema discipline, Auditor cycle-summary emission, Builder pre-stamp pattern catches) deferred from M20, plus Phases E/F/G (slimming, productivity commands, parallel-builders foundation) split from M20 per audit recommendation M3. M21 prerequisites M20 close-out; `/clean-tasks m21` is now unblocked.

Roadmap + per-milestone task files live at [design_docs/roadmap.md](design_docs/roadmap.md) (builder-only, on design branch).
