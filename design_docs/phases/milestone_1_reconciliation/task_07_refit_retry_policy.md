# Task 07 — Refit RetryPolicy to 3-Bucket Taxonomy

**Status:** 📝 Planned.

## What to Build

Align `ai_workflows/primitives/retry.py` with the taxonomy described in [architecture.md §8.2](../../architecture.md) and KDR-006. Three exception classes, a classifier that accepts LiteLLM + subprocess errors, and a policy object that M2's `RetryingEdge` will consume. Remove pydantic-ai `ModelRetry` wiring — LangGraph ships its own.

## Deliverables

### `ai_workflows/primitives/retry.py`

```python
class RetryableTransient(Exception):
    """Network blip, 429, 5xx, stream interruption. Safe to retry the same call."""

class RetryableSemantic(Exception):
    """Output parsed but violated schema. Re-invoke LLM with revision guidance."""
    def __init__(self, reason: str, revision_hint: str): ...

class NonRetryable(Exception):
    """Auth failure, invalid model, logic error, budget exceeded."""

class RetryPolicy(BaseModel):
    max_transient_attempts: int = 3
    max_semantic_attempts: int = 3
    transient_backoff_base_s: float = 1.0
    transient_backoff_max_s: float = 30.0

def classify(exc: BaseException) -> type[RetryableTransient | RetryableSemantic | NonRetryable]:
    """Map LiteLLM exception types + subprocess CalledProcessError + connection errors to the taxonomy."""
```

`classify` must recognise:

- `litellm.Timeout`, `litellm.APIConnectionError`, `litellm.RateLimitError`, `litellm.ServiceUnavailableError` → `RetryableTransient`
- `litellm.BadRequestError`, `litellm.AuthenticationError`, `litellm.NotFoundError`, `litellm.ContextWindowExceededError` → `NonRetryable`
- `subprocess.TimeoutExpired` → `RetryableTransient`
- `subprocess.CalledProcessError` with specific return codes → `NonRetryable` unless the stderr matches a known transient pattern (flagged for M2 refinement)
- Anything else → `NonRetryable`

No `ModelRetry` import. Pydantic `ValidationError` is *not* auto-classified here — M2's `ValidatorNode` raises `RetryableSemantic` explicitly after catching it.

### Test updates

`tests/primitives/test_retry.py`:

- Classifier table-driven test per exception type.
- `RetryPolicy` default-values test.
- Sanity check: no `pydantic_ai` or `ModelRetry` references.

## Acceptance Criteria

- [ ] Three taxonomy classes exported from `primitives.retry`.
- [ ] `classify()` covers every LiteLLM error class listed above.
- [ ] `grep -r "ModelRetry" ai_workflows/ tests/` returns zero matches.
- [ ] `uv run pytest tests/primitives/test_retry.py` green.
- [ ] `uv run pytest` green overall.

## Dependencies

- [Task 03](task_03_remove_llm_substrate.md) — pydantic-ai removal enables ModelRetry deletion.
- [Task 02](task_02_dependency_swap.md) — `litellm` must be installed so its exception types import.
