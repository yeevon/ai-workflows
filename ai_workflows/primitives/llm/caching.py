"""Anthropic multi-breakpoint prompt-caching helpers.

Produced by M1 Task 04 (CRIT-07). Replaces the naive
"cache the last system block" pattern with Anthropic's 2026 strategy:

1. **Last tool definition** → ``cache_control = {"type": "ephemeral", "ttl": "1h"}``
2. **Last system block**   → ``cache_control = {"type": "ephemeral", "ttl": "1h"}``
3. **Conversation history** → 5-minute TTL, handled automatically by Anthropic
   (pydantic-ai passes messages through unchanged).

Why this matters
----------------
Cache keys are computed from the raw block contents. If the last system block
contains a per-call variable (``{{timestamp}}``, ``{{run_id}}``, …), every
call mints a new cache line: the hit rate is 0 and you pay cache-WRITE costs
on every turn. Cache **stable prefixes** only, and push per-call variables
into the LAST user message. :func:`validate_prompt_template` enforces this
invariant at workflow-load time.

Module contents
---------------
* :func:`apply_cache_control` — pure helper that injects ``cache_control``
  into the last tool definition and the last system block. Used by call-sites
  that build raw Anthropic requests (e.g., forensic replay, direct-SDK usage).
* :func:`build_cache_settings` — returns a pydantic-ai
  ``AnthropicModelSettings`` pre-populated with the cache keys when the
  tier's :class:`ClientCapabilities` advertises prompt caching; returns
  ``None`` for providers that do not support it. Pass the result to
  ``Agent(model_settings=...)`` or ``agent.run(..., model_settings=...)``.
* :func:`validate_prompt_template` — regex lint that rejects prompt files
  containing ``{{var}}`` substitutions. Called at workflow load (M3).
* :class:`PromptTemplateError` — raised by :func:`validate_prompt_template`.

Related tasks
-------------
* :mod:`ai_workflows.primitives.llm.model_factory` (Task 03) builds the
  pydantic-ai ``AnthropicModel`` this helper's settings are attached to.
* ``Worker`` / ``AgentLoop`` components (M2) are expected to call
  :func:`build_cache_settings` when constructing their per-tier agents.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any, Literal

from pydantic_ai.models.anthropic import AnthropicModelSettings

from ai_workflows.primitives.llm.types import ClientCapabilities

__all__ = [
    "PromptTemplateError",
    "apply_cache_control",
    "build_cache_settings",
    "validate_prompt_template",
]


# Matches ``{{ var }}`` / ``{{var.sub}}`` Jinja-style substitutions. Deliberately
# narrow: only dotted identifiers, no function calls or pipes. We want to flag
# the common foot-gun (`{{timestamp}}` in a system prompt) without tripping on
# unrelated ``{{ }}`` content that may appear in documentation blocks inside a
# prompt (e.g. code samples for the model to study).
_TEMPLATE_VAR_RE = re.compile(r"\{\{\s*([A-Za-z_][\w.]*)\s*\}\}")


class PromptTemplateError(ValueError):
    """Raised when a system-prompt file contains per-call template variables.

    Per-call variables (``{{timestamp}}``, ``{{run_id}}``, …) break prompt
    caching: each call produces a different system-block hash, so the cache
    never hits. Variables belong in the LAST user message — the system
    prefix must stay static so it can be cached with a 1-hour TTL.
    """


def apply_cache_control(
    system_blocks: list[dict[str, Any]],
    tool_definitions: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    *,
    ttl: Literal["5m", "1h"] = "1h",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Return ``(system_blocks, tool_definitions, messages)`` with cache breakpoints applied.

    The three inputs are **not mutated**; the function returns deep-copied
    lists with ``cache_control`` attached to:

    * the last entry of ``tool_definitions`` (if any)
    * the last entry of ``system_blocks`` (if any)

    ``messages`` is returned as a (deep-copied) passthrough: Anthropic caches
    conversation history automatically with a 5-minute TTL, and pydantic-ai
    forwards the list unchanged, so no manual breakpoint is required.

    Parameters
    ----------
    system_blocks:
        The ``system`` field of an Anthropic Messages request — a list of
        ``{"type": "text", "text": "..."}`` blocks. MUST be static; see
        :func:`validate_prompt_template`.
    tool_definitions:
        The ``tools`` field. Any list of tool-definition dicts (the function
        does not inspect their shape beyond attaching ``cache_control``).
    messages:
        The ``messages`` field. Passed through untouched.
    ttl:
        Cache TTL to apply to the two explicit breakpoints. Anthropic
        supports ``"5m"`` and ``"1h"`` (default here).

    Returns
    -------
    tuple
        ``(system_blocks, tool_definitions, messages)`` — new lists, safe for
        the caller to mutate without affecting the originals.
    """
    new_system = copy.deepcopy(system_blocks)
    new_tools = copy.deepcopy(tool_definitions)
    new_messages = copy.deepcopy(messages)

    breakpoint = {"type": "ephemeral", "ttl": ttl}

    if new_tools:
        new_tools[-1]["cache_control"] = dict(breakpoint)
    if new_system:
        new_system[-1]["cache_control"] = dict(breakpoint)

    return new_system, new_tools, new_messages


def build_cache_settings(
    caps: ClientCapabilities,
    *,
    ttl: Literal["5m", "1h"] = "1h",
) -> AnthropicModelSettings | None:
    """Return model_settings that enable multi-breakpoint caching, or ``None``.

    pydantic-ai 1.x exposes prompt-caching as typed settings on
    ``AnthropicModelSettings``: it injects ``cache_control`` into the last
    tool definition and the last system block at request time, implementing
    exactly the strategy :func:`apply_cache_control` performs on raw lists.

    When ``caps.supports_prompt_caching`` is ``True`` (today: only the
    Anthropic provider), return an ``AnthropicModelSettings`` with the two
    cache keys set. When it is ``False``, return ``None`` — other providers
    do not have an equivalent hook, and we do not want callers to pass
    Anthropic-specific settings to non-Anthropic models.

    Call-site pattern::

        model, caps = build_model("sonnet", tiers, cost_tracker)
        settings = build_cache_settings(caps)
        agent = Agent(model, model_settings=settings, ...)
    """
    if not caps.supports_prompt_caching:
        return None
    return AnthropicModelSettings(
        anthropic_cache_tool_definitions=ttl,
        anthropic_cache_instructions=ttl,
    )


def validate_prompt_template(path: str | Path) -> None:
    """Raise :class:`PromptTemplateError` if ``path`` contains ``{{var}}`` substitutions.

    Intended to be called at workflow-load time (M3) on every file that will
    be wired into a **system** prompt. Per-call variables (``{{timestamp}}``,
    ``{{run_id}}``, …) must be rendered into the last user message instead so
    the cached system prefix stays stable turn-over-turn.

    Parameters
    ----------
    path:
        Path to a prompt file. Read as UTF-8 text.

    Raises
    ------
    PromptTemplateError
        If any ``{{identifier}}`` or ``{{dotted.path}}`` substitution is
        found. The error message lists every offending token.
    FileNotFoundError
        If ``path`` does not exist.
    """
    text = Path(path).read_text(encoding="utf-8")
    matches = _TEMPLATE_VAR_RE.findall(text)
    if matches:
        unique = sorted(set(matches))
        raise PromptTemplateError(
            f"{path}: system prompt contains templated variables "
            f"{unique!r}. Variables MUST go in the LAST user message so "
            f"the cached system prefix stays stable across calls."
        )
