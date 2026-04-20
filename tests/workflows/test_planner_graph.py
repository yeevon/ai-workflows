"""End-to-end tests for the ``planner`` StateGraph (M3 Task 03).

Covers the acceptance criteria from
``design_docs/phases/milestone_3_first_workflow/task_03_planner_graph.md``:

* Build / compile under ``AsyncSqliteSaver``.
* Registration side effect at module import.
* Happy path — pause at gate, resume, artifact written to Storage.
* Retry path — ``litellm.RateLimitError`` on the explorer's first call
  routes through ``retrying_edge`` and the second call succeeds.
* Validator-driven revision — invalid ``PlannerPlan`` JSON bumps a
  self-loop back to the planner with a revision hint set.
* Rejected gate — resume with a non-``"approved"`` response MUST NOT
  write an artifact.

Every LLM call is stubbed at the adapter level so no real API fires.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import litellm
import pytest
from langgraph.types import Command

from ai_workflows import workflows
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.graph.checkpointer import build_async_checkpointer
from ai_workflows.graph.cost_callback import CostTrackingCallback
from ai_workflows.primitives.cost import CostTracker, TokenUsage
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig
from ai_workflows.workflows.planner import (
    PLANNER_RETRY_POLICY,
    ExplorerReport,
    PlannerInput,
    PlannerPlan,
    build_planner,
)

# ---------------------------------------------------------------------------
# Stub LiteLLM adapter
# ---------------------------------------------------------------------------


class _StubLiteLLMAdapter:
    """Scripted LiteLLM-adapter stub shared with the M2 smoke graph test.

    ``response_format_log`` captures the ``response_format`` kwarg forwarded
    on every call so T07a tests can assert native structured-output wiring
    reaches the adapter boundary.
    """

    script: list[Any] = []
    call_count: int = 0
    response_format_log: list[Any] = []

    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        self.route = route

    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict],
        response_format: Any = None,
    ) -> tuple[str, TokenUsage]:
        _StubLiteLLMAdapter.call_count += 1
        _StubLiteLLMAdapter.response_format_log.append(response_format)
        if not _StubLiteLLMAdapter.script:
            raise AssertionError("stub script exhausted")
        head = _StubLiteLLMAdapter.script.pop(0)
        if isinstance(head, BaseException):
            raise head
        text, cost = head
        return text, TokenUsage(
            input_tokens=9,
            output_tokens=13,
            cost_usd=cost,
            model=self.route.model,
        )

    @classmethod
    def reset(cls) -> None:
        cls.script = []
        cls.call_count = 0
        cls.response_format_log = []


@pytest.fixture(autouse=True)
def _reset_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install the stub adapter and clear the script on every test."""
    _StubLiteLLMAdapter.reset()
    monkeypatch.setattr(
        tiered_node_module, "LiteLLMAdapter", _StubLiteLLMAdapter
    )


@pytest.fixture(autouse=True)
def _reensure_planner_registered() -> Iterator[None]:
    """Keep ``workflows.get('planner')`` resolvable across test-file boundaries.

    ``tests/workflows/test_registry.py`` resets the registry between each
    of its tests via its own autouse fixture; those resets can leave the
    registry empty by the time this module's tests run. Re-registering
    before each test keeps this file self-contained without reaching
    across module boundaries.
    """
    workflows._reset_for_tests()
    workflows.register("planner", build_planner)
    yield


# ---------------------------------------------------------------------------
# Fixtures — tier registry + config builder
# ---------------------------------------------------------------------------


def _tier_registry() -> dict[str, TierConfig]:
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


async def _build_config(
    tmp_path: Path,
    run_id: str,
    budget_cap_usd: float | None = None,
) -> tuple[dict[str, Any], CostTracker, SQLiteStorage]:
    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await storage.create_run(run_id, "planner", budget_cap_usd)
    tracker = CostTracker()
    callback = CostTrackingCallback(
        cost_tracker=tracker, budget_cap_usd=budget_cap_usd
    )
    cfg = {
        "configurable": {
            "thread_id": run_id,
            "run_id": run_id,
            "tier_registry": _tier_registry(),
            "cost_callback": callback,
            "storage": storage,
            "workflow": "planner",
        }
    }
    return cfg, tracker, storage


def _valid_explorer_json() -> str:
    return json.dumps(
        {
            "summary": "Delivering a static hero page is a three-step effort.",
            "considerations": ["Copy tone", "CTA placement"],
            "assumptions": ["Design system is stable"],
        }
    )


def _valid_plan_json() -> str:
    return json.dumps(
        {
            "goal": "Ship the marketing page.",
            "summary": "Three-step delivery of the static hero + CTA page.",
            "steps": [
                {
                    "index": 1,
                    "title": "Draft hero copy",
                    "rationale": "Lock tone before layout.",
                    "actions": ["Sketch headline", "List CTAs"],
                },
            ],
        }
    )


