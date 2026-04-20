# Task 08 — Prune CostTracker Surface — Audit Issues

**Source task:** [../task_08_prune_cost_tracker.md](../task_08_prune_cost_tracker.md)
**Audited on:** 2026-04-19 (post-build, Cycle 1 + Cycle 2 sweep)
**Audit scope:** `ai_workflows/primitives/cost.py`, `tests/primitives/test_cost.py`, `ai_workflows/primitives/tiers.py` docstring sweeps, carry-over from M1-T05-ISS-01 / M1-T06-ISS-02, full-suite downstream impact.
**Status:** ✅ PASS on T08's five explicit ACs + both inherited carry-overs + the two cycle-1 LOW findings closed by the cycle-2 docstring sweep. One LOW item forward-deferred to T09 (`logging.py:25` `BudgetExceeded` mention, logger-owned file).

## Design-drift check (mandatory; architecture.md + KDRs re-read)

| Concern | Verdict | Evidence |
| --- | --- | --- |
| New dependency in `pyproject.toml` | ✅ None added | `pyproject.toml` unchanged; only `pydantic` (already present) + `collections.defaultdict` + `retry.NonRetryable` used |
| Four-layer contract | ✅ Kept | `cost.py` imports only `pydantic` + `retry` (same layer); no graph/workflow/surface import. `uv run lint-imports` → 2 kept, 0 broken |
| LLM call added (KDR-004 TieredNode+ValidatorNode) | ✅ N/A | T08 is pure aggregation; no LLM call |
| `anthropic` SDK / `ANTHROPIC_API_KEY` (KDR-003) | ✅ Absent | `grep -n anthropic ai_workflows/primitives/cost.py` → 0 hits |
| Checkpoint / resume logic (KDR-009) | ✅ N/A | `Storage` is not imported from `cost.py`; M2 Pipeline owns terminal-state stamp |
| Retry logic (KDR-006 taxonomy via `RetryingEdge`) | ✅ Compliant | `check_budget` raises `NonRetryable` from `primitives/retry.py`; no bespoke try/except loop |
| Observability (StructuredLogger only) | ✅ Compliant | No `logfire` / Langfuse / OTel / LangSmith import; no new log surface at all (structlog removed with `BudgetExceeded`) |
| `nice_to_have.md` adoption check | ✅ None | No Instructor / Typer / Docker-compose / mkdocs / DeepAgents / LangSmith surface introduced |
| LiteLLM pricing enrichment (KDR-007, §4.1) | ✅ Honoured | `cost_usd` arrives pre-filled on `TokenUsage`; `CostTracker` does no pricing math |
| Sub-model modelUsage (§4.1) | ✅ Preserved | `sub_models: list[TokenUsage]` (recursive); `total` / `by_tier` / `by_model(include_sub_models=True)` all walk the tree |

No design drift. Proceeding to AC grading.

## AC grading (task file + carry-over)

| # | AC | Verdict | Evidence |
| --- | --- | --- | --- |
| AC-1 | `TokenUsage` carries recursive `sub_models` and round-trips through pydantic | ✅ | `TokenUsage.sub_models: list[TokenUsage] = Field(default_factory=list)` + `test_token_usage_round_trips_through_pydantic_serialisation` + `test_token_usage_sub_models_accept_recursive_depth` green |
| AC-2 | `CostTracker.record` is the single write path | ✅ | Only `record(run_id, usage)` mutates `self._entries`; `total` / `by_tier` / `by_model` / `check_budget` are read-only. `test_record_is_the_single_write_method` + `test_total_rolls_up_sub_models_per_modelusage_spec` + `test_by_tier_groups_costs_and_includes_sub_models` + `test_by_model_include_sub_models_true_breaks_out_each_sub_call` |
| AC-3 | `check_budget` raises the `NonRetryable` from task 07 | ✅ | `from ai_workflows.primitives.retry import NonRetryable`; `test_check_budget_raises_non_retryable_on_breach` + `test_check_budget_sub_models_count_toward_cap` + `test_check_budget_exactly_at_cap_does_not_raise` green; message carries `budget exceeded` + `$0.60` + `$0.50` + `r1` |
| AC-4 | `grep -r pydantic_ai ai_workflows/primitives/cost.py tests/primitives/test_cost.py` → zero | 🟢 under code-level reading | cost.py import-line scan → 0 hits; test_cost.py import-line scan → 0 hits. Literal-grep matches are in AC-4's own assertion strings (same paradox T07 AC-3 logged). Pinned by `test_cost_module_has_no_pydantic_ai_imports` |
| AC-5 | `uv run pytest tests/primitives/test_cost.py` green | ✅ | 20 passed in 0.81s |
| Carry-over M1-T05-ISS-01 (MEDIUM) | `CostTracker` no longer calls trimmed Storage surface | ✅ RESOLVED | `log_llm_call` / `get_total_cost` / `get_cost_breakdown` → 0 hits in cost.py. Pinned by `test_cost_module_does_not_call_trimmed_storage_methods`. Previous test_cost.py 13-failure cascade is now 0 failures |
| Carry-over M1-T06-ISS-02 (MEDIUM) | `pricing.yaml` fate decided + documented | ✅ RESOLVED | Decision: **kept as-is** (no `CostTracker` read; retained for M2 Claude Code driver). Documented in T08 CHANGELOG block. `cost.py` imports neither `ModelPricing` nor `load_pricing`; pinned by `test_cost_module_does_not_import_pricing_helpers` |

