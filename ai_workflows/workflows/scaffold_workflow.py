"""scaffold_workflow — meta-workflow that generates other workflows (M17 Task 01).

This workflow accepts a natural-language goal and a target file path, uses an
LLM (Claude Opus via OAuth subprocess, the ``scaffold-synth`` tier) to generate
a ``WorkflowSpec``-based Python workflow file, validates the output, pauses at a
``HumanGate`` for code review, and on approval atomically writes the file to disk.

The scaffold's *own* graph uses the Tier-4 ``register()`` escape hatch (imperative
pattern, same as ``planner`` and ``slice_refactor``).  The code it *generates*
uses ``register_workflow(spec)`` — the primary post-M19 declarative authoring
surface.  Users never need to touch ``TieredNode``, ``ValidatorNode``, or
``StateGraph`` directly; the scaffold abstracts that away.

Relationship to other modules
------------------------------
* :mod:`ai_workflows.workflows` — self-registers via module-top
  ``register("scaffold_workflow", build_scaffold_workflow)`` call.
* :mod:`ai_workflows.workflows._scaffold_write_safety` — write-safety guards
  (path validation, atomic write) kept separate for isolated testing.
* :mod:`ai_workflows.workflows._scaffold_validator` — AST-level output
  validator.  The ``ValidatorNode`` immediately downstream of the synthesis
  node wraps it per KDR-004.
* :mod:`ai_workflows.workflows.scaffold_workflow_prompt` — prompt template
  iterated at T02 without touching the graph wiring.
* :mod:`ai_workflows.workflows._dispatch` — resolves ``scaffold_workflow_tier_registry``
  by convention (``<workflow_name>_tier_registry()``) at dispatch time.
* M16 external load path (``AIW_EXTRA_WORKFLOW_MODULES``) — the files this
  workflow generates are loaded via that env-var.
* ADR-0010 (T03) — records the risk-ownership framing: generated code is the
  user's; the scaffold validates schema only, not safety.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field, model_validator

from ai_workflows.graph.error_handler import wrap_with_error_handler
from ai_workflows.graph.human_gate import human_gate
from ai_workflows.graph.retrying_edge import retrying_edge
from ai_workflows.graph.tiered_node import tiered_node
from ai_workflows.primitives.retry import RetryPolicy
from ai_workflows.primitives.tiers import ClaudeCodeRoute, TierConfig
from ai_workflows.workflows import register
from ai_workflows.workflows._scaffold_validator import (
    ScaffoldOutputValidationError,
    validate_scaffold_output,
)
from ai_workflows.workflows._scaffold_write_safety import (
    TargetDirectoryNotWritableError,
    TargetExistsError,
    TargetInsideInstalledPackageError,
    TargetRelativePathError,
    atomic_write,
    validate_target_path,
)
from ai_workflows.workflows.scaffold_workflow_prompt import render_scaffold_prompt

__all__ = [
    "TERMINAL_GATE_ID",
    "FINAL_STATE_KEY",
    "ScaffoldWorkflowInput",
    "ScaffoldedWorkflow",
    "WriteOutcome",
    "ScaffoldState",
    "build_scaffold_workflow",
    "scaffold_workflow_tier_registry",
    "initial_state",
]

TERMINAL_GATE_ID = "scaffold_review"
"""Gate id for the strict-review ``HumanGate`` this workflow pauses at.

