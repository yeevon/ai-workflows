# Task 02 — Claude Code Planner Tier Refit — Audit Issues

**Source task:** [../task_02_claude_code_planner.md](../task_02_claude_code_planner.md)
**Audited on:** 2026-04-20
**Audit scope:** `ai_workflows/workflows/planner.py` (synth tier),
`tests/workflows/test_planner_synth_claude_code.py` (new),
`tests/workflows/test_planner_explorer_qwen.py` (T01 test re-shaped
after synth flip), `tests/cli/conftest.py` + `tests/mcp/conftest.py`
(new registry-override fixtures), `ai_workflows/graph/tiered_node.py`
(dispatch path verified, no edit), full gate, architecture drift check
(§4.1 provider drivers, §4.3 two-phase planner, KDR-003, KDR-004,
KDR-007), CHANGELOG placement.
**Status:** ✅ PASS — 7/7 ACs green, no design drift, no open issues.

## Design-drift check

Cross-referenced against [architecture.md](../../../architecture.md) +
cited KDRs. No drift found:

- **New dependency?** No. `ClaudeCodeRoute` + `ClaudeCodeSubprocess`
  both exist since M2 T02. No `pyproject.toml` edits.
- **New module / layer?** No. Two production files touched
  (`planner.py` + the two new test conftests); four-layer contract
  unchanged (`uv run lint-imports` 3 / 3 kept).
- **LLM call added?** No new node — T02 repoints an existing
  `TieredNode` (`planner`) to a different route kind. The paired
  `planner_validator` (KDR-004) was shipped in M3 T03 and is untouched.
- **KDR-003 (no Anthropic API).** Verified by a new start-of-line
  regex test that ignores docstring prose and matches only
  `^\s*import anthropic` / `^\s*from anthropic`. Both `planner.py`
  and `claude_code.py` pass. `ANTHROPIC_API_KEY` substring search
  returns zero hits in both files.
