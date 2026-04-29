# Task 16 — `/sweep` ad-hoc reviewer Skill

**Status:** ✅ Done.
**Kind:** Productivity / code + doc.
**Grounding:** [milestone README](README.md) · [research brief §T13–T16](../milestone_20_autonomy_loop_optimization/research_analysis.md) — anchor `### T13–T16 — New commands (/triage, /check, /ship, /sweep)` · [T13 spec](task_13_triage_command.md) (✅ Done — Phase F template precedent) · [T14 spec](task_14_check_command.md) (✅ Done — second Phase F Skill). KDR drift checks apply per M21 scope note.

## Why this task exists

The autonomy-mode terminal gate runs sr-dev + sr-sdet + security-reviewer in parallel against a clean cycle, but those agents only fire as part of `/auto-implement`'s end-of-cycle ceremony. When the operator wants ad-hoc reviewer feedback on a working-tree diff (e.g., a bug fix in progress, an exploratory branch, a PR that hasn't shipped through autopilot), there's no one-shot surface — the operator hand-spawns the three agents.

`/sweep` makes that ad-hoc review a one-shot Skill: run sr-dev + sr-sdet + security-reviewer against the current `git diff` (vs HEAD or a passed base ref) and produce a consolidated report.

T16 is the third Phase F Skill after T13 (`/triage`) and T14 (`/check`). Same template inheritance.

## Skill structure (per `_common/skills_pattern.md`)

T16 follows the 4-rule shape:

1. Frontmatter: `name: sweep`, `description:` (≤ 200 chars, trigger-led), `allowed-tools: Bash` (T16 only invokes `git diff` + the orchestrator-side Task spawn).
2. Body ≤ 5K tokens.
3. Body references `runbook.md` for spawn-prompt templates per reviewer; doesn't inline.
4. New Skill — no agent-prompt duplication risk.

## What to Build

### Step 1 — Create `.claude/skills/sweep/SKILL.md`

Body (≤ 5K tokens) with required `## Inputs / ## Procedure / ## Outputs / ## Return schema` anchors plus `## When to use` / `## When NOT to use`:

```markdown
---
name: sweep
description: Run sr-dev + sr-sdet + security-reviewer against the working-tree diff. Use for ad-hoc review of a branch / fix / exploratory diff outside the auto-implement terminal gate.
allowed-tools: Bash
---

# sweep

Ad-hoc reviewer Skill: spawns sr-dev + sr-sdet + security-reviewer against the current `git diff` and produces a consolidated three-fragment report.

## When to use

- For ad-hoc review of a working-tree diff that hasn't shipped through /auto-implement.
- For a fix-in-progress when you want reviewer feedback before committing.
- For an exploratory branch that's outside the autonomy-mode flow but needs the same lens-set.

## When NOT to use

- During /auto-implement runs — the terminal gate already runs the three reviewers; /sweep duplicates that.
- For post-halt diagnosis — use /triage instead.
- For pre-publish wheel inspection — use dep-audit Skill.

## Inputs

Default: `git diff HEAD` (working tree vs current commit). Optional flags:
- `--base <ref>` — diff against a specific base ref (e.g. `--base main` for branch-vs-main).
- `--files <list>` — restrict to a comma-separated file list.

## Procedure

1. Compute the diff via `git diff <base> [-- <files>]`. Capture stat + name-only output. Skip if diff is empty (verdict: NO-DIFF).
2. Aggregate the files-touched list (passed to all three reviewers).
3. Spawn sr-dev + sr-sdet + security-reviewer in parallel via three Task tool calls in one orchestrator turn (per `_common/parallel_spawn_pattern.md`). Each reviewer writes its fragment to `runs/sweep/<timestamp>/<reviewer>-review.md`.
4. After all three complete, parse the 3-line return-schema verdicts.
5. Apply the precedence rule from `auto-implement.md` §G2: any BLOCK → SWEEP-BLOCK; any FIX-THEN-SHIP (no BLOCK) → SWEEP-FIX; all SHIP → SWEEP-CLEAN.

## Outputs

Write `runs/sweep/<timestamp>/report.md` (consolidated) plus per-reviewer fragments:

- **Consolidated report** — overall verdict + per-reviewer summary line + pointer to each fragment.
- **Per-reviewer fragments** — full review content as written by the agent.

## Return schema

3-line `verdict: / file: / section:` matching `.claude/commands/_common/agent_return_schema.md`. Verdict values: `SWEEP-CLEAN | SWEEP-FIX | SWEEP-BLOCK | NO-DIFF`. `file:` = consolidated report path. `section:` = `—`.

## Helper files

- `runbook.md` — spawn-prompt templates per reviewer (sr-dev / sr-sdet / security); precedence-rule reminder; example consolidated reports.
```

### Step 2 — Create `.claude/skills/sweep/runbook.md`

T24-rubric-conformant. Sections:

- 3-line summary.
- `## Spawn-prompt templates` — three minimal-pre-load prompts per reviewer.
- `## Precedence rule` — CLEAN/FIX/BLOCK aggregation logic.
- `## Example reports` — one CLEAN, one FIX-THEN-SHIP example.

### Step 3 — Add `tests/test_t16_sweep.py`

Mirror T13/T14 pattern: 6 cases (frontmatter parse + char/token budgets + four required anchors + helper-file ref + runbook T24-rubric subprocess).

### Step 4 — Update README §G3

Extend §G3 satisfaction list: `(satisfied at T13 with /triage; T14 adds /check; T16 adds /sweep; T15 separate)`.

### Step 5 — Update `_common/skills_pattern.md`

