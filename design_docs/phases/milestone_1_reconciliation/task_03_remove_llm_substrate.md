# Task 03 — Remove pydantic-ai LLM Substrate

**Status:** 📝 Planned.

## What to Build

Delete the pydantic-ai-coupled LLM layer under `ai_workflows/primitives/llm/`. Leave the package as a minimal empty shell that [M2](../../roadmap.md) can fill with the LiteLLM adapter.

## Deliverables

### Delete

- `ai_workflows/primitives/llm/model_factory.py` (pydantic-ai `Model` factory)
- `ai_workflows/primitives/llm/caching.py` (multi-breakpoint Anthropic cache — never active per KDR-003)
- `ai_workflows/primitives/llm/types.py` (`ContentBlock`, `ClientCapabilities` — pydantic-ai-era types)
- Matching tests under `tests/primitives/llm/`

### Keep (minimal stub)

`ai_workflows/primitives/llm/__init__.py` — left as an empty package module with a one-line docstring:

```python
"""LLM adapters. Populated in M2 with the LiteLLM adapter and the Claude Code subprocess driver."""
```

### Update downstream importers

Any remaining `from ai_workflows.primitives.llm import ...` outside the package — expected locations per [task 01 audit](task_01_reconciliation_audit.md):

- `ai_workflows/cli.py` (handled in [task 11](task_11_cli_stub_down.md))
- Tests that will themselves be deleted under this task

## Acceptance Criteria

- [ ] `grep -r "from pydantic_ai" ai_workflows/ tests/` returns zero matches.
- [ ] `grep -r "ContentBlock\|ClientCapabilities\|model_factory\|prompt_caching" ai_workflows/ tests/` returns zero matches.
- [ ] `ai_workflows/primitives/llm/` contains only `__init__.py`.
- [ ] `uv run pytest` green (failing tests removed alongside their modules).
- [ ] `uv run ruff check` green.

## Dependencies

- [Task 02](task_02_dependency_swap.md) — pydantic-ai must be gone from `pyproject.toml` before its imports are removed, otherwise `uv sync` keeps it alive.
