# Task 03 — Validator Component

**Issues:** C-18, C-19

## What to Build

The component that checks Worker output against declared criteria. Two types: structural (shell command) and semantic (LLM-based). Both defined in the interface from day one. Actual implementations (pytest, gradlew, React build) are registered per workflow.

## Deliverables

### `components/validator.py`

**Config:**
```python
class ValidatorStep(BaseModel):
    type: Literal["structural", "semantic"]
    # structural:
    command: str | None = None          # e.g., "./gradlew build"
    working_dir: str | None = None
    # semantic:
    tier: str | None = None             # e.g., "haiku"
    criteria: str | None = None         # plain-text criteria for the LLM

class ValidatorConfig(ComponentConfig):
    steps: list[ValidatorStep]
    stop_on_first_failure: bool = True
```

**`ValidationResult`:**
```python
class ValidationResult(BaseModel):
    passed: bool
    step_type: str
    failure_reason: str | None = None   # fed back to Orchestrator for mitigation
    output: str | None = None           # command output or LLM response
```

**Structural validator behavior:**
- Runs the shell command via `run_command()` (respects CWD restriction and allowlist)
- Passes if exit code is 0
- `failure_reason` = combined stdout/stderr on non-zero exit

**Semantic validator behavior:**
- Builds a prompt: system criteria + worker output as context
- Calls `generate()` on the declared tier
- Parses response for a pass/fail signal (LLM must respond with a structured verdict)
- `failure_reason` = LLM's explanation of what failed

**The failure reason is the key output** — it's what the Orchestrator feeds back to the Worker on the mitigation attempt. It must be specific enough for the Worker to act on.

## Acceptance Criteria

- [ ] Structural validator passes on exit 0, fails on non-zero with stdout in `failure_reason`
- [ ] Semantic validator calls `generate()` with criteria in the system message
- [ ] `ValidationResult.failure_reason` is non-None on all failures
- [ ] Structural validator respects `run_command` allowlist (test with a disallowed command)
- [ ] `stop_on_first_failure=True` skips remaining steps after first failure

## Dependencies

- Task 01 (BaseComponent)
- Task 09 (shell tool — for structural validation)