## 🔴 HIGH

_None._

## 🟡 MEDIUM

_None._

## 🟢 LOW

### ✅ RESOLVED (cycle 2) — M1-T08-ISS-01: `tiers.py:19` docstring references removed `CostTracker.calculate_cost`

**Original problem:** T08 removed `calculate_cost` from `CostTracker`; the `ModelPricing` docstring bullet at `tiers.py:19` still named it.

**Fix landed in cycle 2:** Rewrote `ai_workflows/primitives/tiers.py:18-21` to describe `ModelPricing` as loaded by `load_pricing` for the M2 Claude Code subprocess driver. Explicitly documents that post-T08 `CostTracker` no longer prices calls. Verified by re-running `grep -n calculate_cost ai_workflows/primitives/tiers.py` → 0 hits. `uv run pytest tests/primitives/test_tiers_loader.py tests/primitives/test_cost.py` → 42 passed.

### ✅ RESOLVED (cycle 2) — M1-T08-ISS-02: `tiers.py:30` claims `cost.py` is the "sole consumer of ModelPricing" after T08 removed the import

**Original problem:** T08 dropped `from ai_workflows.primitives.tiers import ModelPricing` from `cost.py`; the "See also" cross-ref still claimed `cost.py` was the sole consumer.

**Fix landed in cycle 2:** Rewrote `ai_workflows/primitives/tiers.py:30` to point at M2 Task 02 (the Claude Code subprocess driver) as the consumer of `ModelPricing`, with an explicit note that post-T08 `primitives/cost.py` no longer imports the class. Verified by `grep -n "sole consumer" ai_workflows/primitives/tiers.py` → 0 hits.

## Additions beyond spec — audited and justified

