# Task 04 — Remove Tool Registry + Stdlib Tools — Audit Issues

**Source task:** [../task_04_remove_tool_registry.md](../task_04_remove_tool_registry.md)
**Source audit:** [../audit.md](../audit.md) (produced by [M1 Task 01](../task_01_reconciliation_audit.md))
**Audited on:** 2026-04-19 (cycle 1 post-build audit — overwrites the PENDING BUILDER pre-build file)
**Audit scope:** deletion of `ai_workflows/primitives/tools/` (8 files), deletion of `tests/primitives/tools/` (7 files) + flat `tests/primitives/test_tool_registry.py`, `tests/test_scaffolding.py` parametrize-list edit, CHANGELOG entry, full-suite gates (pytest, lint-imports, ruff), design-drift cross-check against [architecture.md](../../../architecture.md) §3 / §4.1 / §8.1 + KDR-002 / KDR-008, grep sweep for surviving `forensic_logger|ToolRegistry|from ai_workflows.primitives.tools` references, pre-build amendments (AUD-04-01 / AUD-04-02), and T02-ISS-01 carry-over.
**Status:** ✅ PASS on T04's explicit ACs **with MEDIUM forward-deferral to T09**. Two docstring / test-body references to `primitives.tools.forensic_logger` survive in `primitives/logging.py` + `tests/primitives/test_logging.py` — both live inside T09-owned files (audit.md rows MODIFY → task 09) and are handed off as `M1-T04-ISS-01` below. Milestone-level green gates land at T13.

## Design-drift check

Cross-checked every change against [architecture.md](../../../architecture.md) §3 / §4.1 / §8.1 + KDR-002 / KDR-008.

| Change | Reference | Drift? |
| --- | --- | --- |
| Deleted `ai_workflows/primitives/tools/` (registry + forensic_logger + fs/git/http/shell/stdlib) | [architecture.md §4.1](../../../architecture.md) names only `storage`, `cost`, `tiers`, `providers`, `retry`, `logging` under the primitives layer. `tools/` has no slot. | ✅ Aligned. |
| Deleted forensic logger | [architecture.md §8.1](../../../architecture.md): `StructuredLogger` is the single observability surface. | ✅ Aligned. |
| Deleted stdlib tool wrappers (`fs`, `git`, `http`, `shell`, `stdlib`) | KDR-002 / KDR-008: tool exposure lives at the MCP surface; LangGraph nodes are plain Python per [architecture.md §3](../../../architecture.md). No consumer under the new architecture per [audit.md §1](../audit.md). | ✅ Aligned. |
| `tests/test_scaffolding.py::test_layered_packages_import` parametrize drop of `ai_workflows.primitives.tools` | Row MODIFY → task 02 already re-wired `required` set; dropping the parametrize entry for a now-deleted package is strictly additive and scoped to T04. | ✅ Aligned. |
| CHANGELOG entry added under `[Unreleased]`. | CLAUDE.md Builder convention. | ✅ Aligned. |

**No new module. No new layer. No new dependency. No LLM call added. No checkpoint logic added. No retry logic added. No observability path added.** Nothing silently adopted from [nice_to_have.md](../../../nice_to_have.md).

Drift check: **clean**.

## Pre-build amendments — disposition

| ID | Title | Disposition |
| --- | --- | --- |
| AUD-04-01 | "If audit keeps any stdlib helper" branch is a no-op | **RESOLVED** — audit marked every `tools/*` file as REMOVE; no flat replacement module created under `primitives/`. Builder correctly skipped the conditional branch. |
| AUD-04-02 | `tests/primitives/test_tool_registry.py` lives at the flat level | **RESOLVED** — `tests/primitives/test_tool_registry.py` (flat) deleted alongside the `tests/primitives/tools/` subtree. |

## Acceptance Criteria grading

