# Task 04 — Telemetry: `TokenUsage.role` tag + `CostTracker.by_role` + cascade-step records

**Status:** Complete (2026-04-27).
**Grounding:** [milestone README](README.md) · [ADR-0004 §Decision item 6 — telemetry is load-bearing](../../adr/0004_tiered_audit_cascade.md) · [architecture.md §4.1 / §4.2 / §8.5 / §9 KDR-009 / KDR-011](../../architecture.md) · [task_03 close-out (cascade workflow integration shipped — `state['cascade_role']` already written)](task_03_workflow_wiring.md) · [primitives/cost.py:66-90 (`TokenUsage`) + `:93-140` (`CostTracker.by_tier`/`by_model`)](../../../ai_workflows/primitives/cost.py) · [graph/tiered_node.py:264-274 (existing `usage.tier` stamp + `cost_callback.on_node_complete` site)](../../../ai_workflows/graph/tiered_node.py).

## What to Build

Add `role` to the `TokenUsage` ledger entry and `by_role(run_id)` to `CostTracker`. When the cascade is active (T03), each generative call inside the cascade sub-graph records a `TokenUsage` with `role ∈ {"author", "auditor", "verdict"}` (the values T03 already writes to `state['cascade_role']` per `audit_cascade.py:_DynamicState`). Non-cascade calls record `role=""` (empty string — matches the existing `tier=""` default-empty pattern in `TokenUsage`).

`CostTracker.by_role(run_id)` mirrors the shape of `by_tier(run_id)` / `by_model(run_id)` (`primitives/cost.py:116-140`) — returns `dict[role, cost_usd]` aggregated across the run's ledger entries. Sub-model costs roll into the parent entry's role (consistent with `by_tier`'s sub-model handling).

T04 is the empirical telemetry surface ADR-0004 §Decision item 6 names as the data-driven flip mechanism for future `_AUDIT_CASCADE_ENABLED_DEFAULT = True` decisions per workflow. Without `by_role`, the operator has `by_tier` (one bucket per tier) but not the author-vs-auditor split needed to reason about "is the audit pass actually adding cost?" or "what fraction of the run's Opus budget went to verdicts vs primary generation?"

## Deliverables

### [ai_workflows/primitives/cost.py](../../../ai_workflows/primitives/cost.py) — `TokenUsage.role` field + `CostTracker.by_role` method

#### `TokenUsage` — add `role` field

```python
class TokenUsage(BaseModel):
    # ... existing fields ...
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""
    tier: str = ""
    role: str = ""  # NEW (M12 T04): cascade role tag — "author", "auditor", "verdict", or "" for non-cascade calls.
    sub_models: list[TokenUsage] = Field(default_factory=list)
```

The `role` field is a free-form `str` (not `Literal`) for two reasons: (a) consistency with the existing `tier` field's free-form-str typing; (b) future cascade roles (e.g. T06's eval harness may stamp `"eval-replay"` or similar) can adopt the channel without a primitive-layer change. Values are conventional strings, validated at the `cascade_role` write site in T03's cascade primitive — not at the ledger record.

Update the docstring on `TokenUsage` to add a `role` paragraph mirroring the existing `tier` paragraph (lines 77-81 of `cost.py`):

> `role` (M12 T04 — KDR-011) is the cascade role tag (`"author"` / `"auditor"` / `"verdict"`). Empty string for non-cascade calls. `CostTracker.by_role` reads it. Stamped by `TieredNode` before handing the record to the cost callback, mirroring the existing `tier` stamp at `tiered_node.py:264-268`.

#### `CostTracker.by_role` — new aggregation method

Add immediately after `by_model` (around line 140 of `cost.py`):

