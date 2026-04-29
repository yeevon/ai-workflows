# Task 13 — `/triage` post-halt diagnosis surface

**Status:** 📝 Planned.
**Kind:** Productivity / code + doc.
**Grounding:** [milestone README](README.md) · [research brief §T13–T16 (SUPPORT + MODIFY)](../milestone_20_autonomy_loop_optimization/research_analysis.md) — anchor `### T13–T16 — New commands (/triage, /check, /ship, /sweep)` · [T12 spec](task_12_skills_extraction.md) (✅ Done — Skills extraction pattern locked at `_common/skills_pattern.md`) · [T26 spec](task_26_two_prompt_long_running.md) (✅ Done — long-running pattern). KDR drift checks apply per M21 scope note.

## Why this task exists

The `/auto-implement` and `/autopilot` flows can halt mid-loop on stop conditions (BLOCKER, USER INPUT REQUIRED, sub-agent disagreement, cycle limit). When that happens, the operator must answer "what failed and what's the next move?" — currently by hand-reading the latest issue file + recommendation file + recent commits. That triage walk happens after every halt, takes 5–10 minutes per occurrence, and leaks context the orchestrator already had.

`/triage` makes the post-halt diagnosis a one-shot Skill: read the latest task issue file + the latest `runs/autopilot-*-iter*-shipped.md` (or `runs/<task>/cycle_<N>/summary.md` if the halt was mid-task) + the last 5 commits + the working-tree diff, and produce a structured "what halted / why / next-action options" report.

Per M21 README §G3, `/triage` is the **highest-value Phase F surface** — post-halt diagnosis is the most-frequent operator need. T13 ships it first; T14/T15/T16 follow.

T12 locked the Skills extraction pattern via `_common/skills_pattern.md`; T13 is the first new productivity Skill that follows that pattern. Behavior precedent: T13 is *new* (not an extraction of an existing capability), so the rule "no agent-prompt duplication" doesn't bite.

## Skill structure (per `_common/skills_pattern.md`)

T13 follows the 4-rule shape locked at T12:

1. Frontmatter: `name: triage` (kebab-case); `description:` (≤ 200 chars, trigger-led — "Use when an autopilot or auto-implement run halted and you need to diagnose what failed.")
2. Body ≤ 5K tokens.
3. Body references helper files; doesn't inline them.
4. New Skill — no agent-prompt duplication risk.

`allowed-tools:` frontmatter set per T25 Step 1b precondition (T13 invokes `Bash` for git log + `Read` for issue files; declare both).

## What to Build

### Step 1 — Create `.claude/skills/triage/SKILL.md`

Body (≤ 5K tokens) with required `## Inputs / ## Procedure / ## Outputs / ## Return schema` anchors per T25's canonical four-anchor shape:

