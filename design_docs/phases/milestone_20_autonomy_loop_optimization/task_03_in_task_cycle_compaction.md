# Task 03 — In-task cycle compaction (`cycle_summary.md` per Auditor)

**Status:** 📝 Planned.
**Grounding:** [milestone README](README.md) · [research brief `research_analysis` §Lens 2.1 (Anthropic 3-primitive memory model)](research_analysis) · memory `project_autonomy_optimization_followups.md` thread #9 · [`.claude/agents/auditor.md`](../../../.claude/agents/auditor.md) · [`.claude/commands/auto-implement.md`](../../../.claude/commands/auto-implement.md) · [`.claude/commands/clean-implement.md`](../../../.claude/commands/clean-implement.md).

## What to Build

Eliminate the **quadratic context growth** within a single `/auto-implement` task across cycles 1..N. Today the orchestrator carries the full text of every Builder report and every Auditor verdict from cycles 1..N-1 into cycle N's spawn prompts. After 5 cycles the orchestrator's per-cycle input is ~5× cycle 1's. M20 T03 replaces this with a **structured per-cycle summary** (`runs/<task>/cycle_<N>_summary.md`) emitted by the Auditor at the end of each cycle. The orchestrator reads only the *latest* summary into cycle N+1's spawn prompt, not the chat history of cycles 1..N-1.

This implements Anthropic's **note-taking memory primitive** (research brief Lens 2.1) at per-cycle granularity. The summary is the durable record; chat history is ephemeral. Combined with T01 (3-line return schema, no chat-summary bodies) and T02 (orchestrator-side input prune), the orchestrator's per-cycle input becomes **roughly constant** instead of linear-in-cycle-count.

## Cycle-summary structure

