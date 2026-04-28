---
model: claude-opus-4-7
thinking:
  type: adaptive
effort: high
# Per-role effort assignment: see .claude/commands/_common/effort_table.md
---

# /autopilot

You are the **Autonomous Queue-Drain orchestrator** for: $ARGUMENTS

`$ARGUMENTS` is optional. If empty, drain the entire open queue. If a milestone-list shorthand (e.g. "m12 m13") is given, scope the drain to those milestones only.

This command is the meta-loop on top of `/queue-pick`, `/clean-tasks`, and `/auto-implement`. It loops over (queue-pick → clean-tasks-if-needed → auto-implement) until the queue drains, the user-supplied scope is exhausted, or a halt fires. **It does not chain via the `Skill` tool** (Skill chaining returns after one call, breaking the outer loop — see memory: `feedback_skill_chaining_reuse.md`); instead, the orchestrator reads `.claude/commands/auto-implement.md` and `.claude/commands/clean-tasks.md` and executes their procedures inline as part of this single conversation.

**This is the autonomy command.** It auto-commits + auto-pushes `design_branch`, runs every team gate, and only stops on halt boundaries or queue exhaustion. Use `/queue-pick` for the manual one-shot version.

---

## Agent-return parser convention

After every `Task` spawn, parse the agent's return per
[`.claude/commands/_common/agent_return_schema.md`](_common/agent_return_schema.md):

1. Capture the full text return to `runs/autopilot-<run-timestamp>-iter<N>/agent_<name>_raw_return.txt`.
2. Split on `\n`; expect exactly 3 non-empty lines.
3. Each line must match `^(verdict|file|section): ?(.+)$`.
4. The `verdict` value must be one of the agent's allowed tokens (see schema reference); trailing whitespace on any value is stripped before validation.
5. On any failure: halt, surface `BLOCKED: agent <name> returned non-conformant text —
   see the raw return file`. **Do not auto-retry.**

---

## Spawn-prompt scope discipline

**Reference:** [`.claude/commands/_common/spawn_prompt_template.md`](_common/spawn_prompt_template.md)

Pass only what each agent will certainly use. Let agents pull the rest on demand via their
own `Read` tool. Full-document content inlining is wasteful; path references are always safe.

After every `Task` spawn, capture the spawn-prompt token count (regex proxy:
`len(re.findall(r"\S+", text)) * 1.3`, truncated to int) into the appropriate path:
- For roadmap-selector: `runs/autopilot-<ts>-iter<N>/spawn_roadmap-selector.tokens.txt`
- For task-analyzer: `runs/<milestone>/round_<N>/spawn_task-analyzer.tokens.txt`
- For all per-task agents: `runs/<task>/cycle_<N>/spawn_<agent>.tokens.txt`

### Per-agent rules (summary — full details in spawn_prompt_template.md)

| Agent | Minimal pre-load | Remove |
|---|---|---|
| Builder | spec path, issue path, milestone README path, context brief | sibling issues, architecture.md content, CHANGELOG content |
| Auditor | spec path, issue path, milestone README path, context brief, `git diff`, cited KDR IDs | architecture.md content, sibling issue content, milestone README content |
| Reviewers (sr-dev, sr-sdet, security-reviewer, dependency-auditor) | spec path, issue path, context brief, `git diff`, files-touched list | full source files, full test files, architecture.md content |
| architect | recommendation file path, issue path, context brief, KDR identifiers | full source files, full architecture.md content — see spawn_prompt_template.md §architect |
| roadmap-selector | recommendation file path, context brief, milestone scope | full milestone README content, full spec content |
| task-analyzer | milestone dir path, analysis file path, context brief, round number, spec filenames list | full spec content, architecture.md, sibling milestone READMEs |

Output budget directives (include verbatim in each spawn prompt — substitute `<BUDGET>`):

```
Output budget: <BUDGET> tokens. Durable findings live in the file you write;
the return is the 3-line schema only — see .claude/commands/_common/agent_return_schema.md
```

Budgets: Builder = 4K; all other agents = 1–2K.

---

## Hard halt boundaries (autonomous-mode non-negotiables)

Same as `/auto-implement`'s set, restated so this orchestrator is self-contained. Memory: `feedback_autonomous_mode_boundaries.md`.

1. **Push boundary — `design_branch` ONLY.** Auto-`git commit` and auto-`git push origin design_branch` are allowed. **HARD HALT** on:
   - any merge to `main` / any `git push origin main` / any rebase rewriting `main` history
   - any `uv publish` invocation
   - any `pyproject.toml` `version` bump beyond what a task spec calls for
