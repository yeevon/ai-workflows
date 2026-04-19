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
| 04 | `list_runs` tool + `get_cost_report` tool (read-only) |
| 05 | `cancel_run` tool (graceful abort via LangGraph cancellation) |
| 06 | stdio transport + `claude mcp add` integration docs |
| 07 | In-process smoke test covering all five tools |
| 08 | Milestone close-out |

Per-task files generated once M3 closes.

## Issues

Land under [issues/](issues/).
