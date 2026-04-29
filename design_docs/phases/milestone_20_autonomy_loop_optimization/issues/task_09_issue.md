# Task 09 — Task-integrity safeguards — Audit Issues

**Source task:** [../task_09_task_integrity_safeguards.md](../task_09_task_integrity_safeguards.md)
**Audited on:** 2026-04-28
**Audit scope:** Cycle 1. Loaded the spec, milestone README, parent README, the new
  `_common/integrity_checks.md`, the updated `auto-implement.md` Pre-commit-ceremony +
  per-cycle directory layout sections, the new `tests/orchestrator/test_integrity_checks.py`,
  the T08 `parse_gate_output` it imports from `tests/orchestrator/test_gate_output_capture.py`,
  the T08 `gate_parse_patterns.md` reference, the CHANGELOG entry under `[Unreleased]`,
  and the four status surfaces (spec line / milestone README task table / milestone README
  G5 #10 / Phase D row). Re-ran all three gates from scratch.
**Status:** ✅ PASS

## Design-drift check

T09 is orchestration-infrastructure only. **Zero `ai_workflows/` package code changed**
(verified: all touched files are under `.claude/commands/`, `tests/orchestrator/`,
`design_docs/`, `CHANGELOG.md`). Therefore none of the seven load-bearing KDRs are
exercised by this change:

- KDR-002 / 008 (MCP surface, FastMCP) — no surface change.
- KDR-003 (no Anthropic API) — no LLM call added; no `anthropic` SDK import; no
  `ANTHROPIC_API_KEY` read.
- KDR-004 (ValidatorNode pairing) — no `TieredNode` added.
- KDR-006 (RetryingEdge taxonomy) — no retry logic added.
- KDR-009 (SqliteSaver checkpoints) — no checkpoint write.
- KDR-013 (user-owned external workflow code) — no workflow loader change.

Four-layer rule (`primitives → graph → workflows → surfaces`) untouched; `lint-imports`
returns 5 contracts kept, 0 broken (re-run from scratch — see Gate summary below).

**No drift detected.**

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| 1 — `auto-implement.md` describes pre-commit ceremony with three checks | ✅ Met | Lines 475-531 in the updated `auto-implement.md`. New `## Pre-commit ceremony` section names all three checks (Check 1 / Check 2 / Check 3), each with command, assertion, and canonical halt message. Inline pre-task-commit capture at lines 202-204 + per-cycle directory layout entry at line 74 close the loop. |
| 2 — `_common/integrity_checks.md` exists | ✅ Met | New file at `.claude/commands/_common/integrity_checks.md`, 156 lines, canonical SOT for the three checks + their failure-mode signatures + relationship-to-T08 table. |
| 3 — Halt surfaces the specific failed check | ✅ Met | `build_integrity_blocked_message` produces exactly `🚧 BLOCKED: task-integrity check <N> (<label>) failed; see runs/<task>/integrity.txt` for each check. Verified by `test_blocked_message_check{1,2,3}`. The orchestrator-prose halt strings in `auto-implement.md` lines 497, 513, 528 use the same canonical format. |
| 4 — `tests/orchestrator/test_integrity_checks.py` passes | ✅ Met | 34 tests, all PASSED (re-run from scratch — see Gate summary). Covers all five spec-named cases plus 4 extra-tightness assertions (case-insensitive kind matching, short-circuit ordering on Check 1 → Check 2, T08 fail-closed exit-code path, doc + analysis bypass). |
| 5 — CHANGELOG entry under `[Unreleased]` | ✅ Met | Line 10: `### Added — M20 Task 09: Task-integrity safeguards (non-empty diff + non-empty test diff for code tasks + independent pre-stamp gate re-run; uses T08 gate_parse_patterns.md) (2026-04-28)`. |
| 6 — Status surfaces flip together | ✅ Met | (a) Spec line 3: `**Status:** ✅ Done.` (b) Milestone README task table row line 132: `✅ Done`. (c) `tasks/README.md` — milestone has no `tasks/README.md` (verified by absence). (d) Milestone README G5 exit-criterion #10 line 59: `**[T09 Done — 2026-04-28]**`. All four surfaces aligned. |

## 🔴 HIGH

(none)

## 🟡 MEDIUM

(none)

## 🟢 LOW

### LOW-1 — Builder cycle 1 return-schema non-conformance (recurrence #9 overall, #1 in this task)

**Where:** `runs/m20_t09/cycle_1/agent_builder_raw_return.txt` (10 lines; expected 3).

**What:** Builder cycle 1 prepended a "Planned commit message" block + "Only the
expected pre-existing failure. All gates green." prose before the 3-line schema. Per
loop-controller observation, this is the 9th occurrence of the documented pattern
(M20 T01–T05, T08, T21, T22, T28 issues all carry the same DEFERRED-LOW). The next
cycle's loop-controller still parses the trailing 3-line block correctly, so this is
non-blocking; it's a prompt-hardening item for M21.

**Action / Recommendation:** Forward-defer to M21 agent-prompt-hardening track —
already tracked under M20 T06 issue file Carry-over §C4. No additional propagation
needed for this task; do not file a duplicate carry-over against an M21 task that
doesn't exist yet (per `nice_to_have.md` boundary rule against deferring to
nonexistent owners).

