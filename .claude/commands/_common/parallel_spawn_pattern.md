# Parallel spawn with fragment files — canonical pattern reference

**Task:** M20 Task 05 — Parallel unified terminal gate.
**Relationship:** Referenced by `/auto-implement` (§Unified terminal gate) and any future
command that fans out to multiple independent sub-agents in a single orchestrator turn.

---

## When to apply this pattern

Use this pattern when **all four conditions hold** (per research brief §Lens 1.4):

1. ≥ 3 independent tasks that produce non-overlapping artefacts.
2. No shared state — agents do not depend on each other's output.
3. Clear non-overlapping file boundaries — each agent writes to a distinct path.
4. Independent verification — each agent's conclusion stands alone.

**Do not apply** when agents need to see each other's output (use sequential spawns) or
when the total spawns would exceed ~7 concurrently (Claude Code's practical sub-agent
concurrency cap per research brief §Lens 1.4).

---

## Mechanism — fragment files

Each parallel agent writes its output to a deterministic fragment path rather than
editing a shared file directly. This eliminates file-write contention for Edit operations
on shared files (e.g. the task issue file).

**Fragment path convention** (matches T03's `runs/<task>/cycle_<N>/` directory layout
per audit M11 and `m<MM>_t<NN>` shorthand per audit M12):

```
runs/<task>/cycle_<N>/<agent>-review.md
```

Example for the terminal gate:

| Agent | Fragment path |
|---|---|
| sr-dev | `runs/<task>/cycle_<N>/sr-dev-review.md` |
| sr-sdet | `runs/<task>/cycle_<N>/sr-sdet-review.md` |
| security-reviewer | `runs/<task>/cycle_<N>/security-review.md` |

---

## Orchestrator procedure (three-step)

### Step 1 — Single-turn parallel spawn

In **one assistant turn**, issue multiple `Task` tool calls (one per agent). Do not
issue them in separate turns — a separate turn breaks the "single multi-Task message"
guarantee that allows the Claude Code runtime to schedule them concurrently.

```
Turn N (orchestrator):
  Task(agent=sr-dev,       prompt=<sr-dev spawn prompt>)
  Task(agent=sr-sdet,      prompt=<sr-sdet spawn prompt>)
  Task(agent=security-reviewer, prompt=<security spawn prompt>)
  [no other content in this turn]
```

Wait for all three Tasks to complete before proceeding.

### Step 2 — Read all fragments in one multi-Read pass

In the follow-up turn, read all fragment files in one multi-Read call (multiple `Read`
invocations in a single assistant turn):

```
Turn N+1 (orchestrator):
  Read(runs/<task>/cycle_<N>/sr-dev-review.md)
  Read(runs/<task>/cycle_<N>/sr-sdet-review.md)
  Read(runs/<task>/cycle_<N>/security-review.md)
```

Parse each agent's T01 return-schema verdict line (`verdict: SHIP | FIX-THEN-SHIP | BLOCK`).

### Step 3 — Single-Edit stitch into the shared file

After evaluating verdicts (and only when the combined verdict is TERMINAL CLEAN), stitch
all fragment content into the shared file in **one Edit pass**. One Edit call appending
all three sections at once avoids the race condition where interleaved Edit calls
clobber sections mid-write.

---

## Precedence rule for the terminal gate

After parsing all three verdicts:

| Combination | Stop condition | Action |
|---|---|---|
| All three SHIP | TERMINAL CLEAN | Stitch fragments; proceed to dependency-auditor (conditional) + commit ceremony |
| Any BLOCK | TERMINAL BLOCK | Halt loop; surface security-reviewer BLOCK first if applicable, else the offending reviewer's BLOCK verbatim |
| Any FIX-THEN-SHIP (no BLOCK) | TERMINAL FIX | Halt; surface all FIX findings for user arbitration (or apply Auditor-agreement bypass if single-clear-recommendation) |

**Security-reviewer BLOCK precedence:** when security-reviewer returns BLOCK and
sr-dev / sr-sdet return SHIP, the orchestrator surfaces the security finding first
because it is the most user-load-bearing (threat-model implications). The TERMINAL BLOCK
condition fires regardless of which reviewer returned it — the security precedence rule
only governs which BLOCK finding is surfaced first.

---

## Conditional spawns — keep out of the parallel batch

Some agents have conditional trigger conditions that don't fit the unconditional 3-way
pattern. Keep these **sequential and post-parallel-batch**:

- **dependency-auditor** — runs only when `pyproject.toml` or `uv.lock` changed.
  Spawn synchronously after the parallel batch returns. dependency-auditor BLOCK has
  the same precedence weight as security-reviewer BLOCK.
- **architect** — runs only on Trigger A (new-KDR finding) or Trigger B (external-claim
  reconciliation). On-demand, not per-cycle. Not in the parallel batch.

---

## Fragment-file naming contract

The fragment file's content is the full `## <Name> review` section — identical to
what the agent previously wrote directly to the issue file. Only the destination changes
(fragment file vs issue file directly). The section heading is the agent's T01 `section:`
return value; the orchestrator uses it as the Edit target when stitching.

---

## Adoption checklist for future commands

When adopting this pattern for a new command (e.g. a future `/sweep` command in M21):

1. Verify all four parallelism conditions hold.
2. Define a fragment path per agent under `runs/<run-id>/<agent>-review.md`.
3. Update each agent's `## Output format` to write to the fragment path.
4. Update each agent's `## Return to invoker` so `file:` points at the fragment path
   and `section:` names the heading the orchestrator will stitch under.
5. Add the parallel-spawn step + read-fragments step + stitch step to the command.
6. Write hermetic tests covering: single-turn spawn assertion, fragment landing,
   single-Edit stitch, and precedence rule correctness.
