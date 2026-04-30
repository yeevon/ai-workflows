"""Tier configuration models + YAML loader.

Produced by M1 Task 06 (``TierConfig`` refit) — replaces the pre-pivot
``(provider, model, max_tokens, temperature, …)`` shape with a
discriminated ``route`` union that matches
[architecture.md §4.1](../../design_docs/architecture.md) and KDR-007:
LiteLLM-backed tiers (Gemini, Ollama/Qwen) and the Claude Code CLI
subprocess tier are the two route kinds this project supports.

Responsibilities
----------------
* ``LiteLLMRoute`` — tier routed through LiteLLM; ``model`` is a LiteLLM
  model string (``"gemini/gemini-2.5-flash"``, ``"ollama/qwen2.5-coder:32b"``).
* ``ClaudeCodeRoute`` — tier routed through the ``claude`` CLI subprocess
  (KDR-003 — no Anthropic API key is consulted).
* ``Route`` — discriminated union; Pydantic picks the variant from ``kind``.
* ``TierConfig`` — name + route + concurrency cap + per-call timeout +
  optional ``fallback: list[Route]`` cascade chain (M15 T01).
* ``ModelPricing`` — per-million-token rates loaded from ``pricing.yaml``.
  Loaded by :func:`load_pricing` for the M2 Claude Code subprocess driver
  to compute per-call cost (LiteLLM enriches its own responses;
  ``CostTracker`` after M1 Task 08 no longer prices calls).
* ``TierRegistry.load(root, profile=None)`` — primary loader surface per
  the M1 Task 06 spec; reads ``tiers.yaml``, optionally overlays
  ``tiers.<profile>.yaml``, expands ``${ENV:-default}`` placeholders, and
  validates each tier against ``TierConfig``.
* ``load_pricing(root)`` — reads ``pricing.yaml`` into
  ``{model_id: ModelPricing}``.
* ``UnknownTierError`` — raised by :func:`get_tier` for missing tier names.

See also
--------
* M2 Task 02 — the Claude Code subprocess driver is the consumer of
  ``ModelPricing`` (post-T08 refit; ``primitives/cost.py`` no longer
  imports the class).
* M2 Task 01 / Task 02 — LiteLLM adapter and ``ClaudeCodeSubprocess``
  driver that consume ``LiteLLMRoute`` / ``ClaudeCodeRoute``.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator


class UnknownTierError(Exception):
    """Raised by :func:`get_tier` when a tier name is not in the loaded map."""


class LiteLLMRoute(BaseModel):
    """Route for a tier that LiteLLM adapts (Gemini, Ollama/Qwen).

    ``model`` is a LiteLLM model string — the provider prefix before the
    slash picks the adapter (``"gemini/…"``, ``"ollama/…"``, etc.).
    ``api_base`` pins a non-default HTTP endpoint, used for Ollama.
    """

    kind: Literal["litellm"] = "litellm"
    model: str
    api_base: str | None = None


class ClaudeCodeRoute(BaseModel):
    """Route for a tier driven by the ``claude`` CLI subprocess.

    The ``cli_model_flag`` string is forwarded as ``claude --model <flag>``
    by the ``ClaudeCodeSubprocess`` driver that lands in M2. KDR-003: no
    Anthropic API key is consulted anywhere — auth is OAuth via the Max
    subscription the CLI already holds.
    """

    kind: Literal["claude_code"] = "claude_code"
    cli_model_flag: str


Route = Annotated[LiteLLMRoute | ClaudeCodeRoute, Field(discriminator="kind")]


class TierConfig(BaseModel):
    """A single named tier as loaded from ``tiers.yaml``.

    ``max_concurrency`` caps in-flight calls at the provider semaphore
    level (architecture.md §8.6). ``per_call_timeout_s`` is the
    driver-level wall-clock timeout enforced by the M2 drivers.

    The ``fallback`` field (added in M15 T01) holds an ordered list of
    ``Route`` objects tried after the primary route's retry budget exhausts
    (KDR-006). Cascade logic lives in ``TieredNode`` (M15 T02). Flat only
    — nested fallbacks are rejected at schema-validation time per ADR-0006.
    """

    name: str
    route: Route
    max_concurrency: int = 1
    per_call_timeout_s: int = 120
    # Added in M15 T01 (fallback cascade).
    fallback: list[Route] = Field(
        default_factory=list,
        description=(
            "Ordered fallback routes tried after this tier's retry budget "
            "exhausts (M15). Flat only — routes in this list cannot themselves "
            "carry a `fallback` field. Cascade logic lives in TieredNode (T02)."
        ),
    )

    @field_validator("fallback", mode="before")
    @classmethod
    def _reject_nested_fallback(cls, v: Any) -> Any:
        """Nested fallback is architecturally forbidden (ADR-0006)."""
        if isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict) and "fallback" in item:
                    raise ValueError(
                        f"nested fallback is not allowed: fallback[{i}] "
                        "declares its own fallback field."
                    )
        return v


class ModelPricing(BaseModel):
    """Per-million-token pricing row.

    Cache rates default to ``0.0`` so pricing entries that do not break
    out cache read/write prices validate cleanly.
    """

    input_per_mtok: float
    output_per_mtok: float
    cache_read_per_mtok: float = 0.0
    cache_write_per_mtok: float = 0.0


# ---------------------------------------------------------------------------
# Env expansion + deep-merge helpers
# ---------------------------------------------------------------------------


# ``${VAR}`` and ``${VAR:-default}``; default stops at the closing brace.
_ENV_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-(?P<default>[^}]*))?\}")


def _expand_env_in_string(value: str) -> str:
    """Expand every ``${VAR}`` / ``${VAR:-default}`` placeholder in ``value``."""

    def replace(match: re.Match[str]) -> str:
        var = match.group(1)
        default = match.group("default")
        env_value = os.environ.get(var)
        if env_value is not None and env_value != "":
            return env_value
        if default is not None:
            return default
        # Leave the placeholder untouched so the downstream validator sees
        # the defect instead of silently substituting an empty string.
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
    """Return a new dict with ``overlay``'s keys merged on top of ``base``.

    Nested dicts merge recursively. Lists and scalars in ``overlay``
    replace the base value — concatenating lists would make it impossible
    for an overlay to express "replace this allowlist".
    """
    merged: dict[str, Any] = {**base}
    for key, overlay_value in overlay.items():
        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(overlay_value, dict):
            merged[key] = _deep_merge(base_value, overlay_value)
        else:
            merged[key] = overlay_value
    return merged


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    """Read ``path`` and return its top-level mapping."""
    if not path.exists():
        raise FileNotFoundError(f"Required config file missing: {path}")
    with path.open("r", encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh) or {}
    if not isinstance(loaded, dict):
        raise ValueError(
            f"{path} must be a YAML mapping at the top level, got {type(loaded).__name__}"
        )
    return loaded


# ---------------------------------------------------------------------------
# Public loaders
# ---------------------------------------------------------------------------


def _project_root() -> Path:
    """Return the directory from which YAML config files are resolved."""
    return Path.cwd()


class TierRegistry:
    """Tier loader.

    The registry is stateless — ``load`` returns the validated mapping
    directly and callers cache it if they need to. Matches the
    ``TierRegistry.load(path)`` shape named in the M1 Task 06 spec.
    """

    @classmethod
    def load(
        cls,
        root: Path | None = None,
        *,
        profile: str | None = None,
    ) -> dict[str, TierConfig]:
        """Read ``tiers.yaml`` into ``{name: TierConfig}``.

        Parameters
        ----------
        root:
            Directory containing ``tiers.yaml``. Defaults to the current
            working directory.
        profile:
            Overlay stem. ``profile="local"`` layers ``tiers.local.yaml``
            on top of the base — only declared keys are overridden.

        Notes
        -----
        Every string leaf is passed through ``${VAR:-default}`` expansion
        before validation, so an ``api_base: "${OLLAMA_BASE_URL:-…}"`` row
        picks up the env value when set and falls back otherwise.
        """
        root = root or _project_root()
        base = _read_yaml_mapping(root / "tiers.yaml")

        if profile is not None:
            overlay_path = root / f"tiers.{profile}.yaml"
            if overlay_path.exists():
                overlay = _read_yaml_mapping(overlay_path)
                base = _deep_merge(base, overlay)

        expanded = _expand_env_recursive(base)
        return {name: TierConfig(name=name, **cfg) for name, cfg in expanded.items()}


def load_pricing(root: Path | None = None) -> dict[str, ModelPricing]:
    """Load ``pricing.yaml`` and return ``{model_id: ModelPricing}``.

    The top-level ``pricing:`` key is required; every row is validated
    against ``ModelPricing`` so typos (``inpput_per_mtok``) surface at
    load time instead of at first pricing lookup. After M1 Task 06 this
    file carries only Claude Code CLI entries — LiteLLM supplies the
    pricing table for LiteLLM-routed tiers (KDR-007).
    """
    root = root or _project_root()
    path = root / "pricing.yaml"
    loaded = _read_yaml_mapping(path)
    body = loaded.get("pricing")
    if body is None:
        return {}
    if not isinstance(body, dict):
        raise ValueError(
            f"{path}: expected ``pricing:`` to be a mapping, got {type(body).__name__}"
        )
    return {model_id: ModelPricing(**row) for model_id, row in body.items()}


def get_tier(tiers: dict[str, TierConfig], name: str) -> TierConfig:
    """Return ``tiers[name]`` or raise :class:`UnknownTierError`."""
    try:
        return tiers[name]
    except KeyError as exc:
        raise UnknownTierError(f"Unknown tier: {name!r}") from exc