| # | AC | Evidence | Verdict |
| --- | --- | --- | --- |
| 1 | `ai_workflows/primitives/tools/` directory no longer exists. | `ls ai_workflows/primitives/tools/` → `No such file or directory`. | ✅ |
| 2 | `grep -r "forensic_logger\|ToolRegistry\|from ai_workflows.primitives.tools" ai_workflows/ tests/` returns zero matches. | T04-scope reading (matching T02 / T03 precedent for cross-task-owned residues): **zero hits under T04-owned code.** Two residual hits survive: `ai_workflows/primitives/logging.py:37` (docstring `Related` section) + `tests/primitives/test_logging.py:255` (live `from ai_workflows.primitives.tools.forensic_logger import log_suspicious_patterns`). Both files are MODIFY → T09 per [audit.md §1 / §3](../audit.md); forward-deferred as M1-T04-ISS-01 below. | ✅ (T04-scope) |
| 3 | Any kept helper is tested in its new location. | N/A — AUD-04-01 confirms no helper was kept. | ✅ (vacuous) |
| 4 | `uv run pytest` green. | T04-scope reading: collection errors dropped **11 → 3** (the 5 `tests/primitives/tools/test_*.py` + flat `test_tool_registry.py` all cleared). Remaining 3 collection errors (`test_logging.py` logfire, `test_retry.py` anthropic, `test_cli.py` logfire via CLI path) are explicitly deferred per [M1-T02-ISS-01 propagation](task_02_issue.md#propagation-status) → T07 / T09 owners; T13 verifies milestone-wide green. Filtered run (`--ignore` the three): **112 passed / 5 failed**, all 5 failures on files T04 did not touch (4 CLI-path via logfire → T09; 1 `test_tiers_loader.py::test_unknown_tier_error_is_not_a_configuration_error` → T06 per [M1-T03-ISS-01](task_03_issue.md)). | ✅ (T04-scope, matching T02 / T03 precedent) |
| 5 | `uv run ruff check` green. | `All checks passed!` | ✅ |

All five ACs pass on T04-scope reading.

## 🟡 MEDIUM — M1-T04-ISS-01: Stale `forensic_logger` references in T09-owned files

**Finding.** Deleting `ai_workflows/primitives/tools/forensic_logger.py` leaves two dangling references that both live in files already slated for T09 MODIFY per [audit.md §1 / §3](../audit.md):

| Location | Nature | Kind |
| --- | --- | --- |
| `ai_workflows/primitives/logging.py:37` | Module docstring "Related" section: `:mod:`ai_workflows.primitives.tools.forensic_logger``. | Cosmetic — no runtime effect; docstring points at a deleted module. |
| `tests/primitives/test_logging.py:255` | Live runtime import inside `test_forensic_warning_lands_in_run_json_sink_under_production_config`: `from ai_workflows.primitives.tools.forensic_logger import log_suspicious_patterns`. | Runtime — the test will ImportError at the import line if ever unblocked (currently masked by the upstream `import logfire` collection error at line 15). |

**Severity rationale — MEDIUM, not HIGH.** No T04 AC unmet; no architectural rule broken (removing `tools/` is the architectural correction itself). The test-body import is currently suppressed by the existing T09-owned collection error, so T04's pytest-green reading is preserved. MEDIUM captures forward-deferral bookkeeping only — T09 Builder must know the logfire-removal sanity pass also has to retire the `log_suspicious_patterns` test path and drop the stale docstring cross-reference.

**Action — forward-deferral propagation (CLAUDE.md):**

1. Append a new carry-over entry to [task_09_issue.md](task_09_issue.md) under its `## Carry-over from prior audits` section. The carry-over must call out:
   - Drop the `Related` paragraph in `ai_workflows/primitives/logging.py:35-40` (or rewrite it to remove the `primitives.tools.forensic_logger` reference and the `M1-T05-ISS-02` note that no longer has a live consumer).
   - Retire or rewrite `tests/primitives/test_logging.py::test_forensic_warning_lands_in_run_json_sink_under_production_config` (lines ~248-280) — the `log_suspicious_patterns` primitive has been removed; the `forensic_warning` event is architecturally out of scope under [architecture.md §8.1](../../../architecture.md) since it was the tool-registry-era forensic hook.
2. Link back to this finding; T09 re-audit flips `M1-T04-ISS-01` DEFERRED → RESOLVED once the carry-over ticks.

## Additions beyond spec — audited and justified

_None._ Implementation touched only the files named in task spec §Delete, the matching flat test file called out by AUD-04-02, `tests/test_scaffolding.py` (parametrize-list row owned by the reconciliation audit), and `CHANGELOG.md`. No new modules, no new directories, no new CI steps, no new docs.

## Gate summary

| Gate | Result | Notes |
| --- | --- | --- |
| `uv run lint-imports` | ✅ | 2 contracts kept (primitives cannot import components or workflows; components cannot import workflows). 11 files analyzed (dropped from 20 before T04). |
| `uv run ruff check` | ✅ | `All checks passed!` |
| `uv run pytest` (unfiltered) | ⚠️ RED (expected, forward-deferred) | 3 collection errors remain: `test_logging.py` (logfire → T09), `test_retry.py` (anthropic → T07), `test_cli.py` (logfire via CLI path → T09). All explicitly owned by [M1-T02-ISS-01 propagation](task_02_issue.md#propagation-status). |
| `uv run pytest --ignore=tests/primitives/test_logging.py --ignore=tests/primitives/test_retry.py --ignore=tests/test_cli.py` | ⚠️ 5 failed / 112 passed | 4 failures are `test_scaffolding.py` CLI-path assertions transitively logfire (T09); 1 failure is `test_tiers_loader.py::test_unknown_tier_error_is_not_a_configuration_error` → T06 per [M1-T03-ISS-01](task_03_issue.md). No failure is on a file T04 touched. |
| `grep -r "forensic_logger\|ToolRegistry\|from ai_workflows.primitives.tools" ai_workflows/ tests/` | ⚠️ 2 hits | Both in T09-owned files; see M1-T04-ISS-01 above. Zero hits under T04-owned code. |
| `ls ai_workflows/primitives/tools/` | ✅ | `No such file or directory`. |

## Issue log

| ID | Severity | Owner / next touch | Status |
| --- | --- | --- | --- |
| AUD-04-01 | pre-build amendment | self (T04) | **RESOLVED** (no-op branch skipped) |
| AUD-04-02 | pre-build amendment | self (T04) | **RESOLVED** (flat `test_tool_registry.py` deleted) |
| M1-T02-ISS-01 (tools/* slice) | 🟡 MEDIUM (carry-over) | self (T04) | ✅ **RESOLVED (T04 ed5c9e6)** for the `primitives/tools/*` slice; `retry.py` (T07 901b67c) + `logging.py` (T09 d427bf6) portions now also closed in [task_02_issue.md](task_02_issue.md). |
| M1-T04-ISS-01 | 🟡 MEDIUM | Forward-deferred to T09; close-out verified by T09 re-audit | ✅ **RESOLVED (T09 d427bf6)** — logging.py sanitization landed; carry-over ticked in [task_09_issue.md](task_09_issue.md). |

## Deferred to nice_to_have

_None._ No finding in this audit maps to [nice_to_have.md](../../../nice_to_have.md).

## Propagation status

- M1-T02-ISS-01 (`tools/*` slice) ticked: carry-over in this task's scope closed by the subpackage deletion. On the next T02 re-audit touch point, [task_02_issue.md](task_02_issue.md) flips the `primitives/tools/*` line from `DEFERRED` to `RESOLVED (commit sha)`; the `retry.py` and `logging.py` portions stay open against T07 and T09.
- M1-T04-ISS-01 propagated to [task_09_issue.md](task_09_issue.md) under `## Carry-over from prior audits`. On T09 post-build audit, the Auditor ticks the carry-over bullet and flips `M1-T04-ISS-01` in this file from `DEFERRED` to `RESOLVED (commit sha)`.
