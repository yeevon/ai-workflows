"""Wire-level e2e integration tests for the M19 spec API (M19 Task 04).

Deliverable 5 of
``design_docs/phases/milestone_19_declarative_surface/task_04_summarize_proof_point.md``.
Five wire-level tests:

1. ``test_aiw_run_summarize_via_input_kvs`` — CLI via ``--input KEY=VALUE``
   (``CliRunner``); pydantic coerces ``"50"`` → ``int 50``.
2. ``test_aiw_show_inputs_summarize_lists_input_fields`` — ``aiw show-inputs summarize``
   lists both ``text`` and ``max_words`` fields (locked H1, refinement #4).
3. ``test_aiw_run_planner_flag_input_conflict_raises`` — ``aiw run planner
   --goal "x" --input goal="y"`` exits 2 with ``conflicting input 'goal'``.
4. ``test_aiw_mcp_run_workflow_summarize_via_fastmcp_client`` — in-process
   MCP tool call (``build_server().get_tool("run_workflow").fn(payload)``);
   asserts ``result.artifact == {"summary": "..."}`` (M19 T03 canonical field).
5. ``test_summarize_artefact_identical_across_surfaces`` — both surfaces
   (CLI + MCP) against the same stub; artefacts are byte-identical.

All tests use ``StubLLMAdapter``-style stubs so no real Gemini call fires.
The live-Gemini smoke runs at T08's release ceremony.

Cross-references
----------------
* :mod:`ai_workflows.workflows.summarize` — the workflow under test (M19 T04).
* :mod:`ai_workflows.cli` — ``aiw run`` / ``aiw show-inputs`` (M19 T04 extension).
* :mod:`ai_workflows.mcp.server` — ``build_server()`` entry point (KDR-002).
* :mod:`ai_workflows.workflows._dispatch` — shared dispatch helper.
* M18 inventory DOC-DG4 resolved by test 4 exercising the ``payload`` wire shape live.

KDRs exercised
--------------
* KDR-002 — MCP as substrate; CLI is the second public surface.
* KDR-004 — ValidatorNode paired by construction.
* KDR-008 — FastMCP pydantic schema contract exercised by tool call.
* KDR-009 — SqliteSaver checkpoints (redirected to tmp_path).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

import ai_workflows.workflows as workflows
from ai_workflows.cli import app
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.mcp import build_server
from ai_workflows.mcp.schemas import RunWorkflowInput
from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.tiers import LiteLLMRoute

_RUNNER = CliRunner()


# ---------------------------------------------------------------------------
# Shared stub LLM adapter
# ---------------------------------------------------------------------------


class _StubLiteLLMAdapter:
    """Scripted LiteLLM-adapter stub — shared across CLI and MCP surfaces."""

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
        """Return the next scripted response or raise if exhausted."""
        _StubLiteLLMAdapter.call_count += 1
        if not _StubLiteLLMAdapter.script:
            raise AssertionError("stub script exhausted")
        head = _StubLiteLLMAdapter.script.pop(0)
        if isinstance(head, BaseException):
            raise head
        text, cost = head
        return text, TokenUsage(
            input_tokens=1,
            output_tokens=1,
            cost_usd=cost,
            model=self.route.model,
        )

    @classmethod
    def reset(cls) -> None:
        """Clear state between tests."""
        cls.script = []
        cls.call_count = 0


def _valid_summary_json() -> str:
    """Return a valid SummarizeOutput JSON for stub use."""
    return json.dumps({"summary": "A brief summary of the text."})


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install the stub adapter and clear the script between tests."""
    _StubLiteLLMAdapter.reset()
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _StubLiteLLMAdapter)


@pytest.fixture(autouse=True)
def _reset_and_register_summarize() -> Iterator[None]:
    """Reset registry and ensure 'summarize' is registered for each test.

    Uses compile_spec(_SPEC) to re-inject the synthetic module into
    sys.modules after each reset (same strategy as test_summarize.py
    _reset_and_register fixture — plain import after reset leaves the
    synthetic module absent, causing KeyError in AsyncSqliteSaver runs).

    Also ensures 'planner' stays registered for conflict-raises test.
    """
    # Ensure summarize module has been imported at least once (side-effect).
    import ai_workflows.workflows.summarize  # noqa: F401

    workflows._reset_for_tests()

    # Re-compile to re-inject the synthetic module.
    from ai_workflows.workflows._compiler import compile_spec
    from ai_workflows.workflows.summarize import _SPEC
    summarize_builder = compile_spec(_SPEC)
    workflows.register("summarize", summarize_builder)

    from ai_workflows.workflows.planner import build_planner
    workflows.register("planner", build_planner)
    yield
    workflows._reset_for_tests()


