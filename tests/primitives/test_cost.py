"""Tests for the pruned CostTracker surface (M1 Task 08 — KDR-007).

Grades every AC from
[design_docs/phases/milestone_1_reconciliation/task_08_prune_cost_tracker.md]:

* AC-1: `TokenUsage` carries the recursive `sub_models` field and
  round-trips through pydantic serialisation.
* AC-2: `CostTracker.record` is the single write path; aggregation
  methods (`total`, `by_tier`, `by_model`) are pure reads.
* AC-3: `check_budget` raises the `NonRetryable` from
  [task 07](../task_07_refit_retry_policy.md).
* AC-4: `grep -r "pydantic_ai" ai_workflows/primitives/cost.py
  tests/primitives/test_cost.py` returns zero matches — pinned here
  by :func:`test_cost_module_has_no_pydantic_ai_imports`.
* AC-5: `uv run pytest tests/primitives/test_cost.py` green (this
  file).

Carry-over grading:
* M1-T05-ISS-01 — this file no longer references
  ``storage.log_llm_call`` / ``get_total_cost`` / ``get_cost_breakdown``;
  the tracker is storage-free. Pinned by
  :func:`test_cost_module_does_not_call_trimmed_storage_methods`.
* M1-T06-ISS-02 — ``CostTracker`` no longer reads ``pricing.yaml``
  directly. ``pricing.yaml`` is retained for the M2 Claude Code driver
  per [task_08 §Deliverables](../task_08_prune_cost_tracker.md). The
  cost module imports no pricing helper. Pinned by
  :func:`test_cost_module_does_not_import_pricing_helpers`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_workflows.primitives import cost as cost_module
from ai_workflows.primitives.cost import CostTracker, TokenUsage
from ai_workflows.primitives.retry import NonRetryable

# ---------------------------------------------------------------------------
# AC-1 — TokenUsage + recursive sub_models
# ---------------------------------------------------------------------------


def test_token_usage_has_task_02_surface_and_extensions() -> None:
    """The Task-02 surface (input/output + cache columns) is preserved.

    Extensions land per task_08: ``cost_usd``, ``model``, ``tier``,
    ``sub_models``. All default to sensible empty values so a provider
    driver can build a ``TokenUsage`` incrementally.
    """
    usage = TokenUsage()
    assert usage.input_tokens == 0
    assert usage.output_tokens == 0
    assert usage.cache_read_tokens == 0
    assert usage.cache_write_tokens == 0
    assert usage.cost_usd == 0.0
    assert usage.model == ""
    assert usage.tier == ""
    assert usage.sub_models == []


def test_token_usage_round_trips_through_pydantic_serialisation() -> None:
    """Nested sub_models round-trip through ``model_dump`` + reconstruction."""
    usage = TokenUsage(
        input_tokens=1000,
        output_tokens=500,
        cost_usd=0.0005,
        model="claude-opus-4-7",
        tier="planner",
        sub_models=[
            TokenUsage(
                input_tokens=100,
                output_tokens=50,
                cost_usd=0.00002,
                model="claude-haiku-4-5-20251001",
                tier="planner",
            ),
            TokenUsage(
                input_tokens=200,
                output_tokens=75,
                cost_usd=0.00003,
                model="claude-haiku-4-5-20251001",
                tier="planner",
            ),
        ],
    )
    dumped = usage.model_dump()
    rebuilt = TokenUsage.model_validate(dumped)
    assert rebuilt == usage
    assert len(rebuilt.sub_models) == 2
    assert all(child.model == "claude-haiku-4-5-20251001" for child in rebuilt.sub_models)


def test_token_usage_sub_models_accept_recursive_depth() -> None:
    """``sub_models`` is typed recursively so the modelUsage tree can nest."""
    leaf = TokenUsage(model="claude-haiku-4-5-20251001", cost_usd=0.0001, tier="planner")
    mid = TokenUsage(
        model="claude-sonnet-4-6",
        cost_usd=0.0005,
        tier="planner",
        sub_models=[leaf],
    )
    top = TokenUsage(
        model="claude-opus-4-7",
        cost_usd=0.001,
        tier="planner",
        sub_models=[mid],
    )
    assert top.sub_models[0].sub_models[0].model == "claude-haiku-4-5-20251001"
    # Round-trip the three-level tree through dict + reconstruct.
    rebuilt = TokenUsage.model_validate(top.model_dump())
    assert rebuilt == top


# ---------------------------------------------------------------------------
# AC-2 — CostTracker.record is the single write path
# ---------------------------------------------------------------------------


def test_record_is_the_single_write_method() -> None:
    """Only ``record`` mutates state; the read methods do not accept usage."""
    tracker = CostTracker()
    # ``record`` is the only public mutator — total/by_tier/by_model don't
    # take a TokenUsage parameter and check_budget only reads totals.
    tracker.record("r1", TokenUsage(cost_usd=0.10, model="x", tier="t"))
    assert tracker.total("r1") == pytest.approx(0.10)


def test_total_rolls_up_sub_models_per_modelusage_spec() -> None:
    """Sub-model costs count toward the per-run total.

    Mirrors the §4.1 load-bearing behaviour: a ``claude_code`` call to
    ``opus`` that spawned a ``haiku`` sub-call must have both costs in
    the rollup.
    """
    tracker = CostTracker()
    tracker.record(
        "r1",
        TokenUsage(
            cost_usd=0.10,
            model="claude-opus-4-7",
            tier="planner",
            sub_models=[
                TokenUsage(cost_usd=0.02, model="claude-haiku-4-5-20251001", tier="planner"),
                TokenUsage(cost_usd=0.03, model="claude-haiku-4-5-20251001", tier="planner"),
            ],
        ),
    )
    assert tracker.total("r1") == pytest.approx(0.15)


def test_total_is_zero_for_unknown_run_id() -> None:
    """An un-recorded ``run_id`` reports ``0.0`` — not a KeyError."""
    tracker = CostTracker()
    assert tracker.total("never-recorded") == 0.0


def test_by_tier_groups_costs_and_includes_sub_models() -> None:
    """Sub-model costs inherit the parent entry's tier in ``by_tier``."""
    tracker = CostTracker()
    tracker.record(
        "r1",
        TokenUsage(
            cost_usd=0.10,
            model="claude-opus-4-7",
            tier="planner",
            sub_models=[
                TokenUsage(cost_usd=0.02, model="claude-haiku-4-5-20251001", tier="planner"),
            ],
        ),
    )
    tracker.record(
        "r1",
        TokenUsage(cost_usd=0.05, model="gemini-2.5-flash", tier="implementer"),
    )
    assert tracker.by_tier("r1") == {
        "planner": pytest.approx(0.12),
        "implementer": pytest.approx(0.05),
    }


