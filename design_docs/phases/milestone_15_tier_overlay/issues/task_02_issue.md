# Task 02 — `TieredNode` fallback-cascade dispatch + cost attribution — Audit Issues

**Source task:** [task_02_tierednode_cascade_dispatch.md](../task_02_tierednode_cascade_dispatch.md)
**Audited on:** 2026-04-30 (cycle 1, cycle 2)
**Audit scope:** Builder cycle 1 — `ai_workflows/graph/tiered_node.py` cascade logic + new types, `tests/graph/test_tiered_node_fallback.py` (9 hermetic tests), CHANGELOG entry, milestone README + spec status flips. Builder cycle 2 — terminal-gate FIX-1 + FIX-2: two new hermetic tests added to `tests/graph/test_tiered_node_fallback.py` (now 11 tests). No code changes to `tiered_node.py`.
**Status:** ✅ PASS

---

## Cycle 1 — Build (2026-04-30)

### Implementation notes (per Builder)

- `TierAttempt` dataclass + `AllFallbacksExhaustedError` added to `ai_workflows/graph/tiered_node.py`; both exported via `__all__`.
- `_emit_failed_log` helper extracted to deduplicate per-attempt log emission across primary and fallback routes.
- `_node()` closure refactored: primary dispatch is separated from cascade logic; success path wrapped in try/except to preserve the budget-cap `NonRetryable` log invariant.
- `CircuitOpen` pre-dispatch guard extended: when `fallback` is non-empty the breaker-denied case sets `circuit_open_before_dispatch=True` and falls through to the cascade rather than raising immediately.
- TA-LOW-02 disposition: `TierAttempt.usage` retained as forward-reserved (with comment + docstring naming the trigger) instead of dropped — Builder rationale: avoid breaking `field()`-positional callers if any exist.

---

## Design-drift check

No drift detected.

- **KDR-004 (validator pairing)** — preserved. `RetryableSemantic` defensive pass-through (cascade is not entered for semantic failures); validator-driven semantic retry remains routed through `RetryingEdge` against the primary route. Spec AC-4 explicit; code at `tiered_node.py:333-336` and `tiered_node.py:429-432` (defensive comment).
- **KDR-006 (three-bucket retry via RetryingEdge)** — preserved. `AllFallbacksExhaustedError` subclasses `NonRetryable` so `RetryingEdge` continues to route via the existing terminal path; no taxonomy change. No new `try/except` retry loop.
- **No new dependencies.** `dataclasses.dataclass`/`field` is stdlib (already imported at module top).
- **Layer contract.** `lint-imports` shows 5 contracts kept, 0 broken. `TierAttempt` and `AllFallbacksExhaustedError` live in `graph/tiered_node.py`, no upward imports introduced. `graph → primitives` only; no `graph → workflows`/`surfaces`/`evals` violations.
- **Status surfaces.** Spec `Status:` line, milestone README task-table row, and issue file all flipped to "✅ Built (cycle 1)". M15 has no `tasks/README.md` (per-milestone convention) and no relevant "Done when" checkboxes affected outside the README task-table row.

---

## AC grading

