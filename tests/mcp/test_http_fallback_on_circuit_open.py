"""HTTP transport — CircuitOpen cascade test (M15 Task 03).

Pins the HTTP-envelope shape when a TieredNode cascade fires under a
tripped circuit breaker.  One hermetic test starts the MCP server in a
background daemon thread on an ephemeral port, installs a stub
``_FallbackStubLiteLLMAdapter`` so the primary route raises
``CircuitOpen`` and a fallback route returns a valid response, invokes
``run_workflow`` over the MCP HTTP transport, and asserts the successful
fallback output in the response envelope.

This satisfies M15 exit criterion #5 and AC-5 from the task spec:
absorbs audit finding #12 — the HTTP envelope shape on CircuitOpen is
now pinned.

Relationship to other modules
-----------------------------
* :mod:`tests.mcp.test_http_transport` — the daemon-thread HTTP server
  pattern is identical; helper functions ``_reserve_ephemeral_port``,
  ``_wait_for_http``, and ``_start_server`` are reproduced here so this
  file is self-contained.
* :mod:`ai_workflows.graph.tiered_node` — ``LiteLLMAdapter`` is
  monkeypatched to the stub so no live provider call fires.
* :mod:`ai_workflows.primitives.circuit_breaker` — ``CircuitOpen`` is
  raised by the primary stub to trigger the cascade.
"""

from __future__ import annotations

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
from pydantic import BaseModel

from ai_workflows import workflows
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.mcp.__main__ import _run_http
from ai_workflows.mcp.server import build_server
from ai_workflows.primitives.circuit_breaker import CircuitOpen
from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig
from ai_workflows.workflows.spec import LLMStep, WorkflowSpec, register_workflow

# ---------------------------------------------------------------------------
# Synthetic input/output schemas
# ---------------------------------------------------------------------------


class _FallbackInput(BaseModel):
    """Input schema for the fallback cascade synthetic test workflow."""

    goal: str


class _FallbackOutput(BaseModel):
    """Output schema for the fallback cascade synthetic test workflow."""

    result: str


# ---------------------------------------------------------------------------
# Stub adapter — mirrors tests/mcp/test_http_transport.py:75-114
# ---------------------------------------------------------------------------


class _FallbackStubLiteLLMAdapter:
    """Scripted LiteLLM-adapter stub for fallback cascade testing.

    Primary route (``gemini/primary``) raises ``CircuitOpen`` to trigger
    the cascade.  Fallback route (``gemini/fallback``) returns a valid
    ``_FallbackOutput`` JSON string so the ``ValidatorNode`` succeeds.
    """

    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        """Bind the route so ``complete`` can inspect the model string."""
        self.route = route

    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict],
        response_format: Any = None,
    ) -> tuple[str, TokenUsage]:
        """Raise ``CircuitOpen`` for the primary route; return valid JSON for fallback."""
        if self.route.model == "gemini/primary":
            raise CircuitOpen("breaker-open")
        # Fallback route: return valid JSON that matches _FallbackOutput.
        text = json.dumps({"result": "fallback-ok"})
        return text, TokenUsage(
            input_tokens=1,
            output_tokens=1,
            cost_usd=0.0,
            model=self.route.model,
        )


# ---------------------------------------------------------------------------
# Test-isolation fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    """Clear the workflow registry before and after each test.

    Prevents synthetic specs registered in one test leaking into another.
    Pattern mirrors tests/mcp/test_http_transport.py:117-121.
    """
    workflows._reset_for_tests()
    yield
    workflows._reset_for_tests()


@pytest.fixture(autouse=True)
def _redirect_default_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Redirect Storage and checkpoint paths to tmp_path for test isolation."""
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("AIW_STORAGE_DB", str(tmp_path / "storage.sqlite"))
    yield


# ---------------------------------------------------------------------------
# HTTP daemon-thread helpers (reproduced from test_http_transport.py)
# ---------------------------------------------------------------------------


def _reserve_ephemeral_port() -> int:
    """Reserve a free TCP port by binding (0), releasing, returning it."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_http(url: str, *, timeout: float = 10.0) -> None:
    """Poll ``url`` until it stops connection-refusing or timeout fires."""
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


def _start_server(*, port: int) -> threading.Thread:
    """Spin the FastMCP HTTP server in a daemon thread on ``port``."""
    server = build_server()

    def _run() -> None:
        _run_http(server, host="127.0.0.1", port=port, cors_origins=[])

    thread = threading.Thread(target=_run, daemon=True, name=f"aiw-mcp-http:{port}")
    thread.start()
    return thread


# ---------------------------------------------------------------------------
# AC-5 — HTTP CircuitOpen cascade test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_http_run_workflow_fallback_cascade_on_circuit_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-5: HTTP envelope is correct when cascade fires under a tripped breaker.

    Setup:
    1. Registry cleared by ``_clean_registry`` autouse fixture.
    2. Register a synthetic ``WorkflowSpec`` (``fallback_cascade_test``)
       with one LLMStep whose tier has ``fallback=[LiteLLMRoute("gemini/fallback")]``.
    3. Monkeypatch ``LiteLLMAdapter`` to ``_FallbackStubLiteLLMAdapter`` so
       the primary route (``gemini/primary``) raises ``CircuitOpen`` and the
       fallback route (``gemini/fallback``) returns valid JSON.
    4. Start the HTTP server in a daemon thread on an ephemeral port.

    Assertions (conjunctive — no "or"):
    (a) Response payload ``error`` field is ``None``.
    (b) Response payload ``run_id`` field is present (not ``None``).
    (c) ``"AllFallbacksExhaustedError"`` does not appear in the serialised payload.
    """
    # Step 2 — register synthetic spec.
    spec = WorkflowSpec(
        name="fallback_cascade_test",
        input_schema=_FallbackInput,
        output_schema=_FallbackOutput,
        steps=[
            LLMStep(
                tier="primary",
                response_format=_FallbackOutput,
                prompt_template="goal: {goal}",
            )
        ],
        tiers={
            "primary": TierConfig(
                name="primary",
                route=LiteLLMRoute(model="gemini/primary"),
                fallback=[LiteLLMRoute(model="gemini/fallback")],
            )
        },
    )
    register_workflow(spec)

    # Step 3 — install the stub adapter.
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _FallbackStubLiteLLMAdapter)

    # Step 4 — start HTTP server after spec is registered.
    port = _reserve_ephemeral_port()
    _start_server(port=port)
    url = f"http://127.0.0.1:{port}/mcp/"
    _wait_for_http(url)

    # Invoke run_workflow over HTTP transport.
    async with Client(url) as client:
        result = await client.call_tool(
            "run_workflow",
            {
                "payload": {
                    "workflow_id": "fallback_cascade_test",
                    "inputs": {"goal": "test"},
                    "run_id": "run-m15-fallback-cascade",
                }
            },
        )

    payload = result.structured_content or result.data
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()

    payload_str = str(payload)

    # (a) error field is None — successful fallback run.
    assert payload["error"] is None, (
        f"expected error=None (successful fallback), got: {payload['error']!r}"
    )

    # (b) run_id is present.
    assert payload["run_id"] is not None, "run_id must be present in the response"

    # (c) no AllFallbacksExhaustedError in payload.
    assert "AllFallbacksExhaustedError" not in payload_str, (
        f"AllFallbacksExhaustedError appeared in payload: {payload_str!r}"
    )

    # (d) fallback output is present in the response artifact — confirms
    # the cascade returned the fallback result, not just a no-error empty shell.
    assert "fallback-ok" in payload_str, (
        f"expected fallback output 'fallback-ok' in payload, got: {payload_str!r}"
    )
