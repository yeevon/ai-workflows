# Task 14 — `/check` on-disk vs pushed-state Skill — Audit Issues

**Source task:** [../task_14_check_command.md](../task_14_check_command.md)
**Audited on:** 2026-04-29
**Audit scope:** Cycle 1 — full re-verification of AC1–AC9 + 11 smoke commands + KDR drift + four-surface status discipline + TA-LOW-01/02 absorption + T10/T24/T25 invariants. Builder reported BUILT (uncommitted working tree).
**Status:** ✅ PASS

## Design-drift check

No drift detected. T14 is a doc-only Skill (frontmatter `allowed-tools: Bash`). No imports, no `pyproject.toml` change, no LLM call, no Anthropic SDK reference, no `pydantic_ai`, no checkpoint/retry/observability surface touched. Layered import discipline (`uv run lint-imports` → 5 kept / 0 broken) holds. KDR-002/003/004/006/008/009/013 all unaffected. M21 scope note ("KDR drift checks only") satisfied.

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| 1 — SKILL.md exists, valid frontmatter, body ≤ 5K tokens, four `##` anchors | ✅ | name=`check`, description=196 chars (≤200), `allowed-tools: Bash`. Body 484 words ≈ 629 tokens. All four anchors present. |
| 2 — runbook.md exists; T24-rubric clean | ✅ | Both files pass `summary` / `section-budget` / `code-block-len --max 20`. |
| 3 — T25 skills_efficiency clean | ✅ | `--check all` → all 7 skill files pass. |
| 4 — T10 invariant 9/9 | ✅ | All nine agents reference `_common/non_negotiables.md`. |
| 5 — T24 invariant on `.claude/agents/` | ✅ | `section-budget` → all 12 agent files pass. |
| 6 — `tests/test_t14_check.py` passes | ✅ | 19 tests pass in 0.34s (spec asked for 6 cases; Builder split into 19 atomic tests — additive, conformant). |
| 7 — `_common/skills_pattern.md` Live Skills includes `check` | ✅ | Line 24: `Live Skills: ai-workflows (legacy), dep-audit (T12), triage (T13), check (T14).` Single line — TA-LOW-01 honoured. |
| 8 — CHANGELOG.md `### Added — M21 Task 14:` anchor | ✅ | Line 10 of CHANGELOG. |
| 9 — Status surfaces flip together (a/b/c) | ✅ | (a) spec L3 → ✅ Done; (b) README L83 task-pool row → ✅ Done; (c) §G3 prose L39 extended with `T14 adds /check`. |

### Carry-over from task analysis

| Item | Status | Notes |
| ---- | ------ | ----- |
| TA-LOW-01 — extend Live Skills line, no second line | ✅ | Single line at `_common/skills_pattern.md:24`. |
| TA-LOW-02 — `allowed-tools: Bash` rationale note | ✅ | One-line note added at SKILL.md L12-13. |

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

None.

## Additions beyond spec — audited and justified

- **Test count expansion** — spec asked for 6 cases; Builder shipped 19 atomic tests. Additive only (each spec case decomposed into focused asserts; no scope creep). Coverage strictly improves. No action.

## Gate summary

| Gate | Command | Result |
| ---- | ------- | ------ |
| pytest (target) | `uv run pytest tests/test_t14_check.py -q` | 19 passed |
| pytest (full) | `AIW_BRANCH=design uv run pytest -q` | 1362 passed, 10 skipped, 22 warnings — clean |
| lint-imports | `uv run lint-imports` | 5 kept, 0 broken |
| ruff | `uv run ruff check` | All checks passed |
| Smoke 1 (files + frontmatter) | grep / test invocations | PASS |
| Smoke 2 (description ≤ 200) | awk substr length | PASS (196 chars) |
| Smoke 3 (body ≤ 5K tokens) | awk word*1.3 | PASS (~629) |
| Smoke 4 (T24 rubric on check/) | md_discoverability summary/section-budget/code-block-len | PASS |
| Smoke 5 (four anchors) | grep `^## ...` | PASS |
| Smoke 6 (T25 skills_efficiency all) | skills_efficiency.py | PASS (7 skill files) |
| Smoke 7 (T10 9/9) | grep -lF `_common/non_negotiables.md` | PASS (9 files) |
| Smoke 8 (T24 agents/) | md_discoverability section-budget | PASS (12 files) |
| Smoke 9 (T14 tests) | pytest test_t14_check | PASS (19) |
| Smoke 10 (CHANGELOG anchor) | grep `### Added — M21 Task 14:` | PASS |
| Smoke 11 (Live Skills line) | grep `^Live Skills:.*check` | PASS |

