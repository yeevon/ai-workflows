# Task 02 — `TieredNode` fallback-cascade dispatch + cost attribution

**Status:** 📝 Planned.
**Grounding:** [milestone README](README.md) · [architecture.md §4.2 + §9](../../architecture.md) · [ai_workflows/graph/tiered_node.py](../../../ai_workflows/graph/tiered_node.py) · [ai_workflows/primitives/cost.py](../../../ai_workflows/primitives/cost.py) · [KDR-006](../../architecture.md) (three-bucket retry via RetryingEdge) · [KDR-004](../../architecture.md) (validator pairing — cascade is an infrastructure mechanism, not a semantic retry).

## What to Build

Wire the fallback cascade into `TieredNode`. When `_dispatch()` raises an infrastructure-level
exception (`RetryableTransient` or `NonRetryable`) for the primary route, the `_node()` closure
walks `tier_config.fallback` in order, attempting each route once via a fresh `_dispatch()` call.
The first successful call returns normally; cost attribution fires for every successful attempt.
If all routes fail, raise `AllFallbacksExhaustedError` (a `NonRetryable` subclass) carrying every
attempt's route + exception.

`RetryableSemantic` exceptions bypass the cascade entirely and propagate unchanged — KDR-004 is
unchanged; validator-failure routing through `RetryingEdge` is not a cascade trigger.

Two new types land in `ai_workflows/graph/tiered_node.py` and are exported via `__all__`:
`TierAttempt` (dataclass: route, exception, usage) and `AllFallbacksExhaustedError`
(NonRetryable subclass). No primitives module changes. No changes to `RetryingEdge`,
`ValidatorNode`, or `RetryPolicy`.

## Deliverables

### 1. `ai_workflows/graph/tiered_node.py` — new types + cascade logic

**New types** (add after existing imports, before `tiered_node()` factory; export via `__all__`):

```python
from dataclasses import dataclass

@dataclass
class TierAttempt:
    """One attempt in a fallback cascade — primary or a fallback route."""

    route: LiteLLMRoute | ClaudeCodeRoute
    exception: BaseException
    usage: TokenUsage | None = None  # None when dispatch raised before returning usage


class AllFallbacksExhaustedError(NonRetryable):
    """All cascade routes (primary + every fallback) failed.

    Carries the full attempt list so callers can surface which routes were
    tried and why each failed. Subclasses NonRetryable so RetryingEdge
    routes it to on_terminal without a taxonomy change.
    """

    def __init__(self, attempts: list[TierAttempt]) -> None:
        routes_summary = ", ".join(
            f"{type(a.route).__name__}({_model_from_route(a.route)!r})"
            for a in attempts
        )
        super().__init__(f"all fallback routes exhausted: [{routes_summary}]")
        self.attempts = attempts
```

Update `__all__` to also export `TierAttempt` and `AllFallbacksExhaustedError`.

**Cascade trigger — primary route failures:** In the existing
`try / except (RetryableTransient, NonRetryable)` block, instead of logging + re-raising
immediately when `tier_config.fallback` is non-empty, walk the fallback list. Additionally,
the pre-dispatch `CircuitOpen` guard (currently at `tiered_node.py:238-247`) is extended so
that when the primary route raises `CircuitOpen` and `tier_config.fallback` is non-empty, the
cascade fires rather than propagating `CircuitOpen` to the caller. In both cases the cascade
entry point is identical:

1. Record the primary failure as `TierAttempt(route=primary_route, exception=exc)`.
2. For each `fallback_route` in `tier_config.fallback` in order:
   - If a per-tier semaphore exists for `resolved_tier`, acquire it via
     `async with semaphore:` before calling `_dispatch()`. This mirrors the primary-route
     concurrency contract — fallback routes share the primary tier's semaphore so the
     operator's `max_concurrency` cap is respected across the entire cascade.
   - Call `await _dispatch(route=fallback_route, tier_config=tier_config, ...)`.
   - On success: break the loop, proceed to the existing cost-record + log success path
     (stamping `tier` and `role` on `usage` as today).
   - Defensive: if `RetryableSemantic` is raised (owned by `ValidatorNode`; adapters should
     never raise it, but pass-through is mandatory — the cascade must not re-classify),
     propagate unchanged. See L1 carry-over note.
   - On `RetryableTransient`, `NonRetryable`, or `CircuitOpen` from the fallback: append
     `TierAttempt(route=fallback_route, exception=fallback_exc)` and continue to the next.
