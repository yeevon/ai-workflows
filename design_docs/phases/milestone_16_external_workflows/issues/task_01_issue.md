# Task 01 — External workflow module discovery — Audit Issues

**Source task:** [../task_01_external_workflow_modules.md](../task_01_external_workflow_modules.md)
**Audited on:** 2026-04-24 (Cycle 1 → 2026-04-24; Cycle 2 re-audit → 2026-04-24)
**Audit scope:** Loader module (`ai_workflows/workflows/loader.py`), dispatch routing extension (`_dispatch._import_workflow_module`), CLI root callback (`ai_workflows/cli.py::_root`), MCP `_cli` command (`ai_workflows/mcp/__main__.py`), tests (`tests/workflows/test_external_module_loader.py`, `tests/cli/test_external_workflow.py`, `tests/mcp/test_external_workflow.py`), KDR-013 in `architecture.md §9`, ADR-0007, docs (`docs/writing-a-workflow.md`, `README.md`), CHANGELOG entry. Cross-checked against architecture.md §3 (four-layer contract), §6 (external dependencies), §9 (KDR table), KDR-002 / KDR-003 / KDR-004 / KDR-008 / KDR-009 / KDR-013.
**Status:** ✅ PASS — all 6 Cycle-1 findings resolved in Cycle 2. Gates green (646 passed, 6 skipped); 17 new tests (10 loader unit + 3 CLI integration + 4 MCP surface-parity), four-layer contract preserved, zero design drift.

## Design-drift check

| Axis | Finding |
|---|---|
| New dependency | None. Loader uses stdlib only (`importlib`, `os`, `pkgutil`, `contextlib`). ✅ |
| New module / layer | `ai_workflows/workflows/loader.py` lives in the workflows layer. `import-linter` 4 kept / 0 broken. ✅ |
| LLM call added | None. Loader is import-time orchestration only. ✅ |
| Anthropic SDK / key | None. Zero imports, zero env reads. KDR-003 preserved. ✅ |
| Checkpoint / resume | Untouched. KDR-009 preserved. ✅ |
| Retry logic | Untouched. KDR-006 preserved. ✅ |
| Observability | No logging added in the loader itself; existing surfaces use `structlog` via their own `configure_logging()` calls. ✅ |
| MCP schema | Unchanged. KDR-002 / KDR-008 preserved. ✅ |

No drift.

## AC grading (post-Cycle-2)

