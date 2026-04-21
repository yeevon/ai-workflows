# ai-workflows — Architecture

**Status:** v0.1 (2026-04-19). Source of truth for the system's shape. Replaces the archived milestone-era design docs.
**Grounding decision:** [analysis/langgraph_mcp_pivot.md](analysis/langgraph_mcp_pivot.md).

---

## 1. Purpose

Orchestrate multi-step AI workflows — planning, execution, validation, human gates, resume — with durable state, multi-provider routing, and deterministic cost accounting, for a **solo developer** using a **Claude Max subscription** as the primary interactive tool.

### **In scope**

- Named workflows (e.g. `planner`, `slice_refactor`) executed as DAGs with checkpointed resume.
- Tiered provider routing (Gemini, Qwen via Ollama, Claude Code CLI subprocess).
- Human-in-the-loop gates with strict-review semantics.
- Cost ledger aggregating per-call and per-sub-model usage.
- Two consumption surfaces: a local CLI and a portable MCP server.

### **Out of scope**

- Anthropic API usage (explicit non-goal — Claude access is OAuth-only via the CLI).
- Hosted / multi-tenant deployment.
- Distributed execution across machines.
- Training / fine-tuning loops.
- Non-Python language support beyond what MCP clients give for free.

## 2. Principles

1. **Outside-in core, inside-out surface.** Orchestration lives in Python (LangGraph). UX can be reached from any MCP host (Claude Code, Cursor, Zed, OpenAI) without coupling the core to any one of them.
2. **Reuse mature infrastructure.** LangGraph for DAG/checkpoint/interrupt; MCP for portable tool exposure. No hand-rolled orchestrators, no hand-rolled resume state machines, no hand-rolled gate timeouts.
3. **Provider-agnostic runtime.** Nodes are plain Python functions. Tier resolution is the *only* place a provider is named.
4. **Deterministic accounting.** Every model call produces a `TokenUsage` record with `modelUsage` sub-model breakdown. Every run is checkpointed. Every interrupt is durable.
5. **Prompting is a contract.** MCP tool schemas, validator nodes after every LLM node, and an eval harness substitute for the determinism we cede to the graph engine and the hosts.
6. **Reversibility over cleverness.** LangGraph nodes are replaceable Python; MCP is an open spec. If either becomes a dead end, migration is bounded.

## 3. Layered structure

The existing `primitives` / `components` / `workflows` import-linter contract is preserved in spirit and extended:

```bash
surfaces        (ai_workflows.cli, ai_workflows.mcp)
    ↓                                       ↘
workflows       (ai_workflows.workflows.*)   → evals (ai_workflows.evals.*)
    ↓                                           ↓
graph           (ai_workflows.graph.*)         (replay reaches back into workflows
    ↓                                           to extract StateNodeSpec.runnable;
primitives      (ai_workflows.primitives.*)    graph stays evals-unaware)
```

- `primitives` imports nothing from `graph` / `workflows` / `surfaces` / `evals`.
- `graph` imports only `primitives`. **`graph → evals` is forbidden** (graph is evals-unaware; capture is wired in duck-typed through `config.configurable["eval_capture_callback"]`). Enforced by `tests/evals/test_layer_contract.py` AST grep alongside the import-linter contracts.
- `workflows` imports `graph` + `primitives`, and **may import `evals`** (`_dispatch` constructs `CaptureCallback` at opt-in time when `AIW_CAPTURE_EVALS` is set).
- `evals` imports `primitives` + `graph` + `workflows` — the replay runner needs `StateNodeSpec.runnable` + `StateGraph.state_schema` to construct single-node replay graphs. **`evals → surfaces` is forbidden** (the fourth import-linter contract).
- `surfaces` import `workflows` + `primitives` + `evals` (the `aiw eval` subcommands dispatch into `EvalRunner`).

Enforced by **four** `import-linter` contracts plus the `graph → evals` AST test. The `components/` layer from the archived design is collapsed into `graph/` — the old `Worker` / `Validator` / `Fanout` / `Pipeline` components become LangGraph node *patterns*, not stand-alone classes. The `evals` layer is described in §4.5.

