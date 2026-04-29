"""Golden hermetic test for planner cascade fixture capture (M12 Task 06).

Drives a cascade-enabled planner run with ``CaptureCallback`` wired and
asserts that both the primary and auditor fixtures land at the expected
paths under ``<dataset>/planner/planner_explorer_audit_primary/`` and
``<dataset>/planner/planner_explorer_audit_auditor/``.

The cascade is built directly via ``audit_cascade_node()`` (inline pattern —
NOT via ``run_workflow``) so the test owns its ``CostTracker`` instance and
can query ``tracker.by_role(run_id)`` directly.

Stub LLM via ``_StubClaudeCodeAdapter`` (canonical pattern from
``tests/graph/test_audit_cascade.py:107``).  The planner cascade uses
``name="planner_explorer_audit"`` (``planner.py:570``) and
``primary_output_schema=ExplorerReport``.

Relationship to other modules
------------------------------
* :mod:`ai_workflows.graph.audit_cascade` — ``audit_cascade_node`` factory.
* :mod:`ai_workflows.workflows.planner` — source of ``ExplorerReport`` schema
  and the ``planner_explorer_audit`` cascade name.
* :mod:`ai_workflows.evals.capture_callback` — ``CaptureCallback`` under test.
* :mod:`ai_workflows.evals.storage` — ``load_case`` for fixture-load assertion.
* ``tests/graph/test_audit_cascade.py`` — stub-adapter pattern source.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypedDict

import pytest
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ai_workflows.evals import CaptureCallback
from ai_workflows.evals.storage import load_case
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.graph.audit_cascade import audit_cascade_node
from ai_workflows.graph.checkpointer import build_async_checkpointer
from ai_workflows.graph.cost_callback import CostTrackingCallback
from ai_workflows.primitives.cost import CostTracker, TokenUsage
from ai_workflows.primitives.retry import RetryPolicy
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.tiers import ClaudeCodeRoute, LiteLLMRoute, TierConfig
from ai_workflows.workflows.planner import ExplorerReport

# ---------------------------------------------------------------------------
# Cascade parameters matching planner.py:564-570
# ---------------------------------------------------------------------------

CASCADE_NAME = "planner_explorer_audit"
DATASET = "test-dataset"
WORKFLOW = "planner"

_POLICY = RetryPolicy(max_transient_attempts=5, max_semantic_attempts=3)

# ---------------------------------------------------------------------------
# Stub adapters (canonical pattern from tests/graph/test_audit_cascade.py:107)
# ---------------------------------------------------------------------------


class _StubLiteLLMAdapter:
    """Scriptable LiteLLMAdapter stub — primary (planner-explorer) tier path."""

    script: list[Any] = []
    calls: list[dict] = []

    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        self.route = route

    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict],
        response_format: Any = None,
    ) -> tuple[str, TokenUsage]:
        _StubLiteLLMAdapter.calls.append({"system": system, "messages": messages})
        if not _StubLiteLLMAdapter.script:
            raise AssertionError("stub script exhausted")
        head = _StubLiteLLMAdapter.script.pop(0)
        if isinstance(head, BaseException):
            raise head
        text, cost = head
        return text, TokenUsage(
            input_tokens=5, output_tokens=7, cost_usd=cost, model=self.route.model
        )


class _StubClaudeCodeAdapter:
    """Stub for the Claude Code subprocess driver — auditor (auditor-sonnet) tier path.

    Canonical pattern from tests/graph/test_audit_cascade.py:107.
    """

    script: list[Any] = []
    calls: list[dict] = []

    def __init__(
        self,
        *,
        route: ClaudeCodeRoute,
        per_call_timeout_s: int,
        pricing: dict,
    ) -> None:
        self.route = route

    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict],
        response_format: Any = None,
    ) -> tuple[str, TokenUsage]:
        _StubClaudeCodeAdapter.calls.append({"system": system, "messages": messages})
        if not _StubClaudeCodeAdapter.script:
            raise AssertionError("stub script exhausted (claude)")
        head = _StubClaudeCodeAdapter.script.pop(0)
        if isinstance(head, BaseException):
            raise head
        text, cost = head
        return text, TokenUsage(
            input_tokens=3, output_tokens=2, cost_usd=cost, model=self.route.cli_model_flag
        )


@pytest.fixture(autouse=True)
def _reset_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install stub adapters and reset call counts before each test."""
    _StubLiteLLMAdapter.script = []
    _StubLiteLLMAdapter.calls = []
    _StubClaudeCodeAdapter.script = []
    _StubClaudeCodeAdapter.calls = []
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _StubLiteLLMAdapter)
    monkeypatch.setattr(tiered_node_module, "ClaudeCodeSubprocess", _StubClaudeCodeAdapter)


# ---------------------------------------------------------------------------
# Stub output that satisfies ExplorerReport validation
# ---------------------------------------------------------------------------

_EXPLORER_REPORT_JSON = (
    '{"summary": "Explore findings summary", '
    '"considerations": ["c1", "c2"], '
    '"assumptions": []}'
)
_AUDIT_PASS_JSON = '{"passed": true, "failure_reasons": [], "suggested_approach": null}'

# ---------------------------------------------------------------------------
# Tier registry
# ---------------------------------------------------------------------------


def _tier_registry() -> dict[str, TierConfig]:
    return {
        "planner-explorer": TierConfig(
            name="planner-explorer",
            route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
            max_concurrency=1,
            per_call_timeout_s=30,
        ),
        "auditor-sonnet": TierConfig(
            name="auditor-sonnet",
            route=ClaudeCodeRoute(cli_model_flag="sonnet"),
            max_concurrency=1,
            per_call_timeout_s=30,
        ),
    }


