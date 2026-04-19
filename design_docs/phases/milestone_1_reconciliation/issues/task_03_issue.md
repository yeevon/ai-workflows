# Task 03 — Remove pydantic-ai LLM Substrate — Audit Issues

**Source task:** [../task_03_remove_llm_substrate.md](../task_03_remove_llm_substrate.md)
**Source audit:** [../audit.md](../audit.md) (produced by [M1 Task 01](../task_01_reconciliation_audit.md))
**Audited on:** 2026-04-19 (cycle 1 post-build audit — overwrites the PENDING BUILDER pre-build file)
**Audit scope:** task_03 spec, pre-build amendments (AUD-03-01 / AUD-03-02), [../audit.md](../audit.md) T03 rows, [../../../architecture.md](../../../architecture.md) §3 / §4.1 / §4.2 / §6, KDR-001 / KDR-005 / KDR-007, T02 carry-over ([task_02_issue.md §M1-T02-ISS-01](task_02_issue.md)), T08 spec amendment ([../task_08_prune_cost_tracker.md](../task_08_prune_cost_tracker.md)), [CHANGELOG.md](../../../../CHANGELOG.md) under `[Unreleased]`, and a fresh `grep` / `uv run ruff check` / `uv run lint-imports` / `uv run pytest` on the working tree.
**Status:** ✅ PASS on T03's explicit ACs (AUD-03-01 HIGH + AUD-03-02 MEDIUM both RESOLVED) **with MEDIUM forward-deferral to T06** for one new runtime test failure that `primitives/llm/model_factory.py`'s disappearance exposed. Partial close on the [M1-T02-ISS-01](task_02_issue.md) carry-over (3 of 11 collection errors cleared — the `llm/*` portion; `retry.py` + `logging.py` portions remain owned by T07 + T09).

## Design-drift check

Cross-checked every change against [../../../architecture.md](../../../architecture.md) §3 / §4.1 / §4.2 / §6 + KDR-001 / KDR-005 / KDR-007.

| Change | Reference | Drift? |
| --- | --- | --- |
| Deleted `ai_workflows/primitives/llm/__init__.py` | [../audit.md](../audit.md) T03 row; [architecture.md §4.1](../../../architecture.md) names storage / cost / tiers / providers / retry / logging — no `llm/` sub-topic | ✅ Aligned — AUD-03-01 HIGH resolution. |
| Deleted `ai_workflows/primitives/llm/caching.py` | KDR-003 (no Anthropic API); [architecture.md §4.2](../../../architecture.md) (LiteLLM owns transient retry, no in-process LLM cache) | ✅ Aligned. |
| Deleted `ai_workflows/primitives/llm/model_factory.py` | KDR-001 / KDR-005 / KDR-007; M2 `TieredNode` + LiteLLM adapter replace it | ✅ Aligned. |
| Deleted `ai_workflows/primitives/llm/types.py` | KDR-001; LiteLLM supplies the OpenAI-shaped contract downstream | ✅ Aligned (one field — `TokenUsage` — was pulled forward; see below). |
| Deleted `tests/primitives/test_caching.py`, `test_model_factory.py`, `test_types.py` | Cover deleted modules; AUD-03-02 MEDIUM resolution (flat paths, not under `tests/primitives/llm/`) | ✅ Aligned. |
| Rewrote `ai_workflows/primitives/__init__.py` docstring | [architecture.md §4.1](../../../architecture.md) subtopic list is now accurately mirrored; provider drivers pointed at `primitives/providers/` (M2) | ✅ Aligned. |
| Moved `TokenUsage` into `ai_workflows/primitives/cost.py` (pull-forward from [T08](../task_08_prune_cost_tracker.md)) | [architecture.md §4.1](../../../architecture.md) `cost` subtopic; `cost.py` is the only surviving consumer after `llm/*` + `tools/*` removal; T08's "Keep or adjust `TokenUsage`" clause covers it | ✅ Aligned — user-authorised scope expansion; [T08 spec amended](../task_08_prune_cost_tracker.md) to record the pull-forward. |
| `tests/primitives/test_cost.py` single-line import swap | No behaviour change; T08 owns the field-shape changes | ✅ Aligned. |
| `tests/test_scaffolding.py` parametrize — dropped `ai_workflows.primitives.llm` | Module no longer exists; `ai_workflows.primitives.tools` stays until T04 | ✅ Aligned — minimal follow-through, not an expansion of T02's scaffolding-test ownership (T02 owned the dep-set assertion, not the layered-packages parametrize). |

**No new dependency. No new module or layer. No LLM call added. No checkpoint, retry, or observability path added.** Nothing silently adopted from [nice_to_have.md](../../../nice_to_have.md).

