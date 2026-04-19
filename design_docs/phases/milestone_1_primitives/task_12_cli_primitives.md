# Task 12 — CLI Primitives Commands

**Issues:** CL-01, CL-02, CL-04, CL-05, CRIT-02

## What to Build

`aiw` CLI entry point. Commands that validate the storage + cost tracking layer work correctly. `aiw run` is a stub at this milestone; full implementation in M3.

## Deliverables

### `ai_workflows/cli.py`

```python
import typer
app = typer.Typer()
```

### `aiw list-runs`

```text
RUN ID    WORKFLOW                STATUS     COST      STARTED
abc123    test_coverage_gap_fill  completed  $0.42     2026-04-17 10:32
def456    jvm_modernization       failed     $1.17     2026-04-17 09:15
```

- Reads from `SQLiteStorage.list_runs()`
- Cost excludes local model calls
- Truncate workflow name to 22 chars

### `aiw inspect <run_id>`

```text
Run: abc123
Workflow: test_coverage_gap_fill
Dir hash: 8f3a2c...  (current match: OK / MISMATCH)
Status: completed
Budget: $0.42 / $5.00 (8% used)
Started: 2026-04-17 10:32  Finished: 2026-04-17 10:47 (15m)

Tasks:
  explore_module_auth     completed   local_coder   $0.00
  plan_refactor           completed   opus          $0.31
  refactor_auth_service   completed   sonnet        $0.08
  validate_build          completed   structural    $0.00

LLM Calls: 12 total
Cost breakdown: opus=$0.31 sonnet=$0.08 haiku=$0.03
```

- Shows `workflow_dir_hash` and computes current hash to flag drift
- Shows budget vs actual spend
- Shows per-component breakdown

### `aiw resume <run_id>` (stub at M1, full impl in M4)

At M1, prints:

```text
Resume for run abc123
Workflow: test_coverage_gap_fill
Status: completed
Tasks that would re-run: (none — already complete)
Workflow hash: match

Full resume available in Milestone 4.
```

The stub exists so the command is discoverable and the SQLite queries are validated.

### `aiw run <workflow>` (stub at M1)

```text
Not yet implemented — coming in Milestone 3.
```

Accepts `--profile` flag for forward compatibility.

### Global Options

- `--log-level INFO|DEBUG|WARNING|ERROR` — passed to `configure_logging()`
- `--db-path` — override default `~/.ai-workflows/runs.db` (for tests)

## Acceptance Criteria

- [ ] `aiw list-runs` renders correctly with seeded test data
- [ ] `aiw inspect <id>` shows cost breakdown
- [ ] `aiw inspect <id>` flags `workflow_dir_hash` mismatch if the directory has changed
- [ ] `aiw inspect <nonexistent>` exits 1 with clear "not found" message
- [ ] `aiw resume <id>` prints placeholder without error
- [ ] `aiw --help` lists all commands
- [ ] `--log-level DEBUG` produces human-readable console output

## Dependencies

- Task 08 (storage)
- Task 09 (cost tracker)
- Task 11 (logging)

## Carry-over from prior audits

Forward-deferred items owned by this task. Treat each entry like an
additional acceptance criterion and tick it when the corresponding test or
change lands.

- [ ] **M1-T04-ISS-01** — Complete Task 04's AC-5 by surfacing
  `cache_read_tokens` and `cache_write_tokens` from `TokenUsage` in the
  `aiw inspect <run_id>` renderer. Task 04 verified the fields flow from
  pydantic-ai's `RunUsage` → our `TokenUsage` → the cost tracker; this
  task is where they become operationally visible. Add the two fields to
  the per-call usage table, and a CLI-level test that shells
  `aiw inspect <run_id>` and greps for `cache_read`.
  Source: [issues/task_04_issue.md](issues/task_04_issue.md) — LOW.
