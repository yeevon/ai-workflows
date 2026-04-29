# M21 Autonomy Loop Continuation — Task Analysis

**Round:** 11 (overall) / Round 3 (T25)
**Analyzed on:** 2026-04-29
**Specs analyzed:** task_25 (primary, 📝 Planned) + cross-spec consistency check against task_10 / task_11 / task_12 / task_24 / task_26 (all ✅, locked)
**Analyst:** task-analyzer agent

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 0 |
| 🟢 LOW | 3 |
| Total | 3 |

**Stop verdict:** LOW-ONLY

Round-10 M1 fix landed cleanly. T25 §Step 2 line 58 now reads: "Required slash-command body sections (T25 introduces this canonical four-anchor shape for audit-style slash commands; existing sibling commands like `audit.md` / `auto-implement.md` / `clean-tasks.md` use free-form section shapes — future audit-style commands inherit T25's anchor set)". The false sibling-convention citation is gone; the four-anchor requirement, smoke step 9, and AC2 all preserved. Live re-verification confirms the framing is now accurate (clean-tasks.md uses free-form `## Phase 1 / Phase 2 / Phase 3 / Stop conditions / Reporting / Why...`; auto-implement.md uses `## Agent-return parser convention / Cache-breakpoint verification / ...`; audit.md has zero `##` anchors — none match Inputs/Procedure/Outputs/Return-schema, confirming T25 introduces the shape rather than inheriting it).

The three remaining LOWs (L1/L2/L3) are the round-10 carry-overs that were not yet pushed to T25's spec `## Carry-over from task analysis` section (line 192 still reads `*None at draft time. Populated by /clean-tasks m21 runs.*`). Per /clean-tasks Phase 3, the orchestrator pushes these to spec carry-over once the analyzer reaches LOW-ONLY and exits the analyze+fix loop.

## Findings

### 🟢 LOW

#### L1 — Smoke step 8's `awk 'END { exit !(NR <= 200) }'` fix landed; carry-over text still pending pushdown

**Task:** task_25_periodic_skill_audit.md
**Issue:** Round-9 L1 recommended swapping smoke step 8 from `$(wc -l < ...)` to `awk 'END { exit !(NR <= 200) }'`. The Bash-safe rewrite landed (verified: line 147 `awk 'END { exit !(NR <= 200) }' scripts/audit/skills_efficiency.py && echo "skills_efficiency.py ≤ 200 lines"`). What did not land is the carry-over text — §Carry-over from task analysis (line 192) still reads `*None at draft time. Populated by /clean-tasks m21 runs.*`. Phase-3 pushdown is the standard path for this LOW.
**Recommendation:** Append to T25 §Carry-over from task analysis: "Round 9 L1 — smoke step 8 swapped from `$(wc -l < ...)` to `awk 'END { exit !(NR <= 200) }'` per `_common/verification_discipline.md` Bash-safety rule (no command substitution / parameter expansion in smoke commands)."
**Push to spec:** yes — orchestrator append to T25 carry-over section at /clean-tasks Phase 3.

#### L2 — Operator-only heuristics' synthetic-fixture testing note still pending pushdown

**Task:** task_25_periodic_skill_audit.md
**Issue:** Round-9 L2 noted that `tool-roundtrips` and `file-rereads` (operator-only heuristics, surfaced via `/audit-skills`) have no live target on disk; the Builder benefits from a note clarifying whether they need Python implementation + unit-test coverage or live solely in the slash-command procedure prose. Round-9 H2 fix structurally moved both rules to operator-only, which resolves the CI concern; the carry-over note about Python-vs-prose implementation has not been pushed.
**Recommendation:** Append to T25 §Carry-over from task analysis: "Round 9 L2 — `tool-roundtrips` and `file-rereads` are operator-only heuristics surfaced via `/audit-skills`. If implemented in `scripts/audit/skills_efficiency.py` (not required), unit tests should drive the rule-fires-on-violation paths via synthetic fixtures (not against live `.claude/skills/`, which is heuristic-clean by Step 1b construction). If they live solely in slash-command procedure prose with no Python implementation, no unit-test coverage is needed."
**Push to spec:** yes — orchestrator append to T25 carry-over section at /clean-tasks Phase 3.

#### L3 — `screenshot-overuse` heuristic Anthropic-tool-name framing note still pending pushdown

**Task:** task_25_periodic_skill_audit.md
**Issue:** Round-9 L3 noted `screenshot-overuse` heuristic phrasing in the spec mentions `get_page_text` (an Anthropic Computer Use tool name) verbatim from the cited Nicholas Rhodes article. ai-workflows is a CLI/MCP project, not a Computer Use surface. The Builder may want to generalize the regex to local-context terms (`text-extraction|parse|extract|read.*text`) so the rule reads ai-workflows-native, or keep verbatim as a deliberate cite — both are acceptable.
**Recommendation:** Append to T25 §Carry-over from task analysis: "Round 9 L3 — `screenshot-overuse` heuristic uses `get_page_text` (Anthropic Computer Use tool name) verbatim from the Nicholas Rhodes source. Builder may keep verbatim (deliberate research-brief cite) OR generalize the adjacency regex to local-context terms (e.g. `text-extraction|parse|extract|read.*text`) so the rule reads ai-workflows-native. Either choice is acceptable; document the chosen framing in the audit script's module docstring."
**Push to spec:** yes — orchestrator append to T25 carry-over section at /clean-tasks Phase 3.

