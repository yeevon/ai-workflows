"""Cost tracking protocol.

Produced by M1 Task 03 (protocol stub). M1 Task 09 provides the full
``CostTracker`` implementation with SQLite storage, ``calculate_cost()``,
``BudgetExceeded``, and per-run budget cap enforcement.

This module intentionally contains only the ``CostTracker`` Protocol so that
Task 03's model factory can type-check its ``cost_tracker`` parameter without
pulling in Task 09's storage dependencies.
"""

from typing import Protocol, runtime_checkable

from ai_workflows.primitives.llm.types import TokenUsage


@runtime_checkable
class CostTracker(Protocol):
    """Protocol that any cost tracker implementation must satisfy.

    Task 09 implements this protocol with SQLite-backed storage and budget cap
    enforcement. Task 03's ``run_with_cost()`` helper depends only on this
    interface so it stays decoupled from the storage layer.
    """

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
        """Record a single LLM call and return the USD cost."""
        ...
