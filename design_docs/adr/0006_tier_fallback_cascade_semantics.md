# ADR-0006 — Tier Fallback Cascade Semantics

**Status:** Accepted (M15).
**Decision owner:** [M15 — Tier Fallback Chains](../phases/milestone_15_tier_overlay/README.md).
**References:** [architecture.md §9](../architecture.md) · KDR-004 · KDR-006 · KDR-014.

## Context

Before M15 there was no declarative fallback path when a tier's retry budget exhausted via
`RetryingEdge`'s three-bucket cycle (KDR-006). The one existing fallback mechanism was the M8 T04
`_mid_run_tier_overrides` post-gate plumbing — reactive (requires a `HumanGate` pause),
Ollama-specific, and operator-manual. There was no *"try provider A, then B, then C"* cascade at
dispatch time.

A YAML-overlay approach (`~/.ai-workflows/tiers.yaml` user-supplied override) was considered and
rejected (see §Alternatives rejected). A persistent-config path would conflict with KDR-014
(framework owns quality policy; env-var is the only operator override). The declarative Python
fallback chain is the correct scope for M15.

## Decision

**Introduce `TierConfig.fallback: list[Route]` — a flat, ordered fallback chain declared in
Python, activated after retry-budget exhaustion.**

The seven concrete decision points:

1. **Fallback schema.** `TierConfig` gains `fallback: list[Route] = Field(default_factory=list)`.
   Nested fallbacks are rejected at schema-validation time: fallback routes cannot themselves carry
   a `fallback` field (flat chain only — avoids infinite-cascade chains). Existing `TierConfig`
   instances without `fallback` round-trip unchanged.

2. **Trigger condition.** Cascade activates *after* `RetryingEdge` exhausts its retry budget on
   the primary route — not on the first error signal, not on the first `NonRetryable` exception.
   The retry budget is the primary correctness surface; bypassing it complicates cost reasoning
   and defeats the three-bucket taxonomy.

3. **Cascade walk.** `TieredNode._node()` walks `fallback` in declaration order. Each fallback
   route gets a fresh retry counter (the `RetryingEdge` budget resets). Walk stops on the first
   route whose output passes the paired `ValidatorNode`; if no route succeeds,
   `AllFallbacksExhaustedError` is raised.

4. **Cost attribution.** Every attempted route — primary + each fallback — logs its `TokenUsage`
   to `CostTracker`. `CostTracker.total(run_id)` reflects the aggregate across the full cascade.
   Cost is truthful; there are no silent free attempts.

5. **Validator interaction.** The `ValidatorNode` downstream of an `LLMStep` runs unchanged
   against the successful route's output. Semantic-validation failure (`RetryableSemantic` bucket)
   is a primary-route concern and does not trigger the fallback cascade — KDR-004 is preserved,
   not modified.

6. **`AllFallbacksExhaustedError` shape.** Raised as a `NonRetryable` when every route in the
   chain (primary + all fallback entries) fails. Carries `attempts: list[TierAttempt]` for
   diagnostics — each `TierAttempt` names the route tried and its final error classification.

7. **YAML overlay rejected.** A `~/.ai-workflows/tiers.yaml` user-supplied merge overlay was
   considered to allow persistent tier rebinding without code edits. Rejected because it conflicts
   with KDR-014: the framework owns quality policy; the env-var (`--tier-override` / `tier_overrides`)
   is the only legitimate operator override path. Persistent per-user config that silently alters
   tier routing at dispatch time would make the framework's quality surface unpredictable and
   untestable. A persistent-config override path is a KDR-014 amendment, not a tiers.yaml file.

## Alternatives rejected

**Immediate fail-over on first `NonRetryable`.** Would bypass the retry budget entirely, skipping
the three-bucket taxonomy (KDR-006). Complicates cost reasoning (unclear whether a `NonRetryable`
is a genuine infra failure or a transient misclassification). Rejected to preserve the retry
budget as the primary correctness surface.

**Score-based routing.** Routing based on estimated quality scores, provider load, or historical
success rates. Rejected for non-determinism (same input can route differently across runs, making
tests unreliable) and testing complexity. Ordered declaration is simple, auditable, and matches
user expectations.

**Provider-health probes.** Querying provider liveness before dispatch to skip failing providers.
Rejected for introducing a network dependency at routing time (Ollama, LiteLLM backends may be
temporarily unreachable but not permanently broken) and for violating the simplicity principle.
The retry budget already handles transient failures; health probes duplicate the mechanism.

**YAML overlay.** `~/.ai-workflows/tiers.yaml` as a user-supplied merge overlay that silently
alters the effective tier registry at dispatch time. Rejected per KDR-014 (framework owns quality
policy; env-var is the operator override; persistent config requires KDR-014 amendment, not a
new loading path).

## Consequences

- **Fallback chains are Python-only.** Declared in workflow Python tier registry functions
  (`TierConfig.fallback=[...]`) — not in any YAML file, not in operator config. This preserves
  the KDR-014 invariant and keeps the authoring surface typed and IDE-navigable.
- **Operator-level override remains `--tier-override` / `tier_overrides`** per KDR-014. Per-call
  rebinding does not touch the fallback chain.
- **A future persistent-config path requires a KDR-014 amendment**, not a tiers.yaml file. This
  ADR forecloses the YAML-overlay route without an explicit architecture change.
- **Cost ledger stays truthful.** `CostTracker.total(run_id)` aggregates every attempt. Budget
  guards (per KDR-009) fire on aggregate cost, not per-route cost.
- **Four-layer import contract preserved.** `TierConfig.fallback` lands in `primitives`; cascade
  walk logic lands in `graph`. No new layer, no upward import.

## References

- [architecture.md §9](../architecture.md) — KDR index (KDR-004, KDR-006, KDR-014).
- KDR-004 — validator-node-after-every-LLM-node; preserved unchanged.
- KDR-006 — three-bucket retry taxonomy; cascade triggers at budget exhaustion.
- KDR-014 — framework owns quality policy; env-var is operator override.
- [M15 README](../phases/milestone_15_tier_overlay/README.md) — milestone execution plan.
- [ADR-0009](0009_framework_owns_policy.md) — framework-owns-policy principle; YAML overlay
  rejection follows directly from this ADR.
