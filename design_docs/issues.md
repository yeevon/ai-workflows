# ai-workflows — Issues Backlog

Status legend: `[ ]` open · `[~]` in progress · `[x]` resolved · `[!]` blocked · `[-]` deferred

---

## Primitives (Layer 1)

### LLM Client

- [x] **P-01** — `Message` type: flat `Message(role, content: list[ContentBlock])`. Content blocks carry tool use, tool results, images, cache markers. Lives in `primitives/llm/base.py`.
- [x] **P-02** — `Response` type: normalized-only — `Response(content: list[ContentBlock], stop_reason: str, usage: TokenUsage)`. Raw provider payload stays inside the adapter.
- [x] **P-03** — Streaming deferred. `generate()` always returns a complete `Response`. A `stream_generate()` variant can be added later as an additive method, used only by `HumanGate`'s display layer.
- [x] **P-04** — Prompt caching automatic in `AnthropicClient` (marks last system message block as cacheable). `ContentBlock` has no cache fields — invisible to callers.
- [x] **P-05** — Ollama token cost recorded as `0.0`, excluded from cost aggregations.
- [ ] **P-06** — `OpenAICompatClient` covers OpenRouter, DeepSeek API, Gemini. Does one adapter handle all three, or do sub-adapters exist per quirk surface? Decide when first compat provider is wired up.
- [x] **P-07** — Tool call response normalization happens inside each adapter. Every adapter translates provider-specific tool call formats into `ContentBlock` entries before returning `Response`.
- [ ] **P-08** — `max_tokens` override per `generate()` call: is it a parameter or only set at the tier level? Decide at Milestone 1 implementation.
- [x] **P-09** — Authentication: env vars only. No API keys in YAML files. `.env` supported locally.
- [ ] **P-10** — Connection pooling: shared `AsyncClient` instance per adapter vs. per-call. Decide at implementation — likely shared instance per `AnthropicClient` instance.

### Tool Registry

- [x] **P-11** — Injected `ToolRegistry` per workflow run. Each workflow registers its tools (stdlib + custom) into its own instance. Test isolation is free.
- [ ] **P-12** — Tool input validation: registry validates args against JSON schema before calling the function. Decide at implementation.
- [x] **P-13** — `run_command` sandboxing: CWD restriction (refuses `..` path traversal) + `allowed_executables` allowlist per workflow YAML + `dry_run: bool` flag.
- [x] **P-14** — `working_dir` defaults to declared project root. Allowlist enforced at call time — commands not in the list raise immediately.
- [ ] **P-15** — Tool timeout: per-tool configurable timeout. Decide at implementation. Likely a `timeout_seconds` param with a generous default.
- [x] **P-16** — No hard truncation. Each tool call accepts optional `max_chars` param. Worker YAML can declare a default. Cost tracker surfaces runs burning budget on large outputs.
- [ ] **P-17** — `http_get` vs `http_fetch` — consolidate to one `http_fetch` tool. Remove the redundancy.
- [ ] **P-18** — `git_apply`: requires a clean working tree check before running. Responsibility: the tool itself checks and refuses if tree is dirty.
- [ ] **P-19** — Tool error representation: failures return a structured `ToolError` content block (not raised exception) so the LLM can react and try a different approach.
- [ ] **P-21** — `tiers.yaml` location when package is installed: bundle as package data via `importlib.resources`. Decide at Milestone 1.
- [x] **P-20** — Workflow-scoped tools resolved by injected registry (from P-11).
- [x] **P-22** — `sonnet` tier missing `temperature` was an oversight. Add `temperature: 0.1`.
- [x] **P-23** — Retired model validation: fail lazily on first call, log the error clearly with the model name.
- [x] **P-24** — No tier hot-reload. Tiers are snapshotted at run start.
- [ ] **P-25** — `deterministic` tier referenced in workflow YAML example but undefined. Likely a non-LLM code path (regex rules, OpenRewrite). Define when first deterministic workflow step is built.

### Storage