2. **No subagent runs git mutations or publish.** The orchestrator is the only surface that performs `git commit` / `git push` / `git tag` / `uv publish`. Every subagent prompt forbids these. **A subagent report claiming to have run one of these = HARD HALT** (rogue behaviour, surface for user investigation).
3. **KDR additions land on isolated commits.** When the architect proposes a new KDR, that change commits separately from the task code change.
4. **Sub-agent disagreement = halt.** When the team's verdicts split (one BLOCK, one SHIP), do not auto-resolve. Halt + surface.
5. **Per-task halt = stop the outer loop.** If `/auto-implement` halts mid-task (cycle limit, BLOCKER, USER INPUT, security BLOCK, team disagreement), the outer loop stops. Do not skip the failing task and pick the next one — the user owns the decision to skip vs. retry.

If at any point the loop attempts to invoke a halted operation, abort the iteration and report the boundary that fired.

---

## Pre-flight (run once, before iteration 1)

**Important — avoid shell expansion in pre-flight Bash calls.** Claude Code's `Contains expansion` and `Contains simple_expansion` guards prompt the user on any single Bash call that uses `$(...)`, `${VAR:-default}`, or `$VAR` inside a loop body. Each pre-flight step below is a **separate** Bash invocation; the orchestrator assembles the resulting strings in its own thinking, never via shell substitution.

