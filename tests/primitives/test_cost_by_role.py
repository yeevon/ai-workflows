"""Tests for ``CostTracker.by_role`` + ``TokenUsage.role`` field (M12 Task 04 — KDR-011).

Five hermetic tests covering the new aggregation surface added by T04.  No real
LLM calls; all records created directly via ``TokenUsage`` + ``CostTracker.record``.

Relationship to sibling test modules
--------------------------------------
* ``tests/primitives/test_cost.py`` — covers ``total``, ``by_tier``, ``by_model``,
  ``check_budget``.  T04 adds ``by_role`` on top; the existing tests are not modified.
* ``tests/graph/test_audit_cascade.py`` — wire-level role-stamp tests (tests 12-13 added
  by T04) verify that the cascade's ``tiered_node`` constructions record the correct role
  end-to-end through the real ``CostTrackingCallback`` path.
"""

from __future__ import annotations

from ai_workflows.primitives.cost import CostTracker, TokenUsage

# ---------------------------------------------------------------------------
# Test 1: empty run
# ---------------------------------------------------------------------------


def test_by_role_empty_run() -> None:
    """``by_role`` on a run that has no entries returns an empty dict."""
    tracker = CostTracker()
    result = tracker.by_role("nonexistent_run")
    assert result == {}


# ---------------------------------------------------------------------------
# Test 2: single role
# ---------------------------------------------------------------------------


def test_by_role_single_role() -> None:
    """Three entries all with role="author" accumulate to a single bucket."""
    tracker = CostTracker()
    run_id = "r_single"
    for cost in (1.0, 2.0, 3.0):
        tracker.record(run_id, TokenUsage(role="author", cost_usd=cost))

    result = tracker.by_role(run_id)
    assert result == {"author": 6.0}


# ---------------------------------------------------------------------------
# Test 3: multiple roles
# ---------------------------------------------------------------------------


def test_by_role_multiple_roles() -> None:
    """Entries with distinct roles land in separate buckets."""
    tracker = CostTracker()
    run_id = "r_multi"
    tracker.record(run_id, TokenUsage(role="author", cost_usd=1.0))
    tracker.record(run_id, TokenUsage(role="auditor", cost_usd=2.0))
    tracker.record(run_id, TokenUsage(role="verdict", cost_usd=0.5))

    result = tracker.by_role(run_id)
    assert result == {"author": 1.0, "auditor": 2.0, "verdict": 0.5}


# ---------------------------------------------------------------------------
# Test 4: sub-model costs inherit parent role (NOT a separate "" bucket)
# ---------------------------------------------------------------------------


def test_by_role_sub_models_inherit_parent_role() -> None:
    """Sub-model costs roll into the parent entry's role via ``_roll_cost``.

    A ``TokenUsage(role="author", cost_usd=1.0, sub_models=[TokenUsage(role="", cost_usd=0.5)])``
    should produce ``{"author": 1.5}`` — the sub-model's empty role does NOT
    create a separate ``""`` bucket.  Sub-model costs roll into the parent's
    role via the ``_roll_cost`` helper (mirrors ``by_tier``'s sub-model behaviour).

    This contract is critical for cascade calls: a single Opus cascade call may
    spawn Haiku sub-calls; the parent role should swallow the sub-model costs so
    the operator sees one entry per cascade step, not one per internal LLM call.
    """
    tracker = CostTracker()
    run_id = "r_submodels"
    entry = TokenUsage(
        role="author",
        cost_usd=1.0,
        sub_models=[
            TokenUsage(role="", cost_usd=0.5),
        ],
    )
    tracker.record(run_id, entry)

    result = tracker.by_role(run_id)
    # The sub-model's "" role must NOT appear as a separate bucket.
    assert "" not in result, (
        f"Sub-model's empty role must not create a separate '' bucket; got: {result}"
    )
    # The full rolled-up cost (parent + sub-model) lands in "author".
    assert result == {"author": 1.5}, f"Expected {{'author': 1.5}}, got {result}"


# ---------------------------------------------------------------------------
# Test 5: empty-string role appears as its own bucket for non-cascade calls
# ---------------------------------------------------------------------------


def test_by_role_includes_empty_string_bucket_for_non_cascade_calls() -> None:
    """Non-cascade calls (role="") appear under the ``""`` key.

    Pins the documented contract from ``CostTracker.by_role``'s docstring:
    non-cascade calls show under the ``""`` key; callers that want only cascade
    roles filter with ``{r: c for r, c in tracker.by_role(run_id).items() if r}``.

    This test pins the empty-string bucket — it must appear as a top-level key
    when there are direct (non-sub-model) entries with role="".
    """
    tracker = CostTracker()
    run_id = "r_empty_role"
    tracker.record(run_id, TokenUsage(role="author", cost_usd=1.0))
    tracker.record(run_id, TokenUsage(role="", cost_usd=0.5))

    result = tracker.by_role(run_id)
    assert result == {"author": 1.0, "": 0.5}, (
        f"Expected {{'author': 1.0, '': 0.5}}, got {result}"
    )