- [x] **P-26** — Global `~/.ai-workflows/` directory. Overridable via `AIWORKFLOWS_HOME` env var or `--profile` flag loading a `tiers.local.yaml` overlay.
- [x] **P-27** — Schema migrations: manual SQL scripts in `migrations/`. No Alembic for now.
- [x] **P-28** — SQLite concurrent writes: WAL mode enabled at connection open.
- [x] **P-29** — Intermediate artifacts (plans, diffs, exploration docs, review decisions) stored as files in `runs/<run_id>/`. Paths stored in SQLite.
- [x] **P-30** — Run directory: `~/.ai-workflows/runs/<run_id>/`. `workflow.yaml` snapshotted into run dir at start. Exploration docs at `runs/<run_id>/exploration/`.
- [ ] **P-31** — Storage interface abstraction: define the `StorageBackend` protocol at Milestone 1 so SQLite implements it correctly and a cloud backend can plug in later.

### Cost Tracking

- [x] **P-32** — Token pricing in `pricing.yaml` alongside `tiers.yaml`, updated manually when provider pricing changes.
- [x] **P-33** — Local model (Ollama) cost: record `0.0`, excluded from aggregations.
- [x] **P-34** — Cost tracking granularity: LLM calls only for MVP. Tool call cost tracking deferred.
- [-] **P-35** — Budget limits per run: out of scope MVP.

### Retry / Rate-Limit / Backoff

- [x] **P-36** — `retry_on_rate_limit()` utility function in primitives. Explicit opt-in, no magic decorator.
- [x] **P-37** — Only 429/529 trigger retry. All other errors raise immediately.
- [ ] **P-38** — Per-tier rate limit tracking: header-based (`x-ratelimit-remaining`) is most accurate. Implement at Milestone 1 if Anthropic headers are reliable.
- [-] **P-39** — Circuit breaker: deferred, out of scope MVP.
- [x] **P-40** — Max retry count: default 3, configurable per tier in `tiers.yaml`.
- [x] **P-41** — Jitter added to exponential backoff to avoid thundering herd.

### Logging

- [x] **P-42** — `structlog` as logging framework.
- [ ] **P-43** — Log level defaults: INFO for cost summaries and run events; DEBUG for full LLM inputs/outputs. Confirm at implementation.
- [x] **P-44** — Sensitive data: logs are local-only, in `.gitignore`. User responsibility. `~/.ai-workflows/` and `runs/` excluded from git.

---

## Components (Layer 2)

### General

- [x] **C-01** — `BaseComponent` ABC with shared logging, cost tagging, and `run_id` threading.
- [x] **C-02** — Component config: Pydantic model per component, loaded from YAML at workflow start.
- [x] **C-03** — Component instantiation at workflow load time, not lazily.
- [x] **C-04** — `run_id`, `workflow_id`, `component` threaded as explicit keyword arguments through all `generate()` calls. No `contextvars`.
- [x] **C-05** — Retry is primitive-level only (`retry_on_rate_limit`). Components don't retry themselves — that is the Orchestrator's job.

### Planner

- [x] **C-06** — Planner outputs a DAG. Tasks declare `depends_on: [task_id]`. DAG from day one.
- [x] **C-07** — Plan DAG parse failure: max 3 retry attempts with failure reason fed back, then run aborts.
- [x] **C-08** — Two-phase planning: Phase 1 — Qwen exploration loop writes per-module summary docs to `runs/<run_id>/exploration/`. Phase 2 — Opus Planner reads those docs + has direct tool access (`read_file`, `grep`, `list_dir`, `git_log`) for targeted lookups. Second run on same repo can skip Phase 1 if exploration docs exist.
- [x] **C-09** — Plan size limit: configurable `max_tasks` in Planner config, default 50.

### Orchestrator

- [x] **C-10** — DAG topological sort via `networkx`. Do not implement by hand.
- [x] **C-11** — Per-provider semaphore for concurrency control. Fanout max concurrency 5, hard cap 8.
- [x] **C-12** — Partial failure: one auto-mitigation attempt (Orchestrator retries with validator failure reason as context). Second failure = full hard stop. All queued and in-flight tasks cancelled. Completed tasks preserved in run log.
- [x] **C-13** — Checkpoint/resume from Milestone 1. Task states (`pending`, `running`, `completed`, `failed`) written to SQLite after every state transition. `aiw resume <run_id>` skips completed tasks, re-queues `running` tasks.
- [ ] **C-14** — Task result passing in DAG: how downstream tasks receive outputs from dependencies. Named output references in plan schema. Decide at Milestone 4 implementation.

