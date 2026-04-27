---
model: claude-opus-4-7
thinking: max
---

# /queue-pick

You are the **Queue Pick orchestrator** for: $ARGUMENTS

`$ARGUMENTS` is optional. If empty, scan all open milestones. If a milestone-list shorthand (e.g. "m10 m15") is given, scope the walk to those milestones only.

This command spawns the `roadmap-selector` agent, reads its recommendation, and reports the next action the user should run. **It does not chain into `/auto-implement` or `/clean-tasks` directly** — per the project rule on slash-command chaining (memory: `feedback_skill_chaining_reuse.md`), composite autonomy lives in a separate orchestrator (`/autopilot`, future) that inlines all three procedures.

This is the manual / one-shot version: run `/queue-pick`, get a recommendation, decide whether to follow it.

---

## Project setup

Resolve `$ARGUMENTS`:

- **Empty:** roadmap-selector scans all `design_docs/phases/milestone_*/` directories.
- **"m10 m15" / "m10":** pass the milestone list verbatim to roadmap-selector.

Build the **project context brief** — pass verbatim to the `roadmap-selector` Task spawn:

```text
Project: ai-workflows (Python, MIT, published as jmdl-ai-workflows on PyPI)
Memory path: ~/.claude/projects/-home-papa-jochy-prj-ai-workflows/memory/MEMORY.md
Architecture: design_docs/architecture.md (especially §9 KDRs)
Roadmap: design_docs/roadmap.md
Deferred-ideas file: design_docs/nice_to_have.md (out-of-scope by default)
Milestone scope: <milestones from $ARGUMENTS, or "all open" if empty>
```

Recommendation file path: `runs/queue-pick-<YYYYMMDD-HHMMSS>.md` (under the gitignored `runs/` directory). Create the path; pass to the agent.

---

## Procedure

### Step 1 — Spawn roadmap-selector

Spawn the `roadmap-selector` subagent via `Task` with: the recommendation-file path, the project context brief, the milestone list (if any). Wait for completion.

### Step 2 — Read recommendation file

Read the file the agent wrote. The verdict line is the source of truth:

- `PROCEED` — a specific task is named.
- `NEEDS-CLEAN-TASKS` — a specific milestone is named (specs missing or unhardened).
- `HALT-AND-ASK` — surface the user-arbitration question.

Do not trust a chat summary; read the file.

### Step 3 — Branch on verdict

#### Verdict: PROCEED

Report:

```
✅ Next task: <task-spec-path>
   Decision rule: <sequential | bug-blocker-override>
   Run: /auto-implement <milestone-shorthand> <task-shorthand>
        e.g. /auto-implement m10 t01
```

Followed by a one-paragraph summary of the agent's reasoning (sourced from the recommendation file's `## Reasoning` section).

If the agent's `## Decisions the orchestrator should expect during this task` block names substantive arbitration (SEMVER bump, KDR proposal, deferral), surface those bullets verbatim — the user should know what `/auto-implement` will surface for them.

#### Verdict: NEEDS-CLEAN-TASKS

Report:

```
⚠ Milestone <milestone> needs spec generation / hardening.
   Reason: <README-only | specs unhardened — task_analysis.md verdict OPEN>
   Run: /clean-tasks <milestone>
   Then re-run: /queue-pick (will re-evaluate after specs are hardened).
```

Followed by the agent's reasoning.

This is the routine routing case — no user arbitration required, just a sequencing call. The `/clean-tasks` command itself loops until LOW-only or CLEAN, so it's safe to run end-to-end.

#### Verdict: HALT-AND-ASK

Surface the agent's reasoning verbatim, including:
- Which milestones / tasks were walked.
- What blocked each (no eligible candidate by Filter 2 or Filter 3, ambiguous bug-blocker override, or codebase-paused signal).
- Which question the user must arbitrate.

Do not pick. Do not recommend a fallback. The user owns the decision.

---

## Reporting

End-of-run one-liner:

`/queue-pick — [PROCEED: <task> | NEEDS-CLEAN-TASKS: <milestone> | HALT-AND-ASK: <count> open questions]`

Plus the per-verdict report above. The recommendation file path is also surfaced so the user can re-read the full reasoning.

---

## Why /queue-pick is one-shot, not a loop

`/queue-pick` does the cheap part: ask the team which task is next. The expensive part (driving the task with `/auto-implement`, generating specs with `/clean-tasks`) is left to dedicated commands the user invokes after seeing the recommendation. This keeps `/queue-pick` light enough to run every time the user asks "what's next?" without paying the autonomy-loop cost.

For fully-autonomous queue draining (queue-pick + clean-tasks + auto-implement chained without user input between steps), see the planned `/autopilot` command — it inlines all three procedures so a single invocation drains the queue end-to-end.

## Why roadmap-selector is a subagent, not inline

The selection logic — sequential walk + three filters + bug-blocker override + verdict rubric — is its own concern. Inlining it would pollute the orchestrator's context with milestone READMEs and task analyses every time. Moving it into a `Task` spawn keeps the orchestrator's context small, lets the agent's read-only stance be enforced by its agent definition, and writes a structured recommendation file the orchestrator can re-read on a future run without re-spending the analysis tokens.
