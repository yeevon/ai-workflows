"""Tests for the slice_refactor workflow's Ollama-outage fallback edge (M8 T04).

Covers the three workflow-layer ACs from
[design_docs/phases/milestone_8_ollama/task_04_tiered_node_integration.md](
../../design_docs/phases/milestone_8_ollama/task_04_tiered_node_integration.md):

* ``test_single_gate_for_all_branches`` — three parallel slice workers
  all observe the breaker OPEN; the parent graph fires exactly one
  ``ollama_fallback`` gate per run (not one per branch). Asserted via
  the single ``__interrupt__`` marker and
  ``state["_ollama_fallback_count"] == 1`` (the stamp node is the sole
  gate-record writer and increments the counter once per gate firing).
* ``test_fallback_applies_to_subsequent_branches`` — resume with
  ``FALLBACK``. The re-fanned branches route through
  :data:`SLICE_REFACTOR_OLLAMA_FALLBACK.fallback_tier` (the override's
  replacement tier is a :class:`ClaudeCodeRoute` — non-Ollama,
  non-breakered), so the worker calls land on the Claude Code
  subprocess stub rather than the LiteLLM adapter. Pins behaviour for
  "two branches still pending run against the replacement tier"; under
  the shared-breaker pre-trip all three branches tripped on the first
  pass, so all three re-fire post-resume against the replacement.
* ``test_abort_cancels_pending_branches`` — resume with ``ABORT``. The
  terminal ``slice_refactor_ollama_abort`` node writes the metadata
  artefact and stamps ``ollama_fallback_aborted=True``; no
  ``slice_result:<id>`` rows land.

Both the LiteLLM adapter and the Claude Code subprocess are stubbed —
no real provider calls fire.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from langgraph.types import Command

from ai_workflows import workflows
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.graph.checkpointer import build_async_checkpointer
from ai_workflows.graph.cost_callback import CostTrackingCallback
from ai_workflows.primitives.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
)
from ai_workflows.primitives.cost import CostTracker, TokenUsage
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.tiers import (
    ClaudeCodeRoute,
    LiteLLMRoute,
    ModelPricing,
    TierConfig,
)
from ai_workflows.workflows.planner import PlannerInput, build_planner
from ai_workflows.workflows.slice_refactor import (
    SLICE_REFACTOR_OLLAMA_FALLBACK,
    SLICE_RESULT_ARTIFACT_KIND,
    build_slice_refactor,
)

# ---------------------------------------------------------------------------
# Adapter stubs — LiteLLM routes planner sub-graph + slice-worker;
# ClaudeCodeSubprocess routes the fallback replacement tier.
# ---------------------------------------------------------------------------


class _StubLiteLLMAdapter:
    """Scripted LiteLLM stub for the planner sub-graph (explorer + synth).

    Pre-tripping the breaker means the slice-worker layer never reaches
    this adapter — the breaker short-circuits before
    :meth:`complete` is called. The adapter's script therefore only
    needs to cover the two planner sub-graph calls that land before
    the fan-out.
    """

    script: list[Any] = []
    call_count: int = 0
    routed_models: list[str] = []

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
        _StubLiteLLMAdapter.routed_models.append(self.route.model)
        if not _StubLiteLLMAdapter.script:
            raise AssertionError("litellm stub script exhausted")
        head = _StubLiteLLMAdapter.script.pop(0)
        if isinstance(head, BaseException):
            raise head
        text, cost = head
        return text, TokenUsage(
            input_tokens=7,
            output_tokens=11,
            cost_usd=cost,
            model=self.route.model,
        )

    @classmethod
    def reset(cls) -> None:
        cls.script = []
        cls.call_count = 0
        cls.routed_models = []


class _StubClaudeCodeSubprocess:
    """Claude Code subprocess stub used as the fallback replacement route.

    Distinct from the LiteLLM adapter because :class:`ClaudeCodeRoute`
    dispatches through a different code path in
    :class:`TieredNode`; the fallback stamps the override so
    ``slice-worker`` resolves to ``planner-synth`` (ClaudeCodeRoute) —
    worker calls on the FALLBACK path land here instead.
    """

    script: list[tuple[str, TokenUsage]] = []
    call_count: int = 0
    routed_flags: list[str] = []
    call_slice_ids: list[str] = []

    def __init__(
        self,
        *,
        route: ClaudeCodeRoute,
        per_call_timeout_s: int,
        pricing: dict[str, ModelPricing],
    ) -> None:
        self.route = route
        self.per_call_timeout_s = per_call_timeout_s
        self.pricing = pricing

    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict],
        response_format: Any = None,
    ) -> tuple[str, TokenUsage]:
        _StubClaudeCodeSubprocess.call_count += 1
        _StubClaudeCodeSubprocess.routed_flags.append(self.route.cli_model_flag)
        content = messages[0].get("content") or ""
        if "Slice id:" in content:
            first_line = content.splitlines()[0]
            _, _, sid = first_line.partition("Slice id: ")
            _StubClaudeCodeSubprocess.call_slice_ids.append(sid.strip())
        if not _StubClaudeCodeSubprocess.script:
            raise AssertionError("claude_code stub script exhausted")
        return _StubClaudeCodeSubprocess.script.pop(0)

    @classmethod
    def reset(cls) -> None:
        cls.script = []
        cls.call_count = 0
        cls.routed_flags = []
        cls.call_slice_ids = []


@pytest.fixture(autouse=True)
def _reset_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    _StubLiteLLMAdapter.reset()
    _StubClaudeCodeSubprocess.reset()
    monkeypatch.setattr(
        tiered_node_module, "LiteLLMAdapter", _StubLiteLLMAdapter
    )
    monkeypatch.setattr(
        tiered_node_module, "ClaudeCodeSubprocess", _StubClaudeCodeSubprocess
    )


@pytest.fixture(autouse=True)
def _reensure_workflows_registered() -> Iterator[None]:
    workflows._reset_for_tests()
    workflows.register("planner", build_planner)
    workflows.register("slice_refactor", build_slice_refactor)
    yield


# ---------------------------------------------------------------------------
# Helpers — tier registry, breaker, config builder, fixture payloads
# ---------------------------------------------------------------------------


def _tier_registry() -> dict[str, TierConfig]:
    """Production-shape registry: Ollama for worker tiers, Claude for synth.

    ``planner-explorer`` + ``slice-worker`` are both Ollama-backed so
    the breaker is consulted on those paths. ``planner-synth`` is the
    fallback target (non-Ollama, non-breakered). Mirrors the shape
    :func:`slice_refactor_tier_registry` produces in production.
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
        "slice-worker": TierConfig(
            name="slice-worker",
            route=LiteLLMRoute(
                model="ollama/qwen2.5-coder:32b",
                api_base="http://localhost:11434",
            ),
            max_concurrency=4,
            per_call_timeout_s=180,
        ),
    }


