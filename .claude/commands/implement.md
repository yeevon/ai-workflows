---
model: claude-sonnet-4-6
thinking: high
---

You are operating in **Builder mode** as defined in CLAUDE.md.

The user wants you to implement: $ARGUMENTS

Follow the Builder mode instructions from CLAUDE.md exactly:
1. Read the task file in full.
2. Read the matching issue file if it exists — treat it as authoritative amendments.
3. Read the milestone README for scope context.
4. Implement strictly against the task file + issue file. Do not invent scope.
5. Write tests for every acceptance criterion under `tests/`.
6. Run the full gate: `uv run pytest`, `uv run lint-imports`, `uv run ruff check`.
7. Update CHANGELOG.md under `## [Unreleased]`.
8. Every new module gets a docstring; every public class and function gets a docstring.
9. Stop and ask if the spec is ambiguous, a criterion is unsatisfiable, or implementing would break prior task behaviour.
