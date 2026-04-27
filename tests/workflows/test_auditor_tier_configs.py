"""Workflow-layer tests for the M12 Task 01 auditor TierConfig registrations.

Verifies that ``auditor-sonnet`` and ``auditor-opus`` are present in every
workflow tier registry that is expected to expose them, with the correct
route shape, concurrency cap, and timeout (AC-1, AC-2, AC-4 from the
task spec).

Relationship to other modules
------------------------------
* :func:`ai_workflows.workflows.planner.planner_tier_registry` — the
  canonical source; ``slice_refactor_tier_registry`` composes it.
* :func:`ai_workflows.workflows.slice_refactor.slice_refactor_tier_registry`
  — inherits auditor tiers via ``dict(planner_tier_registry())``.
* :func:`ai_workflows.workflows.summarize_tiers.summarize_tier_registry`
  — declares auditor tiers directly (no planner composition).
* :mod:`ai_workflows.primitives.tiers` — ``ClaudeCodeRoute`` is the
  asserted route type.

See also: ``tests/workflows/test_planner_synth_claude_code.py`` for the
existing ``planner-synth`` shape test this file mirrors.
"""

from __future__ import annotations

from ai_workflows.primitives.tiers import ClaudeCodeRoute
from ai_workflows.workflows.planner import planner_tier_registry
from ai_workflows.workflows.slice_refactor import slice_refactor_tier_registry
from ai_workflows.workflows.summarize_tiers import summarize_tier_registry

# ---------------------------------------------------------------------------
# planner_tier_registry — auditor-sonnet
# ---------------------------------------------------------------------------


def test_auditor_sonnet_tier_resolves_to_cli_sonnet_in_planner() -> None:
    """AC-1: planner registry exposes ``auditor-sonnet`` with Sonnet CLI flag.

    Mirrors ``test_planner_synth_tier_points_at_claude_code_opus`` —
    isinstance narrowing required before accessing ``cli_model_flag``
    because ``route`` is a union type (``LiteLLMRoute | ClaudeCodeRoute``).
    """
    registry = planner_tier_registry()
    tier = registry["auditor-sonnet"]
    route = tier.route
    assert isinstance(route, ClaudeCodeRoute), (
        f"Expected ClaudeCodeRoute, got {type(route).__name__}"
    )
    assert route.kind == "claude_code"
    assert route.cli_model_flag == "sonnet"
    assert tier.max_concurrency == 1
    assert tier.per_call_timeout_s == 300


# ---------------------------------------------------------------------------
# planner_tier_registry — auditor-opus
# ---------------------------------------------------------------------------


def test_auditor_opus_tier_resolves_to_cli_opus_in_planner() -> None:
    """AC-2: planner registry exposes ``auditor-opus`` with Opus CLI flag."""
    registry = planner_tier_registry()
    tier = registry["auditor-opus"]
    route = tier.route
    assert isinstance(route, ClaudeCodeRoute), (
        f"Expected ClaudeCodeRoute, got {type(route).__name__}"
    )
    assert route.kind == "claude_code"
    assert route.cli_model_flag == "opus"
    assert tier.max_concurrency == 1
    assert tier.per_call_timeout_s == 300


# ---------------------------------------------------------------------------
# slice_refactor_tier_registry inherits auditor tiers via composition
# ---------------------------------------------------------------------------


def test_auditor_sonnet_tier_present_in_slice_refactor() -> None:
    """slice_refactor inherits ``auditor-sonnet`` via planner composition."""
    registry = slice_refactor_tier_registry()
    assert "auditor-sonnet" in registry
    tier = registry["auditor-sonnet"]
    route = tier.route
    assert isinstance(route, ClaudeCodeRoute)
    assert route.cli_model_flag == "sonnet"
    assert tier.max_concurrency == 1
    assert tier.per_call_timeout_s == 300


def test_auditor_opus_tier_present_in_slice_refactor() -> None:
    """slice_refactor inherits ``auditor-opus`` via planner composition."""
    registry = slice_refactor_tier_registry()
    assert "auditor-opus" in registry
    tier = registry["auditor-opus"]
    route = tier.route
    assert isinstance(route, ClaudeCodeRoute)
    assert route.cli_model_flag == "opus"
    assert tier.max_concurrency == 1
    assert tier.per_call_timeout_s == 300


# ---------------------------------------------------------------------------
# summarize_tier_registry — auditor-sonnet (declared directly)
# ---------------------------------------------------------------------------


def test_auditor_sonnet_tier_resolves_to_cli_sonnet_in_summarize() -> None:
    """AC-1 (summarize): ``summarize_tier_registry`` exposes ``auditor-sonnet``.

    Because ``summarize`` does not compose planner, the entry is declared
    directly. This test confirms the direct declaration matches the canonical
    planner-registry shape (same CLI flag, concurrency, timeout).
    """
    registry = summarize_tier_registry()
    tier = registry["auditor-sonnet"]
    route = tier.route
    assert isinstance(route, ClaudeCodeRoute), (
        f"Expected ClaudeCodeRoute, got {type(route).__name__}"
    )
    assert route.kind == "claude_code"
    assert route.cli_model_flag == "sonnet"
    assert tier.max_concurrency == 1
    assert tier.per_call_timeout_s == 300


# ---------------------------------------------------------------------------
# summarize_tier_registry — auditor-opus (declared directly)
# ---------------------------------------------------------------------------


def test_auditor_opus_tier_resolves_to_cli_opus_in_summarize() -> None:
    """AC-2 (summarize): ``summarize_tier_registry`` exposes ``auditor-opus``.

    Direct declaration (no planner composition) must match the canonical
    planner-registry shape.
    """
    registry = summarize_tier_registry()
    tier = registry["auditor-opus"]
    route = tier.route
    assert isinstance(route, ClaudeCodeRoute), (
        f"Expected ClaudeCodeRoute, got {type(route).__name__}"
    )
    assert route.kind == "claude_code"
    assert route.cli_model_flag == "opus"
    assert tier.max_concurrency == 1
    assert tier.per_call_timeout_s == 300


# ---------------------------------------------------------------------------
# Guard: existing planner tiers not clobbered
# ---------------------------------------------------------------------------


def test_planner_existing_tiers_unchanged_after_auditor_addition() -> None:
    """M12 T01 must not alter the pre-existing planner-explorer / planner-synth entries."""
    from ai_workflows.primitives.tiers import LiteLLMRoute

    registry = planner_tier_registry()

    explorer = registry["planner-explorer"]
    assert isinstance(explorer.route, LiteLLMRoute)
    assert explorer.route.model == "ollama/qwen2.5-coder:32b"

    synth = registry["planner-synth"]
    assert isinstance(synth.route, ClaudeCodeRoute)
    assert synth.route.cli_model_flag == "opus"
    assert synth.per_call_timeout_s == 300
