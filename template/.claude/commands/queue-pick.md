---
model: claude-opus-4-7
thinking: max
---

# /queue-pick

You are the **Queue Pick orchestrator** for: $ARGUMENTS

`$ARGUMENTS` is optional. If empty, scan all open milestones. If a milestone-list shorthand (e.g. "m<N> m<M>") is given, scope the walk to those milestones only.

This command spawns the `roadmap-selector` agent, reads its recommendation, and reports the next action the user should run. **It does not chain into `/auto-implement` or `/clean-tasks` directly** — composite autonomy lives in `/autopilot`, which inlines all three procedures.

This is the manual / one-shot version: run `/queue-pick`, get a recommendation, decide whether to follow it.

## Project setup

Resolve `$ARGUMENTS`:
- **Empty:** roadmap-selector scans all `<SPEC_DIR_ROOT>/milestone_*/` directories.
- **List:** pass the milestone list verbatim.

**Compute the project memory path at runtime** — do not hardcode a username or machine path:

```bash
MEMORY_PATH="$HOME/.claude/projects/$(pwd | tr / -)/memory/MEMORY.md"
```

If the resulting path does not exist on disk, halt and surface the question.

Build the **project context brief** — pass verbatim to the `roadmap-selector` Task spawn:

```text
Project: <PROJECT_NAME>
Memory path: <MEMORY_PATH computed above; substitute the resolved absolute path>
Architecture: <ARCHITECTURE_DOC>
Roadmap: <ROADMAP>
Deferred-ideas file: <NICE_TO_HAVE>
Milestone scope: <milestones from $ARGUMENTS, or "all open" if empty>
```

Recommendation file path: `runs/queue-pick-<YYYYMMDD-HHMMSS>.md` (under the gitignored `runs/` directory). Create the path; pass to the agent.

## Procedure

### Step 1 — Spawn roadmap-selector

Spawn the `roadmap-selector` subagent via `Task` with: recommendation-file path, project context brief, milestone list (if any). Wait for completion.

### Step 2 — Read recommendation file

Read the file the agent wrote. The verdict line is the source of truth:

- `PROCEED` — a specific task is named.
- `NEEDS-CLEAN-TASKS` — a specific milestone is named.
- `HALT-AND-ASK` — surface the user-arbitration question.

Do not trust a chat summary; read the file.

**Pre-condition check: empty or missing recommendation file.** If the file does not exist after the Task spawn, OR exists but is empty, OR exists but has no parseable `**Verdict:**` line, that itself is a `HALT-AND-ASK` condition. Surface the agent's last chat reply verbatim; do not silently re-spawn.

### Step 3 — Branch on verdict

#### Verdict: PROCEED

```
✅ Next task: <task-spec-path>
   Decision rule: <sequential | bug-blocker-override>
   Run: /auto-implement <milestone-shorthand> <task-shorthand>
        e.g. /auto-implement m<N> t<NN>
```

Followed by a one-paragraph summary of the agent's reasoning.

If the agent's `## Decisions the orchestrator should expect during this task` block names substantive arbitration (SEMVER bump, KDR proposal, deferral), surface those bullets verbatim.

#### Verdict: NEEDS-CLEAN-TASKS

```
⚠ Milestone <milestone> needs spec generation / hardening.
   Reason: <README-only | specs unhardened — task_analysis.md verdict OPEN>
   Run: /clean-tasks <milestone>
   Then re-run: /queue-pick
```

This is the routine routing case — no user arbitration required.

#### Verdict: HALT-AND-ASK

Surface the agent's reasoning verbatim:
- Which milestones / tasks were walked.
- What blocked each.
- Which question the user must arbitrate.

Do not pick. Do not recommend a fallback.

## Reporting

`/queue-pick — [PROCEED: <task> | NEEDS-CLEAN-TASKS: <milestone> | HALT-AND-ASK: <count> open questions]`

Plus the per-verdict report. The recommendation file path is also surfaced.
