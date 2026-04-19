# Task 04 — Remove Tool Registry + Stdlib Tools

**Status:** 📝 Planned.

## What to Build

Delete `ai_workflows/primitives/tools/` entirely. Rationale: under [architecture.md](../../architecture.md), LangGraph nodes are plain Python — the pydantic-ai agent-style tool registry and `forensic_logger` no longer have a consumer. If any stdlib helper (`fs`, `git`, `http`, `shell`) is genuinely reusable, [task 01](task_01_reconciliation_audit.md) flags it for keeping and this task moves it to a non-`tools` location.

## Deliverables

### Delete

- `ai_workflows/primitives/tools/registry.py`
- `ai_workflows/primitives/tools/forensic_logger.py`
- `ai_workflows/primitives/tools/stdlib.py`
- `ai_workflows/primitives/tools/fs.py` *(unless audit marks KEEP)*
- `ai_workflows/primitives/tools/git.py` *(unless audit marks KEEP)*
- `ai_workflows/primitives/tools/http.py` *(unless audit marks KEEP)*
- `ai_workflows/primitives/tools/shell.py` *(unless audit marks KEEP)*
- `ai_workflows/primitives/tools/__init__.py`
- Matching tests under `tests/primitives/tools/`

### If audit keeps any stdlib helper

Move it out of `primitives/tools/` into a flat `primitives/` module (e.g. `primitives/shell_utils.py`) with only the functions still used. The `tools/` package itself is deleted regardless.

## Acceptance Criteria

- [ ] `ai_workflows/primitives/tools/` directory no longer exists.
- [ ] `grep -r "forensic_logger\|ToolRegistry\|from ai_workflows.primitives.tools" ai_workflows/ tests/` returns zero matches.
- [ ] Any kept helper is tested in its new location.
- [ ] `uv run pytest` green.
- [ ] `uv run ruff check` green.

## Dependencies

- [Task 02](task_02_dependency_swap.md) — pydantic-ai out of `pyproject.toml`.
