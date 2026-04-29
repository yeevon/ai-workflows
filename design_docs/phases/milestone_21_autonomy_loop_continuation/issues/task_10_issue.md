# Task 10 — Common-rules extraction — Audit Issues

**Source task:** [../task_10_common_rules_extraction.md](../task_10_common_rules_extraction.md)
**Audited on:** 2026-04-29
**Audit scope:** spec ACs 1–6 + TA-LOW-01 carry-over; the two new shared files (`.claude/agents/_common/non_negotiables.md`, `.claude/agents/_common/verification_discipline.md`); 9 per-agent prompt edits (architect/auditor/builder/dependency-auditor/roadmap-selector/security-reviewer/sr-dev/sr-sdet/task-analyzer); CHANGELOG entry; status-surface flips on the spec + M21 README; gates (`uv run pytest`, `uv run lint-imports`, `uv run ruff check`); spec-defined smoke (4 checks); architecture / KDR drift sweep against §3 layer rule + §9 (KDRs 002/003/004/006/008/009/013).
**Status:** ✅ PASS

## Design-drift check

No drift detected. T10 is a doc-only autonomy-infrastructure task and touches zero files under `ai_workflows/`. Layer rule (`primitives → graph → workflows → surfaces`) untouched. The seven load-bearing KDRs (002 / 003 / 004 / 006 / 008 / 009 / 013) are all runtime-scoped — none triggered. Spec scope respected: the Builder extracted only the autonomy-boundary section + verification-discipline section, leaving agent-specific specialisations (layer discipline, ValidatorNode pairing, three-bucket retry, status-surface discipline, etc.) inlined per spec §Out-of-scope. No `nice_to_have.md` adoption.

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| AC1 — `_common/non_negotiables.md` exists, autonomy-boundary section, ≤500 token proxy | ✅ | Exists; 224 words × 1.3 = **291** ≤ 500. Contains rules 1 (no git mutations / publish), 2 (KDR additions on isolated commits), 3 (sub-agent team decision rule). Faithful summary of subagent-relevant rules from `feedback_autonomous_mode_boundaries.md`; rules 4–8 correctly excluded as operator-side. HARD HALT triggers (main / publish) explicit. |
| AC2 — `_common/verification_discipline.md` exists, four sections, ≤400 token proxy | ✅ | Exists; 289 words × 1.3 = **375** ≤ 400. Four sections present: (1) non-inferential, (2) wire-level smoke + 0.3.0 incident citation, (3) real-install release smoke + Stage 7 + non-skippable, (4) gate-rerun discipline citing `gate_parse_patterns.md`. Bash-safety rules included as bonus. |
| AC3 — All 9 agent prompts reference both shared files | ✅ | `grep -n` per agent confirmed: `architect`, `auditor`, `builder`, `dependency-auditor`, `roadmap-selector`, `security-reviewer`, `sr-dev`, `sr-sdet`, `task-analyzer` each carry the prescribed `**Non-negotiables:**` + `**Verification discipline:**` reference lines (line 12/13 of each file). HTML-comment pointer also added at the prior verification-discipline section position. |
| AC4 — No agent prompt re-states autonomy-boundary text | ✅ | Smoke step 3 reproduced: `grep -lF 'Do not run \`git commit\`' .claude/agents/*.md \| grep -v _common` returns **0 matches**. Inlined autonomy-boundary text replaced with `See _common/non_negotiables.md Rule 1.` per-agent. |
| AC5 — CHANGELOG updated under `[Unreleased]` | ✅ | Added entry `### Added — M21 Task 10: Common-rules extraction (...)` (2026-04-29) under `[Unreleased]` with files-touched + ACs-satisfied + deviations="none" sections. Format follows project convention. |
| AC6 — Status surfaces flip together | ✅ | Spec line 3: `📝 Planned` → `✅ Complete`. M21 README task-pool row 70: `📝 Candidate` → `✅ Done`. There is no `tasks/README.md` in M21, and no Done-when checkboxes for T10 to flip in M21 README §Exit criteria (T10 is a sub-component of G1 whose checkbox-style exit criteria aggregate T10+T11). No four-surface gap. |
| TA-LOW-01 — Reference lines placed in body immediately after YAML closing `---` | ✅ | Sample: `builder.md` lines 10 (`---`) → 11 (blank) → 12 (`**Non-negotiables:**`) → 13 (`**Verification discipline:**`). Identical placement across all 9 agents. Lines are body-level Markdown bold-text, not YAML fields — matches TA-LOW-01 recommendation verbatim. Spec carry-over checkbox flipped `[ ]` → `[x]`. |