```python
def by_role(self, run_id: str) -> dict[str, float]:
    """Return ``{role: cost_usd}`` for ``run_id``. Sub-model costs roll into
    the parent entry's role — sub-calls inherit the orchestrating role.

    Empty-string role (non-cascade calls) shows under the ``""`` key. Callers
    that want only the cascade roles can ignore the empty key with
    ``{r: c for r, c in tracker.by_role(run_id).items() if r}``.

    M12 T04 — KDR-011 telemetry: feeds the empirical-tuning loop that decides
    when to flip a workflow's ``_AUDIT_CASCADE_ENABLED_DEFAULT`` to ``True``
    (ADR-0004 §Decision item 6). Aggregating by role surfaces the
    author-vs-auditor cost split per run.
    """
    totals: dict[str, float] = defaultdict(float)
    for entry in self._entries.get(run_id, ()):
        totals[entry.role] += _roll_cost(entry)
    return dict(totals)
```

`_roll_cost` (existing helper) handles the sub-model roll-up; no change to it.

### [ai_workflows/graph/tiered_node.py](../../../ai_workflows/graph/tiered_node.py) — `role` factory kwarg + stamp `usage.role`

**Mechanism (locked 2026-04-27 by user arbitration on round-1 H1 — Option 4: factory-time role binding):** add a `role: str = ""` keyword-only parameter to `tiered_node()`'s factory signature, mirroring the existing `tier: str` parameter exactly. The cascade primitive passes the role at construction time (it knows the role at compose time — `"author"` for the primary call, `"auditor"` for the auditor call). `tiered_node` stamps `usage.role` from the constructor-bound role after the existing `tier` stamp. **Zero state involvement, zero ordering risk** — the role is bound at the cascade's compile time and doesn't depend on `state['cascade_role']`.

#### Factory signature change

```python
def tiered_node(
    *,
    tier: str,
    prompt_fn: PromptFn,
    output_schema: type[BaseModel],
    node_name: str,
    role: str = "",  # NEW (M12 T04): cascade role tag — "author", "auditor", "verdict", or "" for non-cascade calls. Stamped onto each recorded TokenUsage; mirrors the existing tier kwarg's stamp pattern.
) -> Callable[..., Any]:
```

The new kwarg is keyword-only, lives alongside the existing `tier` kwarg, defaults to `""` (preserves all existing T01-T03 + T08 callers byte-for-byte — none of them pass `role`).

#### Stamp logic (mirror of `tier` stamp at lines 264-268)

Insert immediately after the existing `tier` stamp:

```python
# Existing (lines 264-268):
usage_with_tier = (
    usage
    if usage.tier
    else usage.model_copy(update={"tier": resolved_tier})
)
# NEW (M12 T04 — KDR-011 telemetry, factory-time role binding):
usage_with_role = (
    usage_with_tier
    if usage_with_tier.role  # respect any role the adapter may have stamped (none today)
    else usage_with_tier.model_copy(update={"role": role})
)
cost_callback.on_node_complete(run_id, node_name, usage_with_role)
```

The `role` here is the closure-captured factory parameter, NOT a state read. No `state.get("cascade_role")` involvement. Non-cascade callers (every existing `tiered_node` invocation across T01-T03, T08, and pre-M12 workflows) get `role=""` by default — `usage.role` ends up `""` and `by_role` shows them under the empty-string bucket. Cascade callers (T04 wires only) explicitly pass `role="author"` / `role="auditor"`.

### [ai_workflows/graph/audit_cascade.py](../../../ai_workflows/graph/audit_cascade.py) — pass `role=` at cascade-construction time

The cascade's primary and auditor `tiered_node` constructions get an explicit `role` kwarg:

- Primary tiered_node (around `audit_cascade.py:282-287`): `tiered_node(tier=primary_tier, prompt_fn=primary_prompt_fn, output_schema=primary_output_schema, node_name=f"{name}_primary", role="author")`.
- Auditor tiered_node (around `audit_cascade.py:317-322`): `tiered_node(tier=auditor_tier, prompt_fn=auditor_prompt_fn, output_schema=AuditVerdict, node_name=f"{name}_auditor", role="auditor")`.

Verbatim line numbers verify against live source at implementation time; the spec calls out the construction sites by structural pattern (primary call + auditor call inside `audit_cascade_node()`).

