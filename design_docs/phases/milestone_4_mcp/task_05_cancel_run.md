# Task 05 — `cancel_run` Tool (Storage-Level)

**Status:** 📝 Planned.

## What to Build

Wire the `cancel_run` tool as a **storage-level status flip** — the canonical M4 cancel path per [architecture.md §8.7](../../architecture.md). Flips `runs.status` from `pending` to `cancelled`, stamps `finished_at`. A subsequent `resume_run` refuses cancelled rows via the precondition guard shipped in [Task 03](task_03_resume_run.md).

**In-flight cancellation (asyncio task abort with `durability="sync"`, subgraph/ToolNode guards) is explicitly out of scope for M4** — owned by [M6 T02](../milestone_6_slice_refactor/README.md) when parallel slice workers push wall-clock runtime into the minutes range. See [architecture.md §8.7](../../architecture.md) for the full M4 / M6 split reasoning.

The planner workflow spends almost all of its wall-clock time paused at the `HumanGate`, so the storage-flip path covers the dominant use case (client starts a run, decides against approving it at gate, sends `cancel_run` instead of `resume_run`).

Aligns with [architecture.md §4.4](../../architecture.md), [§8.7](../../architecture.md), KDR-008, KDR-009.

## Deliverables

### `SQLiteStorage` — `cancel_run` method

[ai_workflows/primitives/storage.py](../../../ai_workflows/primitives/storage.py) gains a new method on both `StorageBackend` (protocol stub) and `SQLiteStorage` (implementation):

```python
async def cancel_run(self, run_id: str) -> Literal["cancelled", "already_terminal"]:
    """Flip run status to 'cancelled' if currently pending.

    Returns 'cancelled' if the flip happened, 'already_terminal' if the row
    was already in a terminal state (completed, gate_rejected, cancelled,
    errored) — i.e. the cancel is a no-op.
    """
```

- Single UPDATE: `UPDATE runs SET status='cancelled', finished_at=? WHERE run_id=? AND status='pending'`.
- Caller maps `rowcount == 0` to `"already_terminal"` vs `rowcount == 1` to `"cancelled"`.
- Raises if `run_id` does not exist (surfaced as a JSON-RPC error by the MCP tool).
- Goes through the same `asyncio.Lock` every other Storage write uses.

### `ai_workflows/mcp/server.py` — `cancel_run` tool body

```python
@mcp.tool()
async def cancel_run(payload: CancelRunInput) -> CancelRunOutput:
    """Cancel a pending run. No-op on terminal runs."""
    storage = await SQLiteStorage.open(default_storage_path())
    result = await storage.cancel_run(payload.run_id)
    return CancelRunOutput(run_id=payload.run_id, status=result)
```

### `resume_run` guard (already shipped in T03)

T03 landed the precondition check: `if row["status"] == "cancelled": raise ValueError(...)`. T05 pins that behaviour with its own regression test — `cancel_run` → `resume_run` must refuse with a clear message, not silently no-op.

### Tests

`tests/mcp/test_cancel_run.py`:

- Seed a `pending` row → `cancel_run` returns `status="cancelled"`; `Storage.get_run` reflects the flip + `finished_at` stamped.
- Idempotence: a second `cancel_run` on the same id returns `status="already_terminal"` (the first flip moved it out of `pending`).
- Pre-existing terminal row (`completed` / `gate_rejected`): `cancel_run` returns `"already_terminal"` without side effect.
- Unknown `run_id`: surfaces as a JSON-RPC error, not a raw exception.
- Cross-tool behaviour: `run_workflow` (pauses at gate) → `cancel_run` → `resume_run` refuses with a clear "cancelled and cannot be resumed" error.

`tests/primitives/test_storage.py`: add a unit test for `SQLiteStorage.cancel_run` covering the three outcomes (flip, no-op, unknown).

## Acceptance Criteria

- [ ] `cancel_run(CancelRunInput)` returns `CancelRunOutput` with `status ∈ {"cancelled", "already_terminal"}`.
- [ ] Storage row flip: `status='cancelled'` + `finished_at` set; no other fields mutated.
- [ ] Tool is idempotent: calling twice on the same id returns `"cancelled"` then `"already_terminal"`.
- [ ] `resume_run` refuses a cancelled run (T03 guard exercised end-to-end here).
- [ ] No LangGraph task cancellation, no `durability="sync"` change, no subgraph or ToolNode handling in this task — that path is M6's (architecture.md §8.7).
- [ ] `uv run pytest tests/mcp/test_cancel_run.py tests/primitives/test_storage.py` green.
- [ ] `uv run lint-imports` 3 / 3 kept; `uv run ruff check` clean.

## Dependencies

- [Task 01](task_01_mcp_scaffold.md) — scaffold + schemas.
- [Task 03](task_03_resume_run.md) — cancelled-run precondition guard on `resume_run`.
- [architecture.md §8.7](../../architecture.md) — cancellation model spec.
- [M6 README Carry-over](../milestone_6_slice_refactor/README.md) — where in-flight cancellation lands.
