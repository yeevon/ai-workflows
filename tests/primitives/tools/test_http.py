"""Tests for :mod:`ai_workflows.primitives.tools.http` (Task 06).

Covers the error-path-returns-string AC and the truncation / format
contract. Uses :class:`httpx.MockTransport` so no live network traffic is
generated — CI and the local developer both exercise the real
``httpx.request`` code path without hitting DNS.
"""

from __future__ import annotations

from unittest.mock import patch

import httpx

from ai_workflows.primitives.tools import http


def _install_mock_transport(handler) -> None:
    """Patch :func:`httpx.request` to route through a :class:`MockTransport`."""
    transport = httpx.MockTransport(handler)

    def fake_request(method, url, **kwargs):  # type: ignore[no-untyped-def]
        with httpx.Client(transport=transport) as client:
            return client.request(method, url, **kwargs)

    return patch.object(http.httpx, "request", side_effect=fake_request)


def test_http_fetch_returns_http_code_and_body(tmp_path, ctx_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="hello world")

    ctx = ctx_factory(project_root=str(tmp_path))
    with _install_mock_transport(handler):
        out = http.http_fetch(ctx, "https://example.com")

    assert out.startswith("HTTP 200\n")
    assert "hello world" in out


def test_http_fetch_truncates_large_body(tmp_path, ctx_factory) -> None:
    big = "A" * 100_000

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=big)

    ctx = ctx_factory(project_root=str(tmp_path))
    with _install_mock_transport(handler):
        out = http.http_fetch(ctx, "https://example.com", max_chars=100)

    assert out.startswith("HTTP 200\n")
    assert "[truncated]" in out
    # Body line is at most max_chars + truncation marker; count only payload.
    body = out.split("\n", 1)[1]
    assert body.count("A") == 100


def test_http_fetch_supports_non_get_method(tmp_path, ctx_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        return httpx.Response(201, text="")

    ctx = ctx_factory(project_root=str(tmp_path))
    with _install_mock_transport(handler):
        out = http.http_fetch(ctx, "https://example.com", method="POST")

    assert out.startswith("HTTP 201\n")


def test_http_fetch_timeout_returns_string_error(tmp_path, ctx_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow")

    ctx = ctx_factory(project_root=str(tmp_path))
    with _install_mock_transport(handler):
        out = http.http_fetch(ctx, "https://example.com")

    assert isinstance(out, str)
    assert out.startswith("Error: HTTP timeout")


def test_http_fetch_network_error_returns_string(tmp_path, ctx_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    ctx = ctx_factory(project_root=str(tmp_path))
    with _install_mock_transport(handler):
        out = http.http_fetch(ctx, "https://example.com")

    assert isinstance(out, str)
    assert out.startswith("Error: HTTP error")
    assert "ConnectError" in out


def test_http_fetch_invalid_url_returns_string(tmp_path, ctx_factory) -> None:
    ctx = ctx_factory(project_root=str(tmp_path))
    # No mock — use a malformed URL to exercise the ValueError/HTTPError path.
    out = http.http_fetch(ctx, "not-a-valid-url")

    assert isinstance(out, str)
    assert out.startswith("Error")
