"""M16 Task 01 — CLI round-trip test for an external workflow module.

Writes a stub workflow module to ``tmp_path``, prepends the dir to
``sys.path``, sets ``AIW_EXTRA_WORKFLOW_MODULES`` so the CLI root
callback imports it at startup, and runs ``aiw run <stub>`` end-to-end.
The stub graph is a single pass-through node — no LLM tier fires — so
the test is hermetic and deterministic. Verifies the full path:
env-var → loader → registry → dispatch → completion.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_workflows import workflows
from ai_workflows.cli import app

_RUNNER = CliRunner()

_STUB_WORKFLOW_SOURCE = """\
'''Stub external workflow for M16 T01 integration test.'''
from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from ai_workflows.workflows import register


FINAL_STATE_KEY = "plan"


class _StubState(TypedDict, total=False):
    run_id: str
    input: dict[str, Any]
    plan: dict[str, Any] | None


def initial_state(run_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
    return {"run_id": run_id, "input": dict(inputs), "plan": None}


def _finalize(state: _StubState) -> dict[str, Any]:
    goal = state.get("input", {}).get("goal", "")
    return {"plan": {"echo": goal}}


def build() -> StateGraph:
    g: StateGraph = StateGraph(_StubState)
    g.add_node("finalize", _finalize)
    g.add_edge(START, "finalize")
    g.add_edge("finalize", END)
    return g


def m16_ext_cli_stub_tier_registry() -> dict[str, Any]:
    return {}


register("m16_ext_cli_stub", build)
"""


@pytest.fixture
def _stub_external_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[str]:
    """Write + register the stub workflow on sys.path for this test."""
    stub_path = tmp_path / "m16_ext_cli_stub.py"
    stub_path.write_text(_STUB_WORKFLOW_SOURCE)
    monkeypatch.syspath_prepend(str(tmp_path))
    # Reset registry so a prior test's registrations don't leak in.
    workflows._reset_for_tests()
    yield "m16_ext_cli_stub"
    workflows._reset_for_tests()
    sys.modules.pop("m16_ext_cli_stub", None)


@pytest.fixture(autouse=True)
def _redirect_default_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Route Storage + checkpointer under tmp_path (same pattern as test_run.py)."""
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("AIW_STORAGE_DB", str(tmp_path / "storage.sqlite"))


def test_env_var_external_workflow_runs_end_to_end(
    _stub_external_workflow: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-1, AC-2, AC-9, AC-11: env-var path drives ``aiw run`` of an external workflow."""
    monkeypatch.setenv("AIW_EXTRA_WORKFLOW_MODULES", _stub_external_workflow)

    result = _RUNNER.invoke(
        app,
        ["run", _stub_external_workflow, "--goal", "hello world"],
    )

    assert result.exit_code == 0, result.output
    # The CLI emits the plan JSON followed by a total-cost line.
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    # The plan dict spans the first N lines (pretty-printed JSON); the
    # final line is "total cost: $0.0000".
    assert lines[-1].startswith("total cost:"), result.output
    plan_text = "\n".join(lines[:-1])
    plan = json.loads(plan_text)
    assert plan == {"echo": "hello world"}


def test_cli_flag_external_workflow_runs_end_to_end(
    _stub_external_workflow: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-3: ``--workflow-module`` flag (no env var) reaches the same surface."""
    monkeypatch.delenv("AIW_EXTRA_WORKFLOW_MODULES", raising=False)

    result = _RUNNER.invoke(
        app,
        [
            "--workflow-module",
            _stub_external_workflow,
            "run",
            _stub_external_workflow,
            "--goal",
            "cli-flag",
        ],
    )

    assert result.exit_code == 0, result.output
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    plan = json.loads("\n".join(lines[:-1]))
    assert plan == {"echo": "cli-flag"}


def test_bad_module_path_exits_two_with_actionable_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-5: a non-importable entry exits 2 with the module path + cause."""
    monkeypatch.setenv("AIW_EXTRA_WORKFLOW_MODULES", "_m16_nope_does_not_exist")

    result = _RUNNER.invoke(app, ["run", "planner", "--goal", "x"])

    assert result.exit_code == 2, result.output
    assert "_m16_nope_does_not_exist" in result.output
    assert "ModuleNotFoundError" in result.output
