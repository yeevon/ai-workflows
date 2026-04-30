"""Directory-local fixtures for the MCP test suite.

M5 Task 02 flipped the production ``planner_tier_registry()`` so
``planner-synth`` dispatches to ``ClaudeCodeSubprocess`` (OAuth CLI)
instead of LiteLLM/Gemini Flash. Every hermetic test in this directory
stubs ``LiteLLMAdapter`` at the tiered-node boundary; without a matching
override the synth call now spawns the real ``claude`` subprocess.

This conftest installs an autouse registry override that pins the two
planner tiers back to LiteLLM routes for the duration of each test, so
the existing ``_StubLiteLLMAdapter`` fixtures cover both calls. Tests
that specifically need the production heterogeneous registry (e.g. the
M5 tier-override tests once they land) can re-monkeypatch locally —
pytest's ``monkeypatch`` stacks so a later ``setattr`` wins.
"""

from __future__ import annotations

import pytest

from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig
from ai_workflows.workflows import planner as planner_module


def _hermetic_registry() -> dict[str, TierConfig]:
    return {
        "planner-explorer": TierConfig(
            name="planner-explorer",
            route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
            max_concurrency=2,
            per_call_timeout_s=60,
        ),
        "planner-synth": TierConfig(
            name="planner-synth",
            route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
            max_concurrency=2,
            per_call_timeout_s=90,
        ),
    }


@pytest.fixture(autouse=True)
def _stub_planner_tier_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin ``planner_tier_registry`` to a LiteLLM-only pair for MCP tests.

    IMPORTANT: This fixture also implicitly stubs out ``auditor_tier_registry``
    because ``workflows.__init__.auditor_tier_registry`` delegates to
    ``planner.planner_tier_registry``.  Any test in this directory that
    exercises ``run_audit_cascade`` must either (a) additionally monkeypatch
    ``mcp_server_module.auditor_tier_registry`` to a hermetic auditor registry,
    or (b) restore the real ``planner.planner_tier_registry`` on
    ``planner_module``.  Forgetting this raises ``KeyError`` at the
    auditor-tier lookup with no breadcrumb back to this autouse stub.
    See ``test_run_audit_cascade.py::_reset_stub`` (option a) and
    ``test_run_audit_cascade_e2e.py`` (option b) for the established patterns.
    """
    monkeypatch.setattr(
        planner_module, "planner_tier_registry", _hermetic_registry
    )
