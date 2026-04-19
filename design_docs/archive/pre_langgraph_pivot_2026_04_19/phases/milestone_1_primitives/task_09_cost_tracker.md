# Task 09 — Cost Tracker with Budget Enforcement

**Status:** ✅ Complete (2026-04-19) — see [issues/task_09_issue.md](issues/task_09_issue.md).

**Issues:** P-32, P-33, P-34, CRIT-03 (revises P-35)

## What to Build

Cost tracker that tags every LLM call, records to SQLite, and **enforces a budget cap per run**. Budget cap is upgraded from deferred to critical — the user is paying Claude Max out of pocket and a runaway Opus loop can burn $50 overnight.

## Deliverables

### `primitives/cost.py`

```python
class BudgetExceeded(Exception):
    def __init__(self, run_id: str, current_cost: float, cap: float):
        self.run_id = run_id
        self.current_cost = current_cost
        self.cap = cap
        super().__init__(
            f"Run {run_id} exceeded budget: ${current_cost:.2f} > ${cap:.2f} cap"
        )


def calculate_cost(model: str, usage: TokenUsage, pricing: dict) -> float:
    """
    Returns USD cost for a single LLM call.

    Pricing lookup:
      (input * input_rate + output * output_rate + cache_read * cache_read_rate + cache_write * cache_write_rate) / 1_000_000

    Returns 0.0 for local models (pricing input_per_mtok=0.0).
    Returns 0.0 with WARNING log for models not in pricing.
    """


class CostTracker:
    def __init__(
        self,
        storage: StorageBackend,
        pricing: dict,
        budget_cap_usd: float | None = None,
    ): ...

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
        is_escalation: bool = False,
    ) -> float:
        """
        Calculate cost, write to storage, update run total.
        IF budget_cap_usd is set AND new total > cap: raise BudgetExceeded.
        """

    async def run_total(self, run_id: str) -> float: ...
    async def component_breakdown(self, run_id: str) -> dict[str, float]: ...
```

### Budget Cap Semantics

- `max_run_cost_usd` declared in workflow YAML:
  ```yaml
  name: jvm_modernization
  max_run_cost_usd: 5.00
  ```
- `CostTracker` receives the cap at construction
- After every `record()` call, checks if `new_total > cap`
- If exceeded: raises `BudgetExceeded` BEFORE returning. The exception propagates up and halts the run. All in-flight tasks via `asyncio.TaskGroup` are cancelled.
- Run is marked `failed` with reason `budget_exceeded`
- Completed tasks are preserved in the run log

### Workflow YAML Integration

```yaml
# Default cap if unset
max_run_cost_usd: 10.00

# Explicit opt-out for dev/testing
max_run_cost_usd: null  # no cap, with warning on run start
```

On workflow load, if `max_run_cost_usd` is `null`, log a WARNING: `"No budget cap set — runs can consume unlimited cost."`

### `aiw inspect` Integration

`aiw inspect <run_id>` should surface cap, current cost, and remaining budget:

```text
Run abc123 — jvm_modernization
Status: running
Budget: $3.47 / $5.00 (69% used)
```

## Acceptance Criteria

- [x] `calculate_cost()` matches expected USD for known (model, tokens) pairs
- [x] Local model records $0.00 and `is_local=1` in the llm_calls row
- [x] `run_total()` excludes rows with `is_local=1`
- [x] `component_breakdown()` groups by component and returns per-component USD
- [x] Budget cap triggers `BudgetExceeded` at or before the call that exceeds
- [x] `BudgetExceeded` includes run_id, current_cost, cap in the message
- [x] `null` budget cap logs a warning on run start
- [x] Escalation calls have `is_escalation=1`

## Dependencies

- Task 02 (TokenUsage)
- Task 07 (pricing loader)
- Task 08 (storage backend)