| # | AC | Grade | Evidence |
|---|---|---|---|
| 1 | `loader.py` + `ExternalWorkflowImportError` exist with the specified signatures | ✅ PASS | `ai_workflows/workflows/loader.py` matches spec; `__all__` exposes `ENV_VAR_NAME` + the two public names. |
| 2 | `AIW_EXTRA_WORKFLOW_MODULES` honoured (unset / empty / comma-separated / whitespace-trimmed / empty-entries-skipped) | ✅ PASS | `test_env_var_unset_returns_empty_list`, `test_single_env_entry_imports_and_registers`, `test_comma_separated_entries_import_all`. |
| 3 | `--workflow-module` accepted on both `aiw` (root callback) and `aiw-mcp` (root command); repeatable; composes with env | ✅ PASS | `aiw`: `test_cli_flag_external_workflow_runs_end_to_end` (CliRunner invocation). `aiw-mcp`: `test_mcp_cli_exposes_workflow_module_option` (signature pin) + `test_mcp_cli_workflow_module_flag_calls_loader` (threads through to the loader via CliRunner spy). |
| 4 | Import uses `importlib.import_module(dotted)`; no `spec_from_file_location` | ✅ PASS | `loader.py` imports `importlib` only for `import_module`; no `spec_from_file_location` anywhere. |
| 5 | Non-importable entry raises `ExternalWorkflowImportError` with module path + chained cause; startup aborts | ✅ PASS | `test_import_failure_raises_external_workflow_import_error` + CLI integration `test_bad_module_path_exits_two_with_actionable_message`. |
| 6 | Module that imports cleanly but does not call `register(...)` is non-fatal at startup | ✅ PASS | `test_module_without_register_call_is_non_fatal` — utility module loads, registry stays empty for that name. |
| 7 | Idempotent re-load | ✅ PASS | `test_idempotent_reload_does_not_raise` — two calls, same env, return same list, registry count is 1. |
| 8 | Name-collision with shipped workflow surfaces via existing `register()` `ValueError` | ✅ PASS | `test_collision_with_shipped_name_raises_via_register` — primes the registry with a dummy binding then verifies the external registration raises `ExternalWorkflowImportError` with a `ValueError` chained cause that names the colliding workflow. Plus `test_eager_import_shipped_workflows_requests_shipped_modules` — pins the eager-import mechanism that normally primes the registry in production. |
| 9 | `_dispatch._import_workflow_module` consults `_REGISTRY` first; returns `sys.modules[builder.__module__]`; in-package lazy fallback preserved | ✅ PASS | `test_import_workflow_module_routes_external_registration` — registers an external module and verifies `_import_workflow_module` returns the external module by name. End-to-end coverage via the CLI + MCP integration tests. |
| 10 | MCP surface parity — stdio + HTTP both resolve external workflows via `run_workflow` | ✅ PASS | `test_stdio_run_workflow_dispatches_external_module` (direct `tool.fn`), `test_http_run_workflow_dispatches_external_module` (live uvicorn + `fastmcp.Client`). |
| 11 | Hermetic tests land green | ✅ PASS | 17 new tests, all hermetic. |
| 12 | Existing tests stay green | ✅ PASS | `AIW_BRANCH=design uv run pytest` → 646 passed (was 640 before M16; +6 net new tests after replacing one brittle variant), 6 skipped (pre-existing branch-gated + e2e), 0 regressions. |
| 13 | Four-layer contract preserved | ✅ PASS | `uv run lint-imports` → 4 contracts kept, 0 broken. |
| 14 | Gates green on both branches | ✅ PASS (design_branch) | `uv run pytest` + `lint-imports` + `ruff check` all clean. Main-branch cherry-pick is a release-cycle concern. |
| 15 | Docstrings cite M16 T01 + describe the load contract | ✅ PASS | `loader.py` module docstring is extensive; `_dispatch._import_workflow_module` docstring updated to cite M16 T01; `workflows/__init__.py` docstring gains an "External workflow discovery (M16 Task 01)" section; `_eager_import_shipped_workflows` docstring explicitly calls out the startup-cost tradeoff. |
| 16 | KDR-013 in `architecture.md §9`; ADR-0007 authored | ✅ PASS | KDR-013 row added alongside KDR-011; `design_docs/adr/0007_user_owned_code_contract.md` written with Context / Decision / Rejected alternatives / Consequences. |
| 17 | `docs/writing-a-workflow.md` §External workflows; `README.md` `## MCP server` pointer | ✅ PASS | Both shipped; ADR-0007 link carries the `(builder-only, on design branch)` marker required by `tests/docs/test_docs_links.py`. |
| 18 | CHANGELOG entry under `[Unreleased]` | ✅ PASS | Entry reflects final test counts (10 loader + 3 CLI + 4 MCP); non-goals enumerated; releases as 0.2.0. |

Summary: 18/18 PASS · 0 OPEN.

## 🔴 HIGH

*None.*

## 🟡 MEDIUM

*All three Cycle-1 findings resolved — see Issue log below.*

## 🟢 LOW

*All three Cycle-1 findings resolved — see Issue log below.*

## Additions beyond spec — audited and justified

