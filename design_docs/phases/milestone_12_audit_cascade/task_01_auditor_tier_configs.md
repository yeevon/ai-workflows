# Task 01 — Auditor TierConfigs (`auditor-sonnet` + `auditor-opus`)

**Status:** ✅ Complete (2026-04-27).
**Grounding:** [milestone README](README.md) · [ADR-0004](../../adr/0004_tiered_audit_cascade.md) · [architecture.md §4.2 (graph adapters where TieredNode resolves the tier) / §4.1 (primitives where TierConfig is defined)](../../architecture.md) · [KDR-003 / KDR-011](../../architecture.md) · [claude_code.py:9,119-129](../../../ai_workflows/primitives/llm/claude_code.py).

## What to Build

Register two new `TierConfig` entries in the tier registry — `auditor-sonnet` and `auditor-opus` — each routing to the existing `ClaudeCodeSubprocess` driver via a `ClaudeCodeRoute` pinning the CLI model flag. No new dependency. No new driver. No edit to `ClaudeCodeSubprocess` itself.

The entire cascade rides on the fact that the Claude Code CLI accepts `--model sonnet` / `--model haiku` / `--model opus` as first-class flags ([claude_code.py:119-129](../../../ai_workflows/primitives/llm/claude_code.py#L119-L129)). Today only `planner-synth` uses `ClaudeCodeRoute(cli_model_flag="opus")`; this task makes the missing Sonnet + Opus audit-role tiers available for `AuditCascadeNode` (T02) to resolve.

## Deliverables

### Workflow-scoped tier registries (the actual landing site)

Production `TierConfig` instances are constructed in **workflow modules**, not in `primitives/tiers.py` (which only ships the pydantic schema + YAML loader). Add two new entries — `auditor-sonnet` and `auditor-opus` — to **every** in-tree workflow tier registry that consumes a generative tier whose output is read downstream. As of M19, those are:

- `ai_workflows/workflows/planner.py:planner_tier_registry()` (lines ~647-682).
- `ai_workflows/workflows/slice_refactor.py:slice_refactor_tier_registry()` (composes planner + adds `slice-worker`; the auditor entries land via the planner-registry composition at line ~1593).
- `ai_workflows/workflows/summarize_tiers.py:summarize_tier_registry()` — `summarize` runs on `gemini/gemini-2.5-flash`, so KDR-011's scope rule (output read by user) makes `auditor-sonnet` reachable here too. Add the entries directly; this registry does not compose another.

Each entry:

- `name="auditor-sonnet"` / `name="auditor-opus"`.
- `route=ClaudeCodeRoute(cli_model_flag="sonnet")` / `route=ClaudeCodeRoute(cli_model_flag="opus")`.
- `max_concurrency=1` (matching `planner-synth`'s single-OAuth-session constraint; no evidence to widen).
- `per_call_timeout_s`: reuse `planner-synth`'s value verbatim (`300`); deviation requires a named-evidence comment.

**The registries `AuditCascadeNode` will resolve through are the same per-workflow registries the existing tiers live in** — there is no separate "audit registry" and no edit to `primitives/tiers.py` is expected at T01.

### No edit to `ai_workflows/primitives/tiers.py`

The schema module is unchanged at T01. New `TierConfig` instances live in workflow modules (`workflows/planner.py`, `workflows/slice_refactor.py`, `workflows/summarize_tiers.py`).

If the M8 T04 mid-run tier-override channel (`_mid_run_tier_overrides`) is workflow-scoped, the new tiers must be reachable via that channel by name for the same override mechanism to work in cascade mode. A test assertion pins this.

### Exception surface — no change at T01

The new auditor tiers share the existing 3-bucket retry taxonomy via the `ClaudeCodeSubprocess` exception-surface. Nothing in `primitives/retry.py` changes at T01. The `AuditFailure` exception (for audit-verdict `passed=False`) lands in T02, not here.

### Tests — registry shape (workflow layer) + override precedence (graph layer)

Two test-file landing sites; cases land where the asserted code lives (mirror existing-pattern alignment, not a single new file).

**Workflow-layer tests** — register-shape assertions land alongside `tests/workflows/test_planner_synth_claude_code.py:test_planner_synth_tier_points_at_claude_code_opus` (line 232). Either extend that file or add a new `tests/workflows/test_auditor_tier_configs.py` mirroring its shape:

1. `test_auditor_sonnet_tier_resolves_to_cli_sonnet` — pull `auditor-sonnet` from the modified registry (the planner registry is the canonical pull, since slice_refactor composes it and summarize defines the same entries directly). Narrow with `assert isinstance(route, ClaudeCodeRoute)` first (mirroring the existing line 236 pattern), then assert `route.cli_model_flag == "sonnet"`, `max_concurrency == 1`, `per_call_timeout_s == 300`. Optionally also assert `route.kind == "claude_code"` to match the existing test shape. Cover the same shape for `summarize_tier_registry()` since that registry defines the entries directly rather than composing.
2. `test_auditor_opus_tier_resolves_to_cli_opus` — mirror for opus across the same registries.

**Graph-layer test** — override-precedence assertion lands in `tests/graph/` (mirroring `tests/graph/test_tiered_node_ollama_breaker.py`'s use of `_mid_run_tier_overrides` at lines 480 / 517):

3. `test_auditor_tiers_override_via_mid_run_channel` — stamp `state = {"_mid_run_tier_overrides": {"auditor-sonnet": "auditor-opus"}}`, call `ai_workflows.graph.tiered_node._resolve_tier("auditor-sonnet", state, configurable={})`, assert it returns `"auditor-opus"`. Confirms the M8 T04 override precedence applies unchanged to the new tiers. `_resolve_tier` is a module-level function (the graph layer ships a `tiered_node` factory, not a `TieredNode` class) — import directly: `from ai_workflows.graph.tiered_node import _resolve_tier`. (Note: leading underscore is intentional; the function is not in `__all__` but is the documented override-precedence surface per its docstring.)

### KDR-003 guardrail — verify, don't extend

The canonical tree-wide grep is `tests/workflows/test_slice_refactor_e2e.py:test_kdr_003_no_anthropic_in_production_tree`; it walks the entire `ai_workflows/` tree, so the new `auditor-*` `TierConfig` registrations in the workflow modules are covered automatically once they land. No new test is required. The AC is "this existing test still passes." A second per-file grep lives at `tests/workflows/test_planner_synth_claude_code.py:test_no_anthropic_sdk_import_in_planner_or_claude_code_driver` over `planner.py` + `claude_code.py` — that one is unaffected at T01 because no edits land in those two specific files (planner.py grows two TierConfig entries, but they hold no anthropic surface). If the Builder wants belt-and-braces, add a one-line targeted assertion against the modified workflow files; it is not required.

### No workflow change at T01

`planner` / `slice_refactor` do not consume the new tiers yet. They will at T03 (workflow wiring). T01 only makes the tiers available.

### [CHANGELOG.md](../../../CHANGELOG.md)

Under `## [Unreleased]`, add a `### Added — M12 Task 01: Auditor TierConfigs (YYYY-MM-DD)` entry. List:

- Files touched: `ai_workflows/workflows/planner.py`, `ai_workflows/workflows/summarize_tiers.py` (auditor entries added directly), and `ai_workflows/workflows/slice_refactor.py` (auditor entries propagate via the existing `dict(planner_tier_registry())` composition — diff may be limited to a docstring tweak naming the new tiers). Zero diff at `ai_workflows/primitives/tiers.py` (schema module unchanged at T01), `ai_workflows/graph/` (cascade primitive lands at T02), and `ai_workflows/mcp/` (standalone MCP tool lands at T05).
- ACs satisfied (linked back to this spec).
- KDR-003 guardrail tests still green over the new tier registrations — no extension required; the existing tree-wide grep at `tests/workflows/test_slice_refactor_e2e.py:test_kdr_003_no_anthropic_in_production_tree` covers the new lines automatically.

## Acceptance Criteria

- [x] `auditor-sonnet` `TierConfig` exists in the registry with `ClaudeCodeRoute(cli_model_flag="sonnet")`.
- [x] `auditor-opus` `TierConfig` exists in the registry with `ClaudeCodeRoute(cli_model_flag="opus")`.
- [x] Pricing for both tiers covered by the existing `pricing.yaml` (Max flat-rate; subscription-billed). No `pricing.yaml` edit expected; if the CLI's `modelUsage` returns a model ID not yet in the file, add it at zero rate with a short comment citing the Max flat-rate rationale.
- [x] `per_call_timeout_s` matches the `planner-synth` baseline; deviation requires a named-evidence comment.
- [x] Mid-run tier-override channel (`_mid_run_tier_overrides`) resolves the new tiers by name (the `ai_workflows.graph.tiered_node._resolve_tier` integration test passes).
- [x] KDR-003 guardrail tests pass: the tree-wide `test_kdr_003_no_anthropic_in_production_tree` and the file-scoped `test_no_anthropic_sdk_import_in_planner_or_claude_code_driver` both green (no extension required — the tree-wide grep covers any new lines automatically).
- [x] No `ai_workflows/workflows/` cascade-wiring diff at T01 (cascade wiring is T03). Note: tier-registration diffs in workflow files are the intended landing site per §Deliverables; AC-7 targets cascade-wiring changes only.
- [x] No `ai_workflows/mcp/` diff at T01 (standalone MCP tool is T05).
- [x] `uv run pytest` + `uv run lint-imports` (4 contracts kept — M12's new contract lands at T02, not T01) + `uv run ruff check` all clean.
- [x] CHANGELOG entry under `[Unreleased]` with files + ACs + packaging-scope notes.
- [x] Status surfaces flipped together at close: (a) this spec's `**Status:**` line to `✅ Complete (YYYY-MM-DD).`; (b) milestone README task-order table row 01 status indicator; (c) milestone README §Exit-criteria bullet 1 (the `auditor-sonnet`/`auditor-opus` registration row) ticked. There is no `tasks/README.md` for M12.

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
- **No change to the existing `planner-synth` tier.** That tier stays exactly as M5 T02 left it (the task that repointed `planner-synth` to `ClaudeCodeRoute(cli_model_flag="opus", per_call_timeout_s=300)`).

## Propagation status

Filled in at audit time. No forward-deferrals expected from T01 (it is a narrow tier-registration task). If the audit surfaces a timing concern on the `per_call_timeout_s` default (e.g. observed Sonnet latency is materially lower than Opus, warranting a tighter ceiling), log as a `nice_to_have.md` entry with trigger "cascade latency sensitivity measurement from M12 T04 telemetry" — not an M12 internal follow-up.

## Carry-over from task analysis

- [x] **TA-LOW-01 — Drop stray `claude_code.py:254` cross-reference** (severity: LOW, source: task_analysis.md round 3)
      §Grounding line cites `[claude_code.py:9,119-129,254]`; line 254 is inside `_find_primary_key` (a `modelUsage`-key resolution helper), not a `--model` flag site. The §What-to-Build cite to `[claude_code.py:254]` should be dropped or repointed to `claude_code.py:124-125` (the actual argv `--model` assembly site).
      **Recommendation:** Drop `,254` from the Grounding citation; drop or repoint the §What-to-Build line-10 cite to `:124-125`.

- [x] **TA-LOW-02 — `isinstance(route, ClaudeCodeRoute)` narrowing in tests #1/#2** (severity: LOW, source: task_analysis.md round 3)
      The Builder must narrow with `isinstance(route, ClaudeCodeRoute)` before asserting `route.cli_model_flag` (mirrors the existing `tests/workflows/test_planner_synth_claude_code.py:235` pattern; required for mypy under the union route type `LiteLLMRoute | ClaudeCodeRoute`). Optional `route.kind == "claude_code"` assertion alongside `cli_model_flag` matches the existing test shape.
      **Recommendation:** Adopt the `isinstance` narrowing in tests #1 and #2.

- [x] **TA-LOW-03 — ADR-0004 §Decision item 1 carries stale tier-location framing** (severity: LOW, source: task_analysis.md round 3)
      `design_docs/adr/0004_tiered_audit_cascade.md:25` reads: *"Both sit in the `TierRegistry` (`ai_workflows/primitives/tiers.py`) next to `planner-synth`."* That framing is superseded by this spec's workflow-scoped landing (`workflows/planner.py`, `workflows/summarize_tiers.py`); the ADR's mechanic — `ClaudeCodeRoute(cli_model_flag="sonnet"/"opus")` over the existing driver — is unchanged.
      **Recommendation:** Do not amend ADR-0004 as part of T01; flag for the Auditor's surface-cite check at audit time. Consider a standalone ADR amendment at M12 close-out.

- [x] **TA-LOW-04 — Reorder §Grounding architecture cite** (severity: LOW, source: task_analysis.md round 3)
      Current order is `architecture.md §4.1 / §4.2`. The cascade primitive resolves in §4.2 (graph layer where `TieredNode` lives); §4.1 (primitives schema) is the secondary anchor. Cosmetic.
      **Recommendation:** Reorder to `§4.2 (graph adapters where TieredNode resolves the tier) / §4.1 (primitives where TierConfig is defined)` for narrative clarity.

- [x] **TA-LOW-05 — pricing.yaml spot-check** (severity: LOW, source: task_analysis.md round 3)
      `pricing.yaml` already carries `claude-opus-4-7`, `claude-sonnet-4-6`, and `claude-haiku-4-5-20251001` at zero rate. `_find_primary_key` (claude_code.py:251-267) resolves `--model sonnet` to `claude-sonnet-4-6` via substring match, so AC-3's pricing-coverage hedge usually won't fire.
      **Recommendation:** Spot-check the actual `modelUsage` keys returned by a real `--model sonnet` call (e.g. `claude --print --output-format json --model sonnet --tools '' 'ping'`); if it returns a date-suffixed ID not in `pricing.yaml`, add at zero rate citing Max flat-rate.
