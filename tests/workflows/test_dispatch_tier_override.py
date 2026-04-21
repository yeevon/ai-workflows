"""Unit tests for M5 Task 04 — ``_dispatch._apply_tier_overrides``.

Pure-function tests of the tier-override helper that backs both the
CLI's ``--tier-override`` flag (M5 T04) and the MCP ``run_workflow``
tool's ``tier_overrides`` argument (M5 T05). No graph compile, no
workflow registry lookup — just the helper's input/output contract
plus the :class:`UnknownTierError` surface.

Two invariants the CLI/MCP tests otherwise can only pin indirectly:

1. ``_apply_tier_overrides`` does not mutate its input registry even
   when overrides are applied — two successive applications against the
   same source registry return independent dicts.
2. The unknown-name error distinguishes ``"logical"`` (LHS) from
   ``"replacement"`` (RHS) so the surface can surface which side of
   ``=`` was bad.
"""

from __future__ import annotations

import pytest

from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig
from ai_workflows.workflows._dispatch import (
    UnknownTierError,
    _apply_tier_overrides,
)


def _two_tier_registry() -> dict[str, TierConfig]:
    return {
        "planner-explorer": TierConfig(
            name="planner-explorer",
            route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
            max_concurrency=2,
            per_call_timeout_s=60,
        ),
        "planner-synth": TierConfig(
            name="planner-synth",
            route=LiteLLMRoute(model="gemini/gemini-2.5-pro"),
            max_concurrency=2,
            per_call_timeout_s=90,
        ),
    }


def test_empty_overrides_returns_copy_not_same_dict() -> None:
    """AC-5: idempotency — the returned registry is a fresh dict."""
    src = _two_tier_registry()
    out = _apply_tier_overrides(src, None)
    assert out == src
    assert out is not src
    out["planner-explorer"] = TierConfig(
        name="planner-explorer",
        route=LiteLLMRoute(model="something-else"),
    )
    assert src["planner-explorer"].route.model == "gemini/gemini-2.5-flash"


def test_single_override_points_logical_at_replacement_config() -> None:
    src = _two_tier_registry()
    out = _apply_tier_overrides(src, {"planner-synth": "planner-explorer"})
    assert out["planner-synth"] is src["planner-explorer"]
    # explorer untouched
    assert out["planner-explorer"] is src["planner-explorer"]


def test_override_does_not_mutate_source_registry_across_repeated_calls() -> None:
    """AC: repeated application against the same source stays idempotent."""
    src = _two_tier_registry()
    snapshot = dict(src)

    _apply_tier_overrides(src, {"planner-synth": "planner-explorer"})
    _apply_tier_overrides(src, {"planner-synth": "planner-explorer"})
    _apply_tier_overrides(src, {"planner-explorer": "planner-synth"})

    assert src == snapshot
    assert src["planner-explorer"].route.model == "gemini/gemini-2.5-flash"
    assert src["planner-synth"].route.model == "gemini/gemini-2.5-pro"


def test_swap_override_reads_rhs_from_source_not_from_partial_output() -> None:
    """Snapshot semantics: a two-way swap uses the original config on both sides."""
    src = _two_tier_registry()
    out = _apply_tier_overrides(
        src,
        {
            "planner-explorer": "planner-synth",
            "planner-synth": "planner-explorer",
        },
    )
    assert out["planner-explorer"].route.model == "gemini/gemini-2.5-pro"
    assert out["planner-synth"].route.model == "gemini/gemini-2.5-flash"


def test_unknown_logical_tier_raises_with_logical_kind() -> None:
    src = _two_tier_registry()
    with pytest.raises(UnknownTierError) as excinfo:
        _apply_tier_overrides(src, {"nonexistent": "planner-synth"})
    assert excinfo.value.tier_name == "nonexistent"
    assert excinfo.value.kind == "logical"
    assert "planner-explorer" in excinfo.value.registered
    assert "planner-synth" in excinfo.value.registered


def test_unknown_replacement_tier_raises_with_replacement_kind() -> None:
    src = _two_tier_registry()
    with pytest.raises(UnknownTierError) as excinfo:
        _apply_tier_overrides(src, {"planner-synth": "nonexistent"})
    assert excinfo.value.tier_name == "nonexistent"
    assert excinfo.value.kind == "replacement"
