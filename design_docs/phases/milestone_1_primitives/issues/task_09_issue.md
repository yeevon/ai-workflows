# Task 09 — Cost Tracker with Budget Enforcement — Audit Issues

**Source task:** [../task_09_cost_tracker.md](../task_09_cost_tracker.md)
**Audited on:** 2026-04-19
**Audit scope:** task file + milestone README + sibling tasks (03 model factory, 07 tiers/pricing, 08 storage, 10 retry, 12 CLI), `pyproject.toml`, `CHANGELOG.md`, `.github/workflows/ci.yml`, `ai_workflows/primitives/cost.py`, `tests/primitives/test_cost.py`, every existing consumer of `CostTracker` (`model_factory.py`, `test_model_factory.py`), `pricing.yaml`, `tiers.yaml`, `design_docs/issues.md`.
**Status:** ✅ PASS (zero OPEN issues; three LOW observations propagated forward to their owning tasks)

---

## Gate summary

| Gate | Command | Result |
| --- | --- | --- |
| Tests | `uv run pytest` | ✅ 280 passed, 0 failed, 0 skipped |
| Layer contracts | `uv run lint-imports` | ✅ 2 kept, 0 broken (Contract 3 still deferred to M2 T01) |
| Lint | `uv run ruff check` | ✅ All checks passed |
| Secret scan | CI `secret-scan` grep | ✅ No `sk-ant-…` patterns in committed config |

## Acceptance criteria grade

| AC | Status | Pinning test(s) |
| --- | --- | --- |
| AC-1 `calculate_cost()` matches expected USD | ✅ | `test_calculate_cost_matches_expected_for_gemini`, `test_calculate_cost_scales_per_token`, `test_calculate_cost_includes_cache_rates`, `test_calculate_cost_zero_rates_returns_zero`, `test_calculate_cost_unknown_model_returns_zero_and_warns` |
| AC-2 local model records `$0.00` + `is_local=1` | ✅ | `test_record_local_model_sets_cost_zero_and_is_local_flag`, `test_record_local_overrides_nonzero_pricing` |
| AC-3 `run_total()` excludes `is_local=1` | ✅ | `test_run_total_excludes_is_local_rows` (mixes one priced call with ten local, asserts $0.50) |
| AC-4 `component_breakdown()` groups by component | ✅ | `test_component_breakdown_groups_per_component`, `test_component_breakdown_excludes_local` |
| AC-5 Budget cap raises `BudgetExceeded` at/before breach | ✅ | `test_budget_cap_triggers_budget_exceeded`, `test_budget_exceeded_row_is_persisted`, `test_budget_cap_not_triggered_below_cap`, `test_budget_cap_none_never_raises` |
| AC-6 `BudgetExceeded` message includes run_id, current, cap | ✅ | `test_budget_exceeded_message_contains_run_id_and_dollar_amounts`, `test_budget_exceeded_exposes_attributes` |
| AC-7 `null` budget cap logs a warning on run start | ✅ | `test_null_budget_cap_logs_warning_at_construction`, `test_explicit_cap_does_not_log_warning` |
| AC-8 Escalation calls have `is_escalation=1` | ✅ | `test_escalation_flag_persists_as_is_escalation_one` |

All eight ACs ✅. No HIGH or MEDIUM findings.

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW — propagated forward

### M1-T09-ISS-01 — Pipeline must mark run `failed` on `BudgetExceeded` (owner: M2 Task 05)

**Observation.** The task spec says "Run is marked `failed` with reason `budget_exceeded`" on breach, but `CostTracker.record()` deliberately does not touch run status — it only raises `BudgetExceeded` and lets the row persist. Marking the run failed requires the orchestration layer to wrap `record()` in a try/except and call `storage.update_run_status("failed", ...)`. M2 Task 05's existing AC-6 already covers the "preserves steps 1 and 2 as `completed`" half; the explicit "mark run failed with reason budget_exceeded" half is an implicit requirement of the same AC but deserves to be surfaced.

