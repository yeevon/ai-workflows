# Task 15 Issue File — `/ship` manual happy-path publish Skill

**Status:** ✅ Done — cycle 2 TERMINAL CLEAN (sr-dev SHIP / sr-sdet SHIP / security-reviewer SHIP). All FIX carry-overs applied; gates clean. Pre-commit.
**Task:** M21 T15 — `/ship` manual happy-path publish Skill (host-only)
**Cycle:** 1 (Auditor PASS → terminal FIX × 2 → bypass + re-loop) → cycle 2 (Builder BUILT → Auditor PASS → terminal CLEAN).
**Builder schema-conformance LOW (cycle 2):** Builder set the issue-file Status line at handoff time; the orchestrator owns Status surface flips. Per memory `feedback_builder_schema_non_conformance.md`, recorded as LOW (durable work landed correctly), not a HALT. Orchestrator updated Status above at terminal-clean stamp time.

## Auditor findings (cycle 1)

No HIGH or MEDIUM findings. Three carry-over LOWs from task analysis accepted per spec.

### Carry-over resolutions

- **TA-LOW-01** (hard-pinned agent count at 9): accepted for sibling parity with T13/T14/T16. No spec change needed.
- **TA-LOW-02** (leading-slash Skill references): accepted for sibling parity. No spec change needed.
- **TA-LOW-03** (`curl -s` → `curl -sf`): applied at implement time — procedure step 6 and runbook §PyPI version compare both use `curl -sf`.

## Files delivered (cycle 1, pre-cycle-2)

- `.claude/skills/ship/SKILL.md` — new
- `.claude/skills/ship/runbook.md` — new (cycle 2 will edit pre-flight matrix)
- `tests/test_t15_ship.py` — new (cycle 2 will tighten CHANGELOG assertion)
- `.claude/agents/_common/skills_pattern.md` — Live Skills line extended
- `design_docs/phases/milestone_21_autonomy_loop_continuation/task_15_ship_command.md` — Status → Done
- `design_docs/phases/milestone_21_autonomy_loop_continuation/README.md` — T15 row → Done; G3 → Phase F complete
- `CHANGELOG.md` — M21 Task 15 entry added

## Cycle 1 terminal-gate verdicts

| Reviewer | Verdict | Fragment |
| --- | --- | --- |
| sr-dev | FIX-THEN-SHIP | `runs/m21_t15/cycle_1/sr-dev-review.md` |
| sr-sdet | FIX-THEN-SHIP | `runs/m21_t15/cycle_1/sr-sdet-review.md` |
| security-reviewer | SHIP | `runs/m21_t15/cycle_1/security-review.md` |

Both FIX verdicts come from different lenses (code-quality vs test-quality). Per memory `feedback_lens_specialisation_not_divergence.md`, this is a TERMINAL FIX → bypass-eligible Builder re-loop, NOT user-arbitration.

### Locked terminal decisions (loop-controller + reviewer concur, 2026-04-29)

**FIX-1 — runbook.md pre-flight version-grep targets wrong file (sr-dev).**
Runbook lists `grep '^version' pyproject.toml`; this repo declares `dynamic = ["version"]` so the actual source is `ai_workflows/__init__.py:__version__`. Locked decision: replace command with `grep '^__version__' ai_workflows/__init__.py`. Failure condition + HALT message unchanged. Single clear fix; in-T15-scope; no KDR conflict.

**FIX-2 — test_t15_ship.py CHANGELOG assertion under-enforces AC9 (sr-sdet).**
`test_changelog_t15_entry` asserts presence anywhere; AC9 requires placement under `[Unreleased]`. Locked decision: tighten the assertion to slice between the `[Unreleased]` anchor and the first versioned `## [0.` block before checking membership. Single clear fix; in-T15-scope; no KDR conflict.

### Out-of-scope reviewer recommendation (rejected from T15)

**sr-sdet sibling-parity hardening — T13/T14/T16 CHANGELOG assertions.**
sr-sdet noted the same weak-assertion pattern in `tests/test_t13_triage.py`, `tests/test_t14_check.py`, `tests/test_t16_sweep.py` and recommended fixing them in the same commit. **Rejected** as drive-by refactor: T13/T14/T16 are already shipped (✅ Done); their AC enforcement was loose-but-correct at ship time. Editing those tests retroactively under T15's scope violates scope discipline. Recorded here as a cross-task observation; not entered as carry-over on T17 (parallel-builders) due to topic mismatch. If a future test-hardening cleanup task is created, this is the seed.

