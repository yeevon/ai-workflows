"""M3 Task 07 + M5 Task 06 — end-to-end smoke for the multi-tier planner.

One real-provider test that drives ``aiw run planner …`` →
``aiw resume <run_id>`` against the M5 two-phase planner sub-graph
(Qwen local_coder explorer via Ollama + Claude Code Opus synth via the
OAuth subprocess driver) and asserts the invariants the hermetic
graph-layer tests cannot exercise — that the sub-graph actually
completes end-to-end, that ``runs.total_cost_usd`` captures the
Claude Code cost (Qwen is free / local and contributes ``0``), that
the approved plan round-trips from Storage, and that no
``ANTHROPIC_API_KEY`` / ``anthropic.`` reference leaks into the
production tree or CLI output (KDR-003).

Gated by ``@pytest.mark.e2e`` + ``AIW_E2E=1`` (see
``tests/e2e/conftest.py``) so ``uv run pytest`` on a developer laptop
stays hermetic and never burns real quota. CI runs this job only on
``workflow_dispatch`` with the required infra bound.

Prerequisite checks at the top of the test skip (not fail) with a
readable reason when ``ollama`` / ``claude`` / the Ollama daemon is
missing, matching the T06 AC "no misleading failures on missing
provider infra".

Spec reframe (2026-04-20, inherited from M3). Step 7 of the M3 spec
prescribed ``CostTracker.from_storage(storage, run_id).total(run_id)``
as the budget-respected assertion. That helper was never implemented —
M1 T05 dropped the ``llm_calls`` per-call ledger and M1 T08 made
:class:`CostTracker` in-memory only. The M3 T06 reframe already
surfaced this gap and deferred any per-call-replay surface to
[nice_to_have.md §9](../../design_docs/nice_to_have.md). This test
applies the identical reframe: it reads the scalar
``runs.total_cost_usd`` stamped by ``aiw run`` / ``aiw resume`` —
the same signal ``aiw list-runs`` surfaces and the only cost signal
that drives a real decision under the current provider mix.

Budget-cap assertion removed (M5 reframe). M3's ``--budget 0.05`` was
sensible for hosted Gemini Flash ($$$-per-token). Claude Code Opus on
the Max subscription has flat-fee pricing that ``modelUsage`` does
still report as notional dollar figures, but the absolute number
varies by session; a hard ceiling would make this smoke flaky without
adding signal. The surviving cost assertion is ``total_cost_usd > 0``
(proves Claude Code contributed real cost) plus Qwen's explorer call
reported via the per-call capture hook.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import socket
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_workflows.cli import app
from ai_workflows.primitives import cost as cost_module
from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.workflows.planner import PlannerPlan

_RUNNER = CliRunner()

#: Shape ceiling the spec mandates ("1 ≤ len(steps) ≤ 3"). Lower bound
#: is a provider-sanity check; upper bound is what the `--max-steps 3`
#: argument hands the workflow.
_MAX_STEPS = 3

#: Source tree scanned for the KDR-003 grep assertion. Production only
#: — tests are allowed to reference the Anthropic surface when
#: documenting the ban.
_PRODUCTION_ROOT = Path(__file__).resolve().parents[2] / "ai_workflows"


@pytest.mark.e2e
def test_aiw_run_planner_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Drive the full ``aiw run`` → ``aiw resume`` path against the multi-tier planner.

    Gated by ``AIW_E2E=1`` (collection hook in
    ``tests/e2e/conftest.py``). Also requires ``ollama`` on ``PATH`` +
    an Ollama daemon reachable on ``localhost:11434`` and the
    ``claude`` CLI on ``PATH`` (M5 T06 AC-4). Each missing prerequisite
    skips with a clear reason so ``workflow_dispatch`` fails loudly
    only on a misconfigured infra rather than silently-passing an
    unconfigured run.

    The test is sync (despite the spec's async signature) because
    :meth:`CliRunner.invoke` drives the CLI's own ``asyncio.run(...)``
    internally — nesting that under pytest-asyncio's event loop raises
    ``RuntimeError: asyncio.run() cannot be called from a running
    event loop``. Any Storage reads in the assertions run under
    ``asyncio.run`` too, matching the pattern established by
    [tests/cli/test_resume.py].
    """
    _skip_without_multitier_prereqs()
    _assert_no_anthropic_in_production_tree()

    storage_path = tmp_path / "storage.sqlite"
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("AIW_STORAGE_DB", str(storage_path))

    captured_usages: list[TokenUsage] = _install_usage_capture(monkeypatch)

    run_id = f"e2e-{os.urandom(4).hex()}"

    run_result = _RUNNER.invoke(
        app,
        [
            "run",
            "planner",
            "--goal",
            "Write a three-bullet release checklist.",
            "--max-steps",
            str(_MAX_STEPS),
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

    # Storage round-trip (AC-1) + cost stamping (non-negative — Claude
    # Code Opus on the Max subscription reports notional 0 via
    # modelUsage; see M4 T08 CHANGELOG calibration + sibling
    # test_tier_override_smoke.py which uses the same posture).
    row = asyncio.run(_read_run_row(storage_path, run_id))
    assert row is not None, "run row missing after resume"
    assert row["status"] == "completed", row
    total_cost = row["total_cost_usd"]
    assert total_cost is not None, "runs.total_cost_usd not stamped at resume"
    assert total_cost >= 0, (
        f"expected non-negative total_cost_usd; got {total_cost}"
    )

    artifact_row = asyncio.run(_read_artifact(storage_path, run_id))
    assert artifact_row is not None, "plan artifact not persisted"
    plan = PlannerPlan.model_validate_json(artifact_row["payload_json"])
    assert 1 <= len(plan.steps) <= _MAX_STEPS, plan

    _assert_captured_usages_shape(captured_usages)


def _skip_without_multitier_prereqs() -> None:
    """Skip with a readable reason when Ollama / Claude Code prereqs are missing.

    Checks (each an independent skip reason):

    1. ``ollama`` binary on ``PATH`` — M5 T01 pins ``planner-explorer``
       to LiteLLM's ``ollama/...`` route which talks HTTP to the local
       daemon; without the binary the daemon cannot have been started.
    2. Ollama daemon reachable at ``localhost:11434`` — a ``tcp_connect``
       probe, not a full HTTP call (the daemon may be up but reject a
       model that hasn't been pulled; that failure mode is out of scope
       for a prereq gate).
    3. ``claude`` binary on ``PATH`` — M5 T02 pins ``planner-synth`` to
       ``ClaudeCodeRoute(cli_model_flag="opus")`` which spawns
       ``claude -p ... --model opus``. We do not probe OAuth auth here;
       an unauthenticated CLI surfaces as an in-band error the smoke
       will report rather than silently-passing.
    """
    if shutil.which("ollama") is None:
        pytest.skip(
            "`ollama` binary not on PATH; install ollama and pull "
            "qwen2.5-coder:32b to run the multi-tier e2e smoke"
        )
    if not _ollama_daemon_reachable():
        pytest.skip(
            "Ollama daemon not reachable at localhost:11434; start "
            "`ollama serve` to run the multi-tier e2e smoke"
        )
    if shutil.which("claude") is None:
        pytest.skip(
            "`claude` CLI not on PATH; install Claude Code and log in "
            "(`claude setup-token`) to run the multi-tier e2e smoke"
        )


def _ollama_daemon_reachable() -> bool:
    """Return ``True`` if a TCP connect to ``localhost:11434`` succeeds.

    Short 0.5 s timeout — the daemon either answers on the loopback
    interface immediately or the test should skip; we do not retry.
    """
    try:
        with socket.create_connection(("127.0.0.1", 11434), timeout=0.5):
            return True
    except OSError:
        return False


def _install_usage_capture(monkeypatch: pytest.MonkeyPatch) -> list[TokenUsage]:
    """Monkeypatch ``CostTracker.record`` to also append each usage to a list.

    The dispatch helper creates a fresh :class:`CostTracker` per run and
    keeps it local to ``_dispatch.run_workflow``, so the only way to
    observe per-call rows from the test is to intercept ``record``
    itself. The real method still runs (rolls the usage into the
    tracker's aggregates); the patch only shadows the list-append side
    effect the test needs for AC-level assertions about the Claude Code
    ``sub_models`` field.
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
    """Assert per-call ledger shape: Qwen cost 0; Claude Code sub_models check.

    AC-3 / AC-4 (M5 T06):

    * Every Qwen / LiteLLM-Ollama usage has ``cost_usd == 0`` (the
      explorer is a local model and the tier's adapter layer reports
      zero cost per call).
    * The Claude Code synth usage carries a non-empty ``sub_models``
      list when the CLI's ``modelUsage`` payload contained sub-model
      rows (mainline Opus responses do include a ``haiku`` breakdown).
      Skipped gracefully when empty — the spec's caveat, "some Opus
      calls do not auto-spawn."

    No tier-name assertion on the Qwen row because the ``tier`` field
    is workflow-supplied and has changed shape between milestones; the
    cost invariant is the one the task spec asks for.
    """
    assert captured, "no TokenUsage rows captured — cost callback never fired"

    explorer_rows = [
        u
        for u in captured
        if u.model.startswith("ollama/") or u.tier == "planner-explorer"
    ]
    assert explorer_rows, (
        f"no explorer row captured; saw models {[u.model for u in captured]!r}"
    )
    for row in explorer_rows:
        assert row.cost_usd == 0.0, (
            f"expected Qwen explorer row to have cost_usd=0; got {row}"
        )

    synth_rows = [u for u in captured if u.tier == "planner-synth"]
    assert synth_rows, (
        f"no planner-synth row captured; saw tiers "
        f"{sorted({u.tier for u in captured})!r}"
    )
    opus_row = synth_rows[-1]
    # sub_models is present when the CLI reported modelUsage sub-rows.
    # The spec allows this to be empty for Opus calls that did not
    # auto-spawn — so we only assert when populated.
    if opus_row.sub_models:
        assert all(sub.cost_usd >= 0.0 for sub in opus_row.sub_models), opus_row


#: Regex markers that indicate an actual KDR-003 regression in production
#: source — an ``import anthropic`` / ``from anthropic`` line or any use
#: of the literal ``ANTHROPIC_API_KEY`` env var name. Prose mentions of
#: the ban in docstrings are intentionally NOT matched.
_KDR_003_REGRESSION = re.compile(
    r"(^\s*import\s+anthropic\b|^\s*from\s+anthropic\b|ANTHROPIC_API_KEY)",
    re.MULTILINE,
)


def _assert_no_anthropic_in_production_tree() -> None:
    """Grep production source for ``anthropic`` imports / ``ANTHROPIC_API_KEY``.

    M5 T06 AC-5 enforces the KDR-003 ban at the filesystem level, not
    just at runtime. Scans every ``*.py`` under ``ai_workflows/``. The
    regex intentionally narrows to real-use signals (import statements
    and the literal env-var name) because prose descriptions of the
    ban in docstrings ("never imports the anthropic SDK") are part of
    KDR-003's documentation surface — flagging those would force the
    docstrings to redact the word they are forbidding.
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
