"""Tests for M3 Task 04 — ``aiw run``.

Covers the acceptance criteria from
``design_docs/phases/milestone_3_first_workflow/task_04_cli_run.md``:

* Happy gate-interrupt path — prints the run id + the exact
  ``aiw resume`` command the user needs.
* ULID-shape auto-generated run id.
* ``Storage.create_run`` is called exactly once per invocation.
* Unknown workflow exits with code 2 and names the registered set.
* Missing ``--goal`` exits with Typer's code 2.
* ``--budget`` cap is enforced end-to-end.
* KDR-003: the CLI module itself never reads ``GEMINI_API_KEY`` /
  ``ANTHROPIC_API_KEY``.

Every LLM call is stubbed at the adapter level so no real API fires.
``AIW_CHECKPOINT_DB`` + ``AIW_STORAGE_DB`` are redirected to
``tmp_path`` so the runs never touch ``~/.ai-workflows/``.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from ai_workflows import workflows
from ai_workflows.cli import _CROCKFORD, _generate_ulid, app
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.tiers import LiteLLMRoute
from ai_workflows.workflows.planner import build_planner

_RUNNER = CliRunner()


# ---------------------------------------------------------------------------
# Stub LiteLLM adapter (mirrors tests/workflows/test_planner_graph.py)
# ---------------------------------------------------------------------------


class _StubLiteLLMAdapter:
    """Scripted LiteLLM-adapter stub so no real HTTP call fires."""

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
    """Install the stub adapter and clear the script between tests."""
    _StubLiteLLMAdapter.reset()
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _StubLiteLLMAdapter)


@pytest.fixture(autouse=True)
def _reensure_planner_registered() -> Iterator[None]:
    """Keep ``workflows.get('planner')`` resolvable.

    ``tests/workflows/test_registry.py`` resets the registry between
    its tests via its own autouse fixture; re-register here so the CLI
    tests are self-contained regardless of collection order.
    """
    workflows._reset_for_tests()
    workflows.register("planner", build_planner)
    yield


@pytest.fixture(autouse=True)
def _redirect_default_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Route the default Storage + checkpointer paths under tmp_path.

    Without this the CLI's ``default_storage_path()`` would open a DB
    under ``~/.ai-workflows/storage.sqlite`` — acceptable for manual
    runs but not for an isolated test.
    """
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("AIW_STORAGE_DB", str(tmp_path / "storage.sqlite"))


# ---------------------------------------------------------------------------
# Fixtures — valid scripted JSON
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


# ---------------------------------------------------------------------------
# ULID-shape helper (unit test — no graph involved)
# ---------------------------------------------------------------------------


def test_generate_ulid_produces_26_crockford_chars() -> None:
    """``_generate_ulid`` returns 26 Crockford-base32 chars."""
    ulid = _generate_ulid()
    assert len(ulid) == 26
    assert re.fullmatch(rf"[{_CROCKFORD}]{{26}}", ulid)


def test_generate_ulid_is_unique_across_calls() -> None:
    """Two successive ids must differ (80-bit random tail dwarfs birthday odds)."""
    assert _generate_ulid() != _generate_ulid()


# ---------------------------------------------------------------------------
# Happy path — gate interrupt with auto-generated run id
# ---------------------------------------------------------------------------


def test_run_pauses_at_gate_and_prints_resume_command(tmp_path: Path) -> None:
    """AC: ``aiw run planner --goal 'x'`` runs to the gate and prints the
    run id + the exact resume command, auto-generating the run id, and
    calls ``Storage.create_run`` exactly once.
    """
    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
    ]

    result = _RUNNER.invoke(
        app,
        ["run", "planner", "--goal", "Ship the marketing page."],
    )
    assert result.exit_code == 0, result.output

    # First line is the run id; second names the gate; third is the
    # resume command — matches the contract the task spec pins.
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) >= 3, result.output
    run_id, awaiting, resume = lines[0], lines[1], lines[2]
    assert re.fullmatch(rf"[{_CROCKFORD}]{{26}}", run_id), run_id
    assert awaiting == "awaiting: gate"
    assert resume == (
        f"resume with: aiw resume {run_id} --gate-response <approved|rejected>"
    )

    # Storage got exactly one ``create_run`` — the row we want to see.
    storage_path = tmp_path / "storage.sqlite"
    assert storage_path.exists()
    row = _read_run_row(storage_path, run_id)
    assert row is not None
    assert row["workflow_id"] == "planner"
    assert row["status"] == "pending"


