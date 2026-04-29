# M12 Task 06 — Task Analysis

**Round:** 1 | **Analyzed on:** 2026-04-29 | **Analyst:** task-analyzer agent
**Specs analyzed:** `task_06_eval_harness_fixture_convention.md`

T01–T05 + T08 already shipped (✅ on `design_branch` per memory checkpoint `project_m12_autopilot_2026_04_27_checkpoint.md`); analysis confined to the freshly-drafted T06 spec per invoker scope.

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 2 |
| 🟡 MEDIUM | 3 |
| 🟢 LOW | 2 |

**Stop verdict:** OPEN

## Findings

### 🔴 HIGH

#### H1 — Spec mis-names the cascade node-name prefix in both golden tests + the user-facing convention doc

**Task:** T06
**Location:** `task_06_eval_harness_fixture_convention.md` lines 12–13, 33–34, 86, 92, plus AC #1 (line 110), AC #4 (line 113), AC #5 (line 114)
**Issue:** The spec asserts that cascade primary fixtures land at `<workflow>/<workflow>_primary/` (e.g. `planner/planner_primary/`, `slice_refactor/slice_worker_primary/`). This is wrong on both real wiring sites:

- **Planner** (`ai_workflows/workflows/planner.py:570`): `audit_cascade_node(..., name="planner_explorer_audit")` → primary `tiered_node` is constructed at `audit_cascade.py:312` with `node_name=f"{name}_primary"` = **`planner_explorer_audit_primary`**. Fixtures land at `evals/<dataset>/planner/planner_explorer_audit_primary/<case_id>.json`.
- **slice_refactor** (`ai_workflows/workflows/slice_refactor.py:1053`): `audit_cascade_node(..., name="slice_worker_audit")` → primary `tiered_node` `node_name` = **`slice_worker_audit_primary`**. Auditor is `slice_worker_audit_auditor`. Fixtures land at `evals/<dataset>/slice_refactor/slice_worker_audit_primary/`.

Spec line 92 even calls out a `slice_worker_primary` literal; production `name` argument is `slice_worker_audit`, not `slice_worker`. The `Note for Builder` block at lines 93–94 acknowledges this risk in the abstract ("verify the exact cascade-node base-name … if the actual base-name in production code is different (e.g. `slice_refactor_worker`)") but it gets the wrong direction — the production code uses a *longer* `_audit`-suffixed name, not a different stem. The note should pre-resolve the literals before the Builder hits them.

The mistake also propagates into the `evals/README.md` documentation block (lines 33–34) which would publish a literal that operators would `ls` against and find empty.

**Recommendation:** Fix every literal in the spec before implementation:

1. Update lines 12–13 + lines 33–34 of the convention example to show `<workflow>/<cascade_name>_primary/` (a placeholder), with a parenthetical "where `<cascade_name>` is the `name=` kwarg passed to `audit_cascade_node()` — `planner_explorer_audit` for planner, `slice_worker_audit` for slice_refactor".
2. Test 1 in `test_cascade_fixture_convention.py` (line 72) — drives `audit_cascade_node()` directly so the test author picks the `name=` kwarg. Pin `name="audit_cascade"` (the default) or any explicit value the test owns; then the primary directory is `audit_cascade_primary/` deterministically. Update assertion accordingly.
3. Test in `test_planner_cascade_fixture_golden.py` (line 86) — assert `<dataset>/planner/planner_explorer_audit_primary/<case_id>.json` and `<dataset>/planner/planner_explorer_audit_auditor/<case_id>.json`, plus `case.node_name == "planner_explorer_audit_primary"` (not `planner_primary`).
4. Test in `test_slice_refactor_cascade_fixture_golden.py` (line 92) — assert `<dataset>/slice_refactor/slice_worker_audit_primary/` and `<dataset>/slice_refactor/slice_worker_audit_auditor/`. The Builder note (lines 93–94) becomes unnecessary once the literal is resolved.
5. AC #1 (line 110) — describe the directory split as `<cascade_name>_primary/` + `<cascade_name>_auditor/` with the planner/slice_refactor literal expansions called out explicitly.

**Apply this fix:** Replace every `<workflow>_primary` / `<workflow>_auditor` / `planner_primary` / `slice_worker_primary` literal in T06 with the correct cascade-name-prefixed form per the production wiring above. Add a one-line cross-reference to `planner.py:570` and `slice_refactor.py:1053` so future readers can verify without re-deriving.

#### H2 — AC4's `EvalRunner` replay test requires a paired validator the cascade does not register for the auditor side; test will fail

**Task:** T06
**Location:** `task_06_eval_harness_fixture_convention.md` line 78 (test 4 of `test_cascade_fixture_convention.py`)
**Issue:** Test 4 asserts that "EvalRunner returns one case (the auditor)" when fed the auditor fixture directory. But `EvalRunner._invoke_replay` (`ai_workflows/evals/runner.py:284-344`) requires `_resolve_node_scope` to find a **paired validator** whose graph node-name = `f"{node_name}_validator"` (KDR-004). For the auditor node `<cascade_name>_auditor`, the cascade graph (`audit_cascade.py:531-540`) only registers nodes `{cascade_name}_primary`, `{cascade_name}_validator`, `{cascade_name}_auditor`, `{cascade_name}_verdict` (+ optional `_human_gate`). There is **no `<cascade_name>_auditor_validator` node** — auditor parsing is done by the verdict node (`_audit_verdict_node` calls `AuditVerdict.model_validate_json` directly, not via `validator_node`).

`runner.py:307-320` will therefore raise `_EvalCaseError("case references node 'X_auditor' but no paired validator 'X_auditor_validator' found in workflow … (KDR-004)")` — and the test asserts the runner *returns* one case, not that it errors.

The same problem exists more subtly for the primary-side replay: the cascade's primary validator IS registered as `f"{name}_validator"` = `<cascade_name>_validator` (single underscore segment), but `_resolve_node_scope` looks for `f"{<cascade_name>_primary}_validator"` = `<cascade_name>_primary_validator`. So the primary-side replay also fails the validator-pair lookup.

This is a real KDR-004 / replay-shape mismatch the cascade primitive was not designed against. T06's "no engine change" framing collides with the fact that the existing engine assumes a 1:1 `<node>_validator` naming convention that the cascade (intentionally) breaks because validator + verdict + primary all share the same retry-counter key per `audit_cascade.py:331-336`.

**Recommendation:** Stop and ask the user. Two reasonable resolutions:

- **Option A:** Drop test 4 from T06 scope. The convention T06 documents is the *capture-time directory split*, which is observable directly via `load_case(path)` (test 4 can use `EvalCase.model_validate_json(path.read_text())` without going through `EvalRunner`). Replay of cascade-emitted fixtures via `EvalRunner` becomes a follow-up task or a `nice_to_have.md` entry. The README's framing "No change to `EvalRunner`'s engine; fixture-naming convention only" stays honest — the convention IS just a directory split, and `EvalRunner` replay of the captured cascade fixtures is genuinely out of scope (and known-broken without engine change).

