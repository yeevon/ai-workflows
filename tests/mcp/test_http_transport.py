"""HTTP transport tests for aiw-mcp (M14 T01 + M14 T02).

Exercises the streamable-HTTP path end-to-end on ephemeral localhost
ports. No live provider — tool stubbing mirrors the stdio-path fixtures
at :mod:`tests.mcp.test_run_workflow`. Each test spins the server in a
background daemon thread on a reserved ephemeral port, polls HTTP until
the listener answers, exercises the behaviour, and lets pytest reap the
thread at process teardown (FastMCP does not expose a clean-stop hook;
documented in the milestone README §Risks).

M14 T01 tests (one per exit criterion 7 bullet):

1. ``test_http_transport_starts_and_serves_run_workflow`` — end-to-end
   ``run_workflow`` round-trip over HTTP via :class:`fastmcp.Client`.
2. ``test_http_cors_headers_present_when_origin_configured`` — CORS
   preflight + allow-origin echo when a single origin is permitted.
3. ``test_http_cors_headers_absent_when_origin_unconfigured`` — CORS
   preflight emits no ACAO header when no origin is configured.
4. ``test_http_default_bind_is_loopback`` — default ``--host`` is
   ``127.0.0.1`` (pinned at the Typer-option layer *and* verified by a
   live loopback connection on a server started without an explicit
   host).

M14 T02 tests (deep-analysis regression-guard carry-over):

5. ``test_http_cli_default_transport_is_stdio`` — protects the zero-
   flag MCP-host registrations by pinning Typer's ``--transport``
   default to ``"stdio"`` (M14-DA-05).
6. ``test_http_run_workflow_schema_parity_with_stdio`` — same payload
   invoked over stdio (direct ``tool.fn``) and over HTTP
   (``fastmcp.Client``) returns equal output dicts modulo the
   explicitly allowed-to-vary fields. Pins KDR-008 at the transport
   layer (M14-DA-SP).
7. ``test_http_list_runs_roundtrip`` — list-return serialisation path
   over HTTP (M14-DA-LR).
8. ``test_http_cancel_run_roundtrip`` — cancel envelope over HTTP
   (M14-DA-LR).
9. ``test_http_resume_run_roundtrip_returns_envelope`` — resume
   envelope over HTTP (M14-DA-LR). Deep resume-branch semantics stay
   pinned stdio-side in :mod:`tests.mcp.test_resume_run`.
"""

from __future__ import annotations

import inspect
import json
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastmcp import Client

from ai_workflows import workflows
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.mcp.__main__ import _cli, _run_http
from ai_workflows.mcp.schemas import (
    CancelRunInput,
    ListRunsInput,
    ResumeRunInput,
    RunWorkflowInput,
)
from ai_workflows.mcp.server import build_server
from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.tiers import LiteLLMRoute
from ai_workflows.workflows.planner import build_planner


class _StubLiteLLMAdapter:
    """Scripted LiteLLM-adapter stub — mirrors tests/mcp/test_run_workflow.py."""

    script: list[Any] = []
    call_count: int = 0

    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        self.route = route

    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict],
        response_format: Any = None,
    ) -> tuple[str, TokenUsage]:
        _StubLiteLLMAdapter.call_count += 1
        if not _StubLiteLLMAdapter.script:
            raise AssertionError("stub script exhausted")
        head = _StubLiteLLMAdapter.script.pop(0)
        if isinstance(head, BaseException):
            raise head
        text, cost = head
        return text, TokenUsage(
            input_tokens=11,
            output_tokens=17,
            cost_usd=cost,
            model=self.route.model,
        )

    @classmethod
    def reset(cls) -> None:
        cls.script = []
        cls.call_count = 0


@pytest.fixture(autouse=True)
def _reset_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    _StubLiteLLMAdapter.reset()
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _StubLiteLLMAdapter)


@pytest.fixture(autouse=True)
def _reensure_planner_registered() -> Iterator[None]:
    workflows._reset_for_tests()
    workflows.register("planner", build_planner)
    yield


