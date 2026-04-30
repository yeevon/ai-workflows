"""In-memory per-run cost ledger + budget enforcement (M1 Task 08 — KDR-007,
[architecture.md §4.1](../../design_docs/architecture.md),
[architecture.md §8.5](../../design_docs/architecture.md)).

Post-pivot the base per-call cost is supplied *before* a
``TokenUsage`` reaches this module — LiteLLM enriches its own response
objects and the (M2) Claude Code subprocess driver computes cost from
``pricing.yaml``. :class:`CostTracker` therefore does **not** price
calls; its unique value is the ``modelUsage`` sub-model breakdown
(``[architecture.md §4.1]`` — a ``claude_code`` call to ``opus`` may
internally spawn ``haiku`` sub-calls and both must be recorded) plus
per-run rollup and budget enforcement.

Responsibilities
----------------
* :class:`TokenUsage` — per-call ledger record. Carries input/output
  plus cache token counts (the Task-02 surface) and the post-pivot
  extensions: ``cost_usd`` (enriched by the provider driver), ``model``
  (for ``by_model`` rollup), ``tier`` (for ``by_tier`` rollup), and an
  optional recursive ``sub_models`` list for Claude Code's modelUsage
  breakdown.
* :class:`CostTracker` — in-memory aggregate keyed by ``run_id``. The
  whole surface is synchronous — record / total / by_tier / by_model /
  check_budget. No direct Storage coupling; the Pipeline / orchestrator
  (M2) stamps the final total onto ``runs.total_cost_usd`` via
  ``StorageBackend.update_run_status(total_cost_usd=...)`` when a run
  reaches a terminal state.
* :func:`check_budget` raises ``NonRetryable("budget exceeded")`` from
  [task 07](../../design_docs/phases/milestone_1_reconciliation/task_07_refit_retry_policy.md)
  per §8.5. The graph-level policy (M2) decides whether the breach
  aborts the run or lets independent siblings finish.

Relationship to sibling modules
-------------------------------
* ``primitives/retry.py`` — ``NonRetryable`` is the exception
  ``check_budget`` raises on breach; no other taxonomy bucket applies.
* ``primitives/tiers.py`` — still ships ``ModelPricing`` and
  ``load_pricing()`` for the M2 Claude Code driver. This module no
  longer reads ``pricing.yaml`` — that concern moves to whichever
  driver enriches ``TokenUsage.cost_usd`` before handing it back.
* ``primitives/storage.py`` — interaction is via the trimmed
  ``StorageBackend.update_run_status`` path only, called by the
  caller (M2 Pipeline) after ``tracker.total(run_id)``. No per-call
  SQL row is written from this module anymore.

The pre-pivot ``BudgetExceeded`` exception and the ``calculate_cost``
helper are removed — cost math moves to the provider-driver layer,
budget breach re-uses the three-bucket taxonomy's
``NonRetryable``.
"""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel, Field

from ai_workflows.primitives.retry import NonRetryable

__all__ = [
    "CostTracker",
    "TokenUsage",
]


