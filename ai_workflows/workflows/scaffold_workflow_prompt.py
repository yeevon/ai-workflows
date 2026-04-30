"""Prompt template for the scaffold_workflow synthesis node (M17 Task 01).

Separate module so the prompt text can be iterated at T02 without touching
the graph wiring in ``scaffold_workflow.py``.  T01 uses a placeholder prompt
that exercises the graph wiring with the stub adapter; T02 will replace this
with a production-quality prompt that teaches Claude Opus the full
``WorkflowSpec`` + ``register_workflow`` contract.

Relationship to other modules
------------------------------
* :mod:`ai_workflows.workflows.scaffold_workflow` — sole caller.
  Renders the template via :func:`render_scaffold_prompt`.
"""

from __future__ import annotations

__all__ = ["SCAFFOLD_PROMPT_TEMPLATE", "render_scaffold_prompt"]


SCAFFOLD_PROMPT_TEMPLATE = """\
You are an expert ai-workflows author.  Your job is to generate a Python \
workflow module that the user can drop into ai-workflows via the \
AIW_EXTRA_WORKFLOW_MODULES environment variable.

The generated file must:
1. Import and use ``WorkflowSpec``, ``LLMStep``, and ``register_workflow``
   from ``ai_workflows.workflows``.
2. Define an input pydantic model that matches the workflow's needs.
3. Define an output pydantic model for the LLM step.
4. Define a ``_SPEC = WorkflowSpec(...)`` object wiring the steps together.
5. Call ``register_workflow(_SPEC)`` at module top level.

The response must be a JSON object matching the ScaffoldedWorkflow schema:
{{
  "name": "<snake_case workflow name>",
  "spec_python": "<full .py file content as a string>",
  "description": "<one-sentence description of what the workflow does>",
  "reasoning": "<brief explanation of design choices>"
}}

User goal: {goal}
Target file: {target_path}
{existing_context_section}

Generate the complete Python file in ``spec_python``.  The file must parse \
as valid Python and contain a ``register_workflow(_SPEC)`` call.
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
        # Escape braces in user-supplied context before .format() so that Python
        # source containing dict literals, f-strings, or format strings does not
        # raise KeyError / IndexError when interpolated into the template.
        safe_ctx = existing_workflow_context.replace("{", "{{").replace("}", "}}")
        ctx = _EXISTING_CONTEXT_SECTION_TEMPLATE.format(
            existing_workflow_context=safe_ctx
        )
    else:
        ctx = ""

    # Escape braces in user-supplied goal and target_path for the same reason.
    safe_goal = goal.replace("{", "{{").replace("}", "}}")
    safe_target_path = target_path.replace("{", "{{").replace("}", "}}")
    return SCAFFOLD_PROMPT_TEMPLATE.format(
        goal=safe_goal,
        target_path=safe_target_path,
        existing_context_section=ctx,
    )
