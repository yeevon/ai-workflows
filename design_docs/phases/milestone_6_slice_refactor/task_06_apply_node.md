# Task 06 — `apply` Node (Artefact Persistence)

**Status:** 📝 Planned.

## What to Build

Implement the terminal `apply` node for `slice_refactor`: write each approved `SliceResult` as a row in `Storage`'s artefacts table (reuse the existing M1 / M3 artefact helper, do not invent a new table) and flip `runs.status` from `pending` to `completed`. No subprocess, no filesystem write, no `git apply` — [milestone README non-goal](README.md) explicitly scopes applying to a real repo as post-M6. `apply` here is a Storage-layer commit of the validated outputs.

Reject path is a no-op: [T05](task_05_strict_review_gate.md)'s gate routes to END without invoking `apply`, and the storage status flip to `gate_rejected` happens in the terminal edge (not in `apply`).

Aligns with [architecture.md §4.3](../../architecture.md) (apply node writes artefacts), [§4.1](../../architecture.md) (`Storage` owns the artefacts table), KDR-009 (Storage vs checkpointer separation — artefacts go to Storage, not the LangGraph checkpoint).

## Deliverables

### `ai_workflows/workflows/slice_refactor.py` — `apply` node

```python
async def apply(state: SliceRefactorState, config: RunnableConfig) -> dict[str, int]:
    run_id = config["configurable"]["thread_id"]
    storage: StorageBackend = config["configurable"]["storage"]
    aggregate: SliceAggregate = state["aggregate"]
    count = 0
    for result in aggregate.succeeded:
        await storage.write_artifact(
            run_id=run_id,
            kind="slice_result",
            slice_id=result.slice_id,
            payload=result.model_dump_json(),
        )
        count += 1
    return {"applied_artifact_count": count}
```

- **`Storage.write_artifact` — reuse whatever shape landed in M1 / M3.** Do not invent a new signature; if the current helper does not accept `slice_id`, extend it with a generic `metadata: dict[str, Any]` keyword rather than a slice-specific field (applies to future workflows too).
- `apply` writes one row per succeeded slice. Failed slices (from partial aggregates, [T04](task_04_aggregator.md)) are **not** written — the audit trail for failures lives in the gate prompt + `Storage.gate_responses` log, not in the artefacts table.
- After the loop, return the artefact count; the terminal graph edge from `apply` → END hooks into the existing `_dispatch._finalize_run` call (or its equivalent from M3) to flip `runs.status` to `completed` and stamp `finished_at`. If `_dispatch._finalize_run` does not currently handle the slice_refactor shape, extend it — do not duplicate the flip.
- No LLM call, no validator pairing (KDR-004 does not apply; not an LLM node).

### Tests

`tests/workflows/test_slice_refactor_apply.py` (new):

- Happy path: approve a 3-slice aggregate → 3 rows land in `Storage.artifacts`; `runs.status == "completed"`; `runs.finished_at` populated.
- Partial aggregate: approve an aggregate with 2 successes + 1 failure → only 2 artefact rows written; `runs.status == "completed"` (the aggregate was approved; the failure is audit metadata, not a run abort). The double-failure hard-stop case is [T07](task_07_concurrency_hard_stop.md)'s scope and happens before the gate.
- Reject path: reject an aggregate → 0 artefact rows; `runs.status == "gate_rejected"`; `finished_at` populated.
- Idempotency: `apply` re-invoked on the same `run_id` (e.g. via resume-after-crash) does not double-write — either (a) the artefact helper has a natural `(run_id, slice_id)` unique constraint, or (b) `apply` checks for existing rows before insert. Pick one and pin it in the test.
- Artefact payload shape: the stored `payload` round-trips through `SliceResult.model_validate_json(...)` to an equivalent object.

## Acceptance Criteria

- [ ] `apply` node writes one artefact row per succeeded slice via the existing `Storage.write_artifact` helper (extended with `metadata: dict[str, Any]` if needed — not a slice-specific field).
- [ ] Failed slices are not written to artefacts (audit trail lives in gate log).
- [ ] Approve terminates run at `runs.status = "completed"`; reject terminates at `gate_rejected`; both stamp `finished_at`.
- [ ] Re-invocation of `apply` on the same `run_id` does not double-write (pin the mechanism).
- [ ] No subprocess, no filesystem write, no `git` invocation (per milestone non-goal).
- [ ] Hermetic tests green.
- [ ] `uv run lint-imports` 3 / 3 kept.
- [ ] `uv run ruff check` clean.

## Dependencies

- [Task 04](task_04_aggregator.md) — `SliceAggregate` populated in state.
- [Task 05](task_05_strict_review_gate.md) — gate routes to `apply` (approve) or END (reject).
- M1 / M3 `Storage.write_artifact` helper already exists (verify signature in Builder's first read).

## Carry-over from prior audits

- [x] **T01-CARRY-DISPATCH-COMPLETE** (MEDIUM, from T01 Builder-phase scope review 2026-04-20): ✅ RESOLVED in T06 Builder — each workflow module publishes a `FINAL_STATE_KEY` constant (planner → `"plan"`, slice_refactor → `"applied_artifact_count"`). Dispatch's `_build_result_from_final` + `_build_resume_result_from_final` read the key via the new `_resolve_final_state_key` helper (defaults to `"plan"` for legacy modules, so the planner regression is preserved). Approved slice_refactor runs flip to `status="completed"` with `finished_at` auto-stamped by `SQLiteStorage.update_run_status`. Test coverage: `tests/workflows/test_slice_refactor_apply.py::test_dispatch_flips_status_completed_with_finished_at_for_slice_refactor` + `::test_dispatch_planner_completion_path_preserved` + `::test_final_state_key_defaults_to_plan_for_legacy_modules`.