| AC | Status | Notes |
|---|---|---|
| AC-1 — `AllFallbacksExhaustedError` defined | ✅ met | `tiered_node.py:137-154`. Subclass of `NonRetryable`; `attempts: list[TierAttempt]` attribute set in `__init__`; exported via `__all__` (line 111). Verified by `test_all_fallbacks_exhausted_error_is_non_retryable`. |
| AC-2 — `TierAttempt` defined | ✅ met | `tiered_node.py:115-134`. `route: LiteLLMRoute \| ClaudeCodeRoute`, `exception: BaseException`, `usage: TokenUsage \| None = None`. Exported. Verified by `test_tier_attempt_dataclass_fields`. |
| AC-3 — Cascade dispatch wired | ✅ met | Primary dispatch failure paths (`RetryableTransient`, `NonRetryable`, `CircuitOpen`) all funnel through `tiered_node.py:360-470` cascade loop. Each fallback acquires the primary tier's semaphore (`tiered_node.py:408-417`). All-fail raises `AllFallbacksExhaustedError(attempts=...)`. Verified by `test_cascade_succeeds_on_fallback_after_primary_fail` + `test_cascade_exhausts_all_raises_AllFallbacksExhaustedError` (3 attempts in correct order). |
| AC-4 — `RetryableSemantic` defensive pass-through | ✅ met | Two `except RetryableSemantic: raise` guards (primary at `:333-336`, fallback at `:429-432`) with TA-LOW-01 defensive comment present. Verified by `test_cascade_skips_on_semantic_failure` — assertion `tracker.total("run-1") == 0` confirms no cost recording on semantic-fail path. |
| AC-5 — Cost attribution | ✅ met | Cost callback only fires on the success path (`tiered_node.py:498-525`); failed dispatches never reach it. `usage_with_tier` stamped to `resolved_tier` (logical name), not the fallback's model. Verified by `test_cascade_cost_attribution` — tracker total == 0.25 (fallback cost), `by_tier["planner"] == 0.25`. |
| AC-6 — Empty-fallback backward compat | ✅ met | `if not tier_config.fallback:` branch (`tiered_node.py:362-375`) re-raises the primary exception unchanged. Pre-existing `tests/graph/test_tiered_node.py` (15 tests) all green unmodified. New `test_empty_fallback_primary_failure_reraises` confirms `AllFallbacksExhaustedError` is **not** raised on `fallback=[]` failure. |
| AC-7 — Hermetic tests green | ✅ met | 9 tests pass in 1.01s. No provider calls, no disk I/O — adapter routing via `_RoutingLiteLLMAdapter` + `_ADAPTER_MAP` monkey-patch. Spec called for 4 tests; Builder shipped 9 (additional coverage on AC-13 cascade logging + dataclass / inheritance assertions). Additions are within scope. |
| AC-8 — Existing tests unchanged | ✅ met | `tests/graph/test_tiered_node.py` 15/15 pass without modification. Full suite: 1522 pass, 12 skip. One pre-existing flake in `tests/mcp/test_cancel_run_inflight.py` (unrelated to T02 — passes in isolation; does not touch `tiered_node`). Documented under Gate Summary. |
| AC-9 — Layer contract preserved | ✅ met | `lint-imports`: 5 contracts kept, 0 broken. New types in `graph/`, no `primitives`-layer change. |
| AC-10 — Gates green | ✅ met | pytest pass (sans pre-existing flake), lint-imports clean, ruff clean. See gate summary. |
| AC-11 — CHANGELOG entry | ✅ met | Entry under `[Unreleased] → Added` with date, file list, ACs satisfied. |
| AC-12 — `CircuitOpen` triggers cascade | ✅ met | Pre-dispatch breaker-deny path at `:289-302`: when `fallback=[]` raises `CircuitOpen` as today; when fallback is non-empty, sets `circuit_open_before_dispatch=True` and threads through to the cascade (primary attempt recorded as `CircuitOpen`). The fallback-loop's exception handler (`:433-466`) explicitly catches `CircuitOpen` from fallback dispatches too. Hermetic tests don't directly exercise the breaker path (see Findings — LOW); behaviour is unit-level reachable, and the spec out-of-scope notes "HTTP CircuitOpen cascade test (MCP transport): T03". |
| AC-13 — Per-attempt log records + docstring | ✅ met | Module docstring updated (`tiered_node.py:40-48`) to per-attempt wording. `_emit_failed_log` helper emits one record per failed route attempt. Verified by `test_per_attempt_log_records_for_cascade` (1 fail + 1 complete) and `test_all_fail_log_records` (2 fails on 2-route exhaustion). `provider`/`model` reflect attempted route; `tier` always logical. |
| TA-LOW-01 (defensive comment) | ✅ ticked + verified | Comment present at `:334-335` and `:430-431` ("Defensive pass-through — adapters do not raise this bucket; ValidatorNode does. Must not re-classify."). Diff matches checkbox. |
| TA-LOW-02 (`TierAttempt.usage` drop-or-document) | ✅ ticked + verified | Builder retained the field with forward-reserved docstring (`:122-127`) + inline comment (`:131-133`) naming the trigger ("partial-usage reporting is added"). The carry-over body explicitly offered "Either drop OR document" — recommendation said drop, but documenting was a sanctioned alternative. No drift; flagging as note (see Findings — LOW reminder). |
| TA-LOW-03 (timeout inheritance comment) | ✅ ticked + verified | Comment at `:401-403`: "Fallback routes inherit per_call_timeout_s from the primary TierConfig." Diff matches checkbox. |
| TA-LOW-04 (breaker bypass comment) | ✅ ticked + verified | Comment at `:404-407`: "Fallback routes bypass circuit-breaker bookkeeping (one shot per fallback; breaker is the primary tier's M8 mechanism)." No `_resolve_breaker()` call in the fallback loop. Diff matches checkbox. |

