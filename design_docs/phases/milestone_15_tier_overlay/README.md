# Milestone 15 — Tier Fallback Chains

**Status:** 📝 Planned (rescoped 2026-04-30; deferred — implement after M17 close-out).
**Rescoping note (2026-04-30):** The original YAML-overlay scope (`~/.ai-workflows/tiers.yaml` user-config) was dropped because it conflicts with KDR-014 (framework owns tier policy; env-var is the only operator override). M15 now covers only the `TierConfig.fallback` schema + `TieredNode` cascade dispatch + cost attribution + `aiw list-tiers` + ADR-0006. If a persistent-config override path is needed later, it requires a KDR-014 amendment and its own milestone.
**Grounding:** [architecture.md §4.1 + §9](../../architecture.md) · [roadmap.md](../../roadmap.md) · [analysis/post_0.1.2_audit_disposition.md](../../analysis/post_0.1.2_audit_disposition.md) · [M8 README](../milestone_8_ollama/README.md) (post-gate tier override — the reactive precedent that M15 generalises) · [M13 README](../milestone_13_v0_release/README.md) (v0.1.0 release baseline) · [KDR-003 / KDR-006 / KDR-007 / KDR-011 / KDR-014](../../architecture.md) (provider-routing constraints + framework-owns-policy rule).

## Why this milestone exists

One real feature gap surfaced during the post-0.1.2 audit on 2026-04-23:

**No tier-level backup chain.** When a tier's retry budget exhausts (via `RetryingEdge`'s three-bucket taxonomy per KDR-006), the workflow just fails. The one existing fallback mechanism is the M8 T04 `_mid_run_tier_overrides` post-gate plumbing — but it's reactive (requires a `HumanGate` to pause), Ollama-specific, and the operator has to manually pick the replacement. There is no declarative *"try A, then B, then C"* cascade at dispatch time.

A second gap (user-level tier configurability via a `~/.ai-workflows/tiers.yaml` overlay) was in the original scope but was dropped on rescoping (2026-04-30): that design conflicts with KDR-014 (framework owns quality policy; env-var is the only operator override path). Per-call rebinding is already available via `--tier-override` (CLI) / `tier_overrides` (MCP); persistent override would require a KDR-014 amendment.

## What M15 ships

**Fallback chain** — a new optional `fallback: list[Route]` field on `TierConfig`. When a primary route exhausts its retry budget via `RetryingEdge`, `TieredNode` walks the fallback list in order, attempting each route against a fresh `RetryingEdge` attempt counter, until one succeeds or the list exhausts. Cost attribution records every attempt (primary + each fallback) so `CostTracker.total(run_id)` stays truthful. The paired `ValidatorNode` runs against whichever route actually produced the output — the schema contract is unchanged regardless of which provider ran.

## Goal

A declarative fallback cascade that makes tier routing fault-tolerant without forking the package. Workflow authors declare the cascade in their Python tier registry:

```python
def planner_tier_registry() -> dict[str, TierConfig]:
    return {
        "planner-synth": TierConfig(
            name="planner-synth",
            route=ClaudeCodeRoute(cli_model_flag="opus"),
            fallback=[
                ClaudeCodeRoute(cli_model_flag="sonnet"),
                LiteLLMRoute(model="gemini/gemini-2.5-flash"),
            ],
        ),
        ...
    }
```

With this registry in place:

- If Opus exhausts its retry budget, `TieredNode` re-dispatches against Sonnet; if Sonnet also exhausts, it tries Gemini Flash; if all three fail, the workflow fails with a structured `AllFallbacksExhaustedError` naming every attempt.
- `CostTracker.total(run_id)` records the aggregate across every attempted route.
- The `ValidatorNode` downstream of `planner-synth` runs unchanged — it sees the final successful route's output via the existing state-update path.

## Exit criteria