3. If no fallback succeeded (loop ended without `break`): raise
   `AllFallbacksExhaustedError(attempts=all_attempts)`.

When `tier_config.fallback` is empty (the common case today), existing behaviour is
preserved — the primary exception is logged and re-raised as before.

**§1.5 — Structured log emission per attempt:** The module's existing "exactly-once invariant"
(one log record per invocation) is relaxed for cascade runs to "one record per attempted
route." Each attempt emits its own `node_failed` or `node_completed` record, with `provider`
and `model` re-derived per route via `_provider_from_route(attempt_route)` and
`_model_from_route(attempt_route)`. Concretely:

- Primary fail + fallback success → 2 records: `node_failed` for primary, `node_completed`
  for the successful fallback.
- All-fail (N routes) → N records of `node_failed` (one per attempted route), then
  `AllFallbacksExhaustedError` propagates.
- Empty fallback (no cascade) → 1 record as today.

The `tier` field on each record is always `resolved_tier` (the logical tier name); the
`model` and `provider` fields vary per attempt.

**Cost attribution:** Every successful `_dispatch()` call — whether the primary route or a
fallback — records its `TokenUsage` to `cost_callback.on_node_complete(...)` via the existing
path. Failed dispatches (primary or fallback) do not record to cost callback (no `TokenUsage`
available; cost is zero or unknown for failed calls). The structured log record
(`node_completed` / `node_failed`) emits for every attempt in the cascade, with the route's
`provider` and `model` fields reflecting whichever route was attempted.

**§1.6 — Module docstring update:** The module docstring at `tiered_node.py:39-44` currently
states "Per-invocation: one provider call, one `CostTracker.record`, and one structured log
record." This invariant is relaxed in T02 for cascade runs. The Builder updates that bullet to:

> Per-invocation: one provider call per *attempted route*, one `CostTracker.record` per
> *successful attempt* (cost callback fires on success only), and one structured log record per
> *attempt* (success or failure). For tiers with `fallback=[]` (the common case, and the default)
> the per-attempt count is 1 — the new contract degenerates to the old invariant.

### 2. Tests — `tests/graph/test_tiered_node_fallback.py` (new)

Hermetic — stub adapters patched via `monkeypatch`, no provider calls, no disk I/O.
Pattern mirrors `tests/graph/test_tiered_node.py` (same `_build_config` helper shape,
same `_FakeLiteLLMAdapter` + `_RaisingLiteLLMAdapter` stub approach).

Four tests:

- **`test_cascade_succeeds_on_fallback_after_primary_fail`** — `TierConfig` with
  `route=LiteLLMRoute(model="gemini/a")` and `fallback=[LiteLLMRoute(model="gemini/b")]`.
  Primary adapter raises `NonRetryable`; fallback adapter returns `("text", TokenUsage(...))`.
  Assert: node returns `{f"{node_name}_output": "text", "last_exception": None}`.
  Assert: `cost_tracker.total(run_id) > 0` (fallback cost recorded).
  Assert: no exception raised from `_node`.

- **`test_cascade_exhausts_all_raises_AllFallbacksExhaustedError`** — primary and both
  fallbacks all raise `NonRetryable`. Assert: `AllFallbacksExhaustedError` is raised.
  Assert: `len(exc.attempts) == 3`. Assert: each `TierAttempt.route` names the correct
  route in order (primary, fallback[0], fallback[1]).

- **`test_cascade_skips_on_semantic_failure`** — primary raises `RetryableSemantic`.
  Assert: `RetryableSemantic` propagates unchanged from `_node`. Assert: no
  `AllFallbacksExhaustedError`; cascade not entered. Assert: `cost_tracker.total(run_id) == 0`
  (semantic failures never reach cost attribution).

