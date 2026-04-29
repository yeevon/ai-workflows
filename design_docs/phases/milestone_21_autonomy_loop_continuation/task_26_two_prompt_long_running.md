# Task 26 — Two-prompt long-running pattern for multi-cycle Builder runs

**Status:** 📝 Planned.
**Kind:** Slimming / doc + code.
**Grounding:** [milestone README](README.md) · [research brief §T26 (NEW)](../milestone_20_autonomy_loop_optimization/research_analysis.md) — anchor `### T26 — Adopt Anthropic's two-prompt long-running pattern for multi-cycle Builder runs` · [Anthropic "Effective harnesses for long-running agents"](https://anthropic.com/engineering/effective-harnesses-for-long-running-agents) (cited in research brief §T26 verbatim). · [T03/T04 cycle-summary pattern](../milestone_20_autonomy_loop_optimization/) — predecessor; T26 strengthens it. · `.claude/commands/auto-implement.md` (`runs/<task>/cycle_<N>/summary.md` is the existing carry-forward) · `.claude/agents/builder.md` (current Builder spawn shape). KDR drift checks apply per M21 scope note (autonomy-infra; no direct KDR citation needed).

## Why this task exists

Multi-cycle Builder runs (≥ 3 cycles) drift in two reproducible ways without an *initializer + coding-agent* split (Anthropic's "Effective harnesses for long-running agents", 2026): (1) one-shot context exhaustion mid-implementation, (2) features left half-implemented + undocumented across cycle boundaries. The current `runs/<task>/cycle_<N>/summary.md` pattern (T03) carries a *per-cycle* snapshot; the two-prompt pattern adds a *per-task* plan written once at cycle 1 + a running progress file that accumulates across cycles. Plan = stable; progress = monotonically updated.

T26 is meta-infrastructure: it wires the pattern into `auto-implement` for the trigger condition and documents it in `agent_docs/long_running_pattern.md`. T26 itself does not exercise the pattern (T26 is small enough to ship in 1–2 cycles); future long-running tasks (T17 spec-format extension at scale, T18 parallel-builders, etc.) trigger it.

## Pattern (locked at T26)

### Trigger

The pattern fires when **either** of these is true at the start of cycle N:

1. The task spec explicitly opts in (`**Long-running:** yes` line under the spec header).
2. `N ≥ 3` (third Builder cycle on the same task).

For N < 3 and no opt-in, the existing T03 cycle-summary pattern is the only carry-forward and the pattern stays dormant.

### File shape

When the trigger fires, two files live under `runs/<task-shorthand>/`:

- **`plan.md`** — written **once** at cycle 1 start (or first time the trigger fires). Immutable thereafter. Contains: task goal in one paragraph; ordered list of milestones / deliverables; explicit out-of-scope items copied from the spec; locked decisions known at task start. Sourced from the spec; no new scope.
- **`progress.md`** — updated at the end of **every** Builder cycle. Append-only sectioned by cycle: `## Cycle <N> (YYYY-MM-DD)` with: what landed (file list with one-line descriptions), what's deferred to next cycle, locked decisions made this cycle, blockers (if any).

These supplement (not replace) the per-cycle `runs/<task>/cycle_<N>/summary.md` files. The `cycle_<N>/summary.md` is the per-cycle snapshot the orchestrator carries to Builder cycle `N+1` per the existing T03 read-only-latest-summary rule. The progress file is the *cumulative* surface that survives across cycles + the plan file.

### Builder cycle-N spawn (when trigger is on)

Replace the cycle ≥ 2 read-only-latest-summary rule with: pass `plan.md` (full content, immutable) + `progress.md` (full content, monotonic). Drop the prior cycle's `summary.md` from the Builder's pre-load (it becomes implicit in `progress.md`'s most recent `## Cycle <N>` section). The Auditor continues to emit `cycle_<N>/summary.md` per the existing T03 cycle-summary rule (`.claude/agents/auditor.md` Phase 5b); that file remains the per-cycle artifact for telemetry + audit trail.

### Auditor writes progress.md update at end of each cycle

The Auditor — not the Builder — owns `progress.md` updates, extending its existing Phase 5b cycle-summary write. After emitting `cycle_<N>/summary.md`, the Auditor also appends a fresh `## Cycle <N>` section to `progress.md`. Single-writer for the cumulative-state surface keeps it free of sync drift; the Builder's 3-line return-text schema stays pure (no Builder-side file writes beyond the durable code/doc artefacts the spec calls for). This mirrors the existing pattern of "Auditor owns durable per-cycle state" already locked at T03/T04.

### Initializer step (one-shot at cycle 1 when trigger is on)

The orchestrator (in `auto-implement.md`'s project-setup step) checks the trigger. If on:

1. Read the task spec.
2. Write `runs/<task>/plan.md` — extracted from spec §Why this task exists + §What to Build (high level) + §Out of scope + §Acceptance criteria. No invented scope.
3. Seed `runs/<task>/progress.md` with the heading `# Progress — <task>` and an empty `## Cycle 1` section the Builder will populate.

This is a one-shot, in-line orchestrator step (not a separate agent spawn — a separate spawn is too heavyweight for what is essentially a copy-from-spec).

## What to Build

### Step 1 — Update `agent_docs/long_running_pattern.md` (creates `agent_docs/`)

Create `agent_docs/` directory (does not yet exist on disk). Inside, create `long_running_pattern.md` documenting the pattern end-to-end. Sections (each ≤ 500 tokens per T24 rubric, applied transitively):

- 3-line top-of-file summary (T24 rule 1).
- `## Trigger` — the two trigger conditions (opt-in + ≥3 cycles).
- `## File shape` — plan.md + progress.md format.
- `## Builder cycle-N spawn changes` — what differs from the T03 cycle-summary rule when the trigger is on.
- `## Initializer step` — what the orchestrator does at cycle 1.
- `## Reference Builder loop` — a concrete example (e.g. a hypothetical T17 / T18 worked example).

### Step 2 — Update `auto-implement.md` to wire the pattern

Add a new section `## Two-prompt long-running pattern (T26)` immediately after `## Project setup`. Inside, the orchestrator's trigger check + initializer step + Builder spawn change for cycle ≥ 2 when trigger is on. Cross-link to `agent_docs/long_running_pattern.md` for the full reference. The existing read-only-latest-summary rule remains the default (when trigger is off).

### Step 3 — Wire the cycle-input override (split across `auto-implement.md` + `builder.md`)

The cycle-input rule lives in `.claude/commands/auto-implement.md` (existing §`### Builder spawn — read-only-latest-summary rule` near line 126). The Builder-side schema-purity reminder belongs in `builder.md` §Hard rules (line 37). Two surgical edits:

1. **`auto-implement.md` edit** — append a one-line **T26 long-running trigger override** to the existing read-only-latest-summary rule near line 126: "**T26 long-running trigger override** — when `runs/<task>/plan.md` and `runs/<task>/progress.md` exist, replace the cycle-N≥2 `cycle_{N-1}/summary.md` pre-load entry with `plan.md` (immutable) + `progress.md` (cumulative). See `agent_docs/long_running_pattern.md`."

2. **`builder.md` §Hard rules edit** — append one bullet: "When the T26 long-running trigger fires (orchestrator passes `plan.md` + `progress.md` instead of `cycle_{N-1}/summary.md`), the 3-line return-text schema is unchanged; `progress.md` is owned by the Auditor (Phase 5b extension), not the Builder."

The `auto-implement.md` half carries the cycle-input mechanics; the `builder.md` half mirrors the `_common/non_negotiables.md` Rule 1 commit-discipline reminder pattern (Builder-side schema-purity anchor).

### Step 3b — Update `.claude/agents/auditor.md` Phase 5b

Extend Phase 5b: after emitting `cycle_<N>/summary.md`, the Auditor checks whether `runs/<task>/progress.md` exists. If it does (T26 trigger fired), append a fresh `## Cycle <N>` section mirroring the summary's content shape. Smoke step 4 of T26 greps `auditor.md` for the `progress.md` Phase-5b extension reference.

### Step 4 — Update README §G5

M21 README §Exit criteria §G5 already reads: "Two-prompt pattern documented in `agent_docs/long_running_pattern.md` with reference Builder loop." Amend with a satisfaction parenthetical at T26 close: `(satisfied at T26; pattern locked, agent_docs/ created)`. Same shape as T11's G1 / T24's G2 / T12's G6.

## Deliverables

- `agent_docs/long_running_pattern.md` — new file (creates `agent_docs/` directory).
- Edit to `.claude/commands/auto-implement.md` — new `## Two-prompt long-running pattern (T26)` section + one-line cross-link from §Project setup, plus the T26 long-running trigger override appended to the existing `### Builder spawn — read-only-latest-summary rule` near line 126.
- Edit to `.claude/agents/builder.md` — one-bullet addition to §Hard rules (line 37) about Builder schema purity when T26 trigger fires.
- Edit to `.claude/agents/auditor.md` — Phase 5b extension: after emitting `cycle_<N>/summary.md`, append a fresh `## Cycle <N>` section to `runs/<task>/progress.md` when the file exists (T26 trigger fired).
- Edit to `design_docs/phases/milestone_21_autonomy_loop_continuation/README.md` row 76 description — replace `iter_<N>_plan.md` / `iter_<N>_progress.md` phrasing with the locked file shape (per AC 8(b)).
- `CHANGELOG.md` updated under `[Unreleased]`.
- M21 README §Exit criteria §G5 prose amended with satisfaction parenthetical (matches T11/T24/T12 pattern).

## Tests / smoke (Auditor runs)

```bash
# 1. agent_docs/ directory + long_running_pattern.md exist.
test -d agent_docs && echo "agent_docs/ exists"
test -f agent_docs/long_running_pattern.md && echo "pattern doc exists"

# 2. T24 rubric holds for agent_docs/. Note: `--check section-count` is intentionally
# NOT invoked against agent_docs/ here — that rubric value (`--min 2`) was inherited
# from .claude/agents/* where multi-section is the rule, but agent_docs/ may
# legitimately carry tightly-scoped one-pagers. Future agent_docs/ files inherit only
# rules 1–3 + 4 (no inline code > 20 lines), not rule 2 section-count.
uv run python scripts/audit/md_discoverability.py --check summary --target agent_docs/
uv run python scripts/audit/md_discoverability.py --check section-budget --target agent_docs/
uv run python scripts/audit/md_discoverability.py --check code-block-len --target agent_docs/ --max 20

# 3. auto-implement.md has the new section.
grep -qE '^## Two-prompt long-running pattern \(T26\)' .claude/commands/auto-implement.md && echo "auto-implement section present"

# 4. builder.md + auditor.md + auto-implement.md carry T26's wiring (semantic patterns,
# not just literal-string presence). Phase patterns guard against wrong-section drops.
grep -qE 'T26.*long.running|plan\.md.*progress\.md' .claude/agents/builder.md && echo "builder.md notes T26 trigger"
grep -qE 'progress\.md.*Phase 5b|Phase 5b.*progress\.md|append.*progress\.md' .claude/agents/auditor.md && echo "auditor.md owns progress.md (Phase 5b extension)"
grep -qE 'T26.*long.running.*trigger|plan\.md.*progress\.md' .claude/commands/auto-implement.md && echo "auto-implement.md wires the trigger override"

# 5. T10 invariant preserved (9 agents reference _common/non_negotiables.md).
rm -f /tmp/aiw_t26_t10inv.txt
grep -lF '_common/non_negotiables.md' .claude/agents/architect.md .claude/agents/auditor.md \
  .claude/agents/builder.md .claude/agents/dependency-auditor.md \
  .claude/agents/roadmap-selector.md .claude/agents/security-reviewer.md \
  .claude/agents/sr-dev.md .claude/agents/sr-sdet.md .claude/agents/task-analyzer.md \
  > /tmp/aiw_t26_t10inv.txt
awk 'END { exit !(NR == 9) }' /tmp/aiw_t26_t10inv.txt && echo "T10 invariant held (9/9)"

# 6. T24 invariant preserved on .claude/agents/.
uv run python scripts/audit/md_discoverability.py --check section-budget --target .claude/agents/

# 7. CHANGELOG anchor.
grep -qE '^### (Added|Changed) — M21 Task 26:' CHANGELOG.md && echo "CHANGELOG anchor present"
```

## Acceptance criteria

1. `agent_docs/long_running_pattern.md` exists, satisfies all four T24 rubric checks (smoke step 2 all pass).
2. `agent_docs/` is the new directory created by this task.
3. `.claude/commands/auto-implement.md` carries the new `## Two-prompt long-running pattern (T26)` section with the trigger / initializer / spawn-change content. Smoke step 3 passes.
4. `.claude/agents/builder.md` references both `plan.md` and `progress.md`. Smoke step 4 passes.
5. T10 invariant held (smoke step 5 = 9).
6. T24 invariant held — `.claude/agents/*.md` still passes section-budget check (smoke step 6 zero exit).
7. `CHANGELOG.md` updated under `[Unreleased]` with `### Added — M21 Task 26: Two-prompt long-running pattern (agent_docs/long_running_pattern.md; auto-implement + builder wired for trigger ≥3 cycles)`.
8. Status surfaces flip together: (a) T26 spec `**Status:**` line moves from `📝 Planned` to `✅ Done`, (b) M21 README task-pool row 76 (the T26 row) Status column moves from `📝 Candidate` to `✅ Done`, AND row 76's description is amended to match the spec's locked file shape: replace `(initializer prompt produces \`iter_<N>_plan.md\` and \`iter_<N>_progress.md\`; subsequent cycles update only progress file)` with `(one immutable \`runs/<task>/plan.md\` written at cycle 1; cumulative \`runs/<task>/progress.md\` appended each cycle when trigger fires — opt-in or N≥3)`. (c) M21 README §Exit criteria §G5 prose is amended in-place with a satisfaction parenthetical (e.g. `(satisfied at T26; pattern locked, agent_docs/ created)`).

## Out of scope

- **Exercising the pattern on an actual ≥ 3-cycle task.** T26 is meta-infrastructure; future long-running tasks (T17 / T18 / etc.) exercise it. T26 ships with the wiring, not the trigger fire.
- **Replacing the existing T03 cycle-summary pattern.** Both coexist — `cycle_<N>/summary.md` remains the per-cycle snapshot for the Auditor's read-only-latest-summary rule; `plan.md` + `progress.md` are the long-running supplements.
- **Removing the existing read-only-latest-summary rule.** It stays as default for short tasks (cycles 1–2 with no opt-in).
- **Adding a separate "initializer" agent.** The initializer is an inline orchestrator step (one-time copy from spec); spawning a dedicated agent for what is a 30-line copy-paste is too heavyweight.
- **`agent_docs/` content beyond `long_running_pattern.md`.** Future doc-only tasks may add more files; T26 only adds the one file the README G5 names.
- **CI gate for `agent_docs/` discoverability.** Deferred to T25 (same destination as T24's TA-LOW-02 + T12's `nice_to_have.md`-adjacent CI hookup).
- **Rewriting `auto-implement.md` more broadly.** Surgical addition of one new section + one cross-link only.
- **Adopting items from `nice_to_have.md`.**
- **Runtime code changes** (per M21 scope note).

## Dependencies

- **Built on T03/T04** (cycle-summary pattern; T26 strengthens it). Both M20 — closed.
- **Built on T10/T11/T24/T12.** Requires the rubric-conformant agent prompts + slimmed CLAUDE.md + T24 audit script (transitive walk) + Skill-extraction precedent.
- **Precedes T17/T18/T19** (parallel-builders). When parallel-Builder tasks land, the long-running pattern is the carry-forward shape they consume.
- **No cross-milestone dependencies.**

## Carry-over from prior milestones

*None.*

## Carry-over from prior audits

*None at draft time.*

## Carry-over from task analysis

- [ ] **TA-LOW-01 — Promote pattern-section H3s to H2s when transposing into `agent_docs/long_running_pattern.md`** (severity: LOW, source: task_analysis.md round 6 / T26 round 1, carried through round 8)
      Spec's `## Pattern (locked at T26)` section is ~580 tokens — fine in the spec (not enforced by `md_discoverability.py`), but a Builder copy-paste into `agent_docs/long_running_pattern.md` as one section would fail T24 rubric.
      **Recommendation:** When transposing the content, promote each H3 (Trigger / File shape / Builder cycle-N spawn / Auditor writes progress.md / Initializer step / Reference Builder loop) to a top-level H2 so each section stays ≤500 tokens per T24 rubric.

- [ ] **TA-LOW-02 — AC 8(b) old_string uses backslash-escaped backticks; the README's actual text is unescaped** (severity: LOW, source: task_analysis.md round 7 / T26 round 2)
      AC 8(b) gives the README row-76 fix as `replace X with Y` where X and Y are written with `\``. The README's actual text uses plain backticks. Verbatim copy into `Edit` would fail.
      **Recommendation:** Builder uses unescaped backticks when constructing the `Edit` `old_string`/`new_string` (trivial hand-correction).

- [ ] **TA-LOW-03 — Builder return-text schema reminder must be copy-pasted verbatim** (severity: LOW, source: task_analysis.md round 6 / T26 round 1, re-affirmed round 8)
      The schema-purity bullet (Step 3 second edit) is the explicit anchor against the recurring `feedback_builder_schema_non_conformance.md` pattern. Paraphrasing dilutes the anchor.
      **Recommendation:** Builder copies the exact text from Step 3: "When the T26 long-running trigger fires (orchestrator passes `plan.md` + `progress.md` instead of `cycle_{N-1}/summary.md`), the 3-line return-text schema is unchanged; `progress.md` is owned by the Auditor (Phase 5b extension), not the Builder."
