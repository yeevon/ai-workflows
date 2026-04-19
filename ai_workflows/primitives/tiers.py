"""Tier configuration models + YAML loaders.

Produced by M1 Task 03 (``TierConfig`` stub) and expanded by M1 Task 07
(``load_tiers()`` / ``load_pricing()``).

Responsibilities
----------------
* ``TierConfig`` — shape of a single tier (provider, model, limits).
* ``ModelPricing`` — shape of a single row in ``pricing.yaml``.
* ``load_tiers(profile=None)`` — read ``tiers.yaml``, expand ``${ENV:-default}``
  placeholders, optionally overlay ``tiers.<profile>.yaml`` (deep-merge,
  only declared keys are overridden), and validate each tier against
  ``TierConfig``.
* ``load_pricing()`` — read ``pricing.yaml``, validate each row against
  ``ModelPricing``. Used by Task 09's ``CostTracker.calculate_cost()``.
* ``UnknownTierError`` — raised on lookup of a tier not present in the
  loaded mapping. Satisfies the Task 07 AC ("Unknown tier raises
  ``UnknownTierError``") and keeps the separation of concerns clear —
  ``ConfigurationError`` (in ``llm.model_factory``) is for missing env
  vars and malformed provider branches; ``UnknownTierError`` is purely
  about tier-name misses.

See also
--------
* ``primitives/workflow_hash.py`` — the directory-content hash utility
  that pairs with this module for CRIT-02 resume safety.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel


class UnknownTierError(Exception):
    """Raised when a tier name is not present in the loaded tiers mapping.

    Kept separate from ``llm.model_factory.ConfigurationError`` so callers can
    distinguish a typo ("unknown tier") from a missing environment variable or
    malformed provider branch ("bad configuration"). The Task 07 AC pins this
    contract ("unknown tier raises ``UnknownTierError``").
    """


class TierConfig(BaseModel):
    """Configuration for a single model tier as loaded from ``tiers.yaml``.

    ``max_retries`` (M1-T03-ISS-12 decision, pinned by M1 Task 07)
    --------------------------------------------------------------
    The field is **kept** and wired through ``load_tiers()`` so it roundtrips
    from YAML → ``TierConfig``. Task 10 (``retry_on_rate_limit``) reads this
    per-tier value at retry time; until Task 10 lands the value is not
    consulted at runtime, but the loader and schema are stable so Task 10
    has no loader-side work.

    The field specifically describes **our** retry layer's budget. The
    underlying SDK clients are always built with ``max_retries=0`` (CRIT-06);
    this setting never leaks into SDK construction.
    """

    provider: Literal["claude_code", "anthropic", "ollama", "openai_compat", "google"]
    # claude_code   → subprocess `claude` CLI (Claude Max subscription, no API key);
    #                 implementation lands in M4 with the Orchestrator component.
    # anthropic     → native AnthropicModel; retained for third-party deployments
    #                 that run on the Anthropic API directly (not used in default
    #                 tiers for this repo — see memory: project_provider_strategy).
    # ollama        → local Ollama server (Qwen, free) via OpenAI-compatible API.
    # openai_compat → Gemini / DeepSeek / OpenRouter via OpenAI-compatible API.
    # google        → native Google SDK (reserved; not in default tiers).
    model: str
    max_tokens: int
    temperature: float
    base_url: str | None = None
    api_key_env: str | None = None
    # Budget for our retry layer (Task 10). Underlying SDK clients are always 0.
    max_retries: int = 3


class ModelPricing(BaseModel):
    """Per-million-token pricing for a single model, loaded from ``pricing.yaml``.

    Task 09's ``calculate_cost()`` multiplies these rates by the usage counts
    in ``TokenUsage``:

        (in * in_rate + out * out_rate + cr * cr_rate + cw * cw_rate) / 1e6

    Cache rates default to ``0.0`` so the canonical ``pricing.yaml`` rows
    (which only list ``input_per_mtok`` / ``output_per_mtok``) validate.
    Anthropic tiers that do expose cache-read / cache-write rates can add
    the fields explicitly.
    """

    input_per_mtok: float
    output_per_mtok: float
    cache_read_per_mtok: float = 0.0
    cache_write_per_mtok: float = 0.0


# ---------------------------------------------------------------------------
# Env var expansion + deep-merge helpers
# ---------------------------------------------------------------------------


# Matches ``${VAR}`` and ``${VAR:-default}`` — default may contain anything
# except a closing brace. No ``$VAR`` bare-word form (too ambiguous inside
# URLs / shell fragments).
_ENV_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-(?P<default>[^}]*))?\}")


def _expand_env_in_string(value: str) -> str:
    """Return ``value`` with every ``${VAR}`` / ``${VAR:-default}`` expanded."""

    def replace(match: re.Match[str]) -> str:
        var = match.group(1)
        default = match.group("default")
        env_value = os.environ.get(var)
        if env_value is not None and env_value != "":
            return env_value
        if default is not None:
            return default
        # Unset and no default — leave the placeholder in the string so the
        # downstream validator sees the defect at construction time instead
        # of silently substituting an empty string.
        return match.group(0)

    return _ENV_VAR_RE.sub(replace, value)


def _expand_env_recursive(node: Any) -> Any:
    """Walk a YAML-loaded structure and expand env placeholders on string leaves."""
    if isinstance(node, str):
        return _expand_env_in_string(node)
    if isinstance(node, dict):
        return {k: _expand_env_recursive(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_expand_env_recursive(v) for v in node]
    return node


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Return a new dict with overlay's keys merged on top of base.

    Nested dicts are merged recursively. Lists and scalars in the overlay
    replace the base entirely — we never concatenate lists, because a
    tiers-overlay that wants to *replace* (not append to) an allowlist
    would otherwise be impossible to express.
    """
    merged: dict[str, Any] = {**base}
    for key, overlay_value in overlay.items():
        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(overlay_value, dict):
            merged[key] = _deep_merge(base_value, overlay_value)
        else:
            merged[key] = overlay_value
    return merged


