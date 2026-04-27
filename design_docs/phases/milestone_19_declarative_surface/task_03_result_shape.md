# Task 03 — Result-shape correctness: artefact-field bug fix + `plan` → `artifact` rename (folded from M18 T01)

**Status:** ✅ Complete (2026-04-26).
**Grounding:** [milestone README](README.md) · [ADR-0008 §Consequences (`RunWorkflowOutput` schema redesigned)](../../adr/0008_declarative_authoring_surface.md) · [KDR-008 (FastMCP + pydantic schema is public contract — backward compatibility preserved via `plan` alias)](../../architecture.md) · [`ai_workflows/workflows/_dispatch.py:540-602`](../../../ai_workflows/workflows/_dispatch.py#L540-L602) (the bug site — `final.get("plan")` hardcoded across multiple result-build paths) · [`ai_workflows/workflows/_dispatch.py:670-810`](../../../ai_workflows/workflows/_dispatch.py#L670-L810) (`_build_result_from_final` — primary fix site) · [`ai_workflows/mcp/schemas.py`](../../../ai_workflows/mcp/schemas.py) (the pydantic schemas being renamed) · CS-300 pre-flight smoke 2026-04-25 (the trigger for the bug discovery; recorded in ADR-0008 §Context).

## What to Build

Two coordinated correctness fixes, foldable into one task because they touch the same surface (`_dispatch.py` result-build paths + `mcp/schemas.py` field definitions):

1. **Bug fix:** `_dispatch.py` lines 721, 781, 977, 1034, 1048 read `final.get("plan")` for the response artefact field, but completion detection one branch up uses the configurable `final.get(final_state_key)`. This split silently drops the artefact for any workflow whose `FINAL_STATE_KEY != "plan"` — the workflow is correctly detected as completed but its terminal artefact never reaches the response. CS-300's 2026-04-25 smoke surfaced this with `FINAL_STATE_KEY = "questions"`. In-tree `slice_refactor` (`FINAL_STATE_KEY = "applied_artifact_count"`) is also affected — the count is detected, never surfaced.
2. **Schema rename:** `RunWorkflowOutput.plan` and `ResumeRunOutput.plan` rename to `artifact`. The field name `plan` bakes the `planner` workflow's domain into the public schema; an external workflow producing questions / grades / refactored code patches all surface through a field literally named `plan`. Rename to a neutral name; `plan` becomes a backward-compatible alias surfaced on the wire alongside `artifact` through the 0.2.x line, with a CHANGELOG `### Deprecated` notice naming **1.0** as the removal target.

T03 is independent of T01 + T02 (the spec API). The bug fix lands in `_dispatch.py`; the rename lands in `mcp/schemas.py`. The two compose with T02's compiler (which emits `FINAL_STATE_KEY` per spec): an external spec-authored workflow with output_schema's first field named `summary` round-trips its summary through `RunWorkflowOutput.artifact` (and through `plan` for backward-compat callers).

## Deliverables

### 1. `_dispatch.py` — read `final_state_key` for artefact surfacing

Five hardcoded `final.get("plan")` call sites (lines 721, 781, 977, 1034, 1048 — verified 2026-04-26 via `grep -n 'final.get("plan")' _dispatch.py`) need to read the configured key:

**Pattern (every call site):**

```python
# Before (silently drops artefact for non-"plan" workflows):
"plan": _dump_plan(final.get("plan")),

# After (reads the configured key; in-tree planner unchanged because its FINAL_STATE_KEY = "plan"):
"plan": _dump_plan(final.get(final_state_key)),
```

The five sites are inside `_build_result_from_final` (lines 721, 781) and `_build_resume_result_from_final` (lines 977, 1034, 1048). Both functions already receive `final_state_key: str` as a parameter (the variable is in scope at every site); the fix is a literal substitution.

All five sites at lines 721, 781, 977, 1034, 1048 read state via `final.get("plan")` (verified 2026-04-26 — the sites span the `__interrupt__` pending branch, terminal-completion branch, resume-path re-gate, resume-path `gate_rejected` last-draft surface, and resume-path completed branch; none of the five are "return None" paths). The substitution applies uniformly. Separately, the existing `"plan": None` literals at lines 586, 744, 766, 793, 802, 900, 999, 1060, 1069 are error-path returns with no state read; T03 adds `"artifact": None` alongside each so artifact + plan stay in lockstep across error paths.

### 2. Rename `plan` → `artifact` in `mcp/schemas.py` with backward-compat alias

`RunWorkflowOutput.plan` → `RunWorkflowOutput.artifact`. Same for `ResumeRunOutput.plan` → `ResumeRunOutput.artifact`. The field definitions:

```python
# In RunWorkflowOutput (and same shape in ResumeRunOutput):
artifact: dict[str, Any] | None = Field(
    default=None,
    description=(
        "The workflow's terminal artefact — the value of the state field "
        "named by the workflow's FINAL_STATE_KEY (declarative spec: the "
        "first field of output_schema). For the in-tree planner this is "
        "the approved PlannerPlan; for slice_refactor it is the applied-"
        "artefact count; for an external workflow it is whatever the "
        "workflow declares. Surfaced through the deprecated `plan` field "
        "alias for backward compatibility through the 0.2.x line; removal "
        "target is 1.0."
    ),
)

# Backward-compat alias — surfaced on the wire alongside `artifact`:
plan: dict[str, Any] | None = Field(
    default=None,
    description=(
        "Deprecated alias for `artifact`. Surfaced alongside `artifact` "
        "for backward compatibility through the 0.2.x line; removal target "
        "is 1.0. Read `artifact` instead."
    ),
    deprecated=True,  # pydantic v2 deprecation marker
)
```

Both fields are populated with the same value at result-build time (see Deliverable 3). Emitting both means existing 0.2.0 callers reading `result.plan` continue to work; new callers read `result.artifact`.

### 3. `_build_result_from_final` + `_build_resume_result_from_final` — populate both `artifact` and `plan`

Wherever the result dict currently emits `"plan": <value>`, change to emit both:

```python
{
    ...,
    "artifact": _dump_plan(final.get(final_state_key)),
    "plan": _dump_plan(final.get(final_state_key)),  # deprecated alias; same value
    ...,
}
```

Error-path branches that emit `"plan": None` change to emit `"artifact": None, "plan": None` — both fields stay in lockstep across every code path.

### 4. `_dispatch._dump_plan` rename — keep or relabel?

The helper name `_dump_plan` is now misleading (it's used for any artefact, not just plans). Rename to `_dump_artifact` for consistency. Single internal helper; rename is mechanical. Update all call sites (5 in `_dispatch.py`, possibly 1-2 elsewhere — `grep -n '_dump_plan' ai_workflows/` to enumerate).

### 5. Tests — `tests/workflows/test_result_shape_correctness.py` (new)

Hermetic. Uses an in-memory stub workflow registered with `register(name, builder)` (the existing M16 surface — does not depend on T01 + T02). Builder returns a `StateGraph` with a single node that writes a deterministic artefact into a non-`plan` state key.

- `test_external_workflow_artifact_round_trips_via_artifact_field` — register a stub workflow with `FINAL_STATE_KEY = "questions"`; dispatch via `_dispatch.run_workflow`; assert `result["artifact"] == {<questions value>}`.
- `test_external_workflow_artifact_also_surfaces_via_plan_alias` — same setup; assert `result["plan"] == result["artifact"]` (alias populated).
- `test_in_tree_planner_unchanged_artifact_path` — stub a planner-shaped workflow with `FINAL_STATE_KEY = "plan"`; dispatch; assert both fields populated and equal. Ensures the in-tree `planner` workflow's existing artefact-surfacing behaviour is preserved by the bug fix (planner stays on the escape hatch per H2; this test guards against regressing its existing path).
- `test_resume_path_populates_both_fields` — stub a workflow with a `HumanGate`; pause the run; resume with approval; assert both `artifact` and `plan` are populated in the resume response.
- `test_error_path_emits_none_for_both_fields` — stub a workflow that raises mid-run; assert the errored response has `artifact: None` and `plan: None` (lockstep across error paths).

### 6. Update `mcp/schemas.py` field documentation

The `RunWorkflowOutput.artifact` field's description (Deliverable 2) explicitly names the deprecated alias. Mirror the description on `ResumeRunOutput.artifact`. Add a top-of-module comment citing M19 T03 + ADR-0008.

### 7. Smoke verification (Auditor runs)

```bash
uv run pytest tests/workflows/test_result_shape_correctness.py -v

# Existing dispatch tests stay green (the in-tree planner fix is
# behaviour-preserving; the existing tests don't explicitly assert
# the response field name, but they assert the response shape — the
# extra `artifact` field is additive).
uv run pytest tests/workflows/ tests/mcp/ -q

# MCP schema introspection — assert both fields appear on RunWorkflowOutput.
uv run python -c "
from ai_workflows.mcp.schemas import RunWorkflowOutput, ResumeRunOutput
ro_fields = set(RunWorkflowOutput.model_fields)
re_fields = set(ResumeRunOutput.model_fields)
assert 'artifact' in ro_fields and 'plan' in ro_fields, ro_fields
assert 'artifact' in re_fields and 'plan' in re_fields, re_fields
print('T03 schema smoke OK')
"
```

### 8. CHANGELOG

Under `[Unreleased]` on both branches:

```markdown
### Fixed — M19 Task 03: result-shape artefact-field bug (YYYY-MM-DD)
- `_dispatch._build_result_from_final` and `_build_resume_result_from_final` now read `final.get(FINAL_STATE_KEY)` for the response artefact field (5 call sites at lines 721, 781, 977, 1034, 1048). Previously hardcoded `final.get("plan")` silently dropped the artefact for any workflow whose `FINAL_STATE_KEY != "plan"`. CS-300's 2026-04-25 pre-flight smoke surfaced the bug; in-tree `slice_refactor` was also affected.

### Changed — M19 Task 03: RunWorkflowOutput / ResumeRunOutput field rename (YYYY-MM-DD)
- `RunWorkflowOutput.artifact` and `ResumeRunOutput.artifact` are now the canonical field names for the workflow's terminal artefact. The `plan` field is preserved as a backward-compatible alias surfaced on the wire alongside `artifact`. Existing 0.2.0 callers reading `result.plan` continue to work.

### Deprecated — M19 Task 03: RunWorkflowOutput.plan / ResumeRunOutput.plan (YYYY-MM-DD)
- The `plan` field on `RunWorkflowOutput` and `ResumeRunOutput` is deprecated in favour of `artifact`. Both fields are populated identically through the 0.2.x line. Removal target: 1.0. Read `artifact` instead.
```

## Acceptance Criteria

- [ ] **AC-1:** All five `final.get("plan")` call sites in `_dispatch.py` (lines 721, 781, 977, 1034, 1048 — re-verify line numbers at implement time as the file may shift) read `final.get(final_state_key)` instead. Error-path branches that emit `"plan": None` are unchanged in their `None` semantics; they emit `"artifact": None` alongside.
- [ ] **AC-2:** `_dispatch._dump_plan` renamed to `_dump_artifact`. All call sites updated. `grep -n '_dump_plan\b' ai_workflows/` returns no matches.
- [ ] **AC-3:** `RunWorkflowOutput.artifact` exists as a `dict[str, Any] | None` field with the description from Deliverable 2. `RunWorkflowOutput.plan` retained as a deprecated alias with `deprecated=True` marker. Same shape on `ResumeRunOutput`.
- [ ] **AC-4:** Every result-build path in `_dispatch.py` populates both `artifact` and `plan` fields with the same value (or both with `None` on error paths). Tests cover the lockstep invariant.
- [ ] **AC-5:** External workflow with `FINAL_STATE_KEY = "questions"` round-trips its `questions` value through `RunWorkflowOutput.artifact`. Test `test_external_workflow_artifact_round_trips_via_artifact_field` proves it.
- [ ] **AC-6:** Backward compat preserved — existing callers reading `result.plan` continue to work. Test `test_external_workflow_artifact_also_surfaces_via_plan_alias` proves the lockstep behavior.
- [ ] **AC-7:** Resume path populates both fields. Test `test_resume_path_populates_both_fields`.
- [ ] **AC-8:** Error path emits `None` for both fields in lockstep. Test `test_error_path_emits_none_for_both_fields`.
- [ ] **AC-9:** Existing tests stay green (`uv run pytest`). The fix is behaviour-preserving for in-tree planner (`FINAL_STATE_KEY = "plan"` resolves identically to the old hardcoded literal).
- [ ] **AC-10:** Module docstring on `_dispatch.py` (or function docstring on `_build_result_from_final`) cites M19 T03 + ADR-0008 + the original M18 T01 fold-in framing.
- [ ] **AC-11:** Smoke verification (Deliverable 7) prints `T03 schema smoke OK` and exits 0.
- [ ] **AC-12:** Layer rule preserved (`uv run lint-imports` 4 contracts kept). Schema rename is additive at the schemas layer; `_dispatch.py` changes don't introduce new imports.
- [ ] **AC-13:** Gates green on both branches. `uv run pytest`, `uv run lint-imports`, `uv run ruff check`.
- [ ] **AC-14:** CHANGELOG entries (Fixed + Changed + Deprecated) under `[Unreleased]` per Deliverable 8.

## Dependencies

- **No precondition on T01 + T02.** T03 lives in `_dispatch.py` and `mcp/schemas.py`; it can run in parallel with the spec-API work.
- **Composes with T01 + T02** — once both land, an external spec-authored workflow's terminal artefact (T01's output_schema first field, T02's synthesized `FINAL_STATE_KEY`) round-trips correctly through `RunWorkflowOutput.artifact` (T03's renamed canonical field). T04's `summarize` workflow verifies this composition end-to-end (`summarize`'s `FINAL_STATE_KEY = "summary"` round-trips through `RunWorkflowOutput.artifact` per T03's bug fix; the in-tree `planner` workflow's `FINAL_STATE_KEY = "plan"` continues to round-trip through both `artifact` and the `plan` deprecated alias).

