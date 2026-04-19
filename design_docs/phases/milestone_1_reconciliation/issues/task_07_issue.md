# Task 07 — Refit RetryPolicy to 3-bucket Taxonomy — Pre-build Audit Amendments

**Source task:** [../task_07_refit_retry_policy.md](../task_07_refit_retry_policy.md)
**Source audit:** [../audit.md](../audit.md) (produced by [M1 Task 01](../task_01_reconciliation_audit.md))
**Created on:** 2026-04-19
**Status:** 📋 PENDING BUILDER — gates not yet run; this file encodes pre-build amendments only.

## Why this file exists

Task files `task_02`…`task_13` were drafted **before** the reconciliation audit ran. Per [CLAUDE.md](../../../../CLAUDE.md) Builder conventions, this file is the bridge to the [audit.md](../audit.md) source of truth.

## Required reading order for Builder

1. [../../../architecture.md](../../../architecture.md) — especially KDR-006 / KDR-007 / §8.2.
2. [../audit.md](../audit.md) — authoritative source. Rows targeting `task 07` apply here.
3. [../task_07_refit_retry_policy.md](../task_07_refit_retry_policy.md) — deliverables + ACs.
4. This file — amendments.
5. If audit and task disagree, **raise the conflict before implementing** per CLAUDE.md Builder conventions.

## Rows from audit.md this task must execute

### MODIFY

| Path | Reason |
| --- | --- |
| `ai_workflows/primitives/retry.py` | Refit to the three-bucket taxonomy (`RetryableTransient` \| `RetryableSemantic` \| `NonRetryable`) per KDR-006 and [architecture.md §8.2](../../../architecture.md); LiteLLM now owns the transient retry layer underneath. |
| `tests/primitives/test_retry.py` | Rewrite around the three-bucket taxonomy. |

## Known amendments vs. task spec

- **Layer split.** Per [architecture.md §8.2](../../../architecture.md): `RetryableTransient` bubbles up to `RetryingEdge` (M2) only after LiteLLM's own transient retry has exhausted; `RetryableSemantic` integrates with `ValidatorNode` (M2) via LangGraph `ModelRetry`; `NonRetryable` feeds the double-failure hard-stop. `RetryPolicy` in this task is the **classifier**, not the executor — the execution layer lands in M2. If the task spec conflates classification and execution, keep classification here and defer execution to M2.

## Carry-over from prior audits

_None._

## Propagation status

Post-build audit will overwrite this file with implementation findings.
