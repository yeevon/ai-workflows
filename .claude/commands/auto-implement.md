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

## Agent-return parser convention

After every `Task` spawn, parse the agent's return per
[`.claude/commands/_common/agent_return_schema.md`](_common/agent_return_schema.md):

1. Capture the full text return to `runs/<task>/cycle_<N>/agent_<name>_raw_return.txt`.
2. Split on `\n`; expect exactly 3 non-empty lines.
3. Each line must match `^(verdict|file|section): ?(.+)$`.
4. The `verdict` value must be one of the agent's allowed tokens (see schema reference); trailing whitespace on any value is stripped before validation.
5. On any failure: halt, surface `BLOCKED: agent <name> returned non-conformant text —
   see runs/<task>/cycle_<N>/agent_<name>_raw_return.txt`. **Do not auto-retry.**

---

## Spawn-prompt scope discipline

**Reference:** [`.claude/commands/_common/spawn_prompt_template.md`](_common/spawn_prompt_template.md)

Pass only what each agent will certainly use. Let agents pull the rest on demand via their
own `Read` tool. Full-document content inlining is wasteful; path references are always safe.

After every `Task` spawn, capture the spawn-prompt token count (regex proxy:
`len(re.findall(r"\S+", text)) * 1.3`, truncated to int) into
`runs/<task>/cycle_<N>/spawn_<agent>.tokens.txt` (nested per-cycle directory; no `_<cycle>`
suffix on the filename).

### runs/<task>/ directory convention

Create `runs/<task-shorthand>/cycle_1/` at the **start of cycle 1**, before spawning the
first Builder.  Create `runs/<task-shorthand>/cycle_<N>/` at the start of each subsequent
cycle.  `<task-shorthand>` is `m<MM>_t<NN>` with both M and T zero-padded to two digits
(e.g. `m20_t03`, `m05_t02`, `m09_t01`).

Per-cycle directory layout (canonical — shared with T05, T08, T22):

```
runs/<task-shorthand>/
  cycle_1/
    summary.md                  ← T03 — cycle-summary (Auditor emits)
    sr-dev-review.md            ← T05 — reviewer fragment
    sr-sdet-review.md           ← T05 — reviewer fragment
    security-review.md          ← T05 — reviewer fragment
    builder.usage.json          ← T22 — telemetry
    auditor.usage.json          ← T22 — telemetry
    gate_pytest.txt             ← T08 — gate-output capture
    gate_lint-imports.txt       ← T08
    gate_ruff.txt               ← T08
    spawn_<agent>.tokens.txt    ← T02 — per-spawn token count
    agent_<name>_raw_return.txt ← T01 — full text return per agent
  cycle_2/
    ...
  cycle_N/
    ...
  integrity.txt                 ← T09 — pre-commit ceremony (top-level, latest run wins)
```

See [`.claude/commands/_common/cycle_summary_template.md`](_common/cycle_summary_template.md)
for the full `cycle_<N>/summary.md` template and the read-only-latest-summary rule.

### Builder spawn — read-only-latest-summary rule

**Cycle 1** — minimal pre-load set:
- Task spec path
- Issue file path (may not exist yet)
- Parent milestone README path
- Project context brief

**Cycle N (N ≥ 2)** — replace the parent milestone README with the latest cycle summary:
- Task spec path
- Issue file path
- **Most recent `runs/<task>/cycle_{N-1}/summary.md`** (include path + content inline)
- Project context brief

**Do not include** prior Builder reports' chat content, prior Auditor chat content, or
prior cycle summaries beyond `cycle_{N-1}/summary.md`.  The summary is the durable
carry-forward; earlier chat history is ephemeral and must not re-enter the spawn prompt.

**Remove from inline content (all cycles):** sibling task issue files, `architecture.md`
content, `CHANGELOG.md` content.

Output budget directive (include verbatim in the Builder spawn prompt):

```
Output budget: 4K tokens. Durable findings live in the file you write;
the return is the 3-line schema only — see .claude/commands/_common/agent_return_schema.md
```

### Auditor spawn — read-only-latest-summary rule

**Cycle 1** — minimal pre-load set:
- Task spec path
- Issue file path
- Parent milestone README path
- Project context brief
- Current `git diff`
- Cited KDR identifiers (parsed from the task spec — e.g. "KDR-003, KDR-013")