## What's structurally sound

- **Round-10 M1 fix landed correctly.** §Step 2 line 58 now frames the four anchors (Inputs / Procedure / Outputs / Return schema) as a *new convention T25 introduces* rather than as one inherited from sibling slash commands. Live verification: `audit.md` has zero `##` anchors; `clean-tasks.md` has `## Agent-return parser convention / Project setup / Spawn-prompt scope discipline / Phase 1/2/3 / Stop conditions / Reporting / Why...`; `auto-implement.md` has `## Agent-return parser convention / Cache-breakpoint verification / Spawn-prompt scope discipline / Hard halt boundaries / Pre-flight / Project setup / Two-prompt long-running pattern / ...`. None match Inputs/Procedure/Outputs/Return-schema — the spec's "introduces" framing is now accurate. Smoke step 9 (line 150) correctly greps for the four anchors; AC2 (line 156) correctly enforces them. Clean resolution.
- **Round-9 H1 fix (heuristic tightening + Step 1b)** still holds. §Step 1 line 37 specifies `missing-tool-decl` counts tool names inside fenced code blocks or at the start of bullets only. §Step 1b authorizes adding `allowed-tools:` frontmatter to both existing Skills (verified: `.claude/skills/ai-workflows/SKILL.md` and `.claude/skills/dep-audit/SKILL.md` both currently lack frontmatter — Step 1b's edits remain necessary for clean-tree precondition). Deliverables list items 3-4 cover both edits; AC2b + smoke step 2b verify them.
- **Round-9 H2 fix (operator-only split)** still holds. CI-gated heuristics (`screenshot-overuse`, `missing-tool-decl`) vs operator-only heuristics (`tool-roundtrips`, `file-rereads`) remain cleanly separated; `--check` flag list narrowed to `screenshot-overuse | missing-tool-decl | all` (line 30, line 42, line 116-118 + AC1). Slash-command Step 2 owns the operator-only walks.
- **Round-9 M1/M2/M3 fixes** all hold. Skill count "currently 2: ai-workflows and dep-audit" (line 169) verified against live tree. `/schedule` softening intact (line 170 — "future scheduling Skill (e.g. `/schedule`) can adopt"). Four-anchor enumeration intact at lines 60-63.
- **Smoke + AC mechanics.** Smoke step 8 (line 147) Bash-safe (`awk 'END { exit !(NR <= 200) }'`, no command substitution). Smoke step 9 (line 150) verifies four `##` anchors. AC1 (CI-gated checks), AC2 (slash-command body shape), AC2b (frontmatter precondition) cleanly distinguish the three classes of verification.
- **Cross-spec deferral convergence** verified clean: T24 TA-LOW-02, T12 §Out of scope, T26 §Out of scope all correctly absorb at T25 (lines 86, 178-180, 188-190).
- **Status surface mechanics.** AC9 names "row 75" as the T25 row — re-verified live; line 75 of M21 README is the T25 row (`| 25 | Periodic skill / scheduled-task efficiency audit ...`). G5 amendment guidance correctly differentiates T25's audit-prompt half from T26's already-applied two-prompt half.
- **Locked specs (T10/T11/T12/T24/T26)** all show ✅ — re-verified at this round. T10 reads `✅ Complete.` while the others read `✅ Done.`; cosmetic-only drift, T10 locked and out of scope.
- **No KDR drift in T25.** Autonomy-infra only (`.claude/`, `scripts/audit/`, `.github/workflows/ci.yml`, two SKILL.md frontmatter edits). Layer rule, MCP-as-substrate (002), no Anthropic API (003), validator pairing (004), retry-via-RetryingEdge (006), FastMCP schema (008), SqliteSaver checkpoint (009), user-owned external workflow code (013) — all unaffected.

## Cross-cutting context

- **Project memory unchanged since round 10.** M12 autopilot checkpoint and autonomy-optimization follow-ups still ground T25's purpose. CS300 pivot status remains non-blocking for M21.
- **Loop trajectory:** Round 9 closed at 2 HIGH + 3 MEDIUM + 3 LOW = 8 findings. Round 10 closed at 0 HIGH + 1 MEDIUM + 3 LOW = 4 findings. Round 11 closes at 0 HIGH + 0 MEDIUM + 3 LOW = 3 findings → **LOW-ONLY**. Orchestrator pushes the three LOWs to T25 §Carry-over from task analysis at /clean-tasks Phase 3 and exits the analyze+fix loop.
- **Loop limit:** Round 3 of 5 for T25 per /clean-tasks per-task limit. Reached LOW-ONLY with two rounds to spare.
