"""stdio-mode entry point for the ai-workflows MCP server.

M4 Task 06 ships the surface as a standalone process MCP clients
(Claude Code, Cursor, Zed, ...) can register over stdio. FastMCP's
``server.run()`` defaults to the stdio transport, so the entry point
is a thin wrapper around :func:`ai_workflows.mcp.build_server` —
``configure_logging(level="INFO")`` first (logs land on stderr per
:mod:`ai_workflows.primitives.logging` so stdout stays clean for the
JSON-RPC channel), then ``server.run()``.

Invoke as:

* ``python -m ai_workflows.mcp``
* ``uv run aiw-mcp`` (console script registered in
  [pyproject.toml](../../pyproject.toml) ``[project.scripts]``).

Registration with Claude Code is documented at
[design_docs/phases/milestone_4_mcp/mcp_setup.md](../../design_docs/phases/milestone_4_mcp/mcp_setup.md).

Relationship to other modules
-----------------------------
* :mod:`ai_workflows.mcp.server` — the FastMCP factory this module
  drives.
* :mod:`ai_workflows.primitives.logging` — stderr-routed structured
  logging so stdout stays reserved for the JSON-RPC frames.
"""

from __future__ import annotations

from ai_workflows.mcp.server import build_server
from ai_workflows.primitives.logging import configure_logging


def main() -> None:
    """Start the MCP server over stdio.

    Logs are routed to stderr (``configure_logging``) so the stdio
    transport's stdout channel stays clean for JSON-RPC. Returns only
    when the peer closes the connection.
    """
    configure_logging(level="INFO")
    server = build_server()
    server.run()


if __name__ == "__main__":
    main()
