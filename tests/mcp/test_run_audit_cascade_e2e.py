"""Wire-level E2E smoke for the ``run_audit_cascade`` MCP tool (M12 Task 05).

Gated by ``AIW_E2E=1``.  Fires the tool against a real ``auditor-sonnet``
Claude CLI subprocess.  Exercises the code path a downstream MCP consumer
hits (``build_server()`` → ``run_audit_cascade`` tool → ``tiered_node`` →
``ClaudeCodeSubprocess`` → real ``claude --model sonnet`` invocation).

Per CLAUDE.md *Code-task verification is non-inferential*: this test is the
wire-level smoke the Builder runs once at implement-close and reports on.
Skipped by default (``AIW_E2E`` unset) so the CI hermetic suite stays fast.

Relationship to other modules
-----------------------------
* ``ai_workflows.mcp.server`` — the module under test.
* ``ai_workflows.graph.audit_cascade`` — provides ``AuditVerdict``; the E2E
  test asserts the returned ``verdicts_by_tier`` values are real
  ``AuditVerdict`` instances.
* ``ai_workflows.primitives.llm.claude_code`` — the real subprocess driver
  fired when ``AIW_E2E=1``; requires an authenticated ``claude`` CLI in PATH
  (``claude auth status`` must be non-erroring).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ai_workflows.graph.audit_cascade import AuditVerdict
from ai_workflows.mcp import build_server
from ai_workflows.mcp.schemas import RunAuditCascadeInput
from ai_workflows.workflows import planner as planner_module
from ai_workflows.workflows.planner import planner_tier_registry as _real_planner_tier_registry


@pytest.mark.skipif(
    not os.getenv("AIW_E2E"),
    reason="E2E test — set AIW_E2E=1 to run against real Claude CLI",
)
@pytest.mark.asyncio
async def test_inline_artefact_audited_by_real_sonnet_e2e(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fire ``run_audit_cascade`` with real ``auditor-sonnet`` Claude subprocess.

    Asserts:
    * ``output.passed in (True, False)`` — any well-formed verdict is acceptable
    * ``output.verdicts_by_tier`` contains ``"auditor-sonnet"`` key
    * the tier-value is a real :class:`~ai_workflows.graph.audit_cascade.AuditVerdict`
    * ``output.total_cost_usd >= 0.0``
    * ``output.by_role`` is not None and contains ``"auditor"`` key
    * no exception raised
    """
    db_path = tmp_path / "storage.sqlite3"
    checkpoint_path = tmp_path / "checkpoint.sqlite3"
    monkeypatch.setenv("AIW_STORAGE_DB", str(db_path))
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(checkpoint_path))
    # The MCP conftest stubs planner_tier_registry to a hermetic-only set
    # (no auditor tiers).  Restore the real function so auditor_tier_registry()
    # can resolve the auditor-sonnet/opus entries from the live planner registry.
    monkeypatch.setattr(planner_module, "planner_tier_registry", _real_planner_tier_registry)

    server = build_server()
    tool = await server.get_tool("run_audit_cascade")
    payload = RunAuditCascadeInput(
        inline_artefact_ref={"sample": "tiny artefact"},
        tier_ceiling="sonnet",  # cheaper than opus for the smoke
    )

    output = await tool.fn(payload)

    assert output.passed in (True, False), (
        f"expected boolean passed, got {output.passed!r}"
    )
    assert "auditor-sonnet" in output.verdicts_by_tier, (
        f"expected 'auditor-sonnet' in verdicts_by_tier; got {list(output.verdicts_by_tier)}"
    )
    tier_verdict = output.verdicts_by_tier["auditor-sonnet"]
    assert isinstance(tier_verdict, AuditVerdict), (
        f"expected AuditVerdict instance, got {type(tier_verdict)}"
    )
    assert output.total_cost_usd >= 0.0, (
        f"expected non-negative cost, got {output.total_cost_usd}"
    )
    assert output.by_role is not None, "expected by_role to be populated"
    assert "auditor" in output.by_role, (
        f"expected 'auditor' key in by_role; got {list(output.by_role)}"
    )
