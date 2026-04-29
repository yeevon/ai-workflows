"""Hermetic tests for the cascade author/auditor fixture convention (M12 Task 06).

Pins the directory-split contract: a cascade-enabled invocation with
``CaptureCallback`` wired emits exactly two fixtures per cascade pair —
one under ``<dataset>/<workflow>/<cascade_name>_primary/`` and one under
``<cascade_name>_auditor/``.  No fixture is written for the verdict node
(pure parse, no LLM call).

These tests use the inline cascade-construction pattern (NOT ``run_workflow``)
so the test owns the ``CostTracker`` instance and can directly query
``tracker.by_role(run_id)``.

Relationship to other modules
------------------------------
* :mod:`ai_workflows.graph.audit_cascade` — the cascade primitive under test.
* :mod:`ai_workflows.evals.capture_callback` — ``CaptureCallback`` wired via
  ``config["configurable"]["eval_capture_callback"]``.
* :mod:`ai_workflows.evals.storage` — ``load_case`` for independent-loadability
  assertion (AC item 4).
* ``tests/graph/test_audit_cascade.py`` — source of the stub-adapter pattern;
  ``_StubClaudeCodeAdapter`` at line 107 is the canonical reuse target.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypedDict

import pytest
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

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

# ---------------------------------------------------------------------------
# Deterministic cascade name — keeps expected filesystem paths predictable.
# ---------------------------------------------------------------------------

CASCADE_NAME = "test_cascade"
# Derived node names:
#   primary: "test_cascade_primary"
#   auditor: "test_cascade_auditor"
#   verdict: "test_cascade_verdict" (no LLM call — no fixture)

DATASET = "test-dataset"
WORKFLOW = "cascade_test"

_POLICY = RetryPolicy(max_transient_attempts=3, max_semantic_attempts=3)

# ---------------------------------------------------------------------------
# Shared schemas
# ---------------------------------------------------------------------------


class _PrimaryOutput(BaseModel):
    """Minimal schema the primary validator parses against."""

    content: str


# ---------------------------------------------------------------------------
# Stub adapters (reused from tests/graph/test_audit_cascade.py:107 pattern)
# ---------------------------------------------------------------------------


class _StubLiteLLMAdapter:
    """Scriptable LiteLLMAdapter stub (primary-tier path)."""

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
    """Stub for the Claude Code subprocess driver — auditor-tier path.

    Independent script from ``_StubLiteLLMAdapter`` (canonical pattern from
    ``tests/graph/test_audit_cascade.py:107``).
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
# Shared JSON fixtures
# ---------------------------------------------------------------------------

_PRIMARY_JSON = '{"content": "hello"}'
_AUDIT_PASS_JSON = '{"passed": true, "failure_reasons": [], "suggested_approach": null}'

# ---------------------------------------------------------------------------
# Tier registry helper
# ---------------------------------------------------------------------------