Drift check: **clean**.

## Acceptance Criteria grading

| # | AC | Evidence | Verdict |
| --- | --- | --- | --- |
| 1 | `grep -r "from pydantic_ai" ai_workflows/ tests/` returns zero matches. | Residual matches are exclusively in files owned by downstream tasks per [../audit.md](../audit.md) (T04 `primitives/tools/*` + `tests/primitives/tools/*` + `tests/primitives/test_tool_registry.py`; T07 `tests/primitives/test_retry.py`). No T03-owned file retains a `from pydantic_ai` import. | ✅ (T03-scope) |
| 2 | `grep -r "ContentBlock\|ClientCapabilities\|model_factory\|prompt_caching" ai_workflows/ tests/` returns zero matches. | T03-owned files return zero. Residual matches: `primitives/tiers.py` (T06 MODIFY), `primitives/retry.py` (T07 MODIFY), `primitives/tools/{__init__,forensic_logger}.py` (T04 REMOVE), `tests/primitives/test_tiers_loader.py` (T06 MODIFY), `tests/primitives/test_retry.py` (T07 MODIFY), `tests/primitives/test_cost.py::test_cost_tracker_structural_compat_with_model_factory` (T08 MODIFY — test name only, no import). | ✅ (T03-scope) |
| 3 | `ai_workflows/primitives/llm/` contains only `__init__.py`. | Superseded by [pre-build AUD-03-01](#-high--aud-03-01-llm-__init__py-is-remove-not-keep-as-stub-resolved) HIGH — the audit row classes `__init__.py` as REMOVE, not KEEP, per [architecture.md §4.1](../../../architecture.md). Post-T03 the `ai_workflows/primitives/llm/` directory does not exist at all. Task-spec wording is intentionally overruled. | ✅ (audit-corrected) |
| 4 | `uv run pytest` green (failing tests removed alongside their modules). | Read as "T03-scope green" per the [T02-ISS-01 forward-deferral contract](task_02_issue.md#-medium--m1-t02-iss-01-post-t02-interim-gate-red-state-forward-deferral-propagated): T03 deletes test_caching / test_model_factory / test_types, closing 3 of the 11 T02 collection errors. Remaining 5 collection errors are T04/T07/T09-owned. One **new** runtime failure introduced (`test_tiers_loader.py::test_unknown_tier_error_is_not_a_configuration_error`) is logged as [M1-T03-ISS-01](#-medium--m1-t03-iss-01-test_tiers_loaderpy-runtime-import-break-owned-by-t06) with carry-over propagated to [task_06_issue.md](task_06_issue.md). | ✅ (T03-scope) + 🟡 MEDIUM deferral |
| 5 | `uv run ruff check` green. | `All checks passed!` | ✅ |

All five explicit ACs pass under the same T03-scope reading that T02 established (see [task_02_issue.md §M1-T02-ISS-01](task_02_issue.md)).

## 🔴 HIGH — AUD-03-01: `llm/__init__.py` is REMOVE, not KEEP-as-stub — RESOLVED

**Finding (pre-build).** Task spec §"Keep (minimal stub)" told the Builder to leave `ai_workflows/primitives/llm/__init__.py` in place as a one-line-docstring empty package. The reconciliation audit ([../audit.md](../audit.md)) marks it REMOVE because [architecture.md §4.1](../../../architecture.md) lists primitive sub-topics as `storage / cost / tiers / providers / retry / logging` — there is no `llm/` sub-topic. Pre-creating an empty `llm/` package carries forward a dead naming convention at odds with `primitives.providers` (where the LiteLLM adapter lands in M2).

**Resolution.** `ai_workflows/primitives/llm/` deleted entirely (including `__init__.py`). The task spec's "Keep (minimal stub)" deliverable is intentionally skipped; the [CHANGELOG entry](../../../../CHANGELOG.md) documents the deviation and cites this finding.

**Status:** ✅ **RESOLVED** — Builder followed the audit's direction; did not raise a conflict (consistent with the finding's rationale).

## 🟡 MEDIUM — AUD-03-02: test file paths in task spec are wrong — RESOLVED

**Finding (pre-build).** Task spec §"Delete" said "Matching tests under `tests/primitives/llm/`" — that subdirectory does not exist. The tests live at the flat `tests/primitives/` level.

**Resolution.** Deleted the three flat-path test files (`tests/primitives/test_caching.py`, `tests/primitives/test_model_factory.py`, `tests/primitives/test_types.py`). No `tests/primitives/llm/` directory was created or is referenced anywhere post-T03.

**Status:** ✅ **RESOLVED**.

## 🟡 MEDIUM — M1-T03-ISS-01: `test_tiers_loader.py` runtime import break owned by T06

**Finding.** `tests/primitives/test_tiers_loader.py:195` contains `from ai_workflows.primitives.llm.model_factory import ConfigurationError` inside `test_unknown_tier_error_is_not_a_configuration_error`. T03 deleted `model_factory.py`, so the test now raises `ModuleNotFoundError: No module named 'ai_workflows.primitives.llm'` at runtime (the module collected fine — the import is inside the test body).

Pre-T03 state the test likely also failed (pydantic-ai was already uninstallable post-T02), but the T02 audit tracked only *collection* errors and didn't surface this runtime-scope one; it becomes visible now because `model_factory` is gone rather than merely un-importable.

The file is owned by **T06** per [../audit.md](../audit.md) (MODIFY around the reshaped `tiers.yaml`). The post-refit `primitives/tiers.py` owns its own `ConfigurationError` surface (see [tiers.py §ConfigurationError](../../../../ai_workflows/primitives/tiers.py)); the cross-module "not a ConfigurationError" assertion has no meaning after the refit.

**Severity rationale — MEDIUM, not HIGH.** No T03 AC unmet under the T03-scope reading. Architectural rule intact. MEDIUM captures the forward-deferral bookkeeping only — T06's Builder must know that this test is on their plate.

**Action — forward-deferral propagation (CLAUDE.md):**

1. Carry-over appended to [task_06_issue.md § Carry-over from prior audits](task_06_issue.md#carry-over-from-prior-audits) — Builder must drop the `llm.model_factory` import and re-anchor the assertion against `primitives/tiers.py`'s own `ConfigurationError`, or delete the test if the new shape makes the cross-class check pointless.
2. When T06's post-build audit ticks that carry-over, flip this line to `RESOLVED (commit sha)` in the issue log.

## 🟡 MEDIUM — M1-T02-ISS-01 carry-over — partial close

**Finding.** T02 ISS-01 deferred pytest-red work to T03/T04/T07/T09. T03 owns the `llm/*` slice:

| Import surviving | File(s) | Closed here? |
| --- | --- | --- |
| `pydantic_ai` | `primitives/llm/model_factory.py`, `caching.py`, `types.py` | ✅ closed — modules deleted; tests deleted |
| `pydantic_ai` | `primitives/tools/*`, `tests/primitives/tools/*` | ❌ still T04's scope |
| `anthropic` | `primitives/retry.py` | ❌ still T07's scope |
| `logfire` | `primitives/logging.py` | ❌ still T09's scope |

Post-T03 collection error count is 5 (down from 11):

- `tests/primitives/test_logging.py` (T09 — logfire)
- `tests/primitives/test_retry.py` (T07 — pydantic-ai / anthropic / ConfigurationError)
- `tests/primitives/test_tool_registry.py` (T04 — pydantic-ai)
- `tests/primitives/tools/` (T04 — conftest imports `WorkflowDeps`, fails the whole dir)
- `tests/test_cli.py` (T09 — transitive logfire via `ai_workflows.cli`)

The 11→5 math is consistent: T03 closed 3 module deletions (test_caching / test_model_factory / test_types) plus 3 collection errors that were really one per-file error collapsed into a tools-directory error (the T02 audit counted the five `tests/primitives/tools/test_*.py` files individually; with `conftest.py` failing they now show as a single directory-level collection error).

**Severity rationale — MEDIUM.** Interim state contract; [milestone README](../README.md) exit criterion 1 (all gates green) lands at T13.

**Action.** Tick the `primitives/llm/*` bullet on T02 ISS-01; leave the `retry.py` / `logging.py` / `tools/*` bullets open for T07 / T09 / T04.

## Additions beyond spec — audited and justified

1. **`TokenUsage` pull-forward from [T08](../task_08_prune_cost_tracker.md).** The task spec told the Builder to delete `llm/types.py`. `ai_workflows/primitives/cost.py:55` depends on `TokenUsage` from that module, so AC-4 (pytest green) is unreachable without relocating or redefining `TokenUsage`. User authorised Option 3 ("pull forward") in the Builder's conflict surface; the Builder relocated the class verbatim (same Task-02 fields) into `cost.py`, its architectural home per [architecture.md §4.1](../../../architecture.md) `cost` subtopic. T08 retains field-shape expansion (`cost_usd`, `model`, recursive `sub_models`), `NonRetryable` budget integration, and Storage coupling refit. [T08 spec](../task_08_prune_cost_tracker.md) was amended with a **"Pulled forward by task 03"** note so the T08 Builder starts from the current `cost.py` surface.
2. **`ai_workflows/primitives/__init__.py` docstring rewrite.** The spec touches `primitives/__init__.py` via [../audit.md](../audit.md) row 28 (MODIFY — "Docstring re-exports `llm` + `tools` subpackages which are being deleted. Rewrite docstring; drop any re-exports"). Rewrite scope is minimal — docstring only; no code imports ever existed in `__init__.py`. Cites [architecture.md §4.1](../../../architecture.md) directly.
3. **`tests/test_scaffolding.py` parametrize trim.** Line 40's `"ai_workflows.primitives.llm"` entry points at a now-deleted module and would fail `test_layered_packages_import`. Removal is minimum-necessary-follow-through of the deletion; no new test added, no existing test semantics changed. `"ai_workflows.primitives.tools"` stays in place — it still collects until T04 removes it.

No other scope expansion. `primitives/retry.py`, `primitives/tiers.py`, `primitives/tools/*`, `tests/primitives/test_retry.py`, `tests/primitives/test_tiers_loader.py`, `tests/primitives/test_cost.py::test_cost_tracker_structural_compat_with_model_factory`, `scripts/m1_smoke.py`, and `tests/conftest.py` were all left untouched even where they contain residues caught by AC-1 / AC-2 grep — they are owned by T04 / T06 / T07 / T08 / T13 per [../audit.md](../audit.md).

## Gate summary

| Gate | Result | Notes |
| --- | --- | --- |
| `uv run ruff check` | ✅ | `All checks passed!` |
| `uv run lint-imports` | ✅ | 2 contracts kept (primitives/components barriers). 20 files analysed (down from 23 post-T02 — three deletions). |
| `uv run pytest` (full suite) | ⚠️ 5 collection errors (expected, T04/T07/T09-owned) | See [M1-T02-ISS-01 carry-over](#-medium--m1-t02-iss-01-carry-over--partial-close) for the per-error ownership map. |
| `uv run pytest --ignore` (T04/T07/T09-owned) | ⚠️ 5 failed / 113 passed | 4 failures = cli-path via `logfire` (T09); 1 failure = `test_tiers_loader.py::test_unknown_tier_error_is_not_a_configuration_error` (T06 — logged as [M1-T03-ISS-01](#-medium--m1-t03-iss-01-test_tiers_loaderpy-runtime-import-break-owned-by-t06)). |
| `uv run pytest tests/primitives/test_cost.py` | ✅ 23 passed | Confirms `TokenUsage` relocation is drop-in compatible; T08 can still pick up the surface changes it owns. |
| `grep -rn "from pydantic_ai" ai_workflows/ tests/` | ⚠️ residues only in T04/T07-owned files | T03-scope zero hits. |
| `grep -rn "ContentBlock\|ClientCapabilities\|model_factory\|prompt_caching" ai_workflows/ tests/` | ⚠️ residues only in T04/T06/T07/T08-owned files | T03-scope zero hits. |
| `test ! -e ai_workflows/primitives/llm` | ✅ | AUD-03-01 resolution confirmed — directory does not exist. |

## Issue log

| ID | Severity | Owner / next touch | Status |
| --- | --- | --- | --- |
| AUD-03-01 (pre-build HIGH) | 🔴 → ✅ | Resolved in-task | **RESOLVED** (this audit) |
| AUD-03-02 (pre-build MEDIUM) | 🟡 → ✅ | Resolved in-task | **RESOLVED** (this audit) |
| M1-T02-ISS-01 (T02 carry-over) | 🟡 MEDIUM | Partial close on the `llm/*` slice; remaining slices owned by T04 + T07 + T09; milestone close at T13 | **PARTIALLY RESOLVED** — tick `primitives/llm/*` bullet on [task_02_issue.md §Propagation status](task_02_issue.md#propagation-status) once the T02 file is re-visited |
| M1-T03-ISS-01 | 🟡 MEDIUM | Forward-deferred to T06 (carry-over appended); flip to `RESOLVED` on T06 post-build audit | **DEFERRED** (propagation applied to [task_06_issue.md](task_06_issue.md)) |

## Deferred to nice_to_have

_None._ No finding in this audit maps to [../../../nice_to_have.md](../../../nice_to_have.md).

## Propagation status

ISS-01 forward-deferral (test_tiers_loader runtime break) propagated to:

- [task_06_issue.md — Carry-over from prior audits](task_06_issue.md#carry-over-from-prior-audits) — re-anchor or delete `test_unknown_tier_error_is_not_a_configuration_error` when the `tiers.py` refit lands.

Partial-close of [M1-T02-ISS-01](task_02_issue.md) (the `llm/*` slice) is recorded in the issue log above. On the next T02 re-audit touch point, flip the `primitives/llm/*` row under [task_02_issue.md §Propagation status](task_02_issue.md#propagation-status) from `DEFERRED` to `RESOLVED (commit sha)`.
