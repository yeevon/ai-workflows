# Task 14 — `/check` on-disk vs pushed-state verifier

**Status:** 📝 Planned.
**Kind:** Productivity / code + doc.
**Grounding:** [milestone README](README.md) · [research brief §T13–T16](../milestone_20_autonomy_loop_optimization/research_analysis.md) — anchor `### T13–T16 — New commands (/triage, /check, /ship, /sweep)` · [T12 spec](task_12_skills_extraction.md) (✅ Done — Skills extraction pattern) · [T13 spec](task_13_triage_command.md) (✅ Done — first Phase F Skill, sets the convention) · [T25 spec](task_25_periodic_skill_audit.md) (✅ Done — four-anchor canonical shape). KDR drift checks apply per M21 scope note.

## Why this task exists

After every autopilot run + commit + push, the operator needs to know: did the working tree, the local branch, and the remote branch all converge? Currently the answer is a hand-walk: `git status --short` (working tree), `git log --oneline @{u}..HEAD` (local-ahead), `git log --oneline HEAD..@{u}` (remote-ahead), `git diff @{u}..HEAD --stat` (push delta), plus PyPI-vs-local-version comparison if a release is in flight.

`/check` makes that verification a one-shot Skill: read the current branch state + remote tracking ref + (optionally) the latest PyPI version + the latest CHANGELOG.md `[Unreleased]` block, and produce a structured "on-disk vs pushed vs published" report.

T14 is the second Phase F Skill (after T13 `/triage`). Same template — T12's Skills extraction pattern + T25's four-anchor canonical shape.

## Skill structure (per `_common/skills_pattern.md`)

T14 follows the 4-rule shape:

1. Frontmatter: `name: check`, `description:` (≤ 200 chars, trigger-led), `allowed-tools: Bash` (T14 only invokes git + curl for PyPI version check).
2. Body ≤ 5K tokens.
3. Body references `runbook.md` for state-classification matrices; doesn't inline.
4. New Skill — no agent-prompt duplication risk.

## What to Build

### Step 1 — Create `.claude/skills/check/SKILL.md`

Body (≤ 5K tokens) with required `## Inputs / ## Procedure / ## Outputs / ## Return schema` anchors plus optional `## When to use` / `## When NOT to use` per T13 precedent:

```markdown
---
name: check
description: Verify on-disk vs local-branch vs remote-branch (and optionally PyPI) state convergence. Use after autopilot/auto-implement runs to confirm pushed state matches local.
allowed-tools: Bash
---

# check

On-disk vs pushed-state verifier. Reads the current branch + remote tracking ref + (optionally) PyPI latest version, and reports drift across the three surfaces.

## When to use

- After /autopilot or /auto-implement runs to confirm local + remote agree.
- Before declaring a release ready (compare local CHANGELOG `[Unreleased]` vs PyPI latest version).
- When returning to a paused session and unsure whether prior commits pushed.

## When NOT to use

- For diagnosing a halt — use `/triage` instead.
- For test-failure investigation — use `uv run pytest` directly.
- For green-path autopilot runs that just landed — `/check` is for verification after the fact, not part of the autopilot procedure.

## Inputs

Default targets (auto-detected from working directory):

- Current branch: `git rev-parse --abbrev-ref HEAD`.
- Remote tracking ref: `git rev-parse --abbrev-ref --symbolic-full-name @{u}` (skip if no upstream).
- Working-tree state: `git status --short`.
- Local-ahead commits: `git log --oneline @{u}..HEAD` (if upstream exists).
- Remote-ahead commits: `git log --oneline HEAD..@{u}` (if upstream exists).
- CHANGELOG.md `[Unreleased]` block (if present).

Optional flags:
- `--pypi <package>` — also fetch latest PyPI version via `curl https://pypi.org/pypi/<package>/json` and compare to local `pyproject.toml` version + the `[Unreleased]` block.
- `--branch <name>` — override branch detection.

## Procedure

1. Detect current branch + upstream. If no upstream is set, classify as `LOCAL-ONLY` and skip remote comparison.
2. Run the six default git inspections above. Categorize each non-empty output.
3. (Optional) If `--pypi <package>` passed, fetch PyPI JSON via `curl`. Compare `info.version` to local `pyproject.toml`'s `version`. Note discrepancy in the report.
4. Classify the overall state:
   - **CLEAN-AND-SYNCED** — empty `git status`, zero local-ahead, zero remote-ahead.
   - **AHEAD-NEEDS-PUSH** — empty `git status`, local-ahead > 0, remote-ahead = 0.
   - **BEHIND-NEEDS-PULL** — empty `git status`, local-ahead = 0, remote-ahead > 0.
   - **DIVERGED** — both local-ahead > 0 AND remote-ahead > 0.
   - **DIRTY-WORKING-TREE** — `git status --short` non-empty.
   - **PUBLISH-DRIFT** — local pyproject version != PyPI latest (only when `--pypi` is passed).
