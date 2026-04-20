# Task 09 — StructuredLogger Sanity Pass — Audit Issues

**Source task:** [../task_09_logger_sanity.md](../task_09_logger_sanity.md)
**Source audit:** [../audit.md](../audit.md) (produced by [M1 Task 01](../task_01_reconciliation_audit.md))
**Audited on:** 2026-04-19 (post-build, Cycle 1 + Cycle 2 sweep)
**Audit scope:** `ai_workflows/primitives/logging.py`, `tests/primitives/test_logging.py`, carry-over sweeps from M1-T02-ISS-01 / M1-T04-ISS-01 / M1-T08-DEF-01, downstream impact on `tests/test_scaffolding.py` CLI-path assertions, full-suite T-scope reading.
**Status:** ✅ PASS on T09's four explicit ACs + three inherited carry-overs + the cycle-1 LOW finding closed by the cycle-2 docstring sweep. No remaining open issues.

## Design-drift check (mandatory; architecture.md + KDRs re-read)

| Concern | Verdict | Evidence |
| --- | --- | --- |
| New dependency in `pyproject.toml` | ✅ None added | `pyproject.toml` unchanged; only `structlog` (already present) used |
| Four-layer contract | ✅ Kept | `logging.py` imports only `structlog` + stdlib (`logging`, `sys`, `pathlib`, `typing`); `uv run lint-imports` → 2 kept, 0 broken |
| LLM call added (KDR-004 TieredNode+ValidatorNode) | ✅ N/A | T09 is observability-only; no LLM call |
| `anthropic` SDK / `ANTHROPIC_API_KEY` (KDR-003) | ✅ Absent | `grep -n anthropic ai_workflows/primitives/logging.py` → 0 hits |
| Checkpoint / resume logic (KDR-009) | ✅ N/A | `Storage` / `SqliteSaver` not imported |
| Retry logic (KDR-006 taxonomy via `RetryingEdge`) | ✅ N/A | No retry loop; `NonRetryable` only named in the docstring ERROR-level example |
| Observability (StructuredLogger only) | ✅ Compliant | Every trace of the removed second backend is gone (literal grep on `ai_workflows/` → 0 hits after cycle 2). `structlog` is the sole backend. `test_logging_module_structlog_is_only_backend` pins zero import-line matches for `logfire` / `langsmith` / `langfuse` / `opentelemetry` |
| `nice_to_have.md` adoption check (§1 Langfuse / §3 LangSmith / §8 OTel) | ✅ None | No Langfuse / LangSmith / OpenTelemetry surface introduced. Deferred per [nice_to_have.md §1/§3/§8](../../../nice_to_have.md) |
| Record shape matches §8.1 | ✅ Honoured | `NODE_LOG_FIELDS` constant is the exact ten fields from architecture.md §8.1; `log_node_event` emits every field with `None` default for "unknown at emit time" per the task spec |
| `configure_logging` signature preserved | ✅ Honoured | `ai_workflows/cli.py:86` + `tests/test_cli.py:322` continue to call `configure_logging(level=...)` unchanged |

No design drift. Proceeding to AC grading.

## AC grading (task file + carry-over)

