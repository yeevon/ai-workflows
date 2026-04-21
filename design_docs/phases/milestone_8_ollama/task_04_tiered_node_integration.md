# Task 04 — `TieredNode` Integration + Workflow Fallback Edges

**Status:** 📝 Planned.
**Grounding:** [milestone README §Exit criteria 2 + 3](README.md) · [architecture.md §4.2 / §8.4](../../architecture.md) · [KDR-003, KDR-006](../../architecture.md).

## What to Build

Wire the T02 `CircuitBreaker` into `TieredNode` for LiteLLM routes that
target Ollama, and compose the T03 fallback gate into both shipped
workflows (`planner`, `slice_refactor`) so an Ollama outage mid-run
routes through the gate and honours the user's `FallbackChoice`.

Two distinct pieces of work:

1. **Graph-layer hook** (`ai_workflows/graph/tiered_node.py`) — read an
   optional breaker from `config.configurable["ollama_circuit_breakers"]`,
   consult it on every call whose route is `kind="litellm"` and whose
   `model.startswith("ollama/")`, raise `CircuitOpen` when the breaker
   denies, record success/failure on the breaker on the response path.
2. **Workflow-layer composition** (`ai_workflows/workflows/planner.py`,
   `ai_workflows/workflows/slice_refactor.py`) — add a `catch_circuit_open`
   conditional edge that routes `CircuitOpen` into the fallback gate
   and dispatches on the returned `FallbackChoice`.

## Deliverables

### Graph-layer hook — [ai_workflows/graph/tiered_node.py](../../../ai_workflows/graph/tiered_node.py)

Extend the existing `TieredNode` function:

- Read optional `breakers = config["configurable"].get("ollama_circuit_breakers") or {}`
  at node entry. Shape: `dict[tier_name, CircuitBreaker]`.
- Only consult the breaker when the resolved route is `LiteLLMRoute`
  **and** `route.model.startswith("ollama/")`. Gemini-backed LiteLLM
  tiers and `ClaudeCodeRoute` are never breakered.
- Pre-call: `if not await breaker.allow(): raise CircuitOpen(tier=..., last_reason=breaker.last_reason)`.
  `CircuitOpen` classifies as `NonRetryable` (it already is — see KDR-006:
  "anything else → NonRetryable"), but the workflow-layer edge
  detects the specific exception **type** (not just the bucket) so the
  fallback gate runs instead of the standard non-retryable abort path.
- Post-call, success: `await breaker.record_success()` before the
  existing `cost_callback.on_node_complete(...)` hook.
- Post-call, failure: after the classify step, if the raised bucket
  is `RetryableTransient`, call `await breaker.record_failure(reason=type(exc).__name__)`.
  Rationale: the three-bucket taxonomy already marks transient provider
  errors (timeout, connection refused, 5xx) as `RetryableTransient`;
  treating those exhaustively as breaker-trip signals matches §8.4's
  "on ConnectionError" policy. `NonRetryable` failures (auth, bad
  request, budget) do **not** count as Ollama-health signals.
- Structured-log field addition: when the breaker is consulted, add
  `breaker_state=<closed|open|half_open>` to the node's success/failure
  log record. One field extension; no new log event.

**No module-level state.** The breaker map is passed via `configurable`
exactly like the existing `tier_registry`, `cost_tracker`, and
`semaphores` collaborators (M2 T03 / M6 T03 convention).

### Workflow-layer composition

#### [ai_workflows/workflows/planner.py](../../../ai_workflows/workflows/planner.py)

Add an `ollama_fallback` gate node and a conditional edge:

```
explorer ──(CircuitOpen)──▶ ollama_fallback ──▶
    RETRY     → explorer (re-fire same tier)
    FALLBACK  → explorer (with mid-run tier swap, see below)
    ABORT     → _hard_stop (status='aborted'; reuse M6 T07 terminal)
```

