# Task 08 — Storage Layer — Audit Issues

**Source task:** [../task_08_storage.md](../task_08_storage.md)
**Audited on:** 2026-04-19
**Audit scope:** full Task 08 surface —
[migrations/001_initial.sql](../../../../migrations/001_initial.sql),
[migrations/001_initial.rollback.sql](../../../../migrations/001_initial.rollback.sql),
[ai_workflows/primitives/storage.py](../../../../ai_workflows/primitives/storage.py),
[tests/primitives/test_storage.py](../../../../tests/primitives/test_storage.py),
[CHANGELOG.md](../../../../CHANGELOG.md) (M1 Task 08 entry),
the milestone [README.md](../README.md), sibling task files
(07 / 09 / 10 / 11 / 12) for interface-drift,
[design_docs/issues.md](../../../issues.md) (CRIT-02, CRIT-10, P-26 … P-31,
W-03), [pyproject.toml](../../../../pyproject.toml) (yoyo-migrations
declared), [.github/workflows/ci.yml](../../../../.github/workflows/ci.yml)
(secret-scan still green), and the existing
[test_scaffolding.py](../../../../tests/test_scaffolding.py) AC that
`migrations/001_initial.sql` exists on disk. All three gates ran
locally; yoyo's SQL-migration format was confirmed against the yoyo
source (`.venv/.../yoyo/migrations.py:190-192`) — rollback statements
live in a sibling `*.rollback.sql` file, not an inline separator.

**Status:** ✅ PASS — every acceptance criterion is satisfied with
dedicated tests, three gates are green (257 passed, 2 contracts kept,
ruff clean, secret-scan clean). No OPEN issues. Four deviations from the
task spec are called out and justified below; none reduces the
behavioural contract. One LOW-severity observation about yoyo's
filename-based deduplication is logged for future developers who may
have run the Task 01 scaffolding DB — it is not a live bug.

---

## 🔴 HIGH

_None._

## 🟡 MEDIUM

_None._

## 🟢 LOW

### M1-T08-ISS-01 — yoyo dedup is filename-keyed, not content-keyed ✅ CLOSED (observation)

yoyo-migrations 9.x deduplicates applied migrations by filename ID (the
`migration_id` column of `_yoyo_migration`), not by content hash.
Replacing the content of `001_initial.sql` — which Task 08 does, per the
Task 01 CHANGELOG explicit plan ("Task 08 will drop or replace it as
part of the first real schema migration") — will NOT re-apply on any DB
that was previously opened with the Task 01 bootstrap stub. Such a DB
would be left with the old `schema_bootstrap` table and none of the
Task 08 tables.

**Impact:** zero in practice — no DB has been deployed anywhere, and
the only environments that could hit this are developer laptops that
ran the Task 01 scaffolding before Task 08 landed. The audit confirmed
by directly testing yoyo's behaviour (`to_apply` returned 0 after a
content change with the same filename).

**Action / Recommendation:** none required. Documented here for
future Task 08 developers. Mitigation if ever needed: delete
`~/.ai-workflows/runs.db` (the only DB location in scope for M1) and
reopen. The full schema will then apply cleanly.

**Owner:** closed / no follow-up. Re-open only if a deployment surface
materialises before M1 Task 12.

---

## Additions beyond spec — audited and justified

