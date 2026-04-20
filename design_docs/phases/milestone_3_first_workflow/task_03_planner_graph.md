# Task 03 — `planner` StateGraph

**Status:** 📝 Planned.

## What to Build

The first real LangGraph workflow. A compiled `StateGraph` with the shape

```
START → explorer (TieredNode, planner-explorer tier)
      → explorer_validator (ValidatorNode → ExplorerReport)
      → planner (TieredNode, planner-synth tier)
      → planner_validator (ValidatorNode → PlannerPlan)
      → gate (HumanGate, strict_review=True)
      → artifact (persists approved plan to Storage)
      → END
```

Each `TieredNode` is wrapped by `wrap_with_error_handler` from [ai_workflows/graph/error_handler.py](../../../ai_workflows/graph/error_handler.py) so the T07 retry loop M2-T07-ISS-01 proved end-to-end applies here unchanged. Two `retrying_edge`s (one after each LLM node) route by the three-bucket taxonomy (KDR-006). Single tier per the M3 [README](README.md): both LLM nodes route to the same Gemini model today; the shape is what M5 replaces with per-node tier overrides.

Aligns with [architecture.md §4.3](../../architecture.md) (workflows are `StateGraph` modules) and §5 (runtime data flow). KDRs: 001, 004, 006, 007, 009.

## Design note — validator-after-every-LLM-node (KDR-004)

The M3 [README](README.md) shows a simplified `explorer → planner-llm → validator → gate` chain. KDR-004 requires a validator after *every* LLM node. This task specs the stricter version (two validators). If the M3 lead wants the simpler shape, raise it before starting — but do not quietly drop the explorer validator, because an unvalidated explorer output propagating into the planner's prompt is exactly the kind of silent schema-drift KDR-004 exists to prevent.

## Deliverables

### `ai_workflows/workflows/planner.py` — graph half

Extend the T02 module with an `ExplorerReport` schema, the graph builder, and the registry hook:

