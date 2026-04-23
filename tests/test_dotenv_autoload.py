"""0.1.1 patch — verify `.env` auto-load at CLI + MCP entry points.

Before 0.1.1 the `python-dotenv` dependency was declared in
[pyproject.toml](../pyproject.toml) but ``load_dotenv()`` was only invoked from
[conftest.py](conftest.py), meaning a `uvx`-installed user with a `.env` in
their current directory got nothing — the running process only saw shell-
exported vars. 0.1.1 adds ``load_dotenv(override=False)`` at module top of
[ai_workflows/cli.py](../ai_workflows/cli.py) and
[ai_workflows/mcp/__main__.py](../ai_workflows/mcp/__main__.py).

Tests run each entry-point import in a subprocess with a tmp_path cwd that
contains a sentinel `.env`. Subprocess isolation is load-bearing — our own
test suite's conftest already loads the repo-root `.env` into this process,
so an in-process monkeypatch re-import would not exercise the cwd-lookup
path we actually ship to users.

Relationship to other tests
---------------------------
* :mod:`tests.test_wheel_contents` pins the wheel-exclusion side (no `.env*`
  leaks into the published artefact); this module pins the runtime-load
  side (a user-provided `.env` is picked up).
* :mod:`tests.conftest` calls :func:`dotenv.load_dotenv` against the repo
  root — orthogonal to this test, which exercises the *surface-module*
  ``load_dotenv`` call added at 0.1.1.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_SENTINEL_NAME = "AIW_DOTENV_AUTOLOAD_TEST_SENTINEL"
_SENTINEL_VALUE = "0p4tch-0.1.1-loaded"


def _run_import_probe(module: str, cwd: Path) -> str:
    """Import ``module`` in a fresh Python process under ``cwd``; return the sentinel."""
    probe = (
        f"import {module}; "
        "import os, sys; "
        f"sys.stdout.write(os.environ.get({_SENTINEL_NAME!r}, '<missing>'))"
    )
    env = {k: v for k, v in os.environ.items() if k != _SENTINEL_NAME}
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout


@pytest.fixture()
def dotenv_tmp(tmp_path: Path) -> Path:
    """Write a sentinel `.env` into a tmp dir and yield the dir."""
    (tmp_path / ".env").write_text(f"{_SENTINEL_NAME}={_SENTINEL_VALUE}\n")
    return tmp_path


def test_cli_module_autoloads_dotenv_from_cwd(dotenv_tmp: Path) -> None:
    """Importing :mod:`ai_workflows.cli` from a cwd with `.env` populates ``os.environ``.

    Regression guard for the 0.1.1 patch. A failure here means a `uvx`
    install path is silently broken for users who rely on a `.env`
    (README §Setup documents this as the primary key-config path).
    """
    loaded = _run_import_probe("ai_workflows.cli", dotenv_tmp)
    assert loaded == _SENTINEL_VALUE, (
        f"ai_workflows.cli did not load .env from cwd; "
        f"expected {_SENTINEL_VALUE!r}, got {loaded!r}"
    )


def test_mcp_main_module_autoloads_dotenv_from_cwd(dotenv_tmp: Path) -> None:
    """Importing :mod:`ai_workflows.mcp.__main__` from a cwd with `.env` populates ``os.environ``.

    The MCP surface is a separate process entry (``aiw-mcp`` vs ``aiw``),
    so it needs its own ``load_dotenv`` call — the CLI's doesn't cover it.
    """
    loaded = _run_import_probe("ai_workflows.mcp.__main__", dotenv_tmp)
    assert loaded == _SENTINEL_VALUE, (
        f"ai_workflows.mcp.__main__ did not load .env from cwd; "
        f"expected {_SENTINEL_VALUE!r}, got {loaded!r}"
    )


def test_shell_export_wins_over_dotenv(dotenv_tmp: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``override=False`` semantics — a shell-exported var beats the `.env` value.

    This is the right precedence for production: a user exporting a key
    in their session (e.g. via direnv, a CI secret, or ``GEMINI_API_KEY=x
    aiw run ...`` inline) must win over a stale `.env`.
    """
    override_value = "shell-export-wins"
    probe = (
        "import ai_workflows.cli; "
        "import os, sys; "
        f"sys.stdout.write(os.environ.get({_SENTINEL_NAME!r}, '<missing>'))"
    )
    env = {k: v for k, v in os.environ.items() if k != _SENTINEL_NAME}
    env[_SENTINEL_NAME] = override_value
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=dotenv_tmp,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.stdout == override_value, (
        f"shell-exported {_SENTINEL_NAME}={override_value!r} should have "
        f"won over .env value; got {result.stdout!r}"
    )
