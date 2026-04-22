# Milestone 8 — Ollama Infrastructure

**Status:** ✅ Complete (2026-04-21).
**Grounding:** [architecture.md §8.4](../../architecture.md) · [roadmap.md](../../roadmap.md).

## Goal

Harden the Qwen/Ollama provider path now that M5/M6 make it load-bearing. Health check, circuit breaker, and fallback `HumanGate` to Gemini when Ollama is unavailable.

## Exit criteria

1. An Ollama health-check module probes the configured endpoint on startup and on a periodic schedule during long runs.
2. A circuit breaker trips after N consecutive failures and short-circuits subsequent calls to a fallback path without waiting for per-call timeouts.
3. A fallback `HumanGate` offers the user the choice to retry, fall back to a higher tier (e.g. `gemini_flash`), or abort — per [architecture.md §8.4](../../architecture.md).
4. Integration test simulates Ollama outage mid-run and exercises all three fallback branches.
5. Gates green.

## Non-goals

- Docker Compose packaging of Ollama — see [nice_to_have.md §5](../../nice_to_have.md).
- Langfuse-backed observability of the circuit breaker — see [nice_to_have.md §1](../../nice_to_have.md).

## Key decisions in effect

| Decision | Reference |
| --- | --- |
| Provider health & fallback semantics | [architecture.md §8.4](../../architecture.md) |
| 3-bucket retry taxonomy | KDR-006 |

## Task order

| # | Task |
| --- | --- |
| 01 | [`OllamaHealthCheck` probe primitive](task_01_health_check.md) |
| 02 | [`CircuitBreaker` primitive (N-failure trip + cooldown)](task_02_circuit_breaker.md) |
| 03 | [Fallback `HumanGate` wiring (retry / fallback-tier / abort)](task_03_fallback_gate.md) |
| 04 | [Integration with `TieredNode` + workflow fallback edges](task_04_tiered_node_integration.md) |
| 05 | [Degraded-mode end-to-end test](task_05_degraded_mode_e2e.md) |
| 06 | [Milestone close-out](task_06_milestone_closeout.md) |

Task files landed 2026-04-21 after M7 close. The README stub's periodic
health-check language is **reframed at T01**: the primary mid-run
health signal is per-call failure classified through the existing
three-bucket taxonomy (KDR-006); the `probe_ollama` primitive is a
one-shot diagnostic tool, not a scheduled poller. Periodic polling
stays out of scope unless a future milestone surfaces an operational
need — recorded at T01's *Out of scope* section.

## Outcome

