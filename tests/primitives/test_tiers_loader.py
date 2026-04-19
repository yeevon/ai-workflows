"""Tests for M1 Task 06 — ``ai_workflows.primitives.tiers`` refit.

Covers every acceptance criterion from
[task_06_refit_tier_config.md](../../design_docs/phases/milestone_1_reconciliation/task_06_refit_tier_config.md):

* AC-1 — ``tiers.yaml`` parses into ``dict[str, TierConfig]`` without errors.
* AC-2 — each tier's ``route`` validates as either ``LiteLLMRoute`` or
  ``ClaudeCodeRoute`` (discriminator round-trip).
* AC-3 — ``pricing.yaml`` contains only Claude Code CLI entries.
* AC-4 — discriminator round-trip, unknown-tier lookup,
  malformed-YAML rejection.
* AC-5 — see ``uv run pytest`` gate evidence in CHANGELOG.

Also covers:

* Env expansion (``${OLLAMA_BASE_URL:-default}``) still works on the
  ``LiteLLMRoute.api_base`` field.
* ``profile`` overlay deep-merges only declared keys (``tiers.<profile>.yaml``).
* Carry-over M1-T03-ISS-01 — the pre-T06 test imported
  ``ConfigurationError`` from ``ai_workflows.primitives.llm.model_factory``,
  a module deleted by T03. The post-refit tier surface exposes a single
  ``UnknownTierError`` class; no cross-module class comparison remains.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from pydantic import ValidationError

from ai_workflows.primitives.tiers import (
    ClaudeCodeRoute,
    LiteLLMRoute,
    ModelPricing,
    TierConfig,
    TierRegistry,
    UnknownTierError,
    get_tier,
    load_pricing,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write(path: Path, text: str) -> None:
    """Dedent and write ``text`` to ``path``, creating parents as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(text).lstrip(), encoding="utf-8")


# ---------------------------------------------------------------------------
# AC-1 + AC-2: tiers.yaml → dict[str, TierConfig] with discriminator
# ---------------------------------------------------------------------------


def test_committed_tiers_yaml_parses_into_tier_config_mapping():
    """AC-1: the checked-in ``tiers.yaml`` parses into the expected mapping."""
    tiers = TierRegistry.load(REPO_ROOT)
    # AC-1: mapping keys match the committed tier names exactly.
    assert set(tiers) == {
        "planner",
        "implementer",
        "local_coder",
        "opus",
        "sonnet",
        "haiku",
    }
    # Every entry is a TierConfig with ``name`` populated from the key.
    for name, cfg in tiers.items():
        assert isinstance(cfg, TierConfig)
        assert cfg.name == name


def test_committed_tiers_resolve_to_the_correct_route_variant():
    """AC-2: each route is the correct discriminated variant."""
    tiers = TierRegistry.load(REPO_ROOT)
    # LiteLLM-routed tiers.
    for name in ("planner", "implementer", "local_coder"):
        assert isinstance(tiers[name].route, LiteLLMRoute), name
        assert tiers[name].route.kind == "litellm"
    # Claude Code CLI-routed tiers.
    for name in ("opus", "sonnet", "haiku"):
        assert isinstance(tiers[name].route, ClaudeCodeRoute), name
        assert tiers[name].route.kind == "claude_code"


def test_claude_code_tiers_carry_the_expected_cli_model_flags():
    """Each Claude Code tier names the CLI model flag the M2 driver forwards."""
    tiers = TierRegistry.load(REPO_ROOT)
    assert tiers["opus"].route.cli_model_flag == "opus"
    assert tiers["sonnet"].route.cli_model_flag == "sonnet"
    assert tiers["haiku"].route.cli_model_flag == "haiku"


def test_litellm_tiers_carry_gemini_and_ollama_model_strings():
    """Gemini via LiteLLM, Ollama via LiteLLM — KDR-007 tier strings."""
    tiers = TierRegistry.load(REPO_ROOT)
    assert tiers["planner"].route.model.startswith("gemini/")
    assert tiers["implementer"].route.model.startswith("gemini/")
    assert tiers["local_coder"].route.model.startswith("ollama/")