1. **Sandbox check.** Run `printenv AIW_AUTONOMY_SANDBOX` (no expansion). Output is `1` inside the sandbox or empty/error on the host. **HARD HALT** if not `1` — autonomous mode does not run on the host. The fix is `make shell` and re-invoke after `claude /login`.
2. **Branch check.** Run `git rev-parse --abbrev-ref HEAD` (no expansion). Output is `design_branch`. HARD HALT otherwise.
3. **Working tree check.** Run `git status --short` (no expansion). Output is empty. HARD HALT on a dirty tree.
4. **Memory path computation.** Run `pwd` (no expansion) and capture the working-directory path. Then in your own thinking, replace every `/` with `-` and substitute into the form `$HOME/.claude/projects/<encoded-path>/memory/MEMORY.md` (`$HOME` is the invoking user's home; resolve via a separate `printenv HOME` call if needed). Run `ls -la <fully-resolved-path>` (literal path; no expansion) to verify the file exists. HARD HALT if missing — the orchestrator was invoked from an unfamiliar directory.
5. **Resolve milestone scope** from `$ARGUMENTS` (empty = all open; otherwise the supplied list).

Surface every pre-flight failure verbatim and halt before iteration 1.

---

## Outer loop — drain the queue

For iteration `N` from 1 upward (no hard cap; halt on the boundaries above or queue-exhaust below):

### Step A — Roadmap selection (queue-pick logic, inlined)

#### Read-only-latest-shipped rule (iteration N ≥ 2)

On iteration 1, spawn the `roadmap-selector` with only the project context brief and the
recommendation-file path (no prior iteration artifact exists yet).

On iteration N ≥ 2, spawn the `roadmap-selector` with:
- The project context brief.
- The recommendation-file path.
- The content of the most recent iter-shipped artifact
  (`runs/autopilot-<run-timestamp>-iter<N-1>-shipped.md`) for context on what the prior
  iteration delivered.
- **Do NOT** carry prior iteration chat history into this spawn. Prior iterations'
  dialogue is compacted into the iter-shipped artifact at Step D; chat replay is dropped.

This is the cross-task analogue of the in-task read-only-latest-summary rule (T03).

1. Build the **project context brief** for `roadmap-selector`:
   ```text
   Project: ai-workflows (Python, MIT, published as jmdl-ai-workflows on PyPI)
   Memory path: <MEMORY_PATH from pre-flight>
   Architecture: design_docs/architecture.md (especially §9 KDRs)
   Roadmap: design_docs/roadmap.md
   Deferred-ideas file: design_docs/nice_to_have.md (out-of-scope by default)
   Milestone scope: <from $ARGUMENTS, or "all open">
   ```
2. Recommendation file path: `runs/autopilot-<run-timestamp>-iter<N>.md` (under the gitignored `runs/` directory).
3. Spawn the `roadmap-selector` subagent via `Task` with: the recommendation-file path,
   the project context brief, the milestone list, and (on N ≥ 2) the most recent
   iter-shipped artifact content per the read-only-latest-shipped rule above. Wait for completion.
4. **Read the recommendation file on disk.** Verdict line is the source of truth. Empty / missing / no-`Verdict:`-line → treat as `HALT-AND-ASK` with the surface "agent halted before producing output" (per `/queue-pick` Step 2's pre-condition rule).

Branch on verdict:

- **PROCEED** with `<task>` → go to Step B.
- **NEEDS-CLEAN-TASKS** with `<milestone>` → go to Step C.
- **HALT-AND-ASK** → surface verbatim, halt the outer loop.

### Step B — Drive the task (auto-implement procedure, inlined)

**Read `.claude/commands/auto-implement.md` and execute its full procedure inline against the recommended task.** That file is the authoritative procedure; do not paraphrase it. Execute every step in order:

- Pre-flight (already covered by this orchestrator's pre-flight; skip the duplicates if state still holds).
- Project setup with the resolved task ID.
- Functional loop (1..10 Builder → Auditor cycles).
- Stop-condition evaluation each cycle (BLOCKER / USER INPUT / FUNCTIONALLY CLEAN / CYCLE LIMIT). Auditor-agreement bypass applies — single clear recommendation + orchestrator concurs against KDRs/spec → stamp locked decision and re-loop instead of halting.
- Security gate (security-reviewer + dependency-auditor conditional).
- Team gate (sr-dev + sr-sdet, plus architect conditional on new-KDR finding).
- Commit ceremony (KDR isolation if applicable + main task commit + push `design_branch`).

**On `AUTO-CLEAN`:** record the task in the run log (see Step E reporting), then return to Step A (next iteration). The working tree is clean again — the next iteration's pre-flight is implicitly satisfied for the clean-tree check.

**On any halt** (cycle limit, BLOCKER, USER INPUT, security BLOCK, security FIX-THEN-SHIP without bypass match, team BLOCK, team divergence, KDR conflict): halt the outer loop with that procedure's halt surface verbatim. Do not skip the task and pick the next one.

### Step C — Harden the milestone's specs (clean-tasks procedure, inlined)

**Read `.claude/commands/clean-tasks.md` and execute its full procedure inline against the recommended milestone.** Execute every step in order:

- Project setup (re-use the memory path + project context brief; substitute the milestone-specific paths).
- Phase 1 — Generate task specs from the README if missing. Skip if any `task_*.md` exists.
- Phase 2 — Spawn `task-analyzer`, read `task_analysis.md`, evaluate stop conditions (CLEAN / LOW-ONLY / OPEN / STOP-AND-ASK / CYCLE LIMIT), apply HIGH+MEDIUM fixes inline, re-loop. Up to 5 rounds.
- Phase 3 — Push LOWs to spec carry-over (only on LOW-ONLY).

**On `CLEAN` or `LOW-ONLY`:** the milestone's specs are now hardened; record the milestone in the run log, then return to Step A (re-spawn `roadmap-selector` — the milestone is now eligible for Step B's auto-implement path).

**On any halt** (GENERATION-BLOCKED, STOP-AND-ASK, CYCLE LIMIT without convergence, FIX-APPLICATION-BLOCKED): halt the outer loop with the surface verbatim.

### Step D — Iteration boundary

After Step B's `AUTO-CLEAN` or Step C's `CLEAN`/`LOW-ONLY`:

1. Re-verify the working tree is clean (`git status --short` empty). If dirty, that's a HARD HALT — Step B's commit ceremony or Step C's phase-3 push left state behind.
2. Re-verify branch is still `design_branch`. HARD HALT otherwise.
3. **Write the iter-shipped artifact** at `runs/autopilot-<run-timestamp>-iter<N>-shipped.md`.
   Populate from the iteration's outcome (recommendation file + commit log + per-cycle
   summaries from T03's `cycle_<M>/summary.md` files):

   ```markdown
   # Autopilot iter <N> — shipped

   **Run timestamp:** <YYYY-MM-DDTHHMMSSZ>
   **Iteration:** N
   **Date:** YYYY-MM-DD
   **Verdict from queue-pick:** <PROCEED | NEEDS-CLEAN-TASKS | HALT-AND-ASK>

   ## Task shipped (if PROCEED)
   - **Task:** <milestone>/<task spec filename>
   - **Cycles:** N
   - **Final commit:** <sha> on `design_branch`
   - **Files touched:** <list>
   - **Auditor verdict:** PASS
   - **Reviewer verdicts:** sr-dev=<verdict>, sr-sdet=<verdict>, security=<verdict>, dependency=<verdict>
   - **KDR additions (if any):** <KDR-XXX + ADR-NNNN, isolated commit sha>

   ## Milestone work (if NEEDS-CLEAN-TASKS)
   - **Milestone:** <milestone>
   - **/clean-tasks rounds:** N
   - **Final stop verdict:** <CLEAN | LOW-ONLY>
   - **Specs hardened:** <list of task spec filenames>

   ## Halt (if HALT-AND-ASK)
   - **Halt reason:** <one paragraph>
   - **State preserved:** <list of uncommitted files>
   - **User-arbitration question(s):** <bullet list>

   ## Carry-over to next iteration
   - *(empty for routine iterations; populated when a finding from this iteration affects the next task)*

   ## Telemetry summary
   - *(retrofitted by T22 when it lands; T04 ships before T22 in Phase A vs Phase C — leave this section empty at T04 land time, per audit M15)*
   ```

   The `-shipped.md` suffix distinguishes close-out from kick-off. Both files have
   read-only semantics after iteration close.

4. Increment `N`; return to Step A.

#### §Path convention

Each iteration produces two sibling files under the flat `runs/` directory:

```
runs/
  autopilot-20260427T152243Z-iter1.md            (kick-off recommendation file, queue-pick output)
  autopilot-20260427T152243Z-iter1-shipped.md    (close-out artifact, Step D)
  autopilot-20260427T152243Z-iter2.md
  autopilot-20260427T152243Z-iter2-shipped.md
  ...
```

Path naming convention: `runs/autopilot-<run-ts>-iter<N>(-shipped)?.md`
- `<run-ts>` is the pre-flight timestamp (e.g. `20260427T152243Z`).
- `-shipped.md` suffix marks the close-out artifact (Step D).
- No per-run subdirectory — flat layout matches today's autopilot.md convention.
- No migration of existing recommendation-file paths needed.

### Queue-exhaust condition

`Step A` returning `HALT-AND-ASK` with a "no eligible candidates after sequential walk" surface and an empty open-task list is the queue-drained signal. Report `QUEUE DRAINED` and exit cleanly. (Distinguish from a real `HALT-AND-ASK` where the user must arbitrate — same verdict, different reasoning.)

---

## Step E — Reporting

### Per-iteration one-liner

After each Step A/B/C completion, emit one line so the user can follow progress:

`Iter N — <PROCEED <task> → AUTO-CLEAN <hash> | NEEDS-CLEAN-TASKS <milestone> → LOW-ONLY (n LOWs) | HALT-AND-ASK: <one-liner>>`

### Final report

When the outer loop terminates (queue drained, halt fired, or scope exhausted), emit a structured summary:

```
/autopilot — <DRAINED | HALT: <reason> | SCOPE-EXHAUSTED>

Iterations run: N
Tasks shipped: <count>
  - <milestone/task> @ design_branch <hash>
  - ...
Milestones cleaned: <count>
  - <milestone> → <CLEAN | LOW-ONLY (n LOWs)>
  - ...
KDR additions: <count>
  - KDR-<NNN> "<name>" — design_branch <isolated commit hash>
Halt reason (if any): <single paragraph; verbatim from the failing step's halt surface>
Recommendation files: runs/autopilot-<run-timestamp>-iter*.md
```

The recommendation file paths are also surfaced so the user can re-read each iteration's full reasoning without replaying the run.

---

## Why /autopilot reads + executes inline instead of Skill-chaining

`Skill("/auto-implement")` returns control after one task completes — the outer loop never sees iteration 2. The project rule (memory: `feedback_skill_chaining_reuse.md`) is "composite commands that loop must inline the full procedure." Inlining a multi-hundred-line procedure into this file would create drift between `/autopilot.md`, `/auto-implement.md`, and `/clean-tasks.md`. The middle path: this orchestrator **reads the procedure files at runtime** and executes their steps inline. Reading a markdown file is not Skill chaining; the procedure files stay authoritative; this orchestrator stays compact.

If `/auto-implement.md` or `/clean-tasks.md` change incompatibly, `/autopilot` picks up the change automatically on the next run — no separate sync required.

## Why the outer loop halts on the first per-task failure

Skipping a failing task and continuing to the next one would silently lose work and surface a broken task only at the end of a long run. Halting at the first failure means the user sees the issue immediately, can decide whether to retry / fix / skip, and re-runs `/autopilot` with the same scope (the queue-pick walk is deterministic — already-shipped tasks are skipped because their `**Status:** ✅` line is set).

## Why the sandbox pre-flight check exists

`/auto-implement` and `/autopilot` both have destructive blast radius — they edit source code, run gates, commit, and push. Running them on the host bypasses the Docker boundary the user explicitly built. The `AIW_AUTONOMY_SANDBOX=1` env var is set in `docker-compose.yml` only; if the orchestrator sees an empty value, the user is on the host by accident. Halt early; the cost of `make shell` + re-invoke is much smaller than the cost of an uncontained autonomy run.