- **`test_cascade_cost_attribution`** — primary raises `NonRetryable`;
  fallback[0] succeeds with `TokenUsage(cost_usd=0.25, model="gemini/b")`.
  Assert: `cost_tracker.total(run_id) == pytest.approx(0.25)`.
  Assert: `cost_tracker.by_tier(run_id)` shows the tier name (not the fallback's model).

### 3. `CHANGELOG.md`

Entry under `## [Unreleased] → ### Added`:
`M15 Task 02: TieredNode fallback-cascade dispatch + cost attribution (YYYY-MM-DD)`
naming files touched and ACs satisfied.

## Acceptance Criteria

- [ ] **AC-1: `AllFallbacksExhaustedError` defined.** New exception class in
  `ai_workflows/graph/tiered_node.py`, subclass of `NonRetryable`. Has
  `attempts: list[TierAttempt]`. Exported via `__all__`.

- [ ] **AC-2: `TierAttempt` defined.** New dataclass in `ai_workflows/graph/tiered_node.py`
  with fields `route: LiteLLMRoute | ClaudeCodeRoute`, `exception: BaseException`,
  `usage: TokenUsage | None`. Exported via `__all__`.

- [ ] **AC-3: Cascade dispatch wired.** `_node()` walks `tier_config.fallback` after primary
  route raises `RetryableTransient`, `NonRetryable`, or `CircuitOpen`. Each fallback dispatch
  acquires the primary tier's semaphore if one is configured. First successful fallback returns
  normally. All-fail raises `AllFallbacksExhaustedError`.

- [ ] **AC-4: `RetryableSemantic` defensive pass-through.** `RetryableSemantic` from any
  dispatch (primary or fallback) propagates unchanged — the cascade does not re-classify it.
  Validator-driven semantic retry runs through `RetryingEdge` against the primary route only;
  the cascade is at a lower layer and is not entered for semantic failures (KDR-004 unchanged).

- [ ] **AC-5: Cost attribution.** Every successful `_dispatch()` call (primary or fallback)
  records its `TokenUsage` to `cost_callback`. Failed dispatches do not record to cost
  callback. `cost_tracker.total(run_id)` reflects only cost-incurring (successful) attempts.

- [ ] **AC-6: Empty-fallback backward compat.** A `TierConfig` with `fallback=[]` (the
  default) behaves identically to pre-T02: primary failure logged + re-raised, no cascade
  initiated. All pre-existing tests for `tiered_node` pass without modification.

- [ ] **AC-12: CircuitOpen triggers cascade.** When the primary route is Ollama-backed and
  the circuit breaker is open, raising `CircuitOpen` (before `_dispatch()` is called), the
  cascade fires if `tier_config.fallback` is non-empty — identical to the post-dispatch
  `RetryableTransient`/`NonRetryable` path. If `fallback=[]`, `CircuitOpen` propagates as
  today.

- [ ] **AC-13: Per-attempt log records + docstring.** For a cascade run (non-empty fallback,
  primary fails), exactly one `node_failed` log record emits per failed route attempt, and one
  `node_completed` emits for the successful route (if any). Each record's `provider` and
  `model` fields reflect the route that was attempted, not the primary route. The module
  docstring "Exactly-once invariants" bullet (lines 39-44 of `tiered_node.py`) is updated to
  read "one record per *attempt*" (see §1.6); for `fallback=[]` tiers the new wording
  degenerates to the prior one-record-per-invocation behaviour.

- [ ] **AC-7: Hermetic tests green.** `tests/graph/test_tiered_node_fallback.py` — 4 new
  tests, all pass. No provider calls.

- [ ] **AC-8: Existing tests unchanged.** Full `uv run pytest` green. No modification to
  existing test files.

- [ ] **AC-9: Layer contract preserved.** `uv run lint-imports` reports 5 contracts kept,
  0 broken. `AllFallbacksExhaustedError` and `TierAttempt` in `graph/`; cascade logic in
  `graph/tiered_node.py`. No primitives-layer change.

- [ ] **AC-10: Gates green.** `uv run pytest` + `uv run lint-imports` + `uv run ruff check`
  all pass.

- [ ] **AC-11: CHANGELOG entry.** M15 T02 entry added under `[Unreleased]`.

## Dependencies

- **T01 must be built first.** This task reads `tier_config.fallback` (the field added in T01).
  T01 is ✅ Built (cycle 1, 2026-04-30).
- Ships against 0.4.0 baseline (M17 closed 2026-04-30). M15 ships as ≥ 0.5.0.

## Out of scope

- **`aiw list-tiers` CLI command.** T03.
- **HTTP CircuitOpen cascade test (MCP transport).** T03.
- **ADR-0006.** T04.
- **`tiers.yaml` relocation → `docs/tiers.example.yaml`.** T04.
- **Per-fallback retry loop.** Each fallback route is attempted exactly once within the
  cascade. Per-fallback retries are a forward-option; not planned at M15.
- **State-level cascade tracking.** No new state key is added. `AllFallbacksExhaustedError`
  carries the attempts record on the exception; no `state` mutation.
- **`RetryingEdge` changes.** `RetryingEdge` is unchanged. It sees `AllFallbacksExhaustedError`
  as a `NonRetryable` and routes to `on_terminal` without modification.
- **`RetryPolicy` changes.** No new budget field for fallback attempts.
- **`ValidatorNode` changes.** `ValidatorNode` is unchanged. It receives the output of
  whichever route succeeded, through the normal `state[f"{node_name}_output"]` key.
- **M8 `_mid_run_tier_overrides` interaction.** The M8 post-gate reactive override and M15
  declarative cascade coexist without conflict. M15 T02 does not modify the override logic.
  Existing M8 tests pass unchanged (AC-8 covers this passively).

## Carry-over from prior milestones

- *None at T02 kickoff.*

## Carry-over from task analysis

- [ ] **TA-LOW-01 — `RetryableSemantic` cascade-bypass framing** (severity: LOW, source: task_analysis.md round 1)
      The spec framing implies `RetryableSemantic` is raised by provider dispatch — it is not.
      `RetryableSemantic` is owned by `ValidatorNode`; the cascade guard is defensive (a custom
      adapter could in principle raise it, so we must not re-classify). The guard is correct and
      load-bearing; the framing in AC-4 and §1 should make clear it is defensive, not a normal
      dispatch path.
      **Recommendation:** Builder ensures code comment on the `except RetryableSemantic` guard
      within the cascade reads: "Defensive pass-through — adapters do not raise this bucket;
      ValidatorNode does. Must not re-classify."

- [ ] **TA-LOW-02 — `TierAttempt.usage` field always `None` — drop or document** (severity: LOW, source: task_analysis.md round 1)
      `TierAttempt.usage` is never populated because `_dispatch()` raises before returning
      `TokenUsage` on failure. Either drop the field (simplest) or document it as
      forward-reserved with a code comment naming the trigger.
      **Recommendation:** Builder drops `TierAttempt.usage` unless there is an immediate
      consumer. If dropped, update `TierAttempt` dataclass definition and any test references.

- [ ] **TA-LOW-03 — Per-call timeout inheritance for fallback routes** (severity: LOW, source: task_analysis.md round 1)
      `_dispatch()` reads `tier_config.per_call_timeout_s` from the primary `TierConfig`. When
      a fallback reuses the primary's `tier_config`, it inherits the primary's timeout. This is
      desirable (operator-set timeout applies to the whole tier call regardless of route) but
      unstated.
      **Recommendation:** Builder adds a one-line code comment near the fallback dispatch call:
      "# Fallback routes inherit per_call_timeout_s from the primary TierConfig."

- [ ] **TA-LOW-04 — Breaker bypass for fallback dispatches** (severity: LOW, source: task_analysis.md round 1)
      Spec is silent on whether breaker `record_success` / `record_failure` calls happen for
      fallback dispatches. Fallback dispatches bypass circuit-breaker bookkeeping — each is one
      shot; no breaker `record_success` or `record_failure` is invoked for fallback routes
      regardless of route kind. This pairs with AC-12's CircuitOpen handling.
      **Recommendation:** Builder adds a code comment near fallback dispatch: "# Fallback routes
      bypass circuit-breaker bookkeeping (one shot per fallback; breaker is the primary tier's
      M8 mechanism)." No per-fallback `_resolve_breaker()` call.
