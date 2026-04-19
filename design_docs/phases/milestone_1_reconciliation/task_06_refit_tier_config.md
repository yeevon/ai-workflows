# Task 06 — Refit TierConfig + tiers.yaml

**Status:** 📝 Planned.

## What to Build

Update `TierConfig`'s schema so each tier declares one of two route types — LiteLLM-backed or Claude Code subprocess — matching [architecture.md §4.1](../../architecture.md). Rewrite `tiers.yaml` to the new shape. Keep `pricing.yaml` for the Claude Code route (LiteLLM's built-in pricing covers its own routes).

## Deliverables

### `ai_workflows/primitives/tiers.py`

New pydantic model shape:

```python
class LiteLLMRoute(BaseModel):
    kind: Literal["litellm"] = "litellm"
    model: str  # e.g. "gemini/gemini-2.0-flash", "ollama/qwen2.5-coder:14b"
    api_base: str | None = None  # set for Ollama

class ClaudeCodeRoute(BaseModel):
    kind: Literal["claude_code"] = "claude_code"
    cli_model_flag: str  # e.g. "opus", "sonnet", "haiku"

Route = Annotated[LiteLLMRoute | ClaudeCodeRoute, Field(discriminator="kind")]

class TierConfig(BaseModel):
    name: str
    route: Route
    max_concurrency: int = 1
    per_call_timeout_s: int = 120
```

`TierRegistry.load(path)` parses `tiers.yaml` into `dict[str, TierConfig]`.

### `tiers.yaml`

```yaml
planner:
  route:
    kind: litellm
    model: gemini/gemini-2.0-flash
  max_concurrency: 2
  per_call_timeout_s: 180

implementer:
  route:
    kind: litellm
    model: gemini/gemini-2.0-flash
  max_concurrency: 2

local_coder:
  route:
    kind: litellm
    model: ollama/qwen2.5-coder:14b
    api_base: http://localhost:11434
  max_concurrency: 1

opus:
  route:
    kind: claude_code
    cli_model_flag: opus
  max_concurrency: 1
  per_call_timeout_s: 600

sonnet:
  route:
    kind: claude_code
    cli_model_flag: sonnet
  max_concurrency: 1

haiku:
  route:
    kind: claude_code
    cli_model_flag: haiku
  max_concurrency: 2
```

Exact tier names are final only pending [task 01 audit](task_01_reconciliation_audit.md) confirmation.

### `pricing.yaml`

Reduced to Claude Code CLI entries only (LiteLLM's pricing table covers the rest). Values can stay as-is from the pre-pivot file if the audit confirms they were never LiteLLM-sourced.

## Acceptance Criteria

- [ ] `tiers.yaml` parses into `dict[str, TierConfig]` without errors.
- [ ] Each tier's route validates as either `LiteLLMRoute` or `ClaudeCodeRoute`.
- [ ] `pricing.yaml` contains only Claude Code CLI entries.
- [ ] `tests/primitives/test_tiers.py` covers: discriminator round-trip, unknown-tier lookup, malformed YAML rejection.
- [ ] `uv run pytest` green.

## Dependencies

- [Task 03](task_03_remove_llm_substrate.md) — pydantic-ai `Model` references must be gone before new loader replaces them.
