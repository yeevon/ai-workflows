# Task 09 — StructuredLogger Sanity Pass — Pre-build Audit Amendments

**Source task:** [../task_09_logger_sanity.md](../task_09_logger_sanity.md)
**Source audit:** [../audit.md](../audit.md) (produced by [M1 Task 01](../task_01_reconciliation_audit.md))
**Created on:** 2026-04-19
**Status:** 📋 PENDING BUILDER — gates not yet run; this file encodes pre-build amendments only.

## Why this file exists

Task files `task_02`…`task_13` were drafted **before** the reconciliation audit ran. Per [CLAUDE.md](../../../../CLAUDE.md) Builder conventions, this file is the bridge to the [audit.md](../audit.md) source of truth.

## Required reading order for Builder

1. [../../../architecture.md](../../../architecture.md) — especially §4.1 / §8.1.
2. [../audit.md](../audit.md) — authoritative source. Rows targeting `task 09` apply here.
3. [../task_09_logger_sanity.md](../task_09_logger_sanity.md) — deliverables + ACs.
4. This file — amendments.
5. If audit and task disagree, **raise the conflict before implementing** per CLAUDE.md Builder conventions.

## Rows from audit.md this task must execute

### MODIFY

| Path | Reason |
| --- | --- |
| `ai_workflows/primitives/logging.py` | `StructuredLogger` is the single observability surface per [architecture.md §8.1](../../../architecture.md); sanity-pass to drop any logfire imports and confirm record shape still matches §4.1. |
| `tests/primitives/test_logging.py` | Update to assert the record shape declared in [architecture.md §8.1](../../../architecture.md); drop any logfire assertions. |

## Known amendments vs. task spec

- **No external sinks.** Per [architecture.md §8.1](../../../architecture.md), Langfuse / LangSmith / OpenTelemetry are **deferred** in [nice_to_have.md §1/§3/§8](../../../nice_to_have.md). Do not silently add any observability dependency or decorator. If the current code has any logfire import, it must be stripped here as a direct consequence of [task 02](../task_02_dependency_swap.md) removing the dependency.
- **Record shape.** [architecture.md §8.1](../../../architecture.md) lists the required fields: `run_id`, `workflow`, `node`, `tier`, `provider`, `model`, `duration_ms`, `input_tokens`, `output_tokens`, `cost_usd`. Some of these (`node`, `tier`, `provider`, `model`, `run_id` at node level) only become populated in M2+; the M1 sanity pass is about the *shape/contract*, not about populating every field at M1.

## Carry-over from prior audits

### From [M1-T02-ISS-01](task_02_issue.md#-medium--m1-t02-iss-01-post-t02-interim-gate-red-state-forward-deferral-propagated) (T02 post-build audit, 2026-04-19)

Task 02 removed `logfire>=2.0` from `pyproject.toml` but `ai_workflows/primitives/logging.py` still does `import logfire` at line 53. The sanity pass under this task must drop that import outright. Highest-leverage carry-over in M1: restoring it closes 2 of the 11 `uv run pytest` collection errors **and** the 4 `tests/test_scaffolding.py` CLI-path assertions (because `ai_workflows.cli` transitively imports `ai_workflows.primitives.logging`).

- [ ] **M1-T02-ISS-01 · MEDIUM** — Remove `import logfire` from `primitives/logging.py`; verify `tests/test_scaffolding.py::test_layered_packages_import[ai_workflows.cli]`, `test_aiw_help_runs`, `test_aiw_version_command`, `test_aiw_console_script_resolves` all return green. Record shape unchanged (see "Record shape" note above — this is purely about the import line). Source: [task_02_issue.md §Propagation status](task_02_issue.md#propagation-status).

### From [M1-T04-ISS-01](task_04_issue.md#-medium--m1-t04-iss-01-stale-forensic_logger-references-in-t09-owned-files) (T04 post-build audit, 2026-04-19)

Task 04 deleted `ai_workflows/primitives/tools/` wholesale, including `forensic_logger.py`. Two stale references now dangle inside files already slated for T09 MODIFY per [audit.md §1 / §3](../audit.md):

| Location | Nature |
| --- | --- |
| `ai_workflows/primitives/logging.py:35-40` | Module docstring `Related` section cross-references `:mod:`ai_workflows.primitives.tools.forensic_logger`` and the `M1-T05-ISS-02` carry-over that the forensic event rode on. Cosmetic; docstring points at a deleted module. |
| `tests/primitives/test_logging.py:~248-280` | `test_forensic_warning_lands_in_run_json_sink_under_production_config` contains `from ai_workflows.primitives.tools.forensic_logger import log_suspicious_patterns` at line 255. Currently masked by the upstream `import logfire` collection error, but surfaces as an ImportError the instant T09 unblocks logfire removal. |

The `log_suspicious_patterns` primitive was part of the pre-pivot tool-registry observability hook and is out of scope under [architecture.md §8.1](../../../architecture.md) (`StructuredLogger` is the single observability surface). There is no replacement to emit the `tool_output_suspicious_patterns` WARNING — the concept belongs to the deleted tool registry.

- [ ] **M1-T04-ISS-01 · MEDIUM** — (a) Drop or rewrite the `Related` paragraph in `ai_workflows/primitives/logging.py:35-40` so it no longer mentions `primitives.tools.forensic_logger` or the `M1-T05-ISS-02` forensic carry-over. (b) Retire or rewrite `tests/primitives/test_logging.py::test_forensic_warning_lands_in_run_json_sink_under_production_config` (lines ~248-280) — the simplest move is to delete the test; if the run-JSON-sink smoke coverage is still worth keeping, rewrite it around a plain `structlog` WARNING and drop the `log_suspicious_patterns` dependency entirely. Source: [task_04_issue.md §M1-T04-ISS-01](task_04_issue.md#-medium--m1-t04-iss-01-stale-forensic_logger-references-in-t09-owned-files).

### From [M1-T08-DEF-01](task_08_issue.md) (T08 post-build audit, 2026-04-19)

T08 removed the `BudgetExceeded` exception from `ai_workflows/primitives/cost.py` (replaced by `NonRetryable("budget exceeded")` from T07 per [architecture.md §8.5](../../../architecture.md)). `ai_workflows/primitives/logging.py:25` still names `BudgetExceeded` as an ERROR-level exemplar in its module docstring. Cosmetic; T09 already owns `logging.py` MODIFY, so the fix lands here as a drive-by with the `logfire` and `forensic_logger` sweeps.

- [ ] **M1-T08-DEF-01 · LOW** — Replace the `BudgetExceeded` reference in `ai_workflows/primitives/logging.py:25` (module docstring, ERROR-level example) with `NonRetryable("budget exceeded")` — that is the post-T08 exception the logger will actually see per [architecture.md §8.5](../../../architecture.md). Docstring-only; no test change. Source: [task_08_issue.md §Deferred to future tasks](task_08_issue.md).

## Propagation status

Post-build audit will overwrite this file with implementation findings. When the T02 carry-over checkbox ticks, [task_02_issue.md](task_02_issue.md) flips ISS-01 from `DEFERRED` to `RESOLVED` on the next T02 re-audit touch point. When the T08 carry-over ticks, [task_08_issue.md](task_08_issue.md) flips `M1-T08-DEF-01` from `DEFERRED` to `RESOLVED` on the next T08 re-audit touch point.