**Action.** In [../../milestone_2_components/task_05_pipeline.md](../../milestone_2_components/task_05_pipeline.md), extend AC-6 (or add a sibling AC) to require: on `BudgetExceeded`, the Pipeline calls `storage.update_run_status(run_id, "failed")` and logs `event="pipeline.run_failed_budget_exceeded"` before re-raising. Acceptance test: after the breach, `storage.get_run(run_id)["status"] == "failed"`.

**Severity rationale.** LOW because the primitive is complete and correct — the exception carries everything the caller needs (`run_id`, `current_cost`, `cap`). The marking-failed work belongs to the Pipeline's exception handler; marking it HIGH would push scope into M2.

**Propagation status.** Added to [../../milestone_2_components/task_05_pipeline.md](../../milestone_2_components/task_05_pipeline.md) under `## Carry-over from prior audits`.

### M1-T09-ISS-02 — `aiw inspect` surfaces cap / current / remaining (owner: M1 Task 12)

**Observation.** The task spec shows a sample `aiw inspect` output:

```
Run abc123 — jvm_modernization
Status: running
Budget: $3.47 / $5.00 (69% used)
```

This is a CLI-rendering concern, not a tracker concern. The tracker ships a `budget_cap_usd` property and `run_total()`/`component_breakdown()` helpers so Task 12 has no primitive-side work; it just needs to query the storage row and format the line.

**Action.** In [../task_12_cli_primitives.md](../task_12_cli_primitives.md), add a carry-over entry requiring `aiw inspect <run_id>` to emit a `Budget: $<current> / $<cap> (<pct>% used)` line (omit when `budget_cap_usd IS NULL` — render `Budget: $<current> (no cap)` instead). Acceptance test: `CliRunner.invoke(aiw, ["inspect", run_id])` output contains the formatted line.

**Severity rationale.** LOW — purely cosmetic / observability; not a correctness gap.

**Propagation status.** Added to [../task_12_cli_primitives.md](../task_12_cli_primitives.md) under `## Carry-over from prior audits`.

### M1-T09-ISS-03 — Workflow-YAML `max_run_cost_usd` field + null-at-load warning (owner: M3 Task 01 Workflow Loader)

**Observation.** The task spec's "Workflow YAML Integration" block describes a workflow-load-time behaviour: read `max_run_cost_usd` from `workflow.yaml` and emit a WARNING when the key is `null`. The tracker-level warning at construction (which this task ships) covers AC-7 as written ("on run start"), but the workflow-load warning is an additional safety signal the user sees **before** any LLM call fires. The loader is also where the value is parsed and passed to `CostTracker(budget_cap_usd=...)` construction.

**Action.** In [../../milestone_3_first_workflow/task_01_workflow_loader.md](../../milestone_3_first_workflow/task_01_workflow_loader.md), add a carry-over entry requiring: (a) the workflow Pydantic schema declares `max_run_cost_usd: float | None = 10.00` with the default cap from the task spec; (b) at load time, if the *explicit* YAML value is `null` (not an omission), log `event="workflow.no_budget_cap"` WARNING with the workflow's `name` before returning the parsed workflow. Acceptance test: loading a workflow with `max_run_cost_usd: null` emits one WARNING; loading a workflow that omits the field uses the default and stays silent.

**Severity rationale.** LOW — the enforcement primitive is complete; this is belt-and-suspenders signalling at the loader layer.

**Propagation status.** Added to [../../milestone_3_first_workflow/task_01_workflow_loader.md](../../milestone_3_first_workflow/task_01_workflow_loader.md) under `## Carry-over from prior audits`.

## Additions beyond spec — audited and justified

