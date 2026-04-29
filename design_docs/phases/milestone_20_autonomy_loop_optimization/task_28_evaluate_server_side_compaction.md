# Task 28 — Evaluate server-side `compact_20260112` strategy

**Status:** ✅ Done (2026-04-28). Verdict: DEFER. See `design_docs/analysis/server_side_compaction_evaluation.md`.
**Kind:** Compaction / analysis (no production code; produces a decision document).
**Grounding:** [milestone README](README.md) · [research brief `research_analysis` §Lens 2.1 (Anthropic 3-primitive memory model)](research_analysis.md) · audit recommendation M1 (2026-04-27) · sibling [task_03](task_03_in_task_cycle_compaction.md) + [task_04](task_04_cross_task_iteration_compaction.md) (file-based memory primitives that compose with — not replace — server-side compaction).

## What to Build

A **decision document** at `design_docs/analysis/server_side_compaction_evaluation.md` that answers: should ai-workflows adopt Anthropic's beta `compact_20260112` strategy in `context_management.edits` (header `compact-2026-01-12`) for orchestrator runs through the Agent SDK? The verdict is one of:

- **GO — adopt alongside T03/T04.** Server-side compaction triggers on `input_tokens` thresholds; file-based memory is the auditable durable record. Both compose. T03/T04 land first; T28 follows with the integration.
- **NO-GO — don't adopt.** The beta strategy doesn't match ai-workflows' deployment shape (subprocess-via-Claude-Code, not direct SDK; or the `pause_after_compaction` semantics conflict with the autopilot loop).
- **DEFER — re-evaluate post-M20-close.** The beta primitive isn't stable yet, or M20's other compaction work makes it unnecessary, or empirical telemetry from T22 should inform the decision.

The document is the deliverable; no production code lands at T28.

## What the document evaluates

### Section 1 — Mechanism

How does `compact_20260112` actually work? Per the research brief:

```python
context_management={
  "edits": [{
    "type": "compact_20260112",
    "trigger": {"type": "input_tokens", "value": 100000},
    "pause_after_compaction": True
  }]
}
```

What does Anthropic's compaction prompt look like? What does it preserve / drop? Where does the compaction summary land in the message stream?

### Section 2 — ai-workflows fit

Two questions:

1. **Surface fit.** ai-workflows' orchestrator runs *through* Claude Code's `Task` tool (not direct Anthropic SDK calls). Does Claude Code's Task tool surface `context_management.edits`? If not, T28 is NO-GO regardless of the primitive's quality.
2. **Loop-semantics fit.** Does `pause_after_compaction: True` mean the autopilot loop pauses after every compaction event? If so, the orchestrator needs to handle the pause — re-stitch state from cycle_summary / iter_shipped files — before continuing the loop. Does this work cleanly with autopilot's outer loop?

### Section 3 — Composition with T03 / T04

