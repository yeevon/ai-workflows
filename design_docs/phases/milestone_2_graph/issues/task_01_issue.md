# Task 01 — LiteLLM Provider Adapter — Audit Issues

**Source task:** [../task_01_litellm_adapter.md](../task_01_litellm_adapter.md)
**Audited on:** 2026-04-19
**Audit scope:** `ai_workflows/primitives/llm/__init__.py`,
`ai_workflows/primitives/llm/litellm_adapter.py`,
`ai_workflows/primitives/__init__.py`,
`tests/primitives/llm/test_litellm_adapter.py`,
`CHANGELOG.md` (Unreleased §M2 Task 01), `pyproject.toml`,
`.github/workflows/ci.yml`,
[architecture.md](../../../architecture.md) (§3 layers, §4.1
primitives layer, §4.2 graph layer, §6 dependencies, §8.2 error
handling, §8.6 concurrency), KDR-003 / KDR-004 / KDR-006 / KDR-007,
sibling tasks [task_02](../task_02_claude_code_driver.md) and
[task_03](../task_03_tiered_node.md).
**Status:** ✅ **PASS** — all 5 ACs met; no OPEN issues; gates green
(pytest 160 passed / lint-imports 3 kept / ruff clean). Two LOW
observations logged for visibility; neither blocks cycle completion.

## Design-drift check — clean

Cross-referenced every change against `architecture.md` before grading
ACs:

| Drift vector | Finding |
| --- | --- |
| **New dependency?** | `litellm>=1.40` was already in [pyproject.toml](../../../../pyproject.toml) since M1 T02 (the dependency swap). No new package added by this task. Approved by KDR-007 + [architecture.md §6](../../../architecture.md). |
| **New module or layer?** | `primitives/llm/` is a new subpackage *inside* the existing primitives layer. The primitives layer is bedrock — nothing above it — and the subpackage adds no upward imports. Four-layer contract (`primitives → graph → workflows → surfaces`) kept. Confirmed by `uv run lint-imports` (3/3 contracts kept). |
| **LLM call added?** | The adapter *is* the provider driver the primitives layer has always been responsible for (architecture.md §4.1: "Provider drivers … both return `(text, TokenUsage)`"). It does not itself add an LLM call path to workflows/surfaces — that happens in M2 T03 via `TieredNode` + paired `ValidatorNode` per KDR-004. No KDR-004 violation at this layer. |
| **KDR-003 (no Anthropic API)?** | `grep "ANTHROPIC_API_KEY\|from anthropic\|import anthropic"` over `primitives/llm/` → 0 matches. The adapter only imports `litellm` + internal primitives. |
| **Checkpoint/resume logic?** | None. KDR-009 is out of scope for this task. |
| **Retry logic?** | The adapter carries **no** try/except and **no** retry loop. `max_retries=0` is forced at the LiteLLM call site so LiteLLM's internal loop is disabled too; the three-bucket taxonomy (KDR-006) runs above the adapter in `RetryingEdge` (M2 T07). Confirmed by grep for `try:`, `except`, `for … retry` → 0 matches in `litellm_adapter.py`. |
| **Observability?** | No new logging backend. `StructuredLogger` use arrives in M2 T03 (`TieredNode`), not here. No Langfuse / OTel / LangSmith imports. |

**Verdict:** no drift. No HIGH recorded.

## AC grading

| AC | Status | Evidence |
| --- | --- | --- |
| AC-1 — `complete()` returns `(str, TokenUsage)` | ✅ Pass | [litellm_adapter.py:62-97](../../../../ai_workflows/primitives/llm/litellm_adapter.py) returns the tuple; [test_litellm_adapter.py::test_complete_returns_text_and_token_usage](../../../../tests/primitives/llm/test_litellm_adapter.py) asserts every field mapping including `model`. |
| AC-2 — `TokenUsage.cost_usd` populated from LiteLLM enrichment | ✅ Pass | `_extract_usage` maps `response.usage.cost_usd` first, falls back to `_hidden_params["response_cost"]`. Three dedicated tests (`test_cost_usd_populated_from_usage`, `test_cost_usd_falls_back_to_hidden_params`, `test_cost_usd_defaults_to_zero_when_absent`) cover the three possible cost sources. |
| AC-3 — `max_retries=0` verified in a unit test | ✅ Pass | [test_litellm_adapter.py::test_max_retries_is_zero](../../../../tests/primitives/llm/test_litellm_adapter.py) inspects `stub.await_args.kwargs["max_retries"] == 0`. |
| AC-4 — no classification / retry logic inside adapter | ✅ Pass | grep over `litellm_adapter.py` returns zero `try:` / `except` / retry-loop lines. Pass-through tests (`test_rate_limit_error_passes_through`, `test_bad_request_error_passes_through`) confirm both a transient and a non-retryable LiteLLM exception surface verbatim. |
| AC-5 — `uv run pytest tests/primitives/llm/test_litellm_adapter.py` green | ✅ Pass | 12 passed in 0.88s locally; full suite 160 passed (was 148 pre-task). |

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 160 passed, 2 warnings (pre-existing yoyo DeprecationWarning from storage tests) |
| `uv run lint-imports` | ✅ 3 contracts kept, 0 broken |
| `uv run ruff check` | ✅ All checks passed |
| `grep ANTHROPIC_API_KEY\|anthropic` on `primitives/llm/` | ✅ 0 matches (KDR-003) |

