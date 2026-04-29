# Task 18 — Worktree-coordinated parallel Builder spawn

**Status:** ✅ Done.
**Kind:** Parallelism / code.
**Grounding:** [milestone README](README.md) · [T17 spec](task_17_spec_format_extension.md) (prerequisite — per-slice scope format must exist) · [`auto-implement.md`](../../../.claude/commands/auto-implement.md) §Functional loop · Claude Code `isolation: worktree` frontmatter · [research brief §T17-T18](../milestone_20_autonomy_loop_optimization/research_analysis.md). KDR drift checks apply per M21 scope note.

**⚠️ Stretch goal.** Explicitly defer to M22 if M21 scope grows beyond T17. The README exit-criteria note: "T18 + T19 stretch — explicit `deferred to M22 if scope-bounded` line in M21 close-out." If T17 lands and M21 scope allows, proceed; otherwise record the M22 deferral in the ZZ close-out.

## Why this task exists

T17 lands the spec format. T18 uses it: when a spec has a `## Slice scope` section, the orchestrator can launch isolated Builder agents — each working in its own git worktree — in parallel. Serial-build time halves or better for multi-slice tasks. Each worktree is a clean copy, so builders can't accidentally clobber each other's edits.

Claude Code v2.1.49+ exposes `isolation: worktree` frontmatter on agent specs. The orchestrator calls the Agent tool with `isolation: "worktree"` to get an isolated working copy automatically. Concurrency is capped at 3–4 to avoid filesystem contention and token budget overruns.

## What to Build

### Step 1 — Parallel-Builder dispatch path in `/auto-implement`

Edit `.claude/commands/auto-implement.md` §Functional loop Step 1 (Builder spawn) to add a parallel dispatch branch:

```
If PARALLEL_ELIGIBLE=true (from runs/<task>/meta.json — written at project setup per T17):
  1. Read the spec's ## Slice scope table to enumerate slices.
  2. For each slice (up to 4 slices), spawn an isolated Builder Agent with:
     - isolation: "worktree"
     - Slice-specific scope: only the files/symbols listed for that slice
     - Same pre-load inputs as the serial Builder spawn rule (spec path, issue path,
       project context brief, latest cycle summary if N >= 2)
     - Extra constraint in prompt: "Work ONLY on the files listed in your slice scope:
       <slice-N files>. Do not touch files outside this list."
  3. Run all slice spawns in a single orchestrator turn (parallel Task calls).
  4. Wait for all slices to complete. Collect all Builder reports.
  5. Merge: git status across all worktrees to confirm no overlap in changed files.
     On overlap: HARD HALT — slice boundaries were incorrect; resolve manually.
  6. Cherry-pick or merge each worktree's changes into the main working tree
     (the Agent tool with isolation: worktree returns the worktree path in its result
     if changes were made; orchestrator applies them).

If PARALLEL_ELIGIBLE=false: run the existing serial Builder as today (no change).
```

### Step 2 — Concurrency cap

Document and enforce: if the spec has more than 4 slices, only the first 4 run in parallel. Slices 5+ run in the next cycle.

### Step 3 — Overlap detection

After all parallel Builders return, before the Auditor spawn:

```bash
git diff --name-only
```

Cross-check: if any file appears in multiple slices' Builder reports, surface:
```
🚧 BLOCKED: parallel-Builder overlap detected — <file> modified by slice-A and slice-B.
Review slice scope in spec ## Slice scope section.
```

### Step 4 — Update Builder spawn rate for telemetry

Edit telemetry calls in the parallel path to record `--agent builder-slice-<N>` so per-slice cost is tracked separately.

### Step 5 — Add `tests/test_t18_parallel_dispatch.py`