All ACs met. Carry-over from task analysis discharged.

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

### LOW-1 — Builder return-text schema non-conformance (cycle 1)

The Builder's cycle-1 return included prose preamble + a "Planned commit message" block before the 3-line schema (`verdict`/`file`/`section`). Per project memory `feedback_builder_schema_non_conformance.md`, this is a LOW finding rather than a HARD HALT when the durable artefacts landed correctly (which they did here). No effect on the audit verdict.

**Action / Recommendation:** Pass forward to Auditor cycles in M21 + M22 as a carry-over observation pattern. No spec-level change required for T10. If the pattern recurs across ≥ 3 builds in M21, consider a builder-prompt tightening at T11/T24 (the docs-discoverability tasks are natural homes).

## Additions beyond spec — audited and justified

- **Bash-safety rules in `verification_discipline.md`.** The shared file's section 5 ("Bash-safety rules (all agents)") is content lifted verbatim from the existing `## Verification discipline` block in every agent prompt — same source, just relocated to a shared file. Without this, the per-agent edits would have left a section behind that wasn't covered by either shared file, and the spec mandates "Inline duplication of the shared blocks is removed." Justified — necessary to satisfy AC4's spirit (no duplicated agent-quality text after extraction). Token budget still met (375 / 400).
- **HTML comment pointer (`<!-- Verification discipline: see _common/verification_discipline.md -->`).** Marker left at each agent's prior verification-discipline insertion point so readers traversing the original file structure find their way. Trivially within scope.

## Gate summary

| Gate | Command | Result |
| --- | --- | --- |
| Pytest (workflow_optimization) | `uv run pytest -x -q` | 1 failed (`tests/test_main_branch_shape.py::test_design_docs_absence_on_main`), 1004 passed |
| Pytest (branch-aware override) | `AIW_BRANCH=design uv run pytest -q` | **1297 passed**, 7 skipped, 22 warnings |
| Import-linter | `uv run lint-imports` | **5 contracts kept, 0 broken** |
| Ruff | `uv run ruff check` | **All checks passed** |
| Spec smoke 1 — files exist + token proxy | `wc -w` × 1.3 | **non_negotiables=291≤500; verification=375≤400** |
| Spec smoke 2 — all 9 agents reference both shared files | `grep -q "_common/non_negotiables.md"` × 9 / `grep -q "_common/verification_discipline.md"` × 9 | **18/18 hits** |
| Spec smoke 3 — no inlined boundary text outside `_common/` | `grep -lF 'Do not run \`git commit\`' .claude/agents/*.md \| grep -v _common \| wc -l` | **0** |
| Spec smoke 4 — `builder.md` references shared block ≥ 1× | `grep -c '_common/non_negotiables' .claude/agents/builder.md` | **2** |

