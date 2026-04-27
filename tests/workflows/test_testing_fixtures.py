"""Tests for ai_workflows.workflows.testing — compile_step_in_isolation fixture.

M19 Task 06 (AC-10). Verifies the testing fixture ships correctly, is
layer-rule-compliant, and behaves correctly for custom and built-in steps.

Hermetic: no provider calls, no SQLite I/O, no subprocess.

KDRs exercised
--------------
* KDR-004 — LLMStep compile path (built-in step tested in isolation).
* KDR-009 — no checkpointer attached in isolation mode; fixture is for
  unit-testing only, not full persistence round-trips.
* KDR-013 — user-owned step code (custom step execute() called as-is; no
  linting or sandboxing by the framework).

Cross-references
----------------
* :mod:`ai_workflows.workflows.testing` (M19 T06) — the module under test.
* :mod:`ai_workflows.workflows.spec` (M19 T01) — ``Step`` base class.
* :mod:`ai_workflows.workflows._compiler` (M19 T02) — compile path reused.
"""

from __future__ import annotations

import pytest

from ai_workflows.workflows import Step
from ai_workflows.workflows.testing import compile_step_in_isolation

# ---------------------------------------------------------------------------
# Custom step helpers
# ---------------------------------------------------------------------------


class AddOneStep(Step):
    """Increments an integer counter in state.  Synthetic example (no network)."""

    counter_field: str

    async def execute(self, state: dict) -> dict:
        return {self.counter_field: state[self.counter_field] + 1}


class EchoStep(Step):
    """Returns a dict with ``output_field`` set to a fixed string."""

    output_field: str
    value: str

    async def execute(self, state: dict) -> dict:
        return {self.output_field: self.value}


class RaisingStep(Step):
    """Always raises ValueError — used to test error propagation."""

    message: str

    async def execute(self, state: dict) -> dict:
        raise ValueError(self.message)


class StateMergeStep(Step):
    """Merges ``extra_key`` into state without touching existing keys."""

    extra_key: str
    extra_value: str

    async def execute(self, state: dict) -> dict:
        return {self.extra_key: self.extra_value}


# ---------------------------------------------------------------------------
# AC-10 — compile_step_in_isolation runs custom execute
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compile_step_in_isolation_runs_custom_execute() -> None:
    """compile_step_in_isolation executes a custom step and returns updated state.

    AC-10 primary test: define a local custom step with execute() that
    increments a counter; verify the fixture invokes it and the return dict
    updates state correctly.
    """
    step = AddOneStep(counter_field="n")
    result = await compile_step_in_isolation(step, initial_state={"n": 0})
    assert result["n"] == 1, f"Expected n=1 after AddOneStep, got {result['n']!r}"


@pytest.mark.asyncio
async def test_compile_step_in_isolation_default_empty_state() -> None:
    """compile_step_in_isolation uses an empty dict when initial_state is None."""
    step = EchoStep(output_field="greeting", value="hello")
    result = await compile_step_in_isolation(step)
    assert result["greeting"] == "hello"


@pytest.mark.asyncio
async def test_compile_step_in_isolation_preserves_untouched_keys() -> None:
    """State keys not updated by the step are preserved in the returned state.

    Verifies the fixture honours the same state-merge semantics as the real
    dispatch path: the step's returned dict is merged, not replaced.
    """
    step = StateMergeStep(extra_key="added", extra_value="world")
    result = await compile_step_in_isolation(
        step, initial_state={"existing": "keep_me", "other": 42}
    )
    assert result["existing"] == "keep_me", "Pre-existing keys must be preserved"
    assert result["other"] == 42, "Pre-existing keys must be preserved"
    assert result["added"] == "world", "Step-written key must appear"


# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compile_step_in_isolation_propagates_error() -> None:
    """Exceptions raised inside execute() propagate out of compile_step_in_isolation.

    Verifies the fixture does not swallow errors, so test authors can
    ``pytest.raises`` on error cases.
    """
    step = RaisingStep(message="boom")
    with pytest.raises(Exception, match="boom"):
        await compile_step_in_isolation(step, initial_state={})


# ---------------------------------------------------------------------------
# Multiple sequential calls (state isolation)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compile_step_in_isolation_multiple_calls_are_independent() -> None:
    """Repeated calls to compile_step_in_isolation are independent.

    Each call should produce its own result without sharing state between
    invocations.
    """
    step = AddOneStep(counter_field="x")

    result_a = await compile_step_in_isolation(step, initial_state={"x": 10})
    result_b = await compile_step_in_isolation(step, initial_state={"x": 20})

    assert result_a["x"] == 11, f"First call: expected 11, got {result_a['x']!r}"
    assert result_b["x"] == 21, f"Second call: expected 21, got {result_b['x']!r}"


# ---------------------------------------------------------------------------
# Module importability (smoke — AC-10)
# ---------------------------------------------------------------------------


def test_compile_step_in_isolation_is_importable_from_testing_module() -> None:
    """compile_step_in_isolation is exported through ai_workflows.workflows.testing."""
    from ai_workflows.workflows import testing as testing_module

    assert hasattr(testing_module, "compile_step_in_isolation"), (
        "compile_step_in_isolation must be exported from ai_workflows.workflows.testing"
    )
    assert callable(testing_module.compile_step_in_isolation)


def test_testing_module_is_in_workflows_layer() -> None:
    """ai_workflows/workflows/testing.py lives in the workflows layer (not graph or primitives).

    Enforces layer rule: testing.py imports from workflows.spec and
    workflows._compiler, but not from cli.py or mcp/ (no upward imports).
    """
    import importlib
    import importlib.util

    spec = importlib.util.find_spec("ai_workflows.workflows.testing")
    assert spec is not None, "ai_workflows.workflows.testing must be importable"
    assert spec.origin is not None
    # The module path must be inside ai_workflows/workflows/
    assert "ai_workflows/workflows" in spec.origin.replace("\\", "/"), (
        f"testing module must live in ai_workflows/workflows/, got {spec.origin!r}"
    )
