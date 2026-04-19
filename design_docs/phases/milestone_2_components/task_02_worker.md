# Task 02 — Worker Component

**Issues:** C-15, C-16, C-17, CRIT-08

## What to Build

`Worker` wraps `pydantic_ai.Agent[WorkflowDeps, Output]`. We don't re-implement the LLM call loop — pydantic-ai does it. We add tier routing, the multi-turn policy for the orchestrator/implementer tiers, output parsing, and the single-call behavior for gemini_flash/local_coder.

> **Deployment note:** Runtime tiers are Gemini (`orchestrator`, `implementer`, `gemini_flash`) and Qwen (`local_coder`). No Anthropic API — the `opus`/`sonnet`/`haiku` names below are replaced by the new tier names.

## Deliverables

### `components/worker.py`

```python
from pydantic_ai import Agent, ModelRetry
from pydantic_ai.models import Model

class WorkerConfig(ComponentConfig):
    tier: str                            # tier name from tiers.yaml
    system_prompt_file: str              # static instructions (no {{var}}!)
    user_prompt_file: str                # per-call prompt (vars allowed)
    output_schema: str                   # "schemas/plan.py:Plan"
    tools: list[str] = []                # tool names from registry
    max_output_chars: int | None = None  # passed to tool calls' max_chars

class Worker(BaseComponent):
    async def run(
        self,
        input: BaseModel,
        *,
        run_id: str,
        workflow_id: str,
        task_id: str,
    ) -> ComponentResult:
        # 1. build pydantic-ai Model from tier
        # 2. gather tools from registry
        # 3. construct Agent[WorkflowDeps, OutputSchema]
        # 4. set max_turns based on tier policy
        # 5. render user prompt with input vars
        # 6. call run_with_cost(agent, user_prompt, deps)
        # 7. map result to ComponentResult
        ...
```

### Tier Policy (Hardcoded)

```python
TIER_MAX_TURNS = {
    "opus":         20,  # orchestration — long tool chains, multi-step planning
    "sonnet":       15,  # large implementation — soft cap
    "haiku":         1,  # fixed — fast single-turn tasks
    "local_coder":   1,  # fixed — local Qwen, single-turn
    "gemini_flash":  1,  # fixed — overflow last resort, single-turn
}
```

Multi-turn tiers (`opus`, `sonnet`) let pydantic-ai's Agent loop through tool calls until max_turns or no tool calls remain. Single-turn tiers get `max_turns=1` — one LLM call, no second round-trip.

Note: `opus` and `sonnet` invoke Claude via the `claude_code` provider (Claude Code CLI, Max subscription). `haiku` similarly. `gemini_flash` is used only when both `haiku` and `local_coder` fail.

### Output Parsing (C-16)

pydantic-ai `Agent[Deps, OutputSchema]` already enforces the output type. On validation failure, pydantic-ai raises `ModelRetry` internally and asks the model to try again. Bounded by Agent's internal retry count (set to 3 max).

If after 3 internal retries the model still can't produce valid output, pydantic-ai raises — we catch and return `status="failed"` with `failure_reason="output_schema_mismatch"`.

### Soft-Cap Behavior for Sonnet

If `sonnet` hits `max_turns=15` without completing: pydantic-ai returns the partial result. We inspect `result.all_messages()` for the last response and return `status="incomplete"` with the partial output. The Pipeline (or later Orchestrator) decides whether to re-trigger or decompose.

### Tool Selection

```python
tools_for_agent = tool_registry.build_pydantic_ai_tools(config.tools)
agent = Agent(
    model,
    deps_type=WorkflowDeps,
    output_type=output_schema,
    tools=tools_for_agent,
    system_prompt=static_system,
    retries=3,  # ModelRetry bound
)
```

## Acceptance Criteria

- [ ] `haiku` / `local_coder` / `gemini_flash` Worker makes exactly one LLM call regardless of tool calls in response
- [ ] `sonnet` Worker loops until termination or max_turns=15
- [ ] Output parsed into the declared Pydantic model on success
- [ ] Output validation failure retries up to 3 times via `ModelRetry`, then returns `status="failed"`
- [ ] `sonnet` at soft cap returns `status="incomplete"` with partial content preserved
- [ ] `WorkflowDeps` carries `run_id`, `workflow_id`, `component="worker"` into every tool call
- [ ] Cost recorded exactly once per LLM call (no double-counting)

## Dependencies

- Task 01 (BaseComponent)
- M1 Task 03 (model factory)
- M1 Task 05 (tool registry)

## Carry-over from prior audits

Forward-deferred items where this task is the **alternative owner** (the
primary owner is listed per entry). Only pick these up if the primary
owner has not already closed them by the time Worker lands.

- [ ] **M1-T05-ISS-01** — End-to-end test that a real `pydantic_ai.Agent.run()`
  call routes a registered tool's output through
  `forensic_logger.log_suspicious_patterns()`. Primary owner: M1 Task 06
  (stdlib tools, first real tool integration test). If M1 Task 06 closed
  it, mark this entry resolved in review; if not, Worker's integration
  test suite is the next natural home.
  Source: [../milestone_1_primitives/issues/task_05_issue.md](../milestone_1_primitives/issues/task_05_issue.md) — LOW.
- [ ] **M1-T05-ISS-03** — Decide the forensic-scanner contract for
  non-string tool outputs. Primary owner: M1 Task 06. If Worker
  introduces structured-output tools (e.g. a Pydantic-model-returning
  tool) before the stdlib tools pin this convention, Worker owns the
  call: either coerce via pydantic-ai's JSON serialiser before forensic
  scanning, or require registered tools return `str`.
  Source: [../milestone_1_primitives/issues/task_05_issue.md](../milestone_1_primitives/issues/task_05_issue.md) — LOW.
