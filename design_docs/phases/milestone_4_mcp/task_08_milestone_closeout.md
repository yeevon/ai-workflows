# Task 08 — Milestone Close-out

**Status:** 📝 Planned.

## What to Build

Close M4. Confirm every exit criterion from the [milestone README](README.md). Update [CHANGELOG.md](../../../CHANGELOG.md) and flip M4 complete in [roadmap.md](../../roadmap.md). No code change beyond docs.

Mirrors [M3 Task 08](../milestone_3_first_workflow/task_08_milestone_closeout.md) so reviewers get identical close-out muscle memory.

## Deliverables

### [README.md](README.md)

- Flip **Status** from `📝 Planned` to `✅ Complete (<YYYY-MM-DD>)`.
- Append an **Outcome** section summarising:
  - FastMCP scaffold + pydantic I/O models ([task 01](task_01_mcp_scaffold.md)).
  - Four tools shipped ([tasks 02–05](README.md)): `run_workflow`, `resume_run`, `list_runs`, `cancel_run`. (`get_cost_report` deferred — see the carry-over section; M4 ships four tools, not five.)
  - Shared dispatch helper (`ai_workflows/mcp/dispatch.py` or equivalent) means CLI + MCP go through one path — refactor completed in tasks 02 + 03.
  - stdio transport + `claude mcp add` setup documented ([task 06](task_06_stdio_transport.md)).
  - In-process smoke test covering all four tools, hermetic ([task 07](task_07_mcp_smoke.md)).
  - Manual verification: `claude mcp add` → live `run_workflow` against planner → paste the actual run_id + gate output.
  - Green-gate snapshot: `uv run pytest`, `uv run lint-imports`, `uv run ruff check`.

### [roadmap.md](../../roadmap.md)

Flip M4 row `Status` from `planned` to `✅ complete (<YYYY-MM-DD>)`.

### [CHANGELOG.md](../../../CHANGELOG.md)

Promote accumulated `[Unreleased]` entries from M4 tasks into a dated section `## [M4 MCP Server] - <YYYY-MM-DD>`. Keep the top-of-file `[Unreleased]` section intact. Add a T08 close-out entry at the top of the new dated section — mirror M3 Task 08's shape. Record the manual `claude mcp add` verification explicitly (command + observed output) in this entry.

### Root [README.md](../../../README.md)

Update the status table (M4 → ✅ Complete), the narrative paragraph (append an M4 summary), the "What runs today" section (surface the four MCP tools + the `aiw-mcp` console script), and the "Next" pointer (→ M5 multi-tier planner). Follow the M3 close-out pattern exactly.

## Acceptance Criteria

- [ ] Every exit criterion in the milestone [README](README.md) has a concrete verification (paths / test names / issue-file links).
- [ ] `uv run pytest && uv run lint-imports && uv run ruff check` green on a fresh clone.
- [ ] Manual `claude mcp add` verification recorded in the close-out CHANGELOG entry (command + output).
- [ ] README (milestone) and roadmap reflect ✅ status.
- [ ] CHANGELOG has a dated `## [M4 MCP Server] - <YYYY-MM-DD>` section; `[Unreleased]` preserved at the top.
- [ ] Root README updated: status table, post-M4 narrative, What-runs-today, Next → M5.

## Dependencies

- [Task 01](task_01_mcp_scaffold.md) through [Task 07](task_07_mcp_smoke.md).

## Carry-over from prior audits

- [ ] **M4-T06-ISS-01** (DEFERRED) — Manual verification: from a fresh Claude Code session registered against `aiw-mcp` via `claude mcp add ai-workflows --scope user -- uv run aiw-mcp`, invoke `run_workflow` with `workflow_id="planner"`, a short `goal`, and a fresh `run_id`; capture the returned `{run_id, status: "pending", awaiting: "gate", …}` payload. Then invoke `resume_run` with `gate_response="approved"` and capture the `{status: "completed", plan: {…}}` payload. Paste both commands + both responses into the close-out CHANGELOG entry verbatim. Source: [issues/task_06_issue.md](issues/task_06_issue.md).
