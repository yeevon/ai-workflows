"""Tests for WorkflowSpec data-model surface (M19 Task 01).

Covers acceptance criteria from
``design_docs/phases/milestone_19_declarative_surface/task_01_workflow_spec.md``
(Deliverable 5).

Hermetic: imports stdlib + pydantic + ai_workflows.workflows only.
No LangGraph imports.  No provider calls.  Runs in < 1 s wall-clock.
"""

from __future__ import annotations

import warnings
from collections.abc import Iterator

import pytest
from pydantic import BaseModel, ValidationError

import ai_workflows.workflows as workflows
from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig
from ai_workflows.workflows import (
    FanOutStep,
    LLMStep,
    RetryPolicy,
    Step,
    ValidateStep,
    WorkflowSpec,
    register_workflow,
)

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_registry() -> Iterator[None]:
    """Registry isolation: clear before and after each test."""
    workflows._reset_for_tests()
    yield
    workflows._reset_for_tests()


class _FooIn(BaseModel):
    x: int


class _FooOut(BaseModel):
    y: str


def _make_tier(name: str = "t") -> TierConfig:
    """Build a minimal TierConfig for test use."""
    return TierConfig(
        name=name,
        route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
    )


# ---------------------------------------------------------------------------
# AC-1 / AC-8 — WorkflowSpec construction + minimum shape
# ---------------------------------------------------------------------------


def test_workflow_spec_minimum_shape_constructs() -> None:
    """WorkflowSpec with tiers={} and a single ValidateStep constructs cleanly."""
    spec = WorkflowSpec(
        name="x",
        input_schema=_FooIn,
        output_schema=_FooOut,
        steps=[ValidateStep(target_field="y", schema=_FooOut)],
        tiers={},
    )
    assert spec.name == "x"
    assert spec.tiers == {}
    assert len(spec.steps) == 1


def test_workflow_spec_extra_field_raises() -> None:
    """WorkflowSpec with extra='forbid' rejects unknown fields."""
    with pytest.raises(ValidationError):
        WorkflowSpec(  # type: ignore[call-arg]
            name="x",
            input_schema=_FooIn,
            output_schema=_FooOut,
            steps=[ValidateStep(target_field="y", schema=_FooOut)],
            tiers={},
            unknown_field="oops",
        )


# ---------------------------------------------------------------------------
# AC-2 — LLMStep KDR-004 + prompt-source exclusivity
# ---------------------------------------------------------------------------


def test_llm_step_requires_response_format() -> None:
    """LLMStep without response_format raises ValidationError (KDR-004)."""
    with pytest.raises(ValidationError):
        LLMStep(tier="t", prompt_template="say hello")  # type: ignore[call-arg]


def test_llm_step_requires_exactly_one_prompt_source_both_set() -> None:
    """LLMStep with both prompt_fn and prompt_template raises (Q2).

    The model validator message is: 'got both' (Deliverable 1 wording).
    """
    with pytest.raises(ValidationError) as exc_info:
        LLMStep(
            tier="t",
            prompt_fn=lambda s: ("", []),
            prompt_template="p",
            response_format=_FooOut,
        )
    assert "got both" in str(exc_info.value)


def test_llm_step_requires_exactly_one_prompt_source_neither_set() -> None:
    """LLMStep with neither prompt_fn nor prompt_template raises (Q2).

    The model validator message is: 'got neither' (Deliverable 1 wording).
    """
    with pytest.raises(ValidationError) as exc_info:
        LLMStep(tier="t", response_format=_FooOut)
    assert "got neither" in str(exc_info.value)


def test_llm_step_with_prompt_template_constructs() -> None:
    """LLMStep with prompt_template only constructs cleanly."""
    step = LLMStep(tier="t", prompt_template="hello {x}", response_format=_FooOut)
    assert step.prompt_template == "hello {x}"
    assert step.prompt_fn is None


def test_llm_step_with_prompt_fn_constructs() -> None:
    """LLMStep with prompt_fn only constructs cleanly."""
    fn = lambda s: ("sys", [{"role": "user", "content": "hi"}])  # noqa: E731
    step = LLMStep(tier="t", prompt_fn=fn, response_format=_FooOut)
    assert step.prompt_fn is fn
    assert step.prompt_template is None


# ---------------------------------------------------------------------------
# AC-3 — Step base class execute() + compile() contract
# ---------------------------------------------------------------------------


async def test_step_base_class_execute_raises_when_unimplemented() -> None:
    """Direct Step() execute() raises NotImplementedError pointing to the doc."""

    class _Bare(Step):
        pass

    step = _Bare()
    with pytest.raises(NotImplementedError) as exc_info:
        await step.execute({})
    msg = str(exc_info.value)
    assert "docs/writing-a-custom-step.md" in msg


