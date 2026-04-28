# Cycle Summary Template

**Task:** M20 Task 03 — In-task cycle compaction (`cycle_<N>/summary.md` per Auditor)
**Canonical reference for:** Auditor Phase 5 (cycle-summary emission); slash commands
  that consume cycle summaries for Builder/Auditor spawn on cycle N ≥ 2.

This file is the single source of truth for the `cycle_<N>/summary.md` template.
The Auditor emits one summary file per cycle as a side-effect of its existing Phase 5
work (issue-file write).  Orchestrators read ONLY the latest summary when constructing
cycle N+1 spawn prompts — not the full Builder+Auditor chat history from prior cycles.

---

## Directory layout

Cycle summaries live inside the per-task nested `runs/` directory:

```
runs/<task-shorthand>/
  cycle_1/
    summary.md           ← this file (Auditor emits; orchestrator reads)
    ...
  cycle_2/
    summary.md
    ...
  cycle_N/
    summary.md
    ...
```

`<task-shorthand>` format: `m<MM>_t<NN>` with both M and T zero-padded to two digits
(e.g. `m20_t03`, `m05_t02`, `m09_t01`).  This avoids lexical ambiguity between
`m1_t1` and `m1_t10`.

The nested `cycle_<N>/summary.md` path is authoritative.  The flat form
`cycle_<N>_summary.md` is incorrect and must not be used.

---

## Template

The Auditor writes this Markdown structure verbatim (filling in values from the
issue file it just wrote in Phase 5):

```markdown
# Cycle <N> summary — Task <NN>

**Cycle:** N
**Date:** YYYY-MM-DD
**Builder verdict:** <BUILT | BLOCKED | STOP-AND-ASK>
**Auditor verdict:** <PASS | OPEN | BLOCKED>
**Files changed this cycle:** <bullet list or "none">
**Gates run this cycle:**

| Gate | Command | Result |
|---|---|---|
| pytest | `uv run pytest` | PASS / FAIL |
| lint-imports | `uv run lint-imports` | PASS / FAIL |
| ruff | `uv run ruff check` | PASS / FAIL |

**Open issues at end of cycle:** <count by severity + IDs, e.g. "2 HIGH (M20-T03-ISS-01, M20-T03-ISS-02), 1 LOW" — or "none">
**Decisions locked this cycle:** <bullet list of Auditor-agreement-bypass locks, user
  arbitrations, or KDR carry-overs locked this cycle — or "none">
**Carry-over to next cycle:** <bullet list of explicit ACs the next Builder cycle must
  satisfy — or "none" if Auditor verdict is PASS>
```

---

## Invariants

1. **Extension, not replacement.**  The `cycle_<N>/summary.md` is a structured
   *projection* of the issue file the Auditor already wrote in Phase 5 — they share the
   same underlying content.  The issue file remains the authoritative artifact;
   `summary.md` is optimised for orchestrator re-read.
2. **Written after the issue file, before Phase 6.**  In Phase 5: write the issue file
   first, then write `cycle_<N>/summary.md`.  Phase 6 (forward-deferral propagation)
   runs after both.
3. **Orchestrator reads only the latest summary.**  On cycle N (N ≥ 2), the orchestrator
   feeds `cycle_{N-1}/summary.md` to both the Builder and Auditor spawn prompts — not
   the full chat content of cycles 1..N-1.
4. **Carry-over populated when OPEN.**  The `Carry-over to next cycle:` field must be
   non-empty whenever the Auditor verdict is `OPEN` — it must list the specific ACs the
   next Builder cycle must satisfy.  Empty carry-over on an OPEN verdict is a spec
   violation.
5. **Directory creation on cycle 1.**  The orchestrator creates `runs/<task>/cycle_1/`
   at the start of cycle 1.  Subsequent cycles create `cycle_<N>/`.

---

## Read-only-latest-summary rule (for orchestrators)

### Cycle 1

Builder spawn-prompt input:
- Task spec path
- Parent milestone README path
- Project context brief
- Issue file path (may not exist yet)

Auditor spawn-prompt input:
- Task spec path
- Issue file path
- Parent milestone README path
- Project context brief
- Current `git diff`
- Cited KDR identifiers (compact pointer)

### Cycle N (N ≥ 2)

Builder spawn-prompt input:
- Task spec path
- Issue file path
- **Most recent `runs/<task>/cycle_{N-1}/summary.md`** (path reference + content)
- Project context brief

**Do not include** prior Builder reports' chat content, prior Auditor chat content, or
prior summaries beyond `cycle_{N-1}/summary.md`.  The summary is the durable
carry-forward; earlier chat history is ephemeral.

Auditor spawn-prompt input:
- Task spec path
- Issue file path
- Parent milestone README path
- Project context brief
- Current `git diff`
- Cited KDR identifiers (compact pointer)
- **Most recent `runs/<task>/cycle_{N-1}/summary.md`** (path reference + content)

**Do not include** prior cycle summaries beyond the most recent one.

---

## Notes

- This file is the third entry under `.claude/commands/_common/` (after
  `agent_return_schema.md` from T01 and `spawn_prompt_template.md` from T02).
- The template is implemented as a document convention, not a Python class —
  the Auditor writes it inline during Phase 5; tests in
  `tests/orchestrator/test_cycle_summary_emission.py` validate the structure.
- Future M20 tasks populate additional files in `_common/`:
  `parallel_spawn_pattern.md` (T05), `dispatch_table.md` (T07),
  `gate_parse_patterns.md` (T08), `integrity_checks.md` (T09),
  `effort_table.md` (T21), `auditor_context_management.md` (T27).
