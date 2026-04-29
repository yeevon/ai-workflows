# Task 17 — Spec Format Extension (per-slice file/symbol scope)

**Status:** 📝 Planned.
**Kind:** Parallelism / doc + code.
**Grounding:** [milestone README](README.md) · [research brief §T17](../milestone_20_autonomy_loop_optimization/research_analysis.md) — anchor `### T17 — Spec format extension (per-slice file/symbol scope)` · [T16 spec](task_16_sweep_command.md) (✅ Done — most-recent Phase F template) · [`clean-tasks.md`](../../../.claude/commands/clean-tasks.md) (Phase 1 generation + Phase 2 analysis — the primary surface this task extends) · [`auto-implement.md`](../../../.claude/commands/auto-implement.md) §Functional loop (Builder spawn — per-slice routing when parallel flag set). KDR drift checks apply per M21 scope note.

## Why this task exists

The parallel-Builders foundation (T18/T19) requires each task spec to declare which files belong to which slice before the orchestrator can dispatch separate Builder agents. Without that declaration, the orchestrator has no machine-readable boundary — it can't know that AC-1 touches `ai_workflows/primitives/` while AC-2 touches `ai_workflows/graph/`, so it can't launch isolated workers.

T17 lands the per-slice file/symbol scope declaration as an optional `## Slice scope` section in task specs. It benefits serial Builders too: a clearer review signature means the Auditor and sr-dev can immediately identify which AC maps to which files, reducing hallucinated-scope findings. The `/clean-tasks` Phase 1 generator learns to emit a `## Slice scope` stub when the README's task row lists multiple file-disjoint ACs.

T17 is the prerequisite for T18 (parallel-Builder dispatch) and T19 (orchestrator close-out). It is explicitly **in-scope for M21** (unlike T18/T19 which are stretch).

## What to Build

### Step 1 — Define the `## Slice scope` spec section format

Extend the task-spec format reference in `.claude/commands/clean-tasks.md` Phase 1 (§Generate section) with the following additions:

**New section template to append when `ACs decompose into file-disjoint slices`:**

```markdown
## Slice scope (optional — required for parallel-Builder dispatch)

| Slice | ACs | Files / symbols |
|-------|-----|-----------------|
| slice-A | AC-1, AC-2 | `ai_workflows/primitives/foo.py`, `tests/test_foo.py` |
| slice-B | AC-3 | `ai_workflows/graph/bar.py`, `tests/test_bar.py` |
```

Rules (document in `clean-tasks.md` Phase 1 §Slice scope rules):
1. The section is **optional**. Specs without it run serial as today.
2. When present, every AC must appear in exactly one slice row. ACs that span multiple files may be grouped into one slice if they cannot be executed in isolation.
3. Slice names are freeform lowercase (e.g. `slice-a`, `primitives-layer`, `tests-only`).
4. Files must be repo-relative paths. Symbols are optional (e.g. `foo.py::BarClass::baz_method`).
5. A spec with this section is a **candidate for parallel dispatch** in T18. Tasks without the section always run serial.

### Step 2 — Update `/clean-tasks` Phase 1 generator

Edit `.claude/commands/clean-tasks.md` §Phase 1 Generate step 4 to add:

> If the milestone README task row enumerates ≥ 2 file-disjoint acceptance-criterion groups (e.g. "AC-1 touches primitives; AC-2 touches graph"), emit a `## Slice scope` stub with one row per group. Leave the `Files / symbols` column populated with `<TODO — fill at spec-review time>`. If the task row is not explicitly multi-slice or the spec author would need to invent the file boundaries, omit the section.

### Step 3 — Update `/auto-implement` pre-flight parallel-flag check

Edit `.claude/commands/auto-implement.md` §Project setup to add a one-paragraph note:

> **Parallel-build flag (T18 gate):** At project-setup time, check whether the task spec contains a `## Slice scope` section. If present, record `PARALLEL_ELIGIBLE=true` in `runs/<task>/meta.json` alongside the pre-task commit SHA. If absent, `PARALLEL_ELIGIBLE=false`. In M21 with T18 not yet shipped, this flag is always `false` in practice — the check is a forward-compatible stub.

### Step 4 — Add `tests/test_t17_spec_format.py`

6 test cases:
1. Slice scope section detected in a spec that has it (happy path).
2. Slice scope section absent in a spec without it (serial-as-today path).
3. AC-to-slice mapping: every AC in the table appears exactly once (validation invariant).
4. Duplicate AC in two slice rows raises a detectable violation.
5. Files column must not be empty when section is present (empty `<TODO>` is acceptable at draft time; a non-`<TODO>` non-empty value is valid).
6. meta.json `PARALLEL_ELIGIBLE` field written correctly for a spec with vs. without the section.

### Step 5 — Update M21 README §G4 prose

Mark G4 as satisfied: `(G4 satisfied at T17 — format spec + auto-implement gate check land; T18/T19 stretch pending per §Suggested phasing)`.