**Status:** DEFERRED (owner: M21 agent-prompt-hardening, when that task lands).

## Additions beyond spec — audited and justified

1. **Extra unit-coverage class `TestIndividualChecks`.** The spec names five test cases;
   the Builder added an additional 6 fine-grained unit tests for each `_checkN_*`
   helper. Justified — exercising each check function in isolation makes failure
   diagnosis cheaper and aligns with the spec's intent ("each check has a distinct
   failure-mode signature so the halt message names the specific check that fired").
   No coupling cost.

2. **Extra short-circuit-ordering tests.** `test_check1_short_circuits_before_check2`
   and `test_check2_short_circuits_before_check3` verify that the first failing check
   wins. Justified — the spec mandates "Each check is independent; the first failure
   halts immediately without running the remaining checks" (auto-implement.md L481), so
   short-circuit semantics are a load-bearing invariant, not an extension.

3. **`build_integrity_blocked_message` helper.** Not strictly required by the spec but
   produces the canonical halt message in one place — single source of truth for the
   format. Justified.

4. **`_common/integrity_checks.md` §Relationship to other checks table.** Adds a
   one-row-per-layer table mapping T01 / T08 / T09 to the layer they catch. Justified —
   the spec's "T09's check (3) reuses T08's `gate_parse_patterns.md`" sentence is
   surfaced here as a navigable diagram for future readers.

## Reuse-check (DRY)

Cycle-1 review item #5 from the loop-controller asks whether the Builder duplicated
T08's pytest-footer regex inside Check 3.

**Verified clean.** `tests/orchestrator/test_integrity_checks.py` line 36 imports
`parse_gate_output` from `tests/orchestrator/test_gate_output_capture.py`. Check 3
(`_check3_pytest_rerun`, lines 115-135) calls `parse_gate_output("pytest", ...)`
directly — no regex duplicated, no copy-paste of the T08 footer pattern. The module
docstring (lines 12-15) calls this out explicitly: "Reuses `parse_gate_output` from
the T08 module ... to avoid duplicating the pytest-footer regex." Single source of
truth honoured.

## Task-kind parsing-check

Cycle-1 review item #6 from the loop-controller asks whether the integrity-check logic
parses the spec's `**Kind:**` line or hardcodes "all tasks must have test diff".

**Verified clean.** `_check2_nonempty_test_diff` (lines 85-112) takes a `task_kind`
string parameter and matches `"code" not in task_kind.lower()` — case-insensitive
substring match against the value of the spec's `**Kind:**` line. Tested for:
- `"Compaction / doc"` → bypassed (no halt) ✓
- `"Model-tier / analysis"` → bypassed ✓
- `"Closeout / doc + analysis"` → bypassed ✓
- `"Safeguards / code"`, `"doc + code"`, `"Model-tier / Code"` → enforced ✓

Auto-implement.md §Pre-commit ceremony Check 2 (lines 502-516) and integrity_checks.md
§Check 2 (lines 37-69) both document the parsing rule: "parse the spec's `**Kind:**`
line in the Status block (present on every M20 spec per the `Kind:` convention). The
value is a slash-separated list of categories ... Check 2 fires only when any category
contains the word `code`. If the `**Kind:**` line is absent ... fall back to the
milestone README's task-pool 'Phase / Kind' column." No hardcoding; doc-only and
analysis-only tasks correctly bypass.

