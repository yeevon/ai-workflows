"""Deterministic content hash of a workflow directory (CRIT-02).

Produced by M1 Task 07. Paired with Task 08's ``runs.workflow_dir_hash``
column to detect when a workflow has been edited between ``aiw run`` and
``aiw resume <run_id>``.

Scope
-----
The hash covers every file in the workflow directory tree (``workflow.yaml``,
``prompts/``, ``schemas/``, ``custom_tools.py``) *except* for the noise
patterns named in the spec:

* ``__pycache__/`` — Python bytecode caches.
* ``*.pyc`` — stray bytecode outside ``__pycache__/``.
* ``.DS_Store`` — macOS Finder metadata.
* ``*.log`` — workflow-local log files.

Everything else contributes to the hash. File modes, timestamps, ownership,
and parent-directory metadata are NOT hashed — only relative paths and file
contents — so re-cloning the workflow or copying it between machines does
not invalidate a resume.

Algorithm
---------
SHA-256 over the concatenation of ``(relative-path, NUL, contents, NUL-NUL)``
for each file, with paths sorted lexicographically as POSIX strings (so the
same directory yields the same digest on Windows and POSIX hosts). The NUL
separators make it impossible for a filename/contents collision (e.g.
renaming ``a`` to ``a/b`` while emptying ``b``) to yield the same digest.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

# Files matching any of these are not hashed. Keep the set narrow — anything
# that could affect workflow behaviour (tests, fixtures, additional configs)
# should contribute to the hash by default.
_IGNORED_SUFFIXES = frozenset({".pyc", ".log"})
_IGNORED_NAMES = frozenset({".DS_Store"})
_IGNORED_DIRS = frozenset({"__pycache__"})


def _is_ignored(path: Path) -> bool:
    """Return True if ``path`` should be skipped by the hash computation."""
    if any(part in _IGNORED_DIRS for part in path.parts):
        return True
    if path.name in _IGNORED_NAMES:
        return True
    return path.suffix in _IGNORED_SUFFIXES


def compute_workflow_hash(workflow_dir: str | Path) -> str:
    """Return a deterministic SHA-256 digest of ``workflow_dir``'s contents.

    Parameters
    ----------
    workflow_dir:
        Path to a workflow directory (e.g.
        ``workflows/jvm_modernization/``). May be a ``str`` or ``Path``.

    Returns
    -------
    str
        Lowercase hexadecimal SHA-256 digest. Identical inputs always yield
        identical digests, regardless of filesystem iteration order.

    Raises
    ------
    FileNotFoundError
        If ``workflow_dir`` does not exist.
    NotADirectoryError
        If ``workflow_dir`` exists but is not a directory.
    """
    root = Path(workflow_dir)
    if not root.exists():
        raise FileNotFoundError(f"Workflow directory not found: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Workflow path is not a directory: {root}")

    h = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or _is_ignored(path):
            continue
        rel = path.relative_to(root).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0\0")
    return h.hexdigest()
