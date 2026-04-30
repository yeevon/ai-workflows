"""Prompt template for the scaffold_workflow synthesis node (M17 Task 02).

Separate module so the prompt text can be iterated without touching
the graph wiring in ``scaffold_workflow.py``.  T02 replaces the T01
placeholder with a production-quality prompt that teaches Claude Opus the
full ``WorkflowSpec`` + ``register_workflow`` contract, the four-layer
module boundary, and tier-naming conventions.

Relationship to other modules
------------------------------
* :mod:`ai_workflows.workflows.scaffold_workflow` — sole caller.
  Renders the template via :func:`render_scaffold_prompt`.
"""

from __future__ import annotations

__all__ = ["SCAFFOLD_PROMPT_TEMPLATE", "render_scaffold_prompt"]


SCAFFOLD_PROMPT_TEMPLATE = """\
You are an expert ai-workflows workflow author.  Your task is to generate a \
complete, runnable Python workflow module that a user can load into \
ai-workflows via the ``AIW_EXTRA_WORKFLOW_MODULES`` environment variable.

## Architecture contract (four-layer rule)

ai-workflows has four layers: ``primitives → graph → workflows → surfaces``.
The file you generate is a *user-owned* module that lives **outside** the \
``ai_workflows/`` package — never inside it.  It imports only from \
``ai_workflows.workflows`` (the public authoring surface).

## WorkflowSpec API

``WorkflowSpec`` is the declarative authoring surface.  Import everything \
from ``ai_workflows.workflows``:

```python
from ai_workflows.workflows import (
    WorkflowSpec,
    LLMStep,
    ValidateStep,
    register_workflow,
    RetryPolicy,
)
from ai_workflows.primitives.tiers import TierConfig, LiteLLMRoute
from pydantic import BaseModel
```

**WorkflowSpec fields** (all required unless noted):

| Field | Type | Purpose |
|---|---|---|
| ``name`` | ``str`` | Unique snake_case workflow name |
| ``input_schema`` | ``type[BaseModel]`` | Pydantic model for the caller's inputs |
| ``output_schema`` | ``type[BaseModel]`` | Pydantic model for the LLM's output |
| ``steps`` | ``list[Step]`` | Ordered list of steps — must be non-empty |
| ``tiers`` | ``dict[str, TierConfig]`` | Tier registry; ``LLMStep.tier`` names must match keys |

## Step types

**LLMStep** — routes to an LLM tier:
```python
LLMStep(
    tier="my-llm",            # must match a key in WorkflowSpec.tiers
    prompt_template=(
        "Summarise {{text}} in {{max_words}} words.\\n"
        "Return JSON matching the MyOutput schema."
    ),
    response_format=MyOutput,  # the pydantic output model
    retry=RetryPolicy(
        max_transient_attempts=3,
        max_semantic_attempts=2,
        transient_backoff_base_s=0.5,
        transient_backoff_max_s=4.0,
    ),
)
```

**ValidateStep** — validates a field from the previous step (KDR-004 \
pairing convention):
```python
ValidateStep(target_field="my_field", schema=MyOutput)
```

## Tier naming convention

Tier names are kebab-case strings that identify the *role* of the call, \
not the model name.  Examples: ``"summarize-llm"``, ``"question-gen-llm"``, \
``"refactor-synth"``.

Define each tier in the ``tiers`` dict:
```python
from ai_workflows.primitives.tiers import TierConfig, LiteLLMRoute

_TIERS = {{
    "question-gen-llm": TierConfig(
        name="question-gen-llm",
        route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
        max_concurrency=2,
        per_call_timeout_s=120,
    ),
}}
```

## Four-layer contract for generated code

The generated module:
1. Lives outside ``ai_workflows/`` — it is user-owned code.
2. Imports from ``ai_workflows.workflows`` (public authoring surface) only.
3. Calls ``register_workflow(_SPEC)`` at module top level — exactly once.
4. Does NOT import from ``ai_workflows.graph`` or \
``ai_workflows.primitives`` except for ``TierConfig`` / ``LiteLLMRoute`` \
(which are re-exported from ``ai_workflows.workflows`` in future releases; \
direct import from ``ai_workflows.primitives.tiers`` is acceptable today).

## Canonical minimal example

```python
from __future__ import annotations
from pydantic import BaseModel
from ai_workflows.workflows import (
    LLMStep, ValidateStep, WorkflowSpec, RetryPolicy, register_workflow,
)
from ai_workflows.primitives.tiers import TierConfig, LiteLLMRoute


class MyInput(BaseModel):
    text: str
    max_words: int = 200


class MyOutput(BaseModel):
    result: str


_TIERS = {{
    "my-llm": TierConfig(
        name="my-llm",
        route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
        max_concurrency=2,
        per_call_timeout_s=120,
    ),
}}

_SPEC = WorkflowSpec(
    name="my_workflow",
    input_schema=MyInput,
    output_schema=MyOutput,
    tiers=_TIERS,
    steps=[
        LLMStep(
            tier="my-llm",
            prompt_template=(
                "Process the following text in at most {{max_words}} words.\\n"
                "Text: {{text}}\\n"
                "Return JSON matching the MyOutput schema."
            ),
            response_format=MyOutput,
            retry=RetryPolicy(
                max_transient_attempts=3,
                max_semantic_attempts=2,
                transient_backoff_base_s=0.5,
                transient_backoff_max_s=4.0,
            ),
        ),
        ValidateStep(target_field="result", schema=MyOutput),
    ],
)

register_workflow(_SPEC)
```

## Output format

Respond with a JSON object matching this exact schema — no markdown fences, \
no preamble, just the JSON:
{{
  "name": "<snake_case workflow name>",
  "spec_python": "<full .py file content as a string — valid Python>",
  "description": "<one-sentence description of what the workflow does>",
  "reasoning": "<brief explanation of design choices, tier selection, step sequence>"
}}

Important rules for ``spec_python``:
- Must be at least 200 characters long.
- Must parse as valid Python (no syntax errors).
- Must contain exactly one top-level ``register_workflow(_SPEC)`` call.
- Must define ``_SPEC = WorkflowSpec(...)`` before calling ``register_workflow``.
- The ``steps`` list must be non-empty — at least one ``LLMStep``.
- Every ``LLMStep.tier`` name must appear as a key in ``_SPEC.tiers``.
- Escape all ``{{`` and ``}}`` inside ``prompt_template`` strings as \
``{{{{`` and ``}}}}`` respectively (because ``prompt_template`` uses \
Python ``.format()`` interpolation at runtime).

User goal: {goal}
Target file: {target_path}
{existing_context_section}

Generate the complete workflow Python file for the user's goal above.
"""

_EXISTING_CONTEXT_SECTION_TEMPLATE = """\
Existing workflow to mimic (shape reference):
{existing_workflow_context}
"""


def render_scaffold_prompt(
    *,
    goal: str,
    target_path: str,
    existing_workflow_context: str | None,
) -> str:
    """Render the scaffold system prompt from the user's inputs.

    Parameters
    ----------
    goal:
        The user's natural-language description of the workflow to generate.
    target_path:
        The absolute target path the generated file will be written to.
    existing_workflow_context:
        Optional — if the user wants the scaffold to mimic an existing
        workflow's shape, pass its content here.

    Returns
    -------
    The rendered prompt string ready to pass to the LLM node.
    """
    if existing_workflow_context:
        ctx = _EXISTING_CONTEXT_SECTION_TEMPLATE.format(
            existing_workflow_context=existing_workflow_context
        )
    else:
        ctx = ""

    return SCAFFOLD_PROMPT_TEMPLATE.format(
        goal=goal,
        target_path=target_path,
        existing_context_section=ctx,
    )
