"""Workflow-layer tests for M12 Task 03 slice_refactor cascade opt-in.

Verifies the module-level ``_AUDIT_CASCADE_ENABLED`` constant + env-var
override pattern (ADR-0009 / KDR-014) for the ``slice_refactor`` workflow:

1. Disabled by default (no env vars set).
2. Enabled via the global ``AIW_AUDIT_CASCADE=1`` override.
3. Enabled via the per-workflow ``AIW_AUDIT_CASCADE_SLICE_REFACTOR=1`` override.
4. ``SliceRefactorInput`` does NOT grow an ``audit_cascade_enabled`` field
   (KDR-014 regression guard).
5. The composed planner sub-graph inherits the planner module's cascade
   decision (not slice_refactor's).
6. Cascade channels on ``SliceBranchState`` do NOT reach ``SliceRefactorState``
   (Option A isolation — prevents ``InvalidUpdateError`` on parallel fan-in).
7. End-to-end: cascade-exhausted branch folds into ``SliceFailure`` with
   ``audit_cascade_exhausted:`` prefix (AC-10 wire-level smoke).
8. End-to-end: cascade-passed branch lands result in ``slice_results`` (AC-11c).
9. End-to-end: N=2 parallel cascade-enabled branches fan-in without
   ``InvalidUpdateError`` (AC-11a).

Relationship to other modules
------------------------------
* :mod:`ai_workflows.workflows.slice_refactor` — the module under test.
* :mod:`ai_workflows.workflows.planner` — composed as sub-graph; inherits its
  own cascade decision independently of slice_refactor's.
* :mod:`ai_workflows.graph.audit_cascade` — the cascade primitive.
* ``tests/graph/test_audit_cascade.py`` — source of the stub-adapter pattern
  reused in tests 7-9.
* ``tests/workflows/test_planner_cascade_enable.py`` — analogous planner tests.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

import ai_workflows.workflows as workflows
import ai_workflows.workflows.slice_refactor as slice_refactor_module
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.graph.cost_callback import CostTrackingCallback
from ai_workflows.primitives.cost import CostTracker, TokenUsage
from ai_workflows.primitives.retry import RetryPolicy
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.tiers import ClaudeCodeRoute, LiteLLMRoute, TierConfig

# ---------------------------------------------------------------------------
# Registry restore fixture — required because tests 1-3 call _reset_for_tests
# and reload the module, which would leave other tests without registrations.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _restore_registry() -> Iterator[None]:
    """Restore workflow registry + module dict after each reload-using test.

    Tests that call ``importlib.reload()`` re-execute the module's top-level
    code, which: (a) creates new class objects (``SliceResult``, etc.) that
    break ``isinstance()`` checks in sibling test files holding pre-reload
    references; (b) re-registers builders with new function-object identities
    that conflict with the registry.

    Strategy — full module ``__dict__`` snapshot:

    1. **Setup**: snapshot both workflow modules' ``__dict__`` and the
       registry, ensuring both companion modules are already in
       ``sys.modules`` so the first-import side effect fires exactly once.
    2. **Teardown**: clear the registry, restore both modules' ``__dict__``
       from the snapshot (this reinstates the original class objects so sibling
       tests' ``isinstance()`` checks stay valid), then re-register from the
       registry snapshot.
    """
    import copy
    import sys

    # Ensure companion module is in sys.modules before the test runs.
    import ai_workflows.workflows.planner  # noqa: F401  # side-effect import

    _planner_mod = sys.modules["ai_workflows.workflows.planner"]
    _sr_mod = sys.modules["ai_workflows.workflows.slice_refactor"]

    # Shallow-copy the module __dict__ (values are class/function refs — no
    # deep copy needed to preserve identity).
    planner_dict_snapshot = dict(_planner_mod.__dict__)
    sr_dict_snapshot = dict(_sr_mod.__dict__)
    registry_snapshot = copy.copy(workflows._REGISTRY)

    yield

    # Restore planner module state (reinstate pre-reload class objects).
    _planner_mod.__dict__.clear()
    _planner_mod.__dict__.update(planner_dict_snapshot)

    # Restore slice_refactor module state.
    _sr_mod.__dict__.clear()
    _sr_mod.__dict__.update(sr_dict_snapshot)

    # Restore registry to original builder function objects.
    workflows._reset_for_tests()
    for name, builder in registry_snapshot.items():
        workflows.register(name, builder)


# ---------------------------------------------------------------------------
# Test 1: disabled by default
# ---------------------------------------------------------------------------


def test_audit_cascade_disabled_by_default(
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[name-defined]  # noqa: F821
) -> None:
    """AC-1: ``_AUDIT_CASCADE_ENABLED`` is False when no env vars are set.

    Uses ``monkeypatch.delenv`` + ``importlib.reload`` to guarantee the module
    is evaluated with a clean environment regardless of test-run order
    (TA-LOW-02 — prevents flake when test #2 or #3 runs first in the same
    session).
    """
    monkeypatch.delenv("AIW_AUDIT_CASCADE", raising=False)
    monkeypatch.delenv("AIW_AUDIT_CASCADE_SLICE_REFACTOR", raising=False)
    workflows._reset_for_tests()
    importlib.reload(slice_refactor_module)

    assert slice_refactor_module._AUDIT_CASCADE_ENABLED_DEFAULT is False
    assert slice_refactor_module._AUDIT_CASCADE_ENABLED is False

    # Compile: graph must build; the slice_branch sub-graph must NOT contain
    # the cascade structural marker.
    g = slice_refactor_module.build_slice_refactor()
    assert g is not None  # builds without error

    # The per-branch sub-graph (from _build_slice_branch_subgraph) should
    # contain "slice_worker" + "slice_worker_validator" but NOT the cascade
    # marker.
    from ai_workflows.workflows.slice_refactor import _build_slice_branch_subgraph
    branch = _build_slice_branch_subgraph()
    assert "slice_worker" in branch.nodes
    assert "slice_worker_validator" in branch.nodes
    # 'cascade_bridge' is only present in the cascade path.
    assert "cascade_bridge" not in branch.nodes, (
        "Disabled-default branch must NOT contain 'cascade_bridge' node "
        "(only added when _AUDIT_CASCADE_ENABLED=True)"
    )


# ---------------------------------------------------------------------------
# Test 2: enabled via global env var
# ---------------------------------------------------------------------------


def test_audit_cascade_enabled_via_global_env(
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[name-defined]  # noqa: F821
) -> None:
    """AC-2: ``_AUDIT_CASCADE_ENABLED`` is True when ``AIW_AUDIT_CASCADE=1``."""
    monkeypatch.setenv("AIW_AUDIT_CASCADE", "1")
    monkeypatch.delenv("AIW_AUDIT_CASCADE_SLICE_REFACTOR", raising=False)
    workflows._reset_for_tests()
    importlib.reload(slice_refactor_module)

    assert slice_refactor_module._AUDIT_CASCADE_ENABLED is True

    # The per-branch sub-graph must contain the cascade structural marker.
    from ai_workflows.workflows.slice_refactor import _build_slice_branch_subgraph
    branch = _build_slice_branch_subgraph()
    # The cascade sub-graph is embedded as 'slice_worker' in the branch; the
    # 'cascade_bridge' node is added in the outer branch graph only in cascade path.
    assert "cascade_bridge" in branch.nodes, (
        "Enabled branch must contain 'cascade_bridge' node "
        "(cascade structural marker — only present when _AUDIT_CASCADE_ENABLED=True)"
    )
    # standalone slice_worker_validator should be absent (cascade replaces it)
    assert "slice_worker_validator" not in branch.nodes, (
        "Enabled branch must NOT contain standalone 'slice_worker_validator'"
    )


# ---------------------------------------------------------------------------
# Test 3: enabled via per-workflow env var
# ---------------------------------------------------------------------------


def test_audit_cascade_enabled_via_per_workflow_env(
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[name-defined]  # noqa: F821
) -> None:
    """AC-3: enabled when ``AIW_AUDIT_CASCADE_SLICE_REFACTOR=1`` (global not set)."""
    monkeypatch.delenv("AIW_AUDIT_CASCADE", raising=False)
    monkeypatch.setenv("AIW_AUDIT_CASCADE_SLICE_REFACTOR", "1")
    workflows._reset_for_tests()
    importlib.reload(slice_refactor_module)

    assert slice_refactor_module._AUDIT_CASCADE_ENABLED is True

    from ai_workflows.workflows.slice_refactor import _build_slice_branch_subgraph
    branch = _build_slice_branch_subgraph()
    assert "cascade_bridge" in branch.nodes, (
        "Per-workflow-env enabled branch must contain 'cascade_bridge' node "
        "(cascade structural marker)"
    )
    assert "slice_worker_validator" not in branch.nodes


# ---------------------------------------------------------------------------
# Test 4: SliceRefactorInput unchanged at T03 (KDR-014 regression guard)
# ---------------------------------------------------------------------------


def test_slice_refactor_input_unchanged_at_t03() -> None:
    """AC-4 / KDR-014: ``SliceRefactorInput.model_fields`` does NOT contain quality knobs.

    Guards against future spec-drift where a Builder might quietly add
    ``audit_cascade_enabled`` (or similar) to the public input contract.
    """
    from ai_workflows.workflows.slice_refactor import SliceRefactorInput

    field_names = set(SliceRefactorInput.model_fields)
    forbidden = {
        "audit_cascade_enabled",
        "validator_strict",
        "retry_budget",
        "tier_default",
        "fallback_chain",
        "escalation_threshold",
    }
    violations = forbidden & field_names
    assert not violations, (
        f"SliceRefactorInput contains quality-knob field(s) that violate KDR-014: "
        f"{violations!r}. Move them to module-level constants + env-var per "
        f"ADR-0009."
    )


# ---------------------------------------------------------------------------
# Test 5: planner subgraph inherits planner module's cascade decision
# ---------------------------------------------------------------------------


def test_planner_subgraph_inherits_planner_module_decision(
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[name-defined]  # noqa: F821
) -> None:
    """AC-5 (TA-LOW-07): planner sub-graph cascade tracks the planner module constant.

    Sets ``AIW_AUDIT_CASCADE_PLANNER=1`` (planner cascade ON) but leaves
    ``AIW_AUDIT_CASCADE_SLICE_REFACTOR`` unset (slice_refactor cascade OFF).

    Asserts:
    - The compiled planner graph has 'planner_explorer_audit_primary'
      in its nodes (positive side — planner cascade wired in).
    - The slice-branch sub-graph does NOT have 'slice_worker_audit_primary'
      in its nodes (negative side — slice_refactor cascade NOT wired in).
    """
    import ai_workflows.workflows.planner as planner_module

    monkeypatch.delenv("AIW_AUDIT_CASCADE", raising=False)
    monkeypatch.setenv("AIW_AUDIT_CASCADE_PLANNER", "1")
    monkeypatch.delenv("AIW_AUDIT_CASCADE_SLICE_REFACTOR", raising=False)

    workflows._reset_for_tests()
    importlib.reload(planner_module)
    importlib.reload(slice_refactor_module)

    # Positive: planner sub-graph (compiled) should have the cascade bridge node
    # (only added in the cascade path when _AUDIT_CASCADE_ENABLED=True in planner).
    planner_compiled = planner_module.build_planner().compile()
    assert "cascade_bridge" in planner_compiled.nodes, (
        "Planner sub-graph must contain 'cascade_bridge' node "
        "when AIW_AUDIT_CASCADE_PLANNER=1"
    )
    assert "explorer_validator" not in planner_compiled.nodes, (
        "Planner sub-graph must NOT have standalone 'explorer_validator' "
        "when AIW_AUDIT_CASCADE_PLANNER=1 (cascade replaces it)"
    )

    # Negative: slice-branch sub-graph must NOT have the cascade bridge node
    # (slice_refactor's cascade is off — only planner's is on).
    from ai_workflows.workflows.slice_refactor import _build_slice_branch_subgraph
    branch = _build_slice_branch_subgraph()
    assert "cascade_bridge" not in branch.nodes, (
        "Slice-branch sub-graph must NOT contain 'cascade_bridge' node "
        "when only AIW_AUDIT_CASCADE_PLANNER=1 (not SLICE_REFACTOR)"
    )
    assert "slice_worker_validator" in branch.nodes, (
        "Slice-branch sub-graph must still have standalone 'slice_worker_validator' "
        "when only planner cascade is on"
    )


# ---------------------------------------------------------------------------
# Test 6: parallel fan-out safety with cascade enabled
# ---------------------------------------------------------------------------


def test_cascade_writes_survive_parallel_fanout(
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[name-defined]  # noqa: F821
) -> None:
    """AC: cascade channels on SliceBranchState do NOT reach the parent state.

    Verifies that ``cascade_role``, ``cascade_transcript``, and
    ``slice_worker_audit_*`` channels are declared on :class:`SliceBranchState`
    but NOT on :class:`SliceRefactorState`, ensuring no ``InvalidUpdateError``
    fires when N parallel cascade-enabled branches fan in.

    This is a structural test (TypedDict annotation inspection) — it
    asserts Option A's isolation property without needing a live LangGraph run.
    """
    from typing import get_type_hints

    from ai_workflows.workflows.slice_refactor import (
        SliceBranchState,
        SliceRefactorState,
    )

    # Ensure the module is reloaded without cascade for this inspection test
    # (the channel declarations are present regardless of _AUDIT_CASCADE_ENABLED).
    monkeypatch.delenv("AIW_AUDIT_CASCADE", raising=False)
    monkeypatch.delenv("AIW_AUDIT_CASCADE_SLICE_REFACTOR", raising=False)
    workflows._reset_for_tests()
    importlib.reload(slice_refactor_module)

    branch_hints = get_type_hints(SliceBranchState, include_extras=True)
    parent_hints = get_type_hints(SliceRefactorState, include_extras=True)

    cascade_branch_channels = {
        "cascade_role",
        "cascade_transcript",
        "slice_worker_audit_primary_output",
        "slice_worker_audit_primary_parsed",
        "slice_worker_audit_primary_output_revision_hint",
        "slice_worker_audit_auditor_output",
        "slice_worker_audit_auditor_output_revision_hint",
        "slice_worker_audit_audit_verdict",
        "slice_worker_audit_audit_exhausted_response",
    }

    for channel in cascade_branch_channels:
        assert channel in branch_hints, (
            f"SliceBranchState must declare cascade channel '{channel}' "
            f"for the cascade sub-graph to write into it (Option A)"
        )
        assert channel not in parent_hints, (
            f"SliceRefactorState must NOT declare cascade channel '{channel}' "
            f"(Option A — keeps cascade writes branch-local, prevents "
            f"InvalidUpdateError on parallel fan-in)"
        )


# ===========================================================================
# Stub adapters (mirroring tests/graph/test_audit_cascade.py pattern)
# ===========================================================================

class _E2EStubLiteLLMAdapter:
    """Scriptable LiteLLMAdapter stub for workflow-layer e2e tests.

    Class-level ``script`` is a list of ``(text, cost_usd)`` tuples or
    Exception instances consumed FIFO.  Reset before each e2e test via
    the ``_reset_e2e_stubs`` fixture.
    """

    script: list[Any] = []
    calls: list[dict] = []

    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        self.route = route

    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict],
        response_format: Any = None,
    ) -> tuple[str, TokenUsage]:
        _E2EStubLiteLLMAdapter.calls.append({"system": system, "messages": messages})
        if not _E2EStubLiteLLMAdapter.script:
            raise AssertionError("E2E LiteLLM stub script exhausted")
        head = _E2EStubLiteLLMAdapter.script.pop(0)
        if isinstance(head, BaseException):
            raise head
        text, cost = head
        return text, TokenUsage(
            input_tokens=5, output_tokens=7, cost_usd=cost, model=self.route.model
        )


class _E2EStubClaudeCodeAdapter:
    """Scriptable ClaudeCodeSubprocess stub for workflow-layer e2e tests.

    Separate from the LiteLLM stub so the primary and auditor paths are
    scripted independently.  Reset alongside ``_E2EStubLiteLLMAdapter``
    via the ``_reset_e2e_stubs`` fixture.
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
        _E2EStubClaudeCodeAdapter.calls.append({"system": system, "messages": messages})
        if not _E2EStubClaudeCodeAdapter.script:
            raise AssertionError("E2E ClaudeCode stub script exhausted")
        head = _E2EStubClaudeCodeAdapter.script.pop(0)
        if isinstance(head, BaseException):
            raise head
        text, cost = head
        return text, TokenUsage(
            input_tokens=3, output_tokens=2, cost_usd=cost,
            model=self.route.cli_model_flag
        )


# E2E script helpers — canonical JSON responses used across tests 7-9.
_SLICE_RESULT_JSON = (
    '{"slice_id": "s1", "diff": "--- a\\n+++ b\\n@@ -1 +1 @@\\n-old\\n+new", "notes": "ok"}'
)
_AUDIT_PASS_JSON = '{"passed": true, "failure_reasons": [], "suggested_approach": null}'
_AUDIT_FAIL_JSON = (
    '{"passed": false, "failure_reasons": ["output incomplete"], '
    '"suggested_approach": "add more context"}'
)

# Small retry policy so the exhaustion test only needs 2 primary+auditor rounds.
_E2E_POLICY_2 = RetryPolicy(max_transient_attempts=3, max_semantic_attempts=2)


def _e2e_tier_registry() -> dict[str, TierConfig]:
    """Minimal tier registry for e2e tests: slice-worker (LiteLLM) + auditor-sonnet."""
    return {
        "slice-worker": TierConfig(
            name="slice-worker",
            route=LiteLLMRoute(model="ollama/qwen2.5-coder:32b"),
            max_concurrency=1,
            per_call_timeout_s=30,
        ),
        "auditor-sonnet": TierConfig(
            name="auditor-sonnet",
            route=ClaudeCodeRoute(cli_model_flag="sonnet"),
            max_concurrency=1,
            per_call_timeout_s=30,
        ),
    }


def _e2e_config(run_id: str, storage: Any) -> dict[str, Any]:
    """Build a RunnableConfig dict for the branch sub-graph invocation."""
    tracker = CostTracker()
    callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=None)
    return {
        "configurable": {
            "thread_id": run_id,
            "run_id": run_id,
            "tier_registry": _e2e_tier_registry(),
            "cost_callback": callback,
            "storage": storage,
            "pricing": {},
        }
    }


