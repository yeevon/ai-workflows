"""Tests for ``ai_workflows.primitives.cost`` (M1 Task 09).

One test per acceptance criterion (AC-1 … AC-8) plus coverage of the
``calculate_cost`` edge cases (missing model in pricing, zero rates,
cache-read / cache-write arithmetic) and the ``BudgetExceeded`` message
format.

Storage is the real :class:`SQLiteStorage` so the cost-tracker's
integration with the Task 08 schema is pinned end-to-end; no mock layer
between the tracker and SQLite.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import structlog
from structlog.testing import capture_logs

from ai_workflows.primitives.cost import (
    BudgetExceeded,
    CostTracker,
    calculate_cost,
)
from ai_workflows.primitives.llm.types import TokenUsage
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.tiers import ModelPricing

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MIGRATIONS = REPO_ROOT / "migrations"


def _pricing() -> dict[str, ModelPricing]:
    """Pricing table used by the tracker tests.

    Matches the canonical ``pricing.yaml`` so the unit values
    (``gemini-2.0-flash`` at ``$0.10`` / ``$0.40`` per MTok) stay in
    lock-step with production pricing.
    """
    return {
        "gemini-2.0-flash": ModelPricing(
            input_per_mtok=0.10,
            output_per_mtok=0.40,
        ),
        "claude-sonnet-4-6": ModelPricing(
            input_per_mtok=3.00,
            output_per_mtok=15.00,
            cache_read_per_mtok=0.30,
            cache_write_per_mtok=3.75,
        ),
        "qwen2.5-coder:32b": ModelPricing(
            input_per_mtok=0.0,
            output_per_mtok=0.0,
        ),
    }


async def _open_storage(tmp_path: Path) -> SQLiteStorage:
    """Open a fresh SQLite DB for a test under ``tmp_path``."""
    db_path = tmp_path / "runs.db"
    return await SQLiteStorage.open(db_path, migrations_dir=MIGRATIONS)


async def _new_run(
    storage: SQLiteStorage,
    *,
    run_id: str = "r1",
    workflow_id: str = "wf",
    budget_cap_usd: float | None = None,
) -> None:
    """Insert a ``runs`` row so foreign-key / schema invariants are honoured."""
    await storage.create_run(
        run_id=run_id,
        workflow_id=workflow_id,
        workflow_dir_hash="deadbeef" * 8,
        budget_cap_usd=budget_cap_usd,
    )


# ---------------------------------------------------------------------------
# AC-1 — calculate_cost arithmetic
# ---------------------------------------------------------------------------


def test_calculate_cost_matches_expected_for_gemini():
    """Gemini-2.0-flash at $0.10/$0.40 per MTok — 1 MTok in + 1 MTok out = $0.50."""
    usage = TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000)
    cost = calculate_cost("gemini-2.0-flash", usage, _pricing())
    assert cost == pytest.approx(0.10 + 0.40)


def test_calculate_cost_scales_per_token():
    """1000 in + 500 out at Gemini rates → 1e3·1e-7 + 5e2·4e-7 = $0.0003."""
    usage = TokenUsage(input_tokens=1000, output_tokens=500)
    cost = calculate_cost("gemini-2.0-flash", usage, _pricing())
    assert cost == pytest.approx(0.0003)


def test_calculate_cost_includes_cache_rates():
    """Cache-read and cache-write columns apply their own rates."""
    usage = TokenUsage(
        input_tokens=0,
        output_tokens=0,
        cache_read_tokens=1_000_000,
        cache_write_tokens=1_000_000,
    )
    cost = calculate_cost("claude-sonnet-4-6", usage, _pricing())
    # $0.30 + $3.75
    assert cost == pytest.approx(4.05)


def test_calculate_cost_zero_rates_returns_zero():
    """Local models (all rates 0.0) naturally return $0 via the math."""
    usage = TokenUsage(input_tokens=123_456, output_tokens=78_910)
    cost = calculate_cost("qwen2.5-coder:32b", usage, _pricing())
    assert cost == 0.0


def test_calculate_cost_unknown_model_returns_zero_and_warns():
    """Unknown model → 0.0 with a structured WARNING (no exception)."""
    usage = TokenUsage(input_tokens=1000, output_tokens=500)
    with capture_logs() as logs:
        cost = calculate_cost("totally-made-up-model", usage, _pricing())
    assert cost == 0.0
    warnings = [e for e in logs if e.get("event") == "cost.model_not_in_pricing"]
    assert len(warnings) == 1
    assert warnings[0]["model"] == "totally-made-up-model"


# ---------------------------------------------------------------------------
# AC-2 — local model records $0 and is_local=1
# ---------------------------------------------------------------------------


async def test_record_local_model_sets_cost_zero_and_is_local_flag(tmp_path):
    """``is_local=True`` forces cost to 0.0 and is_local=1 in storage."""
    storage = await _open_storage(tmp_path)
    await _new_run(storage)
    tracker = CostTracker(storage, _pricing(), budget_cap_usd=None)

    cost = await tracker.record(
        run_id="r1",
        workflow_id="wf",
        component="worker",
        tier="local_coder",
        model="qwen2.5-coder:32b",
        usage=TokenUsage(input_tokens=500, output_tokens=200),
        is_local=True,
    )

    assert cost == 0.0

    # Direct DB probe to pin the is_local=1 value.
    import sqlite3

    with sqlite3.connect(storage._db_path) as conn:
        cursor = conn.execute(
            "SELECT cost_usd, is_local FROM llm_calls WHERE run_id = ?", ("r1",)
        )
        rows = cursor.fetchall()
    assert rows == [(0.0, 1)]


async def test_record_local_overrides_nonzero_pricing(tmp_path):
    """If is_local=True, cost stays 0 even for a model that has pricing."""
    storage = await _open_storage(tmp_path)
    await _new_run(storage)
    tracker = CostTracker(storage, _pricing(), budget_cap_usd=None)

    cost = await tracker.record(
        run_id="r1",
        workflow_id="wf",
        component="worker",
        tier="local_coder",
        model="gemini-2.0-flash",  # priced, but forced local
        usage=TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000),
        is_local=True,
    )
    assert cost == 0.0


# ---------------------------------------------------------------------------
# AC-3 — run_total excludes is_local rows
# ---------------------------------------------------------------------------


async def test_run_total_excludes_is_local_rows(tmp_path):
    """A $0.50 priced call + 10 local $0 calls → run_total stays $0.50."""
    storage = await _open_storage(tmp_path)
    await _new_run(storage)
    tracker = CostTracker(storage, _pricing(), budget_cap_usd=None)

    await tracker.record(
        run_id="r1",
        workflow_id="wf",
        component="worker",
        tier="gemini_flash",
        model="gemini-2.0-flash",
        usage=TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000),
    )
    for _ in range(10):
        await tracker.record(
            run_id="r1",
            workflow_id="wf",
            component="local_worker",
            tier="local_coder",
            model="qwen2.5-coder:32b",
            usage=TokenUsage(input_tokens=10_000, output_tokens=5_000),
            is_local=True,
        )

    assert await tracker.run_total("r1") == pytest.approx(0.50)


# ---------------------------------------------------------------------------
# AC-4 — component_breakdown groups by component
# ---------------------------------------------------------------------------


async def test_component_breakdown_groups_per_component(tmp_path):
    """Two components, each with a different priced call → per-component totals."""
    storage = await _open_storage(tmp_path)
    await _new_run(storage)
    tracker = CostTracker(storage, _pricing(), budget_cap_usd=None)

    await tracker.record(
        run_id="r1",
        workflow_id="wf",
        component="planner",
        tier="gemini_flash",
        model="gemini-2.0-flash",
        usage=TokenUsage(input_tokens=1_000_000, output_tokens=0),
    )
    await tracker.record(
        run_id="r1",
        workflow_id="wf",
        component="validator",
        tier="gemini_flash",
        model="gemini-2.0-flash",
        usage=TokenUsage(input_tokens=0, output_tokens=1_000_000),
    )

    breakdown = await tracker.component_breakdown("r1")
    assert breakdown == {
        "planner": pytest.approx(0.10),
        "validator": pytest.approx(0.40),
    }


async def test_component_breakdown_excludes_local(tmp_path):
    """Local calls never appear in the breakdown (storage filters is_local=1)."""
    storage = await _open_storage(tmp_path)
    await _new_run(storage)
    tracker = CostTracker(storage, _pricing(), budget_cap_usd=None)

    await tracker.record(
        run_id="r1",
        workflow_id="wf",
        component="local_worker",
        tier="local_coder",
        model="qwen2.5-coder:32b",
        usage=TokenUsage(input_tokens=100, output_tokens=100),
        is_local=True,
    )
    breakdown = await tracker.component_breakdown("r1")
    assert breakdown == {}


# ---------------------------------------------------------------------------
# AC-5 — budget cap triggers BudgetExceeded at or before the call that exceeds
# ---------------------------------------------------------------------------


async def test_budget_cap_triggers_budget_exceeded(tmp_path):
    """Two $0.30 calls under a $0.50 cap → second call raises on the breach."""
    storage = await _open_storage(tmp_path)
    await _new_run(storage, budget_cap_usd=0.50)
    tracker = CostTracker(storage, _pricing(), budget_cap_usd=0.50)

    # $0.30 → under cap.
    await tracker.record(
        run_id="r1",
        workflow_id="wf",
        component="worker",
        tier="gemini_flash",
        model="gemini-2.0-flash",
        usage=TokenUsage(input_tokens=1_000_000, output_tokens=500_000),
    )
    # Running total now $0.30. Next identical call pushes to $0.60 → raises.
    with pytest.raises(BudgetExceeded) as exc_info:
        await tracker.record(
            run_id="r1",
            workflow_id="wf",
            component="worker",
            tier="gemini_flash",
            model="gemini-2.0-flash",
            usage=TokenUsage(input_tokens=1_000_000, output_tokens=500_000),
        )
    assert exc_info.value.run_id == "r1"
    assert exc_info.value.current_cost == pytest.approx(0.60)
    assert exc_info.value.cap == pytest.approx(0.50)


async def test_budget_exceeded_row_is_persisted(tmp_path):
    """The call that breached the cap is still written to ``llm_calls``."""
    storage = await _open_storage(tmp_path)
    await _new_run(storage, budget_cap_usd=0.10)
    tracker = CostTracker(storage, _pricing(), budget_cap_usd=0.10)

    with pytest.raises(BudgetExceeded):
        await tracker.record(
            run_id="r1",
            workflow_id="wf",
            component="worker",
            tier="gemini_flash",
            model="gemini-2.0-flash",
            usage=TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000),
        )

    import sqlite3

    with sqlite3.connect(storage._db_path) as conn:
        (count,) = conn.execute(
            "SELECT COUNT(*) FROM llm_calls WHERE run_id = ?", ("r1",)
        ).fetchone()
    assert count == 1


async def test_budget_cap_not_triggered_below_cap(tmp_path):
    """``new_total == cap`` must *not* raise (strict ``>`` comparison)."""
    storage = await _open_storage(tmp_path)
    await _new_run(storage, budget_cap_usd=0.50)
    tracker = CostTracker(storage, _pricing(), budget_cap_usd=0.50)

    # $0.50 exactly.
    cost = await tracker.record(
        run_id="r1",
        workflow_id="wf",
        component="worker",
        tier="gemini_flash",
        model="gemini-2.0-flash",
        usage=TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000),
    )
    assert cost == pytest.approx(0.50)
    assert await tracker.run_total("r1") == pytest.approx(0.50)


async def test_budget_cap_none_never_raises(tmp_path):
    """With no cap, arbitrary spend is permitted (the warning is the only signal)."""
    storage = await _open_storage(tmp_path)
    await _new_run(storage)
    tracker = CostTracker(storage, _pricing(), budget_cap_usd=None)

    for _ in range(5):
        await tracker.record(
            run_id="r1",
            workflow_id="wf",
            component="worker",
            tier="gemini_flash",
            model="gemini-2.0-flash",
            usage=TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000),
        )
    assert await tracker.run_total("r1") == pytest.approx(2.50)


# ---------------------------------------------------------------------------
# AC-6 — BudgetExceeded message includes run_id, current_cost, cap
# ---------------------------------------------------------------------------


def test_budget_exceeded_message_contains_run_id_and_dollar_amounts():
    """The exception message must expose the three diagnostic fields."""
    exc = BudgetExceeded(run_id="run-abc", current_cost=7.89, cap=5.00)
    message = str(exc)
    assert "run-abc" in message
    assert "$7.89" in message
    assert "$5.00" in message


def test_budget_exceeded_exposes_attributes():
    """Attributes are readable for programmatic callers (Pipeline, CLI)."""
    exc = BudgetExceeded(run_id="r", current_cost=1.23, cap=1.00)
    assert exc.run_id == "r"
    assert exc.current_cost == 1.23
    assert exc.cap == 1.00


# ---------------------------------------------------------------------------
# AC-7 — null budget cap logs a warning on run start
# ---------------------------------------------------------------------------


def test_null_budget_cap_logs_warning_at_construction(tmp_path):
    """Constructing with ``budget_cap_usd=None`` emits exactly one WARNING."""
    # Storage is not used for this test — construction-time behaviour only.
    class _StubStorage:
        async def log_llm_call(self, *a, **k): ...
        async def get_total_cost(self, *a, **k): return 0.0
        async def get_cost_breakdown(self, *a, **k): return {}

    with capture_logs() as logs:
        CostTracker(_StubStorage(), _pricing(), budget_cap_usd=None)

    warnings = [
        e for e in logs
        if e.get("event") == "cost.no_budget_cap" and e.get("log_level") == "warning"
    ]
    assert len(warnings) == 1


def test_explicit_cap_does_not_log_warning():
    """Setting an explicit cap (any number) must not emit the no-cap warning."""
    class _StubStorage:
        async def log_llm_call(self, *a, **k): ...
        async def get_total_cost(self, *a, **k): return 0.0
        async def get_cost_breakdown(self, *a, **k): return {}

    with capture_logs() as logs:
        CostTracker(_StubStorage(), _pricing(), budget_cap_usd=5.0)

    assert [e for e in logs if e.get("event") == "cost.no_budget_cap"] == []


# ---------------------------------------------------------------------------
# AC-8 — escalation calls tag is_escalation=1
# ---------------------------------------------------------------------------


async def test_escalation_flag_persists_as_is_escalation_one(tmp_path):
    """``is_escalation=True`` → ``llm_calls.is_escalation == 1`` in storage."""
    storage = await _open_storage(tmp_path)
    await _new_run(storage)
    tracker = CostTracker(storage, _pricing(), budget_cap_usd=None)

    await tracker.record(
        run_id="r1",
        workflow_id="wf",
        component="escalator",
        tier="gemini_flash",
        model="gemini-2.0-flash",
        usage=TokenUsage(input_tokens=100, output_tokens=100),
        is_escalation=True,
    )
    await tracker.record(
        run_id="r1",
        workflow_id="wf",
        component="worker",
        tier="gemini_flash",
        model="gemini-2.0-flash",
        usage=TokenUsage(input_tokens=100, output_tokens=100),
        is_escalation=False,
    )

    import sqlite3

    with sqlite3.connect(storage._db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT component, is_escalation FROM llm_calls WHERE run_id = ? "
            "ORDER BY id",
            ("r1",),
        ).fetchall()
    assert [(r["component"], r["is_escalation"]) for r in rows] == [
        ("escalator", 1),
        ("worker", 0),
    ]


# ---------------------------------------------------------------------------
# Extra coverage — end-to-end integration with storage + task_id threading
# ---------------------------------------------------------------------------


async def test_record_threads_task_id_into_llm_calls(tmp_path):
    """``task_id`` is optional; when provided it lands on the ``llm_calls`` row."""
    storage = await _open_storage(tmp_path)
    await _new_run(storage)
    await storage.upsert_task(run_id="r1", task_id="t1", component="worker", status="running")
    tracker = CostTracker(storage, _pricing(), budget_cap_usd=None)

    await tracker.record(
        run_id="r1",
        workflow_id="wf",
        component="worker",
        tier="gemini_flash",
        model="gemini-2.0-flash",
        usage=TokenUsage(input_tokens=100, output_tokens=100),
        task_id="t1",
    )

    import sqlite3

    with sqlite3.connect(storage._db_path) as conn:
        (task_id,) = conn.execute(
            "SELECT task_id FROM llm_calls WHERE run_id = ?", ("r1",)
        ).fetchone()
    assert task_id == "t1"


async def test_run_total_is_zero_for_empty_run(tmp_path):
    """Freshly created run with no LLM calls reports $0."""
    storage = await _open_storage(tmp_path)
    await _new_run(storage)
    tracker = CostTracker(storage, _pricing(), budget_cap_usd=None)

    assert await tracker.run_total("r1") == 0.0
    assert await tracker.component_breakdown("r1") == {}


async def test_budget_cap_usd_property_roundtrips(tmp_path):
    """The tracker exposes its cap as a read-only property (used by aiw inspect)."""
    storage = await _open_storage(tmp_path)
    await _new_run(storage, budget_cap_usd=3.50)
    tracker = CostTracker(storage, _pricing(), budget_cap_usd=3.50)
    assert tracker.budget_cap_usd == 3.50

    tracker2 = CostTracker(storage, _pricing(), budget_cap_usd=None)
    assert tracker2.budget_cap_usd is None


def test_cost_tracker_structural_compat_with_model_factory():
    """``MagicMock(spec=CostTracker)`` still works for the Task 03 factory.

    The Task 03 model factory type-hints ``cost_tracker: CostTracker`` and
    existing tests build mocks via ``MagicMock(spec=CostTracker)``. Replacing
    the Task 03 Protocol with a concrete class must not regress that spec.
    """
    from unittest.mock import AsyncMock, MagicMock

    mock = MagicMock(spec=CostTracker)
    mock.record = AsyncMock(return_value=0.0)
    # The spec exposes ``record``, ``run_total``, ``component_breakdown``, and
    # ``budget_cap_usd`` — accessing them must not raise.
    assert hasattr(mock, "record")
    assert hasattr(mock, "run_total")
    assert hasattr(mock, "component_breakdown")
    assert hasattr(mock, "budget_cap_usd")


# ---------------------------------------------------------------------------
# structlog must be wired so capture_logs() actually sees the events.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_structlog():
    """Ensure each test starts with structlog's default configuration.

    ``capture_logs`` only captures when structlog is configured; the primitives
    layer uses ``structlog.get_logger()`` which respects the current config.
    """
    structlog.reset_defaults()
    yield
    structlog.reset_defaults()
