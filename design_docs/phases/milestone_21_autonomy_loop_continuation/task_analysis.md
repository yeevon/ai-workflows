# M21 (autonomy_loop_continuation) — Task Analysis

**Round:** 5 (overall; T12 round 3)
**Analyzed on:** 2026-04-29
**Specs analyzed:** task_10_common_rules_extraction.md (locked ✅), task_11_claude_md_slim.md (locked ✅), task_24_md_discoverability.md (locked ✅), task_12_skills_extraction.md (primary)
**Analyst:** task-analyzer agent

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 0 |
| 🟢 LOW | 2 |
| Total | 2 |

**Stop verdict:** LOW-ONLY

Round 4's H1 (SKILL.md template + runbook.md template fail `check_summary`), M1 (Step 5 bullet-shape collides with `##`-anchors claim), M2 (AC4 missing smoke step 8 citation), and L1 (dead `feedback_pyproject_uv_lock_dep_gate.md` pointer pre-emptively removed) all landed correctly and are verified live against the audit script. The two LOWs surfaced this round are both spec-text fragility — neither blocks /clean-implement; both push to spec carry-over.

## Round-4 fix verification

- **H1 (SKILL.md template summary 3 lines + Step 3 runbook.md summary instruction)** ✅ — SKILL.md template at spec lines 51–53 now has three distinct physical prose lines. Step 3 (lines 95–101) gives an explicit 3-line summary instruction with suggested wording. Verified live: wrote both templates to a temp dir, ran `uv run python scripts/audit/md_discoverability.py --check summary --target /tmp/aiw_t12_verify/dep-audit/` → `OK: summary — all 2 file(s) pass`. Section-count check also passes (`OK: section-count — all 2 file(s) pass`). The audit-script gate at smoke step 4 is now reachable.
- **M1 (Step 5 sections re-shaped to `##` anchors)** ✅ — Lead-in at line 134 reads `Sections (each ≤ 500 tokens, ##  anchors per T24 rule 2):`. Bullets at 136–138 describe each section's heading via inline-code-fenced `## When to extract` / `## The 4-rule Skill structure` / `## How to validate`. Builder reading Step 5 with the lead-in will write the file with three `##` headings — section-count `--min 2` will pass.
- **M2 (AC4 cites smoke step 6 + step 8)** ✅ — line 207 reads "Smoke step 6 confirms file presence + magic-phrase grep; smoke step 8 confirms T24-rubric conformance via the `_common/` walk (the audit script's `_get_md_files` walks `_common/`, so `skills_pattern.md` is checked transitively)." The gate-set is now explicit; Builder cannot mis-model AC4 as gated only by step 6.
- **L1 (dead `feedback_pyproject_uv_lock_dep_gate.md` pointer)** ✅ — `grep -n 'feedback_pyproject_uv_lock_dep_gate' task_12_skills_extraction.md` → no matches. Round-3 TA-LOW-01 absorbed; carry-over slot freed (line 243 records the absorption note).

## Findings

### 🟢 LOW

#### L1 — Spec line 218 also hard-codes `line 269`; TA-LOW-01 carry-over scope is too narrow

