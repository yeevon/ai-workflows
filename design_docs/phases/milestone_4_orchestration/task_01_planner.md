# Task 01 — Planner Component

**Issues:** C-06, C-07, C-08, C-09, CRIT-11

## What to Build

Two-phase Planner: Phase 1 Qwen-or-Haiku exploration writing per-module summary docs; Phase 2 Opus planning with tool access that reads those docs and produces a typed DAG. Phase 1 tier is configurable — defaults to `haiku` in cloud-default mode, `local_coder` when Ollama infrastructure is ready.

## Deliverables

### `components/planner.py`

```python
class PlannerConfig(ComponentConfig):
    exploration_tier: str = "haiku"     # was local_coder; cloud-default after SD-03
    planning_tier: str = "opus"
    exploration_prompt_system: str
    planning_prompt_system: str
    output_schema: str                   # DAG schema, e.g. "schemas/plan.py:Plan"
    tools: list[str] = ["read_file", "list_dir", "grep", "git_log"]
    max_tasks: int = 50
    max_planning_attempts: int = 3
    context_isolation: Literal["fresh", "shared"] = "fresh"  # CRIT-11

class Planner(BaseComponent):
    async def run(self, input, *, run_id, workflow_id, task_id) -> ComponentResult:
        # Phase 1: exploration (skipped if runs/<run_id>/exploration/ exists)
        # Phase 2: Opus planning with tool access
        ...
```

### Phase 1 — Exploration (Fresh Context Per Module)

For each top-level module in the repo:

- Build a fresh `pydantic_ai.Agent` with exploration_tier
- Run it with ONLY that module as input context
- Parse output into a structured `ModuleSummary`
- Write to `runs/<run_id>/exploration/{module_name}.md`

**Fresh context per module** (CRIT-11): each Qwen/Haiku call is a new Agent instance with no shared history. Prevents exploration drift and keeps context bounded.

Skip Phase 1 entirely if `runs/<run_id>/exploration/` already exists from a prior run. Resume-safe.

### Phase 2 — Planning (Opus, AgentLoop)

Opus runs as an `AgentLoop` with tool access to:

- `read_file` — can read exploration docs OR raw source files
- `grep`, `list_dir` — targeted searches
- `git_log` — history inspection
- `done(plan: Plan)` — termination tool, takes the final DAG as argument

AgentLoop terminates when Opus calls `done(plan=...)`, or when it returns no tool calls, or at `max_iterations`.

### DAG Output via `ModelRetry`

Opus's final output (returned via `done` tool) is type-validated against the DAG schema. Invalid plans trigger `ModelRetry` with the validation error:

```python
@agent.tool
async def done(ctx: RunContext[WorkflowDeps], plan: dict) -> str:
    try:
        validated = Plan.model_validate(plan)
        _check_dag_integrity(validated)  # no cycles, valid task IDs, size <= max_tasks
        return "Plan accepted"
    except ValidationError as e:
        raise ModelRetry(f"Plan invalid: {e}. Try again.")
    except CyclicDependencyError as e:
        raise ModelRetry(f"Plan has a cycle: {e}. Remove the cycle.")
```

pydantic-ai handles the retry loop automatically, bounded by `max_planning_attempts`.

## Acceptance Criteria

- [ ] Phase 1 writes one `.md` per module to `runs/<run_id>/exploration/`
- [ ] Phase 1 is skipped on resume if exploration dir exists
- [ ] Each exploration call is a fresh Agent (no shared history)
- [ ] Phase 2 Opus can read exploration docs and raw source files
- [ ] Invalid plan triggers `ModelRetry` with validation message, up to 3 attempts
- [ ] 4th attempt raises `PlanGenerationFailed` with all 3 prior failure reasons

## Dependencies

- Task 02 (AgentLoop)
- M1 all
