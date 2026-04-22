# Task 02 — `CircuitBreaker` Primitive — Audit Issues

**Source task:** [../task_02_circuit_breaker.md](../task_02_circuit_breaker.md)
**Audited on:** 2026-04-21
**Audit scope:** task file, milestone README, [ai_workflows/primitives/circuit_breaker.py](../../../../ai_workflows/primitives/circuit_breaker.py), [ai_workflows/primitives/__init__.py](../../../../ai_workflows/primitives/__init__.py), [tests/primitives/test_circuit_breaker.py](../../../../tests/primitives/test_circuit_breaker.py), [CHANGELOG.md](../../../../CHANGELOG.md), [pyproject.toml](../../../../pyproject.toml), sibling task specs (T01, T03–T06), [design_docs/architecture.md](../../../architecture.md) (§3, §4.2, §6, §8.4, §9 KDR-006 / KDR-010), [design_docs/phases/milestone_8_ollama/issues/task_01_issue.md](task_01_issue.md).
**Status:** ✅ PASS — Cycle 1/10. All 9 ACs satisfied; no design drift; gates green (553 passed, 4 skipped; 4 contracts kept; ruff clean).

## Design-drift check

Cross-referenced against [architecture.md](../../../architecture.md):

- **Layering (§3).** `primitives/circuit_breaker.py` sits in the primitives layer. Imports: `asyncio`, `time`, `collections.abc`, `enum`, `structlog`. No edges into `graph/`, `workflows/`, or surfaces. `lint-imports` reports 4 contracts kept.
- **Top-level re-export in `primitives/__init__.py`.** A new convention — until now, primitives were only imported via submodule paths (`from ai_workflows.primitives.retry import …`). The task spec's AC-1 explicitly calls for `from ai_workflows.primitives import CircuitBreaker, CircuitOpen, CircuitState`; added as additive re-exports with a docstring paragraph noting the convention shift. Existing submodule imports continue to work. Not drift — aligns with the spec.
- **Dependencies (§6).** No additions. `structlog` already a direct dep; `asyncio` / `time` / `enum` are stdlib; no `freezegun` pulled in (time source injection used instead, per spec AC-9 contingency).
- **KDR-003 (no Anthropic API).** N/A. No LLM path.
- **KDR-004 (validator-after-LLM).** N/A. No LLM node added.
- **KDR-006 (three-bucket retry).** Default `trip_threshold=3` is documented in the module docstring + class docstring as matching `RetryPolicy.max_transient_attempts=3`. Breaker does not *re-implement* retry — it short-circuits downstream of a failed `RetryingEdge` loop. Consistent.
- **KDR-007 (LiteLLM unified adapter).** N/A for T02 directly; T04 will consume.
- **KDR-009 (SqliteSaver-only checkpointing).** Breaker is intentionally process-local (no Storage table, no `SqliteSaver` entry). Module docstring + task spec both call this out explicitly with the restart-semantics rationale.
- **KDR-010 (bare-typed pydantic).** N/A — `CircuitBreaker` is not a pydantic model. `CircuitState` is a `StrEnum` (ruff UP042 enforced). `CircuitOpen` is a plain exception carrying `tier` + `last_reason`.
- **Observability.** `structlog.get_logger("ai_workflows.circuit_breaker")` — fits the `StructuredLogger` boundary. No external backend pulled in.

**Verdict:** no drift.

## AC grading table

| # | AC | Status | Evidence |
| --- | --- | --- | --- |
| 1 | `from ai_workflows.primitives import CircuitBreaker, CircuitOpen, CircuitState` works | ✅ PASS | [`primitives/__init__.py:29-36`](../../../../ai_workflows/primitives/__init__.py#L29-L36) re-exports all three; tests import them at [L18](../../../../tests/primitives/test_circuit_breaker.py#L18). |
| 2 | CircuitState transitions: CLOSED → OPEN → HALF_OPEN → CLOSED or → OPEN w/ reset | ✅ PASS | Covered by `test_trips_open_after_threshold_failures`, `test_half_open_after_cooldown`, `test_half_open_success_closes`, `test_half_open_failure_reopens` (last asserts cooldown reset via advance-30s-still-False then advance-31s-True). |
| 3 | `allow()` in HALF_OPEN lets through exactly one probe until next `record_*` | ✅ PASS | `test_half_open_after_cooldown` asserts second `allow()` → False. Implementation at [circuit_breaker.py:178-186](../../../../ai_workflows/primitives/circuit_breaker.py#L178-L186) gated by `_half_open_probe_in_flight`. |
| 4 | All ops `asyncio.Lock`-guarded; concurrent branches don't double-count past threshold | ✅ PASS | Every public coroutine wraps body in `async with self._lock`. `test_concurrent_branches_do_not_double_trip` fires 10 concurrent record_failures via `asyncio.gather`; counter reaches 10 but only one transition logs. |
| 5 | State transitions log at INFO exactly once per transition (not per increment) | ✅ PASS | `_transition()` is the only site that emits `circuit_state`; gated by the `_state is CircuitState.CLOSED` check so repeat record_failures while already OPEN are no-ops. Same test above asserts `len(transitions) == 1`. |
| 6 | Every listed test passes | ✅ PASS | 8 tests in `test_circuit_breaker.py` — all green in 0.03s. Superset of the 8 listed in the spec (1-for-1 mapping; no drop, no rename). |
| 7 | `uv run lint-imports` — 4 contracts kept | ✅ PASS | `Contracts: 4 kept, 0 broken.` |
| 8 | `uv run ruff check` clean | ✅ PASS | `All checks passed!` (after UP042 fix: `StrEnum` instead of `(str, Enum)`). |
| 9 | No new runtime dependency; `freezegun` (if used) dev-only | ✅ PASS | `freezegun` not used. Time source injection via `time_source: Callable[[], float]` constructor arg; tests use a local `_FakeClock` helper. No `pyproject.toml` changes. |

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

None.

## Additions beyond spec — audited and justified

- **`CircuitBreaker.tier` property** ([circuit_breaker.py:133-135](../../../../ai_workflows/primitives/circuit_breaker.py#L133-L135)). Not in the spec sketch but needed by `test_last_reason_survives_trip` which constructs `CircuitOpen(tier=breaker.tier, …)`. Symmetric with the existing `state` / `last_reason` properties. Zero-cost, directly supports the spec's AC-8 test.
- **`_FakeClock` test helper** instead of a shared fixture module. Self-contained in the test file; no cross-test coupling. Justified over `freezegun` by spec AC-9.
- **`last_reason` default empty string** (not `None`). Simplifies the T03 fallback gate's prompt rendering — the gate can interpolate the string unconditionally. Spec doesn't pin the default; empty string matches the "short human-readable" contract.

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest tests/primitives/test_circuit_breaker.py` | ✅ 8 passed in 0.03s |
| `uv run pytest` (full suite) | ✅ 553 passed, 4 skipped in 16.62s |
| `uv run lint-imports` | ✅ 4 contracts kept, 0 broken |
| `uv run ruff check` | ✅ All checks passed |
| CHANGELOG updated | ✅ `[Unreleased]` entry above the T01 entry |
| Docstring discipline | ✅ Module docstring cites M8 T02 + downstream consumers; every public class/method/property documented |

## Issue log

None.

## Deferred to nice_to_have

None.

## Propagation status

No forward deferrals from this audit. T03–T06 carry-over sections remain empty.
