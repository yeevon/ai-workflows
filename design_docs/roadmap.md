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
| M4 | MCP server (FastMCP) | [phases/milestone_4_mcp/](phases/milestone_4_mcp/README.md) | ✅ complete (2026-04-20) |
| M5 | Multi-tier `planner` | [phases/milestone_5_multitier_planner/](phases/milestone_5_multitier_planner/README.md) | ✅ complete (2026-04-20) |
| M6 | `slice_refactor` DAG | [phases/milestone_6_slice_refactor/](phases/milestone_6_slice_refactor/README.md) | ✅ complete (2026-04-20) |
| M7 | Eval harness | [phases/milestone_7_evals/](phases/milestone_7_evals/README.md) | ✅ complete (2026-04-21) |
| M8 | Ollama infrastructure | [phases/milestone_8_ollama/](phases/milestone_8_ollama/README.md) | ✅ complete (2026-04-21) |
| M9 | Claude Code skill packaging | [phases/milestone_9_skill/](phases/milestone_9_skill/README.md) | ✅ complete (2026-04-21) |
| M10 | Ollama fault-tolerance hardening | [phases/milestone_10_ollama_hardening/](phases/milestone_10_ollama_hardening/README.md) | planned |
| M11 | MCP gate-review surface | [phases/milestone_11_gate_review/](phases/milestone_11_gate_review/README.md) | planned |
| M12 | Tiered audit cascade | [phases/milestone_12_audit_cascade/](phases/milestone_12_audit_cascade/README.md) | planned |
| M13 | v0.1.0 release + PyPI packaging | [phases/milestone_13_v0_release/](phases/milestone_13_v0_release/README.md) | planned |

**Deferred (see [nice_to_have.md](nice_to_have.md)):** Langfuse, Instructor/pydantic-ai, LangSmith, Typer swap, Docker Compose, mkdocs, DeepAgents templates, standalone OTel. **No milestones for these until their trigger fires.**

---

## M2–M13 summaries

One-liners only; each gets a full `phases/` directory when the prior milestone closes clean.

- **M2 — Graph-layer adapters + provider drivers.** Build `TieredNode`, `ValidatorNode`, `HumanGate`, `CostTrackingCallback`, `RetryingEdge` in `ai_workflows.graph.*`. Ship the LiteLLM provider adapter and the `ClaudeCodeSubprocess` driver. No workflows yet — unit-testable node primitives only.
- **M3 — First workflow (`planner`, single tier).** One Gemini-tier `planner` `StateGraph` with validator + checkpoint (SqliteSaver) + human gate. CLI entry point revived (`aiw run planner …`). End-to-end smoke test.
- **M4 — MCP server (FastMCP).** Expose the five tools from [architecture.md §4.4](architecture.md). Schema-first pydantic contracts. stdio transport first; HTTP later if needed.
- **M5 — Multi-tier `planner`.** Qwen explore → Claude Code plan sub-graph. Exercises the tier-override path and the subprocess provider under a real workflow.
- **M6 — `slice_refactor` DAG.** Architecture's canonical use-case: planner sub-graph → parallel slice workers → per-slice validator → aggregate → strict-review gate → apply. Proves parallelism + strict-review.
- **M7 — Eval harness.** Prompt-regression guard. Captures input/expected pairs per workflow; replay on PR. Fulfils KDR-004's "prompting is a contract" promise.
- **M8 — Ollama infrastructure.** Health check, circuit breaker, fallback-to-Gemini gate. Needed once Qwen is load-bearing in M5/M6.
- **M9 — Claude Code skill packaging (optional).** `.claude/skills/ai-workflows/SKILL.md` wrapping `aiw` or the MCP server. Packaging only — no logic.
- **M10 — Ollama fault-tolerance hardening.** Closes the design-rationale and UX gaps in M8's fault-tolerance surface that were surfaced by the 2026-04-21 M8 deep-analysis pass: retroactive ADR for the `fallback_tier="planner-synth"` choice, RETRY-cooldown guidance in the gate prompt, invariant tests for the single-gate-per-run pattern and the `_mid_run_tier_overrides` Send-payload carry, documented process-local breaker scope, and five new `nice_to_have.md` entries (multi-process breaker, empirical tuning, second-level fallback chain, single-gate factory refactor, Gemini-tier breakers). Composes over existing KDRs — no new KDR.
- **M11 — MCP gate-review surface.** Closes the M9 T04 live-smoke finding (ISS-02): at a plan-review gate pause the MCP `RunWorkflowOutput` / `ResumeRunOutput` return `plan: null`, so the operator and the Claude Code skill have nothing to review. M11 projects the in-flight draft plan (and any other gate-relevant state) into the MCP output at `status="pending", awaiting="gate"`, not only on terminal completion. Pure MCP-surface diff; no graph/workflow change. Precondition for M12's cascade-failure HumanGate escalation path (operator needs reviewable state to arbitrate). No new KDR — composes over KDR-002 + KDR-008.
- **M12 — Tiered audit cascade.** Ships KDR-011 + [ADR-0004](adr/0004_tiered_audit_cascade.md): new `AuditCascadeNode` graph primitive + `auditor-sonnet`/`auditor-opus` TierConfigs + per-workflow `audit_cascade_enabled` opt-in + role-tagged `TokenUsage` telemetry + a `run_audit_cascade` MCP tool for standalone artefact audit. Auditor tiers route via the existing `ClaudeCodeSubprocess` over the OAuth CLI (`--model sonnet` / `--model opus`) — KDR-003 preserved, zero `anthropic` SDK surface. Cascade is inline, opt-in default-off, routes failure through `RetryingEdge` with the auditor's `failure_reasons` + `suggested_approach` re-rendered into the next primary prompt, and escalates to a strict `HumanGate` (M11-visible) on retry exhaustion. Depends on M11.
- **M13 — v0.1.0 release + PyPI packaging.** The project's first distributable release. Polishes `pyproject.toml` metadata (authors, URLs, classifiers, keywords), fixes the hatchling wheel-contents bug (`migrations/` is currently silently omitted from the wheel — breaks first-run `yoyo-migrations` on any `uvx` / `uv tool install` install), adds an "Install from PyPI" section to the root README covering `uvx --from ai-workflows aiw run …` + `uv tool install ai-workflows`, extends [`skill_install.md`](phases/milestone_9_skill/skill_install.md) with a `uvx`-based MCP-server install option (`claude mcp add ai-workflows -- uvx --from ai-workflows aiw-mcp`), adds a `CHANGELOG.md [0.1.0]` release section, and publishes `0.1.0` to PyPI via a manual `uv publish` run gated by a release-smoke script. **Depends on M11** (publishing before the gate-review projection lands would ship a broken first-impression skill UX). M10/M12 are *not* prerequisites — they consolidate into a later 0.2.x release. Packaging-only milestone; no runtime feature, no new KDR.

---

## Amendment rule

Milestone sequencing changes require a new KDR in [architecture.md §9](architecture.md) and an ADR under `design_docs/adr/`. Task-level changes within an active milestone are edited in-place in that milestone's `README.md` + task files.
