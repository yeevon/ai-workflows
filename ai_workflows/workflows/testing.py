"""Testing utilities for the M19 declarative authoring surface.

M19 Task 06. Provides :func:`compile_step_in_isolation` for downstream
consumers and the framework's own test suite to unit-test custom
:class:`~ai_workflows.workflows.spec.Step` types without compiling a full
:class:`~ai_workflows.workflows.spec.WorkflowSpec` or invoking dispatch.

Per locked M4 (M19 task analysis 2026-04-26): downstream consumers need a
way to unit-test custom step types in isolation without compiling a full
``WorkflowSpec`` and dispatching through the runtime.  This module ships
``compile_step_in_isolation`` for that purpose.

Relationship to other modules
------------------------------
* :mod:`ai_workflows.workflows.spec` (M19 T01) — the ``Step`` base class
  instances this module compiles.
* :mod:`ai_workflows.workflows._compiler` (M19 T02) — ``_add_edge_to_graph``
  helper reused; ``step.compile()`` is called exactly as the real compiler
  calls it so the compile path matches the real registration path.
  Custom steps that override ``compile()`` directly are also exercised through
  the same path.

KDR alignment
-------------
* KDR-009 — no hand-rolled checkpoint writes; the fixture compiles and runs a
  minimal ``StateGraph`` without a checkpointer (isolation test only; full
  checkpoint round-trips belong in integration tests using dispatch).
* KDR-013 — user code is user-owned; the fixture calls ``step.execute()`` or
  ``step.compile()`` exactly as the framework does; it does not lint or sandbox
  the step.
"""

from __future__ import annotations

from typing import Any

from langgraph.constants import END, START
from langgraph.graph import StateGraph

from ai_workflows.workflows.spec import Step

__all__ = ["compile_step_in_isolation"]


async def compile_step_in_isolation(
    step: Step,
    *,
    initial_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile a single :class:`~ai_workflows.workflows.spec.Step` and run it in isolation.

    Wraps the step in a one-node ``StateGraph`` (using the same Q4 default
    compile path as the real :func:`~ai_workflows.workflows._compiler.compile_spec`
    compiler), runs the graph against *initial_state*, and returns the final
    state dict.

    Useful for unit-testing custom step types without registering a full
    ``WorkflowSpec`` or invoking dispatch.  The fixture intentionally does
    **not** attach a checkpointer (``SqliteSaver``) — isolation tests do not
    need checkpoint persistence.

    The state class is ``dict`` (plain Python dict) so the graph accepts
    and preserves any keys the step writes, including keys not present in
    *initial_state*.  This matches the "open" state contract for custom step
    testing: the fixture does not limit which keys the step can write.

    Parameters
    ----------
    step:
        The :class:`~ai_workflows.workflows.spec.Step` instance to compile and
        run.  The step may be any subclass — built-in or custom (Tier 3).
    initial_state:
        The initial state dict passed to the compiled graph.  Defaults to an
        empty dict when ``None``.

    Returns
    -------
    dict[str, Any]
        The final state dict after the step's node(s) have executed.

    Raises
    ------
    Exception
        Any exception raised inside ``step.execute()`` (or inside nodes
        contributed by a ``compile()`` override) propagates unchanged so tests
        can assert on error cases.

    Examples
    --------
    .. code-block:: python

        import asyncio
        from ai_workflows.workflows import Step
        from ai_workflows.workflows.testing import compile_step_in_isolation


        class AddOneStep(Step):
            counter_field: str

            async def execute(self, state: dict) -> dict:
                return {self.counter_field: state[self.counter_field] + 1}


        async def main():
            step = AddOneStep(counter_field="n")
            result = await compile_step_in_isolation(step, initial_state={"n": 0})
            assert result["n"] == 1

        asyncio.run(main())
    """
    if initial_state is None:
        initial_state = {}

    # Use plain dict as the state class for the isolation graph.
    # A TypedDict would silently drop keys the step writes that are not
    # declared in the schema — exactly the wrong behaviour for an isolation
    # fixture that accepts arbitrary custom steps.
    isolation_state_cls = dict  # type: ignore[assignment]

    # --- Compile the step -------------------------------------------------------
    # Use the same path the real compiler uses for this step type.
    # step.compile() delegates to _default_step_compile for custom steps that
    # only override execute(), or to the built-in's own compile() for built-ins.
    step_id = f"step_0_{type(step).__name__.lower()}"
    compiled = step.compile(isolation_state_cls, step_id)

    # --- Build minimal StateGraph -----------------------------------------------
    graph = StateGraph(isolation_state_cls)

    # Register all nodes the compiled step contributes.
    for node_id, node_fn in compiled.nodes:
        graph.add_node(node_id, node_fn)

    # Register intra-step edges.
    from ai_workflows.workflows._compiler import _add_edge_to_graph
    for edge in compiled.edges:
        _add_edge_to_graph(graph, edge)

    # Wire START → entry and exit → END (only when exit doesn't already have
    # a conditional edge routing away, e.g. LLMStep's retrying_edge).
    graph.add_edge(START, compiled.entry_node_id)

    exit_has_conditional = any(
        e.condition is not None and e.source == compiled.exit_node_id
        for e in compiled.edges
    )
    if not exit_has_conditional:
        graph.add_edge(compiled.exit_node_id, END)

    # --- Invoke without a checkpointer ------------------------------------------
    compiled_graph = graph.compile()

    # Seed framework-internal keys so nodes that read them don't KeyError.
    seeded_state: dict[str, Any] = {
        "run_id": "",
        "last_exception": None,
        "_retry_counts": {},
        "_non_retryable_failures": 0,
        "_mid_run_tier_overrides": None,
    }
    seeded_state.update(initial_state)

    raw_result: dict[str, Any] = await compiled_graph.ainvoke(seeded_state)

    # Merge semantics: LangGraph's ``dict`` state class replaces the state
    # dict entirely with each node's return value.  For isolation testing,
    # the expected behaviour is that keys not touched by the step survive.
    # We reproduce the merge semantics of a TypedDict-backed graph (where
    # each node's return dict is merged into the existing state, not
    # replaced) by starting from the seeded state and overlaying the result.
    merged: dict[str, Any] = dict(seeded_state)
    merged.update(raw_result)
    return merged
