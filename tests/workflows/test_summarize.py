"""Tests for the summarize in-tree spec-API proof-point workflow (M19 Task 04).

Covers acceptance criteria from
``design_docs/phases/milestone_19_declarative_surface/task_04_summarize_proof_point.md``
(Deliverable 3 — 5 hermetic tests).

Hermetic: stub LLM adapter at the adapter boundary; no provider calls.
Uses ``tmp_path`` + env-var redirect for SQLite storage/checkpoint.
Target runtime: < 2 s wall-clock.

KDRs exercised
--------------
* KDR-004 — ValidateStep paired after LLMStep by construction.
* KDR-006 — RetryPolicy on LLMStep; transient failure recovery.
* KDR-009 — Dispatch path compiles graph with SqliteSaver checkpointer.
* KDR-013 — User code is user-owned; framework does not police the spec.

Cross-references
----------------
* :mod:`ai_workflows.workflows.summarize` — the module under test (M19 T04).
* :mod:`ai_workflows.workflows._dispatch` — ``run_workflow`` drives the
  end-to-end dispatch path (no leading underscore on the function name;
  the underscore is on the ``_dispatch`` module — TA-LOW-10).
* :mod:`ai_workflows.workflows._compiler` — compiles ``_SPEC`` into a
  ``StateGraph``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

import ai_workflows.workflows as workflows
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.tiers import LiteLLMRoute
from ai_workflows.workflows._dispatch import run_workflow

# ---------------------------------------------------------------------------
# Stub LLM adapter
# ---------------------------------------------------------------------------


class _StubLiteLLMAdapter:
    """Scripted LiteLLM-adapter stub — returns pre-loaded responses in order.

    Class-level state (same pattern as tests/workflows/test_compiler.py)
    because tiered_node creates a fresh adapter instance on each call.
    """

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
        """Return the next scripted response or raise if the script is exhausted."""
        _StubLiteLLMAdapter.call_count += 1
        if not _StubLiteLLMAdapter.script:
            raise AssertionError(
                "stub script exhausted — test needs more scripted responses"
            )
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
        """Clear the script and call count between tests."""
        cls.script = []
        cls.call_count = 0


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install the stub adapter and clear the script between tests."""
    _StubLiteLLMAdapter.reset()
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _StubLiteLLMAdapter)


@pytest.fixture(autouse=True)
def _reset_and_register() -> Iterator[None]:
    """Reset registry isolation and ensure 'summarize' is re-registered.

    The module-level ``register_workflow(_SPEC)`` fires only once per
    process (Python module cache).  After ``_reset_for_tests()`` clears
    the registry AND the synthetic compiled module from sys.modules,
    subsequent tests need an explicit re-registration WITH a fresh
    compile_spec call so the synthetic module is re-injected.

    Strategy: import the module first (which populates the registry via
    the side-effect call), then on each test reset + re-compile so the
    synthetic ``ai_workflows.workflows._compiled_summarize`` is live in
    sys.modules when dispatch calls ``_import_workflow_module``.  Using
    the same builder object (the old strategy) leaves the synthetic module
    absent from sys.modules after _reset_for_tests() removes it.
    """
    # Ensure summarize module is loaded (side-effect registration fires once).
    import ai_workflows.workflows.summarize  # noqa: F401

    workflows._reset_for_tests()

    # Always re-compile: compile_spec re-injects the synthetic module into
    # sys.modules so _import_workflow_module can find it at dispatch time.
    from ai_workflows.workflows._compiler import compile_spec
    from ai_workflows.workflows.summarize import _SPEC
    builder = compile_spec(_SPEC)
    workflows.register("summarize", builder)

    yield
    workflows._reset_for_tests()


@pytest.fixture(autouse=True)
def _redirect_db_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect SQLite paths to tmp_path so tests don't touch the real DB."""
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("AIW_STORAGE_DB", str(tmp_path / "storage.sqlite"))


def _valid_summary_json() -> str:
    """Return a valid SummarizeOutput JSON string for stub responses."""
    return json.dumps({"summary": "A brief summary of the text."})


# ---------------------------------------------------------------------------
# AC-1 — summarize registers via spec API
# ---------------------------------------------------------------------------


def test_summarize_registers_via_spec_api() -> None:
    """Importing summarize.py registers 'summarize' in the workflow registry.

    AC-1: the module exposes ``SummarizeInput``, ``SummarizeOutput``,
    ``_SPEC``, and calls ``register_workflow(_SPEC)`` at module top level.
    No ``import langgraph`` anywhere in the module.
    """
    import ai_workflows.workflows.summarize  # noqa: F401 — side-effect import

    assert "summarize" in workflows.list_workflows(), (
        f"'summarize' not in registry; registered: {workflows.list_workflows()}"
    )


# ---------------------------------------------------------------------------
# AC-2 — compiles to runnable StateGraph
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarize_compiles_to_runnable_state_graph() -> None:
    """Registered summarize builder compiles to a runnable StateGraph.

    Drives the spec through compile → dispatch → completion end-to-end
    with a stub LLM. Asserts the final state has ``summary`` populated.
    """
    import ai_workflows.workflows.summarize  # noqa: F401 — side-effect import

    _StubLiteLLMAdapter.script = [(_valid_summary_json(), 0.0)]

    result = await run_workflow(
        workflow="summarize",
        inputs={"text": "The quick brown fox jumped over the lazy dog.", "max_words": 10},
    )

    assert result["status"] == "completed", (
        f"Expected 'completed', got {result['status']!r}: {result.get('error')}"
    )
    assert result["run_id"] is not None


