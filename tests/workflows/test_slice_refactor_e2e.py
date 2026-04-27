"""M6 Task 08 — hermetic end-to-end smoke for ``slice_refactor``.

Drives :func:`ai_workflows.workflows._dispatch.run_workflow` →
:func:`ai_workflows.workflows._dispatch.resume_run` (the shared entry
point both the ``aiw run`` CLI and the ``run_workflow`` MCP tool call)
through the full pipeline:

``START → planner_subgraph → slice_list_normalize → slice_branch (fan-out)
→ aggregate → slice_refactor_review → apply → END``

Always-run (no ``AIW_E2E`` gate). Stubs the ``LiteLLMAdapter`` at the
:mod:`ai_workflows.graph.tiered_node` boundary so no network call
fires; the sibling ``tests/e2e/test_slice_refactor_smoke.py`` covers
the live Qwen + Claude Code path.

Acceptance (from task_08_e2e_smoke.md):

* Approve-at-both-gates path: 3 artefacts in Storage, ``runs.status ==
  "completed"``, ``runs.total_cost_usd >= 0``.
* Reject-at-outer-gate path: 0 artefacts, ``runs.status ==
  "gate_rejected"``.
* KDR-003 regression: no ``anthropic`` import / no ``ANTHROPIC_API_KEY``
  read in production code.

Relationship to siblings
------------------------
* :mod:`tests/workflows/test_slice_refactor_strict_gate.py` — T05 gate
  tests that use ``build_slice_refactor().compile()`` directly; T08
  goes one level up through ``_dispatch`` so the CLI/MCP contract is
  also exercised (status flip, cost stamping, artefact count in the
  result dict).
* :mod:`tests/e2e/test_planner_smoke.py` — reference pattern the live
  T08 smoke mirrors.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from ai_workflows import workflows
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig
from ai_workflows.workflows import planner as planner_module
from ai_workflows.workflows import slice_refactor as slice_refactor_module
from ai_workflows.workflows._dispatch import resume_run, run_workflow
from ai_workflows.workflows.planner import build_planner
from ai_workflows.workflows.slice_refactor import (
    SLICE_RESULT_ARTIFACT_KIND,
    SliceResult,
    build_slice_refactor,
)

#: Production tree scanned for the KDR-003 regression grep.
_PRODUCTION_ROOT = Path(__file__).resolve().parents[2] / "ai_workflows"

#: Regex that matches an ``import anthropic`` / ``from anthropic`` line
#: or any use of the literal ``ANTHROPIC_API_KEY`` env var name. Prose
#: mentions of the ban in docstrings are intentionally not matched.
_KDR_003_REGRESSION = re.compile(
    r"(^\s*import\s+anthropic\b|^\s*from\s+anthropic\b|ANTHROPIC_API_KEY)",
    re.MULTILINE,
)


# ---------------------------------------------------------------------------
# Stub adapter — mirrors the T05 / T07 per-slice scripting pattern
# ---------------------------------------------------------------------------


class _StubLiteLLMAdapter:
    """Scripted adapter for the planner sub-graph + slice-worker tier.

    Calls whose prompt does not contain ``Slice id:`` pop from
    :attr:`script` (the planner sub-graph's explorer + synth calls);
    calls that do pop from :attr:`worker_script` keyed by slice id.
    Each script entry is ``(text, cost_usd)`` or an exception to raise.
    """

    script: list[Any] = []
    call_count: int = 0
    worker_script: dict[str, list[Any]] = {}
    worker_calls_by_slice: dict[str, int] = {}

    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        self.route = route

    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict],
        response_format: Any = None,
    ) -> tuple[str, TokenUsage]:
        _StubLiteLLMAdapter.call_count += 1
        content = messages[0].get("content") or ""
        if "Slice id:" in content:
            first_line = content.splitlines()[0]
            _, _, sid = first_line.partition("Slice id: ")
            sid = sid.strip()
            _StubLiteLLMAdapter.worker_calls_by_slice[sid] = (
                _StubLiteLLMAdapter.worker_calls_by_slice.get(sid, 0) + 1
            )
            per_slice = _StubLiteLLMAdapter.worker_script.get(sid)
            if not per_slice:
                raise AssertionError(
                    f"stub worker script exhausted for slice {sid!r}"
                )
            head = per_slice.pop(0)
        else:
            if not _StubLiteLLMAdapter.script:
                raise AssertionError("stub planner script exhausted")
            head = _StubLiteLLMAdapter.script.pop(0)

        if isinstance(head, BaseException):
            raise head
        text, cost = head
        return text, TokenUsage(
            input_tokens=7,
            output_tokens=11,
            cost_usd=cost,
            model=self.route.model,
        )

    @classmethod
    def reset(cls) -> None:
        cls.script = []
        cls.call_count = 0
        cls.worker_script = {}
        cls.worker_calls_by_slice = defaultdict(int)


@pytest.fixture(autouse=True)
def _reset_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    _StubLiteLLMAdapter.reset()
    monkeypatch.setattr(
        tiered_node_module, "LiteLLMAdapter", _StubLiteLLMAdapter
    )


@pytest.fixture(autouse=True)
def _reensure_workflows_registered() -> Iterator[None]:
    workflows._reset_for_tests()
    workflows.register("planner", build_planner)
    workflows.register("slice_refactor", build_slice_refactor)
    yield


@pytest.fixture(autouse=True)
def _redirect_default_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Redirect ``default_storage_path`` + checkpointer DB into ``tmp_path``.

    ``_dispatch.run_workflow`` / ``resume_run`` call
    :func:`ai_workflows.primitives.storage.default_storage_path` and
    :func:`ai_workflows.graph.checkpointer.build_async_checkpointer`
    with no arguments; both pick up env-var overrides set by the CLI
    fixtures. Mirroring that pattern keeps the dispatch path hermetic
    under pytest without bypassing the production resolution logic.
    """
    monkeypatch.setenv("AIW_STORAGE_DB", str(tmp_path / "storage.sqlite"))
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))


