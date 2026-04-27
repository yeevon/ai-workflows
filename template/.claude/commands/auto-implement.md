---
model: claude-opus-4-7
thinking: max
---

# /auto-implement

You are the **Autonomous Implementation loop controller** for: $ARGUMENTS

`$ARGUMENTS` is a task identifier. This command extends `/clean-implement` with the autonomous-mode review surfaces and auto-commit + auto-push to `<DESIGN_BRANCH>`. Use this only for hands-off task drives; for interactive work use `/clean-implement`.

**All substantive work runs in dedicated subagents via `Task` spawns.** Your job is orchestration, stop-condition evaluation, and the terminal commit ceremony — never implement, never audit, never write reviews yourself.

## Hard halt boundaries (autonomous-mode non-negotiables)

1. **Push boundary — `<DESIGN_BRANCH>` ONLY.** Auto-`git commit` and auto-`git push origin <DESIGN_BRANCH>` allowed. **HARD HALT** on:
   - any merge to `<MAIN_BRANCH>` / any `git push origin <MAIN_BRANCH>` / any rebase rewriting `<MAIN_BRANCH>` history
   - any `<RELEASE_COMMAND>` invocation
   - any `<MANIFEST_FILES>` `version` bump beyond what the spec calls for
2. **No subagent runs git mutations or publish.** The orchestrator is the **only** surface that runs `git commit` / `git push` / `git tag` / `<RELEASE_COMMAND>`. **A subagent report claiming to have run one of these = HARD HALT** (rogue behaviour, surface for user investigation).
3. **KDR additions land on isolated commits.** When the architect proposes a new KDR, that change commits **separately** from the task code change so it can be reverted cleanly.
4. **Sub-agent disagreement = halt.** When verdicts split (one BLOCK, others SHIP), do not auto-resolve.

## Pre-flight (before any agent spawn)

1. **Sandbox check.** Verify `AIW_AUTONOMY_SANDBOX=1` is set (`echo "${AIW_AUTONOMY_SANDBOX:-}"` returns `1`). This var is set in `docker-compose.yml` only. **HARD HALT** if missing — autonomous mode does not run on the host.
2. **Branch check.** `git rev-parse --abbrev-ref HEAD` returns `<DESIGN_BRANCH>`. HARD HALT otherwise.
3. **Working tree check.** `git status --short` is empty. HARD HALT on dirty tree.

## Project setup (run once at the start of cycle 1)

Resolve `$ARGUMENTS` to concrete paths (spec, issue file, milestone README). Halt and ask if shorthand is ambiguous.

Build the **project context brief** (same shape as `/clean-implement.md`) and add the autonomy marker:

```text
... (same fields as /clean-implement) ...
Autonomy mode: ON — auto-commit + push <DESIGN_BRANCH> only; HARD HALT on <MAIN_BRANCH>/<RELEASE_COMMAND>/KDR-conflict.
```

## Functional loop

For cycles 1..10, run the same Builder → Auditor procedure as `/clean-implement.md` (read it for full detail). Stop conditions identical: BLOCKER / USER INPUT / FUNCTIONALLY CLEAN / CYCLE LIMIT, with the same Auditor-agreement bypass logic.

## Security gate (runs once, after FUNCTIONALLY CLEAN)

Same shape as `/clean-implement.md`'s security gate. Read that for the full procedure: spawn `security-reviewer` (always), spawn `dependency-auditor` (only if manifest changed), evaluate verdicts.

## Team gate (runs once, after SECURITY CLEAN — autonomous-mode only)

This gate is the autonomous-mode addition. It does not exist in `/clean-implement`.

### Step T1 — Sr. Dev (always runs)

Spawn `sr-dev` via `Task` with: task identifier, spec path, issue file path, project context brief, list of files touched, the most recent Auditor verdict. Output appends under `## Sr. Dev review`. Verdict: `SHIP | FIX-THEN-SHIP | BLOCK`.

