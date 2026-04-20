"""Tests for ``ai_workflows.graph.cost_callback`` (M2 Task 06).

Cover every AC from
[task_06_cost_callback.md](../../design_docs/phases/milestone_2_graph/task_06_cost_callback.md):
one ``record`` + one ``check_budget`` per invocation when a cap is set,
overage raises :class:`NonRetryable` (architecture §8.2 / §8.5), and a
``None`` cap disables enforcement entirely.
"""

from __future__ import annotations

import pytest

from ai_workflows.graph.cost_callback import CostTrackingCallback
from ai_workflows.primitives.cost import CostTracker, TokenUsage
from ai_workflows.primitives.retry import NonRetryable


class _RecordingTracker(CostTracker):
    """``CostTracker`` subclass counting ``record`` / ``check_budget`` calls."""

    def __init__(self) -> None:
        super().__init__()
        self.record_calls: list[tuple[str, TokenUsage]] = []
        self.check_budget_calls: list[tuple[str, float]] = []

    def record(self, run_id: str, usage: TokenUsage) -> None:
        self.record_calls.append((run_id, usage))
        super().record(run_id, usage)

    def check_budget(self, run_id: str, cap_usd: float) -> None:
        self.check_budget_calls.append((run_id, cap_usd))
        super().check_budget(run_id, cap_usd)


def _usage(cost: float) -> TokenUsage:
    """Build a minimal ``TokenUsage`` carrying ``cost_usd`` only."""
    return TokenUsage(cost_usd=cost, model="gemini-2.5-pro", tier="planner")


def test_on_node_complete_records_usage_through_to_tracker() -> None:
    tracker = _RecordingTracker()
    cb = CostTrackingCallback(tracker, budget_cap_usd=1.00)
    usage = _usage(0.10)

    cb.on_node_complete("r1", "plan", usage)

    assert tracker.record_calls == [("r1", usage)]
    assert tracker.total("r1") == pytest.approx(0.10)


def test_on_node_complete_runs_exactly_one_record_and_one_check_when_capped() -> None:
    """AC-1 — one ``record`` and one ``check_budget`` per invocation (cap set)."""
    tracker = _RecordingTracker()
    cb = CostTrackingCallback(tracker, budget_cap_usd=5.00)

    cb.on_node_complete("r2", "plan", _usage(0.25))

    assert len(tracker.record_calls) == 1
    assert len(tracker.check_budget_calls) == 1
    assert tracker.check_budget_calls == [("r2", 5.00)]


def test_budget_overage_raises_non_retryable() -> None:
    """AC-2 — breach uses ``NonRetryable`` from architecture §8.2."""
    tracker = _RecordingTracker()
    cb = CostTrackingCallback(tracker, budget_cap_usd=0.50)

    cb.on_node_complete("r3", "plan", _usage(0.30))  # under cap — fine

    with pytest.raises(NonRetryable, match="budget exceeded"):
        cb.on_node_complete("r3", "plan", _usage(0.40))  # pushes total to 0.70 > 0.50

    # The breaching invocation still recorded the row before the check fired.
    assert len(tracker.record_calls) == 2
    assert len(tracker.check_budget_calls) == 2


def test_no_cap_never_raises_and_never_checks_budget() -> None:
    tracker = _RecordingTracker()
    cb = CostTrackingCallback(tracker, budget_cap_usd=None)

    cb.on_node_complete("r4", "plan", _usage(1_000_000.00))
    cb.on_node_complete("r4", "plan", _usage(1_000_000.00))

    assert len(tracker.record_calls) == 2
    assert tracker.check_budget_calls == []
    assert tracker.total("r4") == pytest.approx(2_000_000.00)


def test_cap_of_zero_is_enforced_and_any_spend_breaches() -> None:
    """``0.0`` is a real cap (not a sentinel) — ``None`` is the disabler."""
    tracker = _RecordingTracker()
    cb = CostTrackingCallback(tracker, budget_cap_usd=0.0)

    with pytest.raises(NonRetryable, match="budget exceeded"):
        cb.on_node_complete("r5", "plan", _usage(0.01))

    assert tracker.check_budget_calls == [("r5", 0.0)]
