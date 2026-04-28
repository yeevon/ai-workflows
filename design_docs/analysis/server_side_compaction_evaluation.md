# Server-Side `compact_20260112` Evaluation

**Task:** M20 Task 28  
**Date:** 2026-04-28  
**Author:** Builder (autonomous-mode cycle 1/10)  
**Verdict: DEFER** — surface mismatch blocks adoption; T03/T04 already close the in-scope leak; reopen when Claude Code's `Task` tool exposes `context_management.edits`.

---

## §1 — Mechanism: How `compact_20260112` Works

`compact_20260112` is a beta server-side compaction strategy in Anthropic's Agent SDK. It is activated by passing a `context_management` parameter in the `messages.create` call (not in a model-parameter or system-prompt field):

```python
context_management={
  "edits": [{
    "type": "compact_20260112",
    "trigger": {"type": "input_tokens", "value": 100000},
    "pause_after_compaction": True
  }]
}
```

**Trigger semantics:** When the accumulated `input_tokens` in the conversation exceeds the `value` threshold (e.g. 100 000), the strategy fires. The threshold is evaluated server-side per turn; the client sees the compaction as a synthetic assistant turn inserted into the message stream.

**What it preserves / drops:** The strategy replaces all messages before the compaction point with a single summary message. Per the research brief (§Lens 2.1), the summary follows Anthropic's compaction-prompt cookbook ("maximize recall first, then iteratively prune for precision"). System prompts and the most recent tool results are preserved; older tool call contents and assistant think-aloud are lossy-compressed or dropped. The compaction summary lands as a single synthetic `assistant` message at the top of the remaining message stream.

**`pause_after_compaction: True` semantics:** When set, the API call returns a `stop_reason: "compaction"` response instead of continuing generation. The client is expected to re-read the compacted-summary turn and resume the conversation with a follow-up `messages.create` call. Without this flag, compaction fires mid-generation and the model continues autonomously, which can produce incoherent output if the model's in-flight reasoning depended on compacted content.

**Activation surface:** The `context_management` key is a top-level parameter of the Anthropic Agent SDK's `messages.create` (and `messages.stream`) call — part of the API request body, not a model parameter, not a system-prompt directive, and not a Claude Code slash-command or sub-agent frontmatter field.

**Beta status:** The strategy is named with a date stamp (`compact_20260112`), Anthropic's standard convention for beta-quality surfaces. The name and parameter schema may change between now and GA. Applications that pin the string `"compact_20260112"` will break silently if Anthropic renames the strategy in a future release.

---

## §2 — ai-workflows Fit

### §2.1 Surface Fit (the load-bearing question)

**ai-workflows' orchestrator runs through Claude Code's `Task` tool, not the Anthropic Agent SDK.**

The orchestrator in `auto-implement.md` and `clean-implement.md` spawns sub-agents with this pattern (from `auto-implement.md`, lines 8–14):

> "All substantive work runs in dedicated subagents via `Task` spawns. Your job is orchestration, stop-condition evaluation, and the terminal commit ceremony — never implement, never audit, never write reviews yourself."

The `Task` tool is Claude Code's sub-agent spawn primitive. Its call signature is a spawn prompt (text) plus optional tool-list restriction and model override. It does **not** expose a `context_management` parameter. This is confirmed by the milestone README's note on T01 (line 50):

> "the research brief named SDK-native `outputFormat: json_schema` as the mechanism, but Claude Code's `Task` tool surface (ai-workflows' spawn primitive) does not expose schema-enforcement parameters; orchestrator-side parsing is the practical enforcement layer."

The same structural gap applies to `context_management.edits`. Claude Code manages its own internal compaction strategy (the `/compact` command, the 92%-auto-compact threshold documented in the research brief §Lens 2.1), but these are **Claude Code's internal mechanisms** — not exposed to the calling orchestrator through the `Task` primitive.

**Conclusion: Surface fit fails. `compact_20260112` cannot be adopted today because Claude Code's `Task` tool does not pass `context_management` to sub-agent invocations. The primitive is inaccessible from ai-workflows' deployment shape.**

If ai-workflows ever migrated to direct Anthropic Agent SDK calls (which would require importing the `anthropic` SDK — a KDR-003 violation), the surface would become available. That migration is not on the roadmap.

