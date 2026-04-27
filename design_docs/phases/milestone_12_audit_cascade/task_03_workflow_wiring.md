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
# Semantics: per-workflow var is ENABLE-ONLY when the global is on.
# To DISABLE a single workflow when AIW_AUDIT_CASCADE=1 is set, unset
# the global and re-enable the workflows you want via per-workflow vars.
# (Three-state per-workflow override deferred — see ADR-0009 §Open questions.)
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
            policy=PLANNER_RETRY_POLICY,
            name="planner_explorer_audit",  # workflow-distinguishing prefix; see §State-channel additions
            # Other args per T02's audit_cascade_node signature.
        )
    else:
        # Existing M11-shape: wrap_with_error_handler(tiered_node) — preserve
        # the live planner.py:475-483 wrapper. NB: tiered_node's kwarg is
        # `output_schema=` (NOT `response_format=`).
        explorer_node = wrap_with_error_handler(
            tiered_node(
                tier="planner-explorer",
                prompt_fn=_explorer_prompt,
                output_schema=ExplorerReport,
                node_name="explorer",
            ),
            node_name="explorer",
        )
        # ... existing explorer_validator + planner + planner_validator construction unchanged ...
    # ... rest of build unchanged ...
```

The branch lives at one source site. Per ADR-0009: the compiled graph reflects the decision; there is no runtime conditional edge keyed off the cascade flag.

#### `PlannerState` — declare cascade-prefixed channels (cascade-enabled path)

When `_AUDIT_CASCADE_ENABLED=True`, the explorer is replaced by the cascade compiled sub-graph, which writes to `planner_explorer_audit_*`-prefixed channels plus the two shared cascade channels (`cascade_role`, `cascade_transcript`). The cascade primitive's outer-state requirement is documented at `tests/graph/test_audit_cascade.py:609-626` (`_OuterState` TypedDict) — LangGraph silently drops writes to undeclared `total=False` keys, so without these declarations the auditor's verdict + transcript would never reach the outer state.

Add to `PlannerState` (planner.py:223-262, `total=False` TypedDict). The 9 channels (using the workflow-distinguishing prefix `planner_explorer_audit` chosen in `build_planner()`'s `audit_cascade_node(name=...)` to avoid collision if a future graph composes two cascades in one outer state):

```python
class PlannerState(TypedDict, total=False):
    # ... existing fields ...

    # M12 T03 — cascade-prefixed channels populated when
    # _AUDIT_CASCADE_ENABLED is True. Inert when False.
    cascade_role: str  # Literal["author", "auditor", "verdict"] in spirit
    cascade_transcript: dict[str, list]  # {"author_attempts": [...], "auditor_verdicts": [AuditVerdict, ...]}
    planner_explorer_audit_primary_output: str
    planner_explorer_audit_primary_parsed: ExplorerReport  # re-bound to existing `explorer_report` channel by downstream
    planner_explorer_audit_primary_output_revision_hint: str | None
    planner_explorer_audit_auditor_output: str
    planner_explorer_audit_auditor_output_revision_hint: str | None
    planner_explorer_audit_audit_verdict: AuditVerdict
    planner_explorer_audit_audit_exhausted_response: str
