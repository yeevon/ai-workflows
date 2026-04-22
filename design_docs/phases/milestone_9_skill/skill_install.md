# `ai-workflows` skill — install & first run

M9 T03 installation guide. Takes a fresh checkout from zero to invoking
the `planner` workflow through the [M4 MCP server](../milestone_4_mcp/mcp_setup.md)
via the Claude Code skill shipped at [`.claude/skills/ai-workflows/SKILL.md`](../../../.claude/skills/ai-workflows/SKILL.md).

Scope: install + smoke only. MCP server registration lives in M4's
[mcp_setup.md](../milestone_4_mcp/mcp_setup.md); this doc does not
duplicate it.

---

## 1. Prerequisites

- `uv sync` has been run from the repo root. `uv run which aiw` and
  `uv run which aiw-mcp` should both resolve under `.venv/bin/`.
- `GEMINI_API_KEY` is exported in the shell that will launch Claude
  Code. The MCP subprocess inherits the parent environment at spawn
  time; an unset key surfaces as a provider auth error on the first
  `run_workflow` call.
- `claude` CLI is on `PATH`. Needed for (a) `claude mcp add` (MCP
  registration) and (b) the `planner-synth` tier's Claude Code Opus
  OAuth subprocess driver — see [KDR-003](../../architecture.md).
- No Anthropic API key required or consulted (KDR-003).

## 2. Install the MCP server

One link, no duplication: follow [design_docs/phases/milestone_4_mcp/mcp_setup.md](../milestone_4_mcp/mcp_setup.md)
to register `aiw-mcp` with Claude Code (`claude mcp add ai-workflows --scope user -- uv run aiw-mcp`).
Verify with `claude mcp list` before continuing.

## 3. Install the skill

### Option A — in-repo (default, zero extra steps)

The skill file ships under source control at
[`.claude/skills/ai-workflows/SKILL.md`](../../../.claude/skills/ai-workflows/SKILL.md).
Claude Code discovers project-scoped skills automatically when launched
from the repo root (or any subdirectory). No copy, symlink, or extra
registration required.

This is the recommended option for repo-local development.

### Option B — user-level (discoverable from any cwd)

Symlink the skill directory into your Claude Code user-scope skills
directory:

```bash
mkdir -p ~/.claude/skills
ln -s "$(pwd)/.claude/skills/ai-workflows" ~/.claude/skills/ai-workflows
```

(or `cp -r …` if you prefer a copy that won't track upstream edits.)

Every Claude Code session picks the skill up regardless of cwd.

### Option C — plugin

**Not applicable at this revision.** M9 T02 (plugin manifest) is
`📝 Deferred — no trigger fired` per its own task-spec trigger gate
— see [task_02_plugin_manifest.md](task_02_plugin_manifest.md) for
the schema-check findings captured for a future Builder.

Re-open T02 if one of its three triggers fires (marketplace
distribution, second-host manifest install, or internal multi-machine
distribution need), then update this section.

## 4. End-to-end smoke

From a fresh Claude Code session registered against `aiw-mcp` and with
the skill on disk (Option A or B), ask:

> "Use the `ai-workflows` skill to draft a plan for writing a release
> checklist."

Expected chain:

1. Claude Code reads [`.claude/skills/ai-workflows/SKILL.md`](../../../.claude/skills/ai-workflows/SKILL.md).
2. Claude Code calls `run_workflow` on the MCP server with
   `workflow_id="planner"` and `inputs={"goal": "Write a release checklist"}`.
   Expected response shape (the `planner` pauses at its plan-review
   `HumanGate`; M11 T01 populated `plan` + `gate_context` at the
   pause so the operator has something to review):

   ```json
   {
     "run_id": "<ulid>",
     "status": "pending",
     "awaiting": "gate",
     "plan": {"goal": "Write a release checklist", "steps": [{"index": 1, "title": "..."}]},
     "total_cost_usd": 0.0012,
     "error": null,
     "gate_context": {
       "gate_prompt": "Approve plan for: 'Write a release checklist'? 4 steps.",
       "gate_id": "plan_review",
       "workflow_id": "planner",
       "checkpoint_ts": "2026-04-22T14:03:11.240515+00:00"
     }
   }
   ```

3. Claude Code surfaces the draft `plan` (verbatim) and the
   `gate_context.gate_prompt` to the user and asks for an approval
   or rejection.
4. On approval, Claude Code calls `resume_run` with the same `run_id`
   and `gate_response="approved"`. Expected response:

   ```json
   {
     "run_id": "<same-ulid>",
     "status": "completed",
     "awaiting": null,
     "plan": {"...": "...populated artifact..."},
     "total_cost_usd": 0.0023,
     "error": null,
     "gate_context": null
   }
   ```

Round-trip verified — the skill + MCP composed surface is live.

## 5. Troubleshooting

### Skill not discovered

- Confirm `.claude/skills/ai-workflows/SKILL.md` resolves relative to
  the cwd Claude Code launched from (Option A), or relative to
  `~/.claude/skills/` (Option B).
- Run `claude --version` and confirm your Claude Code build advertises
  skill support.
- Inspect the skill's YAML frontmatter: opening `---` on line 1, a
  `name: ai-workflows` line, a non-empty `description: …` line, and a
  closing `---` before the `# ai-workflows` heading. Malformed
  frontmatter silently hides the skill.

### MCP server not responding

Punt to [M4 mcp_setup.md §5 *Troubleshooting*](../milestone_4_mcp/mcp_setup.md)
— the common failure modes (`aiw-mcp` not on PATH, `GEMINI_API_KEY`
missing at spawn time, claude mcp list not showing the server) are
covered there.

### Fallback gate fires mid-run (M8)

If the Qwen/Ollama tier's circuit breaker trips during a
`run_workflow` call, the same `status="pending"` + `awaiting="gate"`
response shape returns — now from the M8 strict-review fallback gate
rather than the planner's plan-review gate. The failing-tier detail
(reason, retry count) is in the LangGraph checkpointer state, not in
`list_runs` (see [SKILL.md §*Gate pauses*](../../../.claude/skills/ai-workflows/SKILL.md)).
Resume with `gate_response="approved"` to trigger the configured
fallback tier (Claude Code Opus), or `"rejected"` to abort the run.

Note: a RETRY-equivalent resume must wait at least the circuit
breaker's `cooldown_s` (default 60 s — see
[`CircuitBreaker`](../../../ai_workflows/primitives/circuit_breaker.py)).
Resuming sooner re-trips the gate immediately because the breaker is
still OPEN. See [M8 milestone Outcome](../milestone_8_ollama/README.md)
for the full design.
