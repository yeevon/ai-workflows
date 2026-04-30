"""HTTP round-trip parity test for scaffold_workflow via fastmcp.Client (M17 Task 01).

Verifies that run_workflow(workflow="scaffold_workflow", ...) works over HTTP,
the HumanGate pause is visible in the response, and resume_run(...,
gate_response="approved") writes the file.

Mirrors the pattern in ``tests/mcp/test_http_transport.py`` (M14).
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

import pytest
from fastmcp import Client

from ai_workflows import workflows
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.mcp.__main__ import _run_http
from ai_workflows.mcp.server import build_server
from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.tiers import LiteLLMRoute
from ai_workflows.workflows.scaffold_workflow import build_scaffold_workflow


class _StubLiteLLMAdapter:
    """Scripted LiteLLM-adapter stub for scaffold HTTP tests."""

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
            input_tokens=10,
            output_tokens=20,
            cost_usd=cost,
            model=self.route.model,
        )

    @classmethod
    def reset(cls) -> None:
        cls.script = []
        cls.call_count = 0


@pytest.fixture(autouse=True)
def _reset_stub(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    _StubLiteLLMAdapter.reset()
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _StubLiteLLMAdapter)
    yield
    _StubLiteLLMAdapter.reset()


@pytest.fixture(autouse=True)
def _reensure_scaffold_registered() -> Iterator[None]:
    workflows._reset_for_tests()
    workflows.register("scaffold_workflow", build_scaffold_workflow)
    yield


@pytest.fixture(autouse=True)
def _redirect_default_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("AIW_STORAGE_DB", str(tmp_path / "storage.sqlite"))


def _reserve_ephemeral_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_http(url: str, *, timeout: float = 10.0) -> None:
    import httpx

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
    server = build_server()

    def _run() -> None:
        _run_http(server, host="127.0.0.1", port=port, cors_origins=[])

    thread = threading.Thread(target=_run, daemon=True, name=f"aiw-mcp-scaffold-http:{port}")
    thread.start()
    return thread


def _valid_scaffold_json(target_path: str) -> str:
    source = (
        "from ai_workflows.workflows import WorkflowSpec, LLMStep, register_workflow\n"
        "from pydantic import BaseModel\n\n"
        "class QGenInput(BaseModel):\n"
        "    text: str\n\n"
        "class QGenOutput(BaseModel):\n"
        "    questions: list[str]\n\n"
        "_SPEC = WorkflowSpec(\n"
        "    name='question_gen',\n"
        "    input_schema=QGenInput,\n"
        "    output_schema=QGenOutput,\n"
        "    tiers={},\n"
        "    steps=[],\n"
        ")\n"
        "register_workflow(_SPEC)\n"
    )
    return json.dumps(
        {
            "name": "question_gen",
            "spec_python": source,
            "description": "HTTP parity test workflow.",
            "reasoning": "Test fixture.",
        }
    )


@pytest.mark.asyncio
async def test_scaffold_round_trips_over_http(tmp_path: Path) -> None:
    """AC-5, AC-8, AC-11: scaffold round-trips over HTTP via fastmcp.Client.

    - run_workflow pauses at gate (status=pending, awaiting=gate).
    - gate_context carries spec_python and target_path in the prompt.
    - resume_run with gate_response=approved writes the file.
    """
    target = tmp_path / "http_test_wf.py"
    run_id = "scaffold-http-01"

    _StubLiteLLMAdapter.script = [(_valid_scaffold_json(str(target)), 0.001)]

    port = _reserve_ephemeral_port()
    _start_server(port=port)
    url = f"http://127.0.0.1:{port}/mcp/"
    _wait_for_http(url)

    async with Client(url) as client:
        # 1. Run workflow → should pause at gate.
        run_result = await client.call_tool(
            "run_workflow",
            {
                "payload": {
                    "workflow_id": "scaffold_workflow",
                    "inputs": {
                        "goal": "Generate exam questions.",
                        "target_path": str(target),
                        "force": False,
                    },
                    "run_id": run_id,
                }
            },
        )

        payload = run_result.structured_content or run_result.data
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump()

        assert payload["status"] == "pending", f"unexpected status: {payload}"
        assert payload["awaiting"] == "gate"

        # gate_context must contain the preview.
        gate_ctx = payload.get("gate_context")
        assert gate_ctx is not None, "gate_context should be present at gate pause"
        gate_prompt = gate_ctx.get("gate_prompt") or gate_ctx.get("prompt") or ""
        # The gate prompt JSON includes spec_python and target_path.
        assert "spec_python" in gate_prompt or "register_workflow" in gate_prompt, (
            f"gate prompt should include spec_python; got: {gate_prompt[:200]!r}"
        )

        # 2. Resume with approval.
        resume_result = await client.call_tool(
            "resume_run",
            {
                "payload": {
                    "run_id": run_id,
                    "gate_response": "approved",
                }
            },
        )

    resume_payload = resume_result.structured_content or resume_result.data
    if hasattr(resume_payload, "model_dump"):
        resume_payload = resume_payload.model_dump()

    assert resume_payload["status"] == "completed", (
        f"unexpected resume status: {resume_payload}"
    )

    # File should be written.
    assert target.exists(), "file should be written after HTTP gate approval"
