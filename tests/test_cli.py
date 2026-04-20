"""Tests for M1 Task 11 — CLI stub-down.

The CLI is reduced to the bare minimum per the task spec: only
``aiw --help`` and ``aiw version`` are exercised here. Every other
command was stripped along with the pre-pivot pydantic-ai substrate
and left behind as a ``TODO(M3)`` / ``TODO(M4)`` pointer in
:mod:`ai_workflows.cli`. Re-introduction tests land with the commands
themselves in Milestones 3 and 4.
"""

from __future__ import annotations

from typer.testing import CliRunner

from ai_workflows import __version__
from ai_workflows.cli import app

_RUNNER = CliRunner()


def test_aiw_help_exits_zero_and_mentions_surface() -> None:
    """``aiw --help`` must exit 0 and name the CLI surface."""
    result = _RUNNER.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "aiw" in result.output.lower()


def test_aiw_version_prints_package_version() -> None:
    """``aiw version`` must print a non-empty version string matching the dunder."""
    result = _RUNNER.invoke(app, ["version"])
    assert result.exit_code == 0, result.output
    assert __version__
    assert __version__ in result.output