class TokenUsage(BaseModel):
    """One ledger entry — enough to cost, rollup, and expand sub-models.

    Per-call record produced by the provider driver (LiteLLM-backed or
    the M2 Claude Code subprocess). Carries the Task-02 token counts
    plus the post-pivot fields needed for aggregation (``cost_usd``,
    ``model``, ``tier``) and the recursive ``sub_models`` used by
    Claude Code's ``modelUsage`` reporting: a top-level call to
    ``opus`` may spawn ``haiku`` sub-calls and both must roll into the
    per-run total.

    ``tier`` is the logical tier label ("planner" / "implementer" /
    "local_coder" / ...). It isn't one of the three fields the task
    spec names under "extend", but ``CostTracker.by_tier`` cannot
    function without it — see T08 CHANGELOG deviations.

    ``role`` (M12 T04 — KDR-011) is the cascade role tag (``"author"`` /
    ``"auditor"`` / ``"verdict"``). Empty string for non-cascade calls.
    ``CostTracker.by_role`` reads it. Stamped by :func:`tiered_node`
    before handing the record to the cost callback, mirroring the
    existing ``tier`` stamp at ``tiered_node.py:264-268``.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""
    tier: str = ""
    role: str = ""
    """M12 T04 — KDR-011: cascade role tag (``"author"`` / ``"auditor"`` /
    ``"verdict"``).  Empty string for non-cascade calls.
    ``CostTracker.by_role`` reads it.  Stamped by :func:`tiered_node` before
    handing the record to the cost callback, mirroring the existing ``tier``
    stamp at ``tiered_node.py:264-268``."""
    sub_models: list[TokenUsage] = Field(default_factory=list)


class CostTracker:
    """In-memory per-run cost aggregate — single write path, four read paths.

    One instance per process is fine; entries are keyed by ``run_id``
    so multiple concurrent runs stay disjoint. Methods are synchronous
    because every operation is a dict / list walk — there is no I/O.

    Pair with the M2 Pipeline's terminal-state handler, which calls
    ``storage.update_run_status(run_id, status, total_cost_usd=tracker.total(run_id))``
    once the graph reaches ``completed`` / ``failed``.
    """

    def __init__(self) -> None:
        self._entries: dict[str, list[TokenUsage]] = defaultdict(list)

    def record(self, run_id: str, usage: TokenUsage) -> None:
        """Append ``usage`` to the ``run_id`` ledger. The single write path."""
        self._entries[run_id].append(usage)

    def total(self, run_id: str) -> float:
        """Return the rolled-up USD total for ``run_id`` (includes sub-models)."""
        return sum(_roll_cost(entry) for entry in self._entries.get(run_id, ()))

    def by_tier(self, run_id: str) -> dict[str, float]:
        """Return ``{tier: cost_usd}`` for ``run_id``. Sub-model costs roll into
        the parent entry's tier — sub-calls inherit the orchestrating tier.
        """
        totals: dict[str, float] = defaultdict(float)
        for entry in self._entries.get(run_id, ()):
            totals[entry.tier] += _roll_cost(entry)
        return dict(totals)

    def by_model(
        self,
        run_id: str,
        include_sub_models: bool = True,
    ) -> dict[str, float]:
        """Return ``{model: cost_usd}`` for ``run_id``.

        When ``include_sub_models`` is true (the default and the
        Claude Code modelUsage path), each sub-model entry contributes
        under its own ``model`` key, so an ``opus`` call that spawns
        two ``haiku`` sub-calls shows three distinct keys.
        """
        totals: dict[str, float] = defaultdict(float)
        for entry in self._entries.get(run_id, ()):
            _accumulate_by_model(entry, totals, include_sub_models=include_sub_models)
        return dict(totals)

    def by_role(self, run_id: str) -> dict[str, float]:
        """Return ``{role: cost_usd}`` for ``run_id``. Sub-model costs roll into
        the parent entry's role — sub-calls inherit the orchestrating role.

        Empty-string role (non-cascade calls) shows under the ``""`` key.  Callers
        that want only the cascade roles can ignore the empty key with
        ``{r: c for r, c in tracker.by_role(run_id).items() if r}``.

        M12 T04 — KDR-011 telemetry: feeds the empirical-tuning loop that decides
        when to flip a workflow's ``_AUDIT_CASCADE_ENABLED_DEFAULT`` to ``True``
        (ADR-0004 §Decision item 6). Aggregating by role surfaces the
        author-vs-auditor cost split per run.
        """
        totals: dict[str, float] = defaultdict(float)
        for entry in self._entries.get(run_id, ()):
            totals[entry.role] += _roll_cost(entry)
        return dict(totals)

    def check_budget(self, run_id: str, cap_usd: float) -> None:
        """Raise ``NonRetryable("budget exceeded")`` if ``total(run_id) > cap``.

        Strict ``>`` — landing exactly on the cap does not raise. The
        exception carries a human-readable reason so log lines show
        the current total and cap.
        """
        current = self.total(run_id)
        if current > cap_usd:
            raise NonRetryable(
                f"budget exceeded: ${current:.2f} > ${cap_usd:.2f} cap for run {run_id}"
            )


def _roll_cost(entry: TokenUsage) -> float:
    """Sum ``entry.cost_usd`` plus the recursive sub-model costs."""
    return entry.cost_usd + sum(_roll_cost(child) for child in entry.sub_models)


def _accumulate_by_model(
    entry: TokenUsage,
    totals: dict[str, float],
    *,
    include_sub_models: bool,
) -> None:
    """Add ``entry.cost_usd`` to ``totals[entry.model]``; recurse if requested."""
    totals[entry.model] += entry.cost_usd
    if include_sub_models:
        for child in entry.sub_models:
            _accumulate_by_model(child, totals, include_sub_models=True)
