# Task 08 — Prune CostTracker Surface

**Status:** 📝 Planned.

## What to Build

Keep `TokenUsage` and `CostTracker`'s per-run aggregation surface, but strip pydantic-ai coupling and prepare a clean hook for the LiteLLM-sourced per-call cost that M2 will feed in. Preserve the `modelUsage` sub-model rollup — it is load-bearing for Claude Code haiku sub-call recording ([architecture.md §4.1](../../architecture.md)).

## Deliverables

### `ai_workflows/primitives/cost.py`

**Pulled forward by [task 03](task_03_remove_llm_substrate.md):** `TokenUsage` was relocated from the (now-deleted) `ai_workflows/primitives/llm/types.py` into `ai_workflows/primitives/cost.py` as a plain pydantic v2 `BaseModel` with the Task-02 field surface (`input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`). `cost.py` and `tests/primitives/test_cost.py` import `TokenUsage` from `ai_workflows.primitives.cost` now. T03 did **not** add `cost_usd`, `model`, or `sub_models` — those remain T08 deliverables.

Keep or adjust:

- `TokenUsage` pydantic model — **extend** the Task-02 surface already relocated into this module with: `cost_usd`, `model`, optional `sub_models: list[TokenUsage]` (recursive for modelUsage).
- `CostTracker` class:
  - `record(run_id, usage: TokenUsage) -> None` — single entry point that accepts an already-costed `TokenUsage`. LiteLLM enriches before we see it; the Claude Code driver computes cost from `pricing.yaml`.
  - `total(run_id) -> float`
  - `by_tier(run_id) -> dict[str, float]`
  - `by_model(run_id, include_sub_models: bool = True) -> dict[str, float]`
  - `check_budget(run_id, cap_usd: float) -> None` — raises `NonRetryable("budget exceeded")` from [task 07](task_07_refit_retry_policy.md).

Remove:

- Anything that imported pydantic-ai result types.
- Any in-process cost table that duplicated `llm_calls` in `Storage` (that row left in [task 05](task_05_trim_storage.md)); if per-call persistence is still needed, add a minimal `cost_entries` table via a migration here — but default to in-memory aggregation per run and persist only the totals on `update_run_status`.

### Storage coupling

`CostTracker` interacts with `Storage` only through the trimmed protocol from [task 05](task_05_trim_storage.md) (`update_run_status(total_cost_usd=…)`). It does not know about migrations.

### Test updates

`tests/primitives/test_cost.py`:

- Roundtrip: record three `TokenUsage` with nested `sub_models`; assert `by_model(include_sub_models=True)` rolls each sub-model separately.
- Budget enforcement: `check_budget` raises `NonRetryable` at threshold.
- No pydantic-ai imports.

## Acceptance Criteria

- [ ] `TokenUsage` carries the recursive `sub_models` field and round-trips through pydantic serialisation.
- [ ] `CostTracker.record` is the single write path.
- [ ] `check_budget` raises the `NonRetryable` from [task 07](task_07_refit_retry_policy.md).
- [ ] `grep -r "pydantic_ai" ai_workflows/primitives/cost.py tests/primitives/test_cost.py` returns zero matches.
- [ ] `uv run pytest tests/primitives/test_cost.py` green.

## Dependencies

- [Task 03](task_03_remove_llm_substrate.md), [Task 05](task_05_trim_storage.md), [Task 07](task_07_refit_retry_policy.md).