All six tasks landed clean. Every task issue file at
[issues/task_0\[1-6\]_issue.md](issues/) carries a `✅ PASS` status line;
no `🔴 HIGH` or `🟡 MEDIUM` is open. Two `🟢 LOW` flags from T05 were
forward-deferred to this close-out as retrospective notes (see
[Spec drift observed during M8](#spec-drift-observed-during-m8) below);
nothing deferred to `nice_to_have.md`.

**Summary of landed surface:**

- **Health probe ([task 01](task_01_health_check.md))** —
  `probe_ollama` + `HealthResult` primitive under
  [`ai_workflows/primitives/llm/ollama_health.py`](../../../ai_workflows/primitives/llm/ollama_health.py);
  never raises; five reason strings (`ok`, `connection_refused`,
  `timeout`, `http_<status>`, `error:<type>`). README stub's
  "periodic health check" language reframed at T01 — primary mid-run
  signal is per-call failure classified through KDR-006; `probe_ollama`
  is a one-shot diagnostic tool, not a scheduled poller.
- **Circuit breaker ([task 02](task_02_circuit_breaker.md))** —
  `CircuitBreaker` / `CircuitOpen` / `CircuitState` under
  [`ai_workflows/primitives/circuit_breaker.py`](../../../ai_workflows/primitives/circuit_breaker.py);
  process-local, `asyncio.Lock`-guarded; CLOSED → OPEN → HALF_OPEN →
  CLOSED transitions verified under concurrent branches. Tuning locked
  at `trip_threshold=3`, `cooldown_s=60.0` defaults.
- **Fallback gate ([task 03](task_03_fallback_gate.md))** —
  `build_ollama_fallback_gate` under
  [`ai_workflows/graph/ollama_fallback_gate.py`](../../../ai_workflows/graph/ollama_fallback_gate.py);
  strict-review; `FallbackChoice.{RETRY, FALLBACK, ABORT}`;
  state-key contract (`_ollama_fallback_reason` / `_ollama_fallback_count`
  / `ollama_fallback_decision`) frozen.
- **Integration ([task 04](task_04_tiered_node_integration.md))** —
  `TieredNode` reads `ollama_circuit_breakers` from `configurable`
  and consults the breaker only for `LiteLLMRoute` tiers with
  `model.startswith("ollama/")`. `CircuitOpen` routes planner +
  slice_refactor through a single fallback gate per run
  (slice_refactor parallel branches share the gate via the
  `_route_before_aggregate` short-circuit). Mid-run tier override via
  `_mid_run_tier_overrides` state key takes precedence over
  `configurable['tier_overrides']` and over the registry default.
  `PLANNER_OLLAMA_FALLBACK.fallback_tier` and
  `SLICE_REFACTOR_OLLAMA_FALLBACK.fallback_tier` both resolve to
  `planner-synth` (Claude Code OAuth subprocess) — see *Spec drift*
  below for the gemini_flash vs. planner-synth delta observed at T05
  audit.
- **Degraded-mode tests ([task 05](task_05_degraded_mode_e2e.md))** —
  hermetic suite
  [`tests/workflows/test_ollama_outage.py`](../../../tests/workflows/test_ollama_outage.py)
  covers the `FallbackChoice` branches on both workflows through the
  full `run_workflow` + `resume_run` dispatch path (six tests);
  operator-run live smoke
  [`tests/e2e/test_ollama_outage_smoke.py`](../../../tests/e2e/test_ollama_outage_smoke.py)
  documents the manual Ollama-stop procedure in its docstring,
  gated by `AIW_E2E=1` + a four-way prereq probe. T05 also closed
  the T04 dispatch-wiring gap: `_build_ollama_circuit_breakers`
  in [`_dispatch.py`](../../../ai_workflows/workflows/_dispatch.py)
  now auto-constructs one `CircuitBreaker` per Ollama-backed tier,
  threaded through `configurable["ollama_circuit_breakers"]` for
  production runs (previously only hermetic tests supplied the dict).
- **Manual verification:** The T05 docstring operator procedure was
  walked once at close-out time with a live Ollama daemon — see the
  *Close-out-time live verification* block in the M8 CHANGELOG entry
  for the baseline pass/fail.
- **Green-gate snapshot (2026-04-21):**
  `uv run pytest` → 587 passed, 5 skipped (4 pre-existing e2e smokes
  plus the new T05 live smoke), 2 pre-existing `yoyo` warnings;
  `uv run lint-imports` → **4 contracts kept** (no new layer contract
  added at M8 — all new modules fit `primitives/` + `graph/`);
  `uv run ruff check` → clean.

### Spec drift observed during M8

Two LOW-severity retrospective notes forward-deferred from the T05
audit, recorded here so future readers hit the explanation once
instead of rediscovering each delta:

- **T05 AC-3 vs deliverables mismatch.** AC-3 demanded "all three
  `FallbackChoice` branches on both `planner` and `slice_refactor`",
  but the spec's own deliverables list for `slice_refactor` named
  only three tests — `single_gate` (invariant, no resume-choice),
  `fallback`, `abort`. No explicit RETRY dispatch-level test was
  asked for; the RETRY semantics are covered at the unit level by
  [`tests/workflows/test_slice_refactor_ollama_fallback.py::test_retry_refires_affected_slices`](../../../tests/workflows/test_slice_refactor_ollama_fallback.py).
  No code change taken. Source:
  [issues/task_05_issue.md §LOW ISS-01](issues/task_05_issue.md).
- **T05 spec body names `gemini_flash` as the fallback replacement
  tier; as-built is `planner-synth`.** The T05 spec body and its
  `_healthy_gemini_stub` fixture description anticipated that
  `FallbackChoice.FALLBACK` re-routes the tripped Ollama tier to
  `gemini_flash`. M8 T04's actual `PLANNER_OLLAMA_FALLBACK` /
  `SLICE_REFACTOR_OLLAMA_FALLBACK` config pinned
  `fallback_tier="planner-synth"` (Claude Code OAuth subprocess).
  The T05 ACs themselves do not name the replacement tier, so the
  implementation is compatible; T05's hermetic
  `test_planner_outage_fallback_succeeds` correctly asserts
  `_HealthyClaudeCodeStub.routed_flags == ["opus", "opus"]`.
  Source: [issues/task_05_issue.md §LOW ISS-02](issues/task_05_issue.md).

## Carry-over from prior milestones

*None.* M7 T06 closed clean.

## Issues

Land under [issues/](issues/).
