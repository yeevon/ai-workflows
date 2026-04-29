# Task 23 — Cache-breakpoint discipline — Audit Issues

**Source task:** [../task_23_cache_breakpoint_discipline.md](../task_23_cache_breakpoint_discipline.md)
**Audited on:** 2026-04-28 (cycle 2 re-audit appended)
**Audit scope:** cycle 1 (Builder + Auditor) + cycle 2 (re-audit after sr-dev FIX-1/FIX-2 + sr-sdet FIX-1/FIX-2/FIX-3 fixes); orchestration-infrastructure task — `.claude/commands/_common/spawn_prompt_template.md` extension, `scripts/orchestration/cache_verify.py` harness (NEW), `auto-implement.md` integration, two hermetic test modules (NEW), CHANGELOG entry, status-surface flip, AC-7 explicit deferral with operator runbook.
**Status:** ✅ PASS (cycle 2)

---

## Design-drift check

No drift detected.

- **`ai_workflows/` untouched.** `git status --short` confirms only `.claude/`, `scripts/orchestration/cache_verify.py`, `tests/orchestrator/`, `CHANGELOG.md`, `runs/cache_verification/methodology.md`, and milestone docs were modified. Zero package-runtime code crosses the orchestration→runtime boundary.
- **Layer rule (`primitives → graph → workflows → surfaces`).** `uv run lint-imports` re-run from scratch — 5 contracts kept, 0 broken.
- **Seven load-bearing KDRs.** Spec cites no specific KDR (consistent with the milestone scope-note: M20 reshapes the autonomy loop, not the runtime). Verification confirms:
  - KDR-002 (MCP surface) — untouched.
  - KDR-003 (no Anthropic API) — `cache_verify.py` reads JSON telemetry records only; no `anthropic` SDK import; no `ANTHROPIC_API_KEY` read; no `claude` subprocess spawn from inside the harness (real-run mode prints an operator runbook rather than invoking `claude`, explicitly to avoid recursive-subprocess confound).
  - KDR-004 / 006 / 008 / 009 / 013 — n/a; no runtime-graph or storage code touched.
- **Stable-prefix discipline rules added to `_common/spawn_prompt_template.md`** sit in the same `_common/` scaffold T02 / T03 created. No new module, no new boundary, no new dependency. Markdown-prose extension only.
- **`scripts/orchestration/`** is the existing orchestration-script tree (T06 study harness, T22 telemetry). Not part of the `ai_workflows/` package; not subject to layer contracts.

---

## AC grading

