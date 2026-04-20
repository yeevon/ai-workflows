# Milestone 2 — Graph-Layer Adapters + Provider Drivers

**Status:** ✅ Complete (2026-04-19).
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

## Outcome (2026-04-19)

M2 closed on 2026-04-19 with every exit criterion met and a single clean cycle per task (T01–T08) plus this docs-only close-out (T09).

**Adapters shipped** ([tasks 03](task_03_tiered_node.md)–[07](task_07_retrying_edge.md)):

- [`TieredNode`](../../../ai_workflows/graph/tiered_node.py) — tier registry lookup, route resolution, `StructuredLogger` hook, `CostTracker` wire-through. Pins KDR-001 / KDR-004 / KDR-007.
- [`ValidatorNode`](../../../ai_workflows/graph/validator_node.py) — schema-first JSON parse with one revision-hint feedback edge per KDR-004.
- [`HumanGate`](../../../ai_workflows/graph/human_gate.py) — `langgraph.types.interrupt` + `SQLiteStorage` gate log; resumes via `Command(resume=...)`.
- [`CostTrackingCallback`](../../../ai_workflows/graph/cost_callback.py) — LangChain callback that folds `TokenUsage` into `CostTracker` and trips `BudgetExceeded` per KDR-008 wiring.
- [`RetryingEdge`](../../../ai_workflows/graph/retrying_edge.py) — pure `(state) -> str` router over the 3-bucket taxonomy (KDR-006); no bespoke retry loops anywhere else.
- [`wrap_with_error_handler`](../../../ai_workflows/graph/error_handler.py) — raise-to-state bridge landed as the M2-T07-ISS-01 carry-over so workflows get a copy-paste template for the retry loop.

**Providers shipped**:

- [`LiteLLMAdapter`](../../../ai_workflows/primitives/llm/litellm_adapter.py) ([task 01](task_01_litellm_adapter.md)) — one interface over Gemini + Qwen/Ollama; returns `(text, TokenUsage)` with exception classification into the 3-bucket taxonomy (KDR-007).
- [`ClaudeCodeSubprocess`](../../../ai_workflows/primitives/llm/claude_code.py) ([task 02](task_02_claude_code_driver.md)) — `claude -p --output-format json` driver, OAuth-only, parses `modelUsage` sub-model entries for haiku sub-calls (KDR-003).

**Checkpointer + smoke graph** ([task 08](task_08_checkpointer.md)):

- [`build_checkpointer` / `build_async_checkpointer`](../../../ai_workflows/graph/checkpointer.py) — thin factories over LangGraph's `SqliteSaver` / `AsyncSqliteSaver` (KDR-009); default path `~/.ai-workflows/checkpoints.sqlite`, env override `AIW_CHECKPOINT_DB`, distinct file from the Storage DB.
- [`tests/graph/test_smoke_graph.py`](../../../tests/graph/test_smoke_graph.py) — end-to-end graph wiring `llm → validator → gate → END` under the async checkpointer; pauses at `interrupt`, resumes via `Command(resume=...)`, and probes the on-disk `checkpoints` table to prove LangGraph persists to the expected file. Stubbed `LiteLLMAdapter` keeps the test hermetic.

**Green-gate snapshot (2026-04-19)**:

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 236 passed, 2 warnings (pre-existing `yoyo` datetime deprecation) in 3.26s |
| `uv run lint-imports` | ✅ 3 contracts kept, 0 broken (21 files, 17 deps analyzed) |
| `uv run ruff check` | ✅ All checks passed |

**Exit-criteria verification**:

1. Adapters + callback + retry edge exist in `ai_workflows.graph.*` with unit tests — verified: see files listed above + per-task issue files (all ✅ PASS).
2. LiteLLM-backed provider speaks Gemini and Qwen/Ollama through one interface — [task_01_issue.md](issues/task_01_issue.md) ✅ PASS.
3. `ClaudeCodeSubprocess` parses `claude -p --output-format json` including `modelUsage` sub-model entries — [task_02_issue.md](issues/task_02_issue.md) ✅ PASS.
4. `SqliteSaver` bound to a dedicated DB file and exercised by a smoke graph that checkpoints + resumes an `interrupt()` — [task_08_issue.md](issues/task_08_issue.md) ✅ PASS.
5. `uv run pytest`, `uv run lint-imports`, `uv run ruff check` all green — snapshot above.
6. Layer contract held: `graph` imports only `primitives`; nothing above `graph` exists yet — `lint-imports` output confirms.
