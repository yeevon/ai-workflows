"""Tests for M1 Task 07 — ``ai_workflows.primitives.tiers`` loader surface.

Covers every acceptance criterion of Task 07 that applies to the tiers +
pricing loaders:

* ``load_tiers()`` expands ``${OLLAMA_BASE_URL:-default}`` from env
* ``--profile local`` overlay overrides only declared keys
* Unknown tier raises ``UnknownTierError``
* ``sonnet`` tier has ``temperature: 0.1`` (P-22 — restored)
* Carry-over M1-T03-ISS-12: ``TierConfig.max_retries`` roundtrips through
  ``load_tiers()`` so Task 10 can consume it per-tier.
* ``load_pricing()`` returns validated ``ModelPricing`` rows.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from ai_workflows.primitives.tiers import (
    ModelPricing,
    TierConfig,
    UnknownTierError,
    get_tier,
    load_pricing,
    load_tiers,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write(path: Path, text: str) -> None:
    """Dedent and write ``text`` to ``path``, creating parents as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(text).lstrip(), encoding="utf-8")


# ---------------------------------------------------------------------------
# Env var expansion
# ---------------------------------------------------------------------------


def test_load_tiers_expands_env_var_with_default(tmp_path, monkeypatch):
    """``${OLLAMA_BASE_URL:-default}`` should yield the env value when set."""
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://lan.example/v1")
    _write(
        tmp_path / "tiers.yaml",
        """
        tiers:
          local_coder:
            provider: ollama
            model: qwen2.5-coder:32b
            base_url: "${OLLAMA_BASE_URL:-http://192.168.1.100:11434/v1}"
            max_tokens: 8192
            temperature: 0.1
        """,
    )
    tiers = load_tiers(_tiers_dir=tmp_path)
    assert tiers["local_coder"].base_url == "http://lan.example/v1"


def test_load_tiers_falls_back_to_default_when_env_unset(tmp_path, monkeypatch):
    """When the env var is unset, the ``:-default`` tail is used verbatim."""
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    _write(
        tmp_path / "tiers.yaml",
        """
        tiers:
          local_coder:
            provider: ollama
            model: qwen2.5-coder:32b
            base_url: "${OLLAMA_BASE_URL:-http://192.168.1.100:11434/v1}"
            max_tokens: 8192
            temperature: 0.1
        """,
    )
    tiers = load_tiers(_tiers_dir=tmp_path)
    assert tiers["local_coder"].base_url == "http://192.168.1.100:11434/v1"


def test_load_tiers_expands_env_var_without_default(tmp_path, monkeypatch):
    """Bare ``${VAR}`` (no default) should still substitute when set."""
    monkeypatch.setenv("MY_BASE", "http://bare.example/v1")
    _write(
        tmp_path / "tiers.yaml",
        """
        tiers:
          local_coder:
            provider: ollama
            model: qwen2.5-coder:32b
            base_url: "${MY_BASE}"
            max_tokens: 8192
            temperature: 0.1
        """,
    )
    tiers = load_tiers(_tiers_dir=tmp_path)
    assert tiers["local_coder"].base_url == "http://bare.example/v1"


# ---------------------------------------------------------------------------
# Profile overlay
# ---------------------------------------------------------------------------


def test_profile_local_overlay_overrides_only_declared_keys(tmp_path):
    """``tiers.local.yaml`` should deep-merge — untouched keys stay from base."""
    _write(
        tmp_path / "tiers.yaml",
        """
        tiers:
          local_coder:
            provider: ollama
            model: qwen2.5-coder:32b
            base_url: "http://192.168.1.100:11434/v1"
            max_tokens: 8192
            temperature: 0.1
          haiku:
            provider: claude_code
            model: claude-haiku-4-5-20251001
            max_tokens: 4096
            temperature: 0.1
        """,
    )
    _write(
        tmp_path / "tiers.local.yaml",
        """
        tiers:
          local_coder:
            base_url: "http://localhost:11434/v1"
        """,
    )

    base = load_tiers(_tiers_dir=tmp_path)
    assert base["local_coder"].base_url == "http://192.168.1.100:11434/v1"

    overlaid = load_tiers(profile="local", _tiers_dir=tmp_path)
    # Only base_url was declared in the overlay — everything else stays from base.
    assert overlaid["local_coder"].base_url == "http://localhost:11434/v1"
    assert overlaid["local_coder"].model == "qwen2.5-coder:32b"
    assert overlaid["local_coder"].max_tokens == 8192
    assert overlaid["local_coder"].temperature == 0.1
    # Tiers that the overlay did not mention are untouched.
    assert overlaid["haiku"].model == "claude-haiku-4-5-20251001"


