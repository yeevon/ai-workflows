"""Error-handler wrapper for bucket-raising nodes (M2 Task 08 carry-over —
M2-T07-ISS-01, KDR-006 / KDR-009,
[architecture.md §4.2 / §8.2 / §8.4](../../design_docs/architecture.md)).

M8 T04 update: the wrapper also recognises
:class:`ai_workflows.primitives.circuit_breaker.CircuitOpen` and writes
``last_exception=exc`` *without* bumping either the per-node retry
counter or the run-wide ``_non_retryable_failures`` counter. This keeps
the Ollama-outage fallback gate (architecture.md §8.4) a one-off pause
rather than a double-failure hard-stop trigger, and lets ``RETRY`` /
``FALLBACK`` resume with a clean transient-retry budget.

Converts a node that *raises* one of the three retry-taxonomy buckets
(:class:`RetryableTransient` / :class:`RetryableSemantic` /
:class:`NonRetryable`) into a node that *returns* the state-update
shape :class:`ai_workflows.graph.retrying_edge.retrying_edge` reads:

    {
        "last_exception": exc,
        "_retry_counts": {**prev, node_name: prev.get(node_name, 0) + 1},
        "_non_retryable_failures": prev + (1 if NonRetryable else 0),
    }

Why this wrapper exists
-----------------------
:class:`retrying_edge` is a pure ``(state) -> str`` router — it cannot
observe a raised exception that was never stored in state. M2 Task 03
and M2 Task 04 both *raise* their classified buckets (preserving the
"adapter raises ``RateLimitError`` → node raises ``RetryableTransient``"
test contract). A LangGraph-native error handler has to sit between the
raising site and the retry edge so the edge has something to route on.
The deferred audit issue M2-T07-ISS-01 assigned that wrapper to T08 and
named the exact dict shape reproduced above. Every value the wrapper
writes rides LangGraph's :class:`SqliteSaver` (KDR-009) alongside the
rest of the graph state, so counters survive a :func:`interrupt` + resume
round trip.

Why the wrapper, not an inline ``try/except`` in every workflow
---------------------------------------------------------------
Centralising the counter-increment shape in one module means every
workflow author writes the retry loop the same way — a concrete
template the T07 audit asked T08 to surface for M3 workflow authors
to copy. Inlining would re-introduce the "copy-paste a six-line
``try/except``" pattern the wrapper was designed to eliminate.

Signature compatibility
-----------------------
LangGraph nodes may accept either ``(state)`` or ``(state, config)``.
The wrapper inspects the wrapped callable's signature once at factory
time and dispatches accordingly — so it wraps both
:func:`ai_workflows.graph.tiered_node.tiered_node` (which accepts
config) and :func:`ai_workflows.graph.validator_node.validator_node`
(which does not) without mutation to either site. The returned
wrapper itself always accepts ``(state, config=None)`` so LangGraph's
runtime can freely pass a ``RunnableConfig``.
"""

import inspect
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from langchain_core.runnables import RunnableConfig

from ai_workflows.primitives.circuit_breaker import CircuitOpen
from ai_workflows.primitives.retry import (
    NonRetryable,
    RetryableSemantic,
    RetryableTransient,
)

__all__ = ["wrap_with_error_handler"]

GraphState = Mapping[str, Any]
_Bucket = RetryableTransient | RetryableSemantic | NonRetryable
NodeFn = Callable[..., Awaitable[dict[str, Any]]]


def wrap_with_error_handler(
    node: NodeFn,
    *,
    node_name: str,
) -> Callable[[GraphState, RunnableConfig | None], Awaitable[dict[str, Any]]]:
    """Return a LangGraph node that converts bucket exceptions into state writes.

    Parameters
    ----------
    node:
        An ``async`` LangGraph node that may raise
        :class:`RetryableTransient` / :class:`RetryableSemantic` /
        :class:`NonRetryable`. Nodes that accept ``(state)`` or
        ``(state, config)`` are both supported; the wrapper inspects
        the signature at factory time and forwards arguments
        accordingly.
    node_name:
        Key under which to bump ``state['_retry_counts']`` on failure.
        Must match the ``on_transient`` / ``on_semantic`` destination
        the paired :func:`retrying_edge` routes to so attempt-budget
        accounting stays consistent.

    Returns
    -------
    An ``async`` ``(state, config=None) -> dict`` callable. On
    exception it returns the retry-state dict (see module docstring);
    on success it returns whatever ``node`` returned (which, for
    :func:`tiered_node`, already includes ``{"last_exception": None}``
    per the T07 carry-over, clearing any stale classified exception).
    """
    accepts_config = _wrapped_node_takes_config(node)

    async def _wrapped(
        state: GraphState, config: RunnableConfig | None = None
    ) -> dict[str, Any]:
        try:
            if accepts_config:
                return await node(state, config)
            return await node(state)
        except CircuitOpen as exc:
            # M8 T04: CircuitOpen bypasses the retry-counter bumping because
            # the workflow's ``catch_circuit_open`` edge routes directly to
            # the fallback ``HumanGate`` (architecture.md §8.4). Counting it
            # as a NonRetryable would double-bump the hard-stop counter when
            # the breaker is shared across parallel branches (one trip, N
            # raises) and would also burn through the per-node transient
            # budget that the operator's ``RETRY`` choice is meant to
            # restart cleanly. Writing ``last_exception`` is sufficient —
            # the workflow edge checks ``isinstance(exc, CircuitOpen)``
            # before delegating to :func:`retrying_edge`.
            return {"last_exception": exc}
        except (RetryableTransient, RetryableSemantic, NonRetryable) as exc:
            return _failure_state_update(state, exc, node_name=node_name)

    return _wrapped


def _wrapped_node_takes_config(node: NodeFn) -> bool:
    """Return ``True`` if ``node`` accepts a second positional arg (``config``).

    LangGraph's ``StateGraph`` introspects node signatures and passes
    ``RunnableConfig`` to nodes that declare it. The wrapper mirrors
    that convention so it can wrap both shapes without touching the
    underlying node.
    """
    try:
        sig = inspect.signature(node)
    except (TypeError, ValueError):
        return False
    positional = [
        p
        for p in sig.parameters.values()
        if p.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    return len(positional) >= 2


def _failure_state_update(
    state: GraphState,
    exc: _Bucket,
    *,
    node_name: str,
) -> dict[str, Any]:
    """Build the retry-state dict from a prior state + a caught bucket.

    Reads ``state['_retry_counts']`` / ``state['_non_retryable_failures']``
    defensively (``.get`` + ``or {}`` / ``or 0``) so nodes wrapped before
    any retry has occurred still produce a valid first-failure dict.
    Returns a *fresh* ``_retry_counts`` dict — we never mutate the
    incoming state, which may be a read-only checkpoint snapshot.
    """
    prev_counts = dict(state.get("_retry_counts") or {})
    prev_counts[node_name] = prev_counts.get(node_name, 0) + 1
    prev_failures = state.get("_non_retryable_failures") or 0
    bumped_failures = prev_failures + (1 if isinstance(exc, NonRetryable) else 0)
    return {
        "last_exception": exc,
        "_retry_counts": prev_counts,
        "_non_retryable_failures": bumped_failures,
    }
