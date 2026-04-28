# Task 05 — Parallel terminal gate (sr-dev + sr-sdet + security-reviewer in one message)

**Status:** 📝 Planned.
**Grounding:** [milestone README](README.md) · [research brief `research_analysis` §Lens 1.4 (parallel sub-agent dispatch)](research_analysis) · memory `project_autonomy_optimization_followups.md` thread #14 · [`.claude/commands/auto-implement.md`](../../../.claude/commands/auto-implement.md) · [`.claude/agents/sr-dev.md`](../../../.claude/agents/sr-dev.md) · [`.claude/agents/sr-sdet.md`](../../../.claude/agents/sr-sdet.md) · [`.claude/agents/security-reviewer.md`](../../../.claude/agents/security-reviewer.md) · sibling [task_01](task_01_sub_agent_return_value_schema.md) (fragment-file format reuses T01's 3-line schema).

## What to Build

Replace the **sequential terminal gate** in `/auto-implement` with a **parallel multi-Task spawn**. Today the orchestrator spawns sr-dev → sr-sdet → security-reviewer in series (each invocation waits for the previous to return). T05 spawns all three in a single orchestrator message (the Agent tool doc explicitly endorses concurrent multi-Task spawns), and stitches their outputs via fragment files.

Per the research brief §Lens 1.4: parallel sub-agent dispatch works when (a) ≥ 3 unrelated tasks, (b) no shared state, (c) clear non-overlapping file boundaries, (d) independent verification. The terminal gate satisfies all four — sr-dev grades code quality, sr-sdet grades test quality, security-reviewer grades the threat-model surface; none depend on the others' output.

**Wall-clock target: ≥ 2× improvement** vs the current serial gate. Sum-of-three becomes max-of-three.

## Mechanism — fragment files (per research brief §Lens 1.4)

Each reviewer writes its verdict to a deterministic fragment path instead of editing the issue file directly:

- sr-dev → `runs/<task>/<cycle>/sr-dev-review.md`
- sr-sdet → `runs/<task>/<cycle>/sr-sdet-review.md`
- security-reviewer → `runs/<task>/<cycle>/security-review.md`

(Where `<task>` is `m<N>_t<NN>` and `<cycle>` is the current cycle number.)

This avoids file-write contention on the issue file. The three reviewers run truly concurrently; no Edit-collision races. After all three return, the orchestrator reads the three fragment files in one Read pass and stitches them into the issue file under their respective `## Sr. Dev review`, `## Sr. SDET review`, `## Security review` sections in one Edit pass.

The Read tool's "Read multiple files at once" pattern (one tool message, multiple Read invocations) keeps the stitch step single-turn.

## Reviewer-agent updates

Each of the three reviewer agent files updates its `## Output format` section:

- **Old:** "Append to the existing issue file under a `## <name> review` section."
- **New:** "Write your full review to `runs/<task>/<cycle>/<agent>-review.md`. The orchestrator stitches it into the issue file in a follow-up turn. Your `## Return to invoker` value (T01) points `file:` at the fragment path; `section:` is the `## <name> review` heading the orchestrator will use when stitching."

The fragment file's content is identical to today's `## <name> review` section content (verdict + critical/high/advisory tiers + reviewer-passed-review per-lens). Only the destination changes.

## Deliverables

### `.claude/commands/auto-implement.md` — parallel-spawn block

Locate the terminal-gate section (currently sequential). Replace with a single message that spawns all three Task invocations in parallel:

```markdown
### Step <N> — Terminal gate (parallel)

Spawn sr-dev, sr-sdet, and security-reviewer concurrently in a single
orchestrator message (three Task tool calls in one assistant turn).
Each agent writes its review to `runs/<task>/<cycle>/<agent>-review.md`
per the agent's updated `## Output format`.

Wait for all three Tasks to complete. Then in a follow-up turn:

1. Read the three fragment files in one Read multi-call.
2. Stitch them into the task issue file under their respective
   `## Sr. Dev review`, `## Sr. SDET review`, `## Security review`
   sections in one Edit pass.
3. Parse each agent's T01 return-schema verdict line.
4. Stop conditions: all three SHIP → continue. Any FIX-THEN-SHIP →
   halt for user arbitration. Any BLOCK → halt with reviewer's
   finding surfaced verbatim.
```

### `.claude/agents/sr-dev.md`, `sr-sdet.md`, `security-reviewer.md` — output-format update

Each updates its `## Output format` section to write to the fragment path. The verdict tokens, severity tiers, and per-lens content stay the same.