## 4. Components

### 4.1 Primitives layer (project-specific, carried forward from M1)

| Module | Role |
| --- | --- |
| `Storage` | SQLite-backed run registry and gate-response log. **Checkpoint blobs are delegated to LangGraph's `SqliteSaver`** (KDR-009). |
| `TokenUsage` + `CostTracker` | Per-call ledger. LiteLLM supplies base per-call cost via its pricing table; `CostTracker` adds `modelUsage` sub-model aggregation (a Claude Code CLI call to `opus` may internally spawn `haiku` sub-calls — both recorded), per-run rollup, and budget enforcement. |
| `TierConfig` + `pricing.yaml` / `tiers.yaml` | Logical tier ("planner", "implementer", "local_coder") → concrete provider + model + limits. Tiers that route to LiteLLM-supported providers carry a LiteLLM model string; the `claude_code` tier carries a subprocess invocation spec. |
| Provider drivers | **LiteLLM-backed adapter** for Gemini + Qwen/Ollama (uniform OpenAI-compatible interface, built-in transient retry, built-in cost enrichment). **`ClaudeCodeSubprocess`** kept as a bespoke driver for the OAuth CLI (LiteLLM does not cover subprocess-auth providers). Both return `(text, TokenUsage)`. |
| `RetryPolicy` | Three-bucket error taxonomy: retryable-transient, retryable-semantic, non-retryable. LiteLLM's own transient retry runs beneath the LiteLLM adapter; `RetryPolicy` layers semantic classification + graph-level routing on top. |
| `StructuredLogger` | JSON log records with run/node/tier/provider/duration/tokens. (See [nice_to_have.md](nice_to_have.md) §1 Langfuse, §8 OTel — deferred observability layers that would consume these records.) |

These remain the project's proprietary value. Nothing in this layer depends on LangGraph.

### 4.2 Graph layer (new — LangGraph adapters)

Thin wrappers that translate between `primitives` semantics and LangGraph idioms:

- **`TieredNode`** — `(tier: str, prompt_fn, output_schema)` → LangGraph node. Resolves tier via `TierConfig`, calls provider, records `TokenUsage`, emits structured log.
- **`ValidatorNode`** — paired with any LLM node; parses output against a pydantic schema; raises `ModelRetry` with revision guidance on parse failure; passes through on success. (Parse-and-retry stays hand-rolled over LiteLLM `response_format` + LangGraph `ModelRetry`; see [nice_to_have.md](nice_to_have.md) §2 for the Instructor / pydantic-ai option if this accretes plumbing.)
- **`HumanGate`** — wraps `langgraph.interrupt()` with `strict_review=True|False` policy; persists gate prompt + response in `Storage`; no in-house timeout plumbing.
- **`CostTrackingCallback`** — LangGraph callback that writes `TokenUsage` rows to `CostTracker` as the graph executes.
- **Checkpointer** — LangGraph's built-in `SqliteSaver` is used directly. No custom adapter. `Storage` keeps the run registry and gate log; LangGraph owns checkpoint persistence. (KDR-009.)
- **`RetryingEdge`** — conditional edge helper that routes on the 3-bucket taxonomy (transient → self-loop with backoff; semantic → validator-revision loop; non-retryable → terminal failure or sibling-only continuation).

No named `Orchestrator`, `AgentLoop`, or `Pipeline` class. LangGraph's `StateGraph` + these adapters is the orchestrator.

### 4.3 Workflows layer (new shape)

Each workflow is a module exporting a built LangGraph `StateGraph`:

- **`planner`** — two-phase sub-graph: Qwen-tier explorer node → Opus-via-claude_code planner node → validator → plan artifact. Reusable as a sub-graph of larger workflows.
- **`slice_refactor`** — outermost DAG: `planner` sub-graph → per-slice worker nodes (parallel) → per-slice validator → aggregate → strict-review gate → apply.

Workflows are registered by name; the registry is how surfaces reach them.

### 4.4 Surfaces