# ---------------------------------------------------------------------------
# AC-4: discriminator round-trip (construction from dict)
# ---------------------------------------------------------------------------


def test_discriminator_round_trip_from_litellm_dict():
    cfg = TierConfig.model_validate(
        {
            "name": "planner",
            "route": {"kind": "litellm", "model": "gemini/gemini-2.5-flash"},
        }
    )
    assert isinstance(cfg.route, LiteLLMRoute)
    assert cfg.route.model == "gemini/gemini-2.5-flash"
    # Defaults fill in max_concurrency / per_call_timeout_s.
    assert cfg.max_concurrency == 1
    assert cfg.per_call_timeout_s == 120


def test_discriminator_round_trip_from_claude_code_dict():
    cfg = TierConfig.model_validate(
        {
            "name": "opus",
            "route": {"kind": "claude_code", "cli_model_flag": "opus"},
            "max_concurrency": 1,
            "per_call_timeout_s": 600,
        }
    )
    assert isinstance(cfg.route, ClaudeCodeRoute)
    assert cfg.route.cli_model_flag == "opus"
    assert cfg.per_call_timeout_s == 600


def test_discriminator_rejects_unknown_kind():
    """An unknown ``kind`` value surfaces as a Pydantic ValidationError."""
    with pytest.raises(ValidationError):
        TierConfig.model_validate(
            {
                "name": "bogus",
                "route": {"kind": "anthropic_api", "model": "claude-3"},
            }
        )


def test_discriminator_rejects_wrong_branch_fields():
    """``kind: litellm`` cannot carry ``cli_model_flag`` — wrong branch."""
    with pytest.raises(ValidationError):
        TierConfig.model_validate(
            {
                "name": "opus",
                "route": {"kind": "litellm", "cli_model_flag": "opus"},
            }
        )


# ---------------------------------------------------------------------------
# AC-4: unknown-tier lookup
# ---------------------------------------------------------------------------


def test_get_tier_raises_unknown_tier_error_for_missing_name(tmp_path):
    _write(
        tmp_path / "tiers.yaml",
        """
        haiku:
          route:
            kind: claude_code
            cli_model_flag: haiku
        """,
    )
    tiers = TierRegistry.load(tmp_path)
    with pytest.raises(UnknownTierError) as exc_info:
        get_tier(tiers, "nope")
    assert "nope" in str(exc_info.value)


# ---------------------------------------------------------------------------
# AC-4: malformed YAML rejection
# ---------------------------------------------------------------------------


def test_malformed_yaml_tier_rejected_with_validation_error(tmp_path):
    """A tier missing the required ``route`` field fails Pydantic validation."""
    _write(
        tmp_path / "tiers.yaml",
        """
        planner:
          max_concurrency: 2
        """,
    )
    with pytest.raises(ValidationError):
        TierRegistry.load(tmp_path)


def test_non_mapping_top_level_rejected(tmp_path):
    """A list at the top level is not a valid tiers file."""
    _write(tmp_path / "tiers.yaml", "- just\n- a\n- list\n")
    with pytest.raises(ValueError):
        TierRegistry.load(tmp_path)


def test_missing_tiers_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        TierRegistry.load(tmp_path)


def test_empty_tiers_file_yields_empty_mapping(tmp_path):
    """An empty ``tiers.yaml`` loads into ``{}`` — useful for scaffolding."""
    _write(tmp_path / "tiers.yaml", "")
    assert TierRegistry.load(tmp_path) == {}


# ---------------------------------------------------------------------------
# Env expansion
# ---------------------------------------------------------------------------


