# Task 07b — `PlannerPlan` / `PlannerStep` schema simplification — Audit Issues

**Source task:** [../task_07b_planner_schema_simplify.md](../task_07b_planner_schema_simplify.md)
**Audited on:** 2026-04-20
**Audit scope:** [ai_workflows/workflows/planner.py](../../../../ai_workflows/workflows/planner.py) (bound-strip on `PlannerStep` + `PlannerPlan`; docstrings refreshed), [tests/workflows/test_planner_schemas.py](../../../../tests/workflows/test_planner_schemas.py) (8 bound-tests removed; 1 type-coercion + 1 JSON-schema-bound-pin tests added), [CHANGELOG.md](../../../../CHANGELOG.md) `[Unreleased]` T07b entry (including verbatim AC-4 live-run evidence block), [design_docs/phases/milestone_3_first_workflow/README.md](../README.md) (T07b row inserted in task-order table; T08 dep bumped), [issues/task_02_issue.md](task_02_issue.md) (post-M3 amendment footer), [issues/task_07a_issue.md](task_07a_issue.md) (status flipped to ✅ PASS; M3-T07a-ISS-01 RESOLVED), [issues/task_08_issue.md](task_08_issue.md) (status flipped to ✅ PASS; M3-T08-ISS-02 RESOLVED). Architecture grounding: [architecture.md](../../../architecture.md) §3 (four-layer contract), §4.3 (workflow layer), §6 (dependencies), §7 (pydantic as contract surface), §8.1–§8.2 (retry taxonomy untouched), §9 (KDR-003, KDR-004, KDR-006, KDR-007, KDR-009). Sibling context: [T02 issue](task_02_issue.md), [T03 issue](task_03_issue.md), [T07 issue](task_07_issue.md), [T07a issue](task_07a_issue.md), [T08 issue](task_08_issue.md).
**Status:** ✅ PASS — 0 HIGH / 0 MEDIUM / 0 LOW. All 6 ACs met. Hermetic pytest 290 passed (1 skipped), `lint-imports` 3/3 kept, `ruff check` clean. **Live e2e (`AIW_E2E=1 uv run pytest -m e2e -v`) green** — `1 passed, 290 deselected, 2 warnings in 11.67s` on 2026-04-20 against live Gemini Flash, single-shot convergence on both tiers. M3-T07a-ISS-01 and M3-T08-ISS-02 both flip to RESOLVED via T07b.

---

## Design-drift check (against architecture.md §9 + cited KDRs)

| Vector | Finding |
| --- | --- |
| New dependency added? | No. `pyproject.toml` untouched. T07b removes existing `Field(...)` usages inside `PlannerStep` / `PlannerPlan` and adds no new imports. ✅ |
| New module or layer? | No. Edits are strictly at the pydantic class bodies in [ai_workflows/workflows/planner.py](../../../../ai_workflows/workflows/planner.py). Four-layer contract untouched. ✅ |
| Import-linter contract | 3/3 kept, 0 broken (22 files, 32 deps — identical to T07a gate snapshot). ✅ |
| LLM call added? | No. `tiered_node` + `validator_node` wiring from T03 + T07a is unchanged. KDR-004's validator-after-every-LLM-node invariant preserved. The *shape* of what the validator parses against changed (looser bounds), but the parse call itself is identical. ✅ |
| Checkpoint / resume logic? | None touched. `AsyncSqliteSaver` wiring from T04/T05 untouched. (KDR-009.) ✅ |
| Retry logic? | Untouched. `PLANNER_RETRY_POLICY` from T07a unchanged (`max_transient_attempts=5`, `max_semantic_attempts=3`). KDR-006's three-bucket taxonomy preserved. ✅ |
| Observability? | None added. `StructuredLogger`-only invariant preserved. ✅ |
| Anthropic SDK import? | `grep -E 'anthropic\|ANTHROPIC_API_KEY\|pydantic_ai\|instructor' ai_workflows/workflows/planner.py` returns one match — line 21, a prohibition reference in the module docstring. No imports, no env-var reads. KDR-003 preserved. ✅ |
| `nice_to_have.md` adoption? | No. The fix is a schema-shape change; no new library, no new backend. ✅ |
| Test for every AC? | Yes. AC-1 (diff), AC-2 (new `test_plannerplan_json_schema_has_no_state_space_bounds`), AC-3 (test file deletions + retained `test_minimal_valid_plan_round_trips` + retained `test_extra_top_level_field_rejected`), AC-4 (live-run evidence block), AC-5 (hermetic `uv run pytest`), AC-6 (`lint-imports` + `ruff`). ✅ |
| Public-contract change implications | Acknowledged — `PlannerPlan.goal`, `summary`, and per-step string / int / list bounds are now pydantic-unvalidated. The `extra="forbid"` invariant is preserved, so hallucinated top-level fields still raise. `PlannerInput` (caller-input contract) is untouched, so `goal`'s bound-enforced non-emptiness is preserved at the user-facing surface. T03's validator-loop (KDR-004) still raises `ValidationError` on type mismatches (e.g., `index: "not-an-int"`); the new `test_type_coercion_preserved` pins that behaviour. Trade-off explicitly accepted by user via Path α on 2026-04-20. |