- **`aiw` CLI** (`ai_workflows.cli`) — `aiw run <workflow> <inputs>`, `aiw resume <run_id>`, `aiw list-runs`. Primary path for CI, scripting, and non-interactive use. Implemented with **Typer** (landed in M1 Task 01; stubs live in `ai_workflows/cli.py`, full commands ship in M3). The originally-paired `aiw cost-report` command was dropped at M3 T06 reframe (2026-04-20); see [nice_to_have.md §9](nice_to_have.md) for the three adoption triggers that would promote it back in.
- **MCP server** (`ai_workflows.mcp`) — **built on FastMCP**: `@mcp.tool()` decorators over pydantic-typed functions; FastMCP generates the JSON-RPC schema, handles stdio/HTTP transport, and runs the server. Exposes:
  - `run_workflow(workflow_id, inputs) → {run_id, status, stream_handle?}` *(the `tier_overrides` argument lands at M5 T05 when the graph layer begins consuming it; shipping it earlier would be a dead field with no test coverage.)*
  - `resume_run(run_id, gate_response?) → {status, ...}`
  - `list_runs(filter?) → [RunSummary]` *(each `RunSummary` carries `total_cost_usd`; this is the only cost surface the MCP server exposes.)*
  - `cancel_run(run_id) → {status}`
  The originally-paired `get_cost_report(run_id) → CostReport` tool was dropped at M4 kickoff (2026-04-20) on the same reasoning as the CLI's `aiw cost-report` (M3 T06 reframe): the by-X breakdowns drive zero decisions under the current subscription-billing provider set, and the total-only scalar is already surfaced by `list_runs`. See [nice_to_have.md §9](nice_to_have.md) for the three adoption triggers that would promote a dedicated cost-report tool back in.
  Schema-first: pydantic models define every input and output. This is the public contract for every host. (KDR-008.)
- **Claude Code skill** (optional, late addition) — `.claude/skills/ai-workflows/SKILL.md` that shells out to `aiw` or calls the MCP server. Packaging-only; no logic.

### 4.5 Evals layer (new — prompt-regression harness, M7)

Peer of the `graph` layer: consumed by `workflows` (capture) and `surfaces` (replay), never by `graph` itself. Landed at M7; see [phases/milestone_7_evals/](phases/milestone_7_evals/README.md).

| Module | Role |
| --- | --- |
| `EvalCase` / `EvalSuite` / `EvalTolerance` (pydantic v2, bare-typed per KDR-010) | On-disk fixture schema. One JSON file per LLM-node call under `evals/<workflow>/<node>/<case_id>.json`. |
| `save_case` / `load_case` / `load_suite` / `fixture_path` | Filesystem helpers; default root `evals/` overridable by `AIW_EVALS_ROOT`. |
| `CaptureCallback` | Opt-in production instrumentation. `TieredNode` invokes it duck-typed after `CostTrackingCallback` when `config.configurable["eval_capture_callback"]` is set. `_dispatch.run_workflow` / `_dispatch.resume_run` construct it when `AIW_CAPTURE_EVALS=<dataset>` is set (or an explicit `capture_evals` override is threaded). Swallows its own exceptions (WARN log) so a broken capture never breaks a live run. |
| `EvalRunner` | Replay engine. Two modes: **deterministic** (default, CI-gated) swaps every tier to a `StubLLMAdapter` that returns captured output verbatim — exercises prompt-template rendering + validator schema parsing + graph wiring without any provider call. **Live** (opt-in via `AIW_EVAL_LIVE=1` + `AIW_E2E=1` double-gate) re-fires the captured inputs against real providers and grades against the pinned expected output with per-case `EvalTolerance`. |
| `_compare` | Tolerance dispatch: `strict_json` (full schema-parsed equality + unified diff on mismatch), `substring`, `regex`; per-field `field_overrides`. |
| `_capture_cli` (internal to the CLI surface) | `aiw eval capture` helper — reconstructs fixtures from `AsyncSqliteSaver.aget(cfg).channel_values` on a completed run. Zero provider calls. |

