## Task 07b — `PlannerPlan` / `PlannerStep` schema simplification

**Status:** 📝 Planned (2026-04-20).
**Owner:** Builder picks up immediately after T07a closes code-clean.
**Source:** T07a audit — [M3-T07a-ISS-01](issues/task_07a_issue.md#m3-t07a-iss-01--live-e2e-ac-4-blocked-by-plannerplan-schema-complexity-exceeding-geminis-structured-output-budget) (user chose Path α on 2026-04-20).

## Why

T07a's `output_schema=PlannerPlan` wiring surfaced a second live-path gap beyond the original T03/T07 spec set: **Gemini rejects the JSON Schema serialised from the current `PlannerPlan` / `PlannerStep`** with `BadRequestError 400`:

> *"The specified schema produces a constraint that has too many states for serving. Typical causes of this error are schemas with lots of text (for example, very long property or enum names), schemas with long array length limits (especially when nested), or schemas using complex value matchers (for example, integers or numbers with minimum/maximum bounds or strings with complex formats like date-time)."*

The current [`PlannerStep` / `PlannerPlan`](../../../ai_workflows/workflows/planner.py) bounds hit every offender Gemini lists:

- Nested array bound: `steps: list[PlannerStep] = Field(min_length=1, max_length=25)` × `actions: list[str] = Field(min_length=1, max_length=10)`.
- Integer bound: `index: int = Field(ge=1)`.
- Multiple bounded-length strings: `title`, `rationale`, `summary` all carry `min_length=1, max_length=N`.

Positive verification of T07a's own fix stands: `ExplorerReport` (which has bounds but a flatter shape) is admitted and converges single-shot on live Gemini. The planner schema alone is over budget.

**T07a's strict scope is "two `output_schema=` kwarg additions"** — amending `PlannerPlan` is a schema change and therefore belongs in a sibling task (this one). The user chose Path α ("surgical `PlannerPlan` amendment") over Path β (switch tier to `gemini-2.5-pro`) or Path γ (defer live-run evidence) on 2026-04-20.

## Scope

### What to change

[`ai_workflows/workflows/planner.py`](../../../ai_workflows/workflows/planner.py) — `PlannerStep` and `PlannerPlan` only. Drop all `Field(...)` constraints that contribute to the JSON Schema state space; keep the bare type annotations and `model_config = {"extra": "forbid"}`:

```python
class PlannerStep(BaseModel):
    """One entry in the plan."""

    index: int
    title: str
    rationale: str
    actions: list[str]


class PlannerPlan(BaseModel):
    """The artifact the workflow commits to produce.

    ``extra="forbid"`` stays: a hallucinated ``"notes"`` or
    ``"disclaimer"`` key from the LLM must still surface as a
    ``ValidationError`` the :class:`RetryingEdge` can route on.

    Per-field bounds (string ``min_length`` / ``max_length``, nested
    array ``min_length`` / ``max_length``, integer ``ge``) were stripped
    by M3 Task 07b — they pushed the JSON Schema beyond Gemini's
    structured-output complexity budget. Step-count and per-step
    verbosity are now prompt-enforced (the ``_planner_prompt`` system
    message says "at most ``{max_steps}`` steps") and ``PlannerInput``
    keeps its own ``max_steps ∈ [1, 25]`` contract, which the prompt
    reads. Runtime type validation (str / int / list) and closed-world
    enforcement are preserved.
    """

    goal: str
    summary: str
    steps: list[PlannerStep]

    model_config = {"extra": "forbid"}
```

`PlannerInput` is untouched — it is a **caller-input** contract, never a `response_format` target, so its bounds never reach Gemini.

### What *not* to change

- `tiered_node` / `validator_node` / `LiteLLMAdapter` signatures — the T07a scope guarantee (its AC-6) stays intact.
- `PlannerInput` — caller-side contract; Gemini never sees it.
- `ExplorerReport` — admitted by Gemini today; the bounds are benign at its smaller state space.
- The prompt text — "at most ``{max_steps}`` steps" already pins step count.
- `extra="forbid"` — keeps closed-world enforcement; Gemini tolerates `additionalProperties: false` fine (explorer schema carries it already).

## Acceptance criteria

1. `PlannerStep` has no `Field(...)` constraints (type annotations only). `PlannerPlan` has no `Field(...)` constraints; keeps `model_config = {"extra": "forbid"}`.
2. `PlannerPlan.model_json_schema()` contains no `minLength`, `maxLength`, `minItems`, `maxItems`, `minimum`, `maximum`, or `exclusiveMinimum` keys — proves Gemini sees no state-space-contributing bounds. Asserted by a new top-level test in `tests/workflows/test_planner_schemas.py`.
3. Existing schema tests that exercised the dropped bounds are removed, not skipped. `test_minimal_valid_plan_round_trips` and `test_extra_top_level_field_rejected` stay and still pass.
4. `AIW_E2E=1 uv run pytest -m e2e -v` green end-to-end against live Gemini Flash, recorded verbatim in the [CHANGELOG.md](../../../CHANGELOG.md) T07b entry under `**AC-4 live-run evidence (YYYY-MM-DD):**`.
5. `uv run pytest` hermetic run green (no regression in any sibling suite).
6. `uv run lint-imports` 3/3 kept, 0 broken. `uv run ruff check` clean.

## Deliverables

- [ai_workflows/workflows/planner.py](../../../ai_workflows/workflows/planner.py) — `PlannerStep` + `PlannerPlan` bound-strip; refresh the `PlannerPlan` docstring with the T07b rationale (why bounds were removed, where the runtime floor now lives).
- [tests/workflows/test_planner_schemas.py](../../../tests/workflows/test_planner_schemas.py) — delete the tests that asserted dropped bounds; add the `model_json_schema()` no-bounds pin.
- [CHANGELOG.md](../../../CHANGELOG.md) — `### Added — M3 Task 07b: PlannerPlan Schema Simplification (YYYY-MM-DD)` entry under `[Unreleased]`, including the verbatim live-run output.
- [design_docs/phases/milestone_3_first_workflow/README.md](README.md) — insert T07b row in task-order table (between T07a and T08); bump T08 dep list.
- [issues/task_02_issue.md](issues/task_02_issue.md) — append a post-M3 amendment footer documenting the schema loosening and pointing at this task.
- [issues/task_07a_issue.md](issues/task_07a_issue.md) — flip M3-T07a-ISS-01 to `RESOLVED (T07b)` and update AC-4's row in the grading table.
- [issues/task_08_issue.md](issues/task_08_issue.md) — flip M3-T08-ISS-02 to `RESOLVED (T07a + T07b)`.

## Non-goals

- Any `tiered_node` / `validator_node` / `LiteLLMAdapter` signature change.
- Any change to `PlannerInput` / `ExplorerReport`.
- Provider-routing changes (that was Path β; explicitly declined).
- Reintroducing bounds at a different layer (e.g., custom `@field_validator`s). The user chose Path α's literal text — "Pydantic's validator-layer still enforces any bound we keep, so the public contract loosens only for what we drop." What we drop, we drop.

## Dependencies

- [T07a](task_07a_planner_structured_output.md) — lands the `output_schema=` kwargs that make AC-4 live-verifiable in the first place.
- Live `GEMINI_API_KEY` with non-free-tier quota for the AC-4 live-run.