@pytest.fixture(autouse=True)
def _redirect_default_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("AIW_STORAGE_DB", str(tmp_path / "storage.sqlite"))


def _reserve_ephemeral_port() -> int:
    """Reserve a free TCP port by binding (0), releasing, returning it.

    Standard "race-window" pattern — the port is free at release time
    and re-bound by the server thread within ~milliseconds. Good enough
    for hermetic single-runner CI; the spec notes this explicitly.
    """
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_http(url: str, *, timeout: float = 10.0) -> None:
    """Poll ``url`` until it stops connection-refusing or timeout fires.

    We send a GET; any HTTP response (even 404 / 405 / 406) proves the
    listener is bound and uvicorn is serving. Connection errors keep
    the loop alive.
    """
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


def _start_server(
    *,
    host: str = "127.0.0.1",
    port: int,
    cors_origins: list[str] | None = None,
) -> threading.Thread:
    """Spin the FastMCP HTTP server in a daemon thread.

    Returns the thread so tests can ``join(timeout=...)`` on teardown
    if they want; daemon=True means pytest process teardown reaps it
    regardless.
    """
    server = build_server()

    def _run() -> None:
        _run_http(
            server,
            host=host,
            port=port,
            cors_origins=cors_origins or [],
        )

    thread = threading.Thread(target=_run, daemon=True, name=f"aiw-mcp-http:{port}")
    thread.start()
    return thread


def _valid_explorer_json() -> str:
    return json.dumps(
        {
            "summary": "Three-step delivery.",
            "considerations": ["Copy tone", "CTA placement"],
            "assumptions": ["Design system stable"],
        }
    )


def _valid_plan_json() -> str:
    return json.dumps(
        {
            "goal": "Ship the marketing page.",
            "summary": "Three-step delivery of the static hero + CTA page.",
            "steps": [
                {
                    "index": 1,
                    "title": "Draft hero copy",
                    "rationale": "Lock tone before layout.",
                    "actions": ["Sketch headline", "List CTAs"],
                }
            ],
        }
    )


@pytest.mark.asyncio
async def test_http_transport_starts_and_serves_run_workflow() -> None:
    """AC-1: HTTP transport serves ``run_workflow`` with the stdio shape.

    Starts the server on an ephemeral port, connects a :class:`fastmcp.Client`
    over HTTP, and invokes ``run_workflow`` against the stubbed planner.
    Asserts the gate-pause projection shape matches the stdio-path test
    in ``tests/mcp/test_run_workflow.py::test_run_workflow_pauses_at_gate_and_stamps_cost``.
    """
    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
    ]
    port = _reserve_ephemeral_port()
    _start_server(port=port)
    url = f"http://127.0.0.1:{port}/mcp/"
    _wait_for_http(url)

    async with Client(url) as client:
        result = await client.call_tool(
            "run_workflow",
            {
                "payload": {
                    "workflow_id": "planner",
                    "inputs": {
                        "goal": "Ship the marketing page.",
                        "context": None,
                        "max_steps": 10,
                    },
                    "run_id": "run-m14-http",
                }
            },
        )

    payload = result.structured_content or result.data
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()
    assert payload["run_id"] == "run-m14-http"
    assert payload["status"] == "pending"
    assert payload["awaiting"] == "gate"
    assert payload["plan"] is not None
    assert payload["total_cost_usd"] == pytest.approx(0.0033)
    assert payload["error"] is None


def test_http_cors_headers_present_when_origin_configured() -> None:
    """AC-2: CORS preflight echoes ACAO when the origin is allow-listed."""
    origin = "http://localhost:4321"
    port = _reserve_ephemeral_port()
    _start_server(port=port, cors_origins=[origin])
    url = f"http://127.0.0.1:{port}/mcp/"
    _wait_for_http(url)

    response = httpx.request(
        "OPTIONS",
        url,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=5.0,
    )
    assert response.headers.get("access-control-allow-origin") == origin
    allow_methods = response.headers.get("access-control-allow-methods", "")
    assert "POST" in allow_methods


