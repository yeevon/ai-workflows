---
model: claude-opus-4-7
thinking: max
---

# /clean-tasks

You are the **Spec Hardening loop controller** for milestone: $ARGUMENTS

`$ARGUMENTS` is a milestone identifier (e.g. "m12" or full path). Resolve to a `<SPEC_DIR_ROOT>/milestone_*` directory.

Three phases:

1. **Generate** — if no `task_*.md` specs exist yet, write them inline from the milestone README.
2. **Analyze + fix loop** — spawn `task-analyzer` subagent; read its report; apply HIGH+MEDIUM fixes; re-loop. Up to 5 rounds.
3. **Push LOWs** — append remaining LOW findings to each spec's `## Carry-over from task analysis` section.

(This is `Task`-based subagent dispatch for Phase 2 only. Phase 1 + Phase 3 + the loop controller stay inlined here so the loop never halts after a sub-step returns.)

## Project setup

Resolve `$ARGUMENTS` to a milestone directory. Verify the directory contains a `README.md`; if not, halt and ask.

**Compute the project memory path at runtime** — do not hardcode a username or machine path:

```bash
MEMORY_PATH="$HOME/.claude/projects/$(pwd | tr / -)/memory/MEMORY.md"
```

Build the **project context brief** — pass verbatim to every `task-analyzer` spawn (substitute the resolved `MEMORY_PATH` into the line below):

```text
Project: <PROJECT_NAME>
Layer rule: <LAYER_RULE>  (if applicable)
Gate commands: <GATE_COMMANDS>
Architecture: <ARCHITECTURE_DOC>
ADRs: <ADR_DIR>/*.md
Deferred-ideas file: <NICE_TO_HAVE>
Changelog convention: ## [Unreleased] → ### Added — M<N> Task <NN>: <Title> (YYYY-MM-DD)
Dep manifests: <MANIFEST_FILES>
Load-bearing KDRs: <KDR_LIST>
Status surfaces (must flip together at task close): per-task spec **Status:** line, milestone README task table row, plus any other tracked-status surface.
Project memory: <MEMORY_PATH computed above; substitute the resolved absolute path>
                   (read for milestone status — on-hold / paused / pending external trigger)
```

## Phase 1 — Generate (run inline; skip if specs already exist)

Check the milestone directory for `task_*.md` files. If at least one exists, skip generation.

If none exist:

1. Read the milestone README in full. Extract the task-order table (each row names a task slug + kind).
2. Read `<ARCHITECTURE_DOC>` (especially the layer rule + KDR section), the cited ADRs, and any sibling milestone READMEs.
3. Read at least two recent task specs from already-shipped milestones as templating examples. Match their structural shape.
4. Write one `task_<NN>_<slug>.md` per row. Each spec must:
   - Cite at least one KDR.
   - Set `**Status:** 📝 Planned.`
   - For code tasks: name an explicit smoke test the Auditor will run.
   - List explicit Out-of-scope items.
   - Include empty Carry-over sections.

Do **not** invent scope beyond what the milestone README names.

## Phase 2 — Analyze + fix loop

For rounds 1..5:

### Step 1 — Spawn task-analyzer

Spawn the `task-analyzer` subagent via `Task` with: milestone directory path, analysis-output file path (`<milestone-dir>/task_analysis.md`), project context brief, round number, list of task specs to analyze.

### Step 2 — Read the analysis report

**Read the analysis file on disk.** Do not trust the agent's chat summary. Parse the Summary table to extract HIGH/MEDIUM/LOW counts.

### Step 3 — Evaluate stop conditions (priority order)

1. **STOP-AND-ASK** — Any finding's Recommendation says *"Stop and ask the user"* (typically a HIGH that can't be auto-resolved). Halt.
2. **CLEAN** — `HIGH = 0` and `MEDIUM = 0` and `LOW = 0`. Loop done.
3. **LOW-ONLY** — `HIGH = 0` and `MEDIUM = 0` and `LOW > 0`. Proceed to Phase 3.
4. **OPEN** — `HIGH > 0` or `MEDIUM > 0`. Proceed to Step 4 and re-loop.
5. **CYCLE LIMIT** — 5 rounds without 2 / 3 / STOP-AND-ASK. Halt; surface remaining HIGH+MEDIUM.

### Step 4 — Apply fixes (only on OPEN)

For each HIGH and MEDIUM finding:
- If the finding's `Apply this fix:` block is mechanical (literal old_string → new_string), apply it with `Edit`.
- If two reasonable options, pick the one the analyzer recommended; if no clear recommendation, apply the lower-coupling option.
- If non-mechanical, apply the Recommendation as best as understood. If you can't apply confidently, treat as STOP-AND-ASK.

**Forbidden during Step 4:**
- Editing source code. Spec edits only.
- Editing the milestone README's task-order table to *avoid* a status-surface MEDIUM (fix the spec to match the README, or add a deliverable to update the README).
- Adopting items from `<NICE_TO_HAVE>`.
- Self-grading pass / fail.
- Skipping a finding.

### Step 5 — Round summary

`Round <N>/5 — <CLEAN | LOW-ONLY (n LOW) | OPEN (h HIGH, m MEDIUM, l LOW; applied <count> fixes) | STOP-AND-ASK: <one-line>>`

## Phase 3 — Push LOWs to spec carry-over (runs once on LOW-ONLY)

For each LOW finding marked `Push to spec: yes`:

1. Open the cited task spec file.
2. Find or append `## Carry-over from task analysis`.
3. Append the LOW finding as a checkbox item:
   ```markdown
   - [ ] **TA-LOW-NN — <title>** (severity: LOW, source: task_analysis.md round <N>)
         <description>
         **Recommendation:** <recommendation>
   ```
4. Mark the LOW as `pushed=true` in the analysis file.

`Phase 3 — pushed <count> LOW findings to <m> task spec carry-over sections.`

## Stop conditions (full priority list)

1. **GENERATION-BLOCKED** — Phase 1: milestone README missing or task-order table can't be parsed.
2. **STOP-AND-ASK** — Phase 2: any finding requires user arbitration.
3. **CLEAN / LOW-ONLY** — Phase 2 verdict triggers Phase 3 (LOW-ONLY) or exits (CLEAN).
4. **CYCLE LIMIT** — Phase 2: 5 rounds without convergence.
5. **FIX-APPLICATION-BLOCKED** — Phase 2 Step 4: a fix can't be applied confidently.

## Reporting

End-of-run one-liner: `/clean-tasks — [DONE: <stop condition> | STOP-AND-ASK: <one-liner>]`
