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
