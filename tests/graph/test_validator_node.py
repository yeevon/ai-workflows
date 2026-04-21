"""Tests for ``ai_workflows.graph.validator_node`` (M2 Task 04).

Covers the three AC-bearing scenarios from
[task_04_validator_node.md](../../design_docs/phases/milestone_2_graph/task_04_validator_node.md):
happy-path parse, schema violation, and non-JSON input. Also asserts
the pure-validation contract (no side effects beyond state) and the
revision-hint content that ``RetryingEdge`` will forward to the next
LLM turn per KDR-004.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from ai_workflows.graph.validator_node import validator_node
from ai_workflows.primitives.retry import NonRetryable, RetryableSemantic


class Plan(BaseModel):
    """Throwaway schema exercised by the validator tests."""

    title: str = Field(min_length=1)
    steps: list[str]


async def test_happy_path_writes_parsed_instance_to_state() -> None:
    node = validator_node(
        schema=Plan,
        input_key="raw_plan",
        output_key="plan",
        node_name="plan_validator",
    )
    state = {"raw_plan": '{"title": "demo", "steps": ["a", "b"]}'}

    out = await node(state)

    assert isinstance(out["plan"], Plan)
    assert out["plan"].title == "demo"
    assert out["plan"].steps == ["a", "b"]
    assert out["raw_plan_revision_hint"] is None


async def test_schema_violation_raises_retryable_semantic_with_hint() -> None:
    node = validator_node(
        schema=Plan,
        input_key="raw_plan",
        output_key="plan",
        node_name="plan_validator",
    )
    state = {"raw_plan": '{"title": "", "steps": "not-a-list"}'}

    with pytest.raises(RetryableSemantic) as excinfo:
        await node(state)

    err = excinfo.value
    assert err.revision_hint
    assert "Plan" in err.revision_hint
    assert "title" in err.revision_hint
    assert "steps" in err.revision_hint
    assert "plan_validator" in err.reason


async def test_non_json_text_raises_retryable_semantic_not_non_retryable() -> None:
    node = validator_node(
        schema=Plan,
        input_key="raw_plan",
        output_key="plan",
        node_name="plan_validator",
    )
    state = {"raw_plan": "this is not json at all"}

    with pytest.raises(RetryableSemantic) as excinfo:
        await node(state)

    assert excinfo.value.revision_hint
    assert "Plan" in excinfo.value.revision_hint


async def test_success_clears_stale_revision_hint() -> None:
    node = validator_node(
        schema=Plan,
        input_key="raw_plan",
        output_key="plan",
        node_name="plan_validator",
    )
    state = {
        "raw_plan": '{"title": "demo", "steps": []}',
        "raw_plan_revision_hint": "prior attempt said: wrong field",
    }

    out = await node(state)

    assert out["raw_plan_revision_hint"] is None


async def test_missing_required_field_hint_references_field_name() -> None:
    node = validator_node(
        schema=Plan,
        input_key="raw_plan",
        output_key="plan",
        node_name="plan_validator",
    )
    state = {"raw_plan": '{"title": "demo"}'}

    with pytest.raises(RetryableSemantic) as excinfo:
        await node(state)

    assert "steps" in excinfo.value.revision_hint


def test_factory_rejects_max_attempts_below_one() -> None:
    with pytest.raises(ValueError):
        validator_node(
            schema=Plan,
            input_key="raw_plan",
            output_key="plan",
            node_name="plan_validator",
            max_attempts=0,
        )


# ---------------------------------------------------------------------------
# Budget-exhaustion escalation (M6 Task 07 — M6-T03-ISS-01 resolution)
# ---------------------------------------------------------------------------


async def test_escalation_raises_non_retryable_on_last_allowed_attempt() -> None:
    """M6-T03-ISS-01: when ``state['_retry_counts'][node_name]`` has
    been bumped ``max_attempts - 1`` times (i.e. this call is the last
    allowed attempt and it failed), the stock validator escalates
    :class:`RetryableSemantic` → :class:`NonRetryable` so the paired
    :func:`retrying_edge` routes to ``on_terminal`` regardless of its
    own budget check keying off ``on_semantic``'s counter.
    """
    node = validator_node(
        schema=Plan,
        input_key="raw_plan",
        output_key="plan",
        node_name="plan_validator",
        max_attempts=3,
    )
    state = {
        "raw_plan": '{"title": "", "steps": "not-a-list"}',
        "_retry_counts": {"plan_validator": 2},  # two prior failures → this is the 3rd
    }
    with pytest.raises(NonRetryable) as excinfo:
        await node(state)
    message = str(excinfo.value)
    assert "plan_validator" in message
    assert "3 attempts" in message
    assert "Plan" in message


async def test_escalation_preserves_retryable_semantic_on_earlier_attempts() -> None:
    """Pre-exhaustion attempts still raise :class:`RetryableSemantic`
    so the retry loop can course-correct — the escalation is only the
    ``max_attempts``-th failing call.
    """
    node = validator_node(
        schema=Plan,
        input_key="raw_plan",
        output_key="plan",
        node_name="plan_validator",
        max_attempts=3,
    )
    for prior in (0, 1):
        state = {
            "raw_plan": '{"title": "", "steps": "not-a-list"}',
            "_retry_counts": {"plan_validator": prior},
        }
        with pytest.raises(RetryableSemantic):
            await node(state)


async def test_escalation_reads_counter_under_validator_node_name() -> None:
    """The escalation must read ``_retry_counts[node_name]`` — the key
    :func:`wrap_with_error_handler` bumps. A counter stored under the
    upstream LLM node's name (``on_semantic`` target) is irrelevant to
    the escalation decision; the keys are disjoint.
    """
    node = validator_node(
        schema=Plan,
        input_key="raw_plan",
        output_key="plan",
        node_name="plan_validator",
        max_attempts=3,
    )
    state = {
        "raw_plan": '{"title": "", "steps": "not-a-list"}',
        # Retries counted under the LLM node, not the validator. The
        # escalation must NOT fire — those bumps are irrelevant to this
        # validator's budget.
        "_retry_counts": {"planner": 5},
    }
    with pytest.raises(RetryableSemantic):
        await node(state)


async def test_escalation_works_with_max_attempts_one() -> None:
    """With ``max_attempts=1``, even the first failure is exhaustion —
    there is no retry budget, so the validator raises
    :class:`NonRetryable` straight away. Pins the ``>=`` check
    (``prior >= max_attempts - 1`` holds for ``prior=0``,
    ``max_attempts=1``).
    """
    node = validator_node(
        schema=Plan,
        input_key="raw_plan",
        output_key="plan",
        node_name="plan_validator",
        max_attempts=1,
    )
    state = {"raw_plan": "not-even-json"}
    with pytest.raises(NonRetryable):
        await node(state)


async def test_exhausting_three_attempts_sequence_surfaces_non_retryable() -> None:
    """End-to-end sequence: 3 failing calls with counter bumped by the
    harness between calls exhausts the budget. Mirrors how
    :func:`wrap_with_error_handler` drives the loop in production.
    """
    node = validator_node(
        schema=Plan,
        input_key="raw_plan",
        output_key="plan",
        node_name="plan_validator",
        max_attempts=3,
    )
    bad_state = {"raw_plan": "malformed"}

    with pytest.raises(RetryableSemantic):
        await node({**bad_state, "_retry_counts": {"plan_validator": 0}})
    with pytest.raises(RetryableSemantic):
        await node({**bad_state, "_retry_counts": {"plan_validator": 1}})
    with pytest.raises(NonRetryable):
        await node({**bad_state, "_retry_counts": {"plan_validator": 2}})
