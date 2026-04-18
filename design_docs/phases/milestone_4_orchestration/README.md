# Milestone 4 — Orchestration Components (+ Ollama Infrastructure)

## Goal

Now that `slice_refactor` demands a DAG (cross-repo dependencies), promote the linear `Pipeline` to a DAG `Orchestrator`. Add `Planner`, `AgentLoop`, `HumanGate`, and full `aiw resume`. Also wire up Ollama operational infrastructure — health checks, VPN drop handling, fallback to Haiku.

**Exit criteria:** a Planner produces a DAG, the Orchestrator executes it with parallel branches, a HumanGate pauses between planning and execution, `aiw resume` picks up from any checkpointed state. Ollama runs reliably against your home desktop with fallback to Haiku on network failures.

## Scope Changes from Original M4

- **DAG Orchestrator now arrives at M4** instead of M1 (SD-02). Promotes from linear `Pipeline`. `networkx` optional-dep installed here.
- **Ollama operational infrastructure now here** (SD-03): health check, circuit breaker, auto-fallback to Haiku.
- **AgentLoop subagent context isolation** is explicit (CRIT-11): fresh context per subagent by default.
- **Send-equivalent runtime fan-out** designed in but deferred to M5 if not needed by first DAG workflow.

## Key Decisions In Effect

| Decision | Value |
| --- | --- |
| DAG implementation | `pydantic-graph` (preferred) or `networkx` for topological sort |
| Planner | Two-phase: Qwen exploration → Opus planning with tools |
| Plan parse retry | Max 3 via `ModelRetry`, then abort |
| Plan max tasks | Configurable, default 50 |
| Concurrency | Per-provider semaphore |
| Double failure | Full hard stop (same as Pipeline but DAG-aware) |
| AgentLoop guarantee | Weak, documented. Orchestrator mandates Validator after every step |
| AgentLoop subagent context | Fresh per subagent (default). Opt-in shared via `shared_context: true` |
| AgentLoop termination | No tool calls OR `done` tool OR `max_iterations` |
| HumanGate timeout | `None` for `strict_review=True` (wait forever). 30 min otherwise |
| Ollama fallback | On `ConnectionError`: pause run, prompt user to fall back to Haiku or retry |

## Task Order

1. `task_01_planner.md` — two-phase Planner
2. `task_02_agent_loop.md` — fresh-context subagents
3. `task_03_orchestrator.md` — DAG executor, promotes Pipeline
4. `task_04_human_gate.md` — full gate with `strict_review`
5. `task_05_aiw_resume.md` — full resume with DAG
6. `task_06_ollama_infrastructure.md` — NEW — health check + circuit breaker + Haiku fallback
