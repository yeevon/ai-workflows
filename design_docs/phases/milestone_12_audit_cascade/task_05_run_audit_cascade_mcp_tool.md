# Task 05 — `run_audit_cascade` MCP tool + SKILL.md ad-hoc-audit section

**Status:** 📝 Planned (drafted 2026-04-27).
**Grounding:** [milestone README](README.md) · [ADR-0004 §Decision item 7 — standalone invocation surface](../../adr/0004_tiered_audit_cascade.md) · [architecture.md §4.4 (MCP surface) / §9 KDR-008 (FastMCP + pydantic schema as public contract) / KDR-011 / KDR-014](../../architecture.md) · [ADR-0009 — framework owns quality policy](../../adr/0009_framework_owns_policy.md) · [task_02 close-out (cascade primitive)](task_02_audit_cascade_node.md) · [task_04 close-out (TokenUsage.role + by_role + factory-time role binding on tiered_node)](task_04_telemetry_role_tag.md) · [task_08 close-out (skip_terminal_gate)](task_08_audit_cascade_skip_terminal_gate.md) · [mcp/server.py:121-204 (existing MCP tools)](../../../ai_workflows/mcp/server.py) · [mcp/schemas.py (existing pydantic I/O models)](../../../ai_workflows/mcp/schemas.py) · [primitives/storage.py:197-203 (`read_artifact` signature)](../../../ai_workflows/primitives/storage.py) · [graph/tiered_node.py:116-122 (factory signature with role kwarg post-T04)](../../../ai_workflows/graph/tiered_node.py) · [graph/audit_cascade.py:75 (`AuditVerdict` canonical owner)](../../../ai_workflows/graph/audit_cascade.py) · [.claude/skills/ai-workflows/SKILL.md (existing skill text)](../../../.claude/skills/ai-workflows/SKILL.md).

## What to Build

