# Milestone 5 — Multi-Tier `planner`

**Status:** 📝 Planned. Starts once [M4](../milestone_4_mcp/README.md) closes clean.
**Grounding:** [architecture.md §4.3](../../architecture.md) · [roadmap.md](../../roadmap.md).

## Goal

Upgrade the `planner` workflow from single-tier to a two-phase sub-graph: **Qwen (local_coder) explore → Claude Code (opus) plan**. This is the first real exercise of both provider drivers inside one workflow and proves the tier-override surface works across CLI and MCP.

## Exit criteria

1. `planner` executes the two-phase sub-graph end-to-end: Qwen explorer produces a findings blob, Claude Code planner consumes it and emits the plan artifact.
2. Tier override (`aiw run planner --tier-override explorer=gemini_flash`) reroutes the explorer node without code change.
3. MCP `run_workflow` accepts a `tier_overrides` argument and produces identical behaviour.
4. `modelUsage` cost ledger records both the Qwen call (cost 0, local) and the Claude Code call (with haiku sub-calls rolled up).
5. Gates green.

## Non-goals

- `slice_refactor` — M6.
- Ollama fallback / circuit breaker — M8.
- Automated prompt evals — M7.

## Key decisions in effect

| Decision | Reference |
| --- | --- |
| Two-phase planner as sub-graph | [architecture.md §4.3](../../architecture.md) |
| Tier override is a surface contract | [architecture.md §4.4](../../architecture.md) |
| No Anthropic API | KDR-003 |

## Task order

| # | Task |
| --- | --- |
| 01 | [Qwen explorer tier refit](task_01_qwen_explorer.md) |
| 02 | [Claude Code planner tier refit](task_02_claude_code_planner.md) |
| 03 | [Sub-graph composition validation (integration)](task_03_subgraph_composition.md) |
| 04 | [Tier-override CLI plumbing (`--tier-override logical=replacement`)](task_04_tier_override_cli.md) |
| 05 | [Tier-override MCP plumbing (`RunWorkflowInput.tier_overrides`)](task_05_tier_override_mcp.md) |
| 06 | [End-to-end smoke (hermetic + `AIW_E2E=1` live)](task_06_e2e_smoke.md) |
| 07 | [Milestone close-out](task_07_milestone_closeout.md) |

## Issues

Land under [issues/](issues/).
