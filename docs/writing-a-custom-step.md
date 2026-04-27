# Writing a Custom Step

> **Note:** This guide ships with M19 Task 06. The full content — `Step` base class contract,
> `execute()` typical path, `compile()` upgrade path for fan-out / sub-graph / conditional
> cases, `compile_step_in_isolation` testing fixture, and graduation hints — lands at T06.

For now, see [`docs/writing-a-workflow.md`](writing-a-workflow.md) §"When you need more" for
a brief orientation on Tier 3 custom step types, and
[`docs/writing-a-graph-primitive.md`](writing-a-graph-primitive.md) for Tier 4 (escape to
LangGraph directly).
