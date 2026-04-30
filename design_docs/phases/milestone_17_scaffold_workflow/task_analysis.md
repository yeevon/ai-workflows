# M17 — Task Analysis

**Round:** 2 — T02/T03/T04 spec review | **Analyzed on:** 2026-04-30 | **Analyst:** task-analyzer agent
**Specs analyzed:** `task_02_prompt_iteration_live_smoke.md`, `task_03_adr_and_docs.md`, `task_04_milestone_closeout.md`
**For reference (not re-graded):** `task_01_scaffold_workflow.md` shipped at 95dc592 (2026-04-30).

> **Round 1 history.** Four MEDIUM findings (M1, M2, M3, M4) and three LOW findings — all applied between rounds. Round 2 verifies the fixes against the live tree and re-sweeps for any new drift.

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 0 |
| 🟢 LOW | 0 |

**Stop verdict:** CLEAN

## Round 1 fixes — verification

All four MEDIUM findings from round 1 are correctly applied; the three LOW findings were pushed to spec carry-over. Verification:

### M1 + M2 — `roadmap.md` stale ADR-0008 + `AIW_WORKFLOWS_PATH` references

**Spec landing:** `task_04_milestone_closeout.md:38-40` — explicit deliverable bullets:
> Also fix two stale references on the M17 narrative line (line 58 at spec-generation time):
> - Replace `[ADR-0008](adr/0008_user_owned_generated_code.md)` (twice) with `[ADR-0010](adr/0010_user_owned_generated_code.md)` …
> - Replace `AIW_WORKFLOWS_PATH` with `AIW_EXTRA_WORKFLOW_MODULES` — M16 shipped with the env-var renamed (verified at `ai_workflows/workflows/loader.py:46`).

And in `task_04_milestone_closeout.md:49`, AC-1 reinforces:
> Also fix two stale roadmap.md references: ADR-0008 → ADR-0010, `AIW_WORKFLOWS_PATH` → `AIW_EXTRA_WORKFLOW_MODULES`.

**Live-tree verification:**
- `roadmap.md:58` still has the stale references (expected — fix lands at T04 close-out, not earlier).
- `ai_workflows/workflows/loader.py:46` has `ENV_VAR_NAME = "AIW_EXTRA_WORKFLOW_MODULES"` ✓.
- `design_docs/adr/` listing confirms `0008_declarative_authoring_surface.md` occupies slot 0008; slot 0010 is genuinely free ✓.

**Status:** ✅ Resolved (deliverable + AC both name the fix).

### M3 — T02 live-smoke `ainvoke` call shape

**Spec landing:** `task_02_prompt_iteration_live_smoke.md:24` rewritten as:
> Mirrors `tests/workflows/test_scaffold_workflow.py::test_scaffold_end_to_end_with_stub_adapter` (same checkpointer + config + initial-state pattern), but the stub adapter is replaced by the real `ClaudeCodeRoute(cli_model_flag="opus")` tier (no `_StubLiteLLMAdapter.script` injection). The initial state is built inline as `{"run_id": run_id, "input": ScaffoldWorkflowInput(goal="generate exam questions from a textbook chapter", target_path=tmp_path / "question_gen.py")}` and invoked via `await app.ainvoke(initial, config=cfg, durability="sync")`.

**Live-tree verification:** Pattern matches `tests/workflows/test_scaffold_workflow.py:399-407` exactly:
```python
initial = {
    "run_id": run_id,
    "input": ScaffoldWorkflowInput(
        goal="Generate exam questions from a textbook chapter.",
        target_path=target,
    ),
}
await app.ainvoke(initial, config=cfg, durability="sync")
```

**Status:** ✅ Resolved.

### M4 — T02 gate detection via `aget_state` not `GraphInterrupt`

