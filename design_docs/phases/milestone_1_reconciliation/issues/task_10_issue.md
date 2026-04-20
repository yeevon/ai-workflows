# Task 10 — `workflow_hash` Decision + ADR — Audit Issues

**Source task:** [../task_10_workflow_hash_decision.md](../task_10_workflow_hash_decision.md)
**Audited on:** 2026-04-19 (post-build, Cycle 1)
**Audit scope:** [ADR-0001](../../../adr/0001_workflow_hash.md), `ai_workflows/primitives/workflow_hash.py` (deleted), `tests/primitives/test_workflow_hash.py` (deleted), `ai_workflows/primitives/__init__.py`, `ai_workflows/workflows/__init__.py`, `ai_workflows/cli.py`, `tests/test_cli.py`, `tests/test_scaffolding.py`, `CHANGELOG.md`, full-suite downstream impact on residual T11 cascade.
**Status:** ✅ PASS on all applicable ACs (AC-3 is N/A under Option B). One 🟢 LOW finding — dead-script stale import — forward-deferred to T13 (`scripts/m1_smoke.py`), which already owns the surrounding script-cleanup decision.

## Design-drift check (mandatory; architecture.md + KDRs re-read)

| Concern | Verdict | Evidence |
| --- | --- | --- |
| New dependency in `pyproject.toml` | ✅ None added | `pyproject.toml` unchanged |
| Four-layer contract | ✅ Kept | `uv run lint-imports` → 2 kept, 0 broken |
| LLM call added (KDR-004) | ✅ N/A | T10 is retirement, no new node or call site |
| `anthropic` SDK / `ANTHROPIC_API_KEY` (KDR-003) | ✅ Absent | `grep -rn 'anthropic' ai_workflows/cli.py ai_workflows/primitives/__init__.py ai_workflows/workflows/__init__.py design_docs/adr/0001_workflow_hash.md` → 0 hits |
| Checkpoint / resume logic (KDR-009) | ✅ Honoured | ADR-0001 explicitly defers resume-safety drift-detect design to M3; acknowledges the genuine source-code drift gap that `SqliteSaver`'s `thread_id`-keyed checkpoints do not close; does not fill the gap with a hand-rolled primitive |
| Retry logic (KDR-006) | ✅ N/A | No retry path touched |
| Observability (StructuredLogger only) | ✅ N/A | No observability surface touched |
| `nice_to_have.md` adoption check | ✅ None | `grep -n 'langfuse\|langsmith\|instructor\|opentelemetry\|deepagents\|mkdocs\|docker-compose' design_docs/adr/0001_workflow_hash.md ai_workflows/ tests/test_scaffolding.py` → 0 new hits |
| KDR-005 "primitives layer preserved and owned" | ✅ Honoured | "Owned" means reshaped when the pre-pivot shape no longer fits — ADR-0001 argues this explicitly and cites [architecture.md §4.3](../../../architecture.md) as evidence that the directory-based hash does not match the module-based workflow model |
| Task spec's `ADR references` list (Context / Decision / Consequences / References, with KDR-009 cited) | ✅ All present | See [../../../adr/0001_workflow_hash.md](../../../adr/0001_workflow_hash.md) — all four sections; KDR-009 cited in body and References; §4.1, §4.3, KDR-005 also cited |

No design drift. Proceeding to AC grading.

## AC grading (task file)

| # | AC | Verdict | Evidence |
| --- | --- | --- | --- |
| AC-1 | ADR exists and states the outcome unambiguously | ✅ | `design_docs/adr/0001_workflow_hash.md` present. Header: `Status: Accepted (2026-04-19)`. `## Decision` section names `Option B — Remove` on its first line. Four required sections present (`Context`, `Decision`, `Consequences`, `References`); `Rationale` added as an extension (not required by spec but helps future readers). Task spec's "References (KDR-009, architecture §4.1, this task)" all appear. Pinned by `test_workflow_hash_module_is_retired_per_adr_0001` (checks for `"Accepted"`, `"Option B"`, `"KDR-009"` substrings). |
| AC-2 | Option B: `ai_workflows/primitives/workflow_hash.py` and its test file are deleted, and the module is removed from any `__init__.py` re-exports | ✅ | `ls ai_workflows/primitives/workflow_hash.py tests/primitives/test_workflow_hash.py` → both absent. `ai_workflows/primitives/__init__.py` has no `from` / `import` lines at all (docstring-only module); the docstring enumeration of primitives no longer names `workflow_hash` and instead cites ADR-0001. `ai_workflows/workflows/__init__.py` docstring rewritten to drop the "content hash of a workflow directory" reference and cites ADR-0001. `grep -rn 'compute_workflow_hash\|from ai_workflows.primitives.workflow_hash' ai_workflows/` → 0 hits. Pinned by `test_workflow_hash_module_is_retired_per_adr_0001` (three file-existence + one live-import-raises assertions). |
| AC-3 | Option A: a one-line docstring links to the ADR; no behaviour change | N/A | Option B chosen. AC-3 does not apply. |
| AC-4 | `uv run pytest` green | 🟡 T-scope | `tests/test_scaffolding.py` + `tests/primitives/` → 139 passed. Full suite → 142 passed / 1 failed / 10 errors. All 11 residuals are `tests/test_cli.py` `SQLiteStorage.create_run() got an unexpected keyword argument 'workflow_dir_hash'` — pre-existing T11 cascade from T05's column removal. T10 *reduced* residuals by 2 (deleted the two workflow-hash-specific tests that were failing for both reasons). Net suite improvement. T09 audit logged this same cascade under the same T-scope reading; T10 does not regress it. |

