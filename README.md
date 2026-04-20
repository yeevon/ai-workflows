# ai-workflows

Composable AI workflow framework for a solo developer using a **Claude** as the primary interactive tool. Orchestrates multi-step workflows — planning, execution, validation, human gates, resume — with durable state, multi-provider routing, and deterministic cost accounting.

**Architecture of record:** [design_docs/architecture.md](design_docs/architecture.md).
**Roadmap:** [design_docs/roadmap.md](design_docs/roadmap.md).
**Grounding analysis:** [design_docs/analysis/langgraph_mcp_pivot.md](design_docs/analysis/langgraph_mcp_pivot.md).

## Status

| Milestone | State |
| --- | --- |
| **M1 — Reconciliation & cleanup** | Complete (2026-04-19) |
| **M2 — Graph-layer adapters + provider drivers** | Complete (2026-04-19) |
| **M3 — First workflow (`planner`, single tier)** | Complete (2026-04-20) |
| M4 — MCP server (FastMCP) | Planned |
| M5–M9 | Planned (see roadmap) |

M1 established the four-layer package skeleton, sanitized the primitives layer for the post-pivot architecture, swapped the dependency set onto LangGraph + LiteLLM + FastMCP, and installed the import-linter contract. M2 filled the `graph/` layer with the LangGraph adapters every future workflow composes over — `TieredNode`, `ValidatorNode`, `HumanGate`, `CostTrackingCallback`, `RetryingEdge` — plus the two provider drivers (LiteLLM for Gemini + Qwen/Ollama, subprocess-OAuth for Claude Code) and the `SqliteSaver`-backed checkpointer. M3 wired the first real workflow: a single-tier `planner` `StateGraph` running end-to-end through the M2 adapters, the `aiw` CLI revived (`run` / `resume` / `list-runs`), and an `AIW_E2E=1`-gated smoke test that drives a real Gemini Flash call. Next up is [M4 — MCP server](design_docs/phases/milestone_4_mcp/README.md).

## What runs today (post-M3)

- **`aiw` CLI** (Typer) with three working commands — `aiw run planner --goal '<goal>' [--run-id …] [--budget-usd …]`, `aiw resume <run_id> [--approve / --reject]`, `aiw list-runs [--workflow / --status / --limit]`. `aiw version` still works; `cost-report` was deferred at M3 T06 reframe (see [architecture.md §4.4](design_docs/architecture.md) and [nice_to_have.md §9](design_docs/nice_to_have.md)). See [ai_workflows/cli.py](ai_workflows/cli.py).
- **Planner workflow** — [`ai_workflows.workflows.planner`](ai_workflows/workflows/planner.py) exports `build_planner_graph()` wired as explorer → `TieredNode` (Gemini Flash via LiteLLM) → `ValidatorNode` → `HumanGate` → artifact, compiled against LangGraph's `AsyncSqliteSaver`. Schema-first: `PlannerInput` / `PlannerPlan` pydantic models are the single contract the CLI, validator, and prompt all enforce. Response schemas ship bare-typed per [KDR-010 / ADR-0002](design_docs/adr/0002_bare_typed_response_format_schemas.md).
- **Workflow registry** — [`ai_workflows.workflows.register / get_workflow`](ai_workflows/workflows/__init__.py) — lazy `(name) → builder()` lookup that the CLI and the future MCP surface both resolve against a stable string key.
- **Primitives layer** — `Storage` (SQLite run registry + gate-response log + `runs.total_cost_usd`), `TokenUsage` + `CostTracker`, `TierRegistry` + `LiteLLMRoute`, three-bucket retry taxonomy (`RetryableTransient` / `RetryableRateLimited` / `NonRetryable`), `StructuredLogger`, and the two LLM drivers — `LiteLLMAdapter` (Gemini + Qwen/Ollama) and `ClaudeCodeSubprocess` (`claude -p --output-format json`, OAuth-only). See [ai_workflows/primitives/](ai_workflows/primitives/).
- **Graph layer** — LangGraph adapters over primitives: [`TieredNode`](ai_workflows/graph/tiered_node.py), [`ValidatorNode`](ai_workflows/graph/validator_node.py), [`HumanGate`](ai_workflows/graph/human_gate.py), [`CostTrackingCallback`](ai_workflows/graph/cost_callback.py), [`RetryingEdge`](ai_workflows/graph/retrying_edge.py), [`wrap_with_error_handler`](ai_workflows/graph/error_handler.py), and [`build_checkpointer` / `build_async_checkpointer`](ai_workflows/graph/checkpointer.py) (LangGraph `SqliteSaver` / `AsyncSqliteSaver`, default `~/.ai-workflows/checkpoints.sqlite`, `AIW_CHECKPOINT_DB` override).
- **End-to-end smoke test** — [`tests/e2e/test_planner_smoke.py`](tests/e2e/test_planner_smoke.py) drives the full `aiw run planner` → `aiw resume` path against real Gemini Flash and asserts every M3 invariant the hermetic tests cannot (real provider call completes, budget cap honoured end-to-end, approved plan round-trips from Storage, no Anthropic API leak per KDR-003). Gated by `AIW_E2E=1`; default `uv run pytest` stays hermetic.
- **Reserved layer marker** — [ai_workflows/mcp/](ai_workflows/mcp/) is a docstring-only package, awaiting content in M4.
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

