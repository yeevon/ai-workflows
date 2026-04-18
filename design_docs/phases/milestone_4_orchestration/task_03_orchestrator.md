# Task 03 — Orchestrator Component

**Issues:** C-10, C-11, C-12, C-13, C-14

## What to Build

Executes a task DAG from the Planner. Handles topological scheduling, per-provider concurrency, checkpoint/resume, and the double-failure hard-stop policy. Mandates a Validator gate after every AgentLoop step.

## Deliverables

### `components/orchestrator.py`

**Config:**
```python
class OrchestratorConfig(ComponentConfig):
    plan_source: str                   # component name that produces the Plan
    parallelism: int = 5               # per-provider semaphore size
    validator_config: ValidatorConfig | None = None
    dispatch_config: dict[str, str] = {}  # task_type -> tier override
```

**Behavior:**

**DAG scheduling:**
- Receive `Plan` (DAG of tasks with `depends_on` edges)
- Topological sort via `networkx.topological_sort()`
- Identify all tasks with no pending dependencies as "ready"
- Schedule ready tasks up to `parallelism` concurrent per provider

**Per-provider semaphore:**
- `asyncio.Semaphore` per provider (anthropic, ollama, openai_compat)
- Prevents overloading a single provider when tasks use different tiers

**Checkpoint/resume:**
- On startup: read task states from SQLite for this `run_id`
- Skip tasks with `status="completed"`
- Re-queue tasks with `status="running"` (treat as interrupted — safe to re-run)
- Continue from ready tasks

**Task execution:**
1. Mark task `running` in SQLite
2. Dispatch to Worker or AgentLoop (based on task type in plan)
3. If AgentLoop: mandatorily run Validator after completion
4. If Validator fails: **one mitigation attempt** — re-run component with `failure_reason` in context
5. If mitigation fails: **hard stop** — cancel all in-flight tasks via `asyncio.TaskGroup` scope cancellation, write `OrchestratorFailure` artifact, raise `OrchestratorHardStopError`
6. On success: mark `completed`, update dependent tasks' ready status

**Task result passing (C-14):**
- Each task declares `output_key: str` in the plan schema
- Completed task outputs stored in a `results: dict[str, Any]` dict keyed by `output_key`
- Downstream tasks receive `results` as available input variables for prompt rendering

**SIGINT cancellation (X-03):**
- Wrap the main execution in `asyncio.TaskGroup`
- On `KeyboardInterrupt`: mark in-flight tasks as `running` (not failed) in SQLite — they are safe to resume
- Print "Run paused — resume with: aiw resume <run_id>"

## Acceptance Criteria

- [ ] Tasks with no dependencies run in parallel (verify with a mock that records call order)
- [ ] Task B waits for Task A if `B.depends_on = [A]`
- [ ] Completed tasks from a prior run are skipped on resume
- [ ] AgentLoop task result always passes through Validator before marking `completed`
- [ ] Double failure triggers hard stop and cancels remaining tasks
- [ ] SIGINT writes `running` (not `failed`) to SQLite for in-flight tasks

## Dependencies

- Task 01 (Planner)
- Task 02 (AgentLoop)
- M2 Task 02 (Worker)
- M2 Task 03 (Validator)
- M1 Task 12 (storage)
