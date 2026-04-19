# Task 09 — StructuredLogger Sanity Pass

**Status:** 📝 Planned.

## What to Build

Confirm `ai_workflows/primitives/logging.py` emits the record shape [architecture.md §8.1](../../architecture.md) specifies. Remove any pydantic-ai-specific context assumptions. This is a short task — expect ≤ 50 LOC of change.

## Deliverables

### `ai_workflows/primitives/logging.py`

Record schema target (exact field names):

- `run_id: str`
- `workflow: str`
- `node: str`
- `tier: str`
- `provider: str`  (`"litellm"` or `"claude_code"`)
- `model: str`
- `duration_ms: int`
- `input_tokens: int`
- `output_tokens: int`
- `cost_usd: float`

Any field unknown at emit time (e.g. `cost_usd` before LiteLLM enrichment) emits `None`, not a placeholder. No `logfire` import unless [task 01 audit](task_01_reconciliation_audit.md) kept it.

### Test updates

`tests/primitives/test_logging.py`:

- One record per route-kind asserting every field above is present (or explicitly `None`).
- Assert `structlog` is the only backend consumed (no pydantic-ai, no logfire unless kept).

## Acceptance Criteria

- [ ] Log record carries every field listed above on emit.
- [ ] `grep -r "logfire" ai_workflows/` matches only if audit kept it; otherwise zero matches.
- [ ] `grep -r "pydantic_ai" ai_workflows/primitives/logging.py` returns zero matches.
- [ ] `uv run pytest tests/primitives/test_logging.py` green.

## Dependencies

- [Task 03](task_03_remove_llm_substrate.md).