**Replay-runner sub-graph resolution.** `EvalRunner` walks each top-level runnable's `.builder` attribute (present on `CompiledStateGraph`) to find LLM nodes wired inside compiled sub-graphs (e.g. `slice_refactor` wraps `slice_worker` + `slice_worker_validator` in the `slice_branch` sub-graph). The replay graph is constructed against the enclosing graph's `state_schema`, so reverse-hydration of pydantic leaves uses the right TypedDict.

**CI surface.** The `eval-replay` GitHub Actions job (gated on paths `ai_workflows/workflows/**`, `ai_workflows/graph/**`, `evals/**`) runs `uv run aiw eval run planner` + `uv run aiw eval run slice_refactor` in deterministic mode on every PR touching those paths. Live mode stays manual / nightly.

## 5. Runtime data flow

A typical run:

1. A surface receives `(workflow_id, inputs)`.
2. Workflow registry returns a built `StateGraph`.
3. The graph is invoked with `StorageCheckpointer(run_id)` bound.
4. Each `TieredNode` invocation:
   - `TierConfig.resolve(tier)` → provider route (LiteLLM model string *or* `claude_code` subprocess spec).
   - Provider call returns `(text, TokenUsage)`. LiteLLM-path calls benefit from its built-in transient retry and cost enrichment before the tuple surfaces.
   - `CostTrackingCallback` writes `TokenUsage` rows (one per sub-model in `modelUsage`).
   - `StructuredLogger` emits a record.
5. If a node raises, `RetryingEdge` classifies by taxonomy and routes.
6. On `HumanGate.interrupt()`, the checkpointer persists. The surface returns a `{run_id, awaiting: "gate"}` handle.
7. On resume, surface passes the gate response; LangGraph rehydrates from checkpoint; execution continues.
8. Terminal nodes emit artifacts to Storage; the run is marked complete; cost report is queryable.

## 6. External dependencies

| Dependency | Role | Notes |
| --- | --- | --- |
| LangGraph (latest stable) | DAG, checkpointer (`SqliteSaver`), interrupt, parallel branches, time-travel | Core substrate. Built-in SQLite checkpointer used directly — no adapter. |
| FastMCP | MCP server ergonomics | Built on the official MCP SDK. Decorators over pydantic functions; replaces ~80% of raw SDK boilerplate. (KDR-008) |
| LiteLLM | Unified provider adapter for Gemini + Qwen/Ollama | One `completion()` call; built-in cost table, transient retry, model fallback. Requires `GEMINI_API_KEY` env var for Gemini; uses Ollama's HTTP endpoint for Qwen. (KDR-007) |
| Ollama (server) | Local Qwen runtime | LiteLLM targets it over HTTP. Health check + fallback policy in §8.4 still apply. |
| Claude Code CLI | Optional power-tier provider | OAuth via Max subscription. **No `ANTHROPIC_API_KEY`.** Driven as a subprocess; LiteLLM does not cover this path. |
| SQLite (stdlib) | Run registry + gate log (Storage) + LangGraph checkpoints (separate table/file) | Single file is fine at solo-dev scale; splittable later. |
| pydantic v2 | Schemas | MCP tool contracts + node I/O. |
| `import-linter` | Layer enforcement | CI gate. |

## 7. Boundaries and contracts

- **MCP tool schemas** are the system's public contract. Versioned in pydantic. Breaking changes require a new tool name.
- **TierConfig schema** is the internal routing contract. Provider and model identifiers are never hardcoded outside this file.
- **Checkpoint format** is LangGraph-owned. We do not serialize our own graph state.
- **Provider errors** are normalized to the 3-bucket taxonomy at the `TieredNode` boundary. Everything downstream sees a `RetryableTransient | RetryableSemantic | NonRetryable` exception type.
- **LLM `response_format` schemas are bare-typed.** Pydantic models passed as `output_schema=` to `tiered_node(...)` carry type annotations + `extra="forbid"` but **no** `Field(min_length/max_length/ge/le/...)` bounds. Runtime bounds live at the caller-input surface and in prompt text. See KDR-010 and [ADR-0002](adr/0002_bare_typed_response_format_schemas.md).
- **Secrets** are read from environment at the provider driver boundary. No key ever crosses into `graph` or `workflows`.

## 8. Cross-cutting concerns

### 8.1 Observability

