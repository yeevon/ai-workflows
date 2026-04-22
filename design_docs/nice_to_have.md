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

## 11. Prune `CostTracker.by_tier` / `by_model` / `sub_models`

**Role:** Simplification pass on [`ai_workflows/primitives/cost.py`](../ai_workflows/primitives/cost.py) that removes the tier/model breakdown methods and the `TokenUsage.sub_models` recursion along with them.

**Replaces / subsumes:**

- `CostTracker.by_tier(run_id)` — returns `dict[tier, float]` rollup.
- `CostTracker.by_model(run_id, include_sub_models=True)` — returns `dict[model, float]` rollup.
- `TokenUsage.sub_models` — nested list that only exists to make `by_model` recurse through Claude Code Opus→Haiku sub-calls.

None of these have a non-test caller today. Every production code path (budget cap, `runs.total_cost_usd` stamp, `aiw list-runs` cost column) reads `CostTracker.total(run_id)` only. `by_tier` / `by_model` / `sub_models` were load-bearing under the pre-pivot per-token-billed provider set and became decorative after the M3 T06 reframe killed `aiw cost-report` (see §9) and M4 kickoff killed `get_cost_report`.

**Adds:**

- Nothing. This is a removal pass.

**Trigger to adopt** — **the same trigger as §9** (`aiw cost-report` / per-run breakdown returns). Specifically:

- **Per-token billing returns** — either Claude Max overages become routine, a second per-token-billed provider gets integrated, or Gemini moves off its free-tier backup role (see §9 triggers in full).

**Why linked to §9:** if §9 fires, `by_tier` / `by_model` become load-bearing again and we'd rebuild them anyway (plus a `provider` field on `TokenUsage`, plus a per-call ledger in Storage). So the right move today is *leave them alone* — deleting them saves ~40 LOC now but costs more than that if they're needed back later. If §9 stays deferred indefinitely (solo dev + subscription billing remains the steady state for another milestone or two), promote this entry to a cleanup task on its own merits.

**Why not now:** zero cost to leave in place; deletion is a separate refactor with its own reasoning and no forcing function. The T06 reframe plan itself flagged this as *"Candidate for a future simplification pass under a new KDR / nice_to_have trigger. Not this task's scope."*

Additional reason as of 2026-04-21 (M9 post-close-out deep-analysis): [M12](phases/milestone_12_audit_cascade/README.md) plans a new `CostTracker.by_role(run_id)` aggregator over `TokenUsage` to split role-tagged ("author" / "auditor" / "verdict") cost for the tiered audit cascade (see [ADR-0004](adr/0004_tiered_audit_cascade.md)). That makes the rollup *idiom* — not the specific `by_tier` / `by_model` signatures — a near-term load-bearing pattern again. Pruning `by_tier` / `by_model` and then adding `by_role` alongside would be a two-step churn. Leave them for now; re-evaluate only after M12 lands and the consumer set is final.

**Related history:** [`design_docs/phases/milestone_3_first_workflow/task_06_cli_list_cost.md`](phases/milestone_3_first_workflow/task_06_cli_list_cost.md) "Design drift and reframe" section. Additional context: [M9 deep analysis §6](phases/milestone_9_skill/deep_analysis.md).

---

## 12. Promote read-only MCP tools (`list_runs`, `cancel_run`) to `_dispatch`

**Role:** Move the storage-opening boilerplate for [`ai_workflows/mcp/server.py`](../ai_workflows/mcp/server.py)'s `list_runs` + `cancel_run` tools, and [`ai_workflows/cli.py`](../ai_workflows/cli.py)'s matching `list-runs` command, into [`ai_workflows/workflows/_dispatch.py`](../ai_workflows/workflows/_dispatch.py) alongside the existing `run_workflow` / `resume_run` helpers so all four tools share one dispatch path.

**Replaces / subsumes:**

- The four-line `await SQLiteStorage.open(default_storage_path())` + `storage.list_runs(...)` / `storage.cancel_run(...)` + close pattern that is currently duplicated between [cli.py](../ai_workflows/cli.py) (`list-runs` command) and [mcp/server.py](../ai_workflows/mcp/server.py) (`list_runs` + `cancel_run` tool bodies).

**Adds:**

