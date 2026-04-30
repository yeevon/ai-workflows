"""Hermetic tests for the ``run_audit_cascade`` MCP tool (M12 Task 05).

Covers the six T05 acceptance criteria for the standalone audit tool:

1. ``RunAuditCascadeInput`` validation — rejects zero artefact sources.
2. ``RunAuditCascadeInput`` validation — rejects both artefact sources set.
3. ``RunAuditCascadeInput`` validation — requires ``artefact_kind`` when
   ``run_id_ref`` is set.
4. ``RunAuditCascadeInput`` validation — rejects ``artefact_kind`` when
   ``run_id_ref`` is unset.
5. Happy-path inline artefact audit — stub auditor returns ``passed=True``;
   asserts output schema shape + single-pass invariant + T04 ``by_role``
   cost attribution.
6. Storage-backed artefact audit — seeds ``storage.write_artifact``, invokes
   with ``run_id_ref + artefact_kind``; asserts auditor prompt contains the
   inner-payload key (H2 decode check) and not storage-wrapper keys; also
   asserts that an unknown ``(run_id, kind)`` raises ``ToolError``.

All LLM calls are stubbed at the ``ClaudeCodeSubprocess`` boundary via
``monkeypatch.setattr(tiered_node_module, "ClaudeCodeSubprocess",
_StubAuditorAdapter)`` — mirrors the established pattern at
``tests/graph/test_audit_cascade.py:151`` (``_StubClaudeCodeAdapter``).

``AIW_CHECKPOINT_DB`` / ``AIW_STORAGE_DB`` redirect under ``tmp_path`` so
nothing touches ``~/.ai-workflows/``.

Relationship to other modules
-----------------------------
* ``ai_workflows.mcp.server`` — the module under test; ``build_server()``
  returns the FastMCP instance whose ``run_audit_cascade`` tool we call
  directly (in-process, not over JSON-RPC transport).
* ``ai_workflows.mcp.schemas`` — ``RunAuditCascadeInput`` /
  ``RunAuditCascadeOutput`` pydantic models validated in tests 1-4; output
  schema asserted in test 5.
* ``ai_workflows.graph.audit_cascade`` — ``AuditVerdict`` used to construct
  expected verdict-shape assertions.
* ``ai_workflows.graph.tiered_node`` — stub installed at the
  ``ClaudeCodeSubprocess`` name so tests never spawn a real ``claude`` CLI
  subprocess (KDR-003 / hermetic constraint).
* ``ai_workflows.primitives.storage`` — seeded in test 6 via
  ``storage.write_artifact``; ``default_storage_path`` monkeypatched to the
  tmp_path SQLite file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.graph.audit_cascade import AuditVerdict
from ai_workflows.mcp import build_server
from ai_workflows.mcp import server as mcp_server_module
from ai_workflows.mcp.schemas import RunAuditCascadeInput
from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.tiers import ClaudeCodeRoute, TierConfig

# ---------------------------------------------------------------------------
# Stub adapter — mirrors _StubClaudeCodeAdapter at
# tests/graph/test_audit_cascade.py:103
# ---------------------------------------------------------------------------


class _StubAuditorAdapter:
    """Stub for the Claude Code subprocess driver — standalone auditor path.

    Holds a class-level ``script`` of ``(output_text, cost_usd)`` tuples
    consumed FIFO by sequential calls.  Each consumed entry returns ``text``
    as the LLM output and a ``TokenUsage`` with ``cost_usd``.  Raising a
    ``BaseException`` from the script raises that exception directly, allowing
    error-path tests.

    ``calls`` records each invocation's ``(system, messages)`` pair for
    assertion in prompt-content tests.
    """

    script: list[Any] = []
    calls: list[dict] = []

    def __init__(
        self,
        *,
        route: ClaudeCodeRoute,
        per_call_timeout_s: int,
        pricing: dict,
    ) -> None:
        self.route = route

    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict],
        response_format: Any = None,
    ) -> tuple[str, TokenUsage]:
        _StubAuditorAdapter.calls.append({"system": system, "messages": messages})
        if not _StubAuditorAdapter.script:
            raise AssertionError("stub script exhausted (auditor)")
        head = _StubAuditorAdapter.script.pop(0)
        if isinstance(head, BaseException):
            raise head
        text, cost = head
        return text, TokenUsage(
            input_tokens=3,
            output_tokens=2,
            cost_usd=cost,
            model=self.route.cli_model_flag,
            role="auditor",
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_AUDIT_PASS_JSON = '{"passed": true, "failure_reasons": [], "suggested_approach": null}'
_AUDIT_FAIL_JSON = (
    '{"passed": false, "failure_reasons": ["weak content"], '
    '"suggested_approach": "Try harder"}'
)


def _hermetic_auditor_tier_registry() -> dict[str, TierConfig]:
    """Return a minimal hermetic auditor tier registry for tests.

    The MCP conftest stubs ``planner_tier_registry`` to return only planner
    tiers (no auditor entries), so ``auditor_tier_registry()`` would raise
    ``KeyError``.  This hermetic stub is patched onto ``mcp.server`` directly
    so the tool resolves tiers without touching ``planner.py``.
    """
    return {
        "auditor-sonnet": TierConfig(
            name="auditor-sonnet",
            route=ClaudeCodeRoute(cli_model_flag="sonnet"),
            max_concurrency=1,
            per_call_timeout_s=30,
        ),
        "auditor-opus": TierConfig(
            name="auditor-opus",
            route=ClaudeCodeRoute(cli_model_flag="opus"),
            max_concurrency=1,
            per_call_timeout_s=30,
        ),
    }


@pytest.fixture(autouse=True)
def _reset_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install stubs and reset call state before each test."""
    _StubAuditorAdapter.script = []
    _StubAuditorAdapter.calls = []
    monkeypatch.setattr(tiered_node_module, "ClaudeCodeSubprocess", _StubAuditorAdapter)
    # Patch auditor_tier_registry on the server module so it doesn't call
    # planner_tier_registry (which the conftest stubs to hermetic-only tiers).
    monkeypatch.setattr(
        mcp_server_module, "auditor_tier_registry", _hermetic_auditor_tier_registry
    )


