# ai-workflows — Issues Backlog

Status legend: `[ ]` open · `[~]` in progress · `[x]` resolved · `[!]` blocked · `[-]` deferred

**Structure:** priority-tiered sections at the top (from post-research analysis). Original layer-grouped issues retained below for reference.

---

## Strategic Decisions (Resolved 2026-04-18)

- [x] **SD-01** — Adopt `pydantic-ai + pydantic-graph + pydantic-evals` as substrate. Our framework is the thin layer: tier routing, workflow YAML loader, SQLite run log, cost tracking with budget caps. Component taxonomy wraps `pydantic_ai.Agent[Deps, Output]`.
- [x] **SD-02** — Linear `Pipeline` in M1–M3; DAG `Orchestrator` promotes Pipeline in M4. Pipeline component is the M2 addition. `networkx` is an optional-dep installed at M4.
- [x] **SD-03** — `OllamaClient` adapter in M1; all M1–M3 workflows default to cloud tiers (Haiku/Sonnet). Ollama operational wrapping (health checks, VPN drop handling, Haiku fallback) lands in M4.
- [x] **SD-04** — Keep Primitives and Components as separate modules. Lego-block composition is core; preserve the boundary. `import-linter` enforces.

---

## Critical — Fix Before Milestone 1 Code Ships

These break correctness or safety if left unresolved. From post-research analysis.

- [ ] **CRIT-01** — Task-to-task data flow (supersedes C-14). Decision needed: typed Pydantic schemas per task with compile-time DAG type-checking (Haystack pattern). Without this, the Orchestrator is incomplete and every workflow reinvents this wheel.
- [ ] **CRIT-02** — Workflow directory content hash stored in `runs` table. Resume refuses on mismatch unless `--force-workflow-version-mismatch`. Current design only snapshots `workflow.yaml`; prompts and `custom_tools.py` changes go undetected.
- [ ] **CRIT-03** — Budget cap `max_run_cost_usd` in workflow config (upgrades P-35 from deferred to critical). `CostTracker` checks after every LLM call, raises `BudgetExceeded`. 30 lines. User is paying Claude Max out of pocket; a runaway Opus loop = $50 overnight.
- [ ] **CRIT-04** — Delete or rebrand the regex sanitizer (revises X-07). ContentBlock `tool_result` wrapping is the real defense and stays. Regex pattern matching against injection is theater; false security is worse than none. Either delete `primitives/tools/sanitizer.py` entirely, or rebrand as `forensic_logger.py` with docstring clarifying it is logging for post-hoc analysis, NOT a security control.
- [x] **CRIT-05** — `ClientCapabilities` descriptor on `LLMClient`. Pydantic model with `supports_prompt_caching`, `supports_parallel_tool_calls`, `supports_structured_output`, `max_context`, `supports_thinking`. Components check capabilities, never `isinstance()` provider class. Prevents layering violations. *Resolved by M1 Task 03: per-adapter wiring in all four `_build_*` helpers.*
- [~] **CRIT-06** — Set `max_retries=0` on every underlying SDK client at adapter construction (Anthropic, OpenAI, httpx). `retry_on_rate_limit()` is the single authority. Prevents 3 × 3 = 9 retry double-amplification and double-counted rate-limit pressure. *Anthropic and OpenAI-compat branches: explicit `max_retries=0`. Google branch: relies on google-genai default `stop_after_attempt(1)` (documented in `_build_google()` + regression test). Fully resolved when Task 10 (`retry_on_rate_limit`) lands.*
- [ ] **CRIT-07** — Multi-breakpoint prompt caching strategy (revises P-04). Auto-cache (a) last tool definition block (1h TTL), (b) last truly static system block (1h TTL), (c) top-level automatic cache on conversation history (5m TTL). Current "cache last system block" fails when the last block has `{{variable}}` substitutions — 100% cache miss. Validate via `cache_read_input_tokens > 0` assertion on turn 2+.
- [ ] **CRIT-08** — Retry error taxonomy (revises P-37). Three classes: retryable-transient (429, 529, `APIConnectionError`, `overloaded_error`) → `retry_on_rate_limit`; retryable-semantic (Pydantic validation, parse errors) → `ModelRetry` feeding the error back to the LLM; non-retryable (`invalid_request_error`, auth) → raise immediately. Current 429/529-only is incomplete.
- [x] **CRIT-09** — `ContentBlock` discriminated union. Add `type: Literal[...]` field to each block class. Apply `Field(discriminator='type')` on the union. Without the discriminator, Pydantic v2 attempts each variant in order — confusing errors, tanks performance on long messages. *Resolved by M1 Task 02.*
- [ ] **CRIT-10** — Migration framework via `yoyo-migrations` or `sqlite-utils.Database.migrate()` (revises P-27). Adds a `_migrations` version table and rollback paths. 10-minute change in M1; a day of archaeology in M5.
- [ ] **CRIT-11** — AgentLoop subagent context isolation policy (completes X-01). Default: fresh context per subagent (Anthropic pattern). Opt-in shared thread with documented risk. Write this down before AgentLoop is built.

