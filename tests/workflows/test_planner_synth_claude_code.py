"""Hermetic tests for the M5 Task 02 Claude Code planner tier refit.

Repoints the ``planner-synth`` tier to ``ClaudeCodeRoute(cli_model_flag="opus")``
and validates the ``modelUsage`` sub-model rollup path end-to-end
through the graph's ``CostTrackingCallback``. The Claude Code CLI
subprocess is stubbed; the LiteLLM explorer tier keeps its stub from
``tests/workflows/test_planner_explorer_qwen.py``.

Covers:

* Production tier registry reflects ``ClaudeCodeRoute(cli_model_flag="opus")``
  + ``max_concurrency=1`` + ``per_call_timeout_s=300``.
* Full graph run with Qwen-shape explorer (LiteLLM stub) + Opus+Haiku
  ``modelUsage`` (Claude Code subprocess stub) lands at the gate with
  a valid ``PlannerPlan``.
* ``TokenUsage.sub_models`` is non-empty on the planner call; primary +
  sub rollup equals ``runs.total_cost_usd``.
* KDR-003 regression: no ``anthropic`` SDK import / ``ANTHROPIC_API_KEY``
  read in ``planner.py`` or ``claude_code.py`` at import-line level.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from ai_workflows import workflows
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.graph.checkpointer import build_async_checkpointer
from ai_workflows.graph.cost_callback import CostTrackingCallback
from ai_workflows.primitives.cost import CostTracker, TokenUsage
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.tiers import (
    ClaudeCodeRoute,
    LiteLLMRoute,
    ModelPricing,
)
from ai_workflows.workflows.planner import (
    ExplorerReport,
    PlannerInput,
    PlannerPlan,
    build_planner,
    planner_tier_registry,
)

# ---------------------------------------------------------------------------
# Stubs: LiteLLM (explorer) + ClaudeCodeSubprocess (synth)
# ---------------------------------------------------------------------------


class _StubLiteLLMAdapter:
    """Scripted LiteLLM stub — explorer tier only in T02's tests."""

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
            raise AssertionError("litellm stub script exhausted")
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


class _StubClaudeCodeSubprocess:
    """Claude Code subprocess stub that returns a pre-built TokenUsage.

    Unlike ``_StubLiteLLMAdapter`` (which reports a flat cost), this stub
    reports a ``TokenUsage`` tree — primary Opus call + one Haiku
    sub-model row — so the test exercises ``CostTracker``'s recursive
    rollup (``_roll_cost``) via the graph's ``CostTrackingCallback``.
    """

    script: list[tuple[str, TokenUsage]] = []
    call_count: int = 0

    def __init__(
        self,
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
        if not _StubClaudeCodeSubprocess.script:
            raise AssertionError("claude_code stub script exhausted")
        return _StubClaudeCodeSubprocess.script.pop(0)

    @classmethod
    def reset(cls) -> None:
        cls.script = []
        cls.call_count = 0


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
def _reensure_planner_registered() -> Iterator[None]:
    workflows._reset_for_tests()
    workflows.register("planner", build_planner)
    yield


async def _build_config(
    tmp_path: Path, run_id: str
) -> tuple[dict[str, Any], CostTracker, SQLiteStorage]:
    """Use the production tier registry directly — this test pins its shape."""
    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await storage.create_run(run_id, "planner", None)
    tracker = CostTracker()
    callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=None)
    cfg = {
        "configurable": {
            "thread_id": run_id,
            "run_id": run_id,
            "tier_registry": planner_tier_registry(),
            "cost_callback": callback,
            "storage": storage,
            "workflow": "planner",
            # The subprocess stub ignores pricing, but tiered_node reads
            # it out of configurable for ClaudeCodeRoute dispatch — pass
            # an empty dict to satisfy the contract.
            "pricing": {},
        }
    }
    return cfg, tracker, storage