Enforced by `import-linter`: lower layers may not import upward. See [design_docs/architecture.md §3](design_docs/architecture.md) for the full contract and [§9](design_docs/architecture.md) for the ten key design records (KDR-001 … KDR-010).

### Key design decisions

- **No Anthropic API** — Claude access is OAuth-only via the `claude` CLI subprocess (KDR-003).
- **LangGraph is the substrate** — no hand-rolled orchestrator, resume state machine, or gate timeout plumbing (KDR-001, KDR-009).
- **Validator after every LLM node** — prompting is a schema contract (KDR-004).
- **LiteLLM adapts Gemini + Qwen/Ollama** — Claude Code CLI stays bespoke because LiteLLM does not cover subprocess-OAuth (KDR-007).
- **FastMCP is the MCP server substrate** — decorators over pydantic-typed functions (KDR-008).
- **LLM `response_format` schemas ship bare-typed** — pydantic models passed as `output_schema=` to `tiered_node(...)` carry type annotations + `extra="forbid"` but no `Field(min/max/ge/le)` bounds; runtime bounds live at the caller-input surface and in prompt text (KDR-010, [ADR-0002](design_docs/adr/0002_bare_typed_response_format_schemas.md)).

## Project layout

```text
ai_workflows/
  primitives/      # storage, cost, tiers, retry, logging, LLM drivers  (M1, M2)
  graph/           # LangGraph adapters over primitives                 (M2)
  workflows/       # concrete StateGraphs — planner lives here          (M3)
  mcp/             # reserved — FastMCP surface                         (M4)
  cli.py           # Typer app — run / resume / list-runs / version     (M3)
migrations/        # yoyo-managed SQLite schema
tests/             # pytest, mirrors package structure
  e2e/             # AIW_E2E=1-gated smoke tests against real providers
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

Then drive a planner run end-to-end (requires `GEMINI_API_KEY`):

```bash
export GEMINI_API_KEY=...
uv run aiw run planner --goal 'Write a release checklist' --run-id demo
uv run aiw resume demo --approve
uv run aiw list-runs
```

## Development

Three gates guard every change. Every task commit must leave them green:

```bash
uv run pytest         # unit + scaffolding tests (hermetic; skips e2e unless AIW_E2E=1)
uv run lint-imports   # four-layer import contract
uv run ruff check     # style + basic correctness
```

Post-M3 snapshot: 290 passed, 1 skipped (e2e, gated by `AIW_E2E=1`), 3 contracts kept, ruff clean.

### Workflow conventions

Task work follows the Builder → Auditor loop defined in [CLAUDE.md](CLAUDE.md):

- [.claude/commands/implement.md](.claude/commands/implement.md) — Builder, single pass.
- [.claude/commands/audit.md](.claude/commands/audit.md) — Auditor, single pass.
- [.claude/commands/clean-implement.md](.claude/commands/clean-implement.md) — Builder → Auditor loop (up to 10 cycles).

Task specs live under [design_docs/phases/milestone_&lt;N&gt;_&lt;name&gt;/](design_docs/phases/). Audit findings are written to a per-task `issues/task_NN_issue.md` file after the first audit run.

## Next

M4 — [MCP server (FastMCP)](design_docs/phases/milestone_4_mcp/README.md). Exposes the `planner` workflow (and future ones) as the portable inside-out surface promised by KDR-002: five FastMCP tools (`run_workflow` / `resume_run` / `list_runs` / `get_cost_report` / `cancel_run`), schema-first pydantic contracts auto-derived by FastMCP, stdio transport first. The `get_cost_report` tool carries forward the M3 T06 reframe — ship as total-only scalar reading `runs.total_cost_usd`, or fold into `list_runs` (see the M4 README's *Carry-over from prior milestones* section).
