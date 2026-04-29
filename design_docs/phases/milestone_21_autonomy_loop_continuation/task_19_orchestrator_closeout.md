# Task 19 — Orchestrator-owned close-out (post-parallel-Builder merge)

**Status:** ✅ Done.
**Kind:** Parallelism / code.
**Grounding:** [milestone README](README.md) · [T17 spec](task_17_spec_format_extension.md) · [T18 spec](task_18_parallel_builder_spawn.md) (prerequisite) · [`auto-implement.md`](../../../.claude/commands/auto-implement.md) §Commit ceremony · [research brief §T19](../milestone_20_autonomy_loop_optimization/research_analysis.md).

**⚠️ Stretch goal.** Explicitly defer to M22 if M21 scope grows beyond T17+T18. The README exit-criteria note: "T18 + T19 stretch — explicit `deferred to M22 if scope-bounded` line in M21 close-out."

## Why this task exists

After T18 launches parallel Builders, each slice produces a set of file changes in an isolated worktree. T18 handles the dispatch and overlap detection; T19 handles what comes after: merging all slice changes into the main working tree, running a single Auditor pass over the combined diff, and performing the commit ceremony (CHANGELOG update, status-surface flips, `git push`).

Without T19, the parallel-Builder flow lacks a defined close-out shape: the Auditor would see a per-slice diff only, and the commit ceremony might run N times instead of once. T19 makes the orchestrator own the merge-and-close step explicitly.

## What to Build

### Step 1 — Post-parallel merge in `/auto-implement`

Edit `.claude/commands/auto-implement.md` §Functional loop, post-Step-1 parallel-Builder path:

```
After all slice Builders return (and overlap check passes — T18 Step 3):
  1. Apply each worktree's changes to the main working tree in slice order.
     For each worktree that produced changes:
       git diff <worktree> | git apply --index   (or git cherry-pick approach)
     On apply failure: HARD HALT — merge conflict in post-parallel merge; resolve manually.
  2. The combined diff is now in the main working tree. Proceed to Step 2 (Auditor spawn)
     exactly as in the serial path. The Auditor sees the full combined diff.
  3. After FUNCTIONALLY CLEAN, the terminal gate runs as today (single pass, not per-slice).
```

### Step 2 — Commit ceremony for parallel-built tasks

Edit `.claude/commands/auto-implement.md` §Commit ceremony Step C3 to add:

> If the task was parallel-built (T18 path), the commit message body includes:
> ```
> Parallel-build: <N> slices dispatched (slice-A: <N> files; slice-B: <N> files; ...)
> ```
> Commit is still a single commit — no per-slice commits. The `Files touched:` list covers all slices.

### Step 3 — Status-surface flips after parallel merge

The existing status-surface discipline (CLAUDE.md non-negotiable) applies unchanged. The close-out flips the same four surfaces as serial builds:
- Per-task spec `**Status:**` line.
- Milestone README task table row.
- `tasks/README.md` row if the milestone has one.
- Milestone README "Done when" checkboxes.

T19 documents that these flips happen **once** after the combined-diff Auditor pass, not once-per-slice.

### Step 4 — Add `tests/test_t19_closeout.py`

4 test cases:
1. Post-parallel merge applies all worktree diffs to main working tree.
2. Commit message includes `Parallel-build:` annotation.
3. Status surfaces flip once (not N times).
4. HARD HALT on post-parallel merge conflict.

### Step 5 — Update `CHANGELOG.md`

Add `### Added — M21 Task 19: Orchestrator-owned close-out (post-parallel-Builder merge) (<YYYY-MM-DD>)` under `## [Unreleased]`.

## Deliverables

- Edit to `.claude/commands/auto-implement.md` — post-parallel merge step, commit ceremony annotation.
- `tests/test_t19_closeout.py` — new (4 test cases).
- `CHANGELOG.md` updated.

## Tests / smoke (Auditor runs)

```bash
# 1. auto-implement.md has post-parallel merge step.
grep -qiE 'post.parallel|parallel.merge|apply.*worktree' .claude/commands/auto-implement.md && echo "post-parallel merge OK"

# 2. Parallel-build commit annotation documented.
grep -qiE 'Parallel.build:|parallel.built' .claude/commands/auto-implement.md && echo "commit annotation OK"

# 3. Tests exist and pass.
test -f tests/test_t19_closeout.py && echo "test file exists"
uv run pytest tests/test_t19_closeout.py -q

# 4. Gates clean.
uv run lint-imports >/dev/null && echo "lint-imports green"
uv run ruff check >/dev/null && echo "ruff green"

# 5. CHANGELOG anchor.
grep -qE '^### (Added|Changed) — M21 Task 19:' CHANGELOG.md && echo "CHANGELOG anchor"
```

## Acceptance criteria

1. `.claude/commands/auto-implement.md` has post-parallel merge step and commit ceremony annotation. Smoke 1+2 pass.
2. `tests/test_t19_closeout.py` passes (4 test cases). Smoke 3 passes.
3. All CI gates green. Smoke 4 passes.
4. `CHANGELOG.md` updated. Smoke 5 passes.
5. Status surfaces flip together: (a) T19 spec `**Status:**` → `✅ Done`, (b) M21 README task-pool T19 row → `✅ Done`.

## Out of scope

- **Per-slice Auditor passes.** A single Auditor sees the combined diff.
- **Conflict resolution automation.** On merge conflict: HARD HALT; user resolves.
- **Runtime code changes in `ai_workflows/`.** Per M21 scope note.

## Dependencies

- **T17 Done** — format spec must exist.
- **T18 Done** — parallel dispatch must be in place.

## Defer-to-M22 condition (explicit)

If T18 was deferred to M22, T19 also defers. Same `nice_to_have.md` entry absorbs both.

## Carry-over from prior milestones

*None.*

## Carry-over from prior audits

*None.*

## Carry-over from task analysis

- [x] **TA-LOW-03 — Test 3 (status-surface single-flip) has no dedicated AC** (severity: LOW, source: task_analysis.md round 20)
      Test 3 asserts "Status surfaces flip once (not N times)" — AC-1 covers post-parallel merge and commit annotation, but the single-flip discipline is not explicitly named as an AC.
      **Recommendation:** Builder picks: add AC-2-bis "Status-surface single-flip discipline documented in §Step 3" OR fold test 3 assertion into AC-1 coverage. Document the choice in the issue file.
