# Task 02 — AgentLoop Component

**Issues:** C-22, C-23, C-24, C-25

## What to Build

An open-ended tool-using loop. Used internally by Planner (Opus planning phase) and directly by workflows needing investigation or research. Weaker guarantee than Worker — documented explicitly.

## Deliverables

### `components/agent_loop.py`

**Config:**
```python
class AgentLoopConfig(ComponentConfig):
    tier: str
    prompt_file: str
    tools: list[str]
    max_iterations: int = 20
    output_schema: str | None = None    # if None, return raw final text
```

**Termination conditions (whichever comes first):**
1. Response contains no `ToolUseBlock`s
2. Model calls a special `done(summary: str)` tool — the summary becomes the output
3. `max_iterations` hard cap reached → return `status="incomplete"` with last response content

**Loop behavior:**
- Iteration N: call `generate()`, get `Response`
- If `ToolUseBlock`s present: execute each tool via registry, append `ToolResultBlock`s, continue
- If `done` tool called: return `status="completed"` with `done.summary` as content
- If no tool calls: return `status="completed"` with last text block as content

**Context compaction (basic):** If accumulated message history exceeds 80% of tier's `max_tokens` (estimated by char count / 4): summarize history by calling the same model with a "summarize our progress so far" prompt, replace the history with `[summary]`, continue. Log when compaction occurs.

**Documented weak guarantee:**
```python
"""
AgentLoop does not guarantee identical outputs for identical inputs.
Tool call history and intermediate state accumulate across turns.
The Orchestrator is responsible for validating AgentLoop output via
a Validator gate — do not trust AgentLoop output without validation.
"""
```

**The `done` tool spec:**
```python
ToolSpec(
    name="done",
    description="Call this when your task is complete. Provide a summary of what you accomplished.",
    input_schema={"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}
)
```
This tool is automatically added to every AgentLoop's tool registry (not via the workflow config).

## Acceptance Criteria

- [ ] Loop stops on no-tool-call response
- [ ] Loop stops on `done` tool call, returns `done.summary` as content
- [ ] Loop returns `status="incomplete"` at `max_iterations`, not an error
- [ ] Compaction triggers when estimated token count exceeds 80% of max_tokens
- [ ] `status="incomplete"` result includes iteration count and last response content
- [ ] Weak guarantee is in the class docstring

## Dependencies

- M2 Task 01 (BaseComponent)
- M1 Task 07 (tool registry)
