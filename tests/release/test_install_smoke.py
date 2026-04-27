"""Real-install end-to-end smoke against the published-shape wheel.

The 0.3.0 publish shipped a non-functional headline feature: the spec-API
``register_workflow`` registration path compiled cleanly, but the dispatch
path's ``_build_initial_state`` could not construct typed input from
``WorkflowSpec.input_schema`` — every existing test that "proved" wire-level
behaviour pre-registered the workflow imperatively via a fixture, so the
broken dispatch path was never exercised.

This module is the gate that catches that class of false-positive: every
release smoke must run ``aiw`` against an ``uv pip install dist/*.whl`` install
in a fresh venv, not against the source tree. A test that compiles + dispatches
through the in-repo source code does not prove the published wheel works for a
downstream consumer.

Composes over: ``uv build`` (build the wheel from the working tree),
``uv venv`` (fresh temp venv), ``uv pip install`` (install the wheel), and
``AIW_EXTRA_WORKFLOW_MODULES`` (KDR-013 — register the synthetic test workflow
without baking it into the package).

Skipped when ``uv`` is not on ``PATH`` so contributors without it can still run
the test suite. Live-network providers (Gemini, Ollama, Claude) are not invoked
— the test workflow is no-LLM (single ``ValidateStep``) so a missing
``GEMINI_API_KEY`` or unreachable Ollama does not affect the assertion.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


pytestmark = pytest.mark.skipif(
    shutil.which("uv") is None,
    reason="uv not on PATH — release-install smoke requires uv",
)


@pytest.fixture(scope="module")
def built_wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the wheel from the working tree once per module run.

    Uses an isolated build directory so concurrent test runs don't fight over
    ``dist/`` at the repo root.
    """
    out_dir = tmp_path_factory.mktemp("build")
    result = subprocess.run(
        ["uv", "build", "--out-dir", str(out_dir)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, (
        f"uv build failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    wheels = sorted(out_dir.glob("*.whl"))
    assert wheels, f"uv build produced no wheel; out_dir contents: {list(out_dir.iterdir())}"
    return wheels[0]


def _write_test_workflow(workflow_dir: Path) -> str:
    """Write a no-LLM spec-API test workflow into ``workflow_dir``.

    The workflow takes a ``message`` input string, validates it as the
    output, and returns it unchanged. No LLM calls; no provider key
    required. Returns the dotted module path the consumer would pass to
    ``AIW_EXTRA_WORKFLOW_MODULES``.
    """
    module_name = "smoke_test_workflow"
    (workflow_dir / f"{module_name}.py").write_text(
        textwrap.dedent(
            '''
            """No-LLM spec-API workflow used by the real-install smoke test.

            Single ``ValidateStep`` that round-trips the ``message`` input as the
            output. Asserting that ``aiw run`` against an installed wheel returns
            exit 0 + the expected artefact proves the dispatch path resolves the
            spec via ``get_spec(name)`` and constructs typed input from
            ``spec.input_schema`` — the 0.3.1 fix.
            """

            from pydantic import BaseModel

            from ai_workflows.workflows import (
                ValidateStep,
                WorkflowSpec,
                register_workflow,
            )


            class SmokeInput(BaseModel):
                message: str


            class SmokeOutput(BaseModel):
                message: str


            register_workflow(
                WorkflowSpec(
                    name="smoke_test_workflow",
                    input_schema=SmokeInput,
                    output_schema=SmokeOutput,
                    tiers={},  # no LLM calls
                    steps=[
                        ValidateStep(target_field="message", schema=SmokeOutput),
                    ],
                )
            )
            '''
        ).strip()
        + "\n"
    )
    return module_name


def test_aiw_run_against_installed_wheel(
    built_wheel: Path,
    tmp_path: Path,
) -> None:
    """End-to-end: build wheel, install in fresh venv, run aiw run, assert success.

    Exercises the same dispatch path the published CLI uses. A spec-API
    workflow registered via ``AIW_EXTRA_WORKFLOW_MODULES`` is invoked through
    ``aiw run`` from the fresh venv's bin directory; success requires the
    ``register_workflow`` → ``get_spec`` → ``_build_initial_state`` path to
    construct typed input from the spec.

    A passing run exits 0 and surfaces the artefact + status in stdout.
    ``aiw run`` does not (yet) expose a ``--json`` mode, so the assertion is
    shape-soft: exit 0 + the input ``message`` value present in stdout proves
    the dispatch path resolved the workflow, constructed typed input, and
    executed the step end-to-end. The 0.3.0 break would surface as exit 1
    with ``ValueError: workflow ... exposes no Input schema`` in stderr.
    """
    venv_dir = tmp_path / ".venv"
    workflow_dir = tmp_path / "workflow_pkg"
    workflow_dir.mkdir()
    storage_dir = tmp_path / "aiw_storage"
    storage_dir.mkdir()

    venv_create = subprocess.run(
        ["uv", "venv", "--python", "3.13", str(venv_dir)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert venv_create.returncode == 0, (
        f"uv venv failed: {venv_create.stderr!r}"
    )

    install = subprocess.run(
        ["uv", "pip", "install", "--python", str(venv_dir / "bin" / "python"), str(built_wheel)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert install.returncode == 0, (
        f"uv pip install failed: {install.stderr!r}"
    )

    module_name = _write_test_workflow(workflow_dir)
    aiw_path = venv_dir / "bin" / "aiw"
    assert aiw_path.exists(), f"aiw entrypoint not found at {aiw_path}"

    env = {
        **os.environ,
        "PYTHONPATH": str(workflow_dir),
        "AIW_EXTRA_WORKFLOW_MODULES": module_name,
        "AIW_STORAGE_DB": str(storage_dir / "smoke.sqlite3"),
        "AIW_CHECKPOINT_DB": str(storage_dir / "smoke_ck.sqlite3"),
    }
    # GEMINI_API_KEY / ANTHROPIC_API_KEY are deliberately NOT set — the no-LLM
    # workflow must run without provider credentials. Strip them to prove it.
    for k in ("GEMINI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        env.pop(k, None)

    run = subprocess.run(
        [
            str(aiw_path),
            "run",
            "smoke_test_workflow",
            "--input",
            "message=hello-from-installed-wheel",
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )

    assert run.returncode == 0, (
        f"aiw run failed (exit {run.returncode}): "
        f"stdout={run.stdout!r} stderr={run.stderr!r}"
    )
    combined = run.stdout + run.stderr
    assert "exposes no Input schema" not in combined, (
        f"0.3.0 dispatch regression resurfaced — Input schema lookup failed. "
        f"Output: {combined!r}"
    )
    assert "hello-from-installed-wheel" in combined, (
        f"expected the round-tripped artefact message in stdout/stderr; got "
        f"stdout={run.stdout!r} stderr={run.stderr!r}"
    )


def test_built_wheel_imports_register_workflow(built_wheel: Path) -> None:
    """The built wheel exposes ``register_workflow`` at the documented path.

    Cheap-but-real check that the build produces something usable: install
    the wheel in a fresh venv and import the spec-API entry point. Catches
    packaging-only regressions (e.g., ``register_workflow`` accidentally
    excluded from the wheel) without standing up a full ``aiw run``.
    """
    venv_dir = built_wheel.parent / ".venv_import_check"
    if venv_dir.exists():
        shutil.rmtree(venv_dir)

    subprocess.run(
        ["uv", "venv", "--python", "3.13", str(venv_dir)],
        check=True,
        capture_output=True,
        timeout=120,
    )
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(venv_dir / "bin" / "python"),
            str(built_wheel),
        ],
        check=True,
        capture_output=True,
        timeout=300,
    )

    probe = subprocess.run(
        [
            str(venv_dir / "bin" / "python"),
            "-c",
            "from ai_workflows.workflows import register_workflow, WorkflowSpec, get_spec; "
            "print('OK', get_spec('nonexistent') is None)",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert probe.returncode == 0, (
        f"import probe failed: stdout={probe.stdout!r} stderr={probe.stderr!r}"
    )
    assert probe.stdout.strip() == "OK True", probe.stdout
