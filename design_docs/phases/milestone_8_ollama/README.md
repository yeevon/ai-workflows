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
| 01 | `OllamaHealthCheck` module (probe + periodic scheduler) |
| 02 | `CircuitBreaker` primitive (N-failure trip + cooldown) |
| 03 | Fallback `HumanGate` wiring (retry / fallback-tier / abort) |
| 04 | Integration with `TieredNode` for `local_coder`-routed tiers |
| 05 | End-to-end degraded-mode test (simulated outage) |
| 06 | Milestone close-out |

Per-task files generated once M7 closes (or if promoted earlier).

## Issues

Land under [issues/](issues/).
