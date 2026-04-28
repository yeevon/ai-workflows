# Task 20 — Carry-over checkbox-cargo-cult catch (extended detection)

**Status:** 📝 Planned.
**Grounding:** [milestone README](README.md) · memory `project_autonomy_optimization_followups.md` thread #5 (post-M12-T01 lesson) · [`.claude/agents/auditor.md`](../../../.claude/agents/auditor.md) · template equivalent in [`/home/papa-jochy/prj/ai-workflows-template/template/.claude/agents/auditor.md`](../../../../ai-workflows-template/template/.claude/agents/auditor.md).

## What to Build

Extend the existing carry-over checkbox-cargo-cult catch (added to template auditor 2026-04-27 post-M12-T01) into a **broader anti-cargo-cult inspection** that catches three failure modes the autonomy loop has surfaced or is at risk of surfacing:

1. **Checkbox marked done without diff/test.** Existing M12-T01 catch — Builder ticks `[x]` in the spec's carry-over section but no corresponding code change appears in the diff. Already in template; needs to ship to live ai-workflows agent + extended.
2. **Two consecutive cycles producing near-identical output.** A spinning loop where the Builder makes superficial changes (e.g. tweaking a comment) cycle after cycle, the Auditor flags new MEDIUMs that resemble prior cycles' MEDIUMs, and progress stalls invisibly. Detect by diffing cycle N's Auditor issue file against cycle N-1's; if the new findings overlap >70% with the prior cycle's, flag as suspicious.
3. **Auditor rubber-stamping pattern.** Auditor returns PASS without raising any HIGH or MEDIUM findings on a cycle that produced substantive code changes. Either the code is genuinely clean (rare) or the Auditor is rubber-stamping. Detect by: PASS verdict + non-trivial diff + zero HIGH+MEDIUM findings → flag as warranting human review of the Auditor's reasoning.

T20 ports the M12-T01 patch from the template into the live ai-workflows auditor + extends with detection (2) + (3).

## Mechanism

Each detection is a small inspection the Auditor runs as part of its existing per-cycle work:

1. **(1) Diff-vs-checkbox cross-reference.** Before grading ACs as `met`, the Auditor diffs the spec's carry-over checkbox state against `git log -p` for the cycle's commits. Each newly-checked carry-over item must have a corresponding diff hunk that addresses it. Already in template; T20 ships to live + adds an explicit failure surface (HIGH finding "carry-over <ID> checked without corresponding diff").

2. **(2) Cycle-N-vs-cycle-(N-1) finding-overlap detection.** New Auditor phase: read cycle (N-1)'s issue file (if exists). Compute Jaccard overlap between cycle N's findings and cycle (N-1)'s findings (by finding-title fuzzy match). If overlap > 70 % → new MEDIUM finding "cycle-N findings substantially overlap cycle-(N-1) — loop may be spinning; recommend human review."

3. **(3) Rubber-stamp detection.** New Auditor phase: when verdict is `PASS` and the cycle's diff exceeds N lines (threshold: 50 lines) AND zero HIGH+MEDIUM findings landed → emit a meta-finding (severity: ADVISORY) "Auditor verdict PASS with substantial diff and no findings — verify the Auditor's reasoning on critical sweep."

## Deliverables

### `.claude/agents/auditor.md` — three new inspections

Add a new "Phase 4.5 — Anti-cargo-cult inspections" section between the existing Phase 4 (critical sweep) and Phase 5 (issue-file write). Lists the three inspections with their failure surfaces.

### `.claude/agents/auditor.md` — port the M12-T01 carry-over patch

Verify the M12-T01 patch is in the live auditor file (it was added to the *template* but possibly held back from live during the M12 autopilot session — see memory thread #5: "carry-over checkbox-cargo-cult catch has been added to both projects' auditor.md (post-M12-T01 lesson)"). Confirm by grep; if missing, port from template.

### `tests/agents/test_auditor_anti_cargo_cult.py` (NEW)

Hermetic test fixtures:
- Carry-over `[x]` without diff hunk → HIGH finding fires.
- Cycle-N findings 80% overlap with cycle-(N-1) → MEDIUM "loop may be spinning" finding fires.
- PASS verdict + 100-line diff + zero findings → ADVISORY "verify reasoning" finding fires.
- All three counter-examples (legitimate clean code, novel findings, no overlap) → no false positives.

## Acceptance criteria

1. `.claude/agents/auditor.md` has Phase 4.5 with the three inspections.
2. The M12-T01 carry-over patch is confirmed live (not just template).
3. Each inspection has its failure surface specified (HIGH / MEDIUM / ADVISORY).
4. `tests/agents/test_auditor_anti_cargo_cult.py` passes — true-positives + true-negatives.
5. CHANGELOG.md updated under `[Unreleased]` with `### Changed — M20 Task 20: Auditor anti-cargo-cult inspections (carry-over diff cross-ref + cycle-N overlap + rubber-stamp detection)`.
6. Status surfaces flip together.

## Smoke test (Auditor runs)

```bash
# Verify Phase 4.5 lands
grep -q "Phase 4.5\|Anti-cargo-cult inspections" .claude/agents/auditor.md && echo "Phase 4.5 OK"

# Verify M12-T01 carry-over patch is live
grep -q "carry-over.*checkbox\|carry-over.*diff" .claude/agents/auditor.md && echo "M12-T01 patch live"

# Run anti-cargo-cult tests
uv run pytest tests/agents/test_auditor_anti_cargo_cult.py -v
```

## Out of scope

- **Auto-corrective action on rubber-stamp detection** — T20 surfaces the finding; user investigates. Auto-spawning a second Auditor at a heavier model would be over-engineering for what's an advisory-tier signal.
- **Real-time cross-cycle drift detection** during a cycle — T20 runs at end-of-cycle. Mid-cycle detection is unnecessary complexity.
- **Cross-task cargo-cult patterns** — out of scope for M20. A future M21 task could detect "this autopilot run keeps producing tasks with the same carry-over IDs," but that's productivity not optimization.
- **Auditor-on-Auditor detection** — out of scope. T20's mechanism is structural pattern detection (file-diff-based), not meta-reasoning about the Auditor's reasoning quality.

## Dependencies

- **T03** (cycle_summary.md) — non-blocking but synergistic. T20's cycle-N-vs-(N-1) overlap check can read either the issue file (today's source) or T03's cycle_summary.md (T03's structured projection); the latter is easier to parse.

## Carry-over from prior milestones

- **From M12 close-out** — the M12-T01 lesson (carry-over without diff). Patched into template 2026-04-27; T20 ships to live + extends.

## Carry-over from task analysis

(populated by `/clean-tasks m20`)

## Carry-over from prior audits

(populated by `/clean-implement` audit cycles)
