# Task 08 — Gate-output integrity (raw-stdout parse, fail-closed on missing output)

**Status:** 📝 Planned.
**Kind:** Safeguards / code.
**Grounding:** [milestone README](README.md) · memory `project_autonomy_optimization_followups.md` thread #10 · sibling [task_01](task_01_sub_agent_return_value_schema.md) (T08's first defence layer reuses T01's orchestrator parser) · [`.claude/commands/auto-implement.md`](../../../.claude/commands/auto-implement.md).

## What to Build

Defense-in-depth against Builder agents claiming "all gates pass" without actually running gates. Today the orchestrator trusts the Builder's textual report of gate results; T08 makes the orchestrator independently capture and parse the raw stdout of each gate command before stamping AUTO-CLEAN. **Fail-closed** on missing or unparseable output.

This is **especially load-bearing under T07's default-Sonnet** (research brief §Lens 3.4 + memory thread #10): Sonnet is more likely to confidently misreport gate outcomes than Opus. Without T08, the safety net for misreports is the Auditor's re-run (which already exists). T08 adds a *second* safety net at the orchestrator layer that catches failures the Auditor's re-run might miss (e.g. if the Auditor itself misreads gate output).

## Mechanism

For each gate command (`uv run pytest`, `uv run lint-imports`, `uv run ruff check`, plus task-specific smoke tests):

1. Orchestrator runs the gate via Bash, captures stdout + stderr + exit code into `runs/<task>/cycle_<N>/gate_<gate-name>.txt`.
2. Orchestrator parses the captured output for the test runner's footer line (`==== N passed ====` for pytest; equivalent for ruff / lint-imports).
3. If footer line is missing OR parse-mismatched OR exit code ≠ 0 → halt with `🚧 BLOCKED: gate <name> output not parseable; see runs/<task>/cycle_<N>/gate_<gate-name>.txt`. **Do not proceed to AUTO-CLEAN stamp.**
4. The captured file becomes the durable record consulted by Auditor + sr-dev + sr-sdet on their re-runs.

T01's orchestrator parser is the **first defence layer** (catches malformed agent verdict-lines). T08 is the **second layer** (catches Builder claims of "gates pass" with empty actual stdout).

## Deliverables

### `.claude/commands/auto-implement.md` — gate-capture convention

Update the AUTO-CLEAN-stamp section to require:

```markdown
Before stamping AUTO-CLEAN, the orchestrator independently runs each
gate command and captures output to `runs/<task>/cycle_<N>/gate_<name>.txt`.
The orchestrator parses each captured file for the runner's footer line:
- pytest:  `^=+ \d+ passed`
- ruff:    `^All checks passed!` or `^\d+ files? checked`
- lint-imports: `^Contracts kept`
Missing or unparseable footer = halt with the BLOCKED surface above.
```

### `.claude/commands/clean-implement.md` — same convention

Apply consistently.

### `.claude/commands/_common/gate_parse_patterns.md` (NEW)

Single source of truth for the per-gate footer-line regex. Each command's gate-capture section links to this file.

## Tests

### `tests/orchestrator/test_gate_output_capture.py` (NEW)

- Synthetic gate output with valid pytest footer → parses cleanly.
- Synthetic empty stdout → halt.
- Synthetic stdout claiming pass without footer line → halt.
- Synthetic stdout with exit code ≠ 0 → halt regardless of footer presence.
- Synthetic stdout with footer indicating failures (`5 failed, 10 passed`) → halt.

### `tests/orchestrator/test_auto_clean_stamp_safety.py` (NEW)

- Builder claims "gates pass" but `runs/<task>/cycle_<N>/gate_pytest.txt` is empty → halt.
- Builder claims "gates pass" and gate captures show pass → AUTO-CLEAN stamp lands.
- Builder claims "gates pass" but one gate has a failure footer → halt.

## Acceptance criteria

1. `.claude/commands/auto-implement.md` describes the gate-capture-and-parse convention.
2. `.claude/commands/clean-implement.md` matches.
3. `.claude/commands/_common/gate_parse_patterns.md` exists with per-gate regex.
4. Captured gate outputs land at `runs/<task>/cycle_<N>/gate_<name>.txt`.
5. Halt-on-missing-footer surfaces `🚧 BLOCKED: gate <name> output not parseable`.
6. `tests/orchestrator/test_gate_output_capture.py` passes.
7. `tests/orchestrator/test_auto_clean_stamp_safety.py` passes.
8. CHANGELOG.md updated under `[Unreleased]` with `### Added — M20 Task 08: Gate-output integrity (orchestrator-side raw-stdout capture + footer-line parse; fail-closed on missing output; load-bearing under default-Sonnet)`.
9. Status surfaces flip together.

## Smoke test (Auditor runs)

```bash
# Verify gate-parse pattern reference exists
test -f .claude/commands/_common/gate_parse_patterns.md && echo "patterns OK"

# Verify auto-implement and clean-implement reference it
# Explicit file list per CLAUDE.md verification-discipline.
grep -lE "gate_parse_patterns.md|gate_<name>.txt" \
  .claude/commands/auto-implement.md \
  .claude/commands/clean-implement.md \
  | wc -l
# Expected: 2

# Run gate-output tests
uv run pytest tests/orchestrator/test_gate_output_capture.py tests/orchestrator/test_auto_clean_stamp_safety.py -v
```

## Out of scope

- **Modifying the gate commands themselves** — `uv run pytest`, `uv run lint-imports`, `uv run ruff check` are unchanged. T08 only changes how the orchestrator captures + parses their output.
- **Custom gate runners** — task-specific gates (smoke tests, eval-harness runs) are also captured via the same pattern; their footer-line regex is added to `_common/gate_parse_patterns.md` as the project grows.
- **Real-time streaming of gate output** — captures are post-hoc (Bash run with capture, then read). Streaming would add complexity for no current benefit.
- **Cross-cycle gate-result diffing** — out of scope. T03 (cycle_summary) records per-cycle gate results; cross-cycle analysis is a future productivity feature.

## Dependencies

- **T01** (orchestrator parser) — **blocking**. T08's first-defence-layer is T01's parser; without T01 landed, T08 has nothing to layer atop. Per audit M2, T01 is content-blocking for T08 (the schema reuse is structural, not optional).
- **T07** (dynamic dispatch) — T08 becomes more load-bearing if T07 ships. Without T07's default-Sonnet, T08 is still useful but less critical.

## Carry-over from prior milestones

*None.*

## Carry-over from task analysis

(populated by `/clean-tasks m20`)

## Carry-over from prior audits

(populated by `/clean-implement` audit cycles)