@pytest.fixture(autouse=True)
def _redirect_db_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect SQLite paths to tmp_path so tests are hermetic."""
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("AIW_STORAGE_DB", str(tmp_path / "storage.sqlite"))


# ---------------------------------------------------------------------------
# Test 1 — CLI via --input KEY=VALUE (locked H1)
# ---------------------------------------------------------------------------


def test_aiw_run_summarize_via_input_kvs() -> None:
    """aiw run summarize --input text=... --input max_words=50 dispatches end-to-end.

    Pydantic coerces the string ``"50"`` to ``int 50`` for
    ``SummarizeInput.max_words`` automatically (refinement #2).
    Exit code 0; stdout contains the run-id and the summary artefact.
    """
    _StubLiteLLMAdapter.script = [(_valid_summary_json(), 0.0)]

    result = _RUNNER.invoke(
        app,
        [
            "run",
            "summarize",
            "--input",
            "text=The quick brown fox jumped over the lazy dog.",
            "--input",
            "max_words=50",
            "--run-id",
            "smry-1",
        ],
    )
    assert result.exit_code == 0, (
        f"Expected exit 0, got {result.exit_code}; output:\n{result.output}"
    )
    assert "smry-1" in result.output or "summary" in result.output.lower(), (
        f"Expected run-id or summary in output; got:\n{result.output}"
    )
    # Artefact JSON should appear in stdout (summarize completes without a gate)
    assert "summary" in result.output.lower(), (
        f"Expected 'summary' key in output; got:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# Test 2 — Help text lists input fields (refinement #4)
# ---------------------------------------------------------------------------


def test_aiw_show_inputs_summarize_lists_input_fields() -> None:
    """aiw show-inputs summarize lists both 'text' and 'max_words' fields.

    Pins locked H1 refinement #4: the CLI surfaces input field discovery
    so users know which --input keys a workflow accepts. The Builder
    chose ``aiw show-inputs <workflow>`` over a custom ``--help`` callback
    per spec line 217 Builder discretion; this test exercises that UX.
    """
    result = _RUNNER.invoke(app, ["show-inputs", "summarize"])
    assert result.exit_code == 0, (
        f"Expected exit 0, got {result.exit_code}; output:\n{result.output}"
    )
    assert "text" in result.output, (
        f"Expected 'text' field name in output; got:\n{result.output}"
    )
    assert "max_words" in result.output, (
        f"Expected 'max_words' field name in output; got:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# Test 3 — Planner flag / --input conflict raises (refinement #1)
# ---------------------------------------------------------------------------


def test_aiw_run_planner_flag_input_conflict_raises() -> None:
    """aiw run planner --goal "x" --input goal="y" exits 2 with conflict message.

    Pins locked H1 refinement #1: explicit conflict between a planner-shape
    flag and an --input entry naming the same key raises BadParameter.
    """
    result = _RUNNER.invoke(
        app,
        ["run", "planner", "--goal", "x", "--input", "goal=y"],
    )
    assert result.exit_code == 2, (
        f"Expected exit 2 (BadParameter), got {result.exit_code}; output:\n{result.output}"
    )
    # Error message must mention the conflicting key
    combined = result.output + (result.stderr if hasattr(result, "stderr") else "")
    assert "conflicting input" in combined.lower() or "goal" in combined.lower(), (
        f"Expected conflict message in output; got:\n{combined}"
    )


# ---------------------------------------------------------------------------
# Test 4 — MCP run_workflow via in-process FastMCP server
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aiw_mcp_run_workflow_summarize_via_fastmcp_client() -> None:
    """MCP run_workflow dispatches summarize and surfaces artifact["summary"].

    Uses ``build_server().get_tool("run_workflow").fn(payload)`` — the
    in-process FastMCP server pattern. Asserts the canonical ``artifact``
    field (M19 T03) is populated (not only the deprecated ``plan`` alias).
    Resolves M18 inventory DOC-DG4 by exercising the ``payload`` wire-shape
    wrapper live in M19's own test surface.
    """
    _StubLiteLLMAdapter.script = [(_valid_summary_json(), 0.0)]

    server = build_server()
    tool = await server.get_tool("run_workflow")
    payload = RunWorkflowInput(
        workflow_id="summarize",
        inputs={"text": "The quick brown fox jumped over the lazy dog.", "max_words": 50},
        run_id="smry-mcp-1",
    )
    result = await tool.fn(payload)

    assert result.run_id == "smry-mcp-1"
    assert result.status == "completed", (
        f"Expected 'completed', got {result.status!r}: {result.error}"
    )
    assert result.artifact is not None, "artifact must be populated on completion"
    assert "summary" in result.artifact, (
        f"artifact missing 'summary' key; got {result.artifact!r}"
    )
    assert result.artifact["summary"] == "A brief summary of the text."
    assert result.error is None


# ---------------------------------------------------------------------------
# Test 5 — Cross-surface artefact identity
# ---------------------------------------------------------------------------


def test_summarize_artefact_identical_across_surfaces() -> None:
    """CLI and MCP surfaces produce byte-identical artefacts for the same stub.

    Drives ``summarize`` through both entry-points:

    - CLI side: ``CliRunner.invoke(app, ["run", "summarize", ...])`` — the
      actual ``aiw run`` entry-point; internally calls ``asyncio.run``.
    - MCP side: ``asyncio.run(_mcp_call())`` wrapping an async
      ``build_server().get_tool("run_workflow").fn(payload)`` call.

    This is a sync test so ``CliRunner`` (which internally calls
    ``asyncio.run``) does not conflict with a running event loop — the
    cycle-1 implementation was ``@pytest.mark.asyncio`` which caused that
    conflict and forced the CLI side to bypass ``CliRunner``. Cycle 2
    fixes this by making the test synchronous (MEDIUM-2 resolution).

    Both paths use the same ``_StubLiteLLMAdapter`` so the LLM response
    is deterministic.  Asserts byte-identical artefacts from both surfaces
    (pins locked H1 refinement #5 — load-bearing wire-level proof).
    """
    import asyncio as _asyncio

    stub_summary = "Stub summary output for identity test."
    stub_response = json.dumps({"summary": stub_summary})

    # --- CLI side (sync — CliRunner internally calls asyncio.run) -----------
    _StubLiteLLMAdapter.reset()
    _StubLiteLLMAdapter.script = [(stub_response, 0.0)]

    cli_result = _RUNNER.invoke(
        app,
        [
            "run",
            "summarize",
            "--input",
            "text=Identity test input text.",
            "--input",
            "max_words=20",
            "--run-id",
            "smry-identity-cli",
        ],
    )
    assert cli_result.exit_code == 0, (
        f"CLI path: expected exit 0, got {cli_result.exit_code}; "
        f"output:\n{cli_result.output}"
    )
    # CLI emits structured log lines (single-line JSON) followed by the artefact
    # JSON block (json.dumps(artefact, indent=2), multi-line) then "total cost:".
    # Extract the artefact by iteratively consuming JSON objects from the output
    # and keeping the last one before "total cost:". That last JSON object is
    # the workflow artefact emitted by _emit_cli_run_result.
    decoder = json.JSONDecoder()
    raw = cli_result.output
    pos = 0
    last_obj = None
    while pos < len(raw):
        # Skip whitespace / newlines
        while pos < len(raw) and raw[pos] in " \t\r\n":
            pos += 1
        if pos >= len(raw) or raw[pos:].startswith("total cost:"):
            break
        try:
            obj, end_pos = decoder.raw_decode(raw, pos)
            last_obj = obj
            pos = end_pos
        except json.JSONDecodeError:
            # Non-JSON line (unlikely but skip ahead to next newline)
            next_nl = raw.find("\n", pos)
            pos = next_nl + 1 if next_nl != -1 else len(raw)
    cli_artefact = last_obj
    assert cli_artefact is not None, "CLI path: artefact must be parsed from stdout"

    # --- MCP side (sync — asyncio.run wraps the async tool call) ------------
    _StubLiteLLMAdapter.reset()
    _StubLiteLLMAdapter.script = [(stub_response, 0.0)]

    async def _mcp_call():
        server = build_server()
        tool = await server.get_tool("run_workflow")
        return await tool.fn(
            RunWorkflowInput(
                workflow_id="summarize",
                inputs={"text": "Identity test input text.", "max_words": 20},
                run_id="smry-identity-mcp",
            )
        )

    mcp_result = _asyncio.run(_mcp_call())

    assert mcp_result.status == "completed", (
        f"MCP path: expected 'completed', got {mcp_result.status!r}: {mcp_result.error}"
    )
    mcp_artefact = mcp_result.artifact
    assert mcp_artefact is not None, "MCP path: artifact must be populated"

    # Cross-surface byte-identity
    assert cli_artefact == mcp_artefact, (
        f"CLI artefact {cli_artefact!r} != MCP artefact {mcp_artefact!r}"
    )
    assert cli_artefact == {"summary": stub_summary}