```markdown
---
name: triage
description: Post-halt diagnosis for autopilot/auto-implement runs. Use after a HALT/BLOCKED/cycle-limit return when you need a structured "what failed / why / next move" report.
allowed-tools: Read, Bash, Grep
---

# triage

Post-halt diagnosis for autonomy-mode runs. Loads the latest run-state surfaces (issue file, iter-shipped, cycle summaries), parses the halt signal, and produces a structured report so the operator can decide retry / fix / skip.

## When to use

- After any /autopilot or /auto-implement run that returned HALT, BLOCKED, USER INPUT REQUIRED, or "cycle limit reached".
- When git working tree is dirty after an autonomy run and you need to know what's safe to commit vs. what was mid-cycle.
- When the operator returns to a paused autonomy session and needs to resume from a clean state.

## When NOT to use

- For routine sr-dev / sr-sdet review of a clean diff → use `/sweep` (T16) instead.
- For pre-publish wheel-contents inspection → use `dep-audit` Skill.
- For green-path autopilot runs (no halt) — `/triage` is for halts only.

## Inputs

Default targets (auto-detected from working directory):

- Latest `design_docs/phases/milestone_*/issues/task_*_issue.md` by mtime.
- Latest `runs/autopilot-*-iter*-shipped.md` by mtime.
- Latest `runs/<task>/cycle_*/summary.md` by mtime (if mid-task).
- `git log --oneline -5` for recent-commit context.
- `git status --short` + `git diff --stat` for working-tree state.

Optional override: pass `--task <task-shorthand>` to scope diagnosis to one specific task's issue file + cycle summaries.

## Procedure

1. Read the latest issue file in full. Parse the `**Status:**` line — `✅ PASS` means no halt; `🚧 BLOCKED` / `OPEN` means a halt is recorded.
2. Read the latest `iter-shipped.md` (autopilot-level) and the latest `cycle_<N>/summary.md` (task-level if present). Note which is more recent.
3. Read `git log --oneline -5`. Note whether the last commit is task-out (`task-out:` prefix) vs task-close (`Task <NN>:` prefix). A task-out + dirty tree = mid-cycle halt; a task-close + clean tree = green run.
4. Read `git status --short` + `git diff --stat`. Map every modified/untracked file to either a task spec / issue file / runs artefact / source code.
5. Classify the halt:
   - **Cycle limit (10/10)** — auto-implement reached cycle limit without convergence.
   - **BLOCKER** — issue file has a HIGH 🚧 BLOCKED finding requiring user action.
   - **USER INPUT REQUIRED** — auditor surfaced ambiguous decision needing user arbitration.
   - **Sub-agent disagreement** — terminal-gate split (one BLOCK, others SHIP).
   - **Pre-flight failure** — sandbox/branch/clean-tree check failed before agent spawns.
6. For each halt category, name 2-3 next-action options the operator can take. Reference helper file `runbook.md` for the option matrices.

## Outputs

Write `runs/triage/<timestamp>/report.md` with:

- **Halt signature** (one-paragraph: which command, which task, which cycle, which classified halt).
- **Run-state inventory** (file list grouped by category: spec/issue/runs/source).
- **Next-action options** (2-3 ranked options for the operator; each names the command + concrete consequence).

## Return schema

3-line `verdict: / file: / section:` matching `.claude/commands/_common/agent_return_schema.md`. Verdict values: `DIAGNOSED | INCONCLUSIVE`. `file:` is the report path. `section:` is `—` (no specific section).

## Helper files

- `runbook.md` — option matrices keyed by halt classification; example reports for each category.
```

### Step 2 — Create `.claude/skills/triage/runbook.md`

T24-rubric-conformant (3-line summary, `##` anchors, ≤ 500 tokens / section, no inline code > 20 lines, one topic). Sections:

- 3-line summary.
- `## Halt classifications` — full taxonomy with detection regexes per kind.
- `## Option matrices` — for each halt, the 2-3 ranked next-actions with command + consequence.
- `## Example reports` — 1-2 worked examples (truncated cycle limit; user-input ambiguity).

### Step 3 — Add `tests/test_t13_triage.py` test contract

