# ADR-0009 — Framework owns quality policy; user owns invocation; operator override is env-var

**Status:** Proposed (2026-04-27, surfaced during M12 T03 spec hardening — first place the gap had operational consequences).
**Locks:** KDR-014 (proposed alongside this ADR; lands in `architecture.md §9`).

## Context

ai-workflows ships **quality primitives** — `ValidatorNode` for shape, `RetryingEdge` for retry buckets, `AuditCascadeNode` for semantic audit, tiered routing for cost/latency tradeoffs. Each primitive comes with policy knobs: cascade on or off, validator strictness, retry budget, default tier per role, audit-failure escalation threshold, etc.

A recurring question, surfaced first during M12 T03 spec hardening: **where do these knobs live?** Three plausible homes:

1. **The user's invocation** (input fields on `PlannerInput`, `SliceRefactorInput`, `WorkflowSpec` — `audit_cascade_enabled: bool = False`).
2. **The graph's runtime state** (conditional edges read state at execution time and route accordingly).
3. **The framework source itself** (module-level constants per workflow, with optional env-var operator override).

The M12 T03 task was drafted around (1) — `PlannerInput.audit_cascade_enabled`. Round-1 task analysis surfaced three HIGH findings clustered around the dispatch-layer plumbing required to thread the field from `Input` → `_dispatch._build_initial_state` → `builder(**kwargs).compile(...)`. None of the threading machinery exists today; adding it would change the `WorkflowBuilder` type signature, introduce signature introspection in the dispatch hot path, and break the spec-API workflow loader.

Option (2) — runtime conditional — would avoid the dispatch break but doubles the graph node count when cascade is enabled and pushes the decision out of build-time semantics.

The drafted T03 collapsed back into "the analyzer can't pick" — but the right move isn't to choose between (1) and (2); it's to recognise that **the question is asking the wrong thing.** Quality knobs aren't user-invocation concerns. They're framework-policy concerns.

## Decision

The framework owns quality policy. The user owns invocation. The operator's override is the env-var.

**Three audiences. Three distinct interfaces.**

| Audience | Examples | Interface |
| --- | --- | --- |
| **Framework author** | Setting cascade default-on for `planner` post-telemetry, switching `slice_refactor`'s default tier, tightening retry budget across all workflows | Module-level constants in workflow source. Code-edit + commit + new release. |
| **Operator** | Debugging a cascade regression, A/B testing with cascade disabled for a session, kill-switching a misbehaving validator | Env-var override (`AIW_AUDIT_CASCADE=1`, `AIW_VALIDATOR_STRICT=0`, etc.). Set in shell / `.env` / docker-compose. Read at process start. |
| **End user** | `aiw run summarize --text "..."`, `mcp__ai-workflows__run_workflow workflow="planner"` | Workflow name + typed inputs only. No quality-policy fields on `Input` schemas. |

**Quality knobs do NOT land on `*Input` pydantic models, `WorkflowSpec` fields, CLI flags on `aiw run`, or MCP tool input schemas.** Those surfaces are reserved for the workflow's actual inputs (the goal, the text to summarize, the run identifier).

**Quality knobs DO land as:**

- Module-level constants in each workflow source file (`_AUDIT_CASCADE_ENABLED_PLANNER = False`).
- Optional env-var override at module-import time (`os.getenv("AIW_AUDIT_CASCADE", "0") == "1"`).
- For finer-grained operator control: per-workflow env vars (`AIW_AUDIT_CASCADE_PLANNER=1`).

The decision is made **once per Python process**, at workflow-module import. The compiled graph reflects that decision; there is no per-call toggle, no input-field threading, no runtime conditional edge keyed off the policy flag.

### Specifically applied to M12 (cascade)

The drafted T03 spec's `audit_cascade_enabled` input field is **rejected**. Replacement pattern:

```python
# in ai_workflows/workflows/planner.py
import os

# Framework-author default. Flip to True post-telemetry per workflow,
# code-edit + commit + release.
_AUDIT_CASCADE_ENABLED_DEFAULT = False

# Operator override. Read at module-import (before build_planner is
# called), so the compiled graph reflects the decision. Env-var-only.
_AUDIT_CASCADE_ENABLED = (
    _AUDIT_CASCADE_ENABLED_DEFAULT
    or os.getenv("AIW_AUDIT_CASCADE", "0") == "1"
    or os.getenv("AIW_AUDIT_CASCADE_PLANNER", "0") == "1"
)


def build_planner() -> StateGraph:
    explorer_node = (
        _explorer_with_cascade()
        if _AUDIT_CASCADE_ENABLED
        else _explorer_raw()
    )
    # ...
```

