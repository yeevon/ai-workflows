# Task 02 — Worker Component

**Issues:** C-15, C-16, C-17

## What to Build

The component that executes one subtask. Tier-aware max_turns: Sonnet gets a multi-turn soft cap, all other tiers are single-call.

## Deliverables

### `components/worker.py`

**Config:**
```python
class WorkerConfig(ComponentConfig):
    tier: str                         # tier name from tiers.yaml
    prompt_file: str                  # path to prompt template
    output_schema: str                # "schemas/plan.py:Plan" — module:class
    tools: list[str] = []             # tool names from registry
    max_output_chars: int | None = None  # passed to tool calls
```

**Behavior:**
- Renders the prompt template with task input variables
- Calls `generate()` with the rendered messages and selected tool specs
- **If tier is `sonnet`**: runs a multi-turn loop up to `max_turns` (default 15). Each iteration: execute any tool calls in the response (via registry), append results as `ToolResultBlock`s, call `generate()` again. Stop when: no tool calls in response, OR `done` tool called, OR `max_turns` reached.
- **All other tiers**: single `generate()` call. Tool calls in the response are executed and returned in the result, but no second LLM call is made.
- At soft cap: return `ComponentResult(status="incomplete", ...)` with accumulated content
- Parses LLM output into `output_schema` Pydantic model. On parse failure: return `ComponentResult(status="failed", failure_reason="parse_error: ...")`

**Tool execution within Worker:**
- After `generate()` returns a response with `ToolUseBlock`s, execute each tool via `registry.execute()`
- The registry sanitizes output before returning
- Append `ToolResultBlock(tool_use_id=..., content=sanitized_output)` to the message history

## Acceptance Criteria

- [ ] Single-call tier (Haiku) makes exactly one `generate()` call regardless of tool calls in response
- [ ] Multi-turn Sonnet Worker loops until termination condition
- [ ] Soft cap returns `status="incomplete"` with partial content (not an error)
- [ ] Output parsed into Pydantic model — type error returns `status="failed"`
- [ ] `run_id`, `workflow_id`, `component="worker"` present in every `generate()` call

## Dependencies

- Task 01 (BaseComponent)