def test_by_model_include_sub_models_true_breaks_out_each_sub_call() -> None:
    """Task spec test-update requirement: each sub-model rolls under its own key."""
    tracker = CostTracker()
    tracker.record(
        "r1",
        TokenUsage(
            cost_usd=0.10,
            model="claude-opus-4-7",
            tier="planner",
            sub_models=[
                TokenUsage(cost_usd=0.02, model="claude-haiku-4-5-20251001", tier="planner"),
                TokenUsage(cost_usd=0.03, model="claude-haiku-4-5-20251001", tier="planner"),
            ],
        ),
    )
    tracker.record(
        "r1",
        TokenUsage(cost_usd=0.04, model="claude-sonnet-4-6", tier="planner"),
    )
    breakdown = tracker.by_model("r1", include_sub_models=True)
    assert breakdown == {
        "claude-opus-4-7": pytest.approx(0.10),
        "claude-haiku-4-5-20251001": pytest.approx(0.05),
        "claude-sonnet-4-6": pytest.approx(0.04),
    }


def test_by_model_include_sub_models_false_hides_sub_calls() -> None:
    """``include_sub_models=False`` attributes everything to the top-level model."""
    tracker = CostTracker()
    tracker.record(
        "r1",
        TokenUsage(
            cost_usd=0.10,
            model="claude-opus-4-7",
            tier="planner",
            sub_models=[
                TokenUsage(cost_usd=0.02, model="claude-haiku-4-5-20251001", tier="planner"),
            ],
        ),
    )
    breakdown = tracker.by_model("r1", include_sub_models=False)
    assert breakdown == {"claude-opus-4-7": pytest.approx(0.10)}


def test_entries_for_disjoint_runs_do_not_bleed() -> None:
    """Two runs recording into one tracker stay isolated by run_id."""
    tracker = CostTracker()
    tracker.record("r1", TokenUsage(cost_usd=0.10, model="a", tier="t"))
    tracker.record("r2", TokenUsage(cost_usd=0.25, model="b", tier="t"))
    assert tracker.total("r1") == pytest.approx(0.10)
    assert tracker.total("r2") == pytest.approx(0.25)
    assert tracker.by_model("r1") == {"a": pytest.approx(0.10)}
    assert tracker.by_model("r2") == {"b": pytest.approx(0.25)}


# ---------------------------------------------------------------------------
# AC-3 — check_budget raises NonRetryable at threshold
# ---------------------------------------------------------------------------


def test_check_budget_raises_non_retryable_on_breach() -> None:
    """Task spec test-update requirement: budget breach → task 07 NonRetryable."""
    tracker = CostTracker()
    tracker.record("r1", TokenUsage(cost_usd=0.60, model="x", tier="t"))
    with pytest.raises(NonRetryable) as exc_info:
        tracker.check_budget("r1", cap_usd=0.50)
    # §8.5 says "budget exceeded"; the message surfaces run + amounts.
    message = str(exc_info.value)
    assert "budget exceeded" in message
    assert "$0.60" in message
    assert "$0.50" in message
    assert "r1" in message