```

The `total=False` declaration means the channels are typed-but-optional — the disabled-default path doesn't populate them, no runtime error. The 7 prefixed channels are internal to the cascade sub-graph; `cascade_role` + `cascade_transcript` are the two outward-facing channels the rest of the graph (M11 gate-context projection, T04 telemetry) reads.

`SliceRefactorState` grows the same shape with prefix `slice_worker_audit` (matching `audit_cascade_node(name="slice_worker_audit", ...)` in `build_slice_refactor()`) — see §slice_refactor below.

#### `PlannerInput` — UNCHANGED

`PlannerInput` does **NOT** grow an `audit_cascade_enabled` field. Per KDR-014, quality knobs do not land on `*Input` models. End-user invocations (`aiw run planner --goal X`) and the MCP `run_workflow` tool stay exactly as they were.

#### Module docstring update

The `planner.py` module docstring grows a "Quality knobs" subsection naming the module-level constant + env-var override pattern, citing ADR-0009 / KDR-014. One paragraph, ~5 lines.

### [ai_workflows/workflows/slice_refactor.py](../../../ai_workflows/workflows/slice_refactor.py)

Same pattern applied:

```python
# Same enable-only-asymmetry semantics as planner.py: per-workflow var
# cannot disable what the global enables. See planner.py block + ADR-0009
# §Open questions for the three-state-override deferral.
_AUDIT_CASCADE_ENABLED_DEFAULT = False
_AUDIT_CASCADE_ENABLED = (
    _AUDIT_CASCADE_ENABLED_DEFAULT
    or os.getenv("AIW_AUDIT_CASCADE", "0") == "1"
    or os.getenv("AIW_AUDIT_CASCADE_SLICE_REFACTOR", "0") == "1"
)
```

The `slice-worker` node-construction site (inside `_build_slice_branch_subgraph()` at `slice_refactor.py:899-957`) branches on `_AUDIT_CASCADE_ENABLED`, passing `name="slice_worker_audit"` to `audit_cascade_node(...)` so the prefixed channels don't collide with anything else in the branch state. The composed `planner` sub-graph inherits the planner module's own cascade decision (the planner sub-graph is built by importing `build_planner()` — its compiled graph reflects whatever the planner module decided at its own import).

`SliceRefactorInput` — UNCHANGED.

#### `SliceBranchState` — declare cascade channels (Option A, per-branch only)

The slice-worker `tiered_node` lives **inside the per-Send sub-graph** built by `_build_slice_branch_subgraph()` (slice_refactor.py:899-957). Its state is `SliceBranchState` (slice_refactor.py:616-658), not the parent `SliceRefactorState`. The cascade compiled sub-graph runs inside this per-slice branch and writes to channels that must be declared on `SliceBranchState` (LangGraph propagation rule: sub-graph keys reach the parent only when the **parent** declares them too — see slice_refactor.py:568-573 for the existing `slice` channel using the same pattern).

**Decision (locked 2026-04-27 by user arbitration on round-3 H1):** **Option A — cascade channels on `SliceBranchState` only; the parent `SliceRefactorState` does NOT grow cascade channels.** Cascade-exhausted branches surface to the parent through the existing `slice_failures` surface — when a branch's cascade exhausts retries, the branch's terminal `SliceFailure` row encodes the auditor's `failure_reasons` + `suggested_approach` into its `last_error` field (the M11 gate-context projection already surfaces `slice_failures` to the operator via the existing per-slice surface; no new aggregate-cascade channel needed).

Rationale (from user-stated locked decision): operator visibility is satisfied by the existing `slice_failures` surface; per-branch detail lives in LangGraph's per-branch checkpoint state if debug ever needs it; telemetry (T04) flows through `TokenUsage.role` independently of state channels; M11's curated projection doesn't need 30 raw auditor transcripts. Option B's three new parent-side reducers were rejected as real complexity for a parent-level view nobody currently consumes — defer until a concrete consumer surfaces.

Add to `SliceBranchState` (slice_refactor.py:616-658, `total=False` TypedDict):

```python
class SliceBranchState(TypedDict, total=False):
    # ... existing fields (slice, last_exception, _retry_counts, etc.) ...

    # M12 T03 — cascade channels populated when slice_refactor's
    # _AUDIT_CASCADE_ENABLED is True. Per-branch only — parent
    # SliceRefactorState does NOT declare these (Option A locked
    # 2026-04-27; see issue file for round-3 H1 arbitration).
    cascade_role: str  # Literal["author", "auditor", "verdict"] in spirit
    cascade_transcript: dict[str, list]  # {"author_attempts": [...], "auditor_verdicts": [AuditVerdict, ...]}
    slice_worker_audit_primary_output: str
    slice_worker_audit_primary_parsed: SliceResult  # branch-local; not propagated up (SliceResult is the slice-worker's parsed-output type per slice_refactor.py:455)
    slice_worker_audit_primary_output_revision_hint: str | None
    slice_worker_audit_auditor_output: str
    slice_worker_audit_auditor_output_revision_hint: str | None
    slice_worker_audit_audit_verdict: AuditVerdict
    slice_worker_audit_audit_exhausted_response: str