## Carry-over for cycle 2 (Builder picks up)

- [x] **FIX-1** — In `.claude/skills/ship/runbook.md`, replace the pre-flight check matrix command `grep '^version' pyproject.toml` with `grep '^__version__' ai_workflows/__init__.py`. Failure condition + HALT message unchanged. ✓ cycle 2
- [x] **FIX-2** — In `tests/test_t15_ship.py::test_changelog_t15_entry`, tighten the assertion. Use the three-line shape from the sr-sdet fragment (`unreleased_idx`, `first_version_idx`, slice-membership check) so the test verifies the M21-Task-15 entry sits between `[Unreleased]` and the first versioned `## [0.` block. ✓ cycle 2
- [x] **Re-run gates** — `uv run pytest tests/test_t15_ship.py -q`, `uv run pytest -q`, `uv run lint-imports`, `uv run ruff check`. All must remain clean. ✓ 21/21 + 1394/7 + 5 kept + all checks passed.
- [x] Do **not** touch `tests/test_t13_triage.py`, `tests/test_t14_check.py`, `tests/test_t16_sweep.py` — sibling hardening is rejected as out-of-scope. ✓ not touched.

## Sr. Dev review (2026-04-29)

**Files reviewed:** `.claude/skills/ship/SKILL.md`, `.claude/skills/ship/runbook.md`, `tests/test_t15_ship.py`, `.claude/agents/_common/skills_pattern.md`, `CHANGELOG.md`, `design_docs/phases/milestone_21_autonomy_loop_continuation/README.md`, `design_docs/phases/milestone_21_autonomy_loop_continuation/task_15_ship_command.md`
**Skipped (out of scope):** none
**Verdict:** FIX-THEN-SHIP

### BLOCK — must-fix before commit

None.

### FIX — fix-then-ship

**`runbook.md:15` — pre-flight version check targets wrong file (hidden bug that passes tests)**
Lens: Hidden bugs that pass tests.

The pre-flight check matrix row "Version not pre-release" specifies command `grep '^version' pyproject.toml`. In this repo `version` is declared `dynamic` in pyproject.toml (`dynamic = ["version"]`) — there is no `version = "..."` key in that file. The single source of truth is `ai_workflows/__init__.py:__version__`. Running the listed command yields no output and exit code 1 on every invocation, meaning the pre-flight check misfires: either a false-positive HALT (blocking every `/ship` attempt for the wrong reason) or silent pass depending on how the executor interprets "failure condition = string contains dev/a/b/rc" when there is no string to inspect. Either outcome is wrong.

Action: Replace the command in the pre-flight matrix with one that reads the actual version source:
```
grep '^__version__' ai_workflows/__init__.py
```
Failure condition remains: value contains `dev`, `a`, `b`, `rc`. HALT message unchanged.

This is a FIX-level finding (not BLOCK) because the Skill is doc-only — no runtime path is broken — but a first-use operator following the runbook verbatim will hit the misfire immediately.

### Advisory — track but not blocking

**`runbook.md` — no post-publish verification section**
Lens: Comment / docstring drift.

SKILL.md step 6 ("Post-publish verification") describes a retry-once-on-mismatch flow but `runbook.md` has no corresponding section (the spec required: "pre-flight check matrix, build+wheel-contents, real-install smoke, operator-approval prompts, publish failure modes" — post-publish verification was not mandated in runbook). The asymmetry means an operator reading runbook.md for guidance on step 6 finds nothing. Advisory because the spec didn't require it; the omission is consistent with minimum-spec delivery.

Advisory: Consider a brief `## Post-publish verification` section in runbook.md with the retry-once logic and the `curl -sf` parsing one-liner, mirroring the check Skill's runbook.

**`tests/test_t15_ship.py:42–45` — `_read_skill_md()` helper called eight times separately**
Lens: Simplification opportunities.

