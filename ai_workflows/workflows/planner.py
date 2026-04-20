"""Single-tier planner workflow (M3).

Pins the pydantic v2 public contract for the ``planner`` workflow — the
schemas that the :class:`ValidatorNode` in `ai_workflows.graph.validator_node`
parses LLM output against (KDR-004), and that the MCP surface will expose as
tool schemas in M4 per
[architecture.md §7](../../design_docs/architecture.md). T03 adds the
compiled ``StateGraph`` that wires every M2 adapter together — two
``TieredNode``/``ValidatorNode`` pairs (KDR-004), two ``retrying_edge``s
per pair routing by the three-bucket taxonomy (KDR-006), a strict-review
``HumanGate``, and a terminal artifact node that persists the approved
plan via :meth:`SQLiteStorage.write_artifact` (added in the same task).

Introduced by M3 Task 02 (see
``design_docs/phases/milestone_3_first_workflow/task_02_planner_schemas.md``)
for the schema half; extended by M3 Task 03 (see
``design_docs/phases/milestone_3_first_workflow/task_03_planner_graph.md``)
with ``build_planner`` and ``register("planner", build_planner)``. The
tier registry that resolves ``planner-explorer`` / ``planner-synth`` is
supplied by the CLI/MCP surface via ``config["configurable"]`` at run time
— this module never reads env vars or imports the ``anthropic`` SDK
(KDR-003).
"""

from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from ai_workflows.graph.error_handler import wrap_with_error_handler
from ai_workflows.graph.human_gate import human_gate
from ai_workflows.graph.retrying_edge import retrying_edge
from ai_workflows.graph.tiered_node import tiered_node
from ai_workflows.graph.validator_node import validator_node
from ai_workflows.primitives.retry import RetryPolicy
from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig
from ai_workflows.workflows import register