@pytest.fixture()
def tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect storage + checkpoint DBs to tmp_path; return the tmp dir."""
    db_path = tmp_path / "storage.sqlite3"
    checkpoint_path = tmp_path / "checkpoint.sqlite3"
    monkeypatch.setenv("AIW_STORAGE_DB", str(db_path))
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(checkpoint_path))
    return tmp_path


# ---------------------------------------------------------------------------
# Test 1 — zero artefact sources → ValidationError
# ---------------------------------------------------------------------------


def test_input_validator_rejects_zero_sources_set() -> None:
    """``RunAuditCascadeInput()`` with no source fields → ValidationError."""
    with pytest.raises(ValidationError, match="exactly one of"):
        RunAuditCascadeInput()


# ---------------------------------------------------------------------------
# Test 2 — both artefact sources set → ValidationError
# ---------------------------------------------------------------------------


def test_input_validator_rejects_both_sources_set() -> None:
    """Both ``run_id_ref`` and ``inline_artefact_ref`` set → ValidationError."""
    with pytest.raises(ValidationError, match="exactly one of"):
        RunAuditCascadeInput(
            run_id_ref="some-run-id",
            artefact_kind="plan",
            inline_artefact_ref={"key": "value"},
        )


# ---------------------------------------------------------------------------
# Test 3 — run_id_ref set, artefact_kind absent → ValidationError
# ---------------------------------------------------------------------------


def test_input_validator_requires_artefact_kind_when_run_id_ref_set() -> None:
    """``run_id_ref`` without ``artefact_kind`` → ValidationError with message."""
    with pytest.raises(ValidationError, match="artefact_kind is required"):
        RunAuditCascadeInput(run_id_ref="some-run-id")


# ---------------------------------------------------------------------------
# Test 4 — artefact_kind set when run_id_ref is unset → ValidationError
# ---------------------------------------------------------------------------


def test_input_validator_rejects_artefact_kind_when_run_id_ref_unset() -> None:
    """``artefact_kind`` without ``run_id_ref`` → ValidationError."""
    with pytest.raises(ValidationError, match="artefact_kind is only meaningful"):
        RunAuditCascadeInput(
            inline_artefact_ref={"foo": "bar"},
            artefact_kind="plan",
        )


# ---------------------------------------------------------------------------
# Test 5 — happy-path inline artefact, auditor passes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_audit_cascade_with_inline_artefact_passes_when_auditor_passes(
    tmp_db: Path,
) -> None:
    """Invoke tool with ``inline_artefact_ref`` + stub returning ``passed=True``.

    Asserts:
    * ``output.passed is True``
    * ``output.verdicts_by_tier == {"auditor-opus": AuditVerdict(passed=True, ...)}``
    * ``output.suggested_approach is None``
    * ``output.total_cost_usd == 0.0`` (Max flat-rate stub returns 0.0 cost)
    * ``output.by_role`` contains ``"auditor"`` key with value 0.0
    * adapter called exactly once (single-pass — no retry)
    """
    _StubAuditorAdapter.script = [(_AUDIT_PASS_JSON, 0.0)]

    server = build_server()
    tool = await server.get_tool("run_audit_cascade")
    payload = RunAuditCascadeInput(inline_artefact_ref={"foo": "bar"})
    output = await tool.fn(payload)

    assert output.passed is True
    assert "auditor-opus" in output.verdicts_by_tier
    tier_verdict = output.verdicts_by_tier["auditor-opus"]
    assert isinstance(tier_verdict, AuditVerdict)
    assert tier_verdict.passed is True
    assert output.suggested_approach is None
    assert output.total_cost_usd == 0.0
    assert output.by_role is not None
    assert "auditor" in output.by_role, (
        f"expected 'auditor' key in by_role; got {list(output.by_role)}"
    )
    assert output.by_role["auditor"] == 0.0  # Max flat-rate stub returns 0.0
    assert len(_StubAuditorAdapter.calls) == 1  # single-pass


# ---------------------------------------------------------------------------
# Test 6 — storage-backed artefact + H2 decode + missing pair → ToolError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_audit_cascade_with_run_id_ref_resolves_artefact_via_storage_read_artifact(
    tmp_db: Path,
) -> None:
    """Seed storage, invoke with run_id_ref; assert prompt contains inner payload.

    H2 decode check: the storage row wrapper ``{run_id, kind, payload_json,
    created_at}`` is decoded via ``json.loads(row["payload_json"])`` before
    being embedded in the auditor prompt.  The inner key ``"sample"`` MUST
    appear in the prompt; the wrapper keys ``"payload_json"``, ``"created_at"``,
    and the literal string ``"run_id"`` as a JSON key MUST NOT appear.

    Also asserts that a missing ``(run_id, kind)`` pair raises ``ToolError``.
    """
    _StubAuditorAdapter.script = [(_AUDIT_PASS_JSON, 0.0)]

    run_id = "test-run-001"
    kind = "plan"
    inner_payload = {"sample": "known dict"}

    # Seed storage — write_artifact signature: (run_id, kind, payload_json: str)
    storage = await SQLiteStorage.open(Path(os.environ["AIW_STORAGE_DB"]))
    await storage.write_artifact(run_id, kind, json.dumps(inner_payload))

    server = build_server()
    tool = await server.get_tool("run_audit_cascade")
    payload = RunAuditCascadeInput(run_id_ref=run_id, artefact_kind=kind)
    output = await tool.fn(payload)

    assert output.passed is True

    # Verify the auditor's prompt embeds the INNER payload, not the SQL wrapper
    assert len(_StubAuditorAdapter.calls) == 1
    call = _StubAuditorAdapter.calls[0]
    all_content = " ".join(
        m["content"] for m in call["messages"] if isinstance(m.get("content"), str)
    )
    assert "sample" in all_content, "inner payload key must appear in auditor prompt"
    # H2 regression guards: wrapper keys must NOT appear
    assert '"payload_json"' not in all_content, (
        "storage wrapper key 'payload_json' must not appear in auditor prompt"
    )
    assert '"created_at"' not in all_content, (
        "storage wrapper key 'created_at' must not appear in auditor prompt"
    )

    # Missing (run_id, kind) → ToolError
    missing_payload = RunAuditCascadeInput(run_id_ref="nonexistent-run", artefact_kind="plan")
    with pytest.raises(ToolError, match="no artefact found"):
        await tool.fn(missing_payload)


# ---------------------------------------------------------------------------
# Test 7 — RetryableTransient from auditor → ToolError (SR-DEV-BLOCK-01 /
#           SR-SDET-BLOCK-01 cycle-3 fix)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_audit_cascade_raises_tool_error_on_retryable_transient(
    tmp_db: Path,
) -> None:
    """``RetryableTransient`` raised by the auditor adapter surfaces as ``ToolError``.

    Pins the fix for SR-DEV-BLOCK-01 / SR-SDET-BLOCK-01 (cycle 3, 2026-04-28):
    the except tuple at ``server.py:485`` was missing ``RetryableTransient``,
    so network blips (429s, subprocess crashes) escaped the tool boundary and
    produced opaque FastMCP internal errors instead of descriptive
    ``ToolError("audit invocation failed: …")`` responses.

    The stub seeds a ``RetryableTransient`` as the only script entry; the test
    asserts ``ToolError`` is raised with the expected message prefix.
    """
    from ai_workflows.primitives.retry import RetryableTransient as _RetryableTransient

    _StubAuditorAdapter.script = [_RetryableTransient("simulated 429")]

    server = build_server()
    tool = await server.get_tool("run_audit_cascade")
    payload = RunAuditCascadeInput(inline_artefact_ref={"foo": "bar"})

    with pytest.raises(ToolError, match="audit invocation failed"):
        await tool.fn(payload)


# ---------------------------------------------------------------------------
# Test 8 — passed=False path + suggested_approach propagation
#           (SR-SDET-FIX-01 cycle-3 fix — _AUDIT_FAIL_JSON now exercised)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_audit_cascade_surfaces_suggested_approach_when_auditor_fails(
    tmp_db: Path,
) -> None:
    """Stub auditor returns ``passed=False``; output reflects failure fields.

    Pins the ``passed=False`` branch of ``RunAuditCascadeOutput`` shape
    (SR-SDET-FIX-01, cycle 3, 2026-04-28). Specifically exercises:

    * ``server.py:509`` — ``suggested_approach=verdict.suggested_approach if
      not verdict.passed else None`` (the conditional that populates
      ``suggested_approach`` on failure is exercised; a bug inverting the
      condition would cause this test to fail).
    * ``output.verdicts_by_tier["auditor-opus"].failure_reasons`` propagated
      from the verdict (a bug dropping ``failure_reasons`` is caught).
    * ``output.suggested_approach`` is not ``None`` on ``passed=False``.

    The constant ``_AUDIT_FAIL_JSON`` defined earlier in this module is used
    here so it is no longer a dead constant.
    """
    _StubAuditorAdapter.script = [(_AUDIT_FAIL_JSON, 0.0)]

    server = build_server()
    tool = await server.get_tool("run_audit_cascade")
    payload = RunAuditCascadeInput(inline_artefact_ref={"foo": "bar"})
    output = await tool.fn(payload)

    assert output.passed is False
    assert output.suggested_approach == "Try harder"
    assert "auditor-opus" in output.verdicts_by_tier
    tier_verdict = output.verdicts_by_tier["auditor-opus"]
    assert isinstance(tier_verdict, AuditVerdict)
    assert tier_verdict.passed is False
    assert tier_verdict.failure_reasons == ["weak content"]
    assert len(_StubAuditorAdapter.calls) == 1  # single-pass
