---
model: claude-opus-4-7
thinking: max
---

# /audit

You are operating in **Auditor mode** as defined in CLAUDE.md.

The user wants you to audit: $ARGUMENTS

Follow the Auditor mode instructions from CLAUDE.md exactly:

1. Load the full project scope (task file, milestone README, sibling task files and their issue files if present, pyproject.toml, CHANGELOG.md, ci.yml, all claimed files, tests, plus `design_docs/architecture.md` and any KDR(s) the task cites). **Opening `architecture.md` is mandatory — skipping it is an incomplete audit.**
2. **Design-drift check (before grading ACs):** cross-reference every change against `design_docs/architecture.md` per the Auditor-conventions `Design-drift check` bullet in CLAUDE.md. Flag any new dependency, module, layer, LLM-call pattern, checkpoint logic, retry logic, or observability path that contradicts the architecture or a KDR. Drift is logged as HIGH and blocks audit pass. Items that map to `design_docs/nice_to_have.md` are never silently adopted — they are HIGH with a pointer to the deferred entry.
3. Run every gate locally: `uv run pytest`, `uv run lint-imports`, `uv run ruff check`, plus any task-specific verification.
4. Grade each acceptance criterion individually.
5. Be extremely critical — assume the implementer missed something.
6. Write or update the issue file at the canonical path with HIGH/MEDIUM/LOW findings, each with a concrete proposed solution. Every drift finding cites the violated KDR or architecture section.
7. Do not modify code unless the user explicitly asks.
