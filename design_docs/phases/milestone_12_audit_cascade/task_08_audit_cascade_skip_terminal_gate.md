# Task 08 — T02 amendment: `audit_cascade_node(skip_terminal_gate=True)` for cascade-exhaustion-without-interrupt path

**Status:** ✅ Complete (2026-04-27).
**Grounding:** [milestone README](README.md) · [task_03 §Folding cascade exhaustion](task_03_workflow_wiring.md) (the consumer of this amendment) · [task_02 close-out (cascade primitive shipped)](task_02_audit_cascade_node.md) · [ai_workflows/graph/audit_cascade.py](../../../ai_workflows/graph/audit_cascade.py) (the module amended) · [ADR-0004](../../adr/0004_tiered_audit_cascade.md) · [architecture.md §4.2 / §9 KDR-006 / KDR-011](../../architecture.md).

## Why this task exists (sequencing exception)

T08 is a **T02 amendment** surfaced during T03 spec hardening (round-4 H1, 2026-04-27). T03's round-3 user arbitration locked Option A for slice_refactor's cascade state-channel home (channels on `SliceBranchState` only; cascade-exhausted branches surface as `SliceFailure` rows). Round 4 surfaced the load-bearing follow-on: **the cascade primitive (T02 shipped at fc8ef19) hard-wires its terminal `human_gate`** at `audit_cascade.py:292-296` + `:447-448`. The gate calls `interrupt(payload)` on exhaustion — and inside slice_refactor's parallel `Send` fan-out, this would trigger N parallel operator interrupts, one per cascade-exhausted branch. T03 cannot ship until this is bypassable.

