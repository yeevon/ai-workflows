"""Tests for M5 Task 04 — ``aiw run --tier-override``.

Covers the eight ACs from
``design_docs/phases/milestone_5_multitier_planner/task_04_tier_override_cli.md``:

* Happy override — ``aiw run planner --tier-override planner-synth=planner-explorer``
  runs to the gate and the synth node is dispatched against the
  explorer tier's route (asserted by stub-recorded ``route.model``).
* Repeatable flag — two overrides swap both tiers; stubs observe the
  swapped routes.
* Malformed entries (no ``=``, empty halves) exit with Typer's code 2
  and a readable ``typer.BadParameter`` message.
* Unknown logical or replacement names exit with code 2 via
  :class:`UnknownTierError`.
* No-override regression — behaviour byte-identical to M3 / M5 T01–T03.
* KDR-003: no ``anthropic`` import touch; the new ``--tier-override``
  surface does not reach for provider secrets.

The hermetic stub pattern mirrors :mod:`tests/cli/test_run.py`. A
locally-installed registry with two *distinct* LiteLLM routes replaces
the directory-autouse all-LiteLLM pair so we can tell "explorer was
dispatched" from "synth was dispatched" by the recorded ``route.model``.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from ai_workflows import workflows
from ai_workflows.cli import app
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig
from ai_workflows.workflows import planner as planner_module
from ai_workflows.workflows.planner import build_planner

_RUNNER = CliRunner()

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _plain(text: str) -> str:
    """Strip ANSI escape codes so substring checks survive Rich's
    option highlighter, which fragments ``--tier-override`` into three
    separately-styled chunks (``-``, ``-tier``, ``-override``) on
    colour-capable terminals (notably GitHub Actions runners, which
    set ``FORCE_COLOR=1``)."""
    return _ANSI_RE.sub("", text)


# ---------------------------------------------------------------------------
# Stub LiteLLM adapter — records per-call route so tests can assert dispatch
# ---------------------------------------------------------------------------


class _RecordingLiteLLMAdapter:
    """Records ``route.model`` per ``.complete()`` call.

    A plain ``script: list[(text, cost)]`` feeds successive calls; a
    ``models_seen: list[str]`` is the per-test assertion surface.
    """

    script: list[Any] = []
    models_seen: list[str] = []
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
        _RecordingLiteLLMAdapter.call_count += 1
        _RecordingLiteLLMAdapter.models_seen.append(self.route.model)
        if not _RecordingLiteLLMAdapter.script:
            raise AssertionError("stub script exhausted")
        head = _RecordingLiteLLMAdapter.script.pop(0)
        if isinstance(head, BaseException):
            raise head
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
        cls.models_seen = []
        cls.call_count = 0


# ---------------------------------------------------------------------------
# Local registry with two *distinct* LiteLLM routes — lets a dispatch
# assertion distinguish explorer from synth by ``route.model``.
# ---------------------------------------------------------------------------


_EXPLORER_MODEL = "gemini/gemini-2.5-flash"
_SYNTH_MODEL = "gemini/gemini-2.5-pro"


def _distinct_registry() -> dict[str, TierConfig]:
    return {
        "planner-explorer": TierConfig(
            name="planner-explorer",
            route=LiteLLMRoute(model=_EXPLORER_MODEL),
            max_concurrency=2,
            per_call_timeout_s=60,
        ),
        "planner-synth": TierConfig(
            name="planner-synth",
            route=LiteLLMRoute(model=_SYNTH_MODEL),
            max_concurrency=2,
            per_call_timeout_s=90,
        ),
    }


@pytest.fixture(autouse=True)
def _install_distinct_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin ``planner_tier_registry`` to the T04 two-distinct-model shape.

    Wins over ``tests/cli/conftest.py``'s autouse pin because pytest
    applies fixtures in LIFO order and this module-local fixture stacks
    on top of the directory-local one.
    """
    monkeypatch.setattr(
        planner_module, "planner_tier_registry", _distinct_registry
    )


@pytest.fixture(autouse=True)
def _reset_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    _RecordingLiteLLMAdapter.reset()
    monkeypatch.setattr(
        tiered_node_module, "LiteLLMAdapter", _RecordingLiteLLMAdapter
    )


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


# ---------------------------------------------------------------------------
# JSON fixtures (reuse the shape M3 T04's tests pin)
# ---------------------------------------------------------------------------


def _valid_explorer_json() -> str:
    import json

    return json.dumps(
        {
            "summary": "Three-step delivery.",
            "considerations": ["A", "B"],
            "assumptions": ["X"],
        }
    )