`_read_skill_md()` is a one-liner (`SKILL_MD.read_text(encoding="utf-8")`) wrapped as a named helper and called once per test. Each test also calls `_parse_frontmatter(body)` separately. Sibling `test_t16_sweep.py` uses the same pattern — this is established idiom for this test tier, so no change needed. Note only: if the test file grows further, a module-scoped `@pytest.fixture` would be cleaner. Not blocking.

### What passed review (one-line per lens)

- Hidden bugs: version-grep false-misfire found (FIX above); curl-sf applied correctly per TA-LOW-03.
- Defensive-code creep: none observed; no extra guards beyond what the Skill's safety mandate requires.
- Idiom alignment: mirrors sibling T13/T14/T16 shape exactly — frontmatter, runbook, test structure all consistent.
- Premature abstraction: none; no new helpers or base classes introduced.
- Comment / docstring drift: module docstring in test file correctly cites task + sibling relationship; inline comments minimal and appropriate.
- Simplification: `_read_skill_md()` helper is consistent with sibling pattern; noted above as advisory only.

## Sr. SDET review (2026-04-29)

**Test files reviewed:** `tests/test_t15_ship.py`
**Skipped (out of scope):** `.claude/skills/ship/SKILL.md`, `.claude/skills/ship/runbook.md` (system under test, not test files)
**Verdict:** FIX-THEN-SHIP

### BLOCK — tests pass for the wrong reason

None.

### FIX — fix-then-ship

**`tests/test_t15_ship.py:301-306` — CHANGELOG assertion weaker than AC9 (assertion message vs. code mismatch)**
Lens 6 / Lens 1 (assertion message misleads; code understates AC).

`test_changelog_t15_entry` asserts `"M21 Task 15" in content` and the assertion failure message says "must contain a 'M21 Task 15' entry under [Unreleased]". The code only verifies presence anywhere in the file; it does not verify placement under `[Unreleased]`. AC9 explicitly requires the entry to be under `[Unreleased]`. At this point in time the test passes for the right reason (the entry IS under `[Unreleased]`), but once a versioned release moves the block, the test still passes regardless of section. The assertion message overstates what the code checks.

Identical pattern is present in sibling `tests/test_t13_triage.py:279` (established prior-art parity), so this is a consistent weakness across the sibling tier, not a T15-specific regression. Nevertheless it is a genuine gap between AC9's stated requirement and the test's actual enforcement.

Action: Tighten the assertion to confirm both (a) the entry is present and (b) it appears before the first versioned `[X.Y.Z]` block. Minimal fix:
```python
unreleased_idx = content.find("[Unreleased]")
first_version_idx = content.find("\n## [0.", unreleased_idx + 1)
assert unreleased_idx != -1 and "M21 Task 15" in content[unreleased_idx:first_version_idx], (
    "CHANGELOG.md must contain a 'M21 Task 15' entry under [Unreleased]"
)
```
Apply the same fix to sibling `test_t13_triage.py`, `test_t14_check.py`, `test_t16_sweep.py` in the same commit (Advisory carry-over for sibling tasks).

Note: The Sr-Dev review already issued a FIX-THEN-SHIP on `runbook.md:15` (version-grep wrong file). This finding is a second, independent FIX. Both must be resolved before ship.

### Advisory — track but not blocking

**`tests/test_t15_ship.py:196-217` — T24 docstrings claim "runbook.md" but --target covers both files**
Lens 6 (assertion-message hygiene).

`test_runbook_md_t24_summary`, `test_runbook_md_t24_section_budget`, `test_runbook_md_t24_code_block_len` all pass `--target str(SKILL_DIR)` (the `ship/` directory). `md_discoverability.py:_get_md_files()` returns all `.md` files under that directory, which includes `SKILL.md` and `runbook.md`. Each test's docstring says "AC2: runbook.md passes T24 rubric..." but both files are checked. The tests bite correctly (a SKILL.md violation would also cause failure, which is conservative), but the docstrings misstate what is being checked.

Advisory: Update docstrings to say "AC2: ship/ directory passes T24 rubric..." to reflect the actual scope.

**ACs 5, 6, 10 not in test file (consistent with sibling pattern)**
Lens 2 (coverage gaps — Advisory tier).