def test_profile_without_overlay_file_is_noop(tmp_path):
    """Passing an unknown profile name does not error; base values pass through."""
    _write(
        tmp_path / "tiers.yaml",
        """
        tiers:
          haiku:
            provider: claude_code
            model: claude-haiku-4-5-20251001
            max_tokens: 4096
            temperature: 0.1
        """,
    )
    tiers = load_tiers(profile="nonexistent", _tiers_dir=tmp_path)
    assert tiers["haiku"].max_tokens == 4096


# ---------------------------------------------------------------------------
# Unknown tier
# ---------------------------------------------------------------------------


def test_get_tier_raises_unknown_tier_error_for_missing_name(tmp_path):
    _write(
        tmp_path / "tiers.yaml",
        """
        tiers:
          haiku:
            provider: claude_code
            model: claude-haiku-4-5-20251001
            max_tokens: 4096
            temperature: 0.1
        """,
    )
    tiers = load_tiers(_tiers_dir=tmp_path)
    with pytest.raises(UnknownTierError) as exc_info:
        get_tier(tiers, "nope")
    assert "nope" in str(exc_info.value)


def test_unknown_tier_error_is_not_a_configuration_error():
    """Keep ``UnknownTierError`` separate from ``ConfigurationError`` so callers
    can distinguish a tier-name typo from a missing env var."""
    from ai_workflows.primitives.llm.model_factory import ConfigurationError

    assert not issubclass(UnknownTierError, ConfigurationError)


# ---------------------------------------------------------------------------
# P-22: sonnet tier has temperature 0.1 (pinned against the committed file)
# ---------------------------------------------------------------------------


def test_committed_tiers_yaml_sonnet_has_temperature_0_1():
    """The checked-in ``tiers.yaml`` must keep ``sonnet.temperature == 0.1``.

    Regression guard for P-22: the original spec had ``sonnet`` without a
    ``temperature`` field; restoring it is the whole point of that issue.
    """
    tiers = load_tiers(_tiers_dir=REPO_ROOT)
    assert "sonnet" in tiers
    assert tiers["sonnet"].temperature == 0.1
    # Keep the rest of the sonnet contract pinned while we're here — any of
    # these flipping would invalidate a downstream deployment.
    assert tiers["sonnet"].provider == "claude_code"
    assert tiers["sonnet"].model == "claude-sonnet-4-6"


def test_committed_tiers_yaml_has_all_five_canonical_tiers():
    tiers = load_tiers(_tiers_dir=REPO_ROOT)
    assert set(tiers) == {"opus", "sonnet", "haiku", "local_coder", "gemini_flash"}


# ---------------------------------------------------------------------------
# M1-T03-ISS-12 carry-over: max_retries roundtrips through the loader
# ---------------------------------------------------------------------------


def test_tier_config_max_retries_roundtrips_through_load_tiers(tmp_path):
    """Carry-over decision: keep the field and wire it through the loader.

    Task 10 will read ``TierConfig.max_retries`` at retry time. This test
    pins the loader contract today so Task 10 has no loader-side work.
    """
    _write(
        tmp_path / "tiers.yaml",
        """
        tiers:
          haiku:
            provider: claude_code
            model: claude-haiku-4-5-20251001
            max_tokens: 4096
            temperature: 0.1
            max_retries: 5
        """,
    )
    tiers = load_tiers(_tiers_dir=tmp_path)
    assert tiers["haiku"].max_retries == 5


