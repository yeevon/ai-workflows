"""summarize_tier_registry — the tier registry for summarize.py.

Lives in a separate module from ``summarize.py`` so the spec module
itself stays pure-pydantic + spec-import. This mirrors the planner /
slice_refactor pattern (each ships an ``<workflow>_tier_registry()``
helper) but the spec-API workflow uses ``WorkflowSpec.tiers=`` rather
than the legacy ``<workflow>_tier_registry()`` getattr fallback.

Authored at M19 T04. Relationship to other modules:

* :mod:`ai_workflows.workflows.summarize` — imports this helper to
  populate ``WorkflowSpec.tiers`` at module load time.
* :mod:`ai_workflows.primitives.tiers` — ``LiteLLMRoute`` + ``TierConfig``
  are the only imports; this module has no graph-layer dependency.
"""

from __future__ import annotations

from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig


def summarize_tier_registry() -> dict[str, TierConfig]:
    """Return the tier registry for the summarize workflow.

    Single tier — ``summarize-llm`` — routes to Gemini Flash via LiteLLM
    (KDR-003: no Anthropic API; LiteLLM is the unified adapter for Gemini).
    Cheaper than Claude Code OAuth paths; faster than Ollama-routed tiers.

    Returns
    -------
    dict[str, TierConfig]
        A mapping with one entry: ``"summarize-llm"``.
    """
    return {
        "summarize-llm": TierConfig(
            name="summarize-llm",
            route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
            max_concurrency=4,
            per_call_timeout_s=120,
        ),
    }
