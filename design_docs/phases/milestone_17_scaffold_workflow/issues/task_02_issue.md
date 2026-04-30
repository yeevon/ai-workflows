# M17 Task 02 Issue File — Prompt Template Iteration + Live-Mode Smoke

## Cycle 1 build report

**Date:** 2026-04-30
**Verdict:** BUILT
**Gates:** uv run pytest (1510 passed, 12 skipped, 0 failed) | uv run lint-imports (5 kept, 0 broken) | uv run ruff check (all checks passed)

---

## Files touched

| File | Change |
|---|---|
| `ai_workflows/workflows/scaffold_workflow_prompt.py` | `SCAFFOLD_PROMPT_TEMPLATE` fully iterated (AC-1 text portion) |
| `ai_workflows/workflows/scaffold_workflow.py` | Inner imports hoisted (ADV-1 / AC-6) |
| `ai_workflows/workflows/_scaffold_write_safety.py` | `atomic_write` docstring fixed (ADV-2 / AC-7) |
| `tests/workflows/test_scaffold_workflow.py` | `test_render_scaffold_prompt_brace_escaping` added (LOW-3 / AC-4) |
| `tests/cli/test_run_scaffold_alias.py` | NEW — 5 CLI alias tests (LOW-2 / AC-5) |
| `tests/release/test_scaffold_live_smoke.py` | NEW — `AIW_E2E=1` gated live smoke (AC-2) |
| `CHANGELOG.md` | `[Unreleased]` M17 Task 02 entry (AC-9) |
| `design_docs/phases/milestone_17_scaffold_workflow/task_02_prompt_iteration_live_smoke.md` | Status flipped to Built |
| `design_docs/phases/milestone_17_scaffold_workflow/README.md` | Task 02 row + CS300 dogfood checkbox updated |

---

## ACs satisfied

| AC | Status | Notes |
|---|---|---|
| AC-1 — Prompt template iterated | PARTIAL | Template text teaches `WorkflowSpec` fields, `register_workflow` convention, four-layer contract, tier-naming, canonical example. Live verification (first-attempt pass) is operator-dependent — see deferred items below. |
| AC-2 — Live-mode smoke file lands | DONE | `tests/release/test_scaffold_live_smoke.py` exists; `AIW_E2E=1` gated; invokes real Opus tier; asserts gate interrupt + non-empty `spec_python` + validator pass. |
| AC-3 — CS300 dogfood documented | DEFERRED TO OPERATOR | See below. |
| AC-4 — Brace-escape regression test | DONE | `test_render_scaffold_prompt_brace_escaping` added; covers `goal`, `target_path`, `existing_workflow_context`. |
| AC-5 — CLI alias test | DONE | 5 tests via `typer.testing.CliRunner`: goal+target parsed, force flag, tier-override, missing-goal exit, missing-target exit. |
| AC-6 — ADV-1 inner import hoisted | DONE | `NonRetryable` + `RetryableSemantic` at module-level; three inner `from ai_workflows.primitives.retry import ...` removed. |
| AC-7 — ADV-2 docstring fix | DONE | `atomic_write` docstring updated: `NamedTemporaryFile` → `mkstemp`. |
| AC-8 — Gates green | DONE | pytest 1510/0, lint-imports 5/0, ruff all-clear. |
| AC-9 — CHANGELOG updated | DONE | Entry under `[Unreleased]` lists all files + ACs. |

---

## Carry-over items closed

| Item | Source | Status |
|---|---|---|
| LOW-2 — CLI alias test | T01 cycle 1, M17-T01-ISS-02 | CLOSED |
| LOW-3 — Brace-escape regression test | T01 cycle 2, M17-T01-ISS-03 | CLOSED |
| ADV-1 — Hoist inner import | T01 sr-dev | CLOSED |
| ADV-2 — Docstring fix (NamedTemporaryFile → mkstemp) | T01 sr-dev | CLOSED |

---

## Deferred to operator (not a BUILD failure)

**AC-1 live verification** — The spec states: "A live run with `goal='generate exam questions from a textbook chapter'` against Claude Opus produces `spec_python` that passes `validate_scaffold_output()` on first attempt." This requires `AIW_E2E=1` + Claude Code CLI auth in sandbox. The prompt template text has been iterated and teaches all required fields; live-run verification is the operator's action via `tests/release/test_scaffold_live_smoke.py`.

**AC-3 CS300 dogfood** — The spec explicitly calls this "non-automated; results in CHANGELOG." The operator must run:
```bash
aiw run scaffold_workflow \
  --goal 'generate exam questions from a textbook chapter' \
  --target ~/tmp/question_gen_smoke.py \
  --run-id scaffold-cs300-smoke-1

aiw resume scaffold-cs300-smoke-1 --gate-response approved

PYTHONPATH=~/tmp AIW_EXTRA_WORKFLOW_MODULES=question_gen_smoke \
  aiw run question_gen_smoke --input "First chapter text here..." --run-id qg-smoke-1
```
Document findings and any prompt changes under `CHANGELOG.md [Unreleased] ### Added`.

---

## Planned commit message

