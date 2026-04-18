# Task 04 — Fanout Component

**Issues:** C-11, C-26, C-27, C-28, C-12

## What to Build

Runs a Worker over a list of inputs in parallel waves, with a concurrency cap. Applies the double-failure hard-stop policy. Preserves input order in results.

## Deliverables

### `components/fanout.py`

**Config:**
```python
class FanoutConfig(ComponentConfig):
    worker_config: WorkerConfig
    validator_config: ValidatorConfig | None = None
    concurrency: int = 5              # wave size; capped at 8
    preserve_order: bool = True
```

**Behavior:**
1. Validate `concurrency <= 8`. Raise `ConfigurationError` if over.
2. Split input list into waves of `concurrency` items.
3. For each wave: run all Workers concurrently via `asyncio.TaskGroup`.
4. For each Worker result:
   - If `status="completed"` and Validator passes: mark task `completed` in storage.
   - If `status="completed"` but Validator fails: **mitigation attempt** — re-run Worker once with `failure_reason` appended to the prompt as context.
     - If mitigation passes Validator: mark `completed`.
     - If mitigation fails Validator: **hard stop** — cancel all in-flight tasks, mark run `failed`, write `FanoutFailure` artifact with: failed task, both validator outputs, completed tasks so far.
   - If `status="incomplete"`: surface to Orchestrator for decomposition decision (not a hard stop at Fanout level).
5. Results list preserves input order regardless of completion order.

**Hard stop on double-failure:**
```python
# Inside the wave processing loop:
if mitigation_failed:
    # Cancel remaining tasks in this wave
    task_group_scope.cancel()
    # Write failure artifact
    await storage.log_artifact(run_id, "fanout_failure", failure_path)
    raise FanoutHardStopError(failed_task_id, failure_reason)
```

## Acceptance Criteria

- [ ] Concurrency > 8 raises `ConfigurationError` at config load time (not at run time)
- [ ] Wave of 5 items runs 5 concurrent `generate()` calls (verify with mock that counts concurrent calls)
- [ ] Results list order matches input list order regardless of which tasks finish first
- [ ] Double-failure cancels remaining tasks in the wave and raises `FanoutHardStopError`
- [ ] Completed tasks before hard stop are written to storage and preserved
- [ ] Single item failure triggers mitigation before hard stop (not immediate abort)

## Dependencies

- Task 02 (Worker)
- Task 03 (Validator)
- Task 12 (storage — for checkpointing task states)
