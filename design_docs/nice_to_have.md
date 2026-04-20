# ai-workflows — Nice-to-have / Future Simplification Candidates

**Status:** Parking lot (2026-04-19). None of these are adopted. Revisit when the triggering condition for each fires — usually "this project has non-solo users" or "this concern is costing real time."
**Grounding decision:** [architecture.md](architecture.md) is the committed design; this file is a deferred-options backlog, not an amendment.

---

## Purpose

The committed architecture (LangGraph + LiteLLM + FastMCP + MCP surface) is deliberately minimal for a **solo developer on a Claude Max subscription**. The candidates below would simplify specific concerns but each adds an operational cost (a running service, a third abstraction, a vendor coupling) that isn't worth paying today. They're tracked here so they aren't re-discovered from scratch later.

Each entry lists: what it replaces, what it adds, and the **trigger** that would justify adoption.

---

## 1. Langfuse (observability + cost + eval)

**Role:** Self-hosted, open-source LLM observability platform. Traces every model call, attaches cost, versions prompts, and ships with an eval harness UI.

**Replaces / subsumes:**

- `StructuredLogger` — its tracing SDK emits structured records with richer per-node context.
- The deferred OpenTelemetry exporter (architecture.md §8.1).
- Parts of `CostTracker`'s reporting surface (the pydantic ledger stays; Langfuse becomes the UI on top).
- The eventual prompt-regression eval harness (mentioned in analysis/langgraph_mcp_pivot.md §E and architecture.md §10).

**Adds:**

- A running service: Postgres + Langfuse web app (Docker Compose is the common deployment).
- One SDK dependency (`langfuse-python`) and a few decorators / callbacks in the graph layer.
- Operational responsibility: backups, upgrades, TLS if exposed.

**Trigger to adopt:**

- More than one user of ai-workflows (non-solo).
- A prompt-regression incident caused by silent model change or prompt drift that log inspection alone couldn't diagnose.
- A need to share cost/usage dashboards with someone who isn't running the CLI themselves.

**Why not now:** the CLI + `CostTracker` report + `aiw list-runs` already answer every question a solo developer has, and running another service for a single user is pure overhead.

---

## 2. Instructor / pydantic-ai (structured-output library)

**Role:** Opinionated structured-output wrappers that take a pydantic model, an LLM call, and return a validated instance — with automatic retry on parse failure.

**Replaces / subsumes:**

- The `ValidatorNode` pattern's parse-and-retry logic.

**Adds:**

- A third abstraction stacked over LiteLLM and LangGraph's `ModelRetry`.

**Trigger to adopt:**

- `ValidatorNode` accretes more than ~50 lines of parse-and-retry plumbing that keeps regressing.
- A workflow needs streaming-validated structured output (Instructor has this natively).

**Why not now:** LiteLLM's `response_format` + LangGraph's `ModelRetry` cover the current needs without introducing a third library's idioms.

---

## 3. LangSmith (hosted LangGraph observability)

**Role:** LangChain's first-party hosted tracing and eval service. Tightest integration with LangGraph; deepest time-travel debugging.

**Replaces / subsumes:**

- Same surface area as Langfuse, but hosted by LangChain.

**Adds:**

- Paid LangChain cloud account.
- Data flows to LangChain's servers (trust / compliance consideration).

**Trigger to adopt:**

- Langfuse self-hosting proves too expensive operationally AND the LangSmith integrations (e.g. automated dataset collection from traces) deliver meaningful savings.
- LangGraph ships features that only work with LangSmith.

**Why not now:** Langfuse is strictly better on the "open-source, self-hostable, vendor-neutral" axis; we'd want Langfuse first.

---

## 4. Typer (pydantic-native CLI)

**Role:** CLI framework built on pydantic + type hints. Natural pairing for a project whose MCP layer is already pydantic-schema-driven.

**Replaces / subsumes:**

- Current `aiw` CLI framework (Click, probably).
- Enables CLI command definitions and MCP tool schemas to share pydantic models directly.

**Adds:**

- One dependency; mostly a rewrite of existing CLI code.

**Trigger to adopt:**

- The CLI and MCP surfaces start diverging (different input shapes for the same action), and keeping them in sync becomes a chore.
- Onboarding friction for new users — Typer's auto-generated `--help` is notably friendlier.

**Why not now:** Click works. Nothing is broken. The schema-sharing win is real but not yet felt.

---

## 5. Docker Compose for the Ollama + Langfuse stack

**Role:** Single-file setup that brings up Ollama (for Qwen) and — if Langfuse is adopted — Langfuse + Postgres, along with any model pulls and volumes.

**Replaces / subsumes:**

- Ad-hoc local Ollama install + manual model pulls.
- The README prose telling adopters how to reproduce the environment.

**Adds:**

- A `docker-compose.yml` plus a small init script.
- Docker as an implicit prerequisite for non-solo adopters.

**Trigger to adopt:**

- Another developer or evaluator tries to run the project and hits setup drift.
- The "bring up my dev environment" path grows past three manual steps.

**Why not now:** the solo-dev machine already has Ollama running; Docker adds a layer for a single user.