```
M17 Task 02: prompt template iteration + live smoke + T01 carry-over (KDR-003, KDR-004, KDR-013)

- SCAFFOLD_PROMPT_TEMPLATE iterated: teaches WorkflowSpec field inventory,
  register_workflow convention, four-layer contract, tier-naming, canonical
  example step.
- tests/release/test_scaffold_live_smoke.py: AIW_E2E-gated live Opus smoke.
- tests/cli/test_run_scaffold_alias.py: 5 CLI alias flag-parsing tests (LOW-2).
- test_render_scaffold_prompt_brace_escaping: brace-escape regression (LOW-3).
- scaffold_workflow.py: NonRetryable/RetryableSemantic imports hoisted (ADV-1).
- _scaffold_write_safety.py: atomic_write docstring fixed (ADV-2).
- CHANGELOG.md: M17 T02 entry.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

---

## Deviations from spec

None. The spec-vs-issue-file comparison found no conflicts. All hermetic ACs satisfied; operator-dependent ACs (AC-1 live verification, AC-3 dogfood) are correctly deferred per the invoker's project context brief.

---

# Cycle 1 audit

**Source task:** [task_02_prompt_iteration_live_smoke.md](../task_02_prompt_iteration_live_smoke.md)
**Audited on:** 2026-04-30
**Audit scope:** prompt template iteration, live smoke file, hermetic CLI alias + brace-escape tests, ADV-1 + ADV-2 carry-over closure, gates re-run from scratch, status surfaces.
**Status:** ⚠️ OPEN — one MEDIUM (carry-over checkboxes not ticked in spec). All ACs structurally met; gate integrity verified clean.

## Design-drift check

No drift detected. Cross-checked against `design_docs/architecture.md §3, §9` and the seven load-bearing KDRs:

- **KDR-003** (no Anthropic API): scaffold-synth tier routes via `ClaudeCodeRoute(cli_model_flag="opus")` — OAuth subprocess, no `anthropic` SDK, no `ANTHROPIC_API_KEY`. Live smoke exercises the OAuth path.  ✓
- **KDR-004** (validator pairing): `synthesize_source` (TieredNode) is followed by `scaffold_validator` (custom validator that raises `RetryableSemantic`/`NonRetryable`). Wiring is unchanged from T01.  ✓
- **KDR-006** (three-bucket retry): retry routing via `retrying_edge` with `RetryPolicy`; no bespoke try/except retry loops in the new code.  ✓
- **KDR-009** (SqliteSaver-only): live smoke uses `build_async_checkpointer`; no hand-rolled checkpoint writes.  ✓
- **KDR-013** (user-owned external code): the prompt explicitly teaches the four-layer contract — generated code lives outside `ai_workflows/`, imports only from `ai_workflows.workflows`, calls `register_workflow(_SPEC)` once.  ✓
- **KDR-014** (workflow-scoped tier names): `scaffold-synth` declared per-workflow via `scaffold_workflow_tier_registry()`; no pre-pivot names (`orchestrator`, `gemini_flash`, `local_coder`, `claude_code`) in new code.  ✓
- **Layer rule** (`primitives → graph → workflows → surfaces`): `lint-imports` re-run clean — 5 contracts kept, 0 broken.  ✓
- **No new dependency** introduced; no nice_to_have.md drive-by adoption.  ✓

## AC grading

| AC | Status | Notes |
|---|---|---|
| AC-1 — Prompt template iterated | PARTIAL (text done) | Template now teaches `WorkflowSpec` field inventory, `register_workflow` convention, four-layer contract, tier-naming, canonical example, and brace-escape rule. Live first-attempt-pass verification is operator-dependent (`AIW_E2E=1` + Claude Code CLI auth) — correctly deferred per spec design and invoker brief. |
| AC-2 — Live smoke file lands | MET | `tests/release/test_scaffold_live_smoke.py` exists; `AIW_E2E=1` gated via `pytestmark = pytest.mark.skipif`; uses real `ClaudeCodeRoute(cli_model_flag="opus")` via `scaffold_workflow_tier_registry()`; asserts `state.next` contains `preview_gate`, `state.values["scaffolded_workflow"].spec_python` non-empty, `validate_scaffold_output()` does not raise, no disk write. Mirrors the stub-adapter test's checkpointer + config + initial-state pattern. |
| AC-3 — CS300 dogfood documented | DEFERRED-TO-OPERATOR | Spec explicitly calls this "non-automated; results in CHANGELOG." Operator must run live commands. CHANGELOG entry under `[Unreleased]` notes the deferral and the commands. |
| AC-4 — Brace-escape regression test | MET | `test_render_scaffold_prompt_brace_escaping` at `tests/workflows/test_scaffold_workflow.py:673`. Exercises `goal`, `target_path`, `existing_workflow_context` with brace-containing inputs; asserts `{x}` and `{'a': 1}` survive `.format()` interpolation. Audit re-ran the smoke manually — passes. |
| AC-5 — CLI alias test | MET | `tests/cli/test_run_scaffold_alias.py` — 5 tests via `typer.testing.CliRunner` covering `--goal`+`--target` parsed, `--force` accepted, `--tier-override` parsed, missing-goal exits non-zero, missing-target exits non-zero. Stub adapter pattern matches `tests/workflows/test_scaffold_workflow.py`. |
| AC-6 — ADV-1 inner import hoisted | MET | `from ai_workflows.primitives.retry import NonRetryable, RetryableSemantic, RetryPolicy` at module-level (`scaffold_workflow.py:47`). Three inner `from ... import` blocks removed (`_make_scaffold_validator_node`, `_write_to_disk`, `_validate_input_node`). Diff verified. |
| AC-7 — ADV-2 docstring fix | MET | `_scaffold_write_safety.py:108` — docstring updated to reference `tempfile.mkstemp(dir=target.parent)`. Implementation already uses `mkstemp` (line 116); docstring now matches code. |
| AC-8 — Gates green | MET | Audit re-ran from scratch: `uv run pytest` → 1510 passed, 12 skipped, 0 failed, 22 warnings (all pre-existing DeprecationWarnings, not introduced by T02); `uv run lint-imports` → 5 kept, 0 broken; `uv run ruff check` → all checks passed. |
| AC-9 — CHANGELOG updated | MET | `[Unreleased]` entry under "Added — M17 Task 02" lists every file + AC mapping. Notes operator-dependent ACs (AC-1 live + AC-3 dogfood) explicitly. |

## 🟡 MEDIUM

### MED-1 — Spec carry-over checkboxes left unchecked despite items landing

**Location:** `design_docs/phases/milestone_17_scaffold_workflow/task_02_prompt_iteration_live_smoke.md:108-111`

The spec's `## Carry-over from prior audits` section retains all four checkboxes as `[ ]`:

```markdown
- [ ] **LOW-2** (T01 cycle 1, M17-T01-ISS-02) — `aiw run-scaffold` CLI alias test ...
- [ ] **LOW-3** (T01 cycle 2, M17-T01-ISS-03) — `render_scaffold_prompt` brace-escape regression test ...
- [ ] **ADV-1** (T01 sr-dev) — hoist inner import ...
- [ ] **ADV-2** (T01 sr-dev) — update `atomic_write` docstring ...
```

All four items have landed (verified in the AC-4/5/6/7 grading rows above) and the issue file's "Carry-over items closed" table marks them CLOSED. Per `CLAUDE.md` non-negotiables: *"Carry-over section at the bottom of a spec = extra ACs. Tick each as it lands."* The spec checkboxes are part of the per-task surface and should flip together with the table row + Status line.

**Severity rationale:** MEDIUM, not HIGH — the work shipped, gates are green, and the issue file unambiguously records closure. The drift is purely on the per-task spec surface (not on the four major status surfaces: spec Status line ✓, milestone README task table ✓, milestone "Done when" boxes that T02 satisfies ✓, no `tasks/README.md` for M17). Convention skipped, downstream risk minimal.

**Action / Recommendation:** flip the four `[ ]` to `[x]` in `task_02_prompt_iteration_live_smoke.md` lines 108-111. One-line edit.

## Additions beyond spec — audited and justified

None. The Builder added exactly what the spec called for: prompt template iteration, live smoke file, two hermetic test files, two carry-over fixes, CHANGELOG entry. No drive-by refactors, no nice_to_have.md adoption, no scope creep.

