---
model: claude-opus-4-7
thinking: max
---

# /auto-implement

You are the **Autonomous Implementation loop controller** for: $ARGUMENTS

`$ARGUMENTS` is a task identifier — task ID, spec file path, or shorthand like "m16 t1". This command extends `/clean-implement` with the autonomous-mode review surfaces and auto-commit+push to `design_branch`. Use this only when you (the user) want the task driven end-to-end without per-cycle approval; for interactive work use `/clean-implement`.

**All substantive work runs in dedicated subagents via `Task` spawns.** Your job is orchestration, stop-condition evaluation, and the terminal commit ceremony — never implement, never audit, never write reviews yourself.

(This is `Task`-based subagent dispatch, not slash-command chaining. The orchestration loop stays inlined here so the loop controller never halts after a sub-step returns. See memory note `feedback_skill_chaining_reuse.md`.)

---

## Hard halt boundaries (autonomous-mode non-negotiables)

Per the eight autonomy decisions locked 2026-04-27 (memory: `feedback_autonomous_mode_boundaries.md`):

1. **Push boundary — `design_branch` ONLY.** You may auto-`git commit` and auto-`git push origin design_branch`. **HARD HALT** on:
   - any merge to `main`
   - any `git push origin main`
   - any rebase that rewrites `main` history
   - any `uv publish` invocation
   - any change to `pyproject.toml` `version` line beyond what the spec calls for
2. **No subagent runs git mutations or publish.** The orchestrator (this command) is the **only** surface that runs `git commit` / `git push` / `git tag` / `uv publish`. Every subagent prompt (`builder`, `auditor`, `security-reviewer`, `dependency-auditor`, `task-analyzer`, `architect`, `sr-dev`, `sr-sdet`) carries an explicit non-negotiable that forbids these operations. **If any subagent's report claims to have run one of these commands, that's a HARD HALT** — surface for user investigation. Do not absorb the apparent commit into the orchestrator's commit ceremony; treat as rogue behaviour.
3. **KDR additions land on isolated commits.** When the architect proposes a new KDR (Trigger B verdict `PROPOSE-NEW-KDR`), the architecture.md + ADR change commits **separately** from the task code change so it can be reverted cleanly.
4. **Sub-agent disagreement = halt.** When the team's verdicts split (one says BLOCK, others say SHIP), do not auto-resolve. Halt and surface for user.

If at any point the loop attempts to invoke a halted operation, abort the cycle and report the boundary that fired.

---

## Project setup (run once at the start of cycle 1)

Resolve `$ARGUMENTS` to concrete paths:

- **Spec path:** `design_docs/phases/milestone_<M>_<name>/task_<NN>_<slug>.md`. Resolve shorthand by glob: "m16 t1" → `design_docs/phases/milestone_16_*/task_01_*.md`. If multiple matches, halt and ask.
- **Issue file path:** `design_docs/phases/milestone_<M>_<name>/issues/task_<NN>_issue.md`. May not exist on cycle 1.
- **Parent milestone README:** `design_docs/phases/milestone_<M>_<name>/README.md`.

Verify the working tree is clean (`git status --short` returns empty) before starting. A dirty tree means the loop would conflate prior in-flight changes with this task's diff at commit time. If dirty, halt and surface the diff for user review.

Confirm current branch is `design_branch`. If not, halt — autonomous mode does not switch branches.

Build the **project context brief** — pass verbatim to every subsequent `Task` spawn:

```text
Project: ai-workflows (Python, MIT, published as jmdl-ai-workflows on PyPI)
Layer rule: primitives → graph → workflows → surfaces (enforced by `uv run lint-imports`)
Gate commands: `uv run pytest`, `uv run lint-imports`, `uv run ruff check`
Architecture: design_docs/architecture.md (especially §3 four-layer rule, §6 dep table, §9 KDRs)
ADRs: design_docs/adr/*.md
Deferred-ideas file: design_docs/nice_to_have.md (out-of-scope by default)
Changelog convention: ## [Unreleased] → ### Added — M<N> Task <NN>: <Title> (YYYY-MM-DD)
Dep manifests: pyproject.toml + uv.lock — either changing triggers the dependency-auditor
Load-bearing KDRs: 002 (MCP-as-substrate), 003 (no Anthropic API), 004 (validator pairing),
                   006 (three-bucket retry via RetryingEdge), 008 (FastMCP + pydantic schema as
                   public contract), 009 (SqliteSaver-only checkpoints),
                   013 (user-owned external workflow code)
Issue file path: <resolved above>
Status surfaces (must flip together at task close): per-task spec **Status:** line,
                   milestone README task table row, tasks/README.md row if present,
                   milestone README "Done when" checkboxes
Autonomy mode: ON — auto-commit + push design_branch only; HARD HALT on main/publish/KDR-conflict.
```

