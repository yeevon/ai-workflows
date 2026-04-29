# Task 13 — `/triage` post-halt diagnosis Skill — Audit Issues

**Source task:** [../task_13_triage_command.md](../task_13_triage_command.md)
**Audited on:** 2026-04-29
**Audit scope:** Cycle 1 — `.claude/skills/triage/SKILL.md`, `.claude/skills/triage/runbook.md`, `tests/test_t13_triage.py`, `_common/skills_pattern.md` Live Skills line, M21 README §G3 + T13 row, T13 spec Status flip, CHANGELOG `[Unreleased]` entry.
**Status:** ✅ PASS

## Design-drift check

No drift detected. T13 is doc-only (no runtime imports, no LLM call, no checkpoint/retry/observability surface, no MCP tool surface change, no new dependency). KDR-013 scope is preserved (Skill is in-tree, framework-owned). Skill body is grounded purely in autonomy-loop diagnosis — no `nice_to_have.md` adoption (no Langfuse / OTel / LangSmith pulled in).

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| AC1 — SKILL.md exists; valid frontmatter; ≤5K tokens; four `##` anchors | ✅ Met | name=`triage`, description=192 chars (≤200), `allowed-tools: Read, Bash, Grep`, body 546 words ≈ 710 tokens (well under 5K), Inputs/Procedure/Outputs/Return schema all present. Smoke 1–3 + 5 pass. |
| AC2 — runbook.md exists; T24 rubric clean | ✅ Met | `md_discoverability.py` summary / section-budget / code-block-len-20 all OK on `.claude/skills/triage/`. Smoke 4 pass. |
| AC3 — T25 skills_efficiency clean | ✅ Met | `skills_efficiency.py --check all --target .claude/skills/` → "all 5 skill file(s) pass". Smoke 6 pass. |
| AC4 — T10 invariant held | ✅ Met | All 9 agent prompts still reference `_common/non_negotiables.md` (smoke 7). |
| AC5 — T24 invariant held on `.claude/agents/` | ✅ Met | `section-budget` over `.claude/agents/` → all 12 file(s) pass (smoke 8). |
| AC6 — `tests/test_t13_triage.py` passes | ✅ Met | 19 tests pass in 0.34s. Full suite: 1343 pass / 1 unrelated `test_main_branch_shape` fail (off-main branch — known) / 10 skipped. |
| AC7 — `_common/skills_pattern.md` Live Skills count line | ✅ Met | Line reads `Live Skills: ai-workflows (legacy), dep-audit (T12), triage (T13).` (smoke 11). |
| AC8 — CHANGELOG entry under `[Unreleased]` | ✅ Met | `### Added — M21 Task 13: /triage post-halt diagnosis Skill (2026-04-29)` at line 10 (smoke 10). |
| AC9a — T13 spec `**Status:**` → ✅ Done | ✅ Met | Confirmed in diff. |
| AC9b — M21 README T13 row Status → ✅ Done | ✅ Met | Confirmed in diff (Phase F task pool). |
| AC9c — M21 README §G3 satisfaction parenthetical | ✅ Met | `(satisfied at T13; /triage shipped as the highest-value Phase F Skill; T14/T15/T16 separate)` appended in-place. |
| TA-LOW-01 (carry-over) — extra `## When to use` / `## When NOT to use` anchors permitted | ✅ Met | Both anchors kept ahead of `## Inputs` per dep-audit precedent; T25 efficiency gate clean (only enforces the four required anchors); no spec edit needed. |

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

None. Builder report's `Co-Authored-By` trailer cites Sonnet 4.6, not the cycle's actual model identity per memory `feedback_builder_schema_non_conformance.md`; observation only — durable work landed correctly and orchestrator owns commit creation, not Builder.

## Additions beyond spec — audited and justified

- **`## When to use` / `## When NOT to use` anchors in SKILL.md** — explicitly permitted by spec carry-over TA-LOW-01 and dep-audit precedent. Token cost trivial (~50 words).
- **Helper-file reference inside `## Procedure`** (step 5 + step 6 cite `runbook.md` §Halt classifications and §Option matrices) — improves progressive-disclosure routing without inflating SKILL.md.

No scope creep, no drive-by refactors, no `nice_to_have.md` adoption.

## Gate summary

| Gate | Command | Result |
| ---- | ------- | ------ |
| pytest (T13 only) | `uv run pytest tests/test_t13_triage.py -q` | ✅ 19 passed |
| pytest (full) | `uv run pytest -q` | 1343 passed / 1 unrelated `test_main_branch_shape` fail (off-main branch — pre-existing, not T13) / 10 skipped |
| lint-imports | `uv run lint-imports` | ✅ 5 contracts kept, 0 broken |
| ruff | `uv run ruff check` | ✅ All checks passed |
| T24 rubric (triage) | `md_discoverability.py --check {summary,section-budget,code-block-len --max 20} --target .claude/skills/triage/` | ✅ all 2 file(s) pass each |
| T25 efficiency | `skills_efficiency.py --check all --target .claude/skills/` | ✅ all 5 skill file(s) pass |
| T10 invariant | grep `_common/non_negotiables.md` over 9 agent prompts | ✅ 9/9 |
| T24 invariant (`.claude/agents/`) | `md_discoverability.py --check section-budget --target .claude/agents/` | ✅ all 12 file(s) pass |
| SKILL.md token budget | `awk` word-count × 1.3 | ✅ 546 words ≈ 710 tokens (≤ 5000) |
| CHANGELOG anchor | `grep -nE '^### (Added\|Changed) — M21 Task 13:' CHANGELOG.md` | ✅ line 10 |