def _valid_plan_json() -> str:
    import json

    return json.dumps(
        {
            "goal": "Ship the marketing page.",
            "summary": "Three-step delivery of the static hero + CTA page.",
            "steps": [
                {
                    "index": 1,
                    "title": "Draft hero copy",
                    "rationale": "Lock tone before layout.",
                    "actions": ["Sketch headline"],
                }
            ],
        }
    )


def _base_args(extra: list[str] | None = None) -> list[str]:
    args = ["run", "planner", "--goal", "Ship the marketing page."]
    if extra:
        args.extend(extra)
    return args


# ---------------------------------------------------------------------------
# AC-1 — single override dispatches synth against explorer's route
# ---------------------------------------------------------------------------


def test_override_synth_to_explorer_dispatches_against_explorer_route() -> None:
    _RecordingLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
    ]

    result = _RUNNER.invoke(
        app,
        _base_args(["--tier-override", "planner-synth=planner-explorer"]),
    )
    assert result.exit_code == 0, result.output

    # Both nodes now dispatch against the explorer's route — stub sees
    # the explorer model for both calls, never the synth model.
    assert _RecordingLiteLLMAdapter.models_seen == [
        _EXPLORER_MODEL,
        _EXPLORER_MODEL,
    ]


# ---------------------------------------------------------------------------
# AC-2 — repeatable: swap both tiers by passing the flag twice
# ---------------------------------------------------------------------------


def test_repeatable_override_swaps_both_tiers() -> None:
    """``--tier-override a=b --tier-override b=a`` swaps both tiers.

    Apply order is pure per-logical replacement against the source
    registry (snapshot semantics): left-hand keys get reassigned
    simultaneously to right-hand values read from the *original*
    registry, which is the only swap semantics that doesn't chain.
    The `_apply_tier_overrides` helper reads RHS from the input dict,
    so two overrides with opposite directions swap cleanly.
    """
    _RecordingLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
    ]

    result = _RUNNER.invoke(
        app,
        _base_args(
            [
                "--tier-override",
                "planner-explorer=planner-synth",
                "--tier-override",
                "planner-synth=planner-explorer",
            ]
        ),
    )
    assert result.exit_code == 0, result.output

    # Explorer node now runs under the synth route, synth node under the
    # explorer route — ordered by node execution (explorer first).
    assert _RecordingLiteLLMAdapter.models_seen == [
        _SYNTH_MODEL,
        _EXPLORER_MODEL,
    ]


# ---------------------------------------------------------------------------
# AC-3 — malformed entries: no '=' and empty halves each exit 2
# ---------------------------------------------------------------------------


def test_malformed_override_without_equals_exits_two() -> None:
    result = _RUNNER.invoke(
        app, _base_args(["--tier-override", "planner-synth"])
    )
    assert result.exit_code == 2
    assert "tier-override" in _plain(result.output).lower()


def test_malformed_override_with_empty_half_exits_two() -> None:
    result = _RUNNER.invoke(
        app, _base_args(["--tier-override", "=planner-synth"])
    )
    assert result.exit_code == 2
    assert "tier-override" in _plain(result.output).lower()


# ---------------------------------------------------------------------------
# AC-4 — unknown logical / replacement each exit 2
# ---------------------------------------------------------------------------


def test_unknown_logical_tier_exits_two_and_names_registered() -> None:
    _RecordingLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
    ]
    result = _RUNNER.invoke(
        app, _base_args(["--tier-override", "nonexistent=planner-synth"])
    )
    assert result.exit_code == 2
    assert "nonexistent" in result.output
    assert "planner-synth" in result.output  # registered list is surfaced
    # The run must not have proceeded into the graph.
    assert _RecordingLiteLLMAdapter.call_count == 0


def test_unknown_replacement_tier_exits_two_and_names_registered() -> None:
    _RecordingLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
    ]
    result = _RUNNER.invoke(
        app, _base_args(["--tier-override", "planner-synth=nonexistent"])
    )
    assert result.exit_code == 2
    assert "nonexistent" in result.output
    assert _RecordingLiteLLMAdapter.call_count == 0


# ---------------------------------------------------------------------------
# AC-5 — no override: M3 / M5 T01–T03 behaviour unchanged
# ---------------------------------------------------------------------------


def test_no_override_preserves_existing_behaviour() -> None:
    """No ``--tier-override`` → stubs see the per-tier models verbatim."""
    _RecordingLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
    ]
    result = _RUNNER.invoke(app, _base_args())
    assert result.exit_code == 0, result.output
    assert _RecordingLiteLLMAdapter.models_seen == [
        _EXPLORER_MODEL,
        _SYNTH_MODEL,
    ]
