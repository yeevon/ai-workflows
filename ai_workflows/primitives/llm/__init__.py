"""Provider-driver primitives (M2 Task 01 + Task 02 — KDR-003, KDR-007,
[architecture.md §4.1](../../../design_docs/architecture.md)).

Subpackage that carries the post-pivot provider drivers: the LiteLLM
adapter (M2 Task 01) for Gemini + Ollama/Qwen tiers, and the
``ClaudeCodeSubprocess`` driver (M2 Task 02) for the OAuth Claude Max
CLI tiers. Both return ``(text, TokenUsage)`` and both keep retry
classification *out* of the driver — the three-bucket taxonomy
(KDR-006) runs above this layer via the M2 ``TieredNode`` /
``RetryingEdge`` pair.

Relationship to sibling modules
-------------------------------
* ``primitives/tiers.py`` — owns ``LiteLLMRoute`` / ``ClaudeCodeRoute``
  and ``ModelPricing``, the inputs to these adapters.
* ``primitives/cost.py`` — owns ``TokenUsage`` (including the
  recursive ``sub_models`` list used by the Claude Code driver's
  ``modelUsage`` breakdown), the second half of the return tuple.
* ``primitives/retry.py`` — classifies the exceptions these adapters
  re-raise (``subprocess.TimeoutExpired`` → ``RetryableTransient``;
  ``subprocess.CalledProcessError`` → ``NonRetryable`` for the Claude
  Code driver; LiteLLM's own exception hierarchy for the LiteLLM
  adapter). The adapters themselves are classification-free.
* ``primitives/llm/ollama_health.py`` (M8 Task 01) — one-shot HTTP
  probe of Ollama's ``/api/tags`` endpoint returning a typed
  :class:`HealthResult`. Consumed by the M8 circuit breaker + fallback
  gate; not invoked from the drivers themselves (driver-layer failures
  are classified via :mod:`primitives.retry`, not via a sibling probe).
"""

from ai_workflows.primitives.llm.ollama_health import (
    HealthResult,
    probe_ollama,
)

__all__ = ["HealthResult", "probe_ollama"]
