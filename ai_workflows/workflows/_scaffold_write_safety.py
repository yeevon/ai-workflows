"""Write-safety guards for the scaffold_workflow output file (M17 Task 01).

Separate module because the safety rules are load-bearing and testable in
isolation from the main workflow graph.  The scaffold calls
:func:`validate_target_path` during input validation and :func:`atomic_write`
after gate approval.

Relationship to other modules
------------------------------
* :mod:`ai_workflows.workflows.scaffold_workflow` — sole caller.
* ADR-0010 (T03 of this milestone) — the risk-ownership decision that these
  guards enforce.  Target paths inside the installed ``ai_workflows`` package
  are rejected here so the scaffold cannot overwrite framework code.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import tempfile
from pathlib import Path

import ai_workflows

__all__ = [
    "TargetInsideInstalledPackageError",
    "TargetDirectoryNotWritableError",
    "TargetExistsError",
    "TargetRelativePathError",
    "validate_target_path",
    "atomic_write",
]


class TargetInsideInstalledPackageError(ValueError):
    """Raised when the target path resolves to inside the ai_workflows package dir."""


class TargetDirectoryNotWritableError(OSError):
    """Raised when the target's parent directory does not exist or is not writable."""


class TargetExistsError(FileExistsError):
    """Raised when the target file already exists and ``force=False``."""


class TargetRelativePathError(ValueError):
    """Raised when the target path is relative (ambiguous against server cwd)."""


def validate_target_path(
    target: Path,
    *,
    force: bool = False,
) -> Path:
    """Resolve, validate, and return an absolute target path.

    Rejects:
      - Paths inside the installed ai_workflows package.
      - Parent directories that don't exist or aren't writable.
      - Existing files when force=False.
      - Relative paths (ambiguous against server/client cwd).

    Returns the resolved absolute path on success.
    """
    # 1. Reject relative paths before any resolve() call.
    if not target.is_absolute():
        raise TargetRelativePathError(
            f"target path must be absolute; got relative path {target!r}. "
            "Pass an absolute path (e.g. /home/user/my-workflows/my_wf.py)."
        )

    resolved = target.expanduser().resolve()

    # 2. Reject paths inside the installed ai_workflows package.
    package_dir = Path(ai_workflows.__file__).parent.resolve()
    if resolved.is_relative_to(package_dir):
        raise TargetInsideInstalledPackageError(
            f"target {resolved!r} is inside the installed ai_workflows package "
            f"({package_dir!r}); the scaffold may not overwrite framework code. "
            "Pick a user-owned directory outside the package."
        )

    # 3. Parent directory must exist and be writable.
    parent = resolved.parent
    if not parent.exists():
        raise TargetDirectoryNotWritableError(
            f"parent directory {parent!r} does not exist; create it first."
        )
    if not os.access(parent, os.W_OK):
        raise TargetDirectoryNotWritableError(
            f"parent directory {parent!r} exists but is not writable."
        )

    # 4. Reject existing files unless force=True.
    if resolved.exists() and not force:
        raise TargetExistsError(
            f"target file {resolved!r} already exists; pass force=True to overwrite."
        )

    return resolved


def atomic_write(target: Path, content: str) -> str:
    """Write content atomically. Returns SHA256 hex of written bytes.

    Uses ``tempfile.mkstemp(dir=target.parent)`` to guarantee
    same-filesystem placement (required for ``os.replace`` atomicity on
    POSIX), then ``os.replace()`` to swap.  Ensures a partial write cannot
    corrupt a previous good file on crash.
    """
    encoded = content.encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()

    fd, tmp_path = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    try:
        os.write(fd, encoded)
        os.fsync(fd)
    finally:
        os.close(fd)

    try:
        os.replace(tmp_path, target)
    except Exception:
        # Clean up the temp file so it does not litter the parent directory.
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise

    return digest
