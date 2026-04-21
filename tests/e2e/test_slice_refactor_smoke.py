"""M6 Task 08 — live end-to-end smoke for ``slice_refactor`` (``AIW_E2E=1``).

Drives the full ``slice_refactor`` pipeline against **real** providers
— Qwen (local, via Ollama) for the ``planner-explorer`` +
``slice-worker`` tiers, Claude Code Opus (OAuth via the ``claude`` CLI
subprocess, KDR-003) for the ``planner-synth`` tier. Mirrors the
prerequisite + skip pattern from
:mod:`tests/e2e/test_planner_smoke.py`; the hermetic sibling at
:mod:`tests/workflows/test_slice_refactor_e2e.py` covers the same
pipeline against stubbed providers.

Gated by ``@pytest.mark.e2e`` + ``AIW_E2E=1`` (see
:mod:`tests/e2e/conftest.py`). Each missing prerequisite —
``ollama`` binary, Ollama daemon on ``localhost:11434``, ``claude``
CLI — skips with a readable reason rather than failing loudly, so
``workflow_dispatch`` surfaces real provider failures instead of
infrastructure misconfiguration.

Acceptance (from task_08_e2e_smoke.md):

* ``run_workflow(workflow='slice_refactor', …)`` pauses at the
  planner's plan-review gate.
* First resume continues to the outer (strict-review) gate with a
  ``SliceAggregate``.
* Second resume completes to ``runs.status == "completed"``.
* ``runs.total_cost_usd`` stamped and non-negative (Claude Code Opus on
  the Max subscription reports notional 0 — informational, not
  billable; match the M5 T06 posture).
* Artefact count in Storage equals the number of approved slices.
* ``TokenUsage.sub_models`` populated if the Claude Code
  ``modelUsage`` payload returned sub-models (skip-if-empty).
* KDR-003 regression: no ``anthropic`` import / no ``ANTHROPIC_API_KEY``
  read in production source.
"""

from __future__ import annotations

import os
import re
import shutil
import socket
from pathlib import Path

import pytest

from ai_workflows.primitives import cost as cost_module
from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.workflows._dispatch import resume_run, run_workflow
from ai_workflows.workflows.slice_refactor import SLICE_RESULT_ARTIFACT_KIND

#: Production tree scanned for the KDR-003 filesystem regression grep.
_PRODUCTION_ROOT = Path(__file__).resolve().parents[2] / "ai_workflows"

