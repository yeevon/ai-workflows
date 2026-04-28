"""AuditCascadeNode graph primitive (M12 Task 02 / amended M12 Task 08 — KDR-004,
KDR-006, KDR-009, KDR-011,
[architecture.md §4.2 / §8.2 / §9](../../design_docs/architecture.md)).

Composes ``TieredNode(primary) → ValidatorNode(shape) → TieredNode(auditor)
→ AuditVerdictNode`` into a compiled ``StateGraph`` that can be embedded as a
single node in any outer ``StateGraph``.  On auditor verdict ``passed=False`` the
verdict node raises :class:`AuditFailure` (a ``RetryableSemantic`` subclass per
KDR-006); :func:`retrying_edge` routes it back to the primary ``TieredNode``
which picks up the rendered revision template via
``state['last_exception'].revision_hint``.  After
``RetryPolicy.max_semantic_attempts`` exhaustion the cascade routes to a strict
:func:`human_gate` carrying the full cascade transcript (default path).

M12 Task 08 amendment: :func:`audit_cascade_node` gains a ``skip_terminal_gate``
keyword-only parameter (default ``False``, backward-compatible).  When ``True``
the cascade's terminal :func:`human_gate` node is omitted entirely from the
compiled sub-graph; exhaustion routes to ``END`` with
``state['last_exception']`` set to the terminal exception so the caller's outer
graph can handle escalation (e.g. M12 T03's slice_refactor parallel fan-out).

Relationship to sibling modules
-------------------------------
* ``graph/tiered_node.py`` (M2 Task 03) — the primary and auditor LLM nodes;
  both are wrapped with ``wrap_with_error_handler``.
* ``graph/validator_node.py`` (M2 Task 04) — the shape-validation node paired
  after the primary per KDR-004; wrapped with ``wrap_with_error_handler``.
* ``graph/retrying_edge.py`` (M2 Task 07) — the conditional-edge factory that
  routes :class:`AuditFailure` (a ``RetryableSemantic`` subclass) back to the
  primary via ``on_semantic`` and exhausted budgets to ``on_terminal``.
  ``graph/audit_cascade.py`` (M12 T02) emits :class:`AuditFailure` (a
  ``RetryableSemantic`` subclass) from the audit-verdict node when the auditor
  reports ``passed=False``. This edge routes it back to the primary
  ``tiered_node`` via the same ``on_semantic`` hop used for shape failures;
  the primary picks up the rendered audit-feedback template via
  ``state['last_exception'].revision_hint`` on re-entry.
* ``graph/error_handler.py`` (M2 Task 08) — ``wrap_with_error_handler`` converts
  raised bucket exceptions into the ``{last_exception, _retry_counts,
  _non_retryable_failures}`` state shape the retrying edge reads.
* ``graph/human_gate.py`` (M2 Task 05) — the strict HumanGate the cascade
  escalates to on retry exhaustion; the cascade-transcript prompt_fn is this
  gate's documented extension point (no source-code edit to human_gate.py).
* ``primitives/retry.py`` — :class:`AuditFailure` + :class:`RetryPolicy` live
  here; :class:`AuditFailure` is a ``RetryableSemantic`` subclass so the
  existing ``RetryingEdge`` routes it without taxonomy changes (KDR-006).
* ``workflows/`` — this module is graph-layer only; workflow integration
  lands via module-level ``_AUDIT_CASCADE_ENABLED`` constants in
  ``planner.py`` / ``slice_refactor.py`` per ADR-0009 / KDR-014 (M12 T03).
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field

from ai_workflows.graph.error_handler import _failure_state_update, wrap_with_error_handler
from ai_workflows.graph.human_gate import human_gate
from ai_workflows.graph.retrying_edge import retrying_edge
from ai_workflows.graph.tiered_node import tiered_node
from ai_workflows.graph.validator_node import validator_node
from ai_workflows.primitives.retry import (
    AuditFailure,
    NonRetryable,
    RetryableSemantic,
    RetryableTransient,
    RetryPolicy,
)

__all__ = ["AuditVerdict", "_strip_code_fence", "audit_cascade_node"]

GraphState = Mapping[str, Any]  # mirrors graph/tiered_node.py:111


def _strip_code_fence(raw_text: str) -> str:
    """Strip a leading/trailing markdown code fence if present.

    Real Claude auditor responses sometimes wrap JSON in a markdown code fence
    (e.g. ````` ```json\\n{...}\\n``` `````) despite system-prompt instructions to
    emit raw JSON only.  This helper tolerates both fenced and unfenced output.

    Used by both :func:`_audit_verdict_node` (cascade primitive) and the
    standalone ``run_audit_cascade`` MCP tool's parse step so both surfaces
    share the same fence-strip behaviour.  If no fence is detected, the
    input string is returned stripped but otherwise unchanged.

    M12 Task 05 — fix for HIGH-01: AIW_E2E smoke caught real ``auditor-sonnet``
    wrapping JSON in a markdown fence; this helper is the shared parse-side fix.
    """
    text = raw_text.strip()
    if text.startswith("```"):
        # Strip the leading fence line (handles ```json, ```, ```\\n, etc.)
        lines = text.split("\n", 1)
        text = lines[1] if len(lines) > 1 else ""
        # Strip the trailing fence
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


class AuditVerdict(BaseModel):
    """Auditor's structured response for a single primary attempt.

    Produced by :func:`_audit_verdict_node`; appended to
    ``state['cascade_transcript']['auditor_verdicts']`` on each cascade cycle.
    When ``passed=False`` the verdict node raises :class:`AuditFailure` carrying
    the ``failure_reasons`` and ``suggested_approach`` payloads.
    """

    passed: bool
    failure_reasons: list[str] = Field(default_factory=list)
    suggested_approach: str | None = None


class _CascadeState(TypedDict, total=False):
    """State schema for the cascade sub-graph.

    Includes all channels the spec pins in §State channels added by the
    cascade plus the standard retry-error channels required by
    ``wrap_with_error_handler`` + ``retrying_edge``.  The prefix placeholders
    (``audit_cascade_*``) are for the default ``name="audit_cascade"``; callers
    that pass a custom ``name`` will use different concrete key names but the
    same schema shape.

    Pass-through channels
    ----------------------
    LangGraph filters parent-graph state to only the keys declared here when
    invoking the cascade as an embedded sub-graph node.  Any field the
    ``primary_prompt_fn`` / ``auditor_prompt_fn`` needs to read from the
    parent state MUST be declared in this TypedDict, or it will be silently
    dropped at the sub-graph boundary.

    * ``slice`` — pass-through for the per-Send :class:`SliceSpec` payload
      that the ``slice_refactor`` workflow's ``_slice_worker_prompt`` reads.
      Typed ``Any`` (no coupling to ``SliceSpec``) — the cascade primitive
      does not use or modify this field; it is strictly a transparent carrier
      for embedding workflows whose prompt_fn reads per-branch context.
      Added M12 T03 (cycle 2): discovered when end-to-end runtime test for
      AC-10 / AC-11 showed ``state["slice"]`` missing inside the cascade.
    """

    # Standard LangGraph / error-handler channels (KDR-006 / KDR-009)
    run_id: str
    last_exception: Any
    _retry_counts: dict[str, int]
    _non_retryable_failures: int

    # Cascade-specific channels (§State channels added by the cascade)
    cascade_role: str  # Literal["author", "auditor", "verdict"]
    cascade_transcript: dict[str, list]

    # Primary node channels (name-prefixed)
    audit_cascade_primary_output: str
    audit_cascade_primary_parsed: Any
    audit_cascade_primary_output_revision_hint: Any

    # Auditor node channels (name-prefixed)
    audit_cascade_auditor_output: str
    audit_cascade_auditor_output_revision_hint: Any

    # Verdict channel (name-prefixed)
    audit_cascade_audit_verdict: Any

    # Human-gate response channel (name-prefixed)
    audit_cascade_audit_exhausted_response: str

    # Pass-through for embedding workflows (see class docstring).
    slice: Any


def audit_cascade_node(
    *,
    primary_tier: str,
    primary_prompt_fn: Callable[[GraphState], tuple[str | None, list[dict]]],
    primary_output_schema: type[BaseModel],
    auditor_tier: str,
    policy: RetryPolicy,
    auditor_prompt_fn: Callable[[GraphState], tuple[str | None, list[dict]]] | None = None,
    cascade_context_fn: Callable[[GraphState], tuple[str, str]] | None = None,
    # NEW (M12 T08): if True, exhaustion routes to END with the terminal exception
    # in state['last_exception'] instead of triggering the cascade's internal
    # human_gate.  Default False preserves T02 behaviour (backward-compatible).
    skip_terminal_gate: bool = False,
    name: str = "audit_cascade",
) -> CompiledStateGraph:
    """Compile a cascade sub-graph: primary → validator → auditor → verdict.

    Returns a :class:`CompiledStateGraph` that can be added as a single node to
    any outer ``StateGraph`` via ``outer.add_node(name, audit_cascade_node(...))``.
    The sub-graph reuses :func:`tiered_node` + :func:`validator_node` for the
    primary half and :func:`tiered_node` for the auditor half — no LLM dispatch
    logic is duplicated.

    Parameters
    ----------
    primary_tier:
        Tier name for the author/generative call (e.g. ``"planner-explorer"``,
        ``"slice-worker"``).
    primary_prompt_fn:
        Same signature as :func:`tiered_node`'s ``prompt_fn`` — accepts the graph
        state and returns ``(system, messages)``. Called twice per cascade
        cycle: once by the primary :func:`tiered_node`, once by the verdict node
        when constructing ``AuditFailure(primary_original=...)`` (unless
        ``cascade_context_fn`` is supplied — see below).
    primary_output_schema:
        Pydantic model the validator parses against. The parsed instance is
        written to state under ``f"{name}_primary_parsed"``.
    auditor_tier:
        Tier name for the audit call (``"auditor-sonnet"`` or ``"auditor-opus"``
        from T01).
    policy:
        Retry budget for both the validator-shape-failure hop and the
        audit-failure hop. Production sites pass a workflow-level constant
        (see ``planner.py:528,556`` for the ``PLANNER_RETRY_POLICY`` pattern).
    auditor_prompt_fn:
        Optional. Same signature as ``primary_prompt_fn``. Defaults to a
        built-in renderer that emits: ``Audit the following <schema-name>
        for <primary_tier>. Return an AuditVerdict JSON. <primary_output
        verbatim>``. Reads ``state[f"{name}_primary_parsed"]`` for the
        verbatim payload.
    cascade_context_fn:
        Optional. Returns ``(primary_original, primary_context)`` for the
        :class:`AuditFailure` constructor on each verdict-failure raise. Defaults
        to re-calling ``primary_prompt_fn(state)`` and using its rendered
        system+messages for ``primary_original``; ``primary_context`` defaults
        to the empty string. Override when the workflow has additional context
        state (e.g. multi-turn slice-worker history) that should be appended
        after the audit-feedback block.
    skip_terminal_gate:
        When ``False`` (default), the cascade's verdict-exhaustion path routes to
        a strict :func:`human_gate` (KDR-011's standard escalation). The gate
        calls ``interrupt(payload)`` and pauses the parent graph for operator
        arbitration via the cascade transcript. **This is the right shape when
        the cascade is the workflow's terminal escalation surface** (e.g. planner
        workflow's explorer cascade — single graph, single operator interrupt on
        exhaustion).

        When ``True``, the cascade's verdict-exhaustion path instead routes to
        ``END`` with ``state['last_exception']`` set to the terminal exception
        (an :class:`AuditFailure` for verdict-exhaustion paths, or a
        :class:`NonRetryable` for double-failure or NonRetryable paths). The
        cascade's :func:`human_gate` node is **not added** to the compiled
        sub-graph at all — the caller's outer graph is responsible for handling
        the exhausted state, typically by inspecting ``state['last_exception']``
        after the cascade returns and folding the auditor's verdict into a
        workflow-specific terminal shape.

        **Use case:** parallel fan-out workflows where the cascade lives inside a
        per-branch sub-graph (e.g. M12 T03's slice_refactor integration). The
        cascade's normal ``interrupt()`` semantics would trigger N parallel
        operator interrupts, one per cascade-exhausted branch — almost always the
        wrong UX. With ``skip_terminal_gate=True``, the per-branch cascade
        exhaustion stays branch-local, the branch's own terminal step folds it
        into the workflow's existing per-branch failure aggregation (e.g.
        ``SliceFailure`` row), and the parent graph aggregates as usual.

        **Backward-compatibility:** ``False`` default preserves T02 behaviour
        exactly. No SEMVER concern.
    name:
        Sub-graph node-name prefix. Defaults to ``"audit_cascade"``; override
        when composing more than one cascade in the same outer graph to keep
        node names disjoint.

    Behaviour
    ---------
    On auditor verdict ``passed=False``, the audit-verdict step raises
    ``AuditFailure(failure_reasons=..., suggested_approach=...,
    primary_original=<rendered primary prompt>,
    primary_context=<state-derived primary context>)``. :func:`retrying_edge`
    routes the failure back to the primary :func:`tiered_node`; the primary
    picks up the rendered revision_hint on re-entry via
    ``state['last_exception'].revision_hint``.

    On ``RetryPolicy.max_semantic_attempts`` exhaustion, the validator's
    in-validator escalation (M6 T07 pattern) converts the final
    ``AuditFailure`` to ``NonRetryable``, and :func:`retrying_edge` routes to
    the cascade's terminal :func:`human_gate`. The HumanGate carries the
    cascade transcript (``author_attempts`` + ``auditor_verdicts``) in its
    state channel so the operator can arbitrate manually.

    Transcript-accumulation design note
    ------------------------------------
    :func:`wrap_with_error_handler` converts raised exceptions into retry-state
    dicts (``{last_exception, _retry_counts, _non_retryable_failures}``) and
    discards any prior state writes in the raising node.  The cascade-transcript
    must therefore accumulate via the *exception instance* on failure cycles:
    :class:`AuditFailure` carries a ``cascade_transcript`` attribute holding the
    updated transcript for that cycle; the gate's prompt_fn reads it from
    ``state['last_exception']`` when ``state['cascade_transcript']`` is absent
    or stale.  On passing cycles the verdict node writes
    ``cascade_transcript`` to state in the normal return dict.
    """
    resolved_auditor_prompt_fn = auditor_prompt_fn or _default_auditor_prompt_fn(
        name=name,
        primary_tier=primary_tier,
        primary_output_schema=primary_output_schema,
    )

    # ------------------------------------------------------------------
    # Node 1: primary — TieredNode + role stamp + error_handler wrap.
    # node_name=f"{name}_primary" so _retry_counts keyed consistently.
    # ------------------------------------------------------------------
    _primary_inner = tiered_node(
        tier=primary_tier,
        prompt_fn=primary_prompt_fn,
        output_schema=primary_output_schema,
        node_name=f"{name}_primary",
        role="author",  # M12 T04: factory-time role binding (Option 4, locked 2026-04-27)
    )
    _primary_with_role = _stamp_role_on_success(_primary_inner, role="author")
    primary_node = wrap_with_error_handler(
        _primary_with_role,
        node_name=f"{name}_primary",
    )

    # ------------------------------------------------------------------
    # Node 2: validator — KDR-004 shape pairing.
    # node_name=f"{name}_primary" so the shared counter is bumped under
    # the primary's key (counter-sharing contract per spec §Counter-sharing
    # contract: validator + verdict + primary all bump the SAME key).
    # ------------------------------------------------------------------
    _validator_inner = validator_node(
        schema=primary_output_schema,
        input_key=f"{name}_primary_output",
        output_key=f"{name}_primary_parsed",
        node_name=f"{name}_primary",
        max_attempts=policy.max_semantic_attempts,
    )
    validator_wrapped = wrap_with_error_handler(
        _validator_inner,
        node_name=f"{name}_primary",
    )

    # ------------------------------------------------------------------
    # Node 3: auditor — TieredNode + role stamp + error_handler wrap.
    # node_name=f"{name}_auditor" (separate counter; auditor failures
    # don't burn the primary's semantic budget).
    # ------------------------------------------------------------------
    _auditor_inner = tiered_node(
        tier=auditor_tier,
        prompt_fn=resolved_auditor_prompt_fn,
        output_schema=AuditVerdict,
        node_name=f"{name}_auditor",
        role="auditor",  # M12 T04: factory-time role binding (Option 4, locked 2026-04-27)
    )
    _auditor_with_role = _stamp_role_on_success(_auditor_inner, role="auditor")
    auditor_node = wrap_with_error_handler(
        _auditor_with_role,
        node_name=f"{name}_auditor",
    )

    # ------------------------------------------------------------------
    # Node 4: verdict — module-private factory.
    # node_name=f"{name}_primary" so the shared counter is bumped when
    # AuditFailure is raised and caught by wrap_with_error_handler
    # (counter-sharing contract: validator + verdict + primary share the
    # same semantic budget key).
    # ------------------------------------------------------------------
    _verdict_inner = _audit_verdict_node(
        name=name,
        primary_prompt_fn=primary_prompt_fn,
        cascade_context_fn=cascade_context_fn,
    )
    # Custom verdict wrapper: functionally equivalent to wrap_with_error_handler
    # but also writes cascade_transcript to state on AuditFailure.  This ensures
    # the transcript accumulates across all cycles even when the verdict raises,
    # since wrap_with_error_handler discards non-exception state writes on raise
    # (see §Transcript-accumulation design note in module docstring).
    verdict_node = _wrap_verdict_with_transcript(
        _verdict_inner,
        node_name=f"{name}_primary",
    )

    # ------------------------------------------------------------------
    # Human gate for exhaustion / terminal escalation.
    # Only constructed when skip_terminal_gate=False (the default).
    # When skip_terminal_gate=True the gate node is omitted from the
    # compiled sub-graph entirely; exhaustion routes to END instead.
    # ------------------------------------------------------------------
    if not skip_terminal_gate:
        gate = human_gate(
            gate_id=f"{name}_audit_exhausted",
            prompt_fn=_cascade_gate_prompt_fn(name=name),
            strict_review=True,
        )
    else:
        gate = None

    # ------------------------------------------------------------------
    # Edge functions
    # ------------------------------------------------------------------

    # After primary: on_terminal=validator serves as the success path.
    # Transient/semantic failures self-loop to primary.
    decide_after_primary = retrying_edge(
        on_transient=f"{name}_primary",
        on_semantic=f"{name}_primary",
        on_terminal=f"{name}_validator",
        policy=policy,
    )

    # After validator: on_terminal=auditor serves as the success path.
    # Shape failures (RetryableSemantic) loop back to primary.
    # In-validator escalation raises NonRetryable → _decide_after_validator
    # intercepts and routes to human_gate instead of forward to auditor.
    _decide_after_validator_base = retrying_edge(
        on_transient=f"{name}_primary",
        on_semantic=f"{name}_primary",
        on_terminal=f"{name}_auditor",
        policy=policy,
    )

    def _decide_after_validator(state: GraphState) -> str:
        """Route after validator.

        In-validator escalation (M6 T07) converts exhausted shape-failures
        to ``NonRetryable``.  The stock ``retrying_edge`` would forward that
        to ``on_terminal=auditor``, which would audit a shape-invalid primary
        output — incorrect behaviour.  This wrapper intercepts ``NonRetryable``
        and routes to ``END`` (when ``skip_terminal_gate=True``) or to the
        cascade's ``human_gate`` (default path).
        """
        exc = state.get("last_exception")
        if isinstance(exc, NonRetryable):
            return END if skip_terminal_gate else f"{name}_human_gate"
        return _decide_after_validator_base(state)

    # After auditor: on_terminal=verdict serves as the success path.
    # Transient/semantic auditor failures self-loop to auditor.
    decide_after_auditor = retrying_edge(
        on_transient=f"{name}_auditor",
        on_semantic=f"{name}_auditor",
        on_terminal=f"{name}_verdict",
        policy=policy,
    )

    # After verdict: success → END (cascade completes); AuditFailure →
    # back to primary; exhausted semantic budget → human_gate.
    # The stock retrying_edge cannot distinguish success from exhaustion
    # (both map to on_terminal), so we use a custom edge function.
    def _decide_after_verdict(state: GraphState) -> str:
        """Custom routing after verdict node.

        Routes:
        * ``last_exception is None`` (success) → END
        * ``RetryableTransient`` under budget → primary
        * ``RetryableSemantic`` (AuditFailure) under budget → primary
        * Any exception at/over budget, or ``NonRetryable`` → human_gate
          (default path) or END (when ``skip_terminal_gate=True``, with
          ``state['last_exception']`` carrying the terminal exception for
          the caller to inspect)
        """
        _terminal = END if skip_terminal_gate else f"{name}_human_gate"

        failures = state.get("_non_retryable_failures") or 0
        if failures >= 2:
            return _terminal

        exc = state.get("last_exception")

        if exc is None:
            return END

        retry_counts = state.get("_retry_counts") or {}

        if isinstance(exc, RetryableTransient):
            if retry_counts.get(f"{name}_primary", 0) >= policy.max_transient_attempts:
                return _terminal
            return f"{name}_primary"

        if isinstance(exc, RetryableSemantic):
            # AuditFailure is a RetryableSemantic subclass.
            if retry_counts.get(f"{name}_primary", 0) >= policy.max_semantic_attempts:
                return _terminal
            return f"{name}_primary"

        # NonRetryable or unknown → terminal
        return _terminal

    # ------------------------------------------------------------------
    # Compile the sub-graph.
    # Build a dynamic TypedDict whose keys include the ``name``-prefixed
    # channel names so LangGraph can accumulate state across all nodes
    # (with StateGraph(dict) only the last node's writes survive in the
    # final state returned to the outer graph; TypedDict accumulates
    # across all nodes). The TypedDict ``_CascadeState`` documents the
    # expected channels for the default ``name="audit_cascade"`` case;
    # this dynamic variant uses the caller's ``name`` prefix.
    # ------------------------------------------------------------------
    _DynamicState = TypedDict(  # type: ignore[misc]
        f"_CascadeState_{name}",
        {
            # Standard error-handler / retry channels
            "run_id": str,
            "last_exception": Any,
            "_retry_counts": dict,
            "_non_retryable_failures": int,
            # Cascade-specific channels
            "cascade_role": str,
            "cascade_transcript": dict,
            # Primary node channels
            f"{name}_primary_output": str,
            f"{name}_primary_parsed": Any,
            f"{name}_primary_output_revision_hint": Any,
            # Auditor node channels
            f"{name}_auditor_output": str,
            f"{name}_auditor_output_revision_hint": Any,
            # Verdict channel
            f"{name}_audit_verdict": Any,
            # Gate channel
            f"{name}_audit_exhausted_response": str,
            # Pass-through for embedding workflows — see _CascadeState docstring.
            # Declared Any so no coupling to the SliceSpec type from slice_refactor.
            # The cascade primitive does not read or write this field; it is a
            # transparent carrier for per-branch context that prompt_fns need
            # (e.g. _slice_worker_prompt reads state["slice"] per-branch).
            # Added M12 T03 cycle 2: discovered when runtime test for AC-10/11
            # showed LangGraph filtering slice from SliceBranchState → cascade
            # state because the key was absent from _DynamicState.
            "slice": Any,
        },
        total=False,
    )
    g: StateGraph = StateGraph(_DynamicState)

    g.add_node(f"{name}_primary", primary_node)
    g.add_node(f"{name}_validator", validator_wrapped)
    g.add_node(f"{name}_auditor", auditor_node)
    g.add_node(f"{name}_verdict", verdict_node)
    # Gate node is omitted entirely when skip_terminal_gate=True (M12 T08).
    # LangGraph compile-time validates every destination-list member is a
    # registered node; omitting the gate node from add_node and from all
    # destination lists keeps the compile clean.
    if not skip_terminal_gate:
        g.add_node(f"{name}_human_gate", gate)

    g.add_edge(START, f"{name}_primary")

    g.add_conditional_edges(
        f"{name}_primary",
        decide_after_primary,
        [f"{name}_primary", f"{name}_validator"],
    )
    if skip_terminal_gate:
        # Without the gate node in the graph, NonRetryable exits to END.
        g.add_conditional_edges(
            f"{name}_validator",
            _decide_after_validator,
            [f"{name}_primary", f"{name}_auditor", END],
        )
    else:
        g.add_conditional_edges(
            f"{name}_validator",
            _decide_after_validator,
            [f"{name}_primary", f"{name}_auditor", f"{name}_human_gate"],
        )
    g.add_conditional_edges(
        f"{name}_auditor",
        decide_after_auditor,
        [f"{name}_auditor", f"{name}_verdict"],
    )
    if skip_terminal_gate:
        # Without the gate node, exhaustion exits to END instead of human_gate.
        g.add_conditional_edges(
            f"{name}_verdict",
            _decide_after_verdict,
            [f"{name}_primary", END],
        )
    else:
        g.add_conditional_edges(
            f"{name}_verdict",
            _decide_after_verdict,
            [f"{name}_primary", f"{name}_human_gate", END],
        )
    if not skip_terminal_gate:
        g.add_edge(f"{name}_human_gate", END)

    return g.compile()


# ---------------------------------------------------------------------------
# Module-private helpers
# ---------------------------------------------------------------------------


def _wrap_verdict_with_transcript(
    node: Callable[..., Any],
    *,
    node_name: str,
) -> Callable[..., Any]:
    """Custom verdict-node wrapper that persists cascade_transcript on failure.

    Functionally equivalent to :func:`wrap_with_error_handler` for all paths
    except :class:`AuditFailure`: on that path, merges ``cascade_transcript``
    from the exception's attached attribute into the failure-state dict so that
    transcript accumulation survives across retry cycles.

    :func:`wrap_with_error_handler` discards non-exception state writes on any
    bucket raise, so the verdict node's ``cascade_transcript`` update would be
    lost every time the auditor fails.  This wrapper preserves it by reading
    ``exc.cascade_transcript`` (attached by ``_audit_verdict_node`` before
    raising) and including it in the returned state dict alongside the standard
    ``last_exception`` / ``_retry_counts`` / ``_non_retryable_failures`` keys.
    """
    async def _wrapped(
        state: GraphState, config: RunnableConfig = None
    ) -> dict[str, Any]:
        try:
            return await node(state)
        except AuditFailure as exc:
            base = _failure_state_update(state, exc, node_name=node_name)
            transcript = getattr(exc, "cascade_transcript", None)
            if transcript:
                base["cascade_transcript"] = transcript
            return base
        except (RetryableTransient, RetryableSemantic, NonRetryable) as exc:
            return _failure_state_update(state, exc, node_name=node_name)

    return _wrapped


def _stamp_role_on_success(
    node: Callable[..., Any],
    *,
    role: str,
) -> Callable[..., Any]:
    """Wrap ``node`` to merge ``cascade_role=<role>`` into successful results.

    The spec requires each cascade sub-node to stamp ``state['cascade_role']``
    on every successful invocation so T04's telemetry can attribute
    ``TokenUsage`` records to the correct cascade role.  Since :func:`tiered_node`
    returns a fixed ``{f"{node_name}_output": text, "last_exception": None}``
    shape, the role stamp must be injected by a thin wrapper that merges the
    extra key into the returned dict on the success path only (identified by
    ``result["last_exception"] is None``).  On the failure path
    ``wrap_with_error_handler`` has already caught the exception and returned
    the retry-state dict — this wrapper never sees the exception.

    Wraps both ``(state)`` and ``(state, config)`` node shapes — the inner
    node's signature is inspected at factory time so LangGraph sees the
    correct arity.
    """
    try:
        sig = inspect.signature(node)
        positional = [
            p
            for p in sig.parameters.values()
            if p.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        accepts_config = len(positional) >= 2
    except (TypeError, ValueError):
        accepts_config = True  # default to the safer two-arg form

    if accepts_config:

        async def _wrapped_with_config(
            state: GraphState, config: RunnableConfig = None
        ) -> dict[str, Any]:
            result = await node(state, config)
            if isinstance(result, dict) and result.get("last_exception") is None:
                return {**result, "cascade_role": role}
            return result

        return _wrapped_with_config

    else:

        async def _wrapped_state_only(state: GraphState) -> dict[str, Any]:
            result = await node(state)
            if isinstance(result, dict) and result.get("last_exception") is None:
                return {**result, "cascade_role": role}
            return result

        return _wrapped_state_only


def _default_auditor_prompt_fn(
    *,
    name: str,
    primary_tier: str,
    primary_output_schema: type[BaseModel],
) -> Callable[[GraphState], tuple[str | None, list[dict]]]:
    """Build the default auditor prompt_fn.

    Emits: ``Audit the following <schema-name> for <primary_tier>. Return an
    AuditVerdict JSON. <primary_output verbatim>``.  Reads
    ``state[f"{name}_primary_parsed"]`` for the verbatim payload.
    """
    schema_name = primary_output_schema.__name__

    def _prompt(state: GraphState) -> tuple[str | None, list[dict]]:
        parsed = state.get(f"{name}_primary_parsed")
        if parsed is None:
            payload_str = "<no parsed output>"
        elif isinstance(parsed, BaseModel):
            payload_str = parsed.model_dump_json(indent=2)
        else:
            payload_str = str(parsed)

        system = (
            "You are a strict auditor. Return ONLY valid JSON matching the "
            "AuditVerdict schema: "
            '{"passed": bool, "failure_reasons": [str, ...], "suggested_approach": str | null}.'
        )
        content = (
            f"Audit the following {schema_name} output for tier '{primary_tier}'.\n\n"
            f"{payload_str}\n\n"
            f"Return an AuditVerdict JSON."
        )
        return (system, [{"role": "user", "content": content}])

    return _prompt


def _default_primary_original(
    state: GraphState,
    primary_prompt_fn: Callable[[GraphState], tuple[str | None, list[dict]]],
) -> str:
    """Reconstruct a rendered primary-prompt string from the prompt_fn + current state.

    Used by :func:`_audit_verdict_node` when ``cascade_context_fn`` is None.
    Joins the ``(system, messages)`` tuple into a single string:

        ``(system or "") + "\\n\\n" + "\\n".join(m.get("content", "") for m in messages)``

    Body shape pinned here per TA-LOW-04 carry-over so test #2's byte-equal
    assertion can construct the expected literal independently of the verdict node.
    """
    system, messages = primary_prompt_fn(state)
    return (system or "") + "\n\n" + "\n".join(m.get("content", "") for m in messages)


def _audit_verdict_node(
    *,
    name: str,
    primary_prompt_fn: Callable[[GraphState], tuple[str | None, list[dict]]],
    cascade_context_fn: Callable[[GraphState], tuple[str, str]] | None,
) -> Callable[[GraphState], Any]:
    """Module-private factory: parse auditor output → AuditVerdict; raise AuditFailure on fail.

    Reads:
      ``state[f"{name}_auditor_output"]`` — raw text from the auditor tiered_node
      ``state[f"{name}_primary_output"]`` — raw primary text (for transcript)

    Writes (success path):
      ``state[f"{name}_audit_verdict"]`` — parsed AuditVerdict instance
      ``state["cascade_transcript"]`` — updated transcript dict
      ``state["cascade_role"]`` — set to ``"verdict"``
      ``state["last_exception"]`` — set to ``None``

    Raises (failure path):
      :class:`AuditFailure` (``RetryableSemantic`` subclass) when
      ``verdict.passed`` is False. The exception carries a ``cascade_transcript``
      attribute with the updated transcript for that cycle so the HumanGate
      prompt_fn can read it from ``state['last_exception']`` when the transcript
      has not yet been written to state (i.e. on all-failure runs where the
      cascade never passes).

    Parse failure (unparseable auditor output):
      Raises :class:`NonRetryable` so the operator is notified rather than the
      cascade silently passing or looping on a bad auditor output.
    """

    async def _node(state: GraphState) -> dict[str, Any]:
        # Parse the auditor's raw output as AuditVerdict.
        # _strip_code_fence tolerates markdown-fenced JSON (e.g. ```json…```)
        # that real Claude CLI responses sometimes emit despite system-prompt
        # instructions to return raw JSON only (M12 T05 HIGH-01 fix).
        auditor_raw: str = state.get(f"{name}_auditor_output", "") or ""
        try:
            verdict = AuditVerdict.model_validate_json(_strip_code_fence(auditor_raw))
        except Exception as parse_exc:  # noqa: BLE001
            raise NonRetryable(
                f"Cascade '{name}': auditor produced unparseable output — "
                f"expected AuditVerdict JSON, got: {auditor_raw[:200]!r}"
            ) from parse_exc

        # Build the accumulated transcript.
        # On failure cycles, wrap_with_error_handler discards non-exception
        # return values so transcript writes from earlier cycles are lost.
        # The verdict node therefore reads the prior transcript from two sources:
        # 1. state['cascade_transcript'] — written on previous passing cycles
        # 2. state['last_exception'].cascade_transcript — written on the most
        #    recent failing cycle (attached to the AuditFailure before raising)
        # The last_exception source takes priority when state['cascade_transcript']
        # is absent or less complete (all-failure runs never write to state).
        prior_transcript: dict[str, list] = dict(state.get("cascade_transcript") or {})
        exc_in_state = state.get("last_exception")
        has_exc_transcript = hasattr(exc_in_state, "cascade_transcript")
        if not prior_transcript.get("author_attempts") and has_exc_transcript:
            exc_transcript = getattr(exc_in_state, "cascade_transcript", None)
            if exc_transcript:
                prior_transcript = dict(exc_transcript)
        author_attempts: list[str] = list(prior_transcript.get("author_attempts") or [])
        auditor_verdicts: list = list(prior_transcript.get("auditor_verdicts") or [])

        primary_raw: str = state.get(f"{name}_primary_output", "") or ""
        author_attempts.append(primary_raw)
        auditor_verdicts.append(verdict)

        new_transcript: dict[str, list] = {
            "author_attempts": author_attempts,
            "auditor_verdicts": auditor_verdicts,
        }

        if not verdict.passed:
            if cascade_context_fn is not None:
                primary_original, primary_context = cascade_context_fn(state)
            else:
                primary_original = _default_primary_original(state, primary_prompt_fn)
                primary_context = ""

            exc = AuditFailure(
                failure_reasons=verdict.failure_reasons,
                suggested_approach=verdict.suggested_approach,
                primary_original=primary_original,
                primary_context=primary_context,
            )
            # Attach the transcript to the exception so the gate prompt_fn
            # can read it even when state['cascade_transcript'] is absent.
            exc.cascade_transcript = new_transcript  # type: ignore[attr-defined]
            raise exc

        # Success path: write the full transcript + verdict to state.
        return {
            f"{name}_audit_verdict": verdict,
            "cascade_transcript": new_transcript,
            "cascade_role": "verdict",
            "last_exception": None,
        }

    return _node


def _cascade_gate_prompt_fn(*, name: str) -> Callable[[GraphState], str]:
    """Build the HumanGate prompt_fn for the cascade's exhaustion gate.

    Renders the full cascade transcript (``author_attempts`` + ``auditor_verdicts``)
    so the operator can arbitrate manually.  On all-failure runs the transcript
    lives on ``state['last_exception'].cascade_transcript`` (attached by the
    verdict node before raising); on mixed-pass runs it lives in
    ``state['cascade_transcript']``.  This prompt_fn checks both sources so
    the operator always sees the full history.
    """

    def _prompt(state: GraphState) -> str:
        # Primary source: written by verdict node on success cycles.
        transcript = state.get("cascade_transcript") or {}

        # Fallback: transcript attached to the last AuditFailure exception.
        exc = state.get("last_exception")
        if (not transcript.get("author_attempts")) and hasattr(exc, "cascade_transcript"):
            transcript = exc.cascade_transcript or transcript

        author_attempts: list[str] = transcript.get("author_attempts") or []
        auditor_verdicts: list = transcript.get("auditor_verdicts") or []

        lines = [
            f"Cascade '{name}' exhausted retry budget. Manual review required.",
            f"\nAttempts recorded: {len(author_attempts)}",
        ]
        for i, (attempt, av) in enumerate(zip(author_attempts, auditor_verdicts, strict=False), 1):
            lines.append(f"\n--- Attempt {i} ---")
            lines.append(f"Primary output:\n{attempt}")
            if isinstance(av, AuditVerdict):
                lines.append(f"Verdict: passed={av.passed}")
                for r in av.failure_reasons:
                    lines.append(f"  - {r}")
                if av.suggested_approach:
                    lines.append(f"Suggested approach: {av.suggested_approach}")
            else:
                lines.append(f"Verdict: {av!r}")

        return "\n".join(lines)

    return _prompt