`PlannerInput`, `SliceRefactorInput`, `SummarizeInput`, and `WorkflowSpec` are unchanged. No dispatch-layer plumbing. No introspection. No conditional edges in the graph for policy.

### Specifically applied to all future quality knobs

The same three-tier pattern applies whenever a new quality knob is introduced:

- Module constant for the framework default.
- Env-var override for the operator escape hatch.
- **Never** an input-schema field for the end user.

If a downstream consumer (CS300 today, others tomorrow) genuinely needs per-call quality variation, they author their own workflow that bakes the policy choice into the source. That's the KDR-013 path: user code is user-owned; the framework provides primitives, the consumer composes their workflow.

## Rationale

### Hyrum's Law and the public surface contract

Every field on `*Input` / `WorkflowSpec` / CLI is **load-bearing for someone** the moment it ships. Removing it is a SEMVER-major break. Adding `audit_cascade_enabled` to `PlannerInput` would mean: six months later, when telemetry shows cascade earns its weight for `planner`, the framework can't simply flip the default to `True` — every downstream caller that wrote `audit_cascade_enabled=False` keeps the old behaviour and has to be migrated. The narrower the public surface, the more freedom the framework retains to evolve quality defaults based on real usage data.

Module constants + env vars are **explicitly not part of the public surface contract**. Flipping `_AUDIT_CASCADE_ENABLED_DEFAULT = True` in a future patch release breaks no downstream consumer; their `aiw run planner --goal X` invocation is unchanged.

### The mirror principle to KDR-013

KDR-013 locks down ownership of *user code*: "User code is user-owned. Externally-registered workflow modules run in-process with full Python privileges; the framework surfaces import errors but does not lint, test, or sandbox them."

The mirror principle, locked here as KDR-014: **framework policy is framework-owned**. End-user invocation does not toggle, override, or fight against framework-level quality decisions. The only legitimate operator override is the env-var escape hatch — narrow, ephemeral (set for a session, unset when done), and explicitly outside the public input-schema contract.

Without this lock, every quality knob the framework adds becomes a negotiation between framework defaults and user toggles. With it, the framework can move fast on policy: telemetry-driven default flips, validator strictness adjustments, retry-budget recalibration — all without user-facing migration churn.

### Operational simplicity

The drafted T03's input-field approach required:
- Threading the field from `Input` model → `_build_initial_state`.
- Adding signature introspection to the dispatch path.
- Updating the spec-API workflow loader for the new field.
- Adding the field to every `Input` model that wants to opt in.
- Tests for the field-threading on every workflow.

The module-constant + env-var approach requires:
- A constant in each workflow's source file.
- An env-var read at the same site.
- Tests that the constant + env var both correctly drive `build_planner()`.

The second is strictly less code, less coupling, and fewer ways to go wrong.

### Telemetry-driven defaults remain the strategy

ADR-0004 §Consequences names "data-driven flips post-M12 based on the telemetry the cascade records" as the strategy for moving cascade from default-off to default-on per workflow. That strategy is **enabled** by this ADR, not contradicted: future flips are one-line code edits to `_AUDIT_CASCADE_ENABLED_DEFAULT`, not migrations of every downstream caller's input field.

## Alternatives considered

### Option A — Input-field with dispatch threading

`audit_cascade_enabled` on `*Input` models; `_build_initial_state` reads it; `builder(**kwargs)` consumes it.

**Rejected.** Hyrum's-Law cost compounds for every future quality knob. Dispatch-layer introspection magic violates the "boring docstrings" rule (the dispatch hot path should be trivially readable; signature introspection isn't). Spec-API workflow loader takes collateral damage.

### Option B — Runtime conditional inside the graph

`build_planner()` always builds both cascaded and non-cascaded explorer nodes; conditional edge reads `state["input"].audit_cascade_enabled` at runtime.

**Rejected.** Doubles graph node count when enabled. Pushes a build-time decision into runtime semantics for no gain. Composes badly with future quality knobs (every additional knob adds another runtime branch). Encourages per-call policy variation, which is the anti-feature this ADR is locking against.

### Option C — Module constant + env-var override (this ADR)

