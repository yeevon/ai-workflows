# Gate-output parse patterns (single source of truth)

**Task:** M20 Task 08 — Gate-output integrity (raw-stdout capture + footer-line parse)
**Canonical reference for:** `.claude/commands/auto-implement.md` §Gate-capture-and-parse
  convention and `.claude/commands/clean-implement.md` §Gate-capture-and-parse convention.

Each gate command produces a deterministic footer line on success. The orchestrator
captures the full stdout + stderr of each gate to `runs/<task>/cycle_<N>/gate_<name>.txt`
and scans that file for the footer line before stamping AUTO-CLEAN (or CLEAN in
`/clean-implement`).

---

## Per-gate footer-line regex

| Gate name | Command | Footer-line regex | Pass condition |
|---|---|---|---|
| `pytest` | `uv run pytest` | `^=+ \d+ passed` | Footer present **and** no `failed` word on the same line |
| `ruff` | `uv run ruff check` | `^All checks passed\.$` or `^\d+ files? checked\.$` | Footer present |
| `lint-imports` | `uv run lint-imports` | `^Contracts kept$` | Exact match on trimmed line |

### Notes

- Match is applied to each line of the captured file individually (not the full blob as
  a single string).  Trim leading/trailing whitespace from each line before matching.
- For `pytest`: a footer like `==== 5 passed ====` satisfies the regex; a footer like
  `==== 5 failed, 10 passed ====` contains `failed` and must be treated as **failure**.
  Fail-closed rule: if the footer is present but contains the word `failed`, halt.
- For `ruff`: both `All checks passed.` (no-violation case) and `N files checked.`
  (informational summary) count as pass footers.  An exit code ≠ 0 overrides the
  footer — always halt on non-zero exit, regardless of footer text.
- For `lint-imports`: the pass footer is the exact string `Contracts kept` (no punctuation).
  Any other footer text means failure.

---

## Halt condition

The orchestrator **halts with**:

```
🚧 BLOCKED: gate <name> output not parseable; see runs/<task>/cycle_<N>/gate_<name>.txt
```

when **any** of the following are true:

1. The captured file is empty (zero bytes or whitespace only).
2. The footer line is absent — no line in the file matches the gate's footer regex.
3. The exit code captured alongside the output is non-zero (even if a footer line is present).
4. The footer line is present but indicates failures (e.g. `failed` in a pytest footer).

---

## Extension hooks for task-specific smoke tests

Custom gates (e.g. `aiw --workflow foo run` or `uv run pytest tests/release/`) follow the
same capture convention.  Add a row to this table when a new gate type is introduced:

| Gate name | Command | Footer-line regex | Pass condition |
|---|---|---|---|
| *(add custom gates here)* | | | |

When a task spec's `## Smoke test` section names a specific command, its footer-line regex
is added here before the task closes. Tasks that reuse an existing gate (e.g. scoped pytest)
do not need a new row — they inherit the `pytest` pattern.

---

## Capture format

Each captured file has the following structure (plain text, no special encoding):

```
EXIT_CODE=<integer>
STDOUT:
<full stdout of the gate command>
STDERR:
<full stderr of the gate command, may be empty>
```

The `EXIT_CODE=` line is always line 1 of the file.  The `STDOUT:` and `STDERR:` labels
are literal separator lines.  The orchestrator reads line 1 to extract the exit code and
scans lines 3 onward (or until the `STDERR:` separator) for the footer-line regex.

> **Shorthand capture** (acceptable alternative when the Bash tool captures stdout and
> stderr together in a single blob): store the combined output as-is, and record the exit
> code in a companion file `runs/<task>/cycle_<N>/gate_<name>.exit`. The parser then reads
> the exit companion file for the exit code and the main capture file for footer scanning.
