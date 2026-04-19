# Task 12 — CLI Primitives — Audit Issues

**Source task:** [../task_12_cli_primitives.md](../task_12_cli_primitives.md)
**Audited on:** 2026-04-19
**Audit scope:** `ai_workflows/cli.py`, `ai_workflows/primitives/storage.py`
(new `list_llm_calls` method), `tests/test_cli.py`, `pyproject.toml`
(ruff bugbear config), `CHANGELOG.md`, milestone README, task spec,
carry-over propagation in `issues/task_04_issue.md` and
`issues/task_09_issue.md`.
**Status:** ✅ PASS — every AC has a dedicated pinning test, both
carry-overs (`M1-T04-ISS-01`, `M1-T09-ISS-02`) are implemented and
tested, all three local gates are green, no HIGH / MEDIUM / LOW
findings.

---

## Acceptance-criterion grading

| AC | Spec | Verdict | Pinning test(s) |
| --- | --- | --- | --- |
| AC-1 | `aiw list-runs` renders correctly with seeded test data | ✅ PASS | `test_list_runs_renders_seeded_runs` (full render, both seeded runs visible, `$` costs formatted), `test_list_runs_truncates_long_workflow_names` (22-char column cap per spec), `test_list_runs_with_empty_db_prints_header_and_message` (empty-DB UX) |
| AC-2 | `aiw inspect <id>` shows cost breakdown | ✅ PASS | `test_inspect_shows_cost_breakdown` (per-component line, local call excluded), `test_inspect_shows_per_task_breakdown` (per-task lines) |
| AC-3 | `aiw inspect <id>` flags `workflow_dir_hash` mismatch | ✅ PASS | `test_inspect_flags_mismatch_when_directory_changed` — hashes a dir, seeds the run, asserts `current match: OK`, drifts the dir contents, asserts `current match: MISMATCH`. |
| AC-4 | `aiw inspect <nonexistent>` exits 1 | ✅ PASS | `test_inspect_missing_run_exits_1_with_message` — asserts `exit_code == 1` and the "not found" message lands on stderr with the requested run id echoed back. |
| AC-5 | `aiw resume <id>` prints placeholder | ✅ PASS | `test_resume_prints_placeholder` (happy path), `test_resume_missing_run_exits_1` (negative path — ensures the stub still validates the SQLite lookup). |
| AC-6 | `aiw --help` lists all commands | ✅ PASS | `test_aiw_help_lists_every_command` — asserts `list-runs`, `inspect`, `resume`, `run`, and `version` all appear in the help text. |
| AC-7 | `--log-level DEBUG` produces human-readable console | ✅ PASS | `test_debug_log_level_produces_human_readable_console` — drives the production `configure_logging(level="DEBUG", stream=buf)` pipeline, asserts `[debug` bracket + event name + `key=value` tokens, then invokes `aiw --log-level DEBUG list-runs` end-to-end. |

## Carry-over grading

| ID | Source | Verdict | Pinning test(s) |
| --- | --- | --- | --- |
| M1-T04-ISS-01 | [task_04_issue.md](task_04_issue.md) | ✅ RESOLVED | `test_inspect_surfaces_cache_read_and_cache_write` — opus call seeded with 200 cache-read / 100 cache-write tokens, asserts both column headers and the token counts render. |
| M1-T09-ISS-02 | [task_09_issue.md](task_09_issue.md) | ✅ RESOLVED | `test_inspect_budget_line_with_cap` (`Budget: $0.42 / $5.00 (8% used)`), `test_inspect_budget_line_without_cap` (`Budget: $0.00 (no cap)`). |

## Additions beyond spec — audited and justified