1. **`tier` field on `TokenUsage` (not listed in the spec's three extension fields).** The spec lists `cost_usd` / `model` / `sub_models` as the extensions but also mandates `CostTracker.by_tier(run_id) -> dict[str, float]` as a public method. `by_tier` cannot function without per-call tier metadata. Adding the field is the minimum scope to satisfy both deliverables. Documented in CHANGELOG deviations.
2. **`calculate_cost` removed (not in the spec's "Remove" list, but implied).** The spec names `BudgetExceeded` removal (replaced by `NonRetryable`) and pydantic-ai coupling removal. `calculate_cost` relies on `ModelPricing` which the new `CostTracker` doesn't read; keeping an unused helper would have been dead code. The M2 Claude Code driver will re-implement pricing math at the driver layer. Noted as deviation in CHANGELOG.
3. **Synchronous API (spec was silent).** Pre-pivot `record` / `run_total` / `component_breakdown` were `async def`. The pruned surface has no I/O, so methods are now plain `def`. Saves awaits everywhere in callers; reversible if M2 needs async.
4. **`defaultdict(list)` for `_entries` + `defaultdict(float)` for rollups.** Implementation detail — avoids `if run_id not in …` branches. No public surface impact.
5. **Recursive `_accumulate_by_model` walks sub-models when `include_sub_models=True`.** Matches §4.1's "both must be recorded" rule across arbitrary modelUsage nesting depth. Spec said only 1-level sub_models; going deeper costs nothing and prevents future drift if LiteLLM/Claude CLI start emitting deeper trees.
6. **`test_cost_tracker_structural_compat_with_magic_mock_spec`.** Carry-forward from the deleted `test_cost_tracker_structural_compat_with_model_factory` — M2 callback will need `MagicMock(spec=CostTracker)` to keep its mocks typed. Small pin, no scope creep.

## Gate summary

| Gate | Result | Notes |
| --- | --- | --- |
| `uv run ruff check` | ✅ | "All checks passed!" |
| `uv run lint-imports` | ✅ | 2 contracts kept, 0 broken |
| `uv run pytest tests/primitives/test_cost.py` | ✅ | 20 passed in 0.81s |
| `uv run pytest` (full suite) | 🟡 T-scope read | 128 passed / 4 failed. Failures = T09 (`logfire`) + T11 (`test_cli.py` cascade + 4 `test_scaffolding.py` fallout). Pre-existing, T07 post-build audit already logged these under the same T-scope reading. T08 *reduced* the prior 13 `test_cost.py` failures to 0 — net suite improvement |
| `grep -r pydantic_ai ai_workflows/primitives/cost.py tests/primitives/test_cost.py` | 🟢 code-level | Zero import-line hits; literal matches are in AC-4's own assertion strings (same paradox as T07 AC-3) |

## Issue log — cross-task follow-up

| ID | Severity | Status | Where | Owner |
| --- | --- | --- | --- | --- |
| M1-T05-ISS-01 | MEDIUM | ✅ RESOLVED (cycle 1) | trimmed-Storage method refs in cost.py | Closed by T08 refit |
| M1-T06-ISS-02 | MEDIUM | ✅ RESOLVED (cycle 1) | `pricing.yaml` kept as-is; cost.py no longer reads it | Closed by T08 refit |
| M1-T08-ISS-01 | LOW | ✅ RESOLVED (cycle 2) | `tiers.py:19` — stale `CostTracker.calculate_cost` ref | Closed |
| M1-T08-ISS-02 | LOW | ✅ RESOLVED (cycle 2) | `tiers.py:30` — stale "sole consumer of ModelPricing" claim | Closed |
| M1-T08-DEF-01 | LOW | ✅ RESOLVED (T09 d427bf6) | `logging.py:25` references removed `BudgetExceeded` | T09 logger-sanity pass landed; docstring drift closed |

## Deferred to future tasks

### To T09 (StructuredLogger sanity pass) — M1-T08-DEF-01

`ai_workflows/primitives/logging.py:25` still lists `BudgetExceeded` as an ERROR-level exemplar in its module docstring. T08 replaced `BudgetExceeded` with the `NonRetryable("budget exceeded")` route from T07. T09's logger-sanity pass is already slated to touch this file; forward-deferring the docstring fix avoids T08 drive-by into T09 territory. Carry-over block appended to `design_docs/phases/milestone_1_reconciliation/issues/task_09_issue.md`.

## Deferred to nice_to_have

_None._ No finding maps to a `design_docs/nice_to_have.md` entry.

## Propagation status

- M1-T08-ISS-01 and M1-T08-ISS-02 resolved above (cycle 2 docstring sweep in `tiers.py`). No external propagation needed — targets lived in the T08-affected `tiers.py` tree.
- On T09 post-build audit: flip `M1-T08-DEF-01` from `DEFERRED` to `RESOLVED`; carry-over entry in [task_09_issue.md](task_09_issue.md) is the channel.
- M1-T05-ISS-01 → already resolved in cycle 1; on the next T05 re-audit touch point, [task_05_issue.md](task_05_issue.md) can flip `M1-T05-ISS-01` from `DEFERRED` to `RESOLVED (<commit sha>)`.
- M1-T06-ISS-02 → already resolved in cycle 1; on the next T06 re-audit touch point, [task_06_issue.md](task_06_issue.md) can flip `M1-T06-ISS-02` from `DEFERRED` to `RESOLVED (<commit sha>)`.
