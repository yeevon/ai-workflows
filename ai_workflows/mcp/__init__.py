"""MCP surface (FastMCP).

Per [architecture.md §4.4](../../design_docs/architecture.md), the MCP
server exposes workflows as ``@mcp.tool()``-decorated pydantic
functions over FastMCP's JSON-RPC transport (KDR-002, KDR-008). M1
Task 12 created this package as an empty shell so the four-layer
import-linter contract could reference it; M4 Task 01 populates it with
the ``build_server()`` factory and the pydantic I/O models in
:mod:`ai_workflows.mcp.schemas`. The four tool bodies themselves land
in M4 T02 (``run_workflow``), T03 (``resume_run``), T04 (``list_runs``),
T05 (``cancel_run``).

Architectural rule (enforced by ``import-linter``): ``mcp`` is part of
the surfaces layer and may import :mod:`ai_workflows.workflows` and
:mod:`ai_workflows.primitives` — but nothing imports ``mcp``.
"""

from ai_workflows.mcp.server import build_server

__all__ = ["build_server"]
