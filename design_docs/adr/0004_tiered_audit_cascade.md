# ADR-0004 — Tiered audit cascade

**Status:** Accepted (2026-04-21).
**Decision owner:** [M12 — Tiered audit cascade](../phases/milestone_12_audit_cascade/README.md).
**References:** [architecture.md §4.2](../architecture.md) · [architecture.md §4.4](../architecture.md) · [architecture.md §9](../architecture.md) · KDR-003 · KDR-004 · KDR-006 · KDR-011 (added by this ADR).
**Supersedes:** nothing. First codification of a cross-tier review pattern in this project.

## Context

The runtime provider set after the 2026-04-19 pivot is **Gemini** (via LiteLLM, free-tier), **Qwen/Ollama** (local), and **Claude Max** accessed OAuth-only through the `claude` CLI subprocess (KDR-003 — no Anthropic HTTP API). Only one tier today routes to the Claude Max subscription: [`planner-synth`](../../ai_workflows/workflows/planner.py) uses `ClaudeCodeRoute(cli_model_flag="opus")`. The Gemini / Qwen tiers carry the bulk of generative work under current workflows.

Two structural concerns sit under that split:

1. **Quality ceiling of the small tiers.** Gemini Flash and Qwen at the sizes we run locally are materially weaker at long-context synthesis, code critique, and specification drafting than Opus. `ValidatorNode` (KDR-004) enforces *shape* (schema parse), not *content quality*. A shaped-correct but semantically weak artefact flows downstream without any audit. As workflows thread more generation through the small tiers, this gap accumulates into user-visible drift.
2. **Cost asymmetry at the Max tier.** Opus is quota-bounded by the Max subscription, which is a **flat, shared pool** across `opus` / `sonnet` / `haiku` — the same pool your interactive Claude Code session draws on. Defaulting every workflow to Opus would exhaust the pool, surfacing as [nice_to_have.md §?](../nice_to_have.md) (Max quota overage trigger). Using smaller CLI tiers (`sonnet`, `haiku`) stays inside the pool but inherits the same quality concern as Gemini/Qwen.

