"""Git stdlib tools — ``git_diff``, ``git_log``, ``git_apply``.

Produced by M1 Task 06 (P-19). All three callables shell out to ``git``
via :func:`subprocess.run`; they never import a Python-git library (the
project deliberately stays free of heavyweight git bindings — every
target machine already has the ``git`` binary). ``git_apply`` additionally
calls ``git status --porcelain`` first and refuses to run on a dirty tree,
so the LLM cannot silently clobber an in-progress manual edit.
"""

from __future__ import annotations

import subprocess

from pydantic_ai import RunContext

from ai_workflows.primitives.llm.types import WorkflowDeps

__all__ = [
    "DirtyWorkingTreeError",
    "git_diff",
    "git_log",
    "git_apply",
]


_DIFF_CAP = 100_000
_DIFF_TRUNCATION_SUFFIX = "\n... [truncated at 100000 chars]"


class DirtyWorkingTreeError(Exception):
    """Raised by :func:`git_apply` when the target repo has uncommitted changes.

    The message includes the offending ``git status --porcelain`` output so
    a human reading the forensic log can see *what* was dirty without
    re-running git themselves.
    """


def git_diff(
    ctx: RunContext[WorkflowDeps],
    repo_path: str,
    ref: str = "HEAD",
) -> str:
    """Return ``git -C {repo_path} diff {ref}`` output, capped at 100K chars.

    Non-zero exit codes (e.g. unknown ref) are surfaced as a
    ``"Error: git diff exited N: …"`` string rather than raised. ``ctx``
    is accepted for stdlib convention.
    """
    _ = ctx
    try:
        proc = subprocess.run(
            ["git", "-C", repo_path, "diff", ref],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as e:
        return f"Error: git executable not found: {e}"
    except OSError as e:
        return f"Error: {type(e).__name__}: {e}"

    if proc.returncode != 0:
        return f"Error: git diff exited {proc.returncode}: {proc.stderr.strip()}"

    out = proc.stdout
    if len(out) > _DIFF_CAP:
        out = out[:_DIFF_CAP] + _DIFF_TRUNCATION_SUFFIX
    return out


def git_log(
    ctx: RunContext[WorkflowDeps],
    repo_path: str,
    max_entries: int = 20,
) -> str:
    """Return up to ``max_entries`` git log entries as ``"<sha> <subject>"`` lines."""
    _ = ctx
    try:
        proc = subprocess.run(
            [
                "git",
                "-C",
                repo_path,
                "log",
                f"-n{max_entries}",
                "--pretty=format:%h %s",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as e:
        return f"Error: git executable not found: {e}"
    except OSError as e:
        return f"Error: {type(e).__name__}: {e}"

    if proc.returncode != 0:
        return f"Error: git log exited {proc.returncode}: {proc.stderr.strip()}"
    return proc.stdout


def _check_clean_tree(repo_path: str) -> None:
    """Raise :class:`DirtyWorkingTreeError` if ``repo_path`` has uncommitted changes.

    Runs ``git status --porcelain`` and treats a non-empty stdout as dirty.
    A non-zero exit code (e.g. the path is not a git repo) is also raised
    as :class:`DirtyWorkingTreeError` so the outer ``git_apply`` catch can
    uniformly convert it to a string — the LLM does not need to
    distinguish "dirty" from "not a repo"; both mean "do not apply".
    """
    proc = subprocess.run(
        ["git", "-C", repo_path, "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise DirtyWorkingTreeError(
            f"git status failed in {repo_path!r}: {proc.stderr.strip()}"
        )
    if proc.stdout.strip():
        raise DirtyWorkingTreeError(
            f"working tree at {repo_path!r} is dirty:\n{proc.stdout}"
        )


def git_apply(
    ctx: RunContext[WorkflowDeps],
    repo_path: str,
    diff_content: str,
    dry_run: bool = False,
) -> str:
    """Apply ``diff_content`` to the repo at ``repo_path``.

    ``dry_run=True`` invokes ``git apply --check`` — it validates the diff
    without modifying the tree. In both modes the function refuses to run
    if the working tree is dirty; see :class:`DirtyWorkingTreeError`.
    """
    _ = ctx
    try:
        _check_clean_tree(repo_path)
    except DirtyWorkingTreeError as e:
        return f"DirtyWorkingTreeError: {e}"
    except FileNotFoundError as e:
        return f"Error: git executable not found: {e}"
    except OSError as e:
        return f"Error: {type(e).__name__}: {e}"

    cmd = ["git", "-C", repo_path, "apply"]
    if dry_run:
        cmd.append("--check")

    try:
        proc = subprocess.run(
            cmd,
            input=diff_content,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as e:
        return f"Error: git executable not found: {e}"
    except OSError as e:
        return f"Error: {type(e).__name__}: {e}"

    if proc.returncode != 0:
        return f"Error: git apply exited {proc.returncode}: {proc.stderr.strip()}"

    if dry_run:
        return "[DRY RUN] Diff applies cleanly."
    return "Applied diff successfully."
