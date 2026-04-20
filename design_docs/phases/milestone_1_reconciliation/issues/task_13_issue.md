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

_Forward-deferred items raised across task 02…12 audits land here as they propagate. All must be resolved (or re-homed with an explicit owner) before the milestone can close._

### From [M1-T06-ISS-04](task_06_issue.md#-low--m1-t06-iss-04-scriptsm1_smokepy-imports-the-removed-load_tiers--owned-by-t13) (T06 post-build audit, 2026-04-19)

T06 removed `load_tiers` (replaced by `TierRegistry.load`). `scripts/m1_smoke.py:35` still contains `from ai_workflows.primitives.tiers import load_pricing, load_tiers`. The file was already broken post-T03 (imports `pydantic_ai`, `llm.model_factory`, `WorkflowDeps`), so no gate is regressed — the file cannot be executed. T06 does not newly break it; it just widens the set of stale imports already in the file.

- [ ] **M1-T06-ISS-04 · LOW** — Decide `scripts/m1_smoke.py`'s fate during M1 close-out: **either rewrite `scripts/m1_smoke.py` against the post-pivot substrate (LiteLLM adapter + `TierRegistry.load`, no `pydantic_ai`, no `WorkflowDeps`) or delete it entirely.** The file is currently unreachable because it imports `pydantic_ai`, `llm.model_factory`, `WorkflowDeps`, and `load_tiers` — all removed in M1. Document the decision in the T13 CHANGELOG block. Source: [task_06_issue.md §M1-T06-ISS-04](task_06_issue.md#-low--m1-t06-iss-04-scriptsm1_smokepy-imports-the-removed-load_tiers--owned-by-t13).

### From [M1-T10-ISS-01](task_10_issue.md) (T10 post-build audit, 2026-04-19)

T10 (ADR-0001) retired `ai_workflows.primitives.workflow_hash`. `scripts/m1_smoke.py:36` still contains `from ai_workflows.primitives.workflow_hash import compute_workflow_hash` and `:62` still calls `compute_workflow_hash(Path.cwd())`. The file was already broken post-T03 / T06 / T07 / T08 (imports `pydantic_ai`, `llm.model_factory`, `WorkflowDeps`, `load_tiers`, `BudgetExceeded`), so no gate is regressed — the file cannot be executed. T10 does not newly break it; it adds one more stale import to a file that is already fully unexecutable.

- [ ] **M1-T10-ISS-01 · LOW** — Fold into the M1-T06-ISS-04 close-out decision for `scripts/m1_smoke.py`: when T13 decides whether to rewrite or delete, the `compute_workflow_hash` import and the `workflow_dir_hash = compute_workflow_hash(Path.cwd())` call must both go. If T13 rewrites the smoke script against the post-pivot substrate, there is no `compute_workflow_hash` replacement — M3 owns the drift-detect design, and the smoke script should not pre-empt it. If T13 deletes the script, the issue resolves by deletion. Source: [task_10_issue.md §M1-T10-ISS-01](task_10_issue.md#-low--m1-t10-iss-01-scriptsm1_smokepy-imports-the-retired-compute_workflow_hash--owned-by-t13).

## Propagation status

Post-build audit of this task will overwrite this file with implementation findings. The milestone does not close until every issue file in this directory reads `✅ PASS`.
On completion of the M1-T06-ISS-04 carry-over, [task_06_issue.md](task_06_issue.md) flips it from `DEFERRED` to `RESOLVED (commit sha)` on the next T06 re-audit touch point.
On completion of the M1-T10-ISS-01 carry-over, [task_10_issue.md](task_10_issue.md) flips it from `DEFERRED` to `RESOLVED (commit sha)` on the next T10 re-audit touch point.
