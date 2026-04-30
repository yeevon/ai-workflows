"""Graph-layer test for M12 Task 01: ``_mid_run_tier_overrides`` resolves
``auditor-sonnet`` / ``auditor-opus`` via the M8 T04 override channel.

Mirrors the override-precedence pattern from
``tests/graph/test_tiered_node_ollama_breaker.py`` (lines 480 / 517).

The ``_resolve_tier`` function is a module-level helper (leading underscore
is intentional — it is not in ``__all__`` but is documented as the
override-precedence surface, per its docstring and M8 T04 spec).

AC-5 from M12 Task 01 spec: the mid-run override channel resolves the new
auditor tiers by name (``_resolve_tier`` integration test passes).

Relationship to other modules
------------------------------
* :func:`ai_workflows.graph.tiered_node._resolve_tier` — the function
  under test; reads ``state["_mid_run_tier_overrides"]`` at precedence
  layer 1.
* ``tests/graph/test_tiered_node_ollama_breaker.py`` — sibling test that
  establishes the override-precedence contract for production tiers;
  this test applies the same check to the new auditor tiers.
"""

from __future__ import annotations

from ai_workflows.graph.tiered_node import _resolve_tier


def test_auditor_tiers_override_via_mid_run_channel() -> None:
    """AC-5: ``_mid_run_tier_overrides`` redirects ``auditor-sonnet`` to
    ``auditor-opus`` without touching the configurable dict.

    Stamps ``state = {"_mid_run_tier_overrides": {"auditor-sonnet": "auditor-opus"}}``
    and calls ``_resolve_tier("auditor-sonnet", state, configurable={})``.
    Asserts the return value is ``"auditor-opus"`` (the M8 T04 state-layer
    override applies unchanged to the new auditor tiers).
    """
    state = {"_mid_run_tier_overrides": {"auditor-sonnet": "auditor-opus"}}
    result = _resolve_tier("auditor-sonnet", state, configurable={})
    assert result == "auditor-opus"


def test_auditor_opus_override_via_mid_run_channel() -> None:
    """State-layer override works for ``auditor-opus`` as the logical key too."""
    state = {"_mid_run_tier_overrides": {"auditor-opus": "planner-synth"}}
    result = _resolve_tier("auditor-opus", state, configurable={})
    assert result == "planner-synth"


def test_auditor_sonnet_falls_through_to_identity_when_no_override() -> None:
    """Without an override, ``_resolve_tier`` returns the logical name unchanged."""
    state: dict = {}
    result = _resolve_tier("auditor-sonnet", state, configurable={})
    assert result == "auditor-sonnet"


def test_auditor_opus_falls_through_to_identity_when_no_override() -> None:
    """Without an override, ``_resolve_tier`` returns the logical name unchanged."""
    state: dict = {}
    result = _resolve_tier("auditor-opus", state, configurable={})
    assert result == "auditor-opus"
