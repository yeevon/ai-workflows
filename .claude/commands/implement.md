---
model: claude-opus-4-7
thinking: high
---

# /implement

The user wants the **builder** subagent to implement: $ARGUMENTS

Spawn the `builder` agent via `Task` with:

- **Task identifier** from `$ARGUMENTS`. Resolve shorthand by glob: "m16 t1" → `design_docs/phases/milestone_16_*/task_01_*.md`. If multiple matches, ask the user.
- **Spec path** (`design_docs/phases/milestone_<M>_<name>/task_<NN>_<slug>.md`).
- **Issue file path** (`design_docs/phases/milestone_<M>_<name>/issues/task_<NN>_issue.md`) — may not exist yet on the first pass.
- **Parent milestone README path**.
- **Project context brief** naming gate commands (`uv run pytest`, `uv run lint-imports`, `uv run ruff check`), the four-layer rule, the seven load-bearing KDRs (002/003/004/006/008/009/013), the `nice_to_have.md` boundary, the changelog convention (`## [Unreleased]` → `### Added — M<N> Task <NN>: <Title> (YYYY-MM-DD)`), and the four status surfaces.

When the builder returns, surface its report and stop. **Do not run the auditor** — that's `/clean-implement`'s job. If the user wants the full loop, they invoke `/clean-implement`.