Exposed so :mod:`ai_workflows.workflows._dispatch` can discover the
resumed-response state key (``f"gate_{TERMINAL_GATE_ID}_response"``)
without hardcoding the scaffold's id.
"""

FINAL_STATE_KEY = "write_outcome"
"""State key dispatch reads to detect a completed scaffold run."""

SCAFFOLD_RETRY_POLICY = RetryPolicy(
    max_transient_attempts=3,
    max_semantic_attempts=2,
    transient_backoff_base_s=0.5,
    transient_backoff_max_s=4.0,
)
"""Retry budget for the scaffold synthesis node."""


# ---------------------------------------------------------------------------
# Input / output pydantic models
# ---------------------------------------------------------------------------


class ScaffoldWorkflowInput(BaseModel):
    """Caller-supplied scaffolding request.

    ``goal`` is the natural-language description of the workflow to generate.
    ``target_path`` is the absolute filesystem path where the ``.py`` file
    will be written.  ``force`` allows overwriting an existing file.
    ``existing_workflow_context`` is an optional hint: if the user wants the
    scaffold to mimic an existing workflow's shape, they paste its source here.

    Per KDR-014, quality knobs (tier preferences) live in module constants
    or per-call ``--tier-override`` flags — not on the input model.
    """

    goal: str = Field(min_length=1, max_length=4000)
    target_path: Path
    force: bool = False
    existing_workflow_context: str | None = None

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _validate_path_is_absolute(self) -> ScaffoldWorkflowInput:
        """Reject relative target paths at model-validation time."""
        if not self.target_path.is_absolute():
            raise ValueError(
                f"target_path must be absolute; got {self.target_path!r}"
            )
        return self


class ScaffoldedWorkflow(BaseModel):
    """LLM output schema — the generated workflow source.

    ``spec_python`` is the full content of the generated ``.py`` file —
    a ``WorkflowSpec`` definition + ``register_workflow(spec)`` call.
    The ``ValidatorNode`` checks this via :func:`validate_scaffold_output`.

    Note: ``declared_tiers`` and ``requires_human_gate`` were intentionally
    dropped — the ``WorkflowSpec`` carries its own ``tiers`` dict; the
    generated code is always reviewed at the ``HumanGate`` regardless.
    """

    name: str = Field(min_length=1)
    spec_python: str = Field(min_length=1)
    description: str = Field(min_length=1)
    reasoning: str = Field(min_length=1)

    model_config = {"extra": "forbid"}


class WriteOutcome(BaseModel):
    """Terminal artifact: path + SHA256 of the written file."""

    target_path: Path
    sha256: str


# ---------------------------------------------------------------------------
# Graph state
# ---------------------------------------------------------------------------


class ScaffoldState(TypedDict, total=False):
    """State carried through the compiled scaffold graph.

    ``synthesize_source_output`` is the raw LLM text written by the
    ``TieredNode`` named ``"synthesize_source"`` — the naming convention is
    ``f"{node_name}_output"`` per :mod:`ai_workflows.graph.tiered_node`.
    """

    run_id: str
    input: ScaffoldWorkflowInput
    # Raw LLM output text from the synthesis node (tiered_node convention:
    # f"{node_name}_output" → "synthesize_source_output")
    synthesize_source_output: str
    synthesize_source_output_revision_hint: Any
    # Validated scaffold object
    scaffolded_workflow: ScaffoldedWorkflow
    # Terminal artifact (after write)
    write_outcome: WriteOutcome
    # Gate response
    gate_scaffold_review_response: str
    # Three-bucket retry slots (KDR-006)
    last_exception: Any
    _retry_counts: dict[str, int]
    _non_retryable_failures: int
    _mid_run_tier_overrides: dict[str, str]


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def _synth_prompt(state: ScaffoldState) -> tuple[str, list[dict[str, str]]]:
    """Build the synthesis node's (system, messages) prompt from scaffold input."""
    inp = state["input"]
    system = render_scaffold_prompt(
        goal=inp.goal,
        target_path=str(inp.target_path),
        existing_workflow_context=inp.existing_workflow_context,
    )
    revision_hint = state.get("synthesize_source_output_revision_hint")
    user_parts = [f"Goal: {inp.goal}"]
    if revision_hint:
        user_parts.append(
            f"\nPrevious attempt failed validation:\n{revision_hint}\n"
            "Please fix the issue and regenerate the complete workflow."
        )
    return system, [{"role": "user", "content": "\n".join(user_parts)}]


# ---------------------------------------------------------------------------
# Custom validator node that calls validate_scaffold_output
# ---------------------------------------------------------------------------


