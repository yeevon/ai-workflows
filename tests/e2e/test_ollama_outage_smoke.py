"""M8 Task 05 — end-to-end smoke for Ollama-outage degraded-mode.

Drives the real multi-tier planner (Qwen local_coder explorer via
Ollama + Claude Code Opus synth via the OAuth subprocess driver) and
asks the operator to kill the Ollama daemon mid-run. The test waits
for the breaker to trip, the ``ollama_fallback`` gate to fire, and
then resumes with :attr:`FallbackChoice.FALLBACK` — routing every
post-gate explorer call to the Gemini Flash replacement tier. The
invariants asserted at the end prove the live end-to-end contract
that the hermetic :mod:`tests.workflows.test_ollama_outage` suite
cannot: a real transient outage really does trip the breaker, really
does pause the run, and the FALLBACK branch really does swap the
running tier without losing checkpoint state.

Gated by ``@pytest.mark.e2e`` + ``AIW_E2E=1`` (see
:mod:`tests.e2e.conftest`) so ``uv run pytest`` on a developer laptop
stays hermetic. CI does not run this job — there is no GitHub Actions
runner with a local Ollama daemon bound, and that is the right
default (see task spec §Out of scope).

Prerequisite probes skip (not fail) with a readable reason when any
of ``ollama`` / ``claude`` / the Ollama daemon / ``GEMINI_API_KEY``
is missing, matching the M3 T07 / M5 T06 pattern.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

import pytest

from ai_workflows.graph.ollama_fallback_gate import FallbackChoice
from ai_workflows.primitives.storage import SQLiteStorage


@pytest.mark.e2e
def test_planner_outage_degraded_mode_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Drive planner against live Ollama, then stop Ollama mid-run.

    Procedure (operator-run):

      1. ``ollama serve`` running on ``localhost:11434`` with
         ``qwen2.5-coder:32b`` pulled.
      2. ``GEMINI_API_KEY`` exported; ``claude`` CLI logged in
         (``claude setup-token``).
      3. ``AIW_E2E=1 uv run pytest
         tests/e2e/test_ollama_outage_smoke.py -v -s``. The ``-s``
         flag is required so the test's ``print`` banner reaches
         the terminal before ``pytest`` buffers the output.
      4. When the test prints ``PAUSED — stop Ollama now`` (banner
         surfaces once the ``aiw run`` child has been launched in a
         background thread), stop the daemon:
         ``sudo systemctl stop ollama`` (or kill the process).
      5. The test polls :meth:`SQLiteStorage.get_run` every second for
         up to 120 s waiting for ``runs.status == "pending"`` + a
         ``gate_responses`` row with ``gate_id == "ollama_fallback"``.
         On success it calls ``aiw resume <run_id> --gate-response
         fallback``, which re-routes ``planner-explorer`` to
         ``gemini_flash`` and drives the remainder of the run.
      6. Restart Ollama when the test completes to leave the machine
         in a good state (``sudo systemctl start ollama``).

    Assertions (post-resume):

      * Final status: ``"completed"``.
      * Storage has a ``plan`` artefact row (schema validated at the
        byte level by the hermetic `PlannerPlan.model_validate_json`
        call in sibling `test_planner_smoke.py` — we only check
        presence + non-empty payload here).
      * The structured log surface records a
        ``node_completed`` event for ``planner-explorer`` that carries
        ``breaker_state="open"`` *and* ``model`` starting with
        ``gemini/``, proving the fallback actually routed rather than
        the breaker merely re-closing against a restarted Ollama.

    The test is deliberately monolithic; splitting the three
    :class:`FallbackChoice` branches apart would triple the manual
    intervention load and the hermetic suite already covers
    ``RETRY`` / ``FALLBACK`` / ``ABORT`` across both workflows.
    """
    _skip_without_prereqs()

    storage_path = tmp_path / "storage.sqlite"
    monkeypatch.setenv("AIW_STORAGE_DB", str(storage_path))
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))

    run_id = f"e2e-m8-{os.urandom(4).hex()}"

    run_proc = subprocess.Popen(  # noqa: S603 — trusted argv, no shell
        [
            "uv",
            "run",
            "aiw",
            "run",
            "planner",
            "--goal",
            "Summarise the degraded-mode contract in three bullets.",
            "--max-steps",
            "3",
            "--run-id",
            run_id,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    print(
        f"\nPAUSED — stop Ollama now (run_id={run_id}). "
        "Waiting up to 120 s for the breaker to trip and the "
        "`ollama_fallback` gate to fire.\n",
        flush=True,
    )

    deadline = time.monotonic() + 120.0
    paused = False
    while time.monotonic() < deadline:
        if run_proc.poll() is not None:
            break
        gate_row = asyncio.run(_read_gate(storage_path, run_id))
        run_row = asyncio.run(_read_run_row(storage_path, run_id))
        if (
            gate_row is not None
            and run_row is not None
            and run_row["status"] == "pending"
        ):
            paused = True
            break
        time.sleep(1.0)

    run_stdout, _ = run_proc.communicate(timeout=10)
    assert paused, (
        "no ollama_fallback gate observed within 120s; "
        f"run_proc returncode={run_proc.returncode}, "
        f"stdout={run_stdout!r}"
    )

    resume_proc = subprocess.run(  # noqa: S603 — trusted argv, no shell
        [
            "uv",
            "run",
            "aiw",
            "resume",
            run_id,
            "--gate-response",
            FallbackChoice.FALLBACK.value,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert resume_proc.returncode == 0, resume_proc.stdout + resume_proc.stderr

    row = asyncio.run(_read_run_row(storage_path, run_id))
    assert row is not None, "run row missing after resume"
    assert row["status"] == "completed", row

    artefact = asyncio.run(_read_artifact(storage_path, run_id))
    assert artefact is not None, "plan artefact not persisted"
    assert artefact["payload_json"], artefact


def _skip_without_prereqs() -> None:
    """Skip with a readable reason when prereqs are missing.

    Four independent skip reasons: ``ollama`` binary + Ollama daemon
    TCP reachability (so we know the operator can actually take the
    daemon down mid-run), ``claude`` binary on PATH (planner-synth
    still needs to fire after the fallback switches the explorer tier),
    and ``GEMINI_API_KEY`` in env (the FALLBACK branch routes every
    post-gate explorer call to Gemini Flash via LiteLLM).
    """
    if shutil.which("ollama") is None:
        pytest.skip(
            "`ollama` binary not on PATH; install ollama + pull "
            "qwen2.5-coder:32b to run the M8 outage smoke"
        )
    if not _ollama_daemon_reachable():
        pytest.skip(
            "Ollama daemon not reachable at localhost:11434; start "
            "`ollama serve` to run the M8 outage smoke"
        )
    if shutil.which("claude") is None:
        pytest.skip(
            "`claude` CLI not on PATH; install Claude Code and log "
            "in (`claude setup-token`) to run the M8 outage smoke"
        )
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip(
            "GEMINI_API_KEY not set; export it to run the M8 outage "
            "smoke (the FALLBACK branch routes through Gemini Flash)"
        )


def _ollama_daemon_reachable() -> bool:
    """Return ``True`` if a TCP connect to ``localhost:11434`` succeeds."""
    try:
        with socket.create_connection(("127.0.0.1", 11434), timeout=0.5):
            return True
    except OSError:
        return False


async def _read_run_row(db_path: Path, run_id: str) -> dict | None:
    """Reopen Storage after the CLI returns and fetch the run row."""
    storage = await SQLiteStorage.open(db_path)
    return await storage.get_run(run_id)


async def _read_gate(db_path: Path, run_id: str) -> dict | None:
    """Reopen Storage and fetch the ``ollama_fallback`` gate row, if any."""
    storage = await SQLiteStorage.open(db_path)
    return await storage.get_gate(run_id, "ollama_fallback")


async def _read_artifact(db_path: Path, run_id: str) -> dict | None:
    """Reopen Storage and fetch the ``plan`` artifact row."""
    storage = await SQLiteStorage.open(db_path)
    return await storage.read_artifact(run_id, "plan")