def test_http_cors_headers_absent_when_origin_unconfigured() -> None:
    """AC-3: Same preflight with no allow-list → no ACAO header."""
    port = _reserve_ephemeral_port()
    _start_server(port=port, cors_origins=[])
    url = f"http://127.0.0.1:{port}/mcp/"
    _wait_for_http(url)

    response = httpx.request(
        "OPTIONS",
        url,
        headers={
            "Origin": "http://localhost:4321",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=5.0,
    )
    assert "access-control-allow-origin" not in {k.lower() for k in response.headers}


def test_http_default_bind_is_loopback() -> None:
    """AC-4: Default ``--host`` is ``127.0.0.1`` and loopback connects succeed.

    Two-pronged check (per spec — inspecting the bound socket is not
    exposed by FastMCP / uvicorn cleanly, so we pin the Typer default
    *and* verify a live loopback connection on a server started without
    an explicit host override).
    """
    host_option = inspect.signature(_cli).parameters["host"].default
    assert host_option.default == "127.0.0.1", (
        "Typer --host default must be 127.0.0.1 (loopback) — M14 exit criterion 4"
    )

    port = _reserve_ephemeral_port()
    _start_server(port=port)
    _wait_for_http(f"http://127.0.0.1:{port}/mcp/")

    with httpx.Client(timeout=2.0) as client:
        response = client.get(f"http://127.0.0.1:{port}/mcp/")
    assert response.status_code < 500, (
        f"Loopback GET should reach the listener, got {response.status_code}"
    )


# ---------------------------------------------------------------------------
# M14 T02 — deep-analysis regression-guard carry-over
# ---------------------------------------------------------------------------


def test_http_cli_default_transport_is_stdio() -> None:
    """M14-DA-05: the zero-flag ``aiw-mcp`` invocation must stay stdio.

    Every existing MCP host registration (Claude Code, Cursor, Zed)
    launches ``aiw-mcp`` with no flags and expects stdio. A regression
    that silently flipped the Typer default to ``"http"`` would break
    every registration, and the stdio-path tests in :mod:`tests.mcp`
    never shell through ``_cli`` — they call :func:`build_server`
    directly. Pinning the Typer-option default is the only signal that
    catches the flip.
    """
    transport_option = inspect.signature(_cli).parameters["transport"].default
    assert transport_option.default == "stdio", (
        "aiw-mcp --transport default must remain 'stdio' — "
        "M14 exit criterion 10 / backwards compatibility invariant"
    )


@pytest.mark.asyncio
async def test_http_run_workflow_schema_parity_with_stdio() -> None:
    """M14-DA-SP: HTTP and stdio ``run_workflow`` serialise the same shape.

    KDR-008 (MCP schemas are the public contract). A FastMCP version
    bump that silently changed the HTTP serialiser without changing the
    stdio serialiser (or vice versa) would let consumers observe
    divergent shapes across transports. This test feeds identical
    payloads to both paths and asserts the output dicts are equal
    modulo the explicitly allowed-to-vary fields (``run_id`` — one
    invocation per path needs its own id to avoid colliding on the
    Storage row; ``gate_context.checkpoint_ts`` — projection-time
    ISO-8601 stamp; ``gate_context.gate_id`` — includes a checkpoint
    thread identifier that differs per invocation).
    """
    # Stdio path — direct tool invocation.
    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
    ]
    server = build_server()
    stdio_tool = await server.get_tool("run_workflow")
    stdio_result = await stdio_tool.fn(
        RunWorkflowInput(
            workflow_id="planner",
            inputs={
                "goal": "Ship the marketing page.",
                "context": None,
                "max_steps": 10,
            },
            run_id="run-m14-parity-stdio",
        )
    )
    stdio_payload: dict[str, Any] = stdio_result.model_dump()

    # HTTP path — same payload through fastmcp.Client on an ephemeral port.
    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
    ]
    port = _reserve_ephemeral_port()
    _start_server(port=port)
    url = f"http://127.0.0.1:{port}/mcp/"
    _wait_for_http(url)

    async with Client(url) as client:
        call_result = await client.call_tool(
            "run_workflow",
            {
                "payload": {
                    "workflow_id": "planner",
                    "inputs": {
                        "goal": "Ship the marketing page.",
                        "context": None,
                        "max_steps": 10,
                    },
                    "run_id": "run-m14-parity-http",
                }
            },
        )
    http_payload = call_result.structured_content or call_result.data
    if hasattr(http_payload, "model_dump"):
        http_payload = http_payload.model_dump()
    assert isinstance(http_payload, dict)

    # Both paths hit the same gate-pause terminal. Strip the fields that
    # legitimately differ per invocation; everything else must match.
    allowed_to_vary = {"run_id"}
    stdio_core = {k: v for k, v in stdio_payload.items() if k not in allowed_to_vary}
    http_core = {k: v for k, v in http_payload.items() if k not in allowed_to_vary}

    # gate_context carries per-checkpoint volatile fields (checkpoint_ts,
    # gate_id). Diff the sub-dict's stable keys explicitly rather than
    # the whole thing.
    stdio_gc = stdio_core.pop("gate_context", None)
    http_gc = http_core.pop("gate_context", None)
    _divergent = [
        (k, stdio_core.get(k), http_core.get(k))
        for k in set(stdio_core) | set(http_core)
        if stdio_core.get(k) != http_core.get(k)
    ]
    assert stdio_core == http_core, (
        f"HTTP/stdio schema divergence (top-level): "
        f"stdio-only={set(stdio_core) - set(http_core)}, "
        f"http-only={set(http_core) - set(stdio_core)}, "
        f"diff={_divergent}"
    )
    assert (stdio_gc is None) == (http_gc is None), (
        "gate_context presence must match across transports"
    )
    if stdio_gc is not None and http_gc is not None:
        # Same keyset; stable keys must match value-for-value.
        assert set(stdio_gc.keys()) == set(http_gc.keys()), (
            f"gate_context keys diverge: stdio={set(stdio_gc)}, http={set(http_gc)}"
        )
        stable_keys = {"gate_prompt", "workflow_id"}
        for key in stable_keys & set(stdio_gc.keys()):
            assert stdio_gc[key] == http_gc[key], (
                f"gate_context[{key!r}] diverges: "
                f"stdio={stdio_gc[key]!r} vs http={http_gc[key]!r}"
            )


