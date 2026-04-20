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
from ai_workflows.primitives.retry import RetryableSemantic


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
