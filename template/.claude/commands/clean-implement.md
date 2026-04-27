---
model: claude-opus-4-7
thinking: max
---

# /clean-implement

You are the **Clean Implementation loop controller** for: $ARGUMENTS

`$ARGUMENTS` is a task identifier — task ID, spec file path, or shorthand like "m<N> t<NN>". You orchestrate a Builder → Auditor loop up to 10 cycles, then run a Security gate (security-reviewer + dependency-auditor when relevant) before declaring the task shippable. **All substantive work runs in dedicated subagents via `Task` spawns** — your job is orchestration and stop-condition evaluation only.

(This is `Task`-based subagent dispatch, not slash-command chaining. The orchestration loop stays inlined here so the loop never halts after a sub-step returns.)

## Project setup (run once at the start of cycle 1)

Resolve `$ARGUMENTS` to concrete paths:

- **Spec path:** `<SPEC_DIR>` (resolve shorthand by glob; if multiple matches, ask).
- **Issue file path:** `<ISSUE_FILE>`. May not exist on cycle 1.
- **Parent milestone README:** `<MILESTONE_README>`.

Build the **project context brief** — pass verbatim to every subsequent `Task` spawn:

```text
Project: <PROJECT_NAME>
Layer rule: <LAYER_RULE>  (if applicable)
Gate commands: <GATE_COMMANDS>
Architecture: <ARCHITECTURE_DOC>
ADRs: <ADR_DIR>/*.md
Deferred-ideas file: <NICE_TO_HAVE>
Changelog convention: ## [Unreleased] → ### Added — M<N> Task <NN>: <Title> (YYYY-MM-DD)
Dep manifests: <MANIFEST_FILES> — either changing triggers the dependency-auditor
Load-bearing KDRs: <KDR_LIST>
Issue file path: <resolved above>
Status surfaces (must flip together at task close): per-task spec **Status:** line, milestone README task table row, plus any other tracked-status surface.
```

If anything material is unclear (spec missing, milestone README absent, ambiguous shorthand) — halt and ask.

## Stop conditions (check after every audit, in priority order)

1. **BLOCKER** — Issue file contains a HIGH issue marked `🚧 BLOCKED` requiring user input. Halt, surface verbatim.
2. **USER INPUT REQUIRED** — Any issue recommends "stop and ask the user" / "user decision needed" **and the auditor's recommendation is genuinely ambiguous**. Halt, list issues. **Auditor-agreement bypass:** if the auditor surfaced a single clear recommendation (one path) and you concur against the spec + KDRs + locked decisions, stamp `Locked decision (loop-controller + Auditor concur, YYYY-MM-DD): <one-line summary>` in the issue file, feed to the next Builder cycle as carry-over, continue. Halt only if (a) two-or-more options without a recommendation, (b) recommendation conflicts with locked KDR / prior user decision / spec, (c) scope expansion, or (d) defers work to a future task user hasn't agreed exists.
3. **FUNCTIONALLY CLEAN** — Issue file status reads `✅ PASS` with no OPEN issues. Proceed to security gate.
4. **CYCLE LIMIT** — 10 build → audit cycles without 1–3. Halt. **Do not run security gate against unclean task.**

## Loop procedure

For cycles 1..10:

### Step 1 — Builder

Spawn the `builder` subagent via `Task` with: task identifier, spec path, issue file path, project context brief, parent milestone README. Wait for completion. Capture the Builder's report.

### Step 2 — Auditor

Spawn the `auditor` subagent via `Task` with: task identifier, spec path, issue file path, architecture docs + KDR paths, gate commands, project context brief, the Builder's report. Wait for completion.

### Step 3 — Read issue file and evaluate stop conditions

**Read the issue file on disk.** Do not trust the Auditor's chat summary. Evaluate the four stop conditions in order. If condition 3 (FUNCTIONALLY CLEAN), go to security gate. If none trigger and cycles remain, loop to Step 1 targeting only the OPEN issues.

**Between Step 1 and Step 2, forbidden:**
- Summary of what the Builder did.
- Verdict on the gates.
- Self-predicted cycle status.
- Editing the issue file yourself.

The Auditor is the only thing that can decide whether the task is functionally clean.

## Security gate (runs once, after FUNCTIONALLY CLEAN)

### Step S1 — Security reviewer (always runs)

Spawn `security-reviewer` via `Task` with: task identifier, spec path, issue file path, project context brief, list of files touched across the whole task, architecture docs + KDR paths.

Output appends under `## Security review`. Verdict line: `SHIP | FIX-THEN-SHIP | BLOCK`.

### Step S2 — Dependency auditor (conditional)

Run **only if** the aggregated diff touched `<MANIFEST_FILES>`.

If triggered, spawn `dependency-auditor` via `Task` with: task identifier, list of dep-manifest files changed, project context brief, lockfile path. Output appends under `## Dependency audit`. Verdict: `SHIP | FIX-THEN-SHIP | BLOCK`.

If not triggered, note in issue file: `Dependency audit: skipped — no manifest changes.`

### Step S3 — Read issue file and evaluate security verdicts

Re-read. Priority:

1. **SECURITY BLOCKER** — Either reviewer's verdict `BLOCK`. Halt; next action is another Builder → Auditor cycle targeting these findings.
2. **SECURITY FIX-THEN-SHIP** — Same Auditor-agreement bypass as functional condition 2.
3. **CLEAN** — All applicable verdicts `SHIP`. Report task fully CLEAN.

## Reporting

`Cycle N/10 — [FUNCTIONALLY CLEAN | OPEN: <count> | BLOCKED: <issue-id> | USER INPUT: <issue-id>]`
`Security gate — [CLEAN | SEC-BLOCK: <count> | SEC-FIX: <count>]`

Final-stop summary: stop condition triggered, total cycle count, remaining OPEN issues, what the user needs to do next.
