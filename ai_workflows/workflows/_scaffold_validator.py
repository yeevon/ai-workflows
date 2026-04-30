"""Validator for the scaffold_workflow output schema (M17 Task 01).

Separate module because the validation rules are load-bearing and testable
in isolation from the main workflow graph.  The paired ``ValidatorNode`` in
``scaffold_workflow.py`` wraps :func:`validate_scaffold_output`; on failure
the ``RetryingEdge`` drives a second LLM attempt (KDR-006 three-bucket retry).

Relationship to other modules
------------------------------
* :mod:`ai_workflows.workflows.scaffold_workflow` — imports the validator
  function and the ``ScaffoldedWorkflow`` model.
* ADR-0010 (T03 of this milestone) — records the explicit non-goal of
  linting or testing user-generated code.  This validator checks **only**
  that ``spec_python`` (a) parses as Python AST, (b) contains at least one
  top-level ``register_workflow(...)`` call, and (c) exceeds the minimum
  non-trivial length floor.  Everything beyond syntax + call presence is the
  user's responsibility.

Why ``register_workflow``, not ``register``
--------------------------------------------
The scaffold targets the post-M19 declarative authoring surface.
``register_workflow(spec)`` is the primary entry point; ``register(name,
build_fn)`` is the Tier-4 escape hatch not surfaced to generated code.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai_workflows.workflows.scaffold_workflow import ScaffoldedWorkflow

__all__ = ["ScaffoldOutputValidationError", "validate_scaffold_output"]

# Minimum non-trivial source length.  80 chars is a heuristic — it rejects
# empty or placeholder emits while accepting the smallest realistic
# WorkflowSpec + register_workflow(...) combination.  Tunable at T02 after
# prompt iteration; the constant and the test fixture move in lockstep
# (see task_01 carry-over note).
_MIN_SOURCE_LENGTH = 80


class ScaffoldOutputValidationError(ValueError):
    """Raised when ScaffoldedWorkflow output fails schema checks."""


def validate_scaffold_output(output: ScaffoldedWorkflow) -> None:
    """Raise if output is not a valid scaffolded workflow spec.

    Checks:
      1. ``spec_python`` parses via ``ast.parse()`` (syntax-valid).
      2. The AST contains at least one top-level ``Call`` node whose
         ``func`` name is ``"register_workflow"``.  The argument may be a
         ``Name`` reference (e.g. ``register_workflow(_SPEC)``) or a direct
         ``Call``/constant — any form is accepted; the validator does not
         resolve bindings.
      3. The ``spec_python`` length is non-trivial (>= 80 chars —
         catches empty / placeholder emits; tune at T02 post-smoke).

    Returns ``None`` on success; raises :class:`ScaffoldOutputValidationError`
    with a descriptive message on failure.
    """
    source = output.spec_python

    # Check 3 first — cheap, avoids unnecessary parse.
    if len(source) < _MIN_SOURCE_LENGTH:
        raise ScaffoldOutputValidationError(
            f"spec_python is too short ({len(source)} chars < {_MIN_SOURCE_LENGTH} "
            "minimum); the output looks like a placeholder rather than a real workflow."
        )

    # Check 1 — syntax validity.
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ScaffoldOutputValidationError(
            f"spec_python is not valid Python: {exc}"
        ) from exc

    # Check 2 — at least one top-level register_workflow(...) call.
    found = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Direct name: register_workflow(...)
        if isinstance(func, ast.Name) and func.id == "register_workflow":
            found = True
            break
        # Attribute access: some_module.register_workflow(...)
        if isinstance(func, ast.Attribute) and func.attr == "register_workflow":
            found = True
            break

    if not found:
        raise ScaffoldOutputValidationError(
            "spec_python does not contain a register_workflow(...) call. "
            "The generated file must call register_workflow(spec) at module top level "
            "so ai-workflows can discover it at startup."
        )
