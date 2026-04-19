# Task 02 — AgentLoop Component

**Issues:** C-22, C-23, C-24, C-25, CRIT-11

## What to Build

Open-ended tool-using loop on top of `pydantic_ai.Agent`. Documented weaker guarantee than Worker. Used by Planner (Phase 2) and directly by workflows needing research/investigation. **Fresh context per subagent** is the default (CRIT-11).

## Deliverables

### `components/agent_loop.py`

```python
class AgentLoopConfig(ComponentConfig):
    tier: str
    system_prompt_file: str
    tools: list[str]
    max_iterations: int = 20
    output_schema: str | None = None
    context_isolation: Literal["fresh", "shared"] = "fresh"  # CRIT-11

class AgentLoop(BaseComponent):
    """
    DOCUMENTED WEAK GUARANTEE:
    AgentLoop does NOT guarantee identical outputs for identical inputs.
    Tool-call history and intermediate state accumulate across turns.
    The Orchestrator is responsible for validating AgentLoop output via
    a Validator gate — do not trust AgentLoop output without validation.
    """
```

### Termination Conditions

Three possible termination triggers, whichever comes first:

1. Response has no `ToolUseBlock`s → complete, return last text content
2. Model calls the `done(summary: str)` tool → complete, return the `summary`
3. `max_iterations` reached → `status="incomplete"`, return accumulated content

### Context Isolation (CRIT-11)

```python
if config.context_isolation == "fresh":
    # Each AgentLoop invocation is a fresh Agent with no shared history.
    # Subagents (e.g., Planner Phase 1 over multiple modules) are independent.
    agent = Agent(model, ...)
elif config.context_isolation == "shared":
    # Opt-in: the AgentLoop shares message history across calls.
    # Document the risk: larger context, higher cost, potential for drift.
    agent = self._shared_agent or Agent(model, ...)
    self._shared_agent = agent
```

Default `fresh` matches Anthropic's subagent pattern. Shared context is opt-in per component config.

### Context Compaction (Basic, C-24)

When accumulated message history exceeds 80% of tier's `max_context` (estimated by char count / 4):

1. Call the same model with a `"Summarize everything you have learned and decided so far"` prompt
2. Replace the history with the summary as a single user message
3. Continue the loop with the compacted context

Log when compaction occurs. Not rocket science — just an emergency valve.

### The `done` Tool

Automatically added to every AgentLoop's tool list:

```python
@loop_agent.tool
async def done(ctx: RunContext[WorkflowDeps], summary: str) -> str:
    """Call when task is complete. Summary becomes the output."""
    ctx.deps._done_called = True
    ctx.deps._done_summary = summary
    return "Task marked done"
```

The loop checks `deps._done_called` after each turn and terminates.

## Acceptance Criteria

- [ ] Loop stops when response has no tool calls
- [ ] Loop stops when `done(summary=...)` is called; returns summary as content
- [ ] `max_iterations` returns `status="incomplete"` with accumulated content
- [ ] Compaction triggers at ~80% context fill
- [ ] `context_isolation="fresh"` builds a new Agent per run call
- [ ] `context_isolation="shared"` preserves history across calls
- [ ] Docstring on class states the weak guarantee

## Dependencies

- M2 Task 01 (BaseComponent)
- M1 all