def _make_scaffold_validator_node() -> Any:
    """Return an async LangGraph node that validates the scaffold LLM output.

    Reads ``synthesize_source_output`` (the raw text key written by
    ``tiered_node(node_name="synthesize_source")``), pydantic-parses it into
    :class:`ScaffoldedWorkflow`, then calls :func:`validate_scaffold_output`
    for the AST + ``register_workflow`` checks.

    On failure raises ``RetryableSemantic`` so ``retrying_edge`` loops back to
    the synthesis node (KDR-004 + KDR-006).  On exhaustion escalates to
    ``NonRetryable``.
    """
    from ai_workflows.primitives.retry import NonRetryable, RetryableSemantic

    async def _node(
        state: ScaffoldState,
        config: RunnableConfig,
    ) -> dict[str, Any]:
        # Count how many semantic retries have fired so far under this node.
        retry_counts: dict = state.get("_retry_counts") or {}
        attempt = retry_counts.get("scaffold_validator", 0)
        max_semantic = SCAFFOLD_RETRY_POLICY.max_semantic_attempts

        # tiered_node(node_name="synthesize_source") writes to
        # "synthesize_source_output" per the f"{node_name}_output" convention.
        raw: str = state.get("synthesize_source_output", "")

        # Attempt pydantic parse first.
        try:
            parsed = ScaffoldedWorkflow.model_validate_json(raw)
        except Exception as exc:
            hint = f"Output was not valid ScaffoldedWorkflow JSON: {exc}"
            if attempt >= max_semantic - 1:
                raise NonRetryable(hint) from exc
            raise RetryableSemantic(
                reason="scaffold_validator: output failed ScaffoldedWorkflow validation",
                revision_hint=hint,
            ) from exc

        # Then run the AST + register_workflow check.
        try:
            validate_scaffold_output(parsed)
        except ScaffoldOutputValidationError as exc:
            hint = str(exc)
            if attempt >= max_semantic - 1:
                raise NonRetryable(hint) from exc
            raise RetryableSemantic(
                reason="scaffold_validator: spec_python failed AST validation",
                revision_hint=hint,
            ) from exc

        return {
            "scaffolded_workflow": parsed,
            "synthesize_source_output_revision_hint": None,
            "last_exception": None,
        }

    return _node


# ---------------------------------------------------------------------------
# Write node
# ---------------------------------------------------------------------------


