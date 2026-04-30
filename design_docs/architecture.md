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
| `TierConfig` + `pricing.yaml` | Logical tier ("planner", "implementer", "local_coder") → concrete provider + model + limits. Tiers that route to LiteLLM-supported providers carry a LiteLLM model string; the `claude_code` tier carries a subprocess invocation spec. Authoritative tier definitions live in per-workflow Python registries (KDR-014); `docs/tiers.example.yaml` is a schema-reference example only, not loaded at dispatch time. |
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
- **`AuditCascadeNode`** (M12, KDR-011) — composes `TieredNode(primary) → ValidatorNode(shape) → TieredNode(auditor) → AuditVerdictNode` into a single sub-graph for **semantic** review on top of shape validation. The auditor tier sits one level above the author (Haiku/Gemini/Qwen → `auditor-sonnet`; Sonnet → `auditor-opus`; Opus is not audited). Scope: wraps only nodes whose output is consumed by a downstream node or the user (scratchpad/explore output is out of scope). On audit failure, the primary re-fires via `RetryingEdge` (`RetryableSemantic` bucket) with the auditor's `failure_reasons` + `suggested_approach` rendered into the next prompt; after bounded retries, the cascade routes to a strict `HumanGate` carrying the full transcript. Opt-in per workflow via `audit_cascade_enabled: bool = False`. Token usage is recorded per cascade step with a `role` tag (`author` / `auditor` / `verdict`) so `CostTracker.by_role` feeds the empirical tuning loop. See [ADR-0004](adr/0004_tiered_audit_cascade.md).

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
  - `run_audit_cascade(artefact_ref, tier_ceiling?) → AuditReport` *(lands at M12 T05 — standalone invocation of the tiered audit cascade over an existing artefact; invokes the auditor `TieredNode` directly, bypassing `AuditCascadeNode` per T05 Option A. See KDR-011 + [ADR-0004](adr/0004_tiered_audit_cascade.md).)*
  - *(Gate-review projection, M11; field honest per M19 T03)* — `RunWorkflowOutput.artifact` / `ResumeRunOutput.artifact` follow `FINAL_STATE_KEY` at `status="pending", awaiting="gate"` and at `status="gate_rejected"`. May be `None` if the workflow's `FINAL_STATE_KEY` channel is empty at gate time (e.g. `slice_refactor`'s `applied_artifact_count` is `None` at the review gate). Closes the M9 T04 live-smoke finding that an operator at a HumanGate had nothing to review. No new tool; surface shape unchanged. `RunWorkflowOutput.plan` / `ResumeRunOutput.plan` are deprecated aliases preserved through 0.2.x; removal target 1.0.
  - *(HTTP transport, M14)* — `aiw-mcp --transport http --port <N> --cors-origin <origin>` serves the same schema over streamable-HTTP for browser-origin consumers (Astro / React / Vue / any JS runtime without subprocess access). Loopback bind default; no auth at M14 (trigger-gated for a later milestone). Skill text unchanged — stdio remains the primary host-registration path. CORS middleware accessor recorded in [ADR-0005](adr/0005_fastmcp_http_middleware_accessor.md).
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

## Extension model — extensibility is a first-class capability

ai-workflows is a declarative orchestration layer over LangGraph. Authors of external workflows engage at four progressively-deeper tiers; each tier has a dedicated guide that teaches it with worked examples. Descending a tier never forces an author to reverse-engineer framework source. This model is the framework's core value proposition: the *majority* of authoring needs are satisfied at Tier 1 or Tier 2, with a clear upgrade path to Tier 3 when a built-in falls short, and a fully-documented escape to Tier 4 when the spec topology itself is insufficient.