def test_tier_config_max_retries_default_is_three(tmp_path):
    """When the field is absent from YAML, ``TierConfig`` defaults to 3."""
    _write(
        tmp_path / "tiers.yaml",
        """
        tiers:
          haiku:
            provider: claude_code
            model: claude-haiku-4-5-20251001
            max_tokens: 4096
            temperature: 0.1
        """,
    )
    tiers = load_tiers(_tiers_dir=tmp_path)
    assert tiers["haiku"].max_retries == 3


# ---------------------------------------------------------------------------
# load_pricing
# ---------------------------------------------------------------------------


def test_load_pricing_parses_committed_file():
    """The checked-in ``pricing.yaml`` must load cleanly into ``ModelPricing``."""
    pricing = load_pricing(_pricing_dir=REPO_ROOT)

    # Claude CLI tiers cost $0 — subscription billing.
    for claude_model in (
        "claude-opus-4-7",
        "claude-sonnet-4-6",
        "claude-haiku-4-5-20251001",
    ):
        assert pricing[claude_model].input_per_mtok == 0.0
        assert pricing[claude_model].output_per_mtok == 0.0

    # Gemini overflow has non-zero rates.
    assert pricing["gemini-2.0-flash"].input_per_mtok == pytest.approx(0.10)
    assert pricing["gemini-2.0-flash"].output_per_mtok == pytest.approx(0.40)

    # Local Qwen is free.
    assert pricing["qwen2.5-coder:32b"].input_per_mtok == 0.0


def test_load_pricing_validates_unknown_keys(tmp_path):
    """Typos like ``inpput_per_mtok`` surface at load time, not first call."""
    _write(
        tmp_path / "pricing.yaml",
        """
        pricing:
          some-model:
            inpput_per_mtok: 0.1  # intentional typo
            output_per_mtok: 0.4
        """,
    )
    # Pydantic default is ``extra="ignore"``, so the typo is silently dropped
    # and the required ``input_per_mtok`` is missing → ValidationError.
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        load_pricing(_pricing_dir=tmp_path)


def test_load_pricing_cache_fields_default_to_zero(tmp_path):
    """Rows that omit cache rates (the canonical shape) default them to 0.0."""
    _write(
        tmp_path / "pricing.yaml",
        """
        pricing:
          some-model:
            input_per_mtok: 1.0
            output_per_mtok: 2.0
        """,
    )
    pricing = load_pricing(_pricing_dir=tmp_path)
    assert pricing["some-model"].cache_read_per_mtok == 0.0
    assert pricing["some-model"].cache_write_per_mtok == 0.0


# ---------------------------------------------------------------------------
# Misc: empty files, missing files
# ---------------------------------------------------------------------------


def test_load_tiers_allows_empty_mapping(tmp_path):
    _write(tmp_path / "tiers.yaml", "tiers: {}\n")
    assert load_tiers(_tiers_dir=tmp_path) == {}


def test_load_tiers_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_tiers(_tiers_dir=tmp_path)


def test_load_pricing_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_pricing(_pricing_dir=tmp_path)


def test_tier_config_instantiation_accepts_full_spec_example():
    """Sanity check: building a ``TierConfig`` from the spec's YAML dict works."""
    tier = TierConfig(
        provider="openai_compat",
        model="gemini-2.0-flash",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key_env="GEMINI_API_KEY",
        max_tokens=4096,
        temperature=0.1,
    )
    assert tier.provider == "openai_compat"
    assert tier.max_retries == 3  # default


def test_model_pricing_accepts_cache_rates_when_present():
    pricing = ModelPricing(
        input_per_mtok=3.0,
        output_per_mtok=15.0,
        cache_read_per_mtok=0.3,
        cache_write_per_mtok=3.75,
    )
    assert pricing.cache_read_per_mtok == pytest.approx(0.3)
    assert pricing.cache_write_per_mtok == pytest.approx(3.75)