---

## Important — Fix Before Milestone 3 Ships

- [ ] **IMP-01** — Evaluation harness via `pydantic-evals` in M3. `Case + Dataset + LLMJudge + span-based evaluators`. Ten cases per workflow, `aiw eval <workflow>` command, results written to SQLite. Without this, prompt iteration is blind.
- [ ] **IMP-02** — OTel GenAI spans via `logfire` in M3. `logfire.configure()` + `logfire.instrument_anthropic()`. Two lines. Emits standardized spans compatible with Langfuse / Phoenix / Braintrust.
- [ ] **IMP-03** — `aiw rerun-task <run_id> <task_id>` — replay one task from checkpointed inputs with current prompts. Minimum viable prompt iteration loop.
- [ ] **IMP-04** — `aiw inspect <run_id> --task <task_id>` — print full prompt + tool calls + LLM output + validator result for one task. Pure SQLite query.
- [ ] **IMP-05** — HumanGate timeout default (revises C-31). `strict_review=True` → `timeout=None` (wait forever, user resumes). Non-strict → 30 min. Or declare per workflow. Current 30-min-always breaks overnight batch review pattern.
- [ ] **IMP-06** — Ollama flakiness handling. Startup health check fails fast with actionable error. Explicit `ConnectionError → pause and surface` (not retry forever). Distinct retry backoff for LAN vs cloud.
- [ ] **IMP-07** — `test_coverage_gap_fill` pass/fail metric defined before writing the workflow. Without a metric, no evals, no DSPy, no regression detection. Required spec input.
- [ ] **IMP-08** — Send-equivalent runtime fan-out (if DAG is built). Plan schema must support "Worker returns K items, spawn K sub-workers." Static DAG can't express "search returned K docs, summarize all." Defer until M4-5 demands it; design Plan schema to permit it.

---

## Important — Operational (Fix Any Time)

- [ ] **OPS-01** — `aiw gc --older-than 30d --keep-artifacts` for log/run directory rotation. Disk fills otherwise.
- [ ] **OPS-02** — `aiw stats --last 30d` multi-run observability. SELECT from `runs`, `llm_calls`, `tasks`. One afternoon; pays back hundreds of hours/year.
- [ ] **OPS-03** — `aiw cost` command (absorbed from CL-03). Query by run_id, workflow, date range, component.

---

## Resolved (Grilling Session, 2026-04-17)

## Primitives (Layer 1)

### LLM Client

- [x] **P-01** — `Message` type: flat `Message(role, content: list[ContentBlock])`. Lives in `primitives/llm/base.py`.
- [x] **P-02** — `Response` type: normalized-only — `Response(content: list[ContentBlock], stop_reason: str, usage: TokenUsage)`.
- [x] **P-03** — Streaming deferred. `generate()` always returns a complete `Response`.
- [~] **P-04** — **REVISED by CRIT-07**: auto caching in `AnthropicClient` replaced by multi-breakpoint strategy.
- [x] **P-05** — Ollama token cost recorded as `0.0`, excluded from cost aggregations.
- [ ] **P-06** — `OpenAICompatClient` sub-adapters: decide when first compat provider is wired up.
- [x] **P-07** — Tool call response normalization happens inside each adapter.
- [ ] **P-08** — `max_tokens` override per `generate()` call — decide at M1 implementation.
- [x] **P-09** — Authentication: env vars only. No API keys in YAML files.
- [ ] **P-10** — Connection pooling: shared `AsyncClient` per adapter instance. Decide at implementation.

### Tool Registry

- [x] **P-11** — Injected `ToolRegistry` per workflow run.
- [ ] **P-12** — Tool input validation against JSON schema: decide at implementation.
- [x] **P-13** — `run_command` sandboxing: CWD restriction + `allowed_executables` allowlist + `dry_run` flag.
- [x] **P-14** — `working_dir` defaults to declared project root.
- [ ] **P-15** — Tool timeout: per-tool configurable with generous default.
- [x] **P-16** — No hard truncation. Each tool call accepts optional `max_chars` param.
- [ ] **P-17** — Consolidate `http_get` / `http_fetch` into one `http_fetch` tool.
- [ ] **P-18** — `git_apply` checks clean working tree, refuses if dirty.
- [ ] **P-19** — Tool errors return structured `ToolError` content block (LLM-reactable), not raised exception.
- [x] **P-20** — Workflow-scoped tools resolved by injected registry.
- [ ] **P-21** — `tiers.yaml` location when installed: bundle as package data via `importlib.resources`.
- [x] **P-22** — `sonnet` tier missing `temperature` was oversight. Add `temperature: 0.1`.
- [x] **P-23** — Retired model validation: fail lazily on first call, log clearly.
- [x] **P-24** — No tier hot-reload. Snapshotted at run start.
- [ ] **P-25** — `deterministic` tier: define when first deterministic workflow step is built.