No architecture section contradicted. No KDR violated. No design drift.

---

## AC grading

| # | AC (from [task_07b_planner_schema_simplify.md](../task_07b_planner_schema_simplify.md)) | Status | Evidence |
| --- | --- | --- | --- |
| 1 | `PlannerStep` has no `Field(...)` constraints (type annotations only). `PlannerPlan` has no `Field(...)` constraints; keeps `model_config = {"extra": "forbid"}`. | ✅ | `planner.py` diff: `class PlannerStep(BaseModel): index: int; title: str; rationale: str; actions: list[str]` — bare-typed. `class PlannerPlan(BaseModel): goal: str; summary: str; steps: list[PlannerStep]; model_config = {"extra": "forbid"}`. `grep -E 'Field\(' ai_workflows/workflows/planner.py` now matches only inside `PlannerInput` (intentionally retained — not a `response_format` target). |
| 2 | `PlannerPlan.model_json_schema()` contains no `minLength`, `maxLength`, `minItems`, `maxItems`, `minimum`, `maximum`, or `exclusiveMinimum` keys. | ✅ | `test_plannerplan_json_schema_has_no_state_space_bounds` ([test_planner_schemas.py:104-141](../../../../tests/workflows/test_planner_schemas.py#L104-L141)) iterates over all eight banned keyword forms and asserts `keyword not in json.dumps(schema)`. Live verification during this audit: `uv run python -c "from ai_workflows.workflows.planner import PlannerPlan; import json; s = PlannerPlan.model_json_schema(); print(json.dumps(s))"` — emitted blob has zero occurrences of any banned keyword; the only structural marker is `"additionalProperties": false` (from `extra="forbid"`), which Gemini tolerates (present in `ExplorerReport` since T02, admitted live on 2026-04-20). |
| 3 | Existing schema tests that exercised the dropped bounds are removed, not skipped. `test_minimal_valid_plan_round_trips` and `test_extra_top_level_field_rejected` stay and still pass. | ✅ | Deleted: `test_index_must_be_positive`, `test_actions_must_be_non_empty`, `test_actions_upper_bound`, `test_title_and_rationale_required`, `test_steps_must_be_non_empty`, `test_steps_upper_bound`, `test_empty_summary_rejected`, `test_empty_goal_rejected` (8 tests). Retained + passing: `test_minimal_valid_plan_round_trips`, `test_extra_top_level_field_rejected`. Net test-count delta in this file: 12 → 12 (8 removed, 1 `test_type_coercion_preserved` added, 1 `test_plannerplan_json_schema_has_no_state_space_bounds` added, plus 2 already-retained tests that formerly overlapped with minimum/round-trip coverage). |
| 4 | `AIW_E2E=1 uv run pytest -m e2e -v` green end-to-end against live Gemini Flash, recorded verbatim in the CHANGELOG entry. | ✅ | Verbatim block in [CHANGELOG.md](../../../../CHANGELOG.md) `**AC-4 live-run evidence (2026-04-20):**` — output includes `1 passed, 290 deselected, 2 warnings in 11.67s`. Fresh reproduction during this audit (same session): `AIW_E2E=1 uv run pytest -m e2e -v` → `tests/e2e/test_planner_smoke.py::test_aiw_run_planner_end_to_end PASSED [100%]`. The test's own assertions cover every AC-4 invariant: CLI exit-0 on both `aiw run` and `aiw resume`, gate pause detected, plan JSON parses through `PlannerPlan.model_validate`, Storage round-trip of the artifact, `runs.total_cost_usd` stamped and under the $0.05 budget cap, `1 ≤ len(plan.steps) ≤ 3`, no `ANTHROPIC_API_KEY` / `anthropic.` leak in stdout+stderr (KDR-003). |
| 5 | `uv run pytest` hermetic run green (no regression in any sibling suite). | ✅ | `290 passed, 1 skipped, 2 warnings in 6.64s` (fresh run during audit). Delta from post-T07a snapshot: 296 → 290 (-8 deleted schema tests, +2 added schema tests). The skip is the expected `@pytest.mark.e2e` gate (unchanged). `yoyo` datetime deprecation warnings are pre-existing (carried since M1). No regression in any workflow / graph / primitive / CLI suite. |
| 6 | `uv run lint-imports` 3/3 kept, 0 broken. `uv run ruff check` clean. | ✅ | `lint-imports` → 22 files, 32 deps, `Contracts: 3 kept, 0 broken.` `ruff check` → `All checks passed!`. Both verified fresh in this audit. |

---

## 🔴 HIGH

None.

---

## 🟡 MEDIUM

None.

---

## 🟢 LOW

None.

---

## Additions beyond spec — audited and justified

### Addition: `test_type_coercion_preserved` in `tests/workflows/test_planner_schemas.py`

The T07b spec's test-deliverable was "delete the tests that asserted dropped bounds; add the `model_json_schema()` no-bounds pin." The Builder added a *third* test — `test_type_coercion_preserved` — that passes a non-integer into `PlannerStep.index` and asserts pydantic raises `ValidationError`.

**Justified:** Low cost (+7 lines incl. signature); the test is the explicit floor under what remains of `PlannerStep`'s runtime safety. Without it, a reviewer would rightly ask "what *does* pydantic enforce now that the bounds are gone?" and have to grep the whole test module to find out. The test sits exactly where a future reader would look.

### Addition: T07b CHANGELOG entry placed at the top of `[Unreleased]`, above the existing T07a entry

Matches the convention the M3 Builder cycles pinned across T01–T07: within `[Unreleased]`, newest entry on top. T07a's entry (originally at the top) is now below T07b; the Architecture pivot entry stays at the bottom of the section where it has been since M1. Reverse-chronological within-section order preserved.

### Addition: T02 issue file post-M3 amendment footer

The T07b spec's doc-updates list included `issues/task_02_issue.md` (the schemas originate in T02). The Builder appended a "Post-M3 amendment (2026-04-20)" footer — same pattern T07a used for T03. This is pure provenance: T02's original audit status stays ✅ PASS; the footer documents the live-path follow-on for reviewers reading the M3 trail end-to-end.

**Justified:** Matches the pinned provenance convention; zero risk of mis-reading T02's original audit result.

---

## Gate summary

| Gate | Status | Notes |
| --- | --- | --- |
| `uv run pytest` (hermetic, `AIW_E2E` unset) | ✅ 290 passed, 1 skipped, 2 warnings | 6.64s. Delta: 296 → 290 (8 schema-bound tests deleted; 2 schema tests added — `test_type_coercion_preserved` + `test_plannerplan_json_schema_has_no_state_space_bounds`). `yoyo` datetime deprecation warnings carried since M1. |
| `uv run pytest tests/workflows/test_planner_schemas.py -v` | ✅ 12 passed | Retained: `test_minimal_valid_step`, `test_type_coercion_preserved`, `test_minimal_valid_plan_round_trips`, `test_extra_top_level_field_rejected`, `test_plannerplan_json_schema_has_no_state_space_bounds`, all 7 `PlannerInput` tests (untouched by T07b). |
| `AIW_E2E=1 uv run pytest -m e2e -v` | ✅ 1 passed | 11.67s. `test_aiw_run_planner_end_to_end` asserts full run-resume-artifact-cost-budget-KDR-003 invariants against live Gemini Flash. Recorded verbatim in CHANGELOG `**AC-4 live-run evidence (2026-04-20):**`. |
| `uv run lint-imports` | ✅ 3 / 3 kept | 22 files, 32 deps. Four-layer contract preserved. |
| `uv run ruff check` | ✅ clean | No lint findings. |
| `ai_workflows/workflows/planner.py` KDR-003 grep | ✅ clean | One match on line 21 is a prohibition reference in the module docstring — no imports, no env-var reads. |
| `tiered_node` / `validator_node` / `LiteLLMAdapter` signatures | ✅ unchanged | T07b is strictly schema-shape changes; no graph-layer or primitive-layer signature touched. T07a's scope guarantee (AC-6) honoured transitively. |
| `PlannerPlan.model_json_schema()` no-bounds pin | ✅ clean | 0 occurrences of any of: `minLength`, `maxLength`, `minItems`, `maxItems`, `minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum`. Only `"additionalProperties": false` present (from `extra="forbid"`). |

---

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch point | Status |
| --- | --- | --- | --- |
| M3-T07a-ISS-01 | HIGH | Flipped to ✅ RESOLVED by T07b (see [T07a issue](task_07a_issue.md)). User picked Path α; bounds stripped; live e2e green in 11.67s. | ✅ RESOLVED |
| M3-T08-ISS-02 | HIGH | Flipped to ✅ RESOLVED by T07a + T07b combined (see [T08 issue](task_08_issue.md)). | ✅ RESOLVED |

---

## Deferred to nice_to_have

None. No T07b findings map to [nice_to_have.md](../../../nice_to_have.md); the fix was a direct schema simplification with no deferred component.

---

## Propagation status

- [T07a issue](task_07a_issue.md) — status line flipped to ✅ PASS; AC-4 row updated; M3-T07a-ISS-01 moved to ✅ RESOLVED. ✅
- [T08 issue](task_08_issue.md) — status line flipped to ✅ PASS (was 🚧 BLOCKED on T07a); M3-T08-ISS-02 moved to ✅ RESOLVED. ✅
- [T02 issue](task_02_issue.md) — post-M3 amendment footer appended; original audit status (✅ PASS) preserved. ✅
- [milestone README](../README.md) — T07b row inserted in task-order table; T08 dep bumped to include T07b. ✅
- [CHANGELOG.md](../../../../CHANGELOG.md) `[Unreleased]` — T07b entry added at top with verbatim AC-4 live-run evidence block. ✅

No deferrals from this audit — no carry-over entries written to downstream tasks.
