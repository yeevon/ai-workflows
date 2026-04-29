Two-prompt long-running pattern for multi-cycle Builder runs (M21 Task 26).
Supplements the T03 cycle-summary pattern with a per-task immutable plan + cumulative progress file.
Owned by the orchestrator (plan seeded at cycle 1) and Auditor (progress appended each cycle).

## Trigger

The pattern fires when **either** of these is true at the start of cycle N:

1. The task spec explicitly opts in (`**Long-running:** yes` line under the spec header).
2. `N >= 3` (third Builder cycle on the same task).

For N < 3 and no opt-in, the existing T03 cycle-summary pattern is the only carry-forward
and the pattern stays dormant.

## File shape

When the trigger fires, two files live under `runs/<task-shorthand>/`:

- **`plan.md`** — written **once** at cycle 1 start (or first time the trigger fires).
  Immutable thereafter. Contains: task goal in one paragraph; ordered list of milestones /
  deliverables; explicit out-of-scope items copied from the spec; locked decisions known at
  task start. Sourced from the spec; no new scope.
- **`progress.md`** — updated at the end of **every** Builder cycle by the Auditor.
  Append-only, sectioned by cycle: `## Cycle <N> (YYYY-MM-DD)` with: what landed (file list
  with one-line descriptions), what is deferred to next cycle, locked decisions made this cycle,
  blockers (if any).

These supplement (not replace) the per-cycle `runs/<task>/cycle_<N>/summary.md` files.
The `cycle_<N>/summary.md` is the per-cycle snapshot the orchestrator carries to Builder
cycle N+1 per the existing T03 read-only-latest-summary rule. The progress file is the
cumulative surface that survives across cycles alongside the plan file.

## Builder cycle-N spawn changes

When the trigger is on, replace the cycle N>=2 read-only-latest-summary rule with:

- Pass `plan.md` (full content, immutable) + `progress.md` (full content, monotonic).
- Drop the prior cycle's `summary.md` from the Builder's pre-load (it becomes implicit in
  `progress.md`'s most recent `## Cycle <N>` section).

The Auditor continues to emit `cycle_<N>/summary.md` per the existing T03 cycle-summary rule;
that file remains the per-cycle artifact for telemetry and audit trail.

The Builder's 3-line return-text schema is unchanged when the trigger is on.
`progress.md` is owned by the Auditor (Phase 5b extension), not the Builder.

## Initializer step

The orchestrator (in `auto-implement.md`'s project-setup step) checks the trigger. If on:

1. Read the task spec.
2. Write `runs/<task>/plan.md` — extracted from spec `## Why this task exists` +
   `## What to Build` (high level) + `## Out of scope` + `## Acceptance criteria`. No invented scope.
3. Seed `runs/<task>/progress.md` with heading `# Progress — <task>` and an empty
   `## Cycle 1` section the Auditor will populate after the first cycle.

This is a one-shot at first trigger fire (cycle 1 for opt-in tasks; cycle 3 for auto-trigger),
inline orchestrator step — not a separate agent spawn.

## Reference Builder loop

Hypothetical T17 (spec-format extension) worked example, 4+ cycles:

**Cycle 1:** orchestrator writes `plan.md` (goal: add per-slice scope to task specs; out-of-scope:
parallel-Builder execution). Seeds `progress.md`. Builder drafts the format extension. Auditor
writes `cycle_1/summary.md` + appends `## Cycle 1 (2026-05-01)` to `progress.md` listing the
schema diff and deferring the validator update to cycle 2.

**Cycle 2:** orchestrator passes `plan.md` + `progress.md` (cycle 1 section) instead of
`cycle_1/summary.md`. Builder sees the goal + what already landed + what is deferred. No
re-reading prior chat history. Auditor appends `## Cycle 2 (2026-05-02)` to `progress.md`.

**Cycle 3+:** same pattern. `plan.md` stays immutable; `progress.md` grows one section per cycle.
The Builder always has the full cumulative state in two short files rather than N-1 cycle summaries.
