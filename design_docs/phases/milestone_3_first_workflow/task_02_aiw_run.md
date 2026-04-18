# Task 02 — `aiw run` Command

**Issues:** CL-02

## What to Build

Full implementation of `aiw run`. Loads the workflow, wires components, executes the flow, streams structured progress to the terminal.

## Deliverables

### `aiw run <workflow> [--profile <name>] [--dry-run] [--log-level DEBUG] [key=value ...]`

**Behavior:**
1. Resolve `<workflow>` to a directory under `ai_workflows/workflows/` or an absolute path
2. Call `load_workflow(workflow_dir, profile)` → `WorkflowDefinition`
3. Generate `run_id` (UUID4 short)
4. Call `build_run_context()` — creates run dir, snapshots YAML
5. Create `SQLiteStorage` run record (`status=running`)
6. Instantiate all components from the definition (at load time, not lazily)
7. Execute `flow:` steps in order (sequential at this milestone — DAG parallel execution comes in Milestone 4)
8. On `FanoutHardStopError`: print failure summary, mark run `failed`, exit 1
9. On success: print cost summary, mark run `completed`, exit 0

**Terminal output format:**
```
[aiw] Starting run abc123 — test_coverage_gap_fill
[aiw] explore   auth_module       running...
[aiw] explore   auth_module       completed  ($0.00 local)
[aiw] worker    generate_tests    running...  [1/12 files]
[aiw] worker    generate_tests    running...  [2/12 files]
[aiw] worker    generate_tests    completed  ($0.08)
[aiw] Run abc123 completed in 4m 32s — Total cost: $0.08
```

**`--dry-run` flag:** Sets `dry_run=True` on all `run_command` calls. Prints what would execute without running. Useful for testing workflow definitions.

## Acceptance Criteria

- [ ] `aiw run test_coverage_gap_fill repo=/path/to/repo slice=AuthModule` executes end-to-end
- [ ] Progress lines appear as tasks complete (not buffered until the end)
- [ ] `--dry-run` completes without any real shell commands executing
- [ ] Run record in SQLite is `completed` after successful run, `failed` after hard stop
- [ ] Cost summary matches `aiw inspect <run_id>` output

## Dependencies

- Task 01 (workflow loader)
- Task 12 (storage)
- Task 13 (cost tracker)
