"""MCP surface (FastMCP). Populated in M4.

Per [architecture.md §4.4](../../design_docs/architecture.md), the MCP
server exposes workflows as ``@mcp.tool()``-decorated pydantic
functions over FastMCP's JSON-RPC transport (KDR-002, KDR-008). M1
Task 12 creates this package as an empty shell so the four-layer
import-linter contract can reference it; the tools themselves land in
M4.

Architectural rule (enforced by ``import-linter``): ``mcp`` is part of
the surfaces layer and may import :mod:`ai_workflows.workflows` and
:mod:`ai_workflows.primitives` — but nothing imports ``mcp``.
"""
