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

## Quality knobs (M12 Task 03 / ADR-0009 / KDR-014)

The audit cascade for ``planner-explorer`` is opt-in via a module-level
constant:

- ``_AUDIT_CASCADE_ENABLED_DEFAULT = False`` — framework-author default;
  flip to ``True`` post-T04 telemetry via code-edit + commit + release.
- ``AIW_AUDIT_CASCADE=1`` — global env-var override; flips ALL workflows
  that consult it.
- ``AIW_AUDIT_CASCADE_PLANNER=1`` — per-workflow override; flips ONLY
  this workflow.

Per KDR-014, quality knobs MUST NOT appear on ``PlannerInput`` or any
``WorkflowSpec``/CLI flag. The decision is made once per Python process at
module-import time; the compiled graph reflects it. See ADR-0009 §Open
questions for the enable-only asymmetry: a per-workflow var cannot DISABLE
what the global enables.

The ``_AUDIT_CASCADE_ENABLED`` constant has the same name in ``planner.py``
and ``slice_refactor.py`` by design — each module owns its own decision;
cross-module references must qualify with the module name.
"""

from __future__ import annotations

import json
import os
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from ai_workflows.graph.audit_cascade import audit_cascade_node
from ai_workflows.graph.error_handler import wrap_with_error_handler
from ai_workflows.graph.human_gate import human_gate
from ai_workflows.graph.ollama_fallback_gate import (
    FALLBACK_DECISION_STATE_KEY,
    FallbackChoice,
    build_ollama_fallback_gate,
)
from ai_workflows.graph.retrying_edge import retrying_edge
from ai_workflows.graph.tiered_node import tiered_node
from ai_workflows.graph.validator_node import validator_node
from ai_workflows.primitives.circuit_breaker import CircuitOpen
from ai_workflows.primitives.retry import RetryPolicy
from ai_workflows.primitives.tiers import ClaudeCodeRoute, LiteLLMRoute, TierConfig
from ai_workflows.workflows import register

# ---------------------------------------------------------------------------
# M12 T03 / ADR-0009 / KDR-014 — cascade quality policy at module level.
# Framework-author default; flip to True post-T04 telemetry per workflow,
# code-edit + commit + release. NO ``audit_cascade_enabled`` field on
# PlannerInput; per KDR-014 quality knobs MUST NOT land on Input models.
# ---------------------------------------------------------------------------
_AUDIT_CASCADE_ENABLED_DEFAULT = False

# Operator override (read at module-import). Two granularities:
#   AIW_AUDIT_CASCADE=1               — flips ALL workflows that consult it.
#   AIW_AUDIT_CASCADE_PLANNER=1       — flips ONLY this workflow.
# Semantics: per-workflow var is ENABLE-ONLY when the global is on.
# To DISABLE a single workflow when AIW_AUDIT_CASCADE=1 is set, unset
# the global and re-enable the workflows you want via per-workflow vars.
# (Three-state per-workflow override deferred — see ADR-0009 §Open questions.)
_AUDIT_CASCADE_ENABLED = (
    _AUDIT_CASCADE_ENABLED_DEFAULT
    or os.getenv("AIW_AUDIT_CASCADE", "0") == "1"
    or os.getenv("AIW_AUDIT_CASCADE_PLANNER", "0") == "1"
)

__all__ = [
    "PLANNER_OLLAMA_FALLBACK",
    "PLANNER_RETRY_POLICY",
    "_AUDIT_CASCADE_ENABLED_DEFAULT",
    "_AUDIT_CASCADE_ENABLED",
    "OllamaFallback",
    "PlannerInput",
    "PlannerStep",
    "PlannerPlan",
    "ExplorerReport",
    "PlannerState",
    "TERMINAL_GATE_ID",
    "FINAL_STATE_KEY",
    "build_planner",
    "planner_eval_node_schemas",
    "planner_tier_registry",
]


TERMINAL_GATE_ID = "plan_review"
"""Gate id for the strict-review ``HumanGate`` this workflow pauses at.