def _build_breaker(clock: dict[str, float]) -> CircuitBreaker:
    """Breaker pre-trippable to OPEN with a controllable clock.

    ``trip_threshold=1`` — a single :meth:`record_failure` flips OPEN.
    ``cooldown_s=1.0`` + an injected clock lets the test move past the
    cooldown between the pause and the resume without a real
    ``time.sleep``.
    """
    return CircuitBreaker(
        tier="slice-worker",
        trip_threshold=1,
        cooldown_s=1.0,
        time_source=lambda: clock["t"],
    )


async def _build_config(
    *,
    tmp_path: Path,
    run_id: str,
    breaker: CircuitBreaker,
) -> tuple[dict[str, Any], CostTracker, SQLiteStorage]:
    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await storage.create_run(run_id, "slice_refactor", None)
    tracker = CostTracker()
    callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=None)
    cfg = {
        "configurable": {
            "thread_id": run_id,
            "run_id": run_id,
            "tier_registry": _tier_registry(),
            "cost_callback": callback,
            "storage": storage,
            "workflow": "slice_refactor",
            "ollama_circuit_breakers": {"slice-worker": breaker},
            "pricing": {},
        }
    }
    return cfg, tracker, storage


def _explorer_report_json() -> str:
    return (
        '{"summary": "Three parallel slices.", '
        '"considerations": ["Independent modules"], '
        '"assumptions": ["Green CI"]}'
    )


