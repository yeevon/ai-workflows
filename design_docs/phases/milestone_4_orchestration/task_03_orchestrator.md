# Task 03 — DAG Orchestrator (Promotes Pipeline)

**Issues:** C-10, C-11, C-12, C-13, C-14, IMP-08, X-03

## What to Build

Executes a task DAG from the Planner. Promotes the linear `Pipeline` (M2) to a full DAG executor. `pydantic-graph` is the preferred substrate — its typed edges give compile-time wiring validation for free. Falls back to `networkx` topological sort if pydantic-graph constraints don't fit.

**Relationship to Pipeline:** the `Pipeline` component stays — simple linear workflows continue to use it. The `Orchestrator` handles workflows with a real DAG topology (`slice_refactor`, `jvm_modernization`).

## Deliverables

### `components/orchestrator.py`

```python
class OrchestratorConfig(ComponentConfig):
    plan_source: str                     # component name producing the Plan
    parallelism: int = 5
    validator_config: ValidatorConfig | None = None
    failure_policy: Literal["hard_stop", "best_effort", "n_of_m"] = "hard_stop"
```

### Behavior

1. Receive `Plan` (DAG of typed tasks)
2. Validate DAG at plan time:
   - No cycles
   - All `depends_on` references point to existing tasks
   - Input/output schemas match across edges (Haystack pattern — type errors at plan time, not runtime)
3. Topological sort — use `pydantic-graph`'s `Graph.compile()` if plan shape permits; else fall back to `networkx.topological_sort()`
4. Schedule ready tasks (no pending deps) up to `parallelism` per provider
5. Per-provider semaphore: prevents overloading any one provider
6. For each task: dispatch to correct component (Worker / AgentLoop / Fanout / HumanGate)
7. After AgentLoop step: mandatorily run Validator (CRIT-25)
8. On validator failure: one mitigation attempt; second failure → hard stop per `failure_policy`

### Failure Policies

Per analysis — the single "hard_stop only" policy is too restrictive:

- **`hard_stop`** (default): double failure cancels the run. Right for modernization where compile gates are load-bearing.
- **`best_effort`**: collect all failures, continue. Right for docs/review workflows where individual failures don't invalidate the batch.
- **`n_of_m`**: succeed if ≥ N of M tasks pass. Right for aggregate workflows (summarize 10 files — 8 good summaries is acceptable).

Each workflow declares its policy. Default stays `hard_stop`.

### Send-Equivalent Preparation (IMP-08)

Plan schema must support dynamic fan-out. A task can declare:

```python
class Task(BaseModel):
    task_id: str
    task_type: Literal["worker", "agent_loop", "fanout", "human_gate", "runtime_fanout"]
    depends_on: list[str] = []
    # ... other fields

    # For runtime_fanout type:
    spawn_template: Task | None = None  # template to instantiate per result item
    spawn_source_output: str | None = None  # output_key from upstream task to iterate
```

When the Orchestrator hits a `runtime_fanout` task: it reads the upstream output, creates one instance of the template per item, schedules them. Not implemented in M4 unless `slice_refactor` needs it — but the Plan schema permits it now so we don't need to change the schema later.

### SIGINT Cancellation (X-03)

Wrap main execution in `asyncio.TaskGroup`:

```python
try:
    async with asyncio.TaskGroup() as tg:
        for task in scheduler.ready():
            tg.create_task(self._run_task(task))
except KeyboardInterrupt:
    # mark in-flight as running (not failed) — resume-safe
    await storage.mark_interrupted(run_id)
    print(f"Run paused — resume with: aiw resume {run_id}")
    raise SystemExit(130)
```

### Checkpoint/Resume

Same as Pipeline: task states in SQLite, `aiw resume` skips `completed`, re-queues `running`.

## Acceptance Criteria

- [ ] Independent tasks run in parallel (verify with mock timestamp recorder)
- [ ] Task B waits for Task A if `B.depends_on = [A]`
- [ ] AgentLoop output always runs through Validator before `completed`
- [ ] `failure_policy: hard_stop` cancels siblings on double-failure
- [ ] `failure_policy: best_effort` continues and reports all failures
- [ ] Plan with a cycle raises at load time (before any LLM call)
- [ ] Plan with type mismatch on an edge raises at load time
- [ ] SIGINT marks running tasks `running` (not `failed`) in SQLite

## Dependencies

- Task 01 (Planner)
- Task 02 (AgentLoop)
- M2 Tasks 02, 03, 04, 05