AC5 (T10 invariant — 9 agent files reference `_common/non_negotiables.md`), AC6 (T24 invariant on `.claude/agents/`), and AC10 (status-surface flips: spec Status line, README task-table row, README §G3 prose) are verified by Auditor smoke commands only, not in `tests/test_t15_ship.py`. This is consistent with sibling T13/T14/T16 which also omit these ACs from their test files. Advisory track for a future test-hardening pass.

### What passed review (one-line per lens)

- Tests-pass-for-wrong-reason: no hidden-bug passing case; CHANGELOG assertion weakness is a known prior-art parity gap, not a new T15 regression.
- Coverage gaps: ACs 5/6/10 omitted — consistent with sibling pattern; advisory only.
- Mock overuse: no mocks at all; pure filesystem + subprocess; clean.
- Fixture / independence: no fixtures; all tests are stateless on-disk readers; no bleed possible.
- Hermetic-vs-E2E gating: all subprocess calls invoke local Python scripts with no network; hermetic; clean.
- Naming / assertion-message hygiene: CHANGELOG assertion message overstates enforcement (FIX above); T24 docstrings misstate scope (Advisory above).

## Auditor cycle 2 verification (2026-04-29)

**Verdict:** PASS — both surgical fixes landed correctly, no regressions, no new HIGH/MEDIUM findings.

### Cycle 2 carry-over fixes verified

| Fix | Location | Verification | Result |
|---|---|---|---|
| FIX-1 (runbook version-pin grep) | `.claude/skills/ship/runbook.md:15` | Reads `grep '^__version__' ai_workflows/__init__.py`; failure-condition + HALT message columns unchanged. Live execution returns `__version__ = "0.3.1"`. | PASS |
| FIX-2 (CHANGELOG slice-membership test) | `tests/test_t15_ship.py:301-308` | Three-line shape exactly per locked decision: `unreleased_idx = content.find("[Unreleased]")` / `first_version_idx = content.find("\n## [0.", unreleased_idx + 1)` / slice-membership assert with combined precondition. | PASS |

### Scope-containment check (no sibling-test drift)

`git diff --name-only HEAD` yields exactly the four expected modified files (`.claude/agents/_common/skills_pattern.md`, `CHANGELOG.md`, `milestone_21 README.md`, `task_15 spec`) plus three expected untracked artefacts (`.claude/skills/ship/`, `tests/test_t15_ship.py`, this issue file). `git diff HEAD -- tests/test_t13_triage.py tests/test_t14_check.py tests/test_t16_sweep.py` is empty — no scope creep into sibling tests. Builder honoured cycle-2 surgical-only directive.

### Gate re-verification (cycle 2 artefacts under `runs/m21_t15/cycle_2/`)

| Gate | Artefact | Result |
|---|---|---|
| `uv run pytest tests/test_t15_ship.py -q` | `gate_pytest_t15.txt` | 21 passed in 0.34s |
| `uv run pytest -q` (full suite) | `gate_pytest_full.txt` | 1394 passed, 7 skipped — matches cycle 1 baseline, zero regression |
| `uv run lint-imports` | `gate_lint-imports.txt` | 5 kept, 0 broken |
| `uv run ruff check` | `gate_ruff.txt` | All checks passed |

### Cycle 1 AC non-regression spot-check

ACs 1-10 from cycle 1 remain satisfied. Spot-checks on the changed files:
- AC2 (runbook pre-flight matrix six checks): row count unchanged (six rows), only the version-pin row body updated; matrix structure intact.
- AC9 (CHANGELOG entry under `[Unreleased]`): test now asserts on the slice between `[Unreleased]` and the first `## [0.` heading — verified passing in `gate_pytest_t15.txt`. The substantive coverage gap (assertion does not enforce ordering, but spec wording requires "under [Unreleased]") was a cycle-1 sr-sdet observation that the locked decision deferred to a parity-fix follow-up; cycle-2 fix tightens the slice but does not fully close the gap. Not blocking — covered by the existing carry-over discussion in `## Sr. SDET review (2026-04-29)`.

### KDR drift check (seven load-bearing)

T15 is a doc-only Skill delivery: no Python source under `ai_workflows/`, no `pyproject.toml` change, no LLM call, no `pydantic_ai`, no checkpoint/retry surface. KDRs 002 / 003 / 004 / 006 / 008 / 009 / 013 are trivially aligned. No drift.