| AC | Status | Notes |
|---|---|---|
| AC-1: `spawn_prompt_template.md` has §Stable-prefix discipline | ✅ MET | Section present (lines 169–259); four rules enumerated (no per-request strings, fixed tool list, byte-identical system prompt, `\n\n` boundary); verification harness referenced. Cites the four anthropics/claude-code issues from the spec grounding. |
| AC-2: `scripts/orchestration/cache_verify.py` with 2-call harness | ✅ MET | Module loads via `importlib`; exposes `verify_cache_discipline(record1, record2)` core logic + `run_dry_run` CLI helper; exit codes 0=PASS / 1=SKIP / 2=FAIL / 3=ERROR; `--dry-run` flag for hermetic execution; 5-min TTL constant; 80% threshold constant; module docstring documents AC-7 deferral inline. |
| AC-3: `auto-implement.md` invokes the verifier | ✅ MET | §Cache-breakpoint verification section (lines 35–76) describes the dry-run CLI form for builder + auditor, output location (`runs/<task>/cache_verification.txt`), halt surface (🚧 marker on FAIL exit 2), and explicit operator-resume framing. Per-cycle vs operator-resume framing is correct: 2 consecutive telemetry records are needed before the verifier is meaningful. |
| AC-4: Halt-surface fires on prefix-instability | ✅ MET | Hermetic test `test_fail_message_contains_high_finding_marker` asserts `🚧` in FAIL message; `test_dry_run_output_contains_fail_status_and_high_marker` asserts the marker reaches `cache_verification.txt`; `test_fail_message_references_stable_prefix_discipline` confirms the message points operators to `spawn_prompt_template.md`. Exit code 2 mapping verified by `test_dry_run_fail_exits_2`. |
| AC-5: `test_cache_breakpoint_verification.py` passes | ✅ MET | 19 tests in test class trio (`TestVerifyCacheDiscipline`, `TestVerificationResultToText`, `TestRunDryRun`); covers PASS / FAIL / SKIP / ERROR paths, exact-80% boundary (PASS), 79.9% (FAIL), TTL boundary at exactly 300 s (SKIP), `None` timestamps (no-skip path), missing `cache_creation` (ERROR), missing record file (exit 3). All passing in re-run. |
| AC-6: `test_stable_prefix_construction.py` passes | ✅ MET | 14 tests across `TestBuilderSpawnPromptStablePrefix`, `TestAuditorSpawnPromptStablePrefix`, `TestReviewerSpawnPromptStablePrefix`, `TestPerCallValueIsolation`, `TestSpawnPromptTemplateRules`. Covers ISO-timestamp / UUID / hostname absence in prefix segment, `\n\n` boundary present in all five prompt builders, byte-identical-prefix invariant under varying dynamic context. All passing. |
| AC-7: Empirical validation (M12 T01 re-run, > 80% on call 2) | ⏸ DEFERRED | Explicit operator-resume deferral. Methodology stub at `runs/cache_verification/methodology.md` names exact operator commands (telemetry spawn + complete + verifier dry-run). Rationale (recursive-subprocess + TTL fragility + telemetry attribution conflict) parallels M20 T06 L5 precedent. CHANGELOG and issue file both flag the deferral; AC-7 is **not silently skipped** — it is named, scoped, and bounded with a runbook. |
| AC-8: CHANGELOG.md updated | ✅ MET | `[Unreleased]` entry (lines 10–58) headline matches spec verbatim ("addresses anthropics/claude-code #27048/#34629/#42338/#43657 5–20× session-cost blowup failure mode"); files-touched list complete; AC-by-AC status table; deviations section flags the AC-7 deferral. |
| AC-9: Status surfaces aligned | ✅ MET | Three surfaces concur: (a) spec line 3 `Status: ✅ Done (2026-04-28)`; (b) README task-table row 134 `✅ Done`; (c) README exit criterion #11 (line 60) `✅ (G6) … [T23 Done — 2026-04-28]`. No `tasks/README.md` for this milestone (correctly absent). No "Done when" checkbox in README that this task satisfies independently. |

**Result:** 8 / 9 ACs MET; AC-7 explicitly DEFERRED with operator runbook (per task brief §For AC-7 instruction). All test gates pass; lint and ruff pass; no drift.

---

## Gate summary

| Gate | Command | Result |
|---|---|---|
| Pytest (T23 tests only) | `uv run pytest tests/orchestrator/test_cache_breakpoint_verification.py tests/orchestrator/test_stable_prefix_construction.py -q` | ✅ 40 passed |
| Pytest (full suite) | `uv run pytest -q` | ⚠ 1 failed / 1248 passed / 10 skipped — failure is `tests/test_main_branch_shape.py::test_design_docs_absence_on_main`, the pre-existing LOW-3 environmental gate that asserts `design_docs/` absent on `main` (we are on `workflow_optimization`, design_branch override per project context). Not introduced by T23; carried from prior cycles. |
| Lint-imports | `uv run lint-imports` | ✅ 5 contracts kept, 0 broken |
| Ruff | `uv run ruff check` | ✅ All checks passed |
| Smoke (spec-named) | `test -f scripts/orchestration/cache_verify.py && grep -q "Stable-prefix discipline" .claude/commands/_common/spawn_prompt_template.md && grep -q "cache_verify.py" .claude/commands/auto-implement.md` | ✅ All three checks pass |

---

## Critical sweep