Add a standalone `run_audit_cascade` MCP tool that audits an existing artefact via a single auditor-tier `tiered_node` invocation — outside of any workflow run. Two artefact-source variants land at T05: **`run_id_ref + artefact_kind`** (recover via `storage.read_artifact(run_id, kind)`) and **`inline_artefact_ref`** (caller passes the artefact verbatim). The tool surfaces an `AuditVerdict` (the same pydantic model T02's cascade primitive emits) plus telemetry.

**Architectural decision (round-1 H1 / Option A — locked 2026-04-27 by user arbitration):** the standalone tool **bypasses `audit_cascade_node()` entirely**. T05 instantiates `tiered_node(tier=auditor_tier, prompt_fn=<emits supplied artefact>, output_schema=AuditVerdict, role="auditor")` directly. The cascade primitive at `audit_cascade.py:150-164` requires `primary_tier` + `primary_prompt_fn` + `primary_output_schema` and wires `START → primary_node` (real LLM dispatch); standalone audit has **no primary call** because the artefact is supplied. ADR-0004 §Decision item 7 currently reads "internal routing reuses the same `AuditCascadeNode`" — that framing is stale post-Option-A; ADR amendment forward-deferred to M12 T07 close-out alongside other ADR-0004 stale items (see §Propagation status).

**Architectural decision (round-1 H2 / Option A — locked 2026-04-27 by user arbitration):** the input schema requires the caller to supply an `artefact_kind` parameter when using `run_id_ref`. The tool calls `storage.read_artifact(run_id_ref, artefact_kind)` directly. There is no "the canonical artefact for this run_id" concept in storage — different workflows write under different `kind` values (planner: `"plan"`; slice_refactor: `"applied_artifacts"`). Pushing the kind selection to the caller keeps T05 narrow; a workflow→kind registry (Option B) is forward-deferred until the standalone tool actually has multi-workflow users.

Telemetry per T04: the auditor `tiered_node` is constructed with `role="auditor"` (factory-time binding from T04) so its `TokenUsage` record carries the role tag; the tool surfaces `total_cost_usd` (via `CostTracker.total(audit_run_id)`) and `by_role: dict[str, float] | None` (via `CostTracker.by_role(audit_run_id)`). SKILL.md grows a new "Ad-hoc artefact audit" section. Three stale `M12 T04` references in design docs (`architecture.md:105`, `adr/0004:56`, `adr/0004:73`) flip to `M12 T05` as part of T05 close-out.

T05 is **MCP surface + skill text + 3 design-doc stale-reference fixes only**. No new graph primitive, no new workflow, no cascade-primitive amendment. T01-T04 + T08 surfaces are reused as-is.

## Deliverables

### [ai_workflows/mcp/schemas.py](../../../ai_workflows/mcp/schemas.py) — new I/O models

#### `RunAuditCascadeInput`

```python
class RunAuditCascadeInput(BaseModel):
    """Arguments to the ``run_audit_cascade`` tool.

    Audit an existing artefact via the M12 auditor tier outside of a
    workflow run. The artefact is supplied via one of the two source
    fields below — exactly one must be set; the validator rejects the
    payload if zero or both are set.

    Per ADR-0004 §Decision item 7 (amendment to land at M12 T07 close-out
    — standalone tool is an adjacent caller of the auditor tier, not a
    re-use of the compiled cascade graph; H1 Option A locked 2026-04-27),
    this is the standalone invocation surface that lets a caller spot-
    check a completed plan, draft spec, or generated code slice without
    kicking off a full workflow.

    A future task may extend the input with a ``file_path_ref`` slot for
    sandboxed-root file-path artefact resolution; deferred from T05 per
    scope discipline (see spec §Propagation status).
    """

    run_id_ref: str | None = Field(
        default=None,
        description=(
            "Audit an artefact from a completed `aiw run` with this "
            "run_id. MUST be paired with ``artefact_kind`` (caller "
            "picks which kind — different workflows write under "
            "different kinds: planner uses 'plan', slice_refactor uses "
            "'applied_artifacts'). The tool calls "
            "``storage.read_artifact(run_id, kind)``. Raises ToolError "
            "if (run_id, kind) is not found."
        ),
    )
    artefact_kind: str | None = Field(
        default=None,
        description=(
            "Kind argument to ``storage.read_artifact(run_id, kind)``. "
            "Required iff ``run_id_ref`` is set; rejected (ValidationError) "
            "if ``run_id_ref`` is unset. Caller-known values include "
            "``'plan'`` (planner workflow) and ``'applied_artifacts'`` "
            "(slice_refactor workflow); external workflows declare their "
            "own kinds via ``storage.write_artifact(run_id, kind, ...)`` "
            "calls in their workflow code (KDR-013)."
        ),
    )
    inline_artefact_ref: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Audit this dict verbatim. The dict shape is opaque to the "
            "tool — the caller is responsible for shaping it consistent "
            "with what the auditor's prompt expects. Useful for spot-"
            "checking a draft artefact before committing it to a run."
        ),
    )
    tier_ceiling: Literal["sonnet", "opus"] = Field(
        default="opus",
        description=(
            "Auditor tier. 'opus' uses ``auditor-opus`` (highest tier). "
            "'sonnet' uses ``auditor-sonnet`` (cheaper). Default 'opus' "
            "matches ADR-0004's standalone-spot-check intent (Max flat-"
            "rate $0). Per ADR-0009 / KDR-014: this is a per-call input "
            "(operator picks which tier to spend on for this specific "
            "audit), NOT a quality knob (which would be a workflow "
            "default the framework owns). The framework default is "
            "'opus'; the per-call override is the operator's privilege."
        ),
    )

    @model_validator(mode="after")
    def _exactly_one_artefact_source(self) -> RunAuditCascadeInput:
        """Enforce one-of {run_id_ref, inline_artefact_ref}; require artefact_kind iff run_id_ref."""
        sources = [self.run_id_ref, self.inline_artefact_ref]
        set_count = sum(1 for s in sources if s is not None)
        if set_count != 1:
            raise ValueError(
                f"exactly one of run_id_ref / inline_artefact_ref must be set (got {set_count})"
            )
        if self.run_id_ref is not None and self.artefact_kind is None:
            raise ValueError(
                "artefact_kind is required when run_id_ref is set "
                "(caller picks the kind: planner uses 'plan', "
                "slice_refactor uses 'applied_artifacts', etc.)"
            )
        if self.run_id_ref is None and self.artefact_kind is not None:
            raise ValueError(
                "artefact_kind is only meaningful when run_id_ref is set"
            )
        return self
```

(`from __future__ import annotations` is already at `mcp/schemas.py:35`, so the `-> RunAuditCascadeInput` forward reference works without quotes. Mirrors the package idiom at `workflows/spec.py:204` + `evals/schemas.py:96`.)

#### `RunAuditCascadeOutput`

```python
class RunAuditCascadeOutput(BaseModel):
    """Response from the ``run_audit_cascade`` tool.

    Carries the verdict structure the caller can act on, plus
    telemetry for the cost-aware operator.
    """

    passed: bool = Field(
        description=(
            "True iff the auditor returned `passed=True` on the artefact. "
            "False on `passed=False`. The standalone tool uses single-pass "
            "dispatch (RetryPolicy(max_transient_attempts=1, "
            "max_semantic_attempts=1)) so there is no retry-cycle path."
        ),
    )
    verdicts_by_tier: dict[str, AuditVerdict] = Field(
        default_factory=dict,
        description=(
            "Map of {tier_name: AuditVerdict} for the auditor tier "
            "invoked. T05 lands single-tier audit (one entry: "
            "{auditor_tier_used: AuditVerdict(...)}); future multi-tier "
            "cascading would populate multiple entries. AuditVerdict is "
            "the same model T02's cascade primitive emits."
        ),
    )
    suggested_approach: str | None = Field(
        default=None,
        description=(
            "The auditor's suggested-approach text from the verdict "
            "(matches `AuditVerdict.suggested_approach`). Populated on "
            "`passed=False`; None on `passed=True`."
        ),
    )
    total_cost_usd: float = Field(
        default=0.0,
        description=(
            "Total USD cost of the audit invocation. Includes the auditor "
            "LLM call; excludes the original artefact production cost. "
            "Cost is $0 today under Claude Max flat-rate pricing "
            "(`pricing.yaml`); a future per-tier-pricing change would "
            "surface non-zero values without a schema break."
        ),
    )
    by_role: dict[str, float] | None = Field(
        default=None,
        description=(
            "Per-role cost breakdown via T04's "
            "``CostTracker.by_role(audit_run_id)``. Populated only when "
            "the audit call actually ran (not on early ToolError paths). "
            "For the standalone single-pass audit (Option A bypasses the "
            "cascade primitive — no primary call), one entry: "
            "``{'auditor': <cost>}``. The author/primary key does NOT "
            "appear because the supplied artefact is never re-generated."
        ),
    )
```

Add `RunAuditCascadeInput` + `RunAuditCascadeOutput` to `mcp/schemas.py:__all__`. **Do NOT re-export `AuditVerdict`** — its canonical owner is `ai_workflows.graph.audit_cascade.__all__` (line 75 of that module). Import `AuditVerdict` from `ai_workflows.graph.audit_cascade` for the `verdicts_by_tier` type hint only; pydantic's schema derivation picks it up automatically via the type-hint resolution (no `__all__` membership needed).

### [ai_workflows/mcp/server.py](../../../ai_workflows/mcp/server.py) — new `@mcp.tool()` (Option A — direct tiered_node invocation)

Add a fifth `@mcp.tool()` after `cancel_run` (Builder reads live source around line 206ish for the exact insertion point):

```python
@mcp.tool()
async def run_audit_cascade(payload: RunAuditCascadeInput) -> RunAuditCascadeOutput:
    """Audit an existing artefact via a single ``auditor-{tier}`` call — standalone.

    Per Option A locked at M12 T05 round-1 (2026-04-27): this tool
    BYPASSES the cascade primitive (``audit_cascade_node``) and
    instantiates a single-pass auditor ``tiered_node`` directly — the
    cascade primitive requires a primary LLM call which standalone
    audit does not have.

    Resolves the artefact via ``payload.run_id_ref + artefact_kind``
    (recover via ``storage.read_artifact(run_id, kind)``) or
    ``payload.inline_artefact_ref`` (caller-supplied dict). Auditor
    tier: ``auditor-opus`` (default) or ``auditor-sonnet`` per
    ``payload.tier_ceiling``. Telemetry (T04) records the audit call
    with ``role="auditor"`` (factory-time binding on ``tiered_node``);
    output's ``by_role`` aggregates via
    ``CostTracker.by_role(audit_run_id)``.

    Errors surface as ``ToolError`` for: unknown ``(run_id, kind)``
    (storage.read_artifact returns None), tier registry lookup miss,
    auditor adapter failure (LLM dispatch or output-parse error).
    """
    artefact = await _resolve_audit_artefact(payload)

    audit_run_id = f"audit-{uuid.uuid4().hex[:12]}"
    auditor_tier_name = f"auditor-{payload.tier_ceiling}"

    cost_tracker, cost_callback, policy, tier_registry = _build_standalone_audit_config(
        audit_run_id=audit_run_id,
    )

    auditor_node = tiered_node(
        tier=auditor_tier_name,
        prompt_fn=_make_standalone_auditor_prompt_fn(artefact),
        output_schema=AuditVerdict,
        node_name="standalone_auditor",
        role="auditor",  # T04 factory-time role binding
    )

    state = {"run_id": audit_run_id}
    config = {"configurable": _build_audit_configurable(
        cost_callback=cost_callback,
        policy=policy,
        tier_registry=tier_registry,
        run_id=audit_run_id,
    )}
    try:
        verdict_state = await auditor_node(state, config)
    except (UnknownTierError, NonRetryable, RetryableSemantic) as exc:
        raise ToolError(f"audit invocation failed: {exc}") from None

    # Round-2 H1: tiered_node returns raw text under f"{node_name}_output"
    # (verified tiered_node.py:395-398) — does NOT auto-parse against
    # output_schema. Cascade primitive parses via _audit_verdict_node at
    # audit_cascade.py:751; Option A's bypass inherits the obligation
    # to parse explicitly here.
    raw_text = verdict_state.get("standalone_auditor_output", "") or ""
    try:
        verdict = AuditVerdict.model_validate_json(raw_text)
    except Exception as exc:
        raise ToolError(
            f"auditor produced unparseable output — expected AuditVerdict JSON, "
            f"got: {raw_text[:200]!r}"
        ) from exc

    return RunAuditCascadeOutput(
        passed=verdict.passed,
        verdicts_by_tier={auditor_tier_name: verdict},
        suggested_approach=verdict.suggested_approach if not verdict.passed else None,
        total_cost_usd=cost_tracker.total(audit_run_id),
        by_role=cost_tracker.by_role(audit_run_id),
    )
```

`_resolve_audit_artefact` is a private module-level function in `mcp/server.py` (NOT `workflows/_dispatch.py` — would couple workflows to surfaces, violating the layer rule).

For `run_id_ref + artefact_kind`: calls `await storage.read_artifact(run_id, kind)`; on `None` return raises `ToolError(f"no artefact found for run_id={run_id!r}, kind={kind!r}")`; otherwise **returns `json.loads(row["payload_json"])`** to decode the stored payload back to a dict (round-2 H2: `read_artifact` returns the full SQL row `{run_id, kind, payload_json: str, created_at}`, not the artefact — `payload_json` is a stringified JSON the storage layer stored verbatim per `storage.py:181-186`; the auditor needs the artefact, not the storage wrapper).

For `inline_artefact_ref`: returns the dict unchanged (no decode needed; caller supplied a real dict).

### Standalone wiring

The standalone audit invocation needs four pieces of plumbing the cascade primitive normally hides inside the compiled sub-graph:

1. **Per-call `audit_run_id`** — `f"audit-{uuid.uuid4().hex[:12]}"`. Format prefix `"audit-"` distinguishes from workflow run IDs in the in-memory CostTracker.

2. **Per-call `CostTracker` + `CostTrackingCallback`** — fresh instances (NOT the dispatch's shared one) so telemetry stays isolated. CostTracker is in-memory only (no SQLite write).

3. **`RetryPolicy` default** — single-pass: `RetryPolicy(max_transient_attempts=1, max_semantic_attempts=1)`. Standalone audit is one-shot; transient retries (network blips) still happen at the LiteLLM-internal layer below `tiered_node`, but no node-level self-loop. Semantic retries are also disabled (no upstream re-firing primary to course-correct).

4. **Tier registry source** — workflow-agnostic. Add a new `auditor_tier_registry()` function in `ai_workflows/workflows/__init__.py` that returns `{"auditor-sonnet": ..., "auditor-opus": ...}`. Implementation: extract the two entries from one of the existing workflow registries at construction time (e.g. read `planner_tier_registry()`'s auditor entries — verified at `workflows/planner.py:692-703` per T01 close).

`_build_standalone_audit_config(audit_run_id)`, `_build_audit_configurable(...)`, and `_make_standalone_auditor_prompt_fn(artefact)` are private helpers in `mcp/server.py`. The auditor prompt function returns `(system, messages)` per `tiered_node`'s contract verified at `tiered_node.py:119`; emits an auditor prompt of the form: `"Audit the following artefact for correctness. Return AuditVerdict JSON.\n\n<artefact>{json.dumps(artefact, indent=2)}</artefact>"`.

**Configurable dict shape (round-2 M2 — enumerate explicitly).** The `_build_audit_configurable` helper constructs the `config["configurable"]` dict per `tiered_node.py:204-221` requirements:

```text
configurable = {
    "tier_registry": <auditor_tier_registry() output>,  # required — auditor-{sonnet,opus} entries
    "cost_callback": <per-call CostTrackingCallback>,    # required — per-call telemetry isolation
    "run_id": audit_run_id,                              # required — for cost-record keying
    "pricing": {},                                       # required for ClaudeCodeRoute dispatch (Max flat-rate is $0; empty dict is fine — ClaudeCodeSubprocess accepts empty pricing and computes $0)
    "workflow": "standalone-audit",                      # for log-record triage (matches _dispatch._build_cfg pattern)
    # NOT supplied: semaphores (no concurrency caps for one-shot audit),
    # ollama_circuit_breakers (auditors are Claude-only, no Ollama path)
}
```

Without `pricing={}` the AIW_E2E test `test_inline_artefact_audited_by_real_sonnet_e2e` would crash inside `ClaudeCodeSubprocess` looking up the model rate (`tiered_node.py:478-485`); the hermetic test #5 wouldn't catch it because the stub adapter sidesteps the dispatch.

### [.claude/skills/ai-workflows/SKILL.md](../../../.claude/skills/ai-workflows/SKILL.md) — new "Ad-hoc artefact audit" section

Add a new section under §"Primary surface — MCP" (after the existing four tool sections, before §"Fallback surface — `aiw` CLI"):

```markdown
### `run_audit_cascade(run_id_ref?, artefact_kind?, inline_artefact_ref?, tier_ceiling?)`

Audit a completed run's artefact (or an inline dict you pass directly) via an `auditor-{sonnet,opus}` tier. Useful for:

- **Spot-checking a plan** before committing to executing it.
- **Auditing a draft artefact** without kicking off a full workflow run.
- **Confidence-checking an artefact** from a completed run when you want a higher-tier opinion than the run's own cascade produced.

Exactly one of `run_id_ref` / `inline_artefact_ref` must be set. When `run_id_ref` is set, `artefact_kind` is also required (caller picks the kind — planner uses `"plan"`, slice_refactor uses `"applied_artifacts"`; external workflows declare their own kinds in their workflow code per KDR-013). `tier_ceiling` defaults to `"opus"` (highest auditor tier — Max flat-rate $0). Use `"sonnet"` for cheaper audits when the artefact is short or pre-vetted.

Returns `{passed, verdicts_by_tier, suggested_approach, total_cost_usd, by_role}`. On `passed=False`, surface the `suggested_approach` to the user verbatim — that's the auditor's recommendation. Standalone audit is single-pass (no retry, no HumanGate); the verdict comes back in the function return.
```

### Stale design-doc references — `M12 T04` → `M12 T05`

Three pre-T08-renumbering references currently say `M12 T04`. Apply the three one-line edits as part of T05 deliverables (not a separate KDR-isolation commit — these are stale-text fixes, not architectural locks):

1. **`design_docs/architecture.md:105`** — `*(lands at M12 T04 — ...)*` → `*(lands at M12 T05 — ...)*`.
2. **`design_docs/adr/0004_tiered_audit_cascade.md:56`** — `lands in ai_workflows/mcp/server.py (M12 T04)` → `lands in ai_workflows/mcp/server.py (M12 T05)`.
3. **`design_docs/adr/0004_tiered_audit_cascade.md:73`** — `grows run_audit_cascade tool at M12 T04` → `grows run_audit_cascade tool at M12 T05`.

### Tests

#### [tests/mcp/test_run_audit_cascade.py](../../../tests/mcp/test_run_audit_cascade.py) — new (hermetic, 6 tests)

Hermetic. Stub LLM dispatch via `monkeypatch.setattr(tiered_node_module, "ClaudeCodeSubprocess", _StubAuditorAdapter)` (mirror the established stub-pattern at `tests/graph/test_audit_cascade.py:151` `_StubClaudeCodeAdapter` — the cascade primitive's hermetic fixture; sibling variants exist as `_FakeClaudeCodeAdapter` at `tests/graph/test_tiered_node.py:172` and `_E2EStubClaudeCodeAdapter` at `tests/workflows/test_slice_refactor_cascade_enable.py:509`. Builder picks whichever shape transfers cleanly).

1. `test_input_validator_rejects_zero_sources_set` — `RunAuditCascadeInput()` (no sources) → ValidationError.
2. `test_input_validator_rejects_both_sources_set` — both `run_id_ref` and `inline_artefact_ref` set → ValidationError.
3. `test_input_validator_requires_artefact_kind_when_run_id_ref_set` — `RunAuditCascadeInput(run_id_ref="x")` (no artefact_kind) → ValidationError with explicit message.
4. `test_input_validator_rejects_artefact_kind_when_run_id_ref_unset` — `RunAuditCascadeInput(inline_artefact_ref={}, artefact_kind="plan")` → ValidationError.
5. `test_run_audit_cascade_with_inline_artefact_passes_when_auditor_passes` — invoke with `inline_artefact_ref={"foo": "bar"}` and a stub auditor returning `AuditVerdict(passed=True)`. Assert: `output.passed is True`, `output.verdicts_by_tier == {"auditor-opus": AuditVerdict(passed=True, ...)}`, `output.suggested_approach is None`, `output.total_cost_usd == 0.0` (Max flat-rate), `output.by_role.get("auditor", 0.0) == 0.0` (defensive against 0.0 sentinel ambiguity), auditor adapter `calls == 1` (single-pass — no retry).
6. `test_run_audit_cascade_with_run_id_ref_resolves_artefact_via_storage_read_artifact` — seed a completed run via `await storage.write_artifact(run_id, kind="plan", payload_json=json.dumps({"sample": "known dict"}))` (round-2 M1: the storage signature is `write_artifact(run_id, kind, payload_json: str)` — the storage layer does NOT json.dumps for the caller; mirror the slice_refactor.py:1350 pattern). Invoke with `run_id_ref=<that-run-id>, artefact_kind="plan"`; assert the auditor's prompt CONTAINS the inner-payload string `"sample"` AND does NOT contain the storage wrapper keys (`"payload_json"`, `"created_at"`, the literal `"run_id"` key from the row dict — those would prove H2's wrapper-bug regression). Plus: invoke with a missing `(run_id, kind)` → `ToolError`.

#### [tests/mcp/test_run_audit_cascade_e2e.py](../../../tests/mcp/test_run_audit_cascade_e2e.py) — new (AIW_E2E gated, 1 test)

The wire-level smoke per CLAUDE.md *Code-task verification is non-inferential*. Gated by `@pytest.mark.skipif(not os.getenv("AIW_E2E"), reason="...")`:

1. `test_inline_artefact_audited_by_real_sonnet_e2e` — fires the tool with `inline_artefact_ref={"sample": "tiny artefact"}` and `tier_ceiling="sonnet"` (cheaper than opus for the smoke). Real `auditor-sonnet` Claude CLI subprocess. Asserts: `output.passed in (True, False)`, `output.verdicts_by_tier == {"auditor-sonnet": <AuditVerdict>}`, `output.total_cost_usd >= 0.0`, `output.by_role` contains `"auditor"` key, no exception raised. Runs only under `AIW_E2E=1`.

### KDR-003 guardrail — verify, don't extend

Tree-wide grep at `tests/workflows/test_slice_refactor_e2e.py:test_kdr_003_no_anthropic_in_production_tree` already covers `mcp/server.py` + `mcp/schemas.py` + `workflows/__init__.py`. AC: that test still passes. T05 adds no Anthropic SDK surface — auditor tiers ride the existing `ClaudeCodeRoute` per T01.

### [CHANGELOG.md](../../../CHANGELOG.md)

`### Added — M12 Task 05: run_audit_cascade MCP tool + SKILL.md ad-hoc-audit section (YYYY-MM-DD)`. List files touched, ACs satisfied, KDR-008 + KDR-011 cited. Note Option A locked decisions (bypass cascade primitive; caller-supplies-kind). Note 3 stale `M12 T04` → `M12 T05` references fixed.

## Acceptance Criteria

- [ ] `RunAuditCascadeInput` + `RunAuditCascadeOutput` added to `mcp/schemas.py:__all__`. `AuditVerdict` imported from `ai_workflows.graph.audit_cascade` for the `verdicts_by_tier` type hint; **NOT** added to `mcp/schemas.py:__all__` (canonical owner is `graph/audit_cascade.py:75`).
- [ ] `RunAuditCascadeInput` enforces exactly-one of `{run_id_ref, inline_artefact_ref}` via `@model_validator(mode="after")` returning `RunAuditCascadeInput` (not `Self`).
- [ ] `RunAuditCascadeInput` requires `artefact_kind` iff `run_id_ref` is set; rejects `artefact_kind` when `run_id_ref` is unset.
- [ ] `tier_ceiling: Literal["sonnet", "opus"] = "opus"` on input. Field description cites ADR-0009 / KDR-014 (per-call input, NOT a quality knob).
- [ ] `RunAuditCascadeOutput` carries `passed: bool`, `verdicts_by_tier: dict[str, AuditVerdict]`, `suggested_approach: str | None`, `total_cost_usd: float`, `by_role: dict[str, float] | None`.
- [ ] `@mcp.tool() async def run_audit_cascade(payload: RunAuditCascadeInput) -> RunAuditCascadeOutput` exists in `mcp/server.py` after the existing 4 tools.
- [ ] Tool BYPASSES `audit_cascade_node()` per Option A — instantiates `tiered_node(role="auditor", ...)` directly.
- [ ] Auditor `tiered_node` constructed with `role="auditor"` (T04 factory-time binding) — verified by test #5's `output.by_role` assertion.
- [ ] Per-call `audit_run_id` (format `audit-{uuid.uuid4().hex[:12]}`) for telemetry isolation.
- [ ] `_build_standalone_audit_config(audit_run_id)` private helper in `mcp/server.py` constructs per-call `CostTracker` + `CostTrackingCallback` + `RetryPolicy(max_transient_attempts=1, max_semantic_attempts=1)` + tier registry. NOT shared with the dispatch's tracker/callback.
- [ ] New `auditor_tier_registry()` helper in `ai_workflows/workflows/__init__.py` returns `{"auditor-sonnet": ..., "auditor-opus": ...}` extracted from one of the existing workflow registries.
- [ ] `_resolve_audit_artefact` helper lives in `mcp/server.py` (NOT `workflows/_dispatch.py`). Resolves `run_id_ref + artefact_kind` via `await storage.read_artifact(run_id, kind)`, **decodes `row["payload_json"]` via `json.loads`** before returning the artefact dict (round-2 H2 — read_artifact returns the SQL row wrapper, not the artefact); raises `ToolError` on `None` row.
- [ ] Tool body explicitly parses the auditor's raw text via `AuditVerdict.model_validate_json(raw_text)` between `auditor_node(...)` invocation and the verdict-shape check (round-2 H1 — `tiered_node` returns raw text, not a parsed model; the cascade primitive's `_audit_verdict_node` does this parse — Option A's bypass inherits the obligation). Wraps the parse in a `try/except` raising `ToolError` on parse failure.
- [ ] `_build_audit_configurable` constructs the `configurable` dict with: `tier_registry`, `cost_callback`, `run_id`, `pricing={}` (Max flat-rate; required for `ClaudeCodeRoute` dispatch — without it `ClaudeCodeSubprocess` raises KeyError), `workflow="standalone-audit"` (log-record triage). NOT supplied: `semaphores`, `ollama_circuit_breakers` (auditors are Claude-only, no concurrency/breaker need for one-shot audit).
- [ ] `output.by_role` populated via `CostTracker.by_role(audit_run_id)`.
- [ ] All 6 hermetic tests in `tests/mcp/test_run_audit_cascade.py` pass.
- [ ] AIW_E2E-gated wire-level test `tests/mcp/test_run_audit_cascade_e2e.py::test_inline_artefact_audited_by_real_sonnet_e2e` skipped by default; runs and passes under `AIW_E2E=1`.
- [ ] Existing 4 MCP tools still pass their existing tests unchanged.
- [ ] No `ai_workflows/workflows/_dispatch.py` diff. No `ai_workflows/workflows/spec.py` diff. No `ai_workflows/graph/` diff. No `ai_workflows/primitives/` diff.
- [ ] No `pyproject.toml` / `uv.lock` diff.
- [ ] KDR-003 guardrail test still passes.
- [ ] KDR-008 honoured — schema additions purely additive; existing tools' schemas unchanged.
- [ ] `uv run pytest` + `uv run lint-imports` (5 contracts kept) + `uv run ruff check` all clean.
- [ ] CHANGELOG entry under `[Unreleased]` cites KDR-008 + KDR-011 + Option A locked decisions + 3 stale-reference fixes.
- [ ] **Hermetic smoke test:** `tests/mcp/test_run_audit_cascade.py::test_run_audit_cascade_with_inline_artefact_passes_when_auditor_passes` invokes the tool through the FastMCP-registered surface; asserts output schema shape. Always-on; pins schema contract.
- [ ] **Wire-level smoke test:** `tests/mcp/test_run_audit_cascade_e2e.py::test_inline_artefact_audited_by_real_sonnet_e2e` runs once at implement-close under `AIW_E2E=1` against a real `auditor-sonnet` Claude CLI subprocess. Builder runs explicitly and reports verdict per CLAUDE.md non-inferential rule.
- [ ] SKILL.md grows the "Ad-hoc artefact audit" subsection.
- [ ] Status surfaces flipped together at task close: (a) spec `**Status:**` line: `📝 Planned` → `✅ Complete (YYYY-MM-DD)`; (b) milestone README task-table row 05 Status column: `📝 Planned` → `✅ Complete (YYYY-MM-DD)` (Kind stays `code + test + doc`); (c) milestone README §Exit-criteria bullets 7 + 8 ticked from `[ ]` to `[x]`; (d) `architecture.md:105`: `M12 T04` → `M12 T05`; (e) `adr/0004_tiered_audit_cascade.md:56` + `:73`: `M12 T04` → `M12 T05`.

## Dependencies

- **T01** ✅ shipped at `a7f3e8f` (auditor tiers).
- **T02** ✅ shipped at `fc8ef19` (cascade primitive — provides `AuditVerdict` model T05 imports for the type hint).
- **T04** ✅ shipped at `f6904cb` (TokenUsage.role + CostTracker.by_role + factory-time `role` kwarg on `tiered_node` — T05 uses `role="auditor"` at the auditor `tiered_node` construction).
- **T08** ✅ shipped at `e7e8a31` (skip_terminal_gate — not directly used by T05's bypass-primitive path).

## Out of scope (explicit)

- **No `file_path_ref` field.** The "reservation" pattern is over-engineered (would carry a "you can't actually use this" signal forever). Future task adds the field properly when there's a concrete operator need.
- **No multi-tier cascading in the standalone tool.** T05 lands single-tier audit; future multi-tier is a separate task.
- **No `aiw audit-cascade` CLI command.** T05 is MCP-tool-only per the M12 README's exit-criteria #7.
- **No new tier.** Auditor tiers are the T01 set.
- **No telemetry primitive change.** T04's surfaces reused as-is.
- **No HumanGate involvement.** Standalone audit is single-pass.
- **No persistence-layer change.** One-shot in-memory CostTracker.
- **No cascade-primitive amendment.** Per Option A: T05 bypasses `audit_cascade_node()` rather than amending it.
- **No workflow→artefact-kind registry.** Per Option A: caller supplies `artefact_kind`.
- **No Anthropic API.** KDR-003 preserved.

## Propagation status

Filled in at audit time. Anticipated forward-deferrals from T05:

- **ADR-0004 §Decision item 7 amendment** — current text reads "internal routing reuses the same `AuditCascadeNode`"; that framing is stale post-Option-A. Forward-deferred to **M12 T07 close-out** alongside the existing ADR-0004 stale items (§Decision item 1 from T01's TA-LOW-03; §Consequences line 54 from T02's M12-T02-MED-01).
- **`file_path_ref` implementation task** — when there's a concrete operator need.
- **`aiw audit-cascade` CLI command** — natural symmetry with the MCP tool.
- **Multi-tier cascading in standalone mode** — when single-tier verdicts prove unstable.
- **`WORKFLOW_TERMINAL_ARTEFACT_KIND` registry (H2 Option B)** — when there are 3+ in-tree workflows whose terminal artefact kinds the caller would benefit from not having to remember.
- **`audit_cascade_node(primary_artefact=...)` short-circuit (H1 Option C)** — if a future task needs a "thin wrapper" shape that genuinely composes the cascade primitive end-to-end.

## Carry-over from prior milestones

- *None.*

## Carry-over from prior audits

- [ ] **TA-T04-LOW-04 (DEFERRED from T04 task analysis)** — T04's §Propagation status forward-deferred the `by_role` surfacing in `RunAuditCascadeOutput` to T05. T05 spec lands `by_role: dict[str, float] | None` per the AC list above; this carry-over is satisfied. Builder ticks at implement-close.

## Carry-over from task analysis

(Round-1 findings were pre-applied to this rewrite — H1+H2 user-arbitrated to Option A; H3 split smoke into hermetic + AIW_E2E; H4 dropped AuditVerdict re-export; M1 dropped file_path_ref; M2 validator return type; M3 tier_ceiling framing; M4 by_role test assertion + cost-pricing note; M5 standalone-wiring section; M6 stale M12 T04 references. Round-2 added two LOWs that push to carry-over below.)

- [ ] **TA-T05-LOW-01 — Validator error-message ordering / framing precision** (severity: LOW, source: round 2)
      `RunAuditCascadeInput._exactly_one_artefact_source` validator's three error branches fire in a specific order; the second/third branches' messages assume the first branch already passed. If a future caller bypasses the validator (e.g. constructs the model with `model_construct()`), the error ordering may surface in a confusing sequence. Cosmetic — no current caller does this; standard pydantic instantiation always passes through `@model_validator(mode="after")` in order.
      **Recommendation:** No spec edit at implement time. If a future Builder needs to construct the model bypassing validation, document at that time.

- [ ] **TA-T05-LOW-02 — `architecture.md:105` carries a secondary stale framing about "compiled cascade graph" reuse** (severity: LOW, source: round 2)
      Beyond the M12 T04 → M12 T05 task-number fix, `architecture.md:105` also frames the standalone tool as reusing the compiled cascade graph — same stale framing as ADR-0004 §Decision item 7 (post-Option-A). The task-number fix at T05 close-out is mechanical; the cascade-reuse framing fix is an architectural amendment that should land alongside the ADR-0004 amendment at M12 T07 close-out (single doc-amendment commit covers both files' stale framings).
      **Recommendation:** Builder at T05 close-out applies ONLY the task-number fix (`M12 T04` → `M12 T05`); the cascade-reuse framing rewrite at the same line is forward-deferred to T07 close-out alongside the ADR-0004 §Decision item 7 amendment.

- [ ] **TA-T05-LOW-03 — `pricing={}` rationale slightly overstates the requirement** (severity: LOW, source: round 3)
      Spec §Standalone wiring frames `pricing={}` as "required for `ClaudeCodeRoute` dispatch — without it `ClaudeCodeSubprocess` raises KeyError." Live code paths (`tiered_node.py:218` defaults `configurable.get("pricing") or {}`; `claude_code.py:349` returns `0.0` cost when model absent from pricing table) actually default gracefully. Functional behaviour unchanged — `pricing={}` is still passed explicitly per the AC for forward-compatibility — only the rationale framing is slightly stronger than reality.
      **Recommendation:** Builder at implement time may soften the inline comment from "required for ClaudeCodeRoute dispatch (Max flat-rate is $0; empty dict is fine — ClaudeCodeSubprocess accepts empty pricing and computes $0)" to "explicit per spec — Max flat-rate computes $0 with empty pricing; future per-tier-pricing change would surface non-zero values without code change." No spec edit at hardening time; Builder picks at implement time.