- Every node emits a structured log record (`run_id`, `workflow`, `node`, `tier`, `provider`, `model`, `duration_ms`, `input_tokens`, `output_tokens`, `cost_usd`).
- `CostTracker` is the single source of truth for spend — queryable per run, per tier, per provider, per sub-model.
- External observability platforms (Langfuse, LangSmith) and tracing exporters (OpenTelemetry) are **deferred** — see [nice_to_have.md](nice_to_have.md) §1, §3, §8. Do not create tasks for these without a matching trigger from that doc.

### 8.2 Error handling

- `RetryableTransient` (network, 429, 5xx) → LiteLLM retries within a single call first; if exhausted, bubbles up and `RetryingEdge` self-loops at the node level with exponential backoff per `RetryPolicy`.
- `RetryableSemantic` (parse failure, schema mismatch) → `ValidatorNode` raises `ModelRetry`; LangGraph re-invokes the LLM node with revision guidance. Max 3 attempts then escalate to non-retryable.
- `NonRetryable` (auth, invalid model, logic error) → node fails; graph-level policy decides (abort run vs. continue independent siblings).
- **Double-failure hard-stop:** if two distinct nodes fail non-retryably in the same run, the graph aborts regardless of sibling independence.

### 8.3 Human gates

- `strict_review=True` → checkpoint and wait indefinitely. No timeout. Gate is cleared only by an explicit `resume_run(run_id, gate_response)`.
- `strict_review=False` → 30-minute default timeout; on expiry, a policy-configured default response is applied.
- Gate prompt and response are persisted in `Storage` for audit.

### 8.4 Provider health & fallback

- Ollama: periodic health check; on `ConnectionError`, pause the run and emit a gate asking the user to retry or fall back to a higher tier (e.g. Gemini Flash).
- Claude Code CLI: `claude --version` probe on startup; on absent binary, disable that tier with a clear error.
- Gemini: API key presence check; quota errors routed through `RetryableTransient`.

### 8.5 Cost control

- Per-run budget (pydantic field on `run_workflow` input; default `None`).
- `CostTracker` checks budget after each node; exceeding it raises `NonRetryable("budget exceeded")`.
- Tier overrides allow the caller to downshift a run to cheaper tiers.

### 8.6 Concurrency

- Per-provider semaphore (e.g. Gemini free-tier QPS). Configured in `TierConfig`.
- LangGraph-level parallelism is bounded by the semaphore at the provider call site, not by the graph shape.

### 8.7 Cancellation

The MCP `cancel_run` tool is **storage-level only** at M4: it flips `runs.status` from `pending` to `cancelled` and stamps `finished_at`; `resume_run` refuses any run whose status is `cancelled`. This covers the dominant cancel case for the planner — a run paused at a `HumanGate` the caller no longer wants to approve — without any LangGraph task-cancellation machinery, and therefore sidesteps every caveat that machinery carries.

**In-flight cancellation lands at M6** (`slice_refactor`), where parallel per-slice workers push wall-clock runtime from ~12s (planner) into minutes and mid-run abort becomes a real UX requirement. The M6 path (spec'd by that milestone's Builder) covers:

