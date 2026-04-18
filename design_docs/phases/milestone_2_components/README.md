# Milestone 2 — Minimum Components (+ Linear Pipeline)

## Goal

Build the components needed to recreate Pipeline 1's shape: a Worker that executes a subtask (thin wrapper over `pydantic_ai.Agent`), a Validator, a Fanout, and a **linear Pipeline** that replaces the DAG Orchestrator for M1-M3 (SD-02).

**Exit criteria:** Pipeline executes a linear sequence of Workers with Validators between them and a Fanout over a list, all on cloud tiers, with budget cap enforcement, and the failure-then-mitigation-then-hard-stop policy working correctly.

## Scope Changes from Original M2

- **Added `Pipeline` component** — linear sequencer. Replaces DAG Orchestrator for M1-M3.
- **Worker is a thin wrapper over `pydantic_ai.Agent[WorkflowDeps, Output]`** — not re-implementing the LLM call loop.
- **Semantic Validator uses `pydantic_ai.Agent` with an LLMJudge-shaped output** — reusable for evals in M3.

## Key Decisions In Effect

| Decision | Value |
| --- | --- |
| Component base | `BaseComponent` ABC — shared logging, cost tagging via `WorkflowDeps` |
| Component config | Pydantic model per component, loaded from YAML |
| Component instantiation | At workflow load time |
| Prompt template rendering | Simple `{{variable}}` substitution. Templates MUST NOT put `{{var}}` in system prompts (breaks caching) |
| Worker max_turns | Sonnet: 15 soft cap; Haiku/Qwen/Flash: 1 fixed |
| Fanout concurrency | Max 5, hard cap 8 |
| Failure policy | One mitigation attempt, then hard stop. `asyncio.TaskGroup` cancels siblings |
| Retry | Primitive-level (`retry_on_rate_limit` + `ModelRetry`) |
| Pipeline execution | Linear, sequential. State persistence via SQLite checkpoint per step |
| Workflow dir hash | Pipeline writes hash to runs row at start |

## Task Order

1. `task_01_base_component.md`
2. `task_02_worker.md`
3. `task_03_validator.md`
4. `task_04_fanout.md`
5. `task_05_pipeline.md` — NEW — linear executor
