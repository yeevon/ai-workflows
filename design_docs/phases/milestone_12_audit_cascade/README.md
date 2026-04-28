# Milestone 12 — Tiered Audit Cascade

**Status:** 📝 Planned (drafted 2026-04-21).
**Grounding:** [ADR-0004](../../adr/0004_tiered_audit_cascade.md) · [architecture.md §4.2 / §4.4 / §9 KDR-011](../../architecture.md) · [roadmap.md](../../roadmap.md) · [M11 README](../milestone_11_gate_review/README.md) (precondition).

## Why this milestone exists

The runtime provider set after the 2026-04-19 pivot puts the bulk of generative work on **Gemini** (free-tier, LiteLLM) and **Qwen/Ollama** (local). Opus via Claude Code CLI is used by one tier today (`planner-synth`). Two structural concerns sit under that split (full discussion in [ADR-0004](../../adr/0004_tiered_audit_cascade.md)):

1. **Quality ceiling of the small tiers.** `ValidatorNode` (KDR-004) enforces *shape*, not *content quality*. Shape-correct but semantically weak output from Gemini/Qwen flows downstream unaudited.
2. **Cost asymmetry at the Max tier.** Opus is quota-bounded by a flat Max subscription pool shared with your interactive Claude Code session. Defaulting every workflow to Opus blows the pool; defaulting to small tiers inherits the quality gap.

The mechanism to close this is a **tiered audit cascade**: pair every generative LLM node whose output is read downstream with an auditor one tier above (Haiku/Gemini/Qwen → `auditor-sonnet`; Sonnet → `auditor-opus`; Opus is not audited). The cascade is inline, opt-in per workflow, routes audit failure via `RetryingEdge` with enriched context, and escalates to a HumanGate on retry exhaustion. The `ClaudeCodeSubprocess` driver already accepts `--model sonnet` and `--model haiku` flags alongside `--model opus` — auditor tiers are new `TierConfig` entries over the existing driver, **zero** new dependency, KDR-003 preserved.

## Goal

1. Ship the auditor **tiers** (`auditor-sonnet`, `auditor-opus`) as `TierConfig` entries routing via the existing `ClaudeCodeSubprocess`.
2. Ship the **`AuditCascadeNode`** graph primitive that composes `TieredNode(primary) → ValidatorNode(shape) → TieredNode(auditor) → AuditVerdictNode` into a reusable sub-graph.
3. Wire a **per-workflow opt-in** (`audit_cascade_enabled: bool = False`) into the existing workflow configs. M12 lands the field; no workflow flips it on at M12 landing. Data-driven flips happen post-M12 based on the telemetry the cascade records.
4. Record **role-tagged `TokenUsage`** (`role ∈ {author, auditor, verdict}`) on every cascade step so `CostTracker` surfaces Opus/Sonnet/small-tier splits per run. This is the empirical surface the post-M12 tuning loop consumes.
5. Expose a **`run_audit_cascade` MCP tool** + matching SKILL.md entry for ad-hoc auditing of an existing artefact (completed plan, draft spec, generated code slice) outside a full workflow.
6. Ship an **eval harness fixture convention** for cascade author/auditor node pairs so M7's `EvalRunner` can replay either node independently.

## Exit criteria

