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
| **M4 — MCP server (FastMCP)** | Complete (2026-04-20) |
| **M5 — Multi-tier `planner`** | Complete (2026-04-20) |
| **M6 — `slice_refactor` DAG** | Complete (2026-04-20) |
| **M7 — Eval harness** | Complete (2026-04-21) |
| M8–M9 | Planned (see roadmap) |

M1 established the four-layer package skeleton, sanitized the primitives layer for the post-pivot architecture, swapped the dependency set onto LangGraph + LiteLLM + FastMCP, and installed the import-linter contract. M2 filled the `graph/` layer with the LangGraph adapters every future workflow composes over — `TieredNode`, `ValidatorNode`, `HumanGate`, `CostTrackingCallback`, `RetryingEdge` — plus the two provider drivers (LiteLLM for Gemini + Qwen/Ollama, subprocess-OAuth for Claude Code) and the `SqliteSaver`-backed checkpointer. M3 wired the first real workflow: a single-tier `planner` `StateGraph` running end-to-end through the M2 adapters, the `aiw` CLI revived (`run` / `resume` / `list-runs`), and an `AIW_E2E=1`-gated smoke test that drives a real Gemini Flash call. M4 shipped the portable inside-out MCP surface promised by KDR-002: four FastMCP tools (`run_workflow`, `resume_run`, `list_runs`, `cancel_run`) with schema-first pydantic contracts, a shared dispatch helper so CLI + MCP route through one path, stdio-transport entry point (`aiw-mcp`), `claude mcp add` registration docs, and an always-run hermetic in-process smoke covering every tool. M5 upgraded the planner from single-tier to a two-phase sub-graph (Qwen local_coder explore → Claude Code Opus plan) — the first real exercise of the `ClaudeCodeSubprocess` driver and the `LiteLLMAdapter`'s Ollama path inside one workflow — and shipped the tier-override surface (CLI `--tier-override logical=replacement` + MCP `RunWorkflowInput.tier_overrides`) that lets callers repoint either phase at runtime without a code change. M6 landed the architecture's canonical DAG: planner sub-graph → `Send(...)`-based parallel slice fan-out (bounded by a per-tier, per-run `asyncio.Semaphore` built from `TierConfig.max_concurrency`) → per-slice validator (KDR-004 under fan-out) → aggregator → **strict-review** `HumanGate` (no-timeout, first use in the codebase) → `apply` node (one `artifacts` row per succeeded slice, idempotent on re-invocation). Two contracts from [architecture.md §8](design_docs/architecture.md) became live at M6: the **double-failure hard-stop** (`len(slice_failures) >= 2` routes to a `_hard_stop` terminal distinct from `gate_rejected` / `cancelled`) and in-flight **`cancel_run`** (process-local `_ACTIVE_RUNS` task registry + `task.cancel()` wired in the MCP surface, `durability="sync"` threaded through `_dispatch` so the last-completed-step checkpoint is on disk before `CancelledError` propagates — resolves the M4-T05 carry-over). M7 landed the KDR-004 prompt-regression harness: a new `ai_workflows.evals` package (peer of `graph`) with pydantic v2 bare-typed `EvalCase` / `EvalSuite` / `EvalTolerance` schemas and on-disk JSON fixtures under `evals/<workflow>/<node>/<case_id>.json`; an opt-in `CaptureCallback` (env-gated by `AIW_CAPTURE_EVALS=<dataset>`) that turns live runs into replay fixtures through a duck-typed `TieredNode` hook, leaving the default path byte-identical; an `EvalRunner` with deterministic mode (hermetic `StubLLMAdapter` swap — the CI-gated path) and double-env-gated live mode (`AIW_EVAL_LIVE=1 + AIW_E2E=1` re-fires captured inputs against real providers for model-drift diagnostics); the `aiw eval capture` + `aiw eval run [--live]` CLI surface that reconstructs fixtures from `AsyncSqliteSaver` channel values with zero provider calls; an `eval-replay` CI job gated by `dorny/paths-filter` on `workflows/**`, `graph/**`, `evals/**`; and three seed fixtures spanning both shipped workflows. Subgraph node resolution was retrofitted to T03's runner so `slice_refactor.slice_worker` (which lives inside the `slice_branch` compiled sub-graph) resolves alongside flat nodes. Next up is [M8 — Ollama infrastructure](design_docs/phases/milestone_8_ollama/README.md).

## What runs today (post-M7)

