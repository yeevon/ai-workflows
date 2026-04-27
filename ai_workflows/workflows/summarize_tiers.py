"""summarize_tier_registry — the tier registry for summarize.py.

Lives in a separate module from ``summarize.py`` so the spec module
itself stays pure-pydantic + spec-import. This mirrors the planner /
slice_refactor pattern (each ships an ``<workflow>_tier_registry()``
helper) but the spec-API workflow uses ``WorkflowSpec.tiers=`` rather
than the legacy ``<workflow>_tier_registry()`` getattr fallback.

Authored at M19 T04. M12 Task 01 adds ``auditor-sonnet`` and
``auditor-opus`` directly to this registry (not via planner composition)
because ``summarize`` does not compose ``planner_tier_registry()`` —
the entries must be declared here for the cascade to resolve them via
the workflow's own registry.

Relationship to other modules:

* :mod:`ai_workflows.workflows.summarize` — imports this helper to
  populate ``WorkflowSpec.tiers`` at module load time.
* :mod:`ai_workflows.primitives.tiers` — ``ClaudeCodeRoute``,
  ``LiteLLMRoute``, and ``TierConfig`` are the only imports; this
  module has no graph-layer dependency.
"""

from __future__ import annotations

from ai_workflows.primitives.tiers import ClaudeCodeRoute, LiteLLMRoute, TierConfig


def summarize_tier_registry() -> dict[str, TierConfig]:
    """Return the tier registry for the summarize workflow.

    ``summarize-llm`` routes to Gemini Flash via LiteLLM (KDR-003: no
    Anthropic API; LiteLLM is the unified adapter for Gemini). Cheaper
    than Claude Code OAuth paths; faster than Ollama-routed tiers.

    M12 Task 01 adds ``auditor-sonnet`` and ``auditor-opus`` — the
    auditor tiers for the tiered audit cascade (ADR-0004 / KDR-011).
    Because ``summarize`` runs on Gemini Flash, KDR-011's scope rule
    (output read by the user) makes ``auditor-sonnet`` the natural
    auditor ceiling. Both tiers are added here directly (not via planner
    composition) so ``AuditCascadeNode`` (T02) can resolve them through
    this workflow's own registry. ``max_concurrency=1`` and
    ``per_call_timeout_s=300`` match the ``planner-synth`` baseline
    (single OAuth session, same subprocess spawn characteristics).

    Returns
    -------
    dict[str, TierConfig]
        Mapping with entries for ``"summarize-llm"``, ``"auditor-sonnet"``,
        and ``"auditor-opus"``.
    """
    return {
        "summarize-llm": TierConfig(
            name="summarize-llm",
            route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
            max_concurrency=4,
            per_call_timeout_s=120,
        ),
        "auditor-sonnet": TierConfig(
            name="auditor-sonnet",
            route=ClaudeCodeRoute(cli_model_flag="sonnet"),
            max_concurrency=1,
            per_call_timeout_s=300,
        ),
        "auditor-opus": TierConfig(
            name="auditor-opus",
            route=ClaudeCodeRoute(cli_model_flag="opus"),
            max_concurrency=1,
            per_call_timeout_s=300,
        ),
    }
