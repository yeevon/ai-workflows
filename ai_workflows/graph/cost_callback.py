"""CostTrackingCallback (M2 Task 06 — KDR-004 pairing,
[architecture.md §4.2 / §8.5](../../design_docs/architecture.md)).

Explicit per-node boundary that routes :class:`TokenUsage` rows from
provider calls into :class:`ai_workflows.primitives.cost.CostTracker` and
enforces the per-run budget cap. The surface is a single synchronous
method (``on_node_complete``) rather than a LangGraph internal hook so
the boundary is trivially unit-testable and decoupled from LangGraph
version churn.

Relationship to sibling modules
-------------------------------
* ``graph/tiered_node.py`` (M2 Task 03) — the only invoker. Each
  ``TieredNode`` call records exactly one ``TokenUsage`` and, if a cap
  is set, runs exactly one ``check_budget``. Structured logging stays
  on the ``TieredNode`` side; this module does not emit logs.
* ``primitives/cost.py`` — provides :class:`CostTracker` (the write +
  read surface) and :class:`TokenUsage` (the ledger record). Sub-model
  roll-up (Claude Code ``modelUsage``) is ``CostTracker``'s concern;
  this callback just hands the top-level row over.
* ``primitives/retry.py`` — ``CostTracker.check_budget`` raises
  :class:`NonRetryable` on overage; the callback re-raises transparently
  so ``RetryingEdge`` (M2 Task 07) can treat budget breach as a
  terminal bucket per the three-bucket taxonomy (§8.2 / §8.5).

No in-house pricing or aggregation logic lives here — the callback is
a thin, synchronous forwarder so the budget-check invariant ("exactly
one record + one check when capped") is obvious from the body.
"""

from __future__ import annotations

from ai_workflows.primitives.cost import CostTracker, TokenUsage

__all__ = ["CostTrackingCallback"]


class CostTrackingCallback:
    """Record ``TokenUsage`` and enforce a per-run budget cap.

    The callback owns no state of its own beyond the injected
    :class:`CostTracker` and the optional cap. ``on_node_complete`` is
    the single invocation surface: one ``record`` and, if a cap is
    set, one ``check_budget``. Budget breach surfaces as
    :class:`ai_workflows.primitives.retry.NonRetryable` —
    :meth:`CostTracker.check_budget` raises it directly and this
    callback does not swallow it.
    """

    def __init__(
        self,
        cost_tracker: CostTracker,
        budget_cap_usd: float | None,
    ) -> None:
        """Wire the callback to a tracker and an optional budget cap.

        Parameters
        ----------
        cost_tracker:
            Shared :class:`CostTracker` keyed by ``run_id``. The
            callback does not construct one; callers pass the graph's
            tracker so every node writes to the same ledger.
        budget_cap_usd:
            Maximum USD the run may spend. ``None`` disables
            enforcement — ``on_node_complete`` then records usage
            without ever calling :meth:`CostTracker.check_budget`.
        """
        self._tracker = cost_tracker
        self._cap = budget_cap_usd

    def on_node_complete(
        self,
        run_id: str,
        node_name: str,  # noqa: ARG002 — kept in signature so TieredNode can pass it without branching
        usage: TokenUsage,
    ) -> None:
        """Record ``usage`` and, if a cap is set, check the run's budget.

        Parameters
        ----------
        run_id:
            The run whose ledger the entry belongs to. Matches the
            ``run_id`` column on the ``runs`` table and the
            ``thread_id`` the LangGraph checkpointer uses.
        node_name:
            Identifier of the ``TieredNode`` that produced the usage
            row. Carried in the signature so the caller passes it
            unconditionally; not consumed here because sub-model roll
            up and per-run aggregation are the tracker's concern.
        usage:
            The freshly produced :class:`TokenUsage` for the node
            invocation, already cost-enriched by the provider driver
            (LiteLLM or the Claude Code subprocess).

        Raises
        ------
        NonRetryable
            If ``budget_cap_usd`` is set and
            :meth:`CostTracker.total` for ``run_id`` now exceeds it.
        """
        self._tracker.record(run_id, usage)
        if self._cap is not None:
            self._tracker.check_budget(run_id, self._cap)
