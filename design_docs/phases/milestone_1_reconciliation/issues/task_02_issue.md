# Task 02 — Dependency Swap — Pre-build Audit Amendments

**Source task:** [../task_02_dependency_swap.md](../task_02_dependency_swap.md)
**Source audit:** [../audit.md](../audit.md) (produced by [M1 Task 01](../task_01_reconciliation_audit.md))
**Created on:** 2026-04-19
**Status:** 📋 PENDING BUILDER — gates not yet run; this file encodes pre-build amendments only. A cycle-1 post-build audit will overwrite with implementation findings.

## Why this file exists

Task files `task_02`…`task_13` were drafted **before** the reconciliation audit ran. Per [CLAUDE.md](../../../../CLAUDE.md) Builder conventions ("Issue file is authoritative amendment to task file"), this file is the bridge: it pulls the [audit.md](../audit.md) rows that target this task into the issue-file channel so `/implement m1 t2` sees them.

## Required reading order for Builder

1. [../../../architecture.md](../../../architecture.md) — KDRs cited in the rows below.
2. [../audit.md](../audit.md) — authoritative source. Every row whose Target task column names `task 02` applies here.
3. [../task_02_dependency_swap.md](../task_02_dependency_swap.md) — deliverables + ACs.
4. This file — any divergence between audit and task spec.
5. If audit and task disagree, **raise the conflict before implementing** per CLAUDE.md Builder conventions.

## Rows from audit.md this task must execute

### `[project].dependencies` REMOVE

| Dependency | Reason |
| --- | --- |
| `pydantic-ai>=1.0` | Replaced by LangGraph per KDR-001 / KDR-005. |
| `pydantic-graph>=1.0` | Hand-rolled DAG helper; LangGraph owns DAGs per KDR-001. |
| `pydantic-evals>=1.0` | Eval harness deferred to M7 per [roadmap.md](../../../roadmap.md). |
| `logfire>=2.0` | Observability is `StructuredLogger` only per [architecture.md §8.1](../../../architecture.md); hosted tracing is deferred — [nice_to_have.md §1/§3/§8](../../../nice_to_have.md). |
| `anthropic>=0.40` | No Anthropic API per KDR-003; Claude access is OAuth-only via the `claude` CLI subprocess. |

### `[project.optional-dependencies]` REMOVE

| Dependency | Reason |
| --- | --- |
| `dag = ["networkx>=3.0"]` | LangGraph replaces every hand-rolled DAG primitive per KDR-001; remove the entire extras group. |

### `[project].dependencies` ADD

| Dependency | Reason |
| --- | --- |
| `langgraph>=0.2` | DAG + checkpoint + interrupt substrate per KDR-001 / [architecture.md §6](../../../architecture.md). |
| `langgraph-checkpoint-sqlite>=1.0` | `SqliteSaver` is the only checkpoint implementation per KDR-009. |
| `litellm>=1.40` | Unified Gemini + Qwen/Ollama adapter per KDR-007. |
| `fastmcp>=0.2` | MCP server ergonomics per KDR-008 / [architecture.md §4.4](../../../architecture.md). |

### `[project].dependencies` KEEP (no change — listed so nothing is accidentally stripped)

- `httpx>=0.27` (transitive for LiteLLM)
- `pydantic>=2.0`
- `pyyaml>=6.0`
- `structlog>=24.0`
- `typer>=0.12`
- `yoyo-migrations>=9.0`

### `[dependency-groups].dev` KEEP (entire block unchanged)

- `import-linter>=2.0`, `pytest>=8.0`, `pytest-asyncio>=0.23`, `python-dotenv>=1.0`, `ruff>=0.5`.

### Non-dependency amendments

- `project.description` → `"Composable AI workflow framework built on LangGraph + MCP."` (drop the pydantic-ai reference).
- `tests/test_scaffolding.py` MODIFY — update the scaffolding smoke assertions to reference the new substrate deps after the swap.

## Known amendments vs. task spec

- **Aligned.** Task spec's REMOVE / ADD / KEEP lists match the audit exactly. `logfire` is confirmed REMOVE (task spec said "if audit classes it as REMOVE"); the audit is unambiguous.

## Carry-over from prior audits

_None. Task 01 raised ISS-01 against itself and resolved it inside the same cycle; no forward-deferred items to this task._

## Propagation status

Post-build audit of this task will overwrite this file with implementation findings.
