# Task 02 — `aiw run` Full Implementation

**Issues:** CL-02

## What to Build

Full implementation of `aiw run`. Loads the workflow, instantiates components, runs the `Pipeline`, streams structured progress.

## Deliverables

### `aiw run <workflow> [--profile <name>] [--dry-run] [--log-level DEBUG] [key=value ...]`

**Behavior:**

1. Resolve `<workflow>` to a directory (relative to `ai_workflows/workflows/` or absolute path)
2. Call `load_workflow(workflow_dir, profile)` → `WorkflowDefinition`, hash
3. Generate `run_id` (UUID4 short form, 6-char display)
4. Snapshot workflow directory to `~/.ai-workflows/runs/<run_id>/workflow/`
5. Configure logging with `run_id`
6. Create `SQLiteStorage` run record with `workflow_dir_hash` and `max_run_cost_usd`
7. Instantiate `ToolRegistry`, register stdlib + custom tools
8. Build all components from `definition.components` (via factory that maps `type:` → class)
9. Build `Pipeline` wrapping the components per `flow:`
10. Execute `pipeline.run(input, run_id=..., workflow_id=...)`
11. On `BudgetExceeded`: mark `failed`, exit 1, print remaining budget vs cap
12. On `CancelledError` (SIGINT): mark running step `running`, exit 130 (shell SIGINT convention)
13. On hard-stop exception: mark `failed`, print failure artifact path, exit 1
14. On success: mark `completed`, print cost summary, exit 0

### Terminal Output

```text
[aiw] run abc123 — test_coverage_gap_fill — budget $10.00
[aiw] explore          running...
[aiw] explore          completed  $0.00 local
[aiw] generate_tests   running...  [wave 1/3 — 5/12 items]
[aiw] generate_tests   running...  [wave 2/3 — 10/12 items]
[aiw] generate_tests   completed  $0.42
[aiw] validate_build   running...
[aiw] validate_build   completed  $0.00 structural
[aiw] run abc123 completed in 4m 32s — $0.42 / $10.00 (4% of budget)
```

### `--dry-run`

Sets `dry_run=True` on all `run_command` tool calls. Prints would-execute commands but doesn't invoke. Useful for validating workflow definitions.

### Input Parsing

`aiw run <workflow> repo=/path/to/repo slice=AuthModule` — `key=value` positional args map to `inputs:` from the workflow YAML. Types validated via Pydantic.

## Acceptance Criteria

- [ ] `aiw run test_coverage_gap_fill repo=/path slice=AuthModule` executes end-to-end
- [ ] Progress lines stream as tasks complete (not buffered to end)
- [ ] `--dry-run` prevents all real shell commands
- [ ] Run record in SQLite moves `pending → running → completed` on success
- [ ] `BudgetExceeded` path marks run `failed` and prints cap vs spend
- [ ] SIGINT leaves interrupted step marked `running` for resume
- [ ] Workflow directory is snapshotted before first LLM call

## Dependencies

- Task 01 (loader)
- All of M2
