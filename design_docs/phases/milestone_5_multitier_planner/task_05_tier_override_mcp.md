# Task 05 — Tier-Override MCP Plumbing

**Status:** 📝 Planned.

## What to Build

Add a `tier_overrides: dict[str, str] | None` field to [`RunWorkflowInput`](../../../ai_workflows/mcp/schemas.py) and thread it through the MCP `run_workflow` tool into the shared [`workflows._dispatch.run_workflow`](../../../ai_workflows/workflows/_dispatch.py) (which [T04](task_04_tier_override_cli.md) extended). Behaviour parity with the CLI `--tier-override` path: same validation, same `UnknownTierError` translated to `ToolError` at the MCP boundary.

This is the task [architecture.md §4.4 line 99](../../architecture.md) defers `tier_overrides` onto: *"the `tier_overrides` argument lands at M5 T05 when the graph layer begins consuming it; shipping it earlier would be a dead field with no test coverage."* M4 shipped `RunWorkflowInput` without it on purpose; T05 closes that deferred field.

Aligns with KDR-002 (MCP portable surface) + KDR-008 (FastMCP schema-first) + architecture.md §4.4.

## Deliverables

### `ai_workflows/mcp/schemas.py` — extend `RunWorkflowInput`

```python
class RunWorkflowInput(BaseModel):
    workflow_id: str
    inputs: dict[str, Any]
    budget_cap_usd: float | None = None
    run_id: str | None = None
    tier_overrides: dict[str, str] | None = Field(
        default=None,
        description=(
            "Optional `{logical: replacement}` map to swap tiers at invoke time. "
            "Both names must already exist in the workflow's tier registry."
        ),
    )
```

Field is `None`-defaulted so the JSON-RPC payload stays backward-compatible with M4-era callers. Docstring-level guidance on the accepted shape is the only schema change — no bounds on keys/values (per [ADR-0002](../../adr/0002_bare_typed_response_format_schemas.md), though MCP I/O is explicitly out of scope; the decision here is pragmatic, not constrained).

### `ai_workflows/mcp/server.py` — forward to `_dispatch`

Update the `run_workflow` tool body to pass `payload.tier_overrides` through to `_dispatch.run_workflow(...)`. Translate the new `UnknownTierError` (raised from T04's dispatch extension) to `ToolError` with the same shape the T02 `UnknownWorkflowError` translator uses — one branch in the existing error-translation path.

### Tests

`tests/mcp/test_tier_override.py` (new):

- MCP `run_workflow` with `tier_overrides={"planner-synth": "planner-explorer"}` runs to the gate; stub adapter recorded tier/model pair matches the replacement route.
- Backward compat: payload without `tier_overrides` (absent key) behaves byte-identically to the M4 path.
- `tier_overrides={}` (empty dict, not None) is a no-op (same behaviour as absent).
- Unknown logical tier → `ToolError` with the tier name in the message.
- Unknown replacement tier → `ToolError` with the tier name in the message.
- `RunWorkflowInput` schema round-trip (`.model_dump()` → `.model_validate()`) preserves `tier_overrides` shape.

Add one assertion to the existing hermetic [`tests/mcp/test_server_smoke.py`](../../../tests/mcp/test_server_smoke.py) smoke test: a second `run_workflow` call with `tier_overrides` exercises the field once in the always-run smoke (small enough to fit without a separate test file).

## Acceptance Criteria

- [ ] `RunWorkflowInput.tier_overrides: dict[str, str] | None` field with a clear description; `None`-default preserves M4 backward compatibility.
- [ ] MCP `run_workflow` forwards `tier_overrides` to `_dispatch.run_workflow`; `UnknownTierError` surfaces as `ToolError`.
- [ ] Hermetic MCP tests cover: override applied, no override, empty-dict override, unknown logical, unknown replacement.
- [ ] `tests/mcp/test_server_smoke.py` gains one call with `tier_overrides` (still hermetic, still always-run).
- [ ] `uv run pytest` green — includes the smoke.
- [ ] `uv run lint-imports` 3 / 3 kept.
- [ ] `uv run ruff check` clean.

## Dependencies

- [Task 04](task_04_tier_override_cli.md) — `_dispatch.run_workflow` already accepts `tier_overrides` and raises `UnknownTierError`. T05 is the MCP-side plumbing only.
