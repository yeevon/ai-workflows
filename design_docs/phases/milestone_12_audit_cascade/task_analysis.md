# milestone_12_audit_cascade — Task Analysis

**Round:** 3
**Analyzed on:** 2026-04-27
**Specs analyzed:** `task_01_auditor_tier_configs.md`
**Analyst:** task-analyzer agent

T02–T07 specs are deferred per the milestone README's explicit policy ("T01 is spec'd below; T02–T07 are written at each predecessor's close-out") and are intentionally absent — not flagged.

Round 2 surfaced 0 HIGH + 2 MEDIUM + 5 LOW. The orchestrator applied both MEDIUM fixes (CHANGELOG-bullet rewrite at spec lines 64-68 + test-section restructure at spec lines 41-52). Round 3 verifies those landed cleanly and re-stress-tests the spec from scratch.

**Round 3 verdict: structural surface is now clean.** No HIGH or MEDIUM remain. Five LOW findings carry over from round 2 (still un-pushed — the spec has no `## Carry-over from task analysis` section yet) plus zero new LOWs surfaced this round. Per the task-analyzer contract, LOWs are pushed to the spec's carry-over section by the orchestrator and the loop exits.

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 0 |
| 🟢 LOW | 5 |
| Total | 5 |

**Stop verdict:** LOW-ONLY

(Per the orchestrator contract: zero HIGH and zero MEDIUM, LOWs exist → push LOWs to spec carry-over and exit.)

**Pushdown status (2026-04-27):** all 5 LOWs (L1–L5) pushed to `task_01_auditor_tier_configs.md` `## Carry-over from task analysis` section as TA-LOW-01..05 by /autopilot orchestrator. `pushed=true`.

## Findings

### 🟢 LOW

#### L1 — `claude_code.py:254` cross-reference still in §Grounding line 4 and §What-to-Build line 10 (round-1 L4 / round-2 L2 carry-over not landed)

**Task:** `task_01_auditor_tier_configs.md`
**Location:** spec line 4 (Grounding) cites `[claude_code.py:9,119-129,254]`; spec line 10 cites `[claude_code.py:254](.../claude_code.py#L254)`.
**Issue:** Verified: `claude_code.py:254` is inside `_find_primary_key` — `lowered = cli_flag.lower()` and the substring-match loop (verified: full helper at lines 251-267 of `ai_workflows/primitives/llm/claude_code.py`). That line is a modelUsage-key resolution helper, not a `--model` flag site. The actual `--model` argv-assembly lines are 124-125 (`"--model", self._route.cli_model_flag,` — verified). The `:9` cite is correct (line 9 is the module-docstring mention of `opus / sonnet / haiku`). The `:119-129` cite is correct (the argv block).

**Recommendation:** Drop `,254` from line 4 and either drop the line-10 cite entirely or repoint it to `claude_code.py:124-125` (the actual `--model` argv assembly).

**Apply this fix (mechanical):**

old_string:
```
**Grounding:** [milestone README](README.md) · [ADR-0004](../../adr/0004_tiered_audit_cascade.md) · [architecture.md §4.1 / §4.2](../../architecture.md) · [KDR-003 / KDR-011](../../architecture.md) · [claude_code.py:9,119-129,254](../../../ai_workflows/primitives/llm/claude_code.py).
```

new_string:
```
**Grounding:** [milestone README](README.md) · [ADR-0004](../../adr/0004_tiered_audit_cascade.md) · [architecture.md §4.1 / §4.2](../../architecture.md) · [KDR-003 / KDR-011](../../architecture.md) · [claude_code.py:9,119-129](../../../ai_workflows/primitives/llm/claude_code.py).
```

The line-10 `[claude_code.py:254]` cite should be dropped or repointed to `[claude_code.py:124-125]` — orchestrator's choice.

**Push to spec:** yes — append to a new `## Carry-over from task analysis` section: *"Drop `,254` from §Grounding `claude_code.py:9,119-129,254` citation; line 254 is inside `_find_primary_key`, not a `--model` flag site. The §What-to-Build line-10 `claude_code.py:254` cite should be dropped or repointed to `claude_code.py:124-125` (the actual argv `--model` assembly)."*