---

## 6. Documentation site (mkdocs-material or similar)

**Role:** Published docs site with navigable architecture, tutorials, API reference.

**Replaces / subsumes:**

- Nothing functional; augments the in-repo `design_docs/` and docstrings.

**Adds:**

- One dev dependency + a GitHub Pages / Netlify deploy.

**Trigger to adopt:**

- External users need onboarding material that a README can't carry.
- The project is being shown to others often enough that linking to a published doc is less friction than pointing at markdown files.

**Why not now:** `design_docs/` is the source of truth and is easy to read in the repo. Publishing it is a presentation problem, not an architecture one.

---

## 7. DeepAgents / pre-built LangGraph agent templates

**Role:** Higher-level agent patterns built on LangGraph (plan-execute loops, ReAct agents, researcher-writer pairs).

**Replaces / subsumes:**

- Potentially parts of the `planner` two-phase workflow (if one of the templates fits exactly).

**Adds:**

- Opinionated node structures that may fight our tier/validator/gate conventions.

**Trigger to adopt:**

- A concrete workflow needs a pattern the templates provide out of the box *and* the template's shape is compatible with `TieredNode` / `ValidatorNode` / `HumanGate`.

**Why not now:** the workflows we want (`planner`, `slice_refactor`) are bespoke enough that the templates likely get in the way.

---

## 9. `aiw cost-report <run_id>` — per-run cost breakdown CLI

**Role:** CLI (and later MCP) command that prints a per-run cost breakdown — total, plus buckets by model / tier / provider — from a persistent per-call `TokenUsage` ledger.

**Replaces / subsumes:**

- Nothing today. `aiw list-runs` already surfaces `runs.total_cost_usd` per row, and that scalar is the only cost signal the current budget-cap path consults ([cost.py](ai_workflows/primitives/cost.py) — `check_budget` reads `total()` only). `by_tier()` / `by_model()` on `CostTracker` exist but have zero non-test call sites.

**Adds:**

- A new per-call ledger in Storage (migration 004: `llm_calls` or `token_usages` table).
- New `SQLiteStorage` methods to write / list per-call rows, and a `CostTrackingCallback` wiring to persist each `TokenUsage` as the graph runs.
- Likely a new `provider` field on `TokenUsage` so `--by provider` has a data source (today `TokenUsage` carries only `model` + `tier`).
- A `CostTracker.from_storage(storage, run_id)` replay helper.
- A CLI command + a mirrored MCP tool (`get_cost_report`) in M4.

**Trigger to adopt** — any one of:

- **Claude Max overages become routine.** Once the subscription's Opus / Sonnet quotas start bounding actual work (the user hits the per-5-hour cap often enough to care), knowing which workflows / models drove the burn is a real decision input. Before that point it's introspection theatre.
- **A second per-token-billed provider gets integrated.** Today the runtime is Gemini Flash (free tier) + Claude Code CLI (Max subscription) + Ollama (local). If an OpenAI / Mistral / Anthropic-direct route lands as a supported tier, per-provider dollar accounting starts mattering for *that* route — promote at that point.
- **Gemini moves off its free-tier backup role.** If Gemini becomes a core tier driving substantial paid traffic (not the current "free Flash via `GEMINI_API_KEY`" setup), per-model cost breakdowns start driving tier-override decisions.

**Why not now:** under the current provider mix (Claude Max flat-rate + Gemini free tier + Ollama local) the by-X breakdowns have zero decision value. The `total_cost_usd` scalar on `aiw list-runs` answers the only question a solo developer has. The original T06 spec (M3) carried a `cost-report <run_id> --by model|tier|provider` half; it was dropped on 2026-04-20 per this entry after the reframe below it exposed the mismatch.

**Related history:** originally specced in [design_docs/phases/milestone_3_first_workflow/task_06_cli_list_cost.md](phases/milestone_3_first_workflow/task_06_cli_list_cost.md) — see that file's "Design drift and reframe" section for the full reasoning.

---

## 10. OpenTelemetry exporter (without Langfuse)

**Role:** Neutral structured-tracing export to any OTel backend (Jaeger, Honeycomb, Datadog, Grafana Tempo).

**Replaces / subsumes:**

- Part of `StructuredLogger`'s job if paired with a log/trace backend.

**Adds:**

- OTel SDK + exporter config.
- A trace-backend dependency (even if only dev-local Jaeger).

**Trigger to adopt:**

- Cross-service tracing becomes relevant (e.g. MCP server is called by something else that already emits OTel).
- Langfuse is rejected for data-locality reasons but tracing is still needed.

**Why not now:** we're not in a multi-service world. Log records are sufficient.

---

## Revisit cadence

Re-read this file:

1. Whenever a second user (human, not agent) starts using ai-workflows.
2. When a concrete pain point matches a listed trigger.
3. Before any milestone that would naturally touch observability, CLI UX, or packaging.

If a candidate moves from "deferred" to "adopt," promote it by:

1. Adding a KDR entry to `architecture.md`.
2. Writing an ADR under `design_docs/adr/` with the trigger that justified the flip.
3. Removing the entry from this file.