All ACs met; all four carry-over items ticked with corresponding diff hunks confirmed.

---

## 🔴 HIGH

*None.*

---

## 🟡 MEDIUM

*None.*

---

## 🟢 LOW

### LOW-1 — TA-LOW-02 framing: Builder labels documenting choice as "Deviation"

**Where:** `design_docs/phases/milestone_15_tier_overlay/issues/task_02_issue.md` Builder section + CHANGELOG. The Builder's own implementation notes describe retaining `TierAttempt.usage` as a "deviation from spec." Reading the carry-over body verbatim: *"Either drop the field (simplest) or document it as forward-reserved with a code comment naming the trigger."* — the document-with-comment path was explicitly sanctioned; the *recommendation* sub-bullet said drop. So the action is in-spec under the carry-over body's wording, but Builder language ("deviation") could mislead future audits.

**Severity rationale:** Cosmetic / framing only. Code is correct, documentation is correct, AC is met. No follow-up code change required.

**Action / Recommendation:** No action required this cycle. If future cleanup touches `TierAttempt`, prefer dropping the field if no consumer has emerged by then (it remains a forward-reserved zero-consumer field today). Note for the M15 close-out task: the choice should be re-examined when the partial-usage trigger fires, per the inline comment.

### LOW-2 — `CircuitOpen` cascade path lacks a unit-level hermetic test

**Where:** `tests/graph/test_tiered_node_fallback.py`. AC-12 is satisfied by code inspection but no dedicated hermetic test stubs the breaker open + asserts the cascade fires. The spec explicitly out-of-scopes the *HTTP* CircuitOpen cascade test ("T03"), and the existing Ollama breaker tests (in other files) cover the breaker-deny path. T02 didn't add a unit-level cascade-on-CircuitOpen test.

**Severity rationale:** AC-12 grades met (the code path is straightforward; both `not tier_config.fallback` (raise) and the fall-through-to-cascade branches are unit-reachable, and `_FailingAdapter` exercises the post-dispatch `NonRetryable` cascade entry, which uses the *same* loop body). Adding a CircuitOpen-specific hermetic test would harden coverage but is not required by the spec. The spec lists the "HTTP CircuitOpen cascade test (MCP transport)" as T03 scope.

**Action / Recommendation:** **Defer to T03** — the milestone has T03 ("`aiw list-tiers` command + HTTP CircuitOpen cascade test") on deck. T03's HTTP-transport cascade test will exercise the same code path end-to-end. If T03 doesn't add a unit-level hermetic supplement, raise this again then. No carry-over propagation needed today (T03 already covers the surface).

---

## Additions beyond spec — audited and justified

- **9 hermetic tests instead of 4** (spec called for 4). The five additional tests are:
  - `test_empty_fallback_primary_failure_reraises` — pins AC-6 (no cascade on empty fallback).
  - `test_per_attempt_log_records_for_cascade` and `test_all_fail_log_records` — pin AC-13 (per-attempt log records).
  - `test_tier_attempt_dataclass_fields` — pins AC-2 (TierAttempt shape).
  - `test_all_fallbacks_exhausted_error_is_non_retryable` — pins AC-1 (exception inheritance).

  All five are in-scope (each maps to a stated AC); no scope creep.