## Out of scope (explicit)

- **No removal of the `plan` field.** Deprecation alias only; removal lands at 1.0 (separate milestone).
- **No changes to other `RunWorkflowOutput` / `ResumeRunOutput` fields.** `awaiting`, `status`, `gate_context`, `total_cost_usd`, `error`, `run_id` keep their names and semantics. ADR-0008 §Non-goals explicitly defers schema redesign beyond the `plan` rename.
- **No new MCP tools.** Existing tools (`run_workflow`, `resume_run`, `list_runs`, `cancel_run`) keep their schemas with the renamed output fields.
- **No `capture_evals` MCP exposure.** Carried forward from M19 propagation status as a parking-lot item.
- **No spec-API work.** T01 + T02 own the declarative authoring surface.
- **No docs work.** T05 + T06 + T07 own docs; T03 ships only the CHANGELOG entry.

## Carry-over from prior milestones

- **M18 Task 01 (drafted 2026-04-26, withdrawn same day, folded into M19 T03 per ADR-0008 §"Defer entirely" rejected alternative).** M18 was a 5-task milestone documenting the M16 contract + fixing this bug + renaming the field. ADR-0008 captured the decision to obsolete M18 and fold T01 into M19. The fold-in's framing: M18's bug fix + rename are real correctness items; the documentation tasks were teaching a contract M19 deprecates, so they were dropped.

## Carry-over from task analysis

- [ ] **TA-LOW-01 — Deprecation-timeline framing consistency** (severity: LOW, source: task_analysis.md round 1)
      T03's CHANGELOG `### Deprecated` entry + T05's `docs/writing-a-workflow.md` §"Running your workflow" both reference the deprecation timeline; the two phrasings ("removal target: 1.0" vs "deprecated alias preserved for backward compatibility through the 0.2.x line") are slight variants. Use one phrasing consistently.
      **Recommendation:** Use one phrasing across all M19 specs and the actual CHANGELOG entry: *"deprecated alias preserved for backward compatibility through the 0.2.x line; removal target 1.0."*
