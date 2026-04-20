# Task 03 — Sub-Graph Composition Validation

**Status:** 📝 Planned.

## What to Build

The `planner` `StateGraph` topology from [M3 T03](../milestone_3_first_workflow/task_03_planner_graph.md) already shapes exactly what architecture.md §4.3 calls for: `START → explorer → explorer_validator → planner → planner_validator → gate → artifact → END` with retry self-loops per node. [T01](task_01_qwen_explorer.md) + [T02](task_02_claude_code_planner.md) repoint the two tiers without changing the topology. This task is the integration pass — confirm the existing graph shape survives the tier swap, and surface any state-routing bug the mixed-provider path exposes that the per-tier hermetic tests did not.

Aligns with [architecture.md §4.3](../../architecture.md) + §8.2 (graph topology), KDR-004 (validator pairing), KDR-006 (three-bucket retry taxonomy).

## Deliverables

### `ai_workflows/workflows/planner.py` — state plumbing audit

Read the current `PlannerState` `TypedDict` and the `_explorer_prompt` / `_planner_prompt` functions. The planner prompt's inputs include the explorer's parsed `ExplorerReport` (via the `explorer_report` state key). Confirm:

1. The explorer's `output_schema=ExplorerReport` (T01) produces a state transition compatible with the planner prompt's read path.
2. The planner's `output_schema=PlannerPlan` survives the Claude Code subprocess driver's pass-through `response_format` handling (per [`claude_code.py` scope discipline](../../../ai_workflows/primitives/llm/claude_code.py) — the driver ignores `response_format` because the CLI has no structured-output mode; the `ValidatorNode` downstream enforces the schema).
3. The retry-bucket routing from both `planner_validator`'s `on_semantic="planner"` edge and `explorer_validator`'s `on_semantic="explorer"` edge still classifies correctly when the failing tier is Claude Code subprocess (not LiteLLM).

If any of the three fails, log it as a scope question before expanding this task. The target outcome is **no code change** — a clean integration pass proves the M2 adapters truly abstract the provider differences away.

### Tests

`tests/workflows/test_planner_multitier_integration.py` (new):

- **Full hermetic end-to-end** with both tiers stubbed: Qwen explorer `_StubLiteLLMAdapter` + Claude Code `_StubClaudeCodeSubprocess`. Graph runs `START → … → gate` and returns the interrupt payload with a parseable `PlannerPlan`.
- **Cross-provider retry**: inject a Qwen transient error (stub raises `APIConnectionError` once, then succeeds) — graph self-loops explorer once and completes.
- **Cross-provider retry**: inject a Claude Code subprocess `TimeoutExpired` once on the planner node — graph self-loops planner once and completes.
- **Validator-driven semantic retry**: stub Qwen to return malformed JSON on first call, valid on second — graph re-enters explorer via `explorer_validator`'s `on_semantic="explorer"` edge and completes.
- **modelUsage rollup across mixed providers**: total cost = Qwen-primary (cost 0, local) + Claude-Code-primary + Claude-Code-sub-model; all three rows land in `CostTracker`; `runs.total_cost_usd` matches the sum.

### CHANGELOG entry

If no production code changes, CHANGELOG entry notes the integration-only scope and the four hermetic tests as the AC evidence.

## Acceptance Criteria

- [ ] Integration test drives `START → explorer (Qwen stub) → explorer_validator → planner (Claude Code stub) → planner_validator → gate` end-to-end with a valid `PlannerPlan` and the expected interrupt payload.
- [ ] Cross-provider transient retries (Ollama `APIConnectionError` on explorer, `TimeoutExpired` on planner) each self-loop once and complete.
- [ ] Cross-provider semantic retry (Qwen malformed JSON → valid JSON) routes through `explorer_validator`'s `on_semantic="explorer"` edge.
- [ ] `CostTracker` records all three rows (Qwen primary, Claude Code primary, Claude Code sub-model); `runs.total_cost_usd` matches the sum.
- [ ] No unplanned topology changes to `build_planner()`; if any are required, raise as a scope question first.
- [ ] `uv run pytest tests/workflows/` green.
- [ ] `uv run lint-imports` 3 / 3 kept.
- [ ] `uv run ruff check` clean.

## Dependencies

- [Task 01](task_01_qwen_explorer.md) — Qwen explorer tier wired.
- [Task 02](task_02_claude_code_planner.md) — Claude Code planner tier wired.
