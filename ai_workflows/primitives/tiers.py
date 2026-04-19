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
    # Number of retries by OUR retry layer (Task 10); the underlying SDK is always 0.
    max_retries: int = 3