- MCP server holds a process-local `dict[run_id, asyncio.Task]` for active runs; `cancel_run` looks the task up and calls `task.cancel()` alongside the existing storage flip.
- Compiled graph runs with `durability="sync"` so the last-completed-step checkpoint is on disk before the `CancelledError` propagates.
- Subgraph cancellation is verified explicitly against [langgraph#5682](https://github.com/langchain-ai/langgraph/issues/5682).
- Any `ToolNode`-using worker in M6 guards against [langgraph#6726](https://github.com/langchain-ai/langgraph/issues/6726) (a mid-tool-call cancel that leaves an `AIMessage.tool_calls` unpaired with a `ToolMessage`, failing the next LLM call with `INVALID_CHAT_HISTORY`).
- SQLite single-writer race between the cancelled task's final write and an immediate re-run on the same `thread_id` is documented but accepted (retry on `database is locked` is fine).

Until M6 opens, nothing in this codebase needs the in-flight path.

## 9. Key design decisions

Referenced by short ID from future specs, tasks, and commits.

| ID | Decision | Source |
| --- | --- | --- |
| KDR-001 | LangGraph replaces hand-rolled DAG orchestrator, resume state machine, and human gate timeout. | [analysis](analysis/langgraph_mcp_pivot.md) § B |
| KDR-002 | MCP server is the portable inside-out surface; Claude Code skill is optional packaging, not the substrate. | [analysis](analysis/langgraph_mcp_pivot.md) § C |
| KDR-003 | No Anthropic API. Gemini + Qwen runtime; Claude Code CLI via OAuth for power-tier only. | memory: provider strategy |
| KDR-004 | Validator-node-after-every-LLM-node is mandatory; prompting is a schema contract. | [analysis](analysis/langgraph_mcp_pivot.md) § E |
| KDR-005 | Project primitives layer is preserved and owned; LangGraph is the substrate, not the replacement. | [analysis](analysis/langgraph_mcp_pivot.md) § F |
| KDR-006 | Three-bucket retry taxonomy at the `TieredNode` boundary; graph-level routing by bucket. | §8.2 |
| KDR-007 | LiteLLM is the unified adapter for Gemini + Qwen/Ollama. Collapses two hand-rolled provider drivers, supplies per-call cost enrichment, and provides transient-retry underneath our taxonomy. Claude Code CLI stays bespoke (subprocess OAuth). | §4.1, §6 |
| KDR-008 | FastMCP is the MCP server implementation. Decorators over pydantic functions; tool schemas derive from signatures. | §4.4, §6 |
| KDR-009 | LangGraph's built-in `SqliteSaver` owns checkpoint persistence. No `StorageCheckpointer` adapter. `Storage` owns run registry and gate log only. | §4.1, §4.2 |
| KDR-010 | Pydantic models bound for LLM `response_format` ship bare-typed — no `Field(min_length/max_length/ge/le/...)` bounds — because Gemini's structured-output complexity budget rejects rich schemas. `extra="forbid"` is retained. Runtime bounds live at the caller-input surface (`*Input` models) and in prompt text; semantic enforcement stays at the paired `ValidatorNode` (KDR-004). MCP tool I/O models are unaffected. | [ADR-0002](adr/0002_bare_typed_response_format_schemas.md), §7 |

## 10. Evolution

- **Reversibility targets:** LangGraph and MCP are both replaceable. LangGraph nodes are Python functions; swapping to another engine (e.g. Temporal, Prefect) re-homes them. MCP's open spec means the server can be re-hosted or wrapped.
- **Deprecation:** the archived `Pipeline` component is not ported; linear workflows become single-chain LangGraph StateGraphs. The archived `AgentLoop` is not ported as a class; its validator-every-step invariant becomes a workflow-construction rule.
- **Deferred simplifications:** [nice_to_have.md](nice_to_have.md) is the authoritative parking lot for candidates (Langfuse, Instructor/pydantic-ai, LangSmith, Typer, Docker Compose, mkdocs, DeepAgents templates, standalone OTel) that were evaluated and intentionally left out of this architecture for the solo-dev phase. **Do not create milestones or tasks for any listed item unless its trigger condition has fired.** Promotion to adopted status requires a new KDR here plus an ADR under `design_docs/adr/`.
- **Roadmap shape (to be sequenced in a follow-up):**
  1. Graph-layer adapters over existing primitives.
  2. Planner workflow end-to-end on a single tier.
  3. MCP server with the five core tools.
  4. Multi-tier planner (Qwen explore → Opus plan).
  5. `slice_refactor` DAG.
  6. Claude Code skill packaging (optional).
  7. Eval harness (prompt regression guard).
  8. Ollama infrastructure (health check, circuit breaker, fallback gate).

## 11. What this document is not

- A milestone plan — sequencing and ACs live in milestone/task docs (to be drafted).
- A commitment to specific library versions — those live in `pyproject.toml`.
- A user manual — surfaces own their own docs.

---

**Amendment rule:** changes to this document require a matching ADR under `design_docs/adr/` or a replacement analysis under `design_docs/analysis/`, cited by KDR ID.
