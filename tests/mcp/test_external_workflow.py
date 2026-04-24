"""M16 Task 01 — MCP surface parity for external workflow modules.

Two tests:

1. Stdio path — calls ``server.get_tool("run_workflow").fn(...)``
   directly (same pattern as :mod:`tests.mcp.test_run_workflow`) after
   loading an external stub via ``load_extra_workflow_modules``.
2. HTTP path — spins the FastMCP HTTP server on an ephemeral port
   (same pattern as :mod:`tests.mcp.test_http_transport`) after
   loading the stub, and invokes ``run_workflow`` via
   :class:`fastmcp.Client`.

Both exercises prove AC-10 (MCP surface parity) against a workflow
sourced from ``AIW_EXTRA_WORKFLOW_MODULES``. The stub graph is a
single pass-through node, so no LLM adapter fires — hermetic.
"""

from __future__ import annotations

import inspect
import socket
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import httpx
import pytest
from fastmcp import Client

from ai_workflows import workflows
from ai_workflows.mcp import build_server
from ai_workflows.mcp.__main__ import _cli, _run_http
from ai_workflows.mcp.schemas import RunWorkflowInput
from ai_workflows.workflows import load_extra_workflow_modules

_STUB_WORKFLOW_SOURCE = """\
'''Stub external workflow for M16 T01 MCP integration test.'''
from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from ai_workflows.workflows import register


FINAL_STATE_KEY = "plan"


class _StubState(TypedDict, total=False):
    run_id: str
    input: dict[str, Any]
    plan: dict[str, Any] | None


def initial_state(run_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
    return {"run_id": run_id, "input": dict(inputs), "plan": None}


def _finalize(state: _StubState) -> dict[str, Any]:
    goal = state.get("input", {}).get("goal", "")
    return {"plan": {"echo": goal}}


def build() -> StateGraph:
    g: StateGraph = StateGraph(_StubState)
    g.add_node("finalize", _finalize)
    g.add_edge(START, "finalize")
    g.add_edge("finalize", END)
    return g


def m16_ext_mcp_stub_tier_registry() -> dict[str, Any]:
    return {}


register("m16_ext_mcp_stub", build)
"""


@pytest.fixture
def _stub_external_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[str]:
    """Write the stub module on sys.path + load it via the loader."""
    stub_path = tmp_path / "m16_ext_mcp_stub.py"
    stub_path.write_text(_STUB_WORKFLOW_SOURCE)
    monkeypatch.syspath_prepend(str(tmp_path))
    workflows._reset_for_tests()
    monkeypatch.setenv("AIW_EXTRA_WORKFLOW_MODULES", "m16_ext_mcp_stub")
    load_extra_workflow_modules()
    yield "m16_ext_mcp_stub"
    workflows._reset_for_tests()
    sys.modules.pop("m16_ext_mcp_stub", None)


@pytest.fixture(autouse=True)
def _redirect_default_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("AIW_STORAGE_DB", str(tmp_path / "storage.sqlite"))


@pytest.mark.asyncio
async def test_stdio_run_workflow_dispatches_external_module(
    _stub_external_workflow: str,
) -> None:
    """AC-10 stdio path: external workflow runs through ``run_workflow``."""
    server = build_server()
    tool = await server.get_tool("run_workflow")
    payload = RunWorkflowInput(
        workflow_id=_stub_external_workflow,
        inputs={"goal": "mcp-stdio-goal"},
        run_id="run-m16-stdio",
    )

    result = await tool.fn(payload)

    assert result.run_id == "run-m16-stdio"
    assert result.status == "completed"
    assert result.plan == {"echo": "mcp-stdio-goal"}
    assert result.error is None


