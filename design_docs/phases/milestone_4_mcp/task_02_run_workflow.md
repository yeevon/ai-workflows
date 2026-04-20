# Task 02 — `run_workflow` Tool

**Status:** 📝 Planned.

## What to Build

Wire the `run_workflow` tool body so a client calling the MCP server kicks off a workflow exactly the way `aiw run <workflow>` does. Returns immediately when the graph yields at a `HumanGate` interrupt or completes. Mirrors [ai_workflows/cli.py:191-240](../../../ai_workflows/cli.py) `_run_async` — the reuse goal is one dispatch path shared by both surfaces.

Aligns with [architecture.md §4.4](../../architecture.md) (`run_workflow` signature), §5 (runtime data flow steps 1–6), KDR-008, KDR-009.

**Out of scope:** `tier_overrides`. Lands at [M5 T05](../milestone_5_multitier_planner/README.md) when the graph layer begins consuming it; shipping it here would be a dead field.

## Deliverables

### `ai_workflows/mcp/dispatch.py` — shared dispatch helper

The CLI already owns `_run_async` / `_resume_async` in [ai_workflows/cli.py](../../../ai_workflows/cli.py). Before writing the MCP tool body, extract the reusable core into `ai_workflows/mcp/dispatch.py` (or `ai_workflows/workflows/_dispatch.py` if keeping it inside the workflows layer is cleaner — **decide at task start**; import-linter allows either). The extracted function:

```python
async def run_workflow(
    *,
    workflow: str,
    inputs: dict[str, Any],
    budget_cap_usd: float | None,
    run_id: str | None,
) -> dict[str, Any]:
    """Dispatch a workflow run. Returns a dict shaped like RunWorkflowOutput.

    Shared by the ``aiw run`` CLI command and the ``run_workflow`` MCP tool.
    """
```

Update `ai_workflows/cli.py` `_run_async` to call this helper so the two surfaces stay in lockstep. No behaviour change on the CLI side — AC-6 below pins that via regression test.

### `ai_workflows/mcp/server.py` — `run_workflow` tool body

```python
@mcp.tool()
async def run_workflow(payload: RunWorkflowInput) -> RunWorkflowOutput:
    """Execute a workflow end-to-end. Pauses at HumanGate interrupts."""
    result = await dispatch.run_workflow(
        workflow=payload.workflow_id,
        inputs=payload.inputs,
        budget_cap_usd=payload.budget_cap_usd,
        run_id=payload.run_id,
    )
    return RunWorkflowOutput(**result)
```

### Tests

`tests/mcp/test_run_workflow.py`:

- Drive the tool in-process against a **stubbed tier registry** (no live API); reuse the `_redirect_default_paths` pattern from [tests/cli/test_run.py](../../../tests/cli/test_run.py) to steer `AIW_STORAGE_DB` / `AIW_CHECKPOINT_DB` under `tmp_path`.
- `run_workflow` returns `{run_id, status: "pending", awaiting: "gate"}` when the graph yields at the planner's `HumanGate`.
- `Storage.create_run(run_id, "planner", budget)` called exactly once per dispatch (asserted by reading `Storage.get_run` after).
- Budget cap trips `BudgetExceeded` → output has `status: "errored"` (or whatever the shared dispatch maps it to — pin the contract in T02, not improvise at call site).
- Unknown workflow name raises a tool error that FastMCP surfaces as a JSON-RPC error response (not an uncaught Python exception).
- Regression: `tests/cli/test_run.py` still green after the `_run_async` refactor to route through the shared helper.

## Acceptance Criteria

- [ ] `run_workflow(RunWorkflowInput)` returns `RunWorkflowOutput` with `{run_id, status, awaiting?, plan?, total_cost_usd?}`.
- [ ] On `HumanGate` interrupt: `status="pending"`, `awaiting="gate"`, `plan=None`, `total_cost_usd` set.
- [ ] On completion without gate: `status="completed"`, `plan` populated, `total_cost_usd` set.
- [ ] Budget breach surfaces as `status="errored"` with a descriptive error in the tool response (not as a raw Python exception).
- [ ] `aiw run` CLI command continues to work byte-identically post-refactor (regression test pins this).
- [ ] MCP tool does not read `GEMINI_API_KEY` directly — env read stays in `LiteLLMAdapter` (KDR-003 boundary).
- [ ] `uv run pytest tests/mcp/test_run_workflow.py tests/cli/test_run.py` green.
- [ ] `uv run lint-imports` 3 / 3 kept; `uv run ruff check` clean.

## Dependencies

- [Task 01](task_01_mcp_scaffold.md) — scaffold + schemas.
- [ai_workflows/cli.py:191](../../../ai_workflows/cli.py) `_run_async` — the canonical dispatch path to extract from.
- M3 [Task 04](../milestone_3_first_workflow/task_04_cli_run.md) — established the run-path contract being mirrored here.
