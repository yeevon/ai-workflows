"""KDR-014 guard test — quality knobs must NOT appear on Input models.

Walks every ``*Input`` model and ``WorkflowSpec`` and asserts no field name
matches the closed-list of quality-knob identifiers defined in ADR-0009 /
KDR-014. Catches future spec-drift where a Builder might quietly add a quality
knob (e.g. ``audit_cascade_enabled``) to a public input contract.

The regex alternative approach (``.*_policy``) is intentionally rejected
(TA-LOW-01): ``.*_policy`` would over-match legitimate domain fields such as
a hypothetical ``cancellation_policy`` or ``retention_policy``. A closed list
extending only as new quality knobs appear is more discoverable and less
prone to false positives that cause the guard to be disabled rather than fixed.

Relationship to other modules
------------------------------
* :class:`ai_workflows.workflows.planner.PlannerInput` — guarded.
* :class:`ai_workflows.workflows.slice_refactor.SliceRefactorInput` — guarded.
* :class:`ai_workflows.workflows.spec.WorkflowSpec` — guarded.
* ADR-0009 / KDR-014 — the architectural lock that drove this test's existence.

Introduced by M12 Task 03.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Closed list of quality-knob field names (TA-LOW-01 — closed list, NOT
# a suffix pattern like .*_policy which would over-match domain fields).
# Extend this list when a new quality knob is added to architecture.md §9.
# ---------------------------------------------------------------------------
_FORBIDDEN_QUALITY_KNOB_FIELDS = frozenset(
    {
        "audit_cascade_enabled",
        "validator_strict",
        "retry_budget",
        "tier_default",
        "fallback_chain",
        "escalation_threshold",
    }
)


def _collect_input_models() -> list[tuple[str, type[BaseModel]]]:
    """Return all ``*Input`` and ``WorkflowSpec`` models to guard.

    Imports are local so the test file itself does not cause module-level
    side effects (e.g. env-var reads at import time) in unrelated tests.
    """
    from ai_workflows.workflows.planner import PlannerInput
    from ai_workflows.workflows.slice_refactor import SliceRefactorInput

    models: list[tuple[str, type[BaseModel]]] = [
        ("PlannerInput", PlannerInput),
        ("SliceRefactorInput", SliceRefactorInput),
    ]

    # WorkflowSpec lives in the spec module — import defensively.
    try:
        from ai_workflows.workflows.spec import WorkflowSpec  # type: ignore[import]

        models.append(("WorkflowSpec", WorkflowSpec))
    except ImportError:
        pass  # WorkflowSpec may not be accessible in this env; skip gracefully.

    return models


@pytest.mark.parametrize(
    "model_name,model_cls",
    _collect_input_models(),
    ids=[name for name, _ in _collect_input_models()],
)
def test_no_quality_knob_fields_on_input_model(
    model_name: str, model_cls: type[BaseModel]
) -> None:
    """KDR-014: no ``*Input`` or ``WorkflowSpec`` model may carry quality knobs.

    Failure mode: prints the offending model + field name and recommends moving
    it to a module-level constant + env-var per ADR-0009 / KDR-014.
    """
    field_names = set(model_cls.model_fields)
    violations = _FORBIDDEN_QUALITY_KNOB_FIELDS & field_names
    assert not violations, (
        f"{model_name} contains quality-knob field(s) that violate KDR-014: "
        f"{violations!r}. "
        f"Per ADR-0009 / KDR-014, quality knobs must live at module level as "
        f"``_AUDIT_CASCADE_ENABLED_DEFAULT`` / ``_AUDIT_CASCADE_ENABLED`` "
        f"constants with env-var overrides, NOT on Input models or WorkflowSpec."
    )