## Issue log — cross-task follow-up

None.

## Deferred to nice_to_have

None.

## Propagation status

No forward-deferrals — clean cycle 1, no carry-over to push.

## Note on commit boundary

Working tree is unstaged at audit time (Builder did not commit). Per autonomous-mode boundary, the orchestrator (or operator under `/auto-implement`) owns commit + push to `design_branch`. Audit verifies in-place state; commit responsibility is outside this artifact.

## Sr. Dev review (2026-04-29)

**Files reviewed:** `.claude/skills/check/SKILL.md`, `.claude/skills/check/runbook.md`, `tests/test_t14_check.py`, `.claude/agents/_common/skills_pattern.md`, `design_docs/phases/milestone_21_autonomy_loop_continuation/task_14_check_command.md`, `design_docs/phases/milestone_21_autonomy_loop_continuation/README.md`, `CHANGELOG.md`
**Skipped (out of scope):** none
**Verdict:** SHIP

### BLOCK — must-fix before commit

None.

### FIX — fix-then-ship

None.

### Advisory — track but not blocking

**A1 — Comment/docstring drift: module docstring claims AC4 and AC5 coverage that does not exist.**
`tests/test_t14_check.py:8-9` — the module docstring lists `AC4: T10 invariant (9/9 agents...)` and `AC5: T24 invariant held on .claude/agents/` as covered by this file. No test functions implement either. T13's parallel test (`tests/test_t13_triage.py:1-16`) correctly omits AC4/AC5 from its docstring. The tests for the T10 and T24 invariants live in `tests/test_t25_skills_efficiency.py` or equivalent and are exercised by the full pytest run — they are not missing as ACs, only falsely claimed here.
Action: remove lines 8-9 from the module docstring (`- AC4: ...` and `- AC5: ...`), matching the T13 precedent.

**A2 — Comment/docstring drift: `_parse_frontmatter` assertion is vacuously true.**
`tests/test_t14_check.py:56` — `assert marker == "\n---\n"` is equivalent to `assert marker` because `str.partition` returns the separator string unchanged when found. The assertion reads as if it is checking the value of `marker` but it can never differ from `"\n---\n"` if `partition` found it. An `assert marker, "..."` idiom would be clearer and honest.
Action: change `assert marker == "\n---\n", "..."` to `assert marker, "SKILL.md frontmatter must close with a trailing ---"` to match what the check actually does.

### What passed review (one-line per lens)

- Hidden bugs: none observed; test logic is correct for the files as they exist.
- Defensive-code creep: none; no try/except or None-guards introduced.
- Idiom alignment: doc-only Skill follows T13 shape cleanly; structlog/async/pydantic untouched.
- Premature abstraction: none; `_parse_frontmatter` and `_run_discoverability` helpers each have multiple callers within the file.
- Comment/docstring drift: two advisory items above (false AC coverage claim + vacuous assertion).
- Simplification: none warranted; test structure is appropriately flat.

## Sr. SDET review (2026-04-29)

**Test files reviewed:** `tests/test_t14_check.py`
**Skipped (out of scope):** `tests/test_t24_md_discoverability.py`, `tests/test_t13_triage.py` (pre-existing; provide inherited invariant coverage for AC4/AC5)
**Verdict:** SHIP