The five CLI alias tests (vs the spec's bullet list of "goal+target, force, tier-override, missing-goal, missing-target") are the natural cardinality of the spec's bullet list — not bonus tests.

## Gate summary

| Gate | Command | Result |
|---|---|---|
| pytest | `uv run pytest` | PASS — 1510 passed, 12 skipped, 0 failed (67.73s) |
| lint-imports | `uv run lint-imports` | PASS — 5 kept, 0 broken |
| ruff | `uv run ruff check` | PASS — all checks passed |
| smoke (manual) | `python -c "render_scaffold_prompt(goal='generate {x}', target_path='/tmp/{name}.py', existing_workflow_context=\"def f(): return {'a': 1}\")"` | PASS — `{x}` and `{'a': 1}` survive interpolation |

Builder's reported gate counts match audit re-run exactly. No gate integrity issues.

## Critical sweep

- **AC-3 / AC-1 framing.** Verified the spec marks AC-1 live verification and AC-3 dogfood as operator-dependent by design (spec line 38: *"Non-automated; results in CHANGELOG."*; spec line 96: *"For AC-2 (live-mode smoke): Claude Code CLI auth required in the sandbox."*). Builder's deferral-to-operator framing is correct, not silently skipped.
- **Test gaps.** AC-4 brace-escape test is a 14-line assertion that exercises the exact failure mode T01 cycle 2 hit. AC-5 CLI alias tests cover the four flag-parsing paths plus two missing-arg paths — adequate coverage. No trivial assertions found.
- **Doc drift.** Module docstrings in `scaffold_workflow_prompt.py` cite T02 explicitly. CHANGELOG entry references every touched file. No `architecture.md` change needed (no new layer/dependency/KDR added).
- **Secrets shortcuts.** Live smoke test reads `AIW_E2E` as a gate flag — that is the project convention for E2E tests, not a secret leak. No `ANTHROPIC_API_KEY` reads, no committed credentials.
- **Scope creep.** None.
- **Status-surface check.** (a) per-task spec `**Status:**` line → `✅ Built (cycle 1, 2026-04-30)` ✓; (b) milestone README task table T02 row → `✅ Built (cycle 1)` ✓; (c) M17 has no `tasks/README.md` — N/A; (d) milestone "Done when" checkboxes that T02 satisfies → "Prompt template" and "MCP exposure" already `[x]` from T01 (T02 hardens, doesn't satisfy a new "Done when" row); the "CS300 dogfood smoke" box at line 90 is correctly left `[ ]` because the operator-side dogfood has not yet run. All four major surfaces agree.
- **Carry-over checkbox-cargo-cult.** Spec carry-over checkboxes are NOT ticked in the spec file (see MED-1). Diff hunks exist for all four items (verified via `git diff` against AC-4/5/6/7), so this is a missed-tick, not a cargo-cult tick of an unimplemented item.
- **Cycle-N-vs-(N-1) overlap.** First cycle for T02; no prior cycle to compare against. (T01 is a separate task with its own issue file; comparison not applicable per the helper's intent.)
- **Rubber-stamp detection.** Verdict is OPEN (not PASS), one MEDIUM raised, so rubber-stamp guard does not fire. The substantial diff (~199 prompt lines + 2 new test files) was reviewed claim-by-claim; gates re-verified from scratch.

## Carry-over items — closure status

| Item | Source | Verified | Notes |
|---|---|---|---|
| LOW-2 — CLI alias test | T01 cycle 1 / M17-T01-ISS-02 | ✓ CLOSED | 5 tests in `tests/cli/test_run_scaffold_alias.py`. |
| LOW-3 — Brace-escape regression test | T01 cycle 2 / M17-T01-ISS-03 | ✓ CLOSED | `tests/workflows/test_scaffold_workflow.py:673`. |
| ADV-1 — Hoist inner import | T01 sr-dev | ✓ CLOSED | Module-level import at `scaffold_workflow.py:47`; three inner imports removed. |
| ADV-2 — Docstring fix | T01 sr-dev | ✓ CLOSED | `_scaffold_write_safety.py:108`. |

## Forward-deferred items

| Item | Severity | Owner | Reason |
|---|---|---|---|
| AC-1 live first-attempt validator pass | follow-up | operator | Requires `AIW_E2E=1` + Claude Code CLI auth in sandbox. Run via `tests/release/test_scaffold_live_smoke.py`. Not a future-task carry-over — it's an operator action. |
| AC-3 CS300 dogfood findings | follow-up | operator | Per spec: "non-automated; results in CHANGELOG." After running, append findings + any prompt changes under `CHANGELOG.md [Unreleased] ### Added`. Not a future-task carry-over. |

These are operator-touch items by spec design, NOT future-task forward-deferrals — no propagation to T03 needed (T03 owns ADR-0010 + skill-install doc, separate scope).

## Propagation status

No forward-deferral to T03. T03's existing scope (ADR-0010 + skill-install §Generating-your-own-workflow + `docs/writing-a-workflow.md` §Scaffolding) is unchanged by this audit. MED-1 is a same-task in-spec edit, not a cross-task deferral.

## Verdict

**⚠️ OPEN** — one MEDIUM finding (MED-1: spec carry-over checkboxes need ticking). All hermetic ACs structurally met; gates clean; design-drift clean. Cycle 2 closes by ticking the four `[ ]` in the spec to `[x]`; no code or test changes required.

**Locked decision (loop-controller + Auditor concur, 2026-04-30):** MED-1 — flip four `[ ]` carry-over checkboxes to `[x]` in `task_02_prompt_iteration_live_smoke.md` lines 108-111. Single mechanical edit; all four items verified landed in AC-4/5/6/7. No code or test changes.

---

## Cycle 2 audit

**Source task:** [task_02_prompt_iteration_live_smoke.md](../task_02_prompt_iteration_live_smoke.md)
**Audited on:** 2026-04-30
**Audit scope:** spec-only edit — verify MED-1 resolution; verify no regressions on hermetic ACs from cycle 1; verify operator-dependent ACs (AC-1, AC-3) remain correctly deferred.
**Status:** ✅ PASS — MED-1 resolved; no new findings; no regressions.

### Diff verification

`git diff` for cycle 2 touches exactly one file: `design_docs/phases/milestone_17_scaffold_workflow/task_02_prompt_iteration_live_smoke.md` lines 108-111. The four checkboxes flipped `[ ] → [x]`:

```
- [x] **LOW-2** (T01 cycle 1, M17-T01-ISS-02) — `aiw run-scaffold` CLI alias test ...
- [x] **LOW-3** (T01 cycle 2, M17-T01-ISS-03) — `render_scaffold_prompt` brace-escape regression test ...
- [x] **ADV-1** (T01 sr-dev) — hoist inner import ...
- [x] **ADV-2** (T01 sr-dev) — update `atomic_write` docstring ...
```

Verified directly via `Read` of spec lines 108-111 — all four show `[x]`. No other lines in the spec changed. No source code, test, or doc files touched.

### Design-drift check

No drift. The cycle 2 edit is metadata-only (Markdown checkboxes in a spec carry-over section). No imports, no LLM calls, no checkpoint logic, no retry logic, no observability, no MCP tool surface, no tier names — none of the seven KDR-anchors are touched. Layer rule trivially holds (no code changed).

### AC grading (regression check)

| AC | Cycle 1 status | Cycle 2 status | Notes |
|---|---|---|---|
| AC-1 | PARTIAL (text done, live op-dependent) | UNCHANGED | Prompt template text in `scaffold_workflow_prompt.py` not touched in cycle 2; live verification correctly remains operator-dependent. |
| AC-2 | MET | UNCHANGED | `tests/release/test_scaffold_live_smoke.py` not touched. |
| AC-3 | DEFERRED-TO-OPERATOR | UNCHANGED | Spec design — non-automated, CHANGELOG-driven. |
| AC-4 | MET | UNCHANGED | Brace-escape regression test still in place. |
| AC-5 | MET | UNCHANGED | CLI alias tests still in place. |
| AC-6 | MET | UNCHANGED | ADV-1 hoist still applied. |
| AC-7 | MET | UNCHANGED | ADV-2 docstring fix still applied. |
| AC-8 | MET | MET | Orchestrator-verified gates: pytest 1510 passed / 12 skipped, lint-imports 5 kept / 0 broken, ruff all-clear. No regressions from spec-only edit (expected — Markdown does not affect Python gates). |
| AC-9 | MET | UNCHANGED | CHANGELOG `[Unreleased]` entry preserved. |

### MED-1 closure

| Finding | Cycle 1 status | Cycle 2 status |
|---|---|---|
| MED-1 — Spec carry-over checkboxes left unchecked | OPEN | ✅ RESOLVED — four `[x]` confirmed at lines 108-111 |

### Critical sweep (cycle 2)

- **No new findings.** The single-line metadata edit cannot introduce code, test, doc, or status-surface drift.
- **Status-surface check.** Spec `**Status:**` line, milestone README task table row, milestone "Done when" boxes — all unchanged from cycle 1 (already correct). Carry-over checkboxes now also tick — fifth surface (per-task spec carry-over) now agrees with the other four.
- **Carry-over checkbox-cargo-cult guard.** Each `[x]` now has a corresponding diff hunk landed in cycle 1 (verified in cycle 1 audit AC-4/5/6/7 grading rows). No cargo-cult ticks.
- **Cycle-1-vs-cycle-2 overlap.** Cycle 2 had no findings. Loop-spinning detection N/A.
- **Rubber-stamp detection.** Verdict is PASS, but cycle 2 diff is 4 lines (well under the 50-line threshold) and the work is purely the locked decision from cycle 1. Rubber-stamp guard does not fire — this is a legitimate single-mechanical-edit close-out, not a glossed-over substantial diff.
- **Operator-dependent ACs.** AC-1 (live first-attempt validator pass) and AC-3 (CS300 dogfood) remain correctly deferred to operator action — not future-task carry-over, not silently skipped. Spec explicitly designs them as operator-touch.

### Gate summary (cycle 2)

| Gate | Command | Result |
|---|---|---|
| pytest | `uv run pytest` | PASS — 1510 passed, 12 skipped (orchestrator-verified before spawn) |
| lint-imports | `uv run lint-imports` | PASS — 5 kept, 0 broken |
| ruff | `uv run ruff check` | PASS — all checks passed |

Cycle 2 edit is Markdown-only; gate re-run from scratch was performed by the orchestrator and matches cycle 1. No re-run needed by Auditor for the metadata edit (no Python code path affected).

### Forward-deferred items

None. Operator-touch items (AC-1 live, AC-3 dogfood) carry over from cycle 1 unchanged — these are not future-task forward-deferrals.

### Propagation status

No propagation needed. T03 scope (ADR-0010 + skill-install doc + writing-a-workflow doc) is unchanged.

### Verdict (cycle 2)

✅ **PASS** — MED-1 resolved cleanly; zero new findings; zero regressions; all hermetic ACs still met; operator-dependent ACs correctly deferred. T02 closes here. No further cycles required.

---

## Sr. Dev review (2026-04-30)
**Files reviewed:** `scaffold_workflow_prompt.py`, `scaffold_workflow.py`, `_scaffold_write_safety.py`, `tests/cli/test_run_scaffold_alias.py`, `tests/release/test_scaffold_live_smoke.py`, `tests/workflows/test_scaffold_workflow.py` (brace-escape test only) | **Skipped:** none | **Verdict:** BLOCK

### 🔴 BLOCK — hidden bugs that pass tests

#### BLK-1 — `render_scaffold_prompt` incorrectly escapes user-supplied values; brace-escape test gives false positive

**File:** `ai_workflows/workflows/scaffold_workflow_prompt.py:234,242,243`
**Lens:** Lens 1 (hidden bug that passes tests)

`str.format()` substitution does **not** recursively parse `{}` inside substituted values — only the template's own `{{`/`}}` sequences are converted. Pre-escaping `goal`, `target_path`, and `existing_workflow_context` before passing them as `.format()` values is therefore wrong: the `{{` sequences survive into the rendered output unchanged, so the LLM receives `{{x}}` instead of `{x}`.

Reproduction:
```python
>>> "{goal}".format(goal="gen {{x}}")
'gen {{x}}'           # LLM sees {{ — not what the user typed
>>> "{goal}".format(goal="gen {x}")
'gen {x}'             # no escaping needed; substituted values are opaque
```

The existing-workflow-context path is affected most severely: `safe_ctx = existing.replace("{", "{{").replace("}", "}}")` followed by `_EXISTING_CONTEXT_SECTION_TEMPLATE.format(existing_workflow_context=safe_ctx)` produces `ctx` whose `{{`/`}}` are then passed as a value to the outer `SCAFFOLD_PROMPT_TEMPLATE.format(existing_context_section=ctx)` — neither `.format()` call converts `{{` in a substituted value, so the LLM receives literal `{{` and `}}` in the reference code block.

The regression test at `tests/workflows/test_scaffold_workflow.py:680-686` gives a **false positive**: it asserts `"{'a': 1}" in result`. After the (wrong) escaping, the result contains `"{{'a': 1}}"`. Python's `in` check passes because `"{'a': 1}"` is a substring of `"{{'a': 1}}"` (the `{{` starts at position 0; `{'a': 1}` matches at position 1). The test passes but the LLM still sees `{{`.

**What actually needs escaping:** Nothing in the user-supplied values. The template literal body already uses `{{`/`}}` for its own literal brace examples (lines 95-102, 136-143, 177-181). Those are template-side and correct. User-supplied strings passed as `.format()` values are opaque to the formatter and should be passed unmodified.

**Action:** In `render_scaffold_prompt`:
1. Remove `safe_ctx`, `safe_goal`, `safe_target_path` — pass `goal`, `target_path`, and `existing_workflow_context` directly as `.format()` values.
2. In `_EXISTING_CONTEXT_SECTION_TEMPLATE.format()`, pass `existing_workflow_context` (not `safe_ctx`) directly.
3. Fix the brace-escape test: assert `"{x}" in result` (should still pass since the value is now passed unmodified), and assert the result does **not** contain `"{{x}}"` to make it a genuine regression guard.

---

### 🟠 FIX — idiom drift / defensive-code creep

*(none — BLOCK finding dominates)*

---

### 🟡 Advisory

#### ADV-1 — `_make_scaffold_validator_node` factory wraps a single closure; could be a plain async function

**File:** `ai_workflows/workflows/scaffold_workflow.py:218-273`
**Lens:** Lens 4 (premature abstraction — factory for one caller)

`_make_scaffold_validator_node()` is a factory function that returns a single inner async function `_node`. It has exactly one call site (`build_scaffold_workflow` line 351). The factory adds no parameterisation (all state comes from module-level constants `SCAFFOLD_RETRY_POLICY`). Consider promoting `_node` to a top-level `async def _scaffold_validator_node(...)` and using it directly. The factory shape is the established pattern in this codebase for parameterised nodes; here there are no parameters to close over.

**Recommendation:** Flatten to a module-level `async def _scaffold_validator_node(...)` — same as `_write_to_disk` and `_validate_input_node`. One less indirection level, same behaviour. Low-priority; no runtime cost.

---

### What passed review

- **Lens 1 (bugs):** One BLOCK found (`render_scaffold_prompt` brace-escape misapplication + false-positive test). No other hidden bugs: `except Exception` at line 246 re-raises as `NonRetryable`/`RetryableSemantic` — not silent. `_write_to_disk` raises `NonRetryable` on all caught `OSError` subtypes — not silent. `atomic_write` temp-file cleanup is correct (closes fd before `os.replace`, cleans up on failure). Stub adapter class-level mutable state is safe (autouse `reset()` fixture wraps every test, same idiom as `test_scaffold_workflow.py`).
- **Lens 2 (defensive creep):** None. No unnecessary guards, no try/except against functions with guaranteed-no-raise contracts.
- **Lens 3 (idiom alignment):** `structlog` usage, `aiosqlite`/`SqliteSaver` pattern, `register()` at module bottom, `<workflow>_tier_registry()` convention — all match neighbour modules. Inner-import hoist (ADV-1 from T01) applied correctly at line 47.
- **Lens 4 (premature abstraction):** `_make_scaffold_validator_node` factory noted as Advisory. No other single-caller helpers introduced.
- **Lens 5 (comment/docstring drift):** Module docstrings cite T01/T02 tasks and list relationships. `atomic_write` docstring fixed (ADV-2 from T01). No restate-the-code comments.
- **Lens 6 (simplification):** No collapsible loops or `if x: return True` patterns. Live smoke test is appropriately minimal.

---

## Sr. SDET review (2026-04-30)
**Test files reviewed:** tests/workflows/test_scaffold_workflow.py (line 673-686), tests/cli/test_run_scaffold_alias.py, tests/release/test_scaffold_live_smoke.py | **Skipped:** none | **Verdict:** SHIP

### BLOCK
None.

### FIX
None.

### Advisory

**ADV-1 — Lens 1 / Lens 6: weak OR-chain assertion in test_run_scaffold_alias_goal_and_target_parsed (tests/cli/test_run_scaffold_alias.py:183-188)**

The assertion `"run" in output_lower` is so broad it matches any output string. The stub call count and the `not target.exists()` assertion already prove dispatch was exercised. Recommend replacing the OR-chain with `assert _StubLiteLLMAdapter.call_count == 1, "stub must have been called once"`.

**ADV-2 — Lens 2: brace-escape test does not assert {name} round-trip (tests/workflows/test_scaffold_workflow.py:680-686)**

`target_path="/tmp/{name}.py"` is passed but `"{name}" in result` is never asserted. A `KeyError` would surface as a test error rather than a silent pass, so no false-negative risk here, but the gap is worth closing. Recommend adding `assert "{name}" in result`.

**ADV-3 — Lens 4: _reset_scaffold fixture has no yield / teardown (tests/cli/test_run_scaffold_alias.py:91-95)**

The autouse fixture calls `workflows.register(...)` but never yields or cleans up. Registry state is left dirty after the last test in the file. Recommend adding `yield` and a `workflows._reset_for_tests()` call in the finally block, matching the existing pattern in test_scaffold_workflow.py.

**ADV-4 — Lens 3: class-level mutable script list in _StubLiteLLMAdapter (tests/cli/test_run_scaffold_alias.py:49)**

`script` and `call_count` are class attributes reset via `cls.script = []`. Pattern is self-consistent and matches the existing project stub. A comment on `reset()` noting that both attributes must remain class-level would guard against a future instance-level assignment silently defeating the reset.

### What passed review

- **Lens 1 (wrong reason):** Live-smoke assertions are meaningfully specific (gate node name, non-empty spec_python, validator pass). No trivial `assert result is not None` patterns, no tautologies, no TODO stubs.
- **Lens 2 (coverage gaps):** All five AC-5 paths covered. AC-4 covers three injection points. AC-2 covers gate-pause + validator. ADV-2 notes a minor intra-test gap (no false-negative risk).
- **Lens 3 (mock overuse):** LiteLLMAdapter is the correct stub boundary. SQLiteStorage and checkpointer use real tmp_path instances. No bare MagicMock() against typed parameters.
- **Lens 4 (fixture hygiene):** _reset_stub resets both before and after. monkeypatch fixtures auto-teardown. _reset_scaffold teardown absent (ADV-3, low blast radius due to monkeypatch tier override).
- **Lens 5 (hermetic/E2E gating):** Live smoke correctly gated with pytestmark skipif. CLI alias tests fully hermetic — stub adapter + tier registry override, no subprocess.run(["claude",...]).
- **Lens 6 (naming/assertions):** Test names state intent. Exit-code assertions include output message. No bare pytest.skip(). Live smoke messages include repr context.

---

## Security review (2026-04-30)

**Task:** M17 Task 02 — Prompt Template Iteration + Live-Mode Smoke
**Reviewer:** security-reviewer agent
**Cycle:** 2
**Threat model scope applied:** wheel contents, OAuth subprocess, KDR-013 external workflow load path

### Threat model checks performed

**Wheel contents (TM item 1):** `unzip -l dist/jmdl_ai_workflows-0.3.1-py3-none-any.whl` shows no hits on prohibited paths (`.env*`, `runs/`, `*.sqlite3`, `.claude/`, `design_docs/`, etc.). New test files do not land in the wheel. Clean.

**OAuth subprocess integrity (TM item 2 / KDR-003):** `ai_workflows/primitives/llm/claude_code.py` reviewed — no `shell=True`; argv is a list literal with no user value injected; prompt content flows exclusively via stdin; timeout is signal-based via `asyncio.wait_for` + `proc.kill()`; stderr captured but not logged. `grep -rn "ANTHROPIC_API_KEY" ai_workflows/` returns zero hits.

**Brace-injection in render_scaffold_prompt:** `goal`, `target_path`, and `existing_workflow_context` are all brace-escaped before `.format()`. Regression test covers this path. No injection vector.

**KDR-013 external workflow load path (TM item 3):** Not touched by this task.

**SQLite paths (TM item 5):** Not touched. Test fixtures redirect DB paths to `tmp_path` via `monkeypatch.setenv`. Correct hermetic pattern.

**Subprocess CWD / env leakage (TM item 6):** `asyncio.create_subprocess_exec` does not pass `env=` — inherits parent env. Pre-existing condition, not introduced by T02. Logged as Advisory.

**Logging hygiene (TM item 7):** No new `StructuredLogger` calls in touched files. `goal` and `target_path` are not emitted to any logger. Clean.

**Dependency CVEs (TM item 8):** No `pyproject.toml` or `uv.lock` changes. Dependency audit not triggered.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

**ADV-SEC-1 — ClaudeCodeSubprocess inherits full parent env (pre-existing)**
- **File:line:** `ai_workflows/primitives/llm/claude_code.py:135`
- **TM item:** 6 (Subprocess CWD / env leakage)
- **Description:** Subprocess spawned for `claude` CLI inherits the parent env without filtering. In the solo-use local deployment model this is an accepted risk. Pre-existing; not introduced by T02.
- **Action:** No change required before release. Future hardening: pass explicit `env=` dict to `create_subprocess_exec` to limit child env exposure.

**Verdict:** SHIP

---

## Cycle 3 audit

**Source task:** [task_02_prompt_iteration_live_smoke.md](../task_02_prompt_iteration_live_smoke.md)
**Audited on:** 2026-04-30
**Audit scope:** verify BLK-1 resolution (sr-dev cycle 2 finding) — `render_scaffold_prompt` no longer pre-escapes user-supplied values; regression test now has genuine `not in` guards. Re-run full gate trio. Confirm no regressions across hermetic ACs from cycles 1+2.
**Status:** ✅ FUNCTIONALLY CLEAN — BLK-1 resolved; regression test now genuine; no new findings; no regressions.

### Diff verification

`git diff` for cycle 3 touches exactly two files:

1. **`ai_workflows/workflows/scaffold_workflow_prompt.py`** — `render_scaffold_prompt` body simplified. Removed three pre-escape statements (`safe_ctx`, `safe_goal`, `safe_target_path`). Now passes `goal`, `target_path`, and (when present) `existing_workflow_context` directly to `.format()`. Verified at lines 230-241 of the current file: the `if existing_workflow_context:` branch calls `_EXISTING_CONTEXT_SECTION_TEMPLATE.format(existing_workflow_context=existing_workflow_context)` (no `safe_ctx`); the outer `SCAFFOLD_PROMPT_TEMPLATE.format(goal=goal, target_path=target_path, existing_context_section=ctx)` passes raw `goal` and `target_path`.

2. **`tests/workflows/test_scaffold_workflow.py:673-689`** — `test_render_scaffold_prompt_brace_escaping` tightened. Added two genuine `not in` guards:
   ```python
   assert "{x}" in result
   assert "{{x}}" not in result          # NEW — guards against re-introducing pre-escape
   assert "{'a': 1}" in result
   assert "{{'a': 1}}" not in result     # NEW — guards against re-introducing pre-escape
   ```
   The docstring now states the invariant: *"str.format() does not scan substituted values for format fields — values are opaque. Pre-escaping user-supplied braces is wrong."*

### BLK-1 verification (programmatic smoke)

Audit re-ran the manual smoke from cycle 1's gate summary against the post-fix source:

```python
>>> render_scaffold_prompt(goal='generate {x}', target_path='/tmp/{name}.py',
...     existing_workflow_context="def f(): return {'a': 1}")
```

Assertions all hold:
- `'{x}' in result` ✓ AND `'{{x}}' not in result` ✓
- `"{'a': 1}" in result` ✓ AND `"{{'a': 1}}" not in result` ✓
- `'{name}' in result` ✓ AND `'{{name}}' not in result` ✓

Sr-dev's cycle 2 reproduction (`"{goal}".format(goal="gen {{x}}")` → `'gen {{x}}'`) is now no longer reachable because the values are passed unmodified. The LLM will receive the user's literal braces, exactly once.

### Design-drift check

No drift. BLK-1 resolution is a behavioural fix inside one helper; no imports, no new layers, no LLM-call shape, no checkpoint logic, no retry logic, no MCP tools, no tier-name strings touched.

- **KDR-003** (no Anthropic API): unchanged. ✓
- **KDR-004** (validator pairing): `synthesize_source` → `scaffold_validator` wiring unchanged. ✓
- **KDR-006** (three-bucket retry): unchanged. ✓
- **KDR-009** (SqliteSaver): unchanged. ✓
- **KDR-013** (user-owned external code): the prompt still teaches the four-layer contract; no shadowing logic touched. ✓
- **Layer rule**: `lint-imports` re-run clean — 5 contracts kept, 0 broken. ✓

### AC grading (regression check)

| AC | Cycle 2 status | Cycle 3 status | Notes |
|---|---|---|---|
| AC-1 — Prompt template iterated | PARTIAL (text done) | UNCHANGED | Template body unchanged in cycle 3; only the wrapper helper was simplified. The prompt's literal-brace examples on lines 95-102, 136-143, 177-181 remain template-side `{{`/`}}` (correct). Live first-attempt-pass remains operator-dependent. |
| AC-2 — Live smoke file lands | MET | UNCHANGED | `tests/release/test_scaffold_live_smoke.py` not touched. |
| AC-3 — CS300 dogfood documented | DEFERRED-TO-OPERATOR | UNCHANGED | Spec design — non-automated. |
| AC-4 — Brace-escape regression test | MET (but false-positive per BLK-1) | MET (genuine) | Test now actually guards against the failure mode it was supposed to. |
| AC-5 — CLI alias test | MET | UNCHANGED | Not touched. |
| AC-6 — ADV-1 inner import hoisted | MET | UNCHANGED | Module-level imports preserved. |
| AC-7 — ADV-2 docstring fix | MET | UNCHANGED | `_scaffold_write_safety.py:108` unchanged. |
| AC-8 — Gates green | MET | MET | Auditor re-ran from scratch: pytest 1510 passed / 12 skipped / 0 failed (67.99s); lint-imports 5 kept / 0 broken; ruff all-clear. |
| AC-9 — CHANGELOG updated | MET | UNCHANGED | `[Unreleased]` entry preserved. |

### BLK-1 closure

| Finding | Cycle 2 status | Cycle 3 status |
|---|---|---|
| BLK-1 (sr-dev) — `render_scaffold_prompt` pre-escapes values; regression test gives false positive | OPEN (BLOCK) | ✅ RESOLVED — pre-escape removed; regression test now has `not in {{x}}` / `not in {{'a': 1}}` guards |

### Critical sweep (cycle 3)

- **Sr-dev BLK-1 fully addressed.** All three remediation steps from sr-dev's Action list are present: (1) `safe_ctx` / `safe_goal` / `safe_target_path` removed; (2) `_EXISTING_CONTEXT_SECTION_TEMPLATE.format()` now receives `existing_workflow_context` directly; (3) regression test now asserts the result does NOT contain the doubled-brace form.
- **No carry-over checkbox cargo-cult.** No carry-over checkboxes were ticked in cycle 3 (none to tick — BLK-1 was a sr-dev finding, not a carry-over from prior audit).
- **Cycle-2-vs-cycle-3 overlap.** Cycle 3 has zero net findings (the only one cleared from cycle 2 was BLK-1; no new ones raised). Loop-spinning detection N/A.
- **Rubber-stamp detection.** Verdict is FUNCTIONALLY CLEAN, cycle 3 diff is ~10 lines of source change + ~6 lines of test tightening (well under the 50-line threshold), and the change directly addresses the locked sr-dev BLOCK with a programmatic smoke confirming behaviour. Not a rubber-stamp.
- **Test gap re-check.** ADV-2 from sr-sdet cycle 2 (`{name}` round-trip not asserted in the test) is also implicitly closed by the smoke I ran (`{name}` survives), though the test itself does not assert it; sr-sdet flagged it as no-false-negative-risk and Advisory only — left as-is, unchanged from cycle 2 disposition.
- **Status-surface check.** No code or test changes affect status surfaces. The four spec/README surfaces remain in agreement from cycle 2.
- **Doc drift.** Module docstring of `scaffold_workflow_prompt.py` already cites T01/T02 (cycle 1 update); the wrapper-helper change does not affect any docstring. No `architecture.md` change needed.

### Gate summary (cycle 3)

| Gate | Command | Result |
|---|---|---|
| pytest | `uv run pytest` | PASS — 1510 passed, 12 skipped, 0 failed (67.99s, 22 pre-existing DeprecationWarnings) |
| lint-imports | `uv run lint-imports` | PASS — 5 kept, 0 broken |
| ruff | `uv run ruff check` | PASS — all checks passed |
| smoke (manual) | `python -c "render_scaffold_prompt(goal='generate {x}', target_path='/tmp/{name}.py', existing_workflow_context=\"def f(): return {'a': 1}\")"` | PASS — single-brace forms present; double-brace forms absent; `{name}` round-trips |
| target test | `uv run pytest tests/workflows/test_scaffold_workflow.py::test_render_scaffold_prompt_brace_escaping -v` | PASS (1.03s) |

Builder/orchestrator-reported gate counts match audit re-run exactly. No gate integrity issues.

### Forward-deferred items

None new. Operator-touch items (AC-1 live, AC-3 dogfood) carry forward unchanged from cycle 2.

### Propagation status

No propagation needed. T03 scope (ADR-0010 + skill-install doc + writing-a-workflow doc) is unchanged.

### Verdict (cycle 3)

✅ **FUNCTIONALLY CLEAN** — BLK-1 fully resolved (pre-escape removed; regression test now genuine); zero new findings; zero regressions; all hermetic ACs still met; gates green re-run from scratch; operator-dependent ACs correctly deferred. T02 closes here.

---

## Sr. Dev review (cycle 3)
**Files reviewed:** `ai_workflows/workflows/scaffold_workflow_prompt.py`, `ai_workflows/workflows/scaffold_workflow.py`, `tests/workflows/test_scaffold_workflow.py` (lines 673-689) | **Skipped:** none (cycle 3 diff is two files; unchanged files not re-read) | **Verdict:** SHIP

### 🔴 BLOCK

None. BLK-1 from cycle 2 is resolved (see below).

### 🟠 FIX

None.

### 🟡 Advisory

#### ADV-1 — `_make_scaffold_validator_node` factory wraps a single closure; could be a plain async function (carry-over from cycle 2, still present, still advisory)

**File:** `ai_workflows/workflows/scaffold_workflow.py:218-273`
**Lens:** Lens 4 (premature abstraction — factory for one caller)

No parameters are closed over; `SCAFFOLD_RETRY_POLICY` is a module-level constant. The factory is callable by one site (`build_scaffold_workflow` line 351). Consider promoting to `async def _scaffold_validator_node(state, config)` at module level, matching `_write_to_disk` and `_validate_input_node`. Zero runtime cost; one less indirection level. Out-of-spec scope — advisory only, no cycle needed.

---

### BLK-1 resolution verification

**`ai_workflows/workflows/scaffold_workflow_prompt.py:230-241`** — `render_scaffold_prompt` now passes `goal`, `target_path`, and (when present) `existing_workflow_context` directly to `.format()`. No `safe_ctx`, `safe_goal`, `safe_target_path` variables. Correct: `str.format()` substituted values are opaque to the formatter; pre-escaping would have produced `{{x}}` in the rendered string rather than `{x}`.

**`tests/workflows/test_scaffold_workflow.py:686-689`** — two genuine `not in` guards added:
- `assert "{{x}}" not in result` — closes the false-positive path from cycle 2 (where `"{'a': 1}" in "{{'a': 1}}"` passed because the single-brace form is a substring of the doubled-brace form).
- `assert "{{'a': 1}}" not in result` — same guard for the dict-literal injection point.

The regression test is now a genuine guard: it will fail if pre-escaping is re-introduced.

---

### What passed review

- **Lens 1 (bugs):** BLK-1 resolved. No new hidden bugs: `except Exception` at `scaffold_workflow.py:246` re-raises as `NonRetryable`/`RetryableSemantic` — not silent. No `time.sleep` in async context. No discarded `create_task`. No mutable default arguments. Template body's own `{{`/`}}` literals (template lines 95-102, 136-143, 177-181) are template-side escaping — untouched and correct.
- **Lens 2 (defensive creep):** None introduced. No new unnecessary guards in the simplified `render_scaffold_prompt` body.
- **Lens 3 (idiom alignment):** `structlog`, `aiosqlite`, `register()` at module bottom, `_tier_registry()` convention — all unchanged from cycles 1+2, matching neighbour modules.
- **Lens 4 (premature abstraction):** `_make_scaffold_validator_node` factory noted as Advisory (carry-over, no change, no cycle needed).
- **Lens 5 (comment/docstring drift):** Test docstring at line 674-679 now correctly states the invariant. Module docstring cites T01/T02 (unchanged).
- **Lens 6 (simplification):** Simplification is the change — three intermediate variables removed from `render_scaffold_prompt`. Reads clearly.

---

## Security review (cycle 3)

**Task:** M17 Task 02 — Prompt Template Iteration + Live-Mode Smoke
**Reviewer:** security-reviewer agent
**Cycle:** 3
**Threat model scope applied:** wheel contents, OAuth subprocess, KDR-013 external workflow load path

### Cycle 3 change reviewed

`render_scaffold_prompt` in `ai_workflows/workflows/scaffold_workflow_prompt.py` — removed pre-escaping of user-supplied values (`safe_ctx`, `safe_goal`, `safe_target_path` eliminated). `goal`, `target_path`, and `existing_workflow_context` now passed directly as `.format()` substitution values. Regression test tightened with `not in "{{x}}"` and `not in "{{'a': 1}}"` guards.

### Security lens question

**Confirmed safe.** Passing user-supplied strings directly to `.format()` as substitution *values* (not as the template string itself) carries zero injection risk. Python's `str.format()` does not execute code, does not recurse into substituted values for format fields, and does not parse `{}`-sequences inside them. A user-controlled `goal="{__import__('os').system('id')}"` is handed to the LLM verbatim as text — no Python evaluation occurs. The only caller of `render_scaffold_prompt` is the scaffold-synth node, which passes the rendered string as prompt content to `ClaudeCodeRoute`; the LLM receives the text, not an `eval` surface.

The cycle 3 fix corrects a prompt-correctness bug (BLK-1 from sr-dev cycle 2), not a security bug. Removing the pre-escape does not open any new attack surface.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

**ADV-SEC-1 — ClaudeCodeSubprocess inherits full parent env (pre-existing, carry-over from cycle 2)**
- **File:line:** `ai_workflows/primitives/llm/claude_code.py` (subprocess spawn site)
- **TM item:** 6 (Subprocess CWD / env leakage)
- **Description:** `asyncio.create_subprocess_exec` does not pass `env=` — inherits full parent environment. Solo-use local deployment model; accepted risk. Not introduced by T02.
- **Action:** No change required before release. Future hardening: pass explicit `env=` dict to `create_subprocess_exec`.

**Verdict:** SHIP

---

## Sr. SDET review (cycle 3)
**Test files reviewed:** tests/workflows/test_scaffold_workflow.py (lines 673-689), tests/cli/test_run_scaffold_alias.py, tests/release/test_scaffold_live_smoke.py | **Skipped:** none | **Verdict:** SHIP

### BLOCK
None.

### FIX
None.

### Advisory

**ADV-1 (carry-forward from cycle 2 sr-sdet) — Lens 6: weak OR-chain assertion in test_run_scaffold_alias_goal_and_target_parsed**
`tests/cli/test_run_scaffold_alias.py:183-188`. The assertion `"run" in output_lower` matches any non-empty output. Already recorded as Advisory in cycle 2. Not introduced in cycle 3; no regression.

**ADV-2 (carry-forward from cycle 2 sr-sdet) — Lens 2: {name} round-trip not asserted in brace-escape test**
`tests/workflows/test_scaffold_workflow.py:681-689`. `target_path="/tmp/{name}.py"` is passed but `"{name}" in result` is never asserted. A `KeyError` would surface as a test error rather than a silent pass, so no false-negative risk. Already recorded as Advisory in cycle 2. Not introduced in cycle 3; no regression.

### What passed review (per lens)

- **Lens 1 (wrong reason):** The two new `not in` assertions at lines 687 and 689 are genuine regression guards. The cycle 1 false-positive was that `"{'a': 1}" in "{{'a': 1}}"` evaluates to `True` in Python (substring match), making the pre-escaping bug invisible to the positive assertion alone. The `assert "{{'a': 1}}" not in result` assertion cannot be satisfied unless the output contains single braces — it directly pins the correct post-fix behaviour. Similarly `assert "{{x}}" not in result` will catch any future re-introduction of `goal.replace("{", "{{")` before `.format()`. Both guards are specific to the failure mode they are supposed to detect. No trivial assertions, no tautologies, no TODO stubs.
- **Lens 2 (coverage gaps):** The fix passes `existing_workflow_context` directly to `_EXISTING_CONTEXT_SECTION_TEMPLATE.format(existing_workflow_context=...)` — the value is the named argument, not part of the template string, so `.format()` does not treat `{'a': 1}` inside it as a format field. The test exercises this exact path. Coverage is adequate for the change scope.
- **Lens 3 (mock overuse):** No mock changes in cycle 3. LiteLLMAdapter remains the correct stub boundary. SQLiteStorage and checkpointer use real tmp_path instances in all hermetic tests.
- **Lens 4 (fixture hygiene):** No fixture changes in cycle 3. Pre-existing Advisory ADV-3 (_reset_scaffold missing yield/teardown in test_run_scaffold_alias.py) is unchanged — blast radius remains low due to the monkeypatch tier override.
- **Lens 5 (hermetic/E2E gating):** Live smoke `pytestmark = pytest.mark.skipif(not os.getenv("AIW_E2E"), ...)` is intact and not touched in cycle 3. All hermetic tests pass with no live network calls. No `subprocess.run(["claude", ...])` without gate.
- **Lens 6 (naming/assertions):** `test_render_scaffold_prompt_brace_escaping` name accurately describes the test intent. The updated docstring is precise and non-redundant. Assertion messages are clear in context.