# ===========================================================================
# Test 7: e2e — cascade-exhausted branch folds into SliceFailure (AC-10 wire)
# ===========================================================================


async def test_cascade_exhaustion_folded_into_slice_failure_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AC-10 wire-level smoke: cascade exhaustion produces ``audit_cascade_exhausted:`` prefix.

    Invokes ``_build_slice_branch_subgraph()`` with cascade enabled and
    ``max_semantic_attempts=2`` (via monkeypatching ``SLICE_WORKER_RETRY_POLICY``).
    Scripts the primary to always return valid JSON; scripts the auditor to
    always fail → 2 audit cycles exhaust → ``AuditFailure`` raised by cascade →
    ``_slice_branch_finalize`` folds it into a ``SliceFailure`` with the
    ``audit_cascade_exhausted:`` prefix.

    Asserts (AC-10 + AC-11b):
    * no exception raised (graph exits to END, not interrupt)
    * ``slice_failures`` contains exactly 1 entry
    * ``slice_results`` is empty
    * ``slice_failures[0].last_error`` starts with ``"audit_cascade_exhausted:"``
    * the prefix contains the auditor's ``failure_reasons`` and ``suggested_approach``
    """
    # Install stub adapters on the tiered_node module (same patch point as
    # tests/graph/test_audit_cascade.py — the cascade primitive reads adapters
    # from tiered_node at call time).
    _E2EStubLiteLLMAdapter.script = []
    _E2EStubLiteLLMAdapter.calls = []
    _E2EStubClaudeCodeAdapter.script = []
    _E2EStubClaudeCodeAdapter.calls = []
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _E2EStubLiteLLMAdapter)
    monkeypatch.setattr(tiered_node_module, "ClaudeCodeSubprocess", _E2EStubClaudeCodeAdapter)

    # Enable cascade for slice_refactor.
    monkeypatch.setenv("AIW_AUDIT_CASCADE_SLICE_REFACTOR", "1")
    monkeypatch.delenv("AIW_AUDIT_CASCADE", raising=False)
    workflows._reset_for_tests()
    importlib.reload(slice_refactor_module)

    # Patch the retry policy to max_semantic_attempts=2 so the test only needs
    # 2 primary calls + 2 auditor calls to exhaust (instead of 3).
    monkeypatch.setattr(slice_refactor_module, "SLICE_WORKER_RETRY_POLICY", _E2E_POLICY_2)

    # Script: primary fires twice (2 valid JSON); auditor fires twice (both fail).
    _E2EStubLiteLLMAdapter.script = [
        (_SLICE_RESULT_JSON, 0.001),
        (_SLICE_RESULT_JSON, 0.001),
    ]
    _E2EStubClaudeCodeAdapter.script = [
        (_AUDIT_FAIL_JSON, 0.0),
        (_AUDIT_FAIL_JSON, 0.0),
    ]

    storage = await SQLiteStorage.open(tmp_path / "storage_t7.sqlite")
    await storage.create_run("r_e2e_exhaust", "slice_refactor_cascade_exhaust", None)

    from ai_workflows.workflows.slice_refactor import (
        SliceSpec,
        _build_slice_branch_subgraph,
    )

    branch = _build_slice_branch_subgraph()
    cfg = _e2e_config("r_e2e_exhaust", storage)

    # Invoke directly with the branch's expected initial state shape
    # (mirrors what _fan_out_to_workers sends via Send("slice_branch", {"slice": s})).
    initial_state = {
        "slice": SliceSpec(id="s1", description="refactor auth module", acceptance=["tests pass"]),
    }

    final = await branch.ainvoke(initial_state, cfg)

    # No interrupt — cascade routes to END (skip_terminal_gate=True).
    assert "__interrupt__" not in final, (
        "Expected branch to reach END (not interrupt) with skip_terminal_gate=True "
        "after cascade exhaustion"
    )

    # The exhausted cascade folds into slice_failures via _slice_branch_finalize.
    failures = final.get("slice_failures") or []
    results = final.get("slice_results") or []
    assert len(failures) == 1, (
        f"Expected 1 slice_failure after cascade exhaustion, got {len(failures)}: {failures}"
    )
    assert len(results) == 0, (
        f"Expected 0 slice_results on the exhaustion path, got {len(results)}"
    )

    failure = failures[0]
    assert failure.last_error.startswith("audit_cascade_exhausted:"), (
        f"Expected last_error to start with 'audit_cascade_exhausted:', "
        f"got: {failure.last_error!r}"
    )
    # The prefix must embed the auditor's failure_reasons and suggested_approach
    # from _AUDIT_FAIL_JSON: reasons=["output incomplete"], suggested="add more context".
    assert "output incomplete" in failure.last_error, (
        f"Expected failure_reasons 'output incomplete' in last_error: {failure.last_error!r}"
    )
    assert "add more context" in failure.last_error, (
        f"Expected suggested_approach 'add more context' in last_error: {failure.last_error!r}"
    )


# ===========================================================================
# Test 8: e2e — cascade-passed branch lands in slice_results (AC-11c)
# ===========================================================================


async def test_cascade_pass_lands_in_slice_results(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AC-11c wire-level smoke: cascade-passed branch result appears in ``slice_results``.

    Invokes ``_build_slice_branch_subgraph()`` with cascade enabled.
    Scripts the primary to return valid JSON; scripts the auditor to pass on
    the first attempt → cascade exits via the verdict node → ``cascade_bridge``
    copies ``slice_worker_audit_primary_parsed`` into ``slice_results``.

    Asserts:
    * no exception raised
    * ``slice_results`` contains exactly 1 ``SliceResult``
    * ``slice_failures`` is empty
    * the ``SliceResult.slice_id`` matches the slice spec
    """
    _E2EStubLiteLLMAdapter.script = []
    _E2EStubLiteLLMAdapter.calls = []
    _E2EStubClaudeCodeAdapter.script = []
    _E2EStubClaudeCodeAdapter.calls = []
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _E2EStubLiteLLMAdapter)
    monkeypatch.setattr(tiered_node_module, "ClaudeCodeSubprocess", _E2EStubClaudeCodeAdapter)

    monkeypatch.setenv("AIW_AUDIT_CASCADE_SLICE_REFACTOR", "1")
    monkeypatch.delenv("AIW_AUDIT_CASCADE", raising=False)
    workflows._reset_for_tests()
    importlib.reload(slice_refactor_module)

    # Script: primary once (valid JSON); auditor once (pass).
    _E2EStubLiteLLMAdapter.script = [(_SLICE_RESULT_JSON, 0.001)]
    _E2EStubClaudeCodeAdapter.script = [(_AUDIT_PASS_JSON, 0.0)]

    storage = await SQLiteStorage.open(tmp_path / "storage_t8.sqlite")
    await storage.create_run("r_e2e_pass", "slice_refactor_cascade_pass", None)

    from ai_workflows.workflows.slice_refactor import (
        SliceResult,
        SliceSpec,
        _build_slice_branch_subgraph,
    )

    branch = _build_slice_branch_subgraph()
    cfg = _e2e_config("r_e2e_pass", storage)

    initial_state = {
        "slice": SliceSpec(id="s1", description="refactor auth module", acceptance=["tests pass"]),
    }

    final = await branch.ainvoke(initial_state, cfg)

    assert "__interrupt__" not in final, (
        "Expected branch to reach END (not interrupt) on cascade-pass path"
    )

    results = final.get("slice_results") or []
    failures = final.get("slice_failures") or []
    assert len(results) == 1, (
        f"Expected 1 slice_result on the cascade-pass path, got {len(results)}: {results}"
    )
    assert len(failures) == 0, (
        f"Expected 0 slice_failures on the cascade-pass path, got {len(failures)}: {failures}"
    )

    result = results[0]
    assert isinstance(result, SliceResult), (
        f"Expected SliceResult in slice_results, got {type(result)}"
    )
    assert result.slice_id == "s1", (
        f"Expected slice_id='s1', got {result.slice_id!r}"
    )


