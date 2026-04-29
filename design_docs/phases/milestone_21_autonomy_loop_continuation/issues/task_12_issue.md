# Task 12 — Skills extraction (`.claude/skills/dep-audit/`) — Audit Issues

**Source task:** [../task_12_skills_extraction.md](../task_12_skills_extraction.md)
**Audited on:** 2026-04-29 (cycle 2 close)
**Audit scope:** Cycle 2. Re-verified the three locked terminal decisions from cycle-1 (sr-dev FIX-01/FIX-02 + sr-sdet FIX-01) landed in `.claude/skills/dep-audit/runbook.md`. Confirmed scope leak boundary (only `runbook.md` + `CHANGELOG.md` touched in this cycle). Re-ran all 9 spec §Tests/smoke steps and the three terminal gates (`uv run pytest`, `uv run lint-imports`, `uv run ruff check`). Re-verified wheel allowlist against the actual `dist/jmdl_ai_workflows-0.3.1-py3-none-any.whl` archive (Python `zipfile` walk).

**Status:** ✅ PASS

## Design-drift check

No drift detected.

- No new dependencies (`pyproject.toml` / `uv.lock` untouched). Dep-audit gate not triggered.
- No source-code changes — diff is `.claude/`, `design_docs/`, `CHANGELOG.md` only. Layer rule untouched; `lint-imports` returns `5 kept, 0 broken`.
- No new LLM call paths, no `anthropic` import, no `ANTHROPIC_API_KEY` reads (KDR-003/004 N/A).
- No checkpoint / retry / observability surface touched (KDR-006/009 N/A).
- No `nice_to_have.md` adoption.
- M21 scope note ("autonomy infrastructure, not runtime") respected.

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| AC1 | ✅ | `SKILL.md` frontmatter intact: `name: dep-audit`, `description:` 182 chars, body 276 words → ~358 est. tokens. T24-rubric four checks all pass against `.claude/skills/dep-audit/`. |
| AC2 | ✅ | `runbook.md` re-verified post-edit: T24-rubric (summary / section-budget / code-block-len ≤20 / section-count ≥2) all pass. |
| AC3 | ✅ | `dependency-auditor.md` `## Operational shortcuts` section unchanged from cycle 1. |
| AC4 | ✅ | `_common/skills_pattern.md` unchanged from cycle 1; literal phrase still grep-matches. |
| AC5 | ✅ | T10 invariant: 9/9 agents reference `_common/non_negotiables.md`. |
| AC6 | ✅ | T24 invariant: all 12 `.claude/agents/` files pass all four discoverability checks. |
| AC7 | ✅ | `CHANGELOG.md` entry expanded to log cycle-2 corrections (Files-touched line now mentions `.claude/skills/dep-audit/runbook.md ... cycle-2: corrected §Lockfile-diff, §Dep-detection exit-code semantics, §Wheel-contents allowlist`). |
| AC8a | ✅ | T12 spec `**Status:**` = `✅ Done`. |
| AC8b | ✅ | M21 README task-pool row 73 = `✅ Done`. |
| AC8c | ✅ | M21 README §Exit criteria G6 present + satisfied parenthetical. G3 untouched (correct). |

## Locked terminal decisions — verification