### LOW (cycle 2) — Builder schema non-conformance on issue-file Status line

**Severity:** LOW (informational; not a HARD HALT per memory `feedback_builder_schema_non_conformance.md`).
**Observation:** Builder cycle-2 set the issue-file Status line to `✅ Done — cycle 2 complete; all FIX carry-overs applied; gates clean.` Authoring the Status line is the orchestrator's prerogative at terminal-gate close, not the Builder's.
**Action / Recommendation:** Orchestrator overwrites the Status line at terminal-gate close. Carry the pattern forward as a Builder-prompt reinforcement candidate; no code change required. Durable work landed correctly — does not block PASS.

### Critical sweep

- ACs that look met but aren't: none new in cycle 2.
- Silently skipped deliverables: none — both locked decisions implemented verbatim.
- Additions beyond spec: none.
- Test gaps: AC9 assertion still parity-matches T13/T14/T16 (deferred follow-up, not new).
- Doc drift: none.
- Secrets shortcuts: none.
- nice_to_have creep: none.
- Status-surface drift: addressed by orchestrator at terminal-gate close (the LOW above).

### Issue log update

| ID | Severity | Status | Note |
|---|---|---|---|
| M21-T15-ISS-01 (FIX-1 runbook grep) | HIGH | RESOLVED (cycle 2) | Verified at runbook.md:15; live grep returns version line. |
| M21-T15-ISS-02 (FIX-2 CHANGELOG slice-membership) | HIGH | RESOLVED (cycle 2) | Verified at test_t15_ship.py:301-308; passing in gate_pytest_t15.txt. |
| M21-T15-ISS-03 (Builder Status-line authorship) | LOW | OPEN | Orchestrator overwrites at terminal-gate close. |

**Status:** ✅ PASS — cycle 2 narrow re-audit complete; both FIX carry-overs verified; no regression; one LOW informational finding (Builder Status-line authorship) deferred to orchestrator close-out.

---

## Security review (cycle 1 — 2026-04-29)

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

**`SKILL.md:49` — `--yes` flag bypasses operator-approval prompt (Threat model §2 / autonomy-mode boundary)**
File: `.claude/skills/ship/SKILL.md`, line 49.
Threat-model item: Subprocess execution / autonomy-mode boundary (CLAUDE.md autonomous-mode boundary, `feedback_autonomous_mode_boundaries.md`).
The `--yes` flag pre-approves the publish step and skips the typed-token interactive prompt entirely. If the host-only boundary ever erodes and an orchestrator agent invokes `/ship --yes`, the approval gate is bypassed with no human in the loop. Within the current single-user local-machine deployment this is not exploitable: the SKILL.md `## Host-only — autonomy-mode forbidden` section mandates a HARD HALT on any orchestrator invocation, and the project is not multi-tenant. The risk is residual — the foot-gun exists if the boundary is later weakened without revisiting this flag.
Action: No immediate change required. If the autonomy boundary is ever relaxed, strip `--yes` from the Skill or gate it on an explicit operator-confirmation environment variable rather than a CLI flag that an LLM can supply.

**`runbook.md:71` — approval-gate display block shows unexpanded `$PYPI_TOKEN` string (Threat model §1 / logging hygiene)**
File: `.claude/skills/ship/runbook.md`, line 71.
Threat-model item: Logging hygiene (§7 of threat model).
The operator-approval prompt template shows the literal string `"$PYPI_TOKEN"` in the command-to-run block. This is the *shell variable reference*, not the expanded token value, so no real secret is exposed. Confirmed: no `set -x`, no echo of the expanded value anywhere in the Skill. Advisory because a future edit that replaces `$PYPI_TOKEN` with the expanded value (e.g., for clarity) would leak the token in the report file written to `runs/ship/<timestamp>/report.md`.
Action: Add a comment in runbook.md explicitly noting that the command template MUST use the variable reference, never the expanded value.

### Findings on specific concerns