Exposed so :mod:`ai_workflows.workflows._dispatch` can discover the
resumed-response state key (``f"gate_{TERMINAL_GATE_ID}_response"``)
without hardcoding the planner's id (resolves T01-CARRY-DISPATCH-GATE
from the M6 T01 Builder-phase scope review). ``slice_refactor``
exposes the same symbol name with its own gate id
(``"slice_refactor_review"``).
"""


FINAL_STATE_KEY = "plan"
"""State key dispatch reads to detect a completed planner run (M6 T06).

Co-defined with ``slice_refactor``'s own :data:`FINAL_STATE_KEY` so
:mod:`ai_workflows.workflows._dispatch` can detect a completed run
uniformly via ``state[FINAL_STATE_KEY] is not None``. For the planner
this has always been ``"plan"`` — the constant formalises the convention
rather than changing behaviour (resolves the planner half of
``T01-CARRY-DISPATCH-COMPLETE`` from the M6 T01 audit). Workflows that
omit the constant fall back to the ``"plan"`` default in dispatch, so
the contract is backwards-compatible for any future workflow whose
terminal signal is still a ``plan`` row.
"""


class OllamaFallback(BaseModel):
    """M8 T04 tier-pair declaration for the Ollama-outage fallback edge.

    Names the **logical** Ollama-backed tier a workflow calls (``logical``)
    and the **non-Ollama replacement** (``fallback_tier``) that
    :func:`_ollama_fallback_dispatch` stamps into
    ``state['_mid_run_tier_overrides']`` when the operator picks
    :attr:`FallbackChoice.FALLBACK`. Both names must already live in the
    workflow's tier registry — this config is pure metadata, it does not
    mint new tiers.

    Introduced by M8 Task 04 (architecture.md §8.4). Exposed at module
    scope so a workflow's constant (e.g. :data:`PLANNER_OLLAMA_FALLBACK`)
    can be inspected by tests without re-threading it through
    :func:`build_planner`.
    """

    logical: str
    fallback_tier: str


PLANNER_OLLAMA_FALLBACK = OllamaFallback(
    logical="planner-explorer",
    fallback_tier="planner-synth",
)
"""Tier-pair the planner workflow falls back to on an Ollama outage (M8 T04).

``planner-explorer`` is ``ollama/qwen2.5-coder:32b`` per M5 T01; the
fallback route is ``planner-synth`` (``ClaudeCodeRoute(cli_model_flag="opus")``
per M5 T02), which is not Ollama-backed and therefore not breakered. After
:attr:`FallbackChoice.FALLBACK` the explorer node resolves
``planner-explorer`` through the state-level override mechanism (see
:func:`ai_workflows.graph.tiered_node._resolve_tier`) and dispatches the
replacement route until the run finishes.
"""


PLANNER_RETRY_POLICY = RetryPolicy(
    max_transient_attempts=5, max_semantic_attempts=3
)
"""Retry budget for both planner LLM nodes.

