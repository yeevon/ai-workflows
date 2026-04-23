# Milestone 15 — Tier Overlay + Fallback Chains

**Status:** 📝 Planned (drafted 2026-04-23).
**Grounding:** [architecture.md §4.1 + §9](../../architecture.md) · [roadmap.md](../../roadmap.md) · [analysis/post_0.1.2_audit_disposition.md](../../analysis/post_0.1.2_audit_disposition.md) · [M8 README](../milestone_8_ollama/README.md) (post-gate tier override — the reactive precedent that M15 generalises) · [M13 README](../milestone_13_v0_release/README.md) (v0.1.0 release; M15 is the first post-release feature milestone) · [KDR-003 / KDR-007 / KDR-011](../../architecture.md) (provider-routing constraints preserved by M15).

## Why this milestone exists

Two real feature gaps surfaced during the post-0.1.2 audit on 2026-04-23:

1. **No tier-level backup chain.** When a tier's retry budget exhausts (via `RetryingEdge`'s three-bucket taxonomy per KDR-006), the workflow just fails. The one existing fallback mechanism is the M8 T04 `_mid_run_tier_overrides` post-gate plumbing — but it's reactive (requires a `HumanGate` to pause), Ollama-specific, and the operator has to manually pick the replacement. There is no declarative *"try A, then B, then C"* cascade at dispatch time.
2. **No user-level tier configurability from a `uvx` install.** The shipped wheel carries no `tiers.yaml`; each workflow's tier registry is hardcoded in Python ([`planner_tier_registry()`](../../../ai_workflows/workflows/planner.py#L647-L682), [`slice_refactor_tier_registry()`](../../../ai_workflows/workflows/slice_refactor.py#L1593-L1603)). A PyPI-installed user who wants `planner-synth` to be Sonnet instead of Opus — or who wants to try OpenAI for exploration — has to fork the package. The existing `--tier-override logical=replacement` flag only repoints one tier to *another tier that the workflow already defined*; it cannot add a new provider binding.

Both gaps are **CS300-relevant**: the interactive CS-300 notes site (the first committed MCP HTTP consumer; see M14) will exercise the MCP surface under real provider conditions. Rate limits, model-name changes, and per-session preference drift are normal; the framework should degrade gracefully and respect the operator's preferences without requiring a fork.

## What M15 ships

M15 introduces a **single cross-cutting tier-config surface** that solves both gaps with one schema extension:

1. **Tier overlay** — a user-supplied `~/.ai-workflows/tiers.yaml` (or `$AIW_TIERS_PATH`) that merges into the effective tier registry at dispatch time. Overlay entries rebind tier names by key: if the workflow's registry declares `planner-synth` and the overlay declares `planner-synth`, the overlay wins. Overlay entries whose names the workflow does not declare are ignored with a warning (typo-guard). This preserves the **"workflow owns the default; user owns the rebind"** contract established in the M15 design review (2026-04-23).
2. **Fallback chain** — a new optional `fallback: list[Route]` field on `TierConfig`. When a primary route exhausts its retry budget via `RetryingEdge`, `TieredNode` walks the fallback list in order, attempting each route against a fresh `RetryingEdge` attempt counter, until one succeeds or the list exhausts. Cost attribution records every attempt (primary + each fallback) so `CostTracker.total(run_id)` stays truthful. The paired `ValidatorNode` runs against whichever route actually produced the output — the schema contract is unchanged regardless of which provider ran.

The overlay and the fallback schema compose — a user can declare a fallback chain on their own overlay entry, or inherit the workflow-author's defaults and just rebind the primary.

## Goal

A user-supplied YAML overlay + fallback cascade that makes tier routing configurable and fault-tolerant without forking the package:

```yaml
# ~/.ai-workflows/tiers.yaml  (user overlay, optional)
planner-synth:
  route: {kind: claude_code, cli_model_flag: sonnet}
  fallback:
    - {kind: claude_code, cli_model_flag: haiku}
    - {kind: litellm, model: gemini/gemini-2.5-flash}
  max_concurrency: 1
```

With this overlay in place:

- `aiw run planner --goal '…'` uses Sonnet for synthesis (overlay wins over workflow default of Opus).
- If Sonnet hits a `NonRetryable` classification past retry budget, `TieredNode` re-dispatches against Haiku; if Haiku also exhausts, it tries Gemini Flash; if all three fail, the workflow fails with a structured error that names every attempt.
- `CostTracker.total(run_id)` records the aggregate across every attempted route.
- The `ValidatorNode` downstream of `planner-synth` runs unchanged — it sees the final successful route's output via the existing state-update path.

## Exit criteria

1. **Overlay loader ships.** `TierRegistry` gains a `load_with_overlay(workflow_registry: dict[str, TierConfig], *, overlay_path: Path | None = None) -> dict[str, TierConfig]` classmethod (or equivalent at the `_resolve_tier_registry()` call site). Path resolution order: `$AIW_TIERS_PATH` env var > `~/.ai-workflows/tiers.yaml` > no overlay. Missing overlay returns the workflow registry unchanged (silent — overlays are optional).
2. **Overlay merge rule is "replace by name."** If the overlay defines a tier name that the workflow registry declares, the overlay's `TierConfig` replaces the workflow's. If the overlay defines a name the workflow does not declare, `_resolve_tier_registry()` logs a structlog warning (`unknown_tier_in_overlay`) and drops the overlay entry. No partial-field merge; no schema inheritance.
3. **Fallback chain schema.** `TierConfig` gains `fallback: list[LiteLLMRoute | ClaudeCodeRoute] = Field(default_factory=list)`. Nested fallbacks are rejected at schema-validation time (fallback routes cannot themselves carry a `fallback` field — flat only, avoids infinite chains).
4. **Fallback dispatch logic.** `TieredNode._dispatch()` (or equivalent) walks the chain after retry-budget exhaustion: primary → `fallback[0]` → `fallback[1]` → … → raise `AllFallbacksExhaustedError` with `attempts: list[TierAttempt]` naming every route tried + its final classification.
5. **Cost attribution.** Every attempt (primary + fallbacks) contributes its `TokenUsage` to `CostTracker`. `runs.total_cost_usd` reflects the aggregate. A new test pins this.
6. **Validator interaction explicit.** The `ValidatorNode` downstream of a `TieredNode` with fallback receives the output of whichever route succeeded. Schema validation runs normally; if validation fails, the `RetryingEdge` retries the validator-paired primary (not fallback) per KDR-004 — a ValidatorNode failure is a *primary-route output* failure, not an infrastructure-level fallback trigger.
7. **CircuitOpen cascade coverage.** When the M8 Ollama circuit-breaker trips mid-run and `planner-explorer`'s retry budget exhausts against `CircuitOpen`, the fallback chain fires. One new test exercises this round-trip end-to-end via the MCP HTTP transport (absorbs audit finding #12 — the HTTP envelope shape on CircuitOpen is now pinned).
8. **`aiw list-tiers` inspection command.** New `aiw list-tiers [--workflow <name>]` CLI command prints the effective tier registry (workflow registry + overlay, post-merge) with the route kind, model string / CLI flag, concurrency cap, timeout, and any configured fallback chain. No-argument form prints the overlay-only view (`$AIW_TIERS_PATH` contents). Pure read; no dispatch side-effects. Absorbs the discoverability gap flagged in the 0.1.2 audit.
9. **`docs/tiers.example.yaml`** — the repo-root `tiers.yaml` is relocated to `docs/` as a user-facing example file, and the authoritative tier-definition path (per-workflow Python registry) is documented inline. The 0.1.3 patch deletes the file's misleading entries; M15 T0N finishes the relocation.
10. **KDR-012 added to architecture.md §9.** *"Tier routing is two-layered: workflow-author registries define defaults; user overlay ($AIW_TIERS_PATH / ~/.ai-workflows/tiers.yaml) rebinds by tier name. Fallback chains are a first-class field on TierConfig; fallback triggers after RetryingEdge retry-budget exhaustion; cost attribution accumulates across every attempt; the paired ValidatorNode runs against whichever route succeeded."* Composes over KDR-003 (no Anthropic API — fallback routes still constrained to LiteLLM + Claude Code subprocess), KDR-004 (validator pairing preserved), KDR-006 (retry taxonomy unchanged), KDR-007 (adapter surface unchanged).
11. **ADR-0006 added.** *"Tier fallback cascade semantics."* Records the decision on trigger condition (retry-budget exhaustion, not immediate error-class fast-path), cost-accounting posture (truthful — every attempt logs), validator interaction (against successful route only), nesting limit (flat — no nested fallbacks), and the rejected alternatives (immediate-fail-over, score-based routing, provider-health probes).
12. **Hermetic tests.** New `tests/primitives/test_tier_overlay.py` for the loader/merge rule + schema. New `tests/graph/test_tiered_node_fallback.py` for the dispatch cascade (stub adapter, deterministic). New `tests/mcp/test_http_fallback_on_circuit_open.py` for the HTTP-transport envelope shape when the cascade fires under a tripped breaker. Existing tests stay green unchanged.
13. **Gates green on both branches.** `uv run pytest` + `uv run lint-imports` (4 contracts kept — no new layer at M15; overlay schema lives in `primitives`, cascade logic in `graph`) + `uv run ruff check`.

