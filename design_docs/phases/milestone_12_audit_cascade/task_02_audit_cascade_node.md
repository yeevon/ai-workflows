# Task 02 — `AuditCascadeNode` graph primitive + `AuditFailure` exception + RetryingEdge re-prompt template

**Status:** ✅ Complete (2026-04-27).
**Grounding:** [milestone README](README.md) · [ADR-0004 §Decision item 4](../../adr/0004_tiered_audit_cascade.md) · [architecture.md §4.2 (graph adapters) / §4.4 (MCP) / §8.2 (retry taxonomy) / §9 KDR-004 / KDR-006 / KDR-009 / KDR-011](../../architecture.md) · [primitives/retry.py:79-92 (`RetryableSemantic`)](../../../ai_workflows/primitives/retry.py#L79-L92) · [graph/tiered_node.py](../../../ai_workflows/graph/tiered_node.py) · [graph/validator_node.py](../../../ai_workflows/graph/validator_node.py) · [graph/retrying_edge.py](../../../ai_workflows/graph/retrying_edge.py) · [graph/human_gate.py](../../../ai_workflows/graph/human_gate.py) · [task_01 close-out (auditor TierConfigs landed)](task_01_auditor_tier_configs.md).

## What to Build

A new graph-layer primitive `AuditCascadeNode` that composes `TieredNode(primary) → ValidatorNode(shape) → TieredNode(auditor) → AuditVerdictNode` into a single sub-graph compilable into any outer `StateGraph`. The cascade pairs every generative LLM node whose output is read downstream with an auditor one tier above (per ADR-0004 §Decision item 3); on auditor verdict `passed=False`, the audit-verdict node raises a new `AuditFailure` exception (a `RetryableSemantic` subclass living in `primitives/retry.py`) carrying the rendered re-prompt as its `revision_hint`. The existing `RetryingEdge` (KDR-006) routes the failure back to the primary `TieredNode`, which picks up the hint via `state['last_exception'].revision_hint` and re-fires with enriched context. After `RetryPolicy.max_semantic_attempts` exhaustion, the cascade routes to a strict `HumanGate` carrying the full cascade transcript (`author_attempts: list[str]`, `auditor_verdicts: list[AuditVerdict]`) for manual arbitration.

T02 is **graph-layer + one primitives-layer addition only**. No workflow integration (T03), no telemetry role tag (T04), no MCP tool (T05), no eval harness (T06). The cascade is built but not yet consumed by any workflow at T02 close.

## Deliverables

### [ai_workflows/primitives/retry.py](../../../ai_workflows/primitives/retry.py) — `AuditFailure` exception

Add a new exception class **subclassing `RetryableSemantic`** (so the existing `classify()` mapping treats it correctly without an entry — `isinstance(exc, RetryableSemantic)` already returns `True` for any `AuditFailure`). Append `AuditFailure` to the module's `__all__` tuple. The re-prompt template lives **inside `AuditFailure.__init__` as a private module-level helper** (`_render_audit_feedback`); it is **not** exported via `__all__` and **not** imported across modules. Single ownership site — the cascade primitive constructs `AuditFailure(...)` and reads `exc.revision_hint` rather than re-rendering.

```python
class AuditFailure(RetryableSemantic):
    """Auditor verdict was passed=False — the primary's output failed semantic review.

    Carries the structured verdict payload + the rendered revision-guidance
    template the primary node will pick up on its next re-fire. Bucketed
    `RetryableSemantic` per KDR-006 so the existing `RetryingEdge` routes
    it back to the primary without taxonomy edits.
    """

    def __init__(
        self,
        *,
        failure_reasons: list[str],
        suggested_approach: str | None,
        primary_original: str,
        primary_context: str,
    ) -> None:
        revision_hint = _render_audit_feedback(
            primary_original=primary_original,
            failure_reasons=failure_reasons,
            suggested_approach=suggested_approach,
            primary_context=primary_context,
        )
        super().__init__(
            reason=f"audit_failed: {len(failure_reasons)} reason(s)",
            revision_hint=revision_hint,
        )
        self.failure_reasons = failure_reasons
        self.suggested_approach = suggested_approach
```

Plus the rendering helper at module scope (private — leading underscore, **not** in `__all__`, **not** imported by `audit_cascade.py` or any other module). The template is owned by `AuditFailure` and surfaced only via `exc.revision_hint`:

```python
def _render_audit_feedback(
    *,
    primary_original: str,
    failure_reasons: list[str],
    suggested_approach: str | None,
    primary_context: str,
) -> str:
    """Render the audit-feedback re-prompt template (KDR-011, exit criterion 3).

    Exact shape pinned by `tests/primitives/test_audit_feedback_template.py`:

        <primary_original>

        <audit-feedback>
        Reasons:
        - <reason 1>
        - <reason 2>
        Suggested approach: <suggested_approach or "(none)">
        </audit-feedback>

        <primary_context>

    Trailing newline omitted. The reasons block always renders (empty list
    → "Reasons:\\n- (none)"); suggested_approach renders "(none)" when the
    auditor returned None.
    """
    reasons_block = "\n".join(f"- {r}" for r in failure_reasons) or "- (none)"
    suggested = suggested_approach or "(none)"
    return (
        f"{primary_original}\n\n"
        f"<audit-feedback>\n"
        f"Reasons:\n{reasons_block}\n"
        f"Suggested approach: {suggested}\n"
        f"</audit-feedback>\n\n"
        f"{primary_context}"
    )
```

**No edit to `classify()`** — `AuditFailure` is structurally a `RetryableSemantic`, and the function maps by `isinstance` against the bucket types it owns. The taxonomy stays three-bucket; `AuditFailure` is a typed instance of an existing bucket, not a new bucket.

### [ai_workflows/graph/audit_cascade.py](../../../ai_workflows/graph/audit_cascade.py) — new graph primitive

Create the new module. Module docstring follows the existing `graph/*.py` convention (cite task ID + KDRs + architecture refs + relationship to sibling modules).

#### Public surface

```python
from collections.abc import Callable, Mapping
from typing import Any
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field

from ai_workflows.graph.error_handler import wrap_with_error_handler
from ai_workflows.graph.human_gate import human_gate
from ai_workflows.graph.retrying_edge import retrying_edge
from ai_workflows.graph.tiered_node import tiered_node
from ai_workflows.graph.validator_node import validator_node
from ai_workflows.primitives.retry import AuditFailure, RetryPolicy

GraphState = Mapping[str, Any]  # mirrors graph/tiered_node.py:111

class AuditVerdict(BaseModel):
    """Auditor's structured response for a single primary attempt."""
    passed: bool
    failure_reasons: list[str] = Field(default_factory=list)
    suggested_approach: str | None = None


def audit_cascade_node(
    *,
    primary_tier: str,
    primary_prompt_fn: Callable[[GraphState], tuple[str | None, list[dict]]],
    primary_output_schema: type[BaseModel],
    auditor_tier: str,
    policy: RetryPolicy,
    auditor_prompt_fn: Callable[[GraphState], tuple[str | None, list[dict]]] | None = None,
    cascade_context_fn: Callable[[GraphState], tuple[str, str]] | None = None,
    name: str = "audit_cascade",
) -> CompiledStateGraph:
    """Compile a cascade sub-graph: primary → validator → auditor → verdict.

    Returns a `CompiledStateGraph` that can be added as a single node to
    any outer `StateGraph` via `outer.add_node(name, audit_cascade_node(...))`.
    The sub-graph reuses `tiered_node` + `validator_node` for the primary
    half and `tiered_node` for the auditor half — no LLM dispatch logic
    is duplicated.

    Parameters
    ----------
    primary_tier:
        Tier name for the author/generative call (e.g. ``"planner-explorer"``,
        ``"slice-worker"``).
    primary_prompt_fn:
        Same signature as `tiered_node`'s `prompt_fn` — accepts the graph
        state and returns ``(system, messages)``. Called twice per cascade
        cycle: once by the primary `tiered_node`, once by the verdict node
        when constructing `AuditFailure(primary_original=...)` (unless
        `cascade_context_fn` is supplied — see below).
    primary_output_schema:
        Pydantic model the validator parses against. The parsed instance is
        written to state under `f"{name}_primary_parsed"`.
    auditor_tier:
        Tier name for the audit call (`"auditor-sonnet"` or `"auditor-opus"`
        from T01).
    policy:
        Retry budget for both the validator-shape-failure hop and the
        audit-failure hop. Production sites pass a workflow-level constant
        (see `planner.py:528,556` for the `PLANNER_RETRY_POLICY` pattern).
    auditor_prompt_fn:
        Optional. Same signature as `primary_prompt_fn`. Defaults to a
        built-in renderer that emits: ``Audit the following <schema-name>
        for <primary_tier>. Return an AuditVerdict JSON. <primary_output
        verbatim>``. Reads `state[f"{name}_primary_parsed"]` for the
        verbatim payload.
    cascade_context_fn:
        Optional. Returns `(primary_original, primary_context)` for the
        `AuditFailure` constructor on each verdict-failure raise. Defaults
        to re-calling `primary_prompt_fn(state)` and using its rendered
        system+messages for `primary_original`; `primary_context` defaults
        to the empty string. Override when the workflow has additional
        context state (e.g. multi-turn slice-worker history) that should
        be appended after the audit-feedback block.
    name:
        Sub-graph node-name prefix. Defaults to ``"audit_cascade"``;
        override when composing more than one cascade in the same outer
        graph to keep node names disjoint.

    Behaviour
    ---------
    On auditor verdict `passed=False`, the audit-verdict step raises
    `AuditFailure(failure_reasons=..., suggested_approach=...,
     primary_original=<rendered primary prompt>,
     primary_context=<state-derived primary context>)`. RetryingEdge
    routes the failure back to the primary `tiered_node`; the primary
    picks up the rendered revision_hint on re-entry via
    `state['last_exception'].revision_hint`.

    On `RetryPolicy.max_semantic_attempts` exhaustion, the validator's
    in-validator escalation (M6 T07 pattern) converts the final
    `AuditFailure` to `NonRetryable`, and RetryingEdge routes to the
    cascade's terminal HumanGate. The HumanGate carries
    `state['cascade_transcript'] = {"author_attempts": [...],
     "auditor_verdicts": [AuditVerdict, ...]}` so the operator can
    arbitrate manually (M11 gate-context projection surfaces these
    keys at the MCP boundary — see ADR-0004 §Context).
    """
```

#### Sub-graph wiring

The compiled sub-graph contains four nodes in this order. **Every node is wrapped with `wrap_with_error_handler`** (`ai_workflows/graph/error_handler.py`) — without that wrap, a raised bucket exception (`RetryableTransient` / `RetryableSemantic` / `AuditFailure` / `NonRetryable`) propagates uncaught and LangGraph aborts the graph instead of routing through `retrying_edge`. The wrap is what writes `state['last_exception']` + bumps `state['_retry_counts'][<node_name>]` (M2 T08 / M6 T07 pattern; verified `planner.py:475,484,493,502` — every production node uses it):

1. `<name>_primary` — `wrap_with_error_handler(tiered_node(tier=primary_tier, prompt_fn=primary_prompt_fn, output_key=f"{name}_primary_output", ...), node_name=f"{name}_primary")`. Tagged with `state['cascade_role'] = "author"` (channel for T04's role-tagged TokenUsage).
2. `<name>_validator` — `wrap_with_error_handler(validator_node(schema=primary_output_schema, input_key=f"{name}_primary_output", output_key=f"{name}_primary_parsed", node_name=f"{name}_primary", max_attempts=policy.max_semantic_attempts), node_name=f"{name}_primary")`. Standard KDR-004 shape pairing. The `input_key`/`output_key` pin the intermediate state channels so the auditor's prompt_fn knows where to read the parsed payload from. The `node_name=f"{name}_primary"` matches the upstream tiered_node's name so `validator_node`'s in-validator escalation (M6 T07) reads the correct retry counter.
3. `<name>_auditor` — `wrap_with_error_handler(tiered_node(tier=auditor_tier, prompt_fn=<built-in or supplied>, output_key=f"{name}_auditor_output", ...), node_name=f"{name}_auditor")`. Tagged with `state['cascade_role'] = "auditor"`. The built-in `prompt_fn` reads `state[f"{name}_primary_parsed"]` for the verbatim payload.
4. `<name>_verdict` — `wrap_with_error_handler(_audit_verdict_node(...), node_name=f"{name}_primary")`. New internal node — see §Internal node block below. Parses the auditor's raw output as `AuditVerdict`; appends to `state['cascade_transcript']`; on `passed=False` raises `AuditFailure(...)` with the rendered revision template. Tagged with `state['cascade_role'] = "verdict"`. Wrapped with `node_name=f"{name}_primary"` (not `f"{name}_verdict"`) so the validator's in-validator escalation reads from the same retry-counter key as audit failures — both shape-fail and audit-fail share the primary's budget.

Edge wiring:
- `<name>_primary` → `<name>_validator` (linear, success path).
- `<name>_validator` → `retrying_edge(on_transient=f"{name}_primary", on_semantic=f"{name}_primary", on_terminal=f"{name}_human_gate", policy=policy)` (existing M2 T07 pattern; the validator handles shape failures).
- `<name>_validator` → `<name>_auditor` on success (parsed instance in state at `f"{name}_primary_parsed"`).
- `<name>_auditor` → `<name>_verdict` (linear).
- `<name>_verdict` → `retrying_edge(on_transient=f"{name}_primary", on_semantic=f"{name}_primary", on_terminal=f"{name}_human_gate", policy=policy)` — same retrying-edge pattern; `AuditFailure`'s `RetryableSemantic` bucketing routes back to the primary.
- `<name>_human_gate` — `human_gate(gate_id=f"{name}_audit_exhausted", prompt_fn=<built-in cascade-transcript renderer>, strict_review=True)`.

The compiled sub-graph exposes a single entry node (`<name>_primary`) and a single exit node (the verdict node on success, the human_gate on exhaustion).

#### Counter-sharing contract

The validator + verdict + primary all bump the **same** `_retry_counts[f"{name}_primary"]` key (because all three are wrapped with `node_name=f"{name}_primary"` per §Sub-graph wiring). This is intentional — the cascade treats shape-failure and audit-failure as a **shared semantic budget** against the primary's `policy.max_semantic_attempts`. A primary that combines audit failures with shape failures across attempts is failing harder than either alone, and exhaustion routes to the same terminal `HumanGate` either way.

The interaction with `validator_node`'s in-validator escalation (M6 T07; `validator_node.py:135-142`) is subtle: the validator reads `state['_retry_counts'][node_name]` (where `node_name=f"{name}_primary"`) and escalates `RetryableSemantic → NonRetryable` when `prior_failures >= max_attempts - 1`. With shared counter, an `AuditFailure` raised on cycle N bumps the counter to N; if cycle N+1 then surfaces a shape failure, the validator's in-validator check sees the audit-bumped counter and may escalate sooner than a pure shape-failure-only sequence would.

Worked example with `policy.max_semantic_attempts=3`:
- Cycle 1: primary → validator(passes shape) → auditor → verdict raises `AuditFailure`. Counter bumps to 1.
- Cycle 2: primary → validator gets shape-invalid output. Validator's in-validator check: `prior_failures=1`, `max_attempts=3`, `1 >= 3-1` → False, so raises `RetryableSemantic` (not `NonRetryable`). Counter bumps to 2.
- Cycle 3: primary → validator gets shape-invalid output again. In-validator check: `prior_failures=2`, `2 >= 3-1` → True, escalates to `NonRetryable`. Counter bumps to 3. retrying_edge routes to `on_terminal` (HumanGate) on the next hop.

A pure-audit-failure-only sequence (no shape failures interleaved) reaches the human_gate after exactly `max_semantic_attempts` primary attempts. Test #3 below pins this clean scenario.

A pure-shape-failure-only sequence (auditor never invoked, see test #4) also reaches the in-validator `NonRetryable` escalation on the same cycle. Test #4 pins this — auditor adapter call count is 0.

#### Internal node — `_audit_verdict_node`

Module-private factory. Same signature shape as `validator_node` but specialised for the cascade.

```python
def _audit_verdict_node(
    *,
    name: str,
    primary_prompt_fn: Callable[[GraphState], tuple[str | None, list[dict]]],
    cascade_context_fn: Callable[[GraphState], tuple[str, str]] | None,
) -> Callable[[GraphState], dict[str, Any]]:
    """Parses auditor output → AuditVerdict; appends to transcript; raises AuditFailure on passed=False.

    Reads:
      state[f"{name}_auditor_output"] — raw text from the auditor tiered_node
      state[f"{name}_primary_parsed"] — parsed primary payload (for transcript)

    Writes:
      state[f"{name}_audit_verdict"] — parsed AuditVerdict instance
      state["cascade_transcript"]["author_attempts"].append(<primary raw text>)
      state["cascade_transcript"]["auditor_verdicts"].append(<AuditVerdict>)
      state["cascade_role"] = "verdict"

    Raises:
      AuditFailure (RetryableSemantic subclass) when verdict.passed is False.
      Constructor args:
        primary_original, primary_context = (
            cascade_context_fn(state) if cascade_context_fn is not None
            else (_default_primary_original(state, primary_prompt_fn), "")
        )
        failure_reasons = verdict.failure_reasons
        suggested_approach = verdict.suggested_approach

    The `_default_primary_original` helper re-calls `primary_prompt_fn(state)`
    and joins the (system, messages) tuple into a single rendered string —
    same shape as the primary's first invocation prompt.
    """
```

Pin in spec because every Builder choice that's not pinned drifts: input keys, output keys, transcript-append shape, AuditFailure constructor inputs.

#### State channels added by the cascade

- `cascade_transcript: dict[str, list]` — keys `author_attempts: list[str]` (raw primary outputs across attempts) and `auditor_verdicts: list[AuditVerdict]` (full verdict payloads). Initialised on first primary entry; appended on every subsequent attempt. Survives via LangGraph's checkpointer (KDR-009) — no new persistence table.
- `cascade_role: Literal["author", "auditor", "verdict"]` — the role tag T04 will read into `TokenUsage.role`. Stamped by each cascade sub-node on entry; not inspected by anything in T02 (telemetry consumption lands at T04). Reserving the channel here so T04 is a pure consumer.
- `<name>_primary_output: str` — raw primary text written by the inner `tiered_node`'s `output_key`. Consumed by `<name>_validator`'s `input_key`.
- `<name>_primary_parsed: <primary_output_schema instance>` — validated payload written by `<name>_validator`'s `output_key`. Consumed by the auditor's `prompt_fn` (default reads it as the verbatim audit subject) and by the verdict node's transcript append.
- `<name>_auditor_output: str` — raw auditor text written by the inner `tiered_node`'s `output_key`. Consumed by `<name>_verdict`.
- `<name>_audit_verdict: AuditVerdict` — parsed verdict written by the verdict node. Consumed downstream by any caller that wants to inspect the final verdict (T03 will read this for the workflow-integration path; T02 only writes).

### [ai_workflows/graph/retrying_edge.py](../../../ai_workflows/graph/retrying_edge.py) — no behavioural change; docstring update only

The existing `retrying_edge` already routes `RetryableSemantic` to `on_semantic`, and `AuditFailure` is a `RetryableSemantic` subclass — so the routing path works unchanged. Update the module docstring's "Relationship to sibling modules" section to add a bullet:

> * ``graph/audit_cascade.py`` (M12 T02) — emits :class:`AuditFailure`
>   (a `RetryableSemantic` subclass) from the audit-verdict node when
>   the auditor reports `passed=False`. This edge routes it back to
>   the primary `tiered_node` via the same `on_semantic` hop used for
>   shape failures; the primary picks up the rendered audit-feedback
>   template via `state['last_exception'].revision_hint` on re-entry.

No code edit; documentation alignment only. (If the auditor folds the docstring update into a single docstring tweak elsewhere, that is acceptable — the deliverable is the cross-reference, not the literal location.)

### [pyproject.toml](../../../pyproject.toml) — new import-linter contract

Add a fifth `[[tool.importlinter.contracts]]` block immediately after the existing `evals cannot import surfaces` contract, pinning the cascade primitive to graph-layer composition only:

```toml
[[tool.importlinter.contracts]]
name = "audit_cascade composes only graph + primitives"
type = "forbidden"
source_modules = ["ai_workflows.graph.audit_cascade"]
forbidden_modules = [
    "ai_workflows.workflows",
    "ai_workflows.cli",
    "ai_workflows.mcp",
]
```

(This is module-scoped narrower than the existing `graph cannot import workflows or surfaces` contract; the new contract provides drift defense if a future commit ever moves `audit_cascade.py` outside `ai_workflows/graph/` or adds a workflow / surface import inside it. The README's exit criterion #11 calls for this contract; the spec asserts `lint-imports` reports `5 contracts kept`. ADR-0004 §Consequences line 54 (`No import-linter edit needed`) is now stale — superseded by this contract. The ADR amendment lands as part of M12 T07 close-out alongside `M12-T01-ISS-02` (the ADR-0004 §Decision item 1 stale-framing fix); see §Propagation status.)

### [CHANGELOG.md](../../../CHANGELOG.md)

Under `## [Unreleased]`, add `### Added — M12 Task 02: AuditCascadeNode primitive + AuditFailure exception (YYYY-MM-DD)`. List:

- Files touched: `ai_workflows/graph/audit_cascade.py` (new), `ai_workflows/primitives/retry.py` (added `AuditFailure` + `_render_audit_feedback`), `ai_workflows/graph/retrying_edge.py` (docstring cross-ref only), `pyproject.toml` (new import-linter contract), `tests/graph/test_audit_cascade.py` (new), `tests/primitives/test_audit_feedback_template.py` (new). Zero diff at `ai_workflows/workflows/` (workflow wiring lands at T03), `ai_workflows/mcp/` (MCP tool lands at T05), `evals/` (fixture convention lands at T06).
- ACs satisfied (linked back to this spec).
- KDR-003 / KDR-004 / KDR-006 / KDR-011 cited.

## Tests

### [tests/primitives/test_audit_feedback_template.py](../../../tests/primitives/test_audit_feedback_template.py) — new

Hermetic. Pins the exact rendered shape of the re-prompt template (per README exit criterion #3):

1. `test_audit_feedback_template_full_shape` — call `_render_audit_feedback(primary_original="<orig>", failure_reasons=["r1", "r2"], suggested_approach="try X", primary_context="<ctx>")`; assert string equality against the literal expected output (exact whitespace + section markers). This is the contract test for the cascade re-prompt — the template is part of the cascade's behavioural surface and must not drift silently.
2. `test_audit_feedback_template_empty_reasons` — passing `failure_reasons=[]` renders `"- (none)"` under the `Reasons:` header.
3. `test_audit_feedback_template_no_suggested_approach` — passing `suggested_approach=None` renders `Suggested approach: (none)`.
4. `test_audit_failure_revision_hint_byte_equal_to_expected_template` — construct `AuditFailure(failure_reasons=["r1", "r2"], suggested_approach="try X", primary_original="P", primary_context="C")`; assert `exc.revision_hint` is byte-equal to a hard-coded literal expected string (the same literal asserted in test #1). The `_render_audit_feedback` helper is module-private and not imported by tests — the test pins the exception's emitted hint, not the helper's return value, so the template ownership stays inside `AuditFailure`.
5. `test_audit_failure_is_retryable_semantic` — `assert issubclass(AuditFailure, RetryableSemantic)`; `assert classify(AuditFailure(...)) is RetryableSemantic` — the bucket inference works without a `classify()` edit.

### [tests/graph/test_audit_cascade.py](../../../tests/graph/test_audit_cascade.py) — new

Hermetic. Exercises the compiled cascade with **stub provider adapters** (the `_FakeLiteLLMAdapter` / `_FakeClaudeCodeAdapter` monkey-patch pattern from `tests/graph/test_tiered_node.py:104,172` — `monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", <fake>)` / `setattr(..., "ClaudeCodeSubprocess", <fake>)`); no real LLM call, no subprocess.

1. `test_cascade_pass_through` — auditor returns `AuditVerdict(passed=True)` on the first try. Assert: cascade exits via the verdict node (not the human_gate); `state['cascade_transcript']` contains exactly one author attempt + one auditor verdict; both `cascade_role` tags fired (`"author"` once, `"auditor"` once, `"verdict"` once); the parsed primary output is in state under the expected schema key.
2. `test_cascade_re_fires_with_audit_feedback_in_revision_hint` — auditor returns `AuditVerdict(passed=False, failure_reasons=["bad shape"], suggested_approach="try Y")` on the first try, `passed=True` on the second. Assert: primary fired twice; the second primary call's prompt input received `state['last_exception'].revision_hint` matching `_render_audit_feedback(...)` exactly (assert against the helper's output for the same args). `cascade_transcript['author_attempts']` has length 2; `cascade_transcript['auditor_verdicts']` has length 2.
3. `test_cascade_exhausts_retries_routes_to_strict_human_gate` — **pure-audit-failure-only scenario** (no shape failures interleaved — primary always returns shape-valid output, auditor always returns `passed=False`). With `RetryPolicy(max_semantic_attempts=2)`, assert: cascade reaches the human_gate after 2 primary attempts; the human_gate's prompt payload (read from `final["__interrupt__"][0].value`) carries the cascade transcript (`author_attempts` length 2, `auditor_verdicts` length 2); `strict_review=True` is set on the gate. Pinning the pure-audit scenario keeps the budget arithmetic unambiguous — the shared counter (§Counter-sharing contract) burns one slot per audit-failure, and exhaustion routes via the verdict-node's retrying_edge on `on_terminal` after `max_semantic_attempts`.
4. `test_cascade_validator_failure_routes_back_to_primary_not_auditor` — primary returns shape-invalid output; `validator_node` raises `RetryableSemantic` (not `AuditFailure`); cascade re-fires the primary without ever invoking the auditor. Assert: auditor adapter was called 0 times after 2 primary attempts (validator failed both); auditor only fires when shape passes. (Pins the cascade's "shape-fail short-circuits the auditor" contract.)
5. `test_cascade_returns_compiled_state_graph_composable_in_outer` — instantiate `audit_cascade_node(...)`; add it as a single node to a minimal outer `StateGraph(state_schema=...)`; compile; invoke. Pins the public surface contract — the cascade is a `CompiledStateGraph` that composes into any outer graph as a node.
6. `test_cascade_role_tags_stamped_on_state` — assert each sub-node stamps `state['cascade_role']` to the correct value (`"author"` / `"auditor"` / `"verdict"`) before returning. T04 will consume this; T02 only writes.

### KDR-003 guardrail — verify, don't extend

The tree-wide `tests/workflows/test_slice_refactor_e2e.py:test_kdr_003_no_anthropic_in_production_tree` already walks every `ai_workflows/` file; the new `audit_cascade.py` module is automatically covered. AC: that test still passes. No new grep test required.

## Acceptance Criteria

- [ ] `ai_workflows/primitives/retry.py` exports `AuditFailure` (subclass of `RetryableSemantic`); `__all__` includes it; `_render_audit_feedback` helper rendered template matches the spec's literal shape.
- [ ] `classify(AuditFailure(...)) is RetryableSemantic` — no edit to `classify()` required.
- [ ] `ai_workflows/graph/audit_cascade.py` exports `audit_cascade_node` factory and `AuditVerdict` pydantic model; factory returns a `CompiledStateGraph` composable into any outer `StateGraph`.
- [ ] Cascade sub-graph wires `primary → validator → auditor → verdict` as four distinct nodes; verdict node raises `AuditFailure` on `passed=False`; `RetryingEdge` routes the failure back to the primary on `on_semantic`.
- [ ] Re-prompt template byte-equal to the spec's literal shape (asserted in `test_audit_feedback_template_full_shape`).
- [ ] `cascade_transcript` state channel populated across attempts with `author_attempts` + `auditor_verdicts`; survives via LangGraph's checkpointer (KDR-009 — no new persistence table).
- [ ] `cascade_role` state channel stamped by each cascade sub-node (`"author"` / `"auditor"` / `"verdict"`). T02 only writes; T04 reads.
- [ ] Exhaustion (`max_semantic_attempts` reached) routes to a strict `HumanGate(strict_review=True)` whose prompt payload carries `author_attempts` + `auditor_verdicts`.
- [ ] Validator shape failure short-circuits the auditor (auditor never invoked when validator raises `RetryableSemantic`). Pinned by `test_cascade_validator_failure_routes_back_to_primary_not_auditor`.
- [ ] No `ai_workflows/workflows/` diff (wiring is T03). No `ai_workflows/mcp/` diff (MCP tool is T05). No `evals/` diff (fixture convention is T06). No `pricing.yaml` diff (auditor tiers' pricing rows already cover the cost shape per T01).
- [ ] `pyproject.toml` grows a fifth `[[tool.importlinter.contracts]]` block scoped to `ai_workflows.graph.audit_cascade`. `uv run lint-imports` reports `5 contracts kept`.
- [ ] KDR-003 guardrail tests pass (`test_kdr_003_no_anthropic_in_production_tree` and the file-scoped `test_no_anthropic_sdk_import_in_planner_or_claude_code_driver` both green — no extension required).
- [ ] `uv run pytest` + `uv run lint-imports` (5 contracts kept) + `uv run ruff check` all clean.
- [ ] CHANGELOG entry under `[Unreleased]` with files + ACs + KDR citations + packaging-scope notes.
- [ ] **Smoke test (CLAUDE.md non-inferential rule):** `tests/graph/test_audit_cascade.py::test_cascade_pass_through` is the wire-level smoke — it invokes the compiled cascade end-to-end through the same `tiered_node` + `validator_node` adapters production code uses (only the LLM dispatch is stubbed). Builder runs this test explicitly and reports the result.
- [ ] Status surfaces flipped together at close: (a) this spec's `**Status:**` line to `✅ Complete (YYYY-MM-DD).`; (b) milestone README task-order table row 02 status indicator; (c) milestone README §Exit-criteria bullets 2 + 3 + 4 (cascade primitive + RetryingEdge re-prompt + HumanGate escalation) ticked, plus bullet 11 (`5 contracts kept` — T02 lands the 5th contract) and bullet 12 (no `anthropic` SDK import — extended grep coverage via the existing tree-wide guard at `tests/workflows/test_slice_refactor_e2e.py:test_kdr_003_no_anthropic_in_production_tree`). There is no `tasks/README.md` for M12.

## Dependencies

- **T01 complete.** The `auditor-sonnet` and `auditor-opus` `TierConfig` entries must exist in the workflow tier registries before T02 lands; T02's compiled cascade resolves the auditor by tier name through those registries. (T01 ✅ Complete 2026-04-27 — dependency satisfied.)

## Out of scope (explicit)

- **No workflow integration.** `planner` / `slice_refactor` / `summarize_tiers` keep `audit_cascade_enabled` absent at T02. Wiring lands at T03.
- **No `TokenUsage.role` tag consumption.** T02 *writes* `state['cascade_role']`; T04 reads it into `TokenUsage.role`. T02 does not edit `CostTracker`.
- **No MCP `run_audit_cascade` tool.** The standalone surface lands at T05.
- **No SKILL.md edit.** Skill update lands at T05.
- **No eval fixture convention.** Author / auditor split fixture naming lands at T06.
- **No new tier.** T01 already shipped `auditor-sonnet` + `auditor-opus`; T02 consumes them. Haiku-as-primary is `nice_to_have.md` material (see milestone README §Propagation status).
- **No `classify()` taxonomy edit.** `AuditFailure` rides the existing `RetryableSemantic` bucket via subclassing.
- **No `RetryingEdge` behavioural edit.** The edge already routes `RetryableSemantic` to `on_semantic`. T02's only edit to `retrying_edge.py` is a docstring cross-reference (no code change).
- **No HumanGate edit.** T02 reuses `HumanGate(strict_review=True)` without source-code edit (the cascade-transcript prompt_fn is HumanGate's documented extension point, not a fork). The cascade-transcript shape is rendered by the audit-verdict node into the gate's prompt at compose time.
- **No Anthropic API.** KDR-003 preserved across all T02 deliverables. Hermetic grep enforces.
- **No Opus-repair tier.** ADR-0004 §Alternatives explicitly rejected the third-tier fixer; T02 honours that.

## Propagation status

Filled in at audit time. Anticipated forward-deferrals from T02:

- ADR-0004 §Decision item 1's stale `primitives/tiers.py` framing already deferred from T01 to M12 T07 close-out (M12-T01-ISS-02). T02 adds nothing to that propagation — the cascade's tier-resolution call site honours the workflow-scoped registry pattern T01 landed.
- ADR-0004 §Consequences line 54 (`No import-linter edit needed`) becomes stale at T02 close — the new fifth import-linter contract supersedes it. Surface for the M12 T07 docs sweep alongside the §Decision-item-1 amendment above (single ADR-0004 amendment commit covers both stale lines).
- If the audit cascades's first end-to-end test surfaces a coupling between `cascade_transcript` and the M11 gate-context projection that requires a schema edit on `mcp/schemas.py`, that lands at T05 (alongside the standalone MCP tool) — surface as a forward-deferral to T05's spec then.
- If the audit-feedback template proves too rigid under real-world auditor outputs (long failure-reason lists overflowing context, or markdown-flavoured `suggested_approach` interfering with the primary's prompt), log as a `nice_to_have.md` entry with trigger "first observed cascade re-fire that produces an empirically worse primary output than the original".

## Carry-over from prior milestones

- *None.* M9 T04's forward-deferral landed on M11 T01, not M12.

## Carry-over from task analysis

- [x] **TA-LOW-01 — Drop `(drafted 2026-04-27)` parenthetical from `**Status:**` line** (severity: LOW, source: task_analysis.md round 3)
      Spec line 3 reads `**Status:** 📝 Planned (drafted 2026-04-27).` while the M12 README task-table row 02 uses `📝 Planned` only. Cosmetic only — does not affect close-out flip.
      **Recommendation:** Optional drop of the `(drafted 2026-04-27)` parenthetical for uniformity with the README task-table row format.

- [x] **TA-LOW-02 — Replace `HumanGate verbatim` phrasing in §Out of scope** (severity: LOW, source: task_analysis.md round 3)
      §Out of scope says `T02 reuses HumanGate(strict_review=True) verbatim`. "Verbatim" is technically true (no source-code edit) but a pedant could read it as "no behavioural customization at all"; the cascade *does* supply a custom `prompt_fn` for the cascade-transcript renderer, which is `human_gate.py:52`'s documented extension point.
      **Recommendation:** Replace `reuses HumanGate(strict_review=True) verbatim` with `reuses HumanGate(strict_review=True) without source-code edit (the cascade-transcript prompt_fn is HumanGate's documented extension point, not a fork)`.

- [x] **TA-LOW-03 — Sketch test #5's outer-graph state schema** (severity: LOW, source: task_analysis.md round 3)
      Test #5 (`test_cascade_returns_compiled_state_graph_composable_in_outer`) says "instantiate `audit_cascade_node(...)`; add it as a single node to a minimal outer `StateGraph(state_schema=...)`; compile; invoke" — the outer state schema is unspecified. The four `<name>_*` channels are pinned in §State channels added by the cascade, but the test still needs `run_id`, `last_exception`, `_retry_counts`, `_non_retryable_failures`, `cascade_role`, `cascade_transcript` plus the four cascade-internal keys.
      **Recommendation:** Name the minimum outer-graph state schema fields the Builder needs: `run_id`, `last_exception`, `_retry_counts`, `_non_retryable_failures`, `cascade_role`, `cascade_transcript`, plus the four cascade-internal keys (`<name>_primary_output`, `<name>_primary_parsed`, `<name>_auditor_output`, `<name>_audit_verdict`). Or reference `tests/graph/test_tiered_node.py:_build_config` shape as the template.

- [x] **TA-LOW-04 — Sketch `_default_primary_original` helper body in §Internal node block** (severity: LOW, source: task_analysis.md round 3)
      §Internal node block references `_default_primary_original(state, primary_prompt_fn)` as the fallback when `cascade_context_fn` is None, with body described in prose only. Builder needs to know the exact join shape so test #2's byte-equal assertion against `exc.revision_hint` can construct the expected literal.
      **Recommendation:** Pin the body shape. Suggested: `system, messages = primary_prompt_fn(state); return (system or "") + "\n\n" + "\n".join(m.get("content", "") for m in messages)`. Or pin a less-opinionated shape (e.g. `repr((system, messages))`) and let test #2's byte-equal assertion drive whatever shape the Builder picks. Either way, the spec should not leave the join shape unwritten.
