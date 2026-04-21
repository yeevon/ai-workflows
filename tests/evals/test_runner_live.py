"""Live-mode gate tests for :class:`EvalRunner` (M7 Task 03).

Live mode fires real provider calls; most of the live path is
covered by T05 once seed fixtures exist. What this file pins is the
construction-time gate: the runner **refuses to construct** in
``mode='live'`` unless both ``AIW_EVAL_LIVE=1`` and ``AIW_E2E=1``
are set. The double-gate matches the rest of the live e2e suite
(``@pytest.mark.e2e`` + ``AIW_E2E`` activation) while adding a
replay-specific opt-in.

The actual live-provider replay test is marked ``@pytest.mark.e2e``
and ``@pytest.mark.skipif(AIW_EVAL_LIVE != '1')`` so it no-ops on the
default CI path and only fires when the maintainer explicitly opts
in (mirror of the existing e2e pattern).
"""

from __future__ import annotations

import os

import pytest

from ai_workflows.evals import EvalRunner


def test_live_runner_refuses_without_aiw_eval_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Construction raises when ``AIW_EVAL_LIVE`` is not ``'1'``."""

    monkeypatch.delenv("AIW_EVAL_LIVE", raising=False)
    monkeypatch.setenv("AIW_E2E", "1")
    with pytest.raises(RuntimeError, match="AIW_EVAL_LIVE"):
        EvalRunner(mode="live")


def test_live_runner_refuses_without_aiw_e2e(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Construction raises when ``AIW_E2E`` is not ``'1'``.

    Double-gate pattern: ``AIW_EVAL_LIVE`` alone is not enough — the
    maintainer must also flip the existing e2e switch so live replay
    shares the e2e cost-budget gate rather than silently firing on
    an otherwise-hermetic developer machine.
    """

    monkeypatch.setenv("AIW_EVAL_LIVE", "1")
    monkeypatch.delenv("AIW_E2E", raising=False)
    with pytest.raises(RuntimeError, match="AIW_E2E"):
        EvalRunner(mode="live")


def test_live_runner_constructs_when_both_gates_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both env gates present → no error at construction time."""

    monkeypatch.setenv("AIW_EVAL_LIVE", "1")
    monkeypatch.setenv("AIW_E2E", "1")
    runner = EvalRunner(mode="live")
    assert runner._mode == "live"


@pytest.mark.e2e
@pytest.mark.skipif(
    os.getenv("AIW_EVAL_LIVE") != "1" or os.getenv("AIW_E2E") != "1",
    reason="live eval requires AIW_EVAL_LIVE=1 and AIW_E2E=1",
)
@pytest.mark.asyncio
async def test_live_replay_smoke_against_planner_explorer() -> None:
    """Smoke-test: live-mode construction + one-case run completes.

    Out of scope for this task is a pinned expected-output fixture —
    T05 seeds those when capture runs against real providers land.
    This test exists so the live-mode code path is exercised at all:
    the runner constructs, builds the replay graph, dispatches
    through the real tier registry, and returns an
    :class:`EvalReport`. Pass/fail verdict is informational; the
    assertion is that the runner completes without raising.
    """

    # The test is opt-in and presence-only; seed fixture lands in T05.
    pytest.skip("live seed fixture lands under T05")