def _qwen_shape_explorer_json() -> str:
    return json.dumps(
        {
            "summary": "Three-step static hero delivery.",
            "considerations": ["Copy tone", "CTA placement", "Mobile layout"],
            "assumptions": ["Design tokens frozen"],
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


def _opus_with_haiku_usage() -> TokenUsage:
    """Primary Opus row + one Haiku sub-model row (auto-classifier shape).

    Cost contributions (chosen to make the total unambiguous):
      primary Opus: 0.0200
      sub Haiku:    0.0004
      rollup:       0.0204
    """
    return TokenUsage(
        input_tokens=400,
        output_tokens=850,
        cost_usd=0.0200,
        model="claude-opus-4-7",
        sub_models=[
            TokenUsage(
                input_tokens=120,
                output_tokens=40,
                cost_usd=0.0004,
                model="claude-haiku-4-5",
            )
        ],
    )


# ---------------------------------------------------------------------------
# AC: tier registry
# ---------------------------------------------------------------------------


def test_planner_synth_tier_points_at_claude_code_opus() -> None:
    """AC-1: ``planner-synth`` route + cli flag + concurrency + timeout."""
    registry = planner_tier_registry()
    synth = registry["planner-synth"]
    assert isinstance(synth.route, ClaudeCodeRoute)
    assert synth.route.cli_model_flag == "opus"
    assert synth.max_concurrency == 1
    assert synth.per_call_timeout_s == 300


def test_planner_explorer_tier_kept_on_qwen_after_t02() -> None:
    """T02 must not clobber T01's explorer tier repoint."""
    registry = planner_tier_registry()
    explorer = registry["planner-explorer"]
    assert isinstance(explorer.route, LiteLLMRoute)
    assert explorer.route.model == "ollama/qwen2.5-coder:32b"


# ---------------------------------------------------------------------------
# AC: hermetic graph run + modelUsage sub-model rollup
# ---------------------------------------------------------------------------


async def test_graph_completes_with_claude_code_synth_and_rolls_up_submodels(
    tmp_path: Path,
) -> None:
    """AC-2 + AC-3: Qwen explorer + Claude Code synth complete to the gate;
    primary + sub-model cost both land in the per-run ``CostTracker``.
    """
    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_planner().compile(checkpointer=checkpointer)

    _StubLiteLLMAdapter.script = [
        (_qwen_shape_explorer_json(), 0.0),  # Ollama → cost 0.
    ]
    _StubClaudeCodeSubprocess.script = [
        (_valid_plan_json(), _opus_with_haiku_usage()),
    ]

    cfg, tracker, storage = await _build_config(tmp_path, "run-m5-t02")
    try:
        paused = await app.ainvoke(
            {
                "run_id": "run-m5-t02",
                "input": PlannerInput(
                    goal="Ship the marketing page.",
                    context="Hero + single CTA.",
                    max_steps=5,
                ),
            },
            cfg,
        )
        assert "__interrupt__" in paused
        assert isinstance(paused["explorer_report"], ExplorerReport)
        assert isinstance(paused["plan"], PlannerPlan)
        assert _StubLiteLLMAdapter.call_count == 1
        assert _StubClaudeCodeSubprocess.call_count == 1

        # AC-3: sub_models non-empty for the Claude Code entry; rollup
        # equals primary + sub (0.0200 + 0.0004 = 0.0204).
        assert tracker.total("run-m5-t02") == pytest.approx(0.0204)

        by_model = tracker.by_model("run-m5-t02")
        assert by_model.get("claude-opus-4-7") == pytest.approx(0.0200)
        assert by_model.get("claude-haiku-4-5") == pytest.approx(0.0004)
    finally:
        await checkpointer.conn.close()
        del storage


# ---------------------------------------------------------------------------
# AC: KDR-003 regression — no Anthropic SDK surface
# ---------------------------------------------------------------------------


_ANTHROPIC_IMPORT_RE = re.compile(
    r"^\s*(?:import\s+anthropic|from\s+anthropic\b)", re.MULTILINE
)


def test_no_anthropic_sdk_import_in_planner_or_claude_code_driver() -> None:
    """KDR-003: neither planner.py nor claude_code.py imports the SDK.

    Match at the start-of-line import-statement level to avoid false
    positives on module docstrings / CHANGELOG-style prose that
    reference the prohibition by name.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    files = [
        repo_root / "ai_workflows" / "workflows" / "planner.py",
        repo_root / "ai_workflows" / "primitives" / "llm" / "claude_code.py",
    ]
    for path in files:
        source = path.read_text(encoding="utf-8")
        assert _ANTHROPIC_IMPORT_RE.search(source) is None, (
            f"KDR-003 violated: anthropic SDK import found in {path}"
        )
        assert "ANTHROPIC_API_KEY" not in source, (
            f"KDR-003 violated: ANTHROPIC_API_KEY referenced in {path}"
        )
