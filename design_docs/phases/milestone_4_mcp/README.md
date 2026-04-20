# Milestone 4 — MCP Server (FastMCP)

**Status:** 📝 Planned. Starts once [M3](../milestone_3_first_workflow/README.md) closes clean.
**Grounding:** [architecture.md §4.4](../../architecture.md) · [roadmap.md](../../roadmap.md).

## Goal

Expose the project as an MCP server built on FastMCP, delivering the portable inside-out surface promised by KDR-002. Four tools — `run_workflow`, `resume_run`, `list_runs`, `cancel_run` — each with schema-first pydantic contracts. stdio transport first; HTTP deferred until a concrete need arises.

The originally-planned fifth tool, `get_cost_report`, was dropped at M4 kickoff (2026-04-20) — `list_runs` already surfaces `total_cost_usd` per `RunSummary`, making a dedicated cost tool pure redundancy under the current subscription-billing provider set. Adoption triggers for re-introducing a dedicated cost-report tool are listed in [nice_to_have.md §9](../../nice_to_have.md).

## Exit criteria

1. `ai_workflows.mcp` package ships a FastMCP `Server` exposing the four tools from [architecture.md §4.4](../../architecture.md).
2. Every tool input and output is a pydantic model; schemas are auto-derived by FastMCP.
3. A documented `claude mcp add` invocation (or MCP JSON config) registers the server with Claude Code locally and the server answers a `run_workflow` call end-to-end against the M3 `planner`.
4. One smoke test drives the server in-process (no subprocess) through all four tools.
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
| 01 | [FastMCP server scaffold + pydantic I/O models](task_01_mcp_scaffold.md) |
| 02 | [`run_workflow` tool (dispatches to workflow registry)](task_02_run_workflow.md) |
| 03 | [`resume_run` tool (drives `HumanGate` response)](task_03_resume_run.md) |
| 04 | [`list_runs` tool (read-only; `RunSummary` carries `total_cost_usd`)](task_04_list_runs.md) |
| 05 | [`cancel_run` tool (storage-level flip; in-flight deferred to M6 per §8.7)](task_05_cancel_run.md) |
| 06 | [stdio transport + `claude mcp add` setup docs](task_06_stdio_transport.md) |
| 07 | [In-process smoke test covering all four tools](task_07_mcp_smoke.md) |
| 08 | [Milestone close-out](task_08_milestone_closeout.md) |

## Issues

Land under [issues/](issues/).

## Carry-over from prior milestones

- [x] **M3 T06 reframe — `get_cost_report` MCP tool re-spec — RESOLVED at M4 kickoff (2026-04-20).**
  The M3 T06 reframe gave M4 two options: (a) ship `get_cost_report(run_id)` as a total-only scalar, or (b) fold the signal into `list_runs` and drop the standalone tool. Option (b) chosen: `list_runs` already returns `total_cost_usd` per `RunSummary`, making a dedicated cost tool pure redundancy under the current subscription-billing provider set (Claude Max / Gemini free tier / Ollama). M4 ships four tools (not five); [architecture.md §4.4](../../architecture.md) updated in the same pass.
  Re-introducing a dedicated cost-report tool is gated on the three triggers in [nice_to_have.md §9](../../nice_to_have.md) — no work to plan here until one fires.
  Source: [task_06_cli_list_cost.md](../milestone_3_first_workflow/task_06_cli_list_cost.md) reframe section · [milestone_3_first_workflow/issues/task_06_issue.md](../milestone_3_first_workflow/issues/task_06_issue.md).
