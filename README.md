# ai-workflows

Composable AI workflow framework for a solo developer using a **Claude Max subscription** as the primary interactive tool. Orchestrates multi-step workflows — planning, execution, validation, human gates, resume — with durable state, multi-provider routing, and deterministic cost accounting.

**Architecture of record:** [design_docs/architecture.md](design_docs/architecture.md).
**Roadmap:** [design_docs/roadmap.md](design_docs/roadmap.md).
**Grounding analysis:** [design_docs/analysis/langgraph_mcp_pivot.md](design_docs/analysis/langgraph_mcp_pivot.md).

## Status

| Milestone | State |
| --- | --- |
| **M1 — Reconciliation & cleanup** | Complete (2026-04-19) |
| M2 — Graph-layer adapters + provider drivers | Planned |
| M3 — First workflow (`planner`, single tier) | Planned |
| M4 — MCP server (FastMCP) | Planned |
| M5–M9 | Planned (see roadmap) |

M1 established the four-layer package skeleton, sanitized the primitives layer for the post-pivot architecture, swapped the dependency set onto LangGraph + LiteLLM + FastMCP, and installed the import-linter contract. No workflows or provider calls run yet — that starts in [M2](design_docs/phases/milestone_2_graph/README.md).

## What runs today (post-M1)

- **`aiw` CLI** (Typer) with one working command — `aiw version` — plus `TODO(M3)` / `TODO(M4)` stubs for `run` / `resume` / `list-runs` / `cost-report`. See [ai_workflows/cli.py](ai_workflows/cli.py).
- **Primitives layer** — `Storage` (SQLite run registry + gate-response log), `TokenUsage` + `CostTracker`, `TierRegistry` + `LiteLLMRoute`, three-bucket retry taxonomy (`RetryableTransient` / `RetryableRateLimited` / `NonRetryable`), and `StructuredLogger`. See [ai_workflows/primitives/](ai_workflows/primitives/).
- **Reserved layer markers** — [ai_workflows/graph/](ai_workflows/graph/), [ai_workflows/workflows/](ai_workflows/workflows/), and [ai_workflows/mcp/](ai_workflows/mcp/) are docstring-only packages, awaiting content in M2 / M3 / M4 respectively.
- **Migrations** — yoyo-managed schema at [migrations/](migrations/) (`001_initial.sql`, `002_reconciliation.sql`).
- **Import-linter contract** — four-layer discipline enforced by three contracts in [pyproject.toml](pyproject.toml).

## Architecture at a glance

```text
surfaces        (ai_workflows.cli, ai_workflows.mcp)
    ↓
workflows       (ai_workflows.workflows.*)        — concrete LangGraph StateGraphs
    ↓
graph           (ai_workflows.graph.*)            — LangGraph adapters over primitives
    ↓
primitives      (ai_workflows.primitives.*)       — storage, cost, tiers, providers, retry, logging
```

Enforced by `import-linter`: lower layers may not import upward. See [design_docs/architecture.md §3](design_docs/architecture.md) for the full contract and [§9](design_docs/architecture.md) for the nine key design records (KDR-001 … KDR-009).

### Key design decisions

- **No Anthropic API** — Claude access is OAuth-only via the `claude` CLI subprocess (KDR-003).
- **LangGraph is the substrate** — no hand-rolled orchestrator, resume state machine, or gate timeout plumbing (KDR-001, KDR-009).
- **Validator after every LLM node** — prompting is a schema contract (KDR-004).
- **LiteLLM adapts Gemini + Qwen/Ollama** — Claude Code CLI stays bespoke because LiteLLM does not cover subprocess-OAuth (KDR-007).
- **FastMCP is the MCP server substrate** — decorators over pydantic-typed functions (KDR-008).

## Project layout

```text
ai_workflows/
  primitives/      # storage, cost, tiers, retry, logging  (M1)
  graph/           # reserved — LangGraph adapters         (M2)
  workflows/       # reserved — concrete StateGraphs       (M3+)
  mcp/             # reserved — FastMCP surface            (M4)
  cli.py           # Typer app — stubbed, M3 fills it in
migrations/        # yoyo-managed SQLite schema
tests/             # pytest, mirrors package structure
design_docs/       # architecture, roadmap, ADRs, milestones, issues
.claude/           # slash commands (/implement, /audit, /clean-implement)
```

See [CLAUDE.md](CLAUDE.md) for the Builder / Auditor conventions and the canonical file-location table.

## Getting started

Requires Python ≥ 3.12 and [uv](https://github.com/astral-sh/uv).

```bash
uv sync              # install runtime + dev dependencies
uv run aiw version   # prints 0.1.0
```

## Development

Three gates guard every change. Every task commit must leave them green:

```bash
uv run pytest         # unit + scaffolding tests
uv run lint-imports   # four-layer import contract
uv run ruff check     # style + basic correctness
```

Post-M1 snapshot: 148 passed, 3 contracts kept, ruff clean.

### Workflow conventions

Task work follows the Builder → Auditor loop defined in [CLAUDE.md](CLAUDE.md):

- [.claude/commands/implement.md](.claude/commands/implement.md) — Builder, single pass.
- [.claude/commands/audit.md](.claude/commands/audit.md) — Auditor, single pass.
- [.claude/commands/clean-implement.md](.claude/commands/clean-implement.md) — Builder → Auditor loop (up to 10 cycles).

Task specs live under [design_docs/phases/milestone_&lt;N&gt;_&lt;name&gt;/](design_docs/phases/). Audit findings are written to a per-task `issues/task_NN_issue.md` file after the first audit run.

## Next

M2 — [Graph-layer adapters + provider drivers](design_docs/phases/milestone_2_graph/README.md). Builds `TieredNode`, `ValidatorNode`, `HumanGate`, `CostTrackingCallback`, `RetryingEdge` on top of the primitives; ships the LiteLLM adapter and the Claude Code subprocess driver.
