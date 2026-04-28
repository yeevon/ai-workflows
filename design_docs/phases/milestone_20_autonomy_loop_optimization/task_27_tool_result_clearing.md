# Task 27 — Auditor input-volume threshold for cycle-rotation (client-side simulation of `clear_tool_uses_20250919`)

**Status:** ✅ Done (2026-04-28).
**Kind:** Safeguards / code.
**Grounding:** [milestone README](README.md) · [research brief `research_analysis` §Lens 2.1 (Anthropic 3-primitive memory model — tool-result clearing)](research_analysis) · audit recommendation H6 (Path A removed: Claude Code's agent frontmatter accepts only `name`/`description`/`tools`/`model`; `context_management.edits` cannot be passed through) · sibling [task_28](task_28_evaluate_server_side_compaction.md) (T28 owns the broader server-side-compaction surface check) · sibling [task_03](task_03_in_task_cycle_compaction.md) (cycle_summary.md is the compacted-input source) · [`.claude/agents/auditor.md`](../../../.claude/agents/auditor.md).

## What to Build

Per audit H6 (user arbitration 2026-04-27 — pick Path B, T28 stays separate): T27 ships the **client-side simulation only**. The Auditor's per-cycle Read-heavy access pattern (research brief §Lens 2.1) means accumulated tool-result content can dominate input-token cost on long-cycle audits. T27 detects when an Auditor spawn's input is climbing toward 60 K tokens and **rotates the next spawn early** — the orchestrator spawns a fresh Auditor at the next cycle boundary with a *compacted input* (T03's `cycle_summary.md` + current diff only), not the full conversation history.

This is essentially "spawn a fresh Auditor at cycle N+1 instead of continuing cycle N's context" — the pattern already in the autonomy loop's design (each cycle = fresh spawn). T27 tightens the rotation trigger by making **per-cycle input volume** the threshold, not just cycle count. A long-cycle audit on a multi-file task can exhaust input budget before completing the audit; T27 catches this and forces a cycle boundary early.

**Path A — server-side `clear_tool_uses_20250919` via agent frontmatter — is rejected.** Claude Code's agent frontmatter accepts only `name`, `description`, `tools`, `model` (verified across all 9 existing agents). There is no documented mechanism for Claude Code to read `context_management:` from agent frontmatter and pass it through to the underlying SDK. Same precedent as T01's `outputFormat: json_schema` (Anthropic SDK has it; Claude Code Task wrapper doesn't surface it). T28 owns the broader question of whether any context-engineering primitive is reachable via Task; if T28's surface check returns YES for `context_management`, a follow-up M21 task can revisit T27 to add server-side optimization on top of the client-side simulation. **T27 itself does not ship Path A.**

**Critical scope limit:** T27 applies **only to the Auditor's spawn**, not to all sub-agents. Builder spawns benefit less (Builder's tool calls are mostly Edit + Write, where the "result" is just success/failure metadata). Reviewer spawns are short (one read + a verdict). **Auditor is the high-volume Read-heavy agent**; T27 targets it specifically.

## Mechanism

T22's per-cycle telemetry captures `input_tokens` for each Auditor spawn. T27 adds a threshold check + rotation trigger to the orchestrator's per-cycle loop:

1. After Auditor spawn N's `complete` telemetry record lands, orchestrator reads `input_tokens` from the JSON.
2. If `input_tokens >= 60000` AND the Auditor's verdict was OPEN (loop continues): the orchestrator's next Auditor spawn is given a **compacted input**:
   - Task spec path (existing).
   - Issue file path (existing).
   - Current `git diff` (existing).
   - **`runs/<task>/cycle_<N>/summary.md`** (T03's structured summary) — replaces the prior cycle's full chat history.
   - **NOT included:** prior Builder reports, prior Auditor verdict text, prior tool-result content.
3. If `input_tokens < 60000` (normal case): orchestrator continues with the standard per-cycle spawn input (no compaction).
4. If the Auditor's verdict was PASS (loop ends), no rotation needed.

The compacted-input path is already implicit in T03's "read only the latest summary" rule for cycle N+1. T27 tightens the trigger from "cycle boundary always" to "cycle boundary OR input-volume threshold," and clarifies the compacted-input shape when the threshold fires.

## Threshold + tunability

- **Trigger threshold:** `60000 input_tokens` (research-brief default; tunable via `AIW_AUDITOR_ROTATION_THRESHOLD` env var).
- **Compaction recovery target:** the compacted input should be ≤ 30 K tokens (cycle_summary + current diff + spec). T22's per-spawn measurement validates.
- **Cache invalidation cost:** rotation creates a fresh sub-agent; cache from the prior spawn is irrelevant. T23 (cache-breakpoint discipline) ensures the fresh spawn's stable prefix is byte-identical, so cache builds cleanly on the new spawn.

## Deliverables

### `.claude/commands/auto-implement.md` — rotation trigger in the per-cycle loop

Update the cycle-N+1-spawn section. Add a check: read T22's `auditor.usage.json` for cycle N; if `input_tokens >= 60000` AND verdict was OPEN, the cycle-N+1 spawn input is the compacted form (per §Mechanism above). Otherwise standard.

### `.claude/commands/clean-implement.md` — same pattern

Apply consistently.

### `.claude/commands/_common/auditor_context_management.md` (NEW)

Documents the threshold + tunability + the rationale for client-side rotation over server-side `clear_tool_uses_20250919`. Cites audit H6 (Path A rejected; Claude Code Task tool surface limitation).

### Telemetry hook (lightweight)

Each rotation event writes a one-line record to `runs/<task>/cycle_<N>/auditor_rotation.txt`:
```
ROTATED: cycle <N> input_tokens=<value>; cycle <N+1> spawn input compacted (cycle_summary + diff only)
```
Aggregated by T04's `iter_<N>_shipped.md` if the iteration includes any rotation events.

## Tests

### `tests/orchestrator/test_auditor_rotation_trigger.py` (NEW)

- Synthetic multi-cycle audit where cycle N's `auditor.usage.json` shows `input_tokens >= 60000` AND verdict OPEN → cycle N+1 spawn input is compacted (cycle_summary.md + current diff, not full chat history).
- Synthetic case where `input_tokens < 60000` → cycle N+1 spawn uses the standard input (no rotation triggered).
- Synthetic case where verdict is PASS at cycle N → no rotation regardless of input volume (loop ends).
- Tunability: `AIW_AUDITOR_ROTATION_THRESHOLD=40000` env var lowers the trigger; verify the trigger fires at the new value.

### `tests/orchestrator/test_auditor_rotation_doesnt_break_verdict.py` (NEW)

Hermetic 5-cycle audit fixture. Run with T27 rotation enabled vs disabled. Assert:
- Final verdicts are identical (rotation didn't change audit outcome).
- T27-enabled run uses ≤ 70 % of the cumulative input tokens of T27-disabled run when the audit triggers ≥ 1 rotation.

## Acceptance criteria

1. `.claude/commands/auto-implement.md` describes the rotation trigger in the per-cycle Auditor spawn loop (per §Mechanism).
2. `.claude/commands/clean-implement.md` matches.
3. `.claude/commands/_common/auditor_context_management.md` exists; documents the threshold (60K default, `AIW_AUDITOR_ROTATION_THRESHOLD` env override), the compaction recovery target (≤ 30K), and the rejection of Path A (Claude Code Task tool surface limitation).
4. Rotation events log to `runs/<task>/cycle_<N>/auditor_rotation.txt`.
5. `tests/orchestrator/test_auditor_rotation_trigger.py` passes — threshold-fire + threshold-no-fire + verdict-PASS + tunability cases.
6. `tests/orchestrator/test_auditor_rotation_doesnt_break_verdict.py` passes — verdicts unchanged; ≤ 70 % cumulative input-token reduction when rotation fires.
7. CHANGELOG.md updated under `[Unreleased]` with `### Added — M20 Task 27: Auditor input-volume rotation trigger (client-side simulation of clear_tool_uses_20250919; tunable via AIW_AUDITOR_ROTATION_THRESHOLD; ≤ 70 % cumulative input-token reduction on long-cycle audits; Path A rejected per audit H6 — Claude Code Task tool does not expose context_management.edits)`.
8. Status surfaces flip together.

## Smoke test (Auditor runs)

```bash
# Verify the canonical reference exists with H6 rationale
grep -q "Path A.*rejected\|Path A is rejected\|client-side simulation" .claude/commands/_common/auditor_context_management.md \
  && echo "H6 rationale documented"

# Verify auto-implement describes the rotation trigger
grep -q "AIW_AUDITOR_ROTATION_THRESHOLD\|input_tokens >= 60000\|input volume threshold" .claude/commands/auto-implement.md \
  && echo "auto-implement integration OK"

# Verify rotation log path exists in spec
grep -q "auditor_rotation.txt" .claude/commands/auto-implement.md && echo "rotation log path OK"

# Run T27 tests
uv run pytest tests/orchestrator/test_auditor_rotation_trigger.py tests/orchestrator/test_auditor_rotation_doesnt_break_verdict.py -v
```

## Out of scope

- **Path A — server-side `clear_tool_uses_20250919` via agent frontmatter.** Rejected per audit H6: Claude Code's agent frontmatter accepts only `name`/`description`/`tools`/`model`; there is no mechanism to pass `context_management.edits` through to the underlying SDK. T28's surface check verifies whether *any* context-engineering primitive is reachable via Task; if T28 returns YES for `context_management`, a follow-up M21 task can revisit T27 to layer server-side optimization on top of the client-side simulation. T27 itself ships only Path B.
- **Tool-result clearing for non-Auditor agents** — Builder, reviewers, task-analyzer don't have the same Read-heavy access pattern. T27 is Auditor-specific.
- **Adopting `compact_20260112`** — T28's evaluation scope. T27 is *cycle rotation triggered by input volume*; T28 evaluates whether a different primitive (server-side compaction) is reachable.
- **Empirical threshold tuning** — `60K input_tokens` trigger comes from research-brief priors. T22's telemetry data could inform tuning, but T27 ships the prior; tuning is a future productivity task.
- **Mid-cycle compaction** — out of scope. T27's compaction is at-cycle-boundary, never mid-spawn. Mid-spawn compaction would require server-side primitives (Path A) which is rejected.

## Dependencies

- **T22** (per-cycle telemetry) — **blocking**. T27's trigger reads `input_tokens` from T22's `auditor.usage.json` records.
- **T03** (cycle_summary.md per Auditor) — **blocking**. T27's compacted input includes T03's cycle_summary; without T03 there's nothing to compact-to.
- **T23** (cache-breakpoint discipline) — non-blocking but synergistic. T27 spawns fresh sub-agents at rotation; T23 ensures their stable prefix is byte-identical so cache builds cleanly.
- **T28** (server-side compaction evaluation) — non-blocking. T28 owns the broader surface-check question; if T28 returns YES for `context_management.edits`, a follow-up task layers Path A on top of T27's Path B.

## Carry-over from prior milestones

*None.*

## Carry-over from task analysis

(populated by `/clean-tasks m20`)

## Carry-over from prior audits

(populated by `/clean-implement` audit cycles)
