# Task 06 — CostTrackingCallback — Audit Issues

**Source task:** [../task_06_cost_callback.md](../task_06_cost_callback.md)
**Audited on:** 2026-04-19
**Audit scope:** `ai_workflows/graph/cost_callback.py`, `tests/graph/test_cost_callback.py`, `CHANGELOG.md` unreleased entry, cross-checked against [architecture.md §3 / §4.1 / §4.2 / §8.2 / §8.5](../../../architecture.md), KDR-004 and the three-bucket taxonomy (§8.2). Sibling tasks T03 (TieredNode — the sole invoker per spec) and T04 (ValidatorNode — the KDR-004 pairing) reviewed for contract alignment. M1 Task 07 (`NonRetryable`) and M1 Task 08 (`CostTracker` / `TokenUsage`) re-verified as the primitives substrate.
**Status:** ✅ PASS on T06's explicit ACs (AC-1..AC-3 all met, no OPEN issues).

## Design-drift check

| Axis | Verdict | Evidence |
| --- | --- | --- |
| New dependency | None | No new entries in [pyproject.toml](../../../../pyproject.toml). Module imports only `ai_workflows.primitives.cost.{CostTracker, TokenUsage}` — no LangGraph, no LiteLLM, no anthropic, no observability backends. |
| Four-layer contract | KEPT | `import-linter` reports 3 / 3 contracts kept, 0 broken (17 files / 8 deps analyzed). New module lives in `ai_workflows.graph` and imports only from `ai_workflows.primitives`. |
| LLM call present? | No | Zero `litellm` / subprocess / `anthropic` imports in production module. `grep` clean on `ANTHROPIC_API_KEY`. The only `litellm`/`subprocess` token is a docstring paragraph referencing the provider drivers that feed this callback. KDR-004 does not apply — this is the cost-tracking boundary, not an LLM node. |
| KDR-003 compliance | Met | No Anthropic SDK import, no key lookup. |
| KDR-004 compliance | Met | This callback is downstream of the KDR-004 boundary: TieredNode runs → validator runs → callback stamps cost. Not a new LLM surface. |
| Checkpoint / resume logic | None | No `SqliteSaver` / `MemorySaver` / custom checkpoint writes. KDR-009 non-applicable. |
| Retry logic | None | No try/except, no retry loop. Budget breach raises `NonRetryable` straight from `CostTracker.check_budget` per the three-bucket taxonomy — `RetryingEdge` (T07) terminal bucket. |
| Observability | None | No `StructuredLogger` wired in — spec explicitly puts log emission on TieredNode (`task_03_tiered_node.md` step 5). No Langfuse / OTel / LangSmith creep. |
| Secrets | None read | Module reads nothing from env. |
| `nice_to_have.md` adoption | None | No items pulled in. |

No drift. Task passes the design-drift gate.

## AC grading

| AC | Verdict | Evidence |
| --- | --- | --- |
| AC-1 — Every `TieredNode` invocation results in exactly one `record` + one `check_budget` (when cap set) | ✅ | [ai_workflows/graph/cost_callback.py:103-105](../../../../ai_workflows/graph/cost_callback.py#L103-L105) body is exactly `self._tracker.record(run_id, usage)` then `self._tracker.check_budget(run_id, self._cap)` under a single `if self._cap is not None`. Pinned by [test_on_node_complete_runs_exactly_one_record_and_one_check_when_capped](../../../../tests/graph/test_cost_callback.py#L49-L58) via a `_RecordingTracker` that asserts both call counts are exactly 1. Complementary [test_no_cap_never_raises_and_never_checks_budget](../../../../tests/graph/test_cost_callback.py#L76-L85) pins the inverse — two invocations with a `None` cap produce two `record` calls and zero `check_budget` calls. |
| AC-2 — Budget enforcement uses `NonRetryable` from [architecture.md §8.2](../../../architecture.md) | ✅ | [ai_workflows/graph/cost_callback.py:105](../../../../ai_workflows/graph/cost_callback.py#L105) delegates to `CostTracker.check_budget`, which raises `NonRetryable` ([ai_workflows/primitives/cost.py:150-153](../../../../ai_workflows/primitives/cost.py#L150-L153)); callback does not wrap / swallow / re-bucket. Pinned by [test_budget_overage_raises_non_retryable](../../../../tests/graph/test_cost_callback.py#L61-L73) using `pytest.raises(NonRetryable, match="budget exceeded")`. The test also verifies the breaching row was recorded before the check fired — pair semantics match §8.5 ("checks budget after each node"). |
| AC-3 — `uv run pytest tests/graph/test_cost_callback.py` green | ✅ | 5 / 5 passed in 0.87s. Full suite: 189 passed in 2.73s. |

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

None.

## Additions beyond spec — audited and justified

1. **`node_name` parameter kept in signature but intentionally unused (marked `# noqa: ARG002`).**
   Spec's reference code snippet (`task_06_cost_callback.md` §Deliverables) does not show `node_name` entering the body, but the section introduction states "A LangGraph callback … routes `TokenUsage` records from provider calls into `CostTracker.record(run_id, usage)`, and checks the per-run budget cap after every node" and lists `on_node_complete(run_id, node_name, usage)` as the surface. Keeping the parameter matches the spec's declared surface; omitting the parameter would force TieredNode callers to branch on whether to pass it. The `# noqa: ARG002` comment makes the "kept-for-caller" status explicit and survives `uv run ruff check` cleanly. Justified — no new code path, just surface fidelity.
2. **Two tests beyond the spec's three** (spec lists: records through, budget cap exceeded raises, no cap never raises).
   - **`test_on_node_complete_runs_exactly_one_record_and_one_check_when_capped`** is the only test that directly pins AC-1's "exactly one record + one check_budget" contract — without it, the spec's AC would be observed only as a side-effect of the other tests. Keeps the invariant regression-proof.
   - **`test_cap_of_zero_is_enforced_and_any_spend_breaches`** pins the semantic disambiguation between `budget_cap_usd=None` (disabler) and `budget_cap_usd=0.0` (real zero cap). Architecture §8.5 says "default `None`" without clarifying `0.0`; the test pins the implementation's behaviour so a future "treat zero as sentinel" regression fails loudly.
   Both tests exercise existing production behaviour — no new code paths were introduced to satisfy them.
3. **`_RecordingTracker` subclass over `CostTracker` in tests.** Instrumentation-only — the subclass records call tuples and delegates to `super()` so the production path is still exercised. An alternative using `unittest.mock` wrappers was rejected because subclassing preserves the real `record` / `total` / `check_budget` semantics (critical for the breach test, which needs `total` to roll up correctly). Justified.

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 189 passed, 2 warnings (pre-existing `yoyo` datetime deprecation inside `SQLiteStorage.open`, unrelated to T06) in 2.73s |
| `uv run lint-imports` | ✅ 3 contracts kept, 0 broken (17 files, 8 deps analyzed) |
| `uv run ruff check` | ✅ All checks passed! |

## Issue log — cross-task follow-up

None. No deferrals; no cross-task findings.

## Deferred to nice_to_have

None.

## Propagation status

Not applicable. Task closed clean with no forward-deferred items.
