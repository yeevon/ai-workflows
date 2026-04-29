# Task 16 — `/sweep` ad-hoc reviewer Skill — Audit Issues

**Source task:** [../task_16_sweep_command.md](../task_16_sweep_command.md)
**Audited on:** 2026-04-29
**Audit scope:** AC1–AC9 smoke (frontmatter, body budget, four anchors, T24 rubric, T25 efficiency, T10/T24 invariants, pytest, status surfaces, CHANGELOG, skills_pattern Live-Skills line). KDR drift surface (doc-only Skill — no source code touched).
**Status:** ✅ PASS

## Design-drift check

No drift detected. Doc-only Skill: no source code modified, no dependency changes, no provider / LLM-call wiring, no checkpoint or retry surface touched. KDR-002/003/004/006/008/009/013 all non-applicable to this delta. Threat-model boundary intact (no new external surface; `/sweep` is operator-invoked, runs locally against `git diff`).

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| 1. SKILL.md frontmatter + body ≤5K + four anchors | ✅ | name=sweep, description=172 chars (≤200), allowed-tools=Bash. Inputs/Procedure/Outputs/Return schema all present. Word-count * 1.3 well under 5K. |
| 2. runbook.md T24-rubric conformant | ✅ | summary / section-budget / code-block-len all OK on `.claude/skills/sweep/`. |
| 3. T25 skills_efficiency clean | ✅ | `OK: all — all 9 skill file(s) pass`. |
| 4. T10 invariant 9/9 | ✅ | All nine agents reference `_common/non_negotiables.md`. |
| 5. T24 invariant on agents/ | ✅ | `OK: section-budget — all 12 file(s) pass`. |
| 6. tests/test_t16_sweep.py passes | ✅ | 7 passed in 0.34s (one extra test split out — exists + fields — exceeds the spec's "6 cases"; harmless). |
| 7. skills_pattern.md Live Skills lists sweep | ✅ | `Live Skills: ai-workflows (legacy), dep-audit (T12), triage (T13), check (T14), sweep (T16).` — single-line extension preserved per Step 5. |
| 8. CHANGELOG anchor `### Added — M21 Task 16:` | ✅ | Line 10: `### Added — M21 Task 16: /sweep ad-hoc reviewer Skill (2026-04-29)`. |
| 9. Status surfaces flip together | ✅ | (a) spec line 3: `**Status:** ✅ Done.`; (b) README task-pool row line 85: `✅ Done`; (c) §G3 prose line 39: `(satisfied at T13 with /triage; T14 adds /check; T16 adds /sweep; T15 separate)`. No `tasks/README.md` for M21. No "Done when" checkbox tied to T16 specifically beyond §G3 (already updated). |

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

### LOW-01 — Test count: 7 functions vs spec "6 cases"

Spec Step 3 says "6 cases (frontmatter parse + char/token budgets + four required anchors + helper-file ref + runbook T24-rubric subprocess)". Implementation has 7 `test_*` functions: frontmatter was split into `test_skill_md_exists` + `test_skill_md_frontmatter_fields`, and a `test_skills_pattern_and_changelog` covers AC7+AC8 jointly. All AC coverage is satisfied; the split is a clarity improvement, not a defect.

**Action / Recommendation:** No change required. Flag-only.

## Additions beyond spec — audited and justified

- The test splits frontmatter checks into existence + fields (LOW-01). Justified — improves diagnostic clarity on failure.
- `## Helper files` anchor in SKILL.md beyond the four required `##` anchors. Justified — the spec body example included `## Helper files` (line 78–80 of the spec); implementation matches.

## Gate summary

| Gate | Command | Result |
| ---- | ------- | ------ |
| pytest (full) | `AIW_BRANCH=design uv run pytest -q` | 1373 passed, 7 skipped |
| lint-imports | `uv run lint-imports` | 5 contracts kept, 0 broken |
| ruff | `uv run ruff check` | All checks passed |
| T16 unit | `uv run pytest tests/test_t16_sweep.py -q` | 7 passed |
| T24 sweep/ | `md_discoverability.py --check {summary,section-budget,code-block-len} --target .claude/skills/sweep/` | all pass |
| T25 skills | `skills_efficiency.py --check all --target .claude/skills/` | all 9 skill files pass |
| T24 agents/ | `md_discoverability.py --check section-budget --target .claude/agents/` | all 12 files pass |
| T10 invariant | grep + wc on 9 agent files for `_common/non_negotiables.md` | 9/9 |
| CHANGELOG anchor | `grep -E '^### (Added|Changed) — M21 Task 16:' CHANGELOG.md` | matched |
| Live Skills line | `grep -E '^Live Skills:.*sweep' .claude/agents/_common/skills_pattern.md` | matched |

## Issue log

None — clean cycle.

## Deferred to nice_to_have

None.

## Propagation status

No forward-deferrals required. Cycle 1 PASS.

## Sr. SDET review (2026-04-29)

**Test files reviewed:** `tests/test_t16_sweep.py`
**Skipped (out of scope):** `tests/test_t13_triage.py`, `tests/test_t14_check.py`, `tests/test_t24_md_discoverability.py` (referenced for cross-file context only)
**Verdict:** SHIP

### BLOCK — tests pass for the wrong reason

None.

### FIX — fix-then-ship

None.

### Advisory — track but not blocking

**ADV-01 — AC5 claim in module docstring has no backing test function** (`tests/test_t16_sweep.py:9`)

The module docstring at line 9 states "AC5: T24 invariant held on `.claude/agents/`" — implying `test_t16_sweep.py` verifies this. No test function in the file calls `md_discoverability.py --check section-budget --target .claude/agents/`. AC5 is in fact enforced by `tests/test_t24_md_discoverability.py:test_rule3_section_budget_passes` (out of scope), so regression protection exists in the full suite.

Impact: on a fresh run of `pytest tests/test_t16_sweep.py` in isolation, AC5 is silently unverified. The misleading docstring could cause a future maintainer to believe the invariant is pinned here when it is not.

Recommendation: either add `def test_t24_agents_section_budget()` that calls `_run_discoverability("section-budget", target=AGENTS_DIR)`, or remove AC5 from the module-level docstring and add a comment pointing to `test_t24_md_discoverability.py`.

**ADV-02 — Over-bundled test assertions reduce failure isolation** (`tests/test_t16_sweep.py:131-142`)

`test_skill_md_body_token_budget_and_anchors` (line 131) combines six independent assertions: token budget, four `##` anchors, and runbook reference. The T13/T14 mirror pattern splits each anchor into its own function (T14: `test_skill_md_anchor_inputs`, `test_skill_md_anchor_procedure`, etc.). On a failure of this test, the pytest output names the function but the relevant assertion is buried inside a loop; developers must read the traceback to determine which anchor was missing.

Recommendation: split into `test_skill_md_token_budget`, `test_skill_md_required_anchors` (or four individual anchor tests), and `test_skill_md_references_runbook` to match the T13/T14 neighbour pattern.

**ADV-03 — `test_skills_pattern_and_changelog` bundles two separate ACs** (`tests/test_t16_sweep.py:215-229`)

`test_skills_pattern_and_changelog` covers AC7 (Live Skills line) and AC8 (CHANGELOG) in a single function. T13/T14 split these into `test_skills_pattern_md_<skill>_in_live_skills_line` and `test_changelog_t1N_entry`. On failure, the single bundled function name (`test_skills_pattern_and_changelog`) gives no hint which of the two ACs broke.

Recommendation: split into `test_skills_pattern_md_sweep_in_live_skills_line` and `test_changelog_t16_entry` to mirror T13/T14 idiom and improve failure isolation.

### What passed review (one-line per lens)

- Tests-pass-for-wrong-reason: none observed — all assertions are substantive and verified against live files.
- Coverage gaps: AC5 module-docstring claim is unverified in-file (ADV-01); covered by out-of-scope test_t24 in full suite.
- Mock overuse: no mocks present — tests read filesystem and invoke subprocess against real scripts; appropriate for a doc-only Skill.
- Fixture / independence: no fixtures used; all tests are stateless reads against repo filesystem; no order dependence or bleed.
- Hermetic-vs-E2E gating: no network calls; no skip gates needed; fully hermetic.
- Naming / assertion-message hygiene: bundling in two test functions reduces failure isolation (ADV-02, ADV-03); no `# TODO` or bare skip markers found.

## Sr. Dev review (2026-04-29)

**Files reviewed:** `.claude/skills/sweep/SKILL.md`, `.claude/skills/sweep/runbook.md`, `tests/test_t16_sweep.py`, `.claude/agents/_common/skills_pattern.md`, `CHANGELOG.md`
**Skipped (out of scope):** none
**Verdict:** SHIP

### BLOCK — must-fix before commit

None.

### FIX — fix-then-ship

None.

### Advisory — track but not blocking

**ADV-01 — Idiom drift: bare `_common/` path reference** (`SKILL.md:38`)

`SKILL.md` line 38 cites `_common/parallel_spawn_pattern.md` without a leading `.claude/commands/` qualifier. Line 53 of the same file and both sibling Skills (T13 `triage/SKILL.md`, T14 `check/SKILL.md`) consistently use the fully-qualified `.claude/commands/_common/` prefix for cross-file prose references. The bare path is unambiguous to a human reader but drifts from the established codebase idiom.

Recommendation: change `_common/parallel_spawn_pattern.md` to `.claude/commands/_common/parallel_spawn_pattern.md` to match the neighbour pattern.

### What passed review (one-line per lens)

- Hidden bugs: none observed — doc-only delta; no executable code paths introduced.
- Defensive-code creep: none — Skill body and test file contain no defensive guards against non-existent scenarios.
- Idiom alignment: one advisory path inconsistency (ADV-01); all other references, return-schema shape, and `skills_pattern.md` extension match T13/T14 neighbours exactly.
- Premature abstraction: none — no new helper classes or base types introduced.
- Comment / docstring drift: clean — module docstring cites task and relationship; inline comments absent (none needed); no restatement comments.
- Simplification: none needed — test helpers are appropriately factored; no simplification opportunity identified.