- **No silently-skipped deliverables.** AC-7 is explicitly named in the issue file, the CHANGELOG, the methodology stub, and the auto-implement.md integration. It is bounded by operator runbook. The deferral matches the established M20 T06 L5 precedent — not a novel pattern invented mid-cycle.
- **No additions beyond spec.** Files touched are exactly the ones the spec listed plus `runs/cache_verification/methodology.md` (which the spec implies via the `runs/<task>/cache_verification.txt` logging deliverable + the AC-7 operator-resume framing the orchestrator brief named).
- **No test gaps.** Both test modules exercise the full state-machine of the verifier (PASS / FAIL / SKIP / ERROR + boundary cases) and the structural rules of the discipline (no per-request strings in prefix, `\n\n` boundary, byte-identical-prefix invariant). The "spawn 2 cache_read_input_tokens > 80% of stable-prefix" assertion is tested both directly (exact-80%, exact-79.9%, broken cache → FAIL) and indirectly via the `run_dry_run` exit-code tests.
- **No doc drift.** `architecture.md`, `docs/`, README do not reference cache-breakpoint discipline outside the milestone-20 scope, so no propagation needed elsewhere.
- **No status-surface drift.** Three surfaces flip together; verified by direct read.
- **No secrets shortcuts.** `cache_verify.py` reads only local JSON telemetry; no API keys, no environment-variable secret reads.
- **No nice_to_have.md scope creep.** Cache-breakpoint discipline is the spec's headline; no out-of-scope expansion.
- **No silent architecture drift.** `ai_workflows/` untouched; verified by `git status` + drift check above.

### Telemetry-test edge case worth noting (LOW)

`test_dry_run_output_contains_fail_status_and_high_marker` asserts `"🚧"` is present in the report file — but the underlying `to_text()` method renders `Message:` directly so the marker survives. Worth confirming on the next CI run that the file's encoding (`encoding="utf-8"`) preserves the emoji round-trip; this run on the local filesystem confirmed it does. Not a blocker — flagging for forward awareness if CI runners ever change locale.

---

## Loop-controller carry-over (received from invoker)

The invoker surfaced two cross-cutting LOW observations from the Builder cycle 1 return:

1. **LOW: Builder return-schema non-conformance — recurrence #13 (1st in this task).** Builder's return text included a "Planned commit message" block before the 3-line schema. Forward-deferred to the M21 hardening track per invoker instruction.
2. **LOW: Builder pre-stamped "Auditor verdict: ✅ PASS"** in the planned commit message before the Auditor (this audit) ran. Recurrence of the M20 T06 LOW-1 pattern (Builder writing decisions on behalf of orchestrator/auditor). Forward-deferred to the same M21 hardening track.

**Action / Recommendation:** Both findings are agent-prompt issues, not T23 implementation issues. The invoker has accepted ownership for the M21 hardening track. No action required from this audit beyond logging.

---

## Deferred to nice_to_have

None. AC-7's deferral is to operator-resume (with a concrete runbook), not to `nice_to_have.md`. The empirical validation has a real owner (operator) and a real trigger (next time M12 T01 audit is run manually outside autopilot).

---

## Propagation status

No forward-deferral to other tasks. AC-7 is operator-owned via the methodology stub; M21 hardening track owns the two Builder-prompt LOWs surfaced by the invoker.

---

## Issue log — cross-task follow-up

