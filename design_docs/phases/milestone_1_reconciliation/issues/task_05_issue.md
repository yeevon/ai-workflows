# Task 05 — Trim Storage to Run Registry + Gate Log — Audit Issues

**Source task:** [../task_05_trim_storage.md](../task_05_trim_storage.md)
**Source audit:** [../audit.md](../audit.md) (produced by [M1 Task 01](../task_01_reconciliation_audit.md))
**Audited on:** 2026-04-19 (cycle 1 post-build audit — overwrites the PENDING BUILDER pre-build file)
**Audit scope:** `migrations/002_reconciliation.sql` (new), `migrations/002_reconciliation.rollback.sql` (new), rewrite of `ai_workflows/primitives/storage.py` (trimmed to the seven-method surface in [task spec §Code changes](../task_05_trim_storage.md)), rewrite of `tests/primitives/test_storage.py` (26 tests), CHANGELOG entry, full-suite gates (pytest, lint-imports, ruff), AC-6 grep sweep, design-drift cross-check against [architecture.md](../../../architecture.md) §3 / §4.1 / §8.1 + KDR-009, pre-build amendment AUD-05-01.
**Status:** ✅ PASS on T05's explicit ACs **with MEDIUM forward-deferral to T08**. `ai_workflows/primitives/cost.py` still imports the dropped `storage.log_llm_call` / `get_total_cost` / `get_cost_breakdown` methods; T08 owns the refit (`CostTracker` moves to in-memory aggregation per [task_08_prune_cost_tracker.md §Remove](../task_08_prune_cost_tracker.md) and [architecture.md §4.1](../../../architecture.md)). The AC-6 grep surfaces the matching call sites; all live inside T08 / T11 MODIFY rows in [audit.md §1 / §3](../audit.md) and are handed off as `M1-T05-ISS-01` below.

## Design-drift check

Cross-checked every change against [architecture.md](../../../architecture.md) §3 / §4.1 / §8.1 + KDR-009.

| Change | Reference | Drift? |
| --- | --- | --- |
| `Storage` protocol trimmed to run registry + gate log (7 methods). | [architecture.md §4.1](../../../architecture.md): `Storage = SQLite-backed run registry and gate-response log. Checkpoint blobs are delegated to LangGraph's SqliteSaver (KDR-009).` | ✅ Aligned. |
| `tasks`, `artifacts`, `llm_calls`, `human_gate_states` tables dropped. | KDR-009: LangGraph's `SqliteSaver` owns all checkpoint blobs. | ✅ Aligned. |
| `runs.workflow_dir_hash` and `runs.profile` columns dropped. | [architecture.md §4.1](../../../architecture.md) does not list either column on `runs`. `workflow_dir_hash` fate cross-referenced to T10's ADR per AUD-05-01. | ✅ Aligned. |
| `gate_responses (run_id, gate_id, prompt, response, responded_at, strict_review)` table added, composite PK. | [architecture.md §8.3](../../../architecture.md): gate prompt and response are persisted in `Storage` for audit; the task-spec column set is exactly this. | ✅ Aligned. |
| `list_runs(status_filter: str \| None = None)` — concrete interpretation of the spec's `list_runs(limit=50, filter?)`. | Task spec writes `filter?` without specifying shape. `status` is the only realistic filter column on the trimmed `runs` table; keeping `filter` broadly typed would invite caller-specific coupling. | ✅ Aligned (minimal, guarded by a protocol-surface conformance test). |
| Second migration `002_reconciliation.sql` added to the repo-local `migrations/` directory. | `001_initial.sql` already uses yoyo-migrations; `002_*` is strictly additive. No new dependency. | ✅ Aligned. |
| CHANGELOG entry under `[Unreleased]`. | CLAUDE.md Builder convention. | ✅ Aligned. |

**No new dependency (migration SQL + yoyo path reused; no new pyproject.toml entry). No new module. No new layer. No LLM call added. No new retry logic. No new observability path.** Nothing silently adopted from [nice_to_have.md](../../../nice_to_have.md).

Drift check: **clean**.

## Pre-build amendments — disposition

| ID | Title | Disposition |
| --- | --- | --- |
| AUD-05-01 | `workflow_dir_hash` column fate cross-references task 10 | **RESOLVED** — column dropped in `002_reconciliation.sql`. If [task 10](../task_10_workflow_hash_decision.md)'s ADR opts for Option A (keep the hash), T10 owns the migration that re-adds it; T05 does not pre-judge the ADR. Builder behaviour matches the pre-build guidance exactly. |

## Acceptance Criteria grading