``max_transient_attempts`` is bumped from the KDR-006 default of 3 to 5 by
M3 Task 07a: Gemini 503 ``ServiceUnavailableError`` is a request-admission
failure with ``input_tokens=null`` / ``cost_usd=null`` on the ``TokenUsage``
record, so every 503 retry costs only ~2s of latency, no tokens. Under the
default budget a single 503 burst during the ``workflow_dispatch`` e2e job
would exhaust the transient bucket before convergence could be tried.
``max_semantic_attempts`` stays at 3 — semantic retries *do* burn tokens
(~1000–1500 output tokens per re-roll) and T07a's ``output_schema=`` wiring
makes the semantic-failure class near-impossible, so widening that bucket
is both expensive and unnecessary.
"""


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
    """One entry in the plan.

    Per-field bounds (``ge=1`` on ``index``; ``min_length``/``max_length``
    on ``title``, ``rationale``, ``actions``) were stripped by M3 Task 07b
    — they pushed the ``PlannerPlan`` JSON Schema beyond Gemini's
    structured-output complexity budget (``BadRequestError 400: schema
    produces a constraint that has too many states for serving``). Runtime
    type validation (``int`` / ``str`` / ``list[str]``) is preserved; the
    dropped bounds are prompt-enforced (``_planner_prompt`` caps step
    count via ``PlannerInput.max_steps``).
    """

    index: int
    title: str
    rationale: str
    actions: list[str]


class PlannerPlan(BaseModel):
    """The artifact the workflow commits to produce.

    ``extra="forbid"`` stays: a hallucinated ``"notes"`` or
    ``"disclaimer"`` key from the LLM must still surface as a
    ``ValidationError`` the :class:`RetryingEdge` can route on.

    Per-field bounds (``min_length``/``max_length`` on ``goal``, ``summary``;
    ``min_length``/``max_length`` on ``steps``) were stripped by M3 Task 07b
    alongside the ``PlannerStep`` bounds — same reason (Gemini
    structured-output budget). The floor that remains:

    * Pydantic type validation (``str``, ``list[PlannerStep]``) and
      closed-world (``extra="forbid"``) enforcement.
    * The planner system prompt, which instructs "at most ``{max_steps}``
      steps" and reads ``PlannerInput.max_steps`` (bounded ``[1, 25]``
      on the caller side, unchanged by T07b).
    """

    goal: str
    summary: str
    steps: list[PlannerStep]

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

    M12 T03 — cascade-prefixed channels populated when
    ``_AUDIT_CASCADE_ENABLED`` is True. Declared ``total=False`` so the
    disabled-default path does not trip on missing keys. Channel naming
    uses ``planner_explorer_audit`` prefix matching
    ``audit_cascade_node(name="planner_explorer_audit", ...)`` in
    :func:`build_planner` to avoid collision if a future graph composes
    two cascades in one outer state.

    The two shared cascade channels (``cascade_role``, ``cascade_transcript``)
    and the 7 prefixed channels are written by the cascade sub-graph.
    ``total=False`` means they are typed-but-optional — the planner and
    validator nodes do not populate them on the disabled-default path.
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
    _mid_run_tier_overrides: dict[str, str]
    _ollama_fallback_fired: bool
    _ollama_fallback_reason: str
    _ollama_fallback_count: int
    ollama_fallback_decision: FallbackChoice
    gate_ollama_fallback_response: str
    ollama_fallback_aborted: bool

    # M12 T03 — cascade channels populated when _AUDIT_CASCADE_ENABLED is True.
    # Inert when False — the disabled-default path never writes these keys.
    cascade_role: str  # Literal["author", "auditor", "verdict"] in spirit
    # cascade_transcript inner shape: {"author_attempts": list[str],
    # "auditor_verdicts": list[AuditVerdict]} — per audit_cascade.py:674-677
    cascade_transcript: dict[str, list]
    planner_explorer_audit_primary_output: str
    planner_explorer_audit_primary_parsed: ExplorerReport
    planner_explorer_audit_primary_output_revision_hint: str | None
    planner_explorer_audit_auditor_output: str
    planner_explorer_audit_auditor_output_revision_hint: str | None
    planner_explorer_audit_audit_verdict: Any
    planner_explorer_audit_audit_exhausted_response: str


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


def _stamp_ollama_fallback_ctx(state: PlannerState) -> dict[str, Any]:
    """Render the Ollama-fallback gate's prompt context from ``last_exception`` (M8 T04).

    Runs on the ``catch_circuit_open`` branch immediately before the
    strict-review gate. Reads the :class:`CircuitOpen` exception the
    upstream :func:`wrap_with_error_handler` captured into
    ``state['last_exception']`` and writes:

    * ``_ollama_fallback_reason`` — mirrors :attr:`CircuitOpen.last_reason`
      so the gate prompt (rendered by
      :func:`render_ollama_fallback_prompt`) can name the exact breaker
      trip cause.
    * ``_ollama_fallback_count`` — monotonically increments so a second
      fallback gate in the same run shows a higher counter even though
      :data:`_ollama_fallback_fired` short-circuits the wiring after the
      first firing.

    Pure synthesis — no LLM call, no validator pairing (KDR-004 n/a). The
    alternative (doing this inside the gate node) would couple the gate
    factory to workflow-specific state vocabulary; keeping the stamp in
    the workflow keeps the factory reusable across planner +
    slice_refactor.
    """
    exc = state.get("last_exception")
    reason = exc.last_reason if isinstance(exc, CircuitOpen) else ""
    count = (state.get("_ollama_fallback_count") or 0) + 1
    return {
        "_ollama_fallback_reason": reason,
        "_ollama_fallback_count": count,
    }


def _ollama_fallback_dispatch(state: PlannerState) -> dict[str, Any]:
    """Consume the operator's :class:`FallbackChoice` and stamp downstream
    state (M8 T04).

    Runs after the Ollama-fallback gate resumes. Three responsibilities:

    1. **Mark the gate as fired** (``_ollama_fallback_fired=True``) so the
       edge wrapper around :func:`retrying_edge` (see
       :func:`_decide_after_explorer_with_fallback`) does not re-route to
       the gate on a second :class:`CircuitOpen` — a repeat trip after
       the operator has already chosen escalates directly to
       :func:`_planner_hard_stop` rather than double-prompting.
    2. **Clear the retry-taxonomy slots** (``last_exception=None``,
       ``_retry_counts={}``) so the explorer re-fire starts with a clean
       transient budget. :class:`CircuitOpen` was never counted against
       the budget (see
       :mod:`ai_workflows.graph.error_handler`), but explorer may have
       bumped the transient counter on earlier attempts in the same
       streak — zeroing it gives the retry choice its full budget back.
       The planner's ``last_exception`` channel has no reducer, so
       writing ``None`` cleanly clears it.
    3. **Stamp the mid-run tier override on** :attr:`FallbackChoice.FALLBACK`
       so :func:`ai_workflows.graph.tiered_node._resolve_tier` swaps the
       tripped tier for :attr:`OllamaFallback.fallback_tier` on every
       subsequent :func:`tiered_node` invocation in this run.

    ABORT is routed by :func:`_route_after_fallback_dispatch` without
    additional state writes — the conditional edge sees
    :attr:`FallbackChoice.ABORT` and directs to :func:`_planner_hard_stop`,
    which owns the ``runs.status='aborted'`` terminal and the
    ``ollama_fallback_aborted`` dispatch signal.
    """
    decision = state.get(FALLBACK_DECISION_STATE_KEY)
    updates: dict[str, Any] = {
        "_ollama_fallback_fired": True,
        "last_exception": None,
        "_retry_counts": {},
    }
    if decision is FallbackChoice.FALLBACK:
        overrides = dict(state.get("_mid_run_tier_overrides") or {})
        overrides[PLANNER_OLLAMA_FALLBACK.logical] = (
            PLANNER_OLLAMA_FALLBACK.fallback_tier
        )
        updates["_mid_run_tier_overrides"] = overrides
    return updates


async def _planner_hard_stop(
    state: PlannerState, config: RunnableConfig
) -> dict[str, Any]:
    """Terminal node for the Ollama-fallback ABORT branch (M8 T04).

    Runs exclusively on the :attr:`FallbackChoice.ABORT` branch of
    :func:`_route_after_fallback_dispatch`, and on a double-:class:`CircuitOpen`
    escalation (repeat trip after the gate already fired — see
    :func:`_decide_after_explorer_with_fallback`). Writes a
    ``hard_stop_metadata`` artefact via
    :meth:`SQLiteStorage.write_artifact` so the post-mortem surface can
    read why the run aborted without re-running the graph, then returns
    ``{"ollama_fallback_aborted": True}`` which
    :mod:`ai_workflows.workflows._dispatch` reads as the terminal signal
    to flip ``runs.status='aborted'``.

    Distinct from the slice_refactor ``hard_stop`` node (which carries a
    ``failing_slice_ids`` payload) — the planner has no per-slice fan-out,
    so the abort signal is a single boolean and the metadata row names
    the tripped tier instead. Reusing the same ``hard_stop_metadata``
    artefact ``kind`` keeps the cross-workflow schema uniform.
    """
    run_id = state["run_id"]
    storage = config["configurable"]["storage"]
    payload = json.dumps(
        {
            "reason": "ollama_fallback_abort",
            "tier": PLANNER_OLLAMA_FALLBACK.logical,
        }
    )
    await storage.write_artifact(run_id, "hard_stop_metadata", payload)
    return {"ollama_fallback_aborted": True}


def _route_after_fallback_dispatch(state: PlannerState) -> str:
    """Conditional-edge router after :func:`_ollama_fallback_dispatch` (M8 T04).

    Reads the :class:`FallbackChoice` the gate parsed into
    :data:`FALLBACK_DECISION_STATE_KEY` and directs:

    * :attr:`FallbackChoice.ABORT` → ``"planner_hard_stop"`` (terminal
      abort, :func:`_planner_hard_stop` writes the metadata artefact and
      dispatch flips ``runs.status='aborted'``).
    * :attr:`FallbackChoice.RETRY` / :attr:`FallbackChoice.FALLBACK` →
      ``"explorer"`` (re-fire the tripped node; FALLBACK also carries the
      stamped tier override so the call routes to the replacement tier).

    Unknown / missing → ``"explorer"`` (safe default — RETRY semantics).
    """
    decision = state.get(FALLBACK_DECISION_STATE_KEY)
    if decision is FallbackChoice.ABORT:
        return "planner_hard_stop"
    return "explorer"


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

    When ``_AUDIT_CASCADE_ENABLED`` is False (default):

    ``START → explorer → explorer_validator → planner → planner_validator
           → gate → artifact → END``

    When ``_AUDIT_CASCADE_ENABLED`` is True (M12 T03):

    ``START → planner_explorer_audit (cascade sub-graph) → planner
           → planner_validator → gate → artifact → END``

    The cascade sub-graph composes primary (planner-explorer) →
    validator → auditor (auditor-sonnet) → verdict. On auditor failure
    the primary re-fires with enriched context; on exhaustion the cascade
    routes to its internal ``HumanGate`` (the planner has no fan-out, so
    the gate-interrupt semantic is correct). Per ADR-0009 / KDR-014, the
    cascade decision is made once at module-import time; there is no
    runtime conditional edge keyed off the policy flag.
    """
    policy = PLANNER_RETRY_POLICY

    if _AUDIT_CASCADE_ENABLED:
        # Build-time only — do NOT call audit_cascade_node() in a
        # per-slice or per-step inner loop.
        explorer = audit_cascade_node(
            primary_tier="planner-explorer",
            primary_prompt_fn=_explorer_prompt,
            primary_output_schema=ExplorerReport,
            auditor_tier="auditor-sonnet",
            policy=policy,
            name="planner_explorer_audit",
        )
        # The cascade sub-graph writes to planner_explorer_audit_primary_parsed
        # but the downstream planner node reads explorer_report. Add a thin
        # bridge node to copy the parsed output into the expected key.
        def _cascade_to_explorer_report(state: PlannerState) -> dict[str, Any]:
            """Bridge cascade output to the explorer_report key expected downstream."""
            parsed = state.get("planner_explorer_audit_primary_parsed")
            if parsed is not None:
                return {"explorer_report": parsed}
            return {}

        cascade_enabled = True
    else:
        # Existing M11-shape: wrap_with_error_handler(tiered_node(...))
        explorer = wrap_with_error_handler(
            tiered_node(
                tier="planner-explorer",
                prompt_fn=_explorer_prompt,
                output_schema=ExplorerReport,
                node_name="explorer",
            ),
            node_name="explorer",
        )
        cascade_enabled = False

    planner = wrap_with_error_handler(
        tiered_node(
            tier="planner-synth",
            prompt_fn=_planner_prompt,
            output_schema=PlannerPlan,
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

    if cascade_enabled:
        # Cascade path: explorer is a compiled cascade sub-graph; the bridge
        # node copies planner_explorer_audit_primary_parsed → explorer_report.
        g.add_node("explorer", explorer)
        g.add_node("cascade_bridge", _cascade_to_explorer_report)
        g.add_node("planner", planner)
        g.add_node("planner_validator", planner_validator)
        g.add_node("gate", gate)
        g.add_node("artifact", _artifact_node)

        g.add_edge(START, "explorer")
        g.add_edge("explorer", "cascade_bridge")
        g.add_edge("cascade_bridge", "planner")
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
    else:
        # Standard M11 path: explorer + explorer_validator with Ollama fallback.
        explorer_validator = wrap_with_error_handler(
            validator_node(
                schema=ExplorerReport,
                input_key="explorer_output",
                output_key="explorer_report",
                node_name="explorer_validator",
            ),
            node_name="explorer_validator",
        )
        ollama_fallback = build_ollama_fallback_gate(
            tier_name=PLANNER_OLLAMA_FALLBACK.logical,
            fallback_tier=PLANNER_OLLAMA_FALLBACK.fallback_tier,
        )
        decide_after_explorer_base = retrying_edge(
            on_transient="explorer",
            on_semantic="explorer",
            on_terminal="explorer_validator",
            policy=policy,
        )

        def _decide_after_explorer_with_fallback(state: PlannerState) -> str:
            """CircuitOpen-aware wrapper around :func:`decide_after_explorer_base`.

            Intercepts :class:`CircuitOpen` on ``state['last_exception']``
            before delegating to the three-bucket :func:`retrying_edge`. First
            trip in the run → route to ``ollama_fallback_stamp`` → gate.
            Second trip (gate already fired; operator already chose) →
            escalate directly to :func:`_planner_hard_stop` rather than
            double-prompting or falling into ``retrying_edge``'s
            ``on_terminal`` branch (which would land the run on
            ``explorer_validator`` with no ``explorer_output`` — a confusing
            downstream error).
            """
            exc = state.get("last_exception")
            already_fired = state.get("_ollama_fallback_fired") or False
            if isinstance(exc, CircuitOpen):
                if already_fired:
                    return "planner_hard_stop"
                return "ollama_fallback_stamp"
            return decide_after_explorer_base(state)

        decide_after_explorer_validator = retrying_edge(
            on_transient="explorer",
            on_semantic="explorer",
            on_terminal="planner",
            policy=policy,
        )

        g.add_node("explorer", explorer)
        g.add_node("explorer_validator", explorer_validator)
        g.add_node("planner", planner)
        g.add_node("planner_validator", planner_validator)
        g.add_node("gate", gate)
        g.add_node("artifact", _artifact_node)
        g.add_node("ollama_fallback_stamp", _stamp_ollama_fallback_ctx)
        g.add_node("ollama_fallback", ollama_fallback)
        g.add_node("ollama_fallback_dispatch", _ollama_fallback_dispatch)
        g.add_node("planner_hard_stop", _planner_hard_stop)

        g.add_edge(START, "explorer")
        g.add_conditional_edges(
            "explorer",
            _decide_after_explorer_with_fallback,
            [
                "explorer",
                "explorer_validator",
                "ollama_fallback_stamp",
                "planner_hard_stop",
            ],
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
        g.add_edge("ollama_fallback_stamp", "ollama_fallback")
        g.add_edge("ollama_fallback", "ollama_fallback_dispatch")
        g.add_conditional_edges(
            "ollama_fallback_dispatch",
            _route_after_fallback_dispatch,
            {"explorer": "explorer", "planner_hard_stop": "planner_hard_stop"},
        )
        g.add_edge("planner_hard_stop", END)

    return g


def planner_eval_node_schemas() -> dict[str, type[BaseModel]]:
    """Return the eval-capture schema map: ``node_name → output pydantic class``.

    Introduced by M7 Task 04 so ``aiw eval capture`` can reconstruct one
    :class:`EvalCase` per LLM node from a completed run's checkpointed
    state without re-firing any provider. The keys are the
    ``TieredNode`` names this workflow wires into its graph (``explorer``
    + ``planner``); the values are the pydantic output classes that the
    paired ``ValidatorNode`` parses against. The capture helper resolves
    each ``case.output_schema_fqn`` by dotting the class's
    ``__module__`` + ``__qualname__`` (matches
    :func:`ai_workflows.evals.capture_callback.output_schema_fqn`).

    Kept as a callable (not a module-level dict) so future workflow
    variants can parameterise it — the CLI just calls this when the
    target workflow exposes it, and falls back to a clear error when
    a workflow has no registry.
    """

    return {
        "explorer": ExplorerReport,
        "planner": PlannerPlan,
    }


def planner_tier_registry() -> dict[str, TierConfig]:
    """Return the tiers this workflow calls plus the auditor pair.

    M5 Task 01 repoints ``planner-explorer`` to local Qwen via Ollama
    (``ollama/qwen2.5-coder:32b``) per architecture.md §4.3's two-phase
    planner design — LiteLLM dispatches the Ollama HTTP call (KDR-007),
    and the default ``api_base`` targets the daemon at
    ``http://localhost:11434``. M5 Task 02 repoints ``planner-synth``
    to Claude Code Opus via the OAuth subprocess driver
    (``ClaudeCodeRoute(cli_model_flag="opus")``) — LiteLLM does not
    cover OAuth-authenticated subprocess providers, so the Claude Code
    path stays bespoke (KDR-007). ``max_concurrency=1`` on both tiers
    reflects the underlying single-writer constraints (local model for
    explorer, single OAuth session for synth); Opus + subprocess spawn
    has a higher p95 than hosted Gemini so the synth timeout goes up
    to 300 s. KDR-003 spirit: this helper never reads API keys — env
    reads stay at the ``LiteLLMAdapter`` / CLI boundary when a provider
    call actually fires.

    M12 Task 01 adds ``auditor-sonnet`` and ``auditor-opus`` — the two
    auditor tiers for the tiered audit cascade (ADR-0004 / KDR-011).
    Both route via the existing ``ClaudeCodeSubprocess`` driver with no
    new dependency. ``max_concurrency=1`` matches ``planner-synth``'s
    single-OAuth-session constraint. ``per_call_timeout_s=300`` reuses
    the ``planner-synth`` baseline (same driver, same subprocess spawn
    characteristics; deviation requires named-evidence comment per spec).
    ``slice_refactor_tier_registry`` composes this registry, so both
    auditor tiers are automatically available there too.
    """
    return {
        "planner-explorer": TierConfig(
            name="planner-explorer",
            route=LiteLLMRoute(
                model="ollama/qwen2.5-coder:32b",
                api_base="http://localhost:11434",
            ),
            max_concurrency=1,
            per_call_timeout_s=180,
        ),
        "planner-synth": TierConfig(
            name="planner-synth",
            route=ClaudeCodeRoute(cli_model_flag="opus"),
            max_concurrency=1,
            per_call_timeout_s=300,
        ),
        "auditor-sonnet": TierConfig(
            name="auditor-sonnet",
            route=ClaudeCodeRoute(cli_model_flag="sonnet"),
            max_concurrency=1,
            per_call_timeout_s=300,
        ),
        "auditor-opus": TierConfig(
            name="auditor-opus",
            route=ClaudeCodeRoute(cli_model_flag="opus"),
            max_concurrency=1,
            per_call_timeout_s=300,
        ),
    }


register("planner", build_planner)
