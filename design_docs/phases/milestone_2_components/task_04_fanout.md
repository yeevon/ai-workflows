# Task 04 — Fanout Component

**Issues:** C-11, C-12, C-26, C-27, C-28

## What to Build

Runs a Worker over a list of inputs in parallel waves. Concurrency max 5 (hard cap 8). Applies the mitigation-then-hard-stop policy. Preserves input order.

## Deliverables

### `components/fanout.py`

```python
class FanoutConfig(ComponentConfig):
    worker_config: WorkerConfig
    validator_config: ValidatorConfig | None = None
    concurrency: int = 5  # hard-capped at 8
    preserve_order: bool = True

class Fanout(BaseComponent):
    async def run(
        self,
        input: BaseModel,
        *,
        run_id: str,
        workflow_id: str,
        task_id: str,
    ) -> ComponentResult:
        # input is expected to expose `.items: list[BaseModel]` — the per-Worker inputs
        ...
```

### Execution

```python
async def _run_wave(items: list) -> list[ComponentResult]:
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(self._run_one(item)) for item in items]
    return [t.result() for t in tasks]

async def _run_one(item) -> ComponentResult:
    result = await worker.run(item, ...)
    if validator:
        val = await validator.run(result.output, ...)
        if not val.passed:
            # Mitigation attempt
            mitigation = await worker.run(
                item.model_copy(update={"failure_context": val.failure_reason}),
                ...
            )
            val2 = await validator.run(mitigation.output, ...)
            if not val2.passed:
                raise FanoutHardStopError(task_id, val.failure_reason, val2.failure_reason)
            return mitigation
    return result
```

### Hard Stop on Double Failure

When `FanoutHardStopError` raises inside a `TaskGroup`, pydantic-ai's SDK and our SDK-level retries don't fire (disabled via max_retries=0), so the exception propagates. `TaskGroup` cancels all sibling tasks — they see `CancelledError` and exit without completing LLM calls in flight.

We catch `FanoutHardStopError` at the Fanout level, write a structured failure artifact to `runs/<run_id>/fanout_failures/`, and re-raise so the Pipeline marks the run failed.

**Preservation:** tasks that completed BEFORE the hard stop are already in SQLite as `completed`. Their outputs are in `artifacts`. Nothing is lost.

### Concurrency Cap Validation

Workflow YAML load time check: `concurrency > 8` raises `ConfigurationError`. This is enforced before any LLM call happens.

## Acceptance Criteria

- [ ] Wave of 5 items executes 5 concurrent `Agent.run()` calls (verify with a mock that records timestamps)
- [ ] Order is preserved in result list
- [ ] Single Worker failure with passing mitigation → wave continues
- [ ] Double failure → `FanoutHardStopError` + all sibling tasks cancelled
- [ ] Completed tasks before hard stop remain in `tasks` table as `completed`
- [ ] `concurrency: 9` in YAML raises at load time
- [ ] Mitigation attempt passes `failure_reason` into the Worker input

## Dependencies

- Task 02 (Worker)
- Task 03 (Validator)
- M1 Task 08 (storage)
