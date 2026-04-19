# Milestone 1 — Primitives (Pydantic AI Substrate)

## Goal

Build the foundation on top of `pydantic-ai`. We don't reimplement what they've already solved (Agent, Model abstraction, tool schema generation, RunContext). We wrap their models with our tier routing, cost tracking, budget caps, and workflow-aware storage. Our layer stays clean; their layer does the hard work.

**Exit criteria:** you can make an LLM call from a Python REPL through our tier system. It gets logged to SQLite with cost, budget cap protects you from runaway spend, retried on rate limits, and the run is visible in `aiw list-runs`. Prompt caching is verified (`cache_read_input_tokens > 0` on turn 2+).

## Scope Changes from Original M1

- **Adopted `pydantic-ai`** as substrate. `Agent[Deps, Output]`, `Model` subclasses, `@agent.tool`, `RunContext[Deps]`, and `ModelRetry` come from there. We build a Model factory around `OpenAIChatModel` (Gemini via openai-compat, Ollama) and `GoogleModel`. The `AnthropicModel` provider is implemented in code for third-party use but is not exercised in this deployment (no Anthropic API key — developer uses Claude Max subscription and Claude Code CLI for orchestration).
- **Claude Code CLI tiers.** `opus`, `sonnet`, `haiku` run via `claude` CLI (Max subscription, no API key). `local_coder` (Qwen/Ollama) is free and local. `gemini_flash` (Gemini API) is the last-resort overflow tier only. `claude_code` provider impl lands in M4 with the Orchestrator.
- **Budget cap upgraded from deferred to critical.** You're paying out of pocket. `max_run_cost_usd` is in from day one.
- **Sanitizer deleted/rebranded.** ContentBlock `tool_result` wrapping stays as the real defense. Regex sanitizer was theater — rebranded to `forensic_logger` for post-hoc analysis only.
- **Multi-breakpoint caching**, not single-last-block.
- **`max_retries=0` on every underlying SDK client** — our retry utility is the single authority.
- **Retry taxonomy** — retryable-transient, retryable-semantic (via `ModelRetry`), non-retryable.
- **`ClientCapabilities` descriptor** on every adapter — components never `isinstance()` check.
- **`ContentBlock` discriminated union** with `Field(discriminator='type')`.
- **`yoyo-migrations` for SQLite** instead of manual SQL.
- **Workflow directory content hash** stored in `runs` table for resume version safety.
- **Linear `Pipeline` planned for M2-M3** instead of DAG `Orchestrator` in M4.

## Key Decisions In Effect

| Decision | Value |
| --- | --- |
| Python floor | 3.12 (`requires-python = ">=3.12"`) |
| Build backend | `hatchling` |
| Dependency manager | `uv` |
| Substrate | `pydantic-ai` |
| Test framework | `pytest` + `pytest-asyncio` |
| Import linter | `import-linter` (3-layer enforcement) |
| CLI framework | `typer` |
| Logging | `structlog` + `logfire` (OTel wired in M3) |
| Migrations | `yoyo-migrations` |
| Storage | SQLite + WAL mode at `~/.ai-workflows/runs.db` |
| Run artifacts | `~/.ai-workflows/runs/<run_id>/` |
| Workflow dir snapshot | Full directory + content hash in SQLite |
| Auth | Env vars only |
| SDK retries | `max_retries=0` on every wrapped SDK client |
| Our retry | `retry_on_rate_limit()` — transient; `ModelRetry` — semantic |
| Context tagging | Explicit kwargs (via `RunContext[Deps]` from pydantic-ai) |
| Prompt injection | `tool_result` `ContentBlock` wrapping (real defense); `forensic_logger` (logging only) |
| Budget cap | `max_run_cost_usd` in workflow config, enforced by `CostTracker` |
| Ollama cost | `0.0`, excluded from aggregations |
| Streaming | Deferred |
| Prompt caching | Helpers built (Task 04); Anthropic API only. Not active — Claude tiers run via CLI, not API. |
| **5 tiers** | **`opus`/`sonnet`/`haiku` → Claude Code CLI (Max sub) · `local_coder` → Qwen/Ollama · `gemini_flash` → Gemini API (last resort)** |

## Task Order

1. `task_01_project_scaffolding.md` — ✅ **Complete** (2026-04-18)
2. `task_02_shared_types.md` — ContentBlock discriminated union + ClientCapabilities — ✅ **Complete** (2026-04-18)
3. `task_03_model_factory.md` — tier name → pydantic-ai Model instance — ✅ **Complete** (2026-04-18)
4. `task_04_prompt_caching.md` — multi-breakpoint Anthropic cache strategy — ✅ **Complete** (2026-04-18)
5. `task_05_tool_registry.md` — injected registry + `forensic_logger` — ✅ **Complete** (2026-04-18)
6. `task_06_stdlib_tools.md` — fs + shell + http + git
7. `task_07_tiers_loader.md` — tiers.yaml + pricing.yaml + profile + dir-hash utility
8. `task_08_storage.md` — SQLite + yoyo-migrations + workflow_dir_hash
9. `task_09_cost_tracker.md` — tagging + budget cap enforcement
10. `task_10_retry.md` — retry taxonomy
11. `task_11_logging.md` — structlog + logfire configuration
12. `task_12_cli_primitives.md` — aiw list-runs / inspect / resume (stub) / run (stub)
