"""Tests for M8 Task 01 — `probe_ollama` + `HealthResult`.

Covers every classification branch of
:func:`ai_workflows.primitives.llm.ollama_health.probe_ollama` against
stubbed ``httpx.AsyncClient.get`` behaviour. No live network I/O —
live probing is exercised at M8 T05 via the degraded-mode e2e smoke.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from ai_workflows.primitives.llm import HealthResult, probe_ollama


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class _ScriptedGet:
    """Swap in for ``httpx.AsyncClient.get`` to script a single response."""

    def __init__(self, *, outcome: Any) -> None:
        self.outcome = outcome
        self.called_with: str | None = None

    async def __call__(self, url: str, *args: Any, **kwargs: Any) -> _FakeResponse:
        self.called_with = url
        outcome = self.outcome
        if isinstance(outcome, BaseException):
            raise outcome
        if callable(outcome):
            return await outcome()
        return outcome


@pytest.fixture
def patch_get(monkeypatch: pytest.MonkeyPatch):
    def _patch(outcome: Any) -> _ScriptedGet:
        scripted = _ScriptedGet(outcome=outcome)
        monkeypatch.setattr(httpx.AsyncClient, "get", scripted)
        return scripted

    return _patch


async def test_probe_reports_healthy_on_200(patch_get) -> None:
    scripted = patch_get(_FakeResponse(status_code=200))

    result = await probe_ollama(endpoint="http://localhost:11434")

    assert isinstance(result, HealthResult)
    assert result.is_healthy is True
    assert result.reason == "ok"
    assert result.endpoint == "http://localhost:11434"
    assert result.latency_ms is not None and result.latency_ms >= 0.0
    assert scripted.called_with == "http://localhost:11434/api/tags"


async def test_probe_reports_unhealthy_on_connect_error(patch_get) -> None:
    patch_get(httpx.ConnectError("refused"))

    result = await probe_ollama(endpoint="http://localhost:11434")

    assert result.is_healthy is False
    assert result.reason == "connection_refused"
    assert result.latency_ms is None


async def test_probe_reports_unhealthy_on_timeout(patch_get) -> None:
    patch_get(httpx.ReadTimeout("slow"))

    result = await probe_ollama(endpoint="http://localhost:11434")

    assert result.is_healthy is False
    assert result.reason == "timeout"
    assert result.latency_ms is None


async def test_probe_reports_unhealthy_on_non_2xx(patch_get) -> None:
    patch_get(_FakeResponse(status_code=503))

    result = await probe_ollama(endpoint="http://localhost:11434")

    assert result.is_healthy is False
    assert result.reason == "http_503"
    # latency_ms is recorded even on non-2xx — we did get a response.
    assert result.latency_ms is not None


async def test_probe_swallows_arbitrary_exceptions(patch_get) -> None:
    patch_get(RuntimeError("boom"))

    result = await probe_ollama(endpoint="http://localhost:11434")

    assert result.is_healthy is False
    assert result.reason == "error:RuntimeError"
    assert result.latency_ms is None


async def test_probe_respects_timeout_s(patch_get) -> None:
    async def _slow_call() -> _FakeResponse:
        await asyncio.sleep(5.0)
        return _FakeResponse(status_code=200)

    patch_get(_slow_call)

    import time

    started = time.monotonic()
    result = await probe_ollama(endpoint="http://localhost:11434", timeout_s=0.1)
    elapsed = time.monotonic() - started

    assert result.is_healthy is False
    assert result.reason == "timeout"
    assert elapsed < 1.0, f"probe took {elapsed:.2f}s, expected <1s"


async def test_probe_trims_trailing_slash_on_endpoint(patch_get) -> None:
    scripted = patch_get(_FakeResponse(status_code=200))

    await probe_ollama(endpoint="http://localhost:11434/")

    assert scripted.called_with == "http://localhost:11434/api/tags"