| Decision | Spec source | Verification | Status |
| -------- | ----------- | ------------ | ------ |
| LTD-1 (sr-dev FIX-01) — §Lockfile-diff uses `git diff <pre-task-commit>..HEAD -- uv.lock`; drop `~ bumped` parser | issue file §Terminal gate locked decision 1 | `grep -c "uv lock --diff" runbook.md` = 0; `grep -c "~ bumped" runbook.md` = 0; `grep -nF "git diff <pre-task-commit>..HEAD -- uv.lock"` matches lines 5 + 64 (top-of-file summary + §Lockfile-diff invocation). Parsing patterns now describe `+` added/upgraded and `-` removed/downgraded only — pure standard git-diff format. Triage rule preserved at line 78. | ✅ Landed verbatim |
| LTD-2 (sr-dev FIX-02) — §Dep-detection uses `--exit-code`; semantics clarified | issue file §Terminal gate locked decision 2 | `grep -nF "git diff --exit-code"` matches lines 4 + 47 (top-of-file summary + §Dep-detection invocation). Lines 51-52 codify the exit-code semantics: "Exit 0 / empty stdout — no manifest changes; dep-audit gate does NOT fire" and "Exit 1 / any stdout lines — changes detected; spawn the `dependency-auditor` agent." Both halves of the locked decision applied (invocation + semantics). | ✅ Landed verbatim |
| LTD-3 (sr-sdet FIX-01) — §Wheel-contents allowlist accuracy | issue file §Terminal gate locked decision 3 | Allowlist (lines 13-15): `ai_workflows/` (subpackages: primitives, graph, workflows, mcp, cli, evals), `migrations/` (top-level; six SQL migration files), `*.dist-info/` (METADATA, RECORD, WHEEL, entry_points.txt, licenses/LICENSE). Misleading "bare LICENSE/README.md/CHANGELOG.md at top level" prose dropped. 3-line top-of-file summary (line 3) now reads `ai_workflows/, migrations/, *.dist-info/` allowlist + `.env*, design_docs/, runs/, *.sqlite3` denylist. `evals/` denylist row removed (`grep -c "evals/" runbook.md` = 0). Example output (lines 36-43) shows `ai_workflows/cli.py`, `migrations/001_initial.sql`, `jmdl_ai_workflows-0.3.1.dist-info/METADATA` — the three real wheel members. | ✅ Landed verbatim |

**Wheel reality check:** Python `zipfile` walk over `dist/jmdl_ai_workflows-0.3.1-py3-none-any.whl` yields top-level entries `['ai_workflows', 'jmdl_ai_workflows-0.3.1.dist-info', 'migrations']` — exactly the three allowlist umbrellas the runbook now documents. The cycle-1 LOW-01 freshness nit (allowlist undercounting) is closed by LTD-3.

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

### LOW-01 (cycle 1, now CLOSED)

Cycle-1 LOW-01 (`runbook.md` allowlist undercounted ai_workflows top-level layout) closed by LTD-3. Allowlist now expanded to `ai_workflows/` subpackages: `primitives, graph, workflows, mcp, cli, evals`. RESOLVED in working-tree edits; will land on the cycle-2 commit owned by orchestrator.

### LOW-02 (cycle 1, retained)

Builder schema-non-conformance is informational. Cycle-2 Builder return is unverified at audit-write time (orchestrator authority); per `feedback_builder_schema_non_conformance.md` this remains LOW-and-continue if it recurs. No change in posture.

## Additions beyond spec — audited and justified

None. Cycle-2 diff is exclusively `.claude/skills/dep-audit/runbook.md` content fixes + a `CHANGELOG.md` files-touched line amplification. No drive-by edits, no scope leak. (Spec amendment §Cycle 2 cited in Files in scope: "Optionally `CHANGELOG.md` if the entry needs amplification" — Builder used that allowance precisely.)

## Gate summary

| Gate | Command | Result |
| ---- | ------- | ------ |
| pytest (default) | `uv run pytest` | 1 expected fail / 1305 passed / 10 skipped — only failure is `tests/test_main_branch_shape.py::test_design_docs_absence_on_main`, the documented branch-shape test. |
| pytest (branch-aware) | `AIW_BRANCH=design uv run pytest tests/test_main_branch_shape.py` | 2 passed / 1 skipped. |
| lint-imports | `uv run lint-imports` | 5 contracts kept, 0 broken. |
| ruff | `uv run ruff check` | All checks passed. |
| smoke 1 (file existence) | `test -f SKILL.md && test -f runbook.md` | PASS |
| smoke 2 (frontmatter) | `grep name + description` | PASS (description = 182 chars) |
| smoke 3 (body ≤5K tokens) | `wc -w` × 1.3 | PASS (276 words → ~358 est. tokens) |
| smoke 4 (T24 rubric on dep-audit/) | 4 × `md_discoverability.py` | PASS — all 2 files pass each check |
| smoke 5 (Operational shortcuts pointer) | grep | PASS |
| smoke 6 (skills_pattern.md + magic phrase) | test + grep | PASS |
| smoke 7 (T10 invariant 9/9) | grep + awk | PASS — 9/9 |
| smoke 8 (T24 rubric on .claude/agents/) | 4 × `md_discoverability.py` | PASS — all 12 files pass each check |
| smoke 9 (CHANGELOG anchor) | grep | PASS |
| LTD-1/2/3 verification | grep + Python zipfile walk | PASS — all three locked decisions landed verbatim; wheel-reality check confirms allowlist accuracy |

