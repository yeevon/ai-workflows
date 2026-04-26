"""Spec → ``StateGraph`` compiler (M19 Task 02).

Walks a :class:`~ai_workflows.workflows.spec.WorkflowSpec` and synthesises
the LangGraph ``StateGraph`` the framework hands to dispatch.  Owns every
piece of LangGraph wiring previously asked of consumers:

* **State-class derivation** — ``input_schema ⊕ output_schema`` (output wins
  on collision); framework-internal keys appended (``run_id``,
  ``_mid_run_*``).
* **START/END wiring** — ``START → step_0.entry`` then
  ``step_n.exit → step_{n+1}.entry`` then ``step_{N-1}.exit → END``.
* **``initial_state`` hook synthesis** — satisfies the existing
  :func:`~ai_workflows.workflows._dispatch._build_initial_state` resolution
  order (M6 T01 convention).
* **``FINAL_STATE_KEY`` resolution** — first field of ``output_schema``; empty
  schema raises at registration time.
* **Validator pairing on every** ``LLMStep`` — KDR-004 enforced by
  construction.

Relationship to other modules
------------------------------
* :mod:`ai_workflows.workflows.spec` (M19 T01) — the data-model layer this
  module compiles.  ``_compiler.py`` may import ``spec.py`` freely (both live
  in the workflows layer); the reverse is forbidden at runtime (``spec.py``
  guards the import under ``TYPE_CHECKING`` so it stays graph-free).
* :mod:`ai_workflows.graph.tiered_node` — ``LLMStep.compile()`` wraps
  :func:`~ai_workflows.graph.tiered_node.tiered_node`.
* :mod:`ai_workflows.graph.validator_node` — paired with every ``LLMStep``
  (KDR-004 by construction).
* :mod:`ai_workflows.graph.human_gate` — compiled from ``GateStep``.
* :mod:`ai_workflows.graph.retrying_edge` — plumbed from
  ``LLMStep(retry=RetryPolicy(...))`` (KDR-006; ``max_semantic_attempts``
  field naming per locked Q1/TA-LOW-07).
* :mod:`ai_workflows.graph.error_handler` — ``wrap_with_error_handler`` wraps
  every LLM call-node so bucket exceptions become state writes that
  :func:`retrying_edge` can route on.
* :mod:`ai_workflows.workflows._dispatch` — calls
  ``builder().compile(checkpointer=...)`` at line 554; the synthesised
  ``StateGraph`` is a standard LangGraph artefact (KDR-009 preserved).

See also
--------
* `ADR-0008 <../../design_docs/adr/0008_declarative_authoring_surface.md>`_
* KDR-004 (validator pairing — by construction)
* KDR-006 (three-bucket retry via ``RetryingEdge``; field is
  ``max_semantic_attempts`` per primitives' naming)
* KDR-009 (LangGraph ``SqliteSaver`` checkpoints — preserved)
"""

from __future__ import annotations

import sys
import types
import typing
from collections.abc import Callable
from dataclasses import dataclass, field

# TYPE_CHECKING guard so spec.py can import CompiledStep for annotations
# without a circular runtime import.
from typing import TYPE_CHECKING, Annotated, Any, Literal

from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.types import Send

from ai_workflows.graph.error_handler import wrap_with_error_handler
from ai_workflows.graph.human_gate import human_gate
from ai_workflows.graph.retrying_edge import retrying_edge
from ai_workflows.graph.tiered_node import tiered_node
from ai_workflows.graph.validator_node import validator_node
from ai_workflows.primitives.retry import RetryPolicy

if TYPE_CHECKING:
    from ai_workflows.workflows.spec import (
        FanOutStep,
        GateStep,
        LLMStep,
        Step,
        TransformStep,
        ValidateStep,
        WorkflowSpec,
    )

__all__ = [
    "CompiledStep",
    "GraphEdge",
    "compile_spec",
]


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass
class GraphEdge:
    """A single edge contribution from a compiled step.

    Returned inside :class:`CompiledStep` so the top-level compiler can
    stitch per-step edge contributions together without each step knowing
    about its neighbours.

    Attributes
    ----------
    source:
        Name of the source node.
    target:
        Name of the target node or ``"END"`` for the terminal edge.
    condition:
        When ``None`` the edge is unconditional.  When set it is a
        ``(state) -> str`` callable suitable for
        ``StateGraph.add_conditional_edges``.
    fanout_targets:
        When set (non-empty list), indicates this edge is a fan-out
        ``Send``-based dispatch.  ``add_conditional_edges`` is called with
        ``(source, condition, list_of_targets)`` so LangGraph knows which
        nodes the ``Send`` packets may target.
    """

    source: str
    target: str | Literal["END"]
    condition: Callable | None = None
    fanout_targets: list[str] = field(default_factory=list)


