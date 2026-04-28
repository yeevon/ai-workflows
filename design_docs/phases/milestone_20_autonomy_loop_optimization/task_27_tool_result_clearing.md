# Task 27 — Tool-result clearing for long Auditor runs (`clear_tool_uses_20250919`)

**Status:** 📝 Planned.
**Grounding:** [milestone README](README.md) · [research brief `research_analysis` §Lens 2.1 (Anthropic 3-primitive memory model — tool-result clearing)](research_analysis) · sibling [task_28](task_28_evaluate_server_side_compaction.md) (T27 is sibling to T28's compaction primitive — both are Anthropic context-edits primitives) · [`.claude/agents/auditor.md`](../../../.claude/agents/auditor.md).

## What to Build

Adopt Anthropic's `clear_tool_uses_20250919` strategy in `context_management.edits` for the **Auditor's per-cycle run**, which makes heavy use of `Read`, `Grep`, `Glob` for verifying the full task scope. Per the research brief §Lens 2.1, tool-result clearing is the right primitive for this access pattern: the Auditor reads many files per cycle to build its verdict, but **once the verdict is formed, the raw file contents are dead weight** in the conversation context.

The strategy keeps the metadata (the call happened) while dropping the bulky tool result bodies. Combined with cache-friendly settings (`clear_at_least` set high enough that each clearing event recovers more tokens than the cache rebuild costs — research brief §Lens 2.2):

```python
context_management={
  "edits": [{
    "type": "clear_tool_uses_20250919",
    "trigger": {"type": "input_tokens", "value": 60000},
    "keep": {"type": "tool_uses", "value": 5},
    "clear_at_least": {"type": "input_tokens", "value": 8000}
  }]
}
```

`keep: 5` retains the 5 most-recent tool results (so the Auditor's *current reasoning chain* isn't disrupted); older Read/Grep results are cleared. `clear_at_least: 8000` ensures each clearing event reclaims enough tokens to amortise the cache invalidation.

**Critical scope limit:** T27 applies **only to the Auditor's spawn**, not to all sub-agents. Builder spawns benefit less (Builder's tool calls are mostly Edit + Write, where the "result" is just success/failure metadata — clearing buys little). Reviewer spawns are short (one read + a verdict); not enough volume to justify clearing. **Auditor is the high-volume Read-heavy agent**; T27 targets it specifically.

## Surface check

Same constraint as T28 (server-side compaction): does Claude Code's `Task` tool surface the `context_management.edits` parameter? If not, T27 reduces to a NO-GO sibling of T28 and the actual mechanism is **client-side simulation** — orchestrator detects "Auditor spawn input is approaching 60K tokens" and *re-spawns* the Auditor with a compacted state inputs (a fresh Auditor instance reads from cycle_summary.md instead of the full prior chat).

If T28's evaluation finds the SDK surface is exposed via Task, T27 ships the server-side strategy. If not, T27 ships the client-side simulation. **T27's deliverable is one or the other — not both.**

## Deliverables

### Determine surface — verification step

Before any code: `python scripts/check_task_tool_surface.py` runs an empirical test. Spawns a Task with `context_management.edits` parameter; if accepted, the surface is exposed and T27 ships server-side. If rejected (or silently ignored), T27 ships client-side simulation.

The check script's output writes to `runs/m20_t27_surface_check.txt` for the audit trail.

### Path A — server-side (if surface exposed)

`.claude/agents/auditor.md` adds frontmatter:
```yaml
context_management:
  edits:
    - type: clear_tool_uses_20250919
      trigger:
        type: input_tokens
        value: 60000
      keep:
        type: tool_uses
        value: 5
      clear_at_least:
        type: input_tokens
        value: 8000
```