async def _write_to_disk(
    state: ScaffoldState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Write the scaffolded source to disk on gate approval.

    If the gate was rejected, returns an empty dict (no write).
    If the write-safety guard trips (e.g. target inside installed package),
    surfaces the error via ``last_exception`` so dispatch detects the failure.
    """
    response = state.get("gate_scaffold_review_response")
    if response != "approved":
        return {}

    inp = state["input"]
    scaffolded = state["scaffolded_workflow"]

    try:
        resolved = validate_target_path(inp.target_path, force=inp.force)
        sha256 = atomic_write(resolved, scaffolded.spec_python)
    except (
        TargetInsideInstalledPackageError,
        TargetDirectoryNotWritableError,
        TargetExistsError,
        TargetRelativePathError,
        OSError,
    ) as exc:
        from ai_workflows.primitives.retry import NonRetryable
        raise NonRetryable(str(exc)) from exc

    outcome = WriteOutcome(target_path=resolved, sha256=sha256)

    # Persist the write outcome as a storage artifact.
    storage = config["configurable"]["storage"]
    run_id = state["run_id"]
    await storage.write_artifact(run_id, "write_outcome", outcome.model_dump_json())

    return {"write_outcome": outcome}


# ---------------------------------------------------------------------------
# Graph factory
# ---------------------------------------------------------------------------


def build_scaffold_workflow() -> StateGraph:
    """Return the uncompiled scaffold_workflow ``StateGraph``.

    Graph shape:

    ``START → validate_input → synthesize_source → scaffold_validator
            → preview_gate → write_to_disk → END``

    The ``retrying_edge`` after ``synthesize_source`` routes back to the
    synthesis node on transient/semantic failures; after ``scaffold_validator``
    it either loops back to the synthesis node or advances to the gate.
    KDR-004: the LLM synthesis node (``synthesize_source``) is paired with
    ``scaffold_validator`` immediately downstream.
    """
    policy = SCAFFOLD_RETRY_POLICY

    synth = wrap_with_error_handler(
        tiered_node(
            tier="scaffold-synth",
            prompt_fn=_synth_prompt,
            output_schema=ScaffoldedWorkflow,
            node_name="synthesize_source",
        ),
        node_name="synthesize_source",
    )

    scaffold_validator = wrap_with_error_handler(
        _make_scaffold_validator_node(),
        node_name="scaffold_validator",
    )

    gate = human_gate(
        gate_id=TERMINAL_GATE_ID,
        prompt_fn=lambda s: json.dumps(
            {
                "summary": (
                    f"Review generated workflow for goal: {s['input'].goal!r}. "
                    f"Target: {s['input'].target_path!s}"
                ),
                "spec_python": s["scaffolded_workflow"].spec_python,
                "target_path": str(s["input"].target_path),
                "name": s["scaffolded_workflow"].name,
                "description": s["scaffolded_workflow"].description,
            },
            indent=2,
        ),
        strict_review=True,
    )

    decide_after_synth = retrying_edge(
        on_transient="synthesize_source",
        on_semantic="synthesize_source",
        on_terminal="scaffold_validator",
        policy=policy,
    )
    decide_after_validator = retrying_edge(
        on_transient="synthesize_source",
        on_semantic="synthesize_source",
        on_terminal="preview_gate",
        policy=policy,
    )

    g: StateGraph = StateGraph(ScaffoldState)

    g.add_node("validate_input", _validate_input_node)
    g.add_node("synthesize_source", synth)
    g.add_node("scaffold_validator", scaffold_validator)
    g.add_node("preview_gate", gate)
    g.add_node("write_to_disk", _write_to_disk)

    g.add_edge(START, "validate_input")
    g.add_edge("validate_input", "synthesize_source")
    g.add_conditional_edges(
        "synthesize_source",
        decide_after_synth,
        ["synthesize_source", "scaffold_validator"],
    )
    g.add_conditional_edges(
        "scaffold_validator",
        decide_after_validator,
        ["synthesize_source", "preview_gate"],
    )
    g.add_edge("preview_gate", "write_to_disk")
    g.add_edge("write_to_disk", END)

    return g


# ---------------------------------------------------------------------------
# Input validation node
# ---------------------------------------------------------------------------


async def _validate_input_node(
    state: ScaffoldState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Validate the input model and run path safety checks early.

    Runs ``validate_target_path`` at the start of the run so the user sees
    path-safety errors before any LLM call fires.  Force=False check is
    deferred to the write node (after gate approval) to avoid blocking on
    an existing file the user might choose not to overwrite at gate time.
    """
    inp: ScaffoldWorkflowInput = state["input"]

    try:
        # Validate everything except the existing-file check (defer to write).
        # We create a temporary ScaffoldWorkflowInput with force=True so
        # validate_target_path does not trip on existing-file — the real
        # check happens at write time.
        validate_target_path(inp.target_path, force=True)
    except (
        TargetInsideInstalledPackageError,
        TargetDirectoryNotWritableError,
        TargetRelativePathError,
    ) as exc:
        from ai_workflows.primitives.retry import NonRetryable
        raise NonRetryable(str(exc)) from exc

    return {}


# ---------------------------------------------------------------------------
# initial_state hook (dispatch convention)
# ---------------------------------------------------------------------------


def initial_state(run_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Convention hook: construct the initial graph state for this workflow.

    Called by :func:`ai_workflows.workflows._dispatch._build_initial_state`
    when the workflow module exposes this symbol.
    """
    inp = ScaffoldWorkflowInput(**inputs)
    return {
        "run_id": run_id,
        "input": inp,
    }


# ---------------------------------------------------------------------------
# Tier registry (load-bearing function name — see KDR-014)
# ---------------------------------------------------------------------------


def scaffold_workflow_tier_registry() -> dict[str, TierConfig]:
    """Return the tier registry for the scaffold_workflow.

    Declares a single ``scaffold-synth`` tier routing to Claude Opus via the
    OAuth subprocess driver (KDR-003).  Matches ``planner-synth`` defaults:
    ``max_concurrency=1``, ``per_call_timeout_s=300``.

    **The function name ``scaffold_workflow_tier_registry`` is load-bearing.**
    :func:`ai_workflows.workflows._dispatch._resolve_tier_registry` looks up
    ``<workflow_name>_tier_registry()`` by convention at dispatch time.
    Renaming this function breaks dispatch silently.

    Per-call rebind: ``--tier-override scaffold-synth=<replacement>`` (CLI)
    or ``tier_overrides={"scaffold-synth": "<replacement>"}`` (MCP) per KDR-014.
    """
    return {
        "scaffold-synth": TierConfig(
            name="scaffold-synth",
            route=ClaudeCodeRoute(cli_model_flag="opus"),
            max_concurrency=1,
            per_call_timeout_s=300,
        ),
    }


# ---------------------------------------------------------------------------
# Module-top registration (Tier-4 escape hatch, imperative pattern)
# ---------------------------------------------------------------------------

register("scaffold_workflow", build_scaffold_workflow)