## 🔴 HIGH

_None._

## 🟡 MEDIUM

_None._

## 🟢 LOW

### 🟡 DEFERRED → T13 — M1-T10-ISS-01: `scripts/m1_smoke.py` imports the retired `compute_workflow_hash` — OWNED BY T13

**Finding.** `scripts/m1_smoke.py:36` still contains `from ai_workflows.primitives.workflow_hash import compute_workflow_hash` and `:62` still calls `workflow_dir_hash = compute_workflow_hash(Path.cwd())`. T10 deleted the target module.

**Why this is LOW, not MEDIUM.** The file was already broken post-T03 (imports `pydantic_ai`, `llm.model_factory`, `llm.types.WorkflowDeps`), post-T06 (imports the removed `load_tiers`), post-T07 (imports `BudgetExceeded` which is now `NonRetryable("budget exceeded")`), and post-T08 (pricing is enriched by LiteLLM, not by `CostTracker`). T10 adds one more stale import to a file that is **already fully unexecutable**. No gate is regressed — `grep m1_smoke scripts/`-like smoke runs are not pytest-gated (the docstring at line 17 reads "Not wired into pytest — this is a manual validation step"). M1-T06-ISS-04 has already forward-deferred the whole-file decision (rewrite vs. delete) to T13's milestone close-out; T10's new stale import folds into that same decision.

**Action / Recommendation.** Forward-defer to [task_13_issue.md](task_13_issue.md) as a companion to M1-T06-ISS-04. The T13 Builder's "rewrite or delete" decision for `scripts/m1_smoke.py` must remove the `compute_workflow_hash` usage regardless of branch:

- If T13 **rewrites** the script against the post-pivot substrate (LiteLLM + `TierRegistry.load`, no `pydantic_ai`, no `WorkflowDeps`, no `BudgetExceeded`), there is no `compute_workflow_hash` replacement — M3 owns the drift-detect design per ADR-0001, and the smoke script should not pre-empt it.
- If T13 **deletes** the script, the issue resolves by deletion.

No T10 re-work is warranted; touching `scripts/m1_smoke.py` to remove one stale import among five would be drive-by scope expansion into a file that T13 owns the fate of.

## Additions beyond spec — audited and justified

1. **`tests/test_scaffolding.py::test_workflow_hash_module_is_retired_per_adr_0001`.** Spec ACs do not require a pin test. Added because (a) AC-2's "module + test deleted" is observable only by file-absence, and a failing `ls` in the audit shell is not a regression guard; (b) accidentally restoring `workflow_hash.py` in a later task would be silently load-bearing; (c) the ADR itself is a design artefact that should be wired to a live assertion. The test checks three artefacts at once (module absent, test absent, ADR present with `"Accepted"` + `"Option B"` + `"KDR-009"` substrings) and pins an active `ModuleNotFoundError` on import. Minimum viable pin, no duplicate coverage.

2. **`ai_workflows/cli.py` edits beyond spec's Option B file list.** Spec Option B AC lists the primitive, its test, and `__init__.py` re-exports. Issue file pre-build amendment added "Remove any `from ai_workflows.primitives.workflow_hash import …` import in `ai_workflows/cli.py`" as a verification step. T11 has **not** yet stub-down cli.py (its issue file still reads `📋 PENDING BUILDER`), so the import was still live pre-T10. Without the edit, deleting `workflow_hash.py` would have broken `ai_workflows/cli.py` at import time → broken `tests/test_scaffolding.py::test_aiw_help_runs` and `test_aiw_version_command` (both import cli.py) → broken M1 scaffolding (T01 territory). The edit is a **minimum incision**: the one import, its two call sites (`_render_dir_hash_line` helper body + `_render_inspect` usage), the `--workflow-dir` option on `inspect`, the "Dir hash" line in `_render_inspect` output, and the `Workflow hash: stored ...` line in the `resume` stub. No other CLI surface touched — the broader stub-down to `--help` + `version` remains T11's scope.