The `explorer` node's `TieredNode` reads an optional state-level
override key `_mid_run_tier_overrides: dict[logical, replacement]`.
When the fallback gate returns `FALLBACK`, the edge handler stamps
`{"local_coder": "gemini_flash"}` (or whatever the workflow declares
as its fallback tier pair) into that state key. On the next entry into
`explorer`, `TieredNode` resolves its logical tier through that state
override before falling back to the registry — same substitution rule
as the M5 T04 CLI `--tier-override`, but sourced from state instead of
CLI flags so it's scoped to this run only.

Declare the planner's fallback pair at the top of `build_planner()`
using a new `OllamaFallback` pydantic config block:

```python
class OllamaFallback(BaseModel):
    logical: str              # "local_coder"
    fallback_tier: str        # "gemini_flash"
```

Pass it into the gate factory via `build_ollama_fallback_gate(
gate_id="ollama_fallback", tier_name=<logical>, fallback_tier=<replacement>)`.

#### [ai_workflows/workflows/slice_refactor.py](../../../ai_workflows/workflows/slice_refactor.py)

Same pattern, wired into the parallel `slice_branch` fan-out:

- Each branch's inner `slice_worker` `TieredNode` consults the shared
  breaker (the breaker map is run-scoped, not branch-scoped — matching
  the per-tier `asyncio.Semaphore` convention from M6 T03).
- `CircuitOpen` in any branch routes that branch to the single
  run-scoped `ollama_fallback` gate (not one gate per branch — a
  `HumanGate` built with the same `(run_id, gate_id)` dedupe on
  `gate_responses`).
- On `FALLBACK`: the mid-run override stamp applies to *all* slice
  branches for the remainder of the run. On `RETRY`: only the
  originating branch re-fires. On `ABORT`: route to `_hard_stop`.

Document the single-gate-for-all-branches design inline at the gate
wiring site — it is the subtlest decision in this task, and the audit
is going to check it explicitly against §8.4's "pause the run" wording
(one pause, not N pauses for N parallel branches).

### Mid-run tier override plumbing

Extend the existing tier-override resolution path so `TieredNode` reads
overrides from state **in addition to** `configurable`. Precedence:

1. State-level `_mid_run_tier_overrides[logical]` (this task).
2. Configurable-level `tier_overrides[logical]` (M5 T04).
3. Registry default.

Only one mechanism may fire per call — the first match wins. Document
this precedence order in `TieredNode`'s docstring.

### Tests

#### [tests/graph/test_tiered_node_ollama_breaker.py](../../../tests/graph/test_tiered_node_ollama_breaker.py)

- `test_breaker_open_raises_circuit_open_without_provider_call` — stub
  adapter raises `AssertionError` on any call; pre-trip the breaker;
  invoke the node; assert `CircuitOpen` was raised and the adapter was
  never called.
- `test_breaker_half_open_allows_single_probe` — half-open breaker;
  stub adapter succeeds; assert call fires, breaker transitions to
  CLOSED, node returns normally.
- `test_transient_failure_records_on_breaker` — stub raises
  `litellm.APIConnectionError`; assert `breaker.record_failure` was
  called with `reason="APIConnectionError"`; assert node re-raises
  `RetryableTransient` as before (breaker hook is purely additive).
- `test_non_retryable_failure_does_not_record_on_breaker` — stub raises
  `litellm.AuthenticationError`; assert `breaker.record_failure` was
  **not** called; node raises `NonRetryable`.
- `test_non_ollama_litellm_route_bypasses_breaker` — route model is
  `"gemini/gemini-2.5-flash"`; even with a tripped breaker in the
  configurable map, the node calls the provider and does not touch
  the breaker.
- `test_claude_code_route_bypasses_breaker` — `ClaudeCodeRoute` tier;
  breaker-present but untouched.
- `test_structured_log_includes_breaker_state` — breaker CLOSED +
  success; assert the node's success log record carries
  `breaker_state="closed"`.

