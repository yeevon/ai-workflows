# Inside-out vs Outside-in — Analysis for ai-workflows

**Status:** 📌 Decision taken 2026-04-19. Direction: **LangGraph-backed M4 + MCP-portable surface. Claude Code is one host among many, not the substrate.**

## Context

The M1 Task 13 spike proved the `claude` CLI can be driven headlessly and returns usable token/cost data. One observation from the findings — every opus/sonnet invocation spawns an internal `claude-haiku-4-5-20251001` sub-call — unsettled the broader architecture: we had been designing an **outside-in framework** (a Python orchestrator that treats `claude` as one provider) but the initial impulse was to pivot to pure **inside-out** (Claude Code *is* the orchestrator).

This document captures the analysis that led to rejecting both extremes in favour of a third option: **adopt LangGraph as the M4 orchestration substrate, expose the project as an MCP server for portability, and treat Claude Code as one MCP consumer among many (Cursor, Zed, OpenAI hosts, future agents).**

It is a design-mode document. No code changes are proposed here.

---

## A. What Claude Code actually is and isn't

| Primitive | What it is | Load-bearing for us? |
| --- | --- | --- |
| **Skills** (`.claude/skills/NAME/SKILL.md`) | Markdown instructions + optional files. No execution. | UX layer only — skills are prompts, not code. |
| **Subagents** (`.claude/agents/` + Task tool) | Separate conversation; optional `run_in_background:true`; fresh context per invocation. | Parallel fan-out, but cannot share in-session state. |
| **MCP servers** (stdio/HTTP JSON-RPC) | External process exposing tools/resources/prompts. | **The one real inside-out surface we can stand on.** |
| **Hooks** | Shell commands on PreToolUse / PostToolUse / SubagentStart / Stop. | Observability & guardrails, not orchestration. |
| **Slash commands** | Prompt templates, no execution. | Macros; softly deprecated by skills. |
| **Plugins** | Packaging wrapper for skills/agents/commands/MCP. | Distribution only. |
| **Headless** (`claude -p --output-format json`) | What Task 13 validated. | Used as a *provider*, not a platform. |

**Hard limitations that drive the decision:**

1. **Skills cannot execute Python in-process.** Any real work goes through Bash shell-out or an MCP call.
2. **No cross-session state / no DAG resume primitive.** We'd have to build it regardless.
3. **Subagents don't share state with siblings.** Shared state requires an external store.
4. **No native cost ledger across a session.** `CostTracker` is still required.
5. **The CLI's internal agent loop is not pluggable.** The haiku sub-call is baked in.
6. **Headless single-turn vs. interactive multi-turn have different semantics.** Mixing entry points is not free.

**Corollary:** "inside-out" does not eliminate the Python library. It moves the *entry point*.

## B. Why LangGraph wins M4

M4 as originally designed ships: DAG orchestrator, parallel branches, checkpointed resume, HumanGate with timeout, double-failure hard-stop, concurrency semaphores. **Every one of these is LangGraph's core competence.**

| M4 requirement | LangGraph primitive | Status |
| --- | --- | --- |
| DAG with parallel branches | `StateGraph` + conditional edges + built-in branching | ✅ native |
| Checkpoint + resume | `Checkpointer` (SQLite/Postgres) | ✅ native, durable |
| HumanGate | `interrupt()` + breakpoints | ✅ native; matches `strict_review=True` semantics |
| Double failure hard-stop | Edge conditions + reducer logic | ✅ expressible |
| Per-provider concurrency | Semaphores in node functions | ✅ trivial |
| Time-travel debugging | Built-in | ➕ bonus |
| Provider-agnostic | Yes — nodes are plain Python functions | ✅ Gemini/Qwen/claude_code all fine |

**Anthropic-API concern: resolved.** LangGraph does not force `langchain-anthropic`. Nodes call whatever the node author calls — `google-generativeai`, Ollama HTTP, the M4 Task 00 claude_code subprocess launcher. The memory-encoded provider strategy (Gemini + Qwen runtime, Claude Code as dev tool, **no Anthropic API**) is preserved.

**What this deletes from the roadmap:**
- Hand-rolled `Orchestrator` class and its DAG executor.
- Hand-rolled `aiw resume` state machine.
- Hand-rolled `HumanGate` with asyncio timeout plumbing.
- `Pipeline` becomes a transitional linear-graph special case (or gets deprecated outright).

**What stays:** every M1 primitive (storage, cost, tiers, providers, retry, logging, CLI) becomes the **project layer** that LangGraph nodes call into.

## C. Why MCP for portability

MCP is Anthropic's neutral inside-out protocol, adopted by OpenAI in March 2025, growing from ~100K to ~97M downloads in a year. Exposing ai-workflows as an MCP server:

- Gives the "live inside Claude Code" UX the user wants **without** coupling to Claude Code.
- Works in Cursor, Zed, VS Code (MCP support), and OpenAI hosts — same surface, zero extra code.
- Keeps the outside-in CLI path intact for CI and non-interactive use.
- Schema-first tool definitions (pydantic-validated) force explicit contracts — helps with the "prompting becomes more critical" concern.

**Planned MCP tool surface (design-mode sketch):**

- `run_workflow(workflow_id, inputs, tier_overrides?)` — submit a LangGraph run, return run id + streaming handle.
- `resume_run(run_id, gate_response?)` — drive a `strict_review` interrupt to the next checkpoint.
- `list_runs(filter?)` — query the run registry.
- `get_cost_report(run_id)` — aggregated `TokenUsage` + `modelUsage` ledger.
- `cancel_run(run_id)` — graceful abort.

## D. Limitations this pivot fixes

