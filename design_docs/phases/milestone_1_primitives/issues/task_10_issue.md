# Task 10 — Retry Taxonomy — Audit Issues

**Source task:** [../task_10_retry.md](../task_10_retry.md)
**Audited on:** 2026-04-19
**Audit scope:** task file + milestone README + sibling tasks (03 model factory, 07 tiers/pricing, 11 logging, 12 CLI) + `pyproject.toml` + `CHANGELOG.md` + `.github/workflows/ci.yml` + `ai_workflows/primitives/retry.py` + `tests/primitives/test_retry.py` + upstream consumers referenced by the spec (`ai_workflows/primitives/llm/model_factory.py` — SDK `max_retries=0` wiring; `ai_workflows/primitives/tiers.py` — `TierConfig.max_retries`) + `design_docs/issues.md`.
**Status:** ✅ PASS — every acceptance criterion is satisfied with a pinning test, the gate is green, and no OPEN issues remain.

---

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 314 passed, 2 warnings (pre-existing `yoyo` SQLite datetime deprecation in `test_cost.py`, unrelated to Task 10) |
| `uv run lint-imports` | ✅ 2 kept / 0 broken (primitives / components contracts both green) |
| `uv run ruff check` | ✅ all checks passed |
| `tests/primitives/test_retry.py` alone | ✅ 34 passed in 1.17s |

---

## Acceptance-criterion grading

| AC | Verdict | Evidence |
| --- | --- | --- |
| AC-1: `is_retryable_transient()` True for 429, 529, 500, `APIConnectionError` | ✅ PASS | `test_is_retryable_transient_true_for_retryable_status_anthropic` + `_openai` parametrise over the full `RETRYABLE_STATUS` frozenset; `test_..._rate_limit_errors`, `test_..._connection_errors` pin the SDK-specific branches. |
| AC-2: `is_retryable_transient()` False for 400, 401, `ConfigurationError` | ✅ PASS | `test_is_retryable_transient_false_for_non_retryable_status` covers 400/401/403/404/422/504; `test_..._configuration_error`; `test_..._arbitrary_exceptions` (ValueError / RuntimeError / KeyError). |
| AC-3: `retry_on_rate_limit()` retries transient up to `max_attempts` | ✅ PASS | `test_retry_on_rate_limit_retries_transient_until_success` (success on attempt 3 of 3), `test_..._exhausts_and_raises_transient` (3 calls, then re-raise), `test_..._uses_tier_max_retries` pins the `TierConfig.max_retries` consumer path (M1-T03-ISS-12 resolution). |
| AC-4: Non-transient errors raise on first attempt (no retry delay) | ✅ PASS | `test_..._raises_non_transient_immediately` + `..._raises_http_400_immediately` both patch `asyncio.sleep` and assert `sleeps == []` after a `ConfigurationError` / 400-status failure. |
| AC-5: Jitter is present | ✅ PASS | `test_..._emits_jittered_delays` asserts `len(set(sleeps)) > 1` with `base_delay=0.0`; `test_..._delays_include_exponential_component` pins the exponential component `[1.0, 2.0, 4.0]` by stubbing `random.uniform`. |
| AC-6: WARNING logged on each retry with attempt number and error type | ✅ PASS | `test_..._logs_warning_per_retry` asserts exactly `max_attempts - 1` `retry.transient` warnings with `attempt`, `max_attempts`, `delay`, and `error_type` fields; `log_level=="warning"`. Negative coverage: `..._does_not_log_on_first_success`, `..._does_not_log_on_non_transient`. |
| AC-7: `ModelRetry` integration — ValidationError in validator → second chance | ✅ PASS | `test_model_retry_feeds_error_back_and_model_retries` drives a `FunctionModel`: call 1 returns `{"steps": "not a list"}`, the `@agent.output_validator` raises `ModelRetry` (from `ValidationError`) with `raise ... from exc`, call 2's history carries a `RetryPromptPart`, and the final `result.output` is `Plan(steps=["a", "b"])`. |

---

## Additions beyond spec — audited and justified

