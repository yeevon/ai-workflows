# Task 13 — Milestone Close-out

**Status:** 📝 Planned.

## What to Build

Close M1. Confirm every exit criterion from the [milestone README](README.md) is met, update [CHANGELOG.md](../../../CHANGELOG.md), and mark the milestone complete in [roadmap.md](../../roadmap.md). No code change in this task beyond docs and a commit.

## Deliverables

### [README.md](README.md)

Change the **Status** line from `🚧 Active` to `✅ Complete (<YYYY-MM-DD>)`.

Append an **Outcome** section summarising:

- Dependencies swapped (links to [task 02](task_02_dependency_swap.md)).
- Packages deleted (links to [task 03](task_03_remove_llm_substrate.md), [task 04](task_04_remove_tool_registry.md)).
- Primitives retuned (links to [tasks 05](task_05_trim_storage.md)–[09](task_09_logger_sanity.md)).
- `workflow_hash` decision reference to the ADR (from [task 10](task_10_workflow_hash_decision.md)).
- CLI stubbed (link to [task 11](task_11_cli_stub_down.md)).
- Import-linter contract in place (link to [task 12](task_12_import_linter_rewrite.md)).
- Green-gate snapshot: `uv run pytest`, `uv run lint-imports`, `uv run ruff check` all passing as of close-out.

### [roadmap.md](../../roadmap.md)

Change M1 row `Status` from `🚧 active` to `✅ complete (<YYYY-MM-DD>)`.

### `CHANGELOG.md`

Promote the accumulated `[Unreleased]` entries from the M1 tasks into a new dated section. Keep the pivot-decision entry already under `[Unreleased]` if it has not yet been released.

## Acceptance Criteria

- [ ] Every exit criterion in the milestone [README](README.md) has a concrete verification (command run + green result).
- [ ] `uv run pytest && uv run lint-imports && uv run ruff check` all green on a fresh clone after `uv sync`.
- [ ] `grep -r "pydantic_ai" ai_workflows/ tests/` returns zero matches.
- [ ] `grep -r "ai_workflows.components" . --include="*.py" --include="*.toml"` returns zero matches.
- [ ] `CHANGELOG.md` has a dated entry summarising M1.
- [ ] README and roadmap reflect ✅ status.

## Dependencies

- All of [task 01](task_01_reconciliation_audit.md) through [task 12](task_12_import_linter_rewrite.md).
