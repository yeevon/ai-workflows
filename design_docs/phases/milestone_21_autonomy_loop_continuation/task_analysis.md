# M21 Autonomy Loop Continuation — Task Analysis

**Round:** 3
**Analyzed on:** 2026-04-29
**Specs analyzed:** `task_10_common_rules_extraction.md`
**Analyst:** task-analyzer agent

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 0 |
| 🟢 LOW | 1 |
| Total | 1 |

**Stop verdict:** LOW-ONLY

Zero HIGH, zero MEDIUM. One LOW carries over from round 1 (L2 — frontmatter wording precision) that was not absorbed by the round-2 fix application. Orchestrator should push it to the spec's `## Carry-over from task analysis` section and exit the loop.

## Findings

### 🟢 LOW

#### L1 — "Frontmatter line or top-of-file declaration" wording is loose (round-1 L2 carry-over)

**Task:** `task_10_common_rules_extraction.md`
**Issue:** §Per-agent frontmatter reference (line 36) says "Each agent's prompt file in `.claude/agents/` … gains a frontmatter line or top-of-file declaration." The example block (lines 38-41) uses Markdown bold-text (`**Non-negotiables:** see [...]`), which is **not** YAML frontmatter — the agent files use YAML frontmatter for `name`/`description`/`tools`/`model`/`thinking`/`effort` (verified against `.claude/agents/builder.md` lines 1-10). The bold-text declaration must land in the prompt body **after** the closing `---`, not inside the YAML block. AC-3's "(or equivalent — two greps must succeed)" gives the Builder flexibility, so this is not blocking, but the wording invites a Builder to attempt YAML-frontmatter insertion that would break the YAML parser.
**Recommendation:** Tighten line 36 to "Each agent's prompt file in `.claude/agents/` (9 files: …) gains a top-of-body declaration immediately after the YAML frontmatter closing `---` referencing the shared blocks." Drop "frontmatter line or" — there is no YAML field for this content.
**Push to spec:** yes — append to the spec's `## Carry-over from task analysis` section as: *"Round-3 carry-over: when adding the `**Non-negotiables:**` and `**Verification discipline:**` declarations to each agent prompt, place them in the prompt body immediately after the YAML frontmatter closing `---`, not inside the YAML block. The example at §Per-agent frontmatter reference shows Markdown bold-text, which is body content, not YAML."*

## What's structurally sound

Verified on hostile re-read; round-2 fixes held:

- **H1 (round-2) — grounding citations.** Spec line 5 cites `research_analysis.md` §T10. Confirmed file exists and line 263 contains `### T10 — Common-rules extraction (.claude/agents/_common/non_negotiables.md)` with the SUPPORT verdict. Secondary `autonomy_model_dispatch_study.md` confirmed to exist. M21 README line 5 propagates both citations.
- **M1 (round-2) — verbatim/token-budget conflict resolved.** Line 21 now reads "faithful summary — only the subagent-relevant rules 1/2/3-decision-rule." Verb list ordering matches CLAUDE.md / agent-prompt convention (`git commit, git push, git merge, git rebase, git tag, uv publish`).
- **M2 (round-2) — smoke step 4 assertion shape.** Lines 86-89 now use `test ... && echo "<pass marker>"` consistent with steps 1-3.
- **All cited paths resolve.** `.claude/agents/architect.md`, `auditor.md`, `builder.md`, `dependency-auditor.md`, `roadmap-selector.md`, `security-reviewer.md`, `sr-dev.md`, `sr-sdet.md`, `task-analyzer.md` — 9/9 exist. `feedback_autonomous_mode_boundaries.md` in project memory exists. `.claude/commands/_common/gate_parse_patterns.md` exists. `.claude/agents/_common/` does **not** yet exist (correct — T10 creates it).
- **Smoke step 3 sentinel grep validity.** `grep -lF 'Do not run \`git commit\`' .claude/agents/*.md` currently matches 9/9 agent files (verified). After T10 extraction, those sentences land only in `_common/non_negotiables.md`; the `grep -v _common` filter excludes the new file. Grep returns 0 lines outside `_common/` after correct extraction.
- **Smoke step 2 grep specificity.** Targets exact filenames `_common/non_negotiables.md` and `_common/verification_discipline.md`. Several agents currently reference `_common/effort_table.md` and `_common/cycle_summary_template.md` (under `.claude/commands/_common/`) but **not** the targeted filenames (verified `grep -c '_common/non_negotiables.md' .claude/agents/builder.md` returns 0 today). No false-positive risk.
- **AC ↔ smoke coverage.** AC-1 ↔ smoke step 1 (file-exists + token-budget). AC-2 ↔ smoke step 1. AC-3 ↔ smoke step 2. AC-4 ↔ smoke step 3. AC-5 (CHANGELOG) is doc-task-appropriate and verified against `## [Unreleased]` convention in `CHANGELOG.md` line 8. AC-6 (status surfaces) — milestone README task-pool row at line 70 currently reads "📝 Candidate"; T10 close flips to "✅ Done" + per-task spec `**Status:**` line.
- **Layer / KDR / SEMVER discipline.** Doc-only task. No `ai_workflows/` touches. No public-API surface. No KDR violation surface. M21 scope-note (README line 7) explicitly bars runtime code changes and the spec §Out of scope honors it (line 109).
- **Cross-task dependencies.** T10 → blocks T11 (correct — T11 needs `_common/` as the destination for moved CLAUDE.md content). README line 109 mirrors this. No circular or out-of-order dependency.
- **`nice_to_have.md` slot drift.** Spec cites no slot numbers; nothing to drift.
- **Status-surface alignment.** Spec `**Status:**` = "📝 Planned"; README task-pool Kind = "Slimming / doc"; spec self-describes as "doc-only task" (line 54). Consistent.

## Cross-cutting context

- **M21 status:** Drafting. T10 is first task in Phase E (Slimming). M20 is closed (commit `8c6e8a6` per README line 3). Project memory `project_m12_autopilot_2026_04_27_checkpoint.md` flags M12 T06+T07 as the in-flight queue, but does not block M21 spec-hardening — M21 specs may be hardened in parallel with M12 implementation, and `/clean-tasks m21` is the right gate before `/auto-implement m21 t10`.
- **L2 round-1 carry-over:** orchestrator's round-3 brief noted "L2 still pending" (frontmatter wording). This round's L1 finding is that same item, surfaced again because hostile re-read confirms it is real and the round-2 fix did not absorb it. Pushing to spec carry-over closes it cleanly.
- **No HIGH/MEDIUM means /clean-tasks loop is exit-eligible** at LOW-ONLY. Orchestrator pushes L1 to spec, then exits. Spec is ready for `/clean-implement m21 t10` whenever queue selector reaches it.
