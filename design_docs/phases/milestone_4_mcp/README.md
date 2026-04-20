# Milestone 4 — MCP Server (FastMCP)

**Status:** ✅ Complete (2026-04-20).
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

## Outcome (2026-04-20)

**Shipped:**

- **FastMCP scaffold + pydantic I/O models** ([task 01](task_01_mcp_scaffold.md), [issues](issues/task_01_issue.md)). Four tools registered (`run_workflow`, `resume_run`, `list_runs`, `cancel_run`), schemas auto-derived from [`ai_workflows/mcp/schemas.py`](../../../ai_workflows/mcp/schemas.py) annotations.
- **`run_workflow` + `resume_run`** ([task 02](task_02_run_workflow.md), [task 03](task_03_resume_run.md), [issues 02](issues/task_02_issue.md) / [03](issues/task_03_issue.md)). Shared dispatch helper [`ai_workflows/workflows/_dispatch.py`](../../../ai_workflows/workflows/_dispatch.py) routes both CLI (`aiw run` / `aiw resume`) and MCP through one path — KDR-002 portable surface promise made concrete. `ResumePreconditionError` + `UnknownWorkflowError` surface-agnostic errors let each surface translate to its native error channel (CLI → `typer.Exit(2)`, MCP → `ToolError`).
- **`list_runs`** ([task 04](task_04_list_runs.md), [issue](issues/task_04_issue.md)). Pure read over `SQLiteStorage.list_runs`; `RunSummary.total_cost_usd` is the sole cost surface the server exposes (the originally-planned `get_cost_report` was dropped at M4 kickoff — see [nice_to_have.md §9](../../nice_to_have.md)).
- **`cancel_run`** ([task 05](task_05_cancel_run.md), [issue](issues/task_05_issue.md)) — storage-level flip only per [architecture.md §8.7](../../architecture.md). In-flight task abort (`durability="sync"`, subgraph / ToolNode guards) explicitly deferred to [M6 T02](../milestone_6_slice_refactor/README.md).
- **stdio transport + setup docs** ([task 06](task_06_stdio_transport.md), [issue](issues/task_06_issue.md)). [`ai_workflows/mcp/__main__.py`](../../../ai_workflows/mcp/__main__.py) + `aiw-mcp` console script + [mcp_setup.md](mcp_setup.md) walking through `claude mcp add` + `.mcp.json` + smoke check + troubleshooting.
- **Hermetic in-process smoke test** ([task 07](task_07_mcp_smoke.md), [issue](issues/task_07_issue.md)). Single pytest case drives all four tools end-to-end against stubbed LiteLLM adapters — no live API — so every commit validates the full MCP surface. Complements [M3's `AIW_E2E=1` smoke](../milestone_3_first_workflow/task_07_e2e_smoke.md) which covers the live-provider path.

**Manual verification** ([M4-T06-ISS-01](issues/task_06_issue.md)): the `claude mcp add` registration + live `run_workflow` round-trip against a fresh Claude Code session is recorded in the T08 close-out CHANGELOG entry.

**Exit criteria verification:**

| # | Criterion | Verification |
| --- | --- | --- |
| 1 | Four-tool FastMCP server | [task_01_issue.md](issues/task_01_issue.md) + individual tool-task issues. `tests/mcp/test_scaffold.py::test_all_four_tools_registered` pins. |
| 2 | Schema-first pydantic contracts | [ai_workflows/mcp/schemas.py](../../../ai_workflows/mcp/schemas.py); `tests/mcp/test_scaffold.py::test_schema_roundtrip` pins round-trip for all 8 I/O models. |
| 3 | `claude mcp add` round-trip | [mcp_setup.md §2 / §4](mcp_setup.md); manual verification recorded in T08 CHANGELOG entry. |
| 4 | In-process smoke covering all four tools | [tests/mcp/test_server_smoke.py::test_mcp_server_all_four_tools_end_to_end](../../../tests/mcp/test_server_smoke.py). |
| 5 | Gates green | T08 close-out CHANGELOG entry records the final gate snapshot. |

## Issues

Land under [issues/](issues/). All eight task issues (01–08) closed clean by 2026-04-20.

## Carry-over from prior milestones

- [x] **M3 T06 reframe — `get_cost_report` MCP tool re-spec — RESOLVED at M4 kickoff (2026-04-20).**
  The M3 T06 reframe gave M4 two options: (a) ship `get_cost_report(run_id)` as a total-only scalar, or (b) fold the signal into `list_runs` and drop the standalone tool. Option (b) chosen: `list_runs` already returns `total_cost_usd` per `RunSummary`, making a dedicated cost tool pure redundancy under the current subscription-billing provider set (Claude Max / Gemini free tier / Ollama). M4 ships four tools (not five); [architecture.md §4.4](../../architecture.md) updated in the same pass.
  Re-introducing a dedicated cost-report tool is gated on the three triggers in [nice_to_have.md §9](../../nice_to_have.md) — no work to plan here until one fires.
  Source: [task_06_cli_list_cost.md](../milestone_3_first_workflow/task_06_cli_list_cost.md) reframe section · [milestone_3_first_workflow/issues/task_06_issue.md](../milestone_3_first_workflow/issues/task_06_issue.md).
