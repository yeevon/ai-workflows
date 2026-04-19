# Task 13 — Milestone Close-out — Pre-build Audit Amendments

**Source task:** [../task_13_milestone_closeout.md](../task_13_milestone_closeout.md)
**Source audit:** [../audit.md](../audit.md) (produced by [M1 Task 01](../task_01_reconciliation_audit.md))
**Created on:** 2026-04-19
**Status:** 📋 PENDING BUILDER — this task runs last; gates will be the milestone gate. This file is a pre-build pointer, not an amendment to the task spec.

## Why this file exists

Task files `task_02`…`task_13` were drafted **before** the reconciliation audit ran. Per [CLAUDE.md](../../../../CLAUDE.md) Builder conventions, this file is the bridge to the [audit.md](../audit.md) source of truth. Task 13 itself has no audit-row deliverables (no file in `ai_workflows/` / `tests/` / `migrations/` / `pyproject.toml` is tagged `task 13`) — this file exists for completeness and to direct the Builder to verify every other issue file has flipped to `✅ RESOLVED` before closing the milestone.

## Required reading order for Builder

1. [../../../architecture.md](../../../architecture.md) — the architecture of record; every exit criterion traces back here.
2. [../audit.md](../audit.md) — authoritative source. Task 13 closes the loop by confirming every KEEP / MODIFY / REMOVE / ADD / DECIDE row in the audit has landed.
3. [../task_13_milestone_closeout.md](../task_13_milestone_closeout.md) — deliverables + ACs.
4. This file — closeout-specific amendments (none for task rows; see pre-close checklist below).
5. [../README.md](../README.md) — milestone exit criteria to tick.

## Pre-close checklist (beyond the task spec's own ACs)

- [ ] Every other issue file in [./](./) has **Status: ✅ PASS**. No task 02…12 issue file should remain in 🟡 OPEN or 🔴 HIGH state.
- [ ] For every `ai_workflows/` row in [../audit.md](../audit.md): verify the expected file state (present for KEEP / MODIFY, absent for REMOVE, present with new contents for ADD).
- [ ] For every `tests/` row: same verification.
- [ ] For every `migrations/` row: same verification, plus `yoyo apply` runs clean on a fresh DB.
- [ ] For every `pyproject.toml` row: verify the dependency set matches — particularly that `logfire`, `anthropic`, `pydantic-ai*`, `networkx` are all gone and `langgraph`, `langgraph-checkpoint-sqlite`, `litellm`, `fastmcp` are present with pinned lower bounds.
- [ ] [task 10](../task_10_workflow_hash_decision.md)'s ADR outcome is reflected in both `workflow_hash.py`'s presence/absence AND the `runs` table's column set.
- [ ] [.github/workflows/ci.yml](../../../../.github/workflows/ci.yml) import-lint step is renamed away from "3-layer architecture" (see [task 12 issue](task_12_issue.md) AUD-12-01).
- [ ] No [nice_to_have.md](../../../nice_to_have.md) entry has been silently adopted — grep for `langfuse`, `langsmith`, `instructor`, `docker-compose`, `mkdocs`, `deepagents`, `opentelemetry` across `pyproject.toml` + `ai_workflows/` to confirm.

## Known amendments vs. task spec

- **Aligned.** The task spec's exit criteria already cover the milestone README, roadmap status, CHANGELOG date-section promotion, and the green-gate snapshot. The pre-close checklist above is additive audit-traceability, not a conflict.

## Carry-over from prior audits

_None at this stage — all M1 tasks either have their own pre-build issue file amendments or are closed. Any `DEFERRED (owner: TBD)` entries raised across task 02…12 audits must be surfaced here before the milestone can close._

## Propagation status

Post-build audit of this task will overwrite this file with implementation findings. The milestone does not close until every issue file in this directory reads `✅ PASS`.