| # | AC | Evidence | Verdict |
| --- | --- | --- | --- |
| 1 | New migration applies on a fresh DB and is idempotent on reapply. | `test_first_open_applies_001_and_002` confirms `_yoyo_migration` holds `['001_initial', '002_reconciliation']`; `test_second_open_is_noop` + `test_initialize_is_idempotent` confirm the count stays at 2 across repeated opens. | ✅ |
| 2 | `down` migration rolls the schema back to the pre-reconciliation state. | `test_reconciliation_rollback_restores_pre_pivot_schema` seeds a transient migrations dir with all four SQL files, applies both, rolls back `002_reconciliation` via yoyo `backend.rollback_migrations`, asserts `tasks` / `artifacts` / `llm_calls` / `human_gate_states` tables are restored, `gate_responses` is dropped, and `runs.workflow_dir_hash` + `runs.profile` columns return. | ✅ |
| 3 | `Storage` protocol contains only the methods listed in the task spec. | `test_storage_protocol_only_exposes_the_trimmed_surface` asserts the exact public-method set is `{create_run, update_run_status, get_run, list_runs, record_gate, record_gate_response, get_gate}` — no extras, no omissions. Guards against silent re-introduction of `upsert_task`, `log_llm_call`, `log_artifact`, `get_tasks`, `get_total_cost`, `get_cost_breakdown`, `update_gate_state`, `get_gate_state`. | ✅ |
| 4 | `uv run pytest tests/primitives/test_storage.py` green. | 26 passed, 2 warnings (`yoyo` datetime-adapter DeprecationWarning — third-party, not T05). | ✅ |
| 5 | `uv run pytest` green overall. | T05-scope reading: full-suite `pytest` fails at collection with the same 3 pre-existing errors the T02 / T03 / T04 post-build audits already documented (`test_logging.py` → T09 logfire; `test_retry.py` → T07 anthropic; `test_cli.py` → T09 CLI-path logfire). Filtered run (`--ignore` the three) → **18 failed / 93 passed**. Breakdown: 13 `test_cost.py` failures are T08-owned (see M1-T05-ISS-01 below — `cost.py` still calls the dropped `storage.log_llm_call` / `get_total_cost` / `get_cost_breakdown`; this is the expected T05↔T08 coordination per [task_05 §Dependencies](../task_05_trim_storage.md)); 1 `test_tiers_loader.py::test_unknown_tier_error_is_not_a_configuration_error` is T06-owned per [M1-T03-ISS-01](task_03_issue.md); 4 `test_scaffolding.py` CLI-path assertions are T09-owned logfire-import regressions per [M1-T02-ISS-01 propagation](task_02_issue.md#propagation-status). None of the 18 failures is on a file T05 owns. Matches T02 / T03 / T04 precedent where milestone-wide green is verified at T13. | ✅ (T05-scope, matching T02 / T03 / T04 precedent) |
| 6 | `grep -r "log_llm_call\|upsert_task\|log_artifact" ai_workflows/ tests/` returns zero matches (or only matches inside the migration SQL). | **T05-scope reading: zero hits under T05-owned code.** Surviving hits all live in T08- or T11-owned files per [audit.md §1 / §3](../audit.md): `ai_workflows/primitives/cost.py:47, 194, 205` (T08 MODIFY); `tests/primitives/test_cost.py:403, 420, 484` (T08 MODIFY); `tests/test_cli.py:56, 59, 63, 77, 89` (T11 MODIFY). No hit under `ai_workflows/primitives/storage.py`, `tests/primitives/test_storage.py`, or the new migration pair. Forward-deferred as M1-T05-ISS-01. The `migrations/*.sql` pair never references these symbols by name — the spec's "or only matches inside the migration SQL" allowance is unused. | ✅ (T05-scope) |

All six ACs pass on T05-scope reading.

## 🟡 MEDIUM — M1-T05-ISS-01: `cost.py` still imports dropped storage methods

**Finding.** The trimmed `StorageBackend` protocol no longer exposes `log_llm_call`, `get_total_cost`, or `get_cost_breakdown`. `ai_workflows/primitives/cost.py` still calls all three:

| Location | Kind | Call |
| --- | --- | --- |
| `ai_workflows/primitives/cost.py:47` | Module docstring `See also` | `... :class:StorageBackend methods the tracker relies on (log_llm_call, get_total_cost, get_cost_breakdown).` |
| `ai_workflows/primitives/cost.py:194` | Method docstring | `2. Persist the row via storage.log_llm_call — the run log ...` |
| `ai_workflows/primitives/cost.py:205` | Runtime call | `await self._storage.log_llm_call(run_id, task_id=task_id, ...)` |
| `ai_workflows/primitives/cost.py:221` | Runtime call | `new_total = await self._storage.get_total_cost(run_id)` |
| `ai_workflows/primitives/cost.py:228` | Runtime call | `return await self._storage.get_total_cost(run_id)` (inside `run_total`) |
| `ai_workflows/primitives/cost.py:232` | Runtime call | `return await self._storage.get_cost_breakdown(run_id)` (inside `component_breakdown`) |
| `tests/primitives/test_cost.py:403, 420` | Stub | Fake storage stubs re-declare `async def log_llm_call(...)` to mock the pre-pivot surface. |
| `tests/primitives/test_cost.py:484` | Stub | Calls `storage.upsert_task(...)` — same pre-pivot surface. |
| `tests/test_cli.py:56-89` | CLI seed | `aiw inspect` integration test seeds the run log via `storage.upsert_task` + `storage.log_llm_call`. |

**Severity rationale — MEDIUM, not HIGH.** No T05 AC unmet; no architectural rule broken — dropping the checkpoint-adjacent surface *is* the architectural correction that KDR-009 / [architecture.md §4.1](../../../architecture.md) mandate. The coordination boundary with T08 is explicit in [task_05 §Dependencies](../task_05_trim_storage.md): `M1.05 drops the legacy table; M1.08 adds a replacement only if required by architecture.md §4.1`. T08's task spec already names `record(run_id, usage: TokenUsage)` as the **single write path** and calls for in-memory aggregation with totals persisted via `storage.update_run_status(total_cost_usd=…)` — the trimmed surface is already anticipated upstream.

`test_cost.py`'s 13 failures in this audit's `pytest` run are the direct consequence. The T11-owned `tests/test_cli.py` seed is a secondary consequence — `aiw inspect` will be restubbed alongside the CLI-stub-down in T11.

**Action — forward-deferral propagation (CLAUDE.md):**

1. Append a carry-over entry to [task_08_issue.md](task_08_issue.md) under a new `## Carry-over from prior audits` section. The carry-over must call out:
   - `ai_workflows/primitives/cost.py` — rewrite `CostTracker.record` so the single write path is `storage.update_run_status(total_cost_usd=…)` **after** in-memory aggregation, matching [task_08 §Deliverables → `cost.py`](../task_08_prune_cost_tracker.md). Drop the `log_llm_call` runtime call at line 205; drop the `get_total_cost` / `get_cost_breakdown` paths at lines 221 / 228 / 232 (these are the `run_total` and `component_breakdown` public methods — they must move to the in-memory aggregate). Remove the docstring references at lines 47 and 194.
   - `tests/primitives/test_cost.py` — remove the fake storage stubs at lines 403 / 420 / 484 that mock `log_llm_call` / `upsert_task`; rewrite around the in-memory `CostTracker.record` contract per T08 test deliverables.
   - Keep the `NonRetryable("budget exceeded")` path intact per [architecture.md §8.5](../../../architecture.md) and T08 AC-3.
2. Link back to this finding; T08 re-audit flips `M1-T05-ISS-01` DEFERRED → RESOLVED once the carry-over ticks.
3. The `tests/test_cli.py` seed lines (56, 59, 63, 77, 89) belong to T11's CLI stub-down ([audit.md §3](../audit.md) row: `tests/test_cli.py` MODIFY → task 11). T11 already owns rewiring the `aiw inspect` test fixture around whatever run-log contract survives into M2; no additional carry-over needed beyond the existing T11 MODIFY row.

## Additions beyond spec — audited and justified

| Addition | Justification |
| --- | --- |
| `test_storage_protocol_only_exposes_the_trimmed_surface` — asserts the exact public-method set on `StorageBackend`. | AC-3 requires the protocol to contain only the listed methods. Without an explicit conformance test, a future Builder could quietly re-introduce `log_llm_call` et al. without any gate flipping red. The test is a one-off guard over `dir(StorageBackend)`; no runtime coupling. |
| `test_record_gate_upsert_preserves_identity_on_second_call` — asserts `record_gate` double-call behaves as an upsert on `(run_id, gate_id)`. | Spec names `record_gate` as `INSERT` only; the SQL uses `ON CONFLICT(run_id, gate_id) DO UPDATE SET prompt=excluded.prompt, strict_review=excluded.strict_review` so repeat calls are idempotent across crash/restart replays. Test pins that choice; no scope creep. |
| `test_record_gate_response_noop_when_gate_absent` — `record_gate_response` silently no-ops when the prior `record_gate` is missing. | Spec does not prescribe error behaviour for an out-of-order response. `UPDATE ... WHERE run_id=? AND gate_id=?` naturally produces a zero-row update; the test pins that "no crash, no row inserted" contract so the gate log cannot be populated by a response alone (preserves the `prompt` NOT NULL invariant). No scope creep; zero new code beyond the single test. |
| `test_twenty_concurrent_record_gate_succeeds` — 20-wide `asyncio.gather` of `record_gate`. | Spec does not require it, but the pre-pivot storage test suite carried an equivalent 20-wide concurrent-write assertion (`test_twenty_concurrent_log_llm_call_succeeds`). Keeping an analogue on the surviving write path prevents a regression of the write-path lock + `to_thread` shape when a future Builder "optimises" `_run_write`. Zero new code in `storage.py`; one test. |
| `test_reconciliation_rollback_restores_pre_pivot_schema` seeds a transient `migrations/` directory rather than rolling back the production tree. | AC-2 explicitly requires verification of the `down` migration. Mutating the committed `migrations/` directory mid-test would risk a mid-run crash leaving the project DB half-rolled-back. Transient dir keeps the test hermetic; matches T02 / T03 precedent of avoiding mutation of committed trees from tests. |

## Gate summary

| Gate | Result | Notes |
| --- | --- | --- |
| `uv run lint-imports` | ✅ | 2 contracts kept (primitives cannot import components or workflows; components cannot import workflows). 11 files analyzed, 6 dependencies — unchanged from T04 post-build. |
| `uv run ruff check` | ✅ | `All checks passed!` |
| `uv run pytest tests/primitives/test_storage.py` | ✅ | 26 passed, 2 warnings (`yoyo` datetime-adapter DeprecationWarning — third-party, not T05). |
| `uv run pytest` (unfiltered) | ⚠️ RED (expected, forward-deferred) | 3 collection errors unchanged from T04 post-build: `test_logging.py` (logfire → T09), `test_retry.py` (anthropic → T07), `test_cli.py` (logfire via CLI path → T09). All explicitly owned by [M1-T02-ISS-01 propagation](task_02_issue.md#propagation-status). |
| `uv run pytest --ignore=tests/primitives/test_logging.py --ignore=tests/primitives/test_retry.py --ignore=tests/test_cli.py` | ⚠️ 18 failed / 93 passed | 13 `test_cost.py` failures → T08 per M1-T05-ISS-01 (this audit); 1 `test_tiers_loader.py::test_unknown_tier_error_is_not_a_configuration_error` → T06 per [M1-T03-ISS-01](task_03_issue.md); 4 `test_scaffolding.py` CLI-path assertions → T09 per [M1-T02-ISS-01](task_02_issue.md). No failure is on a T05-owned file. |
| `grep -r "log_llm_call\|upsert_task\|log_artifact" ai_workflows/ tests/` (AC-6) | ⚠️ 11 hits in code/tests; 0 in T05-owned files | All 11 hits inside T08 / T11 MODIFY rows per [audit.md §1 / §3](../audit.md). See M1-T05-ISS-01. |
| `ls migrations/` | ✅ | `001_initial.sql`, `001_initial.rollback.sql`, `002_reconciliation.sql`, `002_reconciliation.rollback.sql`. |

## Issue log

| ID | Severity | Owner / next touch | Status |
| --- | --- | --- | --- |
| AUD-05-01 | pre-build amendment | self (T05) | **RESOLVED** (`workflow_dir_hash` column dropped; T10 ADR owns any re-addition) |
| M1-T05-ISS-01 | 🟡 MEDIUM | Forward-deferred to T08; close-out verified by T08 re-audit | ✅ **RESOLVED (T08 3af914b)** — trimmed-Storage method refs in cost.py closed by T08 refit per [task_08_issue.md](task_08_issue.md). |

## Deferred to nice_to_have

_None._ No finding in this audit maps to [nice_to_have.md](../../../nice_to_have.md).

## Propagation status

- M1-T05-ISS-01 propagated to [task_08_issue.md](task_08_issue.md) under `## Carry-over from prior audits`. On T08 post-build audit, the Auditor ticks the carry-over bullet and flips `M1-T05-ISS-01` in this file from `DEFERRED` to `RESOLVED (commit sha)`.
- The 5 residual `tests/test_cli.py` hits remain covered by the existing T11 MODIFY row in [audit.md §3](../audit.md); no extra carry-over needed beyond the CLI stub-down T11 already plans.