- **`_emit_failed_log` helper extracted.** Pure refactor to deduplicate three call-sites of the same `log_node_event(event="node_failed", ...)` pattern. Reduces duplication; no behaviour change. Justified.
- **`circuit_open_before_dispatch: bool` local sentinel.** Needed to thread the pre-dispatch breaker-deny case into the cascade entry without raising. Minimal scope; named clearly.
- **`primary_exc: BaseException | None` separation.** Refactor that splits primary-dispatch result extraction from the cascade entry decision; makes the control flow explicit and lets the success-path try/except preserve the budget-cap log invariant.

No drive-by refactors elsewhere in the module.

---

## Gate summary

| Gate | Command | Result |
|---|---|---|
| pytest (full) | `uv run pytest` | 1522 pass, 12 skip, 1 unrelated pre-existing flake (`tests/mcp/test_cancel_run_inflight.py::test_cancel_run_aborts_in_flight_task_and_flips_storage` — passes in isolation; does not touch `tiered_node` or `fallback`). Builder-reported `1523 passed` count consistent with the flake passing in their run. |
| pytest (target file) | `uv run pytest tests/graph/test_tiered_node_fallback.py -v` | 9/9 pass in 1.01s |
| pytest (regression) | `uv run pytest tests/graph/test_tiered_node.py` | 15/15 pass (existing tests unmodified) |
| lint-imports | `uv run lint-imports` | 5 contracts kept, 0 broken |
| ruff | `uv run ruff check` | All checks passed |

**Smoke test (per spec / verification discipline):** Hermetic test `test_cascade_succeeds_on_fallback_after_primary_fail` exercises the wire-level cascade: primary `_FailingAdapter` raises → fallback `_SuccessAdapter` returns → `CostTracker.total` reflects the fallback's cost → `_node` returns the fallback's text under `planner_output`. End-to-end through `_node()` with real `CostTrackingCallback` + `CostTracker`. Smoke surface is satisfied at the unit level; T03 owns the HTTP-transport smoke.

---

## Issue log — cross-task follow-up

| ID | Severity | Title | Owner | Status |
|---|---|---|---|---|
| M15-T02-ISS-01 | LOW | Re-examine `TierAttempt.usage` retention when partial-usage reporting trigger fires | M15 close-out (T05) or first consumer task | OPEN — informational only |
| M15-T02-ISS-02 | LOW | CircuitOpen cascade lacks unit-level hermetic test (HTTP smoke owned by T03) | T03 | OPEN — defer to T03 (already on deck) |

Neither finding requires forward-deferral propagation: ISS-01 is informational and properly noted via the inline code comment naming the trigger; ISS-02 is covered by T03's existing scope.

---

## Terminal gate — cycle 1 (2026-04-30)

| Reviewer | Verdict | Notes |
|---|---|---|
| sr-dev | SHIP | ADV notes on fixture teardown + triple-None guard + semaphore duplication; no FIX |
| sr-sdet | FIX-THEN-SHIP | 2 FIX items: RetryableTransient cascade test (FIX-1) + fallback RetryableSemantic pass-through test (FIX-2) |
| security-reviewer | SHIP | No findings |

**Bypass applied (loop-controller + sr-sdet concur):**

- Locked terminal decision (loop-controller + sr-sdet concur, 2026-04-30): Add `test_cascade_triggers_on_retryable_transient_primary_fail` to `tests/graph/test_tiered_node_fallback.py`. Primary adapter raises `RetryableTransient`; fallback succeeds. Assert: node returns fallback text, cost recorded. Per AC-3 which explicitly names `RetryableTransient` as a cascade trigger. Single clear recommendation; within spec.

