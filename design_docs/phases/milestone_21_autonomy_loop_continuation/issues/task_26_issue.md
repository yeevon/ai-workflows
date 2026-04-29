# Task 26 — Two-prompt long-running pattern — Audit Issues

**Source task:** `design_docs/phases/milestone_21_autonomy_loop_continuation/task_26_two_prompt_long_running.md`
**Audited on:** 2026-04-29 (cycle 1) · 2026-04-29 (cycle 2)
**Audit scope:** Cycle 1 — Builder implementation; Cycle 2 — terminal-gate locked-decision verification
**Status:** ✅ PASS (cycle 2)

## Design-drift check

No drift detected. T26 is autonomy-infrastructure only (`.claude/agents/`, `.claude/commands/`, `agent_docs/`). No `ai_workflows/` runtime code changed. No new runtime dependencies. No KDR violations. All seven load-bearing KDRs unaffected.

## AC grading

| AC | Status | Notes |
|---|---|---|
| AC1 — `agent_docs/long_running_pattern.md` exists; T24 rubric summary/section-budget/code-block-len all pass | met | All three rubric checks exit 0 |
| AC2 — `agent_docs/` directory created by this task | met | Directory did not exist before; created by Builder |
| AC3 — `auto-implement.md` carries `## Two-prompt long-running pattern (T26)` section | met | grep confirmed |
| AC4 — `builder.md` references both `plan.md` and `progress.md` | met | Semantic pattern confirmed |
| AC5 — T10 invariant 9/9 | met | 9/9 grep confirmed |
| AC6 — T24 invariant — `.claude/agents/*.md` passes section-budget | met | 12/12 files pass |
| AC7 — CHANGELOG updated under `[Unreleased]` with correct anchor | met | grep confirmed |
| AC8a — T26 spec `**Status:**` → `✅ Done` | met | Status line updated |
| AC8b — M21 README row 76 description replaced with locked file shape + status → Done | met | `iter_<N>_*` phrasing replaced; status set to Done |
| AC8c — M21 README §G5 satisfaction parenthetical added | met | `(satisfied at T26; pattern locked, agent_docs/ created)` added |
| TA-LOW-01 — H3s promoted to H2s in `long_running_pattern.md` | met | All six sections are `##` headings |
| TA-LOW-02 — Unescaped backticks in Edit old_string/new_string | met | Builder used unescaped backticks |
| TA-LOW-03 — Schema-purity bullet copied verbatim | met | Exact text from spec step 3 used in `builder.md` Hard rules |

## Additions beyond spec — audited and justified

None. All edits are strictly scoped to the spec deliverables.

## Gate summary

| Gate | Command | Result |
|---|---|---|
| pytest | `uv run pytest -q` | PASS (1304 passed, 1 pre-existing branch-shape failure unrelated to T26) |
| lint-imports | `uv run lint-imports` | PASS (5 contracts kept, 0 broken) |
| ruff | `uv run ruff check` | PASS (all checks passed) |
| smoke-1 | `test -d agent_docs && test -f agent_docs/long_running_pattern.md` | PASS |
| smoke-2 | T24 rubric: summary / section-budget / code-block-len on `agent_docs/` | PASS |
| smoke-3 | `grep -qE '^## Two-prompt long-running pattern'` auto-implement.md | PASS |
| smoke-4 | T26 semantic patterns in builder / auditor / auto-implement | PASS |
| smoke-5 | T10 invariant 9/9 | PASS |
| smoke-6 | T24 invariant on `.claude/agents/` | PASS (12/12) |
| smoke-7 | CHANGELOG anchor | PASS |

## Issue log — cross-task follow-up

None.

## Deferred to nice_to_have

None.

## Propagation status

No forward-deferrals from this task. All ACs and carry-over items satisfied in cycle 1.

## Sr. SDET review (2026-04-29)

**Test files reviewed:** No pytest files touched by T26 (doc-only task). Smoke surface: `agent_docs/long_running_pattern.md`, `.claude/commands/auto-implement.md`, `.claude/agents/builder.md`, `.claude/agents/auditor.md`, M21 README, CHANGELOG.md — verified via grep/read as described in the spec smoke steps.
**Skipped (out of scope):** All `tests/` pytest files — no runtime code changed.
**Verdict:** SHIP

### BLOCK — tests pass for the wrong reason

None. T26 is doc-only; the "tests" are spec-mandated grep + file-existence smoke checks. Every smoke check verifies a concrete, falsifiable property (file path exists, regex matches a real line, rubric script exits 0). No tautological assertions, no mock-driven stubs, no trivially-true checks.

