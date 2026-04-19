# Task 08 — Prune CostTracker Surface — Pre-build Audit Amendments

**Source task:** [../task_08_prune_cost_tracker.md](../task_08_prune_cost_tracker.md)
**Source audit:** [../audit.md](../audit.md) (produced by [M1 Task 01](../task_01_reconciliation_audit.md))
**Created on:** 2026-04-19
**Status:** 📋 PENDING BUILDER — gates not yet run; this file encodes pre-build amendments only.

## Why this file exists

Task files `task_02`…`task_13` were drafted **before** the reconciliation audit ran. Per [CLAUDE.md](../../../../CLAUDE.md) Builder conventions, this file is the bridge to the [audit.md](../audit.md) source of truth.

## Required reading order for Builder

1. [../../../architecture.md](../../../architecture.md) — especially KDR-007 / §4.1 / §8.5.
2. [../audit.md](../audit.md) — authoritative source. Rows targeting `task 08` apply here.
3. [../task_08_prune_cost_tracker.md](../task_08_prune_cost_tracker.md) — deliverables + ACs.
4. This file — amendments.
5. If audit and task disagree, **raise the conflict before implementing** per CLAUDE.md Builder conventions.

## Rows from audit.md this task must execute

### MODIFY

| Path | Reason |
| --- | --- |
| `ai_workflows/primitives/cost.py` | `CostTracker` surface shrinks — LiteLLM now supplies per-call base cost (KDR-007); keep `modelUsage` sub-model aggregation + budget enforcement only. |
| `pricing.yaml` | LiteLLM now supplies base per-call cost (KDR-007); `pricing.yaml` reduces to only sub-model / override entries that `CostTracker.modelUsage` still needs. |
| `tests/primitives/test_cost.py` | Rewrite around the pruned `CostTracker` surface. |

## Known amendments vs. task spec

- **Sub-model rule.** Per [architecture.md §4.1](../../../architecture.md), `CostTracker`'s unique value is the `modelUsage` sub-model breakdown — a `claude_code` call to `opus` may internally spawn `haiku` sub-calls and **both must be recorded**. Do not strip this behaviour when pruning.
- **Budget enforcement.** Per [architecture.md §8.5](../../../architecture.md), `CostTracker` raises `NonRetryable("budget exceeded")` when the per-run budget is breached. Keep this path intact.
- **Storage coordination.** Per [task 05](../task_05_trim_storage.md) scope boundary: if `CostTracker` still keeps a per-call ledger table, task 05's migration drops the legacy `llm_calls` table and task 08 is the one that (optionally) adds a replacement migration. Only add a replacement if [architecture.md §4.1](../../../architecture.md) actually demands one.

## Carry-over from prior audits

### From [M1-T05-ISS-01](task_05_issue.md) (T05 post-build audit, 2026-04-19)

T05 trimmed `StorageBackend` to the seven run-registry + gate-log methods mandated by KDR-009 / [architecture.md §4.1](../../../architecture.md). `ai_workflows/primitives/cost.py` still calls the dropped `storage.log_llm_call` / `get_total_cost` / `get_cost_breakdown` methods; the resulting runtime breakage shows up as 13 failures under `tests/primitives/test_cost.py` in the T05 post-build full-suite run. T08 already owns the refit — [task_08 §Deliverables → `cost.py`](../task_08_prune_cost_tracker.md) names `record(run_id, usage: TokenUsage)` as the single write path and specifies "default to in-memory aggregation per run and persist only the totals on `update_run_status`." This carry-over pins the concrete deletions T08 must land before its own pytest can go green.

- [ ] **M1-T05-ISS-01 · MEDIUM** — Rewrite `ai_workflows/primitives/cost.py` so `CostTracker` no longer calls the trimmed-away `Storage` surface:
  - Replace the runtime `await self._storage.log_llm_call(...)` at `ai_workflows/primitives/cost.py:205` with in-memory aggregation; persist totals only, via `storage.update_run_status(total_cost_usd=…)`.
  - Replace `await self._storage.get_total_cost(run_id)` at lines 221 and 228 (inside `run_total`) with an in-memory lookup against the aggregate.
  - Replace `await self._storage.get_cost_breakdown(run_id)` at line 232 (inside `component_breakdown`) with an in-memory dict derived from the same aggregate.
  - Delete the `See also` bullet at line 47 that cross-references `log_llm_call, get_total_cost, get_cost_breakdown`.
  - Delete the "Persist the row via storage.log_llm_call" prose in the `record` docstring near line 194.
  - Rewrite `tests/primitives/test_cost.py` stubs at lines ~403, ~420, ~484 so the fake storage mocks only the trimmed `StorageBackend` surface (`update_run_status(total_cost_usd=…)`, plus the other six methods as no-ops when not exercised). Drop all `log_llm_call` / `upsert_task` references.
  - Keep the `NonRetryable("budget exceeded")` path intact per [architecture.md §8.5](../../../architecture.md); that pairs with T07's taxonomy and T08 AC-3.
  - `tests/test_cli.py` at lines 56, 59, 63, 77, 89 (`aiw inspect` seed) remains **out of scope for T08** — those lines live inside the T11 MODIFY row ([audit.md §3](../audit.md)) and are retired when T11 rewrites the CLI stub.
  Source: [task_05_issue.md §M1-T05-ISS-01](task_05_issue.md).

## Propagation status

Post-build audit will overwrite this file with implementation findings.
On completion of the carry-over above, [task_05_issue.md](task_05_issue.md) flips `M1-T05-ISS-01` from `DEFERRED` to `RESOLVED (commit sha)` on the next T05 re-audit touch point.
