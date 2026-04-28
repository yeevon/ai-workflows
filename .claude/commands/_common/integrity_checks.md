# Task-integrity checks (single source of truth)

**Task:** M20 Task 09 — Task-integrity safeguards (non-empty-diff + non-empty test-diff +
  independent pre-stamp gate re-run)
**Canonical reference for:** `.claude/commands/auto-implement.md` §Pre-commit ceremony.
**Depends on:** `.claude/commands/_common/gate_parse_patterns.md` (pytest footer-line regex).

Three pre-commit safeguards the orchestrator runs **after all reviewers SHIP** and
**before** stamping AUTO-CLEAN. Each check has a distinct failure-mode signature so the
halt message names the specific check that fired.

---

## Check 1 — Non-empty diff

**Command:**
```
git diff --stat <pre-task-commit>..HEAD
```

**Pass condition:** output is non-empty (at least one insertion OR deletion line).

**Failure-mode signature:** output is an empty string (or whitespace only).

**Halt message:**
```
🚧 BLOCKED: task-integrity check 1 (empty diff) failed; see runs/<task>/integrity.txt
```

**Why this check exists:** A Builder + Auditor cycle can converge on "done" with no
meaningful change (e.g. comment-only edits that survive ruff, or a prior-cycle change that
was later reverted). An empty diff after a claimed AUTO-CLEAN is a strong signal of a
loop-behaviour bug and requires user review before the commit lands.

---

## Check 2 — Non-empty test diff (code tasks only)

**Command:**
```
git diff --stat <pre-task-commit>..HEAD -- tests/
```

**Task-kind determination:** parse the spec's `**Kind:**` line in the Status block
(present on every M20 spec per the `Kind:` convention). The value is a slash-separated
list of categories, e.g. `Safeguards / code`, `Compaction / doc + code`, `Model-tier /
analysis`. Check 2 fires **only** when any category contains the word `code`. If the
`**Kind:**` line is absent from the spec, fall back to the milestone README's task-pool
"Phase / Kind" column for this task's row; treat any `code`-containing value as a code
task.

**Pass condition:** output is non-empty (at least one test-file change) for a code task.

**Bypass condition:** task-kind does NOT contain `code` (doc-only, analysis-only) → skip
Check 2 entirely; it does not apply and cannot block.

**Failure-mode signature:** task-kind contains `code` AND `git diff --stat ... -- tests/`
output is empty.

**Halt message:**
```
🚧 BLOCKED: task-integrity check 2 (empty test diff for code task) failed; see runs/<task>/integrity.txt
```

**Why this check exists:** A Builder can satisfy Check 1 by editing a comment or a
docstring in production code. Check 2 ensures that code tasks also have verifiable test
coverage — specifically that something changed in `tests/`. It does not check
*adequacy* of tests (that is the Auditor's + sr-sdet's job); it checks *presence*.

---

## Check 3 — Independent gate re-run (pytest)

**Command:**
```
uv run pytest -q
```

**Pass condition:** footer line matches `^=+ \d+ passed` **and** the line does not
contain `failed` **and** exit code is 0.

**Footer-line regex:** reuses the `pytest` entry in
`.claude/commands/_common/gate_parse_patterns.md` §Per-gate footer-line regex.

**Failure-mode signature:** exit code ≠ 0, OR footer line missing, OR footer line
contains `failed`.

**Halt message:**
```
🚧 BLOCKED: task-integrity check 3 (pytest failure) failed; see runs/<task>/integrity.txt
```

**Why this check exists:** The Auditor's pytest run is not the last word. A regression
can be introduced between the Auditor's run and the commit ceremony (e.g. a
status-surface edit touching a tracked file with hidden side effects). Running pytest
independently and immediately before AUTO-CLEAN stamp closes that window.

---

## Captured output location

Capture the stdout + stderr + exit code of all three checks into:

```
runs/<task-shorthand>/integrity.txt
```

Format (append each check's output):

```
=== Check 1: git diff --stat <pre-task-commit>..HEAD ===
<stdout, may be empty>
EXIT_CODE=<integer>

=== Check 2: git diff --stat <pre-task-commit>..HEAD -- tests/ ===
TASK_KIND=<value from spec or README>
CODE_TASK=<true|false>
<stdout, may be empty>
EXIT_CODE=<integer>

=== Check 3: uv run pytest -q ===
<stdout + stderr>
EXIT_CODE=<integer>
```

This file is the durable debug record for any integrity-check failure surfaced to the user.

---

## When to run

After G6 TERMINAL CLEAN (all reviewers SHIP, gate-capture-and-parse section clean) and
**before** Step C1 (KDR isolation). If any check fails, do NOT proceed to the commit
ceremony; halt with the named BLOCKED message.

The gate-capture-and-parse convention (T08) and the task-integrity checks (T09) are
complementary, not redundant:

- T08 (gate-capture-and-parse): verifies each gate tool's *own output* is trustworthy
  (fail-closed on empty or unparseable stdout — guards against the Builder claiming
  "gates pass" with no actual output).
- T09 (task-integrity): verifies the *task's output* is meaningful (non-empty diff,
  test coverage present, pytest still green at commit time).

---

## Relationship to other checks

| Check | Layer | What it catches |
|---|---|---|
| T01 agent-return parser | Orchestrator-side return validation | Malformed agent verdict lines |
| T08 gate-capture-and-parse | Gate-tool output validation | Builder claims "gates pass" with empty / failure output |
| T09 non-empty diff (Check 1) | Task-output validation | Loop converged with no meaningful change |
| T09 non-empty test diff (Check 2) | Task-output validation | Code task shipped with no test changes |
| T09 independent pytest re-run (Check 3) | Late regression catch | Regression introduced between Auditor run and commit |
