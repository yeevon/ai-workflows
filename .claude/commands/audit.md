---
model: claude-opus-4-7
thinking: max
---

# /audit

The user wants the **auditor** subagent to audit: $ARGUMENTS

Spawn the `auditor` agent via `Task` with:

- **Task identifier** from `$ARGUMENTS`. Resolve shorthand by glob: "m16 t1" → `design_docs/phases/milestone_16_*/task_01_*.md`. If multiple matches, ask the user.
- **Spec path** + **issue file path** (`design_docs/phases/milestone_<M>_<name>/{task_<NN>_<slug>.md, issues/task_<NN>_issue.md}`).
- **Architecture docs:** `design_docs/architecture.md` (especially §3 four-layer rule + §6 dep table + §9 KDRs) and any ADR the task cites.
- **Gate commands:** `uv run pytest`, `uv run lint-imports`, `uv run ruff check`.
- **Project context brief** with the seven load-bearing KDRs (002/003/004/006/008/009/013), the layer rule, the `nice_to_have.md` boundary, and the four status surfaces.
- **Builder report context:** if `/audit` was invoked standalone (no prior Builder spawn this session), pass `"No prior Builder report — audit from current state"` so the agent knows to verify against the working tree directly.

When the auditor returns, surface the issue file path + status line and stop. **Do not invoke the Builder** — that's `/clean-implement`'s job.
