# Task 04 — Cross-task iteration compaction (`iter_<N>_shipped.md` at autopilot iteration boundaries)

**Status:** 📝 Planned.
**Kind:** Compaction / doc + code.
**Grounding:** [milestone README](README.md) · [research brief `research_analysis` §Lens 2.1](research_analysis) · memory `project_autonomy_optimization_followups.md` thread #13 · [`.claude/commands/autopilot.md`](../../../.claude/commands/autopilot.md) · sibling [task_03](task_03_in_task_cycle_compaction.md) (in-task version of the same pattern).

## What to Build

Eliminate the **quadratic context growth** across iterations of a single `/autopilot` queue-drain run. Today an autopilot run that ships tasks T01, T02, T03 carries the full text of T01's and T02's iteration history into T03's iteration. By T05 the orchestrator's input is bloated with 4 prior iterations of dialogue that aren't load-bearing — the durable state lives on disk (commits, issue files, recommendation files).

T04 emits a structured **iteration-shipped artifact** (`runs/autopilot-<run-ts>-iter<N>-shipped.md`) at each autopilot iteration boundary. The orchestrator treats prior iterations' chat history as *compacted-to-this-summary* on the next iteration's `Step A` (queue-pick spawn). T04 is the cross-task analogue of T03's in-task compaction.

## Iteration-shipped artifact structure

```markdown
# Autopilot iter <N> — shipped

**Run timestamp:** <YYYY-MM-DDTHHMMSSZ>
**Iteration:** N
**Date:** YYYY-MM-DD
**Verdict from queue-pick:** <PROCEED | NEEDS-CLEAN-TASKS | HALT-AND-ASK>

## Task shipped (if PROCEED)
- **Task:** <milestone>/<task spec filename>
- **Cycles:** N
- **Final commit:** <sha> on `design_branch`
- **Files touched:** <list>
- **Auditor verdict:** PASS
- **Reviewer verdicts:** sr-dev=<verdict>, sr-sdet=<verdict>, security=<verdict>, dependency=<verdict>
- **KDR additions (if any):** <KDR-XXX + ADR-NNNN, isolated commit sha>

## Milestone work (if NEEDS-CLEAN-TASKS)
- **Milestone:** <milestone>
- **/clean-tasks rounds:** N
- **Final stop verdict:** <CLEAN | LOW-ONLY>
- **Specs hardened:** <list of task spec filenames>

## Halt (if HALT-AND-ASK)
- **Halt reason:** <one paragraph>
- **State preserved:** <list of uncommitted files>
- **User-arbitration question(s):** <bullet list>

## Carry-over to next iteration
- *(empty for routine iterations; populated when a finding from this iteration affects the next task)*

## Telemetry summary
- *(retrofitted by T22 when it lands; T04 ships before T22 in Phase A vs Phase C — leave this section empty at T04 land time, per audit M15)*
```

## Deliverables

### `.claude/commands/autopilot.md` — emit `iter_<N>_shipped.md` at iteration boundary

Update `/autopilot`'s outer-loop Step D (iteration close) to write the iteration-shipped artifact at `runs/autopilot-<run-ts>-iter<N>-shipped.md`. The artifact's content is derived from the iteration's existing recommendation file (`runs/autopilot-<run-ts>-iter<N>.md` — already produced today) plus the iteration's commit log and the per-cycle summaries from T03.

### `.claude/commands/autopilot.md` — read-only-latest-shipped rule on iteration N+1 Step A

Update outer-loop Step A (start of each new iteration). Cycle N+1's queue-pick spawn:
- Reads project memory (existing).
- Reads the most recent `iter_<M>_shipped.md` for context on what the prior iteration delivered (M = N for the just-completed iteration).
- **Does not** carry the prior iteration's chat history into the queue-pick spawn.

This is the cross-task analogue of T03's read-only-latest-cycle-summary rule.

### Path convention — flat hyphenated (matches today's autopilot.md; no migration scope per round-2 user arbitration)

Each iteration emits its close-out artifact at `runs/autopilot-<run-ts>-iter<N>-shipped.md` as a sibling to today's existing kick-off recommendation file `runs/autopilot-<run-ts>-iter<N>.md` (already produced by autopilot.md line 66 today). Pattern:

```
runs/
  autopilot-20260427T152243Z-iter1.md            (existing — recommendation file, queue-pick output)
  autopilot-20260427T152243Z-iter1-shipped.md    (NEW — close-out artifact, T04)
  autopilot-20260427T152243Z-iter2.md
  autopilot-20260427T152243Z-iter2-shipped.md
  ...
```

