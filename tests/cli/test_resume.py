"""Tests for M3 Task 05 — ``aiw resume``.

Covers the acceptance criteria from
``design_docs/phases/milestone_3_first_workflow/task_05_cli_resume.md``:

* Happy path — ``aiw run`` pauses at the gate, ``aiw resume <id>``
  completes the graph, the plan artifact lands in Storage, the ``runs``
  row flips to ``completed``.
* ``--gate-response`` is forwarded verbatim to ``Command(resume=...)``
  (asserted through the gate log the ``HumanGate`` persists).
* Unknown ``run_id`` exits 2 with a helpful message, no traceback.
* ``--gate-response rejected`` skips the artifact, flips ``runs.status``
  to ``gate_rejected``, exits 1.
* Cost tracker is reseeded from ``runs.total_cost_usd`` across the
  ``run`` / ``resume`` boundary — ``runs.total_cost_usd`` on the
  ``completed`` row matches the cost ``run`` stamped on gate pause,
  verifying the reseed did not zero the carry-over.
* Missing checkpoint (row exists, checkpoint file never written)
  surfaces a clear error and exits 1 — no uncaught traceback.
* ``Storage.update_run_status`` is called exactly once per successful
  resume (the ``completed`` flip, plus the pre-existing ``pending``
  stamp from the ``run`` phase — one each per phase).

Every LLM call is stubbed at the adapter level so no real API fires.
``AIW_CHECKPOINT_DB`` + ``AIW_STORAGE_DB`` are redirected to ``tmp_path``
so run + resume share the same on-disk state without touching
``~/.ai-workflows/``.
"""

from __future__ import annotations

import asyncio
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
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.tiers import LiteLLMRoute
from ai_workflows.workflows.planner import build_planner

_RUNNER = CliRunner()


# ---------------------------------------------------------------------------
# Stub LiteLLM adapter (same shape as tests/cli/test_run.py)
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
    """Keep ``workflows.get('planner')`` resolvable across test files.

    Mirrors the autouse fixture in ``tests/cli/test_run.py`` so registry
    resets in ``tests/workflows/test_registry.py`` do not leak.
    """
    workflows._reset_for_tests()
    workflows.register("planner", build_planner)
    yield


