# Task 05 — Documentation Sweep: §8.4 Limitations + Five `nice_to_have.md` Entries

**Status:** 📝 Planned.
**Grounding:** [milestone README §Exit criteria 5 + 6](README.md) · [architecture.md §8.4](../../architecture.md) · [nice_to_have.md](../../nice_to_have.md) · [M8 deep-analysis (fragility #1, #2, #7; debt #1, #4, #5)](../milestone_8_ollama/README.md).

## What to Build

Two documentation deliverables:

1. **architecture.md §8.4 Limitations paragraph.** Today §8.4 mentions
   the process-local breaker inline (line 191: *"a process-local
   `CircuitBreaker`"*) but does not label it as a limitation, does not
   link a promotion trigger, and does not group it with the two other
   single-process / heuristic-tuning assumptions that share the same
   shape. T05 promotes the inline mention to a labeled **Limitations**
   paragraph that gathers all three assumptions and cross-references
   their `nice_to_have.md` entries.

2. **Five new `nice_to_have.md` entries** for the deferred items the M8
   post-mortem surfaced. Each entry follows the §1–§22 shape (Role /
   Replaces & subsumes / Adds / Trigger to adopt / Why not now /
   Related history).

This is a **doc-only** task. No code, no tests.

## ⚠️ Slot-number drift from milestone README

The [milestone README](README.md) (drafted 2026-04-21) reserved slots
`§17`–`§21` for the five new entries. Between the M10 plan date and
M10 T05 spec-write, slots `§17`–`§22` were filled by entries landed
during the 0.1.x release cycle and the M16 kickoff (RELEASE_STEPS
playbook, design_branch CI trigger, dep lower-bound refresh,
StubAdapterMissingCaseError test, entry-point discovery, hot-reload).

**This spec assumes §23–§27 are the next-five-consecutive free slots
based on `nice_to_have.md` state at the time M10 was tasked out
(2026-04-24).** The M10 milestone is on hold pending the CS300 pivot;
when it thaws, the Builder's first action under T05 is to re-grep
`nice_to_have.md` for the actual next-free range:

```bash
grep -E "^## [0-9]+\." design_docs/nice_to_have.md | tail -10
```

If additional entries have landed, the Builder picks the next-five
consecutive free slots (e.g. §28–§32 if §23–§27 are taken) and
updates every cross-reference in T01, T03, T05, and T06 inside this
task's issue file before the audit closes. The mapping table in T05's
*"slot mapping table + branch-count correction"* deliverable section
(further down) is the canonical place to record the actual landing
slots vs. the planned ones.

The Auditor's drift check expects whatever range the Builder selected,
recorded in this task's issue file at the top — not literally
§23–§27.

## Deliverables

### [design_docs/architecture.md](../../architecture.md) §8.4 — Limitations paragraph

Append a new paragraph at the **end** of §8.4 (after the existing
"Non-Ollama tiers." block, around line 226), titled **Limitations** in
bold. The paragraph names three load-bearing single-process assumptions:

1. **Breaker is process-local.** Each `aiw` / `aiw-mcp` worker process
   constructs its own `CircuitBreaker` instances via
   `_build_ollama_circuit_breakers`. State is not shared across workers.
   In a multi-process or multi-host deployment (e.g. an `aiw-mcp
   --transport http` instance behind a process-pool reverse proxy), each
   worker trips independently and a partially-degraded Ollama is observed
   inconsistently across workers. **Promotion trigger:** see
   `nice_to_have.md` §23.
2. **Breaker tuning is heuristic, not empirical.** Defaults
   (`trip_threshold=3`, `cooldown_s=60.0`) were locked at M8 T02 from a
   small-N transient-failure sample on a single workstation. Production
   tuning requires telemetry. **Promotion trigger:** see
   `nice_to_have.md` §24.
3. **Single-level fallback only.** `FallbackChoice.FALLBACK` promotes to
   exactly one replacement tier (`OllamaFallback.fallback_tier`). If the
   replacement is also unavailable (e.g. Claude Code OAuth expired
   simultaneously with an Ollama daemon outage), the fallback round-trip
   fails opaquely. **Promotion trigger:** see `nice_to_have.md` §25.

The paragraph closes with a one-line cross-reference: *"Each limitation has
an explicit `nice_to_have.md` promotion trigger; do not silently expand
breaker scope without reading the corresponding entry first."*

### [design_docs/nice_to_have.md](../../nice_to_have.md) — Five new entries

Each follows the §1–§22 shape (heading, **Role**, **Replaces / subsumes**,
**Adds**, **Trigger to adopt**, **Why not now**, **Related history**).
Append at the file's tail, before the `## Revisit cadence` section.

#### Section 23 — Multi-process / shared-state circuit breaker

- **Role:** Replace the process-local `CircuitBreaker` with a shared-state
  implementation (Redis, SQLite-backed table, or LangGraph's checkpoint
  store, depending on the deployment shape) so multiple `aiw-mcp` workers
  observe the same Ollama-trip state.
- **Replaces / subsumes:** Today's `_build_ollama_circuit_breakers` returns
  per-worker `asyncio.Lock`-guarded objects.
- **Adds:** A `BreakerStorage` protocol; one concrete impl pinned to the
  deployment story (Redis is the natural choice if `aiw-mcp` lands a
  multi-process mode); a contract-level test that two breaker instances
  pointing at the same store agree on `state` after a third instance trips.
- **Trigger to adopt** — any one of:
  - `aiw-mcp` lands a multi-process or multi-host deployment shape (M14+
    or a future containerised packaging).
  - An incident where two workers thrash a partially-degraded Ollama with
    inconsistent breaker state is observed.
  - A second user (per `Revisit cadence` rule 1) starts running a
    long-lived multi-worker `aiw-mcp` against a shared Ollama.
- **Why not now:** ai-workflows is single-user, local-machine
  ([CLAUDE.md threat model](../CLAUDE.md)). The single-process assumption
  is correct for every committed milestone. Adding shared state introduces
  a serialisation hazard the current architecture does not need.
- **Related history:** [M10 README](phases/milestone_10_ollama_hardening/README.md),
  M8 deep-analysis fragility #1.

#### Section 24 — Empirical breaker tuning from production telemetry

- **Role:** Replace the heuristic defaults (`trip_threshold=3`,
  `cooldown_s=60.0`) with values derived from accumulated trip / recovery
  telemetry.
- **Replaces / subsumes:** The M8 T02 defaults that were chosen from a
  small-N workstation sample.
- **Adds:** Exposed metrics on `CircuitBreaker.record_*` calls that flow
  to a Langfuse-style backend (depends on `nice_to_have.md` §1); a
  recalibration runbook entry that names the percentile thresholds the
  defaults should track.
- **Trigger to adopt** — any one of:
  - `nice_to_have.md` §1 (Langfuse) lands.
  - One full milestone of trip / recovery data accumulates after Langfuse
    is wired.
  - An operator complaint about a flaky-Ollama trip-loop indicates the
    defaults are wrong.
- **Why not now:** No telemetry surface. Tuning without data is the
  ceremony equivalent of moving deck chairs.
- **Related history:** M8 T02, M10 T05, M8 deep-analysis fragility #2.

#### Section 25 — Second-level fallback chain (Ollama → Claude Code → Gemini)

- **Role:** Extend `OllamaFallback` from a single replacement tier to an
  ordered chain so a `FallbackChoice.FALLBACK` that hits an *also-unavailable*
  replacement falls through to a third option.
- **Replaces / subsumes:** Today's `OllamaFallback(logical, fallback_tier)`
  shape (one replacement only).
- **Adds:** `OllamaFallback(logical, fallback_chain: list[str])`; logic in
  the FALLBACK-branch terminal node to walk the chain on `CircuitOpen` /
  health-check failure of the first replacement; a UX decision about
  whether to re-prompt the operator on each chain step.
- **Trigger to adopt** — any one of:
  - An incident where Claude Code OAuth is expired simultaneously with
    an Ollama outage and the FALLBACK branch fails opaquely.
  - A second long-running tier (e.g. a remote LLM gateway) is added to
    the registry and would naturally serve as a third fallback.
- **Why not now:** The single-level model has not been observed to fail
  (M8 close-out smoke + no incident reports in 0.1.x). The ADR-0003
  decision (fallback to `planner-synth`, KDR-003 OAuth subprocess)
  decouples the failure modes — Ollama-down ≠ Claude-Code-down on the
  same hardware in any observed scenario.
- **Related history:** ADR-0003, M10 T01, M8 deep-analysis debt #4.

#### Section 26 — Refactor sticky-OR + `_route_before_aggregate` into a gate factory

- **Role:** Promote the four-step recipe documented at architecture.md §8.4
  (M10 T03) into a higher-level graph-layer factory so future parallel
  workflows compose the fallback branch in one call instead of
  copy-pasting the recipe.
- **Replaces / subsumes:** The current copy-paste of the sticky-OR
  reducer + `_route_before_aggregate` router in slice_refactor.py and
  (when added) the same in any future parallel workflow.
- **Adds:** A new graph-layer factory; refactor of slice_refactor to
  consume it; tests that the refactored slice_refactor preserves the
  M10 T03 invariant. The factory's signature shape is deliberately not
  pre-specified — it should emerge from the third concrete example
  (current count: one — slice_refactor).
- **Trigger to adopt** — any one of:
  - A **third** parallel-fan-out workflow ships (planner is linear, so
    today's count is one — slice_refactor). With one example, the
    recipe is fine; with three, the copy-paste is a real maintenance
    cost.
  - The four-step recipe is observed to drift between two workflow
    implementations (i.e. someone copy-pastes wrong).
- **Why not now:** Premature abstraction. One parallel workflow + one
  recipe + one regression test (M10 T03's cross-workflow invariant test)
  is the right shape for a single example. Designing a factory off one
  example would over-fit.
- **Related history:** M10 T03, M8 deep-analysis fragility #5.

#### Section 27 — Extend `CircuitBreaker` to Gemini-backed LiteLLM tiers

- **Role:** Add per-Gemini-tier breakers so a Gemini partial outage under
  parallel fan-out doesn't thrash without a "stop trying" signal.
- **Replaces / subsumes:** Today's `_build_ollama_circuit_breakers`
  ([`ai_workflows/workflows/_dispatch.py`](../../../ai_workflows/workflows/_dispatch.py))
  only emits breaker entries for routes whose `model.startswith("ollama/")`.
- **Adds:** Three coupled changes, not just coverage:
  - A **rename** of `_build_ollama_circuit_breakers` →
    `_build_circuit_breakers` (the function is no longer Ollama-specific
    when this trigger fires). Internal call sites in
    [planner.py](../../../ai_workflows/workflows/planner.py) and
    [slice_refactor.py](../../../ai_workflows/workflows/slice_refactor.py)
    update to the new name.
  - Generalised classification of which tiers warrant a breaker
    (likely: every tier with a `RetryableTransient`-classifiable failure
    mode).
  - A coupled decision about whether each tier's breaker counts towards
    the `FallbackChoice.FALLBACK` promotion or has its own gate (Gemini
    has no obvious replacement tier inside KDR-003's vendor set, so
    `ABORT`-only may be the right shape for a Gemini trip).
- **Trigger to adopt** — any one of:
  - An observed Gemini partial outage under a `slice_refactor` parallel
    fan-out where retry-bucket exhaustion is the failure mode (instead
    of a clean trip).
  - A second remote LLM (e.g. Anthropic via OAuth) lands a non-trivial
    parallel fan-out and the breaker pattern needs to generalise.
- **Why not now:** Gemini's failure modes (503, quota) are well-served by
  the existing KDR-006 retry taxonomy; a breaker on top would conflate
  two independent failure-handling layers without observed need. The
  fallback gate is for *daemon-down* failures, not *quota-burst*.
- **Related history:** M10 T05, M8 deep-analysis fragility #7 + debt #5.

### [README.md](README.md) (M10 milestone) — slot mapping table + branch-count correction

Two coordinated edits to the M10 milestone README:

**(a)** Update the milestone README's `nice_to_have.md` slot references in
the **Exit criteria #6** list and the **Traceability to M8 deep-analysis**
table from `§17`–`§21` to `§23`–`§27` to match what this task lands.

| README reference | Old slot | New slot |
| --- | --- | --- |
| Multi-process / shared-state breaker | §17 | §23 |
| Empirical breaker tuning | §18 | §24 |
| Second-level fallback chain | §19 | §25 |
| Sticky-OR factory refactor | §20 | §26 |
| Gemini-tier breaker | §21 | §27 |

**(b)** Verify Exit criterion #3 reads "three-branch" — the M10
task-analysis pass corrected this pre-emptively against the
pre-revision "two-branch" drift, so the working tree should already
match T03's landed test name `test_three_branch_parallel_fanout_records_one_gate`.
If the README has been reset to "two-branch" since (e.g. via a botched
merge), restore the "three-branch" wording. T03's body explicitly fans
out three parallel `Send(...)` payloads, so the "three-branch" reading
is canonical.

### Smoke verification (Auditor runs)

```bash
grep -n "^## 23\.\|^## 24\.\|^## 25\.\|^## 26\.\|^## 27\." design_docs/nice_to_have.md
grep -n "Limitations" design_docs/architecture.md | head -5
```

Five new headings present in `nice_to_have.md`; the bold "Limitations"
marker present in `architecture.md` §8.4.

## Acceptance Criteria

- [ ] `architecture.md` §8.4 has a **Limitations** paragraph naming all
      three single-process assumptions and citing the landed slot
      numbers for the three "breaker scope / breaker tuning /
      single-level fallback" entries (planned §23 / §24 / §25; actual
      numbers recorded at the top of this task's issue file per the
      slot-drift defensive clause).
- [ ] `nice_to_have.md` has five new sections at the next-five
      consecutive free slots (planned §23–§27; actual numbers recorded
      at the top of this task's issue file), each with the six standard
      subsections.
- [ ] Each new entry has a **named, concrete, falsifiable trigger** (no
      vague "when convenient" / "eventually" wording).
- [ ] M10 README (this milestone's README) slot references updated from
      §17–§21 to the actual landed slot range in both Exit criteria #6
      and the Traceability table.
- [ ] No code change; diff is confined to `architecture.md`,
      `nice_to_have.md`, and the M10 README.
- [ ] `uv run pytest` green (sanity — doc edits should not break tests).
- [ ] `uv run lint-imports` reports **4 contracts kept**.
- [ ] `uv run ruff check` clean.
- [ ] `CHANGELOG.md` `[Unreleased]` gets a
      `### Changed — M10 Task 05: architecture.md §8.4 Limitations paragraph + five nice_to_have.md entries (<YYYY-MM-DD>)`
      entry citing the paragraph + the five new entries by their landed
      slot numbers (recorded at the top of this task's issue file).
      (`### Changed` because the architecture.md edit reframes existing
      content; the project's CHANGELOG vocabulary is `Added | Changed |
      Deprecated | Removed | Fixed | Security` per Keep-a-Changelog —
      `### Docs` is off-vocabulary.)

## Dependencies

- [Task 04](task_04_send_payload_invariant.md) — sequencing only; the doc
  sweep references the M10 T03 + T04 invariant tests as in-place regression
  guards, so those tests must exist before the architecture.md cross-reference
  is honest.

## Out of scope (explicit)

- **No code change to defaults.** `trip_threshold=3` / `cooldown_s=60.0`
  stay; §24 documents the trigger to revisit.
- **No actual implementation of any §23–§27 item.** This task only writes
  the deferral entries with named triggers.
- **No re-numbering of existing entries.** §1–§22 keep their numbers; the
  five new entries land at the tail.
- **No update to other milestone READMEs.** The slot drift between
  M10's plan date and today is M10's to absorb.

## Carry-over from task analysis

- [ ] **TA-LOW-01 — `nice_to_have.md` numbering gap at §8**
      (severity: LOW, source: task_analysis.md round 4)
      The slot-drift defensive section says "slots `§17`–`§22` were
      filled". Verified `nice_to_have.md` has 21 sections (§1–§7, §9–§22)
      — §8 is a long-standing numbering gap inherited from a pre-M10
      deletion. The practical conclusion (§23 is the next free slot) is
      correct, but the framing slightly mis-states the count.
      **Recommendation:** Either drop the "§17–§22 were filled" framing
      or add a footnote: *"Footnote on §8: long-standing numbering gap
      in `nice_to_have.md` (jumps from §7 to §9). Not a free slot — file
      pre-existed M10. If the Builder enumerates filled slots, exclude
      §8 from the count to avoid implying it's available."*
