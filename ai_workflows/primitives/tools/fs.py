"""Filesystem stdlib tools — ``read_file``, ``write_file``, ``list_dir``, ``grep``.

Produced by M1 Task 06 (P-13, P-14). All four callables follow the stdlib
convention: they take a :class:`pydantic_ai.RunContext` carrying our
:class:`~ai_workflows.primitives.llm.types.WorkflowDeps` as the first
positional parameter, and return a human-readable ``str`` — **never** a
bytes / dict / Pydantic model, and **never** raise to the LLM. This matches
the convention documented on ``M1-T05-ISS-03`` and pins the forensic
scanner in :mod:`ai_workflows.primitives.tools.registry` on the exact
bytes the model will receive.

Related
-------
* :mod:`ai_workflows.primitives.tools.registry` — wraps these tools with the
  forensic logger when assembled via
  :meth:`ToolRegistry.build_pydantic_ai_tools`.
* :mod:`ai_workflows.primitives.tools.stdlib` — the
  :func:`register_stdlib_tools` helper that binds these callables to a
  :class:`ToolRegistry` at workflow load time.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic_ai import RunContext

from ai_workflows.primitives.llm.types import WorkflowDeps

__all__ = ["read_file", "write_file", "list_dir", "grep"]


_TRUNCATION_MARKER = "\n... [truncated]"
_LIST_DIR_CAP = 500


def read_file(
    ctx: RunContext[WorkflowDeps],
    path: str,
    max_chars: int | None = None,
) -> str:
    """Return the contents of ``path``.

    Decoding falls back from UTF-8 to latin-1 so binary-adjacent files
    (PDF cover pages, CP1252-encoded logs) still yield a readable string
    rather than raising :class:`UnicodeDecodeError`. ``max_chars`` is
    optional; when set and exceeded, the return value is truncated and a
    ``... [truncated]`` marker is appended.

    ``ctx`` is accepted for stdlib convention (run-id availability in the
    forensic log line); the function itself does not consult it.
    """
    _ = ctx  # pydantic-ai convention — keep the ctx in the signature.
    p = Path(path)
    try:
        data = p.read_bytes()
    except FileNotFoundError:
        return f"Error: file not found: {path}"
    except PermissionError as e:
        return f"Error: permission denied reading {path}: {e}"
    except IsADirectoryError:
        return f"Error: not a regular file: {path}"
    except OSError as e:
        return f"Error: {type(e).__name__}: {e}"

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1", errors="replace")

    if max_chars is not None and len(text) > max_chars:
        text = text[:max_chars] + _TRUNCATION_MARKER
    return text


def write_file(
    ctx: RunContext[WorkflowDeps],
    path: str,
    content: str,
) -> str:
    """Write ``content`` to ``path``, creating parent directories as needed.

    On overwrite, the returned string calls the overwrite out explicitly so
    the model (and a human reading the forensic log) can see when an
    existing file was replaced — a common source of surprise in agentic
    pipelines.
    """
    _ = ctx
    p = Path(path)
    overwrite = p.exists()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    except PermissionError as e:
        return f"Error: permission denied writing {path}: {e}"
    except OSError as e:
        return f"Error: {type(e).__name__}: {e}"

    suffix = " (overwrote existing file)" if overwrite else ""
    return f"Wrote {len(content)} chars to {path}{suffix}"


def list_dir(
    ctx: RunContext[WorkflowDeps],
    path: str,
    pattern: str | None = None,
) -> str:
    """List entries in ``path``, optionally filtered by a glob ``pattern``.

    Results are sorted for deterministic output and capped at
    :data:`_LIST_DIR_CAP` (500) entries — the agent gets a ``... [truncated
    at 500 entries; total N]`` suffix on overflow rather than tens of
    thousands of filenames.
    """
    _ = ctx
    base = Path(path)
    if not base.exists():
        return f"Error: path not found: {path}"
    if not base.is_dir():
        return f"Error: not a directory: {path}"

    try:
        entries = (
            sorted(base.glob(pattern)) if pattern is not None else sorted(base.iterdir())
        )
    except OSError as e:
        return f"Error: {type(e).__name__}: {e}"

    displayed = entries[:_LIST_DIR_CAP]
    lines = [entry.name for entry in displayed]
    if len(entries) > _LIST_DIR_CAP:
        lines.append(
            f"... [truncated at {_LIST_DIR_CAP} entries; total {len(entries)}]"
        )
    return "\n".join(lines)


def grep(
    ctx: RunContext[WorkflowDeps],
    pattern: str,
    path: str,
    max_results: int = 100,
) -> str:
    """Return ``file:line:text`` matches for ``pattern`` under ``path``.

    When ``path`` names a file, the file is searched directly; when it names
    a directory, the search recurses and skips unreadable files silently.
    Results are capped at ``max_results``; overflow yields a ``... [capped
    at N matches]`` suffix.
    """
    _ = ctx
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return f"Error: invalid regex {pattern!r}: {e}"

    base = Path(path)
    if not base.exists():
        return f"Error: path not found: {path}"

    files: list[Path] = (
        [base] if base.is_file() else sorted(p for p in base.rglob("*") if p.is_file())
    )

    results: list[str] = []
    for f in files:
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(content.splitlines(), start=1):
            if regex.search(line):
                results.append(f"{f}:{i}:{line}")
                if len(results) >= max_results:
                    break
        if len(results) >= max_results:
            break

    if not results:
        return f"No matches for {pattern!r} in {path}"
    out = "\n".join(results)
    if len(results) >= max_results:
        out += f"\n... [capped at {max_results} matches]"
    return out