### FIX — fix-then-ship

None identified.

### Advisory — track but not blocking

**A1 — Lens 2 (coverage gap): progress.md append path has no negative smoke test.**
The Phase-5b extension in `auditor.md` (lines 145-150) fires only when `runs/<task>/progress.md` exists. The smoke checks (step 4) confirm the text is present in `auditor.md` but do not exercise the "file absent — skip append" branch. For a doc-only task this is acceptable; if a future Builder task adds a regression test for the Auditor Phase-5b path, the absent-file guard should be covered there. Track as carry-over for whichever task first exercises the T26 trigger live.

**A2 — Lens 6 (naming): `auto-implement.md` trigger-override prose sits at line 147-150 inside the existing `### Builder spawn — read-only-latest-summary rule` section, not inside the new `## Two-prompt long-running pattern (T26)` section (line 283).** The spec required a one-line cross-link plus the trigger override appended to the existing rule — which is exactly what was done — but a future reader may miss the override because it is separated from the canonical section by ~133 lines. Advisory only; the spec explicitly chose this placement. Flag for T17/T18 if the pattern fires live and the two-location shape causes confusion.

### What passed review (one-line per lens)

- Tests-pass-for-wrong-reason: none observed; all smoke assertions are falsifiable property checks, not tautologies.
- Coverage gaps: Phase-5b absent-file branch unexercised (Advisory A1; acceptable for doc-only task).
- Mock overuse: not applicable — no pytest mocks; smoke uses grep + file-existence + audit script.
- Fixture / independence: not applicable — no pytest fixtures introduced.
- Hermetic-vs-E2E gating: not applicable — no network calls; all checks are filesystem + grep.
- Naming / assertion-message hygiene: two-location placement of T26 override prose noted as Advisory A2; no blocking issue.

## Terminal gate — cycle 1 verdict + locked terminal decisions (2026-04-29)

**Reviewer verdicts:** sr-dev = FIX-THEN-SHIP (FIX-1), sr-sdet = SHIP, security-reviewer = SHIP. Auditor-agreement bypass applies — single clear recommendation, no scope expansion, no KDR conflict, no deferral to nonexistent task.

### Locked terminal decision 1 (sr-dev FIX-1) — N≥3 trigger arm unreachable as written

The §Trigger check section in `auto-implement.md` lives inside `## Project setup` which runs once at cycle 1. The N≥3 trigger arm needs cycle-start re-evaluation but the functional loop never re-checks it.

**Resolution for cycle 2:** In `auto-implement.md` §Functional loop procedure Step 1 (around line 338), add a trigger re-check note: "If the T26 long-running trigger was not already on at cycle 1, re-evaluate it now: if N >= 3 and `runs/<task>/plan.md` does not yet exist, run the initializer step inline before spawning the Builder."

### Bundled cycle-2 fixes (sr-dev ADV-1, ADV-2) — applied alongside FIX-1

- **ADV-1** — "one-shot at cycle 1" wording in `auto-implement.md:296` and `agent_docs/long_running_pattern.md:49` now says "first trigger fire (cycle 1 for opt-in tasks; cycle 3 for auto-trigger)" to match the FIX-1 resolution.
- **ADV-2** — Add to `auto-implement.md` §Auditor spawn — read-only-latest-summary rule (after the existing rule body): "No T26 override for the Auditor spawn — the Auditor continues to receive standard inputs regardless of the T26 trigger state."

These three feed forward to Builder cycle 2 as the only carry-over ACs.

## Cycle 2 — terminal-gate locked-decision verification (2026-04-29)

### Cycle 2 AC grading (carry-over from cycle 1 terminal gate)

| Cycle-2 AC | Status | Verification |
|---|---|---|
| **FIX-1** — `auto-implement.md` §Functional loop procedure Step 1 trigger re-check note | met | Lines 340-343: "**T26 trigger re-check (every cycle):** If the T26 long-running trigger was not already on at cycle 1, re-evaluate it now: if N >= 3 and `runs/<task>/plan.md` does not yet exist, run the initializer step inline before spawning the Builder…". Lands inside `### Step 1 — Builder` of `For cycles 1..10:` loop, exactly where the locked decision specified. |
| **ADV-1a** — `auto-implement.md` initializer-step "first trigger fire" wording | met | Line 299: `### Initializer step (one-shot at first trigger fire — cycle 1 for opt-in tasks; cycle 3 for auto-trigger)`. Note: cycle-1 summary referenced `auto-implement.md:296` but the only matching wording was the heading at line 299; correct location updated. |
| **ADV-1b** — `agent_docs/long_running_pattern.md` "first trigger fire" wording | met | Line 57: `This is a one-shot at first trigger fire (cycle 1 for opt-in tasks; cycle 3 for auto-trigger), inline orchestrator step — not a separate agent spawn.` |
| **ADV-2** — `auto-implement.md` Auditor-spawn no-T26-override note | met | Lines 189-190: `**No T26 override for the Auditor spawn** — the Auditor continues to receive standard inputs regardless of the T26 trigger state.` Appended after the `### Auditor spawn — read-only-latest-summary rule` body, exact text from locked decision. |

