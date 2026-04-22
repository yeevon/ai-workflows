"""Hermetic degraded-mode test suite for the Ollama-outage path (M8 T05).

Exercises the full degraded-mode flow end-to-end through
:func:`ai_workflows.workflows._dispatch.run_workflow` and
:func:`ai_workflows.workflows._dispatch.resume_run`:

* Organic breaker trip on the planner's Ollama-backed ``planner-explorer``
  tier (flaky adapter raises :class:`litellm.APIConnectionError` on the
  first N calls; the breaker flips OPEN after ``trip_threshold`` failures
  and subsequent attempts short-circuit to :class:`CircuitOpen`).
* Fallback-gate firing, the three :class:`FallbackChoice` resume
  branches (retry / fallback / abort), and the final ``runs.status``
  transition each branch produces.
* Single-gate-per-run invariant for ``slice_refactor``'s parallel
  fan-out (one ``record_gate`` call shared by all circuit-open branches,
  not one per branch).

Gates on ``runs.status`` in addition to graph-state keys — that is the
reason this suite goes through the dispatch wrapper rather than the
direct-compile pattern the T04 workflow tests use.

No live HTTP: the LiteLLM adapter is replaced by a flaky stub; the Claude
Code subprocess is replaced by a healthy stub. The circuit-breaker
builder inside :mod:`ai_workflows.workflows._dispatch` is monkey-patched
to return a controllable breaker with a test clock so cooldowns can be
advanced deterministically.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import litellm
import pytest

from ai_workflows import workflows
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.primitives.circuit_breaker import CircuitBreaker
from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.tiers import ClaudeCodeRoute, LiteLLMRoute, ModelPricing
from ai_workflows.workflows import _dispatch
from ai_workflows.workflows.planner import build_planner
from ai_workflows.workflows.slice_refactor import (
    SLICE_RESULT_ARTIFACT_KIND,
    build_slice_refactor,
)

# ---------------------------------------------------------------------------
# Adapter stubs — flaky LiteLLM + healthy Claude Code
# ---------------------------------------------------------------------------


class _FlakyLiteLLMAdapter:
    """LiteLLM stub that fails the first N matching calls, then succeeds.

    A call "matches" when :attr:`fail_on_pattern` is ``None`` (all calls
    match) or when the concatenated message content contains the literal
    substring in :attr:`fail_on_pattern`. Pattern-scoped failure lets the
    slice_refactor tests keep the planner sub-graph on a healthy path
    (explorer call succeeds) while slice-worker calls hit the flaky
    branch (prompts carry ``"Slice id:"``).

    All mutation runs through class-level state so a test can observe
    call counts + routed models across the adapter's many instances.
    """

    fail_on_pattern: str | None = None
    fail_first_n: int = 0

    call_count: int = 0
    failed_count: int = 0
    routed_models: list[str] = []
    success_script: list[tuple[str, float]] = []

    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        self.route = route

    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict],
        response_format: Any = None,
    ) -> tuple[str, TokenUsage]:
        cls = _FlakyLiteLLMAdapter
        cls.call_count += 1
        cls.routed_models.append(self.route.model)

        content = "\n".join(str(m.get("content") or "") for m in messages)
        matches = (
            cls.fail_on_pattern is None or cls.fail_on_pattern in content
        )
        if matches and cls.failed_count < cls.fail_first_n:
            cls.failed_count += 1
            raise litellm.exceptions.APIConnectionError(
                message="test-induced Ollama outage",
                llm_provider="ollama",
                model=self.route.model,
            )

        if not cls.success_script:
            raise AssertionError(
                f"litellm stub script exhausted at call #{cls.call_count}"
            )
        text, cost = cls.success_script.pop(0)
        return text, TokenUsage(
            input_tokens=8,
            output_tokens=12,
            cost_usd=cost,
            model=self.route.model,
        )

    @classmethod
    def reset(cls) -> None:
        cls.fail_on_pattern = None
        cls.fail_first_n = 0
        cls.call_count = 0
        cls.failed_count = 0
        cls.routed_models = []
        cls.success_script = []


class _HealthyClaudeCodeStub:
    """Healthy Claude Code subprocess stub serving scripted successes."""

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
        cls = _HealthyClaudeCodeStub
        cls.call_count += 1
        cls.routed_flags.append(self.route.cli_model_flag)
        content = str(messages[0].get("content") or "") if messages else ""
        if "Slice id:" in content:
            first_line = content.splitlines()[0]
            _, _, sid = first_line.partition("Slice id: ")
            cls.call_slice_ids.append(sid.strip())
        if not cls.script:
            raise AssertionError(
                f"claude_code stub script exhausted at call #{cls.call_count}"
            )
        return cls.script.pop(0)

    @classmethod
    def reset(cls) -> None:
        cls.script = []
        cls.call_count = 0
        cls.routed_flags = []
        cls.call_slice_ids = []


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _clock() -> dict[str, float]:
    """Controllable monotonic clock shared between the test and breaker.

    Dict wrapper so mutations in the test body are visible to the
    :class:`CircuitBreaker`'s ``time_source`` closure.
    """
    return {"t": 0.0}


@pytest.fixture(autouse=True)
def _reset_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    _FlakyLiteLLMAdapter.reset()
    _HealthyClaudeCodeStub.reset()
    monkeypatch.setattr(
        tiered_node_module, "LiteLLMAdapter", _FlakyLiteLLMAdapter
    )
    monkeypatch.setattr(
        tiered_node_module, "ClaudeCodeSubprocess", _HealthyClaudeCodeStub
    )


@pytest.fixture(autouse=True)
def _reensure_workflows_registered() -> Iterator[None]:
    """Re-register both workflows so ``workflows.get(...)`` resolves."""
    workflows._reset_for_tests()
    workflows.register("planner", build_planner)
    workflows.register("slice_refactor", build_slice_refactor)
    yield


@pytest.fixture(autouse=True)
def _redirect_default_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIW_STORAGE_DB", str(tmp_path / "storage.sqlite"))
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))


@pytest.fixture
def _injected_breakers(
    monkeypatch: pytest.MonkeyPatch, _clock: dict[str, float]
) -> dict[str, CircuitBreaker]:
    """Monkey-patch ``_build_ollama_circuit_breakers`` to return tight breakers.

    Uses ``trip_threshold=3`` (matches the production default and the
    T05 spec wording), ``cooldown_s=1.0``, and a test clock so the
    planner RETRY test can advance past the cooldown without sleeping.
    The same dict instance is reused across ``run_workflow`` and
    ``resume_run`` for one test because LangGraph's dispatch wires a
    fresh config per invocation but the breaker must persist across
    both to observe the OPEN → HALF_OPEN → CLOSED transition.
    """
    shared: dict[str, CircuitBreaker] = {}

    def _build(tier_registry: dict) -> dict[str, CircuitBreaker]:
        for name, config in tier_registry.items():
            route = config.route
            is_ollama = (
                isinstance(route, LiteLLMRoute)
                and route.model.startswith("ollama/")
            )
            if is_ollama and name not in shared:
                shared[name] = CircuitBreaker(
                    tier=name,
                    trip_threshold=3,
                    cooldown_s=1.0,
                    time_source=lambda: _clock["t"],
                )
        return {
            name: shared[name]
            for name, config in tier_registry.items()
            if isinstance(config.route, LiteLLMRoute)
            and config.route.model.startswith("ollama/")
            and name in shared
        }

    monkeypatch.setattr(_dispatch, "_build_ollama_circuit_breakers", _build)
    return shared


# ---------------------------------------------------------------------------
# Helpers — scripted successful JSON payloads
# ---------------------------------------------------------------------------


def _explorer_report_json() -> str:
    return (
        '{"summary": "Three parallel slices.", '
        '"considerations": ["Independent modules"], '
        '"assumptions": ["Green CI"]}'
    )


def _plan_single_step_json() -> str:
    return (
        '{"goal": "Ship the marketing page.", '
        '"summary": "One-step delivery.", '
        '"steps": [{"index": 1, "title": "t", "rationale": "r", '
        '"actions": ["a"]}]}'
    )


def _plan_three_steps_json() -> str:
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
        input_tokens=100,
        output_tokens=200,
        cost_usd=0.02,
        model="claude-opus-4-7",
    )


def _planner_inputs(
    goal: str = "Ship the marketing page.",
    context: str = "Hero + single CTA.",
    max_steps: int = 5,
) -> dict[str, Any]:
    return {"goal": goal, "context": context, "max_steps": max_steps}


# ---------------------------------------------------------------------------
# Planner — RETRY succeeds
# ---------------------------------------------------------------------------


async def test_planner_outage_retry_succeeds(
    _clock: dict[str, float],
    _injected_breakers: dict[str, CircuitBreaker],
    tmp_path: Path,
) -> None:
    """Organic trip → gate → RETRY → run completes on the Ollama tier.

    Flaky LiteLLM fails the first three planner-explorer calls. The
    breaker records three failures and trips OPEN. The fourth explorer
    attempt short-circuits to :class:`CircuitOpen`, routing through
    ``ollama_fallback_stamp`` → the gate. Resume with ``"retry"`` after
    advancing the clock past the cooldown: the breaker transitions
    HALF_OPEN, the flaky stub's fourth call (now past its fail budget)
    returns a valid explorer report, the planner reaches
    ``plan_review``, and the approved resume persists the plan.
    """
    _FlakyLiteLLMAdapter.fail_first_n = 3
    _FlakyLiteLLMAdapter.success_script = [
        (_explorer_report_json(), 0.001),
    ]
    _HealthyClaudeCodeStub.script = [
        (_plan_single_step_json(), _opus_usage()),
    ]

    run = await _dispatch.run_workflow(
        workflow="planner",
        inputs=_planner_inputs(),
        run_id="run-retry",
    )
    assert run["status"] == "pending", run
    assert run["awaiting"] == "gate", run
    # Post-gate-pause, the fallback gate is first — the plan_review gate
    # only fires after the retry/fallback branch completes the sub-graph.

    # Advance clock past cooldown so the HALF_OPEN probe on retry fires.
    _clock["t"] = 5.0

    post_retry = await _dispatch.resume_run(
        run_id="run-retry", gate_response="retry"
    )
    # The retry re-fires explorer, then planner_synth, then pauses at
    # ``plan_review`` — still "pending".
    assert post_retry["status"] == "pending", post_retry

    # Breaker transitioned OPEN → HALF_OPEN → CLOSED on the successful
    # probe.
    breaker = _injected_breakers["planner-explorer"]
    assert breaker.state.value == "closed", breaker.state

    final = await _dispatch.resume_run(
        run_id="run-retry", gate_response="approved"
    )
    assert final["status"] == "completed", final
    assert final["plan"] is not None

    # Exactly one explorer adapter call succeeded post-resume (the
    # pre-gate attempts raised before the stub's success path).
    # Three failures + one success = four total calls.
    assert _FlakyLiteLLMAdapter.call_count == 4
    assert _FlakyLiteLLMAdapter.failed_count == 3


# ---------------------------------------------------------------------------
# Planner — FALLBACK succeeds on the replacement tier
# ---------------------------------------------------------------------------


async def test_planner_outage_fallback_succeeds(
    _clock: dict[str, float],
    _injected_breakers: dict[str, CircuitBreaker],
    tmp_path: Path,
) -> None:
    """FALLBACK stamps the override → explorer re-dispatches through Claude.

    After the gate fires on the tripped breaker, resume with
    ``"fallback"``. The dispatch helper stamps
    ``_mid_run_tier_overrides["planner-explorer"] = "planner-synth"``;
    :class:`TieredNode` resolves the logical ``planner-explorer`` through
    the override to ``planner-synth`` (:class:`ClaudeCodeRoute`), which
    bypasses the flaky LiteLLM adapter entirely. The Claude Code stub
    handles both the re-fired explorer call and the regular planner
    synth call; the LiteLLM adapter count stays at the pre-gate failures
    (no post-gate Ollama dispatch).
    """
    _FlakyLiteLLMAdapter.fail_first_n = 3
    _HealthyClaudeCodeStub.script = [
        (_explorer_report_json(), _opus_usage()),
        (_plan_single_step_json(), _opus_usage()),
    ]

    run = await _dispatch.run_workflow(
        workflow="planner",
        inputs=_planner_inputs(),
        run_id="run-fallback",
    )
    assert run["status"] == "pending", run

    post_fallback = await _dispatch.resume_run(
        run_id="run-fallback", gate_response="fallback"
    )
    assert post_fallback["status"] == "pending", post_fallback

    final = await _dispatch.resume_run(
        run_id="run-fallback", gate_response="approved"
    )
    assert final["status"] == "completed", final

    # Explorer saw only the three pre-gate failures; no post-resume
    # LiteLLM call (the override routed through Claude Code instead).
    assert _FlakyLiteLLMAdapter.call_count == 3
    # Claude Code handled the re-fired explorer + the planner synth.
    assert _HealthyClaudeCodeStub.call_count == 2
    assert _HealthyClaudeCodeStub.routed_flags == ["opus", "opus"]


# ---------------------------------------------------------------------------
# Planner — ABORT stamps runs.status='aborted'
# ---------------------------------------------------------------------------


async def test_planner_outage_abort_terminates(
    _clock: dict[str, float],
    _injected_breakers: dict[str, CircuitBreaker],
    tmp_path: Path,
) -> None:
    """ABORT routes through ``planner_hard_stop`` → ``runs.status='aborted'``.

    No post-resume provider calls fire — all stub scripts are left
    empty, so any extra call raises ``stub exhausted``. The dispatch
    helper stamps ``runs.status='aborted'`` with ``finished_at`` per
    M8 T04's dispatch contract.
    """
    _FlakyLiteLLMAdapter.fail_first_n = 3

    run = await _dispatch.run_workflow(
        workflow="planner",
        inputs=_planner_inputs(),
        run_id="run-abort",
    )
    assert run["status"] == "pending", run

    final = await _dispatch.resume_run(
        run_id="run-abort", gate_response="abort"
    )
    assert final["status"] == "aborted", final
    assert "ollama_fallback" in (final.get("error") or "")

    # Row in storage reflects the aborted status + finished_at stamp.
    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    row = await storage.get_run("run-abort")
    assert row is not None
    assert row["status"] == "aborted"
    assert row["finished_at"] is not None

    # No provider calls fired post-gate.
    assert _FlakyLiteLLMAdapter.call_count == 3
    assert _HealthyClaudeCodeStub.call_count == 0


# ---------------------------------------------------------------------------
# slice_refactor — single gate fires for all parallel branches
# ---------------------------------------------------------------------------


async def test_slice_refactor_outage_single_gate(
    _clock: dict[str, float],
    _injected_breakers: dict[str, CircuitBreaker],
    tmp_path: Path,
) -> None:
    """Three parallel slice workers → one shared breaker → one gate record.

    The flaky adapter's pattern-scoped failure keeps the planner
    sub-graph happy-path (explorer matches no pattern) but fails on
    every slice-worker call (their prompts carry ``"Slice id:"``). The
    breaker trips after three consecutive slice-worker failures; the
    remaining slice-worker attempts short-circuit to
    :class:`CircuitOpen`. :meth:`SQLiteStorage.record_gate` is invoked
    exactly once per run regardless of the three parallel circuit-open
    emissions.
    """
    _FlakyLiteLLMAdapter.fail_on_pattern = "Slice id:"
    _FlakyLiteLLMAdapter.fail_first_n = 99  # keep failing past trip
    _FlakyLiteLLMAdapter.success_script = [
        (_explorer_report_json(), 0.001),  # planner explorer — no match
    ]
    _HealthyClaudeCodeStub.script = [
        (_plan_three_steps_json(), _opus_usage()),  # planner synth
    ]

    # Count record_gate invocations via a wrapping side-effect.
    gate_calls: list[tuple[str, str]] = []
    original_record_gate = SQLiteStorage.record_gate

    async def _wrapped_record_gate(
        self: SQLiteStorage,
        run_id: str,
        gate_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        gate_calls.append((run_id, gate_id))
        return await original_record_gate(
            self, run_id, gate_id, *args, **kwargs
        )

    from unittest.mock import patch

    with patch.object(SQLiteStorage, "record_gate", _wrapped_record_gate):
        run = await _dispatch.run_workflow(
            workflow="slice_refactor",
            inputs=_planner_inputs(
                goal="Refactor monolith into three slices.",
                context="Three independent modules.",
            ),
            run_id="run-single-gate",
        )
        assert run["status"] == "pending", run

        # Approve plan_review to reach the fan-out.
        paused_fallback = await _dispatch.resume_run(
            run_id="run-single-gate", gate_response="approved"
        )
        assert paused_fallback["status"] == "pending", paused_fallback

    fallback_gate_calls = [
        (rid, gid) for rid, gid in gate_calls if gid == "ollama_fallback"
    ]
    assert len(fallback_gate_calls) == 1, (
        f"expected exactly one ollama_fallback record_gate; got "
        f"{fallback_gate_calls!r}"
    )

    # The breaker landed OPEN after the cascade of slice-worker failures.
    breaker = _injected_breakers["slice-worker"]
    assert breaker.state.value == "open", breaker.state


# ---------------------------------------------------------------------------
# slice_refactor — FALLBACK re-fans branches to the replacement tier
# ---------------------------------------------------------------------------


async def test_slice_refactor_outage_fallback_applies_to_siblings(
    _clock: dict[str, float],
    _injected_breakers: dict[str, CircuitBreaker],
    tmp_path: Path,
) -> None:
    """FALLBACK stamps the override → pending branches re-fire on Claude Code.

    Post-resume the re-fanned worker branches resolve ``slice-worker``
    through the mid-run override to ``planner-synth``
    (:class:`ClaudeCodeRoute`). The flaky LiteLLM adapter never sees
    another worker call; the Claude Code stub serves one success per
    slice id. The final run completes through the
    ``slice_refactor_review`` gate with status ``"completed"``.
    """
    _FlakyLiteLLMAdapter.fail_on_pattern = "Slice id:"
    _FlakyLiteLLMAdapter.fail_first_n = 99
    _FlakyLiteLLMAdapter.success_script = [
        (_explorer_report_json(), 0.001),
    ]
    _HealthyClaudeCodeStub.script = [
        (_plan_three_steps_json(), _opus_usage()),
        (_slice_result_json("1"), _opus_usage()),
        (_slice_result_json("2"), _opus_usage()),
        (_slice_result_json("3"), _opus_usage()),
    ]

    run = await _dispatch.run_workflow(
        workflow="slice_refactor",
        inputs=_planner_inputs(
            goal="Refactor monolith into three slices.",
            context="Three independent modules.",
        ),
        run_id="run-sr-fallback",
    )
    assert run["status"] == "pending", run

    # Approve plan_review → fan-out → breaker trips → fallback gate.
    post_plan = await _dispatch.resume_run(
        run_id="run-sr-fallback", gate_response="approved"
    )
    assert post_plan["status"] == "pending", post_plan

    # Advance past cooldown; FALLBACK routes off the Ollama path but
    # keeps the breaker observable as OPEN if a later call slips back.
    _clock["t"] = 5.0

    post_fallback = await _dispatch.resume_run(
        run_id="run-sr-fallback", gate_response="fallback"
    )
    # slice_refactor_review gate fires next.
    assert post_fallback["status"] == "pending", post_fallback

    final = await _dispatch.resume_run(
        run_id="run-sr-fallback", gate_response="approved"
    )
    assert final["status"] == "completed", final

    # All three slice ids routed through Claude Code post-fallback.
    assert sorted(_HealthyClaudeCodeStub.call_slice_ids) == ["1", "2", "3"]


# ---------------------------------------------------------------------------
# slice_refactor — ABORT cancels pending branches, no slice_result rows
# ---------------------------------------------------------------------------


async def test_slice_refactor_outage_abort_cancels_pending_branches(
    _clock: dict[str, float],
    _injected_breakers: dict[str, CircuitBreaker],
    tmp_path: Path,
) -> None:
    """ABORT terminates the run; no ``slice_result:*`` artefacts land.

    The ``slice_refactor_ollama_abort`` terminal node writes a
    ``hard_stop_metadata`` artefact. Dispatch flips
    ``runs.status='aborted'`` with ``finished_at`` stamped, matching the
    planner abort path. No Claude Code subprocess calls fire past the
    plan-review approval (the fan-out branches all observe the tripped
    breaker and route to the single gate).
    """
    _FlakyLiteLLMAdapter.fail_on_pattern = "Slice id:"
    _FlakyLiteLLMAdapter.fail_first_n = 99
    _FlakyLiteLLMAdapter.success_script = [
        (_explorer_report_json(), 0.001),
    ]
    _HealthyClaudeCodeStub.script = [
        (_plan_three_steps_json(), _opus_usage()),
    ]

    run = await _dispatch.run_workflow(
        workflow="slice_refactor",
        inputs=_planner_inputs(
            goal="Refactor monolith into three slices.",
            context="Three independent modules.",
        ),
        run_id="run-sr-abort",
    )
    assert run["status"] == "pending", run

    post_plan = await _dispatch.resume_run(
        run_id="run-sr-abort", gate_response="approved"
    )
    assert post_plan["status"] == "pending", post_plan

    final = await _dispatch.resume_run(
        run_id="run-sr-abort", gate_response="abort"
    )
    assert final["status"] == "aborted", final

    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    row = await storage.get_run("run-sr-abort")
    assert row is not None
    assert row["status"] == "aborted"
    assert row["finished_at"] is not None

    # No slice_result rows landed — pending branches were cancelled at
    # the gate before reaching the apply stage.
    for slice_id in ("1", "2", "3"):
        artefact = await storage.read_artifact(
            "run-sr-abort", f"{SLICE_RESULT_ARTIFACT_KIND}:{slice_id}"
        )
        assert artefact is None, slice_id

    # Abort metadata artefact landed with the right reason/tier.
    meta = await storage.read_artifact("run-sr-abort", "hard_stop_metadata")
    assert meta is not None
    assert "ollama_fallback_abort" in meta["payload_json"]
