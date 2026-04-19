# Task 12 — CLI Primitives Commands

**Status:** ✅ Complete (2026-04-19)

**Issues:** CL-01, CL-02, CL-04, CL-05, CRIT-02 (resolves carry-overs M1-T04-ISS-01, M1-T09-ISS-02)

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

- [x] `aiw list-runs` renders correctly with seeded test data
  — pinned by `tests/test_cli.py::test_list_runs_renders_seeded_runs`,
  `::test_list_runs_truncates_long_workflow_names`,
  `::test_list_runs_with_empty_db_prints_header_and_message`.
- [x] `aiw inspect <id>` shows cost breakdown
  — pinned by `::test_inspect_shows_cost_breakdown` (per-component
  aggregate excluding local calls) and
  `::test_inspect_shows_per_task_breakdown` (per-task column).
- [x] `aiw inspect <id>` flags `workflow_dir_hash` mismatch if the
  directory has changed
  — pinned by `::test_inspect_flags_mismatch_when_directory_changed`,
  which seeds a workflow dir, hashes it, drifts it, and asserts the
  `current match: OK` → `current match: MISMATCH` flip. Implementation
  accepts an optional `--workflow-dir` flag because `runs` stores the
  hash only, not the path.
- [x] `aiw inspect <nonexistent>` exits 1 with clear "not found" message
  — pinned by `::test_inspect_missing_run_exits_1_with_message`.
- [x] `aiw resume <id>` prints placeholder without error
  — pinned by `::test_resume_prints_placeholder` and a negative
  `::test_resume_missing_run_exits_1`. The stub still hits
  `storage.get_run(...)` so the SQLite round-trip is exercised.
- [x] `aiw --help` lists all commands
  — pinned by `::test_aiw_help_lists_every_command` (asserts
  `list-runs`, `inspect`, `resume`, `run`, `version` all appear).
- [x] `--log-level DEBUG` produces human-readable console output
  — pinned by `::test_debug_log_level_produces_human_readable_console`
  (drives the production `configure_logging(level="DEBUG", stream=...)`
  pipeline and asserts the ConsoleRenderer's `[debug` bracket, event
  name, and key=value tokens all land in the captured stream; the same
  test also asserts the end-to-end `aiw --log-level DEBUG list-runs`
  invocation exits cleanly).

## Dependencies

- Task 08 (storage)
- Task 09 (cost tracker)
- Task 11 (logging)

## Carry-over from prior audits

Forward-deferred items owned by this task. Treat each entry like an
additional acceptance criterion and tick it when the corresponding test or
change lands.

- [x] **M1-T04-ISS-01** — Complete Task 04's AC-5 by surfacing
  `cache_read_tokens` and `cache_write_tokens` from `TokenUsage` in the
  `aiw inspect <run_id>` renderer. Task 04 verified the fields flow from
  pydantic-ai's `RunUsage` → our `TokenUsage` → the cost tracker; this
  task is where they become operationally visible. Add the two fields to
  the per-call usage table, and a CLI-level test that shells
  `aiw inspect <run_id>` and greps for `cache_read`.
  Source: [issues/task_04_issue.md](issues/task_04_issue.md) — LOW.
  Resolved by M1 Task 12 — `_render_call_table()` in
  `ai_workflows/cli.py` prints a per-call table with
  `cache_read` / `cache_write` columns; seeded the opus call with
  200/100 cache tokens and pinned the render in
  `tests/test_cli.py::test_inspect_surfaces_cache_read_and_cache_write`.

- [x] **M1-T09-ISS-02** — `aiw inspect <run_id>` must surface the run's
  budget cap and running total in the shape sketched by Task 09:
  `Budget: $<current> / $<cap> (<pct>% used)` when the run has a cap,
  and `Budget: $<current> (no cap)` when `runs.budget_cap_usd IS NULL`.
  Data plumbing is already in place — `storage.get_run(run_id)` returns
  `budget_cap_usd`; `storage.get_total_cost(run_id)` returns the SUM
  aggregate; `CostTracker.budget_cap_usd` exposes the cap as a
  read-only property. Add one CLI-level test that invokes
  `aiw inspect <run_id>` against a seeded DB and greps for the
  formatted line.
  Source: [issues/task_09_issue.md](issues/task_09_issue.md) — LOW.
  Resolved by M1 Task 12 — `_render_budget_line()` in
  `ai_workflows/cli.py` renders the cap / no-cap shapes verbatim;
  pinned by `tests/test_cli.py::test_inspect_budget_line_with_cap`
  (asserts `Budget: $0.42 / $5.00 (8% used)`) and
  `::test_inspect_budget_line_without_cap` (asserts
  `Budget: $0.00 (no cap)`).
