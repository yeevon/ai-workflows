# Task 06 — Debug Commands (NEW)

**Issues:** IMP-03, IMP-04, OPS-01, OPS-02

## What to Build

Three CLI commands for debugging and operations. All pure queries over existing SQLite state — no new infrastructure.

## Commands

### `aiw inspect <run_id> --task <task_id>` (IMP-04)

Show the full debugging context for one task:

```text
Run abc123 · task refactor_auth_service
Component: worker · tier: sonnet · status: failed
Duration: 2m 14s

Input:
  {
    "module_path": "src/auth/service.py",
    "goals": "Extract discount calculation"
  }

System prompt (rendered, cached):
  You are a refactoring assistant...
  [full text]

User prompt (rendered, per-call):
  Refactor the file at src/auth/service.py per these goals: Extract discount calculation...
  [full text]

Tool calls (3):
  1. read_file(path="src/auth/service.py") → 2415 chars
  2. grep(pattern="discount", path="src/") → 8 matches
  3. write_file(path="src/auth/service.py", content=...) → Written 2891 chars

LLM turns: 6
Output: (partial — incomplete at soft cap 15)
  [partial content]

Validator: structural (./gradlew build)
  Exit 1
  > OrderTest > shouldApplyDiscount FAILED

Failure reason:
  "Build failed: OrderTest.shouldApplyDiscount — NullPointerException at line 42"
```

Joins across `tasks`, `llm_calls`, `artifacts`, and validator output artifacts.

### `aiw rerun-task <run_id> <task_id> [--prompts <path>]` (IMP-03)

Replay a single task with current prompts against its checkpointed input:

```text
aiw rerun-task abc123 refactor_auth_service --prompts workflows/jvm_modernization/prompts/v2/

Replaying refactor_auth_service with prompts from .../v2/
Input loaded from runs/abc123/artifacts/refactor_auth_service.input.json

Tier: sonnet (unchanged)
New system prompt hash: 4e8f2a (was 91c4b3)

Running...
  [turn 1] read_file → ...
  [turn 2] ...
Output: (valid)
Validator: structural (./gradlew build) → Exit 0

Wrote replay as run: abc124 (linked to abc123 as rerun)
```

Creates a new `run_id` linked to the original via a `parent_run_id` column. The original is untouched. `aiw inspect` can diff outputs across reruns.

### `aiw gc --older-than 30d [--keep-artifacts]` (OPS-01)

Delete old run directories and/or database rows:

```text
aiw gc --older-than 30d --keep-artifacts

Would delete:
  12 SQLite run records (completed runs older than 30d)
  0 artifact directories (--keep-artifacts)

Proceed? [y/N] y
Deleted.
```

Without `--keep-artifacts`: also removes `~/.ai-workflows/runs/<run_id>/`.

### `aiw stats [--last 30d]` (OPS-02)

Multi-run observability:

```text
aiw stats --last 30d

Total runs: 47 (42 completed, 5 failed)
Total cost: $12.47
Mean cost per run: $0.27

By workflow:
  test_coverage_gap_fill   34 runs   $4.12   avg $0.12   pass 97%
  jvm_modernization         8 runs   $7.23   avg $0.90   pass 88%
  slice_refactor            5 runs   $1.12   avg $0.22   pass 100%

By tier (of total cost):
  opus      $4.31 (35%)
  sonnet    $6.98 (56%)
  haiku     $1.18  (9%)
  local     $0.00  (0%)

Most expensive run: abc123 (jvm_modernization, $2.47) on 2026-04-03
```

## Schema Additions

Add `parent_run_id` column to `runs` for rerun tracking:

```sql
-- migrations/003_rerun_tracking.sql
ALTER TABLE runs ADD COLUMN parent_run_id TEXT REFERENCES runs(run_id);
ALTER TABLE runs ADD COLUMN rerun_reason TEXT;
```

## Acceptance Criteria

- [ ] `aiw inspect abc123 --task xyz` shows prompt, tool calls, output, validator result
- [ ] `aiw rerun-task` loads input from artifact, creates a new linked run, records `parent_run_id`
- [ ] `aiw rerun-task --prompts` uses the alternate prompt directory
- [ ] `aiw gc --older-than 30d` finds correct rows; `--keep-artifacts` preserves files
- [ ] `aiw stats --last 30d` returns correct aggregates (test with seeded data)

## Dependencies

- Task 01 (loader)
- Task 02 (aiw run)
- M1 Task 08 (storage)