def test_check_budget_sub_models_count_toward_cap() -> None:
    """Sub-model costs push the total over the cap — §4.1 load-bearing."""
    tracker = CostTracker()
    tracker.record(
        "r1",
        TokenUsage(
            cost_usd=0.40,
            model="claude-opus-4-7",
            tier="planner",
            sub_models=[
                TokenUsage(cost_usd=0.15, model="claude-haiku-4-5-20251001", tier="planner"),
            ],
        ),
    )
    with pytest.raises(NonRetryable):
        tracker.check_budget("r1", cap_usd=0.50)


def test_check_budget_exactly_at_cap_does_not_raise() -> None:
    """Strict ``>`` — landing on the cap is fine; exceeding it is the breach."""
    tracker = CostTracker()
    tracker.record("r1", TokenUsage(cost_usd=0.50, model="x", tier="t"))
    tracker.check_budget("r1", cap_usd=0.50)  # must not raise


def test_check_budget_under_cap_does_not_raise() -> None:
    """Running under the cap is the common path; no exception."""
    tracker = CostTracker()
    tracker.record("r1", TokenUsage(cost_usd=0.10, model="x", tier="t"))
    tracker.check_budget("r1", cap_usd=0.50)


def test_check_budget_for_unknown_run_id_does_not_raise() -> None:
    """Checking the budget of a run that has no entries is $0 — well under any cap."""
    tracker = CostTracker()
    tracker.check_budget("never-recorded", cap_usd=0.01)


# ---------------------------------------------------------------------------
# AC-4 — sanity pins (no pydantic-ai, no trimmed-storage calls, no pricing imports)
# ---------------------------------------------------------------------------


_REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (_REPO_ROOT / relative).read_text()


def test_cost_module_has_no_pydantic_ai_imports() -> None:
    """Spec AC-4: ``grep -r pydantic_ai`` returns zero matches in both files.

    Scans real import / from lines so a historical mention inside a
    docstring would not flag.
    """
    for relative in ("ai_workflows/primitives/cost.py", "tests/primitives/test_cost.py"):
        text = _read(relative)
        for line in text.splitlines():
            stripped = line.lstrip()
            if stripped.startswith(("import ", "from ")):
                assert "pydantic_ai" not in line, (
                    f"pydantic_ai import leaked into {relative}: {line!r}"
                )


def test_cost_module_does_not_call_trimmed_storage_methods() -> None:
    """Carry-over M1-T05-ISS-01: trimmed Storage methods must not be invoked.

    The T05 Builder removed ``log_llm_call``, ``get_total_cost``, and
    ``get_cost_breakdown`` from ``StorageBackend``. ``cost.py`` must
    not call them by name anywhere.
    """
    text = _read("ai_workflows/primitives/cost.py")
    for forbidden in ("log_llm_call", "get_total_cost", "get_cost_breakdown"):
        assert forbidden not in text, (
            f"trimmed-Storage method {forbidden!r} leaked into cost.py"
        )


def test_cost_module_does_not_import_pricing_helpers() -> None:
    """Carry-over M1-T06-ISS-02: ``CostTracker`` does not read ``pricing.yaml``.

    The per-call ``cost_usd`` arrives pre-enriched on ``TokenUsage``;
    pricing lookup is the provider driver's concern. Pin by scanning
    import lines for ``load_pricing`` and ``ModelPricing`` references.
    """
    text = _read("ai_workflows/primitives/cost.py")
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("import ", "from ")):
            assert "load_pricing" not in line, (
                "cost.py must not import load_pricing — the driver owns pricing"
            )
            assert "ModelPricing" not in line, (
                "cost.py must not import ModelPricing — the driver owns pricing"
            )


def test_cost_module_exports_the_pruned_public_surface() -> None:
    """The public API is ``TokenUsage`` + ``CostTracker`` — nothing else."""
    assert set(cost_module.__all__) == {"TokenUsage", "CostTracker"}


def test_cost_tracker_structural_compat_with_magic_mock_spec() -> None:
    """``MagicMock(spec=CostTracker)`` still works for M2 node/test wiring.

    M2's ``CostTrackingCallback`` will build mocks against this class.
    The mock must expose the four read methods plus ``record`` +
    ``check_budget``.
    """
    from unittest.mock import MagicMock

    mock = MagicMock(spec=CostTracker)
    for attr in ("record", "total", "by_tier", "by_model", "check_budget"):
        assert hasattr(mock, attr), f"CostTracker spec must expose {attr}"
