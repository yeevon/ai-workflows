"""Tests for M4 Task 06 — stdio entry point + `aiw-mcp` console script.

Pins the two contract surfaces the stdio-transport registration relies
on:

* :mod:`ai_workflows.mcp.__main__` imports cleanly in a fresh
  interpreter (no side-effect `build_server()` at import time, no
  circular-import regressions) and exposes a callable :func:`main`.
* The ``aiw-mcp`` console script resolves via
  :func:`importlib.metadata.entry_points` — the single source of truth
  the ``claude mcp add`` invocation and the ``.mcp.json`` fallback in
  [mcp_setup.md](../../design_docs/phases/milestone_4_mcp/mcp_setup.md)
  both depend on.

Live stdio I/O is not exercised here (``server.run()`` would block
awaiting a JSON-RPC peer); the T07 in-process smoke test covers the
tool-call path hermetically.
"""

from __future__ import annotations

import importlib.metadata as importlib_metadata
import subprocess
import sys


def test_main_module_imports_cleanly() -> None:
    """``import ai_workflows.mcp.__main__`` succeeds in a fresh interpreter.

    A side-effect call to ``build_server()`` or ``server.run()`` at
    import time would either block or surface a spurious exception
    here — this test would catch either regression.
    """
    proc = subprocess.run(
        [sys.executable, "-c", "import ai_workflows.mcp.__main__"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0, (
        f"clean-interpreter import failed:\n"
        f"stdout={proc.stdout}\nstderr={proc.stderr}"
    )


def test_main_callable_is_exposed() -> None:
    """``main`` is the callable the ``aiw-mcp`` entry point resolves to."""
    from ai_workflows.mcp.__main__ import main

    assert callable(main)


def test_aiw_mcp_console_script_is_registered() -> None:
    """The ``aiw-mcp`` console script resolves via entry_points.

    Pins the ``[project.scripts] aiw-mcp = "ai_workflows.mcp.__main__:main"``
    registration in [pyproject.toml](../../pyproject.toml). A rename
    or removal of the entry point would break ``claude mcp add`` +
    ``uv run aiw-mcp`` — the two flows documented in
    ``mcp_setup.md``.
    """
    scripts = importlib_metadata.entry_points(group="console_scripts")
    aiw_mcp = next((ep for ep in scripts if ep.name == "aiw-mcp"), None)
    assert aiw_mcp is not None, (
        "aiw-mcp console script not registered; run `uv sync`."
    )
    assert aiw_mcp.value == "ai_workflows.mcp.__main__:main"
    loaded = aiw_mcp.load()
    assert callable(loaded)