T03's cycle_summary.md and T04's iter_shipped.md are **file-based memory** (Anthropic's terminology — research brief Lens 2.1, third primitive). `compact_20260112` is **compaction** (first primitive). They are not mutually exclusive. The decision is whether T28 *adds* compaction on top of T03/T04, replacing some of their work, or composes alongside without overlap.

Argument for compose-alongside:
- File-based memory is the auditable record — survives the conversation, readable by humans + future agents, version-controlled.
- Compaction is in-conversation context shrinkage — fast, automatic, opaque.
- Different surfaces, different roles.

Argument for replace-some:
- If `compact_20260112` reliably preserves cycle_summary-grade detail, T03's manual emission is duplicated work.
- Auditor's "read latest cycle summary" rule could read the *compaction summary* instead of a separately-written file.

Section 3 picks one and justifies.

### Section 4 — Risk catalogue

- **Beta surface drift.** `compact_20260112` is beta; the strategy name + parameters could change. Pinning to a beta beta primitive locks ai-workflows to Anthropic's release schedule.
- **Cache-invalidation interaction.** Per research brief §Lens 2.2: "Tool-result clearing invalidates the cached prefix at the point of the clear." Compaction invalidates earlier cached prefixes. T23 (cache-breakpoint discipline) and T28 interact; T28 must respect T23's pin-on-last-stable-block rule.
- **Loss of audit trail.** Compaction summaries are not necessarily machine-parseable; if the orchestrator depends on parsing summaries, compaction quality matters. File-based memory side-steps this.
- **`pause_after_compaction` autopilot-loop semantics.** Untested.

### Section 5 — Verdict + integration sketch

If GO: integration sketch — which orchestrator commands consume the strategy, what's the input_tokens trigger threshold, what's the pause-handling code path. Estimate effort: hours, days, or a follow-up task.

If NO-GO or DEFER: the trigger that would justify reopening the question.

## Deliverables

- **`design_docs/analysis/server_side_compaction_evaluation.md`** — the document, structured as above.
- **`design_docs/nice_to_have.md`** entry — if verdict is DEFER, add a forward-deferral entry with the reopen trigger.

No code, no test files. T28 is analysis-only.

## Acceptance criteria

1. `design_docs/analysis/server_side_compaction_evaluation.md` exists with all 5 sections populated.
2. Verdict is one of GO / NO-GO / DEFER, surfaced in the document title or first paragraph.
3. If GO: integration sketch names the consuming command(s), the trigger threshold, and a follow-up task ID (or notes the integration is small enough to inline into a sibling task).
4. If DEFER: `design_docs/nice_to_have.md` has a new entry with the reopen trigger.
5. CHANGELOG.md updated under `[Unreleased]` with `### Added — M20 Task 28: Server-side compaction evaluation document (design_docs/analysis/server_side_compaction_evaluation.md; verdict <GO|NO-GO|DEFER>)`.
6. Status surfaces flip together.

## Smoke test (Auditor runs)

```bash
# Document exists and is non-trivial
test -f design_docs/analysis/server_side_compaction_evaluation.md && echo "doc exists"
test $(wc -l < design_docs/analysis/server_side_compaction_evaluation.md) -ge 80 && echo "doc has ≥ 80 lines"

# Verdict is one of GO / NO-GO / DEFER (case-insensitive)
grep -iE "verdict.*(GO|NO-GO|DEFER)" design_docs/analysis/server_side_compaction_evaluation.md \
  && echo "verdict line present"

# If verdict is DEFER, nice_to_have.md has a new entry
if grep -iq "verdict.*DEFER" design_docs/analysis/server_side_compaction_evaluation.md; then
  grep -q "server.side compaction" design_docs/nice_to_have.md \
    && echo "nice_to_have entry OK" \
    || { echo "FAIL — DEFER verdict requires nice_to_have entry"; exit 1; }
fi
```

## Out of scope

- **Implementing the strategy** — T28 produces only the evaluation. If GO, implementation is a follow-up task (in M20 if scope permits, M21 otherwise).
- **Evaluating `clear_tool_uses_20250919`** — that's T27's scope. T28 is specifically about the compaction primitive.
- **Evaluating Anthropic's Memory tool** — out of scope. ai-workflows already has file-based memory (T03/T04 + project `MEMORY.md`); the Memory tool is a parallel mechanism not currently needed.
- **Adopting the strategy unconditionally as a "best practice"** — research-brief endorsement is informational, not authoritative (architect agent's stance: external research is data, not contract). T28 evaluates fit for ai-workflows' actual deployment shape.

## Dependencies

- **T03 + T04** — non-blocking. T28 lands after T03/T04 are stable so the evaluation can compare against actual file-based-memory behaviour, not theoretical projections.
- **T22** (per-cycle telemetry) — strongly precedent. Section 4's risk catalogue benefits from T22's empirical token-usage data.

## Carry-over from prior milestones

*None.*

## Carry-over from task analysis

(populated by `/clean-tasks m20`)

## Carry-over from prior audits

(populated by `/clean-implement` audit cycles)