| # | AC | Verdict | Evidence |
| --- | --- | --- | --- |
| AC-1 | Log record carries every §8.1 field on emit | ✅ | `NODE_LOG_FIELDS = (run_id, workflow, node, tier, provider, model, duration_ms, input_tokens, output_tokens, cost_usd)` pinned by `test_node_log_fields_match_architecture_81`. Route-kind coverage: `test_log_node_event_emits_all_fields_for_litellm_route` + `test_log_node_event_emits_all_fields_for_claude_code_route`. Unknown-field behaviour: `test_log_node_event_emits_none_for_unpopulated_fields` asserts `None` (not a placeholder). |
| AC-2 | `grep -r "logfire" ai_workflows/` → zero | ✅ | Literal whole-tree grep: 0 hits. Import-line scan: 0. Pinned by three tests: `test_logging_module_has_no_logfire_import` (import lines), `test_logging_module_source_has_no_logfire_mentions_anywhere` (whole-file, added cycle 2), `test_logging_module_structlog_is_only_backend` (backend-name scan). |
| AC-3 | `grep -r "pydantic_ai" ai_workflows/primitives/logging.py` → zero | ✅ | Literal grep → 0 hits. Import-line scan pinned by `test_logging_module_has_no_pydantic_ai_imports`. |
| AC-4 | `uv run pytest tests/primitives/test_logging.py` green | ✅ | 24 passed in 0.04s |
| Carry-over M1-T02-ISS-01 (MEDIUM) | Drop `import logfire` from `primitives/logging.py` | ✅ RESOLVED | Pre-pivot `import logfire` line removed. Scaffolding tests that were blocked by the missing module pass: `test_layered_packages_import[ai_workflows.cli]`, `test_aiw_help_runs`, `test_aiw_version_command`, `test_aiw_console_script_resolves` — all 4 green. `tests/test_scaffolding.py` now: 25 passed. |
| Carry-over M1-T04-ISS-01 (MEDIUM) (a) | `Related` paragraph no longer cites `primitives.tools.forensic_logger` | ✅ RESOLVED | Pre-pivot `Related` section naming `:mod:\`ai_workflows.primitives.tools.forensic_logger\`` removed. Rewritten `Related` cites `primitives.retry` + `primitives.cost` + the `M1-T01-ISS-08` secret-scan pointer. `grep -n 'forensic_logger\|primitives.tools' ai_workflows/primitives/logging.py` → 0 hits. Pinned by `test_logging_module_docstring_no_longer_references_forensic_logger`. |
| Carry-over M1-T04-ISS-01 (MEDIUM) (b) | `test_forensic_warning_…` retired or rewritten | ✅ RESOLVED | Test deleted. `log_suspicious_patterns` belonged to the pre-pivot tool registry that T04 deleted; [architecture.md §8.1](../../../architecture.md) makes `StructuredLogger` the single observability surface — there is no replacement emit path to pin, so retirement is the correct close. Documented in CHANGELOG deviations. |
| Carry-over M1-T08-DEF-01 (LOW) | Replace `BudgetExceeded` with `NonRetryable("budget exceeded")` in `logging.py:25` docstring | ✅ RESOLVED | `grep -n 'BudgetExceeded' ai_workflows/primitives/logging.py` → 0 hits. `NonRetryable` now appears in the ERROR-level docstring example and in the new `Related` cross-ref to `primitives.retry`. Pinned by `test_logging_module_docstring_uses_nonretryable_not_budgetexceeded`. |

## 🔴 HIGH

_None._

## 🟡 MEDIUM

_None._

## 🟢 LOW

### ✅ RESOLVED (cycle 2) — M1-T09-ISS-01: module docstring named the removed second backend, so AC-2's literal grep was non-zero

**Original problem:** `ai_workflows/primitives/logging.py` lines 4 and 8 mentioned the removed second-backend library by name in the module docstring — both were historical narrative text explaining why the backend was absent. The spec AC-2 is phrased as a literal `grep -r` that expects zero matches, so the letter of the AC was not met even though the spirit (no import, no configure call) was.

**Fix landed in cycle 2:** Rewrote the module docstring's first paragraph to describe the removed dependency as "a second observability backend" / "the prior second-backend dependency" without naming the library. Added `test_logging_module_source_has_no_logfire_mentions_anywhere` as a whole-file pin (companion to the existing import-line scans). Verified by re-running `grep -rn 'logfire' ai_workflows/ --include='*.py'` → 0 hits. `uv run pytest tests/primitives/test_logging.py` → 24 passed.

## Additions beyond spec — audited and justified