def _three_step_plan_json() -> str:
    return (
        '{"goal": "Refactor monolith into three slices.", '
        '"summary": "Three independent slices.", '
        '"steps": ['
        '{"index": 1, "title": "Slice 1", '
        '"rationale": "r1", "actions": ["a1"]},'
        '{"index": 2, "title": "Slice 2", '
        '"rationale": "r2", "actions": ["a2"]},'
        '{"index": 3, "title": "Slice 3", '
        '"rationale": "r3", "actions": ["a3"]}'
        ']}'
    )


def _slice_result_json(slice_id: str) -> str:
    return (
        f'{{"slice_id": "{slice_id}", '
        f'"diff": "--- a/s{slice_id}\\n+++ b/s{slice_id}", '
        f'"notes": "applied slice {slice_id}"}}'
    )


def _opus_usage() -> TokenUsage:
    return TokenUsage(
        input_tokens=50,
        output_tokens=80,
        cost_usd=0.008,
        model="claude-opus-4-7",
    )


def _input_dict() -> dict[str, Any]:
    # ``slice_refactor.initial_state`` reads this dict shape via
    # SliceRefactorInput(**inputs) and constructs the PlannerInput.
    return {
        "run_id": "dummy",
        "input": PlannerInput(
            goal="Refactor monolith into three slices.",
            context="Three independent modules.",
            max_steps=5,
        ),
    }


def _seed_planner_sub_graph_scripts() -> None:
    """Seed the planner sub-graph's two LLM calls.

    ``planner-explorer`` is a :class:`LiteLLMRoute` (Ollama) →
    LiteLLM stub handles the explorer report.
    ``planner-synth`` is a :class:`ClaudeCodeRoute` → Claude Code
    subprocess stub handles the plan. The breaker trip sits on
    ``slice-worker`` exclusively, so the planner sub-graph's two
    calls dispatch normally before the fan-out.
    """
    _StubLiteLLMAdapter.script = [(_explorer_report_json(), 0.0010)]
    _StubClaudeCodeSubprocess.script = [
        (_three_step_plan_json(), _opus_usage()),
    ]


# ---------------------------------------------------------------------------
# AC — single gate fires for all parallel branches
# ---------------------------------------------------------------------------


async def test_single_gate_for_all_branches(tmp_path: Path) -> None:
    """Three parallel slice workers, one shared breaker, one gate record.

    Pre-trips the breaker so every slice-worker invocation raises
    :class:`CircuitOpen` pre-call without hitting the LiteLLM adapter.
    All three branches emit their slice id into
    ``_circuit_open_slice_ids``; the fan-in
    :func:`_route_before_aggregate` routes to ``ollama_fallback_stamp``
    once and the gate fires once.

    Asserted invariants:

    * ``__interrupt__`` appears exactly once in the paused state
      (single gate firing).
    * ``_ollama_fallback_count`` == 1 — the stamp node, which is the
      sole per-run gate-record writer, incremented the counter exactly
      one time.
    * ``_circuit_open_slice_ids`` carries all three slice ids (fan-in
      order; ``operator.add`` reducer).
    * LiteLLM worker adapter was NOT invoked for any slice call (the
      breaker short-circuited before dispatch) — the adapter's call
      count equals the two planner sub-graph calls only.
    """
    clock = {"t": 0.0}
    breaker = _build_breaker(clock)
    await breaker.record_failure(reason="connection_refused")
    assert breaker.state is CircuitState.OPEN

    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_slice_refactor().compile(checkpointer=checkpointer)

    _seed_planner_sub_graph_scripts()

    cfg, _tracker, _storage = await _build_config(
        tmp_path=tmp_path, run_id="run-single-gate", breaker=breaker
    )
    try:
        # The planner sub-graph pauses at plan_review first — approve
        # that to reach the fan-out.
        paused_planner = await app.ainvoke(
            {
                "run_id": "run-single-gate",
                "input": _input_dict()["input"],
            },
            cfg,
        )
        assert "__interrupt__" in paused_planner

        paused_fallback = await app.ainvoke(
            Command(resume="approved"), cfg
        )
        assert "__interrupt__" in paused_fallback

        # One LiteLLM call (explorer) + one Claude Code subprocess call
        # (planner synth) fired for the planner sub-graph. Slice-worker
        # calls short-circuited on the tripped breaker and never reached
        # the adapter at all.
        assert _StubLiteLLMAdapter.call_count == 1
        assert _StubClaudeCodeSubprocess.call_count == 1

        # All three branches emitted their id into _circuit_open_slice_ids.
        circuit_ids = sorted(
            paused_fallback.get("_circuit_open_slice_ids") or []
        )
        assert circuit_ids == ["1", "2", "3"]

        # Single gate firing — the stamp node writes _ollama_fallback_count
        # exactly once per gate.
        assert paused_fallback.get("_ollama_fallback_count") == 1

        # Fallback has not fired yet — the flag flips on the dispatch
        # node (post-gate), so at the pause it must still be False.
        assert not paused_fallback.get("_ollama_fallback_fired", False)
    finally:
        await checkpointer.conn.close()