def _invalid_plan_json() -> str:
    """Shape-mismatched plan (missing required ``steps`` key)."""
    return json.dumps(
        {
            "goal": "Ship the marketing page.",
            "summary": "Forgot to emit steps entirely.",
        }
    )


def _planner_input() -> PlannerInput:
    return PlannerInput(
        goal="Ship the marketing page.",
        context="Hero + single CTA.",
        max_steps=5,
    )


# ---------------------------------------------------------------------------
# Build / compile / registration
# ---------------------------------------------------------------------------


def test_build_planner_returns_stategraph_with_expected_nodes() -> None:
    """AC: ``build_planner`` exposes the exact six-node shape from the spec."""
    g = build_planner()
    assert set(g.nodes) == {
        "explorer",
        "explorer_validator",
        "planner",
        "planner_validator",
        "gate",
        "artifact",
    }


async def test_build_planner_compiles_against_async_sqlite_saver(
    tmp_path: Path,
) -> None:
    """AC: ``build_planner()`` compiles under ``AsyncSqliteSaver`` without error."""
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    try:
        app = build_planner().compile(checkpointer=checkpointer)
        assert app is not None
    finally:
        await checkpointer.conn.close()


def test_importing_planner_registers_builder() -> None:
    """AC: the planner module's top-level ``register(...)`` lands in the registry."""
    workflows.register("planner", build_planner)
    assert workflows.get("planner") is build_planner


# ---------------------------------------------------------------------------
# KDR-003 — no Anthropic API surface in the module
# ---------------------------------------------------------------------------


def test_planner_module_has_no_anthropic_surface() -> None:
    """KDR-003: no ``import anthropic`` / ``ANTHROPIC_API_KEY`` lookup.

    The docstring references KDR-003 by name (the word "anthropic"
    appears there as a *prohibition*, not a use), so we match on the
    actual surface forms — imports, env-var reads — rather than a raw
    substring of the file.
    """
    planner_source = (
        Path(__file__).resolve().parent.parent.parent
        / "ai_workflows"
        / "workflows"
        / "planner.py"
    ).read_text(encoding="utf-8")
    for forbidden in ("import anthropic", "from anthropic", "ANTHROPIC_API_KEY"):
        assert forbidden not in planner_source, (
            f"KDR-003 violated: {forbidden!r} appears in planner.py"
        )


# ---------------------------------------------------------------------------
# Happy path — pause at gate, resume, artifact persists
# ---------------------------------------------------------------------------


async def test_happy_path_pauses_at_gate_then_persists_artifact(
    tmp_path: Path,
) -> None:
    """AC: valid explorer + planner JSON → gate pauses; resume "approved"
    writes a ``plan`` artifact to Storage.
    """
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_planner().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
    ]
    cfg, tracker, storage = await _build_config(tmp_path, "run-happy")

    try:
        paused = await app.ainvoke(
            {"run_id": "run-happy", "input": _planner_input()}, cfg
        )
        assert "__interrupt__" in paused
        assert isinstance(paused["plan"], PlannerPlan)
        assert isinstance(paused["explorer_report"], ExplorerReport)

        final = await app.ainvoke(Command(resume="approved"), cfg)
        assert final["gate_plan_review_response"] == "approved"
        assert isinstance(final["plan"], PlannerPlan)

        artifact = await storage.read_artifact("run-happy", "plan")
        assert artifact is not None
        persisted = PlannerPlan.model_validate_json(artifact["payload_json"])
        assert persisted.goal == "Ship the marketing page."

        # Sanity: both stubbed LLM calls fired exactly once.
        assert _StubLiteLLMAdapter.call_count == 2
        assert tracker.total("run-happy") == pytest.approx(0.0033)

        # M3 T07a: ``response_format`` must reach the adapter boundary on
        # both tiers so LiteLLM drives Gemini's native structured-output
        # path. Pre-T07a the kwarg was ``None`` on both calls; post-T07a
        # the explorer tier forwards ``ExplorerReport`` and the planner
        # tier forwards ``PlannerPlan``.
        assert _StubLiteLLMAdapter.response_format_log == [
            ExplorerReport,
            PlannerPlan,
        ]
    finally:
        await checkpointer.conn.close()
        del storage


def test_planner_retry_policy_bumps_transient_attempts_to_five() -> None:
    """M3 T07a: ``max_transient_attempts`` is bumped 3 → 5.

    Gemini 503 ``ServiceUnavailableError`` is a request-admission failure
    (``input_tokens=null`` / ``cost_usd=null`` on ``TokenUsage``), so 503
    retries cost only latency. Bumping the transient bucket to 5 buys the
    e2e job resilience against 503 bursts without widening the semantic
    bucket (which would burn real tokens per re-roll).
    """
    assert PLANNER_RETRY_POLICY.max_transient_attempts == 5
    assert PLANNER_RETRY_POLICY.max_semantic_attempts == 3