1. ✅ (T01 complete 2026-04-27) `auditor-sonnet` and `auditor-opus` `TierConfig` entries exist in the workflow tier registries (`planner.py`, `summarize_tiers.py`; `slice_refactor.py` inherits via composition), routing via `ClaudeCodeRoute(cli_model_flag="sonnet")` / `ClaudeCodeRoute(cli_model_flag="opus")`. Pricing covered by existing `pricing.yaml` (rates = $0; Max is flat-rate — see ADR-0004 §*Consequences*). KDR-003 guardrail tests pass. Note: landing site is workflow modules (not `primitives/tiers.py`) per T01 §Deliverables; ADR-0004 §Decision item 1 framing is stale (TA-LOW-03 — flag for milestone close-out).
2. ✅ (T02 complete 2026-04-27) `ai_workflows/graph/audit_cascade.py` — `AuditCascadeNode` primitive exists, compiles a sub-graph from `(primary_tier, primary_prompt_fn, primary_output_schema, auditor_tier)`, and returns a `CompiledStateGraph` composable into any outer `StateGraph`. Auditor prompt renders the primary's output verbatim + primary prompt context + the verdict schema. The audit verdict is a pydantic model with `passed: bool`, `failure_reasons: list[str]`, `suggested_approach: str | None`. On verdict `passed=False`, the sub-graph raises `AuditFailure` (new exception in `primitives/retry.py` — bucketed `RetryableSemantic` under KDR-006) carrying the verdict payload. `RetryingEdge` is the retry surface; the cascade does not hand-roll a retry loop.
3. ✅ (T02 complete 2026-04-27) `RetryingEdge` re-fire path renders `failure_reasons` + `suggested_approach` into the primary prompt's `revision_guidance` block on the next attempt — not a raw retry. Hermetic test pins the shape of the re-prompt (a `{primary_original}\n\n<audit-feedback>…</audit-feedback>\n\n{primary_context}` template; exact string asserted).
4. ✅ (T02 complete 2026-04-27) After `RetryPolicy.max_semantic_attempts` re-fires, the cascade routes to a strict `HumanGate`. The gate carries the full cascade transcript (`{author_attempts: list[str], auditor_verdicts: list[AuditVerdict]}`) in its state channel; the M11 gate-context projection surfaces those keys at MCP boundary.
5. ✅ (T03 complete 2026-04-27) `planner` and `slice_refactor` carry module-level `_AUDIT_CASCADE_ENABLED_DEFAULT = False` + `_AUDIT_CASCADE_ENABLED` constants (ADR-0009 / KDR-014 — quality knobs must NOT land on `*Input` models). `AIW_AUDIT_CASCADE=1` (global) or `AIW_AUDIT_CASCADE_PLANNER=1` / `AIW_AUDIT_CASCADE_SLICE_REFACTOR=1` (per-workflow) env-var overrides flip the constant at module-import time. Both workflows stay `False` by default. The opt-in *wiring* is integrated (i.e. setting the env var works end-to-end without re-plumbing). Note: original spec said `*Input` field; KDR-014 / ADR-0009 mandate module-level constant instead — see task_03 spec §Locked decision 3.
6. ✅ (T04 complete 2026-04-27) `TokenUsage` records from cascade steps carry a `role` tag (`"author"` | `"auditor"` | `"verdict"`). `CostTracker` grows a `by_role(run_id)` aggregation helper returning `dict[role, float]`. Existing `by_tier` / `by_model` aggregations unaffected. Role-tagged records land in `llm_calls` (or wherever `CostTracker` currently persists; respects KDR-009 / M1 T05 for the ledger storage choice).
7. [x] (T05 complete 2026-04-28) `ai_workflows/mcp/server.py` — new `@mcp.tool()` `run_audit_cascade(input: RunAuditCascadeInput) -> RunAuditCascadeOutput`. Input: `artefact_ref: str` (a completed `run_id`, or a file path under a sandboxed root, or an inline dict — one-of); optional `tier_ceiling: Literal["sonnet", "opus"] = "opus"`. Output: `passed: bool`, `verdicts_by_tier: dict[str, AuditVerdict]`, `suggested_approach: str | None`, `total_cost_usd: float`. Implementation: Option A (H1 locked 2026-04-27) — bypasses `AuditCascadeNode`, invokes auditor `tiered_node` directly; caller supplies `artefact_kind` (H2 Option A). See T05 spec.
8. [x] (T05 complete 2026-04-28) `.claude/skills/ai-workflows/SKILL.md` — new "Ad-hoc artefact audit" section documenting when + how to call `run_audit_cascade`.
9. `evals/<workflow>/<node>/` fixture convention gains an author/auditor split: `author_<case_id>.json` + `auditor_<case_id>.json` land as two independent fixtures captured by the `CaptureCallback` whose existing role-tag can be read. No change to `EvalRunner`'s engine; fixture-naming convention only. One golden test per workflow that opts into the cascade.
10. `tests/graph/test_audit_cascade.py` + `tests/workflows/test_audit_cascade_wiring.py` — hermetic coverage of: cascade pass-through (auditor passes on first try), cascade re-fire (auditor fails → primary re-prompts with enriched context → auditor passes), cascade escalation (retries exhausted → strict gate fires with transcript), opt-out default (`audit_cascade_enabled=False` compiles an identical-to-M11 graph), opt-in roundtrip (`audit_cascade_enabled=True` compiles the cascade sub-graph in place of raw `TieredNode`).
11. ✅ (T02 complete 2026-04-27) Gates green: `uv run pytest` + `uv run lint-imports` (**5 contracts kept** — a new contract is added at M12 T02 to pin the cascade primitive as graph-layer; see T02 spec) + `uv run ruff check`. Count jumps from 4 to 5 because the cascade adds a new cross-file dependency that the contract pins against drift.
12. ✅ (T02 complete 2026-04-27) No `anthropic` SDK import anywhere. No `ANTHROPIC_API_KEY` read. Hermetic grep test extended over the new modules.

## Non-goals