## Issue log — cross-task follow-up

None. Cycle 1 closed clean.

## Deferred to nice_to_have

None.

## Propagation status

No forward-deferrals. T13 is independent of T14/T15/T16; Phase F continues per M21 phasing.

## Sr. Dev review (2026-04-29)

**Files reviewed:** `.claude/skills/triage/SKILL.md`, `.claude/skills/triage/runbook.md`, `tests/test_t13_triage.py`, `.claude/agents/_common/skills_pattern.md`, `CHANGELOG.md`, `design_docs/phases/milestone_21_autonomy_loop_continuation/README.md` (§G3 + T13 row)
**Skipped (out of scope):** none
**Verdict:** SHIP

### BLOCK — must-fix before commit

None.

### FIX — fix-then-ship

None.

### Advisory — track but not blocking

- **`tests/test_t13_triage.py:279` — Simplification / hidden test weakness.** `test_changelog_t13_entry` asserts `"M21 Task 13" in content` over the entire CHANGELOG file. If the entry were under a released version heading (not `[Unreleased]`), the test would still pass. The Auditor confirmed visual placement, so this is not a live bug — but the test is weaker than it looks. Consider tightening to: read lines up to the first `## [` version heading after `[Unreleased]` and assert the entry appears within that slice. Matches the pattern T12 used; same advisory applies there.
  Lens: hidden bugs that pass tests (test-only scope — advisory because doc-only task).

- **`tests/test_t13_triage.py:41` — Simplification.** `_read_skill_md()` is called once per test function (10+ calls), re-reading from disk each time. The helper adds no value over `SKILL_MD.read_text(encoding="utf-8")` at the call site, and the helper's docstring (`Read triage SKILL.md as UTF-8`) is pure restatement. Consider inlining or caching. Advisory only — test runtime is 0.34s and the pattern is idiom-aligned with T12.
  Lens: simplification opportunities + comment/docstring drift.

### What passed review (one-line per lens)

- Hidden bugs: one test-only weakness (CHANGELOG placement assert) — advisory, not a live bug.
- Defensive-code creep: none; no defensive patterns present in a doc-only task.
- Idiom alignment: SKILL.md shape, runbook T24 rubric conformance, subprocess test pattern — all match existing neighbours (dep-audit, test_t25_skills_efficiency.py).
- Premature abstraction: none; `_parse_frontmatter` and `_run_discoverability` helpers both have multiple callers within the file.
- Comment/docstring drift: one restatement docstring on `_read_skill_md` — noted in simplification finding above.
- Simplification: `_read_skill_md` trivially inlineable; no other opportunities.

## Sr. SDET review (2026-04-29)

**Test files reviewed:** `tests/test_t13_triage.py`
**Skipped (out of scope):** none
**Verdict:** SHIP

### BLOCK — tests pass for the wrong reason

None observed.

### FIX — fix-then-ship

None.

### Advisory — track but not blocking

**A1 — Anchor tests use substring match; cannot detect malformed headings.**
`tests/test_t13_triage.py:149,155,161,167` — each of the four anchor tests asserts
`"## Anchortitle" in body`. A heading like `## Inputs (optional)` or `## Return schema notes`
satisfies the substring test while not being the exact T25-mandated anchor. Currently harmless
because the actual SKILL.md has exact headings, but the test does not pin the exactness of the
contract.
Lens 2 (coverage gap — boundary condition).
Recommendation: replace with `re.search(r'^## Inputs$', body, re.MULTILINE) is not None` (and
equivalents) in all four anchor tests.

**A2 — `test_skill_md_body_token_budget` counts words including the YAML frontmatter block.**
`tests/test_t13_triage.py:132` — `body.split()` runs on the raw file text. The spec says "body
<= 5K tokens"; frontmatter is not body. With a 546-word file the budget headroom is large (~4290
tokens) so no false pass risk exists today, but the metric will drift as frontmatter grows.
Lens 2 (coverage gap — wrong granularity).
Recommendation: strip frontmatter before counting using `body.partition("\n---\n")[2]` after the
closing `---`, mirroring `md_discoverability.py`'s `_strip_frontmatter` helper.

**A3 — `test_changelog_t13_entry` does not verify placement under `[Unreleased]`.**
`tests/test_t13_triage.py:279` — asserts `"M21 Task 13" in content` over the full CHANGELOG.
A mention in any released-version section satisfies the assertion. The AC8 requires placement
under `[Unreleased]`. The sr-dev review noted this same weakness; it is confirmed from the test
lens as well.
Lens 2 (coverage gap — partial assertion; placement not checked).
Recommendation: read CHANGELOG lines up to the first `## [` version heading and assert the entry
falls within that slice.

### What passed review (one line per lens)

- Tests-pass-for-wrong-reason: none — assertions are positive-direction and match measurable spec claims.
- Coverage gaps: three advisory items (A1 anchor exactness, A2 word-count scope, A3 CHANGELOG position); none warrant blocking SHIP on a doc-only task.
- Mock overuse: not applicable — no mocks; all tests use real files and real subprocess invocations.
- Fixture / independence: all tests are stateless reads of on-disk files; no fixture scope issues; no inter-test bleed.
- Hermetic-vs-E2E gating: all tests are hermetic; no network calls; subprocess calls target local scripts only; no gating concerns.
- Naming / assertion-message hygiene: test names are descriptive and per-AC; failure messages include diagnostic context; clean.
