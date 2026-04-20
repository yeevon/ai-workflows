# Milestone 3 — First Workflow (`planner`, Single Tier)

**Status:** 📝 Planned. Starts once [M2](../milestone_2_graph/README.md) closes clean.
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

Critical path: T01 registry → T02 schema → T03 graph → T04–T06 CLI commands in any order → T07 smoke test → T08 close-out.

| # | Task | Critical-path dep |
| --- | --- | --- |
| 01 | Workflow registry (`workflows/__init__.py`, `register(name, builder)`) | — |
| 02 | Planner pydantic I/O schemas (`PlannerInput`, `PlannerPlan`) | T01 |
| 03 | `planner` `StateGraph` (explorer + LLM + validator + gate) | T02 |
| 04 | CLI `aiw run` command (revives the stub from M1.11) | T03 |
| 05 | CLI `aiw resume` command | T03 |
| 06 | CLI `aiw list-runs` command (cost-report deferred — see [T06 reframe](task_06_cli_list_cost.md)) | T03 |
| 07 | End-to-end smoke test (`@pytest.mark.e2e`) | T04–T06 |
| 08 | Milestone close-out (README, roadmap, CHANGELOG) | T01–T07 |

Per-task files will be generated once M2 closes, when the concrete node APIs are settled.

## Issues

Land under [issues/](issues/).
