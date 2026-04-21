# Task 09 — Milestone Close-out

**Status:** 📝 Planned.

## What to Build

Close M6. Confirm every exit criterion from the [milestone README](README.md). Update [CHANGELOG.md](../../../CHANGELOG.md) and flip M6 complete in [roadmap.md](../../roadmap.md). No code change beyond docs.

Mirrors [M5 Task 07](../milestone_5_multitier_planner/task_07_milestone_closeout.md) so reviewers get identical close-out muscle memory.

## Deliverables

### [README.md](README.md)

- Flip **Status** from `📝 Planned` to `✅ Complete (<YYYY-MM-DD>)`.
- Append an **Outcome** section summarising:
  - Slice-discovery phase ([task 01](task_01_slice_discovery.md)) — planner composed as sub-graph; `slice_list` normalized from `PlannerPlan.steps`.
  - Parallel slice-worker pattern ([task 02](task_02_parallel_slice_worker.md)) — LangGraph `Send` fan-out + `operator.add` reducer; `durability="sync"` compile; in-flight `cancel_run` wiring (M4-T05 carry-over landed).
  - Per-slice validator wiring ([task 03](task_03_per_slice_validator.md)) — KDR-004 honoured across fan-out; per-slice semantic retry isolated from siblings.
  - Aggregator ([task 04](task_04_aggregator.md)) — partial-failure capture in `SliceAggregate`.
  - Strict-review gate ([task 05](task_05_strict_review_gate.md)) — first `strict_review=True` use; no-timeout semantics verified.
  - Apply node ([task 06](task_06_apply_node.md)) — artefacts persisted to `Storage`; reject path writes nothing.
  - Concurrency semaphore + double-failure hard-stop ([task 07](task_07_concurrency_hard_stop.md)) — architecture §8.6 + §8.2 contracts proven under fan-out for the first time.
  - End-to-end smoke ([task 08](task_08_e2e_smoke.md)) — hermetic always-run; `AIW_E2E=1` real-provider run recorded.
  - Manual verification: `aiw-mcp` → fresh Claude Code session → `run_workflow(workflow_id="slice_refactor", …)` — two-gate flow captured.
  - Green-gate snapshot: `uv run pytest`, `uv run lint-imports`, `uv run ruff check`.
- Flip the **Carry-over from prior milestones** section: mark the M4-T05 `cancel_run` item as `✅ RESOLVED (landed in task 02)` with a link back to the T02 deliverables.

### [roadmap.md](../../roadmap.md)

Flip M6 row `Status` from `planned` to `✅ complete (<YYYY-MM-DD>)`.

### [CHANGELOG.md](../../../CHANGELOG.md)

Promote accumulated `[Unreleased]` entries from M6 tasks into a dated section `## [M6 Slice Refactor] - <YYYY-MM-DD>`. Keep the top-of-file `[Unreleased]` section intact. Add a T09 close-out entry at the top of the new dated section — mirror M5 T07's shape. Record the live `AIW_E2E=1 uv run pytest tests/e2e/test_slice_refactor_smoke.py` run (commit sha + observed `runs.total_cost_usd` range + the goal string used + approved slice count) and the manual `aiw-mcp` two-gate round-trip in this entry.

### Root [README.md](../../../README.md)

Update the status table (M6 → ✅ Complete), the narrative paragraph (append an M6 summary), the "What runs today" section (`slice_refactor` workflow + strict-review gate + in-flight `cancel_run` all documented), and the "Next" pointer (→ M7 eval harness). Follow the M5 close-out pattern exactly.

## Acceptance Criteria

- [ ] Every exit criterion in the milestone [README](README.md) has a concrete verification (paths / test names / issue-file links).
- [ ] `uv run pytest && uv run lint-imports && uv run ruff check` green on a fresh clone.
- [ ] `AIW_E2E=1 uv run pytest tests/e2e/test_slice_refactor_smoke.py` recorded in the close-out CHANGELOG entry.
- [ ] Manual `aiw-mcp` two-gate round-trip recorded in the close-out CHANGELOG entry (command + observed payload).
- [ ] README (milestone) and roadmap reflect ✅ status.
- [ ] M4-T05 carry-over item in the milestone README flipped to `✅ RESOLVED (landed in task 02)`.
- [ ] CHANGELOG has a dated `## [M6 Slice Refactor] - <YYYY-MM-DD>` section; `[Unreleased]` preserved at the top.
- [ ] Root README updated: status table, post-M6 narrative, What-runs-today, Next → M7.

## Dependencies

- [Task 01](task_01_slice_discovery.md) through [Task 08](task_08_e2e_smoke.md).