#### L2 — Builder-time test hygiene: tests #1/#2 should narrow with `isinstance(route, ClaudeCodeRoute)` before asserting `cli_model_flag` (round-1 L1 carry-over not landed)

**Task:** `task_01_auditor_tier_configs.md`
**Issue:** Round-2's M2 fix correctly added `isinstance(route, ClaudeCodeRoute)` narrowing into the test-section deliverable text (verified at spec line 47). But this is a Builder-implementation hygiene reminder rather than a spec-correctness issue per se — it's now spec'd correctly. The remaining LOW concern is that downstream auditors should verify the narrowing actually lands in the implementation (mypy will warn on the unsafe attribute access without it; mirroring the existing line-235 `isinstance(synth.route, ClaudeCodeRoute)` pattern at `tests/workflows/test_planner_synth_claude_code.py:232-239` is mandatory for type-checked test code). Nothing to fix in the spec; informational push for the Builder.
**Recommendation:** Push as carry-over so the Builder remembers to mirror the existing `synth.route` narrowing.
**Push to spec:** yes — append: *"In tests #1 and #2, narrow with `isinstance(route, ClaudeCodeRoute)` before asserting `route.cli_model_flag` (mirrors the existing `tests/workflows/test_planner_synth_claude_code.py:235` pattern; required for mypy under the union route type `LiteLLMRoute | ClaudeCodeRoute`)."*

#### L3 — ADR-0004 §Decision item 1 still names `ai_workflows/primitives/tiers.py` as the auditor-tier landing site (round-2 L3 carry-over not landed)

**Task:** `task_01_auditor_tier_configs.md`
**Location:** `design_docs/adr/0004_tiered_audit_cascade.md:25` reads: *"Both sit in the `TierRegistry` (`ai_workflows/primitives/tiers.py`) next to `planner-synth`."*
**Issue:** Verified — that's the same misframing the round-1 H3 fix corrected in the spec. The spec correctly redirects T01's landing to workflow-scoped registries (`workflows/planner.py`, `workflows/summarize_tiers.py`); the ADR text is stale. Not a T01-blocking concern (the spec doesn't claim to amend the ADR), but a downstream Auditor reading ADR-0004 to verify the spec at audit-time would see the contradiction.
**Recommendation:** Push as carry-over with a no-action note for the Builder. ADR-0004 amendment is out of T01 scope — the user / orchestrator decides whether to amend the ADR at M12 close-out or leave it as a known-stale framing.
**Push to spec:** yes — append: *"Note for the Auditor: ADR-0004 §Decision item 1 (line 25) names `ai_workflows/primitives/tiers.py` as the landing site for the auditor tiers. That framing is superseded by this spec's workflow-scoped landing (`workflows/planner.py`, `workflows/summarize_tiers.py`); the ADR's mechanic — `ClaudeCodeRoute(cli_model_flag="sonnet"/"opus")` over the existing driver — is unchanged. Do not amend the ADR as part of T01; flag for the Auditor's surface-cite check at audit time and consider ADR amendment at M12 close-out."*

#### L4 — Spec §Grounding cites `architecture.md §4.1 / §4.2`; cleaner ordering is §4.2 (graph layer where TieredNode resolves) primary, §4.1 (primitives schema) secondary (round-2 L4 carry-over not landed)

**Task:** `task_01_auditor_tier_configs.md`
**Location:** spec line 4 (Grounding).
**Issue:** Both sections are technically relevant. The cascade primitive runs in §4.2 (graph layer — `TieredNode` resolves the tier and lives at `ai_workflows/graph/tiered_node.py`); §4.1 (primitives) is where `TierConfig` and `ClaudeCodeRoute` are defined. The dual-cite is correct in spirit but the ordering leads with §4.1 (primitives), which downplays the cascade-relevant resolution path. Cosmetic.
**Recommendation:** Push as carry-over.
**Push to spec:** yes — append: *"Optional: reorder §Grounding architecture cite to `§4.2 (graph adapters where TieredNode resolves the tier) / §4.1 (primitives where TierConfig is defined)` for narrative clarity; current ordering is technically correct but downplays the resolution-path layer."*

#### L5 — pricing.yaml spot-check: AC-3's hedge ("if the CLI's `modelUsage` returns a model ID not yet in the file, add it at zero rate") is unlikely to fire — `pricing.yaml` already ships `claude-opus-4-7`, `claude-sonnet-4-6`, and `claude-haiku-4-5-20251001` at $0 (round-2 L5 carry-over not landed)

**Task:** `task_01_auditor_tier_configs.md`
**Location:** spec line 74 (AC-3); `pricing.yaml:12-19` (verified — three Claude entries already at zero rate).
**Issue:** Verified `pricing.yaml` (root of repo) already carries:
- `claude-opus-4-7: input_per_mtok: 0.0 / output_per_mtok: 0.0`
- `claude-sonnet-4-6: input_per_mtok: 0.0 / output_per_mtok: 0.0`
- `claude-haiku-4-5-20251001: input_per_mtok: 0.0 / output_per_mtok: 0.0`

`_find_primary_key` (claude_code.py:251-267, verified) does substring matching, so `--model sonnet` will resolve to `claude-sonnet-4-6` cleanly via the lowered-substring loop. AC-3's hedge is therefore a defensive note, not an expected action. The Builder should still spot-check the actual `modelUsage` keys returned by `--model sonnet` and `--model opus` calls (they could include date-suffixed IDs like `claude-sonnet-4-6-20251001` that aren't yet in the file), and add any missing date-suffixed entries at zero rate per the AC's hedge.
**Recommendation:** Push as carry-over — the AC text is correct; this is just an empirical-spot-check reminder for the Builder.
**Push to spec:** yes — append: *"pricing.yaml spot-check: the file already carries `claude-opus-4-7`, `claude-sonnet-4-6`, and `claude-haiku-4-5-20251001` at zero rate. `_find_primary_key` (claude_code.py:251-267) resolves `--model sonnet` to `claude-sonnet-4-6` via substring match, so AC-3's pricing-coverage hedge usually won't fire. Spot-check the actual `modelUsage` keys returned by a real `--model sonnet` call (e.g. `claude --print --output-format json --model sonnet --tools '' 'ping'`); if it returns a date-suffixed ID not in `pricing.yaml`, add at zero rate citing Max flat-rate."*