```

The 9 channels are scoped strictly inside `SliceBranchState`. They are read by the cascade sub-graph and by the branch's own `_slice_branch_finalize` step (or equivalent) when a cascade exhausts — that step constructs the `SliceFailure` row and folds the auditor's verdict text (`failure_reasons` joined + `suggested_approach`) into the `last_error` string before the row crosses the branch→parent boundary.

**Parent `SliceRefactorState`: NO cascade-channel additions.** This is the load-bearing distinction from the planner half — planner has no fan-out so its cascade channels live on `PlannerState` directly; slice_refactor fans out N parallel branches via `Send`, so cascade channels stay branch-local and the aggregate surface is `slice_failures` (existing) instead of a new transcript channel.

#### Folding cascade exhaustion into `SliceFailure` — mechanism via `audit_cascade_node(skip_terminal_gate=True)` from T08

**Decision (locked 2026-04-27 by user arbitration on round-4 H1):** **Option A — extend `audit_cascade_node()` with a `skip_terminal_gate: bool = False` parameter.** The amendment lands as a new task **M12 T08** (T02 amendment) which MUST ship before T03 implements. Spec for T08 lives at `task_08_audit_cascade_skip_terminal_gate.md`; commit lands as an isolated T02-amendment commit per autonomy decision 2 (the cascade primitive is shipped behavioural surface — the amendment's KDR-clean classification is verified at T08 audit time, but the isolated-commit posture preserves the audit trail).

When T08 ships, `audit_cascade_node(skip_terminal_gate=True, ...)` produces a cascade sub-graph whose verdict-exhaustion path raises `AuditFailure` outward to the caller's state via the standard `wrap_with_error_handler` → `state['last_exception']` mechanism (instead of routing to the cascade-internal `human_gate`). The default (`False`) preserves T02's existing behaviour exactly — backward-compatible, no SEMVER concern.

T03's slice_refactor cascade integration uses the new parameter:

```python
# Inside _build_slice_branch_subgraph(), if _AUDIT_CASCADE_ENABLED:
slice_worker_node = audit_cascade_node(
    primary_tier="slice-worker",
    primary_prompt_fn=_slice_worker_prompt,
    primary_output_schema=SliceResult,
    auditor_tier="auditor-sonnet",
    policy=SLICE_RETRY_POLICY,
    name="slice_worker_audit",
    skip_terminal_gate=True,  # T08 — branch-local exhaustion folds into SliceFailure
)
```

With `skip_terminal_gate=True`, the cascade's verdict-exhaustion path puts `AuditFailure(...)` into `state['last_exception']` and routes to the sub-graph's normal terminal node (no `interrupt`). The branch's existing `_slice_branch_finalize` step (slice_refactor.py:818-896) — which already keys off `state.get("last_exception")` for the existing exception path at line 869-870 — sees the `AuditFailure` and produces a `SliceFailure` row with the `last_error` field prefixed:

```
audit_cascade_exhausted: {auditor_verdict_count} attempts; reasons=[{joined failure_reasons}]; suggested_approach={suggested_approach or "(none)"}
```

The existing `_slice_branch_finalize` handler grows a small `isinstance(exc, AuditFailure)` branch to render the structured prefix; existing non-cascade `last_error=str(exc)` path stays unchanged. `SliceFailure` schema unchanged (single string field gets a structured prefix). The parent's M11 gate-context projection sees the same `slice_failures` list it always has; cascade-exhaustion failures distinguish by the `audit_cascade_exhausted:` prefix.

**Planner's cascade behaviour at T03 — UNCHANGED from T02 default.** `build_planner()`'s cascade call uses `audit_cascade_node(...)` WITHOUT `skip_terminal_gate=True` (default `False` → existing T02 gate-interrupt behaviour preserved). The planner has no fan-out, so the gate-interrupt-on-exhaustion semantic is correct there — operator gets one interrupt for the planner's explorer cascade, sees the cascade transcript via M11's existing gate-context projection, resumes via standard gate-response mechanism. No T08-dependency for planner-side cascade behaviour.

Only slice_refactor's per-branch cascade needs `skip_terminal_gate=True` (so 30 parallel slices don't trigger 30 parallel operator interrupts). This is the load-bearing reason T08 exists.

### [ai_workflows/workflows/summarize_tiers.py](../../../ai_workflows/workflows/summarize_tiers.py)

OUT OF SCOPE for T03. The summarize workflow is a terminal-output workflow with no downstream graph consumer; cascade does not apply per ADR-0004 §Decision item 3. T01 already added `auditor-sonnet` and `auditor-opus` tiers to the summarize tier registry — those tiers are reachable for T05's standalone `run_audit_cascade` MCP tool but are not wired into the summarize graph.

### [ai_workflows/workflows/_dispatch.py](../../../ai_workflows/workflows/_dispatch.py) — UNCHANGED

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
# Planner — disabled-default path (no env var):
uv run python -c "
from ai_workflows.workflows import build_planner, planner
assert planner._AUDIT_CASCADE_ENABLED is False
graph = build_planner()
# Sanity: graph compiles, explorer node is non-cascade shape
print('OK: planner cascade disabled by default')
"

# Planner — enabled-via-env path:
AIW_AUDIT_CASCADE=1 uv run python -c "
import importlib
from ai_workflows.workflows import planner as planner_module
importlib.reload(planner_module)  # re-read env at import
assert planner_module._AUDIT_CASCADE_ENABLED is True
graph = planner_module.build_planner()
print('OK: planner cascade enabled via AIW_AUDIT_CASCADE=1')
"

# Slice_refactor — disabled-default path:
uv run python -c "
from ai_workflows.workflows import build_slice_refactor, slice_refactor
assert slice_refactor._AUDIT_CASCADE_ENABLED is False
graph = build_slice_refactor()
print('OK: slice_refactor cascade disabled by default')
"

# Slice_refactor — enabled-via-env path:
AIW_AUDIT_CASCADE=1 uv run python -c "
import importlib
from ai_workflows.workflows import slice_refactor as sr
importlib.reload(sr)
assert sr._AUDIT_CASCADE_ENABLED is True
graph = sr.build_slice_refactor()
print('OK: slice_refactor cascade enabled via AIW_AUDIT_CASCADE=1')
"
```

