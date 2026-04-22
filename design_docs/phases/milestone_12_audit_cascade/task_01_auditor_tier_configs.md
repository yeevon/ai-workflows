# Task 01 — Auditor TierConfigs (`auditor-sonnet` + `auditor-opus`)

**Status:** 📝 Planned (drafted 2026-04-21).
**Grounding:** [milestone README](README.md) · [ADR-0004](../../adr/0004_tiered_audit_cascade.md) · [architecture.md §4.1 / §4.2](../../architecture.md) · [KDR-003 / KDR-011](../../architecture.md) · [claude_code.py:9,119-129,254](../../../ai_workflows/primitives/llm/claude_code.py).

## What to Build

Register two new `TierConfig` entries in the tier registry — `auditor-sonnet` and `auditor-opus` — each routing to the existing `ClaudeCodeSubprocess` driver via a `ClaudeCodeRoute` pinning the CLI model flag. No new dependency. No new driver. No edit to `ClaudeCodeSubprocess` itself.

The entire cascade rides on the fact that the Claude Code CLI accepts `--model sonnet` / `--model haiku` / `--model opus` as first-class flags ([claude_code.py:119-129](../../../ai_workflows/primitives/llm/claude_code.py#L119-L129), [claude_code.py:254](../../../ai_workflows/primitives/llm/claude_code.py#L254)). Today only `planner-synth` uses `ClaudeCodeRoute(cli_model_flag="opus")`; this task makes the missing Sonnet + Opus audit-role tiers available for `AuditCascadeNode` (T02) to resolve.

## Deliverables

### [ai_workflows/primitives/tiers.py](../../../ai_workflows/primitives/tiers.py) — tier entries

Two new `TierConfig` entries in the registry (or whatever construction surface the existing `planner-synth` entry uses — match the existing shape verbatim). Each entry:

- `name="auditor-sonnet"` / `name="auditor-opus"`.
- `route=ClaudeCodeRoute(cli_model_flag="sonnet")` / `route=ClaudeCodeRoute(cli_model_flag="opus")`.
- `pricing={...}` mapping the expected model IDs the CLI returns in `modelUsage` to `ModelPricing(input_per_million=0.0, output_per_million=0.0)`. Rationale: Max subscription is flat-rate. Zero prices keep `CostTracker`'s ledger shape intact (every call still produces a `TokenUsage` record; the dollar column is zero). Token counts are the empirical tuning signal — not dollars.
- `per_call_timeout_s`: reuse `planner-synth`'s value verbatim unless the CLI docs justify a tighter ceiling for `sonnet` / `haiku` (likely shorter than `opus`, but **do not** pick a value without evidence; default to the `planner-synth` ceiling and flag a follow-up nice-to-have if observed latency warrants a tighter default).

### Wiring — tier registry construction

Identify where the workflow-scoped tier registries live (`_planner_tier_registry()` / `_slice_refactor_tier_registry()` in the respective workflow modules, or wherever the canonical registry is built) and add the two new tiers. **The registries the `AuditCascadeNode` will resolve through are the same per-workflow registries the existing tiers live in** — there is no separate "audit registry".

If the M8 T04 mid-run tier-override channel (`_mid_run_tier_overrides`) is workflow-scoped, the new tiers must be reachable via that channel by name for the same override mechanism to work in cascade mode. A test assertion pins this.

### Exception surface — no change at T01

The new auditor tiers share the existing 3-bucket retry taxonomy via the `ClaudeCodeSubprocess` exception-surface. Nothing in `primitives/retry.py` changes at T01. The `AuditFailure` exception (for audit-verdict `passed=False`) lands in T02, not here.

### [tests/primitives/test_tiers.py](../../../tests/primitives/test_tiers.py) (or equivalent)

Add hermetic cases:

1. `test_auditor_sonnet_tier_resolves_to_cli_sonnet` — construct a registry, pull `auditor-sonnet`, assert `route.cli_model_flag == "sonnet"`.
2. `test_auditor_opus_tier_resolves_to_cli_opus` — mirror for opus.
3. `test_auditor_tiers_override_via_mid_run_channel` — stamp `_mid_run_tier_overrides["auditor-sonnet"] = "auditor-opus"`, assert `TieredNode._resolve_tier_name` returns `"auditor-opus"`. Confirms the M8 T04 override precedence applies unchanged to the new tiers.

### KDR-003 guardrail extension — [tests/primitives/test_claude_code_subprocess.py](../../../tests/primitives/test_claude_code_subprocess.py) (or whichever hermetic grep test M1 T03 shipped)

Extend the existing grep-check over `ai_workflows/` to verify the new tier registrations do not introduce any `anthropic` SDK import or `ANTHROPIC_API_KEY` read. Test name can stay the same (the existing test is over the whole package, not a specific module); an explicit assertion covering the new tier-config lines is the audit-surface change.

### No workflow change at T01

`planner` / `slice_refactor` do not consume the new tiers yet. They will at T03 (workflow wiring). T01 only makes the tiers available.

### [CHANGELOG.md](../../../CHANGELOG.md)

Under `## [Unreleased]`, add a `### Added — M12 Task 01: Auditor TierConfigs (YYYY-MM-DD)` entry. List:

- Files touched: `ai_workflows/primitives/tiers.py` (+ wherever the registries live).
- ACs satisfied.
- KDR-003 guardrail coverage extended.
- Explicit note: zero `ai_workflows/workflows/` diff at T01 (cascade wiring lands at T03); zero `ai_workflows/mcp/` diff (standalone MCP tool lands at T05).

## Acceptance Criteria

- [ ] `auditor-sonnet` `TierConfig` exists in the registry with `ClaudeCodeRoute(cli_model_flag="sonnet")`.
- [ ] `auditor-opus` `TierConfig` exists in the registry with `ClaudeCodeRoute(cli_model_flag="opus")`.
- [ ] Pricing entries for both tiers with zero input/output rates (Max flat-rate rationale documented inline in a short docstring on each entry).
- [ ] `per_call_timeout_s` matches the `planner-synth` baseline; deviation requires a named-evidence comment.
- [ ] Mid-run tier-override channel (`_mid_run_tier_overrides`) resolves the new tiers by name (`TieredNode._resolve_tier_name` integration test passes).
- [ ] KDR-003 guardrail test extended + passing over the new tier registration lines (no `anthropic` SDK import, no `ANTHROPIC_API_KEY` read).
- [ ] No `ai_workflows/workflows/` diff at T01 (cascade wiring is T03).
- [ ] No `ai_workflows/mcp/` diff at T01 (standalone MCP tool is T05).
- [ ] `uv run pytest` + `uv run lint-imports` (4 contracts kept — M12's new contract lands at T02, not T01) + `uv run ruff check` all clean.
- [ ] CHANGELOG entry under `[Unreleased]` with files + ACs + packaging-scope notes.

## Dependencies

- None. T01 is the foundation. T02 (the cascade primitive) depends on T01; T03/T04/T05/T06 all depend on T02.

## Out of scope (explicit)

- **No `AuditCascadeNode` primitive.** Lands at T02.
- **No workflow integration.** Lands at T03.
- **No telemetry `role` tag on `TokenUsage`.** Lands at T04.
- **No MCP tool or SKILL.md update.** Lands at T05.
- **No eval fixture convention.** Lands at T06.
- **No edit to `ClaudeCodeSubprocess`.** The driver already accepts `--model sonnet` / `--model opus` — see [claude_code.py:119-129](../../../ai_workflows/primitives/llm/claude_code.py#L119-L129). T01 consumes the existing driver interface verbatim.
- **No new retry/exception surface.** `AuditFailure` exception lands at T02.
- **No change to the existing `planner-synth` tier.** That tier stays exactly as M3 T07 / M5 T05 left it.

## Propagation status

Filled in at audit time. No forward-deferrals expected from T01 (it is a narrow tier-registration task). If the audit surfaces a timing concern on the `per_call_timeout_s` default (e.g. observed Sonnet latency is materially lower than Opus, warranting a tighter ceiling), log as a `nice_to_have.md` entry with trigger "cascade latency sensitivity measurement from M12 T04 telemetry" — not an M12 internal follow-up.