### Storage

- [x] **P-26** — Global `~/.ai-workflows/` directory. Override via `AIWORKFLOWS_HOME` env var or `--profile`.
- [~] **P-27** — **REVISED by CRIT-10**: switch from manual SQL to `yoyo-migrations`.
- [x] **P-28** — SQLite WAL mode.
- [x] **P-29** — Intermediate artifacts as files in `runs/<run_id>/`. Paths in SQLite.
- [x] **P-30** — Run directory `~/.ai-workflows/runs/<run_id>/`.
- [ ] **P-31** — `StorageBackend` protocol for future cloud backend.

### Cost Tracking

- [x] **P-32** — Token pricing in `pricing.yaml`.
- [x] **P-33** — Local model cost `0.0`.
- [x] **P-34** — LLM calls only for MVP; tool call cost tracking deferred.
- [~] **P-35** — **REVISED by CRIT-03**: budget limits upgraded from deferred to critical.

### Retry / Rate-Limit / Backoff

- [x] **P-36** — `retry_on_rate_limit()` utility function in primitives.
- [~] **P-37** — **REVISED by CRIT-08**: retry error taxonomy expanded beyond 429/529-only.
- [ ] **P-38** — Per-tier rate limit tracking via `x-ratelimit-remaining` headers if reliable.
- [-] **P-39** — Circuit breaker deferred, out of scope MVP.
- [x] **P-40** — Max retry count: default 3, configurable per tier.
- [x] **P-41** — Jitter added to backoff.

### Logging

- [x] **P-42** — `structlog`. **Augmented by IMP-02**: `logfire` for OTel output in M3.
- [ ] **P-43** — Log level defaults: INFO events, DEBUG LLM I/O.
- [x] **P-44** — Sensitive data: local-only, gitignored.

---

## Components (Layer 2)

### General

- [x] **C-01** — `BaseComponent` ABC with shared logging, cost tagging, run_id threading. **Contingent on SD-01** (may be replaced by Pydantic AI `Agent`).
- [x] **C-02** — Pydantic model per component, loaded from YAML at workflow start.
- [x] **C-03** — Component instantiation at workflow load time.
- [x] **C-04** — `run_id`, `workflow_id`, `component` explicit kwargs. **Contingent on SD-01** (may be replaced by Pydantic AI `RunContext`).
- [x] **C-05** — Primitive-level retry only.

### Planner

- [x] **C-06** — Planner outputs a DAG. **Contingent on SD-02** (may be deferred to M4 if linear Pipeline chosen for M1-M3).
- [x] **C-07** — Plan parse failure: max 3 retries, then abort.
- [x] **C-08** — Two-phase planning: Qwen exploration + Opus planning with tools.
- [x] **C-09** — `max_tasks` default 50.

### Orchestrator

- [x] **C-10** — DAG topological sort via `networkx`. **Contingent on SD-02**.
- [x] **C-11** — Per-provider semaphore. Fanout max 5, hard cap 8.
- [x] **C-12** — Double failure = full hard stop. (Note: analysis suggests per-workflow `failure_policy` — `hard_stop` / `best_effort` / `n_of_m` — for future flexibility.)
- [x] **C-13** — Checkpoint/resume from M1.
- [~] **C-14** — **REVISED by CRIT-01**: task data flow now critical, defined as typed Pydantic schemas on tasks.

### Worker

- [x] **C-15** — Simple `{{variable}}` substitution.
- [ ] **C-16** — Worker output parsing into declared Pydantic model. Clarify at M2.
- [x] **C-17** — Worker `max_turns`: Sonnet 15, others single-call. **Contingent on SD-01**.

### Validator

- [x] **C-18** — Structural + semantic types from day one.
- [x] **C-19** — Failure reason returned as structured output. (Analysis suggests chainable validators — `validators: list[Validator]` rather than single; borrow from CrewAI guardrails. Defer until second workflow demands.)

### Escalator

- [x] **C-20** — Fixed escalation order `local_coder → haiku → sonnet → opus`.
- [x] **C-21** — Escalation tagged separately in run log.

### AgentLoop

- [x] **C-22** — Termination: no tool calls + `done` tool + `max_iterations`. (Analysis suggests composable termination conditions à la AutoGen — `cond_a & cond_b | cond_c` — as first-class objects. Nice-to-have, not critical.)
- [x] **C-23** — `max_iterations` default 20.
- [ ] **C-24** — Context compaction when approaching context limit. Implement when AgentLoop is built.
- [x] **C-25** — AgentLoop weak guarantee documented. Orchestrator mandates Validator after every AgentLoop step.