def test_load_tiers_expands_env_var_with_default(tmp_path, monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://lan.example")
    _write(
        tmp_path / "tiers.yaml",
        """
        local_coder:
          route:
            kind: litellm
            model: ollama/qwen2.5-coder:32b
            api_base: "${OLLAMA_BASE_URL:-http://localhost:11434}"
        """,
    )
    tiers = TierRegistry.load(tmp_path)
    assert tiers["local_coder"].route.api_base == "http://lan.example"


def test_load_tiers_falls_back_to_default_when_env_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    _write(
        tmp_path / "tiers.yaml",
        """
        local_coder:
          route:
            kind: litellm
            model: ollama/qwen2.5-coder:32b
            api_base: "${OLLAMA_BASE_URL:-http://localhost:11434}"
        """,
    )
    tiers = TierRegistry.load(tmp_path)
    assert tiers["local_coder"].route.api_base == "http://localhost:11434"


# ---------------------------------------------------------------------------
# Profile overlay
# ---------------------------------------------------------------------------


def test_profile_local_overlay_overrides_only_declared_keys(tmp_path):
    _write(
        tmp_path / "tiers.yaml",
        """
        local_coder:
          route:
            kind: litellm
            model: ollama/qwen2.5-coder:32b
            api_base: "http://192.168.1.100:11434"
          max_concurrency: 1
        haiku:
          route:
            kind: claude_code
            cli_model_flag: haiku
          max_concurrency: 2
        """,
    )
    _write(
        tmp_path / "tiers.local.yaml",
        """
        local_coder:
          route:
            api_base: "http://localhost:11434"
        """,
    )

    base = TierRegistry.load(tmp_path)
    assert base["local_coder"].route.api_base == "http://192.168.1.100:11434"

    overlaid = TierRegistry.load(tmp_path, profile="local")
    # Only api_base was declared in the overlay — other keys stay from base.
    assert overlaid["local_coder"].route.api_base == "http://localhost:11434"
    assert overlaid["local_coder"].route.model == "ollama/qwen2.5-coder:32b"
    assert overlaid["local_coder"].max_concurrency == 1
    # Tiers that the overlay did not mention are untouched.
    assert overlaid["haiku"].route.cli_model_flag == "haiku"


def test_profile_without_overlay_file_is_noop(tmp_path):
    _write(
        tmp_path / "tiers.yaml",
        """
        haiku:
          route:
            kind: claude_code
            cli_model_flag: haiku
          max_concurrency: 2
        """,
    )
    tiers = TierRegistry.load(tmp_path, profile="nonexistent")
    assert tiers["haiku"].max_concurrency == 2


# ---------------------------------------------------------------------------
# AC-3: pricing.yaml contains only Claude Code CLI entries
# ---------------------------------------------------------------------------


def test_committed_pricing_yaml_has_only_claude_cli_entries():
    """AC-3: after the T06 trim, pricing.yaml lists only the three Claude
    Max CLI tiers — LiteLLM supplies the rest (KDR-007)."""
    pricing = load_pricing(REPO_ROOT)
    assert set(pricing) == {
        "claude-opus-4-7",
        "claude-sonnet-4-6",
        "claude-haiku-4-5-20251001",
    }
    # All three are zero-cost because Claude Max bills via subscription.
    for model_id, row in pricing.items():
        assert row.input_per_mtok == 0.0, model_id
        assert row.output_per_mtok == 0.0, model_id


def test_load_pricing_validates_unknown_keys(tmp_path):
    """Typos surface at load time, not at first pricing lookup."""
    _write(
        tmp_path / "pricing.yaml",
        """
        pricing:
          some-model:
            inpput_per_mtok: 0.1  # intentional typo
            output_per_mtok: 0.4
        """,
    )
    with pytest.raises(ValidationError):
        load_pricing(tmp_path)


def test_load_pricing_cache_fields_default_to_zero(tmp_path):
    _write(
        tmp_path / "pricing.yaml",
        """
        pricing:
          some-model:
            input_per_mtok: 1.0
            output_per_mtok: 2.0
        """,
    )
    pricing = load_pricing(tmp_path)
    assert pricing["some-model"].cache_read_per_mtok == 0.0
    assert pricing["some-model"].cache_write_per_mtok == 0.0


def test_load_pricing_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_pricing(tmp_path)


def test_model_pricing_accepts_cache_rates_when_present():
    row = ModelPricing(
        input_per_mtok=3.0,
        output_per_mtok=15.0,
        cache_read_per_mtok=0.3,
        cache_write_per_mtok=3.75,
    )
    assert row.cache_read_per_mtok == pytest.approx(0.3)
    assert row.cache_write_per_mtok == pytest.approx(3.75)