- **KDR-007 (LiteLLM for hosted; bespoke for OAuth subprocess).**
  The route-kind dispatch already lands `ClaudeCodeRoute` on
  `ClaudeCodeSubprocess` via [`tiered_node.py:345-353`](../../../../ai_workflows/graph/tiered_node.py#L345-L353).
  T02 reads but does not edit that dispatch, matching the spec's
  "read … confirm the dispatch path exists" direction.
- **KDR-004 (validator pairing).** Unchanged. The graph still wires
  `planner → planner_validator → gate` per M3 T03 — no node was added
  or removed.
- **KDR-009 (LangGraph checkpointer).** Untouched.
- **KDR-006 (three-bucket retry).** Untouched. `classify()` already
  buckets `subprocess.TimeoutExpired` → `RetryableTransient` and
  `CalledProcessError` → `NonRetryable` since M1 T07 — the T02 route
  change inherits both paths for free.

Verdict: no drift. No HIGH / MEDIUM / LOW issues raised.

## AC grading

| #   | AC                                                                                      | Status | Evidence                                                                                                                                                                                                                                                                                                                  |
| --- | --------------------------------------------------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `planner-synth` route = `ClaudeCodeRoute(cli_model_flag="opus")`, `max_concurrency=1`   | ✅      | `planner.py:389-395` matches spec verbatim. Pinned by `test_planner_synth_tier_points_at_claude_code_opus` (includes `per_call_timeout_s=300` guard).                                                                                                                                                                    |
| 2   | Hermetic full-graph pass — Qwen explorer + Claude Code synth → gate with valid `PlannerPlan` | ✅      | `test_graph_completes_with_claude_code_synth_and_rolls_up_submodels`. Both stubs register exactly one call (`_StubLiteLLMAdapter.call_count == 1`, `_StubClaudeCodeSubprocess.call_count == 1`); gate interrupt reached; `PlannerPlan` + `ExplorerReport` both parsed by validators.                                     |
| 3   | `modelUsage` sub-model rollup — primary + sub land in `TokenUsage.sub_models`; total matches | ✅      | Same test: `_opus_with_haiku_usage()` builds a `TokenUsage(model="claude-opus-4-7", cost_usd=0.02, sub_models=[TokenUsage("claude-haiku-4-5", cost=0.0004)])`; `tracker.total() == pytest.approx(0.0204)`; `tracker.by_model()` reports both keys with the exact split costs.                                         |
| 4   | No `anthropic` SDK import introduced (KDR-003)                                         | ✅      | `test_no_anthropic_sdk_import_in_planner_or_claude_code_driver` uses start-of-line `re.MULTILINE` matching for `import anthropic` / `from anthropic`, plus substring for `ANTHROPIC_API_KEY`. Both files clean.                                                                                                            |
| 5   | `uv run pytest tests/workflows/` green                                                 | ✅      | 38 tests passed (28 planner-module tests + 4 T01 qwen + 4 T02 claude_code + 2 registry + scaffolding). Full suite: 340 passed / 1 skipped (up from 336 / 1 at M5 T01 close).                                                                                                                                              |
| 6   | `uv run lint-imports` 3 / 3 kept                                                       | ✅      | `Contracts: 3 kept, 0 broken.`                                                                                                                                                                                                                                                                                            |
| 7   | `uv run ruff check` clean                                                              | ✅      | `All checks passed!` (one auto-fix for import ordering applied before gate run.)                                                                                                                                                                                                                                          |

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

None.

## Additions beyond spec — audited and justified

1. **T01 explorer-regression assertion in T02's test file** (`test_planner_explorer_tier_kept_on_qwen_after_t02`). Guards against a T02 Builder accidentally clobbering T01's explorer edit while flipping synth. Zero coupling cost; would catch a real regression class.

2. **`tests/cli/conftest.py` + `tests/mcp/conftest.py` autouse registry-stub fixtures.** Not named in the T02 spec, but forced by T02's fundamental change: the production `planner_tier_registry()` is now heterogeneous, so every pre-M5 CLI/MCP test that stubbed `LiteLLMAdapter` alone would silently route synth through the real `claude` subprocess (real OAuth quota, slow, non-hermetic). Three of the MCP tests outright failed on cost assertions; one CLI test file silently spent OAuth quota on every run. The conftest fixtures pin the registry back to all-LiteLLM so the pre-T02 hermetic contract is preserved. Scope-creep analysis: the fixtures are a necessary consequence of T02's registry change; without them T02 would land a silent test-integrity regression. Surfaced in the CHANGELOG "Files touched" list as a deviation from spec.

3. **Re-shaping of T01's `test_planner_synth_tier_still_points_at_gemini_flash`.** Its assertion became false after T02 (expected). Replaced with `test_planner_explorer_tier_independent_of_synth` — a copy-paste guard that still fires when explorer and synth are accidentally aliased. Preserves the AC-2 spirit (distinct tiers, no accidental sharing) in a T02-compatible form. Also refactored the hermetic graph test to use a locally-inlined `_explorer_focused_registry()` rather than the global helper, so T01's graph-run test remains T01-scoped.

All three additions are necessary-consequence edits, not scope creep. They are explicitly called out in the T02 CHANGELOG entry's "Files touched" section.

## Gate summary

| Gate                                          | Result                                       |
| --------------------------------------------- | -------------------------------------------- |
| `uv run pytest`                               | ✅ 340 passed, 1 skipped                     |
| `uv run pytest tests/workflows/`              | ✅ 38 passed                                  |
| `uv run pytest tests/cli/` (hermetic re-verify) | ✅ passes — synth no longer spawns `claude`    |
| `uv run pytest tests/mcp/` (hermetic re-verify) | ✅ passes — cost assertions back to 0.0033    |
| `uv run lint-imports`                         | ✅ 3 / 3 kept                                 |
| `uv run ruff check`                           | ✅ clean                                      |
| KDR-003 regression (`anthropic` SDK grep)     | ✅ no imports; no API-key reads              |

## Issue log — cross-task follow-up

None raised; no forward-deferrals.

## Propagation status

No forward-deferrals. Nothing to propagate to later tasks.
