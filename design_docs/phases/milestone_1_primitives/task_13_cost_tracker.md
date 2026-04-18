# Task 13 — Cost Tracker

**Issues:** P-32, P-33, P-34

## What to Build

Tag every LLM call with cost metadata and write it to storage. Answer queries like "what did this run cost?" and "which component is burning the most budget?"

## Deliverables

### `primitives/cost.py`

**`calculate_cost(model: str, usage: TokenUsage, pricing: dict) -> float`**
- Looks up model in `pricing.yaml` data
- Returns cost in USD: `(input * input_rate + output * output_rate + cache_read * cache_read_rate + cache_write * cache_write_rate) / 1_000_000`
- Returns `0.0` for models with `input_per_mtok: 0.0` (local models)
- Returns `0.0` with a warning log if model not found in pricing

**`CostTracker`:**
```python
class CostTracker:
    def __init__(self, storage: StorageBackend, pricing: dict): ...

    async def record(
        self,
        run_id: str,
        workflow_id: str,
        component: str,
        tier: str,
        model: str,
        usage: TokenUsage,
        task_id: str | None = None,
        is_local: bool = False,
    ) -> float:
        """Calculate cost, write to storage, return cost in USD."""
        ...

    async def run_total(self, run_id: str) -> float:
        """Sum all non-local LLM call costs for a run."""
        ...

    async def component_breakdown(self, run_id: str) -> dict[str, float]:
        """Cost per component for a run."""
        ...
```

**Integration with adapters:** Every adapter's `generate()` calls `cost_tracker.record()` after receiving a response. The `CostTracker` is injected into adapters at construction time.

## Acceptance Criteria

- [ ] `calculate_cost()` matches expected USD for known token counts and models
- [ ] Local model calls record `0.0` and are flagged `is_local=True`
- [ ] `run_total()` excludes local model costs from the sum
- [ ] `component_breakdown()` shows correct per-component totals
- [ ] Unknown model logs a warning but does not crash

## Dependencies

- Task 11 (tiers loader — provides pricing dict)
- Task 12 (storage — provides `StorageBackend`)