### Worker

- [x] **C-15** — Prompt template rendering: simple `{{variable}}` substitution only. No Jinja2. Logic stays in Python, not in templates.
- [ ] **C-16** — Worker output parsing: Worker parses LLM text into the declared output Pydantic model. Decide responsibility clearly at Milestone 2 implementation.
- [x] **C-17** — Worker `max_turns`: Sonnet gets multi-turn soft cap of 15 (configurable up to 20 in workflow YAML). Haiku, Qwen, Gemini Flash are single-call (`max_turns=1`, not configurable). At soft cap, Worker returns state flagged `incomplete`. Orchestrator decides: re-trigger with context, or spawn mini-Planner to decompose.

### Validator

- [x] **C-18** — Validator supports two types from day one: `structural` (shell command, exit 0) and `semantic` (Haiku LLM check against criteria). Actual implementations built on demand per workflow.
- [x] **C-19** — Validator failure reason is returned as structured output and fed back as context for the Orchestrator's mitigation attempt.

### Escalator

- [x] **C-20** — Fixed escalation order: `local_coder → haiku → sonnet → opus`. Configurable override per workflow in YAML.
- [x] **C-21** — Escalation retries tagged separately in run log so cost of escalation is visible in isolation.

### AgentLoop

- [x] **C-22** — Termination: all three conditions — no tool calls in response AND explicit `done` tool call AND `max_iterations` hard cap (whichever comes first).
- [x] **C-23** — `max_iterations` default 20, configurable per component.
- [ ] **C-24** — Context compaction for long AgentLoop runs: summarize history when context approaches limit. Implement when AgentLoop is built in Milestone 4.
- [x] **C-25** — AgentLoop stays in Layer 2 with weaker documented guarantee ("best-effort determinism"). Orchestrator mandates a Validator gate after every AgentLoop step. Failures produce a structured `AgentLoopFailure` artifact in the run log.

### Fanout

- [x] **C-26** — Max concurrency 5, hard cap 8. Total queue unlimited — processed in waves.
- [x] **C-27** — Input order preserved in results.
- [x] **C-28** — Individual item failures are isolated. Others continue unless hard-stop triggered (C-12).

### Synthesizer

- [x] **C-29** — Large input sets: hierarchical synthesis — batch inputs, synthesize batches, synthesize summaries.

### HumanGate

- [x] **C-30** — Raw JSON to structured log file in `runs/<run_id>/`. Terminal renders pretty-printed plan with task summaries and dependency tree.
- [x] **C-31** — Configurable timeout, default 30 min. On expiry: hard stop, last gate state written to SQLite as `timed_out`. `aiw resume <run_id>` re-renders the gate.
- [x] **C-32** — Resume via SQLite checkpoint. Gate state is `pending_review` until resolved.
- [x] **C-33** — Approve / reject / edit-then-approve. Plan always requires review before execution. Dependencies get a separate mandatory review step. `strict_review: true` in workflow YAML blocks `--skip-gate` flag — for government or regulated workflows.

---

## Workflows (Layer 3)

- [x] **W-01** — YAML loader: `pyyaml` + Pydantic validation.
- [x] **W-02** — `flow:` defines top-level sequence; `after:`/`before:` define within-component dependencies. DAG merge at load time.
- [x] **W-03** — `workflow.yaml` snapshotted into `runs/<run_id>/` at run start for reproducibility.
- [ ] **W-04** — `run.py` entry point: CLI arg parsing only. No workflow-specific pre/post processing in `run.py`. Decide at Milestone 3.
- [ ] **W-05** — Cross-workflow data sharing: `jvm_modernization` composes `test_coverage_gap_fill` and `slice_refactor`. Sub-workflows vs. component config import. Decide at Milestone 6.

---

## CLI (`aiw`)

- [x] **CL-01** — CLI framework: `typer`.
- [x] **CL-02** — Run output: structured progress lines (component + task + status). Not a progress bar.
- [ ] **CL-03** — `aiw cost` command: define interface before building storage. Query by run_id, workflow, date range.
- [x] **CL-04** — `aiw resume <run_id>`: built at Milestone 1 alongside checkpoint storage.
- [x] **CL-05** — `aiw list-runs` / `aiw inspect <run_id>`: Milestone 1 — needed to verify cost tracking works.

