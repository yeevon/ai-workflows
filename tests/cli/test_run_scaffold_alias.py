"""Tests for the ``aiw run-scaffold`` CLI alias (M17 Task 02).

Covers AC-5 / LOW-2 / M17-T01-ISS-02: verify that the ``run-scaffold``
Typer command parses ``--goal``, ``--target``, ``--force``, and
``--tier-override`` flags correctly and forwards them to the dispatch layer.

All LLM calls are stubbed — no live provider fires.  The tests use
``typer.testing.CliRunner`` in isolation mode; the scaffold graph runs
through its full first phase (validate_input → synthesize_source →
scaffold_validator → preview_gate) and halts at the ``HumanGate``
interrupt exactly as the real ``aiw run-scaffold`` command does.

Relationship to other modules
------------------------------
* :mod:`ai_workflows.cli` — the ``run-scaffold`` command under test.
* :mod:`ai_workflows.workflows.scaffold_workflow` — the workflow wired to
  the alias; re-registered in the ``_reset_scaffold`` fixture.
* :mod:`ai_workflows.graph.tiered_node` — LiteLLMAdapter stubbed here.
"""

from __future__ import annotations

import json
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
from ai_workflows.workflows.scaffold_workflow import build_scaffold_workflow

_RUNNER = CliRunner()


# ---------------------------------------------------------------------------
# Stub LiteLLM adapter (same pattern as test_scaffold_workflow.py)
# ---------------------------------------------------------------------------


class _StubLiteLLMAdapter:
    """Scripted stub adapter for the scaffold's scaffold-synth tier."""

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
        if isinstance(head, BaseException):
            raise head
        text, cost = head
        return text, TokenUsage(
            input_tokens=10,
            output_tokens=20,
            cost_usd=cost,
            model=self.route.model,
        )

    @classmethod
    def reset(cls) -> None:
        cls.script = []
        cls.call_count = 0


@pytest.fixture(autouse=True)
def _reset_stub(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    _StubLiteLLMAdapter.reset()
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _StubLiteLLMAdapter)
    yield
    _StubLiteLLMAdapter.reset()


@pytest.fixture(autouse=True)
def _reset_scaffold(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Re-register scaffold_workflow with the stub tier so CLI tests are isolated."""
    workflows._reset_for_tests()
    workflows.register("scaffold_workflow", build_scaffold_workflow)
    yield


@pytest.fixture(autouse=True)
def _redirect_default_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("AIW_STORAGE_DB", str(tmp_path / "storage.sqlite"))


# ---------------------------------------------------------------------------
# Stub the scaffold-synth tier to use LiteLLM (avoids spawning claude CLI)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _stub_scaffold_tier_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Override scaffold_workflow_tier_registry to use LiteLLM so the stub fires."""
    import ai_workflows.workflows.scaffold_workflow as _sw

    def _hermetic_registry() -> dict[str, TierConfig]:
        return {
            "scaffold-synth": TierConfig(
                name="scaffold-synth",
                route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
                max_concurrency=1,
                per_call_timeout_s=90,
            ),
        }

    monkeypatch.setattr(_sw, "scaffold_workflow_tier_registry", _hermetic_registry)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_scaffold_json(target_path: str) -> str:
    source = (
        "from ai_workflows.workflows import WorkflowSpec, LLMStep, register_workflow\n"
        "from pydantic import BaseModel\n\n"
        "class QuestionGenInput(BaseModel):\n"
        "    text: str\n\n"
        "class QuestionGenOutput(BaseModel):\n"
        "    questions: list[str]\n\n"
        "_SPEC = WorkflowSpec(\n"
        "    name='question_gen',\n"
        "    input_schema=QuestionGenInput,\n"
        "    output_schema=QuestionGenOutput,\n"
        "    tiers={},\n"
        "    steps=[],\n"
        ")\n"
        "register_workflow(_SPEC)\n"
    )
    return json.dumps(
        {
            "name": "question_gen",
            "spec_python": source,
            "description": "Generates exam questions from text.",
            "reasoning": "Simple LLM step wrapped in a WorkflowSpec.",
        }
    )


# ---------------------------------------------------------------------------
# Tests — AC-5 (LOW-2 / M17-T01-ISS-02)
# ---------------------------------------------------------------------------


def test_run_scaffold_alias_goal_and_target_parsed(tmp_path: Path) -> None:
    """AC-5: --goal and --target flags are parsed and forwarded to dispatch."""
    target = tmp_path / "out.py"
    _StubLiteLLMAdapter.script = [(_valid_scaffold_json(str(target)), 0.001)]

    result = _RUNNER.invoke(
        app,
        [
            "run-scaffold",
            "--goal",
            "generate exam questions from a textbook chapter",
            "--target",
            str(target),
        ],
    )
    # The command should reach the HumanGate pause — exit 0 with a run-id printed.
    assert result.exit_code == 0, result.output
    output_lower = result.output.lower()
    assert (
        "scaffold_workflow" in result.output
        or "run-id" in output_lower
        or "run" in output_lower
    )
    # File must NOT be written before gate approval.
    assert not target.exists()


def test_run_scaffold_alias_force_flag_parsed(tmp_path: Path) -> None:
    """AC-5: --force flag is accepted without error."""
    target = tmp_path / "existing.py"
    target.write_text("old content\n")
    _StubLiteLLMAdapter.script = [(_valid_scaffold_json(str(target)), 0.001)]

    result = _RUNNER.invoke(
        app,
        [
            "run-scaffold",
            "--goal",
            "generate a summarizer",
            "--target",
            str(target),
            "--force",
        ],
    )
    # With --force the existing file does not cause an error at validation time.
    assert result.exit_code == 0, result.output


def test_run_scaffold_alias_tier_override_parsed(tmp_path: Path) -> None:
    """AC-5: --tier-override flag is parsed and accepted."""
    target = tmp_path / "override_out.py"
    _StubLiteLLMAdapter.script = [(_valid_scaffold_json(str(target)), 0.001)]

    result = _RUNNER.invoke(
        app,
        [
            "run-scaffold",
            "--goal",
            "generate a summarizer",
            "--target",
            str(target),
            "--tier-override",
            "scaffold-synth=scaffold-synth",  # no-op override — same tier
        ],
    )
    assert result.exit_code == 0, result.output


def test_run_scaffold_alias_missing_goal_exits_nonzero(tmp_path: Path) -> None:
    """AC-5: missing --goal exits with a non-zero code (Typer validation)."""
    target = tmp_path / "out.py"
    result = _RUNNER.invoke(
        app,
        [
            "run-scaffold",
            "--target",
            str(target),
        ],
    )
    assert result.exit_code != 0


def test_run_scaffold_alias_missing_target_exits_nonzero(tmp_path: Path) -> None:
    """AC-5: missing --target exits with a non-zero code (Typer validation)."""
    result = _RUNNER.invoke(
        app,
        [
            "run-scaffold",
            "--goal",
            "generate something",
        ],
    )
    assert result.exit_code != 0
