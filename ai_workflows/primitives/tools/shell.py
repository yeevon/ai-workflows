"""Shell command stdlib tool — ``run_command`` with CWD and allowlist guards.

Produced by M1 Task 06 (P-15, P-16). :func:`run_command` is the one
subprocess entry point the model is allowed to reach, and it is gated by
three guards applied in strict order before the subprocess is ever
invoked:

1. **CWD containment** — ``working_dir`` must resolve under
   ``ctx.deps.project_root`` or :class:`SecurityError` is raised.
2. **Executable allowlist** — the first token of ``command`` must appear
   in ``ctx.deps.allowed_executables`` or
   :class:`ExecutableNotAllowedError` is raised. An empty allowlist blocks
   everything by design.
3. **Dry run** — when ``dry_run=True``, the function returns without
   touching :mod:`subprocess` (useful for validating plans).
4. **Timeout** — :func:`subprocess.run` is invoked with ``timeout=…``;
   expiry is turned into :class:`CommandTimeoutError`.

The exception classes exist so the guards can fail loudly inside the
function, but every exception is caught at the outer frame and converted
to a structured error string. The LLM never sees a Python traceback —
this is the convention pinned on ``M1-T05-ISS-03``.
"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from pydantic_ai import RunContext

from ai_workflows.primitives.llm.types import WorkflowDeps

__all__ = [
    "SecurityError",
    "ExecutableNotAllowedError",
    "CommandTimeoutError",
    "run_command",
]


class SecurityError(Exception):
    """Raised when ``working_dir`` escapes ``ctx.deps.project_root``.

    The message always names the attempted path so the forensic log line
    and any human reviewer can reconstruct the escape attempt without
    digging in `logging.extra`.
    """


class ExecutableNotAllowedError(Exception):
    """Raised when the first command token is not in ``allowed_executables``.

    An empty allowlist means "block everything" — this is a deliberate
    default that forces every workflow to declare what its agents may run.
    """


class CommandTimeoutError(Exception):
    """Raised when a subprocess exceeds ``timeout_seconds``."""


def _check_cwd_containment(working_dir: str, project_root: str) -> Path:
    """Resolve ``working_dir`` against ``project_root`` and confirm containment.

    Parameters
    ----------
    working_dir:
        Directory the caller wants to run in. Relative paths are joined to
        ``project_root``; absolute paths are taken as-is. In both cases the
        final path is :func:`Path.resolve`-d so symlink and ``..`` escapes
        are normalised before the containment check.
    project_root:
        Absolute directory under which every run is confined.

    Returns
    -------
    Path
        The resolved, absolute working directory (safe to pass as
        ``subprocess.run(cwd=…)``).

    Raises
    ------
    SecurityError
        If the resolved path is not inside ``project_root``.
    """
    root = Path(project_root).resolve()
    candidate = Path(working_dir)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as e:
        raise SecurityError(
            f"working_dir {working_dir!r} escapes project_root "
            f"{project_root!r} (resolved to {resolved!s})"
        ) from e
    return resolved


def _check_executable(command: str, allowed: list[str]) -> str:
    """Confirm the first shell token of ``command`` is in ``allowed``.

    Uses :func:`shlex.split` so quoted arguments with embedded spaces are
    parsed correctly. An empty command (or one that shlexes to nothing) is
    rejected — there is nothing to allow.

    Raises
    ------
    ExecutableNotAllowedError
        If the parsed executable is not present in ``allowed``.
    """
    tokens = shlex.split(command)
    if not tokens:
        raise ExecutableNotAllowedError("command is empty after tokenisation")
    exe = tokens[0]
    if exe not in allowed:
        raise ExecutableNotAllowedError(
            f"executable {exe!r} is not in the allowlist {sorted(allowed)!r}"
        )
    return exe


def run_command(
    ctx: RunContext[WorkflowDeps],
    command: str,
    working_dir: str,
    dry_run: bool = False,
    timeout_seconds: int = 300,
) -> str:
    """Run ``command`` in ``working_dir`` under the stdlib guards.

    Returns ``"Exit {code}\\n{output}"`` on successful execution, a
    ``"[DRY RUN] Would execute: …"`` string when ``dry_run=True``, or a
    structured error string starting with the exception class name when
    any guard or the subprocess itself fails. The LLM never sees a raised
    exception.
    """
    try:
        resolved_cwd = _check_cwd_containment(working_dir, ctx.deps.project_root)
    except SecurityError as e:
        return f"SecurityError: {e}"

    try:
        _check_executable(command, ctx.deps.allowed_executables)
    except ExecutableNotAllowedError as e:
        return f"ExecutableNotAllowedError: {e}"

    if dry_run:
        return f"[DRY RUN] Would execute: {command}"

    try:
        proc = subprocess.run(
            shlex.split(command),
            cwd=str(resolved_cwd),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        timeout_err = CommandTimeoutError(
            f"command {command!r} exceeded {timeout_seconds}s timeout"
        )
        return f"CommandTimeoutError: {timeout_err} (original: {e})"
    except FileNotFoundError as e:
        return f"Error: executable not found on PATH: {e}"
    except OSError as e:
        return f"Error: {type(e).__name__}: {e}"

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    output = stdout + (stderr if stderr else "")
    return f"Exit {proc.returncode}\n{output}"