- Locked terminal decision (loop-controller + sr-sdet concur, 2026-04-30): Add `test_cascade_retryable_semantic_from_fallback_propagates_unchanged` to `tests/graph/test_tiered_node_fallback.py`. Primary fails with `NonRetryable`; `fallback[0]` raises `RetryableSemantic`. Assert: `RetryableSemantic` propagates from `_node`, not `AllFallbacksExhaustedError`, `cost_tracker.total == 0`. Per AC-4 "from any dispatch (primary or fallback)". Single clear recommendation; within spec.

**Rationale for bypass vs. halt:** Both FIX items are pure test additions (no code changes). Both ACs are spec'd. Both have single clear recommendations with no design options for the user to arbitrate. Per lens-specialisation rule: sr-sdet SHIP/FIX on test-coverage lens + sr-dev SHIP on code-quality lens is bypass-eligible (not DIVERGENT VERDICTS). Proceeding to Builder cycle 2.

## Deferred to nice_to_have

*None.*

---

## Propagation status

*No forward-deferral required.* LOW-2 maps to T03's already-spec'd "HTTP CircuitOpen cascade test"; LOW-1 is informational only. No external task spec needs a `## Carry-over from prior audits` entry today.

---

## Cargo-cult / loop-spinning detection

- **Cycle-N-vs-cycle-(N-1) overlap:** N/A — first audit cycle for T02.
- **Rubber-stamp check:** Verdict `PASS` with substantial diff (~310 LoC code + 428 LoC test). Zero HIGH+MEDIUM findings. **Reasoning:** code was reviewed line-by-line against each AC; cascade entry/exit paths verified at `tiered_node.py:289-302, 310-358, 360-477, 498-557`; spec ACs cross-referenced to test-method assertions; gates re-run from scratch (not just trusting Builder's report); architecture/KDR drift checked against §3 (layer rule), §9 (KDR-004, KDR-006). Two LOWs raised (framing, deferred coverage). PASS is justified, not rubber-stamped.

---

## Cycle 2 — Build (2026-04-30)

### Scope (locked terminal decisions from cycle 1)

- **FIX-1:** Add `test_cascade_triggers_on_retryable_transient_primary_fail` — primary raises `RetryableTransient`, fallback succeeds. Per AC-3.
- **FIX-2:** Add `test_cascade_retryable_semantic_from_fallback_propagates_unchanged` — primary raises `NonRetryable`, fallback[0] raises `RetryableSemantic`. Per AC-4.

No code changes to `tiered_node.py`; pure test additions.

### Verification

- **FIX-1 verified at `tests/graph/test_tiered_node_fallback.py:449-474`.** Test stubs `gemini/a` to `_RetryableTransientAdapter` (which raises `RetryableTransient("rate-limit")`), allows `gemini/b` to default to `_SuccessAdapter` (text="ok", cost=0.25). Asserts `out["planner_output"] == "ok"`, `out["last_exception"] is None`, `tracker.total("run-1") > 0`. Correctly exercises AC-3's `RetryableTransient` cascade-trigger path.
- **FIX-2 verified at `tests/graph/test_tiered_node_fallback.py:482-508`.** Test stubs `gemini/a` to `_FailingAdapter` (raises `NonRetryable`), `gemini/b` to `_SemanticAdapter` (raises `RetryableSemantic`). Asserts `pytest.raises(RetryableSemantic)` (not `AllFallbacksExhaustedError`), `tracker.total("run-1") == 0`. Correctly exercises AC-4's "from any dispatch (primary or fallback)" defensive pass-through. The cascade is entered (primary raised `NonRetryable`), fallback[0] raises `RetryableSemantic` which propagates unchanged through the cascade-loop's `except RetryableSemantic: raise` guard at `tiered_node.py:429-432`.
- **No code-side regressions.** `tiered_node.py` unchanged this cycle (`git diff HEAD -- ai_workflows/graph/tiered_node.py` is the same set of cycle-1 hunks). All cycle-1 ACs still met.
- **Test file count:** 11 tests (9 cycle-1 + 2 cycle-2). All pass in 1.01s.

### Cycle-2 gate summary

| Gate | Command | Result |
|---|---|---|
| pytest (target file) | `uv run pytest tests/graph/test_tiered_node_fallback.py -v` | 11/11 pass in 1.01s |
| pytest (full) | `uv run pytest` | 1524 pass, 12 skip, 1 unrelated pre-existing flake (`tests/mcp/test_cancel_run_inflight.py::test_cancel_run_aborts_in_flight_task_and_flips_storage` — confirmed passes in isolation; unchanged from cycle 1) |
| lint-imports | `uv run lint-imports` | 5 contracts kept, 0 broken |
| ruff | `uv run ruff check` | All checks passed |

### Cycle-2 AC re-grading

All 13 ACs remain ✅ met. AC-3 and AC-4 strengthened by direct tests:

- **AC-3 (cascade dispatch wired)** — previously verified for `NonRetryable` primary-fail path; cycle 2 adds direct `RetryableTransient` primary-fail coverage.
- **AC-4 (RetryableSemantic defensive pass-through)** — previously verified for primary-route semantic raise (`test_cascade_skips_on_semantic_failure`); cycle 2 adds direct fallback-route semantic raise coverage, exercising the second `except RetryableSemantic: raise` guard in the cascade loop.

### Cycle-2 critical sweep

- **Test gaps:** None. The two FIX items targeted the only AC paths that were code-reachable but not test-pinned in cycle 1.
- **Doc drift:** None. No code changes; no module-docstring change required.
- **Status surfaces:** Spec `Status:` line + milestone README task-table row remain ✅ Built (cycle 1 wording is still accurate — code didn't move). Issue file updated to cycle 2.
- **Carry-over checkbox-cargo-cult:** All four `[x]` task-analysis carry-overs remain validated against cycle-1 diff hunks; no new carry-overs introduced this cycle.
- **Cycle-2-vs-cycle-1 overlap (loop-spinning):** Cycle 2 raises **zero new findings**. The two cycle-1 LOWs (LOW-1 framing, LOW-2 CircuitOpen unit-test deferred to T03) are unchanged. Loop is converging, not spinning.
- **Rubber-stamp check:** Verdict `PASS`, cycle-2 diff ~62 LoC (test-only). Below the 50-LoC rubber-stamp threshold for the test-only addition, but functionally sound: both new tests verified line-by-line against AC-3 / AC-4; both run green; both exercise paths that were previously code-only-reachable. Not a rubber-stamp PASS.

### Cycle-2 verdict

✅ **PASS — no new findings, no carry-over to cycle 3.** Both terminal-gate FIX items landed correctly. Two LOWs from cycle 1 stay as recorded (LOW-1 informational, LOW-2 deferred to T03). Task ready to commit.

---

## Terminal gate — cycle 2 (2026-04-30)

| Reviewer | Verdict | Notes |
|---|---|---|
| sr-dev | SHIP | No new findings beyond cycle-1 advisories. Cycle-2 test additions are mechanically correct. |
| sr-sdet | SHIP | FIX-1 and FIX-2 confirmed correctly implemented. No new gaps. |
| security-reviewer | SHIP | Two hermetic test additions; no security-relevant changes. Carry-forward ADV-1 (str(exc) propagation) unchanged from cycle 1. |

**Dependency audit:** Skipped — `pyproject.toml` and `uv.lock` were not touched in this task.

**Terminal gate verdict: TERMINAL CLEAN** — all three reviewers returned SHIP. Task is ready for commit.

## Sr. Dev review (2026-04-30)
**Files reviewed:** `tests/graph/test_tiered_node_fallback.py` (lines 449-508, the two cycle-2 additions) | **Skipped:** `ai_workflows/graph/tiered_node.py` (unchanged this cycle; fully reviewed in cycle 1) | **Verdict:** SHIP

### 🔴 BLOCK

None.

### 🟠 FIX

None.

### 🟡 Advisory

None beyond the three cycle-1 advisory items (ADV-1 no-yield teardown, ADV-2 triple-None guard, ADV-3 semaphore duplication). The two new tests follow the same patterns as the 9 cycle-1 tests and do not introduce any new divergences from those advisories.

### What passed review (one line per lens)

- **Lens 1 (hidden bugs):** Both new async test functions are correctly awaited; `asyncio_mode = "auto"` in `pyproject.toml` means no `@pytest.mark.asyncio` is required (correct). The `_ADAPTER_MAP` module-level dict is always cleared before each test by the `autouse` fixture, so `_RetryableTransientAdapter` set in FIX-1 does not bleed into FIX-2. `tracker.total("run-1") == 0` assertion in FIX-2 correctly confirms the semantic pass-through path never reaches cost attribution. No off-by-one, no missing await, no swallowed exception.
- **Lens 2 (defensive creep):** Neither test introduces unnecessary guards. Both are tight: set map entries, monkeypatch adapter, run node, assert outcome. No spurious `try/except`, no `if x is not None` against non-optional types.
- **Lens 3 (idiom alignment):** Pattern matches all 9 cycle-1 tests identically — `_make_registry`, `_build_config`, `monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", ...)`, direct `await node({}, config)`. No idiom drift.
- **Lens 4 (premature abstraction):** No new helpers or fixtures introduced. Both tests are self-contained in the same style as siblings.
- **Lens 5 (comment/docstring drift):** Docstrings name the AC, the stimulus, and the expected outcome. Locked-terminal-decision traceability comment present in each. No restatement of code; no multi-paragraph bloat.
- **Lens 6 (simplification):** No simplification opportunities. Both functions are already at minimum viable length for their scope.

## Sr. SDET review (2026-04-30)
**Test files reviewed:** `tests/graph/test_tiered_node_fallback.py` (lines 449-508 for cycle-2 additions; full file for context) | **Skipped:** none | **Verdict:** SHIP

### 🔴 BLOCK
None.

### 🟠 FIX
None.

### 🟡 Advisory
None. Both FIX items from cycle 1 landed correctly. No new advisory items introduced.

### What passed review

- **Lens 1 (wrong reason):** Both FIX tests assert real observable behaviour. FIX-1 stubs `gemini/a` to `_RetryableTransientAdapter` and asserts `out["planner_output"] == "ok"`, `out["last_exception"] is None`, and `tracker.total("run-1") > 0`. FIX-2 uses `pytest.raises(RetryableSemantic)` and checks `tracker.total("run-1") == 0`. The `pytest.raises(RetryableSemantic)` assertion is load-bearing: if the `except RetryableSemantic: raise` guard were absent, `AllFallbacksExhaustedError` would be raised instead. No tautologies.
- **Lens 2 (coverage gaps):** Both FIX items from cycle 1 are now directly covered. No new gaps introduced.
- **Lens 3 (mock overuse):** Both new tests use the `_RoutingLiteLLMAdapter` / `_ADAPTER_MAP` pattern with real `CostTracker`, real `CostTrackingCallback`. No bare `MagicMock()`.
- **Lens 4 (fixture hygiene):** `_reset_adapter_map` autouse fixture unchanged; no ordering dependency introduced.
- **Lens 5 (hermetic gating):** Both new tests are fully hermetic. No provider calls, no network I/O, no subprocess.
- **Lens 6 (naming and assertion hygiene):** Test names satisfy the "what it verifies" standard. `tracker.total("run-1") == 0` is a scalar equality with no ambiguity.

## Security review (2026-04-30)

Cycle 2 delta: two test functions added to `tests/graph/test_tiered_node_fallback.py` (lines 449-508). No changes to `ai_workflows/graph/tiered_node.py` or any other production file.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

Carry-forward from cycle 1 — ADV-1 (str(exc) propagation may embed provider error messages into re-raised bucket strings, file `ai_workflows/graph/tiered_node.py` primary and fallback dispatch paths). Cycle 2 did not introduce or worsen this. See cycle 1 review for full detail.

No new advisory findings introduced in cycle 2.

**Verdict:** SHIP
