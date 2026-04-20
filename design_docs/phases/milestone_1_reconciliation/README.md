# Milestone 1 — Reconciliation & Cleanup

**Status:** ✅ Complete (2026-04-19).
**Grounding:** [architecture.md](../../architecture.md) · [analysis/langgraph_mcp_pivot.md](../../analysis/langgraph_mcp_pivot.md) · [roadmap.md](../../roadmap.md).

## Goal

Bring the pre-pivot M1 codebase into alignment with the new [architecture.md](../../architecture.md). Strip the pydantic-ai substrate, remove dead-weight tool-registry/caching code, retune `Storage` / `TierConfig` / `RetryPolicy` for the new layering, and leave a clean green-gate foundation for M2.

This milestone writes no new runtime behavior. It only subtracts what the archived design required and adjusts remaining primitives to the contracts in [architecture.md §4.1](../../architecture.md).

## Exit criteria

1. `uv run pytest`, `uv run lint-imports`, `uv run ruff check` all green.
2. `ai_workflows/` contains only code aligned with [architecture.md §4.1](../../architecture.md) plus a stubbed `aiw` CLI. No pydantic-ai imports remain.
3. `pyproject.toml` declares the new substrate deps (LangGraph, `langgraph-checkpoint-sqlite`, LiteLLM, FastMCP) and no longer declares `pydantic-ai`, `pydantic-graph`, `pydantic-evals`, `anthropic`, or any dep whose sole purpose was pydantic-ai integration (unless an ADR justifies keeping it).
4. `import-linter` enforces the four-layer contract from [architecture.md §3](../../architecture.md): `primitives → graph → workflows → surfaces`.
5. Each task below closes cleanly with its own acceptance checklist.

## Non-goals

- Implementing any LangGraph node (M2).
- Writing the LiteLLM adapter or `ClaudeCodeSubprocess` driver (M2).
- Touching the MCP surface (M4).
- Re-implementing CLI commands beyond stubs (M3+).

## Key decisions in effect

| Decision | Reference |
| --- | --- |
| LangGraph is the orchestrator substrate | KDR-001 |
| MCP is the portable surface | KDR-002 |
| No Anthropic API | KDR-003 |
| Validator after every LLM node (enforced from M2) | KDR-004 |
| Primitives layer preserved and owned | KDR-005 |
| Three-bucket retry taxonomy | KDR-006 |
| LiteLLM adapter for Gemini + Qwen/Ollama | KDR-007 |
| FastMCP for MCP server | KDR-008 |
| LangGraph `SqliteSaver` owns checkpoints | KDR-009 |

## Task order

Critical path: **T01 → T02 → T03** unblocks T04–T11 (these run in any order). **T12** closes the contracts after the packages it references are settled. **T13** is last.

| # | Task | Critical-path dep |
| --- | --- | --- |
| 01 | [Reconciliation audit](task_01_reconciliation_audit.md) | — |
| 02 | [Dependency swap](task_02_dependency_swap.md) | T01 |
| 03 | [Remove pydantic-ai LLM substrate](task_03_remove_llm_substrate.md) | T02 |
| 04 | [Remove tool registry + stdlib tools](task_04_remove_tool_registry.md) | T02 |
| 05 | [Trim Storage to run registry + gate log](task_05_trim_storage.md) | T03 |
| 06 | [Refit TierConfig + tiers.yaml](task_06_refit_tier_config.md) | T03 |
| 07 | [Refit RetryPolicy to 3-bucket taxonomy](task_07_refit_retry_policy.md) | T03 |
| 08 | [Prune CostTracker surface](task_08_prune_cost_tracker.md) | T03 |
| 09 | [StructuredLogger sanity pass](task_09_logger_sanity.md) | T03 |
| 10 | [`workflow_hash` decision + ADR](task_10_workflow_hash_decision.md) | T05 |
| 11 | [CLI stub-down](task_11_cli_stub_down.md) | T03 |
| 12 | [Import-linter contract rewrite](task_12_import_linter_rewrite.md) | T03–T11 |
| 13 | [Milestone close-out](task_13_milestone_closeout.md) | T01–T12 |

## Per-task acceptance checklist template

Each task doc carries this shape (filled per task):

- [ ] Read [architecture.md](../../architecture.md) + the M1 audit row ([task 01](task_01_reconciliation_audit.md)) for this concern.
- [ ] Implement the scoped change; touch only the listed files.
- [ ] Tests updated/added; `uv run pytest` green for the touched package.
- [ ] `uv run ruff check` + `uv run lint-imports` green.
- [ ] CHANGELOG.md entry under `[Unreleased]`.
- [ ] KDR / architecture § cited in commit message.

## Issues

Audit findings and blockers land under [issues/](issues/) following the existing `task_NN_issue.md` convention.

## Outcome (2026-04-19)

M1 landed clean on all five exit criteria. Every task 01–12 issue file
reads `✅ PASS`; task 13 ([task_13_issue.md](issues/task_13_issue.md))
closes the milestone.