__all__ = [
    "PlannerInput",
    "PlannerStep",
    "PlannerPlan",
    "ExplorerReport",
    "PlannerState",
    "build_planner",
    "planner_tier_registry",
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


class ExplorerReport(BaseModel):
    """What the explorer LLM produces for the planner to consume.

    Paired with the ``explorer_validator`` node per KDR-004 — the
    two-validator shape is stricter than the M3 README's single-validator
    sketch, and is the shape this task ships.
    """

    summary: str = Field(min_length=1, max_length=2000)
    considerations: list[str] = Field(min_length=1, max_length=15)
    assumptions: list[str] = Field(default_factory=list, max_length=10)

    model_config = {"extra": "forbid"}


class PlannerState(TypedDict, total=False):
    """State carried through the compiled planner graph.

    Keys:
        run_id: stamped by the caller before invoke; read by ``HumanGate``
            for the ``(run_id, gate_id)`` log row.
        input: caller-supplied :class:`PlannerInput`.
        explorer_output / planner_output: raw LLM text from each
            ``TieredNode``; consumed by the paired validator.
        explorer_output_revision_hint / planner_output_revision_hint:
            cleared to ``None`` by the validator on success.
        explorer_report: validated :class:`ExplorerReport`.
        plan: validated :class:`PlannerPlan` — the artifact.
        gate_plan_review_response: the human's response to the gate
            (``"approved"`` for the happy path).
        last_exception / _retry_counts / _non_retryable_failures:
            three-bucket retry-taxonomy slots (KDR-006) written by
            :func:`wrap_with_error_handler` and read by
            :func:`retrying_edge`.
    """

    run_id: str
    input: PlannerInput
    explorer_output: str
    explorer_output_revision_hint: Any
    explorer_report: ExplorerReport
    planner_output: str
    planner_output_revision_hint: Any
    plan: PlannerPlan
    gate_plan_review_response: str
    last_exception: Any
    _retry_counts: dict[str, int]
    _non_retryable_failures: int


def _explorer_prompt(state: PlannerState) -> tuple[str, list[dict[str, str]]]:
    """Build the explorer node's (system, messages) prompt from planner input."""
    pi = state["input"]
    system = (
        "You are a planning explorer. Given a goal, produce a short report of "
        "considerations and assumptions that a downstream planner will use. "
        "Respond as JSON matching the ExplorerReport schema: "
        '{"summary": str, "considerations": [str, ...], "assumptions": [str, ...]}.'
    )
    user = f"Goal: {pi.goal}\nContext: {pi.context or '(none)'}"
    return system, [{"role": "user", "content": user}]


def _planner_prompt(state: PlannerState) -> tuple[str, list[dict[str, str]]]:
    """Build the planner node's (system, messages) prompt from state + explorer."""
    pi = state["input"]
    report = state["explorer_report"]
    system = (
        "You are a planner. Given a goal and an explorer report, produce a "
        f"structured plan of at most {pi.max_steps} steps. Respond as JSON "
        "matching the PlannerPlan schema: "
        '{"goal": str, "summary": str, "steps": [{"index": int, "title": str, '
        '"rationale": str, "actions": [str, ...]}, ...]}.'
    )
    assumptions = report.assumptions or ["(none)"]
    user = (
        f"Goal: {pi.goal}\n"
        f"Summary: {report.summary}\n"
        f"Considerations: {report.considerations}\n"
        f"Assumptions: {assumptions}"
    )
    return system, [{"role": "user", "content": user}]


async def _artifact_node(
    state: PlannerState, config: RunnableConfig
) -> dict[str, Any]:
    """Persist the approved plan to ``Storage`` via :meth:`write_artifact`.

    The graph wires ``gate → artifact → END`` unconditionally, so the
    approve/reject gate is enforced here: if the user resumed the
    strict-review ``HumanGate`` with anything other than ``"approved"``
    the node is a no-op and no artifact row is written. Keeping the
    single linear edge out of the gate avoids an extra conditional
    router.
    """
    response = state.get("gate_plan_review_response")
    if response != "approved":
        return {}
    storage = config["configurable"]["storage"]
    run_id = state["run_id"]
    plan = state["plan"]
    await storage.write_artifact(run_id, "plan", plan.model_dump_json())
    return {}


def build_planner() -> StateGraph:
    """Return the uncompiled ``planner`` :class:`StateGraph`.

    The caller compiles this builder with an ``AsyncSqliteSaver``
    checkpointer (KDR-009) so ``HumanGate`` interrupts + resumes ride
    LangGraph's durable state. Tier registry + storage + cost callback
    are supplied at invoke time through ``config["configurable"]`` so the
    same graph instance can serve many runs without module-level globals
    (see ``graph/tiered_node.py``).

    Graph shape (KDR-004, §8.2):

    ``START → explorer → explorer_validator → planner → planner_validator
           → gate → artifact → END``

    with self-loop retries off each LLM node and a validator → LLM edge
    on semantic failures.
    """
    policy = RetryPolicy(max_transient_attempts=3, max_semantic_attempts=3)

    explorer = wrap_with_error_handler(
        tiered_node(
            tier="planner-explorer",
            prompt_fn=_explorer_prompt,
            node_name="explorer",
        ),
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
        tiered_node(
            tier="planner-synth",
            prompt_fn=_planner_prompt,
            node_name="planner",
        ),
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
        prompt_fn=lambda s: (
            f"Approve plan for: {s['input'].goal!r}? "
            f"{len(s['plan'].steps)} steps."
        ),
        strict_review=True,
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
    g.add_conditional_edges(
        "explorer",
        decide_after_explorer,
        ["explorer", "explorer_validator"],
    )
    g.add_conditional_edges(
        "explorer_validator",
        decide_after_explorer_validator,
        ["explorer", "planner"],
    )
    g.add_conditional_edges(
        "planner",
        decide_after_planner,
        ["planner", "planner_validator"],
    )
    g.add_conditional_edges(
        "planner_validator",
        decide_after_planner_validator,
        ["planner", "gate"],
    )
    g.add_edge("gate", "artifact")
    g.add_edge("artifact", END)
    return g


def planner_tier_registry() -> dict[str, TierConfig]:
    """Return the two tiers this workflow calls (both Gemini Flash via LiteLLM).

    Shared by the ``aiw run`` CLI (M3 Task 04) and the end-to-end smoke
    test (M3 Task 07) so both paths use one definition. KDR-003 spirit:
    this helper never reads ``GEMINI_API_KEY`` — the env-var read stays
    at the ``LiteLLMAdapter`` boundary when a provider call actually
    fires. ``max_concurrency`` + ``per_call_timeout_s`` match the values
    the planner graph was exercised against in T03's tests.
    """
    return {
        "planner-explorer": TierConfig(
            name="planner-explorer",
            route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
            max_concurrency=2,
            per_call_timeout_s=60,
        ),
        "planner-synth": TierConfig(
            name="planner-synth",
            route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
            max_concurrency=2,
            per_call_timeout_s=90,
        ),
    }


register("planner", build_planner)
