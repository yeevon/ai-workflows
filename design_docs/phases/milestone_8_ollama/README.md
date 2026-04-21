# Milestone 8 — Ollama Infrastructure

**Status:** 📝 Planned. Starts once [M7](../milestone_7_evals/README.md) closes clean (or earlier if Qwen flakiness blocks M5/M6 in practice).
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

## Issues

Land under [issues/](issues/).