- Two new functions in `_dispatch.py` (`list_runs(...)`, `cancel_run(...)`) plus matching tests.
- Indirection that isn't strictly necessary today — both surfaces already route through the same primitive (`SQLiteStorage`), so the surface parity KDR-002 promises is already there in spirit.

**Trigger to adopt** — any one of:

- **A third surface lands.** A web UI, a second MCP transport (HTTP, once stdio grows out), or any non-CLI non-MCP entry point would create a third duplicate of the storage-open boilerplate — worth consolidating at that point.
- **The read/flip tools acquire stateful concerns.** If `list_runs` gains cost recomputation, checkpoint inspection, or artifact hydration — or `cancel_run` grows the M6 in-flight abort path (process-local task registry + `task.cancel()` + `durability="sync"` per [architecture.md §8.7](architecture.md)) — the logic is no longer a one-liner and belongs in `_dispatch`.
- **CLI/MCP divergence appears.** If a bug surfaces where one surface's behaviour drifts from the other because the boilerplate was updated in only one place, promote immediately.

**Why not now:** both surfaces currently end on one line — `storage.list_runs(...)` / `storage.cancel_run(...)` — with zero orchestration logic to share. Wrapping two four-line call sites in a dispatch helper is strictly more code than leaving them inline, and KDR-002's "one path" promise is already satisfied at the primitive boundary.

**Related history:** surfaced in the 2026-04-20 M4 post-milestone deep drift-check — no audit issue filed, tracked here as a forward-looking cleanup option.

---

## 13. Register pydantic models with LangGraph's msgpack type registry (or move to JSON-mode checkpointing)

**Role:** Eliminate the `Deserializing unregistered type ai_workflows.workflows.planner.PlannerInput / ExplorerReport / PlannerPlan / SliceSpec / SliceResult / SliceAggregate from checkpoint` warnings LangGraph emits during capture + resume paths. Two implementation options:

1. Register each checkpoint-persisted pydantic model with LangGraph's msgpack type registry at module-import time, so the serializer round-trips them with stable IDs.
2. Switch the checkpoint write path to `model_dump(mode="json")` before handoff to LangGraph's serializer — trades compactness for schema-stable text.

**Replaces / subsumes:**

- Nothing functional today. The warnings are advisory under the current LangGraph release — deserialization still succeeds. But a future LangGraph version is expected to block unregistered types at read time, which would break resume of any checkpoint written before that version.

**Adds:**

- Option 1: a registry-setup module imported once at `ai_workflows.workflows` init, touching every model that flows through LangGraph state.
- Option 2: a small adapter in the `TieredNode` / state-update path that rewrites pydantic instances to JSON dicts before state commit.

**Trigger to adopt** — any one of:

- A LangGraph minor release promotes the warning to an error (tracked via their CHANGELOG; verifiable by running the M7 capture path against the new release).
- A resume path fails in production with a deserialization error that traces back to one of the pydantic classes enumerated above.
- Any milestone whose tests would benefit from warning-free stderr output for readability (e.g. a future eval harness extension that diffs log stream shape across runs).

**Why not now:** the warnings are cosmetic on the current LangGraph version and adopting either fix before LangGraph forces the issue risks committing to an API that moves. The M7 capture + deterministic replay paths round-trip these classes today without functional incident. Tracked as a forward-looking maintenance item rather than a feature-wish.

**Related history:** surfaced during M7 T05 `slice_refactor` seed capture (run `eval-seed-slice2`); logged as M7-T05-ISS-06 in [phases/milestone_7_evals/issues/task_05_issue.md](phases/milestone_7_evals/issues/task_05_issue.md); deferred to this entry at M7 T06 close-out (2026-04-21) per the "No code change beyond docs" close-out discipline.

---

## 14. Promote live-mode eval replay to a nightly or manual-PR-annotated CI job + tolerance refinement

**Role:** Turn the `aiw eval run <workflow> --live` path from "manual opt-in" into a signal-producing automation. Today it is double-gated (`AIW_EVAL_LIVE=1` + `AIW_E2E=1`) and only exercised at milestone close-out; the current committed fixtures fail every live case because `strict_json` + full-sentence `field_overrides={"summary": "substring"}` tolerance is too strict to survive minor model-phrasing drift.

**Replaces / subsumes:**

- The manual "close-out-time live replay baseline" ritual recorded in CHANGELOG at each milestone close.
- Nothing in deterministic CI (the deterministic `eval-replay` job landed at M7 T05 stays unchanged — this item only moves live mode out of manual-only status).

