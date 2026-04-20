"""LiteLLM provider adapter (M2 Task 01 — KDR-007,
[architecture.md §4.1](../../../design_docs/architecture.md)).

Thin async wrapper around ``litellm.acompletion()``. Takes a resolved
``LiteLLMRoute`` plus a system prompt and message list, returns
``(text, TokenUsage)`` with LiteLLM's cost enrichment mapped into the
primitives ledger shape.

Scope discipline
----------------
* ``max_retries=0`` at the LiteLLM call site — the three-bucket retry
  taxonomy (KDR-006) runs *above* the adapter in the M2 graph layer
  via ``RetryingEdge``. Running LiteLLM's internal retry loop in
  addition would double-count attempts and distort the backoff
  budget the graph edge is measuring.
* No exception classification. LiteLLM errors pass through verbatim;
  ``TieredNode`` (M2 Task 03) is the classification boundary.
* No caching, no provider fallback — fallback is a graph-edge
  concern, not an adapter concern.

Relationship to sibling modules
-------------------------------
* ``primitives/tiers.py`` — owns ``LiteLLMRoute``, the input to this
  adapter's ``__init__``.
* ``primitives/cost.py`` — owns ``TokenUsage``, the second half of the
  adapter's return tuple.
* ``primitives/retry.py`` — classifies the LiteLLM exceptions this
  adapter re-raises; the adapter itself is classification-free.
"""

from __future__ import annotations

from typing import Any

import litellm
from pydantic import BaseModel

from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.tiers import LiteLLMRoute

__all__ = ["LiteLLMAdapter"]


class LiteLLMAdapter:
    """Wrap ``litellm.acompletion`` into the ``(text, TokenUsage)`` primitive shape.

    Constructed with a resolved ``LiteLLMRoute`` (from
    ``TierRegistry``) and a per-call wall-clock timeout. One instance
    per tier is the intended pattern; call :meth:`complete` for each
    model invocation.
    """

    def __init__(self, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        self._route = route
        self._per_call_timeout_s = per_call_timeout_s

    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict],
        response_format: type[BaseModel] | None = None,
    ) -> tuple[str, TokenUsage]:
        """Call ``litellm.acompletion`` and return ``(text, TokenUsage)``.

        ``system`` is prepended as a ``{"role": "system", ...}`` entry
        when supplied, otherwise the caller's ``messages`` list is
        sent verbatim. ``response_format`` is forwarded to LiteLLM
        unchanged — LiteLLM drives the native pydantic structured-
        output path on providers that support it (KDR-004's validator
        stays a separate node regardless).

        ``max_retries=0`` disables LiteLLM's internal single-call
        retry; the three-bucket taxonomy (KDR-006) runs above this
        adapter via ``RetryingEdge``. Exceptions pass through verbatim
        — ``TieredNode`` (M2 Task 03) is the classification boundary,
        not this adapter.
        """
        payload: list[dict[str, Any]] = []
        if system is not None:
            payload.append({"role": "system", "content": system})
        payload.extend(messages)

        kwargs: dict[str, Any] = {
            "model": self._route.model,
            "messages": payload,
            "timeout": self._per_call_timeout_s,
            "max_retries": 0,
        }
        if self._route.api_base is not None:
            kwargs["api_base"] = self._route.api_base
        if response_format is not None:
            kwargs["response_format"] = response_format

        response = await litellm.acompletion(**kwargs)

        text = _extract_text(response)
        usage = _extract_usage(response, model=self._route.model)
        return text, usage


def _extract_text(response: Any) -> str:
    """Return the assistant message body from a LiteLLM completion response."""
    choices = getattr(response, "choices", None) or []
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    if message is None:
        return ""
    content = getattr(message, "content", None)
    return content or ""


def _extract_usage(response: Any, *, model: str) -> TokenUsage:
    """Map ``response.usage`` onto :class:`TokenUsage`.

    ``cost_usd`` is sourced from ``response.usage.cost_usd`` per the
    task spec; ``response._hidden_params['response_cost']`` is the
    documented fall-back channel LiteLLM uses for providers that
    expose cost via hidden params only (e.g. Ollama, where LiteLLM
    reports a zero cost but still surfaces the field).
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        input_tokens = 0
        output_tokens = 0
        cost_usd = 0.0
    else:
        input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        cost_usd = float(getattr(usage, "cost_usd", 0.0) or 0.0)

    if not cost_usd:
        hidden = getattr(response, "_hidden_params", None) or {}
        cost_usd = float(hidden.get("response_cost", 0.0) or 0.0)

    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        model=model,
    )