### BLOCK — tests pass for the wrong reason

None.

### FIX — fix-then-ship

None.

### Advisory — track but not blocking

**Advisory 1 — Module docstring overstates coverage: AC4 and AC5 claimed but no test bodies exist (Lens 2 / Lens 6)**

`tests/test_t14_check.py:8-9` lists AC4 (T10 invariant 9/9) and AC5 (T24 invariant on `.claude/agents/`) in the module-level docstring as covered by this file. Zero test functions in the file exercise either invariant. Both are genuinely covered by the pre-existing `test_t24_md_discoverability.py:test_t10_invariant_all_9_agents_reference_non_negotiables` and `test_t24_md_discoverability.py:test_rule3_section_budget_passes`. The tests pass for the right reason (the invariants hold), but the docstring misleads any engineer auditing which test file pins AC4/AC5. The T13 precedent (`test_t13_triage.py`) correctly omits these lines.

Action: remove the AC4 and AC5 lines from the `tests/test_t14_check.py` module docstring, matching the T13 pattern. Alternatively, add brief delegation comments (`# AC4 + AC5 covered by tests/test_t24_md_discoverability.py`) so the traceability is explicit rather than absent.

**Advisory 2 — CHANGELOG assertion does not pin placement under `[Unreleased]` (Lens 2)**

`tests/test_t14_check.py:289`: `assert "M21 Task 14" in content` passes whenever the string appears anywhere in `CHANGELOG.md`, including inside a versioned release block. The spec (AC8) requires the entry to be under `[Unreleased]`. The file is clean today (the entry is at line 10, immediately under `## [Unreleased]`), but the test does not enforce the invariant it claims (AC8 says "under [Unreleased]"). This mirrors the same pattern as T13's `test_changelog_t13_entry`; both are equally weak.

Action: tighten to extract the `[Unreleased]` block (lines between `## [Unreleased]` and the next `## [` heading) and assert the entry appears in that slice, e.g.:

```python
lines = content.splitlines()
start = next(i for i, l in enumerate(lines) if l.startswith("## [Unreleased]"))
end = next((i for i, l in enumerate(lines[start+1:], start+1) if l.startswith("## [")), len(lines))
unreleased_block = "\n".join(lines[start:end])
assert "M21 Task 14" in unreleased_block
```

**Advisory 3 — `_parse_frontmatter` separator assertion is misleading (Lens 1 minor / Lens 6)**

`tests/test_t14_check.py:55`: `assert marker == "\n---\n"` — `str.partition` returns the literal separator when found, so this assertion can only ever hold or the partition returns `""` for `marker` (separator not found). The comparison against the literal separator value adds no information; the real check is `assert marker` (non-empty = separator was found). The same pattern exists in `test_t13_triage.py:55`. Both files have this.

Action: replace `assert marker == "\n---\n", "..."` with `assert marker, "SKILL.md frontmatter must close with a trailing ---"` for honest intent. The existing check is not wrong (it's equivalent to `assert marker`), only misleading to a reader.

### What passed review (one-line per lens)

- Tests-pass-for-wrong-reason: none observed — assertions are load-bearing for the properties they test; no tautologies, no trivial non-None checks.
- Coverage gaps: AC4 and AC5 in the docstring uncovered by this file, but covered by pre-existing tests in scope (advisory); CHANGELOG placement check too weak (advisory).
- Mock overuse: no mocks used; subprocess invocations exercise real audit scripts against real filesystem — correct boundary for a doc-only Skill.
- Fixture / independence: no pytest fixtures; all tests read from REPO_ROOT-rooted absolute paths; no order dependence; no module-level state mutation.
- Hermetic-vs-E2E gating: fully hermetic — filesystem + local subprocess only; no network calls; no `AIW_E2E` gate needed or missing.
- Naming / assertion-message hygiene: all 19 test names describe what they verify; assertion messages include failure context (repr of actual values); no anonymous skip calls.