Extend the existing single `Live Skills:` line with `, sweep (T16).` (do not add a second line).

## Deliverables

- `.claude/skills/sweep/SKILL.md` — new (≤ 5K tokens).
- `.claude/skills/sweep/runbook.md` — new (T24-rubric).
- `tests/test_t16_sweep.py` — new (6 test cases).
- Edit to `_common/skills_pattern.md` Live-Skills line.
- Edit to M21 README §G3 prose.
- `CHANGELOG.md` updated.

## Tests / smoke (Auditor runs)

```bash
# 1. Skill files exist + frontmatter valid.
test -f .claude/skills/sweep/SKILL.md && echo "SKILL.md exists"
test -f .claude/skills/sweep/runbook.md && echo "runbook.md exists"
grep -qE '^name: sweep$' .claude/skills/sweep/SKILL.md && echo "name correct"
grep -qE '^description: ' .claude/skills/sweep/SKILL.md && echo "description present"
grep -qE '^allowed-tools: ' .claude/skills/sweep/SKILL.md && echo "allowed-tools declared"

# 2. Description ≤ 200 chars (Bash-safe).
awk -F': ' '/^description: /{ exit !(length(substr($0, 14)) <= 200) }' .claude/skills/sweep/SKILL.md && echo "description ≤ 200 chars"

# 3. Body ≤ 5K tokens (Bash-safe).
awk '{ w += NF } END { exit !(w * 13 / 10 <= 5000) }' .claude/skills/sweep/SKILL.md && echo "SKILL.md ≤ 5K tokens"

# 4. T24 rubric on .claude/skills/sweep/.
uv run python scripts/audit/md_discoverability.py --check summary --target .claude/skills/sweep/
uv run python scripts/audit/md_discoverability.py --check section-budget --target .claude/skills/sweep/
uv run python scripts/audit/md_discoverability.py --check code-block-len --target .claude/skills/sweep/ --max 20

# 5. Required four `##` anchors.
grep -qE '^## Inputs' .claude/skills/sweep/SKILL.md && echo "Inputs"
grep -qE '^## Procedure' .claude/skills/sweep/SKILL.md && echo "Procedure"
grep -qE '^## Outputs' .claude/skills/sweep/SKILL.md && echo "Outputs"
grep -qE '^## Return schema' .claude/skills/sweep/SKILL.md && echo "Return schema"

# 6. T25 skills_efficiency clean.
uv run python scripts/audit/skills_efficiency.py --check all --target .claude/skills/

# 7. T10 invariant.
rm -f /tmp/aiw_t16_t10inv.txt
grep -lF '_common/non_negotiables.md' .claude/agents/architect.md .claude/agents/auditor.md \
  .claude/agents/builder.md .claude/agents/dependency-auditor.md \
  .claude/agents/roadmap-selector.md .claude/agents/security-reviewer.md \
  .claude/agents/sr-dev.md .claude/agents/sr-sdet.md .claude/agents/task-analyzer.md \
  > /tmp/aiw_t16_t10inv.txt
awk 'END { exit !(NR == 9) }' /tmp/aiw_t16_t10inv.txt && echo "T10 9/9"

# 8. T24 invariant on .claude/agents/.
uv run python scripts/audit/md_discoverability.py --check section-budget --target .claude/agents/

# 9. Tests pass.
uv run pytest tests/test_t16_sweep.py -q

# 10. CHANGELOG anchor.
grep -qE '^### (Added|Changed) — M21 Task 16:' CHANGELOG.md && echo "CHANGELOG anchor"

# 11. _common/skills_pattern.md Live Skills line lists sweep.
grep -qE '^Live Skills:.*sweep' .claude/agents/_common/skills_pattern.md && echo "skills_pattern lists sweep"
```

## Acceptance criteria

1. `.claude/skills/sweep/SKILL.md` exists; valid frontmatter; body ≤ 5K tokens; four required `##` anchors. Smoke 1–3 + 5 pass.
2. `.claude/skills/sweep/runbook.md` exists; T24-rubric conformant. Smoke 4 passes.
3. T25 skills_efficiency clean (smoke 6).
4. T10 invariant held (smoke 7 = 9).
5. T24 invariant held (smoke 8).
6. `tests/test_t16_sweep.py` passes (smoke 9).
7. `_common/skills_pattern.md` Live Skills line lists sweep (smoke 11).
8. `CHANGELOG.md` updated with `### Added — M21 Task 16: /sweep ad-hoc reviewer Skill` (smoke 10).
9. Status surfaces flip together: (a) T16 spec `**Status:**` → `✅ Done`, (b) M21 README task-pool T16 row Status → `✅ Done` (anchor by row content), (c) M21 README §G3 prose extended with `/sweep` in the satisfaction list.

## Out of scope

- **Auto-trigger** — operator-invoked only.
- **Architect / dependency-auditor in /sweep.** Just sr-dev + sr-sdet + security-reviewer (the unified-terminal-gate trio). Architect is on-demand per the auto-implement procedure; dependency-auditor only fires on manifest changes — both stay separate.
- **Multi-base sweep.** Single base ref at a time.
- **`/ship`** — T15.
- **Adopting items from `nice_to_have.md`.**
- **Runtime code changes** (per M21 scope note).

## Dependencies

- **Built on T12** — Skills extraction pattern.
- **Built on T13/T14** — Phase F template.
- **Built on T24, T25** — discoverability + efficiency rubrics + CI.
- **Precedes T15.** Same template; T15 is host-only with the largest blast radius (publish), so it ships last.

## Carry-over from prior milestones

*None.*

## Carry-over from prior audits

*None.*

## Carry-over from task analysis

*None at draft time.*
