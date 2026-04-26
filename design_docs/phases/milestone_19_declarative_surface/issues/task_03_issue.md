# Task 03 — Result-shape correctness: artefact-field bug fix + `plan` → `artifact` rename — Audit Issues

**Source task:** [../task_03_result_shape.md](../task_03_result_shape.md)
**Audited on:** 2026-04-26 (cycle 1) · **Re-audited:** 2026-04-26 (cycle 2)
**Audit scope:** `ai_workflows/workflows/_dispatch.py` (5 site migration + helper rename + scalar-wrap path), `ai_workflows/mcp/schemas.py` (`artifact` canonical + `plan` deprecated alias on `RunWorkflowOutput` + `ResumeRunOutput`), `tests/workflows/test_result_shape_correctness.py` (5 new hermetic regression tests), `tests/workflows/test_slice_refactor_apply.py` (1 assertion updated), `tests/workflows/test_slice_refactor_e2e.py` (2 assertions updated), `tests/mcp/test_gate_pause_projection.py` (1 assertion updated), `CHANGELOG.md` (3 entries under `[Unreleased]`), milestone status surfaces. Cross-referenced against ADR-0008, `design_docs/architecture.md` §3 + §6 + §7 + §9 (KDR-002/003/004/006/008/009/013), the M18 fold-in framing, the M11 T01 spec (`design_docs/phases/milestone_11_gate_review/task_01_gate_pause_projection.md`) which originally designed the `plan`-at-gate-pause "in-flight draft" semantics, and the predecessor T01 + T02 issue files. All three task gates re-run from scratch (`uv run pytest`, `uv run lint-imports`, `uv run ruff check`) plus the spec's smoke (`T03 schema smoke OK`) plus the schema-deprecation JSON-Schema introspection.

**Cycle 2 re-audit scope (2026-04-26):** Re-verified MEDIUM-1 propagation into `task_07_extension_model_propagation.md` (locked Path A); LOW-1 field-description rewrite in `mcp/schemas.py` for both `RunWorkflowOutput.artifact` and `ResumeRunOutput.artifact`; LOW-2 module-docstring path typo fix in `tests/workflows/test_result_shape_correctness.py`; CHANGELOG amendment under the existing `### Changed — M19 Task 03` entry. All three gates re-run from scratch on cycle 2 (687 passed, 9 skipped, 24 warnings; lint-imports 4 kept, 0 broken; ruff clean). All 14 cycle-1 ACs re-graded — none regressed.

**Status:** ✅ PASS (cycle 2 — 2026-04-26). All cycle-1 OPEN findings RESOLVED. MEDIUM-1 propagated to T07 (locked Path A); LOW-1 + LOW-2 fixed in-place. One LOW newly surfaced (LOW-3 — class-level docstring prose drift) but it is non-blocking and naturally absorbs into T07's documentation pass.

## Design-drift check

No KDR drift. The change is read-only against KDR-002/003/004/006/008/009/013 plus the four-layer rule:

