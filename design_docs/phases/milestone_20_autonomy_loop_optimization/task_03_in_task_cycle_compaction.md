# Task 03 — In-task cycle compaction (`cycle_<N>/summary.md` per Auditor)

**Status:** 📝 Planned.
**Kind:** Compaction / doc + code.
**Grounding:** [milestone README](README.md) · [research brief `research_analysis` §Lens 2.1 (Anthropic 3-primitive memory model)](research_analysis) · memory `project_autonomy_optimization_followups.md` thread #9 · [`.claude/agents/auditor.md`](../../../.claude/agents/auditor.md) · [`.claude/commands/auto-implement.md`](../../../.claude/commands/auto-implement.md) · [`.claude/commands/clean-implement.md`](../../../.claude/commands/clean-implement.md).

## What to Build

Eliminate the **quadratic context growth** within a single `/auto-implement` task across cycles 1..N. Today the orchestrator carries the full text of every Builder report and every Auditor verdict from cycles 1..N-1 into cycle N's spawn prompts. After 5 cycles the orchestrator's per-cycle input is ~5× cycle 1's. M20 T03 replaces this with a **structured per-cycle summary** (`runs/<task>/cycle_<N>/summary.md`) emitted by the Auditor at the end of each cycle. The orchestrator reads only the *latest* summary into cycle N+1's spawn prompt, not the chat history of cycles 1..N-1.

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

### `.claude/agents/auditor.md` — extend Phase 5 (issue-file write) to also emit `cycle_<N>/summary.md`

Per audit M14: instead of inserting a new "Phase 7", **extend the existing Phase 5 (issue-file write) with the cycle-summary emission**. The summary is a structured projection of the issue file the Auditor already wrote in that same phase — they share the underlying content, so emitting both within Phase 5 is the natural fit. No new phase numbering introduced; Phases 1-6 stay 1-6.

Auditor writes `runs/<task>/cycle_<N>/summary.md` using the structure above as part of Phase 5's existing work (after the issue file is written; before Phase 6 forward-deferral propagation runs).

### `.claude/commands/auto-implement.md` — read-only-latest-summary rule

Update the loop's per-cycle Builder spawn template:
- Cycle 1: spawn-prompt input = task spec + parent milestone README + project context brief (existing).
- Cycle N (N ≥ 2): spawn-prompt input = task spec + issue file + **most recent `cycle_<N>/summary.md`** + project context brief. **Do not include** prior Builder reports' chat content; the summary is the durable carry-forward.

Same rule for cycle-N Auditor spawns: feed the latest cycle_<N>/summary.md, not full chat history.

### `.claude/commands/clean-implement.md` — same pattern

The non-autonomous variant of the Builder→Auditor loop also benefits.

### `runs/<task>/` directory convention (canonical for T01, T03, T05, T08, T22)

Specify the structure (per audit M11 — nested `cycle_<N>/` subdirectory; all per-cycle artifacts share the same parent):

```
runs/<task-shorthand>/
  cycle_1/
    summary.md                  (T03 — cycle-summary)
    sr-dev-review.md            (T05 — reviewer fragment)
    sr-sdet-review.md           (T05 — reviewer fragment)
    security-review.md          (T05 — reviewer fragment)
    builder.usage.json          (T22 — telemetry)
    auditor.usage.json          (T22 — telemetry)
    sr-dev.usage.json           (T22 — telemetry)
    ...
    gate_pytest.txt             (T08 — gate-output capture)
    gate_lint-imports.txt       (T08)
    gate_ruff.txt               (T08)
    auditor_rotation.txt        (T27 — rotation event log, if rotation fires)
    agent_<name>_raw_return.txt (T01 — full text return per agent per cycle)
  cycle_2/
    ...
  cycle_N/
    ...
  integrity.txt                 (T09 — pre-commit ceremony output, latest cycle only)
```

Notes per audit M11:
- `agent_<name>_raw_return.txt` lives **per-cycle** (full audit trail), not top-level. Per cycle, per agent, latest invocation wins within that cycle.
- `integrity.txt` (T09) is top-level (one per task, latest run wins) since it's a pre-commit ceremony, not a per-cycle artifact.

Per audit M12 — `<task-shorthand>` is `m<MM>_t<NN>` with **both M and T zero-padded to two digits** (e.g. `m20_t01`, `m05_t02`, `m09_t01`). This avoids lexical ambiguity between `m1_t1` and `m1_t10` etc.

Directory creation handled by the orchestrator on cycle 1; subsequent cycles append.

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

1. `.claude/agents/auditor.md` Phase 5 (issue-file write) extends to also emit `cycle_<N>/summary.md` per cycle. No new phase numbering introduced (per audit M14).
2. `cycle_<N>/summary.md` template structure documented in the Auditor agent file (or referenced from `_common/cycle_summary_template.md` if shared with future commands).
3. `.claude/commands/auto-implement.md` and `.claude/commands/clean-implement.md` describe the read-only-latest-summary rule for cycle-N spawns.
4. `runs/<task>/` directory convention documented in the orchestrator command files; directory creation lands on cycle 1.
5. `tests/orchestrator/test_cycle_summary_emission.py` passes for the 3-cycle simulation.
6. `tests/orchestrator/test_cycle_context_constant.py` passes — cycle-N input size is within 10 % of cycle 1's.
7. Validation re-run: re-execute a fixture of the M12 T03 3-cycle loop with T03's compaction in place; assert cycle-3 orchestrator-context size matches cycle-1 size.
8. CHANGELOG.md updated under `[Unreleased]` with `### Changed — M20 Task 03: In-task cycle compaction (cycle_<N>/summary.md per Auditor; constant per-cycle orchestrator context; research brief §Lens 2.1)`.
9. Status surfaces flip together.

## Smoke test (Auditor runs)

```bash
# Verify Auditor agent's Phase 5 references cycle-summary emission (per audit M14 — Phase 5 amendment, not new Phase 7)
grep -qE "cycle_<N>/summary.md|cycle_<N>/summary\.md" .claude/agents/auditor.md && echo "auditor cycle-summary in Phase 5 OK"

# Verify orchestrator commands describe the read-only-latest-summary rule
for cmd in auto-implement clean-implement; do
  grep -q "cycle_<N>/summary.md" .claude/commands/$cmd.md \
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
- **Cycle-summary as the only memory mechanism** — the issue file remains the authoritative artifact. cycle_<N>/summary.md is a structured projection of the issue file's per-cycle delta, optimised for orchestrator re-read; the issue file is the one humans + future agents read for full detail.

## Dependencies

- **T01** (return-value schema) — non-blocking but tightly related. The cycle_<N>/summary.md template references T01's verdict tokens.

## Carry-over from prior milestones

*None.*

## Carry-over from task analysis

- **L2 (round 1, 2026-04-27):** The `(within 10 %)` test threshold is a heuristic — without a concrete pre-T03 baseline measurement (M12 T01 spawn was ~12.4 K input tokens — see T22's surface-check output), the 10% bound is impressionistic. Document in the test docstring that 10% is a heuristic, not an empirical bound. T22's actual baseline measurement may revise the threshold once telemetry data lands.

## Carry-over from prior audits

(populated by `/clean-implement` audit cycles)
