# Task 01 — `.claude/skills/ai-workflows/SKILL.md` + Supporting Files

**Status:** 📝 Planned.
**Grounding:** [milestone README §Exit criteria 1–2](README.md) · [architecture.md §4.4](../../architecture.md) · [KDR-002](../../architecture.md) · [M4 mcp_setup.md](../milestone_4_mcp/mcp_setup.md).

## What to Build

The skill file that teaches Claude Code *when* and *how* to invoke
ai-workflows through the already-shipped MCP surface (M4) or the `aiw`
CLI (M3). This task lands **packaging only** — no orchestration logic,
no new Python modules, no new runtime dependencies. Every action the
skill documents resolves to either:

1. A tool call on the `ai-workflows` MCP server (`run_workflow`,
   `resume_run`, `list_runs`, `cancel_run`), or
2. A shell-out to `uv run aiw …`.

The skill's job is to give the LLM inside Claude Code a recipe card.
**KDR-002 forbids skill-side orchestration** — the substrate stays in
`ai_workflows.workflows.*`.

The SKILL.md goes under `.claude/skills/ai-workflows/` in this repo
(so it travels with the project). The distribution surface (user-level
install) is T03's concern, not T01's.

## Deliverables

### [.claude/skills/ai-workflows/SKILL.md](../../../.claude/skills/ai-workflows/SKILL.md)

Single markdown file. Follow the Claude Code skill convention:
YAML frontmatter + body. Required sections:

```markdown
---
name: ai-workflows
description: Invoke ai-workflows planner / slice_refactor workflows through
  the MCP server (primary) or the aiw CLI (fallback). Use when the user
  asks for a plan from a goal, or to refactor a slice of code across
  parallel branches.
---

# ai-workflows

## When to use
- The user asks for a plan from a goal → call `run_workflow` with
  `workflow_id="planner"`.
- The user asks to refactor a code slice across multiple files in
  parallel → call `run_workflow` with `workflow_id="slice_refactor"`.
- The user asks for the status of a prior run → call `list_runs`.
- A run is paused at a gate and the user approves / rejects →
  call `resume_run`.
- The user cancels a pending run → call `cancel_run`.

## Primary surface — MCP
<documented invocation examples for each of the four tools, each
matching the signature in ai_workflows/mcp/schemas.py>

## Fallback surface — `aiw` CLI
<one-liner per command: aiw run, aiw resume, aiw list-runs>
Use only if the MCP server isn't registered in the current host.

## Gate pauses
- The planner pauses once at the plan-review gate.
- slice_refactor pauses at the strict-review gate.
- The Ollama fallback gate (M8) may fire mid-run with `awaiting="gate"`
  and `gate_reason` naming the failing tier. Surface the reason to the
  user before resuming; RETRY requires waiting the circuit cooldown.

## What this skill does NOT do
- No orchestration logic. All branching lives in the workflows layer.
- No direct LLM calls. The skill never reads GEMINI_API_KEY; the MCP
  subprocess does.
- No Anthropic API. KDR-003 — Claude access is OAuth-only via the
  `claude` CLI subprocess inside the `planner-synth` tier.
```

The exact YAML frontmatter shape matches Claude Code's skill
spec — `name` + `description` only (no `allowed-tools` block; the
skill calls out to MCP tools the host already exposes, and the
`claude mcp add` registration is what grants access).

### Supporting files (if any)

None by default. The skill is a single markdown file. If examples
grow large enough to warrant a nested `examples/` directory, the
split lands at T03's distribution-doc pass, not T01.

### Tests

[tests/skill/test_skill_md_shape.py](../../../tests/skill/test_skill_md_shape.py):

- `test_skill_md_exists` — `.claude/skills/ai-workflows/SKILL.md`
  resolves to a readable file.
- `test_skill_md_frontmatter` — parses YAML frontmatter; asserts
  `name == "ai-workflows"` and `description` is non-empty.
- `test_skill_md_names_all_four_mcp_tools` — body contains the
  literal strings `run_workflow`, `resume_run`, `list_runs`,
  `cancel_run` (guards against MCP-surface drift after M4's
  four-tool contract).
- `test_skill_md_names_registered_workflows` — body contains
  `planner` and `slice_refactor` (the two registered workflows
  today; the test reads `workflows.list_workflows()` so it stays
  honest if a third workflow lands).
- `test_skill_md_forbids_anthropic_api` — body does **not** contain
  `ANTHROPIC_API_KEY` or `anthropic.com/api` (KDR-003 guardrail —
  the skill must never instruct the host to set the banned key).

These are pure-filesystem tests. No pytest fixtures from the
primitives / graph / workflows layers. No subprocess calls.

## Acceptance Criteria

- [ ] `.claude/skills/ai-workflows/SKILL.md` exists with YAML
      frontmatter (`name`, `description`) and the five required body
      sections (*When to use*, *Primary surface — MCP*, *Fallback
      surface — CLI*, *Gate pauses*, *What this skill does NOT do*).
- [ ] Every documented action resolves to an MCP tool call or an
      `aiw` shell-out. No Python import, no direct LLM call.
- [ ] No new runtime or dev dependency introduced (`pyproject.toml`
      diff is empty).
- [ ] No new `ai_workflows.*` module introduced. No new
      import-linter contract. `uv run lint-imports` still reports
      **4 contracts kept**.
- [ ] Every listed test passes under
      `uv run pytest tests/skill/test_skill_md_shape.py`.
- [ ] `uv run pytest` + `uv run lint-imports` + `uv run ruff check`
      all clean.

## Dependencies

- M4 close-out (MCP server is live; `claude mcp add` registration
  is the skill's primary invocation channel).
- M3 close-out (`aiw run` / `aiw resume` / `aiw list-runs` — the
  fallback surface).

## Out of scope (explicit)

- Plugin manifest / marketplace distribution. (T02.)
- User-facing install docs. (T03.)
- Any `.claude/commands/*.md` slash commands wrapping the skill.
  (Not on the M9 punch list. `/implement`, `/audit`,
  `/clean-implement` already exist for Builder / Auditor — the
  skill is the *runtime* surface, not the authoring surface.)
- Non-Claude-Code host onboarding (Cursor, Zed, etc.). The MCP
  surface is portable; the skill is Claude-Code-specific
  packaging. Other hosts read the MCP schema directly.