@pytest.mark.asyncio
async def test_http_list_runs_roundtrip(tmp_path: Path) -> None:
    """M14-DA-LR: ``list_runs`` (list-return shape) serialises over HTTP.

    T01's HTTP suite only exercises ``run_workflow``. A FastMCP
    regression on list-return serialisation (e.g. a JSON null handling
    change, a field drop on ``RunSummary``) would miss the single tool
    with a list return. Seed two rows via ``SQLiteStorage``, call
    ``list_runs`` via HTTP, assert both run_ids land.
    """
    db = tmp_path / "storage.sqlite"
    storage = await SQLiteStorage.open(db)
    await storage.create_run("run-m14-lr-a", "planner", None)
    await storage.create_run("run-m14-lr-b", "planner", None)

    port = _reserve_ephemeral_port()
    _start_server(port=port)
    url = f"http://127.0.0.1:{port}/mcp/"
    _wait_for_http(url)

    async with Client(url) as client:
        call_result = await client.call_tool(
            "list_runs",
            {"payload": ListRunsInput().model_dump()},
        )

    rows = call_result.structured_content or call_result.data
    # fastmcp.Client wraps list returns in {"result": [...]} under the
    # structured-content envelope; unwrap if present.
    if isinstance(rows, dict) and "result" in rows:
        rows = rows["result"]
    assert isinstance(rows, list), f"expected list return, got {type(rows).__name__}"
    run_ids = {row["run_id"] if isinstance(row, dict) else row.run_id for row in rows}
    assert {"run-m14-lr-a", "run-m14-lr-b"}.issubset(run_ids)