- **Four-layer rule.** No new imports cross layers. `_dispatch.py` (workflows layer) imports unchanged; `mcp/schemas.py` (surfaces layer) imports unchanged. `lint-imports` reports `4 contracts kept, 0 broken` (104 dependencies, unchanged from cycle-1 of T02).
- **KDR-002 / KDR-008 (MCP wire surface).** Schema rename is *additive*: `artifact` is the new canonical field; `plan` is preserved with `deprecated=True` (pydantic 2.7+ marker) — verified to surface as `deprecated: true` in the JSON schema FastMCP exposes (`uv run python -c "...model_json_schema()..."`). Existing 0.2.0 callers reading `result.plan` continue to work — `pydantic` raises only a `DeprecationWarning` (visible in pytest's warnings summary, 11 entries) on read. No new MCP tool, no removed field, no required-field flip. KDR-008 preserved (additive growth is non-breaking).
- **KDR-003 (no Anthropic API).** Zero `anthropic` SDK imports added; zero `ANTHROPIC_API_KEY` reads. `grep` confirmed.
- **KDR-004 (validator pairing).** No LLM call sites added or removed.
- **KDR-006 (three-bucket retry).** No retry logic added or removed.
- **KDR-009 (SqliteSaver checkpoints).** No checkpoint-format change; no hand-rolled checkpoint write added.
- **KDR-013 (user code is user-owned).** No external-workflow loading change. The fix actually *honours* KDR-013 better than pre-T03 by ensuring an externally-registered workflow's `FINAL_STATE_KEY` is the truthful artefact source rather than a hardcoded `"plan"` literal — CS-300's 2026-04-25 smoke is the documented trigger.
- **Workflow tier names.** Unchanged.
- **MCP tool surface.** Four shipped tools unchanged; `RunWorkflowOutput` + `ResumeRunOutput` grow one canonical field + retain the alias. Additive.
- **External workflow loading.** `register()` collision check unchanged; no shadowing path opened.

ADR-0008 §Consequences ("`RunWorkflowOutput` schema redesigned") — implemented faithfully. The M18-fold-in framing (T03 = the artefact-loss bug fix + the rename, the rest of M18 obsoleted) is what shipped. Module docstring on `_dispatch.py` cites M19 T03 + ADR-0008 + the original `final.get("plan")` bug discovery context.

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| AC-1 — All 5 `final.get("plan")` call sites read `final.get(final_state_key)` | ✅ PASS | `grep -n 'final.get("plan")' ai_workflows/workflows/_dispatch.py` returns 0 matches in code (2 docstring/prose mentions retained as historical reference, which is correct). The 5 substituted sites are `_dump_artifact(final.get(final_state_key))` at: line 766 (`_build_result_from_final` `__interrupt__` branch), 830 (`_build_result_from_final` completed branch), 1031 (`_build_resume_result_from_final` `__interrupt__` branch), 1088 (`_build_resume_result_from_final` `gate_rejected` branch), 1107 (`_build_resume_result_from_final` completed branch). Error-path branches (5 in `_build_result_from_final` + 4 in `_build_resume_result_from_final` — counting both result-build helpers + the surface-boundary `except` in both `run_workflow` and `resume_run`) emit `"artifact": None, "plan": None` in lockstep. |
| AC-2 — `_dispatch._dump_plan` renamed to `_dump_artifact`; all call sites updated | ✅ PASS | `grep -rn '_dump_plan(' ai_workflows/ tests/` returns 0 hits in code; 3 prose-only mentions remain in module-level docstrings (correctly framed as "renamed from"). All 5 result-build call sites use `_dump_artifact`. The function definition is at `_dispatch.py:629`. |
| AC-3 — `RunWorkflowOutput.artifact` + `ResumeRunOutput.artifact` exist with the prescribed description; `plan` retained with `deprecated=True` | ✅ PASS | `RunWorkflowOutput.artifact` (`schemas.py:121-132`) + `ResumeRunOutput.artifact` (`schemas.py:207-219`) defined as `dict[str, Any] | None = Field(default=None, description=...)` matching Deliverable 2's prescribed text (with one minor framing variant — see LOW-1). Both `plan` fields (lines 133-140, 220-227) carry `deprecated=True`. pydantic 2.13.2 supports the marker; verified via `model_json_schema()` introspection — the `plan` properties carry `deprecated: true` in the emitted JSON schema. |
| AC-4 — Every result-build path populates both `artifact` and `plan` (lockstep) | ✅ PASS | All 9 result-dict literals across the two helpers + the 2 surface-boundary `except` blocks emit both keys. Test `test_error_path_emits_none_for_both_fields` covers the lockstep invariant on the error path; `test_external_workflow_artifact_also_surfaces_via_plan_alias` covers it on the completed path; the resume test covers it on the resume-completed path. |
| AC-5 — External `FINAL_STATE_KEY = "questions"` workflow round-trips through `artifact` | ✅ PASS | `test_external_workflow_artifact_round_trips_via_artifact_field` registers a stub with `FINAL_STATE_KEY = "questions"`, dispatches via `run_workflow`, asserts `result["artifact"] == questions_value`. Green. |
| AC-6 — Backward compat preserved (existing callers reading `.plan` keep working) | ✅ PASS | `test_external_workflow_artifact_also_surfaces_via_plan_alias` proves alias + canonical agree (`result["plan"] == result["artifact"] == questions_value`). The 11 `DeprecationWarning`s in the warnings summary confirm existing test sites that read `.plan` still work, just with a runtime deprecation warning (consistent with the spec's "deprecated alias preserved through 0.2.x" framing). |
| AC-7 — Resume path populates both fields | ✅ PASS | `test_resume_path_populates_both_fields` pauses a stub at a HumanGate, resumes with `"approved"`, asserts the resume response carries both fields populated equal to the artefact. Green. |
| AC-8 — Error path emits `None` for both fields | ✅ PASS | `test_error_path_emits_none_for_both_fields` registers a stub that raises; asserts the errored response has `artifact is None` and `plan is None` and both keys are present. Green. |
| AC-9 — Existing tests stay green | ⚠️ PASS-WITH-CAVEAT | 687 passed, 9 skipped — net 0 regressions in CI sense. **However:** 4 pre-existing tests had assertions weakened or flipped, 3 of which silently change observable behaviour for `slice_refactor` users at re-gate / gate_rejected. See **MEDIUM-1** below; this is an architectural regression of M11 T01 that is preserved by the test updates rather than fixed. The Builder report flagged "verify each updated test now asserts the corrected post-T03 behavior" — it does, but "corrected" is debatable for `slice_refactor`. |
| AC-10 — Module docstring on `_dispatch.py` cites M19 T03 + ADR-0008 + M18 fold-in | ✅ PASS | `_dispatch.py:1-72` module docstring cites M19 T03, ADR-0008 fold-in, and the M18 T01 origin. The `_build_result_from_final` and `_build_resume_result_from_final` function docstrings reference the rename and the lockstep invariant. The schemas module docstring (lines 28-33) cites M19 T03 + ADR-0008. |
| AC-11 — Smoke verification prints `T03 schema smoke OK` and exits 0 | ✅ PASS | Re-ran the spec's introspection probe verbatim. Output: `T03 schema smoke OK`. Both fields appear on both models. |
| AC-12 — Layer rule preserved (`lint-imports` 4 contracts kept) | ✅ PASS | `Contracts: 4 kept, 0 broken.` (re-run from scratch). 104 dependencies — unchanged from T02 cycle-2. |
| AC-13 — Gates green | ✅ PASS | `uv run pytest`: 687 passed, 9 skipped, 24 warnings (11 are the `DeprecationWarning`s for the `plan` alias — explicitly intended). `uv run lint-imports`: 4 kept, 0 broken. `uv run ruff check`: All checks passed! All three re-run from scratch this audit. |
| AC-14 — CHANGELOG entries (Fixed + Changed + Deprecated) under `[Unreleased]` | ✅ PASS | `[Unreleased]` carries `### Deprecated — M19 Task 03: ...` (lines 10-16), `### Changed — M19 Task 03: ...` (18-29), `### Fixed — M19 Task 03: ...` (31-58). Keep-a-Changelog vocabulary only. The Deprecated entry uses the canonical TA-LOW-01 phrasing: *"Deprecated alias preserved for backward compatibility through the 0.2.x line; removal target 1.0. Read `artifact` instead."* (line 13-14). KDR citations included on each entry. |

**Summary:** 13 ACs PASS, 1 PASS-WITH-CAVEAT (AC-9). The PASS-WITH-CAVEAT is the M11 T01 regression captured below as MEDIUM-1.

## Critical sweep — additional concerns

- **No silently-skipped deliverables.** Every Deliverable in the spec (1–8) is materialised in the diff.
- **No additions beyond spec for spec creep / coupling.** The two additions (lockstep `"artifact": None` on error paths, `_dump_artifact` scalar-wrap path) are both directly traceable to the spec's text and are necessary for the substitution to be safe (see Additions section).
- **Test gaps.** None for the spec ACs. There is **one gap in coverage** related to MEDIUM-1: no test asserts that the M11 T01 behaviour for `slice_refactor` re-gate is intentionally changed; instead, the existing M11 tests were silently updated to match the new behaviour. The right fix (see MEDIUM-1) is either (a) accept the behaviour change and document the M11 regression, or (b) restore M11 semantics by surfacing `gate_context` extras for slice_refactor. Neither was done.
- **Doc drift.** `architecture.md §4.4` mentions "`RunWorkflowOutput.plan` / `ResumeRunOutput.plan` carry the in-flight draft plan at `status='pending', awaiting='gate'`" (the M11 T01 framing) — the line is now stale on two counts: (1) field rename to `artifact`, (2) "in-flight draft" semantics are weaker for non-`plan`-keyed workflows. T07 ("Four-tier framing across architecture.md") is the natural owner for the rename update; the semantic-weakening is a separate concern (see MEDIUM-1). The spec explicitly defers docs to T05/T07, so doc drift here is **not** a T03 finding — flagged for T07's audit.
- **Secrets shortcuts.** None.
- **Scope creep from `nice_to_have.md`.** None.
- **Status-surface drift.** Four surfaces aligned:
  1. Per-task spec **Status:** line — `task_03_result_shape.md:3` reads `**Status:** ✅ Implemented (Builder cycle 1–2, 2026-04-26). Awaiting audit.` — flipped correctly.
  2. Milestone README task table row — `README.md:159` reads `| 03 | ... | code + test | — (independent of T01/T02) | ✅ Implemented (2026-04-26) |` — flipped correctly.
  3. `tasks/README.md` — does not exist for this milestone (`find . -name 'tasks' -type d` only matched vendored `fastmcp/server/tasks` directories). Inapplicable.
  4. Milestone README "Done when" / Exit criteria — Items 3 + 4 of the numbered Exit criteria block (lines 106-107) describe T03's deliverables; both are now satisfied. The README uses numbered-text Exit criteria, not `[ ]`/`[x]` markdown checkboxes, so there is nothing to flip per CLAUDE.md status-surface discipline literally — but the spec Builder cycle correctly made the criteria text correspond to landed behaviour. No drift.

## 🔴 HIGH

*None.* The spec's prescribed behaviour is implemented; gates green; KDRs preserved. The MEDIUM below is a behaviour change that the spec implicitly authorised but did not flag as a regression — it does not block AC pass.

## 🟡 MEDIUM

### MEDIUM-1 — M11 T01 in-flight-draft semantics regress for `slice_refactor` at re-gate + `gate_rejected` — RESOLVED 2026-04-26 (cycle 2)

**Cycle 2 resolution (2026-04-26):** User locked **Path A** ("accept the regression and document it") on 2026-04-26. Cycle 2 propagation verified: `task_07_extension_model_propagation.md` line 202 has the carry-over entry under `## Carry-over from prior milestones` with all required components (locked Path A 2026-04-26 cite; post-T03 honest behaviour `artifact=None` at slice_refactor_review gate; T07's documentation responsibilities — (a) architecture.md §"Extension model" notes that gate-pause projection follows `FINAL_STATE_KEY`; (b) `nice_to_have.md` candidate for `gate_review_payload_field` knob if a future consumer requests configurable gate-pause projection; locked Q5+H2 re-open trigger language cross-referenced). The carry-over composes with T07's existing scope (T07 already owns architecture + README + writing-a-graph-primitive + nice_to_have alignment) — the propagation does not require T07 to widen scope beyond what it already covers. Status: **RESOLVED — DEFERRED to T07 (audit-cycle close on T07 will RESOLVE the documentation surface; the behaviour shift itself is locked accepted under Path A).**

**Severity (original — preserved for audit history):** MEDIUM (spec-authorised behaviour change with downstream semantic impact; spec did not flag the regression).

**Where the regression lives.** `_dispatch._build_resume_result_from_final` lines 1031 (`__interrupt__` re-gate) and 1088 (`gate_rejected`). For `slice_refactor` only, both branches now return `artifact=None, plan=None` because:

- `slice_refactor.FINAL_STATE_KEY = "applied_artifact_count"` (`slice_refactor.py:238`).
- At the `slice_refactor_review` re-gate, `final["applied_artifact_count"]` is `None` (the artifact node hasn't run yet).
- At the `gate_rejected` terminal, `final["applied_artifact_count"]` is `None` (the artifact node never ran).
- Pre-T03 the dispatch read `final.get("plan")` literally, which surfaced the `PlannerPlan` written by the composed planner sub-graph — the M11 T01 "in-flight draft" / "last-draft for audit" payload an operator-at-gate could review.
- Post-T03 the dispatch reads `final.get("applied_artifact_count")` (`None`); the operator at `slice_refactor_review` now sees `artifact=None` / `plan=None` and has no reviewable artefact.

**M11 T01's load-bearing claim** ([`milestone_11_gate_review/task_01_gate_pause_projection.md:3-12`](../../milestone_11_gate_review/task_01_gate_pause_projection.md)):

> At a `HumanGate` pause, the MCP `run_workflow` / `resume_run` tools must return the **in-flight draft plan** and a minimum **gate-context projection** so the operator (or the Claude Code skill on their behalf) has something reviewable before they `resume_run`.

M11 T01's AC-4 + AC-5 explicitly tested `slice_refactor` for this:

- AC-4: *"`ResumeRunOutput.plan` and `.gate_context` mirror the above on re-gate resume (tested against `slice_refactor`, which has two gates)."*
- AC-5: *"`ResumeRunOutput.plan` is non-null on `status="gate_rejected"` (last-draft for audit). `gate_context` is `None` on that path."*

**The Builder updated 3 M11-era assertions to lock in the regression rather than mitigate it.**

- `tests/workflows/test_slice_refactor_e2e.py:323` — was `assert second["plan"] is not None` (with comment *"M11 T01: the re-gate pause projects the last-known planner plan so the operator has something to review …"*); now `assert second["artifact"] is None` + `assert second["plan"] is None`.
- `tests/workflows/test_slice_refactor_e2e.py:386` — was `assert third["plan"] is not None` (with comment *"M11 T01 Gap 1: rejected terminals now carry the last-draft plan for audit …"*); now `assert third["artifact"] is None` + `assert third["plan"] is None`.
- `tests/mcp/test_gate_pause_projection.py:343-353` — was `assert regated.plan is not None` + `assert isinstance(regated.plan, dict)`; now `assert regated.artifact is None` + `assert regated.plan is None`. The test name is `test_resume_run_regate_projects_plan_and_gate_context` — the test now no longer "projects a plan" (only the gate_context survives), but the test name was not updated.

The T03 spec's Deliverable 1 prose acknowledges the call sites cover *"resume-path re-gate, resume-path `gate_rejected` last-draft surface"* but prescribes the substitution uniformly — implicitly authorising the regression without naming it as one. The Builder followed the spec literally, which is correct per "spec wins" (CLAUDE.md `## Non-negotiables`). The audit's role is to surface the conflict.

**Why this is MEDIUM not HIGH:**

- The spec explicitly prescribed the substitution at all 5 sites (the spec wins per CLAUDE.md amendment rule).
- The pre-T03 behaviour was arguably *also* incorrect for `slice_refactor`: surfacing the planner's `PlannerPlan` at `slice_refactor_review` is semantically misleading — the operator at that gate is reviewing the slice aggregate (`SliceAggregate`), not the upstream plan. M11 T01's AC-4 was satisfied accidentally because slice_refactor happens to compose the planner sub-graph; the planner plan was the closest-available payload, not the right one.
- T03's CHANGELOG `### Fixed` entry is honest about the bug fix (the `final.get("plan")` hardcode is a real bug); it does not claim M11 semantics are preserved.
- `gate_context` is still populated at re-gate (the new tests assert this), so the operator is not entirely blind — they see the gate prompt and `gate_id`. The artefact channel is the regression.
- No external consumer is currently affected: CS-300 is mid-prototype against external workflows (with `FINAL_STATE_KEY` typically `!= "plan"`); the in-tree `slice_refactor` is solo-developer-only.
- A clean fix is out of scope for T03 and naturally lands in a future task: surface `slice_refactor`'s `SliceAggregate` (the actually-reviewable payload at `slice_refactor_review`) on `gate_context` extras or as the `applied_artifact_count` channel pre-populated to a sentinel / partial value at re-gate.

**Action / Recommendation.**

Two paths; the audit recommends path (a):

(a) **Accept the regression and document it.** Add a one-line note to T03's spec under §"Out of scope" naming the M11 T01 behaviour change as intentional + a forward-deferral entry under "## Carry-over from prior audits" on **a future task** (the right owner is **M19 T04** — the `summarize` proof-point — because T04 is the first task that authors a new workflow against the spec API and will surface "what does the operator see at gate?" naturally). Update the test names + comments in `tests/workflows/test_slice_refactor_e2e.py` + `tests/mcp/test_gate_pause_projection.py` to reflect the new "no draft surfaced; gate_context only" semantics rather than referencing a no-longer-truthful M11 T01 framing.

(b) **Mitigate inside T03.** Project `SliceAggregate` (or a workflow-specified "review payload") through `gate_context` extras on the re-gate / gate_rejected branches for `slice_refactor`. This requires touching `slice_refactor.py` + `_dispatch._extract_gate_context` + adding tests. Out of scope for T03 strictly read; would require user sign-off + a spec amendment.

**Forward-deferral target (cycle 1 proposal — superseded cycle 2):** M19 T04 spec — append a "## Carry-over from prior audits" entry naming `M19-T03-ISS-01` (severity MEDIUM, owner M19 T04) with the recommendation: *"M19 T03 substituted `final.get(final_state_key)` for `final.get('plan')` at all 5 dispatch result-build sites. For `slice_refactor` (whose `FINAL_STATE_KEY = 'applied_artifact_count'`), this regresses M11 T01's in-flight-draft / last-draft-for-audit semantics at the `slice_refactor_review` re-gate + `gate_rejected` paths — the operator now sees `artifact=None, plan=None` instead of the composed planner plan. The new `summarize` workflow shipping in T04 has only one LLMStep + ValidateStep, no gate, so it does not surface this gap. Decide at T04 review time whether (i) to accept the regression for slice_refactor as a no-action (the planner-plan-as-draft was always semantically wrong; only `gate_context` is honest at re-gate) and update test docstrings + comments to reflect that, or (ii) extend `gate_context` extras with a workflow-author-declared 'review payload' field that closes the M11 T01 hole. T04's spec or close-out is the natural decision point."*

**Forward-deferral target (cycle 2 — final, user-locked Path A 2026-04-26):** M19 T07 spec — entry landed at `task_07_extension_model_propagation.md` line 202 under `## Carry-over from prior milestones`. Path A accepts the regression as the honest reading of the bug fix; T07 is the natural documentation owner because it already covers architecture.md + README + nice_to_have.md alignment. The cycle-1 T04 framing is preserved above for audit history.

## 🟢 LOW

### LOW-1 — Schema field description for `RunWorkflowOutput.artifact` deviates slightly from the spec-prescribed text — RESOLVED 2026-04-26 (cycle 2)

**Cycle 2 resolution (2026-04-26):** Both `RunWorkflowOutput.artifact` (`schemas.py:121-137`) and `ResumeRunOutput.artifact` (`schemas.py:213-229`) field descriptions rewritten to match spec Deliverable 2 verbatim:
  - Re-added the planner / slice_refactor / external-workflow worked-example anchors (*"For the in-tree planner this is the approved PlannerPlan; for slice_refactor it is the applied-artefact count; for an external workflow it is whatever the workflow declares."*).
  - Replaced "in-flight draft at gate pause" wording with the locked Path A honest framing: *"At a gate-pause-resume response, reports the value of the workflow's FINAL_STATE_KEY channel — which may be ``None`` if the workflow's terminal artefact has not been computed yet (e.g. slice_refactor's ``applied_artifact_count`` is ``None`` at the ``slice_refactor_review`` gate)."* — directly addresses MEDIUM-1's concrete behaviour.
  - Both `plan` alias descriptions (`schemas.py:138-146`, `schemas.py:230-238`) now use the canonical TA-LOW-01 phrasing verbatim: *"Deprecated alias preserved for backward compatibility through the 0.2.x line; removal target 1.0. Read ``artifact`` instead."*
Verified via direct `Read` of `schemas.py`. No "in-flight draft at a gate pause" phrasing remains in either field description.

**Severity (original — preserved for audit history):** LOW (cosmetic; semantically equivalent).

**Where:** `ai_workflows/mcp/schemas.py:121-132`. The spec's Deliverable 2 prescribed:

> *"The workflow's terminal artefact — the value of the state field named by the workflow's FINAL_STATE_KEY (declarative spec: the first field of output_schema). For the in-tree planner this is the approved PlannerPlan; for slice_refactor it is the applied-artefact count; for an external workflow it is whatever the workflow declares. Surfaced through the deprecated `plan` field alias for backward compatibility through the 0.2.x line; removal target is 1.0."*

The Builder shipped:

> *"The workflow's terminal artefact — the value of the workflow's FINAL_STATE_KEY channel at run completion (or the in-flight draft at a gate pause). `None` on error/aborted paths. M19 T03 (ADR-0008): canonical field replacing the planner-specific 'plan' name so any workflow's artefact is surfaced correctly. The deprecated 'plan' alias carries the same value and is preserved for backward compatibility through the 0.2.x line; removal target 1.0."*

The shipped text is *more* informative (covers the at-gate-pause semantics + the error/aborted None branches + cites the ADR) but drops two examples the spec explicitly named (the planner's `PlannerPlan`, slice_refactor's count). Spec authors writing against this docstring lose the worked-example anchor. Note also that the shipped text says "in-flight draft at a gate pause" which is partly stale per MEDIUM-1 (it is no longer reliably the in-flight draft for non-`plan`-keyed workflows like `slice_refactor`).

**Action / Recommendation.** Re-add the two worked examples to both `RunWorkflowOutput.artifact` and `ResumeRunOutput.artifact` descriptions (one sentence; mechanical edit). Update the "in-flight draft at a gate pause" wording to either drop the framing or add the qualifier *"…when the workflow's FINAL_STATE_KEY channel is populated by an upstream node before the gate fires; otherwise `None`."* to be honest about MEDIUM-1's scope.

**Owner:** Optional follow-up in this task (in-place edit) or absorb into M19 T04 spec amendment.

### LOW-2 — Test-file docstring cites the wrong milestone path — RESOLVED 2026-04-26 (cycle 2)

**Cycle 2 resolution (2026-04-26):** `tests/workflows/test_result_shape_correctness.py:3` now reads `Spec: design_docs/phases/milestone_19_declarative_surface/task_03_result_shape.md`. Verified via `grep -n "milestone_19_workflow_contract\|milestone_19_declarative_surface" …` — only the corrected path matches; zero hits for `milestone_19_workflow_contract` anywhere in the test file. Repo-wide `grep -rn "milestone_19_workflow_contract" tests/ ai_workflows/` returns no remaining stale paths.

**Severity (original — preserved for audit history):** LOW (cosmetic).

**Where:** `tests/workflows/test_result_shape_correctness.py:3`:

```python
"""Regression tests for M19 Task 03 — result-shape artefact-field correctness.

Spec: design_docs/phases/milestone_19_workflow_contract/task_03_result_shape.md
```

The path `milestone_19_workflow_contract` does not exist; the actual path is `milestone_19_declarative_surface`. The directory was renamed during the M18 → M19 fold per ADR-0008.

**Action / Recommendation.** Fix the docstring path to `design_docs/phases/milestone_19_declarative_surface/task_03_result_shape.md`. Mechanical one-line edit.

**Owner:** This task (or absorb into the next test-touching task).

### LOW-3 — Residual "in-flight draft" / "re-gated draft" / "last-draft artefact" framing in class-level docstrings (cycle 2 — newly surfaced)

**Severity:** LOW (cosmetic; non-blocking; the field-description rewrite addressed the load-bearing surface — class-level prose is reader-facing, not contract-facing).

**Where:**
- `ai_workflows/mcp/schemas.py:91` — `RunWorkflowOutput` class docstring: *"`artifact` carries the in-flight draft for the operator to review"* (under `status="pending"` enum branch).
- `ai_workflows/mcp/schemas.py:178` — `ResumeRunOutput` class docstring: *"`artifact` carries the re-gated draft"* (under `status="pending"` enum branch).
- `ai_workflows/mcp/schemas.py:183-184` — `ResumeRunOutput` class docstring: *"`artifact` carries the last-draft artefact (for audit review)"* (under `status="gate_rejected"` enum branch).
- `ai_workflows/workflows/_dispatch.py:729` — function docstring: *"project the in-flight draft `artifact`"* (load-bearing-prose-only, but composes with the same M11 T01 framing the locked Path A retired).

LOW-1's cycle-2 fix updated the **field descriptions** (which surface to MCP clients via `model_json_schema()` introspection) to the locked Path A honest framing; the class-level + function-level docstring prose still carries the M11 T01 in-flight-draft language. For workflows whose `FINAL_STATE_KEY` channel is empty at the gate (e.g. `slice_refactor`'s `applied_artifact_count`), the class-level prose is now honest-but-incomplete. Not a contract issue — internal docstring drift only.

**Why this is LOW not MEDIUM:**
- The MCP wire-surface contract (field descriptions surfaced via `model_json_schema()`) is correct per LOW-1's cycle-2 fix. Class-level docstrings are not surfaced over the wire.
- The text reads "carries the in-flight draft" which is true *when the FINAL_STATE_KEY channel is populated by an upstream node before the gate fires* — i.e. it's not strictly false, just incomplete relative to the locked Path A framing.
- T07's documentation pass over `architecture.md §"Extension model"` is the natural place to update the prose to reflect the FINAL_STATE_KEY-following behaviour; T07's carry-over from T03 already covers the documentation-surface side.

**Action / Recommendation.** Absorb into T07's documentation pass (existing carry-over already covers the documentation surface; extending it to source-tree docstrings is a one-line addition). Specifically, when T07 updates `architecture.md §"Extension model"` to note that gate-pause projection follows `FINAL_STATE_KEY`, also touch up `mcp/schemas.py:91, 178, 183-184` + `_dispatch.py:729` class/function docstring prose to align with the same framing. Optional: a Builder may also choose to land this in a quick T03-cycle-3 if surface symmetry matters more than batching with T07's edits. **Owner:** T07 absorption recommended; alternatively a follow-up T03 cycle.

## Additions beyond spec — audited and justified

Two additions; both directly traceable to the spec's intent and necessary for safety. Neither adds coupling, scope creep, or `nice_to_have.md` adoption.

### Addition 1 — `_dump_artifact` scalar-wrap path (`{"value": <scalar>}`)

**Where:** `_dispatch.py:651-659`. Spec prescribed the rename only; Builder added a `else: return {"value": artefact}` fallback for non-pydantic, non-mapping values.

**Justification.** Pre-T03 the helper's input was always either a `PlannerPlan` (`hasattr(model_dump)`) or `None`; the `dict(plan)` branch existed but was never hit because `final.get("plan")` only ever returned a `PlannerPlan` or `None`. Post-T03 the input space widens to "anything any workflow's `FINAL_STATE_KEY` channel may hold". `slice_refactor`'s `FINAL_STATE_KEY = "applied_artifact_count"` is an `int`. Without the scalar-wrap, `dict(2)` raises `TypeError: cannot convert dictionary update sequence element #0 to a sequence`, which would surface as an unhandled exception in the completed branch. The Builder report flagged the fix and asked the auditor to verify the scalar-wrap is needed (it is) and doesn't break pydantic-model inputs (it doesn't — the `hasattr(model_dump)` branch fires first; verified by `test_in_tree_planner_unchanged_artifact_path`).

**Trade-off audited.** The wire shape `{"value": <scalar>}` is unambiguous for callers (a wrapper they can always destructure) but introduces a layer of indirection for scalar-keyed workflows. Caller code reading `result["artifact"]["value"]` for slice_refactor versus `result["artifact"]["goal"]` for planner is asymmetric. Acceptable: the alternative (typed `dict[str, Any] | None | int | str | …` union on the schema) breaks the existing `dict[str, Any] | None` typing, which would itself be MCP-wire-breaking.

**Verified by:** `test_dispatch_flips_status_completed_with_finished_at_for_slice_refactor` (asserts `result["artifact"] == {"value": 2}`).

### Addition 2 — `"artifact": None` on the surface-boundary `except` blocks in both `run_workflow` and `resume_run`

**Where:** `_dispatch.py:611, 957`. Spec prescribed the lockstep invariant at the result-build helpers; Builder extended it to the two surface-boundary `except` returns where dispatch catches before the helpers run.

**Justification.** The lockstep invariant must hold across *every* result-build path including the early-return error paths the surface-boundary catches build directly. Without this addition, a budget breach during a real workflow run (which routes through `wrap_with_error_handler` → `_extract_error_message` → the early-return dict) would emit `{"plan": None}` without `"artifact"` key, and `RunWorkflowOutput(**raw)` would still validate (both fields `None`-default), but the test contract `"artifact" in result` (asserted by `test_error_path_emits_none_for_both_fields` line 365) would fail. The addition is the literal spec text "every result-build path emits both" applied to its full scope.

**Verified by:** `test_error_path_emits_none_for_both_fields`.

## Gate summary

### Cycle 1 (2026-04-26)

| Gate | Command | Result |
| --- | --- | --- |
| Test suite | `uv run pytest` | ✅ PASS — 687 passed, 9 skipped, 24 warnings (11 are intentional `DeprecationWarning`s for the `plan` alias). 28.57s wall. |
| Layer rule | `uv run lint-imports` | ✅ PASS — `Contracts: 4 kept, 0 broken.` 104 dependencies. |
| Lint | `uv run ruff check` | ✅ PASS — `All checks passed!` |
| Spec-prescribed schema-introspection smoke | `uv run python -c "...print('T03 schema smoke OK')"` (Deliverable 7) | ✅ PASS — `T03 schema smoke OK` printed; both fields present on both models. |
| New regression test file | `uv run pytest tests/workflows/test_result_shape_correctness.py -v` | ✅ PASS — 5 tests, all green, 1.21s wall. |
| Updated pre-existing tests | `uv run pytest tests/workflows/test_slice_refactor_apply.py tests/workflows/test_slice_refactor_e2e.py tests/mcp/test_gate_pause_projection.py -q` | ✅ PASS — 23 passed, 13 warnings. |
| `grep` for hardcoded `final.get("plan")` in code | `grep -n 'final.get("plan")' ai_workflows/workflows/_dispatch.py` | ✅ PASS — 0 code matches; 2 prose-only docstring mentions retained as historical reference (correct). |
| `grep` for `_dump_plan(` call sites | `grep -rn '_dump_plan(' ai_workflows/ tests/` | ✅ PASS — 0 matches. |
| pydantic version supports `Field(deprecated=True)` | `uv run python -c "import pydantic; print(pydantic.VERSION)"` | ✅ PASS — 2.13.2 (≥2.7 required). |
| JSON schema surfaces deprecation marker | model_json_schema() introspection | ✅ PASS — both `plan` properties carry `deprecated: true`. |

All cycle-1 gates pass. Builder's gate report (687 passed, 9 skipped) is verified.

### Cycle 2 (2026-04-26)

| Gate | Command | Result |
| --- | --- | --- |
| Test suite (re-run from scratch) | `uv run pytest` | ✅ PASS — 687 passed, 9 skipped, 24 warnings (11 intentional `DeprecationWarning`s for the `plan` alias). 32.65s wall. **Identical pass count to cycle 1 — no regressions.** |
| Layer rule (re-run from scratch) | `uv run lint-imports` | ✅ PASS — `Contracts: 4 kept, 0 broken.` 104 dependencies (unchanged from cycle 1). |
| Lint (re-run from scratch) | `uv run ruff check` | ✅ PASS — `All checks passed!` |
| LOW-1 verification — no stale "in-flight draft" in field descriptions | `grep -n "in-flight draft at a gate pause" ai_workflows/mcp/schemas.py` | ✅ PASS — 0 matches in field descriptions; only one residual class-level docstring mention remains (LOW-3 — see above). |
| LOW-1 verification — TA-LOW-01 canonical phrasing in `plan` alias descriptions | `grep -n "deprecated alias preserved\|removal target 1.0\|0.2.x line" ai_workflows/mcp/schemas.py` | ✅ PASS — both `plan` alias descriptions and both `artifact` descriptions reference the canonical phrasing. |
| LOW-1 verification — worked examples present in `artifact` descriptions | `grep -n "approved PlannerPlan\|applied-\|external workflow" ai_workflows/mcp/schemas.py` | ✅ PASS — planner / slice_refactor / external-workflow framing present in both `RunWorkflowOutput.artifact` and `ResumeRunOutput.artifact` descriptions. |
| LOW-2 verification — test file docstring path corrected | `grep -n "milestone_19_workflow_contract\|milestone_19_declarative_surface" tests/workflows/test_result_shape_correctness.py` | ✅ PASS — only the corrected `milestone_19_declarative_surface` path matches; zero stale `milestone_19_workflow_contract` matches. |
| LOW-2 verification — repo-wide stale milestone path scrub | `grep -rn "milestone_19_workflow_contract" tests/ ai_workflows/` | ✅ PASS — 0 matches anywhere in source/tests. |
| MEDIUM-1 propagation verification | `grep -n "Path A\|locked\|MEDIUM-1\|FINAL_STATE_KEY\|gate_review_payload_field" task_07_extension_model_propagation.md` | ✅ PASS — carry-over entry at line 202 cites locked Path A 2026-04-26, names T07 documentation responsibilities (architecture.md §"Extension model" + nice_to_have.md gate_review_payload_field candidate), cross-references locked Q5+H2 re-open trigger. |
| Status-surface re-verify | `grep -n "Status:\|^| 03" task_03_result_shape.md README.md` | ✅ PASS — T03 spec status `✅ Implemented (Builder cycle 1–2, 2026-04-26)`; README task table row `✅ Implemented (2026-04-26)`; T07 status correctly unchanged at `📝 Planned`. |
| CHANGELOG amendment audit | direct read | ✅ PASS — cycle-2 amendment notes added to existing `### Changed — M19 Task 03` entry under `[Unreleased]` (CHANGELOG.md:28-40); Keep-a-Changelog vocabulary preserved; no new findings manufactured; no surface widening beyond what shipped. |

All cycle-2 gates pass. Builder's cycle-2 gate report (687 passed, 9 skipped, 24 warnings; lint-imports 4 kept; ruff clean) is verified end-to-end. No new HIGH or MEDIUM findings; one new LOW (LOW-3 — class-level docstring prose drift), naturally absorbed by T07.

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch | Status |
| --- | --- | --- | --- |
| M19-T03-ISS-01 | MEDIUM | M19 T07 (per locked Path A 2026-04-26; carry-over landed on T07 spec line 202) | RESOLVED 2026-04-26 (cycle 2) — DEFERRED to T07. Locked Path A accepts the regression; T07 owns the documentation surface. Re-audit at T07 close will RESOLVE the documentation-surface side; the behaviour shift itself is locked accepted. (Cycle-1 framing proposed T04 as owner; cycle-2 re-routed to T07 per user lock.) |
| M19-T03-ISS-02 | LOW | This task (cycle 2 mechanical in-place edit) | RESOLVED 2026-04-26 (cycle 2) — both `RunWorkflowOutput.artifact` + `ResumeRunOutput.artifact` field descriptions rewritten per LOW-1 above; verified via direct read + grep. |
| M19-T03-ISS-03 | LOW | This task (cycle 2 one-line test docstring fix) | RESOLVED 2026-04-26 (cycle 2) — `tests/workflows/test_result_shape_correctness.py:3` path corrected; verified via grep. |
| M19-T03-ISS-04 | LOW | M19 T07 (absorb into documentation pass) — see LOW-3 above | OPEN — newly surfaced at cycle 2 audit. Class-level + function-level docstring prose still references "in-flight draft" / "re-gated draft" / "last-draft artefact" framing from M11 T01. Non-blocking; T07's documentation pass over architecture.md §"Extension model" + adjacent docstrings is the natural absorption point. |

No HIGH issues; T03 implementation is functionally correct against the spec. **Cycle 2 close-out:** all cycle-1 OPEN findings RESOLVED. MEDIUM-1 propagated and locked Path A; LOW-1 + LOW-2 fixed in-place; one new LOW (LOW-3) surfaced and routed to T07 (the natural documentation-surface owner per its existing carry-over from this task).

This issue file flips to **`✅ PASS`**: HIGH=0, MEDIUM=0 (the cycle-1 MEDIUM is RESOLVED via locked Path A propagation), no still-OPEN issue blocks. The single OPEN LOW (LOW-3) is documented out-of-scope for T03 with an explicit T07 absorption pointer; non-blocking per CLAUDE.md severity definitions.

## Deferred to nice_to_have

T07's existing scope (Deliverable 5) already covers `nice_to_have.md` Q5+H2 trigger work. The cycle-1 audit noted M19-T03-ISS-01 is a milestone-bounded design decision rather than a parking-lot item. Cycle-2 user-locked Path A confirms this: the regression is *accepted* and *documented*, with a forward optionality knob (`gate_review_payload_field` on `WorkflowSpec`) earmarked as a `nice_to_have.md` candidate **only if** a future consumer requests configurable gate-pause projection. T07's carry-over from this task already names that condition. No separate `nice_to_have.md` entry is required from T03 itself — T07 owns the parking-lot ladder.

## Propagation status

### Cycle 2 (final — 2026-04-26)

- **M19-T03-ISS-01 → M19 T07 spec.** ✅ **LANDED.** User locked Path A on 2026-04-26 (accept the regression and document it; T07 is the natural documentation owner because it already covers architecture.md §"Extension model" + nice_to_have.md alignment). Carry-over entry verified at `design_docs/phases/milestone_19_declarative_surface/task_07_extension_model_propagation.md` line 202 under `## Carry-over from prior milestones`. Entry text confirmed to include all required components:
  - Cites the locked Path A 2026-04-26.
  - States the post-T03 honest behaviour (`artifact=None, plan=None` at slice_refactor_review re-gate + gate_rejected for slice_refactor).
  - Names T07's documentation responsibilities — (a) `architecture.md §"Extension model"` notes that gate-pause projection follows `FINAL_STATE_KEY`; (b) `nice_to_have.md` candidate for `gate_review_payload_field` knob if a future consumer requests configurable gate-pause projection.
  - Cross-references the locked Q5+H2 re-open trigger language ("a second external workflow with conditional routing or sub-graph composition").
  - Composes with T07's existing scope (T07 already covers architecture + README + writing-a-graph-primitive + nice_to_have alignment); no scope-widening forced on T07.

- **M19-T03-ISS-04 → M19 T07 spec (newly surfaced cycle 2).** Routed via the existing T07 carry-over (line 202 already names `architecture.md §"Extension model"` documentation work that naturally absorbs source-tree docstring prose touch-ups). No separate carry-over entry needed — LOW-3 is a one-line addition to T07's existing documentation pass scope.

### Cycle 1 (superseded — preserved for audit history)

- **M19-T03-ISS-01 → M19 T04 spec.** **Pending (cycle 1).** The cycle-1 audit recommended T04 as the forward-deferral target on the framing that T04 ships the first new workflow against the spec API and would naturally raise the "what does the operator see at gate?" question. Cycle-2 user lock on Path A re-routed the propagation to T07 (the documentation-surface owner) since the locked decision is "accept and document," not "decide accept-vs-mitigate at T04 review time." T04's carry-over is **not** updated; T07's is. Cycle-1 proposed text preserved in MEDIUM-1's body above for audit history.

  **Carry-over entry (proposed text for T04 spec):**

  > **M19-T03-ISS-01 — `slice_refactor` re-gate / gate_rejected lose M11 T01 in-flight-draft semantics post-T03** (severity: MEDIUM, source: M19 T03 audit cycle 1, 2026-04-26)
  >
  > M19 T03 substituted `final.get(final_state_key)` for the hardcoded `final.get("plan")` at all 5 dispatch result-build sites. For `slice_refactor` (whose `FINAL_STATE_KEY = "applied_artifact_count"`), this changes the operator-at-gate experience at `slice_refactor_review` re-gate + `gate_rejected`: pre-T03 the dispatch surfaced the composed planner sub-graph's `PlannerPlan` as the "in-flight draft" / "last-draft for audit" payload (M11 T01 AC-4 + AC-5); post-T03 both `artifact` and `plan` are `None` because `applied_artifact_count` is `None` until the artifact node runs. The pre-T03 behaviour was arguably also incorrect (planner plan != reviewable payload at `slice_refactor_review` — the SliceAggregate is what the operator wants to see), but the post-T03 behaviour is honest-but-empty.
  >
  > T04's `summarize` workflow has one `LLMStep` + one `ValidateStep` and no `HumanGate`, so `summarize` does not surface this gap directly. T04 is the right decision point because (1) it ships the first new workflow against the spec API and naturally raises the question *"what does the operator see at gate for spec-API workflows that pause?"*, and (2) any mitigation lives in `gate_context` extras / `_dispatch._extract_gate_context` which T04's e2e suite touches.
  >
  > **Recommendation:** Decide at T04 audit close. Two viable paths:
  >
  > (i) **Accept the regression** (recommended absent external pressure). Update test docstrings + comments in `tests/workflows/test_slice_refactor_e2e.py` (lines around 318–324, 384–387) + `tests/mcp/test_gate_pause_projection.py` (test name + body around lines 343–353) to drop the M11 T01 framing and document the new "gate_context-only at non-completed paths" reality. Add an `architecture.md §4.4` note that the in-flight-draft promise from M11 T01 is workflow-author-dependent under the post-T03 contract. Update `RunWorkflowOutput.artifact` + `ResumeRunOutput.artifact` field descriptions per M19-T03-ISS-02 to be honest about this scope.
  >
  > (ii) **Mitigate via `gate_context` extras.** Add a `WorkflowSpec.gate_review_payload_field: str | None` (or per-`GateStep` field) so spec-authored workflows can declare which state channel `_extract_gate_context` should surface as `gate_context["review_payload"]` at gate pause. Migrate `slice_refactor` (escape-hatch path) to populate the same channel via a static module-level constant. This recovers M11 T01's intent without baking workflow-specific state names into dispatch.
  >
  > **Owner:** Builder of T04 (or auditor at T04 close-out if T04 ships before this is decided). **Source:** [`M19 T03 issue file ISS-01`](../issues/task_03_issue.md).

- **Status of this propagation:** **NOT YET LANDED.** The audit recommends path (i) (accept + document). The user should confirm before the auditor edits T04's spec. Per the auditor protocol's "If the fix is unclear … stop and ask the user before finalising," this propagation is paused on user direction.

## Deferred to next-task verification

### Cycle 2 (T07 — final)

- M19-T03-ISS-01 — at T07 audit close, verify `architecture.md §"Extension model"` documents the gate-pause-follows-`FINAL_STATE_KEY` honest framing and (if relevant) the `gate_review_payload_field` `nice_to_have.md` candidate is captured under T07's parking-lot work. Cycle-2 propagation verified the carry-over entry; T07's audit will RESOLVE the documentation surface itself when T07 ships.
- M19-T03-ISS-04 — at T07 audit close, verify the four class-level + function-level docstring prose sites (`mcp/schemas.py:91, 178, 183-184` + `_dispatch.py:729`) are updated to align with the locked Path A framing. Optional in-place follow-up T03 cycle if surface symmetry matters more than batching.

### Cycle 1 (T04 — superseded; preserved for audit history)

- M19-T03-ISS-01 — verify `gate_context`-only behaviour at non-completed paths is documented + test docstrings updated, OR mitigation landed. **Superseded by cycle-2 user lock on Path A; T04 is no longer the propagation target.**

## Security review (2026-04-26)

**Reviewer:** security-reviewer subagent
**Scope:** T03 aggregate diff — `ai_workflows/workflows/_dispatch.py` (5-site migration + `_dump_artifact` rename + scalar-wrap), `ai_workflows/mcp/schemas.py` (`artifact` canonical + `plan` deprecated alias), `tests/workflows/test_result_shape_correctness.py` (new hermetic regression tests), updated pre-existing test files, CHANGELOG, spec/README status surfaces.
**Threat-model items checked:** Wheel contents (TM-1), KDR-003 no-API-key boundary (TM-2), `_dump_artifact` scalar-wrap injection surface (TM-3), `Field(deprecated=True)` runtime behaviour (TM-4), subprocess/network surface (TM-5), logging hygiene (TM-7).

### Critical — must fix before publish/ship

None.

### High — should fix before publish/ship

None.

### Advisory — track; not blocking

**ADV-1 — sdist leaks `.claude/`, `design_docs/`, `.env.example`, `uv.lock`, `CLAUDE.md`, `.github/` (pre-existing T01 HIGH-1, folded to T08)**

File/line: `dist/jmdl_ai_workflows-0.2.0.tar.gz` — confirmed by `tar tzf` inspection.
Threat-model item: TM-1 (wheel/sdist contents).
T03 does not widen the leakage surface — it adds no new non-`ai_workflows/` content. The 0.2.0 sdist already carries `.claude/settings.local.json` (no secrets — only Bash permission rules), `.env.example` (all placeholder values, `GEMINI_API_KEY=` empty), `design_docs/`, `.github/`, `CLAUDE.md`, `uv.lock`, `pricing.yaml`, `tiers.yaml`. None of the leaked files contain real credentials. The `.env.example` explicitly documents that `GEMINI_API_KEY` is left empty and instructs users to copy it to `.env`; the README's sample env blocks (if any) would need separate verification at next build. This finding is pre-existing and already tracked as T01 HIGH-1 → T08; T03 does not make it worse or better.
Action: No T03 action required. T08 owns the `MANIFEST.in` / `pyproject.toml` include-list fix.

**ADV-2 — `_dump_artifact` scalar-wrap path: scalar value is workflow-state-sourced, not MCP-input-sourced (informational confirmation)**

File/line: `ai_workflows/workflows/_dispatch.py:651-659`.
Threat-model item: TM-3 from the task brief.
The `{"value": <scalar>}` wrap accepts any value that a workflow's `FINAL_STATE_KEY` channel holds at completion. `final_state_key` is resolved from `getattr(module, "FINAL_STATE_KEY", "plan")` at `_dispatch.py:309` — a module-level constant set by the workflow author, not supplied by the MCP caller. The value of `final.get(final_state_key)` is produced by the workflow's own terminal node. Per KDR-013, workflow-authored code is user-owned; the framework does not police it. No MCP input path reaches the scalar-wrap without first passing through a LangGraph workflow node that the user wrote. No injection vector exists for external actors.
Action: None — informational confirmation only.

**ADV-3 — `Field(deprecated=True)` pydantic DeprecationWarning does not escalate to error (informational confirmation)**

File/line: `ai_workflows/mcp/schemas.py:138-146, 230-238`.
Threat-model item: TM-4 from the task brief.
Pydantic 2.13.2 (confirmed by prior audit grep) emits a `DeprecationWarning` on field access, not a runtime exception. The 11 `DeprecationWarning` entries in the pytest warnings summary are intentional and do not suppress unrelated warnings — pytest's warning capture is per-test-suite. At runtime in production (MCP server or CLI), pydantic `DeprecationWarning`s are routed through Python's standard `warnings` module; they do not raise. Both `plan` fields remain fully readable. No escalation risk.
Action: None — informational confirmation only.

### Items verified clean

- **KDR-003 boundary.** `grep -rn "ANTHROPIC_API_KEY\|import anthropic"` across all T03-touched files returns zero hits. Clean.
- **Subprocess / network surface.** No subprocess calls, no network calls, no `shell=True`, no `os.system` added in `_dispatch.py` or `mcp/schemas.py`. T03 is pure Python dispatch + schema work.
- **Test hermetic isolation.** `tests/workflows/test_result_shape_correctness.py` uses `monkeypatch.setenv` to redirect both `AIW_CHECKPOINT_DB` and `AIW_STORAGE_DB` to `tmp_path` — no writes to real DB paths, no filesystem side effects outside pytest's managed temp dir, no subprocess invocations, no network calls, no `.env*` reads.
- **Logging hygiene.** The two `_LOG.warning` calls in `_dispatch.py` (lines 694, 701) emit only `workflow` (registered name string) and `payload_type` (a Python type-name string). No artifact values, no API keys, no OAuth tokens, no prompt content appear in any log emit added or touched by T03.
- **Lockstep invariant.** All 9 result-dict literals across `_build_result_from_final` + `_build_resume_result_from_final` plus both surface-boundary `except` blocks emit both `artifact` and `plan` with identical values. `artifact == plan` at every code path — no silent divergence vector. Verified by direct code read and confirmed by functional audit AC-4 + AC-6 + AC-7.
- **CHANGELOG deprecation framing.** The `### Deprecated` entry names `1.0` as the removal target for `RunWorkflowOutput.plan` / `ResumeRunOutput.plan`. No date commitment — version-pinned only. Honest and non-misleading.
- **Privacy-positive gate-pause change.** Post-T03, `slice_refactor`'s re-gate and `gate_rejected` responses no longer incidentally surface the planner's `PlannerPlan` (the pre-T03 accidental exposure via `final.get("plan")`). The operator now sees `artifact=None, plan=None` at `slice_refactor_review` gate, which is the truthful reading. This is a reduction in incidental data surface — no new exposure introduced.

### Verdict: SHIP

T03 is dispatch-layer plumbing + schema alias work with a small, well-bounded threat surface. No new subprocess or network paths. No `ANTHROPIC_API_KEY` or `anthropic` SDK contact. No logging of sensitive values. The `_dump_artifact` scalar-wrap path is not reachable by external actors — only by workflow-authored nodes (KDR-013 user-owned boundary). The `Field(deprecated=True)` marker is safe at pydantic 2.13.2. The pre-existing sdist leakage (ADV-1) is unchanged from T01 HIGH-1 and is already tracked to T08; T03 does not widen or improve it. No security findings block this task.

## Dependency audit (2026-04-26)

**Skipped — no manifest changes.** T03 cycles 1+2 modified `ai_workflows/workflows/_dispatch.py`, `ai_workflows/mcp/schemas.py`, `tests/workflows/test_result_shape_correctness.py` (new), three pre-existing test files (assertions migrated to post-T03 behaviour), `CHANGELOG.md`, and a few design-docs files only. Neither `pyproject.toml` nor `uv.lock` was touched, so the dependency-auditor pass is not triggered per /clean-implement S2.