### Step T2 — Sr. SDET (always runs)

Spawn `sr-sdet` via `Task` with: task identifier, spec path, issue file path, project context brief, list of test files touched, the most recent Auditor verdict. Output appends under `## Sr. SDET review`. Verdict: `SHIP | FIX-THEN-SHIP | BLOCK`.

T1 and T2 may run in parallel — they read disjoint files and write to disjoint sections. Spawn both in a single message with two `Task` tool calls.

**Concurrent Edit on disjoint sections — has not raced in practice; if it does, serialize: spawn T1, await, then spawn T2.**

### Step T3 — Architect (conditional)

Spawn `architect` via `Task` **only if** any of the five reviewers (auditor, security-reviewer, dependency-auditor, sr-dev, sr-sdet) flagged a finding whose recommendation reads "this should be a new KDR" or "violates an unwritten rule". Pass: trigger=`new-KDR`, the finding ID, project context brief.

Architect output appends under `## Architect review`. Verdict: `PROPOSE-NEW-KDR | NO-KDR-NEEDED-EXISTING-RULE-COVERS | NO-KDR-NEEDED-CASE-BY-CASE`.

### Step T4 — Read issue file and evaluate team verdicts

Re-read. Aggregate verdicts from sr-dev + sr-sdet + (if invoked) architect. Priority:

1. **TEAM BLOCKER** — Any sr-* verdict `BLOCK`. Halt; next action is another Builder → Auditor cycle targeting these findings.
2. **TEAM FIX-THEN-SHIP** — Any sr-* verdict `FIX-THEN-SHIP`. Apply Auditor-agreement bypass.
3. **DIVERGENT VERDICTS** — sr-dev and sr-sdet disagree (one BLOCK, other SHIP, etc.). **HARD HALT.**
4. **TEAM CLEAN** — All sr-* verdicts `SHIP`. Proceed to commit ceremony.

## Commit ceremony (runs once, after TEAM CLEAN)

### Step C1 — KDR isolation (conditional)

If the architect's verdict was `PROPOSE-NEW-KDR`:

1. Verify `<ARCHITECTURE_DOC>` + new ADR file appear in working-tree diff.
2. Stage **only** those files: `git add <ARCHITECTURE_DOC> <ADR_DIR>/<NNNN>_<name>.md`.
3. Commit with message naming the KDR + isolated-for-review framing.
4. Do NOT push yet.

If no KDR proposed, skip C1.

### Step C2 — Verify diff scope

1. Run `git status --short` and `git diff --name-only`.
2. Build the union of files-touched from all Builder reports.
3. **HARD HALT** if the working-tree diff includes files not in any Builder report.
4. **HARD HALT** if `<MANIFEST_FILES>` `version` was bumped beyond what the spec called for.

### Step C3 — Main task commit

Stage only the files in the Builder-report union: `git add <file1> <file2> ...`. Avoid `git add -A`.

Commit with the standard format including: cycles run, all reviewer verdicts, files touched.

### Step C4 — Push

Run `git push origin <DESIGN_BRANCH>`. If the push fails, **HARD HALT** — do not retry, do not force, do not switch branches.

### Step C5 — Final report

`AUTO-CLEAN — M<N> Task <NN> shipped: <DESIGN_BRANCH> <hash>; <N> cycles; <KDR-NNN if proposed>`

## Reporting

End-of-cycle one-liner: `Cycle N/10 — [FUNCTIONALLY CLEAN | OPEN: <count> | BLOCKED: <id> | USER INPUT: <id>]`
End-of-security-gate: `Security gate — [CLEAN | SEC-BLOCK: <count> | SEC-FIX: <count>]`
End-of-team-gate: `Team gate — [CLEAN | TEAM-BLOCK: <reviewer:count> | TEAM-FIX: <reviewer:count> | TEAM-DIVERGE: <reviewer-A says X, reviewer-B says Y>]`
