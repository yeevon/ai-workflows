# Milestone 2 — Minimum Components

## Goal

Build the three components needed to recreate Pipeline 1's shape: a Worker that executes a single subtask, a Validator that checks its output, and a Fanout that runs Workers in parallel over a list.

**Exit criteria:** Worker + Validator + Fanout can be composed to process a list of files in parallel, validate each output, and surface failures — matching the shape of `test_coverage_gap_fill` without the workflow-specific logic.

## Scope

- `BaseComponent` ABC
- `Worker` (single-call for Haiku/Qwen/Flash; multi-turn soft cap for Sonnet)
- `Validator` (structural + semantic types)
- `Fanout` (max 5 concurrent, failure isolation, hard stop on double-failure)

## Key Decisions In Effect

| Decision | Value |
|---|---|
| Component base | `BaseComponent` ABC — shared logging, cost tagging, run_id threading |
| Component config | Pydantic model per component, loaded from YAML at workflow start |
| Component instantiation | At workflow load time, not lazily |
| Prompt template rendering | Simple `{{variable}}` substitution only |
| Worker max_turns | Sonnet: 15 soft cap; Haiku/Qwen/Flash: 1 (fixed) |
| Fanout concurrency | Max 5, hard cap 8 |
| Failure policy | One mitigation attempt; double-failure = full hard stop |
| Retry | Primitive-level only — components call `retry_on_rate_limit()`, don't implement their own |

## Task Order

1. `task_01_base_component.md`
2. `task_02_worker.md`
3. `task_03_validator.md`
4. `task_04_fanout.md`
