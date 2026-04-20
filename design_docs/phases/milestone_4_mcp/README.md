# Milestone 4 — MCP Server (FastMCP)

**Status:** 📝 Planned. Starts once [M3](../milestone_3_first_workflow/README.md) closes clean.
**Grounding:** [architecture.md §4.4](../../architecture.md) · [roadmap.md](../../roadmap.md).

## Goal

Expose the project as an MCP server built on FastMCP, delivering the portable inside-out surface promised by KDR-002. Five tools — `run_workflow`, `resume_run`, `list_runs`, `get_cost_report`, `cancel_run` — each with schema-first pydantic contracts. stdio transport first; HTTP deferred until a concrete need arises.

## Exit criteria

1. `ai_workflows.mcp` package ships a FastMCP `Server` exposing the five tools from [architecture.md §4.4](../../architecture.md).
2. Every tool input and output is a pydantic model; schemas are auto-derived by FastMCP.
3. A documented `claude mcp add` invocation (or MCP JSON config) registers the server with Claude Code locally and the server answers a `run_workflow` call end-to-end against the M3 `planner`.
4. One smoke test drives the server in-process (no subprocess) through all five tools.
5. Gates green.

## Non-goals

- HTTP transport (stdio only for this milestone).
- Authentication / multi-user concerns.
- Non-Claude-Code hosts validated manually only — not a test gate.

## Key decisions in effect

| Decision | Reference |
| --- | --- |
| MCP as portable surface | KDR-002 |
| FastMCP as implementation | KDR-008 |
| Schema-first pydantic contracts | [architecture.md §7](../../architecture.md) |

## Task order

| # | Task |
| --- | --- |
| 01 | FastMCP server scaffold + pydantic I/O models for every tool |
| 02 | `run_workflow` tool (dispatches to workflow registry, returns run_id) |
| 03 | `resume_run` tool (drives `HumanGate` response to the next checkpoint) |
| 04 | `list_runs` tool + `get_cost_report` tool (read-only — see *Carry-over* below) |
| 05 | `cancel_run` tool (graceful abort via LangGraph cancellation) |
| 06 | stdio transport + `claude mcp add` integration docs |
| 07 | In-process smoke test covering all five tools |
| 08 | Milestone close-out |

Per-task files generated once M3 closes.

## Issues

Land under [issues/](issues/).

## Carry-over from prior milestones

- [ ] **M3 T06 reframe — `get_cost_report` MCP tool re-spec (LOW, owner: M4 T04).**
  The original M4 spec inherited a by-tier / by-model / by-provider breakdown shape for `get_cost_report`. M3 T06 reframe (2026-04-20) dropped the matching `aiw cost-report` CLI because (i) M1 T05 removed per-call `TokenUsage` rows from Storage, (ii) `TokenUsage` has no `provider` field, and (iii) under the current subscription-billing provider set (Claude Max / Gemini free tier / Ollama) the breakdown drives zero decisions.
  **What to implement at M4 T04:** ship `get_cost_report(run_id) → CostReport` as a total-only scalar (reading `runs.total_cost_usd`) **or** fold the signal into `list_runs` and drop the standalone tool. Do **not** re-introduce the by-X breakdowns unless one of the three triggers in [nice_to_have.md §9](../../nice_to_have.md) fires first.
  Source: [architecture.md §4.4](../../architecture.md) note line · [task_06_cli_list_cost.md](../milestone_3_first_workflow/task_06_cli_list_cost.md) reframe section · [milestone_3_first_workflow/issues/task_06_issue.md](../milestone_3_first_workflow/issues/task_06_issue.md).