| ID | Severity | Description | Owner / Next touch | Status |
|---|---|---|---|---|
| M20-T23-ISS-01 | LOW | Builder return text included "Planned commit message" prologue ahead of the 3-line schema (recurrence #13) | M21 hardening track | OPEN — forwarded by invoker |
| M20-T23-ISS-02 | LOW | Builder pre-stamped "Auditor verdict: ✅ PASS" inside its planned commit message (recurrence of M20-T06 LOW-1 pattern) | M21 hardening track | OPEN — forwarded by invoker |
| AC-7 deferral | DEFERRED (operator-resume) | Empirical M12 T01 re-run with > 80% cache-read-on-call-2 assertion | Operator (outside autopilot) | DEFERRED — runbook at `runs/cache_verification/methodology.md` |

---

## Sr. Dev review (2026-04-28)

**Files reviewed:** `scripts/orchestration/cache_verify.py`, `tests/orchestrator/test_cache_breakpoint_verification.py`, `tests/orchestrator/test_stable_prefix_construction.py`, `.claude/commands/_common/spawn_prompt_template.md`, `.claude/commands/auto-implement.md`, `runs/cache_verification/methodology.md`
**Skipped (out of scope):** none
**Verdict:** FIX-THEN-SHIP

### BLOCK — must-fix before commit

None.

### FIX — fix-then-ship

**FIX-1 — Hidden bug: missing `cache_read_input_tokens` in record2 produces a misleading FAIL**
`cache_verify.py` line 296: `read2: int = s2_read if s2_read is not None else 0` silently coerces a missing field to 0. If `cache_read_input_tokens` is absent from record2 (key not present — a plausible gap in a partially-written T22 record, or a schema mismatch), `ratio` becomes 0.0 and the function returns FAIL with message "spawn 2 read 0 / N tokens (0.0% < 80%)". The report gives no indication the field was absent rather than genuinely zero. An operator would halt the autopilot chasing a phantom cache regression.
Action: Before step 3, check `if s2_read is None and "cache_read_input_tokens" not in record2` and return ERROR with a message distinguishing "field absent" from "field present and zero". Alternatively, add a helper `_require_field(record, key)` that raises `ValueError` (caught by `run_dry_run`'s existing `except ValueError`) rather than silently defaulting.

**FIX-2 — Hidden bug: `to_text` silently suppresses the hit-ratio line when `stable_prefix_tokens == 0`**
`cache_verify.py` line 220: `if self.stable_prefix_tokens and self.spawn2_cache_read is not None` uses a truthy int check. When `stable_prefix_tokens` is `0` (set to `s1_creation` on the SKIP path at line 273, where `s1_creation` could be 0 if the spawn-1 record had `cache_creation_input_tokens: 0`), the ratio line is silently omitted from the report. The SKIP path sets `stable_prefix_tokens=s1_creation` unconditionally; the SKIP gate fires before the `if not s1_creation` guard, so 0 can reach this branch.
Action: Replace the truthy check with `if self.stable_prefix_tokens is not None and self.spawn2_cache_read is not None`.

### Advisory — track but not blocking

**ADV-1 — `_read_record` duplicated between `cache_verify.py` and `telemetry.py`**
Both scripts define a local `_read_record(path: Path) -> dict` with nearly identical semantics. `scripts/orchestration/` is not a package so a shared import is awkward, but the duplication will drift (e.g. telemetry.py returns `{}` on missing file; cache_verify.py raises `FileNotFoundError`). Worth noting for the M21 scripts-as-package consideration.
Recommendation: Track in nice_to_have or M21 scripts-packaging task; not a bug.

**ADV-2 — `_build_parser` docstring restates type info already in the signature**
`cache_verify.py` line 443–448: `Returns: Configured ArgumentParser` is pure type-restatement. One line "Build and return the CLI argument parser" suffices per CLAUDE.md docstring discipline.

### What passed review (one-line per lens)

- Hidden bugs: Two findings above (FIX-1: missing s2 field → false FAIL; FIX-2: truthy int check → suppressed ratio line).
- Defensive-code creep: None observed; the `if not s1_creation` guard at step 2 is correct domain logic, not defensive creep.
- Idiom alignment: `structlog` not applicable (scripts/ layer); `Path`/`json`/`argparse` usage matches `telemetry.py` sibling; `importlib.util` test-loading pattern matches other scripts-test modules in the repo.
- Premature abstraction: None; `VerificationResult` serves the harness, tests, and report rendering — exactly three callers, right at the threshold.
- Comment / docstring drift: ADV-2 above; otherwise module-level docstring is exemplary (cites task, relationship, background, CLI examples, exit codes, AC-7 deferral rationale).
- Simplification: None observed; state machine is flat and readable.

---

## Sr. Dev review — cycle 2 re-confirmation (2026-04-28)

**Files reviewed:** `scripts/orchestration/cache_verify.py` (cycle-2 delta only — lines 220, 294–312)
**Skipped (out of scope):** all files unchanged from cycle 1
**Verdict:** SHIP

### BLOCK — must-fix before commit

None.

### FIX — fix-then-ship

None. Both cycle-1 FIX findings are resolved.

### Advisory — track but not blocking

None new. ADV-1 and ADV-2 from cycle 1 remain open and carry forward to the M21 track as previously noted.

### What passed review (one-line per lens)

- Hidden bugs: FIX-1 resolved — key-absent vs zero-value now returns ERROR at line 298 with a distinguishing message; FIX-2 resolved — `is not None` guard at line 220 replaces truthy int check. The residual `read2 = s2_read if s2_read is not None else 0` at line 314 is now only reachable when the key is present, making the coercion semantically correct.
- Defensive-code creep: None introduced; the ERROR branch is the correct domain response to a schema gap, not defensive creep.
- Idiom alignment: No drift.
- Premature abstraction: None.
- Comment / docstring drift: New inline comment at line 295-297 correctly explains the FIX-1 rationale (why ERROR vs FAIL) — meets the "why is non-obvious" bar.
- Simplification: No new complexity; control-flow is flatter post-fix (early-return ERROR before the ratio path).

---

## Sr. SDET review (2026-04-28)

**Test files reviewed:**
- `tests/orchestrator/test_cache_breakpoint_verification.py` (NEW, 19 tests)
- `tests/orchestrator/test_stable_prefix_construction.py` (NEW, 14 tests)
- `scripts/orchestration/cache_verify.py` (source under test, NEW)
- `tests/orchestrator/_helpers.py` (spawn-prompt builders exercised by prefix tests)

**Skipped (out of scope):** All pre-existing orchestrator test files not touched by T23.

**Verdict:** FIX-THEN-SHIP

### BLOCK — tests pass for the wrong reason

None observed.

### FIX — fix-then-ship

**FIX-1 — Tautological assertion in `test_rule1_no_per_request_strings_in_builder_prefix`**
Lens 1 (wrong granularity — assertion passes regardless of whether the rule is enforced).

`tests/orchestrator/test_stable_prefix_construction.py:334-348`

The test calls `build_builder_spawn_prompt(...)`, which returns a prompt already containing its own internal `\n\n` separators. The test then appends `"\n\n## Run ID\n{run_uuid}"` after that prompt. `_stable_prefix()` splits on the *first* `\n\n` found — which is the one inside the builder's own output, not the boundary before the appended UUID section. So `run_uuid not in prefix` passes trivially because the UUID appears after the first-split point regardless of what the builder puts in its own prefix.

This test does not prove that the builder's own stable prefix (before its first `\n\n`) is free of per-request strings. It would pass even if the builder emitted an ISO timestamp before its own first `\n\n`.

The correct coverage for Rule 1 already exists in `TestBuilderSpawnPromptStablePrefix` (lines 112-162). The `test_rule1` test in `TestSpawnPromptTemplateRules` should be rewritten to add genuinely new coverage — for example, verifying Rule 1 on `build_task_analyzer_spawn_prompt` and `build_roadmap_selector_spawn_prompt`, which the `TestBuilderSpawnPromptStablePrefix` class does not cover.

Action: Rewrite `test_rule1_no_per_request_strings_in_builder_prefix` to call `_stable_prefix(prompt)` on the raw builder output (no appended section), and extend coverage to task-analyzer and roadmap-selector builders. The current test in its existing form gives false confidence.

**FIX-2 — Byte-stability test exercises only the test's own construction helper, not the real builders**
Lens 1 (wrong granularity — testing test infrastructure rather than production code).

`tests/orchestrator/test_stable_prefix_construction.py:300-314`

`test_two_prompts_with_same_stable_prefix_are_byte_identical_in_prefix` calls `_build_prompt_with_dynamic_context` — a test-internal method that performs `stable + "\n\n" + dynamic`. It does not call any of the five real `build_*_spawn_prompt` functions. The assertion proves that string concatenation is self-consistent — not that the real builders produce byte-identical prefixes across calls with varying dynamic context.

Action: Add a companion test that calls `build_builder_spawn_prompt(...)` twice with the same arguments (or with the same static brief and different caller-supplied dynamic paths) and asserts `_stable_prefix(call1) == _stable_prefix(call2)`. Repeat for `build_auditor_spawn_prompt`. This pins the actual byte-stability property the cache discipline depends on.

**FIX-3 — Missing edge case: `cache_read_input_tokens` key entirely absent from record2**
Lens 2 (coverage gap within scope).

`tests/orchestrator/test_cache_breakpoint_verification.py` — no test for this path.

`cache_verify.py:258,296`: When `cache_read_input_tokens` is absent from record2 (key not present, not just None or 0), `record2.get(...)` returns `None` which coerces to `read2 = 0` → FAIL. This is the same outcome as "explicit zero", but the causes are distinct: a missing key could indicate a T22 schema mismatch or a partially-written record, not a genuine cache miss. The test suite covers explicit-zero and explicit-None for record2, but not a missing key. (The sr-dev reviewer noted the same gap from the source-code side; this finding confirms the test gap.)

Action: Add `_SPAWN2_MISSING_READ_KEY = {k: v for k, v in _SPAWN2_GOOD.items() if k != "cache_read_input_tokens"}` fixture and assert `verify_cache_discipline(_SPAWN1_GOOD, _SPAWN2_MISSING_READ_KEY).status == "FAIL"` (or "ERROR" if the source is updated per sr-dev FIX-1 to distinguish the case).

### Advisory — track but not blocking

**ADV-1 — Test name says "boundary is exclusive" but code uses `>=` (inclusive at exactly 300 s)**
Lens 6 (naming hygiene).

`tests/orchestrator/test_cache_breakpoint_verification.py:157-166`

`test_skip_ttl_boundary_exactly_at_limit` docstring says "boundary is exclusive" but `cache_verify.py:263` uses `elapsed >= CACHE_TTL_SECONDS` — meaning elapsed == 300 s produces SKIP (inclusive). The assertion is correct; the docstring word "exclusive" is wrong. Reword docstring to "elapsed == TTL → SKIP (inclusive ge boundary)."

**ADV-2 — Hostname bypass silently disables the test on Docker/CI runners where hostname == "localhost"**
Lens 2 (advisory — coverage gap on common CI environment).

`tests/orchestrator/test_stable_prefix_construction.py:147-149`

When `_HOSTNAME in ("localhost", "")` the hostname assertion is skipped entirely. Container runtimes commonly assign "localhost" or a numeric container ID. The spec says "no hostname in prefix" unconditionally. Consider verifying that the builder helpers never call `socket.gethostname()` at module load time by constructing the prompt and checking for a hardcoded representative hostname string, rather than relying on the runtime host name being non-trivial.

### What passed review (one line per lens)

- Tests-pass-for-wrong-reason: FIX-1 and FIX-2 above. No BLOCK-severity hidden bug found (production logic is correct); the defects reduce the confidence level of passing tests for two specific ACs.
- Coverage gaps: FIX-3 (missing-key path for cache_read in record2); ADV-2 (hostname bypass on localhost CI runners).
- Mock overuse: None. No mocks used. All inputs are real dicts fed to the real `cache_verify.py` functions; prompt-builder tests use the real helpers. Clean.
- Fixture / independence: No order dependence, no module-level state mutation, no env-var leakage, correct `tmp_path` use throughout. Independent across classes.
- Hermetic-vs-E2E gating: No network calls, no subprocess spawns. Both files are fully hermetic; no `AIW_E2E=1` gate needed or missing.
- Naming / assertion-message hygiene: ADV-1 (docstring says "exclusive" for an inclusive boundary). All other test names are specific and descriptive. Assertion messages present on key structural checks.

---

## Cycle 2 re-audit (2026-04-28)

**Trigger:** sr-dev FIX-1 + FIX-2 + sr-sdet FIX-1 + FIX-2 + FIX-3 (and ADV-1 / ADV-2 hardening) applied by Builder cycle 2.

**Verification — all 5 FIXes hold:**

| Fix | Location | Status |
|---|---|---|
| sr-dev FIX-1 — key-absent ERROR distinct from zero-value FAIL | `scripts/orchestration/cache_verify.py:298` (ERROR branch with explicit "missing the 'cache_read_input_tokens' field entirely" message) | ✅ Applied |
| sr-dev FIX-2 — `is not None` instead of truthy int check | `scripts/orchestration/cache_verify.py:220` (`if self.stable_prefix_tokens is not None and self.spawn2_cache_read is not None`) | ✅ Applied |
| sr-sdet FIX-1 — test_rule1 rewritten + extended | `tests/orchestrator/test_stable_prefix_construction.py:406` (rewritten to call `_stable_prefix(prompt)` on raw builder), `:428` task-analyzer, `:446` roadmap-selector | ✅ Applied |
| sr-sdet FIX-2 — real-builder byte-stability companions | `tests/orchestrator/test_stable_prefix_construction.py:344` (`test_real_builder_prefix_is_byte_identical_across_two_calls`), `:365` (`test_real_auditor_prefix_is_byte_identical_across_two_calls`) | ✅ Applied |
| sr-sdet FIX-3 — absent-key test | `tests/orchestrator/test_cache_breakpoint_verification.py:214` (`test_spawn2_missing_cache_read_input_tokens_key_returns_error`) | ✅ Applied |
| sr-sdet ADV-1 — docstring `"inclusive ge boundary"` | `tests/orchestrator/test_cache_breakpoint_verification.py:158` | ✅ Applied |
| sr-sdet ADV-2 — hardcoded-hostname-never-appears | `tests/orchestrator/test_stable_prefix_construction.py:153` (`test_hardcoded_hostname_never_appears_in_builder_prefix`) | ✅ Applied |

### Cycle 2 gate re-run (from scratch)

| Gate | Command | Result |
|---|---|---|
| Pytest (T23 tests) | `uv run pytest tests/orchestrator/test_cache_breakpoint_verification.py tests/orchestrator/test_stable_prefix_construction.py -q` | ✅ 46 passed (up from 33 — net +13 from FIX-1/2/3 + ADV-2 + 2 byte-stability companions) |
| Pytest (full suite) | `uv run pytest -q` | ⚠ 1 failed / 1254 passed / 10 skipped — failure is `tests/test_main_branch_shape.py::test_design_docs_absence_on_main` (pre-existing LOW-3, design_branch override; not introduced by T23) |
| Lint-imports | `uv run lint-imports` | ✅ 5 contracts kept, 0 broken |
| Ruff | `uv run ruff check` | ✅ All checks passed |

### Critical sweep (cycle 2)

- No regressions. T23 test count grew from 33 → 46 (+13); no T23 tests removed; full-suite delta is +6 (1248 → 1254) consistent with new T23 + sibling-task additions.
- No new design drift introduced. `cache_verify.py` ERROR branch added before step-3 ratio computation; control-flow remains flat. `to_text` `is not None` check is a strict tightening, not a behaviour change for non-zero stable_prefix_tokens.
- No source-of-truth contradictions. Spec, README task-table, exit criterion #11, CHANGELOG `[Unreleased]` all still aligned.
- Loop-controller observation #1 (Builder return-schema non-conformance recurrence #14) — already owned by M21 hardening track via M20-T23-ISS-01; nothing to add here.
- Loop-controller observation #2 (cycle 1 Auditor 500 transient) — environmental; no agent issue.

**Cycle 2 verdict:** ✅ PASS — all 5 FIXes verified in source, all gates green (modulo pre-existing design-branch shape gate), no regressions, AC-7 deferral unchanged.
