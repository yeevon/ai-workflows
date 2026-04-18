# Task 05 — Linear Pipeline Component (NEW)

**Issues:** SD-02, C-13, CRIT-02

## What to Build

A linear sequencer that runs `flow:` steps in order. Replaces the DAG `Orchestrator` for M1-M3. The DAG Orchestrator ships in M4 when `slice_refactor` actually needs it.

## Why Pipeline First

- `test_coverage_gap_fill` (M3) is linear: `explore → generate_tests → validate`
- Linear execution is a strict subset of DAG: every linear pipeline is a DAG with only sequential edges
- Checkpoint/resume is simpler: one cursor pointing at the next step
- Testable in isolation without `networkx`, topological sort, or DAG validation
- Pipeline-to-DAG upgrade in M4 is mechanical: the DAG Orchestrator accepts a linear DAG the same way

## Deliverables

### `components/pipeline.py`

```python
class PipelineConfig(ComponentConfig):
    steps: list[str]                     # component names in order, from workflow.yaml flow:
    continue_on_failure: bool = False    # default: hard stop at first step failure

class Pipeline(BaseComponent):
    def __init__(
        self,
        config: PipelineConfig,
        components: dict[str, BaseComponent],  # component name → instance
        storage: StorageBackend,
        cost_tracker: CostTracker,
        tool_registry: ToolRegistry,
    ): ...

    async def run(
        self,
        input: BaseModel,
        *,
        run_id: str,
        workflow_id: str,
        task_id: str = "pipeline",
    ) -> ComponentResult: ...
```

### Execution Semantics

1. Read current step index from SQLite (resume point)
2. For each step from index onward:
   - Mark task `running` in SQLite
   - Execute the component
   - On success: store output as artifact (`runs/<run_id>/artifacts/{step_name}.json`), mark `completed`, advance cursor
   - On failure: write failure artifact, mark `failed`, re-raise
3. On `asyncio.CancelledError` (SIGINT): mark current step `running` (interrupted, safe to resume), exit

### Step-to-Step Data Flow (CRIT-01)

Each step's output is available to subsequent steps as a named input. The Pipeline config resolves `input_from:` references at load time:

```yaml
components:
  explore:
    type: worker
    # ... produces ExplorationReport

  generate_tests:
    type: fanout
    input_from: explore    # receives ExplorationReport as input
```

At load time, the workflow loader checks: does `explore`'s output schema match `generate_tests`'s declared input schema? If not, `TypeMismatchError` — before any LLM call. This is the Haystack typed-socket pattern.

### Checkpoint Storage

SQLite `tasks` table tracks pipeline steps:

```text
task_id="pipeline:explore"        status="completed"
task_id="pipeline:generate_tests" status="running"
task_id="pipeline:validate_build" status="pending"
```

On resume: find the first non-completed step, start from there. Re-queue `running` steps.

### Budget Cap Integration

The `CostTracker` enforces the cap. When `BudgetExceeded` is raised inside a step, it propagates through the Pipeline, marks the run `failed` with reason `budget_exceeded`, and exits. Already-completed steps are preserved.

## Acceptance Criteria

- [ ] Linear flow of 3 steps executes in declared order
- [ ] Output of step 1 is passed as input to step 2 per `input_from:`
- [ ] Type mismatch between step outputs and inputs raises at workflow load time
- [ ] Mid-pipeline failure marks current step `failed`, halts, preserves prior steps as `completed`
- [ ] SIGINT marks current step `running` (not failed), resume picks up from there
- [ ] `BudgetExceeded` in step 3 preserves steps 1 and 2 as `completed`
- [ ] No dependency on `networkx` or DAG libraries

## Dependencies

- All prior M2 tasks
- M1 Task 08 (storage)
- M1 Task 09 (cost tracker with budget cap)
