# Task 01 — Planner Component

**Issues:** C-06, C-07, C-08, C-09

## What to Build

Two-phase planning: Phase 1 uses Qwen to explore and document the codebase incrementally. Phase 2 uses Opus to read those docs and produce a valid task DAG.

## Deliverables

### `components/planner.py`

**Config:**
```python
class PlannerConfig(ComponentConfig):
    exploration_tier: str = "local_coder"   # Qwen
    planning_tier: str = "opus"
    exploration_prompt: str                  # path to template
    planning_prompt: str                     # path to template
    output_schema: str                       # e.g., "schemas/plan.py:Plan"
    tools: list[str] = ["read_file", "list_dir", "grep", "git_log"]
    max_tasks: int = 50
    max_planning_attempts: int = 3
```

**Phase 1 — Qwen Exploration:**
- Check if `runs/<run_id>/exploration/` exists and has files → if yes, skip Phase 1 (resume-safe)
- Run Qwen as a single-call Worker over each top-level module/directory
- Each Qwen call: reads module contents, outputs a structured module summary (public APIs, dependencies, key interfaces)
- Write each summary as `runs/<run_id>/exploration/{module_name}.md`
- Log exploration doc paths to storage as `artifact_type="exploration_doc"`

**Phase 2 — Opus Planning:**
- Run Opus as an AgentLoop with `read_file`, `list_dir`, `grep`, `git_log` tools
- Opus has access to: exploration docs dir + raw repo (for targeted lookups)
- Loop until Opus produces a response with no tool calls (planning is complete)
- Parse the final response into the `output_schema` Pydantic model
- **On parse failure:** retry the parse (not the whole loop) with the failure reason appended to the last message. Up to `max_planning_attempts` parse retries.
- Validate the DAG: no cycles, no references to nonexistent task IDs, `len(tasks) <= max_tasks`
- Return the validated `Plan` as a `ComponentResult`

**Resume behavior:** If exploration docs already exist for this `run_id`, Phase 1 is skipped entirely. Opus picks up from the existing docs.

## Acceptance Criteria

- [ ] Phase 1 writes one `.md` file per top-level module to `runs/<run_id>/exploration/`
- [ ] Phase 2 skips Phase 1 if exploration docs already exist (verified by running twice and checking Phase 1 doesn't execute)
- [ ] DAG validation rejects circular dependencies
- [ ] DAG validation rejects plans with > `max_tasks` tasks
- [ ] Parse failure triggers retry with failure reason in context, up to `max_planning_attempts`
- [ ] Third parse failure aborts the run with a clear error

## Dependencies

- Task 02 (AgentLoop — Opus runs as an AgentLoop in Phase 2)
- Task 07 M1 (tool registry)
- Task 12 M1 (storage — for logging exploration docs)
