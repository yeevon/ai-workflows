---
model: claude-opus-4-7
thinking:
  type: adaptive
effort: medium
# Per-role effort assignment: see .claude/commands/_common/effort_table.md
---

# /queue-pick

You are the **Queue Pick orchestrator** for: $ARGUMENTS

`$ARGUMENTS` is optional. If empty, scan all open milestones. If a milestone-list shorthand (e.g. "m10 m15") is given, scope the walk to those milestones only.

This command spawns the `roadmap-selector` agent, reads its recommendation, and reports the next action the user should run. **It does not chain into `/auto-implement` or `/clean-tasks` directly** — per the project rule on slash-command chaining (memory: `feedback_skill_chaining_reuse.md`), composite autonomy lives in a separate orchestrator (`/autopilot`, future) that inlines all three procedures.

This is the manual / one-shot version: run `/queue-pick`, get a recommendation, decide whether to follow it.

---

## Agent-return parser convention

After the `roadmap-selector` `Task` spawn, parse the agent's return per
[`.claude/commands/_common/agent_return_schema.md`](_common/agent_return_schema.md):

1. Capture the full text return to `runs/queue-pick-<ts>-raw_return.txt`.
2. Split on `\n`; expect exactly 3 non-empty lines.
3. Each line must match `^(verdict|file|section): ?(.+)$`.
4. The `verdict` value must be one of `PROCEED`, `NEEDS-CLEAN-TASKS`, `HALT-AND-ASK`
   (roadmap-selector's allowed tokens); trailing whitespace on any value is stripped before validation.
5. On any failure: halt, surface `BLOCKED: agent roadmap-selector returned non-conformant text —
   see the raw return file`. **Do not auto-retry.**

---

## Spawn-prompt scope discipline

**Reference:** [`.claude/commands/_common/spawn_prompt_template.md`](_common/spawn_prompt_template.md)

Pass only what the `roadmap-selector` will certainly use. Let the agent pull milestone
README contents and task spec details on demand via its own `Read` tool.

After the `Task` spawn, capture the spawn-prompt token count (regex proxy:
`len(re.findall(r"\S+", text)) * 1.3`, truncated to int) into
`runs/queue-pick-<ts>/spawn_roadmap-selector.tokens.txt`.

### roadmap-selector spawn

Minimal pre-load set: recommendation file path, project context brief, milestone scope
(from `$ARGUMENTS`, or "all open").

**Remove from inline content:** full milestone README content, full task spec content,
`architecture.md` content.

Output budget directive (include verbatim in the roadmap-selector spawn prompt):

```
Output budget: 1-2K tokens. Durable findings live in the recommendation file you write;
the return is the 3-line schema only — see .claude/commands/_common/agent_return_schema.md
```

---

## Project setup

Resolve `$ARGUMENTS`:

- **Empty:** roadmap-selector scans all `design_docs/phases/milestone_*/` directories.
- **"m10 m15" / "m10":** pass the milestone list verbatim to roadmap-selector.

**Compute the project memory path at runtime** — do not hardcode a username or machine path. The Claude Code auto-memory directory is hashed off the current working directory (each `/` in cwd becomes `-`), and lives under `$HOME/.claude/projects/`. **Avoid shell expansion**: `$(pwd | tr / -)` and `${HOME}` substitutions inside a single Bash call trip Claude Code's `Contains expansion` guard and prompt the user, breaking unattended autonomy.

Use **two separate Bash calls** plus orchestrator-side string assembly:

```bash
pwd                # capture working-dir path
printenv HOME      # capture invoking user's home (no expansion)
```

Then in your own thinking: replace every `/` in the captured working-dir path with `-`, and substitute into the form `<HOME>/.claude/projects/<encoded-path>/memory/MEMORY.md`. The resolved string is the `MEMORY_PATH`.

If the resulting path does not exist on disk, that's a pre-condition failure — the orchestrator was invoked from a directory Claude Code has not yet seen. Halt and surface the question (which is unusual; in normal operation the auto-memory dir is created on first conversation in the project).

Build the **project context brief** — pass verbatim to the `roadmap-selector` Task spawn:

```text
Project: ai-workflows (Python, MIT, published as jmdl-ai-workflows on PyPI)
Memory path: <MEMORY_PATH computed above; substitute the resolved absolute path>
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

**Telemetry (T22):** before spawning, run:
```bash
python scripts/orchestration/telemetry.py spawn \
  --task queue_pick --cycle 1 \
  --agent roadmap-selector --model <model-slug> --effort medium
```
After the Task returns, run `complete` with the verdict (PROCEED/NEEDS-CLEAN-TASKS/HALT-AND-ASK).
Record lands at `runs/queue_pick/cycle_1/roadmap-selector.usage.json`.

### Step 2 — Read recommendation file

Read the file the agent wrote. The verdict line is the source of truth:

- `PROCEED` — a specific task is named.
- `NEEDS-CLEAN-TASKS` — a specific milestone is named (specs missing or unhardened).
- `HALT-AND-ASK` — surface the user-arbitration question.

Do not trust a chat summary; read the file.

**Pre-condition check: empty or missing recommendation file.** If the file does not exist after the Task spawn, OR exists but is empty, OR exists but has no parseable `**Verdict:**` line, that itself is a `HALT-AND-ASK` condition — the agent halted before producing output (commonly: missing memory path, missing milestone directories, scope-load failure). Report:

```
⚠ /queue-pick — roadmap-selector did not produce a recommendation.
   Recommendation file: <path>
   Likely cause: <missing memory file | unreadable milestone dir | other pre-condition gap>
   Re-check the orchestrator's project context brief and re-run.
```

Surface the agent's last chat reply verbatim (it usually names what it was missing) and halt. Do not silently re-spawn; the issue is upstream of the agent and re-spawning will hit the same wall.

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
