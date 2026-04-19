# Milestone 2 — Graph-Layer Adapters + Provider Drivers

**Status:** 📝 Planned. Starts once [M1](../milestone_1_reconciliation/README.md) closes clean.
**Grounding:** [architecture.md §4.1–§4.2](../../architecture.md) · [roadmap.md](../../roadmap.md).

## Goal

Ship the `ai_workflows.graph.*` adapters and the two provider drivers the architecture depends on, so any future workflow can be composed as a LangGraph `StateGraph` over primitives. **No workflow code yet** — M2 is node-level building blocks plus end-to-end wiring for a trivial throwaway graph that exercises them in tests.

## Exit criteria

1. `TieredNode`, `ValidatorNode`, `HumanGate`, `CostTrackingCallback`, `RetryingEdge` are implemented in `ai_workflows.graph.*` with unit tests.
2. LiteLLM-backed provider adapter can call Gemini and Qwen/Ollama through one interface (KDR-007); returns `(text, TokenUsage)`.
3. `ClaudeCodeSubprocess` driver invokes `claude -p --output-format json`, parses its output, and emits `TokenUsage` rows including `modelUsage` sub-model entries for haiku sub-calls (KDR-003).
4. LangGraph's `SqliteSaver` is bound to a dedicated DB file and exercised by a smoke-test graph that checkpoints + resumes an `interrupt()` (KDR-009).
5. `uv run pytest`, `uv run lint-imports`, `uv run ruff check` all green.
6. Layer contract holds: `graph` imports only `primitives`; nothing above `graph` yet.

## Non-goals

- Any concrete workflow (`planner`, `slice_refactor`) — those are M3+.
- MCP surface — M4.
- Eval harness — M7.
- Ollama circuit breaker — M8.

## Key decisions in effect

| Decision | Reference |
| --- | --- |
| LangGraph as substrate, no hand-rolled orchestrator | KDR-001 |
| Validator-after-every-LLM-node pattern | KDR-004 |
| 3-bucket retry taxonomy applied at node boundary | KDR-006 |
| LiteLLM adapter; Claude Code stays subprocess/OAuth | KDR-007 |
| LangGraph `SqliteSaver` owns checkpoints | KDR-009 |

## Task order

Critical path: **T01 + T02** (providers) run in parallel, both must land before T03. T03–T07 are node-level and can run in any order after T03. T08 binds the checkpointer once the node types exist. T09 closes.

| # | Task | Critical-path dep |
| --- | --- | --- |
| 01 | [LiteLLM provider adapter](task_01_litellm_adapter.md) | — |
| 02 | [Claude Code subprocess driver](task_02_claude_code_driver.md) | — |
| 03 | [TieredNode adapter](task_03_tiered_node.md) | T01, T02 |
| 04 | [ValidatorNode adapter](task_04_validator_node.md) | T03 |
| 05 | [HumanGate adapter](task_05_human_gate.md) | T03 |
| 06 | [CostTrackingCallback](task_06_cost_callback.md) | T03 |
| 07 | [RetryingEdge](task_07_retrying_edge.md) | T03 |
| 08 | [SqliteSaver binding + smoke graph](task_08_checkpointer.md) | T03–T07 |
| 09 | [Milestone close-out](task_09_milestone_closeout.md) | T01–T08 |

## Issues

Audit findings and blockers land under [issues/](issues/) following the `task_NN_issue.md` convention.
