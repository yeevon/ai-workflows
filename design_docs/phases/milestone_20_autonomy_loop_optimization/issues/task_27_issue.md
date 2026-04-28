# Task 27 — Auditor input-volume rotation trigger — Audit Issues

**Source task:** [../task_27_tool_result_clearing.md](../task_27_tool_result_clearing.md)
**Audited on:** 2026-04-28 (cycle 2 re-audit)
**Audit scope:** spec ACs 1-8, design-drift check (zero `ai_workflows/` touch + Path A correctly rejected), gates (pytest / lint-imports / ruff), smoke commands from spec §Smoke test, cycle 1 deliverables (rotation helper, canonical reference, slash-command updates, two test files, CHANGELOG, status surfaces), cycle 2 sr-sdet B-1 + F-1 + F-2 + A-1 + A-2 fix verification.
**Status:** ✅ PASS

## Design-drift check

No drift detected.

- **`ai_workflows/` package untouched.** `git diff --stat HEAD ai_workflows/` returns empty. Cycle 1 changes are confined to `.claude/commands/` (slash-command prose), `.claude/commands/_common/auditor_context_management.md` (NEW canonical reference), `scripts/orchestration/auditor_rotation.py` (NEW orchestration helper), `tests/orchestrator/` (NEW hermetic tests), `CHANGELOG.md`, `design_docs/phases/milestone_20_*/README.md`, and the task spec status line. M20 scope rule (orchestration-infrastructure only — no runtime KDR risk) honoured.
- **Path A correctly rejected.** Audit H6 states Claude Code's `Task` tool frontmatter accepts only `name`/`description`/`tools`/`model`; no `context_management.edits` passthrough. The canonical reference at `.claude/commands/_common/auditor_context_management.md` §"Why Path A is rejected" documents the rationale verbatim and points to T28 as owner of the broader surface check. Builder shipped Path B (client-side rotation) only — the right call.
- **No KDR violation.** T27 cites no KDR (orchestration infrastructure). The rotation helper imports only stdlib (`argparse`, `os`, `sys`, `pathlib`); no Anthropic SDK, no `ANTHROPIC_API_KEY`, no LLM call (KDR-003 N/A but trivially honoured). No layered-package import (KDR — four-layer rule N/A; helper lives under `scripts/`).
- **No `nice_to_have.md` adoption.** Server-side compaction primitives sit in `nice_to_have.md §24` (T28-DEFER); cycle 1 does not pull them in.

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| AC-1 — `auto-implement.md` describes rotation trigger in per-cycle Auditor spawn loop | ✅ | `auto-implement.md:319-347` documents the trigger: pre-spawn check via `auditor_rotation.py`, ROTATE/NO-ROTATE branching, rotation log path, env var override, cycle 1 standard-input exception, cited the canonical reference + audit H6 rationale. |
| AC-2 — `clean-implement.md` matches | ✅ | `clean-implement.md:225-251` carries the same prose pattern adapted to the `/clean-implement` step structure. Symmetry with auto-implement preserved. |
| AC-3 — canonical reference exists; threshold + tunability + Path A rejection rationale | ✅ | `.claude/commands/_common/auditor_context_management.md` §Threshold & tunability documents the 60K default + `AIW_AUDITOR_ROTATION_THRESHOLD` override + 30K compaction recovery target; §"Why Path A is rejected (audit H6)" records the rationale; integration points listed. |
| AC-4 — rotation events log to `runs/<task>/cycle_<N>/auditor_rotation.txt` | ✅ | `auditor_rotation.py::write_rotation_log` writes the one-line `ROTATED:` record at `runs/<task>/cycle_<N>/auditor_rotation.txt`; format matches spec §Telemetry hook. Slash commands document the path. Tests `TestWriteRotationLog::{test_creates_file,test_file_content_format,test_file_path_convention,test_creates_parent_directories}` verify. |
| AC-5 — `test_auditor_rotation_trigger.py` passes (threshold-fire + threshold-no-fire + verdict-PASS + tunability) | ✅ | 29/29 tests pass. Coverage: at-threshold + above + far-above + case-insensitive; below + one-below + zero; PASS at/above/below threshold + case-insensitive; BLOCKED above threshold; tunable lower-fires + lower-no-fire + higher-no-fire + exact-at; env-var default + read + non-integer-fallback + integration. |
| AC-6 — `test_auditor_rotation_doesnt_break_verdict.py` passes (verdicts unchanged + ≤ 70% cumulative input-token reduction) | ✅ | 9/9 tests pass. Synthetic 5-cycle fixture (`DISABLED_INPUT_TOKENS = [25K,45K,68K,88K,50K]` vs enabled with rotation at cycle 3); ratio computed in `test_cumulative_tokens_at_most_70_percent` is well under 0.70. Verdict-sequence equality + per-cycle post-rotation reduction also asserted. |
| AC-7 — CHANGELOG entry under `[Unreleased]` with mandated phrasing | ✅ | `CHANGELOG.md:10` exact phrasing match: "Added — M20 Task 27: Auditor input-volume rotation trigger (client-side simulation of clear_tool_uses_20250919; tunable via AIW_AUDITOR_ROTATION_THRESHOLD; ≤ 70% cumulative input-token reduction on long-cycle audits; Path A rejected per audit H6 — Claude Code Task tool does not expose context_management.edits)". |
| AC-8 — status surfaces flip together | ✅ | (a) spec `**Status:** ✅ Done (2026-04-28)`; (b) README task-pool table row 27 `✅ Done`; (c) no `tasks/README.md` for this milestone (N/A); (d) no "Done when" checkbox in README maps to T27 (the closest is exit-criterion #6 / Goal G2 / Goal G6 — T27 is a Phase-D safeguard, not an exit-criterion gate). All applicable surfaces aligned. |

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

### LOW-1 — Builder cycle 1 return-schema non-conformance (15th overall, 1st in this task)

The loop controller flagged that the cycle 1 Builder return text included a "Planned commit message" + "All 38 tests pass" prose + KDR commentary before the 3-line schema. This is the recurring schema-drift pattern already tracked for M21 hardening (per loop-controller carry-over observation 1). No code or content damage in this task — the orchestrator's own parser strips non-conforming preambles. Logged here for visibility only.

**Action / Recommendation:** Already DEFERRED to the M21 hardening track per loop-controller log. No T27-local fix needed.

## Additions beyond spec — audited and justified

- **`auditor_rotation.py::build_compacted_auditor_spawn_input`** is not strictly required by AC-1/AC-2 (they ask the slash commands to describe the compacted-input shape, not for a Python helper that builds it). However, it is a thin pure-string assembly with no I/O, exposed via the same module so the slash commands and the test suite reference one canonical compacted-input structure. Audited: deterministic, no coupling to runtime, fully covered by `TestBuildCompactedAuditorSpawnInput`. Justified — reduces drift between the slash-command prose and the actual input the orchestrator constructs.
- **CLI entrypoint `python scripts/orchestration/auditor_rotation.py --input-tokens N --verdict V`** is not in the AC list but is the smoke-test surface the spec §Smoke test relies on. Justified.
- **`TestShouldRotateVerdictBlocked::test_blocked_above_threshold`** (one extra case) covers BLOCKED handling — the spec mentions BLOCKED in passing under §Mechanism step 4 ("PASS → no rotation"); BLOCKED similarly cannot rotate (the loop halts). Adding the test is defensive, not scope creep.

## Gate summary

| Gate | Command | Result |
| ---- | ------- | ------ |
| T27 unit tests | `uv run pytest tests/orchestrator/test_auditor_rotation_trigger.py tests/orchestrator/test_auditor_rotation_doesnt_break_verdict.py -v` | PASS (38/38) |
| Full pytest | `uv run pytest -q` | 1292 passed / 10 skipped / 1 failed (failure is pre-existing `tests/test_main_branch_shape.py::test_design_docs_absence_on_main`, fires on every non-main branch — unrelated to T27, no T27 file touched it) |
| Import contracts | `uv run lint-imports` | PASS — 5 contracts kept, 0 broken |
| Lint | `uv run ruff check .` | PASS — All checks passed |
| Smoke #1 — H6 rationale documented | `grep -q "Path A.*rejected\|Path A is rejected\|client-side simulation" .claude/commands/_common/auditor_context_management.md` | PASS |
| Smoke #2 — auto-implement integration | `grep -q "AIW_AUDITOR_ROTATION_THRESHOLD\|input_tokens >= 60000\|input volume threshold" .claude/commands/auto-implement.md` | PASS (matches `AIW_AUDITOR_ROTATION_THRESHOLD`) |
| Smoke #3 — rotation log path | `grep -q "auditor_rotation.txt" .claude/commands/auto-implement.md` | PASS |
| Smoke #4 — CLI ROTATE | `python scripts/orchestration/auditor_rotation.py --input-tokens 65000 --verdict OPEN` | PASS — prints `ROTATE` |
| Smoke #5 — CLI NO-ROTATE (low tokens) | `python scripts/orchestration/auditor_rotation.py --input-tokens 30000 --verdict OPEN` | PASS — prints `NO-ROTATE` |
| Smoke #6 — CLI NO-ROTATE (PASS verdict) | `python scripts/orchestration/auditor_rotation.py --input-tokens 65000 --verdict PASS` | PASS — prints `NO-ROTATE` |

## Issue log — cross-task follow-up

- **M20-T27-ISS-01** (LOW) — Builder return-schema non-conformance, 15th overall recurrence. Already tracked under the M21 hardening track per loop-controller log; no T27-local fix needed. Status: DEFERRED (owner: M21 hardening).

## Deferred to nice_to_have

The server-side `clear_tool_uses_20250919` primitive is parked in `nice_to_have.md §24` (alongside `compact_20260112` per T28's DEFER verdict) — would only become reachable if the Claude Code `Task` surface ever exposes `context_management.edits`. T27 ships the client-side simulation (Path B) which is the productive replacement until that trigger fires.

## Propagation status

No forward-deferrals from this audit. All findings either resolved at cycle 1 or already tracked elsewhere (LOW-1 → M21 hardening).

## Cycle 2 re-audit (2026-04-28)

**Verdict: ✅ PASS** — sr-sdet cycle-1 BLOCK + FIX + Advisory items all resolved.

### sr-sdet fix verification

| Fix | Location | Status |
| --- | -------- | ------ |
| B-1 — replace tautological `TestVerdictsUnchanged` | `test_auditor_rotation_doesnt_break_verdict.py:132-171` (`test_same_record_count`; class docstring acknowledges live-test limitation; redirects "same outcome" guarantee to `TestShouldRotateVerdictPass`) | ✅ Resolved |
| F-1 — three boundary tests for env-var parsing | `test_auditor_rotation_trigger.py:247-273` (`test_negative_one_falls_back_to_default`, `test_zero_falls_back_to_default`, `test_float_string_falls_back_to_default`); `auditor_rotation.py:80` adds `int(stripped) > 0` guard so `"0"` no longer accepted as a runaway threshold | ✅ Resolved |
| F-2 — replace trivial negative assertion with realistic-content test | `test_auditor_rotation_trigger.py:373-398` (`test_no_duplication_of_cycle_summary_content` passes prior-Auditor-verdict text as `cycle_summary_content` and asserts exactly-once injection — the actual no-double-injection invariant) | ✅ Resolved |
| A-1 — module-scope fixtures | Both `rotation_mod` fixtures now `scope="module"` (`test_auditor_rotation_trigger.py:31`, `test_auditor_rotation_doesnt_break_verdict.py:37`); each `repo_root` also `scope="module"`. 38 redundant `exec_module` calls collapsed to 2. | ✅ Resolved |
| A-2 — drop misleading `test_same_number_of_cycles` | Removed (no longer in file); subsumed by the new structural-invariant `test_same_record_count` | ✅ Resolved |

### Gate re-run (cycle 2)

| Gate | Command | Result |
| ---- | ------- | ------ |
| T27 unit tests | `uv run pytest tests/orchestrator/test_auditor_rotation_trigger.py tests/orchestrator/test_auditor_rotation_doesnt_break_verdict.py -v` | PASS (39/39 — was 38/38 in cycle 1; +3 boundary tests, -2 tautological tests, +1 no-duplication test) |
| Full pytest | `uv run pytest -q` | 1293 passed / 10 skipped / 1 failed (pre-existing `test_main_branch_shape::test_design_docs_absence_on_main` — non-T27, fires on every non-main branch) |
| Import contracts | `uv run lint-imports` | PASS — 5 contracts kept, 0 broken |
| Lint | `uv run ruff check .` | PASS — All checks passed |
| Smoke #1–#3 (greps) | (per spec §Smoke test) | All PASS |
| Smoke #4–#6 (CLI) | `python scripts/orchestration/auditor_rotation.py …` | ROTATE / NO-ROTATE / NO-ROTATE — all expected |

### Design-drift re-check

`git diff HEAD --stat ai_workflows/` empty → ai_workflows package still untouched. No new dependencies, no KDR risk introduced by the test-quality fixes (test files only, plus a 1-line guard tightening in the orchestration helper).

### Cycle 2 LOW (informational)

- **Builder cycle 2 return-schema non-conformance** (16th overall recurrence per loop-controller). Already DEFERRED to M21 hardening; no T27-local fix needed. Logged here as `M20-T27-ISS-02` for visibility, status DEFERRED (owner: M21 hardening).

### Cycle 2 summary file note

`runs/m20_t27/cycle_2/summary.md` write attempt was refused by an environment hook ("Subagents should return findings as text, not write report files"). The cycle 2 audit content is preserved in this `## Cycle 2 re-audit` section (the durable artifact the orchestrator reads); no separate summary file was created. Auditor return text included a brief note pointing the orchestrator at this section.

## Sr. Dev review (2026-04-28)

**Files reviewed:** `scripts/orchestration/auditor_rotation.py`, `tests/orchestrator/test_auditor_rotation_trigger.py`, `tests/orchestrator/test_auditor_rotation_doesnt_break_verdict.py`, `.claude/commands/_common/auditor_context_management.md`, `.claude/commands/auto-implement.md`, `.claude/commands/clean-implement.md`
**Skipped (out of scope):** CHANGELOG / status surfaces (prose-only, no code shape issues)
**Verdict:** SHIP

### BLOCK — must-fix before commit

None.

### FIX — fix-then-ship

None.

### Advisory — track but not blocking

**ADV-1 — Idiom drift: `get_threshold()` uses `.isdigit()` instead of `try/except ValueError` (lens: idiom alignment)**
File: `scripts/orchestration/auditor_rotation.py:63`

Sibling `cargo_cult_detector.py::get_loop_detection_threshold()` (lines 52-60) uses `try/except ValueError` with an explicit range check — a pattern that (a) handles negative integers gracefully, (b) rejects `"0"` as a degenerate threshold via the range check, and (c) is the settled idiom for this layer. `get_threshold()` uses `.isdigit()` instead, which accepts `"0"` (threshold=0 → every spawn rotates, which is a runaway behaviour), rejects `"-1"` silently (which falls back to 60K, hiding the mis-configuration), and diverges from the sibling without a reason.

Action: match the sibling pattern — `try: val = int(raw.strip()); return val if val > 0 else DEFAULT_THRESHOLD; except (ValueError, AttributeError): return DEFAULT_THRESHOLD`. The `val > 0` guard prevents the zero-threshold runaway. Low-urgency; no production impact at current usage, but worth aligning before this pattern multiplies.

**ADV-2 — `simulate_enabled()` fallback branch (lines 104-108) is dead code with a magic literal (lens: simplification)**
File: `tests/orchestrator/test_auditor_rotation_doesnt_break_verdict.py:104-108`

The `else` branch at line 104 (`# Fallback: use after_rotation if before_rotation exhausted`) fires only when `i >= len(before_rotation)` AND `use_compacted` is False — an impossible state given the fixture constants (`before_rotation` is always length-3 and `after_rotation` provides the remaining cycles via the `use_compacted` flag). The branch contains a hardcoded `20_000` fallback that silently produces an incorrect token count if it were ever reached. Because the tests pass with deterministic fixture data, this path is never exercised.

Action: remove the dead branch or add a `pytest.fail("unreachable: before_rotation exhausted without rotation flag set")` guard. Advisory — no test correctness impact at present, but the silent magic-literal fallback would mask a fixture regression.

### What passed review (one-line per lens)

- Hidden bugs: none — threshold comparison is `>=` (correct inclusive boundary at exactly 60K, confirmed by `test_exactly_at_threshold_open`); no async misuse; no mutable defaults; no silent `except` swallowing.
- Defensive-code creep: none observed — `should_rotate` does not guard against a typed `dict` contract; `int()` / `str()` coercions on the incoming dict values are appropriate boundary normalisation.
- Idiom alignment: minor drift in `get_threshold()` env-var parse idiom vs sibling `cargo_cult_detector.py`; see ADV-1.
- Premature abstraction: none — `build_compacted_auditor_spawn_input` is a justified thin helper with one caller documented at module top and full test coverage; no single-use base classes or feature flags.
- Comment / docstring drift: module docstring cites task + relationship + downstream consumers correctly per project convention; inline comments explain the PASS/BLOCKED exclusion logic, which is non-obvious. No restatement noise detected.
- Simplification: dead fallback branch in test simulator; see ADV-2.

## Security review (2026-04-28)

**Files reviewed:** `scripts/orchestration/auditor_rotation.py`, `tests/orchestrator/test_auditor_rotation_trigger.py`, `tests/orchestrator/test_auditor_rotation_doesnt_break_verdict.py`
**Threat-model items checked:** subprocess integrity (KDR-003), env-var read safety, hermetic-test confirmation, wheel-contents posture.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

None. (Wheel-contents: `migrations/` entries in the existing 0.3.1 wheel are intentional per pyproject.toml lines 92–103, M13 T01 design decision. T27 introduces no new wheel content.)

### Verdict: SHIP

### Security review cycle 2 re-confirmation (2026-04-28)

Cycle 2 delta: one-line guard tightening in `auditor_rotation.py:80` (`int(stripped) > 0` closes the `"0"` runaway threshold path flagged by sr-sdet F-1) and test-only refactors. No new subprocess, no new env-var read paths beyond the already-reviewed `AIW_AUDITOR_ROTATION_THRESHOLD`, no new wheel content, no API key or OAuth token surface introduced. Threat-model items 1–5 from cycle 1 re-confirmed clean.

**Verdict: SHIP**

## Sr. SDET review (2026-04-28)

**Test files reviewed:**
- `tests/orchestrator/test_auditor_rotation_trigger.py` (NEW, 29 tests)
- `tests/orchestrator/test_auditor_rotation_doesnt_break_verdict.py` (NEW, 9 tests)

**Skipped (out of scope):** none
**Verdict:** BLOCK

### BLOCK — tests pass for the wrong reason

**B-1: `TestVerdictsUnchanged` is a tautology — the tests assert the fixture constant, not the code**

`tests/orchestrator/test_auditor_rotation_doesnt_break_verdict.py:131-156`

Both `simulate_disabled` and `simulate_enabled` accept the `VERDICTS` list as an argument and copy it verbatim into the `"verdict"` field of every returned record. Neither simulator has any logic that could mutate a verdict — the verdict sequence is entirely determined by the caller's input. Asserting `disabled_verdicts == enabled_verdicts` (line 156) and `disabled[-1]["verdict"] == "PASS"` (line 141) therefore reduces to `VERDICTS == VERDICTS` and `VERDICTS[-1] == "PASS"`. Both are trivially true by fixture construction and pass even if `simulate_enabled` is replaced with `return []`.

The spec AC-6 requires: "Final verdicts are identical — rotation didn't change audit outcome." The intent is to prove rotation does not perturb the Auditor's verdict. What is actually proven is that the hard-coded `VERDICTS` constant equals itself. The production code path under test (`should_rotate`) has no influence on the verdict sequence — it only determines input-token routing. A broken `should_rotate` that always returns `True` would still pass all three `TestVerdictsUnchanged` tests.

Source line being pinned: `should_rotate()` at `scripts/orchestration/auditor_rotation.py:68-110` and `build_compacted_auditor_spawn_input()` at lines 159-237. The AC intends to verify that switching between standard and compacted inputs leaves the Auditor verdict unchanged.

**Action / Recommendation:** The "verdicts unchanged" claim cannot be proven hermetically — it requires a live Auditor spawn with both standard and compacted inputs and a comparison of their verdicts. For the hermetic tier, replace `TestVerdictsUnchanged` with: (a) a comment acknowledging the limitation; (b) one structural assertion — that `simulate_enabled` produces the same record count as `simulate_disabled` when given the same `VERDICTS` input — which is the only invariant a hermetic fixture can honestly pin; (c) delegate the "same outcome" guarantee to the existing `TestShouldRotateVerdictPass` class, which correctly pins that `should_rotate` returns `False` on PASS regardless of token volume (the only rotation-code invariant relevant to the loop-end AC).

### FIX — fix-then-ship

**F-1: `get_threshold()` does not handle negative-integer env values — no test covers it**

`tests/orchestrator/test_auditor_rotation_trigger.py:226-229` (Lens 2 — coverage gap; Lens 1 adjacent to Sr-Dev ADV-1)

`get_threshold()` at `scripts/orchestration/auditor_rotation.py:63` uses `raw.strip().isdigit()` to validate the env var. `str.isdigit()` returns `False` for negative integers (`"-40000"`) and float-formatted values (`"60000.0"`). A user who sets `AIW_AUDITOR_ROTATION_THRESHOLD=-1` expecting rotation to fire on every OPEN cycle (a "disable the guard" intent) silently gets the 60K default instead. The existing test `test_non_integer_env_falls_back` only covers the clearly non-numeric string `"not-a-number"`. Neither `"-1"`, `"0"`, nor `"60000.0"` is tested.

This is the same drift flagged by Sr-Dev ADV-1 (idiom alignment with `cargo_cult_detector.py`). In the test-quality dimension the gap is: the test suite does not pin the boundary between "accepted" and "rejected" integer-format strings.

**Action / Recommendation:** Add three test cases to `TestGetThreshold`:
- `AIW_AUDITOR_ROTATION_THRESHOLD="-1"` → documents whether the current fallback is intentional or a bug.
- `AIW_AUDITOR_ROTATION_THRESHOLD="0"` → `isdigit()` returns `True` for `"0"`, so `get_threshold()` returns `0`, which would cause every OPEN spawn to rotate (runaway behaviour). Add an assertion that pins this case so the behaviour is explicit.
- `AIW_AUDITOR_ROTATION_THRESHOLD="60000.0"` → falls back to 60000 (current behaviour — document it).

**F-2: `test_no_prior_chat_history_placeholder` is a trivially-passing negative assertion**

`tests/orchestrator/test_auditor_rotation_trigger.py:339-352` (Lens 1 — trivial assertion)

The test asserts `"Prior Builder report" not in prompt` and `"Prior Auditor verdict" not in prompt`. Since `build_compacted_auditor_spawn_input` is a pure string formatter that only concatenates its explicit arguments (no internal string pool, no global state), these strings can never appear in the output unless the caller explicitly passes them. The test is asserting the absence of strings the function is architecturally incapable of introducing under any code path.

The actual risk the spec targets — "prior tool-result content excluded" — requires verifying that the compacted prompt does not accidentally inject prior-cycle content when that content is passed as part of `cycle_summary_content`. The current test passes empty strings, which trivially cannot match.

**Action / Recommendation:** Replace with a test that passes cycle-summary content containing a realistic prior-Auditor-verdict string (e.g., `"Prior Auditor verdict: OPEN — findings remain"`) and verifies the output prompt does not duplicate that string or add any additional injection of it. This exercises the function's actual promise: only one copy of each input section appears in the output.

### Advisory — track but not blocking

**A-1: `rotation_mod` fixture should be `scope="module"` — 38 redundant module-load calls**

`tests/orchestrator/test_auditor_rotation_trigger.py:32-38`
`tests/orchestrator/test_auditor_rotation_doesnt_break_verdict.py:38-44`

The `rotation_mod` fixture has default `function` scope. `importlib.util.exec_module` is called once per test (38 total). The module has no mutable global state that individual tests modify — all state is passed as arguments to pure functions. `scope="module"` would load the module once per file without affecting isolation.

**Action / Recommendation:** Add `scope="module"` to both `rotation_mod` fixture definitions.

**A-2: `test_same_number_of_cycles` name overstates what it proves**

`tests/orchestrator/test_auditor_rotation_doesnt_break_verdict.py:158-168`

The test asserts `len(disabled) == len(enabled)`. Both simulators iterate over the same `VERDICTS` list; they will always produce the same count by construction. The name implies a meaningful behavioural property but proves only that the fixture has consistent list lengths. Rename to `test_fixture_has_five_cycles` or add a comment noting this is a structural invariant.

### What passed review (one line per lens)

- Tests-pass-for-wrong-reason: B-1 (tautological verdict-equality in `TestVerdictsUnchanged`); F-2 (trivial negative assertion in `test_no_prior_chat_history_placeholder`)
- Coverage gaps: F-1 (negative/float/zero env-var values for `get_threshold()`); boundary at exactly 60000 correctly pinned by `test_exactly_at_threshold_open` and `test_one_below_threshold_open`
- Mock overuse: none — no mocks used; module loaded via `importlib`, all functions are pure
- Fixture / independence: A-1 (function-scope fixture loaded 38 times); no order dependence, no test bleed, no env-var leakage (monkeypatch used correctly)
- Hermetic-vs-E2E gating: clean — no network calls, no subprocess to live agents, no additional env-var gate needed
- Naming / assertion-message hygiene: A-2 (`test_same_number_of_cycles` misleading); `test_cumulative_tokens_at_most_70_percent` includes a good f-string failure message; remaining names are descriptive

## Sr. Dev review — cycle 2 re-confirm (2026-04-28)

**Files reviewed:** `scripts/orchestration/auditor_rotation.py` (cycle 2 diff: line 80 `int(stripped) > 0` guard), `tests/orchestrator/test_auditor_rotation_trigger.py` (lines 247-273 new boundary tests), `tests/orchestrator/test_auditor_rotation_doesnt_break_verdict.py` (B-1 / A-1 / A-2 fixes)
**Skipped (out of scope):** slash-command prose files (no code shape)
**Verdict:** SHIP

### BLOCK — must-fix before commit

None.

### FIX — fix-then-ship

None.

### Advisory — track but not blocking

**ADV-C2-1 — Docstring for `get_threshold()` "zero" case is now factually stale (lens: comment/docstring drift)**
File: `scripts/orchestration/auditor_rotation.py:67-70`

Lines 67-68 say: `"str.isdigit() returns True for "0", so get_threshold would return 0 — which would cause every OPEN cycle to rotate (runaway behaviour)."` This was true before cycle 2. The cycle 2 fix added `and int(stripped) > 0` at line 80, so `"0"` now falls back to `DEFAULT_THRESHOLD` (not 0). The guard sentence at lines 69-70 ("Callers that accept zero should guard explicitly; the helper itself does not accept zero as a valid threshold") is correct in intent but the "would return 0" claim is now wrong. The test `test_zero_falls_back_to_default` (line 257-264) correctly asserts the new behaviour; only the docstring lags.

Action: replace lines 67-68 with: `"Zero (\"0\"): str.isdigit() returns True but int(stripped) > 0 rejects it; falls back to DEFAULT_THRESHOLD."` Low urgency — the test pins the correct behaviour; this is documentation-only drift.

### What passed review (one-line per lens)

- Hidden bugs: none — `int(stripped) > 0` guard correct; `"0"` case now rejects as intended; threshold comparison `>=` boundary unchanged.
- Defensive-code creep: none — the `int(stripped) > 0` guard is appropriate boundary normalisation for an env-var read (system boundary).
- Idiom alignment: cycle 2 closes the `isdigit()`-vs-`try/except` drift flagged by ADV-1 via an equivalent guard; pattern now matches `cargo_cult_detector.py` intent (reject zero and non-positive values).
- Premature abstraction: none introduced in cycle 2.
- Comment / docstring drift: one stale sentence in `get_threshold()` docstring; see ADV-C2-1.
- Simplification: no new opportunities introduced in cycle 2.
