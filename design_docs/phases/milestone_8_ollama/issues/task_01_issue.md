# Task 01 — `OllamaHealthCheck` Probe Primitive — Audit Issues

**Source task:** [../task_01_health_check.md](../task_01_health_check.md)
**Audited on:** 2026-04-21
**Audit scope:** task file, milestone README, [ai_workflows/primitives/llm/ollama_health.py](../../../../ai_workflows/primitives/llm/ollama_health.py), [ai_workflows/primitives/llm/__init__.py](../../../../ai_workflows/primitives/llm/__init__.py), [tests/primitives/llm/test_ollama_health.py](../../../../tests/primitives/llm/test_ollama_health.py), [pyproject.toml](../../../../pyproject.toml), [CHANGELOG.md](../../../../CHANGELOG.md), [design_docs/architecture.md](../../../architecture.md) (§3, §6, §8.4, §9 KDR-007 / KDR-010), sibling task specs (T02–T06), [.github/workflows/ci.yml](../../../../.github/workflows/ci.yml).
**Status:** ✅ PASS — Cycle 1/10. All 7 ACs satisfied; no design drift; gates green (545 passed, 4 skipped; 4 contracts kept; ruff clean).

## Design-drift check

Cross-referenced against [architecture.md](../../../architecture.md):

- **Layering (§3).** Probe lives under `ai_workflows/primitives/llm/` — same subpackage as the LiteLLM adapter and Claude Code subprocess driver, which is the correct layer for provider-adjacent primitives. Import graph: `ollama_health` imports only `asyncio`, `time`, `httpx`, `pydantic`. No edges into `graph/`, `workflows/`, or surfaces. `lint-imports` reports **4 contracts kept** unchanged.
- **Dependencies (§6).** No new runtime dependency. `httpx>=0.27` is already a direct dep ([pyproject.toml:16](../../../../pyproject.toml#L16)) — established pre-M8 via `litellm` usage; task doc's "bundled transitively via litellm" narrative is imprecise (it's direct) but the architectural invariant (no new top-level dep, no [nice_to_have.md](../../../nice_to_have.md) item pulled in) holds. No LOW raised — this is a doc-precision nit inside the task file, not in the shipped code.
- **KDR-003 (no Anthropic API).** Probe targets Ollama's `/api/tags`; no `anthropic` import, no `ANTHROPIC_API_KEY` read. Clean.
- **KDR-004 (validator-after-LLM).** N/A — no LLM call here.
- **KDR-006 (three-bucket retry).** N/A for T01. Probe is single-shot by design; spec explicitly defers periodic polling to never-to-be-built territory (README §Task order reframe) because the mid-run failure signal is the classified exception through `RetryingEdge`, not an ambient probe.
- **KDR-007 (LiteLLM unified adapter).** Endpoint-resolution convention in the module docstring mirrors `LiteLLMRoute.api_base` so T04's integration can forward the same string. Consistent.
- **KDR-009 (SqliteSaver-only checkpointing).** N/A — no checkpoint/resume logic.
- **KDR-010 (bare-typed pydantic).** `HealthResult` uses `ConfigDict(extra="forbid", frozen=True)` and bare field types (`bool`, `str`, `float | None`). No `Field(min/max/ge/le)` constraints. Compliant.
- **Observability.** No new logging added; nothing pulls in Langfuse / OTel / LangSmith. `StructuredLogger` boundary respected.

**Verdict:** no drift. Nothing promoted to HIGH on design grounds.

## AC grading table

| # | AC | Status | Evidence |
| --- | --- | --- | --- |
| 1 | `from ai_workflows.primitives.llm import HealthResult, probe_ollama` works | ✅ PASS | [`__init__.py:31-36`](../../../../ai_workflows/primitives/llm/__init__.py#L31-L36) exports both; test file imports both at [L17](../../../../tests/primitives/llm/test_ollama_health.py#L17); test run green. |
| 2 | `HealthResult` is pydantic v2 w/ `extra="forbid"` + `frozen=True`, bare-typed per KDR-010 | ✅ PASS | [`ollama_health.py:57`](../../../../ai_workflows/primitives/llm/ollama_health.py#L57) `ConfigDict(extra="forbid", frozen=True)`; fields at L59-62 are bare-typed (no `Field(...)` constraints). |
| 3 | `probe_ollama` never propagates; all failures → `HealthResult(is_healthy=False, reason=<stable>)` | ✅ PASS | Classification matrix at [`ollama_health.py:96-131`](../../../../ai_workflows/primitives/llm/ollama_health.py#L96-L131): `timeout`, `connection_refused`, `http_<status>`, `error:<type>`, `ok`. Covered by tests `test_probe_reports_unhealthy_on_connect_error`, `…_on_timeout`, `…_on_non_2xx`, `…_swallows_arbitrary_exceptions`. |
| 4 | All listed tests pass | ✅ PASS | `uv run pytest tests/primitives/llm/test_ollama_health.py` → 7 passed in 0.14s. Superset of spec (6 listed + 1 bonus `test_probe_trims_trailing_slash_on_endpoint` — justified below). |
| 5 | `uv run lint-imports` reports **4 contracts kept** | ✅ PASS | `Contracts: 4 kept, 0 broken.` |
| 6 | `uv run ruff check` clean | ✅ PASS | `All checks passed!` |
| 7 | No new runtime dependency (`httpx` already present) | ✅ PASS | `httpx>=0.27` already direct in [pyproject.toml:16](../../../../pyproject.toml#L16); no `pyproject.toml` changes in this task's diff. |

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

None.

## Additions beyond spec — audited and justified

- **Bonus test `test_probe_trims_trailing_slash_on_endpoint`** ([test_ollama_health.py:124-129](../../../../tests/primitives/llm/test_ollama_health.py#L124-L129)). Validates the documented `endpoint.rstrip('/')` behaviour in the module docstring. Low-cost, no coupling, directly supports the "callers forward `LiteLLMRoute.api_base` as-is" convention that T04 will rely on. **Justified.**
- **Docstring cross-references to T02–T04 consumers** ([ollama_health.py:1-37](../../../../ai_workflows/primitives/llm/ollama_health.py#L1-L37)). Explicitly names the downstream consumers (circuit breaker, fallback gate) and calls out that T04's `TieredNode` is *not* a direct consumer (mid-run health signal is `retry.classify`, not a sibling probe). This is documentation, not code — improves auditability of T02–T04 without introducing coupling. **Justified.**
- **`TimeoutError` (builtin) instead of aliased `asyncio.TimeoutError`** ([ollama_health.py:101](../../../../ai_workflows/primitives/llm/ollama_health.py#L101)). Forced by ruff's UP041; `asyncio.TimeoutError` has been an alias of builtin `TimeoutError` since Python 3.11. Semantically identical. **Justified.**

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest tests/primitives/llm/test_ollama_health.py` | ✅ 7 passed in 0.14s |
| `uv run pytest` (full suite) | ✅ 545 passed, 4 skipped, 2 warnings in 16.16s |
| `uv run lint-imports` | ✅ 4 contracts kept, 0 broken |
| `uv run ruff check` | ✅ All checks passed |
| CHANGELOG updated | ✅ `[Unreleased]` entry at [CHANGELOG.md:10](../../../../CHANGELOG.md#L10) |
| Docstring discipline | ✅ Module + every public class/function documented |

## Issue log

None. No cross-task follow-ups raised.

## Deferred to nice_to_have

None.

## Propagation status

No forward deferrals from this audit. T02–T06 carry-over sections remain empty.