# ---------------------------------------------------------------------------
# Fixture helpers — shared between the happy + reject paths
# ---------------------------------------------------------------------------


def _valid_explorer_json() -> str:
    return json.dumps(
        {
            "summary": "Three isolated slices.",
            "considerations": ["Independent modules"],
            "assumptions": ["Green CI"],
        }
    )


def _three_step_plan_json() -> str:
    return json.dumps(
        {
            "goal": "Refactor monolith into three slices.",
            "summary": "Three parallel slices.",
            "steps": [
                {
                    "index": i,
                    "title": f"Slice {i}",
                    "rationale": f"rationale {i}",
                    "actions": [f"action {i}"],
                }
                for i in range(1, 4)
            ],
        }
    )


def _valid_slice_result_json(slice_id: str) -> str:
    return json.dumps(
        {
            "slice_id": slice_id,
            "diff": f"--- a/slice{slice_id}\n+++ b/slice{slice_id}",
            "notes": f"applied slice {slice_id}",
        }
    )


def _tier_registry_override() -> dict[str, TierConfig]:
    """Return a registry whose tiers all point at the stubbed LiteLLM.

    Overrides :func:`slice_refactor_tier_registry` so even the
    ``planner-synth`` tier (default: Claude Code) routes through the
    stub adapter. The stub adapter is the :class:`LiteLLMAdapter` the
    ``ClaudeCodeRoute`` branch never touches — rerouting the tier onto
    a ``LiteLLMRoute`` is how the hermetic test avoids the Claude Code
    subprocess path entirely.
    """
    route = LiteLLMRoute(model="stub/gemini-flash-equivalent")
    return {
        "planner-explorer": TierConfig(
            name="planner-explorer",
            route=route,
            max_concurrency=2,
            per_call_timeout_s=60,
        ),
        "planner-synth": TierConfig(
            name="planner-synth",
            route=route,
            max_concurrency=2,
            per_call_timeout_s=90,
        ),
        "slice-worker": TierConfig(
            name="slice-worker",
            route=route,
            max_concurrency=4,
            per_call_timeout_s=60,
        ),
    }


def _seed_stub_for_three_slices() -> None:
    """Populate ``_StubLiteLLMAdapter`` with a 3-slice approve-path script."""
    _StubLiteLLMAdapter.script = [
        (_valid_explorer_json(), 0.0010),
        (_three_step_plan_json(), 0.0020),
    ]
    _StubLiteLLMAdapter.worker_script = {
        "1": [(_valid_slice_result_json("1"), 0.0030)],
        "2": [(_valid_slice_result_json("2"), 0.0031)],
        "3": [(_valid_slice_result_json("3"), 0.0032)],
    }


