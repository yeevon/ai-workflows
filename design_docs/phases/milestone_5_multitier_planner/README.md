# Milestone 5 — Multi-Tier `planner`

**Status:** ✅ Complete (2026-04-20).
**Grounding:** [architecture.md §4.3](../../architecture.md) · [roadmap.md](../../roadmap.md).

## Goal

Upgrade the `planner` workflow from single-tier to a two-phase sub-graph: **Qwen (local_coder) explore → Claude Code (opus) plan**. This is the first real exercise of both provider drivers inside one workflow and proves the tier-override surface works across CLI and MCP.

## Exit criteria

1. `planner` executes the two-phase sub-graph end-to-end: Qwen explorer produces a findings blob, Claude Code planner consumes it and emits the plan artifact.
2. Tier override (`aiw run planner --tier-override explorer=gemini_flash`) reroutes the explorer node without code change.
3. MCP `run_workflow` accepts a `tier_overrides` argument and produces identical behaviour.
4. `modelUsage` cost ledger records both the Qwen call (cost 0, local) and the Claude Code call (with haiku sub-calls rolled up).
5. Gates green.

## Non-goals

- `slice_refactor` — M6.
- Ollama fallback / circuit breaker — M8.
- Automated prompt evals — M7.

## Key decisions in effect

| Decision | Reference |
| --- | --- |
| Two-phase planner as sub-graph | [architecture.md §4.3](../../architecture.md) |
| Tier override is a surface contract | [architecture.md §4.4](../../architecture.md) |
| No Anthropic API | KDR-003 |

## Task order

| # | Task |
| --- | --- |
| 01 | [Qwen explorer tier refit](task_01_qwen_explorer.md) |
| 02 | [Claude Code planner tier refit](task_02_claude_code_planner.md) |
| 03 | [Sub-graph composition validation (integration)](task_03_subgraph_composition.md) |
| 04 | [Tier-override CLI plumbing (`--tier-override logical=replacement`)](task_04_tier_override_cli.md) |
| 05 | [Tier-override MCP plumbing (`RunWorkflowInput.tier_overrides`)](task_05_tier_override_mcp.md) |
| 06 | [End-to-end smoke (hermetic + `AIW_E2E=1` live)](task_06_e2e_smoke.md) |
| 07 | [Milestone close-out](task_07_milestone_closeout.md) |

## Issues

Land under [issues/](issues/). All seven tasks audited CLEAN on the first `/clean-implement` cycle — see `task_0{1..7}_issue.md`.

## Outcome (2026-04-20)

All five exit criteria verified; the seven-task `/clean-implement` run closed with every audit `✅ PASS` on the first cycle.

| Exit criterion | Verification |
| --- | --- |
| 1. `planner` executes the two-phase sub-graph end-to-end (Qwen explore → Claude Code plan) | [`tests/workflows/test_planner_multitier_integration.py::test_full_hermetic_end_to_end_mixed_providers`](../../../tests/workflows/test_planner_multitier_integration.py) + live recording in the T07 close-out CHANGELOG. |
| 2. Tier override reroutes the explorer node without code change | [`tests/cli/test_tier_override.py::test_cli_tier_override_routes_synth_to_replacement_model`](../../../tests/cli/test_tier_override.py) at the CLI surface + [`tests/mcp/test_tier_override.py::test_run_workflow_applies_tier_overrides_to_replacement_route`](../../../tests/mcp/test_tier_override.py) at the MCP surface; both pin `models_seen` at the adapter boundary. |
| 3. MCP `run_workflow` accepts `tier_overrides` → identical behaviour | [`tests/mcp/test_tier_override.py`](../../../tests/mcp/test_tier_override.py) (7 cases); the shared dispatch helper in [`ai_workflows/workflows/_dispatch.py`](../../../ai_workflows/workflows/_dispatch.py) is the single plumbing point the CLI + MCP both call. |
| 4. `modelUsage` cost ledger records both Qwen (cost 0) and Claude Code (Opus + Haiku rollup) | [`tests/workflows/test_planner_multitier_integration.py::test_mixed_provider_cost_rollup`](../../../tests/workflows/test_planner_multitier_integration.py) asserts `tracker.total(run_id) == pytest.approx(0.0153)` across three rows (Qwen 0 + Opus 0.0150 + Haiku sub 0.0003). |
| 5. Gates green | `uv run pytest` → 366 passed, 2 skipped (both `AIW_E2E=1`-gated e2e); `uv run lint-imports` → 3/3 kept; `uv run ruff check` → clean. |

**Landed tasks:**

- [Task 01](task_01_qwen_explorer.md) — Qwen explorer tier refit. `planner-explorer` routed to `ollama/qwen2.5-coder:32b` via LiteLLM's Ollama driver (KDR-007); `max_concurrency=1`, `per_call_timeout_s=180`.
- [Task 02](task_02_claude_code_planner.md) — Claude Code planner tier refit. `planner-synth` repointed to `ClaudeCodeRoute(cli_model_flag="opus")` — first real dispatch of the M2 OAuth subprocess driver under a workflow graph. `max_concurrency=1`, `per_call_timeout_s=300`.
- [Task 03](task_03_subgraph_composition.md) — Sub-graph composition validation. Integration-only pass; `git diff ai_workflows/` returned empty — the M2 adapters abstracted every provider difference. Six hermetic tests cover cross-provider retry + cost rollup.
- [Task 04](task_04_tier_override_cli.md) — `aiw run --tier-override logical=replacement` (repeatable). `UnknownTierError` + `kind ∈ {logical, replacement}` added to `_dispatch.__all__` so both surfaces reuse one validation path.
- [Task 05](task_05_tier_override_mcp.md) — `RunWorkflowInput.tier_overrides: dict[str, str] | None`. MCP plumbing with `None`-default for byte-identical M4 backward compatibility; `UnknownTierError` translates to `ToolError` at the FastMCP boundary.
- [Task 06](task_06_e2e_smoke.md) — `AIW_E2E=1`-gated multi-tier + tier-override smokes. Default pytest stays hermetic; filesystem `anthropic` grep enforces KDR-003 at source level. Live run captured in the T07 CHANGELOG entry.
- [Task 07](task_07_milestone_closeout.md) — this close-out.

**Manual verification:** the walkthrough at [manual_smoke.md](manual_smoke.md) pairs with the automated e2e; T07's CHANGELOG entry records the live `aiw-mcp` round-trip against a fresh Claude Code session.

**Green-gate snapshot (2026-04-20):**

- `uv run pytest` — 366 passed, 2 skipped, 2 warnings.
- `uv run lint-imports` — 3/3 contracts kept.
- `uv run ruff check` — clean.
