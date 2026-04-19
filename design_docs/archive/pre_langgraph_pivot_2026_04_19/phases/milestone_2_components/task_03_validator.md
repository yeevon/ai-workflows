# Task 03 — Validator Component

**Issues:** C-18, C-19

## What to Build

`Validator` with two types: structural (shell) and semantic (LLM judge). The semantic variant uses `pydantic_ai.Agent` with an output shape usable by `pydantic-evals` in M3.

## Deliverables

### `components/validator.py`

```python
class ValidatorStep(BaseModel):
    type: Literal["structural", "semantic"]
    # structural:
    command: str | None = None
    working_dir: str | None = None
    # semantic:
    tier: str | None = None
    criteria_prompt: str | None = None  # path to criteria template

class ValidatorConfig(ComponentConfig):
    steps: list[ValidatorStep]
    stop_on_first_failure: bool = True

class ValidationResult(BaseModel):
    passed: bool
    step_type: str
    failure_reason: str | None = None
    output: str | None = None
```

### Structural Validator

- Runs the shell command via `run_command` tool (respects CWD restriction + allowlist)
- Exit 0 → pass; non-zero → `failure_reason = stdout + stderr`
- `working_dir` defaults to `ctx.deps.project_root`

### Semantic Validator

Uses a `pydantic_ai.Agent[WorkflowDeps, JudgeOutput]`:

```python
class JudgeOutput(BaseModel):
    passed: bool
    reason: str  # fed back as failure_reason on fail

semantic_agent = Agent(
    model=build_model(step.tier, tiers, cost_tracker)[0],
    deps_type=WorkflowDeps,
    output_type=JudgeOutput,
    system_prompt=load_prompt(step.criteria_prompt),
)

result = await run_with_cost(
    semantic_agent,
    f"Evaluate this output against the criteria: {worker_output}",
    deps,
    cost_tracker,
)
```

The `JudgeOutput` shape maps directly onto `pydantic-evals`'s `LLMJudge` concept — in M3, the same semantic validator can be used as an eval evaluator with zero changes.

### Failure Reason is Load-Bearing

The Orchestrator (later the Pipeline) feeds `failure_reason` back to the Worker for the mitigation attempt. The reason must be specific enough for the Worker to act on. For structural: include exit code + last N lines of output. For semantic: the judge's reason field verbatim.

## Acceptance Criteria

- [ ] Structural validator passes on exit 0
- [ ] Structural validator fails on non-zero with output in `failure_reason`
- [ ] Structural validator respects `allowed_executables` (blocked command raises)
- [ ] Semantic validator returns structured `JudgeOutput` via pydantic-ai
- [ ] Semantic validator's prompt is a **static** system prompt (no `{{var}}` — validated at load time)
- [ ] `stop_on_first_failure=True` skips remaining steps after first failure
- [ ] Semantic validator's cost is tracked separately and visible in `aiw inspect`

## Dependencies

- Task 01 (BaseComponent)
- M1 Task 06 (shell tool for structural)
- M1 Task 03 (model factory for semantic)
