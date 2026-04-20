# ai-workflows — Roadmap

**Status:** Draft (2026-04-19). Sequences work following the 2026-04-19 LangGraph + MCP pivot.
**Grounding:** [architecture.md](architecture.md) · [analysis/langgraph_mcp_pivot.md](analysis/langgraph_mcp_pivot.md) · [nice_to_have.md](nice_to_have.md) (deferred — do not plan work from this doc without a trigger).

This roadmap replaces the archived milestone plan at `archive/pre_langgraph_pivot_2026_04_19/phases/`. Each milestone has its own directory under `phases/` containing a `README.md` and per-task files, matching the archived convention.

---

## Milestones

| # | Name | Directory | Status |
| --- | --- | --- | --- |
| **M1** | **Reconciliation & cleanup** | [phases/milestone_1_reconciliation/](phases/milestone_1_reconciliation/README.md) | ✅ complete (2026-04-19) |
| M2 | Graph-layer adapters + provider drivers | [phases/milestone_2_graph/](phases/milestone_2_graph/README.md) | ✅ complete (2026-04-19) |
| M3 | First workflow (`planner`, single tier) | [phases/milestone_3_first_workflow/](phases/milestone_3_first_workflow/README.md) | ✅ complete (2026-04-20) |
| M4 | MCP server (FastMCP) | [phases/milestone_4_mcp/](phases/milestone_4_mcp/README.md) | planned |
| M5 | Multi-tier `planner` | [phases/milestone_5_multitier_planner/](phases/milestone_5_multitier_planner/README.md) | planned |
| M6 | `slice_refactor` DAG | [phases/milestone_6_slice_refactor/](phases/milestone_6_slice_refactor/README.md) | planned |
| M7 | Eval harness | [phases/milestone_7_evals/](phases/milestone_7_evals/README.md) | planned |
| M8 | Ollama infrastructure | [phases/milestone_8_ollama/](phases/milestone_8_ollama/README.md) | planned |
| M9 | Claude Code skill packaging | [phases/milestone_9_skill/](phases/milestone_9_skill/README.md) | optional |

**Deferred (see [nice_to_have.md](nice_to_have.md)):** Langfuse, Instructor/pydantic-ai, LangSmith, Typer swap, Docker Compose, mkdocs, DeepAgents templates, standalone OTel. **No milestones for these until their trigger fires.**

---

## M2–M9 summaries

One-liners only; each gets a full `phases/` directory when the prior milestone closes clean.

- **M2 — Graph-layer adapters + provider drivers.** Build `TieredNode`, `ValidatorNode`, `HumanGate`, `CostTrackingCallback`, `RetryingEdge` in `ai_workflows.graph.*`. Ship the LiteLLM provider adapter and the `ClaudeCodeSubprocess` driver. No workflows yet — unit-testable node primitives only.
- **M3 — First workflow (`planner`, single tier).** One Gemini-tier `planner` `StateGraph` with validator + checkpoint (SqliteSaver) + human gate. CLI entry point revived (`aiw run planner …`). End-to-end smoke test.
- **M4 — MCP server (FastMCP).** Expose the five tools from [architecture.md §4.4](architecture.md). Schema-first pydantic contracts. stdio transport first; HTTP later if needed.
- **M5 — Multi-tier `planner`.** Qwen explore → Claude Code plan sub-graph. Exercises the tier-override path and the subprocess provider under a real workflow.
- **M6 — `slice_refactor` DAG.** Architecture's canonical use-case: planner sub-graph → parallel slice workers → per-slice validator → aggregate → strict-review gate → apply. Proves parallelism + strict-review.
- **M7 — Eval harness.** Prompt-regression guard. Captures input/expected pairs per workflow; replay on PR. Fulfils KDR-004's "prompting is a contract" promise.
- **M8 — Ollama infrastructure.** Health check, circuit breaker, fallback-to-Gemini gate. Needed once Qwen is load-bearing in M5/M6.
- **M9 — Claude Code skill packaging (optional).** `.claude/skills/ai-workflows/SKILL.md` wrapping `aiw` or the MCP server. Packaging only — no logic.

---

## Amendment rule

Milestone sequencing changes require a new KDR in [architecture.md §9](architecture.md) and an ADR under `design_docs/adr/`. Task-level changes within an active milestone are edited in-place in that milestone's `README.md` + task files.