The existing `_stamp_role_on_success` wrapper that writes `state['cascade_role']` is left in place unchanged — it serves the existing `test_cascade_role_tags_stamped_on_state` test which reads final state, NOT the recorded TokenUsage. T04's role stamp is independent of that state channel; both surfaces coexist (state channel surfaces the role to graph-layer consumers, factory-time binding surfaces it to the ledger).

The verdict node does NOT pass `role="verdict"` — the verdict node is a pure parse step, no LLM call, no `tiered_node` involvement, no `TokenUsage` recorded. Verified against `audit_cascade.py:_audit_verdict_node` (no LLM dispatch, only `AuditVerdict.model_validate_json`).

### Locked decisions (round 1 user arbitration, 2026-04-27)

> **Option 4 locked** — factory-time role binding on `tiered_node`. Backward-compatible (default `""` preserves T01-T03 + T08 callers byte-for-byte). Mirrors the existing `tier` parameter exactly — symmetric extension of an existing pattern, not a new architectural shape.
>
> **Option 1 rejected** — "move the cascade `_stamp_role_on_success` to entry side." Structurally infeasible inside a single LangGraph node: state mutations come from return values, but `cost_callback.on_node_complete` fires INSIDE the wrapped `tiered_node` BEFORE its return propagates. The "entry-side write" cannot make `state['cascade_role']` visible to the callback in the same node call. (Workable variant: insert 2 new graph nodes + 2 new edges per cascade sub-step to land role via a prior node's return — too much plumbing for what's gained.)
>
> **Option 3 alternative-considered** — wrap `cost_callback` per cascade sub-node to inject role into the recorded TokenUsage. More plumbing than the existing tier-kwarg pattern needs; cost_callback is shared across the whole graph, not per-cascade-sub-node, so wrapping requires care. Option 4 is strictly cleaner.
>
> **KDR-014 does not apply** — `role` is a primitive-layer construction parameter on `tiered_node`, symmetric to the existing `tier` kwarg. It is consumed by the cascade primitive (workflow-internal code) at compose time, NOT exposed as a quality knob on any user-facing surface (`*Input` model, `WorkflowSpec`, CLI flag, MCP tool input schema). KDR-014's domain stays unchanged.

### [tests/primitives/test_cost_by_role.py](../../../tests/primitives/test_cost_by_role.py) — new

Hermetic. 5 tests covering the new aggregation surface:

1. `test_by_role_empty_run` — `tracker.by_role("nonexistent_run")` returns `{}`.
2. `test_by_role_single_role` — record 3 `TokenUsage(role="author", cost_usd=...)` for one run; `by_role` returns `{"author": <sum>}`.
3. `test_by_role_multiple_roles` — record `(author, $1.0)`, `(auditor, $2.0)`, `(verdict, $0.5)`; `by_role` returns `{"author": 1.0, "auditor": 2.0, "verdict": 0.5}`.
4. `test_by_role_sub_models_inherit_parent_role` — record `TokenUsage(role="author", cost_usd=$1.0, sub_models=[TokenUsage(role="", cost_usd=$0.5)])`; `by_role` returns `{"author": 1.5}` (sub-model's empty role does NOT create a separate `""` bucket — sub-model costs roll into the parent's role per the `_roll_cost` helper, mirroring `by_tier`'s sub-model behaviour). Pin this contract — cascade calls produce nested sub_model entries from Claude Code's `modelUsage` reporting (one Opus call may spawn Haiku sub-calls); the parent role should swallow the sub-model costs so the operator sees one entry per cascade step, not one entry per LLM call.
5. `test_by_role_includes_empty_string_bucket_for_non_cascade_calls` — record `(role="author", $1.0)` + `(role="", $0.5)`; assert `tracker.by_role(run_id) == {"author": 1.0, "": 0.5}`. Pins the empty-string non-cascade-bucket contract documented in `by_role`'s docstring (non-cascade calls show under the `""` key; callers that want only cascade roles filter with `{r: c for r, c in tracker.by_role(run_id).items() if r}`).

### [tests/graph/test_audit_cascade.py](../../../tests/graph/test_audit_cascade.py) — extend (not new file)

Add 2 new tests verifying the end-to-end role-stamping path through the cascade primitive:

6. `test_cascade_records_role_tagged_token_usage_per_step` — invoke the compiled cascade with a stub `CostTrackingCallback` that captures every `TokenUsage` it receives. Drive a happy-path cascade (auditor passes on first try). Assert: **callback received exactly 2 records** (primary + auditor — verdict is a pure parse and does not dispatch); `records[0].role == "author"`; `records[1].role == "auditor"`. The exact-2 count is the protective assertion — pins that the verdict node correctly does NOT dispatch (no third record) and the primary + auditor both record exactly once each. Pins the wire-level role-stamp under Option 4: `tiered_node` is constructed with `role="author"` / `role="auditor"` in the cascade primitive, so each recorded TokenUsage carries the constructor-bound role.

7. `test_cascade_role_attribution_survives_audit_retry_cycle` — drive a cascade where auditor fails once (`AuditVerdict(passed=False, ...)`), then succeeds. Capture every TokenUsage the cost callback receives across the retry cycle. Assert: 2 author records (cycle 1 primary + cycle 2 primary on re-fire) all carry `role="author"`; 2 auditor records (cycle 1 auditor failure + cycle 2 auditor success) all carry `role="auditor"`. No author record carries `role="auditor"` and no auditor record carries `role="author"`. **Pins H2's mitigation:** Option 4's factory-time role binding eliminates the stale-role-on-retry concern (under Options 1/3 the role would be read from `state['cascade_role']` and could inherit a stale value from the prior node's success-side write; under Option 4 the role is closure-captured at cascade construction time and immune to state-channel ordering).

### KDR-003 guardrail — verify, don't extend

The KDR-003 hermetic grep test at `tests/workflows/test_slice_refactor_e2e.py:410` (`test_kdr_003_no_anthropic_in_production_tree`) iterates `ai_workflows/`'s `.py` files via `rglob("*.py")` — so T04's edits to `cost.py` + `tiered_node.py` + `audit_cascade.py` are automatically in scope without a test extension. AC: that test still passes after T04's edits. T04 adds no Anthropic-SDK surface.

### [CHANGELOG.md](../../../CHANGELOG.md)

Under `## [Unreleased]`, add `### Added — M12 Task 04: Telemetry — TokenUsage.role tag + CostTracker.by_role + cascade-step records (YYYY-MM-DD)`. List:

- Files touched: `ai_workflows/primitives/cost.py` (TokenUsage.role field + CostTracker.by_role method), `ai_workflows/graph/tiered_node.py` (`role: str = ""` factory kwarg + usage.role stamp before cost_callback.on_node_complete; mirror of existing tier kwarg pattern per Option 4 locked decision), `ai_workflows/graph/audit_cascade.py` (pass role="author" / role="auditor" at the primary + auditor tiered_node construction sites; the existing _stamp_role_on_success state-channel wrapper is left in place unchanged), `tests/primitives/test_cost_by_role.py` (new, 5 tests), `tests/graph/test_audit_cascade.py` (extended, 2 new tests).
- KDR-011 cited (telemetry is the empirical surface for cascade defaults).
- Backward compatibility: `role=""` default preserves all existing TokenUsage construction; existing `by_tier` / `by_model` aggregations unchanged.

## Acceptance Criteria

- [ ] `TokenUsage` exports a `role: str = ""` field with docstring citing M12 T04 / KDR-011.
- [ ] `CostTracker.by_role(run_id)` exists and mirrors the shape of `by_tier(run_id)` (sub-model costs roll into parent's role; empty-string role shown under `""` key).
- [ ] `tiered_node()` factory accepts a `role: str = ""` keyword-only kwarg (mirror of the existing `tier` kwarg). Default `""` preserves all existing T01-T03 + T08 callers byte-for-byte (none of them pass `role`).
- [ ] `tiered_node` stamps `usage.role` from the constructor-bound `role` parameter (NOT from `state.get('cascade_role')`) immediately after the existing `tier` stamp at lines 264-268. Logic: `usage_with_role = usage_with_tier if usage_with_tier.role else usage_with_tier.model_copy(update={"role": role})`. Verified by reading the modified `tiered_node.py:264-274ish` block.
- [ ] Cascade primitive (`audit_cascade.py`) passes `role="author"` to its primary `tiered_node()` construction (around lines 282-287) and `role="auditor"` to its auditor `tiered_node()` construction (around lines 317-322). The verdict node does NOT pass `role="verdict"` (verdict node is a pure parse, no LLM call, no `tiered_node` involvement).
- [ ] The cascade's existing `_stamp_role_on_success` wrapper (which writes `state['cascade_role']`) is left in place unchanged — it serves the existing `test_cascade_role_tags_stamped_on_state` test which reads final state. T04's role stamp is independent of that state channel; both surfaces coexist.
- [ ] All 5 new `tests/primitives/test_cost_by_role.py` tests pass.
- [ ] New `tests/graph/test_audit_cascade.py::test_cascade_records_role_tagged_token_usage_per_step` passes — wire-level proof that the cascade's primary records `role="author"` and the auditor records `role="auditor"` via the production cost callback path. Asserts exactly 2 records (count is the protective assertion — pins the verdict node correctly does NOT dispatch).
- [ ] New `tests/graph/test_audit_cascade.py::test_cascade_role_attribution_survives_audit_retry_cycle` passes — pins H2 mitigation: under Option 4's factory-time role binding, no author record carries `role="auditor"` and no auditor record carries `role="author"` even when the cascade re-fires across retry cycles.
- [ ] All existing tests remain green (backward-compat: existing `TokenUsage` construction without a `role` argument still works; existing `by_tier` / `by_model` aggregations return the same values; existing `tiered_node` invocations across T01-T03 + T08 work without passing `role`).
- [ ] No `ai_workflows/workflows/` diff (T04 is primitives + graph layer only). No `ai_workflows/mcp/` diff. No `ai_workflows/cli.py` diff.
- [ ] No `pyproject.toml` / `uv.lock` diff (no new dependency; no new import-linter contract — T02's audit_cascade contract carries forward, 5 contracts kept).
- [ ] KDR-003 guardrail test (`test_kdr_003_no_anthropic_in_production_tree`) still passes — verified by re-running the test (it iterates `ai_workflows/`'s `.py` files via `rglob`).
- [ ] `uv run pytest` + `uv run lint-imports` (5 contracts kept) + `uv run ruff check` all clean.
- [ ] CHANGELOG entry under `[Unreleased]` cites KDR-011 + backward-compat + Option 4 locked-decision.
- [ ] **Smoke test (CLAUDE.md non-inferential rule):** `tests/graph/test_audit_cascade.py::test_cascade_records_role_tagged_token_usage_per_step` is the wire-level smoke — invokes the compiled cascade end-to-end through real `tiered_node` + real `cost_callback`; asserts the recorded `TokenUsage.role` matches the cascade-construction-time role binding. Builder runs this test explicitly and reports the result.
- [ ] Status surfaces flipped together at task close: (a) spec `**Status:**` line: `📝 Planned` → `✅ Complete (YYYY-MM-DD)`; (b) milestone README task-table row 04 Status column: `📝 Planned` → `✅ Complete (YYYY-MM-DD)` (Kind column stays `code + test`); (c) milestone README §Exit-criteria bullet 6 ticked from `[ ]` to `[x]` (the `TokenUsage.role` tag + `by_role` row).

## Dependencies

- **T01** ✅ shipped at `a7f3e8f` (auditor tiers).
- **T02** ✅ shipped at `fc8ef19` (cascade primitive).
- **T03** ✅ shipped at `1677889` (cascade workflow integration; `state['cascade_role']` channel populated).
- **T08** ✅ shipped at `e7e8a31` (cascade `skip_terminal_gate` parameter — used by T03's slice_refactor wiring).
- **No new dependency on KDR-014** — T04 doesn't introduce any quality knobs; the `role` tag is a diagnostic ledger field, not a policy toggle.

## Out of scope (explicit)

- **No MCP tool change.** T05 is the standalone `run_audit_cascade` MCP tool task.
- **No SKILL.md edit.** T05.
- **No eval fixture convention.** T06.
- **No default-on cascade flip.** ADR-0004 §Decision item 5 + ADR-0009 — flipping `_AUDIT_CASCADE_ENABLED_DEFAULT = True` requires the post-T04 telemetry analysis, not a T04 deliverable.
- **No persistence-layer schema change.** `TokenUsage.role` rides the existing in-memory `CostTracker._entries` dict (lines 105-110 of `cost.py`). If a future task persists the ledger to SQLite per KDR-009, the `role` column lands then; T04 keeps the in-memory shape.
- **No `Literal["author", "auditor", "verdict"]` typing.** Free-form `str` per the existing `tier` field convention. Cascade primitive owns the value-set discipline at the write site.
- **No cascade-primitive (`audit_cascade_node`) signature change.** The `tiered_node` factory signature gains a backward-compatible `role: str = ""` kwarg per Option 4 (default preserves all 25+ existing callers byte-for-byte). T08's `skip_terminal_gate` was the cascade-primitive amendment; T04's primitive-layer change is the symmetric role-kwarg extension on `tiered_node`, not on `audit_cascade_node`.
- **No telemetry export to external systems.** Langfuse / OpenTelemetry / etc. are `nice_to_have.md` items; T04 lands the in-process aggregation surface only.
- **No Anthropic API.** KDR-003 preserved.

## Propagation status

Filled in at audit time. Anticipated forward-deferrals from T04:

- If T05's standalone `run_audit_cascade` MCP tool needs to surface `by_role` aggregation in its output schema, that wiring lands at T05 — surface as a carry-over to T05's spec at draft time.

(Note: a round-1 hypothetical about cascade_role state-channel ordering — Option 1 vs Option 2 plumbing — was made moot by Option 4's lock. Under Option 4, `role` is closure-bound at `tiered_node` construction time and does NOT depend on `state['cascade_role']` ordering. No related forward-deferral applies.)

## Carry-over from prior milestones

- *None.*

## Carry-over from prior audits

- *None at draft time. T03 audit closed clean for T04's scope (the cascade-primitive workflow-name leak — `_DynamicState["slice"]` — is forward-deferred to a future cascade refinement task with trigger "first non-slice embedding workflow," NOT to T04).*

## Carry-over from task analysis

- [x] **TA-LOW-01 — `tiered_node.py:194` line citation drift** (severity: LOW, source: task_analysis.md round 1 L1)
      Spec line 92 cites `tiered_node.py:194` for the typed `GraphState` parameter on the inner `_node` function; live source has it at line 193 (one-off drift). Note: this section was rewritten in the round-1 fix application (Option 4); the new "Cascade primitive — pass `role=` at construction time" section no longer references that line, but the underlying `tiered_node` block at lines 264-274 (where the new role stamp lands) is the load-bearing citation.
      **Recommendation:** Builder verifies the modified `tiered_node.py:264-274` block against live source at implement time; tighten any one-off line citations in the issue file at audit close.

- [x] **TA-LOW-02 — CHANGELOG framing nuance for primitive-layer signature change** (severity: LOW, source: task_analysis.md round 1 L2)
      Per Keep-a-Changelog convention, adding a backward-compatible parameter to an existing public-ish factory could be classified as either `### Added` (new feature: role tagging) or `### Changed` (factory signature gained a kwarg). The spec uses `### Added` per the natural reading (T04 adds the role-tagging behaviour to the cost ledger; the kwarg is an implementation detail of that feature). T08's CHANGELOG entry used `### Changed` because the cascade primitive's signature was the headline (`skip_terminal_gate=True` was a behaviour-shape change at the cascade boundary). T04 is closer to "added telemetry" than "changed factory shape" — `### Added` is appropriate.
      **Recommendation:** Confirm `### Added` framing at CHANGELOG-write time. If the Builder feels the primitive-layer signature change overshadows the telemetry addition, `### Changed` is also acceptable; cite KDR-011 either way.

- [x] **TA-LOW-03 — Test #6 verdict-node assumption is now verified, leave no hand-wave in spec** (severity: LOW, source: task_analysis.md round 1 L3)
      The spec's test #6 description (`test_cascade_records_role_tagged_token_usage_per_step`) initially hand-waved "If the verdict node also records a `TokenUsage` (it shouldn't — the verdict node is a pure parse, no LLM call), assert `role='verdict'` for that record." The hand-wave was resolved during round-1 analysis: `_audit_verdict_node` (`audit_cascade.py:714-810`) only calls `AuditVerdict.model_validate_json` — no LLM dispatch, no `TokenUsage`. The round-1 spec update tightened test #6 to assert `exactly 2 records` (count is the protective assertion). No further spec edit needed; this LOW is informational — flagged for Builder awareness that the verdict-node assumption is verified at spec time, not at implement time.
      **Recommendation:** No action; informational. If a future cascade extension grows a verdict-side LLM dispatch (e.g. an LLM-based verdict explainer at T07), the test count assertion would catch the regression.

- [x] **TA-LOW-04 — Forward-deferral note has no T05 spec to land on yet** (severity: LOW, source: task_analysis.md round 1 L4)
      Spec §Propagation status says "If T05's standalone `run_audit_cascade` MCP tool needs to surface `by_role` aggregation in its output schema, that wiring lands at T05 — surface as a carry-over to T05's spec at draft time." T05 spec doesn't exist yet (per M12 README convention). The note is a forward-deferral that has no spec to carry-over INTO until T05 is drafted (after T04 closes). Tracking lives in this carry-over section until T05 spec lands.
      **Recommendation:** When T05 spec is drafted (post-T04 close-out), the orchestrator's `/clean-tasks` cycle for T05 picks up this carry-over and adds it to T05's `## Carry-over from prior audits` section. Until then, the note stays here as a tracked-but-pending forward-deferral.

- [x] **TA-LOW-05 — `tiered_node.py:264-274ish` line citation drift on the inserted role-stamp block** (severity: LOW, source: task_analysis.md round 2 L1)
      Spec cites `tier`-stamp at `tiered_node.py:264-268`; the new `role` stamp slots between line 268 and the `cost_callback.on_node_complete(...)` call at line 274, pushing that call to ~line 280 post-edit. Spec already says "264-274ish" so Builder isn't blocked, but the once-cited "lines 264-268" describes the pre-edit tier-stamp range, not where the role stamp lives post-edit.
      **Recommendation:** Builder confirms the inserted role-stamp block lands between the existing `tier`-stamp at lines 264-268 and the `cost_callback.on_node_complete` call at line 274 in live source; the spec's `:264-274ish` bound is approximate and acceptable to drift by one or two lines as the new block lands. Tighten any one-off line citations in the issue file at audit close.

- [x] **TA-LOW-06 — §"Out of scope" bullet "no cascade-primitive signature change" is now ambiguous under Option 4** (severity: LOW, source: task_analysis.md round 2 L2)
      Spec §"Out of scope" line 196 still reads `**No cascade-primitive signature change.** T08's skip_terminal_gate was the most recent factory-signature amendment; T04 is internal-only to the cascade's role-stamp wrapper.` Under Option 4, T04 *does* extend a primitive-layer factory signature — `tiered_node()` gains a backward-compat `role: str = ""` kwarg. The cascade primitive (`audit_cascade_node`) signature itself stays unchanged, but the `tiered_node` primitive signature does change.
      **Recommendation:** At spec-edit time (or implement-close time), reword the §`Out of scope` bullet from `**No cascade-primitive signature change.** T08's skip_terminal_gate was the most recent factory-signature amendment; T04 is internal-only to the cascade's role-stamp wrapper.` to: `**No cascade-primitive (audit_cascade_node) signature change.** The tiered_node factory signature gains a backward-compatible role: str = "" kwarg per Option 4 (default preserves all 25+ existing callers byte-for-byte). T08's skip_terminal_gate was the cascade-primitive amendment; T04's primitive-layer change is the symmetric role-kwarg extension on tiered_node, not on audit_cascade_node.`
