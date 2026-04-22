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

1. `ai_workflows/primitives/tiers.py` — `auditor-sonnet` and `auditor-opus` `TierConfig` entries exist in the registry, routing via `ClaudeCodeRoute(cli_model_flag="sonnet")` / `ClaudeCodeRoute(cli_model_flag="opus")`. Paired pricing entries (rates = $0; Max is flat-rate — see ADR-0004 §*Consequences*). KDR-003 guardrail test (grep for `anthropic` SDK + `ANTHROPIC_API_KEY`) extended over the new tier names and passes.
2. `ai_workflows/graph/audit_cascade.py` — `AuditCascadeNode` primitive exists, compiles a sub-graph from `(primary_tier, primary_prompt_fn, primary_output_schema, auditor_tier)`, and returns a `CompiledStateGraph` composable into any outer `StateGraph`. Auditor prompt renders the primary's output verbatim + primary prompt context + the verdict schema. The audit verdict is a pydantic model with `passed: bool`, `failure_reasons: list[str]`, `suggested_approach: str | None`. On verdict `passed=False`, the sub-graph raises `AuditFailure` (new exception in `primitives/retry.py` — bucketed `RetryableSemantic` under KDR-006) carrying the verdict payload. `RetryingEdge` is the retry surface; the cascade does not hand-roll a retry loop.
3. `RetryingEdge` re-fire path renders `failure_reasons` + `suggested_approach` into the primary prompt's `revision_guidance` block on the next attempt — not a raw retry. Hermetic test pins the shape of the re-prompt (a `{primary_original}\n\n<audit-feedback>…</audit-feedback>\n\n{primary_context}` template; exact string asserted).
4. After `RetryPolicy.max_semantic_attempts` re-fires, the cascade routes to a strict `HumanGate`. The gate carries the full cascade transcript (`{author_attempts: list[str], auditor_verdicts: list[AuditVerdict]}`) in its state channel; the M11 gate-context projection surfaces those keys at MCP boundary.
5. `planner` and `slice_refactor` workflow configs grow an `audit_cascade_enabled: bool = False` field. `AIW_AUDIT_CASCADE=1` env override flips it on for ad-hoc runs without a config edit. Landing: both workflows stay `False` by default. The opt-in *wiring* is integrated (i.e. flipping `True` works end-to-end) — no workflow author needs to re-plumb the cascade when flipping a field.
6. `TokenUsage` records from cascade steps carry a `role` tag (`"author"` | `"auditor"` | `"verdict"`). `CostTracker` grows a `by_role(run_id)` aggregation helper returning `dict[role, float]`. Existing `by_tier` / `by_model` aggregations unaffected. Role-tagged records land in `llm_calls` (or wherever `CostTracker` currently persists; respects KDR-009 / M1 T05 for the ledger storage choice).
7. `ai_workflows/mcp/server.py` — new `@mcp.tool()` `run_audit_cascade(input: RunAuditCascadeInput) -> RunAuditCascadeOutput`. Input: `artefact_ref: str` (a completed `run_id`, or a file path under a sandboxed root, or an inline dict — one-of); optional `tier_ceiling: Literal["sonnet", "opus"] = "opus"`. Output: `passed: bool`, `verdicts_by_tier: dict[str, AuditVerdict]`, `suggested_approach: str | None`, `total_cost_usd: float`. Implementation reuses `AuditCascadeNode` — the MCP tool is a thin surface wrapper, not a second primitive.
8. `.claude/skills/ai-workflows/SKILL.md` — new "Ad-hoc artefact audit" section documenting when + how to call `run_audit_cascade`. Matching `skill_install.md` reference if any install-time flag is required.
9. `evals/<workflow>/<node>/` fixture convention gains an author/auditor split: `author_<case_id>.json` + `auditor_<case_id>.json` land as two independent fixtures captured by the `CaptureCallback` whose existing role-tag can be read. No change to `EvalRunner`'s engine; fixture-naming convention only. One golden test per workflow that opts into the cascade.
10. `tests/graph/test_audit_cascade.py` + `tests/workflows/test_audit_cascade_wiring.py` — hermetic coverage of: cascade pass-through (auditor passes on first try), cascade re-fire (auditor fails → primary re-prompts with enriched context → auditor passes), cascade escalation (retries exhausted → strict gate fires with transcript), opt-out default (`audit_cascade_enabled=False` compiles an identical-to-M11 graph), opt-in roundtrip (`audit_cascade_enabled=True` compiles the cascade sub-graph in place of raw `TieredNode`).
11. Gates green: `uv run pytest` + `uv run lint-imports` (**5 contracts kept** — a new contract is added at M12 T02 to pin the cascade primitive as graph-layer; see T02 spec) + `uv run ruff check`. Count jumps from 4 to 5 because the cascade adds a new cross-file dependency that the contract pins against drift.
12. No `anthropic` SDK import anywhere. No `ANTHROPIC_API_KEY` read. Hermetic grep test extended over the new modules.

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

| # | Task | Kind |
| --- | --- | --- |
| 01 | [Auditor TierConfigs — `auditor-sonnet` + `auditor-opus`](task_01_auditor_tier_configs.md) | code + test |
| 02 | `AuditCascadeNode` graph primitive + `AuditFailure` exception + RetryingEdge re-prompt template | code + test |
| 03 | Workflow wiring — `audit_cascade_enabled` config field + planner/slice_refactor integration | code + test |
| 04 | Telemetry — `TokenUsage.role` tag + `CostTracker.by_role` + cascade-step records | code + test |
| 05 | `run_audit_cascade` MCP tool + SKILL.md ad-hoc-audit section | code + test + doc |
| 06 | Eval harness — author/auditor fixture convention + golden cases for one opt-in workflow | code + test + doc |
| 07 | Milestone close-out | doc |

Per-task spec files land as each predecessor closes (same convention as M10 / M11 — scope stays calibrated against landed surface). T01 is spec'd below; T02–T07 are written at each predecessor's close-out. The README alone is enough context to start T01.

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