5. Produce the report (see Outputs).

## Outputs

Write `runs/check/<timestamp>/report.md` with:

- **State classification** (one of the six categories above; one-paragraph summary).
- **Per-surface inventory** (working tree, local branch, remote branch, PyPI if applicable).
- **Next-action recommendation** (one ranked next step the operator should take, or "no action — clean").

## Return schema

3-line `verdict: / file: / section:` matching `.claude/commands/_common/agent_return_schema.md`. Verdict values: `CLEAN | DRIFT | LOCAL-ONLY`. `file:` is the report path.

## Helper files

- `runbook.md` — state-classification matrix (the six classifications mapped to next-action commands); PyPI-comparison example outputs.
```

### Step 2 — Create `.claude/skills/check/runbook.md`

T24-rubric-conformant. Sections:

- 3-line summary.
- `## Classification matrix` — six states × concrete-next-action.
- `## Git invocations` — exact git commands with example outputs.
- `## PyPI version compare` — `curl` invocation + JSON shape + version-string parse.

### Step 3 — Add `tests/test_t14_check.py`

Test cases (mirror T13's pattern):

1. SKILL.md frontmatter parses (YAML-loadable; `name`, `description`, `allowed-tools`).
2. `name == "check"`; `description` ≤ 200 chars; `allowed-tools` non-empty.
3. SKILL.md body word-count × 1.3 ≤ 5000.
4. SKILL.md has all four required `##` anchors (Inputs, Procedure, Outputs, Return schema).
5. `runbook.md` referenced from SKILL.md body.
6. `runbook.md` exists; T24-rubric clean (subprocess-invoke).

### Step 4 — Update README §G3

§G3 currently has T13 satisfaction parenthetical (from iter 10). T14 amends to add `/check` to the list: change the parenthetical to `(satisfied at T13 with /triage; T14 adds /check; T15/T16 separate)`. Or use a list form — Builder picks.

### Step 5 — Update `_common/skills_pattern.md` Live Skills count

Append `check (T14)` to the live-Skills line.

## Deliverables

- `.claude/skills/check/SKILL.md` — new (≤ 5K tokens).
- `.claude/skills/check/runbook.md` — new (T24-rubric).
- `tests/test_t14_check.py` — new (6 test cases).
- Edit to `_common/skills_pattern.md` — Live-Skills count line.
- Edit to M21 README §G3 prose — add T14 to satisfaction list.
- `CHANGELOG.md` updated under `[Unreleased]`.

## Tests / smoke (Auditor runs)

```bash
# 1. Skill files exist + frontmatter valid.
test -f .claude/skills/check/SKILL.md && echo "SKILL.md exists"
test -f .claude/skills/check/runbook.md && echo "runbook.md exists"
grep -qE '^name: check$' .claude/skills/check/SKILL.md && echo "name correct"
grep -qE '^description: ' .claude/skills/check/SKILL.md && echo "description present"
grep -qE '^allowed-tools: ' .claude/skills/check/SKILL.md && echo "allowed-tools declared"

# 2. Description ≤ 200 chars (Bash-safe — pure awk).
awk -F': ' '/^description: /{ exit !(length(substr($0, 14)) <= 200) }' .claude/skills/check/SKILL.md && echo "description ≤ 200 chars"

# 3. Body ≤ 5K tokens (Bash-safe).
awk '{ w += NF } END { exit !(w * 13 / 10 <= 5000) }' .claude/skills/check/SKILL.md && echo "SKILL.md ≤ 5K tokens"

# 4. T24 rubric on .claude/skills/check/.
uv run python scripts/audit/md_discoverability.py --check summary --target .claude/skills/check/
uv run python scripts/audit/md_discoverability.py --check section-budget --target .claude/skills/check/
uv run python scripts/audit/md_discoverability.py --check code-block-len --target .claude/skills/check/ --max 20

# 5. Required four `##` anchors.
grep -qE '^## Inputs' .claude/skills/check/SKILL.md && echo "Inputs"
grep -qE '^## Procedure' .claude/skills/check/SKILL.md && echo "Procedure"
grep -qE '^## Outputs' .claude/skills/check/SKILL.md && echo "Outputs"
grep -qE '^## Return schema' .claude/skills/check/SKILL.md && echo "Return schema"

# 6. T25 skills_efficiency clean.
uv run python scripts/audit/skills_efficiency.py --check all --target .claude/skills/

# 7. T10 invariant.
rm -f /tmp/aiw_t14_t10inv.txt
grep -lF '_common/non_negotiables.md' .claude/agents/architect.md .claude/agents/auditor.md \
  .claude/agents/builder.md .claude/agents/dependency-auditor.md \
  .claude/agents/roadmap-selector.md .claude/agents/security-reviewer.md \
  .claude/agents/sr-dev.md .claude/agents/sr-sdet.md .claude/agents/task-analyzer.md \
  > /tmp/aiw_t14_t10inv.txt
awk 'END { exit !(NR == 9) }' /tmp/aiw_t14_t10inv.txt && echo "T10 9/9"

# 8. T24 invariant on .claude/agents/.
uv run python scripts/audit/md_discoverability.py --check section-budget --target .claude/agents/

# 9. tests pass.
uv run pytest tests/test_t14_check.py -q

# 10. CHANGELOG anchor.
grep -qE '^### (Added|Changed) — M21 Task 14:' CHANGELOG.md && echo "CHANGELOG anchor"

# 11. _common/skills_pattern.md updated (anchor on Live Skills line, not bare 'check' substring).
grep -qE '^Live Skills:.*check' .claude/agents/_common/skills_pattern.md && echo "skills_pattern Live Skills lists check"
```

## Acceptance criteria

1. `.claude/skills/check/SKILL.md` exists; valid frontmatter (name, description ≤ 200, allowed-tools); body ≤ 5K tokens; four required `##` anchors. Smoke 1–3 + 5 pass.
2. `.claude/skills/check/runbook.md` exists; T24-rubric conformant. Smoke 4 passes.
3. T25 skills_efficiency clean (smoke 6).
4. T10 invariant held (smoke 7 = 9).
5. T24 invariant held (smoke 8).
6. `tests/test_t14_check.py` passes (smoke 9).
7. `_common/skills_pattern.md` has `check` in Live Skills (smoke 11).
8. `CHANGELOG.md` updated with `### Added — M21 Task 14: /check on-disk vs pushed-state Skill` (smoke 10).
9. Status surfaces flip together: (a) T14 spec `**Status:**` → `✅ Done`, (b) M21 README task-pool T14 row Status → `✅ Done` (anchor by row content), (c) M21 README §G3 prose extended with `/check` in the satisfaction list.

## Out of scope

- **`/ship`, `/sweep`** — T15, T16.
- **PyPI publish from /check.** /check only verifies; /ship publishes.
- **Auto-trigger** — operator-invoked only.
- **Multi-remote check** — single remote (origin) only at T14 time.
- **Adopting items from `nice_to_have.md`.**
- **Runtime code changes** (per M21 scope note).

## Dependencies

- **Built on T12** — Skills extraction pattern.
- **Built on T13** — Phase F Skill template; same shape.
- **Built on T24, T25** — discoverability + efficiency rubrics + CI.
- **Precedes T15/T16.** Same template inheritance.

## Carry-over from prior milestones

*None.*

## Carry-over from prior audits

*None.*

## Carry-over from task analysis

- [ ] **TA-LOW-01 — Step 5 wording: extend Live Skills line, do not append a new line** (severity: LOW, source: task_analysis.md round 15 / T14 round 1)
      Step 5 says "Append `check (T14)` to the live-Skills line." A careful Builder might add a second `Live Skills:` line.
      **Recommendation:** Builder extends the existing single `Live Skills:` line from `..., triage (T13).` to `..., triage (T13), check (T14).` — single line; do not add a second.

- [ ] **TA-LOW-02 — `allowed-tools` rationale informational note** (severity: LOW, source: task_analysis.md round 15)
      T14 declares `allowed-tools: Bash` only (vs T13's `Read, Bash, Grep`); rationale is that T14's procedure is fully Bash-native (`git`, `curl`, `cat`, `grep` inside Bash subprocess calls). Worth noting for T15/T16 templates.
      **Recommendation:** Builder may add a one-line rationale under §Skill structure §1; optional, no blocker.
