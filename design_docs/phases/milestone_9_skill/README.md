# Milestone 9 — Claude Code Skill Packaging (Optional)

**Status:** 📝 Optional. May be skipped entirely if the MCP server ([M4](../milestone_4_mcp/README.md)) plus `aiw` CLI cover the user-facing UX adequately.
**Grounding:** [architecture.md §4.4](../../architecture.md) · [roadmap.md](../../roadmap.md).

## Goal

Package `ai-workflows` as a Claude Code skill: a thin `.claude/skills/ai-workflows/SKILL.md` that either shells out to `aiw` or calls the MCP server, giving an in-Claude-Code invocation path without coupling the core to Claude Code (which KDR-002 forbids).

## Exit criteria

1. `.claude/skills/ai-workflows/SKILL.md` exists and documents the common `planner` / `slice_refactor` invocations.
2. The skill contains no orchestration logic — every action is a shell-out or an MCP call.
3. Short distribution doc explains how to install the skill and register the MCP server.
4. Manual end-to-end check: invoking the skill from Claude Code runs a workflow via M4's MCP server.

## Non-goals

- Plugin marketplace publishing (out of scope unless the user asks later).
- Skill logic (KDR-002 — Claude Code must remain a consumer, not a substrate).

## Key decisions in effect

| Decision | Reference |
| --- | --- |
| Skills are packaging-only | KDR-002 |
| MCP is the portable surface | KDR-002 |

## Task order

| # | Task | Kind |
| --- | --- | --- |
| 01 | [`.claude/skills/ai-workflows/SKILL.md` + supporting files](task_01_skill_md.md) | doc + test |
| 02 | [Optional plugin manifest (conditional — trigger-gated)](task_02_plugin_manifest.md) | doc + test |
| 03 | [Distribution / install docs](task_03_distribution_docs.md) | doc + test |
| 04 | [Milestone close-out](task_04_milestone_closeout.md) | doc |

Per-task specs drafted 2026-04-21. Milestone remains `📝 Optional` in the roadmap — promotion to active requires a concrete reason (user intent to distribute, a second host onboarding, or the in-repo skill surface being regularly invoked). Task scope stays packaging-only per KDR-002 regardless of when it runs.

## Issues

Land under [issues/](issues/).
