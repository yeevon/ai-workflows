"""M11 Task 01 (Issue C) — ``status="aborted"`` round-trips pydantic validation.

Pre-M11 the dispatch-level ``status="aborted"`` return path
([`_dispatch.py`](../../ai_workflows/workflows/_dispatch.py) —
ollama-fallback ABORT and double-failure hard-stop branches) would
have raised :class:`pydantic.ValidationError` at the MCP boundary
because neither output-model Literal union listed ``"aborted"``. M11
T01 added the missing Literal value; this test pins the fix.

A fuller integration test that actually drives the ollama-fallback
abort through the full dispatch path is unnecessary — the pydantic
validation is what the schema enforces, and the existing
``tests/workflows/test_*_ollama_fallback*.py`` suite already exercises
the dispatch triggers. A cheap pydantic round-trip is sufficient
regression protection for the schema half of the contract.

Relationship to other modules
-----------------------------
* :mod:`ai_workflows.mcp.schemas` — the Literal unions under test.
* :mod:`ai_workflows.workflows._dispatch` — the two dispatch branches
  that emit ``status="aborted"`` (ollama-fallback + hard-stop).
"""

from __future__ import annotations

from ai_workflows.mcp.schemas import ResumeRunOutput, RunWorkflowOutput


def test_aborted_status_does_not_raise_validation_error() -> None:
    """``RunWorkflowOutput`` / ``ResumeRunOutput`` accept ``status="aborted"``.

    Mirrors the dispatch-return shape for both the ollama-fallback
    abort branch and the double-failure hard-stop branch. Pre-M11 this
    would have raised :class:`pydantic.ValidationError`.
    """
    run_raw = {
        "run_id": "run-abort-smoke",
        "status": "aborted",
        "awaiting": None,
        "plan": None,
        "total_cost_usd": 0.0034,
        "error": "ollama_fallback: operator aborted run at the circuit-breaker gate",
        "gate_context": None,
    }
    run_output = RunWorkflowOutput(**run_raw)
    assert run_output.status == "aborted"
    assert run_output.plan is None
    assert run_output.gate_context is None
    assert run_output.awaiting is None
    assert run_output.error is not None
    assert "ollama_fallback" in run_output.error

    resume_raw = {
        "run_id": "run-abort-resume",
        "status": "aborted",
        "awaiting": None,
        "plan": None,
        "total_cost_usd": 0.0055,
        "error": "ollama_fallback: operator aborted run at the circuit-breaker gate",
        "gate_context": None,
    }
    resume_output = ResumeRunOutput(**resume_raw)
    assert resume_output.status == "aborted"
    assert resume_output.plan is None
    assert resume_output.gate_context is None
    assert resume_output.awaiting is None
    assert resume_output.error is not None