### Cycle 2 scope-leak boundary

Files touched in cycle 2 (vs. cycle 1's working-tree state): `.claude/commands/auto-implement.md` (3 edits), `agent_docs/long_running_pattern.md` (1 edit), `CHANGELOG.md` (cycle-2 amplification entry). No edits to `.claude/agents/builder.md`, `.claude/agents/auditor.md`, M21 README, or task spec — those carry only cycle-1 changes. No `ai_workflows/` runtime code changed. No new dependencies. No KDR violations. No design drift.

### Cycle 2 gate re-run

| Gate | Command | Result |
|---|---|---|
| pytest | `AIW_BRANCH=design uv run pytest -q` | PASS (1309 passed, 7 skipped, 22 warnings) |
| lint-imports | `uv run lint-imports` | PASS (5 contracts kept, 0 broken) |
| ruff | `uv run ruff check` | PASS (all checks passed) |
| smoke-1 | `test -d agent_docs && test -f agent_docs/long_running_pattern.md` | PASS |
| smoke-2 | T24 rubric (summary / section-budget / code-block-len on agent_docs/) | PASS (1/1 each) |
| smoke-3 | `grep -qE '^## Two-prompt long-running pattern \(T26\)'` auto-implement.md | PASS |
| smoke-4 | T26 semantic patterns in builder / auditor / auto-implement | PASS (all three) |
| smoke-5 | T10 invariant 9/9 (`_common/non_negotiables.md` references) | PASS |
| smoke-6 | T24 invariant on `.claude/agents/` (section-budget) | PASS (12/12) |
| smoke-7 | CHANGELOG anchor (`### (Added|Changed) — M21 Task 26:`) | PASS |

### Status-surface check

All four surfaces aligned: (a) spec `**Status:**` = `✅ Done`, (b) M21 README row 76 status column = `✅ Done` with description matching locked file shape, (c) M21 README §G5 prose carries satisfaction parenthetical `(satisfied at T26; pattern locked, agent_docs/ created)`, (d) no `tasks/README.md` exists in M21.

### HIGH / MEDIUM / LOW (cycle 2)

None. Cycle 2 lands the three cycle-1 locked decisions verbatim with no scope leak, no drift, all gates green, all status surfaces aligned.

### Terminal gate — cycle 2 verdict

Auditor cycle 2 = PASS. Cycle-1 FIX-1 + ADV-1 + ADV-2 all landed. Stop condition (cycle-1 summary) met: re-run unified terminal gate expected to return TERMINAL CLEAN (3 SHIP).

## Security review (2026-04-29)

Scope: cycle-2 changes only — `.claude/commands/auto-implement.md` (3 edits, procedural prose) and `agent_docs/long_running_pattern.md` (1 edit, procedural prose). No `ai_workflows/` runtime code touched. No wheel contents changed. No subprocess invocations added or modified. No dependency manifest touched.

Threat-model items checked:

1. **Wheel contents** — no change to `pyproject.toml`, `MANIFEST.in`, or any `ai_workflows/` module. The wheel boundary is unchanged. Not applicable.
2. **OAuth subprocess integrity (KDR-003)** — no subprocess spawn paths added or modified. Not applicable.
3. **External workflow load path (KDR-013)** — no loader changes. Not applicable.
4. **MCP HTTP transport bind address** — no MCP surface changes. Not applicable.
5. **SQLite paths** — no storage changes. Not applicable.
6. **Subprocess CWD / env leakage** — no subprocess invocations added. Not applicable.
7. **Logging hygiene** — no logging changes. Not applicable.
8. **Dependency CVEs** — no manifest changes; dependency-auditor gate not triggered.

Cycle-2 diff is three doc-only prose insertions into orchestrator-procedure files. No new secrets surface, no new subprocess pattern, no new file path construction, no new I/O. All threat-model items are not applicable for this changeset.

### Critical — must fix before publish/ship

None.

### High — should fix before publish/ship

None.

### Advisory — track; not blocking

None.

### Verdict: SHIP
