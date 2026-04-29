# Task 11 — CLAUDE.md slim — Audit Issues

**Source task:** [../task_11_claude_md_slim.md](../task_11_claude_md_slim.md)
**Audited on:** 2026-04-29
**Audit scope:** CLAUDE.md, .claude/agents/*.md (9 agents), M21 README, CHANGELOG.md
**Status:** ✅ PASS

## Design-drift check

No drift detected. This is a doc-only task — no runtime code changes, no KDR violations, no layer boundary crossings.

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| AC1 `wc -l CLAUDE.md` ≤ 95 | met | 83 lines (39% reduction from 136) |
| AC2 CLAUDE.md retains summary + anchor for threat model, KDR table, verification discipline | met | All three pointers present and verified |
| AC3 security-reviewer.md has full `## Threat model` section | met | Replaced stub; renamed from `(read first)` per TA-LOW-02 |
| AC4 auditor/task-analyzer/architect/dependency-auditor carry `## Load-bearing KDRs (drift-check anchors)` | met | All four agents verified |
| AC5 ADV-1 absorbed (smoke step 5 = 0) | met | `**No git mutations or publish.**` preamble stripped from all 9 agents |
| AC6 ADV-2 absorbed (smoke step 6 ≥ 9) | met | Parenthetical `(read-only on source code; smoke tests required)` restored in 9/9 agents |
| AC7 T10 invariant held (smoke step 7 = 9) | met | `_common/non_negotiables.md` pointer present in 9/9 agents |
| AC8 CHANGELOG.md updated | met | Entry under `[Unreleased]` |
| AC9a T11 spec `**Status:**` flipped to Done | met | |
| AC9b M21 README task-pool row 71 Status → Done | met | |
| AC9c M21 README §G1 prose amended with satisfaction parenthetical | met | Records 83-line final count |
| TA-LOW-01 Move-table cosmetic numbers | met | Cosmetic line-count claims in spec not material; smoke verifies global threshold |
| TA-LOW-02 Move 1 instruction sequencing | met | Replaced existing stub directly; renamed heading to `## Threat model` |
| TA-LOW-03 G1 grep tightening | met | G1 grep updated to `grep -q "security-reviewer.md#threat-model"` |

## Gate summary

| Gate | Command | Result |
| -- | -- | -- |
| pytest | `uv run pytest` | N/A — doc-only task, no Python changes |
| lint-imports | `uv run lint-imports` | N/A — doc-only task |
| ruff | `uv run ruff check` | N/A — doc-only task |
| smoke-1 | `wc -l CLAUDE.md` | PASS — 83 lines |
| smoke-2 | anchor greps | PASS — all 3 present |
| smoke-3 | threat model in security-reviewer.md | PASS |
| smoke-4 | KDR table in 4 drift-check agents | PASS |
| smoke-5 | ADV-1 preamble stripped | PASS — 0 files retain preamble |
| smoke-6 | ADV-2 parenthetical restored | PASS — 9/9 agents |
| smoke-7 | T10 invariant | PASS — 9/9 agents |

## Sr. SDET ADV-2 — Per-agent prompt word-count baseline (2026-04-29)

Pre-T11 baselines (before this task's edits):

| Agent | Words (pre-T11) |
| ----- | --------------- |
| architect.md | 1221 |
| auditor.md | 1869 |
| builder.md | 788 |
| dependency-auditor.md | 1109 |
| roadmap-selector.md | 2079 |
| security-reviewer.md | 1155 |
| sr-dev.md | 1584 |
| sr-sdet.md | 1641 |
| task-analyzer.md | 2751 |
| **Total** | **14197** |

No enforced budget at this baseline stage. These counts are recorded here for future slimming reference (T12 Skills extraction and T24 MD-file discoverability audit may consume this baseline).

## 🟢 LOW — M21-T11-ISS-01 Builder return-text schema non-conformance

The Builder's cycle-1 return included a prose preamble + planned-commit-message block before the 3-line schema (`verdict: BUILT`, `file: …`, `section: —`). Per project memory `feedback_builder_schema_non_conformance.md`, this is LOW + observation rather than an autopilot HARD HALT — durable work landed correctly (all ACs met, smoke 1–7 pass, status surfaces aligned).

**Action / Recommendation:** No remediation required for this task. Pass observation forward as a carry-over note to whichever Builder spawns next (T12 — Skills extraction is the next blocker downstream). Loop-controller-equivalent behaviour: orchestrator records the schema slip, autonomy proceeds.

## Issue log — cross-task follow-up

| ID | Severity | Owner / Next touch | Status |
| --- | -------- | ------------------ | ------ |
| M21-T11-ISS-01 | LOW | Builder schema discipline (next Builder spawn — T12) | OBSERVED — no remediation gate; recurring-pattern monitor only |

## Propagation status

No forward deferrals to a different task spec — M21-T11-ISS-01 is a recurring-pattern observation handled by the existing memory file, not a per-task carry-over. TA-LOW-01/02/03 absorbed inline.

## Sr. SDET review (2026-04-29)

**Test files reviewed:** None — doc-only task. Smoke checks 1–7 are Bash assertions against doc files; no pytest test files added or modified.
**Skipped (out of scope):** All pytest test files (no Python source touched).
**Verdict:** SHIP

### What the five invoker-directed lens questions found

**Q1 — Smoke step 5 partial-strip regression vector.**
Smoke step 5 (`grep -lF '**No git mutations or publish.**' ... > /tmp/aiw_t11_adv1.txt`) uses `-F` (fixed-string, no glob) against all 9 named agent files and asserts the output file is empty. A partial strip (some agents still carrying the old preamble, others not) would surface as a non-empty file and fail the `awk NR==0` assertion. The sentinel string `**No git mutations or publish.**` is specific enough that there is no realistic false-negative: the old preamble used exactly this bold-formatted phrase. Confirmed on the live files: zero occurrences across all 9 agents. The regression vector is adequately covered.

**Q2 — Smoke step 6 sentinel string exactness.**
Smoke step 6 asserts `**Verification discipline (read-only on source code; smoke tests required):**` across 9/9 files using `-F`. Live verification: all 9 agents carry the string at line 13, matching exactly. The Auditor graded AC6 as met; the live state confirms it.

**Q3 — Smoke step 7 T10 pointer invariant.**
Smoke step 7 asserts `_common/non_negotiables.md` pointer present in 9/9 agents. Live verification: every agent carries it — some on line 12 (header-level `**Non-negotiables:**` reference), others also repeated inline in the `Commit discipline` body line. Count is 9/9 (some agents have 2 occurrences; the `awk NR==9` assertion counts _files_ from `grep -l`, not occurrences, so it tolerates multiple-per-file correctly).

**Q4 — Shape coverage: load-bearing sections not protected by smoke.**
Smoke step 1 protects the line-count ceiling (≤ 95). Smoke steps 2–7 protect the six moved sections' destination anchors. The `## Non-negotiables` section (now lines 66–83) is retained verbatim — confirmed on read. The `## Canonical file locations` table (lines 46–63), the `## Repo layout` section (lines 29–36), and the `## Grounding` section (lines 14–26) are also present. No load-bearing section was accidentally removed. Advisory: the smoke suite does not include a positive presence check for `## Non-negotiables` or `## Canonical file locations` (a future accidental removal would go undetected until someone noticed). This is a test-coverage gap but not a regression the current task introduced; filing as Advisory.

**Q5 — Bash-safety conformance of smoke steps.**
Reviewed all 7 smoke commands in the spec:
- Steps 1–4: `wc -l`, `awk END`, `grep -q` — no `$(...)`, no parameter expansion, no loop body. Clean.
- Step 5: `grep -lF '...' <explicit file list> > /tmp/...` then `awk 'END { exit !(NR == 0) }' /tmp/...` — unrolled (no loop), no `$VAR` expansion in a loop body, no `$(...)`. Clean.
- Step 6: same unrolled pattern. Clean.
- Step 7: same unrolled pattern. Clean.
All 7 steps conform to `_common/verification_discipline.md` Bash-safety rules.

**ADV-1 agent-specific tail check (pointer+tail invariant from T10).**
The invoker noted: verify ADV-1 strip did not accidentally collapse legitimate agent-specific consequence text. Spot-checked `builder.md:39` ("Commit discipline. Cite the planned commit message in your report (per existing rule), but do not commit. _common/non_negotiables.md Rule 1 applies."), `security-reviewer.md:19` ("Surface findings in the issue file — do not run the command. _common/non_negotiables.md Rule 1 applies."), and `sr-sdet.md:24` ("If your finding requires a git operation, describe the need in your output — do not run the command. _common/non_negotiables.md Rule 1 applies."). Each retains a role-specific consequence clause; none collapsed to just the Rule 1 pointer. The tail is intact.

### 🔴 BLOCK — tests pass for the wrong reason
None.

### 🟠 FIX — fix-then-ship
None.

### 🟡 Advisory — track but not blocking
- **Shape-coverage gap** (Lens 2): smoke steps do not include a presence check for `## Non-negativables` or `## Canonical file locations` in CLAUDE.md. A future accidental removal of these sections would pass all 7 smoke steps. Recommendation: add `grep -q "^## Non-negotiables" CLAUDE.md` and `grep -q "^## Canonical file locations" CLAUDE.md` to the smoke suite (or its successor) in T24 or the next doc-touching task. Not a regression introduced by T11.

### What passed review (one line per lens)
- Tests-pass-for-wrong-reason: none observed.
- Coverage gaps: one advisory shape-coverage gap (Non-negotiables / Canonical-file-locations sections unguarded); not a T11 regression.
- Mock overuse: N/A — doc-only task, no pytest.
- Fixture / independence: N/A — doc-only task.
- Hermetic-vs-E2E gating: N/A — no new tests.
- Naming / assertion-message hygiene: smoke step naming is clear and maps 1:1 to ACs.

## Sr. Dev review (2026-04-29)

**Files reviewed:** CLAUDE.md, .claude/agents/architect.md, .claude/agents/auditor.md, .claude/agents/builder.md, .claude/agents/dependency-auditor.md, .claude/agents/roadmap-selector.md, .claude/agents/security-reviewer.md, .claude/agents/sr-dev.md, .claude/agents/sr-sdet.md, .claude/agents/task-analyzer.md, CHANGELOG.md, design_docs/phases/milestone_21_autonomy_loop_continuation/README.md, design_docs/phases/milestone_21_autonomy_loop_continuation/task_11_claude_md_slim.md
**Skipped (out of scope):** none
**Verdict:** FIX-THEN-SHIP

### 🔴 BLOCK — must-fix before commit

_(none)_

### 🟠 FIX — fix-then-ship

**FIX-01 — Dangling self-reference in CLAUDE.md Non-negotiables (idiom alignment)**

`CLAUDE.md:71` — The Seven KDRs bullet reads: "Violation of any KDR (002/003/004/006/008/009/013 — **see the table above**) is HIGH at audit."

The inline KDR table that this phrase pointed to was removed as part of the slim (it now lives in `auditor.md` only, per line 25's pointer). "The table above" no longer exists in CLAUDE.md — the only KDR prose above line 71 is the one-paragraph summary at line 25 and the file-pointer. Any agent reading CLAUDE.md's Non-negotiables section and encountering "see the table above" will find nothing to look at.

The line 25 pointer already tells agents where the full table lives. The parenthetical at line 71 should either be dropped entirely or updated to mirror line 25's pointer.

**Action:** In `CLAUDE.md:71`, change `— see the table above` to `— full table in [auditor.md](`.claude/agents/auditor.md#load-bearing-kdrs-drift-check-anchors`)` (mirroring the line 25 pointer), or simply remove the parenthetical since the KDR IDs are already listed inline and line 25 provides the full-table anchor.

### 🟡 Advisory — track but not blocking

_(none)_

### What passed review (one-line per lens)

- **Hidden bugs:** No runtime code touched; doc-only task — not applicable.
- **Defensive-code creep:** No defensive additions found; all nine agent preambles correctly trimmed.
- **Idiom alignment:** All nine agents follow the settled `**Non-negotiables:** see _common/non_negotiables.md` + `**Verification discipline (read-only on source code; smoke tests required):** see _common/verification_discipline.md` two-liner pattern consistently. One dangling self-reference in CLAUDE.md (FIX-01 above).
- **Premature abstraction:** No new abstractions introduced; this is a content-reorganisation task only.
- **Comment / docstring drift:** KDR table pointer at CLAUDE.md:25 is accurate and consistent with the copies added to four agents. The security-reviewer.md threat-model section is coherent and self-contained. No stale cross-references found beyond FIX-01.
- **Simplification:** CLAUDE.md now 83 lines (was 136); all pointer anchors resolve correctly except FIX-01.

---

## Security review (2026-04-29)

### Lens 1 — Threat model integrity (PRIMARY)

**Destination content complete.** `.claude/agents/security-reviewer.md` carries the full two-attack-surface framing verbatim: (1) published wheel on PyPI, (2) subprocess execution (Claude Code OAuth, Ollama HTTP, LiteLLM dispatch). The `--host 0.0.0.0` foot-gun footnote, KDR-013 user-owned risk surface clause, the eight-item checklist, and the `What NOT to flag` exclusion list are all intact. No content lost.

**CLAUDE.md summary does not soften or contradict.** Anchor link `security-reviewer.md#threat-model` present and accurate.

### Lens 2 — KDR table integrity

All four drift-check agents (`auditor.md`, `task-analyzer.md`, `architect.md`, `dependency-auditor.md`) carry identical seven-row `## Load-bearing KDRs (drift-check anchors)` tables. Character-for-character identical — no paraphrasing drift.

### Lens 3 — Autonomous-mode boundary

`_common/non_negotiables.md` Rule 1 intact. ADV-1 stripped the redundant header preamble from agent prompts (smoke-5: 0 retained); all 9 agents carry the `_common/non_negotiables.md` pointer (smoke-7: 9/9). Substantive Rule 1 content fully preserved.

### Lens 4 — Wheel publish surface

`pyproject.toml` and `MANIFEST.in` not touched. `.claude/agents/` outside the `ai_workflows/` package root. No wheel-contents impact.

### Lens 5 — No nice_to_have.md adoption

Pure consolidation. No new scope.

**Verdict: SHIP** (no Critical / High / Advisory findings).

---

## Terminal gate verdict (2026-04-29)

| Reviewer | Verdict |
| --- | --- |
| Sr. Dev | FIX-THEN-SHIP (FIX-01 — dangling `see the table above` self-reference at CLAUDE.md:71) |
| Sr. SDET | SHIP |
| Security | SHIP |
| Dependency auditor | skipped — no manifest changes |

### Locked terminal decision (loop-controller + Sr. Dev concur, 2026-04-29)

**Decision:** FIX-01 applied in-cycle (orchestrator-side edit; analogous to T10's locked terminal decision). Changed `CLAUDE.md:71` from `— see the table above` to `— full table in [.claude/agents/auditor.md#load-bearing-kdrs-drift-check-anchors](...)` (mirrors line 25's pointer). Verified post-edit: `grep -n "see the table above" CLAUDE.md` returns no matches; `wc -l CLAUDE.md` still 83 (≤ 95 ceiling preserved).

**Why no Builder re-loop:** the FIX is a single mechanical line edit in CLAUDE.md, no agent-prompt changes, no test changes. Orchestrator-side spec/code edit is appropriate at iteration boundary (consistent with project bypass pattern from T10 + memory `feedback_lens_specialisation_not_divergence.md`).

**Final verdict:** TERMINAL CLEAN.