1. **Token handling** — No leak. `set -a && . ./.env && set +a` sources the token into the subprocess environment; `--token "$PYPI_TOKEN"` passes the shell reference. No `set -x`, no echo. The report written to `runs/` logs the command template with `$PYPI_TOKEN` unexpanded. The `runs/` directory is excluded from the wheel (denylist enforced). Clean.

2. **Operator approval gate** — Gate is textual (typed "ship it" / "yes" / "y" / "approve"). `--yes` bypasses the prompt — see Advisory above. The host-only HARD HALT is the primary enforcement layer and is clearly stated in frontmatter + body. Sufficient for current threat model.

3. **Wheel-contents check** — Runbook §Build + wheel-contents enforces both a denylist (`.env*`, `design_docs/`, `runs/`, `*.sqlite3`, `.claude/`, `__pycache__/`) and a required-contents allowlist (`ai_workflows/`, `LICENSE`, `README.md`, `CHANGELOG.md`). Both lists are correct and complete per threat model §1. Clean.

4. **Autonomy-mode discoverability** — SKILL.md frontmatter `description:` includes "Forbidden in autonomy mode." Body has `## ⚠️ Host-only — autonomy-mode forbidden` with explicit HARD HALT language. Unambiguous. Clean.

5. **Subprocess input hijack** — All subprocess invocations in the runbook use fixed command strings with no user-supplied input interpolated into shell commands. No `shell=True` equivalent with dynamic input. Clean.

### Verdict: SHIP
## Sr. Dev review (cycle 2 — 2026-04-29)

**Files reviewed:** `.claude/skills/ship/runbook.md` (FIX-1 verification), `tests/test_t15_ship.py` (sr-sdet domain — not re-reviewed), `design_docs/phases/milestone_21_autonomy_loop_continuation/issues/task_15_issue.md`
**Skipped (out of scope):** `tests/test_t15_ship.py` (sr-sdet domain per scope constraint)
**Verdict:** SHIP

### Cycle-1 FIX verification

**`runbook.md:15` — pre-flight version-grep fix confirmed**

The cell now reads `grep '^__version__' ai_workflows/__init__.py`. Verified against live file.

Runtime check: `grep '^__version__' ai_workflows/__init__.py` → `__version__ = "0.3.1"`. Command executes successfully; exit code 0; output contains no pre-release markers. Fix is correct and functional.

Failure-condition column: "Version string contains `dev`, `a`, `b`, `rc`" — unchanged.
HALT message column: `HALT: pre-release-version (got: <version>)` — unchanged.

No collateral changes to surrounding rows observed.

### Cycle-1 advisory items — state check

- **Post-publish verification section in runbook.md** — still absent. Advisory state unchanged; not a blocker.
- **`_read_skill_md()` helper pattern in tests** — unchanged. Advisory state unchanged; not a blocker.

### 🔴 BLOCK — must-fix before commit

None.

### 🟠 FIX — fix-then-ship

None.

### 🟡 Advisory — track but not blocking

No new advisory items introduced in cycle 2.

### What passed review (one-line per lens)

- Hidden bugs: FIX-1 confirmed resolved; no new hidden bugs introduced in the two-line change.
- Defensive-code creep: none observed.
- Idiom alignment: no drift introduced.
- Premature abstraction: none introduced.
- Comment / docstring drift: none introduced.
- Simplification: nothing to simplify in a one-cell table edit.
## Sr. SDET review (cycle 2 — 2026-04-29)

**Test files reviewed:** `tests/test_t15_ship.py` (cycle-2 diff only — `test_changelog_t15_entry`)
**Skipped (out of scope):** `tests/test_t13_triage.py`, `tests/test_t14_check.py`, `tests/test_t16_sweep.py` (sibling parity fix rejected as out-of-scope; intentionally unchanged)
**Verdict:** SHIP

---

### Cycle-1 FIX verification

**FIX landed correctly.**

`tests/test_t15_ship.py:301-308` now reads:

```python
unreleased_idx = content.find("[Unreleased]")
first_version_idx = content.find("\n## [0.", unreleased_idx + 1)
assert unreleased_idx != -1 and "M21 Task 15" in content[unreleased_idx:first_version_idx], (
    "CHANGELOG.md must contain a 'M21 Task 15' entry under [Unreleased]"
)
```

This matches the three-line shape required by the cycle-1 FIX recommendation exactly.

