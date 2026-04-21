# Task 01 — Qwen Explorer Tier Refit — Audit Issues

**Source task:** [../task_01_qwen_explorer.md](../task_01_qwen_explorer.md)
**Audited on:** 2026-04-20
**Audit scope:** `ai_workflows/workflows/planner.py` (tier registry),
`tests/workflows/test_planner_explorer_qwen.py` (new), full pytest +
lint-imports + ruff gates, architecture drift check (§4.3, KDR-003,
KDR-004, KDR-007, KDR-010 / ADR-0002), CHANGELOG placement.
**Status:** ✅ PASS — all 8 ACs green, no design drift, no open issues.

## Design-drift check

Cross-referenced against [architecture.md](../../../architecture.md) +
cited KDRs. No drift found:

- **New dependency?** No. `ollama/qwen2.5-coder:32b` is routed through
  the existing `LiteLLMAdapter` (already in `pyproject.toml` via M2 T01),
  and Ollama itself is listed in [architecture.md §6 line 131](../../../architecture.md)
  and explicitly cited in KDR-007. No import-linter additions.
- **New module / layer?** No. Only two files touched: the existing
  `ai_workflows/workflows/planner.py` (tier registry edit + docstring)
  and a new test file under `tests/workflows/` (mirrors package path).
  `primitives → graph → workflows → surfaces` contract unchanged.
- **LLM call added?** No new node — T01 only repoints an existing
  `TieredNode` (`explorer`) to a different route. The paired
  `explorer_validator` (KDR-004) was shipped in M3 T03 and is untouched.
- **KDR-003 (no Anthropic API).** Verified by grep: the only match for
  `anthropic` in `planner.py` is in the module docstring as a
  *prohibition* ("never … imports the `anthropic` SDK"). The pre-existing
  regression test `test_planner_module_has_no_anthropic_surface` in
  `test_planner_graph.py` still passes.
- **KDR-007 (LiteLLM adapts Qwen via Ollama).** The new route uses
  `LiteLLMRoute(model="ollama/qwen2.5-coder:32b", api_base="http://localhost:11434")`.
  This matches architecture.md §6 line 130 ("LiteLLM … uses Ollama's
  HTTP endpoint for Qwen") and the `LiteLLMRoute.api_base` field is
  exactly the field the architecture cites (see `tiers.py:64`).
- **KDR-010 / ADR-0002 (bare-typed response schemas).** No schema
  change. `ExplorerReport` retains the same `min_length`/`max_length`
  bounds it has carried since M3 T02 — those are fine on the explorer
  schema because `ExplorerReport` was never in the failing Gemini
  structured-output path (that was `PlannerPlan`, fixed at M3 T07b).
  Leaving `ExplorerReport` alone matches the T01 spec's "Do **not**
  pre-emptively rewrite" direction.
- **Retry logic.** T01 did not add bespoke retry logic. `classify()`
  already covers `litellm.APIConnectionError → RetryableTransient` as
  of M1 T04 (`retry.py:111-116`), and the new test pins that
  contract explicitly.
- **Checkpoint / observability.** Untouched.

Verdict: no drift. No HIGH, MEDIUM, or LOW issues raised.

## AC grading

| #   | AC                                                                                                   | Status | Evidence                                                                                                                                                                              |
| --- | ---------------------------------------------------------------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `planner_tier_registry()["planner-explorer"]` has `ollama/qwen2.5-coder:32b` + `api_base` + `max_concurrency=1` | ✅      | `planner.py:373-381` matches spec verbatim. Pinned by `test_planner_explorer_tier_points_at_qwen_via_ollama`.                                                                         |
| 2   | `planner_tier_registry()["planner-synth"]` unchanged (still Gemini Flash)                           | ✅      | `planner.py:382-387` unchanged. Pinned by `test_planner_synth_tier_still_points_at_gemini_flash`.                                                                                     |
| 3   | Hermetic test passes the full graph through to the gate with Qwen-shape explorer output              | ✅      | `test_graph_completes_to_gate_with_qwen_shape_explorer_output` — both validators parse cleanly, graph reaches `HumanGate` interrupt, `call_count == 2`.                              |
| 4   | Retry-classification test: Ollama connection errors → `RetryableTransient`                          | ✅      | `test_ollama_api_connection_error_classifies_as_transient` explicitly constructs `litellm.APIConnectionError(llm_provider="ollama")` and asserts `classify(exc) is RetryableTransient`. |
| 5   | No `anthropic` import, no `ANTHROPIC_API_KEY` read (KDR-003 regression)                             | ✅      | Pre-existing `test_planner_module_has_no_anthropic_surface` still green. Grep confirms the only `anthropic` hit is the docstring prohibition.                                         |
| 6   | `uv run pytest tests/workflows/` green                                                              | ✅      | 34 passed (`test_planner_explorer_qwen.py` 4 + `test_planner_graph.py` 9 + `test_planner_schemas.py` 12 + `test_registry.py` 9). Full suite: 336 passed / 1 skipped.                  |
| 7   | `uv run lint-imports` 3 / 3 kept                                                                    | ✅      | `Contracts: 3 kept, 0 broken.`                                                                                                                                                        |
| 8   | `uv run ruff check` clean                                                                           | ✅      | `All checks passed!`                                                                                                                                                                  |

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

None.

## Additions beyond spec — audited and justified

- **Second-tier assertion (`test_planner_synth_tier_still_points_at_gemini_flash`).** Not strictly in the spec's bullet list, but guards AC-2 ("planner-synth remains unchanged") and catches the exact error a misdirected T02 Builder would make (flipping synth in T01 instead of its own task). Low-cost, high-value regression guard. Kept.
- **`max_concurrency` + `per_call_timeout_s` assertions in tier test.** The spec's AC-1 only requires `max_concurrency=1` explicitly, but pinning `per_call_timeout_s=180` too prevents a silent regression to the hosted defaults (60s / 90s). Zero coupling cost.

## Gate summary

| Gate                                  | Result                                     |
| ------------------------------------- | ------------------------------------------ |
| `uv run pytest`                       | ✅ 336 passed, 1 skipped                   |
| `uv run pytest tests/workflows/`      | ✅ 34 passed                                |
| `uv run lint-imports`                 | ✅ 3 / 3 kept                              |
| `uv run ruff check`                   | ✅ clean                                    |
| KDR-003 regression (`anthropic` grep) | ✅ only docstring prohibition match         |

## Issue log — cross-task follow-up

None.

## Propagation status

No forward-deferrals. Nothing to propagate.