@pytest.mark.asyncio
async def test_http_cancel_run_roundtrip(tmp_path: Path) -> None:
    """M14-DA-LR: ``cancel_run`` envelope serialises over HTTP.

    Seed a pending run, call ``cancel_run`` via HTTP, assert the
    returned envelope's ``status`` is ``"cancelled"`` and the Storage
    row flipped.
    """
    db = tmp_path / "storage.sqlite"
    storage = await SQLiteStorage.open(db)
    await storage.create_run("run-m14-cancel-http", "planner", None)

    port = _reserve_ephemeral_port()
    _start_server(port=port)
    url = f"http://127.0.0.1:{port}/mcp/"
    _wait_for_http(url)

    async with Client(url) as client:
        call_result = await client.call_tool(
            "cancel_run",
            {"payload": CancelRunInput(run_id="run-m14-cancel-http").model_dump()},
        )

    payload = call_result.structured_content or call_result.data
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()
    assert isinstance(payload, dict)
    assert payload["run_id"] == "run-m14-cancel-http"
    assert payload["status"] == "cancelled"

    # Storage-side flip.
    reopen = await SQLiteStorage.open(db)
    rows = await reopen.list_runs(limit=5)
    row = next(r for r in rows if r["run_id"] == "run-m14-cancel-http")
    assert row["status"] == "cancelled"


@pytest.mark.asyncio
async def test_http_resume_run_roundtrip_returns_envelope() -> None:
    """M14-DA-LR: ``resume_run`` envelope serialises over HTTP.

    Run a workflow to the gate pause over HTTP, then resume with
    ``approved`` over the same transport and assert the completed
    envelope shape. Deep resume-branch semantics (reject, re-gate) stay
    pinned stdio-side — this test only needs to prove the HTTP wire
    round-trip returns the expected envelope for the approve branch.
    """
    # Four stub entries: two feed the initial run-to-gate, two feed the
    # post-resume path. In this workflow the planner halts at a
    # human-gate interrupt after the synth node, so resume re-enters at
    # the gate only; the stub has enough budget either way.
    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
        (_valid_explorer_json(), 0.0012),
        (_valid_plan_json(), 0.0021),
    ]

    port = _reserve_ephemeral_port()
    _start_server(port=port)
    url = f"http://127.0.0.1:{port}/mcp/"
    _wait_for_http(url)

    async with Client(url) as client:
        run_result = await client.call_tool(
            "run_workflow",
            {
                "payload": {
                    "workflow_id": "planner",
                    "inputs": {
                        "goal": "Ship the marketing page.",
                        "context": None,
                        "max_steps": 10,
                    },
                    "run_id": "run-m14-resume-http",
                }
            },
        )
        run_payload = run_result.structured_content or run_result.data
        if hasattr(run_payload, "model_dump"):
            run_payload = run_payload.model_dump()
        assert run_payload["status"] == "pending"
        assert run_payload["awaiting"] == "gate"

        resume_result = await client.call_tool(
            "resume_run",
            {
                "payload": ResumeRunInput(
                    run_id="run-m14-resume-http", gate_response="approved"
                ).model_dump()
            },
        )

    resume_payload = resume_result.structured_content or resume_result.data
    if hasattr(resume_payload, "model_dump"):
        resume_payload = resume_payload.model_dump()
    assert isinstance(resume_payload, dict)
    assert resume_payload["run_id"] == "run-m14-resume-http"
    assert resume_payload["status"] == "completed"
    assert resume_payload["plan"] is not None
    assert resume_payload["error"] is None
    assert resume_payload["total_cost_usd"] == pytest.approx(0.0033)
