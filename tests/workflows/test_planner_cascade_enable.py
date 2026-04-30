"""Workflow-layer tests for M12 Task 03 planner cascade opt-in.

Verifies the module-level ``_AUDIT_CASCADE_ENABLED`` constant + env-var
override pattern (ADR-0009 / KDR-014):

1. Disabled by default (no env vars set).
2. Enabled via the global ``AIW_AUDIT_CASCADE=1`` override.
3. Enabled via the per-workflow ``AIW_AUDIT_CASCADE_PLANNER=1`` override.
4. ``PlannerInput`` does NOT grow an ``audit_cascade_enabled`` field
   (KDR-014 regression guard).

Relationship to other modules
------------------------------
* :mod:`ai_workflows.workflows.planner` — the module under test.
* :mod:`ai_workflows.graph.audit_cascade` — the cascade primitive wired in
  when the constant is True.
* ``tests/workflows/test_slice_refactor_cascade_enable.py`` — the analogous
  tests for the ``slice_refactor`` workflow.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterator

import pytest

import ai_workflows.workflows as workflows
import ai_workflows.workflows.planner as planner_module

# ---------------------------------------------------------------------------
# Registry restore fixture — required because tests 1-3 call _reset_for_tests
# and reload the module, which would leave other tests without registrations.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _restore_registry() -> Iterator[None]:
    """Restore workflow registry + module dict after each reload-using test.

    Tests that call ``importlib.reload()`` re-execute the module's top-level
    code, which: (a) creates new class objects (``PlannerPlan``, etc.) that
    break ``isinstance()`` checks in sibling test files holding pre-reload
    references; (b) re-registers builders with new function-object identities
    that conflict with the registry.

    Strategy — full module ``__dict__`` snapshot:

    1. **Setup**: snapshot the planner module's ``__dict__`` and the registry,
       ensuring both companion modules are already in ``sys.modules`` so that
       the first-import side effect fires exactly once per session.
    2. **Teardown**: clear the registry, restore the module's ``__dict__``
       from the snapshot (this reinstates the original class objects so sibling
       tests' ``isinstance()`` checks stay valid), then re-register from the
       registry snapshot.

    Restoring ``__dict__`` is safe here because (a) modules are shared objects
    and (b) the snapshot is a shallow copy of primitive values + class/function
    references — there are no circular-ref or write-ahead-log concerns at this
    layer.
    """
    import copy
    import sys

    # Ensure companion module is in sys.modules before the test runs.
    import ai_workflows.workflows.slice_refactor  # noqa: F401  # side-effect import

    _planner_mod = sys.modules["ai_workflows.workflows.planner"]
    _sr_mod = sys.modules["ai_workflows.workflows.slice_refactor"]

    # Shallow-copy the module __dict__ (values are class/function refs — no
    # deep copy needed to preserve identity).
    planner_dict_snapshot = dict(_planner_mod.__dict__)
    sr_dict_snapshot = dict(_sr_mod.__dict__)
    registry_snapshot = copy.copy(workflows._REGISTRY)

    yield

    # Restore planner module state (reinstate pre-reload class objects).
    _planner_mod.__dict__.clear()
    _planner_mod.__dict__.update(planner_dict_snapshot)

    # Restore slice_refactor module state.
    _sr_mod.__dict__.clear()
    _sr_mod.__dict__.update(sr_dict_snapshot)

    # Restore registry to original builder function objects.
    workflows._reset_for_tests()
    for name, builder in registry_snapshot.items():
        workflows.register(name, builder)


# ---------------------------------------------------------------------------
# Test 1: disabled by default
# ---------------------------------------------------------------------------


def test_audit_cascade_disabled_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-1: ``_AUDIT_CASCADE_ENABLED`` is False when no env vars are set.

    Uses ``monkeypatch.delenv`` + ``importlib.reload`` to guarantee the module
    is evaluated with a clean environment regardless of test-run order
    (TA-LOW-02 — prevents flake when test #2 or #3 runs first in the same
    session).
    """
    monkeypatch.delenv("AIW_AUDIT_CASCADE", raising=False)
    monkeypatch.delenv("AIW_AUDIT_CASCADE_PLANNER", raising=False)
    workflows._reset_for_tests()
    importlib.reload(planner_module)

    assert planner_module._AUDIT_CASCADE_ENABLED_DEFAULT is False
    assert planner_module._AUDIT_CASCADE_ENABLED is False

    # Compile: graph must build and have the non-cascade explorer node shape
    # (explorer + explorer_validator nodes, no cascade sub-graph wrapper).
    g = planner_module.build_planner()
    compiled = g.compile()
    # Standard M11 shape has "explorer" and "explorer_validator" nodes.
    assert "explorer" in compiled.nodes, (
        "Disabled-default graph must contain 'explorer' node"
    )
    assert "explorer_validator" in compiled.nodes, (
        "Disabled-default graph must contain 'explorer_validator' node"
    )
    # 'cascade_bridge' is only added in the cascade path.
    assert "cascade_bridge" not in compiled.nodes, (
        "Disabled-default graph must NOT contain 'cascade_bridge' node "
        "(that node is only added when _AUDIT_CASCADE_ENABLED=True)"
    )


# ---------------------------------------------------------------------------
# Test 2: enabled via global env var
# ---------------------------------------------------------------------------


def test_audit_cascade_enabled_via_global_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-2: ``_AUDIT_CASCADE_ENABLED`` is True when ``AIW_AUDIT_CASCADE=1``.

    Sets the env var BEFORE reload so the module-import-time read picks it
    up honestly (same code path a downstream operator would trigger).
    """
    monkeypatch.setenv("AIW_AUDIT_CASCADE", "1")
    monkeypatch.delenv("AIW_AUDIT_CASCADE_PLANNER", raising=False)
    workflows._reset_for_tests()
    importlib.reload(planner_module)

    assert planner_module._AUDIT_CASCADE_ENABLED is True

    # Compile: cascade shape — the cascade sub-graph is embedded as the 'explorer'
    # node in the outer graph. LangGraph does not expose the inner sub-graph nodes
    # in the outer compiled.nodes; instead we verify the cascade by:
    # (a) The bridge node 'cascade_bridge' is present (only added in cascade path).
    # (b) The standalone 'explorer_validator' node is absent (replaced by cascade).
    g = planner_module.build_planner()
    compiled = g.compile()
    assert "cascade_bridge" in compiled.nodes, (
        "Enabled graph must contain 'cascade_bridge' node "
        "(cascade structural marker — only present when _AUDIT_CASCADE_ENABLED=True)"
    )
    # Standard explorer_validator must NOT be present (replaced by cascade).
    assert "explorer_validator" not in compiled.nodes, (
        "Enabled graph must NOT contain standalone 'explorer_validator' node "
        "(cascade path replaces it)"
    )


# ---------------------------------------------------------------------------
# Test 3: enabled via per-workflow env var
# ---------------------------------------------------------------------------


def test_audit_cascade_enabled_via_per_workflow_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-3: ``_AUDIT_CASCADE_ENABLED`` is True when ``AIW_AUDIT_CASCADE_PLANNER=1``.

    Uses only the per-workflow override (global not set). Asserts behaviour
    matches the global-env case (same compiled-graph structural marker).
    """
    monkeypatch.delenv("AIW_AUDIT_CASCADE", raising=False)
    monkeypatch.setenv("AIW_AUDIT_CASCADE_PLANNER", "1")
    workflows._reset_for_tests()
    importlib.reload(planner_module)

    assert planner_module._AUDIT_CASCADE_ENABLED is True

    g = planner_module.build_planner()
    compiled = g.compile()
    assert "cascade_bridge" in compiled.nodes, (
        "Per-workflow-env enabled graph must contain 'cascade_bridge' "
        "(cascade structural marker)"
    )
    assert "explorer_validator" not in compiled.nodes


# ---------------------------------------------------------------------------
# Test 4: PlannerInput unchanged at T03 (KDR-014 regression guard)
# ---------------------------------------------------------------------------


def test_planner_input_unchanged_at_t03() -> None:
    """AC-4 / KDR-014: ``PlannerInput.model_fields`` does NOT contain quality knobs.

    Guards against future spec-drift where a Builder might quietly add
    ``audit_cascade_enabled`` (or similar) to the public input contract.
    Per KDR-014, quality knobs belong at module level + env-var, not on
    ``*Input`` models.
    """
    from ai_workflows.workflows.planner import PlannerInput

    field_names = set(PlannerInput.model_fields)
    forbidden = {
        "audit_cascade_enabled",
        "validator_strict",
        "retry_budget",
        "tier_default",
        "fallback_chain",
        "escalation_threshold",
    }
    violations = forbidden & field_names
    assert not violations, (
        f"PlannerInput contains quality-knob field(s) that violate KDR-014: "
        f"{violations!r}. Move them to module-level constants + env-var per "
        f"ADR-0009."
    )


# ---------------------------------------------------------------------------
# Test 5: PlannerState declares all 9 cascade channels (AC-8 regression guard)
# ---------------------------------------------------------------------------


def test_planner_state_has_cascade_channels() -> None:
    """AC-8: ``PlannerState`` declares the closed list of 9 cascade channels.

    Uses ``get_type_hints`` to inspect the TypedDict annotation keys.
    Guards against a future Builder removing one of the 9 channel declarations
    from ``PlannerState`` — the cascade sub-graph writes into these channels
    and silently drops data if a key is absent.

    The channel list is the closed set expected by
    ``audit_cascade_node(name="planner_explorer_audit", ...)`` plus the two
    shared routing channels (``cascade_role``, ``cascade_transcript``).
    """
    from typing import get_type_hints

    from ai_workflows.workflows.planner import PlannerState

    hints = get_type_hints(PlannerState, include_extras=True)

    expected_cascade_channels = {
        "cascade_role",
        "cascade_transcript",
        "planner_explorer_audit_primary_output",
        "planner_explorer_audit_primary_parsed",
        "planner_explorer_audit_primary_output_revision_hint",
        "planner_explorer_audit_auditor_output",
        "planner_explorer_audit_auditor_output_revision_hint",
        "planner_explorer_audit_audit_verdict",
        "planner_explorer_audit_audit_exhausted_response",
    }

    for channel in expected_cascade_channels:
        assert channel in hints, (
            f"PlannerState must declare cascade channel '{channel}' "
            f"for the cascade sub-graph to write into it (AC-8). "
            f"Present keys: {sorted(hints)}"
        )
