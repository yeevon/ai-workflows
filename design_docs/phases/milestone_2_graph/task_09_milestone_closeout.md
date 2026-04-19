# Task 09 — Milestone Close-out

**Status:** 📝 Planned.

## What to Build

Close M2. Confirm every exit criterion from the [milestone README](README.md). Update [CHANGELOG.md](../../../CHANGELOG.md) and mark M2 complete in [roadmap.md](../../roadmap.md). No code change beyond docs.

## Deliverables

### [README.md](README.md)

Change the **Status** line from `📝 Planned` to `✅ Complete (<YYYY-MM-DD>)`.

Append an **Outcome** section summarising:

- Adapters shipped ([tasks 03](task_03_tiered_node.md)–[07](task_07_retrying_edge.md)).
- Providers shipped ([task 01](task_01_litellm_adapter.md), [task 02](task_02_claude_code_driver.md)).
- Checkpointer bound and smoke-graph exercised ([task 08](task_08_checkpointer.md)).
- Green-gate snapshot: `uv run pytest`, `uv run lint-imports`, `uv run ruff check` all passing.

### [roadmap.md](../../roadmap.md)

Change M2 row `Status` from `planned` to `✅ complete (<YYYY-MM-DD>)`.

### `CHANGELOG.md`

Promote accumulated `[Unreleased]` entries from M2 tasks into a dated section.

## Acceptance Criteria

- [ ] Every exit criterion in the milestone [README](README.md) has a concrete verification.
- [ ] `uv run pytest && uv run lint-imports && uv run ruff check` green on a fresh clone.
- [ ] README and roadmap reflect ✅ status.
- [ ] CHANGELOG has a dated entry summarising M2.

## Dependencies

- [Task 01](task_01_litellm_adapter.md) through [Task 08](task_08_checkpointer.md).
