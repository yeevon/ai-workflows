# Task 02 — Claude Code Subprocess Driver

**Status:** 📝 Planned.

## What to Build

Production-grade `ClaudeCodeSubprocess` driver that invokes `claude -p --output-format json`, parses the structured output, and emits `TokenUsage` records including a `modelUsage` sub-model entry for every internal haiku sub-call observed during the M1 Task 13 spike. Handles timeouts and non-zero exits via the 3-bucket taxonomy from M1 [task 07](../milestone_1_reconciliation/task_07_refit_retry_policy.md).

## Deliverables

### `ai_workflows/primitives/llm/claude_code.py`

```python
class ClaudeCodeSubprocess:
    def __init__(self, route: ClaudeCodeRoute, per_call_timeout_s: int, pricing: PricingTable): ...

    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict],
        response_format: type[BaseModel] | None = None,
    ) -> tuple[str, TokenUsage]:
        """Spawn `claude -p --model <cli_model_flag> --output-format json`.
        Feed the prompt via stdin. Parse stdout JSON.
        Build TokenUsage from the top-level tokens and a sub_models list from modelUsage."""
```

- Subprocess launch via `asyncio.create_subprocess_exec`.
- `subprocess.TimeoutExpired` raised on per-call timeout — classified as `RetryableTransient`.
- Non-zero exit: stderr captured; mapped via M1 [task 07](../milestone_1_reconciliation/task_07_refit_retry_policy.md) `classify()`.
- Cost computation uses `pricing.yaml` (Claude Code entries) — LiteLLM does not cover this path.

### Reference

Port the validated behaviour from the M1 Task 13 spike findings (see `scripts/spikes/` in the working tree). The spike proved the JSON output shape and the haiku sub-call observation.

### Tests

`tests/primitives/llm/test_claude_code.py`:

- Fake subprocess fixture returning canned JSON → `TokenUsage` parses correctly including `sub_models`.
- Timeout → raises what `classify()` will bucket as `RetryableTransient`.
- Non-zero exit with known stderr → raises what `classify()` will bucket as `NonRetryable`.

## Acceptance Criteria

- [ ] Driver returns `(str, TokenUsage)` with `sub_models` populated when `modelUsage` is present in the JSON.
- [ ] Cost computed from `pricing.yaml` for the top-level and every sub-model row.
- [ ] Timeouts and non-zero exits bucket correctly via `classify()`.
- [ ] No `ANTHROPIC_API_KEY` lookup anywhere (KDR-003).
- [ ] `uv run pytest tests/primitives/llm/test_claude_code.py` green.

## Dependencies

- M1 [task 06](../milestone_1_reconciliation/task_06_refit_tier_config.md) (`ClaudeCodeRoute`).
- M1 [task 07](../milestone_1_reconciliation/task_07_refit_retry_policy.md) (`classify()`).
- M1 [task 08](../milestone_1_reconciliation/task_08_prune_cost_tracker.md) (`TokenUsage` with `sub_models`).