T03 round-4 H1 surfaced three options (A: extend `audit_cascade_node()` with `skip_terminal_gate=True`; B: hand-roll cascade composition in slice_refactor; C: accept N interrupts). User arbitrated **Option A** (cleanest; backward-compatible) with this T08 task as the new T03 prerequisite. T08 is numbered 8 (out-of-order from T03's 3) so the T03 work doesn't have to renumber; the M12 README task table documents the sequencing exception explicitly.

## What to Build

Extend the `audit_cascade_node()` factory signature (`ai_workflows/graph/audit_cascade.py:122-132`) with a new keyword-only parameter `skip_terminal_gate: bool = False`. Default `False` preserves T02's existing behaviour exactly (no SEMVER concern; backward-compatible). When `True`, the cascade's compiled sub-graph routes verdict-exhaustion to `END` with `state['last_exception'] = AuditFailure(...)` set (instead of routing to the cascade-internal `human_gate` and calling `interrupt`).

The amendment is **strictly additive** — no existing code path changes when callers don't pass the parameter. The cascade primitive's contract (KDR-011 — generative LLM nodes paired with auditor; failure-rendered re-prompt; bounded retries; HumanGate escalation) stays intact for the default path.

The intended consumer is T03's slice_refactor cascade integration (per-branch cascade exhaustion folds into the existing `slice_failures` aggregation surface instead of triggering parallel operator interrupts). Other consumers may emerge for any future cascade composition where the caller wants to handle exhaustion at a different layer (e.g. a workflow-level orchestrator that wants to retry the cascade in a different tier-pair before escalating).

## Deliverables

### [ai_workflows/graph/audit_cascade.py](../../../ai_workflows/graph/audit_cascade.py) — `audit_cascade_node()` signature + sub-graph wiring

#### Signature change

Add `skip_terminal_gate: bool = False` to the factory keyword-only parameters (alongside `auditor_prompt_fn`, `cascade_context_fn`, `name`):

```python
def audit_cascade_node(
    *,
    primary_tier: str,
    primary_prompt_fn: Callable[[GraphState], tuple[str | None, list[dict]]],
    primary_output_schema: type[BaseModel],
    auditor_tier: str,
    policy: RetryPolicy,
    auditor_prompt_fn: Callable[[GraphState], tuple[str | None, list[dict]]] | None = None,
    cascade_context_fn: Callable[[GraphState], tuple[str, str]] | None = None,
    skip_terminal_gate: bool = False,  # NEW (M12 T08): if True, exhaustion routes to END with AuditFailure in state['last_exception'] instead of triggering the cascade's internal human_gate.
    name: str = "audit_cascade",
) -> CompiledStateGraph:
```

Update the docstring `Parameters` block to add a `skip_terminal_gate` entry:

> `skip_terminal_gate`:
>     When `False` (default), the cascade's verdict-exhaustion path routes to a strict `human_gate` (KDR-011's standard escalation). The gate calls `interrupt(payload)` and pauses the parent graph for operator arbitration via the cascade transcript. **This is the right shape when the cascade is the workflow's terminal escalation surface** (e.g. planner workflow's explorer cascade — single graph, single operator interrupt on exhaustion).
>
>     When `True`, the cascade's verdict-exhaustion path instead routes to `END` with `state['last_exception'] = AuditFailure(...)` set (the same `AuditFailure` instance that would have driven the failing re-fire if budget remained). The cascade's `human_gate` node is **not added** to the compiled sub-graph at all. The caller's outer graph is responsible for handling the exhausted state — typically by inspecting `state['last_exception']` after the cascade returns and folding the auditor's verdict into a workflow-specific terminal shape.
>
>     **Use case:** parallel fan-out workflows where the cascade lives inside a per-branch sub-graph (e.g. M12 T03's slice_refactor integration). The cascade's normal `interrupt()` semantics would trigger N parallel operator interrupts, one per cascade-exhausted branch — almost always the wrong UX. With `skip_terminal_gate=True`, the per-branch cascade exhaustion stays branch-local, the branch's own terminal step folds it into the workflow's existing per-branch failure aggregation (e.g. `SliceFailure` row), and the parent graph aggregates as usual.
>
>     **Backward-compatibility:** `False` default preserves T02 behaviour exactly. No SEMVER concern.

#### Sub-graph wiring change

The cascade compiled sub-graph today contains 5 nodes (primary, validator, auditor, verdict, human_gate) plus edges. With `skip_terminal_gate=True`, the human_gate node is omitted entirely:

- `audit_cascade.py:292-296` (gate construction) wraps in `if not skip_terminal_gate:` — gate constructed only when needed.
- `audit_cascade.py:424` (gate `add_node` call) + `audit_cascade.py:448` (gate edge to END) — both wrap in `if not skip_terminal_gate:` so the gate node is neither registered nor edged when the new mode is active.
- `audit_cascade.py:433-437` + `:443-447` (the two `add_conditional_edges` destination-list literals) — the `f"{name}_human_gate"` member must be omitted from the destination list when `skip_terminal_gate=True` (LangGraph compile-time validates that every destination-list member is a registered node; an unregistered destination raises at compile). The after-validator list becomes `[f"{name}_primary", f"{name}_auditor", END]` (END added because `_decide_after_validator` now returns `END` on the `NonRetryable` path under the new mode); the after-verdict list becomes `[f"{name}_primary", END]`.
- `_decide_after_validator()` (audit_cascade.py:322-334): the `f"{name}_human_gate"` return becomes `END` when `skip_terminal_gate=True`. The `last_exception` (`NonRetryable` from in-validator escalation) stays in state for the caller to inspect.
- `_decide_after_verdict()` (audit_cascade.py:349-381): the four `return f"{name}_human_gate"` paths become `return END` when `skip_terminal_gate=True`. `state['last_exception']` carries the `AuditFailure` (for verdict-exhaustion paths) or `NonRetryable` (for double-failure or NonRetryable paths) — caller inspects.

The two route-to-gate decision functions read `skip_terminal_gate` via closure capture (the parameter is in scope when `audit_cascade_node()` builds them). Mechanically:

```python
# After validator (existing):
def _decide_after_validator(state: GraphState) -> str:
    exc = state.get("last_exception")
    if isinstance(exc, NonRetryable):
        return END if skip_terminal_gate else f"{name}_human_gate"
    return _decide_after_validator_base(state)

# After verdict (existing _decide_after_verdict — every f"{name}_human_gate"
# return becomes:
#   return END if skip_terminal_gate else f"{name}_human_gate"
```

The `END` import already exists (`from langgraph.graph import END`).

#### Public surface — no other change

`AuditVerdict`, `AuditFailure`, `_render_audit_feedback`, `cascade_role`, `cascade_transcript` channels, all 7 prefixed channels — UNCHANGED. The amendment is one new kwarg and conditional gate-omission; no other public surface or contract changes.

### Tests — extend [tests/graph/test_audit_cascade.py](../../../tests/graph/test_audit_cascade.py) (existing file)

Add four new tests at the end of the file (preserving the existing 7 cascade tests + 5 template tests landed at T02). Each uses the same `_FakeLiteLLMAdapter` / `_FakeClaudeCodeAdapter` monkey-patch pattern as the existing T02 tests:

1. `test_skip_terminal_gate_default_false_preserves_t02_behaviour` — invoke `audit_cascade_node(skip_terminal_gate=False, ...)` (or omit — same default). Drive an exhaustion scenario (auditor returns `passed=False` until `max_semantic_attempts`). Assert: cascade reaches the `{name}_human_gate` node; `final["__interrupt__"]` is non-empty (gate fired); `strict_review=True` in the interrupt payload. Same as existing T02 test 3 (`test_cascade_exhausts_retries_routes_to_strict_human_gate`) — pinning the default-False path so the new conditional doesn't accidentally regress it.

2. `test_skip_terminal_gate_true_omits_human_gate_node_from_compiled_subgraph` — invoke `audit_cascade_node(skip_terminal_gate=True, ...)`. Assert: `f"{name}_human_gate" not in compiled.nodes` (the gate node is structurally absent, not just unreached). Pins the "no gate constructed at all" contract — the cascade caller doesn't pay the gate-allocation cost when skip is on.

3. `test_skip_terminal_gate_true_routes_exhaustion_to_END_with_audit_failure_in_state` — invoke with `skip_terminal_gate=True`; drive an auditor-fail-every-attempt scenario with `RetryPolicy(max_semantic_attempts=2)`. Assert: graph reaches `END` (no `__interrupt__`); `state["last_exception"]` is an `AuditFailure` instance; `state["last_exception"].failure_reasons` matches the auditor's last verdict; `state["last_exception"].suggested_approach` matches the auditor's last verdict; `state["cascade_transcript"]["author_attempts"]` length is 2; `state["cascade_transcript"]["auditor_verdicts"]` length is 2.

4. `test_skip_terminal_gate_true_routes_validator_exhaustion_to_END_with_nonretryable_in_state` — invoke with `skip_terminal_gate=True`; drive primary-always-shape-invalid scenario (mirror existing `test_cascade_pure_shape_failure_never_invokes_auditor` shape but with `skip_terminal_gate=True`). Assert: graph reaches `END` (no `__interrupt__`); `state["last_exception"]` is `NonRetryable` (from in-validator M6 T07 escalation); auditor adapter call count is 0 (auditor never invoked under pure-shape-failure exhaustion).

The test count for `tests/graph/test_audit_cascade.py` grows from 7 → 11 cascade tests in this file (+4 from T08). The 5 audit-feedback-template tests at `tests/primitives/test_audit_feedback_template.py` are unaffected — that's a separate file.

### KDR-003 guardrail — verify, don't extend

The tree-wide `tests/workflows/test_slice_refactor_e2e.py:test_kdr_003_no_anthropic_in_production_tree` automatically covers the amended `audit_cascade.py`. AC: that test still passes. T08 makes no Anthropic-SDK-touching changes; the parameter and the conditional gate-omission are pure graph topology.

### [CHANGELOG.md](../../../CHANGELOG.md)

Under `## [Unreleased]`, add `### Changed — M12 Task 08: AuditCascadeNode skip_terminal_gate parameter (T02 amendment) (YYYY-MM-DD)` (NB: `### Changed` not `### Added` — the cascade primitive's signature gains a kwarg). List:

- Files touched: `ai_workflows/graph/audit_cascade.py` (new `skip_terminal_gate` kwarg + conditional gate-omission in sub-graph compose), `tests/graph/test_audit_cascade.py` (4 new tests).
- KDR-006 (RetryingEdge taxonomy) preserved — `AuditFailure` still routes via `RetryableSemantic` bucket; only the terminal route changes.
- KDR-011 (cascade primitive contract) preserved — default behaviour unchanged; the new mode is an explicit caller-opt-in.
- Backward compatibility: default `False` preserves T02 behaviour byte-for-byte. Existing callers (none in tree at T08 land time — T03 will be the first) unaffected.
- T03 prerequisite: T03 spec calls `audit_cascade_node(skip_terminal_gate=True, ...)` for slice_refactor's per-branch cascade. T03 cannot ship until T08 closes.

## Acceptance Criteria

- [ ] `audit_cascade_node()` factory signature grows `skip_terminal_gate: bool = False` keyword-only parameter (added between `cascade_context_fn` and `name` to preserve the existing positional/keyword conventions).
- [ ] Docstring `Parameters` block documents the new parameter with the use-case explanation (parallel fan-out workflows where per-branch cascade exhaustion would trigger N parallel operator interrupts).
- [ ] Default `False` preserves T02 behaviour exactly — verified by re-running the existing 7 cascade tests in `tests/graph/test_audit_cascade.py` from scratch; all pass unchanged.
- [ ] When `skip_terminal_gate=True`, the cascade's `human_gate` node is **not** added to the compiled sub-graph (`f"{name}_human_gate" not in compiled.nodes`).
- [ ] When `skip_terminal_gate=True`, verdict-exhaustion routes to `END` with `state["last_exception"]` set to an `AuditFailure` carrying the auditor's last verdict (`failure_reasons` + `suggested_approach`).
- [ ] When `skip_terminal_gate=True`, validator-exhaustion (in-validator M6 T07 escalation) routes to `END` with `state["last_exception"]` set to `NonRetryable`. Auditor never invoked under pure-shape-failure exhaustion.
- [ ] All 4 new tests pass: `test_skip_terminal_gate_default_false_preserves_t02_behaviour`, `test_skip_terminal_gate_true_omits_human_gate_node_from_compiled_subgraph`, `test_skip_terminal_gate_true_routes_exhaustion_to_END_with_audit_failure_in_state`, `test_skip_terminal_gate_true_routes_validator_exhaustion_to_END_with_nonretryable_in_state`.
- [ ] All existing T02 tests in `tests/graph/test_audit_cascade.py` (7 cascade + 5 template) still pass — backward-compat regression guard.
- [ ] No `ai_workflows/workflows/` diff (T08 is graph-layer only; T03 is the consumer).
- [ ] No `ai_workflows/mcp/` diff (T05 is the standalone MCP tool task).
- [ ] No `ai_workflows/primitives/retry.py` diff (`AuditFailure` exception unchanged; `classify()` extension from T02 unchanged).
- [ ] No `pyproject.toml` diff (no new import-linter contract — T08 amends an existing module, doesn't add a new one).
- [ ] KDR-003 guardrail tests pass (`test_kdr_003_no_anthropic_in_production_tree` and the file-scoped guard) — neither extension required since T08 changes graph topology only.
- [ ] `uv run pytest` + `uv run lint-imports` (5 contracts kept — T02's audit_cascade contract still applies and still kept) + `uv run ruff check` all clean.
- [ ] CHANGELOG entry under `[Unreleased]` cites T02 amendment + KDR-006/KDR-011 preservation + backward-compat.
- [ ] **Smoke test (CLAUDE.md non-inferential rule):** `tests/graph/test_audit_cascade.py::test_skip_terminal_gate_true_routes_exhaustion_to_END_with_audit_failure_in_state` is the wire-level smoke — it invokes the compiled cascade end-to-end through real `tiered_node` + `validator_node` + `wrap_with_error_handler` + `retrying_edge` (only LLM dispatch stubbed) and asserts the exhausted state lands at END with the AuditFailure preserved. Builder runs this test explicitly and reports the result.
- [ ] Status surfaces flipped together at close: (a) this spec's `**Status:**` line to `✅ Complete (YYYY-MM-DD).`; (b) milestone README task-table row 08 status indicator. There is no exit-criteria bullet for T08 specifically (T08 is a T02 amendment surfaced during T03 hardening; it's a sequencing exception, not a milestone-level deliverable in its own right). T03's exit-criteria bullet 5 covers the consumer.

## Dependencies

- **T02** — `audit_cascade_node` factory must exist. **Met:** T02 shipped at `fc8ef19`.

## Out of scope (explicit)

- **No edit to `AuditFailure` exception class.** T02 pinned the constructor; T08 reuses it verbatim.
- **No edit to `_render_audit_feedback`.** T02's template is unchanged.
- **No edit to `RetryingEdge`.** T08 changes how the cascade composes its terminal route, not the retry-edge primitive.
- **No edit to `human_gate`.** The gate factory is unchanged; T08 just conditionally omits the gate node from the cascade sub-graph.
- **No new exception class.** Existing `AuditFailure` + `NonRetryable` carry the exhausted state.
- **No telemetry change.** T04 is the telemetry task; T08 doesn't read or write `TokenUsage.role`.
- **No workflow integration.** T03 is the consumer; T08 only ships the primitive amendment.
- **No KDR addition.** T08 preserves KDR-006 + KDR-011 verbatim. The amendment is implementation-detail of KDR-011's mechanism, not a new architectural lock.
- **No SEMVER bump.** Backward-compatible kwarg addition with default that preserves existing behaviour. SEMVER-patch-or-minor at next release.
- **No Anthropic API.** KDR-003 preserved.

## Carry-over from prior milestones

- *None.*

## Carry-over from prior audits

- *None at draft time. T02's audit produced no carry-over for T08 (T08 is itself a follow-on to T02, surfaced at T03 hardening time).*

## Carry-over from task analysis

- [x] **TA-T08-LOW-01 — Test #2 cross-reference uses positional number that drifts** (severity: LOW, source: task_analysis.md round 1 L1)
      Test #4 in T08's spec mirrors an existing `tests/graph/test_audit_cascade.py` test by name (`test_cascade_pure_shape_failure_never_invokes_auditor`) — already corrected during round-1 fix application; the original positional citation ("test 7") drifted from the live file's order (test #5 by position). The test name is canonical; positional references should be avoided.
      **Recommendation:** Builder should avoid positional test references in any new docstrings or comments referencing this test; use the test name only.

- [x] **TA-T08-LOW-02 — T03 dependency-block hash substitution at T08 close** (severity: LOW, source: task_analysis.md round 1 L2) — APPLIED in follow-up commit. T03 spec's `## Dependencies` line for T08 now reads `**Met:** T08 shipped at \`e7e8a31\`.` matching the T01/T02 conventions. Lands as a separate commit on the same push as T08's implementation commit (the spec recommendation called for a single atomic commit, but `git commit hash` is not available pre-commit; two commits + single push keeps the bidirectional reference correct without violating the safety protocol on `--amend`).
      Original recommendation text: *"When T08 closes (commit lands on `design_branch`), the autopilot orchestrator's commit-ceremony for T08 must edit `task_03_workflow_wiring.md` `## Dependencies` block to replace the placeholder text with `Met: T08 shipped at <commit-hash>.` matching the T01 / T02 conventions."*

## Propagation status

- **Commit isolation.** The T08 implementation lands as an isolated commit per autonomy decision 2 (T08 amends a shipped public-ish primitive; isolated commit preserves the audit trail and lets the amendment be reverted independently of T03 if review later objects). The autonomy-loop's commit-ceremony for T08 follows the standard auto-implement flow — no special handling beyond the normal /auto-implement procedure.
- **T03 implementation reads T08's landed commit hash at audit time.** T03 spec's §Folding cascade exhaustion sub-section references `audit_cascade_node(skip_terminal_gate=True)` directly; T03 audit confirms T08 is in the merge-base before T03 ships.
- **T02 audit issue file (`issues/task_02_issue.md`) does NOT need a propagation entry to T08.** T08 was surfaced at T03 hardening time, after T02 already closed clean. The /clean-tasks round-4 audit on T03 surfaced the gap; T08 spec is the formalization. T02's issue file is closed (`✅ PASS`) and stays closed; T08 is independent follow-on work, not a T02 carry-over.