1. **`log_node_event(logger, *, run_id, workflow, ..., **extra)` helper (not in the spec's deliverables list).** The spec's AC-1 is "Log record carries every field listed above on emit" — this is unsatisfiable without a helper that guarantees every field appears on every emit. Leaving the contract to ad-hoc `logger.info(..., run_id=..., cost_usd=...)` call-sites means any caller that forgets a field silently drifts the schema. The helper is the minimum scope to make AC-1 mechanically provable. Documented in CHANGELOG deviations.
2. **`NODE_LOG_FIELDS` constant exposing the ten field names.** Companion to (1); lets the test pin the §8.1 shape at module level without re-hardcoding the tuple. `test_node_log_fields_match_architecture_81` treats it as the source of truth.
3. **`level` parameter on `log_node_event` (default `"info"`).** The spec's WARNING/ERROR use cases from [architecture.md §8.1](../../../architecture.md) (missing pricing rows, `NonRetryable("budget exceeded")`) need the helper to route through `logger.warning` / `logger.error`. Keeping the default as `"info"` preserves the "node_completed" golden path. Covered by `test_log_node_event_level_override_routes_to_warning`.
4. **`**extra` forwarding on `log_node_event`.** Retry counts, validator-revision rounds, and workflow-specific keys are not in §8.1 but are legitimate payload on emit. Forwarding keeps the helper a drop-in without forcing callers to bypass it for extra fields. Covered by `test_log_node_event_forwards_extra_kwargs`.
5. **Retirement of the M1-T05-ISS-02 forensic carry-over test.** The T04 audit explicitly named retirement as the simplest close path; the test's target (`log_suspicious_patterns` in the deleted `primitives.tools.forensic_logger`) has no post-pivot replacement. A drive-by rewrite around a plain `structlog` WARNING was considered but rejected — it would invent a fake run-JSON-sink smoke test detached from any real code path. Documented in CHANGELOG.
6. **Pin tests for all three carry-overs (logfire / forensic / BudgetExceeded).** Each carry-over gets its own `test_logging_module_*` import- or docstring-scan test, so regressions surface at module load instead of at gate time. Small, no scope creep.
7. **Whole-file `logfire` pin (cycle 2).** `test_logging_module_source_has_no_logfire_mentions_anywhere` complements the import-line scan. Small, single-assertion; closes the literal reading of AC-2.

## Gate summary

| Gate | Result | Notes |
| --- | --- | --- |
| `uv run ruff check` | ✅ | "All checks passed!" |
| `uv run lint-imports` | ✅ | 2 contracts kept, 0 broken |
| `uv run pytest tests/primitives/test_logging.py` | ✅ | 24 passed in 0.04s |
| `uv run pytest tests/test_scaffolding.py` | ✅ | 25 passed — T02 carry-over cascade cleared (4 tests were red pre-T09) |
| `uv run pytest` (full suite) | 🟡 T-scope read | 159 passed / 2 failed / 11 errors. All 13 residuals are in `tests/test_cli.py` and trace to `SQLiteStorage.create_run()` no longer accepting the `workflow_dir_hash` kwarg — **T11 territory** (CLI stub-down owns the signature drift). Pre-existing, not introduced here; T08 audit already logged the cascade under the same T-scope reading. T09 *reduced* the pre-T09 baseline by unblocking `test_logging.py` (0 → 24 green) and the 4 scaffolding failures — net +31 passing across the suite |
| `grep -r "logfire" ai_workflows/` | ✅ | 0 hits (literal whole-tree) |
| `grep -r "pydantic_ai" ai_workflows/primitives/logging.py` | ✅ | 0 hits literal; import-line scan pinned by test |

## Issue log — cross-task follow-up

| ID | Severity | Status | Where | Owner |
| --- | --- | --- | --- | --- |
| M1-T02-ISS-01 | MEDIUM | ✅ RESOLVED (cycle 1) | `import logfire` removed from `logging.py` | Closed by T09 refit — flip `DEFERRED → RESOLVED` on next T02 re-audit touch point |
| M1-T04-ISS-01 | MEDIUM | ✅ RESOLVED (cycle 1) | `forensic_logger` `Related` paragraph removed; forensic carry-over test retired | Closed by T09 refit — flip `DEFERRED → RESOLVED` on next T04 re-audit touch point |
| M1-T08-DEF-01 | LOW | ✅ RESOLVED (cycle 1) | `BudgetExceeded` → `NonRetryable` in `logging.py` docstring | Closed by T09 refit — flip `DEFERRED → RESOLVED` on next T08 re-audit touch point |
| M1-T09-ISS-01 | LOW | ✅ RESOLVED (cycle 2) | `logging.py:4`, `logging.py:8` docstring mentions of the removed second-backend library | Closed |

## Deferred to future tasks

_None new._ The `tests/test_cli.py` T11 cascade (13 failures/errors) is already owned by [task_11_cli_stub_down.md](../task_11_cli_stub_down.md); no new carry-over is needed.

## Deferred to nice_to_have

_None._ No finding maps to a [nice_to_have.md](../../../nice_to_have.md) entry. The Langfuse / LangSmith / OpenTelemetry items (§1 / §3 / §8) are correctly deferred — T09's `StructuredLogger`-only stance matches the triggers those sections name.

## Propagation status

- M1-T02-ISS-01 resolved above (cycle 1 `import logfire` removal). Next T02 re-audit touch point, [task_02_issue.md](task_02_issue.md) can flip from `DEFERRED` to `RESOLVED (<commit sha>)`.
- M1-T04-ISS-01 resolved above (cycle 1 `Related` paragraph + forensic test retirement). Next T04 re-audit touch point, [task_04_issue.md](task_04_issue.md) can flip from `DEFERRED` to `RESOLVED (<commit sha>)`.
- M1-T08-DEF-01 resolved above (cycle 1 `BudgetExceeded` → `NonRetryable` docstring sweep). Next T08 re-audit touch point, [task_08_issue.md](task_08_issue.md) can flip from `DEFERRED` to `RESOLVED (<commit sha>)`.
- M1-T09-ISS-01 resolved above (cycle 2 docstring sweep + whole-file pin test). Self-contained; no external propagation.
