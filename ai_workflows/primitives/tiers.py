"""Tier configuration model.

Produced by M1 Task 03 (minimal stub). M1 Task 07 expands this module with
``load_tiers()``, ``load_pricing()``, and full YAML config parsing with env
var expansion and profile overlays.

The ``TierConfig`` model defined here is the single source of truth for tier
shape — Task 07 imports and re-exports it rather than redefining it.
"""

from typing import Literal

from pydantic import BaseModel


class TierConfig(BaseModel):
    """Configuration for a single model tier as loaded from tiers.yaml."""

    provider: Literal["anthropic", "ollama", "openai_compat", "google"]
    model: str
    max_tokens: int
    temperature: float
    base_url: str | None = None
    api_key_env: str | None = None
    # Number of retries by OUR retry layer (Task 10); the underlying SDK is always 0.
    max_retries: int = 3