- **No default-on cascade.** M12 lands opt-in default-off on every workflow. Flipping defaults requires post-M12 telemetry analysis and either a new task (M13+) or a `nice_to_have.md` entry with a trigger. See ADR-0004 §*Alternatives*.
- **No Opus-repair tier.** The cascade is author + auditor. A third "fixer" tier that re-writes the author's output on audit failure is rejected — see ADR-0004 §*Alternatives*.
- **No shared-quota circuit breaker for the Max pool.** Max quota exhaustion is a known future trigger ([nice_to_have.md](../../nice_to_have.md) — track) but M12 does not ship the breaker. The `CostTracker.budget_cap_usd` field is the natural kill-switch once per-tier dollar pricing returns.
- **No extension of the audit cascade to the LiteLLM tiers as auditor.** Auditors are Claude-tier only at M12. A Gemini-Pro-auditing-Gemini-Flash configuration is a forward option, not an M12 deliverable.
- **No Anthropic API.** KDR-003 preserved across all M12 deliverables. Hermetic grep enforces.
- **No cascade for surface tests / CI fast paths.** `AIW_EVAL_LIVE=1` gates still apply to live cascade replay.

## Key decisions in effect

| Decision | Reference |
| --- | --- |
| Tiered audit cascade — pair auditor one tier above author; inline, opt-in, RetryingEdge-driven failure path; HumanGate on exhaust | [KDR-011](../../architecture.md) · [ADR-0004](../../adr/0004_tiered_audit_cascade.md) |
| OAuth CLI subprocess is the only Claude transport | KDR-003 |
| Validator-after-every-LLM-node (shape) is retained; auditor is a semantic layer on top | KDR-004 |
| Retry taxonomy — cascade audit failure → `RetryableSemantic` | KDR-006 |
| Checkpointer remains LangGraph-owned — transcript keys land in graph state, not a new persistence table | KDR-009 |
| MCP tool schemas are the public contract — `run_audit_cascade` is additive, non-breaking | KDR-008 |
| Gate-review surface projection — M11 is the precondition for operator-visible cascade transcripts at HumanGate | [M11 README](../milestone_11_gate_review/README.md) |

## Task order

| # | Task | Kind | Status |
| --- | --- | --- | --- |
| 01 | [Auditor TierConfigs — `auditor-sonnet` + `auditor-opus`](task_01_auditor_tier_configs.md) | code + test | ✅ Complete (2026-04-27) |
| 02 | [`AuditCascadeNode` graph primitive + `AuditFailure` exception + RetryingEdge re-prompt template](task_02_audit_cascade_node.md) | code + test | ✅ Complete (2026-04-27) |
| 03 | [Workflow wiring — module-constant cascade enable + planner/slice_refactor integration](task_03_workflow_wiring.md) | code + test | ✅ Complete (2026-04-27) |
| 04 | Telemetry — `TokenUsage.role` tag + `CostTracker.by_role` + cascade-step records | code + test | ✅ Complete (2026-04-27) |
| 05 | `run_audit_cascade` MCP tool + SKILL.md ad-hoc-audit section | code + test + doc | Complete (2026-04-28) |
| 06 | Eval harness — author/auditor fixture convention + golden cases for one opt-in workflow | code + test + doc | 📝 Planned |
| 07 | Milestone close-out | doc | 📝 Planned |
| 08 | [T02 amendment — `audit_cascade_node(skip_terminal_gate=True)` for cascade-exhaustion-without-interrupt path](task_08_audit_cascade_skip_terminal_gate.md) | code + test | ✅ Complete (2026-04-27) |

Per-task spec files land as each predecessor closes (same convention as M10 / M11 — scope stays calibrated against landed surface). **Sequencing exception:** T08 is a T02 amendment surfaced during T03 spec hardening (round-4 H1 — slice_refactor's parallel fan-out cannot tolerate the cascade's hard-wired terminal `human_gate` triggering N parallel operator interrupts). T08 ships **before** T03 even though its number is higher — the roadmap-selector's sequential default rule defers to T03's explicit `## Dependencies` declaration. Adding the parameter is backward-compatible (default `False` preserves T02's existing behaviour); land as an isolated T02-amendment commit per autonomy decision 2.

## Dependencies

- **M11** — the cascade's HumanGate escalation surfaces the transcript through the gate-context projection M11 ships. If M11 has not landed when M12 starts, T05 (`run_audit_cascade`) can still land (standalone invocation doesn't go through a HumanGate), but the workflow-wiring (T03) escalation path lacks a reviewable surface. Preferred sequence is M11 → M12.
- **No dependency on M10.** M10 is orthogonal (Ollama fault-tolerance).

## Carry-over from prior milestones

- *None.* M9 T04's forward-deferral landed on M11 T01 (gate-review surface), not M12.

## Propagation status

Filled in at audit time. Anticipated forward-deferrals from M12:

- Cascade-depth tuning (add Haiku → Sonnet path once Haiku lands as a primary tier) — `nice_to_have.md` entry with trigger "a workflow adopts Haiku as primary production tier".
- Shared-quota circuit breaker for Max pool — `nice_to_have.md` entry with trigger "first observed 429 / quota-exhausted response from the Claude Code CLI under cascade load".
- Cross-workflow telemetry dashboard (Langfuse, §1) — already deferred in `nice_to_have.md`; cascade telemetry strengthens the trigger but does not fire it alone.

## Issues

Land under [issues/](issues/) after each task's first audit.
