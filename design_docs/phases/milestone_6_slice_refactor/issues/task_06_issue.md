# Task 06 — `apply` Node (Artefact Persistence) — Audit Issues

**Source task:** [../task_06_apply_node.md](../task_06_apply_node.md)
**Audited on:** 2026-04-20
**Audit scope:** Full project load — task file, milestone `README.md`, sibling task files (T01 spec + issue file for the carry-over propagation, T04 spec for aggregator contract, T05 spec for gate routing, T07 spec for the double-failure hard-stop boundary), [design_docs/architecture.md](../../../architecture.md) (§3 four-layer, §4.1 Storage, §4.3 slice_refactor DAG, §8.2 retry taxonomy), cited KDRs (KDR-001, KDR-004 N/A, KDR-006, KDR-009), [design_docs/nice_to_have.md](../../../nice_to_have.md), `pyproject.toml`, `CHANGELOG.md`, `.github/workflows/ci.yml`, every file claimed in the T06 implementation, the `tests/` tree, and the existing `SQLiteStorage.write_artifact` helper + `migrations/003_artifacts.sql` for the idempotency AC.
**Status:** ✅ PASS — all 8 ACs satisfied; T01-CARRY-DISPATCH-COMPLETE resolved (flipped DEFERRED → RESOLVED in [task_01_issue.md](task_01_issue.md)); one deliberate deviation from spec (namespaced `kind` vs `metadata: dict` signature extension) is documented under Additions-beyond-spec and is strictly less invasive than the spec's suggestion.

## Design-drift check — architecture.md + KDRs