**Spec landing:** `task_02_prompt_iteration_live_smoke.md:25-27` rewritten as:
> - Asserts the graph pauses at the `preview_gate` HumanGate (use `await app.aget_state(cfg)` and check that `state.next` contains the gate node name — equivalent to the existing test's `assert not target.exists()` pattern).
> - Asserts the paused graph state's `scaffolded` field has non-empty `spec_python` content.
> - Asserts `validate_scaffold_output(state.values["scaffolded"])` does not raise.

**Live-tree verification:** Existing hermetic test calls `await app.aget_state(cfg)` and reads `state.values.get(...)` (lines 424-426 of the test file). The `preview_gate` node name is verified at `scaffold_workflow.py:395` (`g.add_node("preview_gate", gate)`).

**Status:** ✅ Resolved.

### Version-source fix — T04 §pyproject.toml + AC-1

**Spec landing:** `task_04_milestone_closeout.md:14-16` (the §Version bump section) now correctly cites `ai_workflows/__init__.py:33` as the single source of truth:
> Bump `__version__` from `"0.3.1"` to `"0.4.0"` in `ai_workflows/__init__.py:33`. This is the single source of truth — `pyproject.toml` declares `dynamic = ["version"]` and reads from there. No `pyproject.toml` version line to change directly.

**Live-tree verification:**
- `ai_workflows/__init__.py:33` → `__version__ = "0.3.1"` ✓.
- `pyproject.toml:13` → `dynamic = ["version"]` ✓.
- `pyproject.toml:70` → `[tool.hatch.version]` block (no literal version line) ✓.

**Status:** ✅ Resolved. AC-1 also names `__init__.py` (not `pyproject.toml` directly).

### LOW carry-overs pushed to spec

- **TA-LOW-01** (was L1 — M16 T03 → M16 T01 attribution): present in `task_03_adr_and_docs.md:84-86` ✓.
- **TA-LOW-02** (was L2 — dep-auditor as parallel terminal-gate reviewer): present in `task_04_milestone_closeout.md:70-72` ✓.
- **TA-LOW-03** (was L3 — §Scaffolding placement hint): present in `task_03_adr_and_docs.md:88-90` ✓.

**Status:** ✅ All three carry-overs survive in the specs as actionable Builder hints.

## Round 2 — independent re-verification

A second pass against the live tree found no new findings. Specific re-checks:

- **All five symbol references in T02 verify:** `SCAFFOLD_PROMPT_TEMPLATE` (`scaffold_workflow_prompt.py:20`), `validate_scaffold_output` (imported `scaffold_workflow.py:52`, used `:259`), `build_scaffold_workflow` (`scaffold_workflow.py:328`), `_make_scaffold_validator_node` (`scaffold_workflow.py:218`), `atomic_write` (`_scaffold_write_safety.py:105`).
- **All four T02 carry-over IDs (LOW-2, LOW-3, ADV-1, ADV-2)** trace to the issue file lines noted in round 1.
- **`tests/release/`** exists (`__init__.py`, `__pycache__`, `test_install_smoke.py`); the new `test_scaffold_live_smoke.py` slots in cleanly.
- **`tests/cli/`** exists (`test_eval_commands.py`, `test_external_workflow.py`, `test_list_runs.py`, `test_resume.py`, `test_run.py`, `test_tier_override.py`, `conftest.py`); `test_run_scaffold_alias.py` follows convention.
- **ADR slot 0010 still free** (`design_docs/adr/` listing: 0001/0002/0004/0005/0007/0008/0009 — slot 0010 next).
- **CHANGELOG `[Unreleased]`** has the M17 T01 entry; T02–T04 will append.
- **`ai_workflows/workflows/loader.py:46`** confirms `ENV_VAR_NAME = "AIW_EXTRA_WORKFLOW_MODULES"`.
- **No new layer-rule violations.** T02 source-touches are confined to `ai_workflows/workflows/` (prompt + scaffold modules); T03/T04 are doc + version-bump only.
- **No new KDR violations.** KDR-003 (no Anthropic SDK), KDR-004 (validator pairing), KDR-006 (RetryingEdge), KDR-008 (FastMCP), KDR-009 (SqliteSaver), KDR-013 (user-owned code), KDR-014 (per-call rebind) all preserved.
- **SEMVER:** 0.3.1 → 0.4.0 is additive minor (new workflow, new CLI alias, new MCP-exposed workflow, no API breakage). Correctly framed in `README.md:142-143`.
- **Status surfaces in T04** correctly enumerate four flips: per-task spec, milestone README task row + exit criteria + Outcome, `roadmap.md`, root `README.md`.
- **`nice_to_have.md` slot drift sweep:** none of the new specs cite a slot number; no risk.

## What's structurally sound

**T02:**
- Three deliverable groups (prompt iteration, live-smoke test, CS300 dogfood) each map to ACs (AC-1, AC-2, AC-3) and tests in the §Tests table.
- Carry-over from T01 audits (LOW-2/LOW-3/ADV-1/ADV-2) closes cleanly via AC-4 through AC-7.
- Live-smoke is correctly gated behind `AIW_E2E=1` (matches `tests/release/test_install_smoke.py` precedent).
- Sandbox dependency (Claude Code CLI auth) called out explicitly.
- Out-of-scope is sharp (no auto-evaluation, no validator-rule additions, no ADR text).

**T03:**
- Doc-only task (zero `ai_workflows/` source touches) — correctly framed and out-of-scope-fenced.
- ADR-0010 §Decision lists four binding rules (validator scope / write-target safety / `AIW_EXTRA_WORKFLOW_MODULES` handoff / no auto-registration) traced to the README's exit criteria.
- §Alternatives rejected covers three (lint-the-generated-code / sandbox the runtime / keep generated code in-package).
- Carry-overs TA-LOW-01 + TA-LOW-03 are properly framed as Builder hints (not new ACs).
- §Out of scope correctly defers source code, prompt template, version bump.

**T04:**
- Pattern mirrors M12 T07 (verified at `design_docs/phases/milestone_12_audit_cascade/task_07_milestone_closeout.md`).
- Version-source citation at `ai_workflows/__init__.py:33` is correct.
- Roadmap fix (ADR-0008 → ADR-0010, `AIW_WORKFLOWS_PATH` → `AIW_EXTRA_WORKFLOW_MODULES`) named explicitly in §Deliverables and AC-1.
- AC-7 wheel-contents check matches CLAUDE.md non-negotiables verbatim.
- §Out of scope correctly excludes `uv publish` (manual-only per autonomous-mode boundary, locked 2026-04-27).
- Carry-over TA-LOW-02 (dep-auditor as parallel terminal-gate reviewer) is informational, not blocking.

## Cross-cutting context

- **Project memory.** `project_m13_shipped_cs300_next.md` confirms M16 T01 shipped (2026-04-24). No on-hold flag on M17. CS300 trigger framing applies — T02's CS300 dogfood is the first external-consumer smoke, documented (not automated).
- **Autonomous-mode boundary** preserved: T04 version bump + CHANGELOG promotion run on `design_branch`; only the operator runs `uv publish` after merge. KDR additions on isolated commits — T04 has no KDR additions.
- **Build-clean is necessary, not sufficient.** T02 AC-2 (live-smoke) is the only wire-level proof that the prompt actually works against Claude Opus + the validator. AC-8 (`pytest + lint-imports + ruff`) is build-clean only — correctly framed.
- **Status-surface flip plan (T04)** correctly enumerates four surfaces; no `tasks/README.md` exists for M17 (same as M12).

## Recommendation

The three specs are clean. Round 1 surfaced legitimate drift; round-1-to-round-2 fix-up applied each one correctly with no regression. No HIGH, MEDIUM, or LOW findings remain. The orchestrator can proceed to `/clean-implement m17 t02`.