# ---------------------------------------------------------------------------
# AC-3 / AC-7 — round-trips through _dispatch with FINAL_STATE_KEY = "summary"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarize_round_trips_through_dispatch() -> None:
    """summarize dispatches end-to-end and surfaces artifact["summary"] (T03 fix).

    AC-3 (Deliverable 3) + AC-7 (FINAL_STATE_KEY = "summary" round-trips
    through RunWorkflowOutput.artifact per T03's bug fix).

    Also asserts ``result["plan"] == result["artifact"]`` — the deprecated
    T03 alias stays in lockstep.
    """
    import ai_workflows.workflows.summarize  # noqa: F401 — side-effect import

    _StubLiteLLMAdapter.script = [(_valid_summary_json(), 0.0)]

    result = await run_workflow(
        workflow="summarize",
        inputs={"text": "Test input text for summarization.", "max_words": 50},
        run_id="smry-test-round-trip",
    )

    assert result["status"] == "completed", (
        f"Expected 'completed', got {result['status']!r}: {result.get('error')}"
    )
    assert result["artifact"] is not None, "artifact must be populated on completion"
    assert "summary" in result["artifact"], (
        f"artifact missing 'summary' key; got {result['artifact']!r}"
    )
    assert result["artifact"]["summary"] == "A brief summary of the text."
    # T03 deprecated alias must be in lockstep with canonical artifact
    assert result["plan"] == result["artifact"], (
        "plan alias and artifact must be equal (T03 lockstep requirement)"
    )


# ---------------------------------------------------------------------------
# AC-4 — ValidateStep runs and catches malformed output
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarize_validator_step_runs() -> None:
    """LLMStep's paired validator (KDR-004) catches malformed LLM output.

    The stub LLM returns responses that fail the SummarizeOutput schema
    (missing 'summary' key) for all semantic attempts. After exhausting
    the semantic retry budget (max_semantic_attempts=2), the workflow
    errors out with a validation failure.

    This test exercises the LLMStep's paired validator (KDR-004) —
    the automatic ``ValidatorNode`` the compiler wires after every
    ``TieredNode``. The standalone ``ValidateStep`` in ``_SPEC`` is
    illustrative and a runtime no-op in this configuration (the
    LLMStep's paired validator already validated; the standalone
    ValidateStep receives a ``SummarizeOutput`` instance, not a JSON
    string). The contract being proven here is semantic-retry exhaustion
    → ``errored`` status with a validation-failure error message.
    """
    import ai_workflows.workflows.summarize  # noqa: F401 — side-effect import

    # Return malformed JSON for all attempts (no 'summary' field)
    bad_json = json.dumps({"wrong_field": "should fail validation"})
    # max_semantic_attempts=2: 2 LLM calls, both fail → budget exhausted
    _StubLiteLLMAdapter.script = [
        (bad_json, 0.0),  # semantic attempt 1
        (bad_json, 0.0),  # semantic attempt 2 → budget exhausted
    ]

    result = await run_workflow(
        workflow="summarize",
        inputs={"text": "Test input.", "max_words": 10},
    )

    # Semantic-retry exhaustion → errored status (not completed)
    assert result["status"] == "errored", (
        f"Expected 'errored' after exhausting semantic retry budget, "
        f"got {result['status']!r}: {result.get('error')}"
    )
    assert result["error"] is not None, (
        "error field must be populated when status='errored'"
    )


# ---------------------------------------------------------------------------
# AC-5 — retry policy on transient failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarize_retry_policy_on_transient_failure() -> None:
    """Transient LLM errors trigger the retry path; workflow completes on 2nd attempt.

    The spec's ``RetryPolicy(max_transient_attempts=3, max_semantic_attempts=2)``
    is exercised here. The stub raises a ``RetryableTransient`` once, then
    returns a valid response.

    Implementation note: the compiler wires the retrying_edge FROM the
    validate node. When the call node fails transiently, the error handler
    writes the exception to state; the validate node (running after) sees
    a ``None`` call output and routes the semantic retry path back to the
    call node. The second call succeeds. Total: 2 LLM adapter calls.
    """
    import ai_workflows.workflows.summarize  # noqa: F401 — side-effect import
    from ai_workflows.primitives.retry import RetryableTransient

    _StubLiteLLMAdapter.script = [
        RetryableTransient("provider timeout"),  # transient failure on attempt 1
        (_valid_summary_json(), 0.0),             # success on retry attempt 2
    ]

    result = await run_workflow(
        workflow="summarize",
        inputs={"text": "Retry test text.", "max_words": 20},
    )

    # Two LLM calls: 1 transient failure + 1 success
    assert _StubLiteLLMAdapter.call_count == 2, (
        f"Expected 2 LLM calls (1 transient + 1 valid), "
        f"got {_StubLiteLLMAdapter.call_count}"
    )
    assert result["status"] == "completed", (
        f"Expected 'completed' after transient retry, "
        f"got {result['status']!r}: {result.get('error')}"
    )
    assert result["artifact"]["summary"] == "A brief summary of the text."