def test_custom_step_subclass_with_only_execute_works() -> None:
    """Custom step with execute() only is a valid Step; compile() is inherited.

    T02 ships the default compile() body (locked Q4): a custom step that only
    overrides execute() gets a working single-node CompiledStep from the base
    class compile() delegation to _compiler._default_step_compile.
    """
    from ai_workflows.workflows._compiler import CompiledStep

    class MyStep(Step):
        payload: str

        async def execute(self, state: dict) -> dict:
            return {"out": self.payload}

    step = MyStep(payload="hi")
    assert isinstance(step, Step)
    assert step.payload == "hi"
    # T02: compile() now works — returns a CompiledStep (no longer raises).
    cs = step.compile(dict, "my_step")
    assert isinstance(cs, CompiledStep)
    assert cs.entry_node_id == cs.exit_node_id  # single-node default


# ---------------------------------------------------------------------------
# AC-4 — register_workflow cross-step validation
# ---------------------------------------------------------------------------


def test_register_workflow_empty_steps_raises() -> None:
    """register_workflow with empty steps raises ValueError."""
    spec = WorkflowSpec(
        name="empty",
        input_schema=_FooIn,
        output_schema=_FooOut,
        steps=[],
        tiers={},
    )
    with pytest.raises(ValueError, match="empty step list"):
        register_workflow(spec)


def test_register_workflow_unknown_tier_raises_with_typo_message() -> None:
    """Unknown LLMStep tier raises ValueError naming the offending + available tiers."""
    tier_a = _make_tier("planner-explorer")
    tier_b = _make_tier("planner-synth")
    spec = WorkflowSpec(
        name="typo_test",
        input_schema=_FooIn,
        output_schema=_FooOut,
        steps=[
            LLMStep(tier="planner-syth", prompt_template="hi {x}", response_format=_FooOut),
        ],
        tiers={"planner-explorer": tier_a, "planner-synth": tier_b},
    )
    with pytest.raises(ValueError) as exc_info:
        register_workflow(spec)
    msg = str(exc_info.value)
    # Must name the offending tier
    assert "planner-syth" in msg
    # Must name the available tier set
    assert "planner-explorer" in msg or "planner-synth" in msg


def test_register_workflow_collision_raises() -> None:
    """Registering two specs with the same name raises ValueError (collision guard)."""
    step = ValidateStep(target_field="y", schema=_FooOut)
    spec = WorkflowSpec(
        name="dup",
        input_schema=_FooIn,
        output_schema=_FooOut,
        steps=[step],
        tiers={},
    )
    register_workflow(spec)
    with pytest.raises(ValueError):
        register_workflow(spec)


# ---------------------------------------------------------------------------
# AC-5 — register_workflow calls underlying register()
# ---------------------------------------------------------------------------


def test_register_workflow_calls_underlying_register() -> None:
    """register_workflow adds the name to list_workflows(); builder returns a StateGraph.

    T02: the builder is now the real compile_spec builder, not the T01 stub.
    Calling builder() returns a StateGraph instance.
    """
    from langgraph.graph import StateGraph

    spec = WorkflowSpec(
        name="listed",
        input_schema=_FooIn,
        output_schema=_FooOut,
        steps=[ValidateStep(target_field="y", schema=_FooOut)],
        tiers={},
    )
    register_workflow(spec)
    assert "listed" in workflows.list_workflows()
    # T02: builder() returns a StateGraph (real compiler, not the T01 stub).
    builder = workflows.get("listed")
    graph = builder()
    assert isinstance(graph, StateGraph)


# ---------------------------------------------------------------------------
# AC-4 — FanOutStep unresolvable iter_field warns, not raises
# ---------------------------------------------------------------------------


def test_fan_out_step_unresolvable_iter_field_warns_not_raises() -> None:
    """FanOutStep with unresolvable iter_field emits UserWarning; does not raise."""
    sub = ValidateStep(target_field="y", schema=_FooOut)
    spec = WorkflowSpec(
        name="fanout_warn",
        input_schema=_FooIn,
        output_schema=_FooOut,
        steps=[
            FanOutStep(
                iter_field="missing",   # not on _FooIn or _FooOut
                sub_steps=[sub],
                merge_field="agg",      # not on _FooIn or _FooOut
            ),
        ],
        tiers={},
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        register_workflow(spec)

    warning_messages = [str(w.message) for w in caught if w.category is UserWarning]
    assert any("missing" in m or "iter_field" in m for m in warning_messages), (
        f"Expected UserWarning about 'missing' iter_field; got: {warning_messages}"
    )
    # Registration must succeed despite the warning
    assert "fanout_warn" in workflows.list_workflows()


# ---------------------------------------------------------------------------
# AC-3 — Step frozen invariant
# ---------------------------------------------------------------------------


def test_custom_step_frozen() -> None:
    """Step subclass instances are immutable (frozen=True)."""

    class MyStep(Step):
        payload: str

    step = MyStep(payload="hi")
    with pytest.raises((ValidationError, TypeError)):
        step.payload = "x"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# AC-1 — RetryPolicy re-export from primitives.retry (not redefined)
# ---------------------------------------------------------------------------


def test_retry_policy_reexport_is_same_object() -> None:
    """RetryPolicy re-exported from workflows is the primitives.retry class."""
    from ai_workflows.primitives.retry import RetryPolicy as PrimitivesRetryPolicy

    assert RetryPolicy is PrimitivesRetryPolicy
