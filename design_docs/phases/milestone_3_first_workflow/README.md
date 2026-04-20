# Milestone 3 — First Workflow (`planner`, Single Tier)

**Status:** ✅ Complete (2026-04-20).
**Grounding:** [architecture.md §4.3](../../architecture.md) · [roadmap.md](../../roadmap.md).

## Goal

Ship the first real LangGraph workflow — a single-tier `planner` — running end-to-end through the M2 adapters. Revive the `aiw` CLI so `aiw run planner …` drives a real graph, persists via `SqliteSaver`, and can be resumed through a `HumanGate`.

## Exit criteria

1. `ai_workflows.workflows.planner` exports a built `StateGraph` with explorer → planner-llm → validator → human-gate → artifact.
2. Running `aiw run planner --input '<goal>'` executes a full run end-to-end on a Gemini tier (via LiteLLM), writing the plan artifact and a cost report.
3. `aiw resume <run_id>` rehydrates from the `SqliteSaver` checkpoint and clears a pending `HumanGate`.
4. `aiw list-runs` returns the expected structured output. (The originally-paired `aiw cost-report` command was dropped at T06 reframe (2026-04-20) and deferred to [nice_to_have.md §9](../../nice_to_have.md) — see the T06 spec's "Design drift and reframe" section for the three reasons.)
5. One end-to-end smoke test (marked `@pytest.mark.e2e`) validates the happy path. Default `pytest` run skips it unless `AIW_E2E=1`.
6. All gates green (`uv run pytest`, `uv run lint-imports`, `uv run ruff check`).

## Non-goals

- Multi-tier routing (M5).
- MCP surface (M4).
- `slice_refactor` (M6).
- Eval coverage of planner prompts (M7).

## Key decisions in effect

| Decision | Reference |
| --- | --- |
| Workflows are `StateGraph` modules | [architecture.md §4.3](../../architecture.md) |
| Validator after every LLM node | KDR-004 |
| LiteLLM adapter handles Gemini | KDR-007 |
| SqliteSaver owns resume | KDR-009 |

## Task order

Critical path: T01 registry → T02 schema → T03 graph → T04–T06 CLI commands in any order → T07 smoke test → T07a structured-output fix → T07b schema simplification → T08 close-out.

| # | Task | Critical-path dep |
| --- | --- | --- |
| 01 | Workflow registry (`workflows/__init__.py`, `register(name, builder)`) | — |
| 02 | Planner pydantic I/O schemas (`PlannerInput`, `PlannerPlan`) | T01 |
| 03 | `planner` `StateGraph` (explorer + LLM + validator + gate) | T02 |
| 04 | CLI `aiw run` command (revives the stub from M1.11) | T03 |
| 05 | CLI `aiw resume` command | T03 |
| 06 | CLI `aiw list-runs` command (cost-report deferred — see [T06 reframe](task_06_cli_list_cost.md)) | T03 |
| 07 | End-to-end smoke test (`@pytest.mark.e2e`) | T04–T06 |
| 07a | Planner `tiered_node` native structured output (closes T03 live-path convergence gap surfaced by T07) | T07 |
| 07b | `PlannerPlan` / `PlannerStep` bound-strip (clears Gemini structured-output admission block surfaced by T07a) | T07a |
| 08 | Milestone close-out (README, roadmap, CHANGELOG) | T01–T07, T07a, T07b |

Per-task files will be generated once M2 closes, when the concrete node APIs are settled.

## Issues

Land under [issues/](issues/).

## Outcome (2026-04-20)

M3 closed on 2026-04-20. Every T01–T07 task landed clean (single or two-cycle `/clean-implement` audits — see [issues/](issues/)) plus this docs-only close-out (T08). The milestone ships the first real LangGraph workflow (`planner`, single Gemini tier) end-to-end, with the `aiw` CLI revived on top of the M2 adapters.

**Workflow registry + schemas** ([task 01](task_01_workflow_registry.md), [task 02](task_02_planner_schemas.md)):

- [`ai_workflows.workflows.register / get_workflow`](../../../ai_workflows/workflows/__init__.py) — lazy, idempotent `(name) -> builder()` registry so the CLI and future MCP surface both resolve a workflow by a stable string key.
- [`PlannerInput` / `PlannerPlan`](../../../ai_workflows/workflows/planner.py) — pydantic I/O contracts for the planner; the schema is what the `ValidatorNode` and the `aiw run` CLI surface both enforce (KDR-004).

**Planner `StateGraph`** ([task 03](task_03_planner_graph.md)):

- [`ai_workflows.workflows.planner.build_planner_graph`](../../../ai_workflows/workflows/planner.py) — explorer → `TieredNode` (planner-llm) → `ValidatorNode` → `HumanGate` → artifact node, compiled against `AsyncSqliteSaver` per KDR-009. Every LLM node is paired with a validator per KDR-004; no bespoke retry loops (KDR-006).

**CLI commands revived** ([tasks 04](task_04_cli_run.md)–[06](task_06_cli_list_cost.md)):

- [`aiw run planner`](../../../ai_workflows/cli.py) ([task 04](task_04_cli_run.md)) — compiles the planner graph, pauses at the `HumanGate`, stamps `runs.total_cost_usd` at pause so `aiw resume` can reseed the `CostTracker` across the run / resume boundary.
- [`aiw resume <run_id>`](../../../ai_workflows/cli.py) ([task 05](task_05_cli_resume.md)) — rehydrates from `AsyncSqliteSaver` and hands `Command(resume=<response>)` to LangGraph so the pending `HumanGate` clears; writes the plan artifact on approve, flips status to `gate_rejected` on reject.
- [`aiw list-runs`](../../../ai_workflows/cli.py) ([task 06](task_06_cli_list_cost.md)) — pure read over `SQLiteStorage.list_runs` with `--workflow / --status / --limit` filters and the scalar `runs.total_cost_usd` per row. **The originally-paired `aiw cost-report` command was dropped at T06 reframe (2026-04-20) and deferred to [nice_to_have.md §9](../../nice_to_have.md)** — three adoption triggers recorded there; three reasons (no per-call ledger post-M1.05, no `provider` field on `TokenUsage`, zero decision value under subscription billing) recorded in the [T06 "Design drift and reframe" section](task_06_cli_list_cost.md).

**End-to-end smoke test** ([task 07](task_07_e2e_smoke.md)):

- [`tests/e2e/test_planner_smoke.py`](../../../tests/e2e/test_planner_smoke.py) — one `@pytest.mark.e2e` test that drives the full `aiw run planner` → `aiw resume` path against real Gemini Flash (via LiteLLM) and asserts every M3 invariant the hermetic graph-layer tests cannot exercise: a real provider call completes, budget cap is honoured end-to-end, the approved plan round-trips from Storage, and no `ANTHROPIC_API_KEY` / `anthropic.` reference leaks into logs (KDR-003). Gated by `AIW_E2E=1` via [`tests/e2e/conftest.py`](../../../tests/e2e/conftest.py) so the default `uv run pytest` stays hermetic.
- [`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml) — new `e2e` CI job, manual-trigger-only (`workflow_dispatch`) with `GEMINI_API_KEY` bound as a secret. Per-PR runs would burn quota for no benefit.
- T07 inherits the T06 reframe: budget assertion reads `runs.total_cost_usd` rather than the unsatisfiable `CostTracker.from_storage(...)` that the original spec prescribed. Same deferral to [nice_to_have.md §9](../../nice_to_have.md); no new primitive-layer surface added for a deferred concern.

**Green-gate snapshot (2026-04-20)**:

| Gate | Result |
| --- | --- |
| `uv run pytest` (hermetic, `AIW_E2E` unset) | ✅ 295 passed, 1 skipped, 2 warnings (pre-existing `yoyo` datetime deprecation) in 6.65s |
| `AIW_E2E=1 uv run pytest tests/e2e/ --collect-only` | ✅ 1 test collected (gate flips from skip to run) |
| `uv run lint-imports` | ✅ 3 contracts kept, 0 broken (22 files, 32 dependencies analyzed) |
| `uv run ruff check` | ✅ All checks passed |

The skipped test is the new e2e smoke test, deliberately skipped when `AIW_E2E` is unset per T07 AC-1.

**Exit-criteria verification**:

1. `ai_workflows.workflows.planner` exports a built `StateGraph` with explorer → planner-llm → validator → human-gate → artifact — verified: [task_03_issue.md](issues/task_03_issue.md) ✅ PASS; graph builder at [`planner.py:build_planner_graph`](../../../ai_workflows/workflows/planner.py).
2. `aiw run planner --input '<goal>'` executes a full run end-to-end on a Gemini tier via LiteLLM, writing the plan artifact and a cost report — verified end-to-end by the T07 smoke test ([`tests/e2e/test_planner_smoke.py`](../../../tests/e2e/test_planner_smoke.py)) and locally via [task_04_issue.md](issues/task_04_issue.md) ✅ PASS + [task_07_issue.md](issues/task_07_issue.md) ✅ PASS. Budget-cap assertion reads `runs.total_cost_usd` per the T06/T07 reframe.
3. `aiw resume <run_id>` rehydrates from the `SqliteSaver` checkpoint and clears a pending `HumanGate` — verified: [task_05_issue.md](issues/task_05_issue.md) ✅ PASS; seven unit tests in [`tests/cli/test_resume.py`](../../../tests/cli/test_resume.py) cover approve/reject/unknown-id/missing-checkpoint/cost-reseed.
4. `aiw list-runs` returns the expected structured output (originally-paired `aiw cost-report` dropped at T06 reframe) — verified: [task_06_issue.md](issues/task_06_issue.md) ✅ PASS; six unit tests in [`tests/cli/test_list_runs.py`](../../../tests/cli/test_list_runs.py) cover empty storage, filters, limit, pure-read invariant, and `—` NULL rendering.
5. One end-to-end smoke test (marked `@pytest.mark.e2e`) validates the happy path; default `pytest` run skips it unless `AIW_E2E=1` — verified: [task_07_issue.md](issues/task_07_issue.md) ✅ PASS; skip reason verbatim `"Set AIW_E2E=1 to run e2e tests"`.
6. All gates green (`uv run pytest`, `uv run lint-imports`, `uv run ruff check`) — snapshot above.
