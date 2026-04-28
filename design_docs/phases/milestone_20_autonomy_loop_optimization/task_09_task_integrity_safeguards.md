# Task 09 — Task-integrity safeguards (non-empty-diff + non-empty test-diff + independent gate re-run)

**Status:** 📝 Planned.
**Kind:** Safeguards / code.
**Grounding:** [milestone README](README.md) · memory `project_autonomy_optimization_followups.md` thread #11 · sibling [task_08](task_08_gate_output_integrity.md) (gate-level integrity) · [`.claude/commands/auto-implement.md`](../../../.claude/commands/auto-implement.md).

## What to Build

Three pre-commit safeguards the orchestrator runs before stamping AUTO-CLEAN, catching the failure mode where Builder + Auditor agree the task is done but no semantically-meaningful work landed:

1. **Non-empty diff check.** `git diff --stat <prev-commit>..HEAD` must show non-zero insertions OR deletions. A 2-cycle AUTO-CLEAN with empty diff is suspicious; halt and surface for user review.
2. **Non-empty test diff for feature work.** When the task's kind includes `code` — parsed from the spec's `**Kind:**` line in the Status block (every M20 spec gains this line per audit M3); orchestrator falls back to the milestone README's task-pool "Phase / Kind" column if the spec's Kind line is missing — the diff must include changes under `tests/`. A Builder can satisfy "non-empty diff" by editing only a comment in production code; the test-diff check catches that. Doc-only and analysis-only tasks bypass this check.
3. **Independent gate re-run.** The orchestrator independently runs `uv run pytest -q` (tail-only) immediately before AUTO-CLEAN stamp. The Auditor's pytest run is not the last word — a regression introduced after the Auditor's run (e.g. by a status-surface flip touching a tracked file with hidden side effects) gets caught here. T08's gate-capture infrastructure is the foundation; T09 adds the *re-run-just-before-stamp* invocation.

## Mechanism

After Auditor returns PASS and the terminal gate (T05) returns SHIP / SHIP / SHIP:

1. Orchestrator runs `git diff --stat <pre-task-commit>..HEAD` and asserts non-zero (1).
2. If task-kind includes `code` (parsed from the spec's `**Kind:**` line, falling back to README task-pool Kind column): orchestrator runs `git diff --stat <pre-task-commit>..HEAD -- tests/` and asserts non-zero (2).
3. Orchestrator runs `uv run pytest -q` and parses the footer per T08 (3).
4. If any of (1), (2), (3) fails: halt with `🚧 BLOCKED: task-integrity check <which> failed; see runs/<task>/integrity.txt`.

Captured outputs land at `runs/<task>/integrity.txt` for debugging.

## Deliverables

### `.claude/commands/auto-implement.md` — pre-commit ceremony

Update the AUTO-CLEAN-stamp section. Today the stamp lands immediately after Auditor PASS + reviewer SHIP. T09 inserts the three checks between "all reviewers SHIP" and "stamp AUTO-CLEAN":

```markdown
### Step <N> — Pre-commit ceremony (after all reviewers SHIP)

Before stamping AUTO-CLEAN, the orchestrator runs three integrity checks:

1. `git diff --stat <pre-task-commit>..HEAD` — assert non-zero diff.
   Empty diff = halt with the BLOCKED surface.

2. If task-kind includes `code` (per the spec's kind line):
   `git diff --stat <pre-task-commit>..HEAD -- tests/` — assert non-zero
   test diff. Empty test diff for a code task = halt.

3. `uv run pytest -q` — independent re-run; parse footer per T08's
   gate_parse_patterns.md. Failed footer = halt.

If any check fails: do NOT stamp AUTO-CLEAN. Surface BLOCKED with the
specific failed check named.
```

### `.claude/commands/_common/integrity_checks.md` (NEW)

Canonical reference for the three checks + their failure-mode signatures.

## Tests

### `tests/orchestrator/test_integrity_checks.py` (NEW)

- Empty diff fixture → halt fires.
- Code-task with non-empty production diff but empty test diff → halt fires.
- Code-task with non-empty production + test diff but failing pytest → halt fires.
- Doc-only task with empty test diff → no halt (test-diff check bypassed).
- All three checks pass → no halt; AUTO-CLEAN stamp proceeds.

## Acceptance criteria

1. `.claude/commands/auto-implement.md` describes the pre-commit ceremony with three checks.
2. `.claude/commands/_common/integrity_checks.md` exists.
3. Halt surfaces the specific failed check.
4. `tests/orchestrator/test_integrity_checks.py` passes.
5. CHANGELOG.md updated under `[Unreleased]` with `### Added — M20 Task 09: Task-integrity safeguards (non-empty diff + non-empty test diff for code tasks + independent pre-stamp gate re-run)`.
6. Status surfaces flip together.

## Smoke test (Auditor runs)

```bash
# Verify integrity-checks reference exists
test -f .claude/commands/_common/integrity_checks.md && echo "checks OK"

# Verify auto-implement describes the ceremony
grep -q "pre-commit ceremony\|task-integrity\|integrity_checks.md" .claude/commands/auto-implement.md \
  && echo "auto-implement OK"

# Run integrity tests
uv run pytest tests/orchestrator/test_integrity_checks.py -v
```

## Out of scope

- **Cross-task integrity** — out of scope. T09 is per-task; cross-task drift is the Auditor's "design-drift check" responsibility.
- **Diff-line-count thresholds beyond non-zero** — minimum-diff-size heuristics ("too small to be meaningful") are over-engineering. Non-zero is sufficient.
- **AST-level diff analysis** — out of scope. `git diff --stat` is the granularity.
- **Auto-recovery on integrity failure** — halts go to the user. Auto-recovery would mask the underlying agent-behaviour bug.

## Dependencies

- **T08** (gate-output integrity) — strongly precedent. T09's check (3) reuses T08's `gate_parse_patterns.md`.

## Carry-over from prior milestones

*None.*

## Carry-over from task analysis

(populated by `/clean-tasks m20`)

## Carry-over from prior audits

(populated by `/clean-implement` audit cycles)