Builder cycle-2 work is uncommitted in the working tree (orchestrator owns the commit, per autonomous-mode boundary). Diff against pre-task SHA `7dd34e1` matches Builder's claimed scope (runbook.md + CHANGELOG.md).

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch | Status |
| -- | -------- | ------------------ | ------ |
| M21-T12-ISS-01 | LOW | (was: next runbook touch) | RESOLVED at cycle-2 close (LTD-3 expanded allowlist + dropped misleading prose; wheel-reality verified) |
| M21-T12-ISS-02 | LOW | All M21 Builder cycles | OPEN (informational; meta-process only) |

## Deferred to nice_to_have

N/A — no findings map to a `nice_to_have.md` parking-lot item.

## Propagation status

No forward-deferred items. Both cycle-1 LOWs were either resolved at cycle-2 close (ISS-01) or are meta-process only (ISS-02). No target spec amendments needed.

## Terminal gate — cycle 1 verdict + locked terminal decisions (2026-04-29) — RESOLVED CYCLE 2

**Reviewer verdicts (cycle 1):** sr-dev = FIX-THEN-SHIP, sr-sdet = FIX-THEN-SHIP, security-reviewer = SHIP. Auditor-agreement bypass applied; locked terminal decisions stamped and re-looped to Builder cycle 2 as carry-over ACs.

**Cycle 2 disposition:** All three locked terminal decisions landed verbatim in `.claude/skills/dep-audit/runbook.md`. Auditor cycle 2 PASS. Recommend orchestrator re-run unified terminal gate; expect TERMINAL CLEAN (3 SHIP verdicts) since all factual blockers resolved.

### Locked terminal decision 1 (sr-dev FIX-01) — RESOLVED

`.claude/skills/dep-audit/runbook.md` §Lockfile-diff invocation now `git diff <pre-task-commit>..HEAD -- uv.lock`. Parsing patterns are standard git-diff format only. Fabricated `uv lock --diff` and `~ bumped` parser entry both removed. Triage rule preserved.

### Locked terminal decision 2 (sr-dev FIX-02) — RESOLVED

`§Dep-detection` invocation now `git diff --exit-code <pre-task-commit>..HEAD -- pyproject.toml uv.lock`. Exit-code semantics codified: empty stdout / exit 0 → no changes; any stdout / exit 1 → changes detected. Both halves of the locked decision applied.

### Locked terminal decision 3 (sr-sdet FIX-01) — RESOLVED

§Wheel-contents allowlist now reflects the real `0.3.1` wheel: `ai_workflows/`, `migrations/`, `*.dist-info/`. Misleading bare-top-level prose for LICENSE/README.md/CHANGELOG.md dropped. 3-line top-of-file summary updated. `evals/` denylist row removed. Wheel-reality check (Python zipfile walk) confirms allowlist umbrellas match the three real top-level entries.

## Sr. Dev review (cycle 2)

Verdict: SHIP. All three cycle-1 FIX findings (FIX-01, FIX-02, ADV-01) verified resolved in `runbook.md`. No new findings against the cycle-2 diff. Full review fragment: `runs/m21_t12/cycle_2/sr-dev-review.md`.

## Sr. SDET review (cycle 2)

Verdict: SHIP. Wheel-reality check (Python zipfile walk over `dist/jmdl_ai_workflows-0.3.1-py3-none-any.whl`) confirms the runbook's cycle-2 allowlist (`ai_workflows/`, `migrations/`, `*.dist-info/`) matches the three real top-level entries. cycle-1 FIX-01 (LTD-3) fully resolved.

ADV-01 — SKILL.md procedure step 3 still referenced fabricated `uv lock --diff` (inconsistent with runbook's LTD-1 fix). **Absorbed inline by orchestrator:** SKILL.md line 36 updated to `git diff <pre-task-commit>..HEAD -- uv.lock`. Same wording as runbook §Lockfile-diff. Cycle-2 diff scope expanded by one line accordingly.

Full review fragment: `runs/m21_t12/cycle_2/sr-sdet-review.md`.

## Security review (cycle 2)

Verdict: SHIP. No new threat-model surface introduced by cycle-2 doc edits. No `ai_workflows/` code touched; no `pyproject.toml` / `uv.lock` change. Full review fragment: `runs/m21_t12/cycle_2/security-review.md`.
