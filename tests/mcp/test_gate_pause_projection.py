"""M11 Task 01 — gate-pause projection on the MCP output models.

Pins the four projection acceptance criteria the task spec names:

1. ``run_workflow`` at a ``HumanGate`` pause returns
   ``{status="pending", awaiting="gate", plan=<non-null dict>,
     gate_context={gate_prompt, gate_id, workflow_id, checkpoint_ts}}``
   for the ``planner`` workflow. Closes M9 T04 ISS-02 — the operator
   finally has something to review at the pause.
2. ``resume_run`` on a workflow with two gates (``slice_refactor`` —
   ``planner_review`` then ``slice_refactor_review``) projects the
   same draft + gate_context on the second gate the resume yields.
3. Non-gate paths are unaffected. ``status="completed"`` still returns
   ``gate_context=None``, ``awaiting=None``, and a terminal plan shape
   byte-identical to the M4-era dump (regression guard).
4. ``gate_response="rejected"`` returns the last-draft plan
   (``status="gate_rejected"``) so auditors can inspect what was
   rejected. ``gate_context`` is ``None`` because the gate already
   resolved.

Relationship to other modules
-----------------------------
* :mod:`ai_workflows.mcp.schemas` — ``RunWorkflowOutput`` /
  ``ResumeRunOutput`` are where the new fields land.
* :mod:`ai_workflows.workflows._dispatch` — ``_build_*_from_final``
  helpers are where the projection is built.
* :mod:`tests.mcp.test_run_workflow` / :mod:`tests.mcp.test_resume_run`
  — source of the ``_StubLiteLLMAdapter`` + autouse fixture pattern
  this suite mirrors.
"""

from __future__ import annotations

import datetime as _dt
import json
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from ai_workflows import workflows
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.mcp import build_server
from ai_workflows.mcp.schemas import ResumeRunInput, RunWorkflowInput
from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig
from ai_workflows.workflows import slice_refactor as slice_refactor_module
from ai_workflows.workflows.planner import build_planner
from ai_workflows.workflows.slice_refactor import build_slice_refactor


class _StubLiteLLMAdapter:
    """Scripted adapter — routes planner + worker calls via the slice id marker."""

    script: list[Any] = []
    call_count: int = 0
    worker_script: dict[str, list[Any]] = {}
    worker_calls_by_slice: dict[str, int] = {}

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
        content = messages[0].get("content") or ""
        if "Slice id:" in content:
            first_line = content.splitlines()[0]
            _, _, sid = first_line.partition("Slice id: ")
            sid = sid.strip()
            _StubLiteLLMAdapter.worker_calls_by_slice[sid] = (
                _StubLiteLLMAdapter.worker_calls_by_slice.get(sid, 0) + 1
            )
            per_slice = _StubLiteLLMAdapter.worker_script.get(sid)
            if not per_slice:
                raise AssertionError(
                    f"stub worker script exhausted for slice {sid!r}"
                )
            head = per_slice.pop(0)
        else:
            if not _StubLiteLLMAdapter.script:
                raise AssertionError("stub planner script exhausted")
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
        cls.worker_script = {}
        cls.worker_calls_by_slice = defaultdict(int)


@pytest.fixture(autouse=True)
def _reset_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    _StubLiteLLMAdapter.reset()
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _StubLiteLLMAdapter)


def _hermetic_slice_registry() -> dict[str, TierConfig]:
    """All-LiteLLM registry for slice_refactor tests.

    The production :func:`slice_refactor_tier_registry` composes
    ``planner_tier_registry()`` (which the directory conftest already
    pins to LiteLLM) with an Ollama-routed ``slice-worker``. The stub
    adapter intercepts every :class:`LiteLLMAdapter` call regardless
    of route, so the Ollama string is harmless — but replacing the
    whole registry here means the hermetic test is literal about what
    it exercises rather than implicit.
    """
    route = LiteLLMRoute(model="gemini/gemini-2.5-flash")
    return {
        "planner-explorer": TierConfig(
            name="planner-explorer",
            route=route,
            max_concurrency=2,
            per_call_timeout_s=60,
        ),
        "planner-synth": TierConfig(
            name="planner-synth",
            route=route,
            max_concurrency=2,
            per_call_timeout_s=90,
        ),
        "slice-worker": TierConfig(
            name="slice-worker",
            route=route,
            max_concurrency=4,
            per_call_timeout_s=60,
        ),
    }


