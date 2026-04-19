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

_None._

## Propagation status

Post-build audit will overwrite this file with implementation findings.