| Addition | Justification |
| --- | --- |
| `SQLiteStorage.open()` classmethod async factory | The spec's `def __init__(self, db_path: str)` is sync while `_apply_migrations()` is `async`. `open()` builds, migrates, and flips WAL in a single awaitable — the intended entry point. The sync `__init__` is retained for protocol-conformance checks that don't need the DB; `initialize()` is exposed directly for callers that want to own the await hop. Pinned by `test_sqlite_storage_pre_open_still_satisfies_protocol` (sync path) + `test_initialize_is_idempotent` (callers that construct then init separately). |
| `migrations_dir` keyword-only argument on `__init__` / `open` | The spec hardcodes `"migrations/"` — the rollback AC requires a way to point the loader at a synthetic `tmp_path/migrations` tree without mutating the production tree. Production callers leave it unset; the default resolves to `Path(__file__).parent.parent.parent / "migrations"`. Pinned by `test_migration_rollback_reverts_schema`. |
| `migrations/001_initial.rollback.sql` companion file | yoyo-migrations 9.x parses rollback statements from a sibling `*.rollback.sql` file (`yoyo/migrations.py:190-192`). The inline `-- rollback:` separator is not recognised. This file is required for the rollback AC to be testable. |
| `upsert_task` / `log_llm_call` raise `TypeError` on unknown kwargs | Spec's `**kwargs` suggests passthrough. Silent drop would mask a caller typo forever (e.g. `started_att=` instead of `started_at=`). Failing loudly is the conservative default. Pinned by `test_upsert_task_rejects_unknown_kwargs` + `test_log_llm_call_rejects_unknown_kwargs`. |
| `create_run` Python-level validation of `workflow_dir_hash` | Schema already enforces `NOT NULL`, which rejects `None` via `IntegrityError`. The Python-level `ValueError` surfaces a clearer error message (names the field; also rejects the empty string, which SQLite's `NOT NULL` does not). Pinned by two rejection tests plus the happy-path persistence test. |
| `PRAGMA foreign_keys = ON` per connection | Spec declares `tasks.run_id REFERENCES runs(run_id)` but SQLite needs this pragma to enforce it. Enabling it is the conservative default; no test relies on enforcement yet, but Task 09's cost tracker or Task 12's inspect CLI may. |
| `asyncio.Lock` on the write path + `asyncio.to_thread` for blocking `sqlite3` | Required for AC-7 correctness (20 concurrent writes). Not called out in the spec but implied by the "concurrent writes succeed" AC — without serialisation, WAL-mode writes from multiple threads would race on the writer lock and surface as `SQLITE_BUSY`. |
| `get_cost_breakdown` also filters `is_local = 0` | Spec only calls out `get_total_cost()` for the `is_local` filter. Extending it to `get_cost_breakdown` matches the semantic: Ollama calls should not appear in per-component USD totals either. Pinned by `test_get_cost_breakdown_groups_by_component_excluding_local` (asserts a 99.0-dollar local row is excluded). |
| `update_gate_state` preserves `rendered_at` on second write | Not called out in the spec, but resumes need to know when the gate was first rendered to the user — not the last mutation. Implemented via `COALESCE(human_gate_states.rendered_at, excluded.rendered_at)`; pinned by `test_update_gate_state_upsert_preserves_rendered_at`. |
| `list_runs()` orders newest-first by `started_at DESC` | Spec says "most recent runs" without specifying ordering. `aiw list-runs` (Task 12) expects newest-first to mirror `docker ps` / `git log`. Pinned by `test_list_runs_orders_newest_first`. |

No additions import from `components` or `workflows`. The yoyo import is
deferred to `_apply_migrations_sync` so the primitives layer remains
importable in environments where yoyo is unavailable (e.g. doc builds).

---

## Gate summary (2026-04-19)

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 257 passed, 0 skipped (32 Task 08 tests — protocol × 2, migrations × 4, WAL, create_run × 4, run-status × 2, runs × 3, tasks × 3, LLM calls × 7, rollback, 20-concurrent, artifacts, gates × 3, idempotency) |
| `uv run lint-imports` | ✅ 2 kept / 0 broken |
| `uv run ruff check` | ✅ all checks passed |
| CI `secret-scan` (local dry run) | ✅ `grep -E 'sk-ant-[A-Za-z0-9_-]+' tiers.yaml pricing.yaml` returns no matches |
| `test_scaffolding.py::test_scaffolding_file_exists[migrations/001_initial.sql]` | ✅ still passes — the filename survived Task 08's content replacement |

---

## Acceptance-criterion grading

| AC | Verdict | Evidence |
| --- | --- | --- |
| AC-1: `isinstance(storage, StorageBackend)` structural check | ✅ PASS | `StorageBackend` is `@runtime_checkable`; `SQLiteStorage` exposes every method with matching signatures. Pinned by `test_sqlite_storage_satisfies_storage_backend_protocol` (post-open) and `test_sqlite_storage_pre_open_still_satisfies_protocol` (pre-open — the protocol is structural, so the sync `__init__` path also counts). |
| AC-2: First open applies `001_initial.sql`, second open does nothing | ✅ PASS | `test_first_open_applies_001_initial` asserts exactly one row in `_yoyo_migration` with `migration_id == '001_initial'`. `test_second_open_is_noop` reopens the same DB and asserts the row count stays at 1. `test_first_open_creates_every_schema_table` + `test_first_open_creates_required_indexes` catch accidental schema drift. |
| AC-3: WAL mode via `PRAGMA journal_mode` | ✅ PASS | `test_wal_mode_is_enabled_after_open` opens a raw `sqlite3.connect` on the post-open DB and asserts `PRAGMA journal_mode` returns `wal`. |
| AC-4: `create_run()` requires `workflow_dir_hash` — no null allowed | ✅ PASS | Three tests: `test_create_run_rejects_none_workflow_dir_hash` (`None` → `ValueError`), `test_create_run_rejects_empty_workflow_dir_hash` (`""` → `ValueError`), `test_create_run_persists_workflow_dir_hash` (happy path writes the 64-char hex hash to `runs.workflow_dir_hash`). |
| AC-5: `get_total_cost()` excludes rows where `is_local=1` | ✅ PASS | `test_get_total_cost_excludes_is_local_rows` sums three rows ($0.10 non-local + $0.05 local + $0.03 non-local → $0.13). `test_get_total_cost_is_zero_when_only_local_calls` pins the all-local edge case. `test_get_total_cost_is_zero_when_no_rows` pins the empty case. `test_get_cost_breakdown_groups_by_component_excluding_local` extends the same rule to the per-component aggregator. |
| AC-6: Migration rollback works (create 002, roll back, confirm schema reverts) | ✅ PASS | `test_migration_rollback_reverts_schema` seeds `001_initial.sql` + `001_initial.rollback.sql` + a synthetic `002_tmp.sql` / `002_tmp.rollback.sql` into `tmp_path/migrations`. Opens storage → confirms `tmp_probe` exists. Rolls back 002 via yoyo's `backend.to_rollback()` + `MigrationList` → confirms `tmp_probe` is gone while `runs` and `llm_calls` remain. |
| AC-7: 20 concurrent writes via `asyncio.gather` | ✅ PASS | `test_twenty_concurrent_log_llm_call_succeeds` fires 20 `log_llm_call` coroutines via `asyncio.gather`, each inserting $0.01 cost. Asserts `get_total_cost` == $0.20 and the raw `llm_calls` table has 20 rows. |

---

## Carry-over grading

Task 08 has no carry-over items from prior audits. Task 07's audit
explicitly noted ("Task 07 surfaces no forward-deferred items; no
carry-over sections needed on Task 08 …").

---

## Additional coverage beyond ACs (not required, but present)

- `test_create_run_accepts_none_budget_cap` — optional budget cap.
- `test_update_run_status_sets_finished_at_on_terminal_state` —
  terminal statuses (`completed`, `failed`) auto-populate `finished_at`.
- `test_update_run_status_leaves_finished_at_null_for_non_terminal` —
  non-terminal (`running`) leaves `finished_at` NULL.
- `test_get_run_returns_none_when_missing` — scoped read returns None.
- `test_list_runs_orders_newest_first` — newest-first ordering.
- `test_list_runs_respects_limit` — LIMIT honoured.
- `test_upsert_task_inserts_then_updates` — ON CONFLICT DO UPDATE
  with COALESCE preserves `started_at` when only `finished_at` is
  passed on the second call.
- `test_get_tasks_is_scoped_to_run` — tasks from another run never
  leak in.
- `test_log_llm_call_stores_is_escalation_flag` — C-21 tag round-trips.
- `test_log_llm_call_auto_populates_called_at` — timestamp default.
- `test_log_artifact_persists_row` — P-29 wiring.
- `test_update_gate_state_upsert_preserves_rendered_at` — original
  render time survives a later `approved` write; `resolved_at` is
  set on terminal statuses.
- `test_get_gate_state_returns_none_when_absent` — missing gate.
- `test_initialize_is_idempotent` — second `initialize()` call is a
  no-op (short-circuited by `self._initialized`).

---

## Interface-drift check (sibling tasks)

- **Task 09 (cost tracker)** — spec expects `storage.log_llm_call(...)`,
  `storage.get_total_cost(...)`, `storage.update_run_status(total_cost_usd=...)`.
  All three land here with matching signatures. Task 09 has no
  interface work.
- **Task 10 (retry)** — no storage dependency.
- **Task 11 (logging)** — no storage dependency.
- **Task 12 (CLI primitives)** — spec expects `storage.list_runs()`,
  `storage.get_run(run_id)`, `storage.get_cost_breakdown(run_id)`,
  `storage.get_tasks(run_id)`, `storage.get_gate_state(run_id, gate_id)`.
  All land here.
- **W-03 (workflow dir snapshot)** — only the hash side ships in
  Task 08. Copying the directory to `~/.ai-workflows/runs/<run_id>/workflow/`
  is owned by Task 12 `aiw run`. Documented in `design_docs/issues.md`.

---

## Propagation status

- Task 08 surfaces no forward-deferred items. No carry-over sections
  needed on Task 09, 10, 11, or 12.
- CRIT-02 flipped from `[ ]` to `[~]` in `design_docs/issues.md` — the
  hash storage + `NOT NULL` schema ship here; resume refusal on
  mismatch is owned by Task 12 `aiw resume`, so the box stays partial
  until then.
- W-03 stays `[~]` for the same reason.
- CRIT-10 flipped from `[ ]` to `[x]`.
- P-27 flipped from `[~]` to `[x]`.
- P-31 flipped from `[ ]` to `[x]`.

---

## Issue log — tracked for cross-task follow-up

- **M1-T08-ISS-01** — LOW — yoyo dedup by filename, not content hash.
  Observation only. Closed. Owner: n/a (no live impact).