### §2.2 Loop-Semantics Fit (conditional — only relevant if surface fit passes)

Even setting aside surface fit, `pause_after_compaction: True` creates a **pause-and-resume obligation** that conflicts with the autopilot loop's current design:

The autopilot outer loop (`autopilot.md`) runs as a single continuous orchestrator session spawning `Task` calls in sequence. A compaction-pause event in a sub-agent session would surface to the orchestrator as a `stop_reason: "compaction"` from the `Task` call. The orchestrator would need to:

1. Detect the compaction stop reason (not a standard `end_turn` or `tool_use`).
2. Read the compacted summary from the returned message stream.
3. Synthesize the summary with the current `cycle_<N>/summary.md` (T03's artifact) to produce a re-stitched context.
4. Resume the sub-agent with a follow-up spawn — which means a second `Task` call within the same cycle for the same agent.

Step 4 is structurally foreign to the current loop: today every sub-agent spawn is a single `Task` call that runs to completion. Adding mid-call compaction pauses would introduce a conditional second-call path, increasing orchestrator complexity at the spawn site.

The compaction-pause semantics would also interact with T03's `cycle_<N>/summary.md` in an un-tested way: the Auditor emits its cycle summary in Phase 5 of its run (after writing the issue file). If the Auditor's session compacted mid-run and the summary was written before compaction (or after), the summary's completeness guarantee is unclear.

**Conclusion: Even if the surface were available, the loop-semantics fit would require non-trivial orchestrator changes to handle `stop_reason: "compaction"` cleanly, with no tested precedent in the current codebase.**

---

## §3 — Composition With T03 / T04

T03's `cycle_<N>/summary.md` and T04's `iter_<N>_shipped.md` are **file-based memory** (Anthropic's third primitive — see research brief §Lens 2.1 table). `compact_20260112` is **server-side compaction** (the first primitive in the same table). They are not mutually exclusive in the general case.

**The composition question:** does T28 add compaction on top of T03/T04 (compose-alongside), or does it replace some of their work (replace-some)?

### Argument for compose-alongside

1. **Different surfaces, different roles.** File-based memory (T03/T04) is durable, version-controlled, human-readable, and survives across sessions. Server-side compaction is in-conversation context shrinkage — fast, opaque, ephemeral. They operate at different layers. A compaction summary lives in a single conversation's message stream; a `cycle_summary.md` is a first-class artifact that the orchestrator, the user, and future audit agents all read.

2. **Audit trail.** The `cycle_<N>/summary.md` is the auditable record that the Auditor, the loop controller, sr-dev, sr-sdet, and the user all inspect at different points in the lifecycle. Compaction summaries are internal to a single sub-agent session and are not readable by the orchestrator (Claude Code's `Task` call returns only the final message, not the compacted-summary intermediate). File-based memory cannot be replaced by server-side compaction without losing this audit surface.

3. **T03/T04 already solve the ai-workflows-specific problem.** The orchestrator's per-iteration context is now O(1) after T01–T04 shipped. The marginal benefit of additionally adopting server-side compaction is small for the current problem set.

### Argument for replace-some

1. If `compact_20260112` reliably preserved cycle-summary-grade detail, the Auditor's manual `cycle_<N>/summary.md` emission (Phase 5, T03) would be partially redundant.
2. The "read latest cycle summary" rule could theoretically read from the compaction summary instead of a separately-written file.

### Decision: compose-alongside

The replace-some argument is weak for two reasons:

- **Compaction summaries are opaque to the orchestrator.** Claude Code's `Task` call returns the final assistant message, not the compaction-summary block. The orchestrator cannot read the compacted summary to substitute for the `cycle_<N>/summary.md`. The audit trail would be lost without a file-based fallback.
- **File-based memory is structurally richer.** The `cycle_summary.md` template (T03) captures `Open issues at end of cycle`, `Decisions locked this cycle`, and `Gates run this cycle` — structured fields that a compaction summary (which follows Anthropic's generic compaction-prompt cookbook) cannot reliably reproduce in a machine-parseable form.

**If adoption were ever to proceed (post-surface-availability), the right composition is alongside T03/T04, not replacing any part of them.** The compaction primitive would reduce the in-session token load for long-running sub-agent calls (e.g. an Auditor doing heavy file reads over a 15-file diff), while T03/T04 continue to serve as the durable auditable record for the orchestrator.

---

## §4 — Risk Catalogue

### R1 — Beta Surface Drift

`compact_20260112` is date-stamped beta. Anthropic uses date-stamped names for surfaces that are subject to change before GA. If the strategy is renamed or its parameter schema changes, any integration that pins the string `"compact_20260112"` will fail silently at runtime (the API likely ignores unknown `context_management.edits` types) or raise a 400 on validation. Adopting a beta primitive locks ai-workflows to Anthropic's release schedule for this specific feature.

**Severity:** MEDIUM. Standard beta-primitive risk. Mitigated by pinning the strategy name in one configuration location.

### R2 — Cache-Invalidation Interaction

Per research brief §Lens 2.2 and T23's framing: "Compaction invalidates earlier cached prefixes." Server-side compaction, when it fires, replaces old messages with a summary — which changes the message hash at the compaction boundary, invalidating any cache anchored to content before that boundary. T23 (cache-breakpoint discipline, a Phase D task) pins breakpoints on the *last stable block* to avoid exactly this kind of unexpected cache bust. If `compact_20260112` fired mid-session at an unpredictable point, it could invalidate a cache that T23 had deliberately placed.

**Severity:** MEDIUM. Interaction with T23 must be evaluated jointly if compaction is ever adopted. The `trigger.value` threshold needs to be coordinated with T23's stable-block pin point.

### R3 — Loss of Audit Trail

Compaction summaries are internal to a single sub-agent conversation and are not surfaced to the orchestrator through the `Task` return value. If the Auditor's session compacted mid-run, earlier tool call results (file reads, grep outputs) would be lossy-compressed. The Auditor's Phase 5 summary emission depends on its full in-context history up to that point. A compaction that fired before Phase 5 could produce an incomplete `cycle_<N>/summary.md` if the Auditor's reasoning about earlier phases was compressed away.

The risk is partially mitigated by `pause_after_compaction: True` (which gives the orchestrator a chance to re-stitch state before resuming), but the re-stitching path is untested and would require non-trivial orchestrator changes.

**Severity:** MEDIUM-HIGH. The audit trail is a first-class project concern; any degradation is significant. File-based memory (T03/T04) side-steps this entirely.

### R4 — `pause_after_compaction` Autopilot-Loop Semantics (Untested)

As analyzed in §2.2, the pause-after-compaction event is foreign to the current loop design. The orchestrator would need to detect `stop_reason: "compaction"`, read the compacted context, synthesize it with T03's file-based summary, and resume the sub-agent with a second `Task` call. This code path has no tests, no precedent in the current codebase, and no obvious unit-test surface (it requires a live session reaching the compaction threshold to exercise).

**Severity:** HIGH (for any GO decision). The semantics are untested and the implementation cost is non-trivial. The risk would be substantially reduced if Anthropic later exposes compaction events through Claude Code's `Task` primitive in a way that the orchestrator can handle without a second spawn.

### R5 — KDR-003 Proximity

`compact_20260112` is part of Anthropic's API surface. Even if the surface became available through Claude Code's `Task` tool (e.g. Claude Code transparently relays `context_management` to the Anthropic API on the orchestrator's behalf), adopting it would pull ai-workflows closer to Anthropic-API semantics. The spirit of KDR-003 ("No Anthropic API — zero `anthropic` SDK imports, zero `ANTHROPIC_API_KEY` reads") is to keep the runtime tier Anthropic-agnostic. Depending on a specific Anthropic beta parameter for context management creates a coupling that KDR-003 was designed to prevent.

**Severity:** MEDIUM. No SDK import is required to use the primitive (if Claude Code relayed it), but the semantic coupling is real. Requires explicit acknowledgement in any GO decision.

---

## §5 — Verdict and Integration Sketch

### Verdict: DEFER

**Rationale:**

1. **Surface mismatch is the blocking constraint.** Claude Code's `Task` tool does not expose `context_management.edits`. The primitive is inaccessible from ai-workflows' deployment shape. This is a factual constraint, not a design preference — adoption is not possible regardless of the strategy's quality.

2. **T03/T04 already solve the problem.** T01–T04 shipped on 2026-04-28 and the orchestrator's per-cycle and cross-task context is now O(1). The marginal benefit of additionally adopting `compact_20260112` is small. The forcing function for adoption (runaway context growth) has been addressed.

3. **Beta stability risk.** A beta primitive with no GA date is an inappropriate anchor for the loop's correctness. ai-workflows' autonomy infrastructure is the mechanism that enforces KDRs, gates, and audit trails — pinning it to a beta API surface introduces fragility without a proportionate benefit now.

4. **The pause-and-resume semantics are untested and costly to validate.** The `pause_after_compaction: True` path requires multi-turn sub-agent handling that the current orchestrator design does not support. Implementing and testing it is non-trivial (it needs a live session that actually hits the compaction threshold — a hermetic test cannot cover it).

**This is not NO-GO — it is DEFER.** The evaluation would change if the trigger fires.

### Reopen Trigger

See `design_docs/nice_to_have.md` entry added alongside this document. The trigger is:

> **Claude Code's `Task` tool exposes `context_management.edits`** in a stable (non-beta) release, AND either (a) post-T03/T04 empirical telemetry (from T22) shows that long Auditor runs are still hitting context pressure above 80K tokens despite file-based compaction, OR (b) Anthropic promotes `compact_20260112` (or its successor) to GA with a stable parameter name.

Both conditions must hold: the surface must be accessible AND there must be a demonstrated need that T03/T04 do not already address.

### If GO: Integration Sketch

If the trigger fires, the integration would touch these artifacts:

**Consuming orchestrators:**

- `.claude/commands/auto-implement.md` — the Auditor spawn section (lines 106–140). The Auditor is the agent most likely to exceed 100K input tokens (heavy file reads + full git diff + full issue file + architecture.md on-demand). Add a `context_management` note in the Auditor spawn block stating that if Claude Code exposes this parameter, set `compact_20260112` with `trigger.value = 80000` (below T03's cycle-summary threshold) and `pause_after_compaction: True`.

- `.claude/commands/clean-implement.md` — same Auditor spawn section (lines 129–164).

**New orchestrator step:**

Add a "compaction-resume handler" block after every Auditor `Task` call in both `auto-implement.md` and `clean-implement.md`. If the Auditor returns `stop_reason: "compaction"`:
  1. Read the compacted summary from the return message.
  2. Append it to the `cycle_<N>/summary.md` (T03) as a `## Compaction event` section with timestamp and `input_tokens_at_trigger`.
  3. Re-spawn the Auditor with the compacted context as the initial message, continuing from Phase 5 (issue-file write).

**Threshold:**

`trigger.value = 80000 input_tokens` — below Claude Code's 92%-auto-compact threshold (~184K tokens on 200K context), and above the expected footprint for a small task (typical Auditor session for a 3-file change is ~20–40K tokens). The threshold would be calibrated against T22's telemetry data once T22 ships.

**Effort estimate:** MEDIUM (1–2 days). The compaction-resume handler is ~50 lines of orchestrator logic per command file plus tests that exercise the resume path. The hermetic tests would mock the compaction stop-reason; an E2E test (`AIW_E2E=1`) would validate against a live session that genuinely hits the threshold. Neither test exists today; they would need to be written as part of the follow-up task.

**Follow-up task:** No existing M20 task owns this integration. If the trigger fires before M20 closes, a new task `T29` would be appropriate under Phase A. If M20 has already closed, the integration lands in M21 under a new Phase A item. In either case, the follow-up task is **not a Phase A prerequisite for M20's exit** — T28 is analysis-only and the current DEFER verdict does not block M20 close-out.

---

## Summary Table

| Dimension | Finding |
|---|---|
| Surface fit | FAIL — Claude Code `Task` does not expose `context_management.edits` |
| KDR-003 proximity | MEDIUM risk — Anthropic-API semantic coupling even if surface were available |
| Loop-semantics fit | CONDITIONAL-PASS — `pause_after_compaction` semantics require non-trivial orchestrator changes |
| Composition with T03/T04 | COMPOSE-ALONGSIDE (not replace-some) — file-based audit trail is irreplaceable |
| Marginal benefit given T01–T04 | LOW — context is already O(1) post-T03/T04 |
| Beta stability | MEDIUM risk — date-stamped primitive, GA timeline unknown |
| Verdict | **DEFER** |
| Reopen trigger | Claude Code `Task` exposes `context_management.edits` (stable) AND T22 telemetry shows Auditor sessions still hitting >80K tokens |