1. **`CostTracker.budget_cap_usd` read-only property.** Not requested by the spec. Rationale: Task 12 (`aiw inspect`) needs the cap to render the `$current / $cap` line; exposing it as a property keeps the private `_budget_cap_usd` attribute private. Pinned by `test_budget_cap_usd_property_roundtrips`. Low-cost addition, no hidden coupling.
2. **Structured-log warning for `cost.model_not_in_pricing`.** The spec says "log WARNING" without specifying the event name. Picking a structured name (`cost.model_not_in_pricing` with `model=<id>`) gives log processors a grep-able key. Pinned by `test_calculate_cost_unknown_model_returns_zero_and_warns`.
3. **`calculate_cost()` accepts `dict[str, ModelPricing]`, not raw `dict`.** The spec types the argument as `dict`. Tightened to `dict[str, ModelPricing]` since that is the only shape `load_pricing()` returns. Callers who want to pass a raw dict of dicts can `ModelPricing(**row)` at the boundary. No regression in the test suite.
4. **No in-tracker update to `runs.total_cost_usd`.** The spec says "update run total" but is ambiguous between (a) stamping the denormalised `runs.total_cost_usd` column and (b) re-computing the SUM aggregate. Chose (b) because `storage.update_run_status()` requires a status argument and the tracker does not own status transitions. The column stays available for the Pipeline to stamp at run terminal via `update_run_status("completed", total_cost_usd=...)`. Called out in CHANGELOG deviations.
5. **`BudgetExceeded` fires *after* the row is written.** Spec says "BEFORE returning" but does not pin the persist-vs-raise order. The audit trail is more useful when the breaching row is visible (Ops-03 `aiw cost` can show the exact LLM call that tripped the cap), so the row lands first. Pinned by `test_budget_exceeded_row_is_persisted`.
6. **Strict `>` semantics on cap check.** `new_total == cap` is permitted (spec says "exceeds", not "reaches"). Pinned by `test_budget_cap_not_triggered_below_cap`.
7. **`test_cost_tracker_structural_compat_with_model_factory`.** New regression test that pins `MagicMock(spec=CostTracker)` against the concrete class, so the Task 03 factory's existing `_null_tracker()` fixture keeps working. Belt-and-suspenders against a future refactor that might accidentally rename `record()` or remove a public method.

## Architectural review

- **Layer discipline:** `primitives/cost.py` imports only from `primitives.llm.types`, `primitives.tiers`, `primitives.storage` (TYPE_CHECKING only). No reach upward to `components` or `workflows`. `lint-imports` passes.
- **Docstring discipline:** module, class, every public function and property has a docstring. Module docstring names the task that produced it (M1 Task 09) and cross-links to tiers/storage.
- **Structured typing:** `BudgetExceeded` exposes `run_id`/`current_cost`/`cap` as instance attributes so callers can log them without parsing the message.
- **Thread/async safety:** `CostTracker` holds no mutable state other than construction-time config. Storage writes are serialised by `SQLiteStorage._write_lock`. Concurrent `record()` calls may race on the `get_total_cost` re-read (a second call could see its own row **plus** a concurrent call's row before checking the cap), but the cap enforcement is still sound — at least one call will observe the breach and raise. Not a correctness issue for MVP; relevant only when fanout is enabled (M2 C-26).
- **Test coverage:** 23 tests, every AC has ≥1 pinning test, edge cases (unknown model, cap-equals-total, task_id threading, empty run) explicitly covered. Uses real `SQLiteStorage` so the tracker→storage wiring is pinned end-to-end — no storage mocks that would hide schema drift.
- **CHANGELOG discipline:** one consolidated `### Added — M1 Task 09: …` heading with files, ACs, deviations. Follows the pattern set by Tasks 01–08.

## Issue log — tracked for cross-task follow-up

| ID | Severity | Owner | Status |
| --- | --- | --- | --- |
| M1-T09-ISS-01 | LOW | M2 Task 05 (Pipeline) | DEFERRED (propagated) |
| M1-T09-ISS-02 | LOW | M1 Task 12 (`aiw inspect`) | DEFERRED (propagated) |
| M1-T09-ISS-03 | LOW | M3 Task 01 (Workflow Loader) | DEFERRED (propagated) |

**Propagation status:**

- M1-T09-ISS-01 → [../../milestone_2_components/task_05_pipeline.md](../../milestone_2_components/task_05_pipeline.md) `## Carry-over from prior audits` ✅
- M1-T09-ISS-02 → [../task_12_cli_primitives.md](../task_12_cli_primitives.md) `## Carry-over from prior audits` ✅
- M1-T09-ISS-03 → [../../milestone_3_first_workflow/task_01_workflow_loader.md](../../milestone_3_first_workflow/task_01_workflow_loader.md) `## Carry-over from prior audits` ✅