(YAML key syntax may need adjustment depending on Claude Code's frontmatter parser; verify in the empirical surface check.)

### Path B — client-side simulation (if surface not exposed)

Orchestrator-side: monitor T22's `input_tokens` for each Auditor spawn. When a multi-cycle audit's per-spawn input is climbing toward 60K, the orchestrator's next Auditor spawn is given a *compacted input* (cycle_summary.md from T03 + current diff only), not the full conversation history. This is essentially "spawn a fresh Auditor at cycle N+1 instead of continuing cycle N's context" — a pattern already in the autonomy loop's design (each cycle = fresh spawn). T27's client-side path tightens that by making the per-cycle-input-size the trigger, not just cycle boundaries.

### `.claude/commands/_common/auditor_context_management.md` (NEW)

Single source of truth documenting whichever path landed (A or B) with the trigger thresholds + the rationale.

## Tests

### `tests/agents/test_auditor_tool_clearing.py` (NEW)

Path A (if shipped):
- Synthetic Auditor spawn with > 60K input tokens triggers clearing.
- Post-clearing input has `keep: 5` retained tool results.
- `cache_read_input_tokens` after clearing is ≥ 0 (not a regression beyond cache-invalidation cost).

Path B (if shipped):
- Synthetic multi-cycle audit where cycle N's input approaches 60K → cycle N+1 spawns with compacted input (cycle_summary.md + current diff, not full chat history).
- Compacted input is byte-stable across re-spawns at the same cycle boundary (cache-friendly per T23).

### `tests/agents/test_auditor_clearing_doesnt_break_verdict.py` (NEW)

Hermetic 5-cycle audit fixture. Run with T27 enabled vs disabled. Assert:
- Final verdicts are identical (clearing didn't change the audit outcome).
- T27-enabled run uses ≤ 70 % of the input tokens of T27-disabled run.

## Acceptance criteria

1. Surface check (Path A vs Path B) is run and the result is recorded at `runs/m20_t27_surface_check.txt`.
2. Either Path A's frontmatter lands in auditor.md OR Path B's client-side simulation lands in `.claude/commands/auto-implement.md`.
3. `.claude/commands/_common/auditor_context_management.md` documents the path + thresholds.
4. `tests/agents/test_auditor_tool_clearing.py` passes (whichever path's tests apply).
5. `tests/agents/test_auditor_clearing_doesnt_break_verdict.py` passes — clearing doesn't break audit outcome; ≤ 70 % input-token reduction.
6. CHANGELOG.md updated under `[Unreleased]` with `### Added — M20 Task 27: Auditor tool-result clearing (Path <A | B>; ≤ 70 % input-token reduction; clear_tool_uses_20250919 strategy with keep=5)`.
7. Status surfaces flip together.

## Smoke test (Auditor runs)

```bash
# Verify surface-check artifact exists
test -f runs/m20_t27_surface_check.txt && echo "surface check OK"

# Verify the chosen path landed
grep -q "context_management\|tool-result clearing" .claude/agents/auditor.md \
  || grep -q "compacted input\|tool-result clearing" .claude/commands/auto-implement.md \
  && echo "path A or B landed"

# Verify the canonical reference exists
test -f .claude/commands/_common/auditor_context_management.md && echo "ref OK"

# Run T27 tests
uv run pytest tests/agents/test_auditor_tool_clearing.py tests/agents/test_auditor_clearing_doesnt_break_verdict.py -v
```

## Out of scope

- **Tool-result clearing for non-Auditor agents** — Builder, reviewers, task-analyzer don't have the same Read-heavy access pattern. T27 is Auditor-specific.
- **Adopting `compact_20260112`** — T28's scope. T27 is the *clearing* primitive (drops content of older tool results); T28 is the *compaction* primitive (summarises the conversation). Different primitives, different roles.
- **Tuning the threshold values empirically** — `60K input_tokens trigger` and `keep: 5` come from research-brief priors. T22's telemetry data could inform tuning, but tuning is a future task; T27 ships the priors.
- **Cross-cycle clearing** — out of scope. Each Auditor cycle is a fresh spawn; clearing is in-spawn only.

## Dependencies

- **T22** (per-cycle telemetry) — **blocking** for both Path A and Path B. Path A's verification needs `cache_read_input_tokens`; Path B's trigger needs `input_tokens` per spawn.
- **T28** (server-side compaction evaluation) — non-blocking but informational. T28's surface check (does Task expose `context_management`?) is reused for T27's surface check.
- **T23** (cache-breakpoint discipline) — non-blocking. T27's clearing must respect T23's stable-prefix discipline so cache invalidation is bounded.

## Carry-over from prior milestones

*None.*

## Carry-over from task analysis

(populated by `/clean-tasks m20`)

## Carry-over from prior audits

(populated by `/clean-implement` audit cycles)