### Fanout

- [x] **C-26** — Max 5 concurrent, hard cap 8.
- [x] **C-27** — Input order preserved.
- [x] **C-28** — Individual failures isolated.

### Synthesizer

- [x] **C-29** — Hierarchical synthesis for large input sets.

### HumanGate

- [x] **C-30** — Raw JSON to log file; pretty-printed to terminal.
- [~] **C-31** — **REVISED by IMP-05**: timeout=None for strict_review=True.
- [x] **C-32** — Resume via SQLite checkpoint.
- [x] **C-33** — Approve / reject / edit-then-approve; `strict_review` flag.

---

## Workflows (Layer 3)

- [x] **W-01** — `pyyaml` + Pydantic validation.
- [x] **W-02** — `flow:` + `after:`/`before:` DAG merge.
- [~] **W-03** — **REVISED by CRIT-02**: snapshot entire workflow directory, store content hash.
- [ ] **W-04** — `run.py` entry point: CLI arg parsing only. Decide at M3.
- [ ] **W-05** — Cross-workflow data sharing model. Decide at M6.

---

## CLI (`aiw`)

- [x] **CL-01** — `typer`.
- [x] **CL-02** — Structured progress lines.
- [~] **CL-03** — **REVISED by OPS-03**: absorbed into operational issues.
- [x] **CL-04** — `aiw resume <run_id>`.
- [x] **CL-05** — `aiw list-runs` / `aiw inspect <run_id>`.

---

## Repo / Tooling

- [x] **R-01** — `import-linter` PyPI package. **Contingent on SD-04**.
- [x] **R-02** — `hatchling`.
- [x] **R-03** — Python 3.12 floor, 3.13 target.
- [x] **R-04** — `uv`.
- [x] **R-05** — `pytest-asyncio` with `asyncio_mode = "auto"`.
- [x] **R-06** — CI check: no secrets in `tiers.yaml` / `pricing.yaml`.
- [x] **R-07** — `.gitignore` covers runs, db, env, tiers.local.yaml.
- [ ] **R-08** — Workflow-specific `custom_tools.py` auto-discovered at workflow load.

---

## Cross-Cutting / Architecture

- [~] **X-01** — **REVISED by CRIT-11**: AgentLoop subagent context isolation policy now critical.
- [x] **X-02** — Explicit param threading. **Contingent on SD-01**.
- [ ] **X-03** — SIGINT cancellation for in-flight LLM and fan-out tasks. Implement at M4.
- [-] **X-04** — OpenTelemetry. **Superseded by IMP-02** (logfire).
- [ ] **X-05** — `py.typed` marker: add if package is published.
- [ ] **X-06** — CI pipeline. Define at M1 scaffolding.
- [~] **X-07** — **REVISED by CRIT-04**: sanitizer rebranded or deleted; ContentBlock wrapping stays.
- [-] **X-08** — Multi-machine distributed: deferred.
- [ ] **X-09** — Windows/WSL: document as untested.
- [ ] **X-10** — Pydantic v2 pinned.

---

## Open Questions (from original design doc)

- [x] **OQ-01** — Plan schema strictness: strict + bounded retry (C-07).
- [x] **OQ-02** — `HumanGate` render: CLI-first (C-30).
- [x] **OQ-03** — Long-running workflow blocking: checkpoint/resume from M1 (C-13).
- [-] **OQ-04** — Workflow packaging as plugins: deferred.
- [x] **OQ-05** — Workflow output versioning: timestamped run directories (P-30).
- [ ] **OQ-06** — Windows support: documented as untested.

---

## Post-MVP

- [ ] **PM-01** — MCP server: thin read interface over SQLite, post-M2.
- [ ] **PM-02** — Streaming via `stream_generate()`: additive, for HumanGate display only.
- [ ] **PM-03** — Encrypted checkpoint serde (LangGraph pattern) if ever shared-machine deployed.
- [ ] **PM-04** — Cross-run `Store` / memory (LangGraph pattern) when workflow #3 needs it.
- [ ] **PM-05** — DSPy prompt optimization for highest-value workflows with labeled data.
- [ ] **PM-06** — Chainable `Validator` (CrewAI guardrail pattern) when second workflow demands.
- [ ] **PM-07** — Composable termination conditions (AutoGen pattern) — first-class predicate objects.
- [ ] **PM-08** — Qwen2.5-Coder:14b benchmark vs :32b.

---

*Last updated: 2026-04-18 — post-research analysis. Add new issues at the bottom of the relevant section with the next available ID.*
