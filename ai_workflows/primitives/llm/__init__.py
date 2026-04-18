"""LLM primitives — typed messages, model factory, and prompt caching.

Modules (filled in by later M1 tasks):

* ``types`` (Task 02) — ``ContentBlock`` discriminated union, ``Message``,
  ``Response``, and the ``ClientCapabilities`` descriptor used to advertise
  per-provider features (prompt caching, tool use, vision, …) without the
  callers having to ``isinstance``-sniff the underlying client.
* ``model_factory`` (Task 03) — ``build_model(tier_name)`` reads
  ``tiers.yaml`` and returns a configured pydantic-ai ``Model`` with
  ``max_retries=0`` (we own retries via :mod:`ai_workflows.primitives.retry`).
* ``caching`` (Task 04) — Anthropic multi-breakpoint cache helpers used by
  the model factory and by Worker/AgentLoop call sites.
"""