## What's structurally sound

Round 3 verifies all round-1 and round-2 fixes held up under fresh stress-testing:

- **Round-2 M1 fix held.** CHANGELOG bullets (spec lines 64-68) correctly name `workflows/planner.py`, `workflows/summarize_tiers.py`, and `workflows/slice_refactor.py` as touched files; explicitly note zero diff at `primitives/tiers.py` / `graph/` / `mcp/`. The internal contradiction with the deliverable headings is gone. The round-2 finding's exact replacement text is in place verbatim.
- **Round-2 M2 fix held.** Test-section heading is now `### Tests — registry shape (workflow layer) + override precedence (graph layer)` (verified at spec line 41). Workflow-layer tests #1 and #2 are pinned to `tests/workflows/` (alongside `test_planner_synth_claude_code.py:test_planner_synth_tier_points_at_claude_code_opus`); graph-layer test #3 is pinned to `tests/graph/`. Test #1 includes the `isinstance(route, ClaudeCodeRoute)` narrowing and the optional `route.kind == "claude_code"` assertion. The non-existent `tests/primitives/test_tiers.py` reference is gone.
- **Round-1 H1-H4 fixes held** (re-verified):
  - `_resolve_tier_name` does not appear; `_resolve_tier` is correctly cited at module level with the `(logical, state, configurable)` signature (verified at `ai_workflows/graph/tiered_node.py:381` — three-arg signature confirmed).
  - `pricing={...}` and `input_per_million` / `output_per_million` strings remain absent.
  - Workflow-scoped registries (`planner.py`, `slice_refactor.py`, `summarize_tiers.py`) are the named landing sites; verified at `planner.py:647` (`def planner_tier_registry`), `slice_refactor.py:1568` (`def slice_refactor_tier_registry`), `summarize_tiers.py:22` (`def summarize_tier_registry`).
  - "M5 T02" is the planner-synth shape origin (no bogus M3 T07 / M5 T05).