**Task:** task_12_skills_extraction.md
**Issue:** TA-LOW-01 (lines 239–241) recommends replacing `line 269` and `line 145` in the §Grounding line (spec line 5) with anchor strings. But spec line 218 (Out of scope, "Validating the extraction by omission") also reads "Research-brief §T12 line 269 suggests testing the Skill by omitting it…". The same line-number drift hazard applies. Either both references should be migrated, or TA-LOW-01 should explicitly note the second occurrence so the Builder doesn't migrate one and miss the other.
**Recommendation:** Broaden TA-LOW-01's recommendation to cover both spec line 5 and spec line 218. Suggested edit to lines 240–241:
```
Spec §Grounding (line 5) AND §Out of scope "Validating the extraction by omission" (line 218) both hard-code `line 269` for the research brief. Verified accurate today, but the line numbers will drift with future re-flow.
**Recommendation:** Replace each occurrence of `line 269` → `(matching ### T12 — Skills extraction (per-agent capabilities)`; replace `line 145` (line 5 only) → `(matching T12 (Skills extraction) aligns directly with Anthropic's Agent Skills pattern)`. Anchor strings survive re-flow.
```
**Push to spec:** yes — broaden TA-LOW-01 in the carry-over section so the Builder migrates both at implement time.

#### L2 — Step 5 doesn't explicitly mandate the literal phrase "Skill-extraction pattern" in `_common/skills_pattern.md` body

**Task:** task_12_skills_extraction.md
**Location:** §Step 5 (lines 128–140) and smoke step 6 (lines 178–181).
**Issue:** Smoke step 6 asserts `grep -qF "Skill-extraction pattern" .claude/agents/_common/skills_pattern.md` — a literal case-sensitive substring match. Step 5's body content (sections "When to extract", "The 4-rule Skill structure", "How to validate") does not name "Skill-extraction pattern" verbatim; the phrase appears only in the file's *purpose description* (line 130: "carrying the Skill-extraction pattern documentation"), which is meta-spec, not body content. A Builder writing the file freehand could use synonyms ("extraction recipe", "Skill extraction guidance", "extraction pattern") and pass T24 rubric checks but fail smoke step 6. Reasonable Builder behavior would echo the spec's phrasing, so the risk is low; nonetheless the spec text leaves a gap that a defensive instruction would close.
**Recommendation:** Add a one-liner to Step 5 body — after line 130, insert: `Include the literal phrase **Skill-extraction pattern** in the file body (intro paragraph or first section) so smoke step 6's grep is satisfied unambiguously.` Two-line edit, no scope drift, hardens the smoke gate.
**Push to spec:** yes — append to the Carry-over from task analysis section as TA-LOW-02 with the recommendation above.

## What's structurally sound

- **All round-4 fixes verified against the live audit script** — temp-dir reproduction with the spec's exact SKILL.md and runbook.md templates passes both `check_summary` and `check_section_count` gates. The H1 / M2 fixes are not just spec-text edits; they cause the gates to be actually reachable.
- **Description length holds at 182 chars** (line 46) — under the ≤200 cap; smoke step 2's `${#desc} -le 200` will pass.
- **Step 4 surgical-edit list precise.** Confirmed `## Load-bearing KDRs (drift-check anchors)` exists at `dependency-auditor.md:102`, so "before the `## Load-bearing KDRs` table" placement instruction (line 115) hits a real anchor.
- **AC4 gate-set explicit.** Line 207 cites both step 6 (presence + grep) and step 8 (transitive `_common/` rubric walk). Builder cannot ship `skills_pattern.md` with structurally non-conformant shape thinking step 6 alone closes AC4.
- **Sibling-task statuses aligned.** T10 (✅ Complete), T11 (✅ Done), T24 (✅ Done) — all locked; no cross-spec drift candidates.
- **README row 72 alignment** — verified that row 72 of M21 README is the T12 row with status `📝 Candidate`; AC8(b) transition path is well-formed.
- **G6 framing internally consistent.** Deliverable bullet 6 (line 149) and AC8(c) (line 211) both forbid amending G3 and both name `dep-audit` as the satisfaction parenthetical. M21 README §Exit criteria currently lists G1–G5; G6 is a clean addition.
- **KDR drift checks pass.** T12 is autonomy-infra (`.claude/skills/`, `.claude/agents/`); layer rule + KDR-002/003/004/006/008/009/013 unaffected.
- **`nice_to_have.md` slot drift clean.** Highest current section is §24; T12 claims no slot.
- **CHANGELOG anchor regex unchanged from round 4** (`^### (Added|Changed) — M21 Task 12:`) — locked to T24 round-2 convention.
- **Bash safety in smoke** — `${#desc}` length-check is the one harness-eligible exception (necessary for the gate to be meaningful); no `$(...)` substitutions in loops, no simple-expansion-in-loops.
- **Pre-emptive L1 absorption** — round-3 TA-LOW-01 (dead memory-file pointer) was removed from the SKILL.md template at round-4 close; carry-over checkbox correctly deleted; absorption note left at line 243 for audit trail.

## Cross-cutting context

- **M21 status:** active; T10/T11/T24 shipped (commits `2f73143`, `012a9d9`, `ca4397d`); T12 is round 3 of /clean-tasks, round 5 overall. Per the suggested phasing in M21 README (E: T10 → T11 → T24 → T12 → T26 → T25), T12 is the next slimming task.
- **Round-limit reached.** Round 5 is the cycle limit per /clean-tasks procedure. LOW-ONLY verdict means orchestrator pushes both LOWs to T12's carry-over and exits the loop cleanly — no user-arbitration needed.
- **CS300-pivot status** unchanged from round 4 — post-0.3.1 live, no return-trigger fired (per `project_m13_shipped_cs300_next.md`); autonomy-infra continues as background priority.
- **No M20 forward-deferrals carried into M21.** README §Carry-over remains empty.
- **Locked autonomy boundaries hold.** Per `feedback_autonomous_mode_boundaries.md`, only the orchestrator commits/pushes; T12 deliverables don't touch any release surface (no `pyproject.toml` / `uv.lock` change, no version bump, no PyPI publish path). Dep-audit gate not triggered by T12 itself.
- **No HARD HALT triggers in this analysis.** Both round-5 findings are LOW spec-text fragility (line-number drift, magic-phrase explicitness). Neither blocks /clean-implement; both push to T12 carry-over for the Builder to absorb at implement time.
