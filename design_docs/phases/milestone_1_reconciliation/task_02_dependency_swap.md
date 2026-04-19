# Task 02 — Dependency Swap

**Status:** 📝 Planned.

## What to Build

Replace the pydantic-ai-era runtime dependencies in `pyproject.toml` with the LangGraph + MCP + LiteLLM substrate declared in [architecture.md §6](../../architecture.md). Refresh `uv.lock` so `uv sync` completes clean.

## Deliverables

### `pyproject.toml`

**Remove** (verify each against the [task 01 audit](task_01_reconciliation_audit.md) first):

- `pydantic-ai`
- `pydantic-graph`
- `pydantic-evals`
- `anthropic`
- `logfire` (if audit classes it as REMOVE)
- `[project.optional-dependencies].dag` (`networkx`) — LangGraph replaces it.

**Add** to `[project].dependencies`:

- `langgraph>=0.2`
- `langgraph-checkpoint-sqlite>=1.0`
- `litellm>=1.40`
- `fastmcp>=0.2`

**Keep:** `pydantic`, `pyyaml`, `structlog`, `typer`, `yoyo-migrations`, `httpx` (transitive for LiteLLM), and the existing `dev` group.

Update the `description` field to drop the pydantic-ai reference: `"Composable AI workflow framework built on LangGraph + MCP."`

### `uv.lock`

Regenerated via `uv lock`. Commit alongside `pyproject.toml`.

## Acceptance Criteria

- [ ] `uv sync` completes without error on a fresh clone.
- [ ] `grep -r pydantic_ai ai_workflows/` returns nothing after [task 03](task_03_remove_llm_substrate.md) — flagged as a follow-on check, not this task's gate.
- [ ] No dependency marked REMOVE in the audit remains in `pyproject.toml`.
- [ ] Every dependency marked ADD in the audit is present with a pinned lower bound.
- [ ] `project.description` no longer mentions pydantic-ai.
- [ ] CHANGELOG.md notes the dependency swap under `[Unreleased]`.

## Dependencies

- [Task 01](task_01_reconciliation_audit.md) — audit must tag every dep first.