6 test cases:
1. `PARALLEL_ELIGIBLE=true` in meta.json triggers parallel path (mocked).
2. `PARALLEL_ELIGIBLE=false` takes serial path (no-op / regression guard).
3. Slice cap: spec with 5 slices only dispatches 4 in cycle 1.
4. Overlap detection: two slices claiming the same file triggers BLOCKED output.
5. Worktree cleanup: if Builder makes no changes, worktree is not left behind.
6. Telemetry records `builder-slice-<N>` naming for parallel invocations.

### Step 6 — Update `CHANGELOG.md`

Add `### Added — M21 Task 18: Worktree-coordinated parallel Builder spawn (<YYYY-MM-DD>)` under `## [Unreleased]`.

## Deliverables

- Edit to `.claude/commands/auto-implement.md` — parallel-Builder dispatch path in Step 1 (Builder spawn), concurrency cap, overlap detection.
- `tests/test_t18_parallel_dispatch.py` — new (6 test cases).
- Edit to M21 README §G4 prose: `(T18 parallel-Builder dispatch: landed / deferred to M22 — see ZZ close-out)`.
- `CHANGELOG.md` updated.

## Tests / smoke (Auditor runs)

```bash
# 1. auto-implement.md parallel dispatch path documented.
grep -qiE 'PARALLEL_ELIGIBLE|parallel.dispatch|isolation.*worktree' .claude/commands/auto-implement.md && echo "parallel dispatch OK"

# 2. Concurrency cap documented.
grep -qiE 'cap.*[34]|[34].*slice|concurren' .claude/commands/auto-implement.md && echo "concurrency cap OK"

# 3. Tests exist and pass.
test -f tests/test_t18_parallel_dispatch.py && echo "test file exists"
uv run pytest tests/test_t18_parallel_dispatch.py -q

# 4. Gates clean.
uv run lint-imports >/dev/null && echo "lint-imports green"
uv run ruff check >/dev/null && echo "ruff green"

# 5. CHANGELOG anchor.
grep -qE '^### (Added|Changed) — M21 Task 18:' CHANGELOG.md && echo "CHANGELOG anchor"
```

## Acceptance criteria

1. `.claude/commands/auto-implement.md` has parallel-Builder dispatch path: reads `PARALLEL_ELIGIBLE`, spawns slice-isolated Builders, cap at 4 slices, overlap detection. Smoke 1+2 pass.
2. `tests/test_t18_parallel_dispatch.py` passes (6 test cases). Smoke 3 passes.
3. All CI gates green. Smoke 4 passes.
4. `CHANGELOG.md` updated. Smoke 5 passes.
5. Status surfaces flip together: (a) T18 spec `**Status:**` → `✅ Done`, (b) M21 README task-pool T18 row → `✅ Done`.

## Out of scope

- **Orchestrator close-out after parallel merge** — T19.
- **Auditor parallelization.** Each slice's output goes to a single Auditor (serial), same as today.
- **Runtime code changes in `ai_workflows/`.** Per M21 scope note.
- **More than 4 concurrent workers** — explicit cap.

## Dependencies

- **T17 Done** — `## Slice scope` format + `PARALLEL_ELIGIBLE` meta.json must exist.
- **Blocks T19** — T19 orchestrator close-out is the post-parallel-merge step.

## Defer-to-M22 condition (explicit)

If M21 scope at ZZ close-out time shows T18 was not implemented: ZZ records `T18 deferred to M22 — trigger: T17 adopted on ≥ 5 tasks AND operator requests parallel dispatch`. The `nice_to_have.md` entry for multi-orchestrator parallelism absorbs T18+T19 if deferred.

## Carry-over from prior milestones

*None.*

## Carry-over from prior audits

*None.*

## Carry-over from task analysis

- [ ] **TA-LOW-02 — Worktree cleanup procedure step missing in Step 1** (severity: LOW, source: task_analysis.md round 20)
      Step 1 documents dispatch + overlap detection + cherry-pick but does not describe worktree cleanup when a slice produces no changes (test case 5 asserts this).
      **Recommendation:** Builder: add explicit `git worktree remove <path>` step under Step 1 for the empty-diff case to satisfy AC-5 / test 5.
