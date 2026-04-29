# Task 05 — Parallel unified terminal gate (sr-dev + sr-sdet + security-reviewer in one message)

**Status:** ✅ Done (2026-04-28).
**Kind:** Performance / doc + code.
**Grounding:** [milestone README](README.md) · [research brief `research_analysis` §Lens 1.4 (parallel sub-agent dispatch)](research_analysis.md) · memory `project_autonomy_optimization_followups.md` thread #14 · [`.claude/commands/auto-implement.md`](../../../.claude/commands/auto-implement.md) (today's two-gate flow: Security gate at line 121, Team gate at line 149) · [`.claude/agents/sr-dev.md`](../../../.claude/agents/sr-dev.md) · [`.claude/agents/sr-sdet.md`](../../../.claude/agents/sr-sdet.md) · [`.claude/agents/security-reviewer.md`](../../../.claude/agents/security-reviewer.md) · sibling [task_01](task_01_sub_agent_return_value_schema.md) (fragment-file format reuses T01's 3-line schema).

## What to Build

Replace `/auto-implement`'s **two-gate sequential structure** (Security gate first → Team gate second) with **one unified terminal gate** that spawns sr-dev + sr-sdet + security-reviewer concurrently in a single orchestrator message. Today's flow:

- **Security gate** (auto-implement.md line 121): Step S1 spawns `security-reviewer`; Step S2 conditionally spawns `dependency-auditor`. Runs FIRST after FUNCTIONALLY CLEAN.
- **Team gate** (line 149): Step T1 spawns `sr-dev`; Step T2 spawns `sr-sdet`; Step T3 conditionally spawns `architect`. Runs SECOND after SECURITY CLEAN.

T05's design (per user arbitration, audit recommendation H2 Option A) consolidates the security-reviewer's invocation into the same parallel batch as sr-dev + sr-sdet. **Old SECURITY CLEAN → TEAM CLEAN sequencing is replaced by a single TERMINAL CLEAN stop condition.** dependency-auditor and architect retain their conditional + standalone semantics (see §Conditional spawns below).

Per the research brief §Lens 1.4: parallel sub-agent dispatch works when (a) ≥ 3 unrelated tasks, (b) no shared state, (c) clear non-overlapping file boundaries, (d) independent verification. The unified terminal gate satisfies all four — sr-dev grades code quality, sr-sdet grades test quality, security-reviewer grades the threat-model surface; none depend on the others' output.

**Wall-clock target: ≥ 2× improvement** vs today's two-gate serial flow. Sum-of-three becomes max-of-three.

## Stop-condition precedence rule (new — replaces SECURITY CLEAN / TEAM CLEAN)

After all three reviewers return their T01 verdict lines:

| Reviewer combination | Stop condition | Action |
| --- | --- | --- |
| All three SHIP | TERMINAL CLEAN | Proceed to pre-commit ceremony (T09) → AUTO-CLEAN stamp |
| Any reviewer BLOCK | TERMINAL BLOCK | Halt loop; surface the BLOCK finding verbatim. **security-reviewer BLOCK takes precedence over sr-dev/sr-sdet SHIP** when surfacing reason (the threat-model finding is the most user-load-bearing) |
| Any reviewer FIX-THEN-SHIP (no BLOCK) | TERMINAL FIX | Halt loop; surface all FIX-THEN-SHIP findings for user arbitration |

