"""Integration tests for M7 Task 02 — `_dispatch.run_workflow` eval-capture wiring.

Pins the full AIW_CAPTURE_EVALS → `_build_eval_capture_callback` →
`_build_cfg` → `TieredNode` → `CaptureCallback.on_node_complete` →
fixture-on-disk chain at the dispatch boundary. The unit tests in
[tests/evals/test_capture_callback.py](../evals/test_capture_callback.py)
exercise the callback class in isolation — this module complements them
by proving the wiring chain fires end-to-end against a stubbed planner
run.

Closes M7-T02-ISS-02 (missing dispatch integration tests) from the
Task 02 audit.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from ai_workflows import workflows
from ai_workflows.evals import EvalCase
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig
from ai_workflows.workflows import planner as planner_module
from ai_workflows.workflows._dispatch import (
    _build_cfg,
    _build_eval_capture_callback,
    run_workflow,
)
from ai_workflows.workflows.planner import build_planner


def _hermetic_planner_registry() -> dict[str, TierConfig]:
    """Pin both planner tiers to LiteLLM so the stub intercepts both calls.

    Production ``planner-synth`` routes to ``ClaudeCodeSubprocess``
    (OAuth CLI) — which would spawn a real subprocess here and defeat
    hermeticity. Same override the MCP suite installs in
    :mod:`tests/mcp/conftest.py`.
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


class _StubLiteLLMAdapter:
    """Scripted LiteLLM-adapter stub — mirrors tests/mcp/test_run_workflow.py."""

    script: list[Any] = []
    call_count: int = 0

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
        if not _StubLiteLLMAdapter.script:
            raise AssertionError("stub script exhausted")
        head = _StubLiteLLMAdapter.script.pop(0)
        text, cost = head
        return text, TokenUsage(
            input_tokens=11,
            output_tokens=17,
            cost_usd=cost,
            model=self.route.model,
        )

    @classmethod
    def reset(cls) -> None:
        cls.script = []
        cls.call_count = 0


@pytest.fixture(autouse=True)
def _reset_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    _StubLiteLLMAdapter.reset()
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _StubLiteLLMAdapter)


@pytest.fixture(autouse=True)
def _reensure_planner_registered() -> Iterator[None]:
    workflows._reset_for_tests()
    workflows.register("planner", build_planner)
    yield


@pytest.fixture(autouse=True)
def _redirect_default_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("AIW_STORAGE_DB", str(tmp_path / "storage.sqlite"))


@pytest.fixture(autouse=True)
def _stub_planner_tier_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        planner_module, "planner_tier_registry", _hermetic_planner_registry
    )


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


def _seed_planner_script() -> None:
    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
    ]


@pytest.mark.asyncio
async def test_dispatch_attaches_capture_callback_when_env_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-2: env-set dispatch writes one fixture per LLM-node call.

    Fixture path: ``<root>/<dataset>/<workflow>/<node>/*.json``.
    """

    evals_root = tmp_path / "evals"
    monkeypatch.setenv("AIW_EVALS_ROOT", str(evals_root))
    monkeypatch.setenv("AIW_CAPTURE_EVALS", "testsuite")

    _seed_planner_script()

    result = await run_workflow(
        workflow="planner",
        inputs={
            "goal": "Ship the marketing page.",
            "context": None,
            "max_steps": 10,
        },
        run_id="run-capture-on",
    )

    # Planner pauses at plan_review gate — both LLM nodes ran.
    assert result["status"] == "pending"
    assert result["awaiting"] == "gate"

    explorer_dir = evals_root / "testsuite" / "planner" / "explorer"
    # The synth LLM node is registered as ``planner`` in the graph
    # (workflows/planner.py:360). Capture lands under the node name.
    synth_dir = evals_root / "testsuite" / "planner" / "planner"
    explorer_fixtures = list(explorer_dir.glob("*.json"))
    synth_fixtures = list(synth_dir.glob("*.json"))

    assert len(explorer_fixtures) == 1, (
        f"expected one explorer fixture, got {explorer_fixtures}"
    )
    assert len(synth_fixtures) == 1, (
        f"expected one synth fixture, got {synth_fixtures}"
    )

    # Fixtures round-trip as EvalCase and carry provenance back to the run.
    explorer_case = EvalCase.model_validate_json(
        explorer_fixtures[0].read_text(encoding="utf-8")
    )
    assert explorer_case.workflow_id == "planner"
    assert explorer_case.node_name == "explorer"
    assert explorer_case.captured_from_run_id == "run-capture-on"


@pytest.mark.asyncio
async def test_dispatch_skips_capture_when_env_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-3: env unset → no fixture directory, no callback in configurable."""

    evals_root = tmp_path / "evals"
    monkeypatch.setenv("AIW_EVALS_ROOT", str(evals_root))
    monkeypatch.delenv("AIW_CAPTURE_EVALS", raising=False)

    _seed_planner_script()

    result = await run_workflow(
        workflow="planner",
        inputs={
            "goal": "Ship the marketing page.",
            "context": None,
            "max_steps": 10,
        },
        run_id="run-capture-off",
    )

    assert result["status"] == "pending"
    assert not evals_root.exists()

    # Direct unit assertion on the wiring helpers — env unset → None →
    # configurable dict does not carry the key.
    assert (
        _build_eval_capture_callback(
            workflow="planner",
            run_id="run-capture-off",
        )
        is None
    )
    cfg = _build_cfg(
        run_id="run-capture-off",
        workflow="planner",
        tier_registry={},
        callback=None,  # type: ignore[arg-type]  # helper tolerates None here in this unit assertion
        storage=None,  # type: ignore[arg-type]
        eval_capture_callback=None,
    )
    assert "eval_capture_callback" not in cfg["configurable"]


@pytest.mark.asyncio
async def test_capture_does_not_affect_run_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-4 (dispatch-level): approve-path result shape is identical with/without capture."""

    evals_root = tmp_path / "evals"
    monkeypatch.setenv("AIW_EVALS_ROOT", str(evals_root))

    # First run — capture off.
    monkeypatch.delenv("AIW_CAPTURE_EVALS", raising=False)
    _seed_planner_script()
    baseline = await run_workflow(
        workflow="planner",
        inputs={
            "goal": "Ship the marketing page.",
            "context": None,
            "max_steps": 10,
        },
        run_id="run-shape-baseline",
    )

    # Second run — capture on; identical inputs + stub outputs.
    monkeypatch.setenv("AIW_CAPTURE_EVALS", "testsuite")
    _seed_planner_script()
    captured = await run_workflow(
        workflow="planner",
        inputs={
            "goal": "Ship the marketing page.",
            "context": None,
            "max_steps": 10,
        },
        run_id="run-shape-captured",
    )

    assert set(baseline) == set(captured)
    assert baseline["status"] == captured["status"]
    assert baseline["awaiting"] == captured["awaiting"]
    assert baseline["plan"] == captured["plan"]
    assert baseline["total_cost_usd"] == pytest.approx(captured["total_cost_usd"])
    assert baseline["error"] == captured["error"]
