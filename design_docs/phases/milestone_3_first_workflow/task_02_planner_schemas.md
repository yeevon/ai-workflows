# Task 02 — Planner Pydantic I/O Schemas

**Status:** 📝 Planned.

## What to Build

The two pydantic v2 models that pin the `planner` workflow's public contract: `PlannerInput` (what a caller hands in) and `PlannerPlan` (what the workflow commits to produce). These are the schemas the `ValidatorNode` parses against in [task 03](task_03_planner_graph.md), and — downstream in M4 — the MCP tool schemas exposed to hosts. Pin them here so the graph in T03 and the CLI in T04 can import a stable surface.

Aligns with [architecture.md §7](../../architecture.md) ("MCP tool schemas are the system's public contract. Versioned in pydantic.") and KDR-004 (validators run against these schemas).

## Deliverables

### `ai_workflows/workflows/planner.py` — schema half

Create the workflow module; this task only lands the schema half. The graph builder + `register("planner", …)` call are T03's job.

```python
"""Single-tier planner workflow (M3).

Exports ``PlannerInput`` / ``PlannerPlan`` as the workflow's public contract
and ``build_planner`` (added in T03) returning a compiled ``StateGraph``.
Registered under the name ``"planner"`` at module import time.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PlannerInput(BaseModel):
    """Caller-supplied planning goal.

    ``goal`` is the natural-language ask. ``context`` is an optional short hint
    the caller can pass when they already know relevant files / constraints —
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
    # Free-form; the validator checks the field exists and is non-empty.
    actions: list[str] = Field(min_length=1, max_length=10)


class PlannerPlan(BaseModel):
    """The artifact the workflow commits to produce."""

    goal: str = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=1000)
    steps: list[PlannerStep] = Field(min_length=1, max_length=25)

    # Pydantic v2 — disallow unknown top-level fields so a hallucinated
    # "notes" or "disclaimer" key from the LLM surfaces as a validation error
    # the RetryingEdge can route on.
    model_config = {"extra": "forbid"}
```

### Tests

`tests/workflows/test_planner_schemas.py`:

- `PlannerInput` accepts a minimal `{goal}` payload; defaults `max_steps=10`, `context=None`.
- `PlannerInput(goal="")` raises (min_length=1).
- `PlannerInput(max_steps=0)` and `PlannerInput(max_steps=26)` both raise.
- `PlannerPlan.model_validate` accepts a minimal 1-step plan.
- Extra top-level fields (e.g. `{"goal": "x", "summary": "y", "steps": [...], "disclaimer": "…"}`) raise `ValidationError` — pinning `extra="forbid"` so a rogue LLM output cannot silently extend the contract.
- `PlannerStep.index` must be ≥ 1; `PlannerStep.actions` must be non-empty.

## Acceptance Criteria

- [ ] `PlannerInput`, `PlannerStep`, `PlannerPlan` exported from `ai_workflows.workflows.planner`.
- [ ] Minimal valid payload round-trips through `.model_validate(...)` and `.model_dump()`.
- [ ] `extra="forbid"` on `PlannerPlan` rejects unknown top-level fields.
- [ ] `PlannerInput.max_steps` bounded `[1, 25]`; `PlannerPlan.steps` bounded `[1, 25]`.
- [ ] `uv run pytest tests/workflows/test_planner_schemas.py` green.
- [ ] `uv run lint-imports` stays 3 / 3 kept, 0 broken.

## Dependencies

- [Task 01](task_01_workflow_registry.md) — conceptual (same module will host the T03 registration).
- `pydantic` v2 (already a project dep per [architecture.md §6](../../architecture.md)).