If anything material is unclear (spec missing, milestone README absent, ambiguous shorthand) — **halt and surface to the user** before spawning agents.

---

## Stop conditions (functional loop, check after every audit, in priority order)

1. **BLOCKER** — Issue file contains a HIGH issue marked `🚧 BLOCKED` requiring user input. Halt, surface verbatim.
2. **USER INPUT REQUIRED** — Any issue recommends "stop and ask the user" / "user decision needed" **and the auditor's recommendation is genuinely ambiguous** (two or more reasonable paths surfaced; the auditor declines to pick one; the choice is a substantive design lock the user must own). Halt, list all such issues. **Auditor-agreement bypass:** if the auditor surfaced a single clear recommendation (one path, not "Option A vs Option B for the user to pick") and you concur with that recommendation against the spec + KDRs + locked decisions in the issue file, treat the recommendation as the locked decision: stamp it into the issue file as `Locked decision (loop-controller + Auditor concur, YYYY-MM-DD): <one-line summary>`, feed it to the next Builder cycle as a carry-over AC, and continue the loop. Halt only if (a) the auditor presents two or more options without a recommendation, (b) the recommendation conflicts with a locked KDR / prior user decision / the spec, (c) the recommendation expands scope beyond the spec, or (d) the recommendation defers work to a future task that the user hasn't already agreed exists.
3. **FUNCTIONALLY CLEAN** — Issue file status line reads `✅ PASS` with no OPEN issues. Proceed to the **security + team gates** below.
4. **CYCLE LIMIT** — 10 build → audit cycles without 1–3. Halt, present outstanding issues. **Do not run the security or team gates against an unclean task.**

**At the start of cycle 1 only:** if the issue file already contains an unresolved BLOCKER from a prior session, treat as condition 1 immediately — don't spawn the Builder against an open blocker.

---

## Functional loop procedure

For cycles 1..10:

### Step 1 — Builder

Spawn the `builder` subagent via `Task` with: task identifier, spec path, issue file path, project context brief, parent milestone README path. Wait for completion. Capture the Builder's report.

### Step 2 — Auditor

Spawn the `auditor` subagent via `Task` with: task identifier, spec path, issue file path, architecture docs + KDR paths, gate commands, project context brief, the Builder's report from Step 1. Wait for completion.

### Step 3 — Read issue file and evaluate stop conditions

**Read the issue file on disk.** Do not trust the Auditor's chat summary — the issue file is the source of truth. Evaluate the four stop conditions in order against what's actually written. If condition 3 (FUNCTIONALLY CLEAN) triggers, go to the **security gate**. If none trigger and cycles remain, loop to Step 1 targeting only the OPEN issues the audit identified.

**Between Step 1 and Step 2, forbidden:**

- Summary of what the Builder did.
- Verdict on the gates ("gates pass, so the cycle is clean").
- Self-predicted cycle status.
- A "ready for audit" todo update.
- Editing the issue file yourself.

The Auditor is the only thing that can decide whether the task is functionally clean.

---

## Security gate (runs once, after FUNCTIONALLY CLEAN)

Same shape as `/clean-implement`. Re-stated here so the autonomous loop is self-contained.

### Step S1 — Security reviewer (always runs)

Spawn `security-reviewer` via `Task` with: task identifier, spec path, issue file path, project context brief, list of files touched across the whole task (aggregate from all Builder reports), architecture docs + KDR paths.

Output appends under `## Security review` in the issue file. Verdict line: `SHIP | FIX-THEN-SHIP | BLOCK`.

### Step S2 — Dependency auditor (conditional)

Run **only if** the aggregated diff across this task touched `pyproject.toml` or `uv.lock`. Check by inspecting Builder reports for manifest edits.

If triggered, spawn `dependency-auditor` via `Task` with: task identifier, list of dep-manifest files changed, project context brief, lockfile path. Output appends under `## Dependency audit` in the issue file. Verdict line: `SHIP | FIX-THEN-SHIP | BLOCK`.

If not triggered, note in the issue file: `Dependency audit: skipped — no manifest changes.`

### Step S3 — Read issue file and evaluate security verdicts

Re-read the issue file. Evaluate in priority order:

