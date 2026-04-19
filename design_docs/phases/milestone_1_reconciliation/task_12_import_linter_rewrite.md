# Task 12 — Import-Linter Contract Rewrite

**Status:** 📝 Planned.

## What to Build

Replace the existing `primitives`-vs-`components`-vs-`workflows` contracts in `pyproject.toml` with the four-layer contract from [architecture.md §3](../../architecture.md): `primitives → graph → workflows → surfaces`. Delete the (empty) `ai_workflows/components/` package. Create empty `ai_workflows/graph/` and `ai_workflows/workflows/` packages so the contract loads.

## Deliverables

### Package changes

- Delete `ai_workflows/components/` (empty per the pre-pivot archive).
- Create `ai_workflows/graph/__init__.py` — one-line docstring: `"""LangGraph adapters over primitives. Populated in M2."""`.
- Ensure `ai_workflows/workflows/__init__.py` exists with: `"""Concrete LangGraph StateGraphs. Populated from M3 onward."""`.
- Create `ai_workflows/mcp/__init__.py` — `"""MCP surface (FastMCP). Populated in M4."""` — and keep `ai_workflows/cli.py` in place. The "surfaces" layer means the two modules `ai_workflows.cli` and `ai_workflows.mcp`.

### `pyproject.toml` — replace existing `[tool.importlinter.contracts]` block with

```toml
[tool.importlinter]
root_package = "ai_workflows"

[[tool.importlinter.contracts]]
name = "primitives cannot import graph, workflows, or surfaces"
type = "forbidden"
source_modules = ["ai_workflows.primitives"]
forbidden_modules = [
    "ai_workflows.graph",
    "ai_workflows.workflows",
    "ai_workflows.cli",
    "ai_workflows.mcp",
]

[[tool.importlinter.contracts]]
name = "graph cannot import workflows or surfaces"
type = "forbidden"
source_modules = ["ai_workflows.graph"]
forbidden_modules = [
    "ai_workflows.workflows",
    "ai_workflows.cli",
    "ai_workflows.mcp",
]

[[tool.importlinter.contracts]]
name = "workflows cannot import surfaces"
type = "forbidden"
source_modules = ["ai_workflows.workflows"]
forbidden_modules = ["ai_workflows.cli", "ai_workflows.mcp"]
```

### Remove

Any trailing references to `ai_workflows.components` in `pyproject.toml` or anywhere else.

## Acceptance Criteria

- [ ] `ai_workflows/components/` no longer exists.
- [ ] `ai_workflows/graph/`, `ai_workflows/workflows/`, `ai_workflows/mcp/` exist with package docstrings only.
- [ ] `uv run lint-imports` succeeds and reports three contracts passing.
- [ ] `grep -r "ai_workflows.components" . --include="*.py" --include="*.toml"` returns zero matches.
- [ ] `uv run pytest` green.

## Dependencies

- [Task 03](task_03_remove_llm_substrate.md) — [Task 11](task_11_cli_stub_down.md). Run this after the layer contents are settled, otherwise the linter flags transient boundary violations.
