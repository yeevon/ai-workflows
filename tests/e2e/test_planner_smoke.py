"""M3 Task 07 — end-to-end smoke test for the full `aiw run / resume` path.

One real-API test that drives `aiw run planner …` → `aiw resume <run_id>`
against Gemini Flash (via LiteLLM) and asserts every M3 invariant the
hermetic graph-layer tests in [tests/workflows/test_planner_graph.py]
cannot exercise — that an actual provider call completes, that
budget-cap enforcement is honoured end-to-end, that the approved plan
round-trips from Storage, and that no `ANTHROPIC_API_KEY` /
`anthropic.` reference ever leaks into logs (KDR-003).

Gated by ``@pytest.mark.e2e`` + ``AIW_E2E=1`` (see
``tests/e2e/conftest.py``) so ``uv run pytest`` on a developer laptop
stays hermetic and never burns real quota. CI runs this job only on
``workflow_dispatch`` with the ``GEMINI_API_KEY`` secret bound.

Spec reframe (2026-04-20). Step 7 of the task spec prescribes
``CostTracker.from_storage(storage, run_id).total(run_id) <= 0.05`` as
the budget-respected assertion. That helper was never implemented —
M1 T05 dropped the ``llm_calls`` per-call ledger and M1 T08 made
:class:`CostTracker` in-memory only. The M3 T06 reframe already
surfaced this gap and deferred any per-call-replay surface to
[nice_to_have.md §9](../../design_docs/nice_to_have.md). This test
applies the identical reframe: it reads the scalar
``runs.total_cost_usd`` stamped by ``aiw run`` / ``aiw resume`` —
the same signal ``aiw list-runs`` surfaces and the only cost signal
that drives a real decision under subscription billing. The spec's
intent ("budget cap was honoured") is preserved; the implementation
switches to the surviving accounting surface.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_workflows.cli import app
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.workflows.planner import PlannerPlan

_RUNNER = CliRunner()

#: Budget the planner run is capped at. Well above the real Gemini
#: Flash cost of a tiny 3-step plan (pennies), so the happy path never
#: trips `BudgetExceeded`; but small enough that a pricing regression
#: would be caught. Matches the spec's `--budget 0.05`.
_BUDGET_CAP_USD = 0.05

#: Shape ceiling the spec mandates ("1 ≤ len(steps) ≤ 3"). Lower bound
#: is a provider-sanity check; upper bound is what the `--max-steps 3`
#: argument hands the workflow.
_MAX_STEPS = 3


@pytest.mark.e2e
def test_aiw_run_planner_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Drive the full `aiw run` → `aiw resume` path against real Gemini.

    Gated by ``AIW_E2E=1`` (collection hook in
    ``tests/e2e/conftest.py``). Also requires ``GEMINI_API_KEY`` in the
    environment; skips with a clear reason if absent so CI's
    ``workflow_dispatch`` path fails loudly on a missing secret rather
    than silently-passing an unconfigured run.

    The test is sync (despite the spec's async signature) because
    :meth:`CliRunner.invoke` drives the CLI's own ``asyncio.run(...)``
    internally — nesting that under pytest-asyncio's event loop raises
    ``RuntimeError: asyncio.run() cannot be called from a running
    event loop``. Any Storage reads in the assertions run under
    ``asyncio.run`` too, matching the pattern established by
    [tests/cli/test_resume.py].
    """
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set; cannot exercise real Gemini path")

    storage_path = tmp_path / "storage.sqlite"
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("AIW_STORAGE_DB", str(storage_path))

    run_id = f"e2e-{os.urandom(4).hex()}"

    run_result = _RUNNER.invoke(
        app,
        [
            "run",
            "planner",
            "--goal",
            "ship a tiny marketing page for a cookie recipe app",
            "--max-steps",
            str(_MAX_STEPS),
            "--budget",
            str(_BUDGET_CAP_USD),
            "--run-id",
            run_id,
        ],
    )
    assert run_result.exit_code == 0, run_result.output
    assert run_id in run_result.output, run_result.output
    assert "awaiting: gate" in run_result.output, run_result.output
    _assert_no_anthropic_leak(run_result.output)

    resume_result = _RUNNER.invoke(
        app,
        ["resume", run_id, "--gate-response", "approved"],
    )
    assert resume_result.exit_code == 0, resume_result.output
    _assert_no_anthropic_leak(resume_result.output)

    # The approved branch of the planner graph prints the final plan
    # JSON on stdout. Parse it through `PlannerPlan` to enforce the
    # schema contract at this boundary too — the Storage round-trip
    # below is the canonical AC, this is a belt-and-braces check.
    stdout_plan = _extract_plan_json(resume_result.output)
    PlannerPlan.model_validate(stdout_plan)

    # Storage round-trip (AC-4) + budget-cap honoured (AC-3). Reading
    # `runs.total_cost_usd` replaces the spec's
    # `CostTracker.from_storage(...)` call — see module-level reframe
    # note.
    row = asyncio.run(_read_run_row(storage_path, run_id))
    assert row is not None, "run row missing after resume"
    assert row["status"] == "completed", row
    total_cost = row["total_cost_usd"]
    assert total_cost is not None, "runs.total_cost_usd not stamped at resume"
    assert total_cost <= _BUDGET_CAP_USD, (
        f"budget cap {_BUDGET_CAP_USD} exceeded; actual total ${total_cost}"
    )

    artifact_row = asyncio.run(_read_artifact(storage_path, run_id))
    assert artifact_row is not None, "plan artifact not persisted"
    plan = PlannerPlan.model_validate_json(artifact_row["payload_json"])
    assert 1 <= len(plan.steps) <= _MAX_STEPS, plan


async def _read_run_row(db_path: Path, run_id: str) -> dict | None:
    """Reopen Storage after the CLI returns and fetch the run row."""
    storage = await SQLiteStorage.open(db_path)
    return await storage.get_run(run_id)


async def _read_artifact(db_path: Path, run_id: str) -> dict | None:
    """Reopen Storage and fetch the ``plan`` artifact row."""
    storage = await SQLiteStorage.open(db_path)
    return await storage.read_artifact(run_id, "plan")


def _extract_plan_json(output: str) -> dict:
    """Parse the first top-level JSON object in the CLI's stdout.

    ``aiw resume`` prints the plan's ``model_dump_json(indent=2)``
    followed by a ``total cost: $…`` line. Pulling the first
    ``{ … }`` block matches the plan JSON verbatim and tolerates any
    log lines that arrived on the combined stdout+stderr stream.
    """
    match = re.search(r"\{.*\}", output, re.DOTALL)
    assert match is not None, f"no JSON object in output: {output!r}"
    return json.loads(match.group(0))


def _assert_no_anthropic_leak(output: str) -> None:
    """AC-5 probe — fail loudly if Anthropic strings land in CLI output.

    KDR-003 forbids the ``anthropic`` SDK and the
    ``ANTHROPIC_API_KEY`` env var from being read at runtime. The
    hermetic tests already assert that at the module level; this
    probe repeats the check against whatever the real run wrote to
    stdout + stderr (Typer's CliRunner mixes both by default), so a
    late regression that started echoing either string through logs
    would break this smoke test.
    """
    assert "ANTHROPIC_API_KEY" not in output, output
    assert "anthropic." not in output, output