| Addition | Justification |
| --- | --- |
| `openai` SDK exception classification (`openai.RateLimitError`, `openai.APIStatusError`, `openai.APIConnectionError`) | The spec code block imports only from `anthropic`, but the spec's Class-1 wording (“HTTP 429”, “network”) is provider-agnostic, and CRIT-06 calls `retry_on_rate_limit` the framework's **single retry authority**. This repo's default tiers drive Gemini via the OpenAI-compatible endpoint (memory `project_provider_strategy`), so without the openai branch the retry layer would silently no-op on the primary runtime path. Pinned by the parametrised `..._openai[…]` tests and the `_rate_limit_errors` / `_connection_errors` twin assertions. |
| `RETRYABLE_STATUS` exported as a `frozenset[int]` module constant | The spec defines `RETRYABLE_STATUS = {429, 529, 500, 502, 503}` as a set literal; making it a `frozenset` prevents callers from mutating it at runtime, and the module-level test `test_retryable_status_set_covers_spec` pins the contents against the spec. |
| `max_attempts < 1` → `ValueError` | Defensive input validation. `range(0)` would silently return the unreachable `RuntimeError` at the end of the function; the explicit guard fails fast with a clear message. Pinned by `test_retry_on_rate_limit_rejects_nonpositive_max_attempts`. |
| Logger uses `structlog.get_logger(__name__)` (not spec's bare `log.warning`) | Matches the house style established by `primitives/cost.py`; `structlog.testing.capture_logs` pins AC-6. Task 11 (logging) will configure the root logger; the module already works in tests. |
| Log event name `retry.transient` + `max_attempts` field | The spec writes `log.warning("retry_transient", attempt=..., delay=..., error_type=...)`. Event name changed to dotted form for consistency with `primitives/cost.py`'s `cost.no_budget_cap` / `cost.model_not_in_pricing` convention; `max_attempts` added because it is free context that helps operators tell “2/3” from “2/5” at a glance. Both fields are asserted by AC-6's pin. |
| Final-attempt short-circuit (no sleep before final raise) | The spec pseudocode computes `delay` and sleeps unconditionally inside the `except` block, which would delay the failure by ~`base_delay * 2**(max_attempts - 1)` seconds without any chance of changing the outcome. The guard (`is_last = attempt == max_attempts - 1`) re-raises immediately; the behaviour is pinned by `test_..._delays_include_exponential_component` (only `max_attempts - 1` sleeps for `max_attempts=4`). |
| PEP 695 generic `retry_on_rate_limit[T](...)` | Satisfies ruff `UP047` on the Python 3.12 floor. Equivalent to the spec's `TypeVar("T")` form; keeps the return type inferred from `fn`. |

No addition imports from `components` or `workflows`; no adapter-specific types leak into other modules; no file beyond `primitives/retry.py` and `tests/primitives/test_retry.py` is added.

---

## Convention checks

| Check | Verdict |
| --- | --- |
| Layer discipline — `primitives/retry.py` imports only from `anthropic`, `openai`, `structlog`, stdlib | ✅ `lint-imports` green. |
| Module docstring names the task that produced it and how it relates to other modules | ✅ Docstring cites “M1 Task 10 (P-36, P-40, P-41, CRIT-06, CRIT-08; revises P-37)” and points to `primitives/llm/model_factory.py` + `primitives/tiers.py`. |
| Every public function has a docstring | ✅ `is_retryable_transient`, `retry_on_rate_limit`. |
| CHANGELOG updated under `## [Unreleased]` with `### Added — M1 Task 10: …` | ✅ Entry lists every file touched and calls out the deviations from spec (openai branch, structlog event name, no-sleep-on-final-attempt). |
| Milestone README task line flipped to ✅ Complete (2026-04-19) | ✅ `README.md:62`. |
| AC checkboxes in task file all ticked with pinning-test names | ✅ `task_10_retry.md:108-137`. |
| No task-10 work orphaned on `issues.md` — CRIT-06, CRIT-08, P-37 flipped to `[x]` with a “Resolved by M1 Task 10” note | ✅ `design_docs/issues.md:27`, `:29`, `:112`. |
| No CI / workflow changes needed | ✅ `.github/workflows/ci.yml` unchanged; retry module is pure Python and is exercised by the existing `uv run pytest` job. |
| Secrets discipline — no API keys, no env-var prompts, no credentials in the module | ✅ Module only imports exception classes. |
| `max_retries=0` on SDK clients remains the invariant | ✅ No change to `model_factory.py`; `test_google_client_retry_is_disabled` + Task 03 AC-3 already pin this. The retry module is additive. |
| Forward-deferral propagation | ✅ No deferrals — every AC is satisfied in this task. |

---

## 🔴 HIGH

_None._

## 🟡 MEDIUM

_None._

## 🟢 LOW

_None._

---

## Issue log — tracked for cross-task follow-up

_No OPEN issues. Task 10 lands clean on the first cycle._

### Cross-cutting status updated by this audit

- **CRIT-06** flipped `[~]` → `[x]`: `primitives/retry.py` is now the single retry authority referenced by the CRIT-06 note. Pinned by the SDK-agnostic classifier tests in `test_retry.py` and by the existing Task 03 regression (`test_google_client_retry_is_disabled`, `test_anthropic_client_max_retries_zero`, `test_openai_compat_client_max_retries_zero`, `test_ollama_client_max_retries_zero`).
- **CRIT-08** flipped `[ ]` → `[x]`: the three-class taxonomy is implemented (transient via `retry_on_rate_limit`, semantic via `ModelRetry` integration test, non-retryable surfaces on first attempt).
- **P-37** flipped `[~]` → `[x]`: resolved alongside CRIT-08.

### Propagation status

No forward deferrals — nothing to propagate.