1. **Fallback chain schema.** `TierConfig` gains `fallback: list[Route] = Field(default_factory=list)`. Nested fallbacks are rejected at schema-validation time (fallback routes cannot themselves carry a `fallback` field — flat only, avoids infinite chains). Existing `TierConfig` instances without `fallback` round-trip unchanged.
2. **Fallback dispatch logic.** `TieredNode._dispatch()` (or equivalent) walks the chain after retry-budget exhaustion: primary → `fallback[0]` → `fallback[1]` → … → raise `AllFallbacksExhaustedError` with `attempts: list[TierAttempt]` naming every route tried + its final classification.
3. **Cost attribution.** Every attempt (primary + fallbacks) contributes its `TokenUsage` to `CostTracker`. `runs.total_cost_usd` reflects the aggregate. A new test pins this.
4. **Validator interaction explicit.** The `ValidatorNode` downstream of a `TieredNode` with fallback receives the output of whichever route succeeded. Schema validation runs normally; if validation fails, the `RetryingEdge` retries the validator-paired primary (not fallback) per KDR-004 — a ValidatorNode failure is a *primary-route output* failure, not an infrastructure-level fallback trigger.
5. **CircuitOpen cascade coverage.** When the M8 Ollama circuit-breaker trips mid-run and `planner-explorer`'s retry budget exhausts against `CircuitOpen`, the fallback chain fires. One new test exercises this round-trip end-to-end via the MCP HTTP transport (absorbs audit finding #12 — the HTTP envelope shape on CircuitOpen is now pinned).
6. **`aiw list-tiers` inspection command.** New `aiw list-tiers [--workflow <name>]` CLI command prints the workflow's effective tier registry with the route kind, model string / CLI flag, concurrency cap, timeout, and any configured fallback chain. Pure read; no dispatch side-effects. Absorbs the discoverability gap flagged in the 0.1.2 audit.
7. **`docs/tiers.example.yaml`** — the repo-root `tiers.yaml` is relocated to `docs/` as a user-facing example file, and the authoritative tier-definition path (per-workflow Python registry) is documented inline.
8. **ADR-0006 added.** *"Tier fallback cascade semantics."* Records the decision on trigger condition (retry-budget exhaustion, not immediate error-class fast-path), cost-accounting posture (truthful — every attempt logs), validator interaction (against successful route only), nesting limit (flat — no nested fallbacks), and the rejected alternatives (immediate-fail-over, score-based routing, provider-health probes, YAML overlay). Explicitly notes that the YAML-overlay design was considered and rejected due to KDR-014.
9. **Hermetic tests.** New `tests/primitives/test_tiered_node_fallback_schema.py` for the `TierConfig.fallback` field + nested-fallback rejection. New `tests/graph/test_tiered_node_fallback.py` for the dispatch cascade (stub adapter, deterministic). New `tests/mcp/test_http_fallback_on_circuit_open.py` for the HTTP-transport envelope shape when the cascade fires under a tripped breaker. Existing tests stay green unchanged.
10. **Gates green.** `uv run pytest` + `uv run lint-imports` (4 contracts kept — no new layer; fallback schema in `primitives`, cascade logic in `graph`) + `uv run ruff check`.

## Non-goals

- **No YAML overlay / persistent user config.** Dropped on rescoping (2026-04-30). Per KDR-014, framework owns quality policy; env-var is the only operator override path. Per-call rebinding is available via `--tier-override` (CLI) / `tier_overrides` (MCP). A persistent config path would require a KDR-014 amendment.
- **No new route kinds.** `LiteLLMRoute` + `ClaudeCodeRoute` are still the only two. Adding a new route kind is a separate KDR change; M15 just enables existing kinds to be composed into fallback chains.
- **No score-based routing.** Fallback is ordered (primary first, then fallback[0], then fallback[1], …), not weighted or probabilistic. Smart routing is a forward-option.
- **No immediate error-class fallback.** Fallback triggers *after* retry-budget exhaustion, not on the first `NonRetryable` signal. The retry budget is the primary correctness surface; bypassing it complicates cost reasoning.
- **No MCP schema change.** `tier_overrides` (the per-invocation override) stays the consumer-facing surface, unchanged.
- **No workflow-file change.** Shipped workflows (`planner`, `slice_refactor`) continue to declare their own Python tier registries. M15 adds fallback field support; it does not rewrite the workflows.
- **No `0.0.0.0` bind discussion.** HTTP transport security posture is owned by M14's README. M15 is dispatch-layer only.

## Key decisions in effect

| Decision | Reference |
|---|---|
| Workflow owns tier defaults in Python module constants; per-call override via `tier_overrides` | KDR-014 + ADR-0009 |
| Fallback triggers after retry-budget exhaustion | KDR-006 (retry taxonomy) + ADR-0006 (M15 T0N) |
| Cost attribution accumulates across every route attempted | KDR-004 + ADR-0006 |
| No nested fallbacks — flat chain only | ADR-0006 |
| No YAML overlay — dropped to respect KDR-014 | rescoping 2026-04-30 |
| Four-layer import contract preserved — no new layer | architecture.md §3 |
| KDR-003 / KDR-007 preserved — no new adapter surface | architecture.md §9 |