# ---------------------------------------------------------------------------
# AC — FALLBACK re-fans all circuit-open branches to the replacement tier
# ---------------------------------------------------------------------------


async def test_fallback_applies_to_subsequent_branches(tmp_path: Path) -> None:
    """``FallbackChoice.FALLBACK`` stamps the override; pending branches
    re-fire on the replacement tier.

    Under the shared-breaker pre-trip, all three branches observed
    :class:`CircuitOpen` on the first pass and all three are re-fanned
    by :func:`_route_after_fallback_dispatch_slice`. Post-resume every
    re-fired branch resolves ``slice-worker`` through
    :data:`SLICE_REFACTOR_OLLAMA_FALLBACK.fallback_tier`
    (``planner-synth`` / :class:`ClaudeCodeRoute`) — the Claude Code
    subprocess stub handles the three calls.

    Asserted invariants:

    * No further LiteLLM worker calls land (the override routes away
      from the Ollama path).
    * Three ``planner-synth`` worker calls land on the Claude Code
      subprocess stub — one per re-fanned slice id.
    * ``_mid_run_tier_overrides`` carries the
      ``slice-worker -> planner-synth`` mapping at the final state.
    * ``_ollama_fallback_fired`` is True.
    * The run pauses at the downstream ``slice_refactor_review`` gate
      (the happy post-fallback path continues to aggregate + gate).
    """
    clock = {"t": 0.0}
    breaker = _build_breaker(clock)
    await breaker.record_failure(reason="connection_refused")

    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_slice_refactor().compile(checkpointer=checkpointer)

    # Planner sub-graph calls + three fallback-routed worker calls via
    # Claude Code subprocess. The planner synth + all three workers all
    # dispatch through the subprocess stub; the worker calls carry the
    # slice id in the prompt.
    _seed_planner_sub_graph_scripts()
    _StubClaudeCodeSubprocess.script.extend(
        [
            (_slice_result_json("1"), _opus_usage()),
            (_slice_result_json("2"), _opus_usage()),
            (_slice_result_json("3"), _opus_usage()),
        ]
    )

    cfg, _tracker, _storage = await _build_config(
        tmp_path=tmp_path, run_id="run-fallback", breaker=breaker
    )
    try:
        paused_planner = await app.ainvoke(
            {"run_id": "run-fallback", "input": _input_dict()["input"]},
            cfg,
        )
        assert "__interrupt__" in paused_planner

        paused_fallback = await app.ainvoke(
            Command(resume="approved"), cfg
        )
        assert "__interrupt__" in paused_fallback

        # Advance the clock past the breaker cooldown — not strictly
        # required for FALLBACK (the override routes away from Ollama)
        # but keeps the test deterministic under any future semantics
        # change that retries on the original tier first.
        clock["t"] = 5.0

        post_fallback = await app.ainvoke(Command(resume="fallback"), cfg)
        # Post-resume the run reaches the slice_refactor_review gate.
        assert "__interrupt__" in post_fallback

        # LiteLLM adapter saw only the one planner sub-graph explorer
        # call — no worker calls ever reached LiteLLM (breaker
        # short-circuit on the first pass; override on the second).
        assert _StubLiteLLMAdapter.call_count == 1

        # Claude Code subprocess saw 1 planner synth + 3 fallback-routed
        # worker calls (one per re-fanned slice).
        assert _StubClaudeCodeSubprocess.call_count == 4
        assert _StubClaudeCodeSubprocess.routed_flags == [
            "opus",
            "opus",
            "opus",
            "opus",
        ]
        # The planner synth call does not carry a "Slice id:" header,
        # so call_slice_ids only holds the three worker-call ids.
        assert sorted(_StubClaudeCodeSubprocess.call_slice_ids) == [
            "1",
            "2",
            "3",
        ]

        # Override stamped for the rest of the run.
        assert post_fallback["_mid_run_tier_overrides"] == {
            SLICE_REFACTOR_OLLAMA_FALLBACK.logical: (
                SLICE_REFACTOR_OLLAMA_FALLBACK.fallback_tier
            )
        }
        assert post_fallback["_ollama_fallback_fired"] is True
    finally:
        await checkpointer.conn.close()


