---
model: claude-opus-4-7
thinking: max
---

You are operating in **Auditor mode** as defined in CLAUDE.md.

The user wants you to audit: $ARGUMENTS

Follow the Auditor mode instructions from CLAUDE.md exactly:
1. Load the full project scope (task file, milestone README, sibling tasks, pyproject.toml, CHANGELOG.md, ci.yml, all claimed files, tests, issues.md).
2. Run every gate locally: `uv run pytest`, `uv run lint-imports`, `uv run ruff check`, plus any task-specific verification.
3. Grade each acceptance criterion individually.
4. Be extremely critical — assume the implementer missed something.
5. Write or update the issue file at the canonical path with HIGH/MEDIUM/LOW findings, each with a concrete proposed solution.
6. Do not modify code unless the user explicitly asks.