| Limitation (from § A) | Resolution |
| --- | --- |
| No cross-session DAG resume in Claude Code | LangGraph checkpointer outside the session |
| Subagents can't share in-session state | LangGraph `StateGraph` is the shared state |
| No native cost ledger | Project `CostTracker` remains canonical; exposed via MCP |
| CLI's internal agent loop not pluggable | Irrelevant — we don't override it, we consume it |
| Pure inside-out one-way door | MCP-neutral surface keeps the door open |

## E. Trade-off: prompting becomes more critical

The user flagged this correctly. Ceding orchestration to LangGraph and UX to hosts means **less deterministic Python control, more reliance on prompt + tool-schema contracts.** Mitigations:

1. **Schema-first MCP tools.** Pydantic in, pydantic out. Invalid inputs rejected at the boundary.
2. **Validator-node-after-every-LLM-node** pattern (carry forward from the original AgentLoop design — still useful as a LangGraph node type).
3. **Eval harness** for prompt regressions (new M-level task, replaces parts of the old AgentLoop scope).
4. **Structured logs + cost tracking** remain the operational safety net.
5. **Two-phase Planner** (Qwen explore → Opus plan) survives as a sub-graph pattern; value unchanged, now LangGraph-native.

## F. What survives, repurposes, or dies across the whole roadmap

| Concept | Status |
| --- | --- |
| `Storage` (SQLite) | ✅ Kept |
| `TokenUsage` / `CostTracker` | ✅ Kept; exposed via MCP |
| `TierConfig` + `pricing.yaml` | ✅ Kept |
| `RetryPolicy` + 3-bucket error taxonomy | ✅ Kept; applied at node + MCP boundary |
| `StructuredLogger` | ✅ Kept |
| `Pipeline` (linear) | ⚠️ Transitional — becomes a single-chain LangGraph; evaluate deprecation |
| `Orchestrator` (M4 hand-roll) | ❌ Replaced by LangGraph `StateGraph` |
| `AgentLoop` (M4 hand-roll) | ⚠️ Redesigned as a LangGraph node pattern, not a standalone class |
| `Planner` two-phase (M4) | ✅ Kept; expressed as a LangGraph sub-graph |
| `HumanGate` (M4 hand-roll) | ❌ Replaced by LangGraph `interrupt()` |
| `aiw resume` (M4 hand-roll) | ❌ Replaced by LangGraph checkpoint resumption |
| M4 Task 00 `claude_code` launcher | ✅ Kept; it's the subprocess provider a LangGraph node uses |
| `aiw` CLI | ✅ Kept; doubles as skill shell-out target |
| MCP server (`ai_workflows.mcp`) | ➕ **NEW** — first-class deliverable |
| Claude Code skill (`.claude/skills/ai-workflows/`) | ➕ **NEW — optional UX thin wrapper** |

## G. Why not the alternatives

- **Pure inside-out (Claude Code as the orchestrator):** one-way door. ChatGPT Plugins and OpenAI Assistants both walked it back. Half of M4's hard parts (DAG, resume, cost ledger, gate-with-timeout) are not provided by Claude Code and must be rebuilt anyway.
- **Stay pure outside-in with a hand-rolled orchestrator:** reinvents LangGraph; delays M4 by weeks; no portability gain.
- **Just use LangGraph agent templates without MCP:** possible but locks UX to the CLI; skips the portability win that solves the Claude Code coupling worry.

## Recommendation — single path

**Rewrite M4 around LangGraph + MCP. Archive the current milestone_2..milestone_7 design docs; treat this analysis as the new foundation. Keep the M1 implementation (code) intact.**

Concretely:

1. **M1 code stays as is.** Its primitives are the project layer that LangGraph nodes will call.
2. **Archive `design_docs/phases/milestone_2..7` and related top-level analyses** (they all assume a hand-rolled orchestrator path). Preserve them under `design_docs/archive/pre_langgraph_pivot_2026_04_19/` for historical reference.
3. **This analysis becomes the new foundation doc** at `design_docs/analysis/langgraph_mcp_pivot.md`.
4. **Draft a fresh roadmap** (separate follow-up task, not this plan) around:
   - M2 (new): LangGraph adapters over M1 primitives (`TierNode`, `CostTrackingCallback`, `RetryingNode`, `Checkpointer` binding to our `Storage`).
   - M3 (new): MCP server (`ai_workflows.mcp`) exposing `run_workflow`, `resume_run`, `list_runs`, `get_cost_report`.
   - M4 (new): First real LangGraph workflow (Planner + Validator + HumanGate) end-to-end.
   - M5 (new): `slice_refactor` DAG using the above.
   - Claude Code skill + plugin packaging: optional late-stage deliverable, not a milestone of its own.

## Next concrete steps

1. Archive `design_docs/phases/` and legacy top-level analyses (`analysis_summary.md`, `grill_me_results.md`, `search_analysis.md`, `worflow_initial_design.md`, `issues.md`) under `design_docs/archive/pre_langgraph_pivot_2026_04_19/`.
2. Place this analysis at `design_docs/analysis/langgraph_mcp_pivot.md` as the new foundation.
3. In a subsequent session (not this one), draft the new milestone plan around LangGraph + MCP.

## Verification (this plan)

- Archive directory exists and contains the previously-listed phase + analysis files.
- `design_docs/analysis/langgraph_mcp_pivot.md` exists with this content.
- M1 code under `ai_workflows/` is untouched (grep: no changes to `ai_workflows/`, `tiers.yaml`, `pricing.yaml`, `pyproject.toml`, or `tests/`).
- `CHANGELOG.md` receives a new entry under `[Unreleased]` noting the design-mode pivot decision (no code change).
