# Milestone 1 — Primitives

## Goal

Build the foundation every layer above depends on. No business logic. No components. No workflows. Just plumbing — stable, boring, well-tested.

**Exit criteria:** You can make an LLM call from a Python REPL, it gets logged with cost, retried on 429, and the run is visible in `aiw list-runs`.

## Scope

- Project scaffolding (pyproject.toml, import-linter, pytest, CI skeleton)
- Shared types: `Message`, `ContentBlock`, `Response`, `TokenUsage`, `ToolSpec`
- LLM client adapters: Anthropic, Ollama, OpenAI-compat
- Tool sanitizer (prompt injection protection)
- Tool registry (injected, per-run)
- Stdlib tools: filesystem, shell, HTTP, git
- Tiers loader (`tiers.yaml` + `pricing.yaml`)
- Storage layer (SQLite + WAL, run log, checkpoint states)
- Cost tracker
- `retry_on_rate_limit()` utility
- `structlog` setup
- Basic CLI: `aiw list-runs`, `aiw inspect`, `aiw resume` (stub), `aiw run` (stub)

## Key Decisions In Effect

| Decision | Value |
|---|---|
| Python floor | 3.12 (`requires-python = ">=3.12"`) |
| Build backend | `hatchling` |
| Dependency manager | `uv` |
| Test framework | `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`) |
| Import linter | `import-linter` configured in `pyproject.toml` |
| CLI framework | `typer` |
| Logging | `structlog` |
| Storage | SQLite + WAL mode at `~/.ai-workflows/runs.db` |
| Run artifacts | `~/.ai-workflows/runs/<run_id>/` |
| Auth | Env vars only (no secrets in YAML) |
| Retry | `retry_on_rate_limit()` utility, 429/529 only, max 3, exponential backoff + jitter |
| Context tagging | Explicit `run_id`, `workflow_id`, `component` kwargs on every `generate()` call |
| Prompt injection | Sanitizer in `primitives/tools/sanitizer.py` wraps all tool outputs |
| Ollama cost | Record `0.0`, excluded from aggregations |
| Streaming | Deferred — `generate()` always returns complete `Response` |

## Task Order

Tasks within this milestone should be completed in this order — each task builds on the previous:

1. `task_01_project_scaffolding.md`
2. `task_02_shared_types.md`
3. `task_03_anthropic_client.md`
4. `task_04_ollama_client.md`
5. `task_05_openai_compat_client.md`
6. `task_06_tool_sanitizer.md`
7. `task_07_tool_registry.md`
8. `task_08_stdlib_tools_fs.md`
9. `task_09_stdlib_tools_shell.md`
10. `task_10_stdlib_tools_http_git.md`
11. `task_11_tiers_loader.md`
12. `task_12_storage.md`
13. `task_13_cost_tracker.md`
14. `task_14_retry.md`
15. `task_15_logging.md`
16. `task_16_cli_primitives.md`
