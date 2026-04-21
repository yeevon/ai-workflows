# Task 05 — Degraded-Mode End-to-End Test

**Status:** 📝 Planned.
**Grounding:** [milestone README §Exit criteria 4](README.md) · [architecture.md §8.4](../../architecture.md) · [M7 T02 / T03 capture-replay convention](../milestone_7_evals/task_02_capture_callback.md).

## What to Build

A hermetic-first, live-optional test pair that proves the full
degraded-mode path: Ollama outage mid-run → circuit trips → fallback
gate fires → each `FallbackChoice` branch lands correctly.

Two test files:

1. **Hermetic suite** (`tests/workflows/test_ollama_outage.py`) — runs
   on every `uv run pytest`, uses a stub `LiteLLMAdapter` that raises
   `httpx.ConnectError` for the first N calls and succeeds afterwards.
   Covers the three `FallbackChoice` outcomes against both `planner`
   and `slice_refactor` on the hermetic stub path.
2. **E2E smoke** (`tests/e2e/test_ollama_outage_smoke.py`) — gated on
   `AIW_E2E=1`, drives a real Ollama instance that the tester
   temporarily stops mid-run. Spec-only; the test docstring tells the
   operator the manual-intervention sequence. Mirrors the M3 T07 /
   M6 T08 e2e smoke shape.

## Deliverables

### Hermetic suite — [tests/workflows/test_ollama_outage.py](../../../tests/workflows/test_ollama_outage.py)

Reuses the stub-adapter pattern already established in
`tests/workflows/test_planner_graph.py` + `test_slice_refactor_e2e.py`.
Fixtures:

- `_injected_breakers` — build `{"local_coder": CircuitBreaker(tier="local_coder",
  trip_threshold=3, cooldown_s=0.01)}`, inject via `_dispatch` to both
  `build_planner()` and `build_slice_refactor()`.
- `_flaky_ollama_adapter` — class-level `fail_first_n: int` counter
  decrements each call; first N calls raise `litellm.APIConnectionError`,
  subsequent calls return a valid JSON stub.
- `_healthy_gemini_stub` — separate adapter class that records
  `route.model` so the `FALLBACK` test can assert the replacement
  tier was actually used.

Test cases:

- `test_planner_outage_retry_succeeds` — explorer fails three times
  (breaker trips), gate fires, resume with `retry`, flaky adapter now
  healthy on the next call; assert run completes with
  `route.model == "ollama/qwen2.5-coder:32b"` for every post-gate call.
- `test_planner_outage_fallback_succeeds` — same flaky setup; resume
  with `fallback`; assert subsequent explorer calls dispatch against
  `"gemini/gemini-2.5-flash"` (the fallback tier), and the final run
  status is `completed`.
- `test_planner_outage_abort_terminates` — resume with `abort`; assert
  `runs.status == "aborted"`, `finished_at` is stamped, no further
  provider calls fire. (Uses the M6 T07 `_hard_stop` terminal — confirm
  the assertion set matches that task's precedent.)
- `test_slice_refactor_outage_single_gate` — three parallel branches,
  flaky adapter trips breaker on the first branch's retry loop;
  assert `Storage.record_gate` was invoked exactly once with
  `gate_id="ollama_fallback"`, and the two sibling branches suspended
  on the shared breaker rather than each emitting their own gate.
- `test_slice_refactor_outage_fallback_applies_to_siblings` — resume
  with `fallback`; assert both sibling branches re-fire against the
  `gemini_flash` replacement; final run status is `completed` with
  the expected `artifacts` rows.
- `test_slice_refactor_outage_abort_cancels_pending_branches` — resume
  with `abort`; assert no `slice_result:*` artefact rows land, and
  `runs.status == "aborted"`.

No live HTTP — all network I/O is stubbed at the adapter boundary.

### E2E smoke — [tests/e2e/test_ollama_outage_smoke.py](../../../tests/e2e/test_ollama_outage_smoke.py)

Gated by `AIW_E2E=1` (collection hook in `tests/e2e/conftest.py`).
Single test function, with a **manual-intervention procedure in the
docstring** matching the operator-run shape of `test_planner_smoke.py`:

```python
def test_planner_outage_degraded_mode_live() -> None:
    """Drive planner against live Ollama, then stop Ollama mid-run.

    Procedure (operator-run):
      1. `ollama serve` running on localhost:11434 with qwen2.5-coder:32b pulled.
      2. `AIW_E2E=1 uv run pytest tests/e2e/test_ollama_outage_smoke.py -v`
      3. When the test prints 'PAUSED — stop Ollama now', stop the daemon:
         `sudo systemctl stop ollama` (or kill the process).
      4. The test waits up to 60s for the breaker to trip + gate to fire,
         then resumes with FallbackChoice.FALLBACK. Restart Ollama when the
         test completes to leave the machine in a good state.

    Assertions (post-resume):
      - Final status: 'completed'.
      - At least one TokenUsage row with model starting with 'gemini/' —
        proves fallback actually routed.
      - Circuit breaker logs show CLOSED → OPEN → HALF_OPEN → CLOSED
        transitions in the structured log record.
    """
```

This test is operator-run (the way `test_planner_smoke.py` is) — it
does not need to be fully automated. Its role is to validate the
live path once per M8 close-out, not to run on CI.

### CHANGELOG

Standard `### Added — M8 Task 05: Degraded-Mode E2E Test (<date>)`
entry under `## [Unreleased]`.

### No CI change

The hermetic suite runs inside the existing `test` job — no new CI
job needed. The e2e smoke stays manual-trigger-only (there's no
GitHub Actions runner with Ollama installed, and that's the right
default).

## Acceptance Criteria

- [ ] `tests/workflows/test_ollama_outage.py` — all six hermetic cases
      pass under `uv run pytest`.
- [ ] `tests/e2e/test_ollama_outage_smoke.py` — skipped by default,
      runnable under `AIW_E2E=1` with a live Ollama instance; docstring
      documents the manual-intervention procedure.
- [ ] Hermetic suite exercises all three `FallbackChoice` branches on
      both `planner` and `slice_refactor`.
- [ ] Single-gate-per-run invariant verified for `slice_refactor`
      (one `record_gate` call regardless of parallel branch count).
- [ ] `uv run pytest` — full suite green (no regression on M6/M7).
- [ ] `uv run lint-imports` — **4 contracts kept**.
- [ ] `uv run ruff check` clean.

## Dependencies

- [Task 01](task_01_health_check.md) through [Task 04](task_04_tiered_node_integration.md).

## Out of scope (explicit)

- CI runner with a live Ollama daemon. (Manual-trigger-only remains
  the right trade-off; adding Ollama to the CI runner image is a
  nice_to_have at best, and the hermetic suite is the PR gate.)
- Chaos-style test harness (random daemon kills, partitioned networks).
  The fail-first-N stub is sufficient for the gate + breaker contract.
- Cross-provider degraded mode (e.g. Gemini free-tier quota exhaustion
  routing to Claude Code). Gemini quota failures are `RetryableTransient`
  via the existing taxonomy; M8 scope is Ollama-specific.