**Cycle N (N ≥ 2)** — add the latest cycle summary:
- Task spec path
- Issue file path
- Parent milestone README path
- Project context brief
- Current `git diff`
- Cited KDR identifiers (compact pointer)
- **Most recent `runs/<task>/cycle_{N-1}/summary.md`** (include path + content inline)

**Do not include** prior cycle summaries beyond the most recent one.  The summary is the
durable carry-forward; full prior-cycle chat history must not re-enter the spawn prompt.

**Remove from inline content (all cycles):** whole `architecture.md` content (Auditor reads
on-demand), sibling issue file content, whole-milestone-README content. Path references
stay; content inlining goes.

**KDR pre-load rule:** parse KDR citations from the task spec. Pass only those identifiers
as a compact list (e.g. "Relevant KDRs: KDR-003, KDR-013 — read §9 of architecture.md
on-demand for the full text"). When no KDRs are cited, pass the §9 grid header only.

Output budget directive (include verbatim in the Auditor spawn prompt):

```
Output budget: 1-2K tokens. Durable findings live in the issue file you write;
the return is the 3-line schema only — see .claude/commands/_common/agent_return_schema.md
```

### Reviewer spawns (sr-dev, sr-sdet, security-reviewer)

Minimal pre-load set: task spec path, issue file path, project context brief, current
`git diff`, list of files touched (aggregated from Builder reports across all cycles).

**Remove from inline content:** full source file content, full test file content,
`architecture.md` content.

Output budget directive (include verbatim in each reviewer spawn prompt):

```
Output budget: 1-2K tokens. Durable findings live in the issue file you append;
the return is the 3-line schema only — see .claude/commands/_common/agent_return_schema.md
```

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

## Pre-flight (before any agent spawn)

**Important — avoid shell expansion in pre-flight Bash calls.** Each step below is a separate Bash invocation; do not assemble status strings via `$(...)` substitution or `${VAR:-default}` in a single Bash call (Claude Code's `Contains expansion` guard prompts the user on those, breaking unattended autonomy).

1. **Sandbox check.** Run `printenv AIW_AUTONOMY_SANDBOX` (no expansion). Output is `1` inside the sandbox container or empty/error on the host. **HARD HALT** if not `1` — autonomous mode does not run on the host. The fix is `make shell` (or `docker compose run --rm aiw bash`) and re-invoke from inside the container after `claude /login`.
2. **Branch check.** Run `git rev-parse --abbrev-ref HEAD`. Output must be `design_branch`. HARD HALT otherwise — autonomous mode does not switch branches.
3. **Working tree check.** Run `git status --short`. Output must be empty. HARD HALT on a dirty tree — the loop would conflate prior changes with this task's diff at commit time.

If any pre-flight check fails, surface the failure verbatim and halt before spawning the first subagent.

---

## Project setup (run once at the start of cycle 1)

Resolve `$ARGUMENTS` to concrete paths:

- **Spec path:** `design_docs/phases/milestone_<M>_<name>/task_<NN>_<slug>.md`. Resolve shorthand by glob: "m16 t1" → `design_docs/phases/milestone_16_*/task_01_*.md`. If multiple matches, halt and ask.
- **Issue file path:** `design_docs/phases/milestone_<M>_<name>/issues/task_<NN>_issue.md`. May not exist on cycle 1.
- **Parent milestone README:** `design_docs/phases/milestone_<M>_<name>/README.md`.

(Branch + clean-tree checks already ran in the pre-flight section above.)

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
3. **FUNCTIONALLY CLEAN** — Issue file status line reads `✅ PASS` with no OPEN issues. Proceed to the **unified terminal gate** below.
4. **CYCLE LIMIT** — 10 build → audit cycles without 1–3. Halt, present outstanding issues. **Do not run the terminal gate against an unclean task.**

**At the start of cycle 1 only:** if the issue file already contains an unresolved BLOCKER from a prior session, treat as condition 1 immediately — don't spawn the Builder against an open blocker.

---

## Functional loop procedure

For cycles 1..10:

### Step 1 — Builder

Spawn the `builder` subagent via `Task` with the inputs prescribed by the
"Builder spawn — read-only-latest-summary rule" section above (cycle 1: include
parent milestone README path; cycle N ≥ 2: replace it with the latest cycle
summary content). Wait for completion. Capture the Builder's report.

### Step 2 — Auditor

Spawn the `auditor` subagent via `Task` with the inputs prescribed by the
"Auditor spawn — read-only-latest-summary rule" section above (cycle 1: standard
pre-load set; cycle N ≥ 2: add the latest cycle summary). Include cited KDR
identifiers (compact pointer per scope-discipline section above). Wait for completion.

### Step 3 — Read issue file and evaluate stop conditions

**Read the issue file on disk.** Do not trust the Auditor's chat summary — the issue file is the source of truth. Evaluate the four stop conditions in order against what's actually written. If condition 3 (FUNCTIONALLY CLEAN) triggers, go to the **unified terminal gate**. If none trigger and cycles remain, loop to Step 1 targeting only the OPEN issues the audit identified.

**Between Step 1 and Step 2, forbidden:**

- Summary of what the Builder did.
- Verdict on the gates ("gates pass, so the cycle is clean").
- Self-predicted cycle status.
- A "ready for audit" todo update.
- Editing the issue file yourself.

The Auditor is the only thing that can decide whether the task is functionally clean.

---

## Unified terminal gate (runs once, after FUNCTIONALLY CLEAN — parallel)

Replaces the prior two-gate Security+Team sequential flow. sr-dev, sr-sdet, and
security-reviewer run concurrently in a single orchestrator message (three Task tool
calls in one assistant turn). Each writes to a fragment file; the orchestrator
stitches the fragments into the issue file in a follow-up turn.

### Step G1 — Parallel spawn (three Task tool calls in one assistant turn)

Spawn sr-dev, sr-sdet, and security-reviewer concurrently in a single
orchestrator message (three Task tool calls in one assistant turn).

Each agent writes its review to `runs/<task>/cycle_<N>/<agent>-review.md`
per the agent's updated `## Output format`:
- sr-dev → `runs/<task>/cycle_<N>/sr-dev-review.md`
- sr-sdet → `runs/<task>/cycle_<N>/sr-sdet-review.md`
- security-reviewer → `runs/<task>/cycle_<N>/security-review.md`

Spawn inputs per scope discipline:
- sr-dev: task identifier, spec path, issue file path, project context brief, list of
  files touched across the whole task, the most recent Auditor verdict.
- sr-sdet: task identifier, spec path, issue file path, project context brief, list of
  test files touched across the whole task, the most recent Auditor verdict.
- security-reviewer: task identifier, spec path, issue file path, project context brief,
  list of files touched across the whole task, cited KDR identifiers (compact pointer).

Wait for all three Tasks to complete.

### Step G2 — Read fragments, parse verdicts, apply precedence rule

In a follow-up turn:

1. Read the three fragment files in one multi-Read call:
   `runs/<task>/cycle_<N>/sr-dev-review.md`,
   `runs/<task>/cycle_<N>/sr-sdet-review.md`,
   `runs/<task>/cycle_<N>/security-review.md`.
2. Parse each agent's T01 return-schema verdict line.
3. Apply the precedence rule:
   - **All three SHIP → TERMINAL CLEAN.** Proceed to stitch step (G3) then
     conditional spawns (G4, G5), then the commit ceremony.
   - **Any reviewer BLOCK → TERMINAL BLOCK.** Halt loop; surface the
     security-reviewer BLOCK first if applicable (threat-model finding is the
     most user-load-bearing), else the offending reviewer's BLOCK verbatim.
     Next action is another Builder → Auditor cycle targeting these findings.
   - **Any reviewer FIX-THEN-SHIP (no BLOCK) → TERMINAL FIX.** Apply the
     Auditor-agreement bypass: if all FIX findings carry single clear
     recommendations and you concur against KDRs + spec, stamp
     `Locked terminal decision (loop-controller + reviewer concur, YYYY-MM-DD): <summary>`
     per finding and re-loop with each as carry-over. Halt only on the same
     four conditions (multi-option, KDR conflict, scope expansion, deferral to
     nonexistent task).
4. If TERMINAL CLEAN: stitch the three fragment files into the issue file under
   `## Sr. Dev review`, `## Sr. SDET review`, `## Security review` sections in
   one Edit pass.

### Step G3 — Stitch fragments into issue file (TERMINAL CLEAN only)

Read all three fragment files (already done in G2 step 1). In one Edit pass,
append all three `## <Name> review` sections to the issue file in this order:
`## Sr. Dev review`, `## Sr. SDET review`, `## Security review`.

### Step G4 — Dependency auditor (conditional, synchronous, post-parallel-batch)

Run **only if** the aggregated diff across this task touched `pyproject.toml` or
`uv.lock`. Check by inspecting Builder reports for manifest edits.

If triggered, spawn `dependency-auditor` via `Task` (synchronous — after the
parallel batch returns and G3 stitch completes) with: task identifier, list of
dep-manifest files changed, project context brief, lockfile path. Output appends
under `## Dependency audit` in the issue file. Verdict line: `SHIP | FIX-THEN-SHIP | BLOCK`.

If triggered and verdict is BLOCK, surface it ahead of any FIX-THEN-SHIP from
the parallel batch — dependency-auditor BLOCK has the same precedence weight as
security-reviewer BLOCK (supply-chain-shaped threat).

If not triggered, note in the issue file: `Dependency audit: skipped — no manifest changes.`

### Step G5 — Architect (conditional, on-demand)

Spawn `architect` via `Task` **only if** any of the reviewers (auditor,
security-reviewer, dependency-auditor, sr-dev, sr-sdet) flagged a finding whose
recommendation reads "this should be a new KDR" or "violates an unwritten rule".
Pass: trigger=`new-KDR`, the finding ID, the project context brief.

Architect output appends under `## Architect review` in the issue file. Verdict
line: `ALIGNED / MISALIGNED / OPEN / PROPOSE-NEW-KDR`.

This is unchanged from the prior conditional spawn — architect is invoked
on-demand, not per-cycle.

### Step G6 — Final gate verdict

After G3 stitch (and G4 if triggered, and G5 if triggered), evaluate the final
terminal verdict in priority order:

1. **TERMINAL BLOCK** — Any reviewer (including dependency-auditor) returned
   BLOCK. Halt; surface security-reviewer BLOCK first if applicable. The task is
   **not** CLEAN. Next action is another Builder → Auditor cycle.
2. **TERMINAL FIX** — Any reviewer returned FIX-THEN-SHIP (no BLOCK). Apply
   Auditor-agreement bypass or halt for user arbitration.
3. **TERMINAL CLEAN** — All applicable reviewers returned SHIP. Proceed to the
   **commit ceremony**.

---

## Commit ceremony (runs once, after TERMINAL CLEAN — autonomous-mode only)

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
Terminal gate: CLEAN (Sr. Dev: SHIP, Sr. SDET: SHIP, Security: SHIP)
Dependency audit: <SHIP | skipped — no manifest changes>
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

End-of-terminal-gate one-liner:

`Terminal gate — [CLEAN | TERMINAL-BLOCK: <reviewer:count> | TERMINAL-FIX: <reviewer:count>]`

Final-stop summary (whether AUTO-CLEAN or HALT): stop condition triggered, total cycle count, remaining OPEN issues (id + one-liner), commit hash(es) if AUTO-CLEAN, the user action needed if HALT.

---

## Why the unified terminal gate parallelizes all three reviewers

sr-dev, sr-sdet, and security-reviewer each check non-overlapping concerns (code quality,
test quality, threat model) and write to non-overlapping fragment files — no shared-state
or file-write contention. Spawning all three concurrently reduces wall-clock time from
sum-of-three to max-of-three (target ≥ 2× improvement). When security-reviewer returns
BLOCK, the TERMINAL BLOCK precedence rule surfaces that finding first — the same
precedence that the old sequential flow achieved implicitly (by running security first)
is now made explicit in the combined verdict evaluation step (G2).

## Why this is a separate command from /clean-implement

`/clean-implement` is the manual flow — user reviews each cycle, owns the commit. `/auto-implement` adds the team gate + commit ceremony + hard halt boundaries that only make sense when the user is delegating end-to-end. Keeping them separate means a user can still drive `/clean-implement` interactively without the autonomous-mode rules kicking in.

## Why architect is conditional in the team gate, not always-on

Architect runs when there's a question to answer — a new-KDR proposal, an external-claim verification, a queue-selection call. Running it on every clean task burns budget on a question that wasn't asked. The conditional trigger ("any reviewer flagged new-KDR-needed") concentrates architect's effort where it adds value.