## 🔴 HIGH — none

## 🟡 MEDIUM — none

## 🟢 LOW

### M2-T01-ISS-01 (LOW) — Task spec omits `api_base` + `timeout` forwarding; adapter forwards both

- **Finding.** The task spec's deliverable block lists
  `complete(*, system, messages, response_format=None) -> (text, TokenUsage)`
  and the class signature `__init__(self, route, per_call_timeout_s)`,
  but the body of the spec says nothing about forwarding
  `LiteLLMRoute.api_base` to `litellm.acompletion` or propagating
  `per_call_timeout_s` as LiteLLM's `timeout=` kwarg. The
  implementation forwards both because:
  - Ollama-routed tiers carry `api_base: "${OLLAMA_BASE_URL:-…}"`
    from `tiers.yaml`; without propagation, every local-coder call
    would hit LiteLLM's default (public Ollama Cloud) and silently
    misroute.
  - `architecture.md §8.6` names the per-call timeout as a driver-
    level wall-clock concern; storing `per_call_timeout_s` on the
    adapter without passing it to LiteLLM would leave the field dead.
- **Severity.** LOW — both additions are spec-omissions, not drift;
  they are required by contracts that already exist upstream
  (`LiteLLMRoute.api_base` from M1 T06, `TierConfig.per_call_timeout_s`
  also from M1 T06). Reasonable builder judgment, documented in the
  CHANGELOG *Deviations* list.
- **Action / Recommendation.** None. No code change. Captured here
  so the M2 T03 (`TieredNode`) author does not re-litigate the
  decision when they discover these kwargs flowing through.

### M2-T01-ISS-02 (LOW) — `primitives/__init__.py` docstring correction

- **Finding.** `ai_workflows/primitives/__init__.py` carried a
  docstring line — written in M1 T03 — that speculated M2's provider
  drivers would land under `primitives/providers/`. The task spec
  for M2 T01 places them under `primitives/llm/` instead (matching
  [M2 T02](../task_02_claude_code_driver.md)'s `primitives/llm/claude_code.py`
  path). The builder corrected the docstring in the same commit and
  logged the edit in the CHANGELOG *Files updated* list.
- **Severity.** LOW — docstring-only; no runtime effect.
- **Action / Recommendation.** None. Included in scope so the
  package docstring matches reality going forward.

## Additions beyond spec — audited and justified

| Addition | Justification |
| --- | --- |
| `api_base` kwarg forwarded to `litellm.acompletion` | Required by Ollama routing (see M2-T01-ISS-01). |
| `timeout` kwarg forwarded from `per_call_timeout_s` | Required by `architecture.md §8.6`; otherwise the field is vestigial. |
| `_hidden_params["response_cost"]` fall-back in `_extract_usage` | LiteLLM-for-Ollama zero-prices on `response.usage` but populates hidden params. Without the fall-back `CostTracker.by_model` under-counts local-coder calls. Logged as a deviation in CHANGELOG. |
| `primitives/__init__.py` docstring edit | Corrects a dead reference to `primitives/providers/` (see M2-T01-ISS-02). |

None of these introduce new coupling, none imports any new dependency, and all are justified by contracts that already exist upstream. Cleared.

## Issue log — cross-task follow-up

None. Both LOW observations are self-contained in this task; nothing propagates forward.

## Deferred to nice_to_have

None — no findings map to any `nice_to_have.md` trigger.

## Propagation status

No forward-deferred items. No sibling task spec modified.

---

**Final verdict:** ✅ **PASS on cycle 1.** All five ACs graded individually, no design drift, no HIGH / MEDIUM findings, two LOW observations logged for traceability only.