@dataclass
class CompiledStep:
    """The graph-contribution of a single compiled step.

    Returned by every :meth:`~ai_workflows.workflows.spec.Step.compile`
    implementation (both built-in and custom).  The top-level
    :func:`compile_spec` stitches ``CompiledStep`` instances together
    via ``START``/``END`` and consecutive-step edges.

    Exported so custom-step authors can build their own ``CompiledStep``
    instances (Tier 3 advanced-override path per ADR-0008 §Extension model).

    Attributes
    ----------
    entry_node_id:
        The first node the compiler should wire a predecessor's exit to.
    exit_node_id:
        The last node the compiler should wire a successor's entry from.
    nodes:
        ``[(node_id, node_fn), ...]`` pairs to register with
        ``StateGraph.add_node``.
    edges:
        Additional edge contributions *within* this step (e.g. the
        ``call → validate`` edge on an ``LLMStep``).  Inter-step stitching
        (``step_n.exit → step_{n+1}.entry``) is the compiler's job, not the
        step's.
    """

    entry_node_id: str
    exit_node_id: str
    nodes: list[tuple[str, Callable]] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Top-level compiler
# ---------------------------------------------------------------------------


def compile_spec(spec: WorkflowSpec) -> Callable[[], StateGraph]:
    """Return a zero-argument builder that synthesises the workflow's StateGraph.

    The returned callable matches the ``WorkflowBuilder`` type that
    :func:`~ai_workflows.workflows.register` expects, so dispatch's
    ``builder().compile(checkpointer=...)`` call at ``_dispatch.py:554``
    works unchanged (KDR-009).

    Parameters
    ----------
    spec:
        A validated :class:`~ai_workflows.workflows.spec.WorkflowSpec`.
        Must have at least one step and a non-empty ``output_schema``.

    Returns
    -------
    A zero-argument callable (closure over ``spec``) that returns a fresh
    :class:`langgraph.graph.StateGraph` on every call.

    Raises
    ------
    ValueError
        If ``spec.output_schema`` has no fields — a schema-less workflow
        cannot determine when it is done.
    """
    from ai_workflows.workflows.spec import GateStep

    # --- Validate output schema has at least one field -----------------------
    output_fields = list(spec.output_schema.model_fields)
    if not output_fields:
        raise ValueError(
            f"WorkflowSpec {spec.name!r}: output_schema "
            f"{spec.output_schema.__name__!r} has no fields — "
            "the framework cannot determine when the workflow is done. "
            "Add at least one output field."
        )

    final_state_key = output_fields[0]

    # --- Synthesise state class ----------------------------------------------
    state_class = _derive_state_class(spec)

    # --- Synthesise initial_state hook ---------------------------------------
    def initial_state(run_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        """Satisfy the _dispatch._build_initial_state resolution order (M6 T01).

        Validates ``inputs`` against ``spec.input_schema``, populates
        output-schema fields with ``None`` so
        ``_dispatch._build_result_from_final`` can distinguish "not yet
        set" from "set to a non-None value".
        """
        parsed = spec.input_schema(**inputs)
        state: dict[str, Any] = {"run_id": run_id}
        state.update(parsed.model_dump())
        for fname in spec.output_schema.model_fields:
            state.setdefault(fname, None)
        return state

    # --- Synthesise tier_registry helper (per _resolve_tier_registry) --------
    def _tier_registry_helper() -> dict:
        return dict(spec.tiers)

    # --- Register a synthetic module so _import_workflow_module finds hooks --
    #
    # _dispatch._import_workflow_module reads builder.__module__ and looks up
    # sys.modules[builder.__module__] to find initial_state / FINAL_STATE_KEY.
    # We inject a lightweight synthetic module per spec so each spec gets its
    # own hook set without colliding.
    _module_name = f"ai_workflows.workflows._compiled_{spec.name}"
    _synth_module = types.ModuleType(_module_name)
    _synth_module.initial_state = initial_state  # type: ignore[attr-defined]
    _synth_module.FINAL_STATE_KEY = final_state_key  # type: ignore[attr-defined]
    _synth_module.__name__ = _module_name
    _synth_module.__package__ = "ai_workflows.workflows"

    # Attach the tier-registry helper under the canonical helper-name pattern
    # (<workflow>_tier_registry) that _dispatch._resolve_tier_registry reads.
    #
    # MEDIUM-2 fix: store under the *raw* spec.name (not a sanitised variant)
    # because _dispatch._resolve_tier_registry does:
    #   getattr(module, f"{workflow}_tier_registry", None)
    # where `workflow` is the registry key verbatim — e.g. "my-workflow" not
    # "my_workflow".  setattr/getattr work on any string key, even ones that
    # are not valid Python identifiers, so hyphens are fine here.
    setattr(_synth_module, f"{spec.name}_tier_registry", _tier_registry_helper)

    # Set TERMINAL_GATE_ID if the last step is a GateStep (dispatch reads it).
    if spec.steps and isinstance(spec.steps[-1], GateStep):
        _synth_module.TERMINAL_GATE_ID = spec.steps[-1].id  # type: ignore[attr-defined]

    sys.modules[_module_name] = _synth_module

    # --- Build the StateGraph builder closure --------------------------------
    def _builder() -> StateGraph:
        """Synthesise the LangGraph StateGraph for this spec.

        Called by dispatch's ``builder().compile(checkpointer=...)`` line.
        Returns a fresh ``StateGraph`` on every call so each run gets its
        own compiled graph instance (important for per-run checkpointers).
        """
        graph = StateGraph(state_class)

        compiled_steps: list[CompiledStep] = []
        for idx, step in enumerate(spec.steps):
            step_id = f"step_{idx}_{type(step).__name__.lower()}"
            cs = _compile_step(step, state_class, step_id, spec)
            _assert_kdr004_invariant(step, cs)
            compiled_steps.append(cs)

            # Register nodes
            for node_id, node_fn in cs.nodes:
                graph.add_node(node_id, node_fn)

            # Register intra-step edges
            for edge in cs.edges:
                _add_edge_to_graph(graph, edge)

        # Stitch inter-step edges: START → first.entry
        graph.add_edge(START, compiled_steps[0].entry_node_id)

        # Consecutive step stitching: step_n.exit → step_{n+1}.entry
        for i in range(len(compiled_steps) - 1):
            graph.add_edge(
                compiled_steps[i].exit_node_id,
                compiled_steps[i + 1].entry_node_id,
            )

        # Final step.exit → END — only when the exit node does not already have
        # a conditional edge that includes END routing (e.g. LLMStep with retry
        # already routes to END via retrying_edge's on_terminal path).
        last_cs = compiled_steps[-1]
        exit_has_conditional = any(
            e.condition is not None and e.source == last_cs.exit_node_id
            for e in last_cs.edges
        )
        if not exit_has_conditional:
            graph.add_edge(last_cs.exit_node_id, END)

        return graph

    # Stamp the builder's __module__ so _import_workflow_module finds the
    # synthetic module (and through it initial_state + FINAL_STATE_KEY).
    _builder.__module__ = _module_name

    return _builder


def _add_edge_to_graph(graph: StateGraph, edge: GraphEdge) -> None:
    """Register a single ``GraphEdge`` on the ``StateGraph``.

    Handles three cases:

    1. Unconditional: ``add_edge(source, target)``.
    2. Conditional (regular): ``add_conditional_edges(source, condition, map)``.
    3. Fan-out (Send-based): ``add_conditional_edges(source, condition,
       list_of_targets)`` — LangGraph resolves ``Send`` objects returned
       by the condition function to the appropriate targets.
    """
    if edge.condition is None:
        # Unconditional edge.
        graph.add_edge(edge.source, edge.target)
    elif edge.fanout_targets:
        # Fan-out Send-based dispatch.
        graph.add_conditional_edges(edge.source, edge.condition, edge.fanout_targets)
    else:
        # Regular conditional edge with explicit target mapping.
        path_map: dict[str, str] = {
            edge.source: edge.source,
            edge.target: edge.target,
            END: END,
        }
        graph.add_conditional_edges(edge.source, edge.condition, path_map)


# ---------------------------------------------------------------------------
# Step dispatch
# ---------------------------------------------------------------------------


def _compile_step(
    step: Step,
    state_class: type,
    step_id: str,
    spec: WorkflowSpec,
) -> CompiledStep:
    """Dispatch to the appropriate compile implementation for ``step``.

    Built-in step types each have a dedicated helper.  Custom step types
    (Tier 3) fall through to :func:`_compile_custom_step`, which calls
    ``step.execute()`` per the base-class contract.
    """
    from ai_workflows.workflows.spec import (
        FanOutStep,
        GateStep,
        LLMStep,
        TransformStep,
        ValidateStep,
    )

    if isinstance(step, LLMStep):
        return _compile_llm_step(step, state_class, step_id, spec)
    if isinstance(step, ValidateStep):
        return _compile_validate_step(step, step_id)
    if isinstance(step, GateStep):
        return _compile_gate_step(step, step_id, spec)
    if isinstance(step, TransformStep):
        return _compile_transform_step(step, step_id)
    if isinstance(step, FanOutStep):
        return _compile_fan_out_step(step, state_class, step_id, spec)
    # Tier 3 custom step — delegate to the step's own compile()
    return _compile_custom_step(step, state_class, step_id)


# ---------------------------------------------------------------------------
# LLMStep
# ---------------------------------------------------------------------------


def _compile_llm_step(
    step: LLMStep,
    state_class: type,
    step_id: str,
    spec: WorkflowSpec,
) -> CompiledStep:
    """Compile an ``LLMStep`` to ``TieredNode`` + paired ``ValidatorNode``.

    Emits two nodes (``<step_id>_call`` + ``<step_id>_validate``) and the
    intra-step edge between them.  ``retrying_edge`` (KDR-006) is **always**
    wired — when ``step.retry is None``, a default :class:`RetryPolicy` is
    instantiated (``max_transient_attempts=3, max_semantic_attempts=3``).
    This matches the ``LLMStep.retry`` docstring: "When ``None`` the compiler
    uses the default ``RetryPolicy()``." (MEDIUM-1 fix.)

    ``validator_node``'s ``max_attempts`` is derived from
    ``policy.max_semantic_attempts`` so the two budgets always agree
    (uses ``max_semantic_attempts`` field naming per locked Q1 / TA-LOW-07).

    KDR-004 enforced by construction: the returned ``CompiledStep`` always
    has exactly two nodes.  :func:`_assert_kdr004_invariant` verifies the
    shape.
    """
    call_node_id = f"{step_id}_call"
    validate_node_id = f"{step_id}_validate"

    # --- Resolve prompt source (locked Q2) -----------------------------------
    if step.prompt_fn is not None:
        _prompt_fn: Callable = step.prompt_fn
    else:
        # Tier 1 sugar: synthesise a prompt_fn from the template.
        # The synthesised function runs str.format(**state) so {field}
        # placeholders are substituted from graph state at invocation time.
        # No Jinja, no f-string evaluation, no callbacks (locked Q2).
        template: str = step.prompt_template  # type: ignore[assignment]

        def _prompt_fn(state: dict) -> tuple[str | None, list[dict]]:  # type: ignore[misc]
            """Synthesised prompt_fn from prompt_template (Tier 1 sugar).

            Runs ``template.format(**state)`` and returns the rendered
            template as a user-role message with ``system=None``.

            LOW-1 fix: returning ``(rendered, [])`` (system-only, no user
            message) causes Gemini's chat-completions API to reject the
            request ("at least one user message is required").  The correct
            shape is ``(None, [{"role": "user", "content": rendered}])``.
            Authors who need an explicit system prompt should use the
            ``prompt_fn=`` Tier 2 path.
            """
            rendered = template.format(**state)
            return None, [{"role": "user", "content": rendered}]

    # --- Build TieredNode + ValidatorNode ------------------------------------
    # MEDIUM-1 fix: when step.retry is None, use RetryPolicy() defaults so the
    # Tier 1 spec API gives "sensible defaults" behaviour (default-on retry per
    # the docstring on spec.py LLMStep.retry).  Explicitly passing a RetryPolicy
    # overrides the defaults; passing retry=None is the *convenient* path, not the
    # "no retry" path.  This aligns the docstring with the actual behaviour.
    policy: RetryPolicy = step.retry if step.retry is not None else RetryPolicy()

    call_node = tiered_node(
        tier=step.tier,
        prompt_fn=_prompt_fn,
        output_schema=step.response_format,
        node_name=call_node_id,
    )
    validate_node = validator_node(
        schema=step.response_format,
        input_key=f"{call_node_id}_output",
        output_key=_first_field_name(step.response_format),
        node_name=validate_node_id,
        # Use policy.max_semantic_attempts so both ValidatorNode and
        # RetryingEdge share the same semantic-retry budget (no split-brain
        # between "validator says N retries; retry edge says M retries").
        max_attempts=policy.max_semantic_attempts,
    )

    # Wrap call + validate nodes with error handler so bucket exceptions
    # become state writes that RetryingEdge can route on.
    wrapped_call = wrap_with_error_handler(call_node, node_name=call_node_id)
    wrapped_validate = wrap_with_error_handler(validate_node, node_name=validate_node_id)

    # --- Build intra-step edges -----------------------------------------------
    # Always wire call → validate (unconditional).
    intra_edges: list[GraphEdge] = [
        GraphEdge(source=call_node_id, target=validate_node_id, condition=None)
    ]

    # KDR-006: three-bucket retry via retrying_edge — always wired (default-on).
    # max_semantic_attempts field naming per locked Q1 + TA-LOW-07.
    # After validate either routes back to call (semantic/transient retry)
    # or to END (hard-stop / terminal).
    edge_fn = retrying_edge(
        on_transient=call_node_id,
        on_semantic=call_node_id,
        on_terminal=END,
        policy=policy,
    )
    intra_edges.append(
        GraphEdge(
            source=validate_node_id,
            target=call_node_id,
            condition=edge_fn,
        )
    )

    return CompiledStep(
        entry_node_id=call_node_id,
        exit_node_id=validate_node_id,
        nodes=[
            (call_node_id, wrapped_call),
            (validate_node_id, wrapped_validate),
        ],
        edges=intra_edges,
    )


# ---------------------------------------------------------------------------
# ValidateStep
# ---------------------------------------------------------------------------


def _compile_validate_step(step: ValidateStep, step_id: str) -> CompiledStep:
    """Compile a ``ValidateStep`` to a standalone ``ValidatorNode``.

    No retry edge — a failure here is a workflow logic bug, not a
    transient provider error.  The workflow errors via the existing
    ``_dispatch._extract_error_message`` path on failure.
    """
    node_id = f"{step_id}_validate"

    validate_fn = validator_node(
        schema=step.schema,
        input_key=step.target_field,
        output_key=step.target_field,
        node_name=node_id,
        max_attempts=1,
    )
    wrapped = wrap_with_error_handler(validate_fn, node_name=node_id)

    return CompiledStep(
        entry_node_id=node_id,
        exit_node_id=node_id,
        nodes=[(node_id, wrapped)],
        edges=[],
    )


# ---------------------------------------------------------------------------
# GateStep
# ---------------------------------------------------------------------------


def _compile_gate_step(
    step: GateStep,
    step_id: str,
    spec: WorkflowSpec,
) -> CompiledStep:
    """Compile a ``GateStep`` to a ``HumanGate`` (``interrupt``-based) node.

    The ``prompt_fn`` renders ``step.prompt`` when set; falls back to a
    generic pause message when ``None``.  The ``on_reject`` field is
    preserved in the gate payload; its routing is handled by
    ``_dispatch.resume_run`` (the full reject-routing topology is a Tier 4
    concern beyond the five built-in step types).
    """
    node_id = f"{step_id}_gate"

    gate_prompt = step.prompt or f"Gate {step.id!r}: awaiting operator review."

    def _prompt_fn(state: dict) -> str:
        return gate_prompt

    gate_node = human_gate(
        gate_id=step.id,
        prompt_fn=_prompt_fn,
    )

    return CompiledStep(
        entry_node_id=node_id,
        exit_node_id=node_id,
        nodes=[(node_id, gate_node)],
        edges=[],
    )


# ---------------------------------------------------------------------------
# TransformStep
# ---------------------------------------------------------------------------


def _compile_transform_step(step: TransformStep, step_id: str) -> CompiledStep:
    """Compile a ``TransformStep`` to a plain async LangGraph node.

    The compiler does not inspect ``step.fn``'s body — KDR-013 "user code is
    user-owned" applies.  The node name is ``<step_id>_<step.name>`` so the
    step author's chosen name surfaces in LangGraph's node graph.
    """
    node_id = f"{step_id}_{step.name}"

    async def _node(state: dict) -> dict:
        return await step.fn(state)

    return CompiledStep(
        entry_node_id=node_id,
        exit_node_id=node_id,
        nodes=[(node_id, _node)],
        edges=[],
    )


# ---------------------------------------------------------------------------
# FanOutStep
# ---------------------------------------------------------------------------


def _append_reducer(existing: list, new: Any) -> list:
    """Append-reducer for ``Annotated`` list fields used in FanOut merge channels.

    Called by LangGraph's state-channel machinery to merge per-branch
    outputs into the parent state's list-valued field.
    """
    if existing is None:
        existing = []
    if isinstance(new, list):
        return list(existing) + new
    return list(existing) + [new]


def _compile_fan_out_step(
    step: FanOutStep,
    state_class: type,
    step_id: str,
    spec: WorkflowSpec,
) -> CompiledStep:
    """Compile a ``FanOutStep`` to a ``Send``-pattern parallel dispatch.

    Emits three node contributions:

    1. ``<step_id>_dispatch`` — reads ``state[iter_field]`` and returns one
       :class:`langgraph.types.Send` per element, each targeting
       ``<step_id>_branch`` with a per-element sub-state dict.
    2. ``<step_id>_branch`` — the compiled sub-graph that runs ``sub_steps``
       for one element.  Registered as a node in the parent graph per the
       LangGraph ``Send``-based sub-graph pattern (cf. slice_refactor).
    3. ``<step_id>_merge`` — a no-op synchronisation point; results have
       already accumulated via the ``merge_field`` append-reducer channel.

    The parent state's ``merge_field`` is declared as
    ``Annotated[list, _append_reducer]`` in :func:`_derive_state_class` so
    parallel ``Send`` branches can each write ``{merge_field: [result]}``
    without clobbering each other.

    ``entry == "<step_id>_dispatch"``, ``exit == "<step_id>_merge"``.
    """
    dispatch_node_id = f"{step_id}_dispatch"
    branch_node_id = f"{step_id}_branch"
    merge_node_id = f"{step_id}_merge"

    iter_field = step.iter_field
    merge_field = step.merge_field

    # --- Build sub-state class for per-branch state -------------------------
    sub_state_class = _derive_sub_state_class(state_class, iter_field, merge_field)

    # --- Compile sub-steps into a sub-graph ----------------------------------
    sub_compiled: list[CompiledStep] = []
    for sub_idx, sub_step in enumerate(step.sub_steps):
        sub_step_id = f"{step_id}_sub_{sub_idx}_{type(sub_step).__name__.lower()}"
        sub_cs = _compile_step(sub_step, sub_state_class, sub_step_id, spec)
        sub_compiled.append(sub_cs)

    sub_graph = StateGraph(sub_state_class)
    for sub_cs in sub_compiled:
        for node_id, node_fn in sub_cs.nodes:
            sub_graph.add_node(node_id, node_fn)
        for edge in sub_cs.edges:
            _add_edge_to_graph(sub_graph, edge)

    if sub_compiled:
        sub_graph.add_edge(START, sub_compiled[0].entry_node_id)
        for i in range(len(sub_compiled) - 1):
            sub_graph.add_edge(
                sub_compiled[i].exit_node_id,
                sub_compiled[i + 1].entry_node_id,
            )
        sub_graph.add_edge(sub_compiled[-1].exit_node_id, END)

    # Compile the sub-graph without a checkpointer — it runs inside the parent
    # graph which owns the checkpointer.
    compiled_sub = sub_graph.compile()

    # --- Dispatch function (returns Send objects) ----------------------------
    def _dispatch_fn(state: dict) -> list[Send]:
        """Fan-out: one ``Send`` per element of ``state[iter_field]``."""
        items = state.get(iter_field) or []
        run_id = state.get("run_id", "")
        return [
            Send(branch_node_id, {"run_id": run_id, iter_field: item})
            for item in items
        ]

    # Dummy entry for the dispatch node — the actual work is done by returning
    # Send objects from the conditional edge function.
    async def _dispatch_node(state: dict) -> dict:
        """No-op dispatch node; fan-out logic lives in _dispatch_fn."""
        return {}

    # --- Branch wrapper (runs the compiled sub-graph for one element) -------
    async def _branch_node(state: dict) -> dict:
        """Run the sub-graph for one branch element and accumulate the result.

        The sub-graph is invoked with the per-element branch state.  Its
        output is wrapped in a list so the ``merge_field`` append-reducer
        on the parent state accumulates one entry per branch.
        """
        result = await compiled_sub.ainvoke(state)
        # The sub-graph result dict is the per-element output.
        # Wrap in a list so the parent append-reducer accumulates correctly.
        return {merge_field: [result]}

    # --- Merge node (synchronisation point) ---------------------------------
    async def _merge_node(state: dict) -> dict:
        """Synchronisation point after all branches complete.

        Results have already been accumulated into ``merge_field`` by the
        append-reducer; this node is a no-op structural marker.
        """
        return {}

    # The dispatch → branch fan-out edge uses add_conditional_edges with the
    # list-form path_map so LangGraph knows which nodes the Send packets target.
    fan_out_edge = GraphEdge(
        source=dispatch_node_id,
        target=branch_node_id,
        condition=_dispatch_fn,
        fanout_targets=[branch_node_id],
    )

    return CompiledStep(
        entry_node_id=dispatch_node_id,
        exit_node_id=merge_node_id,
        nodes=[
            (dispatch_node_id, _dispatch_node),
            (branch_node_id, _branch_node),
            (merge_node_id, _merge_node),
        ],
        edges=[
            fan_out_edge,
            # branch → merge (unconditional — all branches flow here after completing)
            GraphEdge(source=branch_node_id, target=merge_node_id, condition=None),
        ],
    )


# ---------------------------------------------------------------------------
# Custom step (Tier 3)
# ---------------------------------------------------------------------------


def _compile_custom_step(
    step: Step,
    state_class: type,
    step_id: str,
) -> CompiledStep:
    """Wrap a custom-step's ``execute()`` in a single LangGraph node.

    This is the default :meth:`~ai_workflows.workflows.spec.Step.compile`
    implementation (locked Q4 per ADR-0008 §Extension model).  Custom step
    types that subclass :class:`Step` and implement only ``execute()``
    inherit this path automatically — they do not need to override
    ``compile()``.

    The node id is ``<step_id>_execute`` so custom steps have a predictable
    id in the compiled graph.
    """
    node_id = f"{step_id}_execute"

    async def _node(state: dict) -> dict:
        return await step.execute(state)

    return CompiledStep(
        entry_node_id=node_id,
        exit_node_id=node_id,
        nodes=[(node_id, _node)],
        edges=[],
    )


# ---------------------------------------------------------------------------
# Step base-class default compile() — shipped in T02 (spec locked Q4)
# ---------------------------------------------------------------------------


def _default_step_compile(
    step: Step,
    state_class: type,
    step_id: str,
) -> CompiledStep:
    """Default ``compile()`` for :class:`~ai_workflows.workflows.spec.Step`.

    Wraps ``self.execute()`` in a single LangGraph node.  This is the
    implementation body that T01's stub pointed to; it ships here (T02)
    per the locked Q4 contract.  Custom step authors who only override
    ``execute()`` get a working compile path automatically.

    Called from :meth:`ai_workflows.workflows.spec.Step.compile` after
    T02 updates the body to delegate here.
    """
    return _compile_custom_step(step, state_class, step_id)


# ---------------------------------------------------------------------------
# KDR-004 structural assertion
# ---------------------------------------------------------------------------


def _assert_kdr004_invariant(step: Step, cs: CompiledStep) -> None:
    """Assert KDR-004: every ``LLMStep``-emitted ``CompiledStep`` has two nodes.

    The compiler verifies the structure by inspection — it does not trust the
    step's self-reporting.  If an ``LLMStep`` subclass somehow drops the
    validator (e.g. a custom override that forgets the pairing), this assertion
    surfaces the violation at compile time rather than at runtime.
    """
    from ai_workflows.workflows.spec import LLMStep

    if not isinstance(step, LLMStep):
        return  # Only LLMStep is subject to this invariant.

    if len(cs.nodes) != 2:
        raise ValueError(
            f"KDR-004 violation: LLMStep.compile() must return a CompiledStep "
            f"with exactly 2 nodes (call + validator), got {len(cs.nodes)!r}. "
            f"If you subclassed LLMStep and overrode compile(), ensure the "
            f"override includes a paired ValidatorNode."
        )

    # Verify the exit node is not the same as the entry (call != validate)
    if cs.entry_node_id == cs.exit_node_id:
        raise ValueError(
            f"KDR-004 violation: LLMStep.compile() entry_node_id and "
            f"exit_node_id must differ (call node ≠ validate node), "
            f"got both == {cs.entry_node_id!r}."
        )


# ---------------------------------------------------------------------------
# State class derivation
# ---------------------------------------------------------------------------


def _derive_state_class(spec: WorkflowSpec) -> type:
    """Synthesise a ``TypedDict``-compatible class from ``input_schema ⊕ output_schema``.

    Algorithm (spec Deliverable 3):

    1. Collect all field names + annotations from ``input_schema`` and
       ``output_schema``.  Output-schema fields win on collision so the
       terminal artefact type is correct.
    2. Add framework-internal state keys: ``run_id: str``, retry counters
       (``last_exception``, ``_retry_counts``, ``_non_retryable_failures``),
       and the M8 T04 mid-run tier-override key
       (``_mid_run_tier_overrides``) so
       :func:`~ai_workflows.graph.tiered_node._resolve_tier` works correctly
       for specs that use ``LLMStep``.
    3. Add ``Annotated[list, _append_reducer]`` channels for any
       ``FanOutStep.merge_field`` fields.
    4. Synthesise a ``TypedDict`` named ``<spec_name_title>State``.

    The state class is held as a closure inside the builder thunk so each
    spec's compile produces a fresh state class per :func:`register_workflow`
    call (spec Deliverable 3 requirement).
    """
    from ai_workflows.workflows.spec import FanOutStep, LLMStep

    annotations: dict[str, Any] = {}

    # Input schema fields (lower priority on collision)
    for fname, finfo in spec.input_schema.model_fields.items():
        annotations[fname] = finfo.annotation or Any

    # Output schema fields (higher priority — overwrite on collision)
    for fname, finfo in spec.output_schema.model_fields.items():
        annotations[fname] = finfo.annotation or Any

    # Framework-internal keys (used by TieredNode, RetryingEdge, dispatch)
    annotations["run_id"] = str
    annotations["last_exception"] = Any
    annotations["_retry_counts"] = Any
    annotations["_non_retryable_failures"] = Any
    annotations["_mid_run_tier_overrides"] = Any  # M8 T04 mid-run override key

    # LLMStep intermediate output keys.
    # TieredNode writes f"{node_name}_output" to state; ValidatorNode reads it.
    # These keys must be declared in the TypedDict so LangGraph carries them
    # through state updates (undeclared keys are dropped by the state reducer).
    for idx, step in enumerate(spec.steps):
        if isinstance(step, LLMStep):
            step_id = f"step_{idx}_{type(step).__name__.lower()}"
            call_node_id = f"{step_id}_call"
            # The raw LLM output key and its revision-hint companion (ValidatorNode).
            annotations[f"{call_node_id}_output"] = Any
            annotations[f"{call_node_id}_output_revision_hint"] = Any

    # FanOut merge-field channels with append-reducer (prevents parallel-write
    # clobbering under Send-based fan-out — mirrors the slice_refactor pattern).
    # Always override: even if merge_field appears in output_schema, it must use
    # the Annotated reducer so LangGraph merges parallel branch writes correctly.
    for step in spec.steps:
        if isinstance(step, FanOutStep):
            annotations[step.merge_field] = Annotated[list, _append_reducer]

    class_name = f"{''.join(w.capitalize() for w in spec.name.replace('-', '_').split('_'))}State"
    state_cls = typing.TypedDict(class_name, annotations)  # type: ignore[misc]
    return state_cls


def _derive_sub_state_class(
    parent_state_class: type,
    iter_field: str,
    merge_field: str,
) -> type:
    """Synthesise a sub-state class for a ``FanOutStep`` branch.

    The sub-state contains ``run_id``, the ``iter_field`` (the single
    per-element value the branch operates on), and framework-internal keys.
    The ``merge_field`` is intentionally excluded — the branch writes its
    result back to the parent state via ``Send``'s state-update mechanism.
    """
    annotations: dict[str, Any] = {
        "run_id": str,
        iter_field: Any,
        "last_exception": Any,
        "_retry_counts": Any,
        "_non_retryable_failures": Any,
        "_mid_run_tier_overrides": Any,
    }
    # Inherit any other fields from the parent state class that sub-steps
    # might read (best-effort; sub-steps are user-owned per KDR-013).
    parent_hints = getattr(parent_state_class, "__annotations__", {})
    for fname, ftype in parent_hints.items():
        if fname not in annotations and fname != merge_field:
            annotations[fname] = ftype

    safe_iter = iter_field.replace("-", "_").title()
    sub_cls = typing.TypedDict(f"_SubState{safe_iter}", annotations)  # type: ignore[misc]
    return sub_cls


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _first_field_name(model: type) -> str:
    """Return the first field name declared on a pydantic model.

    Used to determine the state key a ``ValidatorNode`` writes its output to
    (the compiled ``output_key`` parameter).  If the model has no fields the
    LLMStep-construction-time invariant should have caught it, but we guard
    defensively here.
    """
    fields = list(model.model_fields)
    if not fields:
        raise ValueError(
            f"response_format {model.__name__!r} has no fields — "
            "cannot determine the output state key."
        )
    return fields[0]
