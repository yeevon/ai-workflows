"""Cost tracking, budget enforcement, and the CostTracker implementation.

Produced by M1 Task 09 (CRIT-03, P-32 … P-35). Builds on the Task 07 pricing
loader and the Task 08 storage layer to turn every LLM call into a priced,
logged, and budget-checked transaction.

Responsibilities
----------------
* :func:`calculate_cost` — pure function that multiplies a ``TokenUsage`` by
  a ``ModelPricing`` row and divides by 1e6. Returns ``0.0`` for models not
  in the pricing table (with a structured WARNING) so a missing entry never
  crashes a workflow.
* :class:`BudgetExceeded` — the exception the tracker raises when a run's
  total cost crosses ``budget_cap_usd``. Carries ``run_id``,
  ``current_cost``, and ``cap`` so the Pipeline / Orchestrator can log the
  failure and mark the run ``failed`` with reason ``budget_exceeded``.
* :class:`CostTracker` — concrete implementation. Wraps a
  :class:`~ai_workflows.primitives.storage.StorageBackend`, a pricing
  mapping, and an optional ``budget_cap_usd``. Every ``record()`` call
  persists one ``llm_calls`` row and re-runs the ``get_total_cost`` SUM
  aggregate; if the new total crosses the cap, :class:`BudgetExceeded`
  fires **after** the row is written so the run log preserves the exact
  state at the moment of the budget breach.

Design notes
------------
* The protocol used by the Task 03 model factory is this same class. It is
  still runtime-checkable via duck typing (``MagicMock(spec=CostTracker)``
  in the existing ``test_model_factory.py`` continues to work) because
  ``record()`` keeps its Task 03 signature. A separate ``Protocol`` class
  is not needed — Python's structural type-checking is adequate.
* Running total is never cached in the tracker — we always ask the storage
  backend via ``get_total_cost``, so a second ``CostTracker`` that mounts
  the same DB reads the true aggregate. This matches the M4 checkpoint /
  resume story (CRIT-02 + P-30).
* ``runs.total_cost_usd`` is intentionally **not** stamped from within
  ``record()``. The Pipeline / Orchestrator stamps it once on terminal
  state via ``storage.update_run_status("completed", total_cost_usd=...)``.
  The tracker's source of truth is the ``llm_calls`` SUM aggregate; the
  column is a denormalised cache filled at run end.

See also
--------
* ``primitives/tiers.py`` — :class:`ModelPricing` and ``load_pricing()``.
* ``primitives/storage.py`` — :class:`StorageBackend` methods the tracker
  relies on (``log_llm_call``, ``get_total_cost``, ``get_cost_breakdown``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from ai_workflows.primitives.llm.types import TokenUsage
from ai_workflows.primitives.tiers import ModelPricing

if TYPE_CHECKING:
    from ai_workflows.primitives.storage import StorageBackend


logger = structlog.get_logger(__name__)


class BudgetExceeded(Exception):
    """Raised by :class:`CostTracker` when a run crosses ``budget_cap_usd``.

    The Pipeline / Orchestrator catches this, marks the run ``failed``
    with reason ``budget_exceeded``, and cancels any in-flight sibling
    tasks (pattern lands with M2 ``Pipeline``). Completed rows stay in
    the run log — the ``llm_calls`` row that triggered the breach is
    persisted before the exception fires.
    """

    def __init__(self, run_id: str, current_cost: float, cap: float) -> None:
        self.run_id = run_id
        self.current_cost = current_cost
        self.cap = cap
        super().__init__(
            f"Run {run_id} exceeded budget: ${current_cost:.2f} > ${cap:.2f} cap"
        )


def calculate_cost(
    model: str,
    usage: TokenUsage,
    pricing: dict[str, ModelPricing],
) -> float:
    """Return the USD cost of a single LLM call.

    Computes ``(in·in_rate + out·out_rate + cr·cr_rate + cw·cw_rate) / 1e6``
    where rates come from the ``ModelPricing`` row keyed by ``model``.
    Models not in the pricing mapping log a structured WARNING and return
    ``0.0`` — a missing entry is a config gap, not a workflow-halting bug.
    Claude Max tiers (all rates ``0.0``) naturally return ``0.0`` via the
    math; the ``is_local`` short-circuit in :class:`CostTracker` is for
    Ollama-style flows that want the row tagged ``is_local=1`` regardless
    of whether pricing is declared.
    """
    row = pricing.get(model)
    if row is None:
        logger.warning("cost.model_not_in_pricing", model=model)
        return 0.0
    cost = (
        usage.input_tokens * row.input_per_mtok
        + usage.output_tokens * row.output_per_mtok
        + usage.cache_read_tokens * row.cache_read_per_mtok
        + usage.cache_write_tokens * row.cache_write_per_mtok
    ) / 1_000_000
    return cost


class CostTracker:
    """Cost tracker with budget enforcement for a single workflow run.

    One instance per run. ``budget_cap_usd=None`` disables the cap but
    emits a WARNING at construction (the common case for dev workflows —
    called out so the user never *accidentally* ends up uncapped).

    Example
    -------
    >>> storage = await SQLiteStorage.open("~/.ai-workflows/runs.db")
    >>> pricing = load_pricing()
    >>> tracker = CostTracker(storage, pricing, budget_cap_usd=5.00)
    >>> await tracker.record(
    ...     run_id="r1",
    ...     workflow_id="wf",
    ...     component="worker",
    ...     tier="gemini_flash",
    ...     model="gemini-2.0-flash",
    ...     usage=TokenUsage(input_tokens=1000, output_tokens=500),
    ... )
    0.00030  # ($0.10/MTok in + $0.40/MTok out → 1e3·1e-7 + 5e2·4e-7)
    """

    def __init__(
        self,
        storage: StorageBackend,
        pricing: dict[str, ModelPricing],
        budget_cap_usd: float | None = None,
    ) -> None:
        self._storage = storage
        self._pricing = pricing
        self._budget_cap_usd = budget_cap_usd
        if budget_cap_usd is None:
            # AC: `null` budget cap logs a warning on run start. Emitted here
            # because the tracker's construction happens once per run.
            logger.warning(
                "cost.no_budget_cap",
                message="No budget cap set — runs can consume unlimited cost.",
            )

    @property
    def budget_cap_usd(self) -> float | None:
        """The cap the tracker was constructed with (or ``None`` if disabled)."""
        return self._budget_cap_usd

    async def record(
        self,
        run_id: str,
        workflow_id: str,
        component: str,
        tier: str,
        model: str,
        usage: TokenUsage,
        task_id: str | None = None,
        is_local: bool = False,
        is_escalation: bool = False,
    ) -> float:
        """Price the call, persist it, and enforce the budget cap.

        Order of operations matters:

        1. Compute ``cost`` — ``0.0`` if ``is_local`` (Ollama) or if the
           model isn't in pricing (WARNING logged once).
        2. Persist the row via ``storage.log_llm_call`` — the run log
           always reflects the actual call, even if step 3 raises.
        3. Re-aggregate the run total via ``storage.get_total_cost``.
        4. If ``budget_cap_usd`` is set and ``new_total > cap``, raise
           :class:`BudgetExceeded`. The run row is left in whatever
           status the caller last set; the Pipeline marks it ``failed``.

        Returns the USD cost of *this* call (not the running total).
        """
        cost = 0.0 if is_local else calculate_cost(model, usage, self._pricing)

        await self._storage.log_llm_call(
            run_id,
            task_id=task_id,
            workflow_id=workflow_id,
            component=component,
            tier=tier,
            model=model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            cache_write_tokens=usage.cache_write_tokens,
            cost_usd=cost,
            is_local=is_local,
            is_escalation=is_escalation,
        )

        new_total = await self._storage.get_total_cost(run_id)
        if self._budget_cap_usd is not None and new_total > self._budget_cap_usd:
            raise BudgetExceeded(run_id, new_total, self._budget_cap_usd)
        return cost

    async def run_total(self, run_id: str) -> float:
        """Return the USD total for a run (delegates to storage aggregate)."""
        return await self._storage.get_total_cost(run_id)

    async def component_breakdown(self, run_id: str) -> dict[str, float]:
        """Return ``{component: cost_usd}`` for a run (excludes local rows)."""
        return await self._storage.get_cost_breakdown(run_id)