Test cases (mirrors T12's pattern):

1. SKILL.md frontmatter parses (YAML-loadable; has `name`, `description`, `allowed-tools` keys).
2. `name == "triage"`; `description` ≤ 200 chars; `allowed-tools` non-empty list/string.
3. SKILL.md body word-count × 1.3 ≤ 5000.
4. SKILL.md has all four required `##` anchors (Inputs, Procedure, Outputs, Return schema).
5. `runbook.md` referenced from SKILL.md body (string-search for `runbook.md`).
6. `runbook.md` exists; T24-rubric clean (subprocess-invoke `scripts/audit/md_discoverability.py --check summary --target .claude/skills/triage/`).

Use `subprocess.run([sys.executable, ...])` with explicit argv list (no `shell=True`); `cwd` not passed; aligns with `tests/test_t24_md_discoverability.py` and `tests/test_t25_skills_efficiency.py` patterns.

### Step 4 — Update README §G3

M21 README §G3 currently reads: "At least one new productivity command lands as a Skill (`/triage` recommended). Spec covers full set; M21 ships at minimum the highest-value surface." Amend with a satisfaction parenthetical at T13 close: `(satisfied at T13; /triage shipped as the highest-value Phase F Skill; T14/T15/T16 separate)`.

### Step 5 — Update `_common/skills_pattern.md` reference list

`_common/skills_pattern.md` currently has the pattern documentation but no concrete-Skill list. Append a line under `## How to validate` (or in the file footer): `Live Skills: ai-workflows (legacy), dep-audit (T12), triage (T13).` So the count is auditable as Skills land.

## Deliverables

- `.claude/skills/triage/SKILL.md` — new (≤ 5K tokens; four required `##` anchors).
- `.claude/skills/triage/runbook.md` — new (T24-rubric-conformant).
- `tests/test_t13_triage.py` — new (covers SKILL.md frontmatter validity, runbook rubric, helper-file reference).
- Edit to `.claude/agents/_common/skills_pattern.md` — append live-Skills count line.
- `CHANGELOG.md` updated under `[Unreleased]`.
- M21 README §G3 prose amended with satisfaction parenthetical.

## Tests / smoke (Auditor runs)

```bash
# 1. Skill files exist + frontmatter valid.
test -f .claude/skills/triage/SKILL.md && echo "SKILL.md exists"
test -f .claude/skills/triage/runbook.md && echo "runbook.md exists"
grep -qE '^name: triage$' .claude/skills/triage/SKILL.md && echo "name field correct"
grep -qE '^description: ' .claude/skills/triage/SKILL.md && echo "description present"
grep -qE '^allowed-tools: ' .claude/skills/triage/SKILL.md && echo "allowed-tools declared"

# 2. SKILL.md description ≤ 200 chars (Bash-safe — no command substitution).
awk -F': ' '/^description: /{ exit !(length(substr($0, 14)) <= 200) }' .claude/skills/triage/SKILL.md && echo "description ≤ 200 chars"

# 3. SKILL.md body ≤ 5K tokens (Bash-safe — pure awk, no $(...) or ${...}).
awk '{ w += NF } END { exit !(w * 13 / 10 <= 5000) }' .claude/skills/triage/SKILL.md && echo "SKILL.md ≤ 5K tokens"

# 4. T24 rubric on .claude/skills/triage/.
uv run python scripts/audit/md_discoverability.py --check summary --target .claude/skills/triage/
uv run python scripts/audit/md_discoverability.py --check section-budget --target .claude/skills/triage/
uv run python scripts/audit/md_discoverability.py --check code-block-len --target .claude/skills/triage/ --max 20

# 5. Required four `##` anchors in SKILL.md.
grep -qE '^## Inputs' .claude/skills/triage/SKILL.md && echo "Inputs anchor present"
grep -qE '^## Procedure' .claude/skills/triage/SKILL.md && echo "Procedure anchor present"
grep -qE '^## Outputs' .claude/skills/triage/SKILL.md && echo "Outputs anchor present"
grep -qE '^## Return schema' .claude/skills/triage/SKILL.md && echo "Return schema anchor present"

# 6. T25 skills_efficiency clean against the new Skill.
uv run python scripts/audit/skills_efficiency.py --check all --target .claude/skills/

# 7. T10 invariant preserved.
rm -f /tmp/aiw_t13_t10inv.txt
grep -lF '_common/non_negotiables.md' .claude/agents/architect.md .claude/agents/auditor.md \
  .claude/agents/builder.md .claude/agents/dependency-auditor.md \
  .claude/agents/roadmap-selector.md .claude/agents/security-reviewer.md \
  .claude/agents/sr-dev.md .claude/agents/sr-sdet.md .claude/agents/task-analyzer.md \
  > /tmp/aiw_t13_t10inv.txt
awk 'END { exit !(NR == 9) }' /tmp/aiw_t13_t10inv.txt && echo "T10 invariant held (9/9)"

# 8. T24 invariant preserved on .claude/agents/.
uv run python scripts/audit/md_discoverability.py --check section-budget --target .claude/agents/

# 9. tests/test_t13_triage.py passes.
uv run pytest tests/test_t13_triage.py -q

# 10. CHANGELOG anchor.
grep -qE '^### (Added|Changed) — M21 Task 13:' CHANGELOG.md && echo "CHANGELOG anchor present"

# 11. Live-Skills count line in skills_pattern.md.
grep -qF 'Live Skills:' .claude/agents/_common/skills_pattern.md && echo "skills count line present"
```

## Acceptance criteria

1. `.claude/skills/triage/SKILL.md` exists; valid frontmatter (`name`, `description ≤ 200 chars`, `allowed-tools`); body ≤ 5K tokens; four `##` anchors (Inputs, Procedure, Outputs, Return schema). Smoke steps 1–3 + 5 pass.
2. `.claude/skills/triage/runbook.md` exists, T24-rubric conformant. Smoke step 4 passes.
3. T25 skills_efficiency CI gate clean against the new Skill (smoke step 6 passes).
4. T10 invariant held (smoke step 7 = 9).
5. T24 invariant held on `.claude/agents/` (smoke step 8 zero exit).
6. `tests/test_t13_triage.py` passes (smoke step 9).
7. `_common/skills_pattern.md` has the live-Skills count line (smoke step 11).
8. `CHANGELOG.md` updated with `### Added — M21 Task 13: /triage post-halt diagnosis Skill` (smoke step 10).
9. Status surfaces flip together: (a) T13 spec `**Status:**` → `✅ Done`, (b) M21 README task-pool T13 row Status cell → `✅ Done` (anchor by row content, not line number — line numbers drift), (c) M21 README §G3 prose amended in-place with satisfaction parenthetical naming `/triage` as the highest-value Phase F Skill that landed.

## Out of scope

- **`/check`, `/ship`, `/sweep`.** Those are T14/T15/T16 — separate specs.
- **Auto-triggering /triage on every halt.** Operator-invoked only at T13 land time. Auto-trigger could be a future T13-shaped follow-up.
- **Behavioral integration with /autopilot's halt surface.** /autopilot's halt remains as-is; /triage is a *companion* tool the operator runs after, not a callback /autopilot invokes.
- **Multi-task aggregate triage** (e.g. "what's halted across all M21 tasks"). T13 diagnoses one halt at a time.
- **Adopting items from `nice_to_have.md`.**
- **Runtime code changes** (per M21 scope note).

## Dependencies

- **Built on T12** — Skills extraction pattern locked at `_common/skills_pattern.md`.
- **Built on T24** — discoverability rubric (audit script reusable for `.claude/skills/triage/`).
- **Built on T25** — skills_efficiency CI gate catches T13 regressions; `/audit-skills` walks `triage/` along with the rest.
- **Precedes T14/T15/T16.** All Phase F productivity commands inherit T13's pattern.

## Carry-over from prior milestones

*None.*

## Carry-over from prior audits

*None at draft time.*

## Carry-over from task analysis

- [ ] **TA-LOW-01 — `## When to use` / `## When NOT to use` anchors permitted beyond T25's mandated four** (severity: LOW, source: task_analysis.md round 12, carried through round 14)
      T13's SKILL.md adds `## When to use` and `## When NOT to use` anchors before `## Inputs`. T25's smoke step 9 only enforces the four required anchors (`Inputs`, `Procedure`, `Outputs`, `Return schema`), not the absence of others. Additional sections are permitted; this mirrors dep-audit's existing shape.
      **Recommendation:** Builder may keep both `When to use` / `When NOT to use` anchors (precedent: dep-audit) — they add useful trigger-disambiguation prose. No spec edit needed; this carry-over documents the explicit framing so the Builder doesn't second-guess the additional anchors.