### `.claude/commands/_common/parallel_spawn_pattern.md` (NEW)

Canonical reference for the parallel-spawn-with-fragment-files pattern, in case future commands adopt it (e.g. a future `/sweep` command in M21 that runs ad-hoc reviews).

## Tests

### `tests/orchestrator/test_parallel_terminal_gate.py` (NEW)

Hermetic test simulating a terminal-gate run with three stub reviewer agents:
- All three Task invocations are spawned in a single orchestrator turn (assert via the test harness's spawn-call recorder that the three calls happen with no intervening assistant turn).
- Each fragment file lands at the expected path.
- Orchestrator reads the three fragments and stitches into the issue file in one Edit pass.
- Final issue file contains all three `## ... review` sections in the expected order.

### Wall-clock benchmark

Add `tests/orchestrator/bench_terminal_gate.py` (run manually, not in CI). Compare:
- Old serial gate: time from start-of-sr-dev-spawn to end-of-security-spawn.
- New parallel gate: time from start-of-multi-spawn to end-of-stitch.

Fixture: a frozen issue file from M12 T03 (the most recent multi-reviewer run). Assert post-T05 wall-clock ≤ 0.6 × pre-T05 (i.e. ≥ 1.67× improvement; 2× is the goal but 1.67× is the bar — wall-clock includes the stitch overhead which is small but real).

## Acceptance criteria

1. `.claude/commands/auto-implement.md` describes the parallel-spawn-with-fragment-files terminal gate.
2. The 3 reviewer agent files (`sr-dev.md`, `sr-sdet.md`, `security-reviewer.md`) write to `runs/<task>/<cycle>/<agent>-review.md` instead of editing the issue file directly.
3. `.claude/commands/_common/parallel_spawn_pattern.md` exists.
4. `tests/orchestrator/test_parallel_terminal_gate.py` passes — single-turn spawn assertion + fragment-file-landing + stitch-pass assertions.
5. Wall-clock benchmark shows ≥ 1.67× improvement over the serial baseline (frozen M12 T03 fixture). 2× is the goal.
6. CHANGELOG.md updated under `[Unreleased]` with `### Changed — M20 Task 05: Parallel terminal gate (sr-dev + sr-sdet + security-reviewer in single multi-Task message; fragment files; research brief §Lens 1.4)`.
7. Status surfaces flip together.

## Smoke test (Auditor runs)

```bash
# Verify auto-implement describes parallel-spawn pattern
grep -q "parallel.*terminal gate\|three Task tool calls" .claude/commands/auto-implement.md && echo "auto-implement OK"

# Verify each reviewer agent writes to fragment path
for agent in sr-dev sr-sdet security-reviewer; do
  grep -q "runs/.*<cycle>.*review.md\|runs/<task>/<cycle>/" .claude/agents/$agent.md \
    && echo "$agent OK" \
    || { echo "$agent FAIL"; exit 1; }
done

# Run parallel-gate test
uv run pytest tests/orchestrator/test_parallel_terminal_gate.py -v

# Optional: wall-clock benchmark (not in CI)
uv run pytest tests/orchestrator/bench_terminal_gate.py -v
```

## Out of scope

- **Parallel Builders** — that's M21 T17/T18/T19 scope. T05 is reviewer-only parallelism.
- **Architect agent in the parallel batch** — architect is invoked on-demand at autonomy-loop boundaries (Trigger A or B per its agent file), not per-cycle. Adding it to the parallel batch would break that invariant.
- **dependency-auditor in the parallel batch** — it runs only when `pyproject.toml` / `uv.lock` changes (per CLAUDE.md). Conditional spawn doesn't fit cleanly into the unconditional 3-way parallel pattern; keep it conditional and serial.
- **Auditor in the parallel batch** — auditor is the *driver* of the terminal-gate decision (its PASS verdict precedes the gate). The terminal gate runs *after* auditor reaches FUNCTIONALLY CLEAN, then runs the three reviewers in parallel. Auditor stays serial to the reviewers.
- **Hard concurrency cap** — Claude Code caps practical sub-agent concurrency at ~7 (research brief §Lens 1.4). T05 spawns 3, well under the cap. Future extensions (e.g. a 5-reviewer panel) should respect this cap.

## Dependencies

- **T01** (return-value schema) — strongly precedent. T05's stitch step parses each agent's T01 return; the fragment-file format reuses T01's `file:` and `section:` semantics.

## Carry-over from prior milestones

*None.*

## Carry-over from task analysis

(populated by `/clean-tasks m20`)

## Carry-over from prior audits

(populated by `/clean-implement` audit cycles)
