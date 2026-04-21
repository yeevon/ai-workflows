# Task 03 — Sub-Graph Composition Validation — Audit Issues

**Source task:** [../task_03_subgraph_composition.md](../task_03_subgraph_composition.md)
**Audited on:** 2026-04-20
**Audit scope:** `tests/workflows/test_planner_multitier_integration.py`
(new, the only file added by T03); production code under
`ai_workflows/` (unchanged — verified via `git status`);
`ai_workflows/workflows/planner.py` (no T03 delta; last-edited by T02);
`ai_workflows/graph/retrying_edge.py` +
`ai_workflows/graph/error_handler.py` (retry-counter semantics
cross-check for AC-3's semantic edge); `ai_workflows/primitives/retry.py`
(three-bucket `classify()`); CHANGELOG placement; CI gates;
architecture drift check (§3 four-layer, §4.3 two-phase planner,
§8.2 topology, KDR-003, KDR-004, KDR-006, KDR-009); sibling issue
files [`task_01_issue.md`](task_01_issue.md) + [`task_02_issue.md`](task_02_issue.md)
for continuity.
**Status:** ✅ PASS — 8/8 ACs green, no design drift, no open issues.

## Design-drift check

Cross-referenced against [architecture.md](../../../architecture.md)
and the cited KDRs. No drift found:

- **New dependency?** None. `litellm` (for the explorer transient
  retry's `APIConnectionError`) is already in `pyproject.toml` since
  M2 T01. `subprocess` (for the planner transient retry's
  `TimeoutExpired`), `json`, and `pathlib` are stdlib. Zero
  `pyproject.toml` edits — T03 is a pure integration pass.
- **New module / layer?** None. The single new file lives under
  `tests/workflows/`, mirroring the package path. Four-layer contract
  kept (`primitives → graph → workflows → surfaces`, 3 / 3 kept).
- **LLM call added?** None. T03 exercises the M3 T03 `TieredNode` +
  `ValidatorNode` pairs (`explorer` / `explorer_validator`,
  `planner` / `planner_validator`) in place; no new node added,
  no KDR-004 pairing broken.
- **KDR-003 (no Anthropic API).** Clean. Grep
  `^\s*(?:import|from)\s+anthropic|ANTHROPIC_API_KEY` across
  `ai_workflows/**/*.py` returns zero hits. The new test file uses
  the production `planner_tier_registry()` verbatim (Qwen explorer +
  `ClaudeCodeRoute` synth) and never touches the SDK.
- **KDR-004 (validator pairing).** Unchanged. The graph still wires
  `explorer → explorer_validator` and `planner → planner_validator`
  per M3 T03 — no node was added or removed.
- **KDR-006 (three-bucket retry).** Verified in two directions:
  (a) the explorer transient test injects `litellm.APIConnectionError`,
  which `classify()` at `retry.py:61` routes to `RetryableTransient`;
  (b) the planner transient test injects `subprocess.TimeoutExpired`,
  which `classify()` at `retry.py:57-58` also routes to
  `RetryableTransient`. Both run through the same
  `retrying_edge(on_transient=<self>)` wiring, confirming the
  bucket taxonomy covers both provider families uniformly.
- **KDR-009 (LangGraph checkpointer).** Untouched.
  `build_async_checkpointer(tmp_path / "cp.sqlite")` is consumed
  as-is; no hand-rolled checkpoint writes.

Verdict: no drift. No HIGH / MEDIUM / LOW issues raised.

## AC grading

| #   | AC                                                                                                     | Status | Evidence                                                                                                                                                                                                                                                                                                                                                |
| --- | ------------------------------------------------------------------------------------------------------ | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Integration drives full six-node topology end-to-end with valid `PlannerPlan` + expected interrupt     | ✅      | `test_planner_multitier_integration.py:260-280` (`test_full_hermetic_end_to_end_mixed_providers`) — asserts `__interrupt__` in paused payload, `isinstance(paused["plan"], PlannerPlan)`, `isinstance(paused["explorer_report"], ExplorerReport)`, both stubs register exactly one call.                                                           |
| 2   | Cross-provider transient retry — Ollama `APIConnectionError` on explorer self-loops once and completes | ✅      | `test_planner_multitier_integration.py:287-315` — script is `[APIConnectionError, (valid_json, 0.0)]`; asserts `_retry_counts == {"explorer": 1}` + `_non_retryable_failures == 0` + litellm call_count=2.                                                                                                                                              |
| 3   | Cross-provider transient retry — `TimeoutExpired` on planner self-loops once and completes             | ✅      | `test_planner_multitier_integration.py:323-347` — script is `[TimeoutExpired(cmd=["claude"], timeout=300.0), (plan_json, usage)]`; asserts `_retry_counts == {"planner": 1}` + `_non_retryable_failures == 0` + claude call_count=2.                                                                                                                    |
| 4   | Semantic retry (malformed JSON) routes via `explorer_validator` → `explorer`                           | ✅      | `test_planner_multitier_integration.py:355-386` — script is `[invalid_json (missing considerations), valid_json]`; asserts `_retry_counts["explorer_validator"] == 1` + litellm call_count=2. Counter semantics cross-verified against `error_handler.py:149-157` (wrapper bumps the *wrapped* node's counter; matches sibling pattern at `test_planner_graph.py:404`). |
| 5   | Mixed-provider cost rollup — Qwen primary + Opus primary + Haiku sub all land in `CostTracker`         | ✅      | `test_planner_multitier_integration.py:394-421` — `tracker.total("run-m5-t03-rollup") == pytest.approx(0.0153)` (= 0.0 + 0.0150 + 0.0003); `by_model` returns all three model IDs with exact split.                                                                                                                                                   |
| 5b  | No unplanned topology changes to `build_planner()`                                                     | ✅      | `test_planner_multitier_integration.py:242-252` pins the six-node set (`explorer`, `explorer_validator`, `planner`, `planner_validator`, `gate`, `artifact`); `git diff ai_workflows/` shows no T03 delta.                                                                                                                                              |
| 6   | `uv run pytest tests/workflows/` green                                                                 | ✅      | 346 passed / 1 skipped (up from 340 / 1 at M5 T02 — six new tests).                                                                                                                                                                                                                                                                                    |
| 7   | `uv run lint-imports` 3 / 3 kept                                                                       | ✅      | `Contracts: 3 kept, 0 broken.`                                                                                                                                                                                                                                                                                                                         |
| 8   | `uv run ruff check` clean                                                                              | ✅      | `All checks passed!` (one auto-fix for import ordering on the new file before gate run.)                                                                                                                                                                                                                                                                |

## Production-code cross-checks

- **Registry still returns both tiers T03 relies on.** Verified at
  `planner.py:381-397`: `planner-explorer` =
  `LiteLLMRoute(model="ollama/qwen2.5-coder:32b",
  api_base="http://localhost:11434")`; `planner-synth` =
  `ClaudeCodeRoute(cli_model_flag="opus")`. T01 + T02 outputs both
  intact — no silent regression.
- **Retry-counter semantics.** `wrap_with_error_handler`
  (`error_handler.py:149-157`) bumps `_retry_counts[node_name]` on
  the *wrapped* node when that node raises. The validator itself
  raises `RetryableSemantic` on schema failure, so
  `explorer_validator`'s counter bumps — then
  `retrying_edge(on_semantic="explorer")` at `planner.py:309-314`
  routes upstream to the LLM node. T03's AC-4 assertion is
  correct and matches the sibling pattern in
  `test_planner_graph.py:404` (`_retry_counts["planner_validator"]
  == 1`) for the planner-side semantic retry.
- **CHANGELOG.** `CHANGELOG.md:10-70` contains the T03 entry under
  `[Unreleased]`: integration-only scope call-out, all six tests
  enumerated, AC-to-test mapping, gate snapshot. Accurate.
- **CI.** `.github/workflows/ci.yml` runs `uv run pytest` with no
  path filter; `tests/workflows/` is part of the gate.

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

None.

## Additions beyond spec — audited and justified

1. **Topology guard test** (`test_topology_unchanged_six_nodes_as_shipped_by_m3_t03`).
   Not named as an explicit AC in the task spec, but AC-5 reads
   "No unplanned topology changes to `build_planner()`; if any are
   required, raise as a scope question first." The topology guard
   is the direct test for that AC — a diff-only check would fail
   silently if a future refactor renamed a node. Zero coupling
   cost; the node set is a small, stable invariant per
   architecture.md §8.2.

2. **`_non_retryable_failures == 0` side-assertion** in both
   transient-retry tests. Guards against a regression where a
   retry path silently promotes a transient into a non-retryable
   via mis-classification (e.g. if a future `classify()` edit
   accidentally downgraded `APIConnectionError` or
   `TimeoutExpired`). The assertion is free — the state key is
   already maintained by `wrap_with_error_handler` — and it makes
   the KDR-006 bucket contract test-visible from the integration
   layer.

Both additions are necessary-consequence test scaffolding for the
ACs as written, not scope creep.

## Gate summary

| Gate                                          | Result                                       |
| --------------------------------------------- | -------------------------------------------- |
| `uv run pytest`                               | ✅ 346 passed, 1 skipped                     |
| `uv run pytest tests/workflows/`              | ✅ all green (includes 6 new tests)          |
| `uv run lint-imports`                         | ✅ 3 / 3 kept                                 |
| `uv run ruff check`                           | ✅ All checks passed!                        |
| KDR-003 regression (grep `anthropic` + key)   | ✅ zero hits across `ai_workflows/`          |
| Production-code diff (`git diff ai_workflows/` scoped to T03) | ✅ empty — integration-only scope genuine |

## Issue log — cross-task follow-up

None raised; no forward-deferrals.

## Propagation status

No forward-deferrals. Nothing to propagate to later tasks.