### Step 6 — Update `CHANGELOG.md`

Add `### Added — M21 Task 17: Spec format extension (per-slice file/symbol scope) (<YYYY-MM-DD>)` under `## [Unreleased]`.

## Deliverables

- Edit to `.claude/commands/clean-tasks.md` — add `## Slice scope` section template, rules, and Phase 1 generator guidance.
- Edit to `.claude/commands/auto-implement.md` — add parallel-flag check stub at project-setup time (writes `runs/<task>/meta.json`).
- `tests/test_t17_spec_format.py` — new (6 test cases).
- Edit to M21 README §G4 prose.
- `CHANGELOG.md` updated.

## Tests / smoke (Auditor runs)

```bash
# 1. clean-tasks.md has Slice scope section added.
grep -qE '## Slice scope' .claude/commands/clean-tasks.md && echo "clean-tasks.md slice section OK"

# 2. auto-implement.md has parallel-flag check stub.
grep -qiE 'PARALLEL_ELIGIBLE|parallel.build.flag|slice.scope' .claude/commands/auto-implement.md && echo "auto-implement.md gate check OK"

# 3. Tests exist and pass.
test -f tests/test_t17_spec_format.py && echo "test file exists"
uv run pytest tests/test_t17_spec_format.py -q

# 4. Gates clean.
uv run lint-imports >/dev/null && echo "lint-imports green"
uv run ruff check >/dev/null && echo "ruff green"

# 5. CHANGELOG anchor.
grep -qE '^### (Added|Changed) — M21 Task 17:' CHANGELOG.md && echo "CHANGELOG anchor"

# 6. M21 README G4 updated.
grep -qiE 'G4.*T17|T17.*satisfied' design_docs/phases/milestone_21_autonomy_loop_continuation/README.md && echo "README G4 updated"

# 7. T10 invariant held.
grep -lF '_common/non_negotiables.md' .claude/agents/architect.md .claude/agents/auditor.md \
  .claude/agents/builder.md .claude/agents/dependency-auditor.md \
  .claude/agents/roadmap-selector.md .claude/agents/security-reviewer.md \
  .claude/agents/sr-dev.md .claude/agents/sr-sdet.md .claude/agents/task-analyzer.md \
  | wc -l | awk '{ exit !($1 == 9) }' && echo "T10 9/9"

# 8. T24 invariant on .claude/agents/.
uv run python scripts/audit/md_discoverability.py --check section-budget --target .claude/agents/
```

## Acceptance criteria

1. `.claude/commands/clean-tasks.md` extended: `## Slice scope` section template + 5 rules documented in Phase 1 §Generate; Phase 1 generator emits stub when milestone README enumerates ≥ 2 file-disjoint AC groups. Smoke 1 passes.
2. `.claude/commands/auto-implement.md` extended: parallel-flag check stub at project-setup time (reads spec, writes `runs/<task>/meta.json` with `PARALLEL_ELIGIBLE`). Smoke 2 passes.
3. `tests/test_t17_spec_format.py` passes (6 test cases). Smoke 3 passes.
4. All CI gates green. Smoke 4 passes.
5. `CHANGELOG.md` updated. Smoke 5 passes.
6. M21 README §G4 updated with T17 satisfaction note. Smoke 6 passes.
7. T10 invariant held (9/9 agent files reference `_common/non_negotiables.md`). Smoke 7 passes.
8. T24 invariant held on `.claude/agents/`. Smoke 8 passes.
9. Status surfaces flip together: (a) T17 spec `**Status:**` → `✅ Done`, (b) M21 README task-pool T17 row → `✅ Done`.

## Out of scope

- **Actual parallel Builder dispatch** — T18.
- **Orchestrator close-out after parallel merge** — T19.
- **Mandatory slice sections on existing specs.** The section is always optional; existing specs remain valid.
- **Spec-validation CI gate.** A future task can add an `md_slice_validator.py` CI step; T17 only defines the format and tests the parser used at dispatch time.
- **Runtime code changes in `ai_workflows/`.** Per M21 scope note.
- **Adopting `nice_to_have.md` items.**

## Dependencies

- **All Phase E + F tasks Done** — T10 (common rules), T11 (CLAUDE.md slim), T12 (skills), T24 (MD discoverability), T25 (audit), T26 (two-prompt pattern), T13/T14/T15/T16 (productivity commands).
- **Blocks T18 and T19** — they cannot run until the format spec exists.

## Carry-over from prior milestones

*None.*

## Carry-over from prior audits

*None.*

## Carry-over from task analysis

- [ ] **TA-LOW-01 — Agent count hard-pin at 9 in smoke step 7** (severity: LOW, source: task_analysis.md round 20)
      Smoke step 7 pins the `_common/non_negotiables.md` reference count to exactly 9 — kept for sibling parity with T13–T16. Acceptable as-is.
      **Recommendation:** Future agent-roster changes will need to sweep all sibling smokes that use this 9-pin.
