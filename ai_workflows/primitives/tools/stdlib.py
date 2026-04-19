"""Stdlib tool registration helper.

Produced by M1 Task 06. Exposes :func:`register_stdlib_tools`, which binds
every callable from the sibling ``fs``, ``shell``, ``http``, and ``git``
modules onto a freshly-minted :class:`ToolRegistry` at workflow-run start.

This is the single spot in the primitives layer that knows the canonical
tool-name → callable mapping. Components and workflows never import the
callables directly; they receive the registry instance and call
:meth:`ToolRegistry.build_pydantic_ai_tools` with a scoped name list — the
per-component allowlist pattern pinned by M1 Task 05.
"""

from __future__ import annotations

from ai_workflows.primitives.tools import fs, git, http, shell
from ai_workflows.primitives.tools.registry import ToolRegistry

__all__ = ["register_stdlib_tools"]


def register_stdlib_tools(registry: ToolRegistry) -> None:
    """Register the fs/shell/http/git stdlib tools onto ``registry``.

    Raises :class:`ToolAlreadyRegisteredError` if any of the canonical
    names are already present on ``registry`` — this catches a double
    registration (two calls) immediately rather than silently shadowing.
    """
    registry.register(
        "read_file",
        fs.read_file,
        "Read the full contents of a file as text (UTF-8 with latin-1 fallback).",
    )
    registry.register(
        "write_file",
        fs.write_file,
        "Write text content to a file, creating parent directories as needed.",
    )
    registry.register(
        "list_dir",
        fs.list_dir,
        "List entries in a directory, optionally filtered by a glob pattern.",
    )
    registry.register(
        "grep",
        fs.grep,
        "Regex-search files under a path and return file:line:text match entries.",
    )
    registry.register(
        "run_command",
        shell.run_command,
        "Run a shell command under CWD-containment, executable-allowlist, and timeout guards.",
    )
    registry.register(
        "http_fetch",
        http.http_fetch,
        "Fetch a URL with the given HTTP method and return the response as text.",
    )
    registry.register(
        "git_diff",
        git.git_diff,
        "Return the git diff output for a repository against the given ref.",
    )
    registry.register(
        "git_log",
        git.git_log,
        "Return the git log (oneline format) for a repository.",
    )
    registry.register(
        "git_apply",
        git.git_apply,
        "Apply a diff to a repository (refuses on a dirty working tree).",
    )