# ---------------------------------------------------------------------------
# Public loaders
# ---------------------------------------------------------------------------


def _project_root() -> Path:
    """Return the directory from which YAML config files are resolved.

    P-21 ("package data via ``importlib.resources`` when installed") is still
    open, so for now we look in the current working directory. Tests inject
    the root via the ``_tiers_dir`` / ``_pricing_dir`` keyword argument.
    """
    return Path.cwd()


def load_tiers(
    profile: str | None = None,
    *,
    _tiers_dir: Path | None = None,
) -> dict[str, TierConfig]:
    """Load ``tiers.yaml`` (plus optional ``tiers.<profile>.yaml`` overlay).

    Parameters
    ----------
    profile:
        Name of an overlay file to apply on top of the base ``tiers.yaml``.
        ``profile="local"`` looks for ``tiers.local.yaml``. Overlay values
        deep-merge — only the keys the overlay declares are overridden.
    _tiers_dir:
        Internal override used by tests to point the loader at a temp
        directory. Production callers always leave this as ``None``.

    Returns
    -------
    dict[str, TierConfig]
        Mapping from tier name (``opus``, ``sonnet``, ``local_coder``, …) to
        validated ``TierConfig``.

    Notes
    -----
    * Every string value is passed through ``${VAR:-default}`` expansion
      before validation. A ``base_url`` like
      ``"${OLLAMA_BASE_URL:-http://192.168.1.100:11434/v1}"`` yields the
      env var when set, else the default.
    * The top-level ``tiers:`` key is required. An empty mapping is allowed
      (useful for the Task 01 stub) and returns an empty dict.
    """
    root = _tiers_dir or _project_root()
    base_path = root / "tiers.yaml"
    base = _load_yaml_section(base_path, section="tiers")

    if profile is not None:
        overlay_path = root / f"tiers.{profile}.yaml"
        if overlay_path.exists():
            overlay = _load_yaml_section(overlay_path, section="tiers")
            base = _deep_merge(base, overlay)

    expanded = _expand_env_recursive(base)
    return {name: TierConfig(**cfg) for name, cfg in expanded.items()}


def load_pricing(
    *,
    _pricing_dir: Path | None = None,
) -> dict[str, ModelPricing]:
    """Load ``pricing.yaml`` and return ``{model_id: ModelPricing}``.

    The top-level ``pricing:`` key is required. Every row is validated
    against ``ModelPricing``; unknown keys cause a Pydantic ``ValidationError``
    (catches typos like ``inpput_per_mtok`` at load time, not at first call).
    """
    root = _pricing_dir or _project_root()
    path = root / "pricing.yaml"
    raw = _load_yaml_section(path, section="pricing")
    return {model_id: ModelPricing(**row) for model_id, row in raw.items()}


def get_tier(tiers: dict[str, TierConfig], name: str) -> TierConfig:
    """Look up a tier by name, raising ``UnknownTierError`` if absent.

    Small helper that matches the Task 07 AC ("unknown tier raises
    ``UnknownTierError``"). Callers that prefer the raw dict lookup can
    still use ``tiers[name]``; this helper exists for the common case
    where the error class matters.
    """
    try:
        return tiers[name]
    except KeyError as exc:
        raise UnknownTierError(f"Unknown tier: {name!r}") from exc


# ---------------------------------------------------------------------------
# Internal YAML helpers
# ---------------------------------------------------------------------------


def _load_yaml_section(path: Path, *, section: str) -> dict[str, Any]:
    """Read ``path``, return the mapping under ``section`` (or ``{}`` if null)."""
    if not path.exists():
        raise FileNotFoundError(f"Required config file missing: {path}")
    with path.open("r", encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh) or {}
    if not isinstance(loaded, dict):
        raise ValueError(
            f"{path} must be a YAML mapping at the top level, got {type(loaded).__name__}"
        )
    body = loaded.get(section)
    if body is None:
        return {}
    if not isinstance(body, dict):
        raise ValueError(
            f"{path}: expected ``{section}:`` to be a mapping, got {type(body).__name__}"
        )
    return body