All four invocations must print their `OK:` line. The smoke fails closed: any assertion failure or import failure means T03 isn't shippable. Each invocation is a fresh subprocess so the module-import-time env-var read is honestly tested. The slice_refactor smoke verifies that `build_slice_refactor()` compiles (plus its inner `_build_slice_branch_subgraph()` with the cascade primitive embedded) — round-3 H1 surfaced the silent-drop risk this smoke addition catches.

## Acceptance Criteria

- [ ] `ai_workflows/workflows/planner.py` grows `_AUDIT_CASCADE_ENABLED_DEFAULT` (module constant, default `False`) and `_AUDIT_CASCADE_ENABLED` (env-var-aware, read at module import).
- [ ] `build_planner()` branches once on `_AUDIT_CASCADE_ENABLED` to wrap the explorer node in `audit_cascade_node(auditor_tier="auditor-sonnet")` from T02.
- [ ] `ai_workflows/workflows/slice_refactor.py` grows the same pattern with `AIW_AUDIT_CASCADE_SLICE_REFACTOR` per-workflow override.
- [ ] `slice_refactor`'s composed planner sub-graph inherits the planner module's cascade decision (via planner's own module-level constant, not via slice_refactor plumbing).
- [ ] `PlannerInput.model_fields` does NOT contain `audit_cascade_enabled` (KDR-014 regression guard).
- [ ] `SliceRefactorInput.model_fields` does NOT contain `audit_cascade_enabled` (KDR-014 regression guard).
- [ ] `WorkflowSpec.model_fields` does NOT contain `audit_cascade_enabled` (KDR-014 regression guard).
- [ ] `PlannerState` grows the 9 cascade channels (`cascade_role`, `cascade_transcript`, plus the 7 `planner_explorer_audit_*` prefixed channels) declared `total=False` so the disabled-default path doesn't trip on missing keys; mirror shape from `tests/graph/test_audit_cascade.py:609-626` `_OuterState`.
- [ ] `SliceBranchState` (NOT `SliceRefactorState`) grows the 9 cascade channels with prefix `slice_worker_audit_*`. Per Option A locked 2026-04-27: parent `SliceRefactorState` does NOT declare cascade channels; per-branch detail stays branch-local; aggregate surface is the existing `slice_failures` list.
- [ ] When a branch's cascade exhausts (`max_semantic_attempts` reached without a passing verdict), the branch's terminal step converts the cascade-exhausted state into a `SliceFailure` row (instead of triggering the cascade's internal `human_gate`) with the `last_error` field prefixed `audit_cascade_exhausted: ...` and embedding the auditor's `failure_reasons` + `suggested_approach`. The existing M11 gate-context projection surfaces this row through the existing `slice_failures` list — no schema change at the projection layer or to `SliceFailure` itself.
- [ ] **Parallel fan-out safety:** new pytest `tests/workflows/test_slice_refactor_cascade_enable.py::test_cascade_writes_survive_parallel_fanout` invokes `build_slice_refactor()` end-to-end with `AIW_AUDIT_CASCADE_SLICE_REFACTOR=1`, N≥2 slices, and stub adapters that script per-branch cascade behaviour. Asserts: (a) no `InvalidUpdateError: Can receive only one value per step` on fan-in (proves `SliceBranchState` scoping is correct — the cascade channels never reach the parent for the parallel-write conflict to fire on); (b) cascade-exhausted branches show up in `slice_failures` with the `audit_cascade_exhausted:` prefix; (c) cascade-passed branches show up in `slice_results` as normal.
- [ ] ZERO diff at `ai_workflows/workflows/_dispatch.py`, `ai_workflows/workflows/spec.py`, any MCP tool schema in `ai_workflows/mcp/`, or any CLI flag in `ai_workflows/cli.py`.
- [ ] All 9+ new tests pass (4 in planner test file, 5 in slice_refactor test file, 1 KDR-014 guard).
- [ ] KDR-003 guardrail tests still green: `tests/workflows/test_slice_refactor_e2e.py:test_kdr_003_no_anthropic_in_production_tree` and `tests/workflows/test_planner_synth_claude_code.py:test_no_anthropic_sdk_import_in_planner_or_claude_code_driver`.
- [ ] Smoke (planner + slice_refactor, both disabled-default + enabled-via-env) prints all four `OK:` lines.
- [ ] `uv run pytest` + `uv run lint-imports` (5 contracts kept — T03 adds no new contract; T02's `audit_cascade composes only graph + primitives` contract carries forward) + `uv run ruff check` all clean.
- [ ] CHANGELOG entry under `[Unreleased]` cites ADR-0009 / KDR-014 and notes the zero-diff areas.
- [ ] Status surfaces flipped together: spec `**Status:**` line, milestone README task-table row 03, milestone README §Exit-criteria bullet 5 (the `audit_cascade_enabled` opt-in row — verbiage updates to reflect module-constant pattern, not Input field).

## Dependencies

- **T01** — `auditor-sonnet` / `auditor-opus` tiers must exist in the workflow registries. **Met:** T01 shipped at `a7f3e8f`.
- **T02** — `audit_cascade_node` primitive must exist. **Met:** T02 shipped at `fc8ef19`.
- **T08** — `audit_cascade_node()` `skip_terminal_gate: bool = False` parameter must exist (T02 amendment for cascade-exhausted-without-interrupt path; load-bearing for slice_refactor's per-branch cascade). **Required predecessor — T03 cannot ship until T08 closes.** Spec at `task_08_audit_cascade_skip_terminal_gate.md` (drafted 2026-04-27 after round-4 H1 arbitration). Roadmap-selector's sequential walk must respect this — T08 ships before T03 even though T03's number is lower.
- **ADR-0009 / KDR-014** — must be committed to architecture.md §9 + the ADR file before T03 implements (per autonomous-mode KDR-isolation rule, KDR additions land on a separate isolated commit). **Met:** committed at `91ca343`.

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

- [ ] **M12-T02-LOW-02 (DEFERRED from T02 audit, source: `issues/task_02_issue.md` line 248)** — When this task touches the cascade wiring, drop `RunnableConfig | None` from the `config` annotation on `_wrap_verdict_with_transcript._wrapped` (`audit_cascade.py:478`) and `_stamp_role_on_success._wrapped_with_config` (`audit_cascade.py:533`) — annotate as `RunnableConfig` (defaults to `None` at runtime stays valid) to silence the LangGraph `UserWarning` about non-`Optional` annotations on optional-in-practice params. `_stamp_role_on_success._wrapped_state_only` (line 544) takes no `config` and is unaffected.

- [ ] **M12-T02-LOW-03 (DEFERRED from T02 audit, source: `issues/task_02_issue.md` line 250)** — `audit_cascade_node()` must be called at workflow build time (once per cascade site inside `build_planner()` / `build_slice_refactor()`), not per runtime invocation (e.g. NOT per slice in `slice_refactor`'s slice loop). T03's design honours this by construction (the build-time `if _AUDIT_CASCADE_ENABLED` branch fires once at module-import-driven `build_planner()` entry). Add a one-line invariant comment at each cascade construction site (`# Build-time only — do NOT call audit_cascade_node() in a per-slice or per-step inner loop.`) referencing this constraint so a future Builder can't accidentally regress it.

## Carry-over from task analysis

- [ ] **TA-LOW-01 — Narrow the KDR-014 guard test regex** (severity: LOW, source: task_analysis.md round 2 L2 / round 3 L2)
      `tests/test_kdr_014_no_quality_fields_on_input_models.py` proposed regex `audit_cascade_enabled|validator_strict|retry_budget|tier_default|.*_policy` would over-match legitimate domain fields ending in `_policy` (e.g. future `cancellation_policy`, `retention_policy`). A guard with false positives gets disabled, not fixed.
      **Recommendation:** Builder picks one of: (a) closed list `audit_cascade_enabled|validator_strict|retry_budget|tier_default|fallback_chain|escalation_threshold` extending only as new quality knobs appear; (b) qualified suffix `(retry|validator|cascade|tier)_policy`. Default to (a) — explicit closed list is more discoverable and easier to extend.

- [ ] **TA-LOW-02 — Test-file flake guard via explicit `monkeypatch.delenv` + reload** (severity: LOW, source: task_analysis.md round 2 L3 / round 3 L3)
      Test #1 (`test_audit_cascade_disabled_by_default`) in both `test_planner_cascade_enable.py` and `test_slice_refactor_cascade_enable.py` reads `_AUDIT_CASCADE_ENABLED is False`. If test #2 / #3 (`monkeypatch.setenv` + `importlib.reload`) ran first in the same session, the module-level constant could already be `True` even after env unset.
      **Recommendation:** Add to test #1 (both files): `monkeypatch.delenv("AIW_AUDIT_CASCADE", raising=False); monkeypatch.delenv("AIW_AUDIT_CASCADE_<WORKFLOW>", raising=False); importlib.reload(planner_module|slice_refactor_module)` BEFORE the `assert ... is False`.

- [ ] **TA-LOW-03 — Quality-knobs docstring section in planner.py / slice_refactor.py** (severity: LOW, source: task_analysis.md round 2 L5 / round 3 L5)
      Each workflow module's docstring should explicitly map the framework-author flippable (`_AUDIT_CASCADE_ENABLED_DEFAULT`) to its operator overrides (`AIW_AUDIT_CASCADE` global, `AIW_AUDIT_CASCADE_<WORKFLOW>` per-workflow) so a future reader doesn't need to triangulate ADR-0009 line 54 against architecture.md line 295's KDR-014 row example.
      **Recommendation:** Add a `## Quality knobs` subsection to each workflow's module docstring (~5 lines): name the constant, the env vars, link ADR-0009 + KDR-014, document the enable-only asymmetry from §M4 of round-2 analysis.

- [ ] **TA-LOW-04 — Symmetric `_AUDIT_CASCADE_ENABLED` constant naming intent** (severity: LOW, source: task_analysis.md round 3 L6)
      Both `planner.py` and `slice_refactor.py` define `_AUDIT_CASCADE_ENABLED` at module scope. Symmetric naming is intentional (consistency with the `AIW_AUDIT_CASCADE_<WORKFLOW>` env-var symmetry, and helps T04 by-role aggregation). When debugging at the REPL, the bare name is ambiguous — operator must qualify with the module.
      **Recommendation:** Document the symmetric-by-design intent in the same `## Quality knobs` docstring subsection as TA-LOW-03 (single sentence: *"The `_AUDIT_CASCADE_ENABLED` constant has the same name in `planner.py` and `slice_refactor.py` by design — each module owns its own decision; cross-module references must qualify."*). No code change.

- [ ] **TA-LOW-05 — Smoke-test env hygiene (developer shell isolation)** (severity: LOW, source: task_analysis.md round 4 L2)
      Smoke invocations 1 + 3 (the two disabled-default invocations) inherit shell env from the outer test runner. If a developer has previously exported `AIW_AUDIT_CASCADE=1` for ad-hoc testing or has it in `.env`, the disabled-default smoke fails for the wrong reason.
      **Recommendation:** Either prefix with `env -u AIW_AUDIT_CASCADE -u AIW_AUDIT_CASCADE_PLANNER -u AIW_AUDIT_CASCADE_SLICE_REFACTOR` (POSIX `env -u` to unset specific vars), or add `import os; os.environ.pop("AIW_AUDIT_CASCADE", None); os.environ.pop("AIW_AUDIT_CASCADE_<WORKFLOW>", None)` before the import inside the inline `python -c` block. Either gives deterministic isolation.

- [ ] **TA-LOW-06 — `cascade_transcript` inner-type pin** (severity: LOW, source: task_analysis.md round 4 L3)
      Spec types `cascade_transcript: dict[str, list]` on PlannerState (line 101) and SliceBranchState (line 162). The cascade primitive's actual write at `audit_cascade.py:674-677` is `{"author_attempts": list[str], "auditor_verdicts": list[AuditVerdict]}`. The looser `dict[str, list]` is at least directional but a future reader may try to "tighten" the primitive to match a stale narrowing.
      **Recommendation:** Add an inline comment at each channel declaration documenting the inner shape: `# {"author_attempts": list[str], "auditor_verdicts": list[AuditVerdict]} per audit_cascade.py:674-677`. No type-annotation change needed — `total=False` TypedDict inner types are advisory.

- [ ] **TA-LOW-07 — Cascade structural-marker pin in test #5 (positive AND negative side)** (severity: LOW, source: task_analysis.md round 4 L4 + round 5 L2)
      Test #5 (`test_planner_subgraph_inherits_planner_module_decision`) references "the cascade primitive's structural marker — see T02's compiled-graph fixture" without enumerating it. Builder will hunt. Test also asserts negative-side ("slice-worker node does NOT have cascade wrapping") but the slice-worker lives inside `_build_slice_branch_subgraph()` — Builder must descend into the per-branch sub-graph for the negative assertion.
      **Recommendation:** Pin both sides:
      - Positive: assert `'planner_explorer_audit_primary' in <planner subgraph>.nodes` (the cascade primitive adds 5 prefixed nodes per `audit_cascade.py:420-424`: `{name}_primary`, `{name}_validator`, `{name}_auditor`, `{name}_verdict`, `{name}_human_gate`).
      - Negative: assert `'slice_worker_audit_primary' not in <slice-branch subgraph>.nodes`. Builder may need a helper to descend into the compiled `slice_branch` sub-graph; cite `_build_slice_branch_subgraph()` at slice_refactor.py:899 as the construction site.

- [ ] **TA-LOW-08 — Tighten line-citation in §Folding cascade exhaustion** (severity: LOW, source: task_analysis.md round 5 L1)
      Spec line 197 cites `_slice_branch_finalize` "line 869-870" for the existing exception path; live `slice_refactor.py:868` is `exc = state.get("last_exception")`, line 869 is `if exc is None:`, line 870 is `return {}`. Citation is one-off — Builder lands on the early-return branch instead of the exception-read site.
      **Recommendation:** Change "at line 869-870" to "at line 868 (the `state.get('last_exception')` read), with the early-return at line 869-870 the path the new `isinstance(exc, AuditFailure)` branch must precede". Tightens Builder targeting.

## Propagation status

- **ADR-0009 + KDR-014** committed in isolated commit `91ca343` (autonomous-mode KDR-isolation rule satisfied).
- **architecture.md §9** carries the KDR-014 row in the same isolated commit.
- **ADR-0004 §Decision item 5** carries a stale "build-time-vs-runtime semantic shifts" framing that's superseded by ADR-0009's module-import-time decision. Forward-deferred to **M12 T07 (milestone close-out)** — same destination as T01's TA-LOW-03 deferral about ADR-0004 line 25.
- **README §Exit-criteria bullet 5** carries the `audit_cascade_enabled: bool = False` field framing that's superseded by this spec's module-constant pattern. Update at T03 close-out as part of the status-surface flip.
- **ADR-0009 §Open-questions amendment (M12 T03 round-2 M4)** — the env-var precedence asymmetry surfaced in round-2 task analysis (per-workflow var is enable-only when the global is on; cannot disable cascade only for planner when `AIW_AUDIT_CASCADE=1` is set globally) is documented in the planner.py / slice_refactor.py module-constant blocks at T03 implementation time. The ADR-0009 §Open-questions amendment to formalize the three-state-override deferral lands at **M12 T07 close-out** alongside the ADR-0004 amendments above (single ADR-amendment commit covers all three deferrals). Trigger for un-deferring: first observed operator request for "cascade everywhere except this one workflow" granularity.