def _tier_registry() -> dict[str, TierConfig]:
    return {
        "primary-litellm": TierConfig(
            name="primary-litellm",
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
# Outer state + graph helpers
# ---------------------------------------------------------------------------


class _OuterState(TypedDict, total=False):
    run_id: str
    last_exception: Any
    _retry_counts: dict[str, int]
    _non_retryable_failures: int
    cascade_role: str
    cascade_transcript: dict[str, list]
    test_cascade_primary_output: str
    test_cascade_primary_parsed: Any
    test_cascade_primary_output_revision_hint: Any
    test_cascade_auditor_output: str
    test_cascade_auditor_output_revision_hint: Any
    test_cascade_audit_verdict: Any
    test_cascade_audit_exhausted_response: str


def _build_outer_graph(cascade: CompiledStateGraph) -> Any:
    g: StateGraph = StateGraph(_OuterState)
    g.add_node("cascade", cascade)
    g.add_edge(START, "cascade")
    g.add_edge("cascade", END)
    return g.compile()


def _primary_prompt_fn(state: Mapping[str, Any]) -> tuple[str | None, list[dict]]:
    return ("sys-primary", [{"role": "user", "content": "produce output"}])


# ---------------------------------------------------------------------------
# Per-test shared setup helper (inline cascade pattern)
# ---------------------------------------------------------------------------


async def _run_cascade(
    *,
    tmp_path: Path,
    run_id: str,
    tracker: CostTracker,
    capture: CaptureCallback,
) -> dict[str, Any]:
    """Drive a single happy-path cascade invocation with capture wired.

    Returns the final outer-graph state dict.
    """
    _StubLiteLLMAdapter.script = [(_PRIMARY_JSON, 0.001)]
    _StubClaudeCodeAdapter.script = [(_AUDIT_PASS_JSON, 0.0)]

    checkpointer = await build_async_checkpointer(tmp_path / f"cp-{run_id}.sqlite")
    storage = await SQLiteStorage.open(tmp_path / f"storage-{run_id}.sqlite")
    await storage.create_run(run_id, WORKFLOW, None)

    cost_callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=None)

    cascade = audit_cascade_node(
        primary_tier="primary-litellm",
        primary_prompt_fn=_primary_prompt_fn,
        primary_output_schema=_PrimaryOutput,
        auditor_tier="auditor-sonnet",
        policy=_POLICY,
        name=CASCADE_NAME,
    )
    outer = _build_outer_graph(cascade)

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

    return final


# ---------------------------------------------------------------------------
# Test 1: primary + auditor directories emitted; no verdict directory
# ---------------------------------------------------------------------------


async def test_cascade_run_emits_separate_primary_and_auditor_fixtures(
    tmp_path: Path,
) -> None:
    """AC-3 / hermetic smoke: cascade emits one fixture per role under separate dirs.

    Asserts:
    - Exactly one *.json file under ``<dataset>/<workflow>/<cascade_name>_primary/``
    - Exactly one *.json file under ``<dataset>/<workflow>/<cascade_name>_auditor/``
    - No fixture under ``<cascade_name>_verdict/`` (verdict node has no LLM call)
    - Fixture filenames match the ``<case_id>.json`` pattern (not prefixed with role)

    Note: ``root=tmp_path`` bypasses the dataset-name prefix, so the on-disk path is
    ``<root>/<workflow>/<node>/`` not ``<root>/<dataset>/<workflow>/<node>/``.
    """
    run_id = f"test-{uuid.uuid4().hex[:12]}"
    tracker = CostTracker()
    capture = CaptureCallback(
        dataset_name=DATASET,
        workflow_id=WORKFLOW,
        run_id=run_id,
        root=tmp_path,
    )

    final = await _run_cascade(tmp_path=tmp_path, run_id=run_id, tracker=tracker, capture=capture)

    assert "__interrupt__" not in final

    primary_dir = tmp_path / WORKFLOW / f"{CASCADE_NAME}_primary"
    auditor_dir = tmp_path / WORKFLOW / f"{CASCADE_NAME}_auditor"
    verdict_dir = tmp_path / WORKFLOW / f"{CASCADE_NAME}_verdict"

    assert primary_dir.exists(), f"Primary fixture directory missing: {primary_dir}"
    assert auditor_dir.exists(), f"Auditor fixture directory missing: {auditor_dir}"

    primary_fixtures = list(primary_dir.glob("*.json"))
    auditor_fixtures = list(auditor_dir.glob("*.json"))

    assert len(primary_fixtures) == 1, (
        f"Expected exactly 1 primary fixture, got {len(primary_fixtures)}: {primary_fixtures}"
    )
    assert len(auditor_fixtures) == 1, (
        f"Expected exactly 1 auditor fixture, got {len(auditor_fixtures)}: {auditor_fixtures}"
    )

    # Verdict node must NOT write a fixture (pure parse step, no LLM call).
    assert not verdict_dir.exists(), (
        f"Verdict directory must not exist (no LLM call in verdict node): {verdict_dir}"
    )

    # Filenames follow the <case_id>.json pattern (no role prefix).
    assert primary_fixtures[0].suffix == ".json"
    assert auditor_fixtures[0].suffix == ".json"


# ---------------------------------------------------------------------------
# Test 2: primary fixture is paired with role="author" in cost tracker
# ---------------------------------------------------------------------------


async def test_primary_fixture_role_tag_is_author(tmp_path: Path) -> None:
    """AC-2: primary fixture's captured_from_run_id matches run_id; tracker has "author" key.

    Cross-references the fixture path with the ``CostTracker`` ledger to pin
    that the same run_id binds both surfaces.

    Note: ``TokenUsage.role`` lives on the ledger entry, NOT in the fixture file;
    the fixture file carries ``captured_from_run_id`` for provenance.

    Note: ``root=tmp_path`` bypasses the dataset-name prefix, so the on-disk path is
    ``<root>/<workflow>/<node>/`` not ``<root>/<dataset>/<workflow>/<node>/``.
    """
    run_id = f"test-{uuid.uuid4().hex[:12]}"
    tracker = CostTracker()
    capture = CaptureCallback(
        dataset_name=DATASET,
        workflow_id=WORKFLOW,
        run_id=run_id,
        root=tmp_path,
    )

    final = await _run_cascade(tmp_path=tmp_path, run_id=run_id, tracker=tracker, capture=capture)
    assert "__interrupt__" not in final

    primary_dir = tmp_path / WORKFLOW / f"{CASCADE_NAME}_primary"
    primary_fixtures = list(primary_dir.glob("*.json"))
    assert len(primary_fixtures) == 1

    # Load the primary fixture and verify provenance.
    case = load_case(primary_fixtures[0])
    assert case.captured_from_run_id == run_id, (
        f"Expected captured_from_run_id={run_id!r}, got {case.captured_from_run_id!r}"
    )

    # Check cost tracker ledger for "author" role.
    roles = tracker.by_role(run_id)
    assert "author" in roles, (
        f"Expected 'author' key in tracker.by_role({run_id!r}), got keys: {list(roles)}"
    )
    assert roles["author"] >= 0.0


# ---------------------------------------------------------------------------
# Test 3: auditor fixture is paired with role="auditor" in cost tracker
# ---------------------------------------------------------------------------


async def test_auditor_fixture_role_tag_is_auditor(tmp_path: Path) -> None:
    """AC-3: auditor fixture's captured_from_run_id matches run_id; tracker has "auditor" key.

    Symmetric to test 2 for the auditor side.

    Note: ``root=tmp_path`` bypasses the dataset-name prefix, so the on-disk path is
    ``<root>/<workflow>/<node>/`` not ``<root>/<dataset>/<workflow>/<node>/``.
    """
    run_id = f"test-{uuid.uuid4().hex[:12]}"
    tracker = CostTracker()
    capture = CaptureCallback(
        dataset_name=DATASET,
        workflow_id=WORKFLOW,
        run_id=run_id,
        root=tmp_path,
    )

    final = await _run_cascade(tmp_path=tmp_path, run_id=run_id, tracker=tracker, capture=capture)
    assert "__interrupt__" not in final

    auditor_dir = tmp_path / WORKFLOW / f"{CASCADE_NAME}_auditor"
    auditor_fixtures = list(auditor_dir.glob("*.json"))
    assert len(auditor_fixtures) == 1

    # Load the auditor fixture and verify provenance.
    case = load_case(auditor_fixtures[0])
    assert case.captured_from_run_id == run_id, (
        f"Expected captured_from_run_id={run_id!r}, got {case.captured_from_run_id!r}"
    )

    # Check cost tracker ledger for "auditor" role.
    roles = tracker.by_role(run_id)
    assert "auditor" in roles, (
        f"Expected 'auditor' key in tracker.by_role({run_id!r}), got keys: {list(roles)}"
    )
    assert roles["auditor"] >= 0.0


# ---------------------------------------------------------------------------
# Test 4: both fixtures load independently as EvalCase instances
# ---------------------------------------------------------------------------


async def test_captured_fixtures_load_independently_as_eval_cases(tmp_path: Path) -> None:
    """AC-4: both fixtures load via load_case and surface expected metadata triples.

    Pins the independent-loadability contract (README Exit-criteria #9).
    Does NOT invoke EvalRunner — cascade replay through
    ``EvalRunner._resolve_node_scope`` is known-broken (validator-pair
    lookup mismatch per KDR-004 carve-out) and is forward-deferred.

    Asserts per fixture:
    - ``node_name`` matches the expected cascade-prefixed name
    - ``workflow_id == WORKFLOW``
    - ``captured_from_run_id == run_id``

    Note: ``root=tmp_path`` bypasses the dataset-name prefix, so the on-disk path is
    ``<root>/<workflow>/<node>/`` not ``<root>/<dataset>/<workflow>/<node>/``.
    """
    run_id = f"test-{uuid.uuid4().hex[:12]}"
    tracker = CostTracker()
    capture = CaptureCallback(
        dataset_name=DATASET,
        workflow_id=WORKFLOW,
        run_id=run_id,
        root=tmp_path,
    )

    final = await _run_cascade(tmp_path=tmp_path, run_id=run_id, tracker=tracker, capture=capture)
    assert "__interrupt__" not in final

    primary_dir = tmp_path / WORKFLOW / f"{CASCADE_NAME}_primary"
    auditor_dir = tmp_path / WORKFLOW / f"{CASCADE_NAME}_auditor"

    primary_fixtures = list(primary_dir.glob("*.json"))
    auditor_fixtures = list(auditor_dir.glob("*.json"))
    assert len(primary_fixtures) == 1
    assert len(auditor_fixtures) == 1

    primary_case = load_case(primary_fixtures[0])
    auditor_case = load_case(auditor_fixtures[0])

    # node_name matches cascade-prefixed pattern.
    assert primary_case.node_name == f"{CASCADE_NAME}_primary", (
        f"Expected node_name={CASCADE_NAME}_primary, got {primary_case.node_name!r}"
    )
    assert auditor_case.node_name == f"{CASCADE_NAME}_auditor", (
        f"Expected node_name={CASCADE_NAME}_auditor, got {auditor_case.node_name!r}"
    )

    # workflow_id is set on both.
    assert primary_case.workflow_id == WORKFLOW
    assert auditor_case.workflow_id == WORKFLOW

    # captured_from_run_id binds both to the same run.
    assert primary_case.captured_from_run_id == run_id
    assert auditor_case.captured_from_run_id == run_id


# ---------------------------------------------------------------------------
# Test 5: root=None path — dataset_name segment is appended to AIW_EVALS_ROOT
# ---------------------------------------------------------------------------


def test_capture_callback_root_none_uses_dataset_segment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With root=None, CaptureCallback appends dataset_name to AIW_EVALS_ROOT.

    Exercises the production path (``CaptureCallback.__init__:107-109``) that
    appends ``dataset_name`` to ``default_evals_root()`` when ``root`` is not
    supplied.  All four tests above pass ``root=tmp_path`` which bypasses this
    branch — this test closes the coverage gap against the core convention
    documented in ``evals/README.md``:

        evals/<dataset>/<workflow>/<node>/<case_id>.json

    ``AIW_EVALS_ROOT`` is monkeypatched to ``tmp_path`` so fixtures land
    under a controlled temporary directory rather than the real ``evals/``
    tree.
    """
    monkeypatch.setenv("AIW_EVALS_ROOT", str(tmp_path))
    dataset = "my-dataset"
    workflow = "cascade_test"
    node = "test_cascade_primary"
    run_id = f"test-{uuid.uuid4().hex[:12]}"
    capture = CaptureCallback(dataset_name=dataset, workflow_id=workflow, run_id=run_id)
    # Drive on_node_complete with a minimal stub — no LLM call needed.
    result_path = capture.on_node_complete(
        run_id=run_id,
        node_name=node,
        inputs={"prompt": "hello"},
        raw_output="world",
        output_schema=None,
    )
    assert result_path is not None, "on_node_complete should return a path"
    # Fixture must land at tmp_path / dataset / workflow / node / <case_id>.json
    assert result_path.is_relative_to(tmp_path / dataset / workflow / node), (
        f"Expected fixture under {tmp_path / dataset / workflow / node}, got {result_path}"
    )
    case = load_case(result_path)
    assert case.node_name == node
    assert case.workflow_id == workflow
    assert case.captured_from_run_id == run_id