The precedence rule resolves the question "what happens when security-reviewer says BLOCK while sr-dev says SHIP?" — the orchestrator halts and surfaces the security finding first. (Today's two-gate flow halts at the Security gate boundary before reaching the Team gate, achieving the same precedence implicitly. The unified gate makes precedence explicit.)

## Conditional spawns (preserved)

- **dependency-auditor** stays **conditional + standalone**, not in the parallel batch. It runs only when `pyproject.toml` or `uv.lock` change in the cycle's diff (existing CLAUDE.md non-negotiable). Spawn synchronously after the parallel batch returns; runs in series before the precedence rule evaluates. If dependency-auditor returns BLOCK, surface ahead of any FIX-THEN-SHIP from the parallel batch (dependency-auditor BLOCK is supply-chain-shaped — same precedence weight as security-reviewer BLOCK).
- **architect** stays **conditional + standalone** (Trigger A or B per its agent file). Not in the parallel batch.

## Mechanism — fragment files (per research brief §Lens 1.4)

Each parallel reviewer writes its verdict to a deterministic fragment path instead of editing the issue file directly:

- sr-dev → `runs/<task>/cycle_<N>/sr-dev-review.md`
- sr-sdet → `runs/<task>/cycle_<N>/sr-sdet-review.md`
- security-reviewer → `runs/<task>/cycle_<N>/security-review.md`

(Path convention matches T03's directory layout per audit M11. `<task>` is the zero-padded `m<MM>_t<NN>` shorthand per audit M12.)

This avoids file-write contention on the issue file. The three reviewers run truly concurrently; no Edit-collision races. After all three return, the orchestrator reads the three fragment files in one Read pass and stitches them into the issue file under their respective `## Sr. Dev review`, `## Sr. SDET review`, `## Security review` sections in one Edit pass.

The Read tool's "Read multiple files at once" pattern (one tool message, multiple Read invocations) keeps the stitch step single-turn.

## Reviewer-agent updates

Each of the three reviewer agent files updates its `## Output format` section:

- **Old:** "Append to the existing issue file under a `## <name> review` section."
- **New:** "Write your full review to `runs/<task>/cycle_<N>/<agent>-review.md` (where `<task>` is the zero-padded `m<MM>_t<NN>` shorthand per audit M12 and `cycle_<N>/` is the per-cycle subdirectory per audit M11). The orchestrator stitches it into the issue file in a follow-up turn. Your `## Return to invoker` value (T01) points `file:` at the fragment path; `section:` is the `## <name> review` heading the orchestrator will use when stitching."

The fragment file's content is identical to today's `## <name> review` section content (verdict + critical/high/advisory tiers + reviewer-passed-review per-lens). Only the destination changes.

## Deliverables

### `.claude/commands/auto-implement.md` — replace two-gate flow with unified gate

**Delete** the existing Security gate section (Step S1 + Step S2 + SECURITY CLEAN stop condition, around line 121) and the existing Team gate section (Step T1 + Step T2 + Step T3 + TEAM CLEAN stop condition, around line 149). **Replace** with a single Terminal gate section:

```markdown
### Step <N> — Unified terminal gate (parallel)

Spawn sr-dev, sr-sdet, and security-reviewer concurrently in a single
orchestrator message (three Task tool calls in one assistant turn).
Each agent writes its review to `runs/<task>/cycle_<N>/<agent>-review.md`
per the agent's updated `## Output format`.

Wait for all three Tasks to complete. Then in a follow-up turn:

1. Read the three fragment files in one Read multi-call.
2. Parse each agent's T01 return-schema verdict line.
3. Apply the precedence rule (per T05 spec):
   - All three SHIP → TERMINAL CLEAN; proceed.
   - Any BLOCK → TERMINAL BLOCK; halt with security-reviewer BLOCK
     surfaced first if applicable, else the offending reviewer's
     BLOCK verbatim.
   - Any FIX-THEN-SHIP (no BLOCK) → TERMINAL FIX; halt for user
     arbitration with all FIX findings surfaced.
4. If TERMINAL CLEAN: stitch the three fragment files into the issue
   file under `## Sr. Dev review`, `## Sr. SDET review`, `## Security
   review` sections in one Edit pass.
5. Conditional dependency-auditor spawn (synchronous, after the
   parallel batch): only if `pyproject.toml` or `uv.lock` changed in
   the cycle's diff. dependency-auditor BLOCK has same precedence
   weight as security-reviewer BLOCK.
6. Conditional architect spawn (Trigger A / B): existing on-demand
   flow, unchanged.

Stop conditions for this step replace the prior SECURITY CLEAN /
TEAM CLEAN stops. The single TERMINAL CLEAN gate hands off to the
pre-commit ceremony (T09) when satisfied.
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

1. `.claude/commands/auto-implement.md` describes the unified terminal gate replacing the two-gate (Security + Team) flow. The old Security gate + Team gate sections are deleted; the single Terminal gate section lands.
2. The unified gate's precedence rule (TERMINAL CLEAN / TERMINAL BLOCK with security-reviewer-precedence / TERMINAL FIX) is documented in `auto-implement.md` and matches §Stop-condition precedence rule above.
3. The 3 reviewer agent files (`sr-dev.md`, `sr-sdet.md`, `security-reviewer.md`) write to `runs/<task>/cycle_<N>/<agent>-review.md` instead of editing the issue file directly.
4. dependency-auditor stays conditional + standalone (post-parallel-batch); architect stays conditional + standalone (on-demand). Verified in `auto-implement.md`.
5. `.claude/commands/_common/parallel_spawn_pattern.md` exists.
6. `tests/orchestrator/test_parallel_terminal_gate.py` passes — single-turn spawn assertion + fragment-file-landing + stitch-pass assertions + precedence-rule-correctness assertions (BLOCK > FIX-THEN-SHIP > SHIP; security-reviewer BLOCK surfaced first).
7. Wall-clock benchmark shows ≥ 2× improvement over the two-gate serial baseline (frozen M12 T03 fixture).
8. CHANGELOG.md updated under `[Unreleased]` with `### Changed — M20 Task 05: Unified parallel terminal gate (sr-dev + sr-sdet + security-reviewer in single multi-Task message; fragment files; replaces two-gate Security+Team flow with single TERMINAL CLEAN/BLOCK/FIX precedence rule; research brief §Lens 1.4)`.
9. Status surfaces flip together.

## Smoke test (Auditor runs)

```bash
# Verify auto-implement describes parallel-spawn pattern
grep -q "parallel.*terminal gate\|three Task tool calls" .claude/commands/auto-implement.md && echo "auto-implement OK"

# Verify each reviewer agent writes to fragment path
# Explicit file list per CLAUDE.md verification-discipline.
grep -lE "runs/.*cycle_<N>.*review.md|runs/<task>/cycle_<N>/" \
  .claude/agents/sr-dev.md \
  .claude/agents/sr-sdet.md \
  .claude/agents/security-reviewer.md \
  | wc -l
# Expected: 3

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

- **T01** (return-value schema) — **blocking**. T05's stitch step parses each agent's T01 return; the fragment-file format reuses T01's `file:` and `section:` semantics. Per audit M2, T01 is content-blocking for T05 (without T01's schema landed, T05 has no definite contract to depend on).

## Carry-over from prior milestones

*None.*

## Carry-over from task analysis

- **L4 (round 1, 2026-04-27):** The wall-clock benchmark `bench_terminal_gate.py` lands but is "not in CI" — needs an explicit invocation hook. Add `@pytest.mark.benchmark` decorator + register the `benchmark` marker in `pyproject.toml` `[tool.pytest.ini_options]` markers block. Then `uv run pytest -m benchmark` runs benchmarks on demand. Without a marker the file becomes forgotten.
- **L2 (round 2, 2026-04-27):** Tighten the smoke-test grep at line 158 to pin the `cycle_<N>/` form (`grep -q "runs/.*cycle_<N>.*review.md\|runs/<task>/cycle_<N>/"`). Already applied inline by H2; flagged here in case future drift re-introduces the legacy `<cycle>` shorthand.

## Carry-over from prior audits

(populated by `/clean-implement` audit cycles)
