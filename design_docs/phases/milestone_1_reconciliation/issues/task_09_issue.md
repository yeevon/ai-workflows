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

_None._

## Propagation status

Post-build audit will overwrite this file with implementation findings.