- **`aiw-mcp` MCP server** (FastMCP, stdio transport) — four tools exposed per [architecture.md §4.4](design_docs/architecture.md): `run_workflow`, `resume_run`, `list_runs`, `cancel_run`. Schema-first pydantic I/O (auto-derived by FastMCP per KDR-008). CLI and MCP route through one shared dispatch helper [`ai_workflows/workflows/_dispatch.py`](ai_workflows/workflows/_dispatch.py) so both surfaces stay in lockstep. Register with Claude Code via `claude mcp add ai-workflows --scope user -- uv run aiw-mcp` — full walkthrough in [design_docs/phases/milestone_4_mcp/mcp_setup.md](design_docs/phases/milestone_4_mcp/mcp_setup.md). `cancel_run` performs both the Storage-level status flip and (per M6 T02) looks the active run up in a process-local `_ACTIVE_RUNS: dict[run_id, asyncio.Task]` registry and calls `task.cancel()` — satisfies [architecture.md §8.7](design_docs/architecture.md) for the in-flight-abort case that the parallel slice_refactor fan-out made a UX requirement.
- **`aiw` CLI** (Typer) with five working commands — `aiw run planner --goal '<goal>' [--run-id …] [--budget-usd …] [--tier-override logical=replacement …]`, `aiw resume <run_id> [--approve / --reject]`, `aiw list-runs [--workflow / --status / --limit]`, `aiw eval capture --run-id <id> --dataset <name>`, `aiw eval run <workflow> [--live] [--dataset …] [--fail-fast]`. `--tier-override` is repeatable (M5 T04) and validates both sides against the workflow's tier registry; unknown names exit with code 2. `aiw eval` is the M7 harness surface — `capture` reconstructs fixtures from a completed run's checkpointed LangGraph state (zero provider calls); `run` dispatches `EvalRunner` with deterministic mode by default, `--live` double-gated on `AIW_EVAL_LIVE=1` + `AIW_E2E=1`. `aiw version` still works; `cost-report` was deferred at M3 T06 reframe (see [architecture.md §4.4](design_docs/architecture.md) and [nice_to_have.md §9](design_docs/nice_to_have.md)). See [ai_workflows/cli.py](ai_workflows/cli.py).
- **Multi-tier planner workflow** — [`ai_workflows.workflows.planner`](ai_workflows/workflows/planner.py) exports `build_planner()` wired as `explorer` (`TieredNode`, `planner-explorer` → `ollama/qwen2.5-coder:32b` via LiteLLM's Ollama driver) → `explorer_validator` (`ExplorerReport` schema) → `planner` (`TieredNode`, `planner-synth` → Claude Code Opus via the OAuth subprocess driver) → `planner_validator` (`PlannerPlan` schema) → `HumanGate` → artifact, compiled against LangGraph's `AsyncSqliteSaver`. Each LLM node pairs with a `ValidatorNode` (KDR-004) and a `RetryingEdge` self-loop on the three-bucket taxonomy (KDR-006). MCP `run_workflow` accepts `tier_overrides: dict[str, str]` to repoint either phase at invoke time (M5 T05). Response schemas ship bare-typed per [KDR-010 / ADR-0002](design_docs/adr/0002_bare_typed_response_format_schemas.md).
- **`slice_refactor` DAG workflow** (M6) — [`ai_workflows.workflows.slice_refactor`](ai_workflows/workflows/slice_refactor.py) exports `build_slice_refactor()` wired as `planner_subgraph` (composes `build_planner().compile()` as a sub-graph) → `slice_list_normalize` (converts `PlannerPlan.steps` into the fan-out input list) → `Send(...)`-based parallel `slice_branch` (one `TieredNode` per planner step on the `slice-worker` tier → `ollama/qwen2.5-coder:32b` by default) → per-branch `_slice_worker_validator` (KDR-004 under fan-out; escalates `RetryableSemantic → NonRetryable` on `max_attempts − 1`) → `aggregate` (folds `slice_results` + `slice_failures` into a `SliceAggregate` payload) → **strict-review** `HumanGate` (`strict_review=True`, no-timeout — first use in the codebase) → `apply` (one `artifacts` row per succeeded `SliceResult`, keyed `slice_result:<slice_id>`, idempotent via `ON CONFLICT DO UPDATE`). Parallel branches are bounded by a per-tier, per-run `asyncio.Semaphore` built from `TierConfig.max_concurrency` and threaded via `config["configurable"]["semaphores"]` ([architecture.md §8.6](design_docs/architecture.md)). The **double-failure hard-stop** ([architecture.md §8.2](design_docs/architecture.md)) routes to a `_hard_stop` terminal (`runs.status = "aborted"`, distinct from `gate_rejected` and `cancelled`) when `len(slice_failures) >= 2`, bypassing aggregator + gate + apply. Compiled with `durability="sync"` so `cancel_run`'s `task.cancel()` leaves the last-completed-step checkpoint on disk. No subprocess / `git apply` invocation at M6 per the milestone's non-goals — `apply` writes to Storage only.
- **Workflow registry** — [`ai_workflows.workflows.register / get_workflow`](ai_workflows/workflows/__init__.py) — lazy `(name) → builder()` lookup that the CLI and the future MCP surface both resolve against a stable string key.
- **Primitives layer** — `Storage` (SQLite run registry + gate-response log + `runs.total_cost_usd`), `TokenUsage` + `CostTracker`, `TierRegistry` + `LiteLLMRoute`, three-bucket retry taxonomy (`RetryableTransient` / `RetryableRateLimited` / `NonRetryable`), `StructuredLogger`, and the two LLM drivers — `LiteLLMAdapter` (Gemini + Qwen/Ollama) and `ClaudeCodeSubprocess` (`claude -p --output-format json`, OAuth-only). See [ai_workflows/primitives/](ai_workflows/primitives/).
- **Graph layer** — LangGraph adapters over primitives: [`TieredNode`](ai_workflows/graph/tiered_node.py), [`ValidatorNode`](ai_workflows/graph/validator_node.py), [`HumanGate`](ai_workflows/graph/human_gate.py), [`CostTrackingCallback`](ai_workflows/graph/cost_callback.py), [`RetryingEdge`](ai_workflows/graph/retrying_edge.py), [`wrap_with_error_handler`](ai_workflows/graph/error_handler.py), and [`build_checkpointer` / `build_async_checkpointer`](ai_workflows/graph/checkpointer.py) (LangGraph `SqliteSaver` / `AsyncSqliteSaver`, default `~/.ai-workflows/checkpoints.sqlite`, `AIW_CHECKPOINT_DB` override). `TieredNode` also fires an optional duck-typed `eval_capture_callback` (M7 T02) after the cost callback when wired — the graph stays evals-unaware.
- **Evals layer** (M7, peer of `graph`) — [`ai_workflows/evals/`](ai_workflows/evals/): `EvalCase` / `EvalSuite` / `EvalTolerance` bare-typed pydantic v2 models, `save_case` / `load_case` / `load_suite` filesystem helpers, [`CaptureCallback`](ai_workflows/evals/capture_callback.py) (graph-layer sibling to `CostTrackingCallback`, opt-in via `AIW_CAPTURE_EVALS=<dataset>`), [`EvalRunner`](ai_workflows/evals/runner.py) with deterministic (`StubLLMAdapter` swap) + double-gated live mode, `_compare` tolerance dispatch (`strict_json` + `substring` + `regex` + `field_overrides`), and `_resolve_node_scope` that walks `CompiledStateGraph.builder` to find LLM nodes wired inside compiled sub-graphs. See [design_docs/architecture.md §4.5](design_docs/architecture.md).
- **Eval fixture tree** ([`evals/`](evals/)) — three seed fixtures committed at M7 T05: [`evals/planner/explorer/happy-path-01.json`](evals/planner/explorer/happy-path-01.json), [`evals/planner/planner/happy-path-01.json`](evals/planner/planner/happy-path-01.json), [`evals/slice_refactor/slice_worker/happy-path-01.json`](evals/slice_refactor/slice_worker/happy-path-01.json). Deterministic replay of this tree runs on every PR that touches `ai_workflows/workflows/**`, `ai_workflows/graph/**`, or `evals/**` via the `eval-replay` CI job in [`.github/workflows/ci.yml`](.github/workflows/ci.yml).
- **End-to-end smoke tests** (gated by `AIW_E2E=1`; default `uv run pytest` stays hermetic):
  - [`tests/e2e/test_planner_smoke.py`](tests/e2e/test_planner_smoke.py) drives the full `aiw run planner` → `aiw resume` path against the live two-phase multi-tier sub-graph (Qwen explorer on Ollama + Claude Code Opus synth) and asserts every M5 invariant the hermetic tests cannot — both provider calls fire, captured `TokenUsage` rows show Qwen-cost=0 + Claude Code sub-model rollup, approved plan round-trips from Storage, no Anthropic API leak per KDR-003 (narrow regex catches only `import anthropic` / `ANTHROPIC_API_KEY` — not docstring prose).
  - [`tests/e2e/test_tier_override_smoke.py`](tests/e2e/test_tier_override_smoke.py) drives `aiw run planner --tier-override planner-synth=planner-explorer` against a pinned registry (explorer → Gemini Flash, synth → Claude Code Opus) and proves the override actually routes — a raise-on-init `ClaudeCodeSubprocess` stub guarantees zero Claude Code dispatch, Gemini Flash handles both phases, run completes.
  - [`tests/e2e/test_slice_refactor_smoke.py`](tests/e2e/test_slice_refactor_smoke.py) (new in M6 T08) drives `_dispatch.run_workflow("slice_refactor", …)` → `resume_run` → `resume_run` through the live multi-tier fan-out (planner sub-graph on Qwen + Claude Code Opus; three `slice-worker` branches on Qwen) and asserts the two-gate round-trip reaches `status="completed"` with at least one `slice_result:<id>` artefact row. The hermetic sibling [`tests/workflows/test_slice_refactor_e2e.py`](tests/workflows/test_slice_refactor_e2e.py) covers the same shape always, plus a narrow KDR-003 regression grep over `ai_workflows/**/*.py`.
- **MCP surface** — [ai_workflows/mcp/](ai_workflows/mcp/): `build_server()` factory, pydantic I/O models in `schemas.py`, stdio entry point in `__main__.py`, the four tool bodies in `server.py`.
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

Enforced by `import-linter`: lower layers may not import upward. Four contracts since M7 (the new `evals cannot import surfaces` sits alongside the three layer contracts). `ai_workflows.evals` is a peer of `graph` — consumed by `workflows` (capture) and `surfaces` (replay); `graph` stays evals-unaware. See [design_docs/architecture.md §3 / §4.5](design_docs/architecture.md) for the full contract and [§9](design_docs/architecture.md) for the ten key design records (KDR-001 … KDR-010).

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
  workflows/       # concrete StateGraphs — planner + slice_refactor    (M3, M6)
  evals/           # EvalCase/Suite, CaptureCallback, EvalRunner        (M7)
  mcp/             # FastMCP surface — four tools over stdio            (M4)
  cli.py           # Typer app — run / resume / list-runs / eval        (M3, M7)
evals/             # committed fixture tree for deterministic replay    (M7)
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

## MCP server

Register the `aiw-mcp` stdio server with Claude Code (or any MCP host) to drive the same workflows inside-out. Setup walkthrough: [design_docs/phases/milestone_4_mcp/mcp_setup.md](design_docs/phases/milestone_4_mcp/mcp_setup.md).

## Development

Three gates guard every change. Every task commit must leave them green:

```bash
uv run pytest         # unit + scaffolding tests (hermetic; skips e2e unless AIW_E2E=1)
uv run lint-imports   # four-layer import contract
uv run ruff check     # style + basic correctness
```

Post-M7 snapshot: 538 passed, 4 skipped (the three e2e smokes — `test_planner_smoke.py`, `test_tier_override_smoke.py`, `test_slice_refactor_smoke.py` — gated by `AIW_E2E=1`, plus the live-mode eval replay suite gated by `AIW_EVAL_LIVE=1 + AIW_E2E=1`), 4 contracts kept, ruff clean.

### Workflow conventions

Task work follows the Builder → Auditor loop defined in [CLAUDE.md](CLAUDE.md):

- [.claude/commands/implement.md](.claude/commands/implement.md) — Builder, single pass.
- [.claude/commands/audit.md](.claude/commands/audit.md) — Auditor, single pass.
- [.claude/commands/clean-implement.md](.claude/commands/clean-implement.md) — Builder → Auditor loop (up to 10 cycles).

Task specs live under [design_docs/phases/milestone_&lt;N&gt;_&lt;name&gt;/](design_docs/phases/). Audit findings are written to a per-task `issues/task_NN_issue.md` file after the first audit run.

## Next

M8 — [Ollama infrastructure](design_docs/phases/milestone_8_ollama/README.md). Health check, circuit breaker, and fallback-to-Gemini gate for the Qwen/Ollama tier that M5/M6 made load-bearing. Needed before the local-coder tier can be trusted in unattended runs.