```python
from __future__ import annotations

from typing import TypedDict, Any

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from ai_workflows.graph.cost_callback import CostTrackingCallback  # type: ignore[import-not-found]  # layer-clean via module-level only
from ai_workflows.graph.error_handler import wrap_with_error_handler
from ai_workflows.graph.human_gate import human_gate
from ai_workflows.graph.retrying_edge import retrying_edge
from ai_workflows.graph.tiered_node import tiered_node
from ai_workflows.graph.validator_node import validator_node
from ai_workflows.primitives.retry import RetryPolicy
from ai_workflows.workflows import register


class ExplorerReport(BaseModel):
    """What the explorer LLM produces for the planner to consume."""

    summary: str = Field(min_length=1, max_length=2000)
    considerations: list[str] = Field(min_length=1, max_length=15)
    assumptions: list[str] = Field(default_factory=list, max_length=10)

    model_config = {"extra": "forbid"}


class PlannerState(TypedDict, total=False):
    """State carried through the planner graph.

    Keys:
        input: ``PlannerInput`` — the caller's request.
        explorer_output: raw LLM text from the explorer node.
        explorer_output_revision_hint: set by the explorer_validator on parse failure.
        explorer_report: validated ``ExplorerReport``.
        planner_output: raw LLM text from the planner node.
        planner_output_revision_hint: set by the planner_validator on parse failure.
        plan: validated ``PlannerPlan`` — the artifact.
        gate_review_response: human response captured at the gate.
        last_exception: T07 retry-edge classified-exception slot.
        _retry_counts / _non_retryable_failures: retry-taxonomy counters (KDR-006).
    """

    input: "PlannerInput"
    explorer_output: str
    explorer_output_revision_hint: Any
    explorer_report: ExplorerReport
    planner_output: str
    planner_output_revision_hint: Any
    plan: "PlannerPlan"
    gate_review_response: str
    last_exception: Any
    _retry_counts: dict[str, int]
    _non_retryable_failures: int


def _explorer_prompt(state):
    pi = state["input"]
    sys = (
        "You are a planning explorer. Given a goal, produce a short report "
        "of considerations and assumptions. Respond as JSON ExplorerReport."
    )
    user = f"Goal: {pi.goal}\nContext: {pi.context or '(none)'}"
    return sys, [{"role": "user", "content": user}]


def _planner_prompt(state):
    pi = state["input"]
    rep = state["explorer_report"]
    sys = (
        "You are a planner. Given a goal and an explorer report, produce a "
        f"structured plan of at most {pi.max_steps} steps. Respond as JSON PlannerPlan."
    )
    user = (
        f"Goal: {pi.goal}\n"
        f"Summary: {rep.summary}\n"
        f"Considerations: {rep.considerations}\n"
        f"Assumptions: {rep.assumptions or '(none)'}"
    )
    return sys, [{"role": "user", "content": user}]


async def _artifact_node(state, config):
    """Persist the approved plan to Storage. Gate has already cleared."""
    storage = config["configurable"]["storage"]
    run_id = config["configurable"]["run_id"]
    await storage.write_artifact(run_id, "plan", state["plan"].model_dump_json())
    return {}


def build_planner():
    """Return the compiled ``planner`` ``StateGraph`` (checkpointer attached by caller)."""
    policy = RetryPolicy(max_transient_attempts=3, max_semantic_attempts=3)

    explorer = wrap_with_error_handler(
        tiered_node(tier="planner-explorer", prompt_fn=_explorer_prompt, node_name="explorer"),
        node_name="explorer",
    )
    explorer_validator = wrap_with_error_handler(
        validator_node(
            schema=ExplorerReport,
            input_key="explorer_output",
            output_key="explorer_report",
            node_name="explorer_validator",
        ),
        node_name="explorer_validator",
    )
    planner = wrap_with_error_handler(
        tiered_node(tier="planner-synth", prompt_fn=_planner_prompt, node_name="planner"),
        node_name="planner",
    )
    planner_validator = wrap_with_error_handler(
        validator_node(
            schema=PlannerPlan,
            input_key="planner_output",
            output_key="plan",
            node_name="planner_validator",
        ),
        node_name="planner_validator",
    )
    gate = human_gate(
        gate_id="plan_review",
        prompt_fn=lambda s: f"Approve plan for: {s['input'].goal!r}? {len(s['plan'].steps)} steps.",
    )

    decide_after_explorer = retrying_edge(
        on_transient="explorer",
        on_semantic="explorer",
        on_terminal="explorer_validator",
        policy=policy,
    )
    decide_after_explorer_validator = retrying_edge(
        on_transient="explorer",
        on_semantic="explorer",
        on_terminal="planner",
        policy=policy,
    )
    decide_after_planner = retrying_edge(
        on_transient="planner",
        on_semantic="planner",
        on_terminal="planner_validator",
        policy=policy,
    )
    decide_after_planner_validator = retrying_edge(
        on_transient="planner",
        on_semantic="planner",
        on_terminal="gate",
        policy=policy,
    )

    g: StateGraph = StateGraph(PlannerState)
    g.add_node("explorer", explorer)
    g.add_node("explorer_validator", explorer_validator)
    g.add_node("planner", planner)
    g.add_node("planner_validator", planner_validator)
    g.add_node("gate", gate)
    g.add_node("artifact", _artifact_node)
    g.add_edge(START, "explorer")
    g.add_conditional_edges("explorer", decide_after_explorer, ["explorer", "explorer_validator"])
    g.add_conditional_edges(
        "explorer_validator", decide_after_explorer_validator, ["explorer", "planner"]
    )
    g.add_conditional_edges("planner", decide_after_planner, ["planner", "planner_validator"])
    g.add_conditional_edges(
        "planner_validator", decide_after_planner_validator, ["planner", "gate"]
    )
    g.add_edge("gate", "artifact")
    g.add_edge("artifact", END)
    return g


# Register at import time — callers `import ai_workflows.workflows.planner` before
# invoking `ai_workflows.workflows.get("planner")`.
register("planner", build_planner)
```

### Tier registry additions

Two new entries under the tier registry the CLI passes in via `config["configurable"]["tier_registry"]`:

