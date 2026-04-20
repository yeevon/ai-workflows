# Task 01 — FastMCP Scaffold + Pydantic I/O Models

**Status:** 📝 Planned.

## What to Build

Populate the currently-empty [`ai_workflows/mcp/`](../../../ai_workflows/mcp/__init__.py) package with a FastMCP `Server` factory plus the pydantic I/O models for every M4 tool. Ships the surface shape only — tool bodies are stubs that raise `NotImplementedError`. The four tools' real implementations land in [tasks 02–05](README.md).

Aligns with [architecture.md §4.4](../../architecture.md) (MCP server surface), [§7](../../architecture.md) (pydantic-typed tool contracts), KDR-002, KDR-008.

## Deliverables

### `ai_workflows/mcp/schemas.py` — pydantic I/O models

One module with the public I/O contract for every tool. Schema-first: FastMCP auto-derives the JSON-RPC tool schemas from these types.

```python
class RunWorkflowInput(BaseModel):
    workflow_id: str
    inputs: dict[str, Any]
    budget_cap_usd: float | None = None
    run_id: str | None = None

class RunWorkflowOutput(BaseModel):
    run_id: str
    status: Literal["pending", "completed", "errored"]
    awaiting: Literal["gate"] | None = None
    plan: dict[str, Any] | None = None
    total_cost_usd: float | None = None

class ResumeRunInput(BaseModel):
    run_id: str
    gate_response: Literal["approved", "rejected"] = "approved"

class ResumeRunOutput(BaseModel):
    run_id: str
    status: Literal["pending", "completed", "gate_rejected", "errored"]
    plan: dict[str, Any] | None = None
    total_cost_usd: float | None = None

class RunSummary(BaseModel):
    run_id: str
    workflow_id: str
    status: str
    started_at: str
    finished_at: str | None
    total_cost_usd: float | None  # single cost surface the MCP server exposes

class ListRunsInput(BaseModel):
    workflow: str | None = None
    status: str | None = None
    limit: int = 20

class CancelRunInput(BaseModel):
    run_id: str

class CancelRunOutput(BaseModel):
    run_id: str
    status: Literal["cancelled", "already_terminal"]
```

Per [KDR-010 / ADR-0002](../../adr/0002_bare_typed_response_format_schemas.md): MCP tool I/O models are explicitly **out of scope** — bound fields (`Field(min_length=...)` etc.) are *permitted* here because these schemas never cross into `response_format`. Apply bounds where they genuinely add contract-at-boundary value (e.g. `ListRunsInput.limit: int = Field(20, ge=1, le=500)`), skip them where noise outweighs signal.

### `ai_workflows/mcp/server.py` — FastMCP factory

```python
from fastmcp import FastMCP

def build_server() -> FastMCP:
    """Construct and return a FastMCP server with all four tools registered.

    Factory returns a fresh server per call so tests can drive the surface
    in-process without global state (mirrors the ``aiw`` Typer app pattern).
    """
    mcp = FastMCP("ai-workflows")

    @mcp.tool()
    async def run_workflow(payload: RunWorkflowInput) -> RunWorkflowOutput:
        raise NotImplementedError("lands in M4 T02")

    @mcp.tool()
    async def resume_run(payload: ResumeRunInput) -> ResumeRunOutput:
        raise NotImplementedError("lands in M4 T03")

    @mcp.tool()
    async def list_runs(payload: ListRunsInput) -> list[RunSummary]:
        raise NotImplementedError("lands in M4 T04")

    @mcp.tool()
    async def cancel_run(payload: CancelRunInput) -> CancelRunOutput:
        raise NotImplementedError("lands in M4 T05")

    return mcp
```

### `ai_workflows/mcp/__init__.py`

Expand the current docstring-only module to export `build_server`. Keep the layer-boundary docstring intact (mcp is a surface; nothing imports it).

### Tests

`tests/mcp/test_scaffold.py`:

- `build_server()` returns a `FastMCP` instance; calling it twice returns **distinct** instances (no shared global).
- The server reports all four expected tools registered (`run_workflow`, `resume_run`, `list_runs`, `cancel_run`) via FastMCP's tool-listing API.
- Each tool's in-process dispatcher raises `NotImplementedError` (pins the "scaffold-only" property until later tasks wire bodies).
- Every schema module re-exports: round-trip `.model_dump()` → `.model_validate()` for each model.
- `ai_workflows.mcp` imports cleanly without pulling anything above the surfaces layer (regression guard — `import ai_workflows.mcp` must not import `langgraph` transitively unless via `ai_workflows.workflows` / `ai_workflows.graph`, which is the allowed path).

## Acceptance Criteria

- [ ] `ai_workflows/mcp/{server.py,schemas.py,__init__.py}` land; `build_server() -> FastMCP` is the sole public constructor.
- [ ] All four tools are `@mcp.tool()`-registered with pydantic `*Input` / `*Output` signatures; FastMCP auto-derives schemas.
- [ ] Tool bodies raise `NotImplementedError` with a "lands in M4 T0X" message.
- [ ] `build_server()` is idempotent on distinct calls (no global mutation).
- [ ] `RunSummary` includes `total_cost_usd` as the single cost surface (per M4 Goal — `get_cost_report` tool is not shipped).
- [ ] `uv run pytest tests/mcp/test_scaffold.py` green.
- [ ] `uv run lint-imports` 3 / 3 kept.
- [ ] `uv run ruff check` clean.

## Dependencies

- `fastmcp>=0.2` — already in [pyproject.toml](../../../pyproject.toml).
- [architecture.md §4.4](../../architecture.md) — tool list.
- [ADR-0002 / KDR-010](../../adr/0002_bare_typed_response_format_schemas.md) — MCP I/O models are out-of-scope for the bare-typed rule.