---

## Repo / Tooling

- [x] **R-01** — Import linter: `import-linter` PyPI package, configured in `pyproject.toml`.
- [x] **R-02** — Build backend: `hatchling`.
- [x] **R-03** — Python 3.13 target. `requires-python = ">=3.12"` in `pyproject.toml` to accommodate local 3.12 env.
- [x] **R-04** — `uv` for dependency management. Confirmed.
- [x] **R-05** — `pytest-asyncio` with `asyncio_mode = "auto"` in `pyproject.toml`.
- [x] **R-06** — CI check: no secrets in `tiers.yaml` or `pricing.yaml`.
- [x] **R-07** — `.gitignore`: `~/.ai-workflows/`, `runs/`, `.env`, `__pycache__`, `.venv`. Logs local-only.
- [ ] **R-08** — Workflow-specific `custom_tools.py` auto-discovered at workflow load time via explicit import in `workflow.yaml`.

---

## Cross-Cutting / Architecture

- [ ] **X-01** — AgentLoop vs Worker distinction: Worker runs a bounded task (single-call or soft-cap multi-turn). AgentLoop runs open-ended investigation until a termination condition. Document the line clearly in `docs/writing-a-component.md`.
- [x] **X-02** — Explicit param threading: `run_id`, `workflow_id`, `component` as required keyword args on `generate()`. No `contextvars`.
- [ ] **X-03** — Cancellation on SIGINT: `asyncio.CancelledError` propagation strategy for in-flight LLM calls and fan-out tasks. Implement at Milestone 4 when orchestration is built.
- [-] **X-04** — OpenTelemetry: not required for MVP. Hook points designed in at primitive layer but not wired.
- [ ] **X-05** — `py.typed` marker: add if package is published. Defer until packaging decision.
- [ ] **X-06** — CI pipeline: GitHub Actions. Runs: `import-linter`, `pytest`, `ruff`. Define at Milestone 1 project scaffolding.
- [x] **X-07** — Prompt injection: tool outputs wrapped as `tool_result` `ContentBlock` entries (data, not instructions). Sanitizer at `primitives/tools/sanitizer.py` strips injection patterns before tool results enter message history.
- [-] **X-08** — Multi-machine distributed runs: current design is single-machine. Orchestrator on work laptop, Ollama on home desktop via `base_url`. True distributed execution deferred.
- [ ] **X-09** — Windows/WSL: document as "untested, WSL recommended" in README. Not a priority.
- [ ] **X-10** — Pydantic v2: pin to v2 from day one in `pyproject.toml`. Note in constraints.

---

## Open Questions (from design doc)

- [x] **OQ-01** — Plan schema strictness: strict Pydantic + bounded retry loop (max 3) on parse failure. See C-07.
- [x] **OQ-02** — `HumanGate` render: CLI-first pretty-printed; web UI additive later. See C-30.
- [x] **OQ-03** — Long-running workflow blocking: checkpoint/resume from Milestone 1. See C-13.
- [-] **OQ-04** — Workflow packaging as plugins: deferred. Subdirectories only for now.
- [x] **OQ-05** — Workflow output versioning: timestamped run directories. See P-30.
- [ ] **OQ-06** — Windows support: document as "untested, WSL recommended". See X-09.

---

## Post-MVP

- [ ] **PM-01** — MCP server: thin read interface over SQLite storage for querying run history, costs, task states from Claude clients. Additive post-Milestone 2. No primitives changes required.
- [ ] **PM-02** — Streaming via `stream_generate()`: additive method on adapters, used only by `HumanGate` display layer. See P-03.
- [ ] **PM-03** — `aiw cost` dashboard/command for cost aggregation queries. See CL-03.
- [ ] **PM-04** — Qwen2.5-Coder:14b benchmark vs :32b on exploration reads. 14b may be fast enough and fits in RAM with more headroom.

---

*Last updated: 2026-04-17. Add new issues at the bottom of the relevant section with the next available ID.*