1. **SECURITY BLOCKER** — Either reviewer's verdict is `BLOCK`. Halt; surface findings verbatim. The task is **not** CLEAN. Next action is another Builder → Auditor cycle targeting these findings.
2. **SECURITY FIX-THEN-SHIP** — Either reviewer's verdict is `FIX-THEN-SHIP`. Apply the same Auditor-agreement bypass logic from functional condition 2. If clear consensus → stamp `Locked security decision (loop-controller + reviewer concur, YYYY-MM-DD): <summary>` and re-loop with the finding as carry-over. Halt and surface only if (a) two-plus options without recommendation, (b) recommendation conflicts with KDR / prior user decision / spec, (c) scope expansion, or (d) defers to a future task that doesn't exist.
3. **SECURITY CLEAN** — All applicable reviewers' verdicts are `SHIP`. Proceed to the **team gate**.

---

## Team gate (runs once, after SECURITY CLEAN — autonomous-mode only)

This gate is the autonomous-mode addition. It does not exist in `/clean-implement`. The gate enforces the consensus rule from autonomy decision 3: "more auditor sub-agents for resolving bugs if they align or agree".

### Step T1 — Sr. Dev (always runs)

Spawn `sr-dev` via `Task` with: task identifier, spec path, issue file path, project context brief, list of files touched across the whole task, the most recent Auditor verdict.

Output appends under `## Sr. Dev review` in the issue file. Verdict line: `SHIP | FIX-THEN-SHIP | BLOCK`.

### Step T2 — Sr. SDET (always runs)

Spawn `sr-sdet` via `Task` with: task identifier, spec path, issue file path, project context brief, list of test files touched across the whole task, the most recent Auditor verdict.

Output appends under `## Sr. SDET review` in the issue file. Verdict line: `SHIP | FIX-THEN-SHIP | BLOCK`.

T1 and T2 may run in parallel — they read disjoint files (sr-dev reads source, sr-sdet reads tests) and write to disjoint sections of the same issue file. Spawn both in a single message with two `Task` tool calls.

**Concurrent Edit on disjoint sections — has not raced in practice; if it does (e.g. one section's append clobbers the other's mid-write), serialize: spawn T1, await completion, then spawn T2.** Each agent uses Edit to append its own `## Sr. <Role> review` section, so the disjoint-section assumption holds as long as neither rewrites the other's section. Surface the race as a tooling finding for follow-up rather than retrying the gate.

### Step T3 — Architect (conditional)

Spawn `architect` via `Task` **only if** any of the five reviewers (auditor, security-reviewer, dependency-auditor, sr-dev, sr-sdet) flagged a finding whose recommendation reads "this should be a new KDR" or "violates an unwritten rule". Pass: trigger=`new-KDR`, the finding ID, the project context brief.

Architect output appends under `## Architect review` in the issue file. Verdict line: `PROPOSE-NEW-KDR | NO-KDR-NEEDED-EXISTING-RULE-COVERS | NO-KDR-NEEDED-CASE-BY-CASE`.

### Step T4 — Read issue file and evaluate team verdicts

Re-read the issue file. Aggregate verdicts from sr-dev + sr-sdet + (if invoked) architect. Evaluate in priority order:

1. **TEAM BLOCKER** — Any sr-* verdict is `BLOCK`. Halt; surface findings. Next action is another Builder → Auditor cycle targeting these findings (BLOCK from sr-dev / sr-sdet means a hidden bug or test-passes-for-wrong-reason — code change required, security and team gates re-run after).
2. **TEAM FIX-THEN-SHIP** — Any sr-* verdict is `FIX-THEN-SHIP`. Apply the Auditor-agreement bypass: if all FIX findings carry single clear recommendations and you concur against KDRs + spec, stamp `Locked team decision (loop-controller + sr-* concur, YYYY-MM-DD): <summary>` per finding and re-loop with each as carry-over. Halt only on the same four conditions (multi-option, KDR conflict, scope expansion, deferral to nonexistent task).
3. **DIVERGENT VERDICTS** — sr-dev and sr-sdet disagree (one says BLOCK, other says SHIP, etc.). **HARD HALT.** Surface the disagreement; user arbitrates. Per autonomy decision 3 the team must align before work proceeds.
4. **TEAM CLEAN** — All sr-* verdicts are `SHIP`. Proceed to the **commit ceremony**.

---

## Commit ceremony (runs once, after TEAM CLEAN — autonomous-mode only)

Per autonomy decisions 1 and 2.

### Step C1 — KDR isolation (conditional)

If the architect's verdict was `PROPOSE-NEW-KDR`:

1. The architect's review section names the architecture.md edit + ADR file. The Builder will have already written these (the architect proposes; the Builder writes the actual file edits when re-looping).
2. Verify those files appear in the working-tree diff: `design_docs/architecture.md`, `design_docs/adr/<NNNN>_<name>.md`.
3. Stage **only** those files: `git add design_docs/architecture.md design_docs/adr/<NNNN>_<name>.md`.
4. Commit with message naming the KDR + isolated-for-review framing:
   ```
   KDR-<NNN>: <one-line name> — proposed by architect, isolated for review

   Surfaced during M<N> Task <NN> autonomous-mode close-out. Lands as
   its own commit so the architectural lock can be reverted independently
   of the task code if later review rejects the KDR.

   Failure mode: <from architect review>
   Locked pattern: <from architect review>
   Alternative considered: <from architect review>

   See design_docs/adr/<NNNN>_<name>.md for the full ADR.

   Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
   ```
5. Do NOT push yet — push happens once at the end after the task commit lands.

If no KDR proposed, skip C1.

### Step C2 — Verify diff scope

Before the main task commit, verify the remaining working-tree diff matches what the Builder reported across all cycles:

1. Run `git status --short` and `git diff --name-only`.
2. Build the union of files-touched from all Builder reports.
3. **HARD HALT** if the working-tree diff includes files not in any Builder report. That means either an out-of-scope edit landed silently or a cycle's report was incomplete — either way, surface for user review.
4. **HARD HALT** if `pyproject.toml` `version` was bumped beyond what the spec called for. Version bumps are the publish-side ceremony's job, never autonomous-mode's.

### Step C3 — Main task commit

Stage only the files in the Builder-report union: `git add <file1> <file2> ...`. Avoid `git add -A` to keep the boundary explicit.

Commit with the standard format:

```
M<N> Task <NN>: <title> — autonomous-mode close-out (cycle <N>/10)

<one or two sentences naming what landed, citing the KDR(s) the
task implements>

Cycles run: <N>
Auditor verdict: ✅ PASS
Security: SHIP (or "FIX-THEN-SHIP locked: <summary>" if bypass fired)
Sr. Dev: SHIP
Sr. SDET: SHIP
Architect: <if invoked: verdict + KDR-NNN if proposed>

Files touched:
- <list>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

### Step C4 — Push

Run `git push origin design_branch`. Capture the resulting hash.

If the push fails (e.g. non-fast-forward, auth issue), **HARD HALT** — do not retry, do not force, do not switch branches. Surface the error verbatim.

### Step C5 — Final report

End-of-task one-liner:

`AUTO-CLEAN — M<N> Task <NN> shipped: design_branch <hash>; <N> cycles; <KDR-NNN if proposed, else "no KDR proposed">`

If no KDR was proposed, only one commit lands. If KDR was proposed, two commits: KDR isolation first, then the task commit.

---

## Reporting

End-of-cycle one-liner for build → audit cycles:

`Cycle N/10 — [FUNCTIONALLY CLEAN | OPEN: <count> issues | BLOCKED: <issue-id> | USER INPUT: <issue-id>]`

End-of-security-gate one-liner:

`Security gate — [CLEAN | SEC-BLOCK: <count> | SEC-FIX: <count>]`

End-of-team-gate one-liner:

`Team gate — [CLEAN | TEAM-BLOCK: <reviewer:count> | TEAM-FIX: <reviewer:count> | TEAM-DIVERGE: <reviewer-A says X, reviewer-B says Y>]`

Final-stop summary (whether AUTO-CLEAN or HALT): stop condition triggered, total cycle count, remaining OPEN issues (id + one-liner), commit hash(es) if AUTO-CLEAN, the user action needed if HALT.

---

## Why team-gate runs after security-gate, not in parallel

The security-reviewer's threat-model check is narrower than sr-dev / sr-sdet's quality check; running them all in parallel would burn tokens redundantly when a security BLOCK already invalidates the run. Order matters: security-blockers are the hardest gate (re-loops to Builder), then quality-blockers, then quality-fixes. Each later gate only fires when its prerequisite passed.

## Why this is a separate command from /clean-implement

`/clean-implement` is the manual flow — user reviews each cycle, owns the commit. `/auto-implement` adds the team gate + commit ceremony + hard halt boundaries that only make sense when the user is delegating end-to-end. Keeping them separate means a user can still drive `/clean-implement` interactively without the autonomous-mode rules kicking in.

## Why architect is conditional in the team gate, not always-on

Architect runs when there's a question to answer — a new-KDR proposal, an external-claim verification, a queue-selection call. Running it on every clean task burns budget on a question that wasn't asked. The conditional trigger ("any reviewer flagged new-KDR-needed") concentrates architect's effort where it adds value.
