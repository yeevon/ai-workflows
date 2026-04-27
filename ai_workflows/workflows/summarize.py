"""summarize — the M19 spec-API proof-point workflow.

Authored at M19 T04 to (a) prove the declarative spec API compiles +
dispatches + checkpoints + surfaces results end-to-end through both
``aiw run`` and ``aiw-mcp run_workflow``, and (b) provide a worked
example downstream consumers copy-paste from. The same code is the
literal source of ``docs/writing-a-workflow.md`` §Worked example
(T05); when one changes, the other does.

Shape: single tier-routed LLM call (LLMStep) + a ValidateStep against
the output schema. Uses the simplest realistic spec — no GateStep, no
TransformStep, no FanOutStep — so an external author reading this
module sees the smallest viable spec rather than a large reference.

The ``ValidateStep`` after the ``LLMStep`` is illustrative — it shows
downstream consumers how to compose ``ValidateStep`` syntactically, but
in this exact configuration where its ``schema`` matches the upstream
``LLMStep.response_format``, it is a runtime no-op (the LLMStep's
paired validator already validated). T01's hermetic tests cover
``ValidateStep``'s test surface standalone
(``tests/workflows/test_spec.py`` exercises ``ValidateStep``
construction + cross-step invariants) and T02's compiler tests cover
its compile path
(``tests/workflows/test_compiler.py::test_compile_validate_step_emits_validator_node``).
M19's test surface for the step type is covered there, not here.

Per ADR-0008 + locked H2 (2026-04-26): this is the only in-tree
workflow on the spec API at 0.3.0. The legacy ``planner`` and
``slice_refactor`` workflows remain on the existing
``register(name, build_fn)`` escape hatch through 0.3.x; their
ports are forward-deferred per locked Q5 + H2 + the re-open
trigger captured in nice_to_have.md.

Relationship to other modules
------------------------------
* :mod:`ai_workflows.workflows` — re-exports the spec types this module
  imports; ``register_workflow`` wires this spec into the shared
  ``_REGISTRY`` at module load time.
* :mod:`ai_workflows.workflows.summarize_tiers` — companion module that
  houses the ``summarize_tier_registry()`` helper (TA-LOW-02 carry-over:
  split kept because no circular imports surfaced at implement time).
* :mod:`ai_workflows.workflows._compiler` — compiles ``_SPEC`` into a
  runnable ``StateGraph``; called transitively via ``register_workflow``.
* :mod:`ai_workflows.workflows._dispatch` — drives the compiled graph
  at invocation time; reads ``FINAL_STATE_KEY = "summary"`` from the
  synthetic module injected by the compiler (M19 T03 fix ensures this
  key round-trips through ``RunWorkflowOutput.artifact``).
"""

from __future__ import annotations

from pydantic import BaseModel

from ai_workflows.workflows import (
    LLMStep,
    RetryPolicy,  # re-exported from ai_workflows.primitives.retry per locked Q1
    ValidateStep,
    WorkflowSpec,
    register_workflow,
)
from ai_workflows.workflows.summarize_tiers import summarize_tier_registry


class SummarizeInput(BaseModel):
    """Input schema — the user's text + how aggressively to summarise."""

    text: str
    max_words: int


class SummarizeOutput(BaseModel):
    """Output schema — the LLM's summary.

    First field (``summary``) is the workflow's terminal artefact
    (``FINAL_STATE_KEY``). Per M19 T03: ``RunWorkflowOutput.artifact``
    will contain ``{"summary": "..."}`` after a completed dispatch.
    """

    summary: str


_SPEC = WorkflowSpec(
    name="summarize",
    input_schema=SummarizeInput,
    output_schema=SummarizeOutput,
    tiers=summarize_tier_registry(),
    steps=[
        LLMStep(
            tier="summarize-llm",
            prompt_template=(
                "Summarize the following text in at most {max_words} words. "
                "Respond with a JSON object matching the SummarizeOutput schema.\n\n"
                "Text:\n{text}"
            ),
            response_format=SummarizeOutput,
            retry=RetryPolicy(
                max_transient_attempts=3,
                max_semantic_attempts=2,
                transient_backoff_base_s=0.5,
                transient_backoff_max_s=4.0,
            ),
        ),
        ValidateStep(  # illustrative; runtime no-op when schema == upstream LLMStep.response_format
            target_field="summary",
            schema=SummarizeOutput,
        ),
    ],
)
"""Declarative spec for the summarize workflow.

``LLMStep`` exercises ``prompt_template`` Tier 1 sugar (locked Q2).
``ValidateStep`` is illustrative; in this exact configuration where its
``schema`` matches the upstream ``LLMStep.response_format``, it is a
runtime no-op (the LLMStep's paired validator already validated). The
composition is shown for syntactic illustration only. The
``RetryPolicy`` parameterisation uses the primitives' field names per
locked Q1.
"""


register_workflow(_SPEC)
