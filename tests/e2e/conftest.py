"""Pytest collection gate for the ``tests/e2e/`` suite.

End-to-end tests hit a real provider API (Gemini Flash via LiteLLM in
M3 Task 07) and are gated behind the ``AIW_E2E=1`` environment
variable so that ``uv run pytest`` on a developer laptop stays
hermetic and does not accidentally burn real quota.

The collection hook below adds a ``pytest.skip`` marker to every test
tagged ``@pytest.mark.e2e`` *unless* ``AIW_E2E=1`` is set in the
environment. Skipped tests still appear in the pytest output (counted
as skipped, not dropped), which satisfies M3 T07 AC-1 —
"collected-and-skipped, not silently dropped, not an error."

Mirrors the pattern M3 T07 spec §"Conftest gate" prescribes verbatim.
"""

from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(
    config: pytest.Config,  # noqa: ARG001 — pytest hook signature
    items: list[pytest.Item],
) -> None:
    """Skip every ``e2e``-tagged test unless ``AIW_E2E=1``."""
    if os.environ.get("AIW_E2E") == "1":
        return
    skip = pytest.mark.skip(reason="Set AIW_E2E=1 to run e2e tests")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip)