def _read_run_row(db_path: Path, run_id: str) -> dict[str, Any] | None:
    """Return the ``runs`` row for ``run_id`` via a fresh connection."""
    import sqlite3

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def test_run_respects_explicit_run_id_override() -> None:
    """AC: ``--run-id`` overrides the auto-generated ULID."""
    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
    ]
    result = _RUNNER.invoke(
        app,
        [
            "run",
            "planner",
            "--goal",
            "Ship the marketing page.",
            "--run-id",
            "run-explicit-1",
        ],
    )
    assert result.exit_code == 0, result.output
    first_line = result.stdout.splitlines()[0]
    assert first_line == "run-explicit-1"


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_run_unknown_workflow_exits_two_with_registered_list() -> None:
    """AC: ``aiw run unknown_workflow --goal 'x'`` exits 2 and lists
    registered workflows.
    """
    result = _RUNNER.invoke(
        app, ["run", "unknown_workflow", "--goal", "anything"]
    )
    assert result.exit_code == 2
    # The error message is written to stderr; the combined-output view
    # is what ``result.output`` exposes, so search there.
    assert "unknown workflow 'unknown_workflow'" in result.output
    assert "planner" in result.output


def test_run_missing_goal_exits_two() -> None:
    """AC: ``aiw run planner`` without ``--goal`` exits 2 (Typer convention)."""
    result = _RUNNER.invoke(app, ["run", "planner"])
    assert result.exit_code == 2


def test_run_budget_cap_breach_exits_nonzero_with_budget_message() -> None:
    """AC: ``--budget 0.00001`` trips the budget cap and surfaces a budget message.

    The first stubbed call's cost (``$0.0012``) is well above the
    ``$0.00001`` cap, so ``CostTrackingCallback.on_node_complete``
    raises ``NonRetryable('budget exceeded: ...')`` from inside the
    explorer node. ``wrap_with_error_handler`` writes that into state;
    the CLI pulls it back out of the checkpointed state when the
    downstream validator (reading the never-written ``explorer_output``)
    errors out.
    """
    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
        # Extra entries in case the graph cascades through retries;
        # exhausting the script would mask the budget signal with a
        # misleading AssertionError.
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
    ]
    result = _RUNNER.invoke(
        app,
        [
            "run",
            "planner",
            "--goal",
            "Ship the marketing page.",
            "--budget",
            "0.00001",
        ],
    )
    assert result.exit_code != 0, result.output
    assert "budget" in result.output.lower()


# ---------------------------------------------------------------------------
# KDR-003 — CLI never reads GEMINI_API_KEY / ANTHROPIC_API_KEY directly
# ---------------------------------------------------------------------------


def test_cli_module_does_not_read_provider_secrets() -> None:
    """AC: the CLI module does not reach for ``GEMINI_API_KEY`` or
    ``ANTHROPIC_API_KEY`` directly — secrets stay at the adapter
    boundary (KDR-003).
    """
    cli_source = (
        Path(__file__).resolve().parent.parent.parent
        / "ai_workflows"
        / "cli.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "GEMINI_API_KEY",
        "ANTHROPIC_API_KEY",
        "import anthropic",
        "from anthropic",
    ):
        assert forbidden not in cli_source, (
            f"KDR-003 violated: {forbidden!r} appears in cli.py"
        )