**Adds:**

- Tolerance refinement work across the seed fixtures: replace full-sentence captured substrings with short distinctive keywords (e.g. `"release checklist"`, `"v1.2.0"`, `"def add"`) so live comparisons produce signal rather than noise from phrasing drift. Each fixture needs per-field analysis.
- A nightly or label-triggered GitHub Actions job (scheduled cron or `workflow_dispatch` + PR label) that runs `AIW_E2E=1 AIW_EVAL_LIVE=1 uv run aiw eval run planner --live` + `... slice_refactor --live`. Secrets wiring (`GEMINI_API_KEY`), Ollama runtime in CI, and a flake-rate policy (live output varies more than deterministic).
- A drift-triage workflow when the live job fails: is the failure (a) genuine model-side regression, (b) phrasing drift below the threshold, or (c) tolerance mis-spec.

**Trigger to adopt** — any one of:

- **A prompt-regression incident** that deterministic replay missed but live replay would have caught — makes the cost of running live mode automatically worth paying.
- **A second LLM-node-bearing workflow** beyond `planner` + `slice_refactor` where per-node model-side drift would bite before the next manual close-out.
- **Provider-side changes** that land without advance notice often enough that a trailing signal becomes valuable (e.g. Gemini Flash retraining, Claude Code model upgrades).

**Why not now:** at close-out time (M7 T06, 2026-04-21) the live replay was recorded once as a baseline — `planner` 0/2 live-fail, `slice_refactor` 0/1 live-fail, all model-phrasing drift below what the current substring tolerance tolerates. The deterministic CI gate (2/2 + 1/1 pass) is the one that protects PRs; live mode today is a diagnostic, not a gate. Automating it without refining tolerances would green-flag wall-of-noise failures, drowning real signal. Deferring both the automation and the tolerance tune until a concrete drift incident demonstrates the need.

**Related history:** live-replay baseline recorded in CHANGELOG at M7 T06 close-out (2026-04-21).

---

## 15. Expose eval-harness tools on the MCP surface (parity with `aiw eval capture` / `aiw eval run`)

**Role:** Add `capture_eval_dataset(run_id, dataset)` + `run_eval(workflow_id, dataset?, live?)` tools to [`ai_workflows/mcp/server.py`](../ai_workflows/mcp/server.py) so agents driving the workflow inside-out have the same replay + capture hooks that the CLI now exposes. KDR-002 ("CLI and MCP are peers"): the asymmetry is today's dev-loop shape — the harness is a Builder / Auditor tool, not a workflow-client one — but a host-authored agent that wanted to run a regression replay after a live run finished has no surface to call.

**Replaces / subsumes:**

- Nothing functional today. The CLI paths (`aiw eval capture --run-id ... --dataset ...` in [`ai_workflows/cli.py`](../ai_workflows/cli.py)) already cover the full capture + replay loop. No MCP consumer has asked.

**Adds:**

