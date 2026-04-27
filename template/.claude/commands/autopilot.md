---
model: claude-opus-4-7
thinking: max
---

# /autopilot

You are the **Autonomous Queue-Drain orchestrator** for: $ARGUMENTS

`$ARGUMENTS` is optional. If empty, drain the entire open queue. If a milestone-list shorthand (e.g. "m<N> m<M>") is given, scope the drain to those milestones only.

This command is the meta-loop on top of `/queue-pick`, `/clean-tasks`, and `/auto-implement`. It loops over (queue-pick → clean-tasks-if-needed → auto-implement) until the queue drains, the supplied scope exhausts, or a halt fires. **It does not chain via the `Skill` tool** (Skill chaining returns after one call, breaking the outer loop); instead, the orchestrator reads `.claude/commands/auto-implement.md` and `.claude/commands/clean-tasks.md` and executes their procedures inline as part of this single conversation.

**This is the autonomy command.** It auto-commits + auto-pushes `<DESIGN_BRANCH>`, runs every team gate, and only stops on halt boundaries or queue exhaustion. Use `/queue-pick` for the manual one-shot version.

## Hard halt boundaries (autonomous-mode non-negotiables)

Same as `/auto-implement`'s set, restated so this orchestrator is self-contained:

1. **Push boundary — `<DESIGN_BRANCH>` ONLY.** Auto-commit + push allowed. **HARD HALT** on:
   - any merge to `<MAIN_BRANCH>` / push to `<MAIN_BRANCH>` / rebase rewriting `<MAIN_BRANCH>` history
   - any `<RELEASE_COMMAND>` invocation
   - any `<MANIFEST_FILES>` `version` bump beyond what a task spec calls for
2. **No subagent runs git mutations or publish.** Subagent claiming to have done so = HARD HALT.
3. **KDR additions land on isolated commits.**
4. **Sub-agent disagreement = halt.**
5. **Per-task halt = stop the outer loop.** Do not skip a failing task and pick the next one.

## Pre-flight (run once, before iteration 1)

1. **Sandbox check.** `AIW_AUTONOMY_SANDBOX=1` must be set. HARD HALT if missing.
2. **Branch check.** Must be on `<DESIGN_BRANCH>`. HARD HALT otherwise.
3. **Working tree check.** `git status --short` must be empty. HARD HALT on dirty tree.
4. **Memory path computation:**
   ```bash
   MEMORY_PATH="$HOME/.claude/projects/$(pwd | tr / -)/memory/MEMORY.md"
   ```
   Verify exists.
5. **Resolve milestone scope** from `$ARGUMENTS`.

## Outer loop — drain the queue

For iteration `N` from 1 upward (no hard cap; halt on boundaries above or queue-exhaust below):

### Step A — Roadmap selection (queue-pick logic, inlined)

1. Build the project context brief for `roadmap-selector` (memory path + milestone scope + standard fields).
2. Recommendation file path: `runs/autopilot-<run-timestamp>-iter<N>.md`.
3. Spawn `roadmap-selector` via `Task`. Wait for completion.
4. **Read the recommendation file on disk.** Verdict line is the source of truth. Empty / missing / no-`Verdict:`-line → treat as `HALT-AND-ASK` with surface "agent halted before producing output".

Branch on verdict:

- **PROCEED** with `<task>` → go to Step B.
- **NEEDS-CLEAN-TASKS** with `<milestone>` → go to Step C.
- **HALT-AND-ASK** → surface verbatim, halt the outer loop.

### Step B — Drive the task (auto-implement procedure, inlined)

**Read `.claude/commands/auto-implement.md` and execute its full procedure inline against the recommended task.** That file is the authoritative procedure; do not paraphrase it. Execute every step in order: pre-flight, project setup, functional loop (1..10 cycles), security gate, team gate, commit ceremony.

**On `AUTO-CLEAN`:** record the task; return to Step A. Working tree is clean again.

**On any halt:** halt the outer loop with the procedure's halt surface verbatim. Do not skip and pick next.

### Step C — Harden the milestone's specs (clean-tasks procedure, inlined)

**Read `.claude/commands/clean-tasks.md` and execute its full procedure inline against the recommended milestone.** Phase 1 (generate if missing) → Phase 2 (analyze + fix loop, up to 5 rounds) → Phase 3 (push LOWs).

**On `CLEAN` or `LOW-ONLY`:** record the milestone; return to Step A (re-spawn `roadmap-selector` — milestone now eligible).

**On any halt:** halt the outer loop with the surface verbatim.

### Step D — Iteration boundary

After Step B's `AUTO-CLEAN` or Step C's `CLEAN`/`LOW-ONLY`:
1. Re-verify working tree is clean. Dirty = HARD HALT.
2. Re-verify branch is `<DESIGN_BRANCH>`. HARD HALT otherwise.
3. Increment `N`; return to Step A.

### Queue-exhaust condition

`Step A` returning `HALT-AND-ASK` with an empty open-task list = queue drained. Report `QUEUE DRAINED` and exit cleanly.

## Step E — Reporting

### Per-iteration one-liner

`Iter N — <PROCEED <task> → AUTO-CLEAN <hash> | NEEDS-CLEAN-TASKS <milestone> → LOW-ONLY (n LOWs) | HALT-AND-ASK: <one-liner>>`

### Final report

```
/autopilot — <DRAINED | HALT: <reason> | SCOPE-EXHAUSTED>

Iterations run: N
Tasks shipped: <count>
  - <milestone/task> @ <DESIGN_BRANCH> <hash>
Milestones cleaned: <count>
  - <milestone> → <CLEAN | LOW-ONLY (n LOWs)>
KDR additions: <count>
  - KDR-<NNN> "<name>" — <DESIGN_BRANCH> <isolated commit hash>
Halt reason (if any): <verbatim from the failing step>
Recommendation files: runs/autopilot-<run-timestamp>-iter*.md
```
