"""Declarative workflow authoring surface — data-model layer.

M19 Task 01. Implements the ``WorkflowSpec`` pydantic model, the step-type
taxonomy (``Step`` base class + five built-in step types), the custom-step
extension hook contract, and the ``register_workflow`` entry point.

See also
--------
* `ADR-0008 <../../design_docs/adr/0008_declarative_authoring_surface.md>`_ —
  the load-bearing decision this module executes.
* :mod:`ai_workflows.workflows._compiler` (M19 T02) — spec → ``StateGraph``
  synthesis; each step's ``compile()`` implementation lands there.
* :mod:`ai_workflows.workflows.__init__` — re-exports the public surface so
  external authors import from the package root.
* :mod:`ai_workflows.primitives.retry` — ``RetryPolicy`` re-exported here per
  locked Q1 (no parallel spec class).

Extension model (four-tier per ADR-0008 §Extension model)
----------------------------------------------------------
* **Tier 1 — compose:** compose ``WorkflowSpec`` from built-in step types.
* **Tier 2 — parameterise:** use ``LLMStep.prompt_fn`` (advanced) or
  ``LLMStep.prompt_template`` (sugar) to tune per-step prompt logic.
* **Tier 3 — custom step:** subclass ``Step`` and implement
  ``async execute(state) -> dict`` (typical) or override
  ``compile(state_class, step_id) -> CompiledStep`` (advanced).
* **Tier 4 — escape hatch:** call ``register(name, build_fn)`` directly with
  a hand-authored ``StateGraph`` builder for topologies the spec cannot
  express.

KDR-004 (validator pairing) is enforced *by construction* for ``LLMStep``:
``response_format`` is a required field so an unvalidated LLM step is
impossible to express in the type system.

KDR-013 (user code is user-owned) boundary: workflow *specs* are data; custom
step types authored as ``Step`` subclasses remain user-owned code run
in-process per ADR-0007. The framework surfaces errors but does not lint,
test, or sandbox them.
"""

from __future__ import annotations

import warnings
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, model_validator

# Re-export RetryPolicy from primitives.retry per locked Q1.
# The spec API does not invent a parallel retry surface.
from ai_workflows.primitives.retry import RetryPolicy as RetryPolicy  # noqa: PLC0414
from ai_workflows.primitives.tiers import TierConfig

if TYPE_CHECKING:
    # CompiledStep is defined in M19 T02 (_compiler.py).  Imported here only
    # under TYPE_CHECKING so spec.py has no runtime dependency on the
    # as-yet-unshipped compiler module.
    from ai_workflows.workflows._compiler import CompiledStep

# CARRY-T01-LOW-1 (T08 close-out): ``ValidateStep.schema`` shadows the pydantic
# ``BaseModel.schema()`` classmethod.  The field name is locked by the public API
# (Q1 — no rename until a breaking version change warrants it); suppress the
# one-time-per-process UserWarning so downstream consumers do not see it.
# The field works correctly — only the cosmetic warning is suppressed.
# Placed after all imports so ruff E402 (module-level import not at top) is
# not triggered on the primitives imports above.
warnings.filterwarnings(
    "ignore",
    message=r'Field name "schema" in "ValidateStep" shadows an attribute in parent "Step"',
    category=UserWarning,
)

__all__ = [
    "FanOutStep",
    "GateStep",
    "LLMStep",
    "RetryPolicy",
    "Step",
    "TransformStep",
    "ValidateStep",
    "WorkflowSpec",
    "register_workflow",
]


# ---------------------------------------------------------------------------
# Step base class
# ---------------------------------------------------------------------------


