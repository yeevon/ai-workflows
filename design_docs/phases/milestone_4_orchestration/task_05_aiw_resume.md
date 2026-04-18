# Task 05 — `aiw resume` (Full Implementation)

**Issues:** CL-04, C-13

## What to Build

Full resume from checkpoint. Reads SQLite task states, skips completed tasks, re-queues interrupted ones, handles pending HumanGate states.

## Deliverables

### `aiw resume <run_id> [--profile <name>]`

**Behavior:**
1. Load run record from SQLite → get `workflow_id`, snapshotted `workflow.yaml`, `profile`
2. Load the snapshotted `workflow.yaml` (from `runs/<run_id>/workflow.yaml`) — not the current one on disk. This ensures resume uses the exact config the run started with.
3. Read all task states from SQLite
4. Print resume preview:
   ```
   Resuming run abc123 — jvm_modernization
   
   Skipping (completed): explore_repo_a, explore_repo_b, refactor_auth
   Re-running (interrupted): refactor_payments
   Pending: refactor_reporting, validate_build, human_gate_review
   
   Resume? [y/N]
   ```
5. On confirm: reconstruct `RunContext`, instantiate components, pass to `Orchestrator.run()` with task states pre-loaded
6. If a `HumanGate` is in `pending_review` or `timed_out` state: re-render the gate immediately before resuming execution

**Key invariant:** Resume always uses the snapshotted `workflow.yaml`, not the current file on disk. If the user changed `workflow.yaml` between the original run and the resume, warn them but proceed with the snapshot.

## Acceptance Criteria

- [ ] Resume skips all tasks marked `completed` in SQLite
- [ ] Resume re-runs tasks marked `running` (interrupted)
- [ ] Snapshotted `workflow.yaml` is used, not the current disk version
- [ ] Pending HumanGate re-renders before resuming execution
- [ ] `aiw resume <nonexistent_run_id>` shows clear error, exits 1

## Dependencies

- Task 03 (Orchestrator)
- Task 04 (HumanGate)
- M1 Task 12 (storage)
