# Effort Table — Per-role adaptive thinking + effort assignments

**Task:** M20 Task 21 — Adaptive-thinking migration
**Canonical reference for:** all 9 agent frontmatters and all 7 slash-command frontmatters.

Every agent and slash command declares `thinking: { type: adaptive }` and `effort:` in its
frontmatter. The table below is the single authoritative source for those assignments.
Per-file frontmatter must match this table exactly; the
`tests/orchestrator/test_effort_table_consistency.py` test enforces it.

**Research basis:** research brief §Lens 3.3 (adaptive thinking is the new dial) · Anthropic API
docs `whats-new-claude-4-7`.

**Critical rule (research brief §Lens 2.2):** never switch model mid-context. Effort is set
per-spawn at agent invocation. Effort change requires a fresh sub-agent spawn, never re-using
a context across model boundaries.

---

## Slash commands

| Command file | Model | `effort` | Rationale |
|---|---|---|---|
| `auto-implement.md` | `claude-opus-4-7` | `high` | Orchestrator running multi-cycle Builder→Auditor loops. |
| `audit.md` | `claude-opus-4-7` | `high` | Single audit pass; same rationale as Auditor agent. |
| `clean-tasks.md` | `claude-opus-4-7` | `high` | Loop + spec-fix application; analyzes codebase + sibling specs. |
| `clean-implement.md` | `claude-opus-4-7` | `high` | Builder→Auditor loop orchestrator. |
| `queue-pick.md` | `claude-opus-4-7` | `medium` | Sequential walk + 3 eligibility filters; not deep reasoning. |
| `autopilot.md` | `claude-opus-4-7` | `high` | Meta-loop orchestrator for full queue drain. |
| `implement.md` | `claude-opus-4-7` | `high` | Single Builder pass; mirrors clean-implement. |

## Agents

| Agent file | Model | `effort` | Rationale |
|---|---|---|---|
| `builder.md` | `claude-sonnet-4-6` | `high` | API default `high`; Claude Code's Mar 3, 2026 drift to `medium` caused quality regression — explicit `high` prevents future drift. |
| `auditor.md` | `claude-opus-4-7` | `high` | Same rationale as builder; `max` for hostile-spec/multi-file-drift is a per-invocation escalation not a frontmatter change (would require mid-context model switch, which is a footgun per §Lens 2.2). |
| `security-reviewer.md` | `claude-sonnet-4-6` | `high` | Same as builder. |
| `dependency-auditor.md` | `claude-sonnet-4-6` | `medium` | Mostly mechanical: CVE scan + wheel-contents check. |
| `architect.md` | `claude-opus-4-7` | `high` | Architectural reasoning depth needed; `max` for trigger-A KDR proposals is a per-invocation escalation. |
| `sr-dev.md` | `claude-sonnet-4-6` | `high` | Same as builder. |
| `sr-sdet.md` | `claude-sonnet-4-6` | `high` | Same as builder. |
| `task-analyzer.md` | `claude-opus-4-7` | `high` | Hostile re-read against codebase; requires deep reasoning. |
| `roadmap-selector.md` | `claude-opus-4-7` | `medium` | Sequential walk + 3 filters; not deep reasoning. |

## Haiku agents

No Haiku-based agents are currently defined in `.claude/agents/`. If any are added in the
future, omit the `effort:` frontmatter field (Haiku 4.5 does not expose the `effort` parameter)
and use prompt-level brevity directives instead.

---

## How frontmatter should look after T21

```yaml
---
name: <agent-name>
description: <...>
tools: <...>
model: <model-id>
thinking:
  type: adaptive
effort: <high|medium>
# Per-role effort assignment: see .claude/commands/_common/effort_table.md
---
```

For slash commands (no `name:` / `description:` / `tools:` fields):

```yaml
---
model: <model-id>
thinking:
  type: adaptive
effort: <high|medium>
# Per-role effort assignment: see .claude/commands/_common/effort_table.md
---
```
