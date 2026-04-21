"""M5 Task 06 — tier-override end-to-end smoke (``AIW_E2E=1`` gated).

Drives the MCP ``run_workflow`` tool in-process (mirrors the hermetic
:mod:`tests/mcp/test_server_smoke.py`) with a ``tier_overrides`` payload
and verifies the override actually reroutes ``planner-synth`` away from
Claude Code Opus at the dispatch boundary. The run uses **real** Gemini
Flash via LiteLLM so the test qualifies as e2e (a provider call
executes end-to-end); ``ClaudeCodeSubprocess`` is monkeypatched to a
raise-on-call stub so an override regression (synth still routing
through the Claude Code CLI) fails loudly instead of silently passing.

Gated by ``@pytest.mark.e2e`` + ``AIW_E2E=1`` (see
:mod:`tests/e2e/conftest.py`). Prerequisite is a single env var —
``GEMINI_API_KEY``. No ``ollama`` binary or ``claude`` CLI is required
because the override removes both dependencies from the resolved
registry: ``planner-explorer`` is test-pinned to Gemini Flash,
``planner-synth`` is overridden onto the same config.

Relationship to siblings
------------------------
* :mod:`tests/e2e/test_planner_smoke.py` — the sibling multi-tier
  smoke that covers the real Qwen + Claude Code path; this module
  covers the override plumbing across the MCP surface instead.
* :mod:`tests/mcp/test_tier_override.py` — the hermetic T05 suite
  that asserts ``models_seen`` at the adapter boundary. This module
  is the live-provider counterpart.
* :mod:`tests/mcp/test_server_smoke.py` — the hermetic always-run
  MCP smoke; shares the in-process ``build_server()`` + ``get_tool``
  pattern but fires real LiteLLM calls instead of stubbing the
  adapter.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.mcp import build_server
from ai_workflows.mcp.schemas import ResumeRunInput, RunWorkflowInput
from ai_workflows.primitives.tiers import (
    ClaudeCodeRoute,
    LiteLLMRoute,
    TierConfig,
)
from ai_workflows.workflows import planner as planner_module

_GEMINI_FLASH = "gemini/gemini-2.5-flash"


def _pinned_tier_registry() -> dict[str, TierConfig]:
    """Return a three-tier registry scoped to this e2e.

    ``planner-explorer`` is pinned to Gemini Flash so the explorer call
    fires against real LiteLLM without needing Ollama locally.
    ``planner-synth`` is intentionally left pointing at Claude Code
    Opus so the override ``{"planner-synth": "planner-explorer"}`` has
    observable semantic effect: without it the synth call would fire
    against the monkeypatched (raise-on-call) Claude Code stub and the
    test would fail loudly. With the override the synth call collapses
    onto the Gemini Flash tier.
    """
    return {
        "planner-explorer": TierConfig(
            name="planner-explorer",
            route=LiteLLMRoute(model=_GEMINI_FLASH),
            max_concurrency=2,
            per_call_timeout_s=60,
        ),
        "planner-synth": TierConfig(
            name="planner-synth",
            route=ClaudeCodeRoute(cli_model_flag="opus"),
            max_concurrency=1,
            per_call_timeout_s=300,
        ),
    }


class _RaiseIfInstantiated:
    """Stub that fails the test if ``ClaudeCodeSubprocess`` is constructed.

    The override under test is supposed to remove ``planner-synth``'s
    dependency on Claude Code — that invariant holds only if the
    subprocess driver is never instantiated during the run. Raising at
    ``__init__`` is the loudest possible failure mode and cannot be
    silenced by a downstream ``try/except`` in the tiered-node adapter
    wiring.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise AssertionError(
            "ClaudeCodeSubprocess was instantiated despite "
            "tier_overrides={'planner-synth': 'planner-explorer'}; "
            "override regressed — synth still routed to Claude Code."
        )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mcp_tier_override_routes_synth_to_gemini_flash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Drive ``run_workflow`` → ``resume_run`` with a Claude-Code-removing override.

    AC: the run completes to the gate, ``resume_run`` approves to
    ``completed``, and ``ClaudeCodeSubprocess`` was never instantiated
    (the raise-on-call stub would have broken the run otherwise). The
    ``total_cost_usd`` assertion is ``>= 0`` because Gemini Flash on
    the free tier reports ``cost_usd=0.0`` while still contributing a
    real network round-trip; a strict ``> 0`` check would be flaky.
    """
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set; cannot exercise Gemini path")

    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("AIW_STORAGE_DB", str(tmp_path / "storage.sqlite"))

    monkeypatch.setattr(
        planner_module, "planner_tier_registry", _pinned_tier_registry
    )
    monkeypatch.setattr(
        tiered_node_module, "ClaudeCodeSubprocess", _RaiseIfInstantiated
    )

    run_id = f"e2e-override-{os.urandom(4).hex()}"

    server = build_server()
    run_tool = await server.get_tool("run_workflow")
    resume_tool = await server.get_tool("resume_run")

    run_result = await run_tool.fn(
        RunWorkflowInput(
            workflow_id="planner",
            inputs={
                "goal": "Write a three-bullet release checklist.",
                "context": None,
                "max_steps": 3,
            },
            run_id=run_id,
            tier_overrides={"planner-synth": "planner-explorer"},
        )
    )
    assert run_result.status == "pending", run_result
    assert run_result.awaiting == "gate", run_result
    assert run_result.run_id == run_id
    assert run_result.total_cost_usd is not None
    assert run_result.total_cost_usd >= 0.0

    resume_result = await resume_tool.fn(
        ResumeRunInput(run_id=run_id, gate_response="approved")
    )
    assert resume_result.status == "completed", resume_result
    assert resume_result.plan is not None
    assert resume_result.plan["goal"]
    assert resume_result.error is None
    assert resume_result.total_cost_usd is not None
    assert resume_result.total_cost_usd >= 0.0
