# Task 07 — Milestone Close-out

**Status:** 📝 Planned.

## What to Build

Close M5. Confirm every exit criterion from the [milestone README](README.md). Update [CHANGELOG.md](../../../CHANGELOG.md) and flip M5 complete in [roadmap.md](../../roadmap.md). No code change beyond docs.

Mirrors [M4 Task 08](../milestone_4_mcp/task_08_milestone_closeout.md) so reviewers get identical close-out muscle memory.

## Deliverables

### [README.md](README.md)

- Flip **Status** from `📝 Planned` to `✅ Complete (<YYYY-MM-DD>)`.
- Append an **Outcome** section summarising:
  - Qwen explorer tier refit ([task 01](task_01_qwen_explorer.md)) — Ollama-backed local_coder path live.
  - Claude Code planner tier refit ([task 02](task_02_claude_code_planner.md)) — `ClaudeCodeRoute` + subprocess driver dispatched under a real workflow for the first time.
  - Sub-graph integration validation ([task 03](task_03_subgraph_composition.md)) — topology unchanged; mixed-provider retry + cost-rollup paths proven.
  - Tier-override surface ([tasks 04](task_04_tier_override_cli.md) + [05](task_05_tier_override_mcp.md)) — one dispatch-level implementation, both surfaces.
  - End-to-end smoke ([task 06](task_06_e2e_smoke.md)) — hermetic always-run; `AIW_E2E=1` real-provider run recorded.
  - Manual verification: `aiw-mcp` → fresh Claude Code session → `run_workflow(workflow_id="planner", …)` with the multi-tier registry.
  - Green-gate snapshot: `uv run pytest`, `uv run lint-imports`, `uv run ruff check`.

### [roadmap.md](../../roadmap.md)

Flip M5 row `Status` from `planned` to `✅ complete (<YYYY-MM-DD>)`.

### [CHANGELOG.md](../../../CHANGELOG.md)

Promote accumulated `[Unreleased]` entries from M5 tasks into a dated section `## [M5 Multi-Tier Planner] - <YYYY-MM-DD>`. Keep the top-of-file `[Unreleased]` section intact. Add a T07 close-out entry at the top of the new dated section — mirror M4 Task 08's shape. Record the live `AIW_E2E=1 uv run pytest tests/e2e/` run (commit sha + observed `runs.total_cost_usd` range + the goal string used) and the manual `aiw-mcp` multi-tier round-trip in this entry.

### Root [README.md](../../../README.md)

Update the status table (M5 → ✅ Complete), the narrative paragraph (append an M5 summary), the "What runs today" section (multi-tier planner + tier-override flag documented), and the "Next" pointer (→ M6 `slice_refactor`). Follow the M4 close-out pattern exactly.

## Acceptance Criteria

- [ ] Every exit criterion in the milestone [README](README.md) has a concrete verification (paths / test names / issue-file links).
- [ ] `uv run pytest && uv run lint-imports && uv run ruff check` green on a fresh clone.
- [ ] `AIW_E2E=1 uv run pytest tests/e2e/` recorded in the close-out CHANGELOG entry (both the multi-tier smoke and the tier-override smoke).
- [ ] Manual `aiw-mcp` multi-tier round-trip recorded in the close-out CHANGELOG entry (command + observed payload).
- [ ] README (milestone) and roadmap reflect ✅ status.
- [ ] CHANGELOG has a dated `## [M5 Multi-Tier Planner] - <YYYY-MM-DD>` section; `[Unreleased]` preserved at the top.
- [ ] Root README updated: status table, post-M5 narrative, What-runs-today, Next → M6.

## Dependencies

- [Task 01](task_01_qwen_explorer.md) through [Task 06](task_06_e2e_smoke.md).