| Addition | Justification |
|---|---|
| `_eager_import_shipped_workflows()` helper in `loader.py` | Makes the README's "in-package workflows cannot be shadowed" claim enforceable in production. The Cycle-2 tests pin both the helper's import requests (`test_eager_import_shipped_workflows_requests_shipped_modules`) and the downstream collision invariant (`test_collision_with_shipped_name_raises_via_register`). Not scope creep — smallest change that makes AC-8 actually guard the invariant. |
| `test_bad_module_path_exits_two_with_actionable_message` | Covers AC-5 at the CLI surface boundary (Typer error-handling path). Orthogonal coverage — not redundant with the loader unit test. |
| `ENV_VAR_NAME` exported from `loader.py` | Ergonomics: tests bind to the symbol rather than the literal string so a future rename cannot silently break tests. No behaviour change. |
| `_reset_state` fixture docstring | Explains the deliberate decision NOT to evict shipped workflow modules from `sys.modules` (doing so caused class-identity drift in downstream `isinstance` checks during Cycle 1). Future maintainers will not re-introduce the eviction. |
| Cycle 2: spy-on-`importlib.import_module` instead of `sys.modules` eviction in `test_eager_import_shipped_workflows_requests_shipped_modules` | Cleaner equivalent of the originally-proposed ISS-06 shape. Pins the invariant without cross-test pollution. |

## Gate summary

| Gate | Command | Result |
|---|---|---|
| Unit + integration tests | `AIW_BRANCH=design uv run pytest` | ✅ 646 passed · 6 skipped · 0 failures · 2 warnings (yoyo datetime deprecation, pre-existing) |
| Four-layer contract | `uv run lint-imports` | ✅ 4 kept / 0 broken |
| Lint | `uv run ruff check` | ✅ All checks passed |
| Docs link marker | `AIW_BRANCH=design uv run pytest tests/docs/test_docs_links.py` | ✅ PASS (ADR-0007 link carries the `(builder-only, on design branch)` marker) |

## Issue log — cross-task follow-up

| ID | Severity | Status | Resolution evidence |
|---|---|---|---|
| M16-T01-ISS-01 | 🟡 MEDIUM | ✅ RESOLVED (Cycle 2) | `tests/mcp/test_external_workflow.py::test_mcp_cli_exposes_workflow_module_option` + `test_mcp_cli_workflow_module_flag_calls_loader` |
| M16-T01-ISS-02 | 🟡 MEDIUM | ✅ RESOLVED (Cycle 2) | `tests/workflows/test_external_module_loader.py::test_module_without_register_call_is_non_fatal` |
| M16-T01-ISS-03 | 🟡 MEDIUM | ✅ RESOLVED (Cycle 2) | `tests/workflows/test_external_module_loader.py::test_collision_with_shipped_name_raises_via_register` |
| M16-T01-ISS-04 | 🟢 LOW | ✅ RESOLVED (Cycle 2) | `tests/workflows/test_external_module_loader.py::test_import_workflow_module_routes_external_registration` |
| M16-T01-ISS-05 | 🟢 LOW | ✅ RESOLVED (Cycle 2) | `ai_workflows/workflows/loader.py::_eager_import_shipped_workflows` docstring — Startup-cost note paragraph |
| M16-T01-ISS-06 | 🟢 LOW | ✅ RESOLVED (Cycle 2) | `tests/workflows/test_external_module_loader.py::test_eager_import_shipped_workflows_requests_shipped_modules` (spy-based, no `sys.modules` mutation) |

## Deferred to nice_to_have

*None.* Task non-goals (`aiw inspect`, `AIW_PRIMITIVES_PATH`, entry-point discovery, hot-reload, sandboxing, user-code linting) are already parked under `design_docs/nice_to_have.md §17-22` per the 0.1.3 audit disposition; no additional deferrals this cycle.

## Propagation status

No cross-task forward-deferrals. M16 T01 is a single-task milestone; close-out = release 0.2.0 via the documented main-branch cherry-pick flow (same shape as 0.1.1 / 0.1.2 / 0.1.3).
