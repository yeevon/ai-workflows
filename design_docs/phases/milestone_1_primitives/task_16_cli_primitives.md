# Task 16 — CLI: Primitives Commands

**Issues:** CL-01, CL-02, CL-04, CL-05

## What to Build

The `aiw` CLI entry point and the commands that validate the storage + cost tracking layer work correctly. `aiw run` is a stub at this milestone — full implementation comes in Milestone 3.

## Deliverables

### `ai_workflows/cli.py`

```python
import typer
app = typer.Typer()
```

**`aiw list-runs`**
```
RUN ID          WORKFLOW              STATUS     COST      STARTED
abc123          test_coverage_gap_fill completed  $0.42     2026-04-17 10:32
def456          jvm_modernization     failed     $1.17     2026-04-17 09:15
```
- Reads from `SQLiteStorage.list_runs()`
- Shows: run_id (short), workflow_id, status, total cost (excluding local), started_at

**`aiw inspect <run_id>`**
```
Run: abc123
Workflow: test_coverage_gap_fill
Status: completed
Total cost: $0.42
Started: 2026-04-17 10:32  Finished: 2026-04-17 10:47 (15m)

Tasks:
  explore_module_auth      completed   local_coder   $0.00
  plan_refactor            completed   opus          $0.31
  refactor_auth_service    completed   sonnet        $0.08
  validate_build           completed   structural    $0.00
  ...

LLM Calls: 12 total  |  Cost breakdown: opus=$0.31 sonnet=$0.08 haiku=$0.03
```

**`aiw resume <run_id>`**
- Reads checkpoint from SQLite
- Prints what will be skipped (completed tasks) and what will re-run
- Prompts `Resume? [y/N]` before proceeding
- Full resume logic wired in Milestone 4 — at this milestone, just prints the checkpoint state and exits cleanly

**`aiw run <workflow> [args]`**
- Stub: prints `"Not yet implemented — coming in Milestone 3"` and exits 0
- Accepts `--profile` flag (stores for later use)

**`--log-level` global option:** `aiw --log-level DEBUG list-runs` passes level to `configure_logging()`.

## Acceptance Criteria

- [ ] `aiw list-runs` shows correct data from SQLite (seed a test run in the DB to verify)
- [ ] `aiw inspect <run_id>` shows task breakdown and cost by component
- [ ] `aiw inspect <nonexistent>` shows a clear "Run not found" message, exits 1
- [ ] `aiw resume <run_id>` shows checkpoint state without erroring
- [ ] `aiw --help` shows all commands with descriptions

## Dependencies

- Task 12 (storage)
- Task 13 (cost tracker)
- Task 15 (logging)