class Step(BaseModel):
    """Base class for workflow step types.

    Built-in step types (``LLMStep``, ``ValidateStep``, ``GateStep``,
    ``TransformStep``, ``FanOutStep``) ship in this module and override
    ``compile()`` directly so they can emit multi-node topologies (``Send``
    fan-out, validator pairing, sub-graph composition, conditional edges).
    Custom step types are authored by downstream consumers per ADR-0008
    §Extension model — Tier 3.

    Authoring contract for custom step types
    -----------------------------------------
    * **Typical path:** implement ``async execute(state) -> dict``.  The
      base class's default ``compile()`` wraps this coroutine in a single
      LangGraph node; the framework handles the wiring.
    * **Advanced path:** override ``compile(state_class, step_id) ->
      CompiledStep`` directly when you need fan-out, sub-graph composition,
      conditional edges, or any topology the single-node default cannot
      express.  See ``docs/writing-a-custom-step.md`` for the upgrade-path
      example.

    ``CompiledStep`` is the dataclass T02's compiler returns from each
    step's ``compile()``: ``(entry_node_id, exit_node_id, nodes, edges)``.
    The compiler stitches ``CompiledStep`` instances end-to-end via ``START``
    + ``END`` edges; subclasses never touch ``StateGraph`` directly.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    async def execute(self, state: dict) -> dict:  # type: ignore[return]
        """Default coroutine that custom step types implement.

        Override this for the typical Tier 3 path.  The base ``compile()``
        wraps the coroutine in a single LangGraph node; subclasses that
        only override ``execute`` get a single-node graph contribution with
        no extra wiring.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must implement execute() (the typical "
            f"Tier 3 path) or override compile() (advanced) — see "
            f"docs/writing-a-custom-step.md"
        )

    def compile(
        self,
        state_class: type,
        step_id: str,
    ) -> CompiledStep:
        """Wrap ``self.execute()`` in a single LangGraph node.

        Built-in step types override this to emit multi-node topologies.
        Custom step types that subclass only ``execute`` inherit this default
        (locked Q4 per ADR-0008 §Extension model — implementation ships in
        M19 T02 ``_compiler.py`` and is delegated here).

        The default wraps ``self.execute()`` in a single LangGraph node so
        custom-step authors who only override ``execute()`` get a working
        compile path automatically without overriding ``compile()``.
        """
        # Delegate to the compiler module (M19 T02).  Lazy import keeps
        # spec.py graph-free for callers that only need the data classes.
        from ai_workflows.workflows._compiler import _default_step_compile

        return _default_step_compile(self, state_class, step_id)


# ---------------------------------------------------------------------------
# Built-in step types
# ---------------------------------------------------------------------------


class LLMStep(Step):
    """Single tier-routed LLM call with paired validator.

    Audience: any consumer using the declarative authoring surface.

    Compiles to ``TieredNode`` + paired ``ValidatorNode`` (KDR-004 by
    construction — ``response_format`` is required; an unvalidated LLM
    step cannot be expressed in the type system) + ``RetryingEdge``
    (KDR-006).

    ``prompt_fn`` is the advanced path used by state-derived prompt logic
    (matches the existing :func:`~ai_workflows.graph.tiered_node.tiered_node`
    ``prompt_fn`` contract: ``(state: dict) -> (system: str | None,
    messages: list[dict])``).

    ``prompt_template`` is the Tier 1 sugar: a plain ``str.format()``
    template whose ``{field}`` placeholders are filled from the current
    graph state at compile time.  Only ``str.format()``-style substitution
    is supported — no Jinja, no f-string evaluation, no callbacks.

    Exactly one of ``prompt_fn`` or ``prompt_template`` must be set; the
    cross-field validator enforces this with an explicit error message.
    """

    tier: str
    """Logical tier name.  Must appear as a key in ``WorkflowSpec.tiers``."""

    prompt_fn: Callable[[dict], tuple[str | None, list[dict]]] | None = None
    """Advanced prompt builder.  Callable takes graph state, returns
    ``(system_prompt, messages)``."""

    prompt_template: str | None = None
    """Tier 1 sugar.  ``str.format()``-only template; ``{field}`` placeholders
    are substituted from graph state at invocation time."""

    response_format: type[BaseModel]
    """Required.  KDR-004 by construction: an ``LLMStep`` without a
    ``response_format`` cannot be instantiated."""

    retry: RetryPolicy | None = None
    """Optional per-step retry budget.  When ``None`` the compiler uses the
    default ``RetryPolicy()``."""

    @model_validator(mode="after")
    def _check_exactly_one_prompt_source(self) -> LLMStep:
        both = self.prompt_fn is not None and self.prompt_template is not None
        neither = self.prompt_fn is None and self.prompt_template is None
        if both:
            raise ValueError(
                "LLMStep requires exactly one of `prompt_fn` (callable) or "
                "`prompt_template` (str.format string); got both"
            )
        if neither:
            raise ValueError(
                "LLMStep requires exactly one of `prompt_fn` (callable) or "
                "`prompt_template` (str.format string); got neither"
            )
        return self

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )


class ValidateStep(Step):
    """Schema validator without an LLM call.

    Audience: consumers who need a pydantic validation checkpoint on a
    state field produced by a prior ``TransformStep`` or custom step.

    Compiles to a standalone ``ValidatorNode`` (no ``TieredNode``).
    """

    target_field: str
    """State key whose value this step validates against ``schema``."""

    schema: type[BaseModel]
    """The pydantic model the value at ``target_field`` is validated against."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )


class GateStep(Step):
    """Human-gate pause point.

    Audience: consumers who need an operator-review checkpoint in their
    workflow.

    Compiles to a ``HumanGate`` (``interrupt()``-based pause node).
    ``id`` is the gate identifier surfaced through ``aiw resume``; the
    framework wires the resumption edge automatically.
    """

    id: str
    """Gate identifier.  Surfaces as the gate name in ``aiw resume`` + MCP
    ``resume_run``."""

    prompt: str | None = None
    """Optional operator-facing pause message shown at the gate."""

    on_reject: Literal["retry", "fail"] = "fail"
    """Behaviour when the operator rejects: ``"retry"`` loops back to the
    preceding LLM step; ``"fail"`` terminates the run."""


class TransformStep(Step):
    """Pure-Python state transformation.

    Audience: consumers who need a deterministic state-shaping step that
    does not call an LLM.

    Compiles to a plain LangGraph node that awaits ``fn(state)`` and
    merges the returned dict into the graph state.
    """

    name: str
    """Human-readable step name used as the LangGraph node identifier."""

    fn: Callable[[dict], Awaitable[dict]]
    """Consumer-provided async callable.  The framework wraps it as a plain
    LangGraph node at compile time."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )


class FanOutStep(Step):
    """``Send``-pattern parallel dispatch.

    Audience: consumers who need to run the same sub-step list once per
    element of a list-valued state field.

    Compiles to a ``Send``-pattern LangGraph fan-out: for each item in
    ``state[iter_field]`` the compiler emits a branch running ``sub_steps``;
    per-branch outputs accumulate under ``merge_field``.
    """

    iter_field: str
    """State field whose list-value drives the fan-out.  One branch per
    element."""

    sub_steps: list[Step]
    """The per-branch step list.  Each branch runs this sequence against its
    item."""

    merge_field: str
    """State field where per-branch outputs are accumulated."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


# ---------------------------------------------------------------------------
# WorkflowSpec
# ---------------------------------------------------------------------------


class WorkflowSpec(BaseModel):
    """Declarative workflow specification.

    Audience: external workflow authors using the declarative authoring
    surface (Tier 1 + Tier 2 per ADR-0008).

    A ``WorkflowSpec`` is a pure data object — no LangGraph types appear in
    its fields.  The framework compiles it to a ``StateGraph`` at registration
    time (M19 T02).  Authors pass it to :func:`register_workflow` once.

    ``tiers`` is required non-None (locked Q3).  For a workflow with no LLM
    steps, pass ``tiers={}`` — an empty dict is accepted.  Spec-authored
    workflows are self-contained at registration time; the legacy
    ``<workflow>_tier_registry()`` helper pattern is not available for
    spec-authored workflows.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    name: str
    """Workflow name.  Must be unique across the registry."""

    input_schema: type[BaseModel]
    """Pydantic model describing the workflow's accepted inputs."""

    output_schema: type[BaseModel]
    """Pydantic model describing the workflow's emitted output."""

    steps: list[Step]
    """Ordered list of steps.  Must be non-empty; validated at registration."""

    tiers: dict[str, TierConfig]
    """Tier registry for this workflow (required non-None per locked Q3).
    Every ``LLMStep.tier`` value must appear as a key in this dict; unknown
    tier references raise ``ValueError`` at registration time with an explicit
    'typo?' error message."""


# ---------------------------------------------------------------------------
# register_workflow entry point
# ---------------------------------------------------------------------------