# ===========================================================================
# Test 9: e2e — N=2 parallel cascade-enabled branches fan-in without
#          InvalidUpdateError (AC-11a)
# ===========================================================================


async def test_cascade_parallel_fanin_no_invalid_update_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AC-11a wire-level smoke: 2 cascade-enabled parallel branches fan in cleanly.

    Builds a minimal outer ``StateGraph`` using ``SliceRefactorState`` that
    fans out N=2 slices via ``Send("slice_branch", ...)`` to a compiled
    ``_build_slice_branch_subgraph()``, then fans in via the
    ``operator.add`` reducers.  Both branches are scripted to pass (1 primary
    + 1 auditor each) so the fan-in sees 2 concurrent ``slice_results`` writes
    and 2 concurrent ``cascade_role``/``cascade_transcript`` writes — the
    last of which would fire ``InvalidUpdateError`` if those channels reached
    ``SliceRefactorState`` (Option A guarantees they don't).

    Asserts:
    * no ``InvalidUpdateError`` raised (LangGraph fan-in safety)
    * ``slice_results`` accumulates exactly 2 entries (one per branch)
    * ``slice_failures`` is empty
    * ``cascade_role`` and ``cascade_transcript`` are NOT in the outer
      final state (proving the channels stayed branch-local)
    """
    _E2EStubLiteLLMAdapter.script = []
    _E2EStubLiteLLMAdapter.calls = []
    _E2EStubClaudeCodeAdapter.script = []
    _E2EStubClaudeCodeAdapter.calls = []
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _E2EStubLiteLLMAdapter)
    monkeypatch.setattr(tiered_node_module, "ClaudeCodeSubprocess", _E2EStubClaudeCodeAdapter)

    monkeypatch.setenv("AIW_AUDIT_CASCADE_SLICE_REFACTOR", "1")
    monkeypatch.delenv("AIW_AUDIT_CASCADE", raising=False)
    workflows._reset_for_tests()
    importlib.reload(slice_refactor_module)

    # N=2 branches, both pass: 2 primary calls + 2 auditor calls.
    # Each branch gets 1 item each from the shared class-level lists.
    # LangGraph runs async branches interleaved, but the adapters are
    # class-level FIFO — both branches produce valid output regardless
    # of which branch's primary call arrives first.
    _E2EStubLiteLLMAdapter.script = [
        (_SLICE_RESULT_JSON, 0.001),  # branch 1 primary
        (_SLICE_RESULT_JSON, 0.001),  # branch 2 primary (slice_id field will be "s1" from JSON)
    ]
    _E2EStubClaudeCodeAdapter.script = [
        (_AUDIT_PASS_JSON, 0.0),  # branch 1 auditor
        (_AUDIT_PASS_JSON, 0.0),  # branch 2 auditor
    ]

    storage = await SQLiteStorage.open(tmp_path / "storage_t9.sqlite")
    await storage.create_run("r_e2e_fanin", "slice_refactor_cascade_fanin", None)

    from ai_workflows.workflows.slice_refactor import (
        SliceRefactorState,
        SliceSpec,
        _build_slice_branch_subgraph,
    )

    slice_branch = _build_slice_branch_subgraph()

    # Minimal outer graph: fan out 2 slices → slice_branch → END.
    # Uses SliceRefactorState so the cascade channels (declared only on
    # SliceBranchState) cannot reach the parent — Option A isolation.
    # No type annotation on `state` to avoid NameError when LangGraph calls
    # get_type_hints() — the local-import SliceRefactorState is not in the
    # module global namespace that get_type_hints resolves against.
    def _fan_out_2(state: dict) -> list:  # type: ignore[type-arg]
        slices = state.get("slice_list") or []
        return [Send("slice_branch", {"slice": s}) for s in slices]

    outer = StateGraph(SliceRefactorState)
    outer.add_node("slice_branch", slice_branch)
    outer.add_conditional_edges(START, _fan_out_2, ["slice_branch"])
    outer.add_edge("slice_branch", END)
    compiled = outer.compile()

    cfg = _e2e_config("r_e2e_fanin", storage)

    slice_specs = [
        SliceSpec(id="s1", description="refactor module A", acceptance=["tests pass"]),
        SliceSpec(id="s2", description="refactor module B", acceptance=["tests pass"]),
    ]
    initial_state: dict[str, Any] = {"slice_list": slice_specs}

    # This must NOT raise InvalidUpdateError — if cascade channels leaked into
    # SliceRefactorState, 2 concurrent writes to scalar cascade_role /
    # cascade_transcript would trigger LangGraph's fan-in guard.
    final = await compiled.ainvoke(initial_state, cfg)

    assert "__interrupt__" not in final, (
        "Expected fan-in graph to reach END cleanly (no interrupt)"
    )

    results = final.get("slice_results") or []
    failures = final.get("slice_failures") or []
    assert len(results) == 2, (
        f"Expected 2 slice_results after 2-branch fan-in, got {len(results)}"
    )
    assert len(failures) == 0, (
        f"Expected 0 slice_failures for all-pass branches, got {len(failures)}"
    )

    # Option A isolation proof: cascade_role + cascade_transcript must NOT
    # appear in the outer state (they are branch-local to SliceBranchState).
    assert "cascade_role" not in final or final.get("cascade_role") is None, (
        "cascade_role must not propagate from SliceBranchState to SliceRefactorState "
        "(Option A — prevents InvalidUpdateError on parallel fan-in)"
    )
    assert "cascade_transcript" not in final or final.get("cascade_transcript") is None, (
        "cascade_transcript must not propagate from SliceBranchState to SliceRefactorState "
        "(Option A — prevents InvalidUpdateError on parallel fan-in)"
    )