| Addition | Rationale |
| --- | --- |
| `--workflow-dir` opt-in flag on `aiw inspect` | Spec says "computes current hash to flag drift" but `runs` stores only the hash, not the path. Without this flag, AC-3 cannot be tested end-to-end. Default behaviour prints the stored hash with a hint, so the common case still matches the spec sketch. |
| `list_llm_calls(run_id)` on `SQLiteStorage` + `StorageBackend` | Spec requires "LLM Calls: N total" and the `M1-T04-ISS-01` carry-over needs per-call `cache_read`/`cache_write` visibility. A single query method handles both — cheaper than adding a count plus a separate per-call fetch. |
| `tool.ruff.lint.flake8-bugbear.extend-immutable-calls` | Typer's `typer.Option(...)` / `typer.Argument(...)` defaults are the framework's only parameter-declaration idiom. They're evaluated once at import time and treated as markers, so they're safe and the Typer docs recommend this exact ruff knob. |
| Negative test `test_resume_missing_run_exits_1` | Stub still hits `storage.get_run(...)`; pairing the positive AC with a negative path validates the SQLite round-trip — the exact reason the spec calls out "the stub exists so the SQLite queries are validated". |
| `test_run_stub_prints_not_implemented` | AC-6 requires `run` to appear in `--help`; this test pins that invoking the stub itself works with `--profile`, protecting the forward-compat flag from silent removal. |

## Convention checks

| Check | Result |
| --- | --- |
| Module docstring cites task + relationships | ✅ `ai_workflows/cli.py` top-of-file docstring names M1 Task 12 and cross-links storage / workflow_hash / logging. |
| Every public function has a docstring | ✅ `version`, `list_runs`, `inspect`, `resume`, `run`, plus the `_root` callback all have docstrings. Private helpers (`_render_*`, `_format_*`, `_load_*`) also carry docstrings since several are testable via their side effects. |
| New storage method carries a docstring | ✅ `SQLiteStorage.list_llm_calls` and the protocol method both do. |
| Layer discipline | ✅ `cli.py` is under `ai_workflows/` (the outer CLI layer) and imports only from `ai_workflows.primitives.*`. `import-linter` reports 2 kept / 0 broken. |
| Changelog discipline | ✅ New `### Added — M1 Task 12:` entry added under `## [Unreleased]` above Task 11's entry, lists files, ACs, carry-overs, and three explicit deviations. |
| Propagation discipline | ✅ `task_04_issue.md` and `task_09_issue.md` both flipped DEFERRED → RESOLVED with test-name citations; target task file's `Carry-over from prior audits` section ticked with "Resolved by M1 Task 12 — …" pointers. |
| Scope discipline | ✅ No drive-by refactors; unrelated modules untouched. `storage.list_llm_calls` is the only net-new primitive, and it's pulled in strictly because the spec sketch ("LLM Calls: N total") + M1-T04-ISS-01 carry-over require it. |

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 346 passed, 2 deprecation warnings (both pre-existing yoyo-migrations datetime-adapter notices — unrelated to Task 12) |
| `uv run lint-imports` | ✅ 2 contracts kept / 0 broken (primitives → components/workflows forbidden; components → workflows forbidden) |
| `uv run ruff check` | ✅ all checks passed |

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

None.

## Issue log — cross-task follow-up

| ID | Severity | Owner | Status |
| --- | --- | --- | --- |
| — | — | — | No new issues opened by this audit. |

## Propagation status

- `M1-T04-ISS-01` — flipped in [task_04_issue.md](task_04_issue.md) to
  ✅ RESOLVED citing the Task 12 pinning test.
- `M1-T09-ISS-02` — flipped in [task_09_issue.md](task_09_issue.md)
  issue-log table to ✅ RESOLVED.
- No new forward-deferrals introduced by this task.

---

**Milestone 1 status at end of Task 12 audit:** all 12 tasks complete
with ✅ PASS audits. M1 exit-criteria readiness check is the natural
follow-up (live LLM call from REPL → tier system → logged SQLite row
→ visible in `aiw list-runs`), but that's an end-to-end integration
rather than a unit-level task and is outside Task 12's scope.