# ---------------------------------------------------------------------------
# Outer state + graph — wraps the cascade sub-graph only
# ---------------------------------------------------------------------------


class _OuterState(TypedDict, total=False):
    run_id: str
    last_exception: Any
    _retry_counts: dict[str, int]
    _non_retryable_failures: int
    cascade_role: str
    cascade_transcript: dict[str, list]
    planner_explorer_audit_primary_output: str
    planner_explorer_audit_primary_parsed: Any
    planner_explorer_audit_primary_output_revision_hint: Any
    planner_explorer_audit_auditor_output: str
    planner_explorer_audit_auditor_output_revision_hint: Any
    planner_explorer_audit_audit_verdict: Any
    planner_explorer_audit_audit_exhausted_response: str


def _build_outer_graph(cascade: CompiledStateGraph) -> Any:
    g: StateGraph = StateGraph(_OuterState)
    g.add_node("cascade", cascade)
    g.add_edge(START, "cascade")
    g.add_edge("cascade", END)
    return g.compile()


def _explorer_stub_prompt(state: Mapping[str, Any]) -> tuple[str | None, list[dict]]:
    return ("sys-explorer", [{"role": "user", "content": "explore the goal"}])


# ---------------------------------------------------------------------------
# Test: planner cascade writes primary + auditor fixtures at expected paths
# ---------------------------------------------------------------------------


async def test_planner_cascade_capture_writes_primary_and_auditor_fixtures(
    tmp_path: Path,
) -> None:
    """Golden: cascade-enabled planner run emits fixtures at planner_explorer_audit_* paths.

    Inline cascade construction — NOT ``run_workflow`` — so the test owns
    the ``CostTracker`` instance and can query ``tracker.by_role(run_id)``.

    Asserts:
    - Exactly one fixture under ``<dataset>/planner/planner_explorer_audit_primary/``
    - Exactly one fixture under ``<dataset>/planner/planner_explorer_audit_auditor/``
    - Both load via ``load_case``; ``workflow_id == "planner"``
    - ``primary_case.node_name == "planner_explorer_audit_primary"``
    - ``auditor_case.node_name == "planner_explorer_audit_auditor"``
    - ``tracker.by_role(run_id)`` contains both ``"author"`` and ``"auditor"`` keys
    """
    _StubLiteLLMAdapter.script = [(_EXPLORER_REPORT_JSON, 0.002)]
    _StubClaudeCodeAdapter.script = [(_AUDIT_PASS_JSON, 0.0)]

    run_id = f"planner-golden-{uuid.uuid4().hex[:12]}"
    tracker = CostTracker()
    cost_callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=None)
    capture = CaptureCallback(
        dataset_name=DATASET,
        workflow_id=WORKFLOW,
        run_id=run_id,
        root=tmp_path,
    )

    cascade = audit_cascade_node(
        primary_tier="planner-explorer",
        primary_prompt_fn=_explorer_stub_prompt,
        primary_output_schema=ExplorerReport,
        auditor_tier="auditor-sonnet",
        policy=_POLICY,
        name=CASCADE_NAME,
    )
    outer = _build_outer_graph(cascade)

    checkpointer = await build_async_checkpointer(tmp_path / f"cp-{run_id}.sqlite")
    storage = await SQLiteStorage.open(tmp_path / f"storage-{run_id}.sqlite")
    await storage.create_run(run_id, WORKFLOW, None)

    cfg = {
        "configurable": {
            "thread_id": run_id,
            "run_id": run_id,
            "tier_registry": _tier_registry(),
            "cost_callback": cost_callback,
            "storage": storage,
            "pricing": {},
            "eval_capture_callback": capture,
        }
    }

    try:
        final = await outer.ainvoke({"run_id": run_id}, cfg)
    finally:
        await checkpointer.conn.close()

    assert "__interrupt__" not in final

    # Check fixture directories.
    primary_dir = tmp_path / WORKFLOW / f"{CASCADE_NAME}_primary"
    auditor_dir = tmp_path / WORKFLOW / f"{CASCADE_NAME}_auditor"

    assert primary_dir.exists(), f"Primary fixture directory missing: {primary_dir}"
    assert auditor_dir.exists(), f"Auditor fixture directory missing: {auditor_dir}"

    primary_fixtures = list(primary_dir.glob("*.json"))
    auditor_fixtures = list(auditor_dir.glob("*.json"))
    assert len(primary_fixtures) == 1, (
        f"Expected 1 primary fixture; got {len(primary_fixtures)}"
    )
    assert len(auditor_fixtures) == 1, (
        f"Expected 1 auditor fixture; got {len(auditor_fixtures)}"
    )

    # Load and assert fixture metadata.
    primary_case = load_case(primary_fixtures[0])
    auditor_case = load_case(auditor_fixtures[0])

    assert primary_case.workflow_id == WORKFLOW
    assert auditor_case.workflow_id == WORKFLOW

    assert primary_case.node_name == f"{CASCADE_NAME}_primary", (
        f"Expected node_name={CASCADE_NAME}_primary, got {primary_case.node_name!r}"
    )
    assert auditor_case.node_name == f"{CASCADE_NAME}_auditor", (
        f"Expected node_name={CASCADE_NAME}_auditor, got {auditor_case.node_name!r}"
    )

    assert primary_case.captured_from_run_id == run_id
    assert auditor_case.captured_from_run_id == run_id

    # Role keys present in cost tracker.
    roles = tracker.by_role(run_id)
    assert "author" in roles, (
        f"Expected 'author' key in tracker.by_role({run_id!r}); got {list(roles)}"
    )
    assert "auditor" in roles, (
        f"Expected 'auditor' key in tracker.by_role({run_id!r}); got {list(roles)}"
    )
