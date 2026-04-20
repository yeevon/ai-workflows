"""Single-tier planner workflow (M3).

Pins the pydantic v2 public contract for the ``planner`` workflow — the
schemas that the :class:`ValidatorNode` in `ai_workflows.graph.validator_node`
parses LLM output against (KDR-004), and that the MCP surface will expose as
tool schemas in M4 per
[architecture.md §7](../../design_docs/architecture.md).

Introduced by M3 Task 02 (see
``design_docs/phases/milestone_3_first_workflow/task_02_planner_schemas.md``).
T02 ships the schema half only: ``PlannerInput`` / ``PlannerStep`` /
``PlannerPlan``. The compiled ``StateGraph`` (``build_planner``) and the
``register("planner", build_planner)`` call land in Task 03
(``task_03_planner_graph.md``).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = [
    "PlannerInput",
    "PlannerStep",
    "PlannerPlan",
]


class PlannerInput(BaseModel):
    """Caller-supplied planning goal.

    ``goal`` is the natural-language ask. ``context`` is an optional short hint
    the caller can pass when they already know relevant files or constraints —
    the explorer node will still run, but it gets seeded with this text.
    ``max_steps`` caps the plan's length so a bad prompt cannot produce a
    200-step plan that blows the budget.
    """

    goal: str = Field(min_length=1, max_length=4000)
    context: str | None = Field(default=None, max_length=4000)
    max_steps: int = Field(default=10, ge=1, le=25)


class PlannerStep(BaseModel):
    """One entry in the plan."""

    index: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=1, max_length=1000)
    actions: list[str] = Field(min_length=1, max_length=10)


class PlannerPlan(BaseModel):
    """The artifact the workflow commits to produce.

    ``extra="forbid"`` is deliberate: a hallucinated ``"notes"`` or
    ``"disclaimer"`` key from the LLM must surface as a ``ValidationError`` the
    :class:`RetryingEdge` can route on, not silently extend the contract.
    """

    goal: str = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=1000)
    steps: list[PlannerStep] = Field(min_length=1, max_length=25)

    model_config = {"extra": "forbid"}
