# Task 04 — HumanGate Component

**Issues:** C-30, C-32, C-33, IMP-05 (revises C-31)

## What to Build

Pauses workflow execution for human review. Pretty-printed in terminal, raw JSON in log file, survives process restart. `strict_review=True` blocks `--skip-gate`. **Timeout defaults to `None` when `strict_review=True`** (overnight batch pattern), 30 min otherwise.

## Deliverables

### `components/human_gate.py`

```python
class HumanGateConfig(ComponentConfig):
    gate_id: str
    review_subject: str                # "plan" | "diff" | "output"
    timeout_minutes: int | None = None # None = wait forever; default depends on strict_review
    allow_edit: bool = True
    dependency_review: bool = False
```

### Default Timeout Rule (IMP-05)

- If workflow has `strict_review: true` AND gate doesn't override: timeout is `None` (wait forever)
- If non-strict AND gate doesn't override: timeout is 30 minutes
- If gate overrides: use that value (including `None`)

Overnight pattern: submit the plan before bed, resume in the morning. The process may still be running, or it may have been killed by a sleep/reboot — resume picks up from the `pending_review` state either way.

### Render Logic

**On entry:**

1. Write raw JSON of the review subject to `runs/<run_id>/gates/{gate_id}.json`
2. Render pretty-printed summary to terminal:
   - For `plan` subject: task count, task list with `depends_on` shown as tree, dependencies requiring review (if `dependency_review=True`)
   - For `diff` subject: colorized diff with context
   - For `output` subject: structured output with field names

```text
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
Timeout: no timeout (strict_review)
```

Then:

1. Write gate state `pending_review` to SQLite
2. Wait for input (via stdin `input()`; timeout via `asyncio.wait_for()` if set)

**On response:**

- `a`: mark `approved`, continue
- `r`: mark `rejected`, raise `HumanGateRejectedError` → run fails
- `e`: open `$EDITOR` on the JSON artifact, re-render, prompt again
- `?`: print full JSON, prompt again

**On timeout (finite case):**

- Mark `timed_out`, raise `HumanGateTimedOutError`
- Print: `Gate timed out. Resume with: aiw resume <run_id>`

### `strict_review: true` Enforcement

At workflow load time: if `strict_review=True` AND `--skip-gate` flag present → raise `StrictReviewViolationError` BEFORE any component runs.

### Resume

On `aiw resume`: read gate state from SQLite. If `pending_review` or `timed_out`: re-render from the saved JSON artifact, prompt again. Artifact preserved across restarts.

## Acceptance Criteria

- [ ] Pretty-printed render for 12-task DAG looks sensible
- [ ] Full JSON saved to `runs/<run_id>/gates/{gate_id}.json` before prompting
- [ ] `strict_review=True` → default timeout is `None`
- [ ] `strict_review=False` → default timeout is 30 min
- [ ] `strict_review=True` + `--skip-gate` → `StrictReviewViolationError` at load time
- [ ] `e` opens `$EDITOR` and re-prompts after save
- [ ] Resume re-renders from saved JSON artifact

## Dependencies

- M2 Task 01 (BaseComponent)
- M1 Task 08 (storage)
