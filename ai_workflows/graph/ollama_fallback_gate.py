"""Fallback `HumanGate` wiring for Ollama outages (M8 Task 03).

Grounding: [architecture.md §4.2 / §8.3 / §8.4](../../design_docs/architecture.md),
[KDR-001](../../design_docs/architecture.md),
[KDR-009](../../design_docs/architecture.md).

When M8 Task 04's :class:`ai_workflows.graph.TieredNode` trips the
:class:`ai_workflows.primitives.CircuitBreaker` for an Ollama-routed
tier, the workflow layer stamps three state keys and routes to the
strict-review gate this module builds:

* ``_ollama_fallback_reason`` — mirrors :attr:`CircuitBreaker.last_reason`.
* ``_ollama_fallback_count`` — consecutive-failure counter.
* ``ollama_fallback_decision`` — written by this gate on resume with a
  typed :class:`FallbackChoice` so the workflow's conditional edge can
  branch on an enum rather than a free-text string.

Three user choices: ``retry`` (one more attempt on the same tier),
``fallback`` (promote this tier to a higher one for the rest of the
run), ``abort`` (stop the run). Unknown responses default to
``RETRY`` with a WARN log — one more loop is safer than an accidental
abort, and the gate re-fires if the breaker is still open.

Relationship to sibling modules
-------------------------------
* :mod:`ai_workflows.graph.human_gate` — sibling strict-review gate
  factory. We do not wrap it here: this gate normalises the raw
  resume string into :class:`FallbackChoice` before persisting, so the
  ``gate_responses`` row always stores the canonical enum value. The
  two gates share the same :class:`StorageBackend` protocol shape
  (``record_gate`` / ``record_gate_response``) — no new storage
  primitive, no migration.
* :mod:`ai_workflows.primitives.circuit_breaker` — supplies the
  ``last_reason`` vocabulary the prompt renders.
* :mod:`ai_workflows.graph.tiered_node` (M8 Task 04) — the node that
  writes the three ``_ollama_fallback_*`` state keys before routing
  here.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from enum import StrEnum
from typing import Any

import structlog
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

__all__ = [
    "FALLBACK_DECISION_STATE_KEY",
    "FALLBACK_GATE_ID",
    "FallbackChoice",
    "build_ollama_fallback_gate",
    "render_ollama_fallback_prompt",
]

GraphState = Mapping[str, Any]

_logger = structlog.get_logger("ai_workflows.ollama_fallback_gate")


FALLBACK_GATE_ID = "ollama_fallback"
"""Canonical ``gate_id`` used by both the planner and the slice_refactor
workflows at M8 Task 04. Stable so persisted ``gate_responses`` rows are
cross-workflow grep-able."""

FALLBACK_DECISION_STATE_KEY = "ollama_fallback_decision"
"""State key the gate writes its parsed :class:`FallbackChoice` into
on resume. Read by the conditional edge the workflow layer composes
around the gate."""


class FallbackChoice(StrEnum):
    """Three responses the fallback gate accepts."""

    RETRY = "retry"
    FALLBACK = "fallback"
    ABORT = "abort"


def parse_fallback_choice(raw: str) -> FallbackChoice:
    """Normalise a resume-time response string into :class:`FallbackChoice`.

    Case-insensitive whitespace-trimmed match against the three
    canonical values. Unknown input → :attr:`FallbackChoice.RETRY` with
    a WARN log so a user typo does not silently abort a run.
    """
    normalised = raw.strip().lower() if isinstance(raw, str) else ""
    for choice in FallbackChoice:
        if normalised == choice.value:
            return choice

    _logger.warning(
        "ollama_fallback_unknown_response",
        raw=raw,
        default=FallbackChoice.RETRY.value,
    )
    return FallbackChoice.RETRY


def render_ollama_fallback_prompt(
    state: GraphState,
    *,
    tier_name: str,
    fallback_tier: str,
) -> str:
    """Render the gate prompt from state + the two pinned tier names.

    Reads only from ``state`` — no fresh probe, no network call. The
    breaker already carries the last reason and failure count; the
    workflow layer stamps them into state before routing here.
    """
    last_reason = state.get("_ollama_fallback_reason", "")
    failure_count = state.get("_ollama_fallback_count", 0)
    return (
        f"Ollama is unavailable for tier '{tier_name}'.\n"
        "\n"
        f"Last probe / call reason: {last_reason}\n"
        f"Consecutive failures: {failure_count}\n"
        "\n"
        "How do you want to proceed?\n"
        "  [retry]    — try the same tier again (one shot).\n"
        f"  [fallback] — promote this tier to '{fallback_tier}' for the rest of the run.\n"
        "  [abort]    — stop the run (status='aborted')."
    )


def build_ollama_fallback_gate(
    *,
    gate_id: str = FALLBACK_GATE_ID,
    tier_name: str,
    fallback_tier: str,
) -> Callable[[GraphState, RunnableConfig], Awaitable[dict[str, Any]]]:
    """Return a strict-review async LangGraph node for the Ollama-outage branch.

    Parameters
    ----------
    gate_id:
        Stable identifier for this gate within a run. Defaults to
        :data:`FALLBACK_GATE_ID` so every workflow converges on the same
        persisted row name; override only if a workflow needs multiple
        fallback gates in one run.
    tier_name:
        Logical name of the tripped tier (e.g. ``"local_coder"``).
    fallback_tier:
        Logical name of the higher tier the user can promote to on
        ``FallbackChoice.FALLBACK`` (e.g. ``"gemini_flash"``).

    Returns
    -------
    An ``async`` callable ``(state, config) → dict``. On first invocation
    it persists the rendered prompt via
    :meth:`StorageBackend.record_gate` and raises the LangGraph
    ``interrupt``. On resume the raw string is parsed into a
    :class:`FallbackChoice`; the parsed enum value (not the raw string)
    is persisted via :meth:`StorageBackend.record_gate_response` and
    written into ``state[FALLBACK_DECISION_STATE_KEY]``.
    """

    async def _node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
        run_id = state["run_id"]
        storage = config["configurable"]["storage"]
        prompt = render_ollama_fallback_prompt(
            state, tier_name=tier_name, fallback_tier=fallback_tier
        )

        await storage.record_gate(run_id, gate_id, prompt, True)

        payload: dict[str, Any] = {
            "gate_id": gate_id,
            "prompt": prompt,
            "strict_review": True,
            "timeout_s": None,
            "default_response_on_timeout": None,
        }
        raw = interrupt(payload)
        decision = parse_fallback_choice(raw if isinstance(raw, str) else str(raw))

        await storage.record_gate_response(run_id, gate_id, decision.value)
        return {
            f"gate_{gate_id}_response": decision.value,
            FALLBACK_DECISION_STATE_KEY: decision,
        }

    return _node