- Two new FastMCP tools in [`ai_workflows/mcp/server.py`](../ai_workflows/mcp/server.py), pydantic-typed I/O per KDR-008, routed through `_capture_cli` + `EvalRunner` the CLI already uses (no new dispatch helper — these are read-side + stub-adapter-replay-side calls that don't need [`_dispatch.py`](../ai_workflows/workflows/_dispatch.py)).
- Corresponding schemas under [`ai_workflows/mcp/schemas.py`](../ai_workflows/mcp/schemas.py).
- MCP smoke coverage (same always-run hermetic style as M4 T07's four-tool smoke).
- An architecture.md §4.4 line acknowledging the dev-loop boundary (either documenting the intentional asymmetry, or — if promoted — folding the new tools into the §4.4 table).

**Trigger to adopt** — any one of:

- **A second host consumer** beyond Claude Code lands (a web agent, a scheduled MCP job, a skill that wants to replay after a user-driven run) — at that point the CLI-only hook forces a subprocess shell-out from inside an MCP tool, which is worse than exposing the surface natively.
- **A nightly automation workflow** (see §14) gets built. If live-replay moves from "manual close-out ritual" to "scheduled automation that needs to be triggered from a CI-adjacent surface", doing it through MCP-tool calls from an orchestrator is cleaner than CLI-in-shell.
- **Eval-as-gate semantics** emerge — e.g. a workflow run that won't close without a passing replay against its own fresh capture. That forces the harness into the inside-out call path.

**Why not now:** M7 evals are a dev-loop concern — Builders capture, Auditors review, CI replays on PR. No inside-out consumer exists today, and the CLI covers every real workflow. Exposing the MCP surface without a consumer costs two tool surfaces + their test + their schema + their doc line, in exchange for nothing concrete. The CLI path stays authoritative; MCP parity is deferred until a real caller appears.

**Related history:** surfaced in the 2026-04-21 M7 post-milestone deep drift-check — no audit issue filed, tracked here as a forward-looking cleanup option. Mirrors the [§12](#12-promote-read-only-mcp-tools-list_runs-cancel_run-to-_dispatch) shape from the M4 post-milestone drift-check.

---

## 16. Centralise env-var documentation in one reference table

**Role:** Collect every `AIW_*` environment variable the project reads into a single discoverable table — either an `## Environment variables` section in [`design_docs/architecture.md`](architecture.md) (preferred — architecture.md is the grounding doc every Builder opens) or a standalone `design_docs/env_vars.md`. Today the env-vars are documented at their use sites (module docstrings, task files, test gates), which is accurate but non-discoverable.

**Replaces / subsumes:**

- The scattered references: `AIW_CAPTURE_EVALS` is documented in [`ai_workflows/evals/capture_callback.py`](../ai_workflows/evals/capture_callback.py) + [`ai_workflows/workflows/_dispatch.py`](../ai_workflows/workflows/_dispatch.py); `AIW_EVAL_LIVE` in [`ai_workflows/evals/runner.py`](../ai_workflows/evals/runner.py); `AIW_EVALS_ROOT` in [`ai_workflows/evals/storage.py`](../ai_workflows/evals/storage.py); `AIW_STORAGE_DB` + `AIW_CHECKPOINT_DB` in the primitives layer; `AIW_E2E` in the `tests/e2e/` gate plumbing; `GEMINI_API_KEY` in the provider tier config. Seven variables, zero single-reference point.

**Adds:**

- One markdown table: `Variable | Purpose | Read by | Default behaviour when unset | First introduced (milestone)`.
- A convention note: new Builders who add an env-var are expected to update the table in the same PR.
- Optional: a `tests/test_env_vars_documented.py` that greps for `os.environ[...]` / `os.getenv(...)` in `ai_workflows/**` and asserts each variable appears in the table. Low value today, high value once the table exists.

**Trigger to adopt** — any one of:

- **A third contributor joins the project.** The single-maintainer case today makes site-local docstrings sufficient; a second human without the author's mental model is the first person who actually needs a central reference.
- **An env-var collision or footgun incident** — e.g. a Builder lands a new `AIW_FOO` that silently overrides an existing one, or a test leaks an env-var into a later test module. The postmortem would call for exactly this table.
- **A packaging / distribution step** (container image, standalone binary, Claude Code skill packaging per [roadmap.md M9](roadmap.md)) — any external-facing artifact needs the env-var surface enumerated for the user reading a `docker run ... -e AIW_FOO=bar` line.

**Why not now:** single-maintainer project with ~7 env-vars, all documented at their use sites. Grepping for `AIW_` across the repo finds every one. Adding a table now is ceremony without a consumer, and the table would silently rot unless a test enforces it. Deferred until a forcing function appears.

**Related history:** surfaced in the 2026-04-21 M7 post-milestone deep drift-check — the `AIW_CAPTURE_EVALS` + `AIW_EVAL_LIVE` + `AIW_EVALS_ROOT` additions brought the total to ~7 env-vars spread across ~28 files. No audit issue filed.

Re-evaluated during the 2026-04-21 [M9 post-close-out deep-analysis](phases/milestone_9_skill/deep_analysis.md): [`skill_install.md §1`](phases/milestone_9_skill/skill_install.md) enumerates `GEMINI_API_KEY` + the `claude` CLI on PATH as external-facing prereqs — the skill-packaging sub-trigger in the list above fired *weakly*. Threshold judged **not met**: the skill doc is consumed in-repo (no `docker run -e` line, no standalone binary), the single-maintainer precondition still holds, and both prereqs are already discoverable at their use sites. The call flips if any of the stronger triggers above fire (second human contributor, env-var collision incident, or an external-facing distribution artefact like a container image or standalone binary).

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
