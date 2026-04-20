# Task 03 — `resume_run` Tool

**Status:** 📝 Planned.

## What to Build

Wire the `resume_run` tool body so a client can clear a pending `HumanGate` the way `aiw resume <run_id>` does. Reads run metadata from `Storage`, reseeds the cost tracker from `runs.total_cost_usd`, recompiles the graph under the async checkpointer, and hands `Command(resume=...)` to LangGraph (KDR-009). Mirrors [ai_workflows/cli.py:442-506](../../../ai_workflows/cli.py) `_resume_async`.

Aligns with [architecture.md §4.4](../../architecture.md) (`resume_run` signature), §5 (runtime data flow step 7), KDR-008, KDR-009.

## Deliverables

### Shared dispatch helper (extended from T02)

Extend the shared dispatch module from [T02](task_02_run_workflow.md) with a `resume_run` entry point:

```python
async def resume_run(
    *,
    run_id: str,
    gate_response: Literal["approved", "rejected"],
) -> dict[str, Any]:
    """Rehydrate a checkpointed run and clear the pending HumanGate.

    Shared by the ``aiw resume`` CLI command and the ``resume_run`` MCP tool.
    """
```

Refactor `ai_workflows/cli.py` `_resume_async` to route through this helper — same pattern as T02's refactor of `_run_async`. Behaviour on the CLI side must be byte-identical (regression test pins).

### `ai_workflows/mcp/server.py` — `resume_run` tool body

```python
@mcp.tool()
async def resume_run(payload: ResumeRunInput) -> ResumeRunOutput:
    """Clear a pending HumanGate and advance the workflow."""
    result = await dispatch.resume_run(
        run_id=payload.run_id,
        gate_response=payload.gate_response,
    )
    return ResumeRunOutput(**result)
```

### Cancelled-run precondition (carry-over hook for T05)

Add a single precondition check at the top of the shared `resume_run` helper:

```python
row = await storage.get_run(run_id)
if row is None:
    raise ValueError(f"no run found: {run_id}")
if row["status"] == "cancelled":
    raise ValueError(f"run {run_id} was cancelled and cannot be resumed")
```

[Task 05](task_05_cancel_run.md) flips `runs.status` to `"cancelled"`; this guard is what makes the flip meaningful. Ships here (not in T05) because the CLI `aiw resume` needs the same guard and the shared helper is the one place that serves both surfaces.

### Tests

`tests/mcp/test_resume_run.py`:

- Drive `run_workflow` → `resume_run` in-process against a stubbed tier registry; assert the final output has `status="completed"` + `plan` populated + `total_cost_usd` rolled up.
- `gate_response="rejected"` produces `status="gate_rejected"` with no plan; `Storage.get_run` row reflects `status="gate_rejected"`.
- Unknown `run_id` surfaces as a JSON-RPC error, not a raw exception.
- **Precondition test:** a run whose `status="cancelled"` refuses `resume_run` with a clear error.
- Regression: `tests/cli/test_resume.py` still green post-refactor.

## Acceptance Criteria

- [ ] `resume_run(ResumeRunInput)` returns `ResumeRunOutput` with `{run_id, status, plan?, total_cost_usd?}`.
- [ ] Approved + completed: `status="completed"`, `plan` populated, Storage row flipped to `"completed"`.
- [ ] Rejected: `status="gate_rejected"`, `plan=None`, Storage row flipped to `"gate_rejected"`.
- [ ] Cancelled-run guard refuses resume with an actionable error message (T05 relies on this).
- [ ] `aiw resume` CLI continues to work byte-identically post-refactor.
- [ ] CostTracker reseed from `runs.total_cost_usd` still budget-caps correctly (regression from M3 T05 AC-5).
- [ ] `uv run pytest tests/mcp/test_resume_run.py tests/cli/test_resume.py` green.
- [ ] `uv run lint-imports` 3 / 3 kept; `uv run ruff check` clean.

## Dependencies

- [Task 01](task_01_mcp_scaffold.md) — scaffold + schemas.
- [Task 02](task_02_run_workflow.md) — establishes the shared dispatch module.
- [ai_workflows/cli.py:442](../../../ai_workflows/cli.py) `_resume_async` — canonical resume path.
- M3 [Task 05](../milestone_3_first_workflow/task_05_cli_resume.md) — resume-path contract being mirrored.
