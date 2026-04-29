# Task 24 — MD-file discoverability audit (`.claude/agents/`)

**Status:** 📝 Planned.
**Kind:** Slimming / doc.
**Grounding:** [milestone README](README.md) · [research brief §T24 (NEW)](../milestone_20_autonomy_loop_optimization/research_analysis.md) — line 294, "MD-file discoverability audit (search-by-section)" verdict · existing files under `.claude/agents/*.md` and `.claude/agents/_common/*.md` · [T10 spec](task_10_common_rules_extraction.md) (✅ Done — `_common/` extraction baseline) · [T11 spec](task_11_claude_md_slim.md) (✅ Done — CLAUDE.md slim baseline). KDR drift checks apply per M21 scope note (autonomy-infra task, no direct KDR citation needed).

## Why this task exists

After T10 + T11, the agent-prompt MD files under `.claude/agents/` are the primary load when a sub-agent spawns. Sub-agents read these prompts in full at every spawn. Some are large (`task-analyzer.md` 259 lines, `roadmap-selector.md` 210 lines, `auditor.md` 201 lines), interleave multiple topics, and embed inline code that bloats context without paying its way. Sub-agents that need only one section pay the full file cost on every spawn.

T24 is a one-time audit + refactor pass that imposes a uniform discoverability rubric so each agent prompt is scannable, sectioned, and pulled-on-demand-friendly. The rubric is the same rubric named in M21 README §G2 and research brief §T24. T24 lays the rubric down once; T26 (`agent_docs/`) inherits it when those files materialize.

## Discoverability rubric (locked at T24)

Every MD file under `.claude/agents/` (both top-level agent prompts and `_common/` shared files) must satisfy:

1. **Top-of-file 3-line summary.** Immediately after the YAML frontmatter's closing `---` (or at file head if no frontmatter), three lines (each ≤ 200 chars after rendering) summarize: (a) what this file is, (b) when it's loaded, (c) where its rules originate or what it points to. The summary is plain prose — not a heading, not a bullet list. The first `##` heading appears after these 3 lines (with a blank-line separator).
2. **`##` heading anchors.** Every distinct topic in the file is its own `##` section. A file may contain multiple `##` sections but each section is internally cohesive (one topic). Sub-section nesting via `###` is fine; cross-section content duplication is not.
3. **≤500-token sections.** No `##` section exceeds 500 tokens. Token proxy: section words × 1.3 ≤ 500 (i.e. ≤ 384 words). Sections that exceed the budget split into two `##` sections or push detail into a referenced file.
4. **No inline code blocks > 20 lines.** Inline code that exceeds 20 lines must move to a referenced source path (`src/foo.py:42`, `scripts/release_smoke.sh:60-95`) with a short prose pointer in the agent prompt. Short illustrative snippets (≤ 20 lines) remain inline.
5. **One topic per file.** A file's `##` sections all relate to that file's topic. If two `##` sections cover unrelated topics, the file is a refactor candidate (split, or push the off-topic section to `_common/`).

The rubric applies to `.claude/agents/*.md` (9 agent prompts) and `.claude/agents/_common/*.md` (2 shared files at T24 time — `non_negotiables.md`, `verification_discipline.md`). It does **not** apply to `.claude/commands/*.md` (those are slash-command procedure files with different structural conventions; out of scope per §Out of scope).

## What to Build

### Step 1 — Audit each MD file against the rubric

Run the rubric checks (smoke section below) against each of:

```
.claude/agents/architect.md
.claude/agents/auditor.md
.claude/agents/builder.md
.claude/agents/dependency-auditor.md
.claude/agents/roadmap-selector.md
.claude/agents/security-reviewer.md
.claude/agents/sr-dev.md
.claude/agents/sr-sdet.md
.claude/agents/task-analyzer.md
.claude/agents/_common/non_negotiables.md
.claude/agents/_common/verification_discipline.md
```

Record per-file per-rule pass/fail in T24's issue file (`issues/task_24_issue.md`) as a baseline table. The baseline is informational; downstream tasks read it to confirm rubric adoption.

### Step 2 — Refactor each violating file

For each rule violation, apply the minimal edit that satisfies the rule:

- **Missing 3-line summary** → insert three prose lines immediately after the frontmatter `---` close.
- **No `##` headings** → add `##` headings around existing topical groupings; do not invent new sections.
- **Section > 500 tokens** → split into two `##` sections at the natural topic boundary, or push detail to a referenced file (e.g. an existing `_common/*.md` if the content fits there, or move to a new section in the same file under a more specific `##` heading).
- **Inline code > 20 lines** → move the code to its existing canonical source path (e.g. `scripts/orchestration/telemetry.py:42-78` if the snippet is from that script) and replace with a one-paragraph pointer. If the code has no canonical source path (it's an example), shrink to ≤ 20 lines or push to a referenced file under `_common/` or `agent_docs/` (deferred — see §Out of scope).
- **Multi-topic file** → flag in the issue file. Splitting is heavyweight (moves cause sub-agent prompt churn); only split if the file has ≥ 3 unrelated topics. Single off-topic sections move to `_common/` or `agent_docs/` only when a clear destination exists.

Refactors must preserve the agent's behavior. Do not rewrite procedural content; only re-section it. The Auditor verifies behavior preservation by checking that the agent still references its load-bearing files (`_common/non_negotiables.md`, `_common/verification_discipline.md`).

### Step 3 — Verify no behavioral regressions

After refactor, run smoke step 7 (T11 invariant check) plus T10 invariants:

```bash
# T10 invariant: all 9 agents reference _common/non_negotiables.md.
grep -lF '_common/non_negotiables.md' .claude/agents/*.md | grep -v _common | wc -l
# Expected: 9

# T11 invariants (drift-check anchors): KDR table copies still present.
grep -l "^## Load-bearing KDRs" .claude/agents/auditor.md \
  .claude/agents/task-analyzer.md \
  .claude/agents/architect.md \
  .claude/agents/dependency-auditor.md | wc -l
# Expected: 4
```

T24 must not regress T10 or T11 invariants. If a refactor would, choose the alternate edit.

## Deliverables

- Edits to `.claude/agents/*.md` (9 files) — apply rubric where violated.
- Edits to `.claude/agents/_common/*.md` (2 files) — same rubric.
- New file `design_docs/phases/milestone_21_autonomy_loop_continuation/issues/task_24_issue.md` carrying the per-file baseline table.
- `CHANGELOG.md` updated under `[Unreleased]`.
- M21 README §Exit criteria §G2 prose amended to record T24 satisfaction (e.g. add a parenthetical `(satisfied at T24; rubric locked, all 11 .claude/agents/*.md files conform)`).

## Tests / smoke (Auditor runs)

Each smoke step uses one Bash invocation and avoids `$(...)` command-substitution + parameter expansion inside loop bodies (per `_common/verification_discipline.md` §Bash-safety rules — those patterns trip the harness's shell-injection heuristic and break unattended autonomy).

```bash
# 1. Every audited file has a top-of-file 3-line summary.
# Proxy: lines 1..N (where N = first `##` heading line) contain frontmatter (--- ... ---) followed
# by exactly 3 non-empty prose lines. The audit script lives at scripts/audit/md_discoverability.py.
uv run python scripts/audit/md_discoverability.py --check summary --target .claude/agents/

# 2. No `##` section exceeds 500 tokens (words × 1.3 ≤ 500 i.e. ≤ 384 words per section).
uv run python scripts/audit/md_discoverability.py --check section-budget --target .claude/agents/

# 3. No inline code block exceeds 20 lines.
uv run python scripts/audit/md_discoverability.py --check code-block-len --target .claude/agents/ --max 20

# 4. Each file has ≥ 2 `##` headings.
uv run python scripts/audit/md_discoverability.py --check section-count --target .claude/agents/ --min 2

# 5. T10 invariant preserved.
rm -f /tmp/aiw_t24_t10inv.txt
grep -lF '_common/non_negotiables.md' .claude/agents/architect.md .claude/agents/auditor.md \
  .claude/agents/builder.md .claude/agents/dependency-auditor.md \
  .claude/agents/roadmap-selector.md .claude/agents/security-reviewer.md \
  .claude/agents/sr-dev.md .claude/agents/sr-sdet.md .claude/agents/task-analyzer.md \
  > /tmp/aiw_t24_t10inv.txt
awk 'END { exit !(NR == 9) }' /tmp/aiw_t24_t10inv.txt && echo "T10 invariant held (9/9)"

# 6. T11 invariant preserved (4 drift-check agents carry the KDR table).
rm -f /tmp/aiw_t24_t11inv.txt
grep -l "^## Load-bearing KDRs" .claude/agents/auditor.md .claude/agents/task-analyzer.md \
  .claude/agents/architect.md .claude/agents/dependency-auditor.md > /tmp/aiw_t24_t11inv.txt
awk 'END { exit !(NR == 4) }' /tmp/aiw_t24_t11inv.txt && echo "T11 invariant held (4/4)"

# 7. Issue-file baseline table exists.
test -f design_docs/phases/milestone_21_autonomy_loop_continuation/issues/task_24_issue.md \
  && grep -q "Per-file rubric baseline" design_docs/phases/milestone_21_autonomy_loop_continuation/issues/task_24_issue.md \
  && echo "issue-file baseline present"

# 8. CHANGELOG entry exists.
grep -q "M21 Task 24" CHANGELOG.md && echo "CHANGELOG entry present"
```

The `scripts/audit/md_discoverability.py` script is created as part of this task. It is a small Python utility (≤ 200 lines) that walks the target directory, parses each `.md` file, and reports per-rule pass/fail. Spec-API: `--check {summary|section-budget|code-block-len|section-count}` and exits non-zero on violations. The script is reusable for T26's `agent_docs/` audit when those files materialize.

## Acceptance criteria

1. All 11 audited MD files (9 agent prompts + 2 `_common/` shared files) satisfy rules 1–4 of the rubric (summary header, `##` anchors, ≤500-token sections, no inline code > 20 lines). Smoke steps 1–4 all exit zero.
2. Multi-topic violations (rule 5) are recorded in the issue file as flagged candidates; refactor only when a clear destination exists (don't force-split for cosmetic gain).
3. T10 invariant held (smoke step 5 = 9).
4. T11 invariant held (smoke step 6 = 4).
5. `scripts/audit/md_discoverability.py` exists, is runnable via `uv run python ...`, supports the four checks listed, exits non-zero on violations, ≤ 200 lines.
6. `design_docs/phases/milestone_21_autonomy_loop_continuation/issues/task_24_issue.md` exists with a `## Per-file rubric baseline` table covering all 11 audited files.
7. `CHANGELOG.md` updated under `[Unreleased]` with `### Changed — M21 Task 24: MD-file discoverability audit (rubric locked; .claude/agents/*.md conform; scripts/audit/md_discoverability.py added)`.
8. Status surfaces flip together: (a) T24 spec `**Status:**` line moves from `📝 Planned` to `✅ Done`, (b) M21 README task-pool row 73 Status column moves from `📝 Candidate` to `✅ Done`, (c) M21 README §Exit criteria §G2 prose is amended in-place with an explicit partial-satisfaction parenthetical, e.g. `(rubric locked at T24; .claude/agents/*.md and _common/*.md portion satisfied; agent_docs/ portion deferred to T26 — audit script reusable there)`. The parenthetical must name both the satisfied portion and the deferred portion so future readers see the partial coverage immediately.

## Out of scope

- **`agent_docs/` directory.** Doesn't exist at T24 time; created at T26 (two-prompt long-running pattern). T26's deliverable inherits the rubric automatically — when those files land, the audit script catches violations. The README §G2 satisfaction parenthetical (AC8 c) makes this partial coverage explicit so the deferred portion is auditable.
- **`.claude/commands/*.md`.** Slash-command procedure files have different structural conventions (per-command procedures often need single long Bash blocks for inline execution). T24 only audits agent prompts.
- **CLAUDE.md.** Already slimmed at T11; not re-audited here.
- **Skill extraction (`.claude/skills/`).** That's T12; T24 precedes T12 (per README §Cross-phase dependencies).
- **Splitting multi-topic files into multiple files.** Heavyweight refactor; only flag in the issue file unless ≥ 3 unrelated topics demand it.
- **Rewriting agent procedures.** T24 re-sections; it does not change behavior. If a section is mis-described or stale, that's a separate finding for a different task.
- **Adopting items from `nice_to_have.md`.**
- **Runtime code changes** (per M21 scope note).

## Dependencies

- **Built on T10 + T11.** Requires `_common/non_negotiables.md`, `_common/verification_discipline.md`, and the slimmed CLAUDE.md (✅ both shipped).
- **Blocks T12 (Skills extraction).** Per README §Cross-phase dependencies: "T24 (MD discoverability) → strongly precedes T12 (Skills) — Skills' progressive-disclosure pattern depends on the source MDs being scannable."
- **Precedes T26 (`agent_docs/long_running_pattern.md`).** T26's MD files inherit T24's rubric automatically; the audit script is reusable there.

## Carry-over from prior milestones

*None.*

## Carry-over from prior audits

*None at draft time. Populated if a Builder cycle's audit surfaces forward-deferred items.*

## Carry-over from task analysis

- [ ] **TA-LOW-01 — Smoke step 8 CHANGELOG grep is loose** (severity: LOW, source: task_analysis.md round 1, carried through round 2)
      `grep -q "M21 Task 24" CHANGELOG.md` matches any mention of the string anywhere — including a body reference inside another task's entry. The established T10/T11 entries use `### Added — M21 Task <NN>:` / `### Changed — M21 Task <NN>:` as the section anchor.
      **Recommendation:** Tighten to `grep -qE '^### (Added|Changed) — M21 Task 24:' CHANGELOG.md`.

- [ ] **TA-LOW-02 — Audit script has no CI hookup; will rot silently** (severity: LOW, source: task_analysis.md round 1, carried through round 2)
      `scripts/audit/md_discoverability.py` is created at T24 and run by the Auditor smoke, but it is not attached to `.github/workflows/ci.yml`. Sections that grow past 500 tokens *after* T24 ships will not regress any gate; only the next person to re-run the smoke notices.
      **Recommendation:** Deferred to T25 (periodic skill / scheduled-task efficiency audit) unless T24 Builder elects to add a CI step in-scope. T25 is the natural home.

- [ ] **TA-LOW-03 — Rule 5 (one-topic-per-file) is not encoded in the audit script — worth saying so** (severity: LOW, source: task_analysis.md round 1, carried through round 2)
      AC2 says rule-5 violations are "recorded in the issue file as flagged candidates; refactor only when a clear destination exists." The audit script's `--check` flags only cover rules 1–4 (`summary|section-budget|code-block-len|section-count`). Rule 5 is purely human-judged. Without an explicit note, a Builder may try to encode rule 5 in the script and burn cycles.
      **Recommendation:** Add one sentence to §Step 1 of T24: "Rule 5 (one topic per file) is human-judged at audit time; the audit script does not attempt to encode it. Baseline-table column for rule 5 is filled in manually."