**Accepted.** Matches existing project precedent (`AIW_E2E=1`, `AIW_BUDGET_CAP_USD`, tier registries, `AIW_EXTRA_WORKFLOW_MODULES`). Smallest blast radius. Largest future flexibility. Aligned with KDR-013's user-vs-framework ownership boundary.

### Option D — Workflow-author per-spec field on `WorkflowSpec` (declarative API)

`WorkflowSpec(audit_cascade_enabled=True, ...)` for spec-API workflows.

**Partially rejected.** The spec-API surface is itself a public contract — adding policy fields to `WorkflowSpec` has the same Hyrum's-Law cost as adding them to `Input` models. If a spec-API workflow author wants cascade on, they read the env var or set the module constant in their own workflow file (which is user code, KDR-013). The framework's `WorkflowSpec` does not grow policy fields.

## Consequences

### Positive

- **Stable public surface contract.** `*Input` models stay focused on workflow inputs. `WorkflowSpec` stays focused on workflow structure. Both can evolve framework-internal quality decisions without SEMVER breakage.
- **Fast policy iteration.** Telemetry-driven default flips are one-line code edits, not migrations.
- **Clearer ownership boundary.** Framework decides quality; user runs workflow; operator's lever is env var.
- **Smaller M12 T03.** No dispatch plumbing, no introspection, no spec-API loader changes. The three HIGH findings from round-1 task analysis dissolve.
- **Generalizes.** The same pattern applies to every future quality knob — cascade, validator strictness, retry budget, tier defaults, fallback chains (M15), audit-failure escalation thresholds, post-M12 dimensions we haven't named yet.

### Negative

- **No per-call quality variation for end users.** A user who wants to run the same workflow once with cascade and once without must use the operator escape hatch (set / unset env var between calls) or pick a different workflow. Acceptable: this kind of toggling is operator territory, not user territory.
- **Discoverability shifts to operator docs.** End users won't see `--audit-cascade-enabled` in `aiw run --help`. The cascade is documented in the operator-facing README §Operator config + per-workflow docstrings, not in the user-facing CLI help. Acceptable: discoverability of policy knobs through end-user help is itself an anti-feature; they shouldn't be flipping these.
- **Framework-author flips need code commits.** Changing the default for `planner` from cascade-off to cascade-on requires a code edit + release. No live config push. Acceptable: matches every other framework-policy decision in the project (tier registries, layer rule, etc.).

### Migration impact

- **None for shipped workflows.** `planner`, `slice_refactor`, `summarize` keep their current `Input` models. The cascade flag never lands there.
- **None for end-user invocations.** `aiw run planner --goal X` is unchanged.
- **M12 T03 spec rewrite.** The drafted T03 spec must be replaced. The replacement uses module constants + env vars, no input-schema changes, no dispatch-layer plumbing.
- **ADR-0004 §Decision item 5 amendment.** The "build-time-vs-runtime semantic shifts" framing is superseded — the decision is now strictly at module-import time, before build or runtime. ADR-0004 should be amended at M12 close-out (M12 T07) to reference this ADR.
- **Documentation for operators.** Each workflow's docstring + the operator README grow a "Quality knobs" section listing the env vars that override its module defaults.

## Related

- KDR-011 (tiered audit cascade) — this ADR is the policy-control complement to KDR-011's mechanism lock.
- KDR-013 (user-owned external workflow code) — the framework-vs-user mirror principle this ADR generalises across the policy axis.
- ADR-0004 (tiered audit cascade design) — §Decision item 5's "per-workflow opt-in" intent is honoured here; the implementation shape changes from input-field to module-constant + env-var.
- ADR-0007 (user-owned code contract) — the framework-vs-user boundary this ADR mirrors for policy.
- ADR-0008 (declarative authoring surface) — `WorkflowSpec` does **not** grow policy fields per this ADR.

## Open questions

- **Per-tier overrides** (e.g. `AIW_AUDIT_CASCADE_FOR_PLANNER_EXPLORER=1` to cascade only the explorer, not other generative nodes in the same workflow). M12 lands global + per-workflow env vars only. Per-tier granularity is a future operator-need; deferred to a future task with its own trigger.
- **Operator-facing config file** (`~/.ai-workflows/policy.yaml`) as an alternative to env vars. Out of scope for M12. If env-var fan-out gets unwieldy as the framework grows quality knobs, this ADR will be amended; for now the env-var pattern is consistent with existing `AIW_*` vars and fits the operator scenario (set at shell/process level).