# ---------------------------------------------------------------------------
# AC — ABORT terminates pending branches via the fallback-abort node
# ---------------------------------------------------------------------------


async def test_abort_cancels_pending_branches(tmp_path: Path) -> None:
    """``FallbackChoice.ABORT`` routes to ``slice_refactor_ollama_abort``.

    Under the shared-breaker pre-trip, every branch observed
    :class:`CircuitOpen` on the first pass and the run paused at the
    single fallback gate. Resuming with ``ABORT`` terminates the run:
    :func:`_route_after_fallback_dispatch_slice` routes to the
    ``slice_refactor_ollama_abort`` terminal node, which writes a
    ``hard_stop_metadata`` artefact (``reason="ollama_fallback_abort"``,
    ``tier=slice-worker``) and stamps ``ollama_fallback_aborted=True``.

    Asserted invariants:

    * No further interrupts fire (terminal run).
    * No ``slice_result:<id>`` rows land in ``artifacts`` — the
      pending branches were cancelled via the abort terminal.
    * The metadata artefact's JSON payload names
      ``ollama_fallback_abort`` and the
      :data:`SLICE_REFACTOR_OLLAMA_FALLBACK.logical` tier.
    * No Claude Code subprocess or LiteLLM worker calls fired — no
      stub scripts are populated post-pause, so any call would raise
      "stub exhausted".
    """
    clock = {"t": 0.0}
    breaker = _build_breaker(clock)
    await breaker.record_failure(reason="connection_refused")

    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_slice_refactor().compile(checkpointer=checkpointer)

    # Planner sub-graph only — no worker scripts; any slice-worker call
    # on the abort branch would trip "stub exhausted".
    _seed_planner_sub_graph_scripts()

    cfg, _tracker, storage = await _build_config(
        tmp_path=tmp_path, run_id="run-abort", breaker=breaker
    )
    try:
        paused_planner = await app.ainvoke(
            {"run_id": "run-abort", "input": _input_dict()["input"]},
            cfg,
        )
        assert "__interrupt__" in paused_planner

        paused_fallback = await app.ainvoke(
            Command(resume="approved"), cfg
        )
        assert "__interrupt__" in paused_fallback

        final = await app.ainvoke(Command(resume="abort"), cfg)

        # Terminal — no further interrupt, abort flag set.
        assert "__interrupt__" not in final
        assert final.get("ollama_fallback_aborted") is True

        # No additional provider calls fired past the gate — the
        # planner sub-graph consumed 1 LiteLLM (explorer) + 1 subprocess
        # (synth); nothing else was scripted.
        assert _StubLiteLLMAdapter.call_count == 1
        assert _StubClaudeCodeSubprocess.call_count == 1

        # No slice_result artefacts landed (pending branches terminated
        # at the gate; apply never ran).
        for slice_id in ("1", "2", "3"):
            row = await storage.read_artifact(
                "run-abort", f"{SLICE_RESULT_ARTIFACT_KIND}:{slice_id}"
            )
            assert row is None

        # Abort metadata artefact landed with the right reason/tier.
        meta = await storage.read_artifact(
            "run-abort", "hard_stop_metadata"
        )
        assert meta is not None
        assert "ollama_fallback_abort" in meta["payload_json"]
        assert (
            SLICE_REFACTOR_OLLAMA_FALLBACK.logical in meta["payload_json"]
        )
    finally:
        await checkpointer.conn.close()
