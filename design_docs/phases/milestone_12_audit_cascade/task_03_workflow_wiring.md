# Task 03 — Workflow wiring (module-constant cascade enable + planner / slice_refactor integration)

**Status:** 📝 Planned (drafted 2026-04-27, rewritten 2026-04-27 to apply KDR-014 / ADR-0009).
**Grounding:** [milestone README](README.md) · [ADR-0004 §Decision items 3 + 5](../../adr/0004_tiered_audit_cascade.md) · [ADR-0009 — framework owns quality policy](../../adr/0009_framework_owns_policy.md) · [architecture.md §4.2 / §4.3 / §9 KDR-004 / KDR-006 / KDR-011 / KDR-014](../../architecture.md) · [task_02 close-out (cascade primitive landed)](task_02_audit_cascade_node.md) · [graph/audit_cascade.py](../../../ai_workflows/graph/audit_cascade.py) · [workflows/planner.py:148-160 (PlannerInput)](../../../ai_workflows/workflows/planner.py#L148-L160) · [workflows/slice_refactor.py:413-470 (SliceRefactorInput)](../../../ai_workflows/workflows/slice_refactor.py#L413-L470).

## What to Build

Wire the `AuditCascadeNode` (T02) into the `planner` and `slice_refactor` workflows as **opt-in, default-off** behaviour. The opt-in is a **module-level constant per workflow** (`_AUDIT_CASCADE_ENABLED_DEFAULT`), with operator override via env vars (`AIW_AUDIT_CASCADE`, `AIW_AUDIT_CASCADE_<WORKFLOW>`) read once at module import. Per **KDR-014** (ADR-0009): quality knobs do not land on `*Input` models, `WorkflowSpec` fields, or CLI flags. The decision is made once per Python process; the compiled graph reflects it; no input-schema field, no dispatch-layer plumbing, no runtime conditional edge keyed off the policy flag.

Per ADR-0004 §Decision item 3 the cascade pairs only nodes whose output is **read downstream** by another graph node:

- **planner workflow** — `planner-explorer` (Gemini Flash) produces an `ExplorerReport` consumed by `planner-synth`. Cascade target: `auditor-sonnet`. The `planner-synth` (Opus) terminal output is **not audited** (top tier — ADR-0004 §Decision item 3).
- **slice_refactor workflow** — `slice-worker` (Qwen) produces output consumed by the apply step. Cascade target: `auditor-sonnet`. The composed `planner` sub-graph inherits the planner workflow's wiring (cascade flips at the planner module's constant, not separately at slice_refactor).
- **summarize_tiers workflow** — out of scope for T03 (the README's exit criterion #5 explicitly names `planner` + `slice_refactor` only). Summarize is a terminal-output workflow with no downstream consumer in-tree; if a future caller composes it, T05's MCP standalone `run_audit_cascade` is the appropriate surface.

Default-off everywhere at T03 landing — no workflow flips its module constant to `True`. Telemetry (T04) is the empirical surface that drives any subsequent default flip; flipping is a one-line code edit to `_AUDIT_CASCADE_ENABLED_DEFAULT`, no migration of any downstream caller required.

## Key architectural decision (locked 2026-04-27, ADR-0009 / KDR-014)

The drafted T03 originally proposed `audit_cascade_enabled: bool = False` on `PlannerInput` and `SliceRefactorInput`. Round-1 task analysis (`task_analysis.md`) surfaced 3 HIGH findings clustered around the dispatch-layer plumbing required to thread the field from `Input` → `_dispatch._build_initial_state` → `builder(**kwargs).compile(...)`. The threading machinery does not exist; adding it would change the `WorkflowBuilder` type signature, introduce signature introspection in dispatch, and break the spec-API workflow loader.

ADR-0009 / KDR-014 **rejects the input-field approach** and locks the module-constant + env-var pattern instead. The H1/H2/H3 findings dissolve under this rewrite — there is no kwarg-threading to do because the decision is at module-import time, before `build_planner()` is called.

## Deliverables

### [ai_workflows/workflows/planner.py](../../../ai_workflows/workflows/planner.py)

#### Module-level cascade enable (NEW, top of file after imports)

```python
import os

# M12 T03 / ADR-0009 / KDR-014 — quality policy lives at module level.
# Framework-author default; flip to True post-T04 telemetry per workflow,
# code-edit + commit + release. NO `audit_cascade_enabled` field on
# PlannerInput; per KDR-014 quality knobs MUST NOT land on Input models.
_AUDIT_CASCADE_ENABLED_DEFAULT = False

# Operator override (read at module-import). Two granularities:
#   AIW_AUDIT_CASCADE=1                — flips ALL workflows that consult it.
#   AIW_AUDIT_CASCADE_PLANNER=1        — flips ONLY this workflow.
# Per-workflow takes precedence by being checked alongside the global.
_AUDIT_CASCADE_ENABLED = (
    _AUDIT_CASCADE_ENABLED_DEFAULT
    or os.getenv("AIW_AUDIT_CASCADE", "0") == "1"
    or os.getenv("AIW_AUDIT_CASCADE_PLANNER", "0") == "1"
)
```

#### `build_planner()` (existing) — branch on `_AUDIT_CASCADE_ENABLED`

The explorer-node construction site flips between the existing M11-shape `tiered_node + validator_node` pair and the cascaded `audit_cascade_node(auditor_tier="auditor-sonnet")` introduced at T02. **Single branch in source, single graph topology compiled**, regardless of branch chosen.

```python
def build_planner() -> StateGraph:
    if _AUDIT_CASCADE_ENABLED:
        explorer_node = audit_cascade_node(
            primary_tier="planner-explorer",
            primary_prompt_fn=_explorer_prompt,
            primary_output_schema=ExplorerReport,
            auditor_tier="auditor-sonnet",
            # Other args per T02's audit_cascade_node signature.
        )
    else:
        # Existing M11-shape: TieredNode → ValidatorNode pair.
        explorer_node = tiered_node(
            tier="planner-explorer",
            prompt_fn=_explorer_prompt,
            response_format=ExplorerReport,
        )
        # ... existing validator pairing ...
    # ... rest of build unchanged ...
```

The branch lives at one source site. Per ADR-0009: the compiled graph reflects the decision; there is no runtime conditional edge keyed off the cascade flag.

#### `PlannerInput` — UNCHANGED

`PlannerInput` does **NOT** grow an `audit_cascade_enabled` field. Per KDR-014, quality knobs do not land on `*Input` models. End-user invocations (`aiw run planner --goal X`) and the MCP `run_workflow` tool stay exactly as they were.

#### Module docstring update

The `planner.py` module docstring grows a "Quality knobs" subsection naming the module-level constant + env-var override pattern, citing ADR-0009 / KDR-014. One paragraph, ~5 lines.

### [ai_workflows/workflows/slice_refactor.py](../../../ai_workflows/workflows/slice_refactor.py)

Same pattern applied:

```python
_AUDIT_CASCADE_ENABLED_DEFAULT = False
_AUDIT_CASCADE_ENABLED = (
    _AUDIT_CASCADE_ENABLED_DEFAULT
    or os.getenv("AIW_AUDIT_CASCADE", "0") == "1"
    or os.getenv("AIW_AUDIT_CASCADE_SLICE_REFACTOR", "0") == "1"
)
```

The `slice-worker` node-construction site branches on `_AUDIT_CASCADE_ENABLED`. The composed `planner` sub-graph inherits the planner module's own cascade decision (the planner sub-graph is built by importing `build_planner()` — its compiled graph reflects whatever the planner module decided at its own import).

`SliceRefactorInput` — UNCHANGED.

### [ai_workflows/workflows/summarize_tiers.py](../../../ai_workflows/workflows/summarize_tiers.py)

OUT OF SCOPE for T03. The summarize workflow is a terminal-output workflow with no downstream graph consumer; cascade does not apply per ADR-0004 §Decision item 3. T01 already added `auditor-sonnet` and `auditor-opus` tiers to the summarize tier registry — those tiers are reachable for T05's standalone `run_audit_cascade` MCP tool but are not wired into the summarize graph.

### [ai_workflows/_dispatch.py](../../../ai_workflows/workflows/_dispatch.py) — UNCHANGED

`_dispatch.py` is **NOT** modified at T03. Per KDR-014 the cascade decision is made before `build_planner()` is called; there is no kwarg-threading, no signature introspection, no spec-API loader change. This is the load-bearing reduction in T03's surface area compared to the original draft.

### Spec-API workflow loader — UNCHANGED

`WorkflowSpec` does NOT grow an `audit_cascade_enabled` field per ADR-0009 / KDR-014. Spec-API workflows that want cascade either:

1. Set the env var (operator path), or
2. Bake the choice into their own workflow source file (KDR-013 user-owned-code path — the consumer's workflow module reads its own env var or hardcodes the constant).

### [CHANGELOG.md](../../../CHANGELOG.md)

Under `## [Unreleased]`, add a `### Added — M12 Task 03: Workflow wiring (cascade opt-in via module constant + env var) (YYYY-MM-DD)` entry. List:

- Files touched: `ai_workflows/workflows/planner.py` (module constant + env-var override + build_planner() branch + docstring), `ai_workflows/workflows/slice_refactor.py` (same pattern).
- ADR-0009 / KDR-014 referenced as the architectural lock that drove the implementation shape.
- ZERO diff at: `ai_workflows/workflows/_dispatch.py`, `ai_workflows/workflows/spec.py`, any `*Input` model, any MCP tool schema. (The spec-API loader, dispatch path, and public Input contracts are explicitly preserved.)
- KDR-003 guardrail tests still green (no new `anthropic` SDK surface; the `auditor-sonnet` / `auditor-opus` tiers from T01 are already in place and route through `ClaudeCodeSubprocess`).

### Tests

Three test landing sites:

#### `tests/workflows/test_planner_cascade_enable.py` (NEW)

1. `test_audit_cascade_disabled_by_default` — import `planner` with no env vars set; assert `_AUDIT_CASCADE_ENABLED is False`. Compile `build_planner()` and assert the explorer-node count + shape match the M11-era graph (no cascade sub-graph nodes).
2. `test_audit_cascade_enabled_via_global_env` — `monkeypatch.setenv("AIW_AUDIT_CASCADE", "1")` BEFORE re-importing the planner module (use `importlib.reload`); assert `_AUDIT_CASCADE_ENABLED is True`. Compile and assert the explorer-node is now wrapped in a cascade sub-graph (asserted via the cascade primitive's structural marker — see T02's compiled-graph fixture).
3. `test_audit_cascade_enabled_via_per_workflow_env` — same as #2 but with `AIW_AUDIT_CASCADE_PLANNER=1` instead. Assert behaviour matches the global-env case.
4. `test_planner_input_unchanged_at_t03` — verify `PlannerInput.model_fields` does NOT contain `audit_cascade_enabled` (regression guard for KDR-014).

#### `tests/workflows/test_slice_refactor_cascade_enable.py` (NEW)

1. `test_audit_cascade_disabled_by_default` — analogue of test #1 above.
2. `test_audit_cascade_enabled_via_global_env` — analogue of #2.
3. `test_audit_cascade_enabled_via_per_workflow_env` — `AIW_AUDIT_CASCADE_SLICE_REFACTOR=1`.
4. `test_slice_refactor_input_unchanged_at_t03` — `SliceRefactorInput.model_fields` regression guard.
5. `test_planner_subgraph_inherits_planner_module_decision` — set `AIW_AUDIT_CASCADE_PLANNER=1` only (not `AIW_AUDIT_CASCADE_SLICE_REFACTOR`); compile `build_slice_refactor()`; assert the composed planner sub-graph has the cascade wrapper (planner's decision propagates) and the slice-worker node does NOT (slice_refactor's decision was off).

#### `tests/test_kdr_014_no_quality_fields_on_input_models.py` (NEW, top-level)

A guard test that walks every `*Input` model and every `WorkflowSpec` and asserts no field name matches the regex `audit_cascade_enabled|validator_strict|retry_budget|tier_default|.*_policy`. Catches future spec-drift where a Builder might quietly add a quality knob to a public input contract. Failure mode: prints the offending model + field, recommends moving to module-constant + env-var per KDR-014.

### Smoke test (Code-task verification — non-inferential)

The Auditor MUST run this end-to-end smoke before grading T03's ACs:

```bash
# Disabled-default path (no env var):
uv run python -c "
from ai_workflows.workflows import build_planner, planner
assert planner._AUDIT_CASCADE_ENABLED is False
graph = build_planner()
# Sanity: graph compiles, explorer node is non-cascade shape
print('OK: cascade disabled by default')
"

# Enabled-via-env path:
AIW_AUDIT_CASCADE=1 uv run python -c "
import importlib
from ai_workflows.workflows import planner as planner_module
importlib.reload(planner_module)  # re-read env at import
assert planner_module._AUDIT_CASCADE_ENABLED is True
graph = planner_module.build_planner()
print('OK: cascade enabled via AIW_AUDIT_CASCADE=1')
"
```

Both invocations must print their `OK:` line. The smoke fails closed: any assertion failure or import failure means T03 isn't shippable.

## Acceptance Criteria

- [ ] `ai_workflows/workflows/planner.py` grows `_AUDIT_CASCADE_ENABLED_DEFAULT` (module constant, default `False`) and `_AUDIT_CASCADE_ENABLED` (env-var-aware, read at module import).
- [ ] `build_planner()` branches once on `_AUDIT_CASCADE_ENABLED` to wrap the explorer node in `audit_cascade_node(auditor_tier="auditor-sonnet")` from T02.
- [ ] `ai_workflows/workflows/slice_refactor.py` grows the same pattern with `AIW_AUDIT_CASCADE_SLICE_REFACTOR` per-workflow override.
- [ ] `slice_refactor`'s composed planner sub-graph inherits the planner module's cascade decision (via planner's own module-level constant, not via slice_refactor plumbing).
- [ ] `PlannerInput.model_fields` does NOT contain `audit_cascade_enabled` (KDR-014 regression guard).
- [ ] `SliceRefactorInput.model_fields` does NOT contain `audit_cascade_enabled` (KDR-014 regression guard).
- [ ] `WorkflowSpec.model_fields` does NOT contain `audit_cascade_enabled` (KDR-014 regression guard).
- [ ] ZERO diff at `ai_workflows/workflows/_dispatch.py`, `ai_workflows/workflows/spec.py`, any MCP tool schema in `ai_workflows/mcp/`, or any CLI flag in `ai_workflows/cli.py`.
- [ ] All 9+ new tests pass (4 in planner test file, 5 in slice_refactor test file, 1 KDR-014 guard).
- [ ] KDR-003 guardrail tests still green: `tests/workflows/test_slice_refactor_e2e.py:test_kdr_003_no_anthropic_in_production_tree` and `tests/workflows/test_planner_synth_claude_code.py:test_no_anthropic_sdk_import_in_planner_or_claude_code_driver`.
- [ ] Smoke (disabled-default + enabled-via-env) prints both `OK:` lines.
- [ ] `uv run pytest` + `uv run lint-imports` (4 contracts kept — no new contract at T03) + `uv run ruff check` all clean.
- [ ] CHANGELOG entry under `[Unreleased]` cites ADR-0009 / KDR-014 and notes the zero-diff areas.
- [ ] Status surfaces flipped together: spec `**Status:**` line, milestone README task-table row 03, milestone README §Exit-criteria bullet 5 (the `audit_cascade_enabled` opt-in row — verbiage updates to reflect module-constant pattern, not Input field).

## Dependencies

- **T02** — `audit_cascade_node` primitive must exist. **Met:** T02 shipped at `fc8ef19`.
- **T01** — `auditor-sonnet` / `auditor-opus` tiers must exist in the workflow registries. **Met:** T01 shipped at `a7f3e8f`.
- **ADR-0009 / KDR-014** — must be committed to architecture.md §9 + the ADR file before T03 implements (per autonomous-mode KDR-isolation rule, KDR additions land on a separate isolated commit).

## Out of scope (explicit)

- **No edit to `_dispatch.py`.** Per KDR-014, dispatch is unchanged at T03.
- **No edit to `WorkflowSpec`** (`spec.py`). Per KDR-014, declarative-API workflows do not get an `audit_cascade_enabled` spec-field; spec-API workflow authors set their own module constants per KDR-013.
- **No edit to any `*Input` model.** Per KDR-014.
- **No edit to MCP tool schemas** (`mcp/server.py`). The standalone `run_audit_cascade` MCP tool lands at T05 with its own input schema (which IS allowed to take cascade-target tiers as inputs since standalone audit IS the workflow's purpose, not a quality-knob on an unrelated workflow).
- **No edit to `summarize_tiers.py`'s `build` (if it had one)** — summarize workflow is terminal-output; cascade does not apply.
- **No telemetry / role-tagging on TokenUsage.** Lands at T04.
- **No new MCP tool.** Lands at T05.
- **No eval fixture convention.** Lands at T06.
- **No default flip.** Both workflows ship default-off; flipping requires post-T04 telemetry justification and a new milestone-or-task with its own commit.

## Carry-over from prior audits

- *None at draft time. T02's audit produced no carry-over for T03.*

## Carry-over from task analysis

- *To be populated after the rewritten spec is re-analyzed by `task-analyzer` in `/clean-tasks` round 1. The original draft's HIGH findings (H1: dispatch-layer plumbing missing; H2: SliceRefactorInput discards the field; H3: smoke test non-functional) ALL DISSOLVE under this rewrite per ADR-0009 — there is no kwarg to thread, no field to discard, no dispatch path to verify.*

## Propagation status

- **ADR-0009** must commit on its own isolated commit before T03 implements (autonomous-mode KDR-isolation rule).
- **architecture.md §9** grows the KDR-014 row in that same isolated commit.
- **ADR-0004 §Decision item 5** carries a stale "build-time-vs-runtime semantic shifts" framing that's superseded by ADR-0009's module-import-time decision. Forward-deferred to **M12 T07 (milestone close-out)** — same destination as T01's TA-LOW-03 deferral about ADR-0004 line 25.
- **README §Exit-criteria bullet 5** carries the `audit_cascade_enabled: bool = False` field framing that's superseded by this spec's module-constant pattern. Update at T03 close-out as part of the status-surface flip.