@pytest.fixture(autouse=True)
def _stub_slice_tier_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin ``slice_refactor_tier_registry`` to the all-LiteLLM version."""
    monkeypatch.setattr(
        slice_refactor_module,
        "slice_refactor_tier_registry",
        _hermetic_slice_registry,
    )


@pytest.fixture(autouse=True)
def _reensure_workflows_registered() -> Iterator[None]:
    workflows._reset_for_tests()
    workflows.register("planner", build_planner)
    workflows.register("slice_refactor", build_slice_refactor)
    yield


@pytest.fixture(autouse=True)
def _redirect_default_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("AIW_STORAGE_DB", str(tmp_path / "storage.sqlite"))


# ---------------------------------------------------------------------------
# Fixture JSON
# ---------------------------------------------------------------------------


def _valid_explorer_json() -> str:
    return json.dumps(
        {
            "summary": "Three-step delivery.",
            "considerations": ["Copy tone", "CTA placement"],
            "assumptions": ["Design system stable"],
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
                }
            ],
        }
    )


def _slice_plan_json(n: int) -> str:
    steps = [
        {
            "index": i,
            "title": f"Slice {i}",
            "rationale": f"r{i}",
            "actions": [f"act {i}"],
        }
        for i in range(1, n + 1)
    ]
    return json.dumps(
        {
            "goal": "Split the monolith.",
            "summary": f"{n} parallel slices.",
            "steps": steps,
        }
    )


def _valid_slice_result_json(slice_id: str) -> str:
    return json.dumps(
        {
            "slice_id": slice_id,
            "diff": f"--- a/s{slice_id}\n+++ b/s{slice_id}",
            "notes": f"completed slice {slice_id}",
        }
    )


# ---------------------------------------------------------------------------
# AC: run_workflow gate pause projects plan + gate_context (planner)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_workflow_gate_pause_projects_plan_and_gate_context() -> None:
    """AC (spec §Acceptance): ``RunWorkflowOutput`` at a gate pause carries
    the in-flight ``plan`` and a populated ``gate_context``.

    Regression guard for M9 T04 ISS-02 — the operator used to see
    ``plan: null`` + no prompt at pause; M11 T01 populates both.
    """
    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
    ]
    server = build_server()
    tool = await server.get_tool("run_workflow")
    result = await tool.fn(
        RunWorkflowInput(
            workflow_id="planner",
            inputs={
                "goal": "Ship the marketing page.",
                "context": None,
                "max_steps": 10,
            },
            run_id="run-m11-pause",
        )
    )

    assert result.status == "pending"
    assert result.awaiting == "gate"
    assert result.error is None

    assert result.plan is not None, "plan must be populated at gate pause (M9 T04 ISS-02)"
    assert isinstance(result.plan, dict)
    assert "steps" in result.plan, f"expected PlannerPlan shape; got keys {list(result.plan)}"
    assert isinstance(result.plan["steps"], list)
    assert len(result.plan["steps"]) == 1

    assert result.gate_context is not None, "gate_context must be populated at pause"
    gc = result.gate_context
    assert isinstance(gc, dict)
    assert set(gc.keys()) >= {
        "gate_prompt",
        "gate_id",
        "workflow_id",
        "checkpoint_ts",
    }, f"gate_context missing required keys; got {list(gc)}"
    assert isinstance(gc["gate_prompt"], str) and gc["gate_prompt"].strip()
    assert gc["gate_id"] == "plan_review"
    assert gc["workflow_id"] == "planner"
    # checkpoint_ts parses as ISO-8601.
    parsed = _dt.datetime.fromisoformat(gc["checkpoint_ts"])
    assert parsed.tzinfo is not None, "checkpoint_ts must be TZ-aware ISO-8601"


# ---------------------------------------------------------------------------
# AC: resume_run re-gate pause projects plan + gate_context (slice_refactor)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resume_run_regate_projects_plan_and_gate_context() -> None:
    """AC (spec §Acceptance): ``ResumeRunOutput`` at a re-gate pause also
    carries ``plan`` + ``gate_context``, with ``awaiting="gate"``.

    Exercises the slice_refactor workflow: ``run_workflow`` pauses at
    ``planner_review``, the resume-approved flips through fan-out + aggregate
    and lands on ``slice_refactor_review`` — whose gate is what the resume
    response must project.
    """
    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0010),
        (_slice_plan_json(2), 0.0020),
    ]
    _StubLiteLLMAdapter.worker_script = {
        "1": [(_valid_slice_result_json("1"), 0.0030)],
        "2": [(_valid_slice_result_json("2"), 0.0031)],
    }

    server = build_server()
    run_tool = await server.get_tool("run_workflow")
    resume_tool = await server.get_tool("resume_run")

    first = await run_tool.fn(
        RunWorkflowInput(
            workflow_id="slice_refactor",
            inputs={
                "goal": "Split the monolith.",
                "context": "Three modules.",
                "max_steps": 5,
            },
            run_id="run-m11-regate",
        )
    )
    assert first.status == "pending"
    assert first.awaiting == "gate"
    # First pause is the nested planner's plan_review gate.
    assert first.gate_context is not None
    assert first.gate_context["gate_id"] == "plan_review"
    assert first.gate_context["workflow_id"] == "slice_refactor"

    regated = await resume_tool.fn(
        ResumeRunInput(run_id="run-m11-regate", gate_response="approved")
    )
    assert regated.status == "pending"
    assert regated.awaiting == "gate"
    assert regated.error is None
    # M19 T03 (ADR-0008): slice_refactor's FINAL_STATE_KEY is
    # "applied_artifact_count", which is None at the re-gate interrupt
    # (the artifact node hasn't run yet — it only runs after the gate
    # is approved). Both artifact and plan are None here; the canonical
    # artefact is not yet available and the gate_context carries the
    # review payload instead.
    assert regated.artifact is None
    assert regated.plan is None  # deprecated alias; same value
    assert regated.gate_context is not None
    gc = regated.gate_context
    assert gc["gate_id"] == "slice_refactor_review"
    assert gc["workflow_id"] == "slice_refactor"
    assert isinstance(gc["gate_prompt"], str) and gc["gate_prompt"].strip()


# ---------------------------------------------------------------------------
# AC: completed status has null gate_context + M4-era plan shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_completed_status_has_null_gate_context_and_matches_m4_plan_shape() -> None:
    """AC (spec §Acceptance): non-gate paths are unaffected.

    ``status="completed"`` returns ``gate_context=None``, ``awaiting=None``,
    and a terminal ``plan`` byte-identical to the M4-era pydantic dump.
    Locks the additive-only contract against regressions where a future
    edit bleeds M11 projection logic into the completed branch.
    """
    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
    ]
    server = build_server()
    run_tool = await server.get_tool("run_workflow")
    resume_tool = await server.get_tool("resume_run")

    await run_tool.fn(
        RunWorkflowInput(
            workflow_id="planner",
            inputs={
                "goal": "Ship the marketing page.",
                "context": None,
                "max_steps": 10,
            },
            run_id="run-m11-complete",
        )
    )
    result = await resume_tool.fn(
        ResumeRunInput(run_id="run-m11-complete", gate_response="approved")
    )

    assert result.status == "completed"
    assert result.awaiting is None
    assert result.gate_context is None
    assert result.error is None

    # Golden dict: the M4-era PlannerPlan.model_dump() shape.
    expected_plan = {
        "goal": "Ship the marketing page.",
        "summary": "Three-step delivery of the static hero + CTA page.",
        "steps": [
            {
                "index": 1,
                "title": "Draft hero copy",
                "rationale": "Lock tone before layout.",
                "actions": ["Sketch headline", "List CTAs"],
            }
        ],
    }
    assert result.plan == expected_plan


# ---------------------------------------------------------------------------
# AC: gate_rejected preserves last-draft plan for audit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gate_rejected_preserves_last_draft_plan() -> None:
    """AC (spec §Gap 1): ``status="gate_rejected"`` surfaces the last-draft
    plan for audit review; ``gate_context`` stays ``None`` (gate has
    resolved).
    """
    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
    ]
    server = build_server()
    run_tool = await server.get_tool("run_workflow")
    resume_tool = await server.get_tool("resume_run")

    await run_tool.fn(
        RunWorkflowInput(
            workflow_id="planner",
            inputs={
                "goal": "Ship the marketing page.",
                "context": None,
                "max_steps": 10,
            },
            run_id="run-m11-rej",
        )
    )
    result = await resume_tool.fn(
        ResumeRunInput(run_id="run-m11-rej", gate_response="rejected")
    )

    assert result.status == "gate_rejected"
    assert result.awaiting is None
    assert result.gate_context is None
    assert result.error is None
    assert result.plan is not None, (
        "M11 Gap 1: rejected terminal must carry the last-draft plan for audit"
    )
    assert isinstance(result.plan, dict)
    assert "steps" in result.plan