The `ClaudeCodeSubprocess` driver already accepts `--model sonnet` and `--model haiku` as first-class CLI flags alongside `--model opus` — see [claude_code.py:9](../../ai_workflows/primitives/llm/claude_code.py#L9), [claude_code.py:119-129](../../ai_workflows/primitives/llm/claude_code.py#L119-L129). Adding those as runtime tiers requires zero driver work, zero new dependencies, and preserves KDR-003 (OAuth CLI subprocess; no `anthropic` SDK import, no `ANTHROPIC_API_KEY` read). The mechanism for inserting a **higher-tier auditor** between primary generation and downstream consumption is therefore in reach without expanding the architectural footprint.

The M9 T04 close-out live smoke (2026-04-21) surfaced the adjacent UX concern that a **human**-in-the-loop review at gate pause is currently blind (ISS-02 — `RunWorkflowOutput.plan` is `null` at gate pause). That fix lands in M11 and is a precondition for the cascade's *failure-escalation* path (auditor exhausts retries → HumanGate surfaces the cascade context to the operator for manual arbitration). M11 ships before M12.

## Decision

**Introduce a tiered audit cascade as the KDR-004 quality surface.** Concretely:

1. **Auditor tiers are a pair.** `auditor-sonnet` routes to `ClaudeCodeRoute(cli_model_flag="sonnet")`; `auditor-opus` routes to `ClaudeCodeRoute(cli_model_flag="opus")`. Both sit in the `TierRegistry` (`ai_workflows/primitives/tiers.py`) next to `planner-synth`. No new driver, no new LiteLLM route, no new env var.

2. **Cascade wraps generative nodes whose output is read downstream.** A node's output qualifies if it is consumed by another graph node or surfaced to the user. Scratchpad / explore-only output is **out of scope** — auditing it would erase the cost rationale of the small tier.

3. **Audit tier is one level above the author.**
   - Haiku, Gemini, Qwen production → audited by **`auditor-sonnet`**.
   - Sonnet production → audited by **`auditor-opus`**.
   - Opus production → **not audited** (no higher tier; self-audit adds no signal).

4. **Cascade is inline per-node, not post-hoc.** Implemented as a new graph primitive `AuditCascadeNode` (`ai_workflows/graph/audit_cascade.py`) that composes `TieredNode(primary)` → `ValidatorNode(shape)` → `TieredNode(auditor)` → `AuditVerdictNode` into a single sub-graph. On failure the primary node re-fires via `RetryingEdge` (KDR-006 `RetryableSemantic` bucket) with the auditor's structured error context + suggested fix rendered into the next prompt — not a raw retry. After bounded retries (defaults: 3 attempts), failure routes to a strict `HumanGate` carrying the full cascade transcript for manual arbitration.

5. **Cascade is opt-in per workflow.** Each workflow declares `audit_cascade_enabled: bool = False` on its config surface. Default off for M12 landing. Runtime flip via `AIW_AUDIT_CASCADE=1` env override is available for ad-hoc testing. Opt-in is the mechanism for rolling the cascade out workflow-by-workflow while Max quota behaviour is empirically observed.

6. **Telemetry is load-bearing.** Each cascade step records `TokenUsage` with a `role` tag (`"author"` / `"auditor"` / `"verdict"`) so the existing ledger surfaces *Opus vs Sonnet vs small-tier* usage per run. Aggregation queries (`by_role`, `by_audit_outcome`) feed the empirical-tuning loop that decides when to flip a workflow's `audit_cascade_enabled` default to `True`, widen/narrow the scope rule, or promote/demote an auditor tier.

7. **Standalone invocation surface.** A new MCP tool `run_audit_cascade(artefact_ref, tier_ceiling?) → AuditReport` plus a companion slash-command entry in `.claude/skills/ai-workflows/SKILL.md` lets a caller run the cascade over an **existing** artefact (a completed plan, a draft spec, a generated code slice) without kicking off a full workflow. Internal routing reuses the same `AuditCascadeNode`; the MCP tool is a thin surface wrapper. The standalone surface is for ad-hoc auditing (spot-check a plan before committing it, audit a doc change before push) and is load-bearing for end-to-end testing of the cascade independently of any workflow.

## Rationale

- **Preserves KDR-003.** The entire cascade lives in `ClaudeCodeRoute` space. `ClaudeCodeSubprocess` spawns `claude --print --model <tier> ...` — OAuth, no API. No edit to the ban on the `anthropic` SDK. The M12 implementation grep-checks this explicitly in the test suite, mirroring the M1 T03 discipline.
- **Composes over KDR-004, doesn't replace it.** The existing `ValidatorNode` stays exactly where it is (shape validation). The auditor is a *semantic* layer on top, which is what the validator was never meant to be (ADR-0002's rationale — bound-checking and semantic enforcement are validator concerns, but the validator's role was scoped to shape + post-parse assertions, not cross-model review).
- **Inline cascade beats post-hoc audit.** A post-hoc audit pass over a completed run's artefact can flag quality issues but cannot **halt** the graph mid-run. Inline cascade lets the author re-fire with context on semantic failure, preventing downstream waste (a bad plan that fans out into ten slice-workers costs ten-fold the small-tier budget to discover post-hoc). KDR-006's `RetryableSemantic` bucket already owns the re-fire-with-revision-guidance pattern; the cascade's verdict feeds it natively.
- **Scope rule = "read downstream" is the sharp line.** Auditing every TieredNode emission would multiply per-run LLM calls by 2-3× **including for scratchpad output that nobody reads** — the quality gain is zero, the cost is linear. Limiting to downstream-consumed output preserves the majority of the savings that motivated using small tiers in the first place, per user guidance (2026-04-21).
- **Re-prompt with enriched context > raw retry.** User-stated (2026-04-21): "With context added with errors and how to approach solution not just dump retry." The auditor's structured response carries `failure_reasons: list[str]` and `suggested_approach: str | None`; both are rendered into the next primary prompt via the `AuditCascadeNode`'s re-prompt template. This is strictly richer than a bare `ModelRetry(revision_guidance="try again")` and matches the human-mentor loop the audit cascade is modelled on.
- **Opt-in + telemetry before defaults flip.** User-stated (2026-04-21): "c) but make sure we flag after some heavy testing and tracking claude tokens which we should save even if there is no cost so we know how to tweak." Flipping defaults on without telemetry is how quota surprises happen; opt-in per workflow + `by_role` usage aggregation lets us flip *data-driven*, not *vibes-driven*. The Max subscription being flat-rate does not remove the need to track — quota is finite, and the empirical tuning loop needs raw token counts to reason about cascade depth, scope rule tightness, and tier-pair choice.
- **Standalone MCP tool is the cascade's second surface.** The cascade lives in the graph layer as a primitive, is consumed by workflows (inline) and by the standalone MCP tool (one-shot invocation). Two consumers validate that the primitive is correctly factored — any coupling that only surfaces under a workflow context would fail the standalone test, and vice versa. This mirrors the M7 evals split (`graph` is evals-unaware, `workflows` and `surfaces` both consume evals).

## Consequences

- **New primitive.** `AuditCascadeNode` lands in `ai_workflows/graph/audit_cascade.py` (M12 T02). Fits the existing four-layer contract (graph imports only primitives; workflows / surfaces import graph). No import-linter edit needed.
- **New TierConfigs.** `auditor-sonnet` + `auditor-opus` land in `ai_workflows/primitives/tiers.py` (M12 T01) with matching pricing entries. Pricing is **$0 per million tokens** — Max is flat-rate; the zero price keeps `CostTracker`'s ledger shape intact without introducing a fiction about per-call cost. Usage is still recorded in tokens for the empirical-tuning loop.
- **New MCP tool.** `run_audit_cascade` lands in `ai_workflows/mcp/server.py` (M12 T05) with paired pydantic input/output schemas. Skill gets a matching natural-language entry.
- **Workflow opt-in field.** Each existing workflow's config model grows an `audit_cascade_enabled: bool = False` field (M12 T03). Landing the field without any workflow flipping it on preserves backwards compatibility.
- **Eval harness gains cascade fixtures.** M7's `EvalRunner` replay-path already handles multi-node sub-graphs; the cascade's author + auditor nodes capture independently under `evals/<workflow>/<node>/` with role-tagged filenames (`author_<case_id>.json` / `auditor_<case_id>.json`). No M7 engine change required; fixture convention only.
- **Budget-guard tension.** `CostTracker.total(run_id)` against the per-run `budget_usd` (architecture.md §8.5) is presently zero-cost under Claude Max (Opus rate is $0). Cascade does not change this. If the Max quota overage trigger fires ([nice_to_have.md](../nice_to_have.md) — track) and per-tier dollar pricing returns, the cascade multiplies cost, and the budget-guard becomes the natural kill-switch.
- **No CI path change.** `uv run pytest` / `uv run lint-imports` / `uv run ruff check` cover the new primitive + tier-config + MCP tool the same way they cover every other addition. No new gate.

## Alternatives considered and rejected

- **Post-hoc audit pass over a completed run.** Cheap (one audit call per artefact) but cannot short-circuit the graph; a bad plan fans out into full slice-worker cost before discovery. Rejected for cost-of-downstream-waste.
- **Opus-repair on Sonnet audit failure** (a third tier in the cascade that *fixes* the artefact itself, rather than re-prompting the author). Rejected for blurring author / auditor separation — the auditor becomes responsible for both grading and rewriting, which is the same failure mode that makes unpaired LLM-self-critique unreliable. User-stated (2026-04-21): "a) then c)" — re-prompt with context, then HumanGate on exhaustion. No Opus-repair tier.
- **Default-on cascade.** Rejected. Without per-workflow telemetry showing where the cascade actually improves output, default-on converts every existing workflow into a 2-3× quota consumer overnight. Opt-in lets us roll workflow-by-workflow once each workflow's audit-yield is observed. User-stated (2026-04-21): "c) but make sure we flag after some heavy testing and tracking claude tokens."
- **Anthropic API for the auditor tiers.** Rejected. KDR-003 forbids it, and the Claude Code CLI subprocess already provides OAuth-backed access to the exact same models. No justification for reintroducing the API surface.
- **Combining M11 (gate-review) + M12 (cascade) into one milestone.** User confirmed 2026-04-21: "confirmtionation we are creating milestone 11 and 12 not combining both issues." Split preserves clean green-gates — M11 is a pure MCP surface diff, M12 is a pure graph/workflows diff.

## References

- [architecture.md §4.2](../architecture.md) — graph-layer adapters (TieredNode, ValidatorNode, RetryingEdge, HumanGate; grows AuditCascadeNode at M12 T02).
- [architecture.md §4.4](../architecture.md) — MCP surface (grows `run_audit_cascade` tool at M12 T05).
- [architecture.md §9](../architecture.md) — KDR index (grows KDR-011 at M12 T02).
- KDR-003 — no Anthropic API. Preserved.
- KDR-004 — validator-node-after-every-LLM-node. Auditor is a semantic layer *on top* of shape validation; composition, not replacement.
- KDR-006 — three-bucket retry taxonomy. Auditor failure feeds `RetryableSemantic`.
- KDR-011 — this ADR's codified form in the KDR index.
- [ClaudeCodeSubprocess](../../ai_workflows/primitives/llm/claude_code.py) — driver the cascade reuses verbatim.
- [M11 — MCP gate-review surface](../phases/milestone_11_gate_review/README.md) — the upstream UX fix the cascade's failure-escalation path relies on.
- [M12 — Tiered audit cascade](../phases/milestone_12_audit_cascade/README.md) — the execution plan for this ADR.
- [M9 T04 issue file — ISS-02](../phases/milestone_9_skill/issues/task_04_issue.md) — discovery point of the upstream gate-review gap.