#: Regex mirrors the hermetic sibling; see that module for the rationale
#: behind narrowing the pattern to real-use signals.
_KDR_003_REGRESSION = re.compile(
    r"(^\s*import\s+anthropic\b|^\s*from\s+anthropic\b|ANTHROPIC_API_KEY)",
    re.MULTILINE,
)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_slice_refactor_live_smoke_multitier_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run the full ``slice_refactor`` graph end-to-end against real providers.

    Gated by ``AIW_E2E=1`` (collection hook) *and* by the three
    prerequisite checks below. The test is async (``pytest-asyncio``
    mode=auto) because :func:`run_workflow` / :func:`resume_run` are
    coroutines — the live smoke drives them directly rather than
    through Typer's ``CliRunner`` to keep the assertions in-process.
    """
    _skip_without_multitier_prereqs()
    _assert_no_anthropic_in_production_tree()

    monkeypatch.setenv("AIW_STORAGE_DB", str(tmp_path / "storage.sqlite"))
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))

    captured: list[TokenUsage] = _install_usage_capture(monkeypatch)
    run_id = f"e2e-slice-{os.urandom(4).hex()}"

    first = await run_workflow(
        workflow="slice_refactor",
        inputs={
            "goal": "Write three one-line unit tests for an add(a, b) function.",
            "context": None,
            "max_steps": 3,
        },
        run_id=run_id,
    )
    assert first["status"] == "pending", first
    assert first["awaiting"] == "gate", first

    second = await resume_run(run_id=run_id, gate_response="approved")
    assert second["status"] == "pending", second

    third = await resume_run(run_id=run_id, gate_response="approved")
    assert third["status"] == "completed", third
    assert third["total_cost_usd"] is not None
    assert third["total_cost_usd"] >= 0.0

    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    row = await storage.get_run(run_id)
    assert row is not None
    assert row["status"] == "completed"
    assert row["total_cost_usd"] is not None
    assert row["total_cost_usd"] >= 0.0

    artefact_count = await _count_slice_result_artefacts(storage, run_id)
    assert artefact_count >= 1, (
        f"expected at least one slice_result artefact; got {artefact_count}"
    )

    _assert_captured_usages_shape(captured)


def _skip_without_multitier_prereqs() -> None:
    """Skip with a readable reason when infra prereqs are missing.

    Mirrors :func:`tests/e2e/test_planner_smoke._skip_without_multitier_prereqs`.
    Three independent checks, each with its own skip reason so CI
    ``workflow_dispatch`` diagnoses the gap rather than silently
    passing an unconfigured run.
    """
    if shutil.which("ollama") is None:
        pytest.skip(
            "`ollama` binary not on PATH; install ollama and pull "
            "qwen2.5-coder:32b to run the slice_refactor live smoke"
        )
    if not _ollama_daemon_reachable():
        pytest.skip(
            "Ollama daemon not reachable at localhost:11434; start "
            "`ollama serve` to run the slice_refactor live smoke"
        )
    if shutil.which("claude") is None:
        pytest.skip(
            "`claude` CLI not on PATH; install Claude Code and log in "
            "(`claude setup-token`) to run the slice_refactor live smoke"
        )


def _ollama_daemon_reachable() -> bool:
    """Return ``True`` if a TCP connect to ``localhost:11434`` succeeds."""
    try:
        with socket.create_connection(("127.0.0.1", 11434), timeout=0.5):
            return True
    except OSError:
        return False


def _install_usage_capture(monkeypatch: pytest.MonkeyPatch) -> list[TokenUsage]:
    """Intercept :meth:`CostTracker.record` to also append each usage.

    ``_dispatch`` creates a fresh :class:`CostTracker` per run and
    keeps it local to ``run_workflow`` / ``resume_run``, so the only
    way to observe per-call rows from the test is to patch
    :meth:`record` itself. The real method still runs (rolls the usage
    into the tracker's aggregates); the patch only shadows the
    list-append side effect the test needs for the ``sub_models``
    assertion.
    """
    captured: list[TokenUsage] = []
    original = cost_module.CostTracker.record

    def _capture(
        self: cost_module.CostTracker, run_id: str, usage: TokenUsage
    ) -> None:
        captured.append(usage)
        original(self, run_id, usage)

    monkeypatch.setattr(cost_module.CostTracker, "record", _capture)
    return captured


def _assert_captured_usages_shape(captured: list[TokenUsage]) -> None:
    """Assert shape invariants on the captured per-call ledger.

    * At least one usage row captured — the cost callback fired.
    * Claude Code synth rows (tier == ``planner-synth``) with a
      populated :attr:`sub_models` list have non-negative per-sub costs.
      ``sub_models`` may be empty for Opus calls whose
      ``modelUsage`` payload did not include sub-model rows; matches
      the M5 T06 caveat.
    """
    assert captured, "no TokenUsage rows captured — cost callback never fired"
    synth_rows = [u for u in captured if u.tier == "planner-synth"]
    for row in synth_rows:
        if row.sub_models:
            assert all(sub.cost_usd >= 0.0 for sub in row.sub_models), row


async def _count_slice_result_artefacts(
    storage: SQLiteStorage, run_id: str
) -> int:
    """Count ``slice_result:<id>`` artefact rows for ``run_id``.

    Uses :meth:`read_artifact` with the three slice indices the goal
    is expected to produce. A plan may land fewer than three steps
    (the synth prompt does not guarantee exactly three), so the
    assertion in the test is ``>= 1`` rather than ``== 3``. Return
    value is the count of non-``None`` reads.
    """
    count = 0
    for candidate_id in ("1", "2", "3"):
        row = await storage.read_artifact(
            run_id, f"{SLICE_RESULT_ARTIFACT_KIND}:{candidate_id}"
        )
        if row is not None:
            count += 1
    return count


def _assert_no_anthropic_in_production_tree() -> None:
    """Grep production source for ``anthropic`` imports / ``ANTHROPIC_API_KEY``.

    Mirrors :func:`tests/e2e/test_planner_smoke._assert_no_anthropic_in_production_tree`;
    see that module's docstring for the regex rationale.
    """
    hits: list[tuple[str, int, str]] = []
    for py_file in _PRODUCTION_ROOT.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for match in _KDR_003_REGRESSION.finditer(text):
            lineno = text.count("\n", 0, match.start()) + 1
            line = text.splitlines()[lineno - 1]
            hits.append((str(py_file), lineno, line))
    assert not hits, (
        "KDR-003 regression: anthropic surface leaked into production "
        f"tree. Hits: {hits!r}"
    )