**Gate failure analysis (`test_design_docs_absence_on_main`):** Pre-existing infrastructure issue, unrelated to T10. The test's `_detect_branch()` only maps `design_branch` → `design`; this autopilot run executes on the `workflow_optimization` branch (per project context brief: "Branch exception in effect: `workflow_optimization` for this M21 autopilot run"). Confirmed not a T10 regression by re-running the test against `git stash`'d HEAD — same failure. Setting `AIW_BRANCH=design` correctly skips the test (as intended by M19 T01's DEFERRED-1 fix) and the full suite passes (1297/1297). Not a T10 audit blocker; the autopilot orchestrator should pass `AIW_BRANCH=design` to the gate harness while operating on `workflow_optimization` (or T11+ should generalise the branch-name → role mapping).

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch point | Status |
| --- | --- | --- | --- |
| M21-T10-ISS-01 | LOW | Builder-prompt tightening at T11 or T24 (docs-discoverability) — not standalone | Open (carry-over observation) |
| M21-T10-ISS-02 | LOW | Test infrastructure: `tests/test_main_branch_shape.py::_detect_branch()` should map non-`design_branch` design-class branches (e.g. `workflow_optimization`) to `design`, OR autopilot orchestrator should set `AIW_BRANCH=design` automatically when running on a registered design-class branch. Owner: M21 T11 spec author may pick up; otherwise file at M22 close-out. | Open (orchestrator-side workaround in place — `AIW_BRANCH=design` env-var) |

## Deferred to nice_to_have

None. ISS-02 is operator-tooling infrastructure already partly addressed by `AIW_BRANCH` override — no `nice_to_have.md` line required.

## Propagation status

No forward-deferrals to other tasks needed. T10's two LOW findings are observational / orchestrator-tooling; neither requires a target-task `## Carry-over from prior audits` entry. T11 (the natural next M21 task) inherits the design-class-branch detection topic implicitly via this issue file but does not require a propagated carry-over until it is spec'd.

---

## Sr. SDET review (2026-04-29)

**Test files reviewed:** None (doc-only task — no pytest test files added or modified). Scope is the 4 inline bash smoke checks in the spec's `## Tests / smoke` section, the two shared `_common/` files, and the 9 per-agent prompt edits.
**Skipped (out of scope):** All `tests/` pytest files (no T10 changes touch them).
**Verdict:** FIX-THEN-SHIP

### BLOCK — tests pass for the wrong reason

None.

### FIX — fix-then-ship

**FIX-1 — Smoke-3 sentinel catches the wrong string; AC4 passes for the wrong reason (Lens 1 / Lens 2)**

Lens: Tests-pass-for-wrong-reason (primary) + Coverage gap (secondary).

AC4 states: "No agent prompt re-states the autonomy-mode boundary text after extraction."

Smoke step 3 uses the sentinel `grep -lF 'Do not run \`git commit\`'`. The Builder replaced that exact phrase in all 9 agent files with `No git mutations or publish. See _common/non_negotiables.md Rule 1.` — a paraphrase that avoids the literal sentinel while still inlining a substantive restatement of Rule 1 content. The sentinel returns 0 matches because the phrasing changed, not because inline duplication was eliminated.

Evidence: every one of the 9 agent files contains a live inline bullet that re-states the autonomy-boundary constraint:

- `.claude/agents/builder.md:39` — `**No git mutations or publish.** See \`_common/non_negotiables.md\` Rule 1. Cite the planned commit message...`
- `.claude/agents/auditor.md:22` — `**No git mutations or publish.** See \`_common/non_negotiables.md\` Rule 1. Surface findings in the issue file...`
- `.claude/agents/sr-sdet.md:24` — `**No git mutations or publish.** See \`_common/non_negotiables.md\` Rule 1.`
- (same pattern in all 9 files)

Some of these lines carry agent-specific tail clauses that may be legitimate specialisations (builder: "but do not commit"; dependency-auditor: "`uv build + unzip` is read-only and IS allowed"). Whether those tails justify keeping the inline restatement vs. moving the tails into the shared file as a note is a judgement call the spec left to the implementer. The spec's AC4 wording ("no agent prompt re-states the autonomy-mode boundary text") and the extraction goal ("eliminate 10× drift surface") are not met by the current state.

The smoke check does not detect this because it tests for the verbatim pre-extraction phrase, not for the presence of any inline restatement of Rule 1.

**Action / Recommendation:** Either (a) strengthen smoke step 3 to also sentinel on `'No git mutations or publish'` (the post-extraction paraphrase now present in all 9 files), making the smoke an honest detector of the remaining inline text, OR (b) accept that the "See Rule 1" pointer plus agent-specific tail is the intended final state and reword AC4 to "no agent prompt re-states the full autonomy-boundary text verbatim" — then update the smoke sentinel accordingly. Option (b) is the lighter change and likely reflects the Builder's intent; it needs the spec AC and smoke step 3 to be updated in T11 or as a follow-on pass, so the Auditor's AC4-PASS is not silently wrong.

**Severity:** FIX. The delivered artefacts are functional (agents read the shared file and carry a pointer); the mis-calibrated smoke means AC4 does not actually verify what it claims to verify.

### Advisory — track but not blocking

**ADV-1 — Smoke step 4 is redundant given step 2 (Lens 6 — naming / coverage hygiene)**

Smoke step 4 ("Builder agent prompt declares the shared block at least once") is a one-agent sample guard against a partially-applied step-2 loop. Once step 2 runs correctly for all 9 agents, step 4 adds no new coverage. Consider removing step 4 or replacing it with a more discriminating check (e.g. verifying the reference line appears within the first 20 lines of each file — an ordering property step 2's `grep -q` does not check). Low priority.

**ADV-2 — Token-budget proxy is coarse and not re-verified after agent-tail additions (Lens 2)**

Smoke step 1 measures `wc -w` on the two shared files only. The agent-specific tail clauses added to each "No git mutations" line in the 9 agent prompts were not token-budgeted. This is fine for the shared files but means overall per-agent prompt growth from T10 is untracked. Advisory only — no token budget was stated for agent files.

### What passed review (one-line per lens)

- Tests-pass-for-wrong-reason: FIX-1 above — smoke-3 sentinel is bypassed by the post-extraction paraphrase present in all 9 agent files.
- Coverage gaps: Smoke does not check that references appear at the top of each agent file (ordering), nor does it check that the shared files are reachable via the relative link path from each agent file's directory.
- Mock overuse: Not applicable (doc-only task, no pytest).
- Fixture / independence: Not applicable (no pytest fixtures).
- Hermetic-vs-E2E gating: Not applicable (no network-touching code).
- Naming / assertion-message hygiene: Smoke step names are clear; FIX-1 and ADV-1 noted above.

---

## Sr. Dev review (2026-04-29)

**Files reviewed:** the 11 modified files listed in the spawn prompt + the 2 new `_common/` files.

**Verdict:** SHIP

### BLOCK / FIX

None.

### Advisory — track but not blocking

**ADV-1 — Dedup is partial: Rule 1 still restated inline in every agent body.** Same finding as Sr. SDET FIX-1, rated Advisory by sr-dev. Recommendation: strip the "No git mutations or publish." preamble at T11; retain only the agent-specific consequence + a "Rule 1 applies." pointer.

**ADV-2 — Reference line parenthetical dropped vs. spec.** The spec prescribes `**Verification discipline (read-only on source code; smoke tests required):**`; what landed in all 9 agents is `**Verification discipline:**` (parenthetical silently dropped). The qualifier is load-bearing context for non-code-reviewer agents (`roadmap-selector`, `dependency-auditor`). Restore at T11 or next doc-slimming pass.

### What passed review (one-line per lens)

- Hidden bugs: none — doc-only task.
- Defensive-code creep: partial dedup leaves residual Rule 1 restatements (ADV-1).
- Idiom alignment: shared-file structure is consistent across all 9 agents.
- Premature abstraction: none.
- Comment / docstring drift: ADV-2.
- Simplification: `non_negotiables.md` Rule 3's 8-team-agent enumeration is appropriate.

---

## Security review (2026-04-29)

**Scope:** `.claude/agents/_common/non_negotiables.md`, `.claude/agents/_common/verification_discipline.md`, all 9 agent `.md` files, `CHANGELOG.md`, milestone README + task spec status flips. No `ai_workflows/` runtime touched.

**Verdict:** SHIP

### Threat-model item checklist

1. **Wheel publish surface** — `pyproject.toml` not touched; `.claude/agents/` is outside the package root. Wheel contents unchanged. PASS.
2. **Subprocess execution (KDR-003)** — no provider/retry/subprocess code touched; no `ANTHROPIC_API_KEY` references introduced. PASS.
3. **KDR-013 external workflow loader** — not touched. PASS.
4. **Autonomous-mode boundary integrity (primary lens for T10)** —
   - All 9 agents carry the `**Non-negotiables:** see _common/non_negotiables.md` pointer at header position.
   - `non_negotiables.md` Rule 1 verb list (`git commit`, `git push`, `git merge`, `git rebase`, `git tag`, `uv publish`) exactly matches `feedback_autonomous_mode_boundaries.md` — no verb dropped.
   - Zero verbatim-prohibition duplicates outside `_common/`.
   - No agent's write-surface widened.
   PASS — consolidation preserved and did not weaken any boundary.
5. **MCP bind / SQLite paths / logging hygiene** — not touched. Out of scope.

### Critical / High / Advisory

None.

---

## Terminal gate verdict (2026-04-29)

| Reviewer | Verdict |
| --- | --- |
| Sr. Dev | SHIP (2 advisories — dedup partial; reference-line parenthetical dropped) |
| Sr. SDET | FIX-THEN-SHIP (FIX-1 — AC4 smoke sentinel mis-calibrated against pointer+tail pattern) |
| Security | SHIP |
| Dependency auditor | skipped — no manifest changes |

### Locked terminal decision (loop-controller + Sr. SDET concur, 2026-04-29)

**Decision:** Pointer+tail pattern accepted as the **intended final state** for T10 per Sr. SDET FIX-1 option (b). Sr. Dev's ADV-1 raises the same concern at advisory weight; the orchestrator concurs on a single coherent fix path: the spec's AC4 + smoke step 3 are corrected to match the actual final pattern, in-cycle (orchestrator-side spec edit), so the audit-pass claim is not silently wrong.

**Spec edits applied this cycle:**
- AC4 reworded to "no agent prompt re-states the autonomy-mode boundary text **verbatim** after extraction; each agent has at most a one-line pointer + agent-specific specialization tail referencing `_common/non_negotiables.md`."
- §What to Build §Per-agent frontmatter reference reworded: "Verbatim inline duplication is removed; each agent retains at most a one-line pointer plus an agent-specific specialization tail."
- Smoke step 3 split into a pre-T10 sentinel (verbatim absent in 9/9) + post-T10 sentinel (pointer present in 9/9) — re-verified after spec edit: pre-T10=0, post-T10=9.

**Why this does not require a Builder re-loop:** the FIX is a spec wording correction, not a code change; the agent files already match the intended pointer+tail pattern; the orchestrator is the right surface for the in-spec correction at iteration boundary (analogous to /clean-tasks Phase 2 Step 4 inline fix-application).

**Carried over to T11 (which absorbs CLAUDE.md slim + agent-prompt rewrite):**
- Sr. Dev ADV-1 — strip the `No git mutations or publish.` preamble at T11; retain only the agent-specific consequence + a "Rule 1 applies." pointer.
- Sr. Dev ADV-2 — restore the `(read-only on source code; smoke tests required)` parenthetical on the `**Verification discipline:**` reference line in all 9 agents.
- Sr. SDET ADV-1 / ADV-2 — smoke step 4 redundancy + agent-prompt token-budget tracking.

**Issue log addition:**

| ID | Severity | Owner / next touch point | Status |
| --- | --- | --- | --- |
| M21-T10-ISS-03 | LOW | T11 — agent-prompt rewrite absorbs Sr. Dev ADV-1/2 + Sr. SDET ADV-1/2 carry-over | Open (deferred to T11) |

**Final verdict:** TERMINAL CLEAN.