## Gate summary

| Gate | Command | Result |
| --- | --- | --- |
| pytest (T09 scope) | `uv run pytest tests/orchestrator/test_integrity_checks.py -v` | PASS — 34 passed in 0.05s |
| pytest (full) | `uv run pytest -q` | PASS for T09 — 1174 passed, 1 failed, 10 skipped, 22 warnings. The 1 failure is `tests/test_main_branch_shape.py::test_design_docs_absence_on_main`, which is a pre-existing main-branch-shape test infrastructure quirk (skipif gates on literal branch name `"design"` not `"workflow_optimization"` / `"design_branch"`) — unrelated to T09 and present in every M20 cycle audit since the branch was created. Treat as expected pre-existing failure. |
| lint-imports | `uv run lint-imports` | PASS — Contracts: 5 kept, 0 broken |
| ruff | `uv run ruff check` | PASS — All checks passed |
| Smoke (per spec §Smoke test) | `test -f .claude/commands/_common/integrity_checks.md && grep -q "pre-commit ceremony\|task-integrity\|integrity_checks.md" .claude/commands/auto-implement.md && uv run pytest tests/orchestrator/test_integrity_checks.py -v` | PASS — file exists, auto-implement references the ceremony, 34/34 tests green |

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch | Status |
| --- | --- | --- | --- |
| M20-T09-ISS-01 | LOW | M21 agent-prompt-hardening track | DEFERRED (recurrence of M20 T06 issue file Carry-over §C4) |

## Deferred to nice_to_have

(none — LOW-1 is tracked against an existing follow-up thread, not a `nice_to_have.md`
item)

## Propagation status

No new forward-deferrals from this audit. The single LOW (return-schema non-conformance
recurrence) consolidates onto the existing M20 T06 issue file §C4 carry-over thread for
the M21 agent-prompt-hardening work, which has no per-task spec yet — propagation will
land when M21's prompt-hardening task spec is generated.

---

## Sr. Dev review (2026-04-28)

**Verdict:** SHIP. **BLOCK:** none. **FIX:** none. **Advisory:** none.

DRY check: integrity-check logic correctly imports and reuses T08's `parse_gate_output` for the pytest-footer parsing inside check 3 — single source of truth honored. Task-kind parsing is real (parses the spec's `**Kind:**` line; falls back to README task-pool Kind column); doc-only / analysis-only tasks correctly bypass the test-diff check. No defensive-code creep, no premature abstraction. Idiom-aligned with T08's test-module pattern.

---

## Sr. SDET review (2026-04-28)

**Verdict:** SHIP. **BLOCK:** none. **FIX:** none. **Advisory:** none.

All 5 spec-named cases covered:
1. Empty diff → `blocked=True`, reason names "empty diff".
2. Code-task non-empty prod diff + empty test diff → `blocked=True`, reason names "empty test diff for code task".
3. Code-task all-non-empty diffs + failing pytest footer → `blocked=True`, reason names "pytest failure".
4. Doc-only task with empty test diff → `blocked=False` (test-diff bypass).
5. All checks pass → `blocked=False`.

No tautological assertions, no short-circuit masking. Tests are hermetic — `git diff` output is fixtured, not invoked in-process. Reuses T08's `parse_gate_output` cleanly for the pytest-footer assertion in case 3.

---

## Security review (2026-04-28)

**Verdict:** SHIP. **Critical:** none. **High:** none. **Advisory:** none new.

No `shell=True`, no `ANTHROPIC_API_KEY` / `anthropic` SDK access (KDR-003 boundary intact). Tests hermetic — fixtured `git diff` output, no in-process git invocation. The orchestrator's `git diff --stat` invocation is markdown-described (executed by the Bash tool from the orchestrator, not Python code under `ai_workflows/`). Wheel-contents posture unchanged.

---

## Terminal-gate verdict (cycle 1)

**TERMINAL CLEAN** — sr-dev: SHIP / sr-sdet: SHIP / security: SHIP. Dependency audit skipped (no `pyproject.toml` / `uv.lock` changes). Architect not invoked. Proceeding to commit ceremony.