@pytest.fixture(autouse=True)
def _pin_tier_registries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin both workflows' tier registries onto the stub-routed tiers.

    ``_dispatch`` resolves the registry per run by calling
    ``<workflow>_tier_registry()`` at the module level. Monkeypatching
    the ``planner`` module's helper too keeps the sub-graph's calls
    inside the stub boundary — otherwise the planner sub-graph would
    try to route ``planner-synth`` through ``ClaudeCodeSubprocess``.
    """
    monkeypatch.setattr(
        slice_refactor_module,
        "slice_refactor_tier_registry",
        _tier_registry_override,
    )
    monkeypatch.setattr(
        planner_module, "planner_tier_registry", _tier_registry_override
    )


# ---------------------------------------------------------------------------
# AC: approve-at-both-gates path → 3 artefacts + runs.status == completed
# ---------------------------------------------------------------------------


async def test_slice_refactor_e2e_approve_path_writes_three_artefacts(
    tmp_path: Path,
) -> None:
    """AC-1: full pipeline runs; both gates fire in order; approve path
    writes three ``slice_result:<id>`` artefacts, flips ``runs.status``
    to ``completed``, and surfaces ``total_cost_usd >= 0``.
    """
    _seed_stub_for_three_slices()
    run_id = "run-e2e-approve"

    first = await run_workflow(
        workflow="slice_refactor",
        inputs={
            "goal": "Refactor monolith into three slices.",
            "context": "Three independent modules.",
            "max_steps": 5,
        },
        run_id=run_id,
    )
    # Planner's plan_review gate — inherited from the sub-graph. The
    # dispatch result does not expose the gate id, but the pause shape
    # is unambiguous (status=pending + awaiting=gate).
    assert first["status"] == "pending", first
    assert first["awaiting"] == "gate", first
    assert first["run_id"] == run_id

    second = await resume_run(run_id=run_id, gate_response="approved")
    # slice_refactor_review strict-review gate — the fan-out completed
    # and the aggregator staged the SliceAggregate payload.
    assert second["status"] == "pending", second
    # M19 T03 (ADR-0008): at this re-gate pause the FINAL_STATE_KEY
    # "applied_artifact_count" is still None (the artifact node hasn't
    # run yet — it only runs after slice_refactor_review is approved).
    # Both artifact and plan are None; the gate_context carries the
    # operator-review payload instead.
    assert second["artifact"] is None
    assert second["plan"] is None  # deprecated alias; same value
    assert second["gate_context"] is not None
    assert second["gate_context"]["gate_id"] == "slice_refactor_review"

    third = await resume_run(run_id=run_id, gate_response="approved")
    assert third["status"] == "completed", third
    assert third["error"] is None
    assert third["total_cost_usd"] is not None
    assert third["total_cost_usd"] >= 0.0

    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    row = await storage.get_run(run_id)
    assert row is not None
    assert row["status"] == "completed"
    assert row["finished_at"] is not None

    for slice_id in ("1", "2", "3"):
        artefact = await storage.read_artifact(
            run_id, f"{SLICE_RESULT_ARTIFACT_KIND}:{slice_id}"
        )
        assert artefact is not None, (
            f"expected slice_result:{slice_id} artefact"
        )
        parsed = SliceResult.model_validate_json(artefact["payload_json"])
        assert parsed.slice_id == slice_id


# ---------------------------------------------------------------------------
# AC: reject-at-outer-gate path → 0 artefacts + runs.status == gate_rejected
# ---------------------------------------------------------------------------


async def test_slice_refactor_e2e_reject_outer_gate_writes_no_artefacts(
    tmp_path: Path,
) -> None:
    """AC-1 reject variant: approve the planner gate, reject the
    strict-review gate → 0 artefacts, ``runs.status == "gate_rejected"``,
    ``finished_at`` stamped.
    """
    _seed_stub_for_three_slices()
    run_id = "run-e2e-reject"

    first = await run_workflow(
        workflow="slice_refactor",
        inputs={
            "goal": "Refactor monolith into three slices.",
            "context": "Three independent modules.",
            "max_steps": 5,
        },
        run_id=run_id,
    )
    assert first["status"] == "pending", first

    second = await resume_run(run_id=run_id, gate_response="approved")
    assert second["status"] == "pending", second

    third = await resume_run(run_id=run_id, gate_response="rejected")
    assert third["status"] == "gate_rejected", third
    # M19 T03 (ADR-0008): gate_rejected surfaces final.get(FINAL_STATE_KEY).
    # For slice_refactor, FINAL_STATE_KEY = "applied_artifact_count" which
    # is None at rejection time (the artifact node never ran). Both artifact
    # and plan are None on the gate_rejected path for slice_refactor.
    assert third["artifact"] is None
    assert third["plan"] is None  # deprecated alias; same value
    assert third["error"] is None

    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    row = await storage.get_run(run_id)
    assert row is not None
    assert row["status"] == "gate_rejected"
    assert row["finished_at"] is not None

    for slice_id in ("1", "2", "3"):
        artefact = await storage.read_artifact(
            run_id, f"{SLICE_RESULT_ARTIFACT_KIND}:{slice_id}"
        )
        assert artefact is None, (
            f"reject path must not write slice_result:{slice_id}"
        )


# ---------------------------------------------------------------------------
# AC: KDR-003 regression — no anthropic import / ANTHROPIC_API_KEY read
# ---------------------------------------------------------------------------


def test_kdr_003_no_anthropic_in_production_tree() -> None:
    """KDR-003 regression: ``import anthropic`` / ``from anthropic`` /
    ``ANTHROPIC_API_KEY`` must not appear in any production source file.

    The regex intentionally narrows to real-use signals so docstrings
    that document the ban ("never imports the anthropic SDK") do not
    trigger false positives.
    """
    hits: list[tuple[str, int, str]] = []
    for py_file in _PRODUCTION_ROOT.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for match in _KDR_003_REGRESSION.finditer(text):
            lineno = text.count("\n", 0, match.start()) + 1
            line = text.splitlines()[lineno - 1]
            hits.append((str(py_file), lineno, line))
    assert not hits, (
        "KDR-003 regression: anthropic surface leaked into production "
        f"tree. Hits: {hits!r}"
    )