| Tier | What the author does | Guide |
|---|---|---|
| 1 — Compose | Combine built-in step types into a `WorkflowSpec`. The declarative happy path. | [`docs/writing-a-workflow.md`](../docs/writing-a-workflow.md) |
| 2 — Parameterise | Configure built-in steps: retry policy, validator override, gate-rejection behaviour, tier choice. | [`docs/writing-a-workflow.md`](../docs/writing-a-workflow.md) (same doc — Tier 2 is parameter configuration of Tier 1's step types) |
| 3 — Author a custom step type | Subclass `Step` when no built-in covers the need. Custom step is user-owned Python (KDR-013) but composes with built-ins indistinguishably. | [`docs/writing-a-custom-step.md`](../docs/writing-a-custom-step.md) |
| 4 — Escape to LangGraph directly | Drop to the legacy `register(name, build_fn)` API and author the `StateGraph` directly. Reserved for genuinely non-standard topologies. | [`docs/writing-a-graph-primitive.md`](../docs/writing-a-graph-primitive.md) |

**Tier 1 — the happy path.** Most authoring needs are expressed as a `WorkflowSpec` whose `steps` list composes five built-in types: `LLMStep` (LLM call + automatic `ValidatorNode` pairing, satisfying KDR-004 by construction), `ValidateStep` (standalone schema check), `GateStep` (human-review pause via `HumanGate`), `TransformStep` (pure-Python state transformation), and `FanOutStep` (parallel sub-workflow fan-out via LangGraph `Send`). The framework synthesises the `StateGraph`, the state class (from `input_schema ⊕ output_schema`), `FINAL_STATE_KEY` resolution, `initial_state`, and retry wiring — the author writes data, not graph code.

**Tier 2 — parameter depth.** Every built-in step type exposes configuration knobs that let authors tune behaviour without leaving the declarative surface. `LLMStep` accepts either a `prompt_fn` (arbitrary callable → messages) for advanced prompt logic, or a `prompt_template` (simple `str.format` sugar) for the common case; a `RetryPolicy` for three-bucket retry semantics (KDR-006); a `response_format` for the pydantic schema the `ValidatorNode` validates against. `GateStep` accepts an `on_reject` callable for programmatic rejection handling. `FanOutStep` accepts `iter_field` / `merge_field` for state-channel routing. Tier 2 stays within the declarative surface; no subclassing required.

**Tier 3 — custom step types (KDR-013, user-owned code).** When no built-in covers a need — an HTTP fetch, a database lookup, a side-effecting operation — the author subclasses `Step` and implements `async execute(state: dict) -> dict`. The framework wires the custom step into the graph at registration time exactly as it wires a built-in; the custom step is indistinguishable from the author's side. For advanced topologies (fan-out emission, conditional edges, sub-graph composition from within a step), the author overrides `compile(state_class, step_id) -> CompiledStep` directly — see [`docs/writing-a-custom-step.md`](../docs/writing-a-custom-step.md) §Advanced.

**Out of scope for external authors.** Graph-layer primitives (`TieredNode`, `ValidatorNode`, `HumanGate`, `RetryingEdge`, the cost-tracking callback, the `SqliteSaver` checkpointer) are framework-internal. External extension at this depth dissolves the four-layer rule. Custom needs at this depth route through Tier 3 (wrap the behaviour in a step) or surface as feature requests; only framework contributors author new graph-layer primitives.

**Graduation path.** When a custom step pattern proves broadly useful — appearing in two or more workflows — the framework absorbs it as a built-in step in a future minor. When the underlying *wiring* (not just the step semantics) is reusable across step types, it graduates to the graph layer per the heuristic in `docs/writing-a-graph-primitive.md`. The graduation pattern is the framework's organic-growth mechanism; it keeps the built-in taxonomy earn-its-weight small while leaving a clear path for promoted patterns.

**Gate-pause projection note.** Gate-pause `artifact` projection follows `FINAL_STATE_KEY`. Workflows whose `FINAL_STATE_KEY` channel is empty at gate time will see `artifact=None` in gate-pause-resume responses. This is the honest reading: the artefact is not yet available when the gate fires. If a downstream consumer needs a configurable gate-pause projection (e.g. a `gate_review_payload_field` knob on `WorkflowSpec`), that fires the locked re-open trigger in `design_docs/nice_to_have.md §23` ("a second external workflow with conditional routing or sub-graph composition wants to use the spec API").

For the decision to introduce the declarative authoring surface, rejected alternatives, and the documentation propagation requirements, see [ADR-0008](adr/0008_declarative_authoring_surface.md).

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

**Ollama (M8, landed 2026-04-21).** The original bullet's "periodic health check" was **reframed at M8 T01**: the primary mid-run health signal is per-call failure classified through the three-bucket taxonomy (KDR-006), not a scheduled poller. `probe_ollama` (under `ai_workflows.primitives.llm.ollama_health`) is retained as a one-shot diagnostic tool — returns a `HealthResult` with one of five reasons (`ok` / `connection_refused` / `timeout` / `http_<status>` / `error:<type>`) and never raises — but no background task drives it. A process-local `CircuitBreaker` (`ai_workflows.primitives.circuit_breaker`) sits between `TieredNode` and every `LiteLLMRoute` whose `model.startswith("ollama/")`:

- Breaker defaults: `trip_threshold=3` (three consecutive `RetryableTransient`-bucketed failures flip CLOSED → OPEN), `cooldown_s=60.0` (OPEN → HALF_OPEN window during which one probe is allowed). A HALF_OPEN probe that succeeds flips the breaker CLOSED; a probe that fails flips it back to OPEN with a fresh cooldown. State transitions are serialized by an `asyncio.Lock`.
- Only `RetryableTransient` failures feed `record_failure` — auth / bad-request / budget failures are **not** Ollama-health signals.
- `TieredNode` raises `CircuitOpen(*, tier, last_reason)` pre-call when the breaker denies; the adapter is never invoked on that path. `wrap_with_error_handler` recognises `CircuitOpen` as a distinct exception type and routes it to `state["last_exception"]` **without** bumping retry counters (it is not a KDR-006 bucket).
- Gemini-backed LiteLLM tiers and `ClaudeCodeRoute` bypass the breaker entirely (the breaker dict only receives entries for tiers whose route is an Ollama `LiteLLMRoute` — see `_build_ollama_circuit_breakers` in `ai_workflows/workflows/_dispatch.py`).

**Fallback `HumanGate` (M8 T03/T04).** When `CircuitOpen` propagates, the workflow routes to a strict-review gate built by `build_ollama_fallback_gate` (under `ai_workflows.graph.ollama_fallback_gate`). The gate stamps three state-channel keys so the rest of the graph can reason about it:

- `_ollama_fallback_reason: str` — the `last_reason` from the breaker (`"circuit_open"` when the breaker short-circuited; otherwise the classifier's reason string).
- `_ollama_fallback_count: int` — incremented once per gate-pause per run (sticky via a dict-merge reducer for safe parallel fan-in).
- `ollama_fallback_decision: FallbackChoice | None` — the caller's response when the gate resumes. `FallbackChoice.{RETRY, FALLBACK, ABORT}` is a `StrEnum`, so CLI / MCP callers can pass the string value directly.

A workflow-scoped `OllamaFallback` dataclass (`PLANNER_OLLAMA_FALLBACK` in `planner.py`, `SLICE_REFACTOR_OLLAMA_FALLBACK` in `slice_refactor.py`) names the tripped tier (`tier_name`) and the replacement tier (`fallback_tier`). Both workflows point `fallback_tier` at `planner-synth` (the Claude Code OAuth subprocess tier) — the replacement tier is not hard-coded as `gemini_flash`; it is a per-workflow knob.

**Resume branches:**

- `RETRY` — clears `_retry_counts` and re-dispatches the tripped tier. The breaker is unchanged; if it is still OPEN, the next call re-raises `CircuitOpen` and the gate fires again. The caller is expected to have advanced the clock past `cooldown_s` (by waiting wall-clock time) before choosing RETRY — this is the "try again; Ollama might be back" branch.
- `FALLBACK` — stamps `_mid_run_tier_overrides[tier_name] = fallback_tier` on the state. Every subsequent `TieredNode` call for `tier_name` resolves to `fallback_tier` for the remainder of the run. The tripped Ollama tier is not re-attempted.
- `ABORT` — routes to a workflow-specific terminal node (`planner_hard_stop` / `slice_refactor_ollama_abort`) that writes a `hard_stop_metadata` artefact with `reason="ollama_fallback_abort"`. Dispatch's `_build_result_from_final` / `_build_resume_result_from_final` observe the terminal state and flip `runs.status='aborted'` with `finished_at` stamped (matching the M6 double-failure hard-stop shape, but distinct in artefact payload).

**Mid-run tier override precedence (locked at M8 T04).** `TieredNode._resolve_tier_name` walks three levels and returns the first match:

1. `state["_mid_run_tier_overrides"].get(tier_name)` — the post-FALLBACK channel.
2. `config["configurable"]["tier_overrides"].get(tier_name)` — the at-invoke-time channel wired from `aiw run --tier-override logical=replacement` and from MCP `RunWorkflowInput.tier_overrides`.
3. The registry default (`TierRegistry[tier_name]`).

State wins over configurable wins over registry. Future workflow authors plumbing a mid-run override should write to the state key; static at-invoke overrides stay on the configurable channel.

**Single-gate-per-run invariant for parallel fan-out.** `slice_refactor`'s `Send`-based slice fan-out means three independent `slice-worker` branches can each trip the shared breaker and each emit a `CircuitOpen` exception in the same super-step. Without protection, each branch would record-gate its own `ollama_fallback` row. The workflow prevents this by a `sticky-OR` `_ollama_fallback_fired: bool` state key (flipped `True` on the first `CircuitOpen` emission of the run) plus a `_route_before_aggregate` router that short-circuits to the single `ollama_fallback_stamp` → gate chain when the flag is already `True`. The gate pauses once per run; all three branches resume on the same `FallbackChoice` decision; on `FALLBACK`, the override dict is re-read by every re-fired branch via the `_mid_run_tier_overrides` Send-payload carry (M8 T04 addition-beyond-spec — needed because LangGraph's `Send` payload *is* the sub-graph's initial state view; keys absent from the payload don't propagate).

**Non-Ollama tiers.**

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
| KDR-004 | Validator-node-after-every-LLM-node is mandatory; prompting is a schema contract. Under the M19 spec API (ADR-0008), this graduates from convention-enforced-by-review to invariant-enforced-by-construction — `LLMStep` requires `response_format`, and the compiler pairs the validator automatically. The escape-hatch `register(name, build_fn)` API retains the convention-enforced-by-review status quo. | [analysis](analysis/langgraph_mcp_pivot.md) § E · [ADR-0008](adr/0008_declarative_authoring_surface.md) |
| KDR-005 | Project primitives layer is preserved and owned; LangGraph is the substrate, not the replacement. | [analysis](analysis/langgraph_mcp_pivot.md) § F |
| KDR-006 | Three-bucket retry taxonomy at the `TieredNode` boundary; graph-level routing by bucket. | §8.2 |
| KDR-007 | LiteLLM is the unified adapter for Gemini + Qwen/Ollama. Collapses two hand-rolled provider drivers, supplies per-call cost enrichment, and provides transient-retry underneath our taxonomy. Claude Code CLI stays bespoke (subprocess OAuth). | §4.1, §6 |
| KDR-008 | FastMCP is the MCP server implementation. Decorators over pydantic functions; tool schemas derive from signatures. | §4.4, §6 |
| KDR-009 | LangGraph's built-in `SqliteSaver` owns checkpoint persistence. No `StorageCheckpointer` adapter. `Storage` owns run registry and gate log only. | §4.1, §4.2 |
| KDR-010 | Pydantic models bound for LLM `response_format` ship bare-typed — no `Field(min_length/max_length/ge/le/...)` bounds — because Gemini's structured-output complexity budget rejects rich schemas. `extra="forbid"` is retained. Runtime bounds live at the caller-input surface (`*Input` models) and in prompt text; semantic enforcement stays at the paired `ValidatorNode` (KDR-004). MCP tool I/O models are unaffected. | [ADR-0002](adr/0002_bare_typed_response_format_schemas.md), §7 |
| KDR-011 | **Tiered audit cascade.** Generative LLM nodes whose output is read by a downstream node or user are paired with an **auditor** one tier above the author (Haiku/Gemini/Qwen → `auditor-sonnet`; Sonnet → `auditor-opus`; Opus is not audited). The cascade is **inline** (sub-graph per generative node, not post-hoc), **opt-in** per workflow (`audit_cascade_enabled: bool = False`), and **routed through `RetryingEdge`** on audit failure with the auditor's `failure_reasons` + `suggested_approach` re-rendered into the next prompt (not a raw retry). After bounded retries, failure escalates to a strict `HumanGate`. Auditor tiers route through the existing `ClaudeCodeSubprocess` over the OAuth CLI (`--model sonnet` / `--model opus`) — KDR-003 preserved. Standalone invocation over an existing artefact is exposed by the `run_audit_cascade` MCP tool (§4.4). Telemetry: each cascade step tags `TokenUsage` with `role` (`author` / `auditor` / `verdict`) so `CostTracker.by_role` feeds the empirical tuning loop. | [ADR-0004](adr/0004_tiered_audit_cascade.md), §4.2, §4.4 |
| KDR-013 | **External workflow module discovery.** Downstream consumers register their own workflow modules via dotted Python module paths through `AIW_EXTRA_WORKFLOW_MODULES` (comma-separated env var) or the `--workflow-module` CLI flag on `aiw` and `aiw-mcp` (repeatable, composes with the env var). Loading uses `importlib.import_module`; user modules are expected to call `ai_workflows.workflows.register(...)` at module top level. The existing `register()` collision check prevents shadowing of in-package workflows — `load_extra_workflow_modules()` eagerly pre-imports shipped workflows so that check fires reliably. `_dispatch._import_workflow_module` consults the registry first and routes to the registered builder's source module via `sys.modules[builder.__module__]`, so external workflows resolve even though their module path sits outside `ai_workflows.workflows.*`. User code is owned by the user — ai-workflows does not lint, test, or sandbox it. Entry-point discovery (PEP 621) and directory-scan loaders are deferred to separate milestones with their own triggers. Under the M19 spec API (ADR-0008), the user-owned-code boundary shifts: workflow specs are *data* (no Python privileges to worry about); custom step types remain *code* (still user-owned). The framework continues to surface — not police — custom step type implementations. | [ADR-0007](adr/0007_user_owned_code_contract.md), §4.2 · [ADR-0008](adr/0008_declarative_authoring_surface.md) |
| KDR-014 | **Framework owns quality policy; user owns invocation; operator override is env-var.** Quality knobs (audit cascade, validator strictness, retry budget defaults, tier defaults, fallback chains, audit-failure escalation thresholds) live in module-level constants in each workflow source file — never on `*Input` pydantic models, `WorkflowSpec` fields, CLI flags on `aiw run`, or MCP tool input schemas. The only operator-side override path is environment variables (global `AIW_<KNOB>=1` or per-workflow `AIW_<KNOB>_<WORKFLOW>=1`), read once at module-import time so the compiled graph reflects the decision. Public input schemas carry domain inputs (goal, context, max_steps, etc.), not policy toggles. Mirror principle to KDR-013: framework decides quality, user runs workflow, operator's lever is the env-var escape hatch. Telemetry-driven default flips become one-line code edits to module constants — no SEMVER break, no migration of downstream callers. ADR-0004 §Decision item 5's per-workflow opt-in intent is honoured via this pattern (the `audit_cascade_enabled` field semantic stays; the implementation surface moves from input-field to module-constant + env-var). | [ADR-0009](adr/0009_framework_owns_policy.md), §4.2 · mirror of KDR-013 |

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