- `planner-explorer` → `LiteLLMRoute(model="gemini/gemini-2.5-flash")`, `max_concurrency=2`, `per_call_timeout_s=60`.
- `planner-synth` → `LiteLLMRoute(model="gemini/gemini-2.5-flash")`, `max_concurrency=2`, `per_call_timeout_s=90`.

Both single-tier (same Gemini model) per M3's `Non-goals → Multi-tier routing (M5)`. M5 replaces `planner-synth` with a Claude Code subprocess or Qwen-via-Ollama route without touching the graph.

### Artifact persistence

Extend `SQLiteStorage` with a `write_artifact(run_id, kind, payload_json)` + `read_artifact(run_id, kind)` pair — they do not exist yet, so T03 adds them. This is a cross-layer change (primitives), so flag it clearly in the task's deviations if it must land inside this task or file a sibling T03a if the M3 lead prefers splitting.

### Tests

`tests/workflows/test_planner_graph.py`:

- Build: `build_planner()` returns a builder that compiles against `AsyncSqliteSaver` without error; the graph's node set is exactly `{explorer, explorer_validator, planner, planner_validator, gate, artifact}`.
- Registration: importing the module registers `"planner"` in the registry (checked via `ai_workflows.workflows.get("planner")`).
- Happy path (stubbed `LiteLLMAdapter`): valid `ExplorerReport` JSON + valid `PlannerPlan` JSON → graph pauses at gate; resume with `"approved"` → `state["plan"]` is a `PlannerPlan`; artifact row written to `Storage`.
- Retry path (stubbed): `litellm.RateLimitError` on first explorer call → `_retry_counts["explorer"]` bumps to 1 → second call succeeds → graph continues. Mirror of the T08 smoke test's retry proof, at workflow scope.
- Validator-driven revision: invalid JSON from the planner → `planner_validator` raises `RetryableSemantic` → `retrying_edge` routes back to `planner` with a revision hint set.
- Rejected gate: resume with `"rejected"` (or any string ≠ `"approved"`) does NOT write an artifact. Picking the exact rejected-response handling is up to the builder — the test just pins the contract that `storage.write_artifact` is not invoked on rejection.

## Acceptance Criteria

- [ ] `build_planner()` returns a builder that compiles against `AsyncSqliteSaver`.
- [ ] Importing `ai_workflows.workflows.planner` registers the builder under `"planner"` in the registry from [task 01](task_01_workflow_registry.md).
- [ ] Graph includes two validators (one after explorer, one after planner) per KDR-004.
- [ ] All `TieredNode`s are wrapped with `wrap_with_error_handler`; all retry decisions go through `retrying_edge`.
- [ ] Happy-path test pauses at `HumanGate` and resumes to produce a valid `PlannerPlan` artifact in `Storage`.
- [ ] Retry-path test proves the T08 retry loop applies at workflow scope.
- [ ] No `ANTHROPIC_API_KEY` / `anthropic` reference in the module (KDR-003).
- [ ] `uv run pytest tests/workflows/test_planner_graph.py` green; `uv run lint-imports` 3 / 3 kept.

## Dependencies

- [Task 01](task_01_workflow_registry.md) — `register`.
- [Task 02](task_02_planner_schemas.md) — `PlannerInput`, `PlannerPlan`.
- M2 [Task 03](../milestone_2_graph/task_03_tiered_node.md) (`tiered_node`), [Task 04](../milestone_2_graph/task_04_validator_node.md) (`validator_node`), [Task 05](../milestone_2_graph/task_05_human_gate.md) (`human_gate`), [Task 07](../milestone_2_graph/task_07_retrying_edge.md) (`retrying_edge`), [Task 08](../milestone_2_graph/task_08_checkpointer.md) (checkpointer + `wrap_with_error_handler`).
- M1 [Task 05](../milestone_1_reconciliation/task_05_trim_storage.md) — `SQLiteStorage`; extends it with `write_artifact` / `read_artifact`.
- M1 [Task 06](../milestone_1_reconciliation/task_06_refit_tier_config.md) — `TierConfig`, `LiteLLMRoute`.
