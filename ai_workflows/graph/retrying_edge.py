"""RetryingEdge (M2 Task 07 — KDR-006,
[architecture.md §4.2 / §8.2](../../design_docs/architecture.md)).

LangGraph conditional-edge factory that routes by the three-bucket
retry taxonomy. The edge is a pure ``(state) -> str`` router: it
reads the latest classified exception and the durable attempt
counters out of graph state and returns the next node name. Counters
themselves are written upstream (by the raising node or by the
self-loop target on re-entry) so they ride LangGraph's checkpointer
(KDR-009) and survive a resume after ``HumanGate`` or a crash.

Relationship to sibling modules
-------------------------------
* ``primitives/retry.py`` — defines the three bucket exceptions
  (:class:`RetryableTransient`, :class:`RetryableSemantic`,
  :class:`NonRetryable`) and :class:`RetryPolicy`. This edge consumes
  them as types; classification itself happens upstream per KDR-006
  (see M1 Task 07).
* ``graph/tiered_node.py`` (M2 Task 03) — raises-and-classifies the
  transient bucket for LLM-call failures the edge then routes around.
* ``graph/validator_node.py`` (M2 Task 04) — raises the semantic
  bucket with a ``revision_hint`` that this edge preserves
  transparently (the hint lives on the exception instance already
  stored in ``state['last_exception']``; the edge does not copy or
  touch it).
* ``graph/audit_cascade.py`` (M12 T02) — emits :class:`AuditFailure`
  (a ``RetryableSemantic`` subclass) from the audit-verdict node when
  the auditor reports ``passed=False``. This edge routes it back to
  the primary ``tiered_node`` via the same ``on_semantic`` hop used for
  shape failures; the primary picks up the rendered audit-feedback
  template via ``state['last_exception'].revision_hint`` on re-entry.

Exponential backoff is **not** implemented here — per the spec it
belongs in the self-loop target as an ``asyncio.sleep`` wrapper so
the edge stays a pure routing function and can be unit-tested
without time-advance fixtures. ``RetryPolicy.transient_backoff_*`` is
read by the target, not by this module.

Double-failure hard-stop (§8.2): the edge checks
``state['_non_retryable_failures']`` before any bucket dispatch, so a
second non-retryable failure anywhere in the run forces the terminal
path regardless of the current bucket.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from ai_workflows.primitives.retry import (
    RetryableSemantic,
    RetryableTransient,
    RetryPolicy,
)

__all__ = ["retrying_edge"]

GraphState = Mapping[str, Any]


def retrying_edge(
    *,
    on_transient: str,
    on_semantic: str,
    on_terminal: str,
    policy: RetryPolicy,
) -> Callable[[GraphState], str]:
    """Build a LangGraph conditional-edge function routing by retry bucket.

    The returned callable inspects ``state['last_exception']`` (the
    classified exception instance written by the upstream
    :class:`ai_workflows.graph.tiered_node.TieredNode` /
    :class:`validator_node` on failure) together with the durable
    per-node attempt counters at ``state['_retry_counts']`` and the
    run-scoped non-retryable counter at
    ``state['_non_retryable_failures']``.

    Parameters
    ----------
    on_transient:
        Node name to route to for :class:`RetryableTransient`. The
        typical wiring is a self-loop back to the raising node so
        LiteLLM retries against the same call; the target node is
        expected to honour :attr:`RetryPolicy.transient_backoff_base_s`
        / :attr:`RetryPolicy.transient_backoff_max_s` via an
        ``asyncio.sleep`` wrapper on entry.
    on_semantic:
        Node name to route to for :class:`RetryableSemantic`. Per
        KDR-004 this is the paired LLM node (a ``TieredNode``) so it
        re-invokes the model with the hint stored on the exception.
    on_terminal:
        Destination for exhaustion, :class:`NonRetryable`, and the
        double-failure hard-stop. Typically ``"__end__"`` or a
        cleanup node.
    policy:
        Attempt budget for transient / semantic loops. Backoff
        fields are forwarded to the target node, not consumed here.

    Returns
    -------
    A synchronous ``(state) -> str`` function suitable for
    ``StateGraph.add_conditional_edges``. The function is pure —
    it does not mutate state, so it safely round-trips under
    LangGraph's checkpointer (KDR-009).
    """

    def _edge(state: GraphState) -> str:
        """Classify and route based on ``state`` (see factory docstring)."""
        if _non_retryable_failures(state) >= 2:
            return on_terminal

        exc = state.get("last_exception")
        if exc is None:
            return on_terminal

        retry_counts = _retry_counts(state)

        if isinstance(exc, RetryableTransient):
            if retry_counts.get(on_transient, 0) >= policy.max_transient_attempts:
                return on_terminal
            return on_transient

        if isinstance(exc, RetryableSemantic):
            if retry_counts.get(on_semantic, 0) >= policy.max_semantic_attempts:
                return on_terminal
            return on_semantic

        return on_terminal

    return _edge


def _retry_counts(state: GraphState) -> Mapping[str, int]:
    """Return ``state['_retry_counts']`` as a mapping, tolerating absence."""
    counts = state.get("_retry_counts")
    if counts is None:
        return {}
    return counts


def _non_retryable_failures(state: GraphState) -> int:
    """Return ``state['_non_retryable_failures']``, defaulting to ``0``."""
    value = state.get("_non_retryable_failures", 0)
    return value or 0