def _reserve_ephemeral_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_http(url: str, *, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            httpx.get(url, timeout=1.0)
            return
        except httpx.TransportError as exc:
            last_error = exc
            time.sleep(0.1)
    raise RuntimeError(
        f"HTTP server at {url} did not come up within {timeout}s; last={last_error!r}"
    )


@pytest.mark.asyncio
async def test_http_run_workflow_dispatches_external_module(
    _stub_external_workflow: str,
) -> None:
    """AC-10 HTTP path: external workflow runs through ``run_workflow`` over HTTP."""
    port = _reserve_ephemeral_port()
    server = build_server()

    def _run() -> None:
        _run_http(server, host="127.0.0.1", port=port, cors_origins=[])

    thread = threading.Thread(
        target=_run, daemon=True, name=f"aiw-mcp-m16-http:{port}"
    )
    thread.start()

    url = f"http://127.0.0.1:{port}/mcp/"
    _wait_for_http(url)

    async with Client(url) as client:
        result = await client.call_tool(
            "run_workflow",
            {
                "payload": {
                    "workflow_id": _stub_external_workflow,
                    "inputs": {"goal": "mcp-http-goal"},
                    "run_id": "run-m16-http",
                }
            },
        )

    payload = result.structured_content or result.data
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()
    assert payload["run_id"] == "run-m16-http"
    assert payload["status"] == "completed"
    assert payload["plan"] == {"echo": "mcp-http-goal"}
    assert payload["error"] is None


def test_mcp_cli_exposes_workflow_module_option() -> None:
    """AC-3 (ISS-01): ``aiw-mcp`` Typer command declares
    ``--workflow-module`` with the repeatable list-typed Typer option.

    Signature-level pin so a refactor that drops the flag, renames it,
    or changes its type-annotation shape fails this test without
    needing to spin up the server. Symmetric to the ``aiw`` coverage
    in ``tests/cli/test_external_workflow.py`` which exercises the
    flag end-to-end via ``CliRunner``.
    """
    params = inspect.signature(_cli).parameters
    assert "workflow_module" in params, (
        "_cli must accept the --workflow-module option"
    )
    option = params["workflow_module"].default
    # Typer's OptionInfo carries the CLI-flag names under ``param_decls``
    # (positional values passed to ``typer.Option``). A public attribute;
    # the fallback below handles future Typer versions that rename it.
    decls = getattr(option, "param_decls", None) or getattr(
        option, "option_decls", ()
    )
    assert "--workflow-module" in decls, (
        f"expected --workflow-module in param decls, got {decls!r}"
    )
    # Typer's default-list pattern: the option's default is a typer
    # OptionInfo wrapping the real Python default (an empty list).
    assert option.default == [], (
        f"expected --workflow-module default to be [], got {option.default!r}"
    )


def test_mcp_cli_workflow_module_flag_calls_loader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-3 (ISS-01): ``aiw-mcp --workflow-module <dotted>`` threads
    the dotted path through to ``load_extra_workflow_modules``.

    Monkeypatches the loader in the ``__main__`` module's namespace
    to capture the CLI-sourced list without spinning the server up
    (the server would then block forever on stdio / bind uvicorn —
    both unhelpful for a signature-level test). Returns before
    ``build_server()`` fires by making the patched loader raise an
    ``ExternalWorkflowImportError`` after capturing its argument.
    """
    from typer.testing import CliRunner

    import ai_workflows.mcp.__main__ as mcp_main

    captured: dict[str, list[str] | None] = {"cli_modules": None}

    def _spy(*, cli_modules: list[str] | None = None) -> list[str]:
        captured["cli_modules"] = (
            list(cli_modules) if cli_modules is not None else None
        )
        # Abort before build_server() to keep the test fast; the
        # MCP `_cli` converts ExternalWorkflowImportError to exit 2
        # and returns, so no uvicorn spin-up happens.
        raise mcp_main.ExternalWorkflowImportError(
            "stop-before-server-spin-up",
            RuntimeError("spy abort"),
        )

    monkeypatch.setattr(mcp_main, "load_extra_workflow_modules", _spy)
    # Ensure no stray env var leaks in.
    monkeypatch.delenv("AIW_EXTRA_WORKFLOW_MODULES", raising=False)

    runner = CliRunner()
    result = runner.invoke(
        mcp_main.app,
        ["--workflow-module", "pkg.workflows.alpha",
         "--workflow-module", "pkg.workflows.beta"],
    )

    assert captured["cli_modules"] == [
        "pkg.workflows.alpha",
        "pkg.workflows.beta",
    ], f"loader received {captured['cli_modules']!r}"
    # Typer maps our Exit(code=2) to exit_code 2.
    assert result.exit_code == 2, result.output