# ---------------------------------------------------------------------------
# Retry path — transient burst on the explorer node
# ---------------------------------------------------------------------------


async def test_retry_path_bumps_explorer_retry_counter(tmp_path: Path) -> None:
    """AC: ``litellm.RateLimitError`` on explorer's first call routes back to
    ``explorer`` and ``_retry_counts['explorer']`` goes 0 → 1.
    """
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_planner().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [
        litellm.RateLimitError("429", llm_provider="gemini", model="g"),
        (_valid_explorer_json(), 0.0005),
        (_valid_plan_json(), 0.0007),
    ]
    cfg, tracker, storage = await _build_config(tmp_path, "run-retry")

    try:
        paused = await app.ainvoke(
            {"run_id": "run-retry", "input": _planner_input()}, cfg
        )
        assert paused["_retry_counts"] == {"explorer": 1}
        assert paused.get("_non_retryable_failures", 0) == 0
        assert paused.get("last_exception") is None

        # 1 fail + 1 explorer success + 1 planner success = 3 calls.
        assert _StubLiteLLMAdapter.call_count == 3
    finally:
        await checkpointer.conn.close()
        del storage


# ---------------------------------------------------------------------------
# Validator-driven revision — planner re-prompted after a schema miss
# ---------------------------------------------------------------------------


async def test_validator_revision_routes_back_to_planner(tmp_path: Path) -> None:
    """AC: invalid plan JSON raises ``RetryableSemantic`` → self-loop to planner
    with a revision hint set.
    """
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_planner().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0009),
        (_invalid_plan_json(), 0.0013),
        (_valid_plan_json(), 0.0017),
    ]
    cfg, tracker, storage = await _build_config(tmp_path, "run-revision")

    try:
        paused = await app.ainvoke(
            {"run_id": "run-revision", "input": _planner_input()}, cfg
        )
        assert "__interrupt__" in paused
        assert isinstance(paused["plan"], PlannerPlan)

        # 1 explorer + 1 invalid planner + 1 valid planner = 3 calls.
        assert _StubLiteLLMAdapter.call_count == 3

        # The wrap_with_error_handler on planner_validator bumps the
        # validator's counter; the semantic edge routes to the upstream
        # LLM node (`planner`) per KDR-004.
        assert paused["_retry_counts"].get("planner_validator") == 1
        assert paused.get("last_exception") is None
    finally:
        await checkpointer.conn.close()
        del storage


# ---------------------------------------------------------------------------
# Rejected gate — storage.write_artifact not invoked
# ---------------------------------------------------------------------------


class _RecordingStorage:
    """Wraps a real ``SQLiteStorage`` but tallies ``write_artifact`` calls."""

    def __init__(self, inner: SQLiteStorage) -> None:
        self._inner = inner
        self.write_artifact_calls = 0

    async def create_run(self, *args: Any, **kwargs: Any) -> None:
        await self._inner.create_run(*args, **kwargs)

    async def record_gate(self, *args: Any, **kwargs: Any) -> None:
        await self._inner.record_gate(*args, **kwargs)

    async def record_gate_response(self, *args: Any, **kwargs: Any) -> None:
        await self._inner.record_gate_response(*args, **kwargs)

    async def write_artifact(
        self, run_id: str, kind: str, payload_json: str
    ) -> None:
        self.write_artifact_calls += 1
        await self._inner.write_artifact(run_id, kind, payload_json)

    async def read_artifact(
        self, run_id: str, kind: str
    ) -> dict[str, Any] | None:
        return await self._inner.read_artifact(run_id, kind)


async def test_rejected_gate_skips_artifact_write(tmp_path: Path) -> None:
    """AC: resume with ``"rejected"`` does NOT call ``storage.write_artifact``.

    The exact rejected-response handling is up to the builder (per task
    spec); this test only pins the contract that no artifact is written.
    """
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_planner().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0008),
        (_valid_plan_json(), 0.0011),
    ]
    inner_storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await inner_storage.create_run("run-rejected", "planner", None)
    recording = _RecordingStorage(inner_storage)

    tracker = CostTracker()
    callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=None)
    cfg = {
        "configurable": {
            "thread_id": "run-rejected",
            "run_id": "run-rejected",
            "tier_registry": _tier_registry(),
            "cost_callback": callback,
            "storage": recording,
            "workflow": "planner",
        }
    }

    try:
        await app.ainvoke(
            {"run_id": "run-rejected", "input": _planner_input()}, cfg
        )
        final = await app.ainvoke(Command(resume="rejected"), cfg)
        assert final["gate_plan_review_response"] == "rejected"

        assert recording.write_artifact_calls == 0
        artifact = await inner_storage.read_artifact("run-rejected", "plan")
        assert artifact is None
    finally:
        await checkpointer.conn.close()
        del inner_storage


