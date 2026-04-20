# Task 08 — Milestone Close-out

**Status:** 📝 Planned.

## What to Build

Close M3. Confirm every exit criterion from the [milestone README](README.md). Update [CHANGELOG.md](../../../CHANGELOG.md) and mark M3 complete in [roadmap.md](../../roadmap.md). No code change beyond docs.

Mirrors the shape of M2 [Task 09](../milestone_2_graph/task_09_milestone_closeout.md) so reviewers get identical close-out muscle memory.

## Deliverables

### [README.md](README.md)

Change the **Status** line from `📝 Planned` to `✅ Complete (<YYYY-MM-DD>)`.

Append an **Outcome** section summarising:

- Workflow registry ([task 01](task_01_workflow_registry.md)) + planner schemas ([task 02](task_02_planner_schemas.md)).
- `planner` `StateGraph` shipped ([task 03](task_03_planner_graph.md)) — explorer + validator + planner + validator + gate + artifact.
- CLI commands revived ([tasks 04](task_04_cli_run.md)–[06](task_06_cli_list_cost.md)): `aiw run`, `aiw resume`, `aiw list-runs`. (`aiw cost-report` was dropped at T06 reframe on 2026-04-20 and deferred to [nice_to_have.md §9](../../nice_to_have.md) — see the T06 spec's "Design drift and reframe" section.)
- End-to-end smoke test gated by `AIW_E2E=1` ([task 07](task_07_e2e_smoke.md)).
- Green-gate snapshot: `uv run pytest` (unit), `AIW_E2E=1 uv run pytest -m e2e` (one-off), `uv run lint-imports`, `uv run ruff check` all passing.

### [roadmap.md](../../roadmap.md)

Change M3 row `Status` from `planned` to `✅ complete (<YYYY-MM-DD>)`.

### `CHANGELOG.md`

Promote accumulated `[Unreleased]` entries from M3 tasks into a dated section `## [M3 First Workflow — planner] - <YYYY-MM-DD>`. Keep the top-of-file `[Unreleased]` section intact (it will still hold the Architecture pivot entry carried since M1). Add a T08 close-out entry at the top of the new dated section — mirror the M1 Task 13 / M2 Task 09 `### Changed — M3 Task 08: Milestone Close-out` header shape.

## Acceptance Criteria

- [ ] Every exit criterion in the milestone [README](README.md) has a concrete verification (paths / test names / issue-file links).
- [ ] `uv run pytest && uv run lint-imports && uv run ruff check` green on a fresh clone.
- [ ] `AIW_E2E=1 uv run pytest -m e2e` green once (record in the close-out CHANGELOG entry).
- [ ] README and roadmap reflect ✅ status.
- [ ] CHANGELOG has a dated entry summarising M3; `[Unreleased]` remains at the top of the file holding only the Architecture pivot entry.

## Dependencies

- [Task 01](task_01_workflow_registry.md) through [Task 07](task_07_e2e_smoke.md).
- [Task 07a](task_07a_planner_structured_output.md) — **hard prerequisite**. T07's live e2e run on 2026-04-20 surfaced a requirement gap in T03's `tiered_node` wiring (no `output_schema=` forwarded, so Gemini returns free-form text and the validator's strict JSON parse is probabilistic against live output). T07a closes the gap. M3 cannot close green until T07a lands and a live `green-once` is recorded in the T08 CHANGELOG entry per AC-3. See [issues/task_08_issue.md](issues/task_08_issue.md) M3-T08-ISS-02.