### Dependencies swapped

[Task 02 — Dependency swap](task_02_dependency_swap.md) dropped
`pydantic-ai[*]`, `anthropic`, `pydantic-graph`, `pydantic-evals`,
`logfire`, `networkx`, `tenacity`, `platformdirs`, and added
`langgraph`, `langgraph-checkpoint-sqlite`, `litellm`, `fastmcp` per
[architecture.md §6](../../architecture.md). `pyproject.toml` is the
source of truth.

### Packages deleted

- [Task 03 — Remove pydantic-ai LLM substrate](task_03_remove_llm_substrate.md)
  deleted `ai_workflows/primitives/llm/` (`model_factory`, `types`,
  `caching`) and the matching tests.
- [Task 04 — Remove tool registry + stdlib tools](task_04_remove_tool_registry.md)
  deleted `ai_workflows/primitives/tools/` (registry, fs, shell, http,
  git, validators) and the matching tests.
- [Task 12 — Import-linter contract rewrite](task_12_import_linter_rewrite.md)
  deleted `ai_workflows/components/` (empty pre-pivot shell).

### Primitives retuned

- [Task 05 — Trim Storage to run registry + gate log](task_05_trim_storage.md) —
  `SQLiteStorage` reduced to `runs` + `human_gate_decisions`;
  LangGraph's `SqliteSaver` owns checkpoints (KDR-009).
- [Task 06 — Refit TierConfig + tiers.yaml](task_06_refit_tier_config.md) —
  `TierRegistry.load` replaces the eager `load_tiers` helper; two
  runtime tiers (`gemini_flash`, `local_coder`) per KDR-007.
- [Task 07 — Refit RetryPolicy to 3-bucket taxonomy](task_07_refit_retry_policy.md) —
  `RetryableTransient` / `RetryableRateLimited` / `NonRetryable` per
  KDR-006; `RetryingEdge` deferred to M2.
- [Task 08 — Prune CostTracker surface](task_08_prune_cost_tracker.md) —
  accept LiteLLM-enriched cost events, tighten the budget/cap path.
- [Task 09 — StructuredLogger sanity pass](task_09_logger_sanity.md) —
  structlog-only, no Logfire residue.

### `workflow_hash` decision

[Task 10 — `workflow_hash` decision + ADR-0001](task_10_workflow_hash_decision.md)
landed as **Option B — Remove**. See
[design_docs/adr/0001_workflow_hash.md](../../adr/0001_workflow_hash.md).
M3's drift-detect design owns any future replacement.

### CLI stubbed

[Task 11 — CLI stub-down](task_11_cli_stub_down.md) reduced
`ai_workflows/cli/` to `app = Typer(...)` + `version` command; runtime
subcommands (`run`, `resume`, `list-runs`, `inspect`) are reintroduced
in M3 when a workflow exists to drive.

### Import-linter contract

[Task 12 — Import-linter contract rewrite](task_12_import_linter_rewrite.md)
installed the four-layer contract from
[architecture.md §3](../../architecture.md):
`primitives → graph → workflows → surfaces`. Three `forbidden` contracts
in `pyproject.toml`. Empty `ai_workflows/graph/` and `ai_workflows/mcp/`
packages reserved for M2 and M4.

### Green-gate snapshot

Verified in [task_13_issue.md](issues/task_13_issue.md) as the
close-out audit; commands re-run by any future clone:

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ green |
| `uv run lint-imports` | ✅ 3 contracts kept / 0 broken |
| `uv run ruff check` | ✅ all checks passed |
| `grep -rn "pydantic_ai" ai_workflows/` | zero hits (source tree clean; test-side regression-guard assertions intentionally pin the string's absence per T03 audit) |
| `grep -r "ai_workflows.components" . --include="*.py" --include="*.toml"` | zero hits |
| `grep -rn "langfuse\|langsmith\|instructor\|docker-compose\|mkdocs\|deepagents\|opentelemetry" pyproject.toml ai_workflows/` | zero hits (no [nice_to_have.md](../../nice_to_have.md) adoption) |

### Orphaned script removed

`scripts/m1_smoke.py` was deleted as part of close-out: post-M1 it
imported six removed symbols (`pydantic_ai`, `llm.model_factory`,
`WorkflowDeps`, `load_tiers`, `BudgetExceeded`, `compute_workflow_hash`)
and could not be executed. A post-pivot smoke script is not required
until M3 has a runnable workflow; it will be reintroduced there.
Resolves forward-deferred carry-over
[M1-T06-ISS-04](issues/task_06_issue.md) and
[M1-T10-ISS-01](issues/task_10_issue.md).

### Next

[M2 — Graph-layer adapters + provider drivers](../milestone_2_graph/README.md)
is unblocked. M2 Task 01 picks up from the reserved
`ai_workflows.graph` package marker installed in T12.
