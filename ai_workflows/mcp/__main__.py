"""Entry point for the ai-workflows MCP server (M4 T06 / M14 T01).

M4 Task 06 shipped the surface as a standalone process MCP clients
(Claude Code, Cursor, Zed, ...) can register over stdio — FastMCP's
``server.run()`` defaults to the stdio transport, so the original
entry point was a thin wrapper around :func:`ai_workflows.mcp.build_server`.

M14 Task 01 adds a Typer-based flag surface so the same server can also
be served over streamable-HTTP for browser-origin consumers (Astro /
React / Vue / any JS runtime without subprocess access). Stdio remains
the default — every existing MCP-host registration of ``aiw-mcp`` works
unchanged. The HTTP path attaches Starlette's ``CORSMiddleware`` when
``--cors-origin`` is passed; with no origin, same-origin is the secure
default (no ``Access-Control-Allow-Origin`` header emitted).

Invoke as:

* ``python -m ai_workflows.mcp`` — stdio (default).
* ``uv run aiw-mcp`` — stdio, via the console script registered in
  [pyproject.toml](../../pyproject.toml) ``[project.scripts]``.
* ``uv run aiw-mcp --transport http`` — streamable-HTTP on 127.0.0.1:8000.
* ``uv run aiw-mcp --transport http --port 8099 --cors-origin http://localhost:4321``
  — custom port + permissive CORS for one origin.

Registration with Claude Code is documented at
[design_docs/phases/milestone_4_mcp/mcp_setup.md](../../design_docs/phases/milestone_4_mcp/mcp_setup.md).
HTTP-mode notes for external (non-subprocess) hosts live at
`design_docs/phases/milestone_9_skill/skill_install.md` §5.

Relationship to other modules
-----------------------------
* :mod:`ai_workflows.mcp.server` — the FastMCP factory this module
  drives. Byte-identical across transports — the HTTP mode reuses
  ``build_server()`` without a second factory (M14 T01 exit criterion 6).
* :mod:`ai_workflows.primitives.logging` — stderr-routed structured
  logging so stdout stays reserved for JSON-RPC frames on stdio; on
  HTTP, uvicorn owns the socket and stderr framing is unchanged.
"""

from __future__ import annotations

from typing import Any

import typer
from dotenv import load_dotenv

# 0.1.1 patch: load a cwd-local ``.env`` before :mod:`ai_workflows.mcp`
# submodules resolve any env-var lookup (LiteLLM / Claude Code tiers).
# ``override=False`` keeps shell-exported vars winning — mirrors the
# CLI-surface precedence.
load_dotenv(override=False)

from ai_workflows.mcp.server import build_server  # noqa: E402
from ai_workflows.primitives.logging import configure_logging  # noqa: E402

app = typer.Typer(add_completion=False, help="ai-workflows MCP server.")


@app.command()
def _cli(
    transport: str = typer.Option(
        "stdio",
        "--transport",
        help=(
            "Transport. 'stdio' (default) matches every existing MCP host. "
            "'http' serves over streamable-HTTP for browser-origin consumers."
        ),
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        help=(
            "Bind address when --transport http. Loopback default; pass "
            "0.0.0.0 only if you own every process on the host."
        ),
    ),
    port: int = typer.Option(
        8000,
        "--port",
        min=1,
        max=65535,
        help="TCP port when --transport http.",
    ),
    cors_origin: list[str] = typer.Option(
        None,
        "--cors-origin",
        help=(
            "Origin to permit via CORS. Repeatable. Empty (default) means "
            "same-origin only. Exact-match; no regex."
        ),
    ),
) -> None:
    """Start the MCP server on the selected transport.

    Logs route to stderr (``configure_logging``). On stdio the JSON-RPC
    channel owns stdout; on HTTP the uvicorn loop owns the socket and
    stdout is unused for framing. Returns when the peer closes the
    connection (stdio) or the HTTP server shuts down (http).
    """
    if transport not in ("stdio", "http"):
        raise typer.BadParameter(
            f"--transport must be 'stdio' or 'http', got {transport!r}"
        )

    configure_logging(level="INFO")
    server = build_server()
    if transport == "stdio":
        server.run()
        return
    _run_http(server, host=host, port=port, cors_origins=cors_origin or [])


def _run_http(
    server: Any,
    *,
    host: str,
    port: int,
    cors_origins: list[str],
) -> None:
    """Run the FastMCP server over streamable-HTTP with optional CORS.

    FastMCP 3.2.4 accepts an ASGI ``middleware`` list through its
    transport kwargs: ``server.run(transport="http", middleware=[...])``
    flows through to ``run_http_async`` → ``http_app(middleware=...)``.
    ``ASGIMiddleware`` is Starlette's ``Middleware`` (see
    ``fastmcp.server.mixins.transport``); we build it here with
    Starlette's own import to avoid the FastMCP-internal re-export.

    The spec (``design_docs/phases/milestone_14_mcp_http/task_01_http_transport.md``
    §Risks #2) authorises the Builder to pick the correct accessor at
    implementation time — ``server.add_middleware(CORSMiddleware, ...)``
    does not match FastMCP 3.2.4's signature (that method takes a
    FastMCP-internal ``Middleware`` instance, not a Starlette class).
    """
    middleware: list[Any] | None = None
    if cors_origins:
        from starlette.middleware import Middleware  # noqa: PLC0415
        from starlette.middleware.cors import CORSMiddleware  # noqa: PLC0415

        middleware = [
            Middleware(
                CORSMiddleware,
                allow_origins=cors_origins,
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["*"],
            )
        ]

    kwargs: dict[str, Any] = {"host": host, "port": port}
    if middleware is not None:
        kwargs["middleware"] = middleware
    server.run(transport="http", **kwargs)


def main() -> None:
    """Console-script entry point — delegate to Typer for sys.argv parsing.

    ``aiw-mcp`` is registered in ``pyproject.toml`` as
    ``ai_workflows.mcp.__main__:main``. Typer's ``@app.command()``
    decorator does **not** rewrite the decorated function to parse
    ``sys.argv`` when called directly; calling ``app()`` does. Keeping
    ``main`` as a plain wrapper preserves the console-script surface
    while routing through Typer for flag parsing.
    """
    app()


if __name__ == "__main__":
    main()