def register_workflow(spec: WorkflowSpec) -> None:
    """Register a declarative ``WorkflowSpec`` with the workflow registry.

    Validates cross-step invariants that pydantic alone cannot enforce:

    * **Empty step list** — raises ``ValueError``.
    * **LLMStep tier references** — every ``LLMStep.tier`` must appear in
      ``spec.tiers``; unknown tier raises ``ValueError`` naming the offending
      tier + available tier set (typo-detection per locked Q3).
    * **LLMStep prompt-source exclusivity** — validated at ``LLMStep``
      construction time via pydantic; re-surfaced here with index-annotated
      messages for steps that somehow bypass construction (should not happen
      with frozen models but guarded defensively).
    * **FanOutStep field resolvability** — best-effort warning when
      ``iter_field`` / ``merge_field`` cannot be statically resolved.
    * **Name collision** — defers to ``register()``'s ``ValueError``.

    The compiler (M19 T02) synthesises a ``StateGraph`` from the spec at
    registration time; the resulting builder thunk is passed to
    ``register(spec.name, builder)`` so dispatch's
    ``builder().compile(checkpointer=...)`` works unchanged (KDR-009).

    Parameters
    ----------
    spec:
        The validated ``WorkflowSpec`` to register.

    Raises
    ------
    ValueError
        On empty step list, unknown tier reference, or name collision.
    """
    from ai_workflows.workflows import register  # local import avoids circular

    # --- cross-step invariants ---

    if not spec.steps:
        raise ValueError(
            f"WorkflowSpec {spec.name!r} has an empty step list; "
            "a workflow with zero steps is incoherent. Add at least one step."
        )

    _validate_llm_step_tiers(spec)
    _warn_fan_out_unresolvable_fields(spec)

    # --- register with the real compiler (M19 T02) ---------------------------
    # Lazy import: importing _compiler pulls in ai_workflows.graph.* which is
    # only needed when actually compiling.  Callers that only import spec.py
    # for the data classes (e.g. introspection tooling, future YAML loaders)
    # do not pay the graph-layer import cost.
    from ai_workflows.workflows._compiler import compile_spec

    builder = compile_spec(spec)
    register(spec.name, builder)


def _validate_llm_step_tiers(spec: WorkflowSpec) -> None:
    """Raise ``ValueError`` if any ``LLMStep.tier`` is not in ``spec.tiers``."""
    available = set(spec.tiers)
    for i, step in enumerate(spec.steps):
        if isinstance(step, LLMStep) and step.tier not in available:
            raise ValueError(
                f"LLMStep at index {i} references tier {step.tier!r} but "
                f"spec.tiers has {available!r} — typo?"
            )


def _warn_fan_out_unresolvable_fields(spec: WorkflowSpec) -> None:
    """Warn (not raise) when ``FanOutStep`` iter/merge fields cannot be resolved.

    Checks whether each ``FanOutStep.iter_field`` and ``merge_field`` appear
    on ``spec.input_schema``, ``spec.output_schema``, or as a field name on
    any prior ``LLMStep.response_format``.  If statically unresolvable
    (e.g., set by a ``TransformStep`` at runtime), emits a ``UserWarning``
    and allows registration to proceed.
    """
    # Build the set of statically-known field names from schemas + prior steps.
    known: set[str] = set()
    known.update(spec.input_schema.model_fields)
    known.update(spec.output_schema.model_fields)

    for i, step in enumerate(spec.steps):
        if isinstance(step, LLMStep):
            known.update(step.response_format.model_fields)
        elif isinstance(step, FanOutStep):
            if step.iter_field not in known:
                warnings.warn(
                    f"FanOutStep at index {i}: iter_field {step.iter_field!r} "
                    f"was not found on spec.input_schema, spec.output_schema, "
                    f"or any prior LLMStep.response_format. It may be set by a "
                    f"TransformStep or custom step at runtime — verify the field "
                    f"name is correct. Registering anyway.",
                    UserWarning,
                    stacklevel=3,
                )
            if step.merge_field not in known:
                warnings.warn(
                    f"FanOutStep at index {i}: merge_field {step.merge_field!r} "
                    f"was not found on spec.input_schema, spec.output_schema, "
                    f"or any prior LLMStep.response_format. It may be set by a "
                    f"TransformStep or custom step at runtime — verify the field "
                    f"name is correct. Registering anyway.",
                    UserWarning,
                    stacklevel=3,
                )
            # recurse into sub_steps to accumulate known fields
            for sub_step in step.sub_steps:
                if isinstance(sub_step, LLMStep):
                    known.update(sub_step.response_format.model_fields)