- **Round-1 M1-M4 fixes held** (re-verified):
  - `summarize_tier_registry()` is in the deliverables list with KDR-011 scope-rule rationale.
  - "KDR-003 guardrail — verify, don't extend" framing is in place; both grep-test names verified at `tests/workflows/test_slice_refactor_e2e.py:410` (`test_kdr_003_no_anthropic_in_production_tree`) and `tests/workflows/test_planner_synth_claude_code.py:312` (`test_no_anthropic_sdk_import_in_planner_or_claude_code_driver`).
  - Status-surface AC bullet (line 82) names spec status line + README task-table row + Exit-criteria bullet 1; correctly notes there is no `tasks/README.md` for M12.
- **M11 dependency satisfied.** Verified M11 is `✅ complete (2026-04-22)` per roadmap.md line 24 and `milestone_11_gate_review/README.md:3`.
- **KDR-003 preserved by construction at T01.** New tier configs use `ClaudeCodeRoute(cli_model_flag="sonnet"/"opus")` — same OAuth subprocess path the existing `planner-synth` runs on; no new env reads, no `anthropic` SDK surface. The driver's argv assembly (verified at `claude_code.py:119-129`) accepts `self._route.cli_model_flag` verbatim.
- **Layer rule preserved.** New entries land in `workflows/*` (which legitimately imports `primitives.tiers`); no `primitives → graph` or `graph → workflows` upward edges. AC-9's `lint-imports` 4-contract count is correct (verified — `pyproject.toml` carries exactly four `[[tool.importlinter.contracts]]` blocks; the M12 5th contract lands at T02).
- **Other KDRs (002 / 004 / 006 / 008 / 009 / 013) undisturbed at T01.** T01 is purely additive registry data.
- **Cross-task dependency claim verified.** Spec line 86 says "T02 (the cascade primitive) depends on T01; T03/T04/T05/T06 all depend on T02"; the README task table (lines 64-69) and ADR-0004 §Decision agree.
- **No new HIGH or MEDIUM surfaced under fresh stress-test.** The spec is structurally sound: every cited line number, function name, test name, registry function, and KDR reference resolves against the live codebase.

## Cross-cutting context

- **Project memory state (CS300 pivot active).** Per `MEMORY.md` + `project_m13_shipped_cs300_next.md`, ai-workflows is in CS300 hold-mode for M10 / M15 / M17. M12 is **not on hold** — the README still lists it as `📝 Planned` and the spec hardening is happening proactively. Specs hardened across rounds 1–3 sit ready until M12's go-ahead. Informational, not a finding.
- **0.3.1 is live on PyPI; 0.3.0 yanked** (per `project_0_3_1_live.md`). T01 is registry-data-only; adding two entries to `planner_tier_registry()`'s return dict is a new-key addition, not a contract break. The non-skippable real-install gate at `tests/release/test_install_smoke.py` continues to fire as a regression guard.
- **`nice_to_have.md` slot range:** highest-numbered section is **§23** (verified by `grep -n "^## " design_docs/nice_to_have.md | tail -10` — sections 15-23). T01 does not propose any new `nice_to_have.md` entry. The spec's `per_call_timeout_s` deviation forward-note (line 101) lands at §24+ if it fires. No slot-drift risk.
- **ADR-0004 carries a stale tier-location framing** (L3 above) — the ADR text says auditor tiers land in `primitives/tiers.py`. Not a T01-blocking finding because the spec correctly redirects, but worth surfacing to the user for an eventual ADR amendment when M12 closes.
- **summarize workflow uses M19 spec API.** Verified `summarize.py` consumes `summarize_tier_registry()` via `WorkflowSpec(tiers=..., ...)` — adding auditor entries to the registry will propagate into the spec automatically. No spec-API edit required at T01.
- **Round-3 conclusion.** The structural pass on T01 is complete. The five LOWs are wordsmithing, cross-reference fragility, and Builder-time test-hygiene reminders — none gate implementation. Orchestrator should push them to a fresh `## Carry-over from task analysis` section at the spec's bottom (above or beside the existing `## Propagation status` heading) and exit the `/clean-tasks` loop.