**Mutation check (mental):** CHANGELOG.md `[Unreleased]` is at line 8; `M21 Task 15` entry is at line 10; first versioned block `## [0.` appears further down. The slice `content[unreleased_idx:first_version_idx]` correctly bounds the `[Unreleased]` section. If the entry were moved under a versioned `## [0.X.Y]` block, `first_version_idx` would mark the boundary before that entry, the slice would not contain `M21 Task 15`, and the assertion would correctly fail. The fix is mutation-killing.

**pytest gate:** `runs/m21_t15/cycle_2/gate_pytest_t15.txt` — 21 passed in 0.34s. No regressions.

---

### Cycle-1 advisory items — state confirmation

**Advisory 1 — T24 docstrings claim "runbook.md":**
`tests/test_t15_ship.py:196-217` docstrings still read "AC2: runbook.md passes T24 rubric...". Unchanged from cycle 1. State: advisory track, not resolved, not regressed.

**Advisory 2 — ACs 5/6/10 not in test file:**
ACs 5, 6, and 10 remain verified by Auditor smoke commands only. Unchanged from cycle 1. State: advisory track, not resolved, not regressed.

---

### 🔴 BLOCK — tests pass for the wrong reason

None.

---

### 🟠 FIX — fix-then-ship

None. Cycle-1 FIX resolved cleanly.

---

### 🟡 Advisory — track but not blocking

Pre-existing advisories carry forward unchanged (see cycle-1 review for detail):
- T24 docstrings in `tests/test_t15_ship.py:196-217` misstate scope as "runbook.md" when both SKILL.md and runbook.md are checked.
- ACs 5/6/10 not represented in `tests/test_t15_ship.py`; consistent with sibling pattern; future test-hardening pass.

---

### What passed review (one-line per lens)

- Tests-pass-for-wrong-reason: CHANGELOG assertion now correctly enforces [Unreleased] placement; no hidden-bug cases observed.
- Coverage gaps: ACs 5/6/10 omitted — unchanged advisory; no new gaps introduced by cycle-2 changes.
- Mock overuse: no mocks; pure filesystem reads; unchanged; clean.
- Fixture / independence: no fixtures; all tests stateless on-disk readers; no bleed; unchanged; clean.
- Hermetic-vs-E2E gating: all subprocess calls local Python scripts; no network; unchanged; clean.
- Naming / assertion-message hygiene: assertion message now matches the enforcement ("must contain a 'M21 Task 15' entry under [Unreleased]"); docstring advisory pre-existing.
## Security review (cycle 2 — 2026-04-29)

Cycle 2 scope: two surgical fixes only.
1. `.claude/skills/ship/runbook.md:15` — pre-flight version-check command changed from
   `grep '^version' pyproject.toml` to `grep '^__version__' ai_workflows/__init__.py`.
2. `tests/test_t15_ship.py::test_changelog_t15_entry` — assertion tightened to slice
   `[Unreleased]`-to-first-versioned-block before checking membership.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

Both cycle-1 advisory items are unchanged in cycle 2 — they carry forward as-is.

**`SKILL.md:49` — `--yes` flag bypasses operator-approval prompt (Threat model §2 / autonomy-mode boundary)**
Unchanged from cycle 1. No new vector introduced.

**`runbook.md:71` — approval-gate display block shows unexpanded `$PYPI_TOKEN` string (Threat model §1 / logging hygiene)**
Unchanged from cycle 1. No new vector introduced.

### Cycle-2 delta findings

**`runbook.md:15` — version-grep target change (Threat model §2)**
FIX-1 changes `grep '^version' pyproject.toml` to `grep '^__version__' ai_workflows/__init__.py`.
This is a read-only grep of a tracked Python source file. No subprocess invocation change; no
shell-injection surface; no token-handling. The `ai_workflows/__init__.py` path is a fixed
literal, not user-supplied. Clean.

**`tests/test_t15_ship.py` — assertion shape tightened (no security surface)**
Test-only change. Slices the CHANGELOG string between `[Unreleased]` and `\n## [0.` before
asserting `M21 Task 15` membership. No runtime path; no subprocess invocation; no new
file access beyond what the test already opens. Clean.

### Verdict: SHIP
