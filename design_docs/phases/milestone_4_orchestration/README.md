# Milestone 4 — Orchestration Components

## Goal

Build the components needed to support multi-step, DAG-driven workflows with human review gates: Planner, Orchestrator, AgentLoop, and HumanGate.

**Exit criteria:** These four components can be composed to recreate Pipeline 2's shape — a Planner produces a DAG, the Orchestrator executes it with parallel branches, and a HumanGate pauses for review between planning and execution.

## Scope

- `Planner` (two-phase: Qwen exploration + Opus planning with tools)
- `Orchestrator` (DAG execution, topological sort, checkpoint/resume, double-failure hard stop)
- `AgentLoop` (multi-turn, termination conditions, weak guarantee documented)
- `HumanGate` (pretty-printed review, timeout, strict_review flag)
- `aiw resume` (full implementation — was a stub in Milestone 1)
- SIGINT cancellation handling

## Key Decisions In Effect

| Decision | Value |
|---|---|
| Planner output | DAG with `depends_on: [task_id]` |
| Plan parse retry | Max 3, then abort |
| Plan max tasks | Configurable, default 50 |
| Two-phase planning | Phase 1: Qwen exploration → `runs/<run_id>/exploration/` docs. Phase 2: Opus with tool access reads docs + targeted lookups |
| Topological sort | `networkx` |
| Concurrency | Per-provider semaphore |
| Double-failure | Hard stop — same policy as Fanout but at Orchestrator level |
| AgentLoop guarantee | Weaker: best-effort determinism. Orchestrator mandates Validator after every AgentLoop step |
| AgentLoop termination | No tool calls + explicit `done` tool + `max_iterations` (default 20) |
| HumanGate render | Raw JSON → log file; pretty-printed plan → terminal |
| HumanGate timeout | 30min default, configurable. Hard stop on expiry → `timed_out` in SQLite |
| strict_review | `strict_review: true` in workflow YAML blocks `--skip-gate` |

## Task Order

1. `task_01_planner.md`
2. `task_02_agent_loop.md` (Planner depends on AgentLoop internally)
3. `task_03_orchestrator.md`
4. `task_04_human_gate.md`
5. `task_05_aiw_resume.md`