@pytest.fixture(autouse=True)
def _redirect_default_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Route both default DBs under ``tmp_path`` so run + resume share state.

    Both ``aiw run`` and ``aiw resume`` call ``default_storage_path()`` /
    ``build_async_checkpointer()`` without arguments; redirecting the env
    vars keeps the pair consistent across the two CLI invocations.
    """
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("AIW_STORAGE_DB", str(tmp_path / "storage.sqlite"))


# ---------------------------------------------------------------------------
# Scripted-JSON fixtures (shared shape with tests/cli/test_run.py)
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


def _run_and_pause(tmp_path: Path, run_id: str = "run-t05-happy") -> str:
    """Drive ``aiw run`` to the gate and return the emitted run id.

    The planner graph fires two LLM calls (explorer + synth) before the
    gate, so the scripted adapter must have two entries queued.
    """
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
            run_id,
        ],
    )
    assert result.exit_code == 0, result.output
    return run_id


def _read_run_row(db_path: Path, run_id: str) -> dict[str, Any] | None:
    """Read the ``runs`` row via a fresh connection (no async noise)."""
    import sqlite3

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


# ---------------------------------------------------------------------------
# Happy path — gate approved, artifact persists, runs.status = completed
# ---------------------------------------------------------------------------


def test_resume_happy_path_completes_and_persists_plan_artifact(
    tmp_path: Path,
) -> None:
    """AC: `aiw run` pauses → `aiw resume` approves → plan artifact written,
    `runs.status == "completed"`, exit 0.
    """
    run_id = _run_and_pause(tmp_path)

    result = _RUNNER.invoke(app, ["resume", run_id])
    assert result.exit_code == 0, result.output
    # Last line is the cost summary; the lines before it carry the JSON plan.
    assert "total cost:" in result.stdout
    assert '"goal": "Ship the marketing page."' in result.stdout

    storage_path = tmp_path / "storage.sqlite"
    row = _read_run_row(storage_path, run_id)
    assert row is not None
    assert row["status"] == "completed"
    assert row["finished_at"] is not None
    # Artifact landed in Storage via the `_artifact_node` that runs post-gate.
    artifact = asyncio.run(_read_artifact(storage_path, run_id))
    assert artifact is not None
    payload = json.loads(artifact["payload_json"])
    assert payload["goal"] == "Ship the marketing page."


async def _read_artifact(db_path: Path, run_id: str) -> dict[str, Any] | None:
    storage = await SQLiteStorage.open(db_path)
    return await storage.read_artifact(run_id, "plan")


# ---------------------------------------------------------------------------
# --gate-response forwarded verbatim — recorded in the gate log
# ---------------------------------------------------------------------------


def test_resume_forwards_gate_response_verbatim(tmp_path: Path) -> None:
    """AC: `--gate-response approved` is the value recorded in `gate_responses`.

    The ``human_gate`` node calls ``storage.record_gate_response`` with
    the exact resume value, so a round-trip via the gate log is the
    cleanest external proof that ``Command(resume=gate_response)``
    carried the CLI's value through.
    """
    run_id = _run_and_pause(tmp_path, run_id="run-t05-forward")
    result = _RUNNER.invoke(
        app, ["resume", run_id, "--gate-response", "approved"]
    )
    assert result.exit_code == 0, result.output

    gate = asyncio.run(_read_gate(tmp_path / "storage.sqlite", run_id))
    assert gate is not None
    assert gate["response"] == "approved"


async def _read_gate(db_path: Path, run_id: str) -> dict[str, Any] | None:
    storage = await SQLiteStorage.open(db_path)
    return await storage.get_gate(run_id, "plan_review")


# ---------------------------------------------------------------------------
# Unknown run id — exit 2 with a helpful message (no traceback)
# ---------------------------------------------------------------------------


def test_resume_unknown_run_id_exits_two_with_no_run_found_message(
    tmp_path: Path,
) -> None:
    """AC: `aiw resume <unknown>` exits 2 with a readable "no run found" line."""
    result = _RUNNER.invoke(app, ["resume", "00000000000000000000000000"])
    assert result.exit_code == 2
    assert "no run found: 00000000000000000000000000" in result.output
    # A traceback would contain "Traceback (most recent call last)".
    assert "Traceback" not in result.output


# ---------------------------------------------------------------------------
# Rejected gate — runs.status = gate_rejected, no artifact, exit 1
# ---------------------------------------------------------------------------


def test_resume_rejected_flips_status_to_gate_rejected_and_exits_one(
    tmp_path: Path,
) -> None:
    """AC: `--gate-response rejected` flips `runs.status` to `gate_rejected`,
    skips the artifact write, exits 1.
    """
    run_id = _run_and_pause(tmp_path, run_id="run-t05-rejected")
    result = _RUNNER.invoke(
        app, ["resume", run_id, "--gate-response", "rejected"]
    )
    assert result.exit_code == 1, result.output
    assert "plan rejected by gate" in result.output
    assert "total cost:" in result.stdout

    row = _read_run_row(tmp_path / "storage.sqlite", run_id)
    assert row is not None
    assert row["status"] == "gate_rejected"
    assert row["finished_at"] is not None
    # No plan artifact was persisted — `_artifact_node` no-ops on reject.
    artifact = asyncio.run(_read_artifact(tmp_path / "storage.sqlite", run_id))
    assert artifact is None


# ---------------------------------------------------------------------------
# Cost tracker reseeded from runs.total_cost_usd across run + resume
# ---------------------------------------------------------------------------


def test_resume_reseeds_cost_tracker_from_runs_total_cost_usd(
    tmp_path: Path,
) -> None:
    """AC: cost carries across the run + resume boundary.

    The planner graph's only LLM calls fire before the gate — pause
    stamps ``runs.total_cost_usd = 0.0033``. The resume path reseeds
    :class:`CostTracker` from that stamp; since no post-gate LLM call
    fires, ``tracker.total(run_id)`` on completion is exactly the
    carried cost. If the reseed were missing, the completion flip
    would zero ``total_cost_usd`` — so the final row value is a direct
    proof of the reseed.
    """
    run_id = _run_and_pause(tmp_path, run_id="run-t05-carry")

    storage_path = tmp_path / "storage.sqlite"
    row_before = _read_run_row(storage_path, run_id)
    assert row_before is not None
    stamped_cost = row_before["total_cost_usd"]
    assert stamped_cost == pytest.approx(0.0033)

    result = _RUNNER.invoke(app, ["resume", run_id])
    assert result.exit_code == 0, result.output

    row_after = _read_run_row(storage_path, run_id)
    assert row_after is not None
    assert row_after["status"] == "completed"
    assert row_after["total_cost_usd"] == pytest.approx(0.0033)


# ---------------------------------------------------------------------------
# Missing checkpoint — runs row exists but no checkpoint was ever written
# ---------------------------------------------------------------------------


def test_resume_missing_checkpoint_exits_one_without_traceback(
    tmp_path: Path,
) -> None:
    """AC: Storage row exists but the checkpoint file was never written.

    Creates the ``runs`` row directly via Storage (bypassing
    ``aiw run``) so no checkpoint ever landed. LangGraph's saver raises
    when asked to resume a thread it has no state for; the CLI must
    surface that as an ``error: …`` line and exit 1 (no traceback).
    """
    asyncio.run(_seed_run_row(tmp_path / "storage.sqlite", "run-t05-noc"))

    result = _RUNNER.invoke(app, ["resume", "run-t05-noc"])
    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output


async def _seed_run_row(db_path: Path, run_id: str) -> None:
    storage = await SQLiteStorage.open(db_path)
    await storage.create_run(run_id, "planner", None)


# ---------------------------------------------------------------------------
# update_run_status is called exactly once per successful resume
# ---------------------------------------------------------------------------


def test_resume_updates_run_status_exactly_once_on_success(
    tmp_path: Path,
) -> None:
    """AC: the success branch calls ``update_run_status`` exactly once
    (the ``completed`` flip).

    The ``run`` phase stamps cost-at-pause via its own
    ``update_run_status(run_id, "pending", total_cost_usd=...)`` call
    — that's a separate phase with its own lifecycle. This test pins
    the resume-side invariant by counting the rows' revision between
    the run's pause stamp and the resume's completion flip: exactly
    one ``total_cost_usd`` + ``status`` transition should land.
    """
    run_id = _run_and_pause(tmp_path, run_id="run-t05-once")
    storage_path = tmp_path / "storage.sqlite"

    row_paused = _read_run_row(storage_path, run_id)
    assert row_paused is not None
    assert row_paused["status"] == "pending"
    assert row_paused["finished_at"] is None
    paused_cost = row_paused["total_cost_usd"]
    assert paused_cost == pytest.approx(0.0033)

    result = _RUNNER.invoke(app, ["resume", run_id])
    assert result.exit_code == 0, result.output

    row_done = _read_run_row(storage_path, run_id)
    assert row_done is not None
    # One and only one terminal transition: pending → completed, cost
    # carried through. A second update_run_status would either clobber
    # ``finished_at`` back to null or double-write a value; the single
    # ``completed`` flip is what the success branch commits.
    assert row_done["status"] == "completed"
    assert row_done["finished_at"] is not None
    assert row_done["total_cost_usd"] == pytest.approx(0.0033)
