# Task 01 — Qwen Explorer Tier Refit

**Status:** 📝 Planned.

## What to Build

Repoint the [`planner-explorer` tier](../../../ai_workflows/workflows/planner.py#L372) from Gemini Flash (`LiteLLMRoute(model="gemini/gemini-2.5-flash")`) to local Qwen via Ollama (`LiteLLMRoute(model="ollama/qwen2.5-coder:32b")`). Prompt-tune [`_explorer_prompt`](../../../ai_workflows/workflows/planner.py) if needed so Qwen produces a valid [`ExplorerReport`](../../../ai_workflows/workflows/planner.py) under the bare-typed KDR-010 schema. Scope is the explorer half only — the planner tier moves to Claude Code in [T02](task_02_claude_code_planner.md).

Aligns with [architecture.md §4.3](../../architecture.md) (two-phase planner), KDR-007 (LiteLLM adapts Qwen via Ollama), KDR-010 / ADR-0002 (bare-typed response schemas).

## Deliverables

### `ai_workflows/workflows/planner.py` — tier registry

Update `planner_tier_registry()` to repoint `planner-explorer`:

```python
"planner-explorer": TierConfig(
    name="planner-explorer",
    route=LiteLLMRoute(
        model="ollama/qwen2.5-coder:32b",
        api_base="http://localhost:11434",
    ),
    max_concurrency=1,  # single local model, no concurrency win
    per_call_timeout_s=180,  # local inference is slower than hosted
),
```

Keep `planner-synth` pointed at Gemini Flash for this task; T02 moves it to Claude Code. `planner-explorer` + `planner-synth` can legitimately ride different providers under the single-phase planner during the M5 interim commits.

### `_explorer_prompt` adjustment (only if tests force it)

Do **not** pre-emptively rewrite the prompt. Land the tier change + run the hermetic tests first. If Qwen's `ExplorerReport` JSON fails to validate on a stub-replayed real-world output, add minimal prompt guidance (e.g. `"Return ONLY a JSON object matching the schema — no commentary."`). Document any prompt delta in the CHANGELOG entry with a one-line reason.

### Tests

`tests/workflows/test_planner_explorer_qwen.py` (new):

- `planner_tier_registry()` returns `planner-explorer.route.model == "ollama/qwen2.5-coder:32b"` and `api_base` set.
- Hermetic graph run: replay a recorded Qwen-shape `ExplorerReport` JSON blob through `_StubLiteLLMAdapter` for the explorer tier, Gemini Flash shape for the planner tier. Assert the graph completes up to the gate and the validator extracts a parseable `ExplorerReport`.
- Retry taxonomy spot check: a simulated Ollama `APIConnectionError` (common when the daemon is down) classifies as `RetryableTransient` via [`classify()`](../../../ai_workflows/primitives/retry.py), not `NonRetryable`.

## Acceptance Criteria

- [ ] `planner_tier_registry()["planner-explorer"]` has `LiteLLMRoute(model="ollama/qwen2.5-coder:32b", api_base=...)` and `max_concurrency=1`.
- [ ] `planner_tier_registry()["planner-synth"]` remains unchanged (still Gemini Flash). Interim state; T02 flips it.
- [ ] Hermetic test passes the full graph through to the gate with Qwen-shape explorer output and Gemini-shape planner output.
- [ ] Retry-classification test confirms Ollama connection errors route to `RetryableTransient`.
- [ ] No `anthropic` import, no `ANTHROPIC_API_KEY` read (KDR-003 regression guard).
- [ ] `uv run pytest tests/workflows/` green.
- [ ] `uv run lint-imports` 3 / 3 kept.
- [ ] `uv run ruff check` clean.

## Dependencies

- [Task 07a (M3)](../milestone_3_first_workflow/task_07a_planner_structured_output.md) — `output_schema=` plumbing on `tiered_node(...)` must already forward to Ollama via LiteLLM (verify this assumption in the Builder's first read).
- Ollama daemon is **not** required for hermetic tests (stubbed). Live verification lands in [T06](task_06_e2e_smoke.md).