#### [tests/workflows/test_planner_ollama_fallback.py](../../../tests/workflows/test_planner_ollama_fallback.py)

- `test_retry_re_fires_same_tier` — explorer fails three times with
  `APIConnectionError` (trips breaker), gate fires, resume with `RETRY`
  plus a healthy stub on the next call; assert run completes with
  the explorer tier's original route.
- `test_fallback_routes_to_replacement_tier` — same setup; resume with
  `FALLBACK`; assert the next explorer call dispatches to the
  `gemini_flash` route (stub records `route.model == "gemini/gemini-2.5-flash"`).
- `test_abort_terminates_hard_stop` — resume with `ABORT`; assert
  `runs.status == "aborted"`, no further provider calls fire.

#### [tests/workflows/test_slice_refactor_ollama_fallback.py](../../../tests/workflows/test_slice_refactor_ollama_fallback.py)

- `test_single_gate_for_all_branches` — three parallel slice workers,
  first to trip the breaker stamps state; subsequent branches waiting
  on the shared breaker observe CLOSED→OPEN and route to the *same*
  `(run_id, gate_id="ollama_fallback")` gate; assert `record_gate`
  fired exactly once for the run.
- `test_fallback_applies_to_subsequent_branches` — resume with
  `FALLBACK`; the two branches still pending run against the
  replacement tier. (The originating branch re-fires per RETRY-style
  semantics — exact wording is subtle; pin the behaviour in the test.)
- `test_abort_cancels_pending_branches` — resume with `ABORT`; the
  pending branches terminate via `_hard_stop`; no artefact rows land.

## Acceptance Criteria

- [ ] `TieredNode` reads `ollama_circuit_breakers` from `configurable`
      and consults only for `LiteLLMRoute` + `model.startswith("ollama/")`.
- [ ] `CircuitOpen` raised pre-call when breaker denies; adapter not
      called on that path.
- [ ] `record_success` on success path; `record_failure` only for
      `RetryableTransient`-bucketed exceptions.
- [ ] `breaker_state` surfaces in the node's structured log record.
- [ ] Mid-run tier override via `_mid_run_tier_overrides` takes
      precedence over the existing configurable override path.
- [ ] `planner` + `slice_refactor` both route `CircuitOpen` through a
      single `ollama_fallback` `HumanGate` per run.
- [ ] `slice_refactor` parallel branches share one gate per run, not
      one per branch.
- [ ] `FallbackChoice.RETRY` / `FALLBACK` / `ABORT` each route
      correctly (RETRY → re-fire same tier; FALLBACK → replacement
      tier; ABORT → `_hard_stop`).
- [ ] Every listed test passes under `uv run pytest tests/graph/test_tiered_node_ollama_breaker.py tests/workflows/test_planner_ollama_fallback.py tests/workflows/test_slice_refactor_ollama_fallback.py`.
- [ ] Full `uv run pytest` green (no regression on existing tests
      — especially M6's hard-stop / cancel tests).
- [ ] `uv run lint-imports` — **4 contracts kept**.
- [ ] `uv run ruff check` clean.

## Dependencies

- [Task 01](task_01_health_check.md), [Task 02](task_02_circuit_breaker.md),
  [Task 03](task_03_fallback_gate.md).

## Out of scope (explicit)

- Persisting breaker state across process restarts. (Process-local
  per T02.)
- Retroactive fallback for past failures (i.e. undoing a completed
  branch's output because a later branch tripped the breaker). State
  is forward-only.
- Circuit breakers for non-Ollama tiers (Gemini, Claude Code). Gemini
  has its own rate-limit handling via `RetryableTransient`; Claude
  Code has its own startup probe (§8.4). No breaker logic there.
- A `--no-ollama-breaker` CLI flag. Not on the punch list; breakers
  activate only when the configurable is populated, so tests /
  unrelated workflows can leave them off by not passing the map.
