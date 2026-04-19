"""Tests for :mod:`ai_workflows.primitives.tools.shell` (Task 06).

Covers the Task 06 acceptance criteria that land in ``shell.py``:

* AC — ``..`` in ``working_dir`` raises :class:`SecurityError` with the
  attempted path. The guard helper raises the real exception; the
  top-level :func:`run_command` catches it and returns a string that
  names the error class and the attempted path.
* AC — executable not in allowlist raises
  :class:`ExecutableNotAllowedError`. Same internal-raise / string-return
  contract.
* AC — ``dry_run=True`` never invokes subprocess.
* AC — every failure mode returns a string, never raises to the LLM.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from ai_workflows.primitives.tools import shell
from ai_workflows.primitives.tools.shell import (
    CommandTimeoutError,
    ExecutableNotAllowedError,
    SecurityError,
    _check_cwd_containment,
    _check_executable,
    run_command,
)

# ---------------------------------------------------------------------------
# Guard helpers — direct unit tests for the raises-on-failure contract
# ---------------------------------------------------------------------------


def test_check_cwd_containment_accepts_subdirectory(tmp_path: Path) -> None:
    sub = tmp_path / "nested"
    sub.mkdir()
    out = _check_cwd_containment(str(sub), str(tmp_path))
    assert out == sub.resolve()


def test_check_cwd_containment_rejects_parent_traversal(tmp_path: Path) -> None:
    """AC: ``..`` traversal → SecurityError naming the attempted path."""
    with pytest.raises(SecurityError) as exc:
        _check_cwd_containment("../escape", str(tmp_path))

    assert "escape" in str(exc.value)
    assert "escapes project_root" in str(exc.value)


def test_check_cwd_containment_rejects_absolute_outside(tmp_path: Path) -> None:
    outside = tmp_path.parent / "sibling"
    with pytest.raises(SecurityError) as exc:
        _check_cwd_containment(str(outside), str(tmp_path))

    assert "sibling" in str(exc.value)


def test_check_executable_accepts_when_in_allowlist() -> None:
    assert _check_executable("ls -la", ["ls", "echo"]) == "ls"


def test_check_executable_rejects_when_not_in_allowlist() -> None:
    with pytest.raises(ExecutableNotAllowedError) as exc:
        _check_executable("rm -rf /", ["ls"])

    assert "rm" in str(exc.value)
    assert "allowlist" in str(exc.value).lower()


def test_check_executable_rejects_empty_allowlist() -> None:
    with pytest.raises(ExecutableNotAllowedError):
        _check_executable("ls", [])


def test_check_executable_rejects_empty_command() -> None:
    with pytest.raises(ExecutableNotAllowedError):
        _check_executable("", ["ls"])


# ---------------------------------------------------------------------------
# run_command — string-return contract for every failure mode
# ---------------------------------------------------------------------------


def test_run_command_security_error_returns_string(
    tmp_path: Path, ctx_factory
) -> None:
    ctx = ctx_factory(
        project_root=str(tmp_path),
        allowed_executables=["ls"],
    )

    out = run_command(ctx, "ls", "../escape")

    assert isinstance(out, str)
    assert out.startswith("SecurityError")
    assert "../escape" in out  # attempted path is named in the error


def test_run_command_executable_not_allowed_returns_string(
    tmp_path: Path, ctx_factory
) -> None:
    ctx = ctx_factory(
        project_root=str(tmp_path),
        allowed_executables=["echo"],
    )

    out = run_command(ctx, "rm -rf /", str(tmp_path))

    assert isinstance(out, str)
    assert out.startswith("ExecutableNotAllowedError")
    assert "'rm'" in out


def test_run_command_dry_run_does_not_invoke_subprocess(
    tmp_path: Path, ctx_factory
) -> None:
    """AC: dry_run=True never invokes subprocess."""
    ctx = ctx_factory(
        project_root=str(tmp_path),
        allowed_executables=["ls"],
    )

    with patch.object(subprocess, "run") as mocked_run:
        out = run_command(ctx, "ls -la", str(tmp_path), dry_run=True)

    mocked_run.assert_not_called()
    assert out == "[DRY RUN] Would execute: ls -la"


def test_run_command_dry_run_still_enforces_guards(
    tmp_path: Path, ctx_factory
) -> None:
    """dry_run=True must not bypass the CWD or allowlist guards."""
    ctx = ctx_factory(
        project_root=str(tmp_path),
        allowed_executables=["ls"],
    )

    # Allowlist guard fires before dry-run short-circuit.
    out = run_command(ctx, "rm -rf /", str(tmp_path), dry_run=True)
    assert out.startswith("ExecutableNotAllowedError")

    # CWD guard fires before either.
    out = run_command(ctx, "ls", "../escape", dry_run=True)
    assert out.startswith("SecurityError")


def test_run_command_success_returns_exit_code_and_output(
    tmp_path: Path, ctx_factory
) -> None:
    ctx = ctx_factory(
        project_root=str(tmp_path),
        allowed_executables=["echo"],
    )

    out = run_command(ctx, "echo hello", str(tmp_path))

    assert out.startswith("Exit 0\n")
    assert "hello" in out


def test_run_command_nonzero_exit_still_returns_string(
    tmp_path: Path, ctx_factory
) -> None:
    """A failing command is reported — not raised — so the LLM can react."""
    ctx = ctx_factory(
        project_root=str(tmp_path),
        allowed_executables=["sh"],
    )

    out = run_command(ctx, "sh -c 'exit 7'", str(tmp_path))

    assert out.startswith("Exit 7\n")


def test_run_command_timeout_returns_string(tmp_path: Path, ctx_factory) -> None:
    """AC: timeout → CommandTimeoutError; LLM sees the error as a string."""
    ctx = ctx_factory(
        project_root=str(tmp_path),
        allowed_executables=["sleep"],
    )

    out = run_command(ctx, "sleep 5", str(tmp_path), timeout_seconds=1)

    assert isinstance(out, str)
    assert out.startswith("CommandTimeoutError")
    assert "exceeded 1s" in out


def test_run_command_missing_executable_returns_string(
    tmp_path: Path, ctx_factory
) -> None:
    """The executable being allowlisted but missing on PATH is still a string."""
    ctx = ctx_factory(
        project_root=str(tmp_path),
        allowed_executables=["not_a_real_program_xyz_123"],
    )

    out = run_command(ctx, "not_a_real_program_xyz_123", str(tmp_path))

    assert isinstance(out, str)
    assert out.startswith("Error")


def test_command_timeout_error_is_the_right_class() -> None:
    """Pin the exception class name — imports rely on it."""
    err = CommandTimeoutError("…")
    assert isinstance(err, Exception)
    assert type(err).__name__ == "CommandTimeoutError"


def test_run_command_first_token_is_the_allowlist_check(
    tmp_path: Path, ctx_factory
) -> None:
    """Make sure ``ls -la /etc`` is checked against ``ls`` (first token)."""
    ctx = ctx_factory(
        project_root=str(tmp_path),
        allowed_executables=["ls"],
    )

    with patch.object(shell, "subprocess") as mocked_sp:
        # Wire the mock to return a fake CompletedProcess.
        mocked_sp.run.return_value = subprocess.CompletedProcess(
            args=["ls", "-la"], returncode=0, stdout="listed\n", stderr=""
        )
        mocked_sp.TimeoutExpired = subprocess.TimeoutExpired

        out = run_command(ctx, "ls -la /etc", str(tmp_path))

    assert mocked_sp.run.called
    assert out.startswith("Exit 0\n")
