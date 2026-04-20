# Task 02 — Claude Code Planner Tier Refit

**Status:** 📝 Planned.

## What to Build

Repoint the `planner-synth` tier from Gemini Flash (`LiteLLMRoute`) to Claude Code Opus via the subprocess driver ([`ClaudeCodeSubprocess`](../../../ai_workflows/primitives/llm/claude_code.py)). This is M5's first real exercise of the `ClaudeCodeRoute` + subprocess driver combination inside a compiled graph — M2 built and unit-tested both pieces; nothing until now wired them into a workflow.

Aligns with [architecture.md §4.1](../../architecture.md) (provider drivers), KDR-003 (OAuth-only — no `anthropic` SDK, no `ANTHROPIC_API_KEY`), KDR-007 (Claude Code stays bespoke because LiteLLM does not cover OAuth-authenticated subprocess providers), KDR-004 (validator pairing preserved).

## Deliverables

### `ai_workflows/workflows/planner.py` — tier registry

Update `planner_tier_registry()` to repoint `planner-synth`:

```python
"planner-synth": TierConfig(
    name="planner-synth",
    route=ClaudeCodeRoute(cli_model_flag="opus"),
    max_concurrency=1,  # OAuth session is single-writer; no parallelism win
    per_call_timeout_s=300,  # Opus + subprocess spawn has higher p95
),
```

Import `ClaudeCodeRoute` from `ai_workflows.primitives.tiers`.

### `TieredNode` route-dispatch verification

The graph-layer `tiered_node` must already dispatch to `ClaudeCodeSubprocess` when it sees a `ClaudeCodeRoute` (M2 T03 wired this). Before making any code change, **read** [`ai_workflows/graph/tiered_node.py`](../../../ai_workflows/graph/tiered_node.py) and confirm the dispatch path exists. If the branch is stub-only or mis-wired, raise it as a scope question before proceeding — do not silently expand scope.

### `modelUsage` sub-model capture

Claude Code Opus calls can spawn internal Haiku sub-model calls (auto-classifier, summarisation). The [`ClaudeCodeSubprocess`](../../../ai_workflows/primitives/llm/claude_code.py) driver already populates `TokenUsage.sub_models` from the CLI's `modelUsage` JSON. This task validates that the sub-model rollup is preserved end-to-end through the graph's `CostTrackingCallback` into `runs.total_cost_usd`.

### Tests

`tests/workflows/test_planner_synth_claude_code.py` (new):

- `planner_tier_registry()` returns `planner-synth.route` as `ClaudeCodeRoute(cli_model_flag="opus")`.
- Hermetic graph run: replay a recorded Claude Code CLI JSON blob (with an Opus primary call + one Haiku sub-model row in `modelUsage`) through a `_StubClaudeCodeSubprocess`. Assert:
  - The full graph completes up to the gate.
  - The validator extracts a parseable `PlannerPlan`.
  - `runs.total_cost_usd` equals the sum of the primary + sub-model rows.
  - Both rows land in the per-run `CostTracker` via `record()`; `TokenUsage.sub_models` is non-empty.
- KDR-003 regression: `grep` in the test file asserts `"anthropic"` appears zero times in `ai_workflows/workflows/planner.py` and `ai_workflows/primitives/llm/claude_code.py` (import lines only, to avoid false positives on docstring mentions).

## Acceptance Criteria

- [ ] `planner_tier_registry()["planner-synth"]` has `ClaudeCodeRoute(cli_model_flag="opus")` and `max_concurrency=1`.
- [ ] Hermetic test drives a full graph pass with Qwen explorer (from [T01](task_01_qwen_explorer.md)) + Claude Code planner stubs, ending at the gate with a valid `PlannerPlan`.
- [ ] `modelUsage` sub-model rollup: primary + sub rows both land in `TokenUsage.sub_models`; `runs.total_cost_usd` matches the sum.
- [ ] No `anthropic` SDK import introduced anywhere (KDR-003).
- [ ] `uv run pytest tests/workflows/` green.
- [ ] `uv run lint-imports` 3 / 3 kept.
- [ ] `uv run ruff check` clean.

## Dependencies

- [Task 01](task_01_qwen_explorer.md) — tier registry already edited for `planner-explorer`; this task adds the second half to the same registry.
- [M2 Task 02](../milestone_2_graph/task_02_claude_code_subprocess.md) — `ClaudeCodeSubprocess` driver + route-dispatch branch in `tiered_node` must already exist.
- The `claude` CLI is **not** required for hermetic tests (stubbed). Live verification lands in [T06](task_06_e2e_smoke.md).