The `-shipped.md` suffix distinguishes close-out from kick-off. Both files have read-only semantics after iteration close. **No directory-grouping** — flat layout with run-timestamp + iter-number in the filename matches today's autopilot.md convention (no migration of existing recommendation-file paths needed).

## Tests

### `tests/orchestrator/test_iter_shipped_emission.py` (NEW)

Hermetic test simulating a 3-iteration autopilot run with stub queue-pick + Builder + Auditor agents. Asserts:
- After iter 1: `iter_1_shipped.md` exists; parses to expected structure with the verdict + commit sha + reviewer verdicts.
- After iter 2: `iter_2_shipped.md` exists; iter_1_shipped.md unchanged.
- After iter 3: `iter_3_shipped.md` exists.

### `tests/orchestrator/test_cross_task_context_constant.py` (NEW)

Hermetic test that constructs iter-N queue-pick spawn prompts for iters 1, 2, 3, 4, 5 and asserts:
- Iter 2's input-token-count ≈ iter 1's (within 10 %).
- Iter 5's input-token-count ≈ iter 1's (within 10 %).
- The orchestrator does **not** include iter 1's chat history in iter 5's spawn prompt.

## Acceptance criteria

1. `.claude/commands/autopilot.md` outer-loop Step D writes `iter_<N>_shipped.md` per the structure above.
2. `.claude/commands/autopilot.md` outer-loop Step A reads only the latest `iter_<M>_shipped.md` plus project memory; does not carry prior-iteration chat history.
3. `runs/autopilot-<run-ts>/` directory convention documented in `autopilot.md`.
4. `tests/orchestrator/test_iter_shipped_emission.py` passes for the 3-iteration simulation.
5. `tests/orchestrator/test_cross_task_context_constant.py` passes — iter-5 input size is within 10 % of iter-1 size.
6. Validation re-run: re-execute a fixture of the M12 4-iteration autopilot run with T04's compaction in place; assert iter-4 orchestrator-context matches iter-1.
7. CHANGELOG.md updated under `[Unreleased]` with `### Changed — M20 Task 04: Cross-task iteration compaction (iter_<N>_shipped.md per autopilot iteration; constant cross-task orchestrator context; research brief §Lens 2.1)`.
8. Status surfaces flip together.

## Smoke test (Auditor runs)

```bash
# Verify autopilot describes iter_<N>_shipped emission
grep -q "iter_<N>_shipped.md" .claude/commands/autopilot.md && echo "autopilot emit OK"

# Verify autopilot describes the read-only-latest-shipped rule
grep -q "iter_<N>_shipped" .claude/commands/autopilot.md && echo "autopilot read OK"

# Run cross-task tests
uv run pytest tests/orchestrator/test_iter_shipped_emission.py tests/orchestrator/test_cross_task_context_constant.py -v
```

## Out of scope

- **In-task cycle compaction** — T03's scope.
- **Replacing the iter_<N>.md recommendation files** — those are kick-off artifacts (queue-pick output); `iter_<N>_shipped.md` is a separate close-out artifact. Both are kept.
- **Cross-run compaction (autopilot run M into autopilot run N)** — out of scope. Each autopilot run starts fresh; cross-run continuity is handled by project memory (`MEMORY.md`), not by iteration-shipped artifacts.
- **Server-side compaction at iteration boundary** — that's T28's evaluation scope.
- **Native Claude Code `/compact` invocation between iterations** — explicitly rejected per memory `project_autonomy_optimization_followups.md` thread #13: "(b) Native compaction is opaque and depends on Claude Code's compaction heuristics; (a) file-based summary is preferred because it's deterministic and produces auditable artifacts."

## Dependencies

- **T03** (in-task cycle compaction) — non-blocking but synergistic. T04's iteration-shipped artifact references the per-cycle summaries T03 produces.

## Carry-over from prior milestones

*None.*

## Carry-over from task analysis

- **L3 (round 1, 2026-04-27):** The `(within 10 %)` cross-task test threshold is the same heuristic as T03's L2. Document as heuristic, not empirical bound. T22's actual baseline measurement may revise.
- **L2 (round 3, 2026-04-27):** AC #3 references "`runs/autopilot-<run-ts>/` directory convention documented in autopilot.md" — but the round-2 M5 fix pinned flat hyphenated paths (no per-run subdirectory). Reword AC #3 to: "Path naming convention (`runs/autopilot-<run-ts>-iter<N>(-shipped)?.md`) documented in autopilot.md per §Path convention."

## Carry-over from prior audits

(populated by `/clean-implement` audit cycles)
