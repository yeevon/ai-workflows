# Task 06 — Refit TierConfig + tiers.yaml — Pre-build Audit Amendments

**Source task:** [../task_06_refit_tier_config.md](../task_06_refit_tier_config.md)
**Source audit:** [../audit.md](../audit.md) (produced by [M1 Task 01](../task_01_reconciliation_audit.md))
**Created on:** 2026-04-19
**Status:** 📋 PENDING BUILDER — gates not yet run; this file encodes pre-build amendments only.

## Why this file exists

Task files `task_02`…`task_13` were drafted **before** the reconciliation audit ran. Per [CLAUDE.md](../../../../CLAUDE.md) Builder conventions, this file is the bridge to the [audit.md](../audit.md) source of truth.

## Required reading order for Builder

1. [../../../architecture.md](../../../architecture.md) — especially KDR-003 / KDR-007 / §4.1.
2. [../audit.md](../audit.md) — authoritative source. Rows targeting `task 06` apply here.
3. [../task_06_refit_tier_config.md](../task_06_refit_tier_config.md) — deliverables + ACs.
4. This file — amendments.
5. If audit and task disagree, **raise the conflict before implementing** per CLAUDE.md Builder conventions.

## Rows from audit.md this task must execute

### MODIFY

| Path | Reason |
| --- | --- |
| `ai_workflows/primitives/tiers.py` | Needs LiteLLM model strings and the `claude_code` subprocess spec column per KDR-007 and [architecture.md §4.1](../../../architecture.md); current tier shape predates both. |
| `tiers.yaml` | Needs to express LiteLLM model strings + a `claude_code` subprocess spec per KDR-007 / [architecture.md §4.1](../../../architecture.md). |
| `tests/primitives/test_tiers_loader.py` | Exercise the reshaped `tiers.yaml` (LiteLLM strings + claude_code subprocess spec). |

## Known amendments vs. task spec

- **Provider strategy.** Runtime tiers are Gemini (via LiteLLM, `GEMINI_API_KEY`) + Qwen (via Ollama through LiteLLM) + `claude_code` (subprocess). **No Anthropic API** per KDR-003 — `tiers.yaml` must not carry an `anthropic:*` LiteLLM model string even if LiteLLM supports that provider family. Any Claude tier routes via the `claude_code` subprocess driver only.
- Read the task spec alongside this constraint; flag any conflict before implementing.

## Carry-over from prior audits

_None._

## Propagation status

Post-build audit will overwrite this file with implementation findings.
