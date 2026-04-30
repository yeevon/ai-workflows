"""Hermetic tests for ``TierConfig.fallback`` schema field (M15 Task 01).

Covers AC-1 and AC-2: flat acceptance, nested rejection, empty default, and
round-trip via ``model_dump`` + ``TypeAdapter``. No provider calls, no disk I/O.

Relationship to other modules
------------------------------
* Tests ``ai_workflows/primitives/tiers.py`` — the ``TierConfig`` pydantic
  model extended in M15 T01 with the ``fallback: list[Route]`` field.
* Does NOT exercise ``TieredNode`` cascade dispatch (M15 T02) or any
  ``graph/`` / ``workflows/`` layer code.
"""

import pytest
from pydantic import TypeAdapter, ValidationError  # noqa: TC002

from ai_workflows.primitives.tiers import (
    ClaudeCodeRoute,
    LiteLLMRoute,
    TierConfig,
)

# ---------------------------------------------------------------------------
# Helpers shared across tests
# ---------------------------------------------------------------------------


def _minimal_tier_config(**kwargs: object) -> TierConfig:
    """Return a ``TierConfig`` with a ``LiteLLMRoute`` primary route."""
    return TierConfig(
        name="test-tier",
        route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# AC-2 / AC-1: flat acceptance
# ---------------------------------------------------------------------------


def test_tierconfig_fallback_field_accepts_flat_list() -> None:
    """Construct ``TierConfig`` with a 2-entry fallback list; assert len == 2."""
    tier = _minimal_tier_config(
        fallback=[
            LiteLLMRoute(model="gemini/gemini-2.5-flash"),
            ClaudeCodeRoute(cli_model_flag="sonnet"),
        ]
    )
    assert len(tier.fallback) == 2
    assert isinstance(tier.fallback[0], LiteLLMRoute)
    assert isinstance(tier.fallback[1], ClaudeCodeRoute)


# ---------------------------------------------------------------------------
# AC-2 / AC-1: nested rejection
# ---------------------------------------------------------------------------


def test_tierconfig_fallback_field_rejects_nested_fallback() -> None:
    """Attempt to build ``TierConfig`` with a nested fallback; expect ``ValidationError``."""
    with pytest.raises(ValidationError) as exc_info:
        TierConfig(
            name="test-tier",
            route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
            fallback=[
                {
                    "kind": "litellm",
                    "model": "gemini/gemini-2.5-flash",
                    "fallback": [{"kind": "claude_code", "cli_model_flag": "sonnet"}],
                }
            ],
        )
    error_text = str(exc_info.value)
    assert "nested fallback is not allowed" in error_text
    assert "fallback[0]" in error_text


# ---------------------------------------------------------------------------
# AC-1: empty default
# ---------------------------------------------------------------------------


def test_tierconfig_fallback_defaults_to_empty_list() -> None:
    """Construct ``TierConfig`` without ``fallback``; assert ``tier.fallback == []``."""
    tier = _minimal_tier_config()
    assert tier.fallback == []


# ---------------------------------------------------------------------------
# AC-1: round-trip via model_dump + TypeAdapter
# ---------------------------------------------------------------------------


def test_tierconfig_fallback_roundtrip_via_model_dump() -> None:
    """Round-trip a 1-entry fallback through ``model_dump(mode='json')`` + ``TypeAdapter``."""
    original = _minimal_tier_config(
        fallback=[LiteLLMRoute(model="ollama/qwen2.5-coder:32b")]
    )
    dumped = original.model_dump(mode="json")
    adapter = TypeAdapter(TierConfig)
    restored = adapter.validate_python(dumped)
    assert restored == original
    assert len(restored.fallback) == 1
    assert isinstance(restored.fallback[0], LiteLLMRoute)
    assert restored.fallback[0].model == "ollama/qwen2.5-coder:32b"
