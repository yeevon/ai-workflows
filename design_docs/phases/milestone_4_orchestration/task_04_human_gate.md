# Task 04 — HumanGate Component

**Issues:** C-30, C-31, C-32, C-33

## What to Build

Pauses workflow execution for human review. Renders the current plan/output in the terminal, waits for a decision, and optionally allows the reviewer to edit the plan before approving. Supports `strict_review` mode for regulated workflows.

## Deliverables

### `components/human_gate.py`

**Config:**
```python
class HumanGateConfig(ComponentConfig):
    gate_id: str                          # unique within a workflow
    review_subject: str                   # "plan", "diff", or "output"
    timeout_minutes: int = 30
    allow_edit: bool = True
    dependency_review: bool = False       # separate mandatory review of DAG dependencies
```

**Behavior:**

**On entry:**
1. Write full JSON of the review subject to `runs/<run_id>/gates/{gate_id}.json` (for deep analysis)
2. Render pretty-printed summary to terminal:
   ```
   ═══════════════════════════════════════════════
   REVIEW REQUIRED — jvm_modernization / gate: pre_execution
   ═══════════════════════════════════════════════
   Plan: 12 tasks across 3 repos
   
   Task summary:
     [1] explore_repo_a          (no deps)
     [2] explore_repo_b          (no deps)
     [3] refactor_auth           (depends on: 1, 2)
     ...
   
   Dependencies requiring review:
     repo_a → repo_b: AuthService imports UserRepository
   
   [a]pprove  [r]eject  [e]dit  [?]full JSON
   ═══════════════════════════════════════════════
   ```
3. Write gate state `pending_review` to SQLite

**On response:**
- `a`: mark `approved` in SQLite, continue
- `r`: mark `rejected`, raise `HumanGateRejectedError` (triggers run failure)
- `e`: open `$EDITOR` on the JSON artifact, re-render after save, prompt again
- `?`: print full JSON to terminal, prompt again

**On timeout:**
- Mark gate `timed_out` in SQLite
- Raise `HumanGateTimedOutError`
- Print: "Gate timed out. Resume with: aiw resume <run_id>"

**`strict_review: true` enforcement:**
- At workflow load time: if `strict_review=True` and `--skip-gate` flag is present, raise `StrictReviewViolationError` before any component runs
- The gate cannot be bypassed in strict mode — `--skip-gate` is rejected outright

**`dependency_review: true`:**
- Adds a separate review step specifically rendering the DAG dependency edges
- Reviewer must explicitly approve the dependency structure before approving the full plan

**Resume:**
- On `aiw resume <run_id>`: read gate state from SQLite
- If `pending_review` or `timed_out`: re-render the gate (from the JSON artifact), prompt again
- Gate artifact in `runs/<run_id>/gates/` is preserved across restarts

## Acceptance Criteria

- [ ] Gate renders plan summary correctly for a 12-task DAG
- [ ] Full JSON written to `runs/<run_id>/gates/{gate_id}.json` before prompting
- [ ] Timeout triggers `HumanGateTimedOutError` after configured minutes
- [ ] `strict_review=True` + `--skip-gate` raises `StrictReviewViolationError` at load time (before any LLM call)
- [ ] Resume re-renders the gate from the saved JSON artifact
- [ ] `e` (edit) opens `$EDITOR` and re-prompts after save

## Dependencies

- M2 Task 01 (BaseComponent)
- M1 Task 12 (storage — for gate state)
