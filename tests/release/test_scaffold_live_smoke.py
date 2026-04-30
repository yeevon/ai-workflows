"""Live-mode smoke test for the scaffold_workflow meta-workflow (M17 Task 02).

Gated behind ``AIW_E2E=1`` — this test invokes the real Claude Opus tier
(``ClaudeCodeRoute(cli_model_flag="opus")``) via the OAuth subprocess driver.
It does NOT run during the standard ``uv run pytest`` gate.

Purpose: verify that the iterated ``SCAFFOLD_PROMPT_TEMPLATE`` produces a
``spec_python`` that passes ``validate_scaffold_output()`` on first attempt
(no retry budget consumed) when given the canonical CS300 goal.

Mirrors ``tests/workflows/test_scaffold_workflow.py::
test_scaffold_end_to_end_with_stub_adapter`` with the stub adapter replaced
by the real ``ClaudeCodeRoute``.  The test ONLY verifies that the graph
reaches the ``preview_gate`` HumanGate interrupt with valid ``spec_python``
— it does NOT approve the gate or write any file to disk.

Relationship to other modules
------------------------------
* :mod:`ai_workflows.workflows.scaffold_workflow` — the workflow under test.
* :mod:`ai_workflows.workflows._scaffold_validator` — validator called
  against the live output.
* :mod:`ai_workflows.workflows.scaffold_workflow_prompt` — the iterated
  prompt template being validated in production.
* :mod:`ai_workflows.graph.checkpointer` — ``SqliteSaver`` factory (KDR-009).
* :mod:`ai_workflows.primitives.storage` — run registry.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from ai_workflows.graph.checkpointer import build_async_checkpointer
from ai_workflows.graph.cost_callback import CostTrackingCallback
from ai_workflows.primitives.cost import CostTracker
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.workflows._scaffold_validator import validate_scaffold_output
from ai_workflows.workflows.scaffold_workflow import (
    ScaffoldedWorkflow,
    ScaffoldWorkflowInput,
    build_scaffold_workflow,
    scaffold_workflow_tier_registry,
)

# ---------------------------------------------------------------------------
# Gate — skip unless AIW_E2E=1 is set
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    not os.getenv("AIW_E2E"),
    reason="AIW_E2E not set — live scaffold smoke skipped",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _build_config(
    tmp_path: Path,
    run_id: str,
) -> tuple[dict[str, Any], CostTracker, SQLiteStorage]:
    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await storage.create_run(run_id, "scaffold_workflow", None)
    tracker = CostTracker()
    callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=None)
    cfg: dict[str, Any] = {
        "configurable": {
            "thread_id": run_id,
            "run_id": run_id,
            # Use the real production tier registry (Claude Opus via OAuth).
            "tier_registry": scaffold_workflow_tier_registry(),
            "cost_callback": callback,
            "storage": storage,
            "workflow": "scaffold_workflow",
        }
    }
    return cfg, tracker, storage


# ---------------------------------------------------------------------------
# Live smoke test (AC-2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scaffold_live_smoke(tmp_path: Path) -> None:
    """AC-2: live Opus run reaches preview_gate with valid spec_python.

    Uses the canonical CS300 goal.  Asserts:
    - The graph pauses at the ``preview_gate`` HumanGate node (state.next
      contains the gate node name, and the target file does NOT exist).
    - The paused state's ``scaffolded_workflow`` has non-empty ``spec_python``.
    - ``validate_scaffold_output()`` does not raise on the live output.

    Does NOT resume with approval — the test halts at the gate; no file
    is written to disk.

    Requires:
    - Claude Code CLI auth in the sandbox (``claude`` on PATH + valid OAuth).
    - ``AIW_E2E=1`` in the environment.
    """
    target = tmp_path / "question_gen.py"
    run_id = "scaffold-live-smoke-01"

    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_scaffold_workflow().compile(checkpointer=checkpointer)

    cfg, tracker, storage = await _build_config(tmp_path, run_id)

    initial = {
        "run_id": run_id,
        "input": ScaffoldWorkflowInput(
            goal="generate exam questions from a textbook chapter",
            target_path=target,
        ),
    }

    # Invoke — the graph should run to the HumanGate interrupt and pause.
    await app.ainvoke(initial, config=cfg, durability="sync")

    # The target file must NOT exist yet (no approval has been given).
    assert not target.exists(), (
        "scaffold target must not be written before gate approval"
    )

    # Inspect the paused state.
    state = await app.aget_state(cfg)

    # The graph must be paused at the preview_gate node.
    assert state.next, "graph should be paused at the preview_gate (state.next non-empty)"
    assert "preview_gate" in state.next, (
        f"expected graph to pause at 'preview_gate'; got state.next={state.next!r}"
    )

    # The scaffolded_workflow field must be populated with non-empty spec_python.
    scaffolded: ScaffoldedWorkflow | None = state.values.get("scaffolded_workflow")
    assert scaffolded is not None, "scaffolded_workflow must be present in paused state"
    assert scaffolded.spec_python, "spec_python must be non-empty"

    # The live output must pass the validator (AC-1 proxy: first-attempt quality).
    validate_scaffold_output(scaffolded)  # raises ScaffoldOutputValidationError on failure