## Task order

| # | Task | Kind |
|---|---|---|
| 01 | [`TierConfig.fallback` schema + hermetic tests](task_01_fallback_schema.md) ✅ Built (cycle 1) | code + test |
| 02 | [`TieredNode` fallback-cascade dispatch + cost attribution](task_02_tierednode_cascade_dispatch.md) ✅ Built (cycle 1) | code + test |
| 03 | [`aiw list-tiers` command + HTTP CircuitOpen cascade test](task_03_aiw_list_tiers_and_circuit_open_cascade.md) ✅ Built (cycle 2) | code + test + doc |
| 04 | [ADR-0006 + relocate `tiers.yaml` → `docs/tiers.example.yaml` + `docs/writing-a-workflow.md` tier-config section](task_04_adr_0006_and_tiers_doc_relocation.md) ✅ Built (cycle 1) | doc |
| 05 | Milestone close-out | doc |

Per-task spec files land as each predecessor closes (same convention as M11 / M13 / M14). T01 is spec'd alongside this README; T02–T05 are written at the predecessor's close-out so the scope stays calibrated against landed surface.

## Dependencies

- **M13 + current release baseline (0.3.1).** M15 was drafted as "first post-release feature milestone" targeting 0.2.0 — both stale. 0.3.1 is live (M16 + M19 shipped). M15 will ship as the next minor (0.4.0 if M17 hasn't shipped, or later).
- **0.1.3 patch — complete.** The misleading `planner` / `implementer` entries were already removed from `tiers.yaml`. M15 T04 finishes the relocation to `docs/tiers.example.yaml`.
- **M8 (Ollama infrastructure) — composes over.** M8 T04's `_mid_run_tier_overrides` (post-gate reactive fallback) and M15's declarative fallback chain **coexist**: M8 still handles the post-gate operator-arbitration path; M15 handles the declarative cascade. No conflict; T02 validates both mechanisms fire correctly in the same test run.
- **M14 (MCP HTTP transport) — composes over.** M15's HTTP-envelope test for cascade-on-CircuitOpen rides on M14's HTTP transport; no schema change at the MCP layer.
- **M16 (external workflows) — already shipped (2026-04-24).** M15 was listed as M16's precondition; M16 shipped without it. M15 composes with M16: external workflows can declare `TierConfig.fallback` chains in their own Python registries once M15 lands.
- **M17 (scaffold workflow) — not blocked on M15.** M17 was listed as requiring M15 for tier rebinding, but the scaffold's tier is overridable via `--tier-override` / `tier_overrides` per KDR-014. M15 is a nice-to-have for M17 (richer cascade options) but not a hard prerequisite.

## Open questions (resolve before T01 kickoff)

- **Cost assertion in tests.** Claude Code tiers report `cost_usd=0.0` under the Max subscription (per `project_provider_strategy.md`). Fallback tests use `>= 0` assertions, matching the existing convention.
- **Fallback route type: inlined `Route` vs. tier-name reference.** Current plan: `fallback: list[Route]` (inlined), not `list[str]` (tier-name references). Reason: avoids resolution ordering headaches; tier-name references would make the resolution graph recursive.

## Carry-over from prior milestones

- *None at M15 kickoff.* The 0.1.3 patch absorbs every audit finding that's not a milestone deliverable; M15 starts from a clean slate.

## Propagation status

Filled in at audit time. Anticipated forward-deferrals:

- A "fail over immediately on specific error classes" feature — `nice_to_have.md` candidate with trigger "a workflow needs fail-over before the retry budget is spent." Not planned at M15.
- A tier-name-reference variant of `fallback:` (e.g. `fallback: [my-sonnet-tier]`) — `nice_to_have.md` candidate with trigger "users are copy-pasting the same route definitions across multiple tier registries." Not planned at M15.
- YAML overlay / persistent user tier config — deferred pending KDR-014 amendment. Trigger: "a user needs persistent tier rebinding without passing `--tier-override` every call." Not planned at M15.

## Issues

Land under [issues/](issues/) after each task's first audit.