3. **`tests/test_cli.py` edits beyond spec.** Same rationale as (2): `from ai_workflows.primitives.workflow_hash import compute_workflow_hash` at line 21 would break collection under Option B. Edit is the one-line import deletion + removal of two test functions (`test_inspect_flags_mismatch_when_directory_changed` and `test_inspect_dir_hash_without_workflow_dir`) which were the only `compute_workflow_hash` / `--workflow-dir` / `"Dir hash"` callers. Both tests were already failing under the T11-owned `workflow_dir_hash=...` kwarg drift; removing them narrows the residual failure set. The remaining tests (that fail on `workflow_dir_hash` kwarg drift alone) are left intact — T11 will reduce `tests/test_cli.py` to `aiw --help` + `aiw version` assertions per its spec.

4. **ADR `Rationale` section (beyond Context / Decision / Consequences / References).** Spec names only four sections; the ADR adds a `Rationale` block. `Rationale` is a standard ADR extension (see e.g. MADR template) and is where the four rationale bullets (directory hashing doesn't fit module-based workflows; the real gap belongs to M3; zero current consumer; deferring is cheap to reverse) land. Each bullet is one-sentence and load-bearing for the decision; moving them into `Consequences` would have conflated *why* with *what-happens-now*. No AC impact; additive.

## Gate summary

| Gate | Result | Notes |
| --- | --- | --- |
| `uv run ruff check` | ✅ | "All checks passed!" |
| `uv run lint-imports` | ✅ | 2 contracts kept, 0 broken |
| `uv run pytest tests/test_scaffolding.py tests/primitives/` | ✅ | 139 passed in 2.34s |
| `uv run pytest` (full suite) | 🟡 T-scope | 142 passed / 1 failed / 10 errors. 11 residuals = `tests/test_cli.py` `SQLiteStorage.create_run(workflow_dir_hash=...)` kwarg drift (T11 territory, pre-existing). T10 *reduced* residuals by 2 vs. T09 baseline. Net suite improvement |
| `ls ai_workflows/primitives/workflow_hash.py tests/primitives/test_workflow_hash.py` | ✅ | Both absent |
| `ls design_docs/adr/0001_workflow_hash.md` | ✅ | Present |
| `grep -rn 'compute_workflow_hash\|from ai_workflows.primitives.workflow_hash' ai_workflows/` | ✅ | 0 hits |
| `grep -rn 'compute_workflow_hash\|from ai_workflows.primitives.workflow_hash' scripts/` | 🟢 | 2 hits in `scripts/m1_smoke.py` — logged as M1-T10-ISS-01, deferred to T13 per file-fate decision |
| `grep -c 'KDR-009' design_docs/adr/0001_workflow_hash.md` | ✅ | 3 hits (Context, Decision, References) — spec requires explicit KDR-009 cite |

## Issue log — cross-task follow-up

| ID | Severity | Status | Where | Owner |
| --- | --- | --- | --- | --- |
| M1-T10-ISS-01 | LOW | 🟡 DEFERRED → T13 | `scripts/m1_smoke.py:36/:62` — stale `compute_workflow_hash` import + call in already-dead script | T13 (milestone close-out; folds into existing M1-T06-ISS-04 "rewrite or delete" decision) |

## Deferred to future tasks

### To T13 (Milestone close-out) — M1-T10-ISS-01

Carry-over block appended to [task_13_issue.md](task_13_issue.md) under `## Carry-over from prior audits`, co-located with the existing `M1-T06-ISS-04` entry (both cover the same file and share the same remediation branches).

## Deferred to nice_to_have

_None._ No finding maps to a [design_docs/nice_to_have.md](../../../nice_to_have.md) entry. The source-code drift-detect gap that the ADR documents is **not** a nice-to-have item — it is an open M3 design question, appropriately deferred to when `aiw resume` lands.

## Propagation status

- M1-T10-ISS-01 → forward-deferred to [task_13_issue.md](task_13_issue.md) `## Carry-over from prior audits` (new `### From M1-T10-ISS-01 …` block added alongside the pre-existing `M1-T06-ISS-04` block). On T13 close-out, flip M1-T10-ISS-01 from `DEFERRED` to `RESOLVED (<commit sha>)` here and tick the carry-over checkbox in [task_13_issue.md](task_13_issue.md).
- No other audit file cross-impacted — T05 (the dependency in the task header) already resolved its column-drop work; this task's Option B outcome confirms T05's removal stands (no `migrations/00N_workflow_hash_column.sql` was added, per task spec's "If Option A" scope boundary).