| Check | Result |
| --- | --- |
| New dependency vs [architecture.md §6](../../../architecture.md) | ✅ None added. The `apply` node only imports `SQLiteStorage` / `StorageBackend` (already on the workflow layer's allow-list), `NonRetryable` from `primitives.retry`, and the existing `SliceResult` / `SliceAggregate` types. `pyproject.toml` unchanged. |
| New module / layer vs [architecture.md §3](../../../architecture.md) four-layer contract | ✅ Unchanged. All edits live in `workflows/` (slice_refactor, planner, _dispatch). Import-linter: 3 / 3 contracts kept. |
| LLM call added → paired with validator (KDR-004) | ✅ N/A. `apply` is not an LLM node (no `TieredNode`, no provider call). The T06 spec explicitly states "KDR-004 does not apply; not an LLM node" — audit confirms zero LLM call paths reach this node. |
| Anthropic SDK / `ANTHROPIC_API_KEY` (KDR-003) | ✅ Clean. `grep -n anthropic\|ANTHROPIC_API_KEY` on touched files returns zero hits. |
| Checkpoint / resume logic — `SqliteSaver` only (KDR-009) | ✅ Honoured. Artefact rows go to **Storage** (`artifacts` table), not to the LangGraph checkpoint. The T06 spec calls this out explicitly; implementation matches. No hand-rolled checkpoint writes added. |
| Retry logic — three-bucket taxonomy (KDR-006) via `RetryingEdge` | ✅ No retry wiring added. `_apply` raises `NonRetryable` on a missing `state["aggregate"]` (a contract violation, not a transient failure) — correct bucket per architecture.md §8.2; the run aborts rather than looping. |
| Observability — `StructuredLogger` only | ✅ No new observability surface. Storage writes are the only side effect. |
| Subprocess / filesystem write / `git apply` (milestone non-goal) | ✅ Clean. `grep -n subprocess\.\|pathlib\|open(` on `slice_refactor.py` returns zero hits. `test_apply_does_not_invoke_subprocess_or_filesystem` monkey-patches `subprocess.run` + `subprocess.Popen` to raise and asserts `_apply` still succeeds — pinned by test, not just by source inspection. |
| KDR-001 — LangGraph owns composition | ✅ `_apply` is a plain async function registered via `StateGraph.add_node`; routing to it from the gate comes from `build_slice_refactor`'s edges. No bespoke orchestration layer. |

**Drift verdict:** No violations. No nice_to_have.md items touched.

## AC grading

| AC | Status | Evidence |
| --- | --- | --- |
| 1. `apply` writes one artefact row per succeeded slice via the existing `Storage.write_artifact` (extended with `metadata: dict[str, Any]` if needed — not slice-specific) | ✅ | `test_apply_writes_one_artifact_per_succeeded_slice` seeds a 3-success aggregate and asserts 3 `artifacts` rows land, one per `SliceResult`. Deviation from spec: the Builder kept the `write_artifact(run_id, kind, payload)` signature unchanged and embedded `slice_id` into `kind` (namespaced `"slice_result:{slice_id}"`) — strictly less invasive than the spec's `metadata: dict` suggestion; same natural uniqueness property via the existing `(run_id, kind)` PK. Documented under Additions-beyond-spec and in `CHANGELOG.md`. |
| 2. Failed slices are not written to artefacts (audit trail lives in gate log) | ✅ | `test_apply_does_not_write_rows_for_failed_slices` seeds an aggregate with 2 successes + 1 failure; asserts exactly 2 rows land and no `artifacts.kind` carries the failed slice's id. |
| 3. Approve terminates run at `runs.status = "completed"`; reject terminates at `gate_rejected`; both stamp `finished_at` | ✅ | Approve path: `test_dispatch_flips_status_completed_with_finished_at_for_slice_refactor` drives the full compiled graph to `apply` → END and asserts `runs.status == "completed"` + `finished_at is not None`. Reject path: `test_dispatch_reject_path_flips_gate_rejected_with_finished_at` asserts `gate_rejected` + `finished_at`. `SQLiteStorage.update_run_status` auto-stamps `finished_at` on both terminal transitions. |
| 4. Re-invocation of `apply` on the same `run_id` does not double-write (pin the mechanism) | ✅ | Mechanism pinned: natural `(run_id, kind)` unique constraint on the existing `artifacts` PK + `ON CONFLICT(run_id, kind) DO UPDATE SET payload = excluded.payload` in `migrations/003_artifacts.sql`. `test_apply_is_idempotent_on_reinvocation` invokes `_apply` twice and asserts the row count is unchanged; `test_apply_reinvocation_with_same_payload_is_byte_identical` tightens the assertion to payload-equality. |
| 5. No subprocess, no filesystem write, no `git` invocation (per milestone non-goal) | ✅ | `test_apply_does_not_invoke_subprocess_or_filesystem` monkey-patches `subprocess.run` + `subprocess.Popen` to raise, then runs `_apply` end-to-end; `_apply` succeeds (proving it never called into those paths). Source grep confirms zero `subprocess.`, `pathlib.`, or bare `open(` in `slice_refactor.py`. |
| 6. Hermetic tests green | ✅ | Full suite: **441 passed, 2 skipped**, 0 failed (up from T05's 425). New T06 suite alone: 16 passed in 1.42s. No real API calls. |
| 7. `uv run lint-imports` 3 / 3 kept | ✅ | `primitives cannot import graph, workflows, or surfaces` KEPT. `graph cannot import workflows or surfaces` KEPT. `workflows cannot import surfaces` KEPT. 0 broken. |
| 8. `uv run ruff check` clean | ✅ | "All checks passed!" |

## Carry-over grading

| Carry-over | Status | Evidence |
| --- | --- | --- |
| T01-CARRY-DISPATCH-COMPLETE (MEDIUM, from T01 Builder-phase scope review 2026-04-20) — dispatch's completion detection hardcoded `state["plan"]`, leaving slice_refactor's approve path without a completion surface | ✅ RESOLVED | Convention landed: each workflow module publishes a `FINAL_STATE_KEY` constant (planner → `"plan"`, slice_refactor → `"applied_artifact_count"`). Dispatch's `_build_result_from_final` + `_build_resume_result_from_final` call a new `_resolve_final_state_key(module)` helper (defaults to `"plan"` for legacy modules, preserving the planner regression). Completion check uses `state.get(final_state_key) is not None` — `0` (zero-success aggregate the reviewer approved for audit trail) still satisfies the check. Test coverage: `test_final_state_key_exposed_on_both_workflow_modules`, `test_final_state_key_defaults_to_plan_for_legacy_modules`, `test_dispatch_flips_status_completed_with_finished_at_for_slice_refactor`, `test_dispatch_flips_status_completed_for_zero_artifact_count`, `test_dispatch_planner_completion_path_preserved`. Source task's issue file (T01) flipped from `DEFERRED` → `✅ RESOLVED` in both the issue log table and the Propagation status footer; task_06 spec carry-over checkbox ticked. |

## 🔴 HIGH

*(None.)*

## 🟡 MEDIUM

*(None.)*

## 🟢 LOW

*(None.)*

## Additions beyond spec — audited and justified

### ADD-01 — Namespaced `kind=f"slice_result:{slice_id}"` instead of `write_artifact(..., metadata: dict[str, Any])` signature extension

**Spec direction ([task_06_apply_node.md §Deliverables](../task_06_apply_node.md)):** "If the current helper does not accept `slice_id`, extend it with a generic `metadata: dict[str, Any]` keyword rather than a slice-specific field (applies to future workflows too)."

**What landed:** The Builder kept `SQLiteStorage.write_artifact(run_id, kind, payload)`'s signature unchanged and embedded the `slice_id` into the `kind` string as `f"slice_result:{slice_id}"`. Rationale:

1. The spec's justification for `metadata: dict` is "not a slice-specific field (applies to future workflows too)". Namespaced kinds generalise exactly the same way — future workflows can pick a different prefix (e.g. `"migration_result:<id>"`) without touching the primitive.
2. The `(run_id, kind)` primary key on `artifacts` (`migrations/003_artifacts.sql`) already gives the `(run_id, slice_id)` natural unique constraint the T06 idempotency AC asks for, plus the `ON CONFLICT(run_id, kind) DO UPDATE` clause makes re-invocation byte-identical. No schema migration; no protocol signature change on `StorageBackend`; no ripple through `MemoryStorage` or callers.
3. Strictly **less invasive** than the spec's suggestion — the Builder made the smaller of two possible changes to satisfy the AC, which is the preferred posture per CLAUDE.md "no invented scope, no drive-by refactors."

**Audit verdict:** Accepted. The deviation is documented in `CHANGELOG.md`'s T06 entry ("namespaced kind vs metadata kwarg — less invasive, same uniqueness property"), the task spec carry-over checkbox is ticked with a one-line resolution summary citing the approach, and the in-code docstrings on both `SLICE_RESULT_ARTIFACT_KIND` and `_apply` spell out why this shape was chosen. If a future workflow surfaces a genuine need for *non-identifier* metadata (e.g. a structured-object attachment that can't be encoded in a prefix string), the `metadata: dict` extension remains open to take — the Builder did not close off that door.

### ADD-02 — `FINAL_STATE_KEY` constant as the completion-detection convention (resolves T01-CARRY-DISPATCH-COMPLETE)

**Source task carry-over** ([task_01_issue.md](task_01_issue.md) / [task_06_apply_node.md §Carry-over](../task_06_apply_node.md)): two options were surfaced — (a) a sentinel-boolean `state.get(f"{workflow}_completed")`, or (b) a per-workflow `FINAL_STATE_KEY` constant dispatch reads to locate the terminal-step output.

**What landed:** Option (b). Rationale:

1. Matches the `TERMINAL_GATE_ID` convention T05 shipped to resolve T01-CARRY-DISPATCH-GATE — same symbol-shape ("workflow module publishes a module-level constant; dispatch reads it with a default-fallback helper"). Keeps the dispatch→workflow coupling discoverable and symmetric.
2. No extra state-channel writes required — `_apply`'s existing return value (`{"applied_artifact_count": <int>}`) already witnesses completion; the constant just names the key dispatch should read.
3. `is not None` check (not truthy check) preserves the 0-count edge case (reviewer approves a fully-failed aggregate for audit-trail reasons). Regression test pins this.

**Audit verdict:** Accepted. Matches the T05 pattern for structural consistency; test coverage is thorough; the `"plan"` default preserves the planner's existing behaviour without needing a planner-side edit to keep the regression green (but the Builder added the explicit `FINAL_STATE_KEY = "plan"` constant to the planner anyway, which is the right call — it makes the convention self-documenting and removes the default-branch from the hot path for the planner too).

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 441 passed, 2 skipped, 2 warnings (pre-existing yoyo DeprecationWarning). Up from 425 post-T05 → +16 tests, matches the new-suite count. |
| `uv run pytest tests/workflows/test_slice_refactor_apply.py` | ✅ 16 passed in 1.42s. |
| `uv run lint-imports` | ✅ 3 / 3 kept, 0 broken. |
| `uv run ruff check` | ✅ "All checks passed!" |
| `grep -n anthropic\|ANTHROPIC_API_KEY` on touched files | ✅ 0 hits. |
| `grep -n subprocess\.\|pathlib\|open(` on `slice_refactor.py` | ✅ 0 hits. |
| Docstring discipline (module + public symbols) | ✅ `slice_refactor.py` module docstring updated for T06 shape (lines 51–65); `_apply`, `FINAL_STATE_KEY`, `SLICE_RESULT_ARTIFACT_KIND`, `build_slice_refactor` all carry task-citing docstrings; `_dispatch._resolve_final_state_key` carries a T06-citing docstring. |
| `CHANGELOG.md` has `### Added — M6 Task 06: apply Node (Artefact Persistence) (2026-04-20)` entry under `## [Unreleased]` | ✅ Present; lists files touched, ACs satisfied, deviation (namespaced kind vs metadata kwarg), and T01-CARRY-DISPATCH-COMPLETE resolution. |
| T01-CARRY-DISPATCH-COMPLETE propagation closed | ✅ `task_01_issue.md` flipped `DEFERRED` → `✅ RESOLVED` in both the issue log table and the Propagation status footer; `task_06_apply_node.md` carry-over checkbox ticked with a one-line resolution summary. |

## Issue log — cross-task follow-up

*(None — T06 introduces no forward-deferred items.)*

## Deferred to nice_to_have

*(None.)*

## Propagation status

| Deferral | Target | Status |
| --- | --- | --- |
| T01-CARRY-DISPATCH-COMPLETE (raised 2026-04-20 in T01 Builder-phase scope review) | T06 apply node + dispatch completion detection | ✅ RESOLVED in T06 Builder; propagation closed (T01 issue file updated, T06 task spec checkbox ticked). |

**Carry-over for downstream tasks:** None introduced by T06.