Per the research brief (Lens 2.1, citing Anthropic's compaction-prompt cookbook): "maximize recall first, then iteratively prune for precision." Cycle summaries are written as:

```markdown
# Cycle <N> summary — Task <NN>

**Cycle:** N
**Date:** YYYY-MM-DD
**Builder verdict:** <BUILT | BLOCKED | STOP-AND-ASK>
**Auditor verdict:** <PASS | OPEN | BLOCKED>
**Files changed this cycle:** <list>
**Gates run this cycle:** <table — gate command + pass/fail>
**Open issues at end of cycle:** <count by severity + IDs>
**Decisions locked this cycle:** <bullet list — Auditor-agreement-bypass locks, user arbitrations, KDR carry-overs>
**Carry-over to next cycle:** <list of explicit ACs the next Builder cycle must satisfy>
```

Auditor writes this as a side-effect of its existing per-cycle work (the issue file already has all of this content; the summary is a structured projection of it). Orchestrator reads the summary on cycle N+1's Builder spawn instead of the full Builder+Auditor chat from cycle N.

## Deliverables

### `.claude/agents/auditor.md` — emit `cycle_summary.md` as final phase

Add a new "Phase 7 — Cycle summary" section after the existing audit phases. Auditor writes `runs/<task>/cycle_<N>_summary.md` using the structure above as the *last* action of every cycle. The summary's content is derived from the issue file the Auditor already wrote; this is a projection, not new work.

### `.claude/commands/auto-implement.md` — read-only-latest-summary rule

Update the loop's per-cycle Builder spawn template:
- Cycle 1: spawn-prompt input = task spec + parent milestone README + project context brief (existing).
- Cycle N (N ≥ 2): spawn-prompt input = task spec + issue file + **most recent `cycle_summary.md`** + project context brief. **Do not include** prior Builder reports' chat content; the summary is the durable carry-forward.

Same rule for cycle-N Auditor spawns: feed the latest cycle_summary.md, not full chat history.

### `.claude/commands/clean-implement.md` — same pattern

The non-autonomous variant of the Builder→Auditor loop also benefits.

### `runs/<task>/` directory convention

Specify the structure:
```
runs/<task-shorthand>/
  cycle_1_summary.md
  cycle_2_summary.md
  ...
  agent_<name>_raw_return.txt   (T01)
  spawn_<agent>_<cycle>.tokens.txt   (T02)
```

`<task-shorthand>` is `m<N>_t<NN>` (e.g. `m20_t01`). Directory creation handled by the orchestrator on cycle 1; subsequent cycles append.

## Tests

### `tests/orchestrator/test_cycle_summary_emission.py` (NEW)

Hermetic test that simulates a 3-cycle Builder→Auditor loop with a stub Auditor agent. Asserts:
- After cycle 1: `runs/<task>/cycle_1_summary.md` exists, parses to the expected structure.
- After cycle 2: `cycle_2_summary.md` exists; cycle_1_summary.md unchanged.
- After cycle 3: `cycle_3_summary.md` exists.
- Each summary's `Carry-over to next cycle:` section is populated when the Auditor verdict was OPEN.

### `tests/orchestrator/test_cycle_context_constant.py` (NEW)

Hermetic test that constructs cycle-N Builder spawn prompts for cycles 1, 2, 3 and asserts:
- Cycle 2's input-token-count ≈ cycle 1's (within 10 %).
- Cycle 3's input-token-count ≈ cycle 1's (within 10 %).
- The orchestrator does **not** include cycle 1's Builder report in cycle 3's spawn prompt (grep-style assertion against the constructed prompt).

## Acceptance criteria

1. `.claude/agents/auditor.md` instructs the Auditor to emit `cycle_summary.md` as Phase 7 of every cycle.
2. `cycle_summary.md` template structure documented in the Auditor agent file (or referenced from `_common/cycle_summary_template.md` if shared with future commands).
3. `.claude/commands/auto-implement.md` and `.claude/commands/clean-implement.md` describe the read-only-latest-summary rule for cycle-N spawns.
4. `runs/<task>/` directory convention documented in the orchestrator command files; directory creation lands on cycle 1.
5. `tests/orchestrator/test_cycle_summary_emission.py` passes for the 3-cycle simulation.
6. `tests/orchestrator/test_cycle_context_constant.py` passes — cycle-N input size is within 10 % of cycle 1's.
7. Validation re-run: re-execute a fixture of the M12 T03 3-cycle loop with T03's compaction in place; assert cycle-3 orchestrator-context size matches cycle-1 size.
8. CHANGELOG.md updated under `[Unreleased]` with `### Changed — M20 Task 03: In-task cycle compaction (cycle_summary.md per Auditor; constant per-cycle orchestrator context; research brief §Lens 2.1)`.
9. Status surfaces flip together.

## Smoke test (Auditor runs)

```bash
# Verify Auditor agent has the Phase 7 cycle-summary section
grep -q "Phase 7 — Cycle summary" .claude/agents/auditor.md && echo "auditor Phase 7 OK"

# Verify orchestrator commands describe the read-only-latest-summary rule
for cmd in auto-implement clean-implement; do
  grep -q "cycle_summary.md" .claude/commands/$cmd.md \
    && echo "$cmd OK" \
    || { echo "$cmd FAIL"; exit 1; }
done

# Run cycle-summary + context-constant tests
uv run pytest tests/orchestrator/test_cycle_summary_emission.py tests/orchestrator/test_cycle_context_constant.py -v
```

## Out of scope

- **Cross-task compaction** — T04's scope. T03 is intra-task only.
- **Server-side `compact_20260112` strategy** — T28's evaluation scope. File-based summaries are the auditable durable record per memory `project_autonomy_optimization_followups.md` thread #9; T28 evaluates whether server-side compaction *composes* alongside T03, not replaces it.
- **Modifying the Auditor's existing audit phases** — T03 only adds Phase 7. Phases 1–6 (design-drift check, gate re-run, AC grading, critical sweep, issue-file write, forward-deferral propagation) are unchanged.
- **Cycle-summary as the only memory mechanism** — the issue file remains the authoritative artifact. cycle_summary.md is a structured projection of the issue file's per-cycle delta, optimised for orchestrator re-read; the issue file is the one humans + future agents read for full detail.

## Dependencies

- **T01** (return-value schema) — non-blocking but tightly related. The cycle_summary.md template references T01's verdict tokens.

## Carry-over from prior milestones

*None.*

## Carry-over from task analysis

(populated by `/clean-tasks m20`)

## Carry-over from prior audits

(populated by `/clean-implement` audit cycles)