- **Option B:** Extend T06 scope to teach `EvalRunner._resolve_node_scope` about cascade-internal node-name conventions (e.g. when `node_name` ends in `_primary` look for `<base>_validator`, when `node_name` ends in `_auditor` skip the validator pair). This is an engine change (contradicting README Exit-criteria #9 + ADR scope) and a SEMVER-additive `_resolve_node_scope` behaviour change; would require its own KDR / ADR.

Option A is the README-aligned read; the milestone-level intent of #9 has always been the *capture-side* convention. Recommend Option A explicitly in the spec and re-frame test 4 as a `load_case`-only assertion ("auditor fixture is a valid `EvalCase` with `node_name=<cascade_name>_auditor` and `captured_from_run_id` matching the primary").

**Apply this fix:** Replace test 4 entirely with a `load_case` shape:

```python
def test_captured_fixtures_load_independently_as_eval_cases(tmp_path):
    # ... drive cascade once with capture wired (same as test 1) ...
    primary_path = next((tmp_path / "<dataset>" / "<workflow>" / "<cascade_name>_primary").glob("*.json"))
    auditor_path = next((tmp_path / "<dataset>" / "<workflow>" / "<cascade_name>_auditor").glob("*.json"))
    primary_case = load_case(primary_path)
    auditor_case = load_case(auditor_path)
    assert primary_case.node_name.endswith("_primary")
    assert auditor_case.node_name.endswith("_auditor")
    assert primary_case.captured_from_run_id == auditor_case.captured_from_run_id
```

…and update AC #1 + the README documentation to say "each captured fixture is independently loadable via `load_case` / `EvalCase.model_validate_json`; full-suite replay through `EvalRunner` is a follow-up (cascade nodes do not match the engine's `<node>_validator` pair-lookup convention)."

### 🟡 MEDIUM

#### M1 — `evals/README.md` already needs to coexist with non-empty `evals/planner/explorer/` + `evals/slice_refactor/slice_worker/` seed fixtures; the documented convention conflicts with the layout on disk

**Task:** T06
**Location:** Spec lines 20–52 (the proposed `evals/README.md` content)
**Issue:** The spec's documentation block describes paths shaped `evals/<dataset>/<workflow>/<cascade_name>_primary/<case_id>.json`. But `evals/planner/explorer/happy-path-01.json` and `evals/slice_refactor/slice_worker/happy-path-01.json` already exist on disk *without* a dataset segment. Those are seed fixtures from M7 T05 (per `tests/evals/test_seed_fixtures_deterministic.py`) and they live at `evals/<workflow>/<node>/` (no dataset dir), captured by hand or by a default-dataset capture. An operator reading the new convention doc would then `ls evals/` and see a layout with both shapes — flat `evals/planner/explorer/` AND dataset-segmented `evals/<dataset>/planner/<cascade>_primary/`.

The dataset segment is determined by `CaptureCallback.__init__` which appends `dataset_name` to `default_evals_root()` only when `root is None` — production opt-in via `AIW_CAPTURE_EVALS=<dataset>` always sets a dataset. Seed fixtures appear to have been authored bypassing that path (probably via `save_case()` direct).

**Recommendation:** Add one paragraph to the proposed `evals/README.md` body acknowledging the two-shapes-on-disk reality so operators don't get confused: hand-written or M7-T05 seed fixtures live at `evals/<workflow>/<node>/<case>.json` (the original M7 layout); capture-callback-emitted fixtures land at `evals/<dataset>/<workflow>/<node>/<case>.json` (M7 T02 layout, with `dataset` derived from `AIW_CAPTURE_EVALS`). The cascade convention this section documents is a sub-shape of the M7 T02 layout.

**Apply this fix:** Insert this paragraph into the spec's proposed README block, ahead of the cascade-fixture convention section:

```markdown
## Layout reference

Two shapes live in `evals/`:

- **Hand-written / seed fixtures** (M7 T05) — `evals/<workflow>/<node>/<case>.json`. Authored directly via `save_case()` or committed by hand. The `EvalRunner` finds them via `load_suite(workflow_id)`.
- **Capture-callback-emitted fixtures** (M7 T02) — `evals/<dataset>/<workflow>/<node>/<case>.json`. Written when a workflow run sets `AIW_CAPTURE_EVALS=<dataset>` (or a future surface threads `--capture-evals <dataset>`). The dataset segment disambiguates capture batches.

The cascade fixture convention below is a sub-shape of the second layout.
```

#### M2 — Test 2 + Test 3 cross-reference `CostTracker.by_role(run_id)` but the spec doesn't show how the same-run `CostTracker` instance is recovered after the graph invocation completes

**Task:** T06
**Location:** Spec lines 74–76 (test 2 + 3 of `test_cascade_fixture_convention.py`)
**Issue:** The tests claim to "query via the same-run `CostTracker.by_role(run_id)`". But `CostTracker` is constructed by `_dispatch._build_config` (`_dispatch.py:382-388`) and threaded into the config under `cost_callback` as a `CostTrackingCallback(cost_tracker=tracker)`. After `compiled.ainvoke()` returns, the tracker instance is reachable only through that callback or through the test's own scope. The spec does not say whether tests bypass `_dispatch.run_workflow` and build the config themselves (recovering `tracker` directly), or call `run_workflow` and then somehow recover the in-memory tracker.

If tests use `run_workflow`, the tracker is internal — `run_workflow` returns a `dict[str, Any]` shape with `total_cost_usd` aggregated, not the tracker handle. Builder will guess wrong (probably re-instantiate a `CostTracker` from scratch and find it empty), the test fails, and the round burns.

**Recommendation:** Tighten the spec for tests 2 + 3 to pin the cost-tracker recovery shape. Recommended (mirrors `tests/graph/test_audit_cascade.py:243` style): build the cascade graph inline in the test (do not go through `run_workflow`), construct your own `CostTracker` + `CostTrackingCallback`, thread both into config, drive `compiled.ainvoke()`, then assert against the local `tracker.by_role(run_id)`. Same `CaptureCallback` thread-through.

**Apply this fix:** Insert into test 1's setup (then 2/3 reuse the fixture):

```python
tracker = CostTracker()
cost_callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=None)
capture = CaptureCallback(dataset_name="test", workflow_id="cascade_test", run_id=run_id, root=tmp_path)
cfg = {"configurable": {
    "thread_id": run_id, "run_id": run_id,
    "tier_registry": tier_registry,
    "cost_callback": cost_callback,
    "eval_capture_callback": capture,
    "workflow": "cascade_test",
    "semaphores": {...},
}}
# … drive cascade …
roles = tracker.by_role(run_id)  # tests 2 + 3 assert against this
```

#### M3 — Status-surface AC mentions only items (a)/(b)/(c); CLAUDE.md non-negotiable lists four surfaces

**Task:** T06
**Location:** Spec line 122 (the status-surface AC)
**Issue:** AC enumerates: (a) spec Status line, (b) milestone README task-table row, (c) milestone README §Exit-criteria bullet 9. Missing the fourth surface from CLAUDE.md "Status-surface discipline": `tasks/README.md` row if the milestone has one. The M12 milestone does not have a `tasks/README.md` (verified — only README.md at milestone root), so the AC is functionally complete, but the framing should match the convention so the autopilot's surface-flip checker doesn't flag a phantom miss.

**Recommendation:** Add an explicit "(d) `tasks/README.md` — N/A; M12 has no `tasks/README.md`" line so the surface-flip discipline reads as four-of-four-considered, not three-of-four-listed.

**Apply this fix:** Append to AC line 122:
```
; (d) `tasks/README.md` row — N/A (M12 has no per-task subdirectory README).
```

### 🟢 LOW

#### L1 — Spec should explicitly mention that the planner integration writes `cascade_role` into `PlannerState` per `planner.py` lines 324–330 — clarifies why the `usage.role` source-of-truth (factory-time, not state-keyed) matters

**Task:** T06
**Location:** Spec lines 45–49 (the role-tag paragraph in the proposed `evals/README.md`)
**Issue:** The doc explains role is "stamped at `tiered_node` factory time (closure-bound), not read from graph state — so retried/re-fired cascade attempts inherit the correct role on every record." Correct, but the contrast would land harder if the doc explicitly named the alternative state surface (`state['cascade_role']`) and why telemetry does NOT key off it (state can be stale on retry; closure-bound role is not).

**Push to spec:** Add a single sentence to the convention-doc role-tag paragraph: *"Note: `state['cascade_role']` exists as a debug surface for in-flight inspection of which sub-node last ran, but `TokenUsage.role` is the persistent telemetry field — it is bound at `tiered_node` construction time per `audit_cascade.py:313, 349` and survives retry/re-fire correctly."*

Carry-over text for the spec:

> **TA-LOW-01 (Round 1):** In the proposed `evals/README.md` cascade-fixture-convention block, append one sentence to the role-tag paragraph clarifying the difference between `state['cascade_role']` (debug-only) and `TokenUsage.role` (telemetry source-of-truth). Pin the `audit_cascade.py:313, 349` references so future readers can verify the factory-time binding directly.

#### L2 — `_StubClaudeCodeAdapter` reuse claim is correct for `tests/graph/`; for `tests/workflows/` the spec cites `_E2EStubClaudeCodeAdapter` from `test_slice_refactor_cascade_enable.py:509` — that exact symbol may not exist there

**Task:** T06
**Location:** Spec line 90 (slice_refactor golden test stub-adapter cite)
**Issue:** Spec says "Stub slice_refactor LLM via the existing `_E2EStubClaudeCodeAdapter` (or sibling) at `tests/workflows/test_slice_refactor_cascade_enable.py:509`." Verified `tests/workflows/test_slice_refactor_cascade_enable.py` exists. Did not exhaustively verify the literal symbol `_E2EStubClaudeCodeAdapter` at line 509 — Builder may need to substitute whatever stub-adapter shape that test uses (the parenthetical "or sibling" already softens the citation, so this is a minor calibration rather than a hard-fail).

**Push to spec:** Builder reads `test_slice_refactor_cascade_enable.py` at implementation time, picks the stub-adapter pattern that matches (probably `_StubClaudeCodeAdapter` from `tests/graph/test_audit_cascade.py:107` is the safer canonical reuse target since it's already cited for the other test file).

Carry-over text for the spec:

> **TA-LOW-02 (Round 1):** When implementing `tests/workflows/test_slice_refactor_cascade_fixture_golden.py`, prefer to reuse the canonical `_StubClaudeCodeAdapter` shape from `tests/graph/test_audit_cascade.py:107` (already cited for `test_cascade_fixture_convention.py`); fall back to whatever stub-adapter is in use at `tests/workflows/test_slice_refactor_cascade_enable.py` only if `slice_refactor` requires a different fixture seed. Update the spec citation if the chosen adapter differs from `_E2EStubClaudeCodeAdapter`.

## What's structurally sound

- **Scope discipline preserved.** Spec correctly identifies T06 as documentation + golden tests over T02/T03/T04 surfaces already shipped. AC #1 list of `ai_workflows/` files NOT to touch (line 115) is exhaustive and well-scoped — no drive-by refactor risk.
- **KDR alignment.** No new KDR proposed; KDR-009 / KDR-011 / KDR-013 cited correctly and used as guardrails-not-extensions. KDR-003 guardrail unchanged.
- **No new dependency.** Confirmed — spec adds zero `pyproject.toml` / `uv.lock` diff; reuses existing `_StubClaudeCodeAdapter` pattern.
- **Hermetic-only test discipline.** No `AIW_E2E` requirement; capture is observable above the dispatch surface. Correct.
- **Verdict-node-no-fixture rule** (line 14) is verified: `_audit_verdict_node` (`audit_cascade.py:742`) does NOT call `tiered_node` — pure parse step, so no `eval_capture.on_node_complete` fires for it. Spec's claim correct.
- **Role-tag binding mechanism.** Verified at `tiered_node.py:122, 280-296` — `role` is a constructor kwarg, closure-captured, stamped onto every `TokenUsage` record on the success path. `cost.py:96-99, 154-169` confirms `CostTracker.by_role` aggregation surface exists.
- **Five import-linter contracts** confirmed at `pyproject.toml:143, 154, 164, 186, 195` — milestone README's "5 contracts kept" claim is accurate.
- **CHANGELOG `[Unreleased]` block exists** (line 8); T06 entry will land cleanly.
- **Two surfaces (planner + slice_refactor) opt into cascade** per T03 — golden-test-per-opt-in-workflow framing is correct (matches Exit-criteria #9 "One golden test per workflow that opts into the cascade").

## Cross-cutting context

- **M12 autopilot checkpoint** (memory `project_m12_autopilot_2026_04_27_checkpoint.md`): T06 is the next task; T07 close-out follows. T06's "doc + test only, no production code change" framing is correct for the post-T05 state. The roadmap-selector will return `m12 t06` next.
- **Carry-over forward-deferral to T07** (per milestone README §"Cumulative carry-over forward-deferred to M12 T07 close-out", lines 128–137): T06 should NOT bundle the four ADR-0004 stale-framing fixes — T07 owns those. Spec correctly omits them.
- **`evals/` directory state.** `evals/planner/explorer/happy-path-01.json` and `evals/slice_refactor/slice_worker/happy-path-01.json` already exist (seed fixtures from M7 T05). M1 above flags the README-doc layout-consistency issue. No fixtures yet land under any cascade-emitted path, so test cleanup discipline (`tmp_path` / `monkeypatch.setenv("AIW_EVALS_ROOT", ...)`) is critical to keep test runs hermetic.
- **No memory flag for M12 hold-status.** Milestone is in active autopilot resume state; T06 is timely.
- **No `nice_to_have.md` slot adoption.** T06 introduces no slot drift.

---

## Round 2

**Round:** 2 | **Analyzed on:** 2026-04-29 | **Analyst:** task-analyzer agent
**Specs analyzed:** `task_06_eval_harness_fixture_convention.md` (Round 2 confirmation pass after Round 1 fixes for H1/H2/M1/M2/M3 + L1/L2 → carry-over)

### Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 0 |
| 🟢 LOW | 0 (TA-LOW-01 + TA-LOW-02 already in spec carry-over) |

**Stop verdict:** CLEAN

### Verification of Round 1 fixes

All five fixes from the orchestrator's Round 1 application landed correctly and verifiably against the live codebase:

- **H1 fix verified.** Every cascade node-name literal in the spec now uses the correct `<cascade_name>_primary` / `<cascade_name>_auditor` form. Planner: `planner_explorer_audit_primary` / `_auditor` (spec lines 13, 66, 161-162, 164, 187, 190). Slice_refactor: `slice_worker_audit_primary` / `_auditor` (spec lines 13, 67, 169-170, 191). Cross-references to `planner.py:570` and `slice_refactor.py:1053` present and accurate. Verified against live code: `planner.py:570` reads `name="planner_explorer_audit"` ✅; `slice_refactor.py:1053` reads `name="slice_worker_audit"` ✅; `audit_cascade.py:312` constructs primary `tiered_node` with `node_name=f"{name}_primary"` ✅; `:348` constructs auditor with `node_name=f"{name}_auditor"` ✅. The "Note for Builder" abstraction-layer block was correctly removed.

- **H2 fix verified.** Test 4 (`test_captured_fixtures_load_independently_as_eval_cases`) at spec line 152 now uses `load_case(primary_path)` / `load_case(auditor_path)` only, asserts the `node_name` / `workflow_id` / `captured_from_run_id` triples for both fixtures, and explicitly states "**NOT** invoking `EvalRunner`". The KDR-004 carve-out is now documented in three coordinated places: spec §What to Build "Replay constraint" (lines 15), spec KDR guardrails (lines 177), spec Out-of-scope (line 212), and the proposed `evals/README.md` body (lines 77-83). AC #1 (line 187) reflects the carve-out. Forward-deferral logged at §Propagation status (line 238). Verified against live code: `EvalCase` schema has `case_id`, `workflow_id`, `node_name`, `captured_from_run_id` fields (`schemas.py:71-79`) ✅; `load_case(path)` exists at `storage.py:77` ✅.

- **M1 fix verified.** `evals/README.md` proposed content (spec lines 26-93) now opens with a `## Layout reference` section documenting both shapes: hand-written/seed fixtures (M7 T05, `evals/<workflow>/<node>/<case>.json`) and capture-callback-emitted fixtures (M7 T02, `evals/<dataset>/<workflow>/<node>/<case>.json`). Concrete on-disk examples cited at lines 40-41. Verified against filesystem: `evals/planner/explorer/happy-path-01.json` and `evals/slice_refactor/slice_worker/happy-path-01.json` exist ✅; `evals/README.md` does NOT yet exist (so spec's "If absent, create the file" branch applies) ✅.

- **M2 fix verified.** Spec setup pattern (lines 116-144) now shows inline cascade construction: `tracker = CostTracker()`, `cost_callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=None)`, `capture = CaptureCallback(dataset_name=..., workflow_id=..., run_id=..., root=tmp_path)`, both threaded into `config["configurable"]`. Tests 2+3 reference `tracker.by_role(run_id)` directly against the local `tracker` instance (lines 148, 150). The line "drives the cascade graph inline, not via `run_workflow`, so the test owns the `CostTracker` instance" is explicit at line 116. AC line 192 pins this convention. Verified against live code: `CostTracker.by_role(run_id)` at `cost.py:154` ✅; `CostTrackingCallback(cost_tracker=, budget_cap_usd=)` at `cost_callback.py:52-53` ✅; `CaptureCallback.__init__(dataset_name, workflow_id, run_id, *, root=None)` at `capture_callback.py:96-109` ✅. The `tier_registry` + `semaphores` config-keys mentioned in the setup are real and used by the canonical `tests/graph/test_audit_cascade.py` test file ✅.

- **M3 fix verified.** AC status-surface line at spec line 200 now reads "(d) `tasks/README.md` row — N/A (M12 has no per-task subdirectory README)". Verified against filesystem: `design_docs/phases/milestone_12_audit_cascade/tasks/` does not exist ✅. All four CLAUDE.md status surfaces enumerated.

- **L1, L2 verified in carry-over.** Spec lines 230-231 carry both `TA-LOW-01` (role-tag debug surface vs telemetry source-of-truth clarification — the sentence already lives in the proposed README at lines 88-92, so this is a verify-at-implementation-time carry-over) and `TA-LOW-02` (stub-adapter reuse — spec body now prefers `_StubClaudeCodeAdapter` from `tests/graph/test_audit_cascade.py:107` as the canonical reuse target, with the slice_refactor-specific fallback noted at line 168). Both LOWs are correctly framed for the Builder to absorb at implementation time without blocking.

### New issues found in Round 2

None. The hostile re-read surfaced no new HIGH or MEDIUM regressions from the Round 1 edits.

### Minor observations (informational, not findings)

- The milestone README task-table row 110 currently reads `📝 Planned (spec missing)` — when T06 lands, AC #11(b) will need the `(spec missing)` parenthetical dropped in addition to the Status flip from `📝 Planned` → `✅ Complete (YYYY-MM-DD)`. The spec's AC #11(b) says "row 06 Status column: `📝 Planned` → `✅ Complete (YYYY-MM-DD)`" which functionally covers this (the parenthetical is part of the Status column text), but a literal Builder might miss it. Not worth a finding — the Builder will see the actual cell content when editing the README and the surface-flip discipline catches it.

- Spec line 53 cites `ADR-0009 / KDR-014` in the cascade-fixture convention block. Verified `ADR-0009` exists at `design_docs/adr/0009_framework_owns_policy.md` ✅ (per milestone README line 113). No drift.

- Spec correctly avoids any production-code touch under `ai_workflows/` (AC line 193 enumerates the don't-touch list). Layer rule (`primitives → graph → workflows → surfaces`) is unaffected because T06 only touches `evals/README.md`, `.claude/skills/`, `tests/`, and `CHANGELOG.md`.

### What's structurally sound (Round 2 confirmation)

- All seven load-bearing KDRs preserved; KDR-003/004/009/011/013 explicitly cited as guardrails.
- No `pyproject.toml` / `uv.lock` diff (AC line 194). No dependency-auditor trigger.
- No `nice_to_have.md` slot adoption.
- Hermetic tests only; no AIW_E2E gate.
- Smoke test pinned (AC line 198).
- CHANGELOG `[Unreleased]` block noted (AC line 197).

The spec is ready for `/clean-implement m12 t06`.

---

## Round 3 — T07 initial analysis (task-analyzer, 2026-04-29)

**Round:** 3 | **Analyzed on:** 2026-04-29 | **Analyst:** task-analyzer agent
**Specs analyzed:** `task_07_milestone_closeout.md` (freshly drafted; T01–T06 + T08 already shipped on `design_branch`).

### Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 3 |
| 🟢 LOW | 4 |

**Stop verdict:** OPEN

### Findings

#### 🟡 MEDIUM

##### M1 — AC list omits explicit "flip row 07 in milestone README task-order table" surface

**Task:** T07
**Location:** `task_07_milestone_closeout.md` lines 100–113 (§Deliverables → milestone README block) + AC line 143
**Issue:** CLAUDE.md status-surface discipline requires four surfaces flip together; for the milestone README that is **two** distinct cells: the top-of-file `**Status:**` line *and* the row in the §"Task order" table. Verified in the live README (lines 70 of the milestone README): row 07 currently reads `| 07 | Milestone close-out | doc | 📝 Planned |`. The T07 spec only enumerates the top-of-file Status flip + the Outcome-section append; the §"Task order" row 07 cell is not called out as a deliverable nor as an AC. M11 T02 (the mirrored close-out spec) had the same omission shape and the close-out commit landed it implicitly via Builder discipline — but the spec being explicit removes any wiggle for a literal Builder.

Same gap exists for the §"Task order" row format. Other rows already flipped (T01..T06 + T08) all carry `✅ Complete (YYYY-MM-DD)`; T07 should follow.

Additionally, milestone README Exit-criteria item 10 (`tests/graph/test_audit_cascade.py + tests/workflows/test_audit_cascade_wiring.py — hermetic coverage of...`) currently has **no** check-marker prefix, while items 1–9 + 11–12 carry `✅` / `[x]`. Substantively the test coverage shipped at T02/T03; T07 close-out is the natural moment to flip item 10 to `✅ (T02/T03 complete 2026-04-27)`. Spec is silent on this. Either a deliverable or an explicit "out of scope, item 10 is descriptive of the wider hermetic-test surface and stays unchecked because no single task owns it."

**Recommendation:** Add two AC items:
- `[ ] Milestone README §"Task order" row 07 Status column flipped from "📝 Planned" to "✅ Complete (2026-04-29)".`
- `[ ] Milestone README §"Exit criteria" item 10 marked complete (or explicitly justified as left unchecked).`

And add a one-line bullet under §Deliverables → milestone README block:
- `Flip row 07 in §"Task order" table from "📝 Planned" to "✅ Complete (2026-04-29)" (matches every other already-shipped row's format).`

**Apply this fix:** Insert above plus an AC entry after current AC line 143 ("Milestone README Status flipped to `✅ Complete (2026-04-29)`; Outcome section covers all 8 tasks.") splitting it into three AC items: top-of-file Status flip, §"Task order" row 07 flip, §"Exit criteria" item 10 disposition.

##### M2 — Milestone README §"Cumulative carry-over forward-deferred to M12 T07 close-out" lists only 4 items; T07 spec carries 5 (missing CO-5)

**Task:** T07
**Location:** Milestone README lines 128–137 (the cumulative-carry-over section); T07 spec §Carry-over items (CO-5 lines 72–82)
**Issue:** Inconsistency between the milestone README's own forward-deferral roster and the T07 spec's carry-over set. The milestone README enumerates 4 items (4 stale-framing fixes — CO-1/CO-2/CO-3/CO-4). T07 spec adds a 5th: CO-5 (nice_to_have.md §25 EvalRunner cascade-fixture replay entry, sourced from T06 KDR-004 carve-out). T06 was the source — verified at `task_06_eval_harness_fixture_convention.md` (T06's "Replay constraint" / "Out of scope" sections explicitly defer cascade replay through `EvalRunner`).

This is not a HIGH because the T07 spec is the authoritative carry-over manifest at this point (the milestone README's roster was authored at T05 close-out, before T06 added the new carry-over). But the milestone README will outlive T07 as a reading surface; an operator reading the milestone README to understand what landed at T07 will miss CO-5 entirely. The T07 deliverable should backfill the milestone README's list.

**Recommendation:** Add a deliverable under §Deliverables (milestone README block):
- `Update §"Cumulative carry-over forward-deferred to M12 T07 close-out" to add CO-5 as the fifth bundled item: "**`nice_to_have.md` §25** EvalRunner cascade-fixture replay — from T06 spec / KDR-004 carve-out."`

And an AC item:
- `[ ] Milestone README §"Cumulative carry-over forward-deferred to M12 T07 close-out" backfilled with CO-5 (currently lists only CO-1–CO-4).`

**Apply this fix:** Three-line edit to the milestone README's bulleted list at line 132–135 — insert one new bullet after the existing four, citing T06 as the source. Same shape as the existing four bullets.

##### M3 — CO-3 "Required fix" leaves the second-clause staleness ("the MCP tool is a thin surface wrapper") implicit; Builder may rewrite only the first clause

**Task:** T07
**Location:** `task_07_milestone_closeout.md` lines 50–56 (CO-3 block)
**Issue:** ADR-0004 §Decision item 7's stale sentence is **two semicolon-joined clauses**:

> Internal routing reuses the same `AuditCascadeNode`; the MCP tool is a thin surface wrapper.

Both halves are stale per the T05 Option A landing:
- Clause 1: "Internal routing reuses the same `AuditCascadeNode`" — false; tool bypasses the cascade primitive.
- Clause 2: "the MCP tool is a thin surface wrapper" — false; the tool is a standalone, schema-compatible re-implementation that builds its own `tiered_node` + config + verdict-parse path (see `mcp/server.py` `_build_standalone_audit_config`, `_build_audit_configurable`, `_make_standalone_auditor_prompt_fn` — four private helpers, not "thin").

The spec's "Required fix" (line 56) says to "name Option A and explain that the tool invokes the auditor tier directly (standalone path independent of workflow sub-graph composition)" — implicitly addresses both clauses, but a literal Builder might preserve "the MCP tool is a thin surface wrapper" because the explicit prose only calls out the routing-reuse clause. The wrapper-vs-standalone distinction is the entire point of H1 Option A — both clauses must die.

**Recommendation:** Tighten the CO-3 "Required fix" prose to enumerate both clauses explicitly:

> Replace **both clauses** of the stale sentence:
> - Clause 1 ("Internal routing reuses the same `AuditCascadeNode`") — false; tool bypasses the cascade primitive.
> - Clause 2 ("the MCP tool is a thin surface wrapper") — false; tool is a standalone re-implementation (see `mcp/server.py`'s four `_build_standalone_*` helpers).
> Accurate replacement must name Option A (H1 locked 2026-04-27), explain that `run_audit_cascade` invokes the auditor `tiered_node` directly with caller-supplied `artefact_kind` (H2 Option A), and acknowledge that the cascade primitive remains the inline-workflow surface.

Same shape applies to CO-4 (the architecture.md line 105 sentence-fragment carries the same "reuses the `AuditCascadeNode` primitive" framing that needs to die — the spec already calls this out cleanly there, so CO-4 is fine; CO-3 is the underspecified one).

**Apply this fix:** Replace T07 spec lines 50–56 with the expanded "Required fix" text above.

#### 🟢 LOW

##### L1 — Outcome bullet list orders T08 before T03 (chronological), not numeric — flag for reader's eye

**Task:** T07
**Location:** Spec lines 103–112 (Outcome section under milestone README deliverable)
**Issue:** Bullet list reads T01 → T02 → T08 → T03 → T04 → T05 → T06 → T07 — chronological order matching the autopilot landing sequence (T08 was a T02 amendment that shipped before T03 per the milestone README §"Task order" sequencing exception). This is intentional and accurate, but a reader who scans by task number first will trip on the T08-between-T02-and-T03 placement.

**Push to spec:** Add a one-line parenthetical above the bullet list explaining the ordering choice:

> *(Bullets ordered chronologically per landing date — T08 amends T02 and ships before T03 per milestone README §"Task order" sequencing exception.)*

Carry-over text for the spec:

> **TA-T07-LOW-01 (Round 3):** When writing the Outcome section, prepend a one-line parenthetical explaining the chronological-not-numeric ordering of T08 in the bullet list, so readers don't mistake it for an editorial typo.

##### L2 — CO-5's nice_to_have.md entry spec lacks an "Integration sketch" body even though §Deliverables says all five canonical fields are required

**Task:** T07
**Location:** Spec lines 78–82 (CO-5 §Required addition) + spec line 98 (Deliverables note "following the established entry format: **What this would add**, **Why deferred**, **Trigger to adopt**, **Integration sketch**, **Related**")
**Issue:** The spec says the new §25 entry must follow the 5-field convention (matches §24's shape — verified). But CO-5's "Required addition" enumerates content for only 4 of the 5 fields: "What it would add", "Why deferred", "Trigger to adopt", "Related". No content sketched for "Integration sketch". Builder will either (a) write one freehand without explicit guidance, (b) skip it (then AC is technically unmet because the entry is missing a required field).

The §24 Integration sketch is concrete: *"Add compaction-resume handler to `auto-implement.md` + `clean-implement.md` Auditor spawn blocks. `trigger.value = 80000`. New task T29 (M20 if open, M21 otherwise). Effort: MEDIUM (1–2 days)."* — i.e. names the touchpoints + a trigger value + a follow-on task placement.

**Push to spec:** Add a 5th bullet to CO-5's Required addition (line 78 onwards) sketching the Integration approach:

> - **Integration sketch:** Either (a) extend `EvalRunner._resolve_node_scope` to recognise `_primary` / `_auditor` suffixes as cascade-internal node-name conventions and skip the validator-pair lookup for the `_auditor` side (validator is the cascade's `<cascade_name>_validator` node, not `<cascade_name>_primary_validator`), or (b) introduce a `CascadeEvalRunner` subclass that overrides `_resolve_node_scope` for cascade fixtures while leaving the base `EvalRunner` untouched. Touchpoints: `ai_workflows/evals/runner.py` (`_resolve_node_scope` + `_invoke_replay`), `tests/evals/test_runner.py` (new test cases for the cascade-replay path). New ADR required to record the validator-pairing carve-out per KDR-004.

Carry-over text for the spec:

> **TA-T07-LOW-02 (Round 3):** Add the missing 5th bullet ("Integration sketch") to CO-5's Required addition before implementation, so the Builder doesn't have to derive the technical sketch fresh while drafting the §25 entry. Without this, the Builder either lands a 4-field entry (AC fail because the spec says "all five canonical fields") or freehand-writes a sketch that may not match the actual `_resolve_node_scope` shape.

##### L3 — AC for "Zero `ai_workflows/` diff" cites comparison "against T06 landing commit" but doesn't pin the commit SHA

**Task:** T07
**Location:** Spec line 147 (AC zero-diff invariant)
**Issue:** AC reads "verify with `git diff --stat` against T06 landing commit" — but doesn't pin the SHA. The T06 landing commit is `e8f43c9` per `git log` at top of session. T07 will land its own commit; without a SHA pin, "T06 landing commit" is recoverable by `git log --grep "M12 Task 06"` but adds friction and risks Builder picking a different commit (e.g. an in-flight T06 fix-up commit). M11 T02's analogous AC pinned the comparison commit SHA explicitly (line 92–93 of M11 T02 spec).

**Push to spec:** Tighten AC line 147:

> `[ ] Zero `ai_workflows/` diff at T07 (docs-only invariant — verify with `git diff --stat e8f43c9..HEAD -- ai_workflows/` against the T06 landing commit `e8f43c9`).`

Carry-over text for the spec:

> **TA-T07-LOW-03 (Round 3):** Pin the T06 landing commit SHA (`e8f43c9` at time of T07 spec drafting) into the zero-diff AC so the Builder doesn't have to re-derive the baseline. If T07 starts from a later commit (e.g. an in-flight T06 fix-up shipped after `e8f43c9`), update the SHA at Builder pre-flight time.

##### L4 — Root README "Next" section currently points at M22 (post-M21); spec's "Update if applicable" hedge means Builder may unnecessarily rewrite

**Task:** T07
**Location:** Spec lines 130–132 (Root README deliverable)
**Issue:** Root README §Next currently reads "M21 is complete. The next planned milestone is **M22**, which will address any operator-resume items from M20/M21..." — verified at `README.md:148`. M12 closing does NOT change this narrative because M12 is older than M21 (M12 is being closed retroactively; M21 already shipped). Spec's hedge "Update the **Next** section if applicable (M13 or later milestone pointer)" is correct that nothing-to-do is the likely answer, but a literal Builder may still rewrite the section to "mention M12 complete" — adding noise that contradicts the linear-narrative-by-newest-milestone shape every other Next section uses.

**Push to spec:** Sharpen the spec to either (a) explicitly say "no change required to §Next — M21 is the newest milestone and its Next pointer at M22 is unaffected by M12 close-out", or (b) remove the §Next bullet entirely from the deliverables list (it's already noise-free if Builder skips it — but absence of explicit guidance risks unnecessary edits).

Carry-over text for the spec:

> **TA-T07-LOW-04 (Round 3):** The Root README §Next section ("M21 is complete. The next planned milestone is **M22**…") is unaffected by M12 close-out — M12 is older than M21, so the linear-narrative-by-newest-milestone surface stays as-is. Sharpen the spec from "if applicable" to "no change expected to §Next; M21's M22 pointer remains authoritative" so Builder doesn't add stale M12-mentioning prose to the §Next narrative.

### What's structurally sound

- **CO-1 / CO-2 / CO-4 source-text precision is verified.** Live ADR-0004 line 25 (CO-1 source), line 54 (CO-2 source), line 40 (CO-3 source), and architecture.md line 105 (CO-4 source) all match the spec's quoted current-text exactly. Builder will not have to hunt for the right sentence.
- **CO-5 slot is free.** nice_to_have.md highest-numbered section is §24 (Server-side compaction); §25 is unclaimed. No slot drift. Verified all sections from §1 onwards: §8 is missing (legacy gap, intentional — section numbers don't have to be contiguous); §25 is the right next slot.
- **All seven load-bearing KDRs preserved.** T07 is docs-only — zero risk of KDR-002/003/004/006/008/009/013 violation. Spec correctly forbids any `ai_workflows/` diff.
- **Layer rule unaffected.** No production-code touch; primitives → graph → workflows → surfaces remains untouched.
- **Status-surface discipline four-of-four enumerated** if M1 above is applied: (a) per-task spec Status, (b) milestone README §Status + §"Task order" row 07 + §"Exit criteria" item 10, (c) `tasks/README.md` — N/A (verified no `tasks/` subdir under `milestone_12_audit_cascade/`), (d) roadmap.md row.
- **CHANGELOG handling matches M11 T02 precedent.** Promote `[Unreleased]` block (currently contains T06 entry + T05/T04/T03/T02/T01 entries) into a dated `[M12 Tiered Audit Cascade] - 2026-04-29` section + retain `[Unreleased]` skeleton + add T07 entry at top of new section. Mirror exact.
- **Roadmap.md format correctly differentiates lower-case "planned" from emoji "📝 Planned".** Spec line 117 says `from 'planned' to '✅ complete (2026-04-29)'` (lowercase, no emoji) — matches the live cell text format. Spec line 102 uses capital `📝 Planned` → `✅ Complete (2026-04-29)` for the milestone README — matches that file's convention. No format conflation.
- **No SEMVER touch.** Version stays at `0.3.1` (verified at `ai_workflows/__init__.py:33`). T07 is docs-only; no `pyproject.toml` version bump implied. Spec correctly omits any version-bump deliverable.
- **No `nice_to_have.md` adoption.** §25 is a NEW deferred entry, not an adoption — KDR-014 + ADR-0009 already cover the architectural promotion story for the audit cascade. CO-5 is parking-lot bookkeeping, not promotion.
- **No `pyproject.toml` / `uv.lock` diff.** No dependency-auditor trigger.

### Cross-cutting context

- **M12 autopilot resume target.** Per memory `project_m12_autopilot_2026_04_27_checkpoint.md` and the milestone README §"Autopilot checkpoint", T07 is the final task of M12 — the only task left after T06 closed today. The spec is appropriately scoped for a doc-only close-out.
- **No memory flag for M12 hold-status.** Milestone is in active autopilot resume state; T07 is timely.
- **CHANGELOG `[Unreleased]` block contains 6 M12 entries** (T01–T06) — verified at lines 8 onwards. T07's promotion-to-dated-section deliverable will sweep all six into the new dated section, and T07's own entry will sit at the top.
- **No cross-task collision.** No other in-flight task spec touches ADR-0004, architecture.md §4.4 line 105, nice_to_have.md §25, roadmap.md M12 row, root README M12 row, or milestone README §Status. T07 is the sole owner of all five surfaces.
- **The `_DynamicState["slice"]` workflow-name leak (T03 audit `M12-T03-LOW-05`) is correctly OUT of T07 scope** per spec line 159 + milestone README §138. Future task triggered by "first non-`slice` embedding workflow." Spec discipline preserved.
- **AC line 148** ("uv run pytest + lint-imports (5 contracts) + ruff all clean") matches the live state — verified `lint-imports` runs 5 contracts post-T02 (per milestone README exit-criterion 11). No drift.

---

## Round 4 — T07 re-read after MEDIUM fixes (task-analyzer, 2026-04-29)

**Round:** 4 | **Analyzed on:** 2026-04-29 | **Analyst:** task-analyzer agent
**Specs analyzed:** `task_07_milestone_closeout.md` (hostile re-read after Round 3 MEDIUM fixes M1/M2/M3 + LOW carry-over).

### Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 0 |
| 🟢 LOW | 0 (Round-3 LOWs all carried over into spec §Carry-over from spec-hardening) |

**Stop verdict:** CLEAN

### Verification of Round 3 fixes

All three MEDIUM fixes from Round 3 landed correctly and verifiably; all four LOWs were correctly carried into the spec rather than left open:

- **M1 fix verified (Task-order row 07 + Exit-criteria item 10 + new ACs).** Spec §Deliverables → milestone README block (lines 105–110) now enumerates four explicit deliverable bullets: Status flip, §"Task order" row 07 flip, §"Exit criteria" item 10 flip to `✅ (T02/T03 complete 2026-04-27)`, and §"Cumulative carry-over" CO-5 backfill. Three new ACs added at lines 152–154 mirror these ("§"Task order" row 07 Status column flipped", "§"Exit criteria" item 10 marked", "§"Cumulative carry-over" backfilled with CO-5"). Verified against live milestone README: row 07 at line 70 currently reads `| 07 | Milestone close-out | doc | 📝 Planned |` (matches the spec's "from" state); §"Exit criteria" item 10 (lines 35–36 of the README) is unchecked while items 1–9 + 11–12 carry `✅` (matches the spec's claim); §"Cumulative carry-over" at lines 128–137 enumerates 4 items (matches the spec's "currently lists only CO-1–CO-4" claim). All three surface flips resolve cleanly.

- **M2 fix verified (CO-5 5-field convention).** CO-5 §Required addition (spec lines 82–87) now enumerates all five canonical nice_to_have entry fields: **What it would add**, **Why deferred**, **Trigger to adopt**, **Integration sketch**, **Related**. The Integration sketch (line 86) names both Option A (extend `_resolve_node_scope`) and Option B (`CascadeEvalRunner` subclass), pins touchpoints (`ai_workflows/evals/runner.py` `_resolve_node_scope` + `_invoke_replay`, `tests/evals/test_runner.py`), and notes "New ADR required to record the validator-pairing carve-out per KDR-004." Verified against `nice_to_have.md` §24 (the highest-numbered live entry, line 557+): same 5-field convention (What this would add / Why deferred / Trigger to adopt / Integration sketch / Related). CO-5's shape is conformant. AC line 150 ("`nice_to_have.md` §25 EvalRunner cascade-fixture replay entry added with trigger + integration sketch") covers the additive surface. The §Deliverables block at line 103 also names the five-field convention explicitly ("**What this would add**, **Why deferred**, **Trigger to adopt**, **Integration sketch**, **Related**"), so the Builder cannot accidentally drop a field.

- **M3 fix verified (CO-3 both clauses enumerated).** CO-3 §Required fix (spec lines 56–60) now explicitly enumerates **both** stale clauses: Clause 1 ("Internal routing reuses the same `AuditCascadeNode`") and Clause 2 ("the MCP tool is a thin surface wrapper"), with concrete refutation evidence for each (Clause 2 cites `mcp/server.py`'s `_build_standalone_audit_config`, `_build_audit_configurable`, `_make_standalone_auditor_prompt_fn` and the fourth build helper). Accurate-replacement constraints are pinned: "must name Option A (H1 locked 2026-04-27), explain that `run_audit_cascade` invokes the auditor `TieredNode` directly with caller-supplied `artefact_kind` (H2 Option A), and acknowledge that `AuditCascadeNode` remains the inline-workflow surface." Builder cannot rewrite only the first clause. Verified against live ADR-0004 line 40: the actual sentence reads `Internal routing reuses the same AuditCascadeNode; the MCP tool is a thin surface wrapper.` — exactly the two-clause shape the fix enumerates.

- **L1–L4 all carried over correctly.** Spec lines 173–180 contain a new §"Carry-over from spec-hardening (task-analyzer Round 3 LOWs — push to Builder)" section enumerating all four Round-3 LOWs verbatim:
  - **TA-T07-LOW-01** (chronological-not-numeric T08 ordering parenthetical) — line 177.
  - **TA-T07-LOW-02** (use the CO-5 Integration sketch verbatim, do not derive new) — line 178.
  - **TA-T07-LOW-03** (T06 landing commit SHA `e8f43c9` — verified live: `git log` HEAD shows `e8f43c9 M12 Task 06: harden T06 spec…`, but actually T06 LANDING commit is per memory checkpoint; the spec also embeds the SHA into AC line 158 directly: `git diff --stat e8f43c9..HEAD -- ai_workflows/`) — line 179.
  - **TA-T07-LOW-04** (Root README §Next is unaffected by M12 close-out) — line 180.
  Section framing ("not ACs but should be followed during implementation") matches the carry-over discipline used elsewhere (T06 spec §"Carry-over from spec-hardening"). Plus, the Root README §Next deliverable text at spec lines 138–140 was sharpened from the Round-3 hedge to an explicit "**No change to the §Next section.** ... Do not add M12-mentioning prose to the §Next narrative." — this lifts TA-T07-LOW-04 from a guidance carry-over into a deliverable-level instruction, which is even stronger than the Round-3 recommendation.

### New issues found in Round 4

**None.** The hostile re-read surfaced no new HIGH or MEDIUM regressions from the Round-3 edits.

### Minor observations (informational, not findings)

- **AC line 158 SHA pin is robust.** The zero-diff AC now reads `verify with git diff --stat e8f43c9..HEAD -- ai_workflows/` against T06 landing commit `e8f43c9`; update SHA at Builder pre-flight if a later commit has since landed on `design_branch`. This handles both the happy path (no intervening commit) and the drift path (the Builder swaps the SHA at pre-flight). The carry-over TA-T07-LOW-03 reinforces this. Verified against live `git log -5 --oneline`: `e8f43c9` is the T06 landing commit on `design_branch`. Spec is internally consistent.

- **Outcome-section bullets cover all 8 tasks (lines 112–121).** T01–T08 each have a one-line summary; bullet ordering is T01 → T02 → T08 → T03 → T04 → T05 → T06 → T07 (chronological per Round-3 L1 finding). The Builder will follow TA-T07-LOW-01 to prepend the parenthetical explaining the ordering. Each bullet correctly attributes the landing artifact (e.g. T03 → "module-constant cascade enable + `AIW_AUDIT_CASCADE*` env-var overrides for `planner` + `slice_refactor`; KDR-014 / ADR-0009 locked decision"). No misattribution. T05's bullet correctly says "Option A standalone path (bypasses `AuditCascadeNode`)" — consistent with CO-3's required-fix framing. The "KDR additions" bullet at line 120 names KDR-011 + KDR-014 + ADR-0004 + ADR-0009 — accurate per milestone README line 113.

- **CHANGELOG section lines 127–134** correctly enumerate CO-1/2/3 (ADR-0004 amendments), CO-4 (architecture.md framing fix), CO-5 (nice_to_have.md §25), the 5-contract lint-imports snapshot, and the docs-only zero-diff invariant. Mirror of the M11 T02 close-out shape.

- **Out-of-scope block (lines 167–171)** correctly excludes the `_DynamicState["slice"]` workflow-name leak (T03 audit `M12-T03-LOW-05`) and cascade-depth tuning / shared-quota circuit breaker / cross-workflow telemetry dashboard. Spec discipline preserved.

- **Spec internal consistency.** The CO-5 §Required addition Integration sketch (line 86) and the carry-over guidance TA-T07-LOW-02 (line 178) both point to the same prose — "Builder should use that sketch verbatim — do not derive a new one from scratch." This is mutually reinforcing, not duplicative.

- **AC count consistency.** Spec lists 14 ACs (lines 146–159). Each AC maps to a deliverable bullet: CO-1 → AC1, CO-2 → AC2, CO-3 → AC3, CO-4 → AC4, CO-5 → AC5, milestone README Status → AC6, milestone README task-order row 07 → AC7, milestone README exit-criteria item 10 → AC8, milestone README cumulative-carry-over → AC9, roadmap.md → AC10, CHANGELOG → AC11, root README → AC12, zero-diff invariant → AC13, gates → AC14. No orphan deliverables, no orphan ACs.

### What's structurally sound (Round 4 confirmation)

- All three Round-3 MEDIUMs resolved with explicit deliverable + AC pairs (no implicit Builder discretion left).
- All four Round-3 LOWs surfaced as a §Carry-over section the Builder reads at implementation time; one of them (TA-T07-LOW-04 §Next) was promoted into a stronger deliverable-level instruction rather than left as guidance.
- All seven load-bearing KDRs preserved (T07 is docs-only, zero `ai_workflows/` diff per AC13).
- Layer rule (`primitives → graph → workflows → surfaces`) unaffected — no production-code touch.
- Status-surface discipline is now four-of-four explicitly addressed: (a) per-task spec Status, (b) milestone README §Status + §"Task order" row 07 + §"Exit criteria" item 10, (c) `tasks/README.md` — N/A (no per-task subdir under M12), (d) roadmap.md row.
- CHANGELOG handling matches M11 T02 precedent (promote `[Unreleased]` to dated `[M12 Tiered Audit Cascade] - 2026-04-29`, retain skeleton, T07 entry at top).
- nice_to_have.md slot §25 free (verified live: §24 is the highest-numbered section; legacy §8 gap is intentional). No slot drift.
- No SEMVER touch (version stays at `0.3.1`, verified at `__init__.py:33` per Round-3 verification — unchanged).
- No `pyproject.toml` / `uv.lock` diff; no dependency-auditor trigger.

### Cross-cutting context

- **M12 autopilot resume target unchanged.** T07 is the final task; spec is now ready for `/clean-implement m12 t07`.
- **No memory flag for M12 hold-status.** Milestone is in active autopilot resume state; T07 is timely.
- **No cross-task collision.** Confirmed Round 3 still holds: no other in-flight task spec touches ADR-0004, architecture.md §4.4 line 105, nice_to_have.md §25, roadmap.md M12 row, root README M12 row, or milestone README §Status.
- **The spec is internally consistent and complete enough for a Builder to execute without ambiguity.** Every CO has a quoted "current text" + "required fix" + Builder-discretion boundary; every status-surface flip has a concrete from→to literal; every carry-over LOW has implementation-time guidance.

The spec is ready for `/clean-implement m12 t07`.