## Non-goals

- **No role vocabulary.** The M15 design review (2026-04-23) considered a "role-based" config (`explorer`, `synthesizer`, `implementer`) where workflows reference roles and users bind roles to models. Rejected: introduces a fixed vocabulary that would fight M17's scaffold-generated workflows. The chosen design is name-based rebinding instead — every workflow picks its own tier names; the overlay rebinds by name, not role.
- **No new route kinds.** `LiteLLMRoute` + `ClaudeCodeRoute` are still the only two. Adding a new route kind (e.g. for a provider LiteLLM doesn't cover) is a separate KDR change; M15 just enables existing kinds to be composed into fallback chains.
- **No score-based routing.** Fallback is ordered (primary first, then fallback[0], then fallback[1], …), not weighted or probabilistic. Smart routing is a forward-option; its trigger would be "a second workflow needs different provider preferences for the same logical step."
- **No immediate error-class fallback.** Fallback triggers *after* retry-budget exhaustion, not on the first `NonRetryable` signal. Reason: the retry budget is the primary correctness surface; bypassing it would couple fallback into every single LLM call and complicate cost reasoning. If a future workflow needs "fail over to Sonnet immediately on rate-limit," that's a separate feature.
- **No auth / secrets surface change.** Overlay secrets still flow through env-var expansion (`${VAR:-default}` pattern already in `tiers.py`); the overlay YAML never carries literal keys.
- **No MCP schema change.** The overlay is a server-local config; no MCP tool gains an "overlay override" input at M15. `tier_overrides` (the per-invocation override) stays the consumer-facing surface, unchanged.
- **No workflow-file change.** Every shipped workflow (`planner`, `slice_refactor`) continues to declare its own Python tier registry. M15 adds the overlay on top; it does not rewrite the workflows.
- **No `0.0.0.0` bind discussion.** HTTP transport security posture is owned by M14's README. M15 is dispatch-layer only.

## Key decisions in effect

| Decision | Reference |
|---|---|
| Workflow owns tier defaults; user overlay rebinds by name | M15 design review (2026-04-23) — recorded in this README § "Why" |
| Fallback triggers after retry-budget exhaustion | KDR-006 (retry taxonomy) + ADR-0006 (M15 T0N) |
| Cost attribution accumulates across every route attempted | KDR-004 + ADR-0006 |
| No nested fallbacks — flat chain only | ADR-0006 |
| Overlay path: `$AIW_TIERS_PATH` > `~/.ai-workflows/tiers.yaml` > none | M15 T01 |
| Four-layer import contract preserved — no new layer | architecture.md §3 |
| KDR-003 / KDR-007 preserved — no new adapter surface | architecture.md §9 |

## Task order

| # | Task | Kind |
|---|---|---|
| 01 | [Overlay loader + `TierConfig.fallback` schema](task_01_overlay_and_fallback_schema.md) | code + test |
| 02 | `TieredNode` fallback-cascade dispatch + cost attribution | code + test |
| 03 | `aiw list-tiers` command + HTTP CircuitOpen cascade test | code + test + doc |
| 04 | KDR-012 + ADR-0006 + relocate `tiers.yaml` → `docs/tiers.example.yaml` + `docs/writing-a-workflow.md` tier-config section | doc |
| 05 | Milestone close-out | doc |

Per-task spec files land as each predecessor closes (same convention as M11 / M13 / M14). T01 is spec'd alongside this README; T02–T05 are written at the predecessor's close-out so the scope stays calibrated against landed surface.

## Dependencies

- **M13 (v0.1.0 release) — prerequisite.** M15 is the first post-release feature milestone. Ships as `0.2.0`.
- **0.1.3 patch — sibling.** The 0.1.3 patch (scoped in [post_0.1.2_audit_disposition.md](../../analysis/post_0.1.2_audit_disposition.md)) deletes the misleading `planner` / `implementer` entries from `tiers.yaml` and adds header-comment clarification. M15 T04 finishes the relocation to `docs/tiers.example.yaml`. The patch should land **before** M15 kickoff so T01's work starts against a clean tier-config surface; alternatively the patch can fold into M15 T01's scope if the operator prefers.
- **M8 (Ollama infrastructure) — composes over.** M8 T04's `_mid_run_tier_overrides` (post-gate reactive fallback) and M15's declarative fallback chain **coexist**: M8 still handles the post-gate operator-arbitration path; M15 handles the declarative "here's what to try next without asking" path. No conflict; T02 validates both mechanisms fire correctly in the same test run.
- **M14 (MCP HTTP transport) — composes over.** M15's HTTP-envelope test for cascade-on-CircuitOpen (exit criterion 7) rides on M14's HTTP transport; no schema change at the MCP layer.
- **M16 (external workflows) — M15 is precondition.** Once users can drop in their own workflows (M16), those workflows' tier registries can be rebound via M15's overlay without editing the user-supplied Python. M15 ships first so M16's load-path has a stable tier surface to target.
- **M17 (scaffold workflow) — M15 is precondition.** The scaffold-generated workflows' tier registries use M15's overlay for model-selection freedom without regenerating the scaffolded code.

## Open questions (resolve before T01 kickoff)

- **Overlay file name convention.** `~/.ai-workflows/tiers.yaml` vs. `~/.ai-workflows/tiers.overlay.yaml` vs. `~/.config/ai-workflows/tiers.yaml`. Current plan: `~/.ai-workflows/tiers.yaml` matches the existing `~/.ai-workflows/storage.sqlite3` + `checkpoint.sqlite3` convention.
- **Overlay schema surfaced via `aiw list-tiers` or as a separate `aiw tiers validate`?** Current plan: `aiw list-tiers` prints the effective registry; schema errors in the overlay file surface as loud warnings at startup (same channel as "unknown tier in overlay" — structlog warning + `aiw list-tiers` shows the overlay was ignored).
- **Cost assertion in tests.** Claude Code tiers report `cost_usd=0.0` under the Max subscription (per `project_provider_strategy.md`). Fallback tests use `>= 0` assertions, matching the existing convention.
- **Fallback route reusing an existing tier name vs. inlined `Route`.** Current plan: `fallback:` is `list[Route]` (inlined), not `list[str]` (tier-name references). Reason: avoids resolution ordering headaches; the overlay can inline the same model string directly. Tier-name references would make the resolution graph recursive.

## Carry-over from prior milestones

- *None at M15 kickoff.* The 0.1.3 patch absorbs every audit finding that's not a milestone deliverable; M15 starts from a clean slate.

## Propagation status

Filled in at audit time. Anticipated forward-deferrals:

- A "fail over immediately on specific error classes" feature — `nice_to_have.md` candidate with trigger "a workflow needs fail-over before the retry budget is spent." Not planned at M15.
- A tier-name-reference variant of `fallback:` (e.g. `fallback: [my-sonnet-tier]`) — `nice_to_have.md` candidate with trigger "users are copy-pasting the same route definitions into every overlay entry." Not planned at M15.
- Overlay hot-reload (pick up `~/.ai-workflows/tiers.yaml` edits without restart) — `nice_to_have.md` candidate with trigger "a long-running MCP HTTP server wants mid-session overlay swaps." Current design is load-once at dispatch start.

## Issues

Land under [issues/](issues/) after each task's first audit.
