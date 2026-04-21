"""Replay runner for eval suites (M7 Task 03).

Loads an :class:`ai_workflows.evals.EvalSuite` and replays every case
against the workflow's current graph, one case at a time, reporting
pass/fail per case in an :class:`EvalReport`. The runner exists to
catch three orthogonal drift classes that determinism-only tests miss:

* **Code-side drift (deterministic mode)** — prompt-template drift,
  validator-schema drift, and tier-wiring drift. The stub adapter
  returns the pinned :attr:`EvalCase.expected_output` verbatim, so
  the only way a deterministic replay fails is if the current
  prompt_fn / schema / wiring rejects what it previously accepted.
* **Model-side drift (live mode)** — the same expected output no
  longer matches fresh provider output under the case's
  :class:`EvalTolerance`. Gated at construction time by
  ``AIW_EVAL_LIVE=1`` + ``AIW_E2E=1`` (mirror of the existing
  ``AIW_E2E`` pattern the live CI path already uses).
* **Suite-completeness drift (both modes)** — a case references a
  node that no longer exists in the workflow, or the stub is asked
  to serve a node whose case is missing. :class:`_stub_adapter.StubAdapterMissingCaseError`
  surfaces the latter; the runner surfaces the former.

Single-node replay
------------------
Each case runs through a minimal replay graph ``START → <node> →
<node>_validator → END``, not the full workflow. The target node's
:class:`~langgraph.graph.state.StateNodeSpec.runnable` is pulled
out of the workflow's own :class:`~langgraph.graph.StateGraph` —
the runner never rebuilds the TieredNode / ValidatorNode from
scratch. This keeps prompt_fn + output_schema + validator parsing
wired exactly as in production (KDR-004: the paired validator
runs in the same graph position as in the live run) while
side-stepping fan-out, human-gate, and artifact persistence.

When an LLM node is wired inside a compiled sub-graph (e.g.
:mod:`ai_workflows.workflows.slice_refactor`'s ``slice_branch``
wraps ``slice_worker`` + ``slice_worker_validator`` behind a
:class:`~langgraph.types.Send` fan-out), the target and its paired
validator resolve through :func:`_resolve_node_scope` — the helper
walks each top-level runnable's ``builder`` attribute (present on
:class:`CompiledStateGraph`) to find the enclosing
:class:`StateGraph`, then uses *that* graph's ``state_schema`` for
the replay. This was the M7-T05-ISS gap in the original T03 runner:
flat-node lookup succeeded for planner (LLM nodes at the top level)
but failed for slice_refactor (LLM nodes under ``slice_branch``).

Relationship to sibling modules
-------------------------------
* :mod:`ai_workflows.evals._stub_adapter` — the deterministic
  adapter the runner monkey-patches into
  :mod:`ai_workflows.graph.tiered_node` for each case replay.
* :mod:`ai_workflows.evals._compare` — the tolerance-aware
  comparison layer. Every ``passed=True``/``False`` verdict on an
  :class:`EvalResult` comes from :func:`_compare.compare`.
* :mod:`ai_workflows.evals.schemas` — provides :class:`EvalSuite`
  / :class:`EvalCase` / :class:`EvalTolerance` the runner
  consumes.
* :mod:`ai_workflows.graph.tiered_node` — the monkey-patch target
  for deterministic mode (``tiered_node_module.LiteLLMAdapter``).
* :mod:`ai_workflows.workflows` — registry the runner resolves
  ``case.workflow_id`` through to locate the workflow's builder.

Scope discipline
----------------
* No CLI surface here — T04 wires ``aiw eval run`` over this
  class.
* No CI integration — T05 picks it up.
* No LLM-as-judge — explicit non-goal per the milestone README.
* No parallel replay — class-level stub state makes the
  sequential loop the correct shape.
"""

from __future__ import annotations

import asyncio
import importlib
import os
import time
from dataclasses import dataclass
from typing import Any, Literal, get_type_hints
from unittest.mock import patch

from pydantic import BaseModel

from ai_workflows import workflows
from ai_workflows.evals._compare import compare
from ai_workflows.evals._stub_adapter import (
    StubAdapterMissingCaseError,
    StubLLMAdapter,
)
from ai_workflows.evals.schemas import EvalCase, EvalSuite, EvalTolerance
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.graph.cost_callback import CostTrackingCallback
from ai_workflows.primitives.cost import CostTracker
from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig

try:  # pragma: no cover — import-error branch only on a broken install
    from langgraph.graph import END, START, StateGraph
except ImportError as _lg_exc:  # pragma: no cover
    raise RuntimeError(
        "langgraph must be installed for eval replay; "
        f"underlying import error: {_lg_exc}"
    ) from _lg_exc

__all__ = ["EvalResult", "EvalReport", "EvalRunner"]

Mode = Literal["deterministic", "live"]


@dataclass(frozen=True)
class EvalResult:
    """One case's replay outcome.

    ``diff`` is a human-readable explanation of the mismatch on a
    failing compare (unified diff for ``strict_json``, per-field
    detail for ``substring`` / ``regex``); it is empty on success.
    ``error`` is set only when the replay raised before reaching
    the compare step (prompt_fn raised, validator raised, etc.) —
    on an error path ``passed`` is always ``False`` and ``diff`` is
    empty.
    """

    case_id: str
    node_name: str
    mode: Mode
    passed: bool
    diff: str
    duration_s: float
    error: str | None = None


@dataclass(frozen=True)
class EvalReport:
    """Aggregate of every per-case :class:`EvalResult` in one run."""

    suite_workflow_id: str
    mode: Mode
    results: tuple[EvalResult, ...]

    @property
    def pass_count(self) -> int:
        """Number of results with ``passed=True``."""

        return sum(1 for r in self.results if r.passed)

    @property
    def fail_count(self) -> int:
        """Number of results with ``passed=False`` (including errors)."""

        return sum(1 for r in self.results if not r.passed)

    def summary_lines(self) -> list[str]:
        """Render a human-readable summary for CLI / CI output."""

        header = (
            f"Eval replay [{self.mode}] for {self.suite_workflow_id!r}: "
            f"{self.pass_count} passed, {self.fail_count} failed"
        )
        lines = [header]
        for result in self.results:
            tag = "PASS" if result.passed else "FAIL"
            detail = ""
            if result.error:
                detail = f" — error: {result.error}"
            elif result.diff:
                first_line = result.diff.splitlines()[0] if result.diff else ""
                detail = f" — {first_line}"
            lines.append(
                f"  [{tag}] {result.case_id} ({result.node_name}) "
                f"{result.duration_s:.3f}s{detail}"
            )
        return lines


class EvalRunner:
    """Replay an :class:`EvalSuite` against the current graph.

    Construct with ``mode`` set to ``"deterministic"`` (default) or
    ``"live"``. Deterministic mode monkey-patches
    ``tiered_node_module.LiteLLMAdapter`` with :class:`StubLLMAdapter`
    so every provider call returns the case's
    :attr:`EvalCase.expected_output` verbatim. Live mode is gated by
    ``AIW_EVAL_LIVE=1`` **and** ``AIW_E2E=1`` at construction time —
    both must be set, otherwise ``__init__`` raises
    :class:`RuntimeError` before any replay happens.

    ``tolerance_override`` lets the caller force one tolerance across
    every case (e.g. for a full-suite dry run where every string
    field should be substring-compared). When ``None`` each case's
    :attr:`EvalCase.tolerance` is honoured per-case.
    """

    def __init__(
        self,
        *,
        mode: Mode = "deterministic",
        tolerance_override: EvalTolerance | None = None,
    ) -> None:
        if mode == "live":
            if os.getenv("AIW_EVAL_LIVE") != "1":
                raise RuntimeError(
                    "EvalRunner(mode='live') requires AIW_EVAL_LIVE=1 — "
                    "live replay fires real provider calls."
                )
            if os.getenv("AIW_E2E") != "1":
                raise RuntimeError(
                    "EvalRunner(mode='live') requires AIW_E2E=1 — live "
                    "replay shares the e2e gate since it incurs provider cost."
                )
        self._mode: Mode = mode
        self._tolerance_override = tolerance_override

    async def run(self, suite: EvalSuite) -> EvalReport:
        """Replay every case in ``suite`` and return the aggregate report.

        Sequential (no parallelism) so the class-level stub state in
        :class:`StubLLMAdapter` is unambiguous: exactly one case is
        armed at any moment, and one ``ainvoke`` fires per arm.
        """

        results: list[EvalResult] = []
        for case in suite.cases:
            result = await self._run_case(case)
            results.append(result)
        return EvalReport(
            suite_workflow_id=suite.workflow_id,
            mode=self._mode,
            results=tuple(results),
        )

    async def _run_case(self, case: EvalCase) -> EvalResult:
        start = time.monotonic()
        try:
            raw_output = await self._invoke_replay(case)
        except StubAdapterMissingCaseError as exc:
            return EvalResult(
                case_id=case.case_id,
                node_name=case.node_name,
                mode=self._mode,
                passed=False,
                diff="",
                duration_s=time.monotonic() - start,
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001 — surface-boundary catch
            return EvalResult(
                case_id=case.case_id,
                node_name=case.node_name,
                mode=self._mode,
                passed=False,
                diff="",
                duration_s=time.monotonic() - start,
                error=f"{type(exc).__name__}: {exc}",
            )

        if raw_output is None:
            return EvalResult(
                case_id=case.case_id,
                node_name=case.node_name,
                mode=self._mode,
                passed=False,
                diff="",
                duration_s=time.monotonic() - start,
                error="replay produced no raw output for node",
            )

        tolerance = self._tolerance_override or case.tolerance
        passed, diff = compare(
            case.expected_output,
            raw_output,
            tolerance,
            case.output_schema_fqn,
        )
        return EvalResult(
            case_id=case.case_id,
            node_name=case.node_name,
            mode=self._mode,
            passed=passed,
            diff=diff,
            duration_s=time.monotonic() - start,
            error=None,
        )

    async def _invoke_replay(self, case: EvalCase) -> str | None:
        """Build + invoke the single-node replay graph for one case.

        Returns the node's raw text output (state key
        ``f"{node_name}_output"``) on success. Raises (caller
        translates to an :class:`EvalResult` with ``error=...``) on:

        * The workflow not being registered.
        * The node name not existing in the workflow's graph.
        * Any exception raised during ``ainvoke`` (prompt_fn,
          adapter, validator, etc.).

        When ``wrap_with_error_handler`` catches a bucket exception
        the runner inspects ``state["last_exception"]`` and re-raises
        its text as an :class:`EvalCaseFailure` so the caller stamps
        the diagnostic on the result.
        """

        builder = self._resolve_builder(case.workflow_id)
        original_graph = builder()
        node_name = case.node_name
        validator_name = f"{node_name}_validator"

        resolution = _resolve_node_scope(
            original_graph, node_name, validator_name
        )
        if resolution is None:
            if not _node_exists_anywhere(original_graph, node_name):
                raise _EvalCaseError(
                    f"case references node {node_name!r} which is not "
                    f"registered in workflow {case.workflow_id!r}"
                )
            raise _EvalCaseError(
                f"case references node {node_name!r} but no paired "
                f"validator {validator_name!r} found in workflow "
                f"{case.workflow_id!r} (KDR-004)"
            )

        state_schema, target_spec, validator_spec = resolution

        replay_g: StateGraph = StateGraph(state_schema)
        replay_g.add_node(node_name, target_spec.runnable)
        replay_g.add_node(validator_name, validator_spec.runnable)
        replay_g.add_edge(START, node_name)
        replay_g.add_edge(node_name, validator_name)
        replay_g.add_edge(validator_name, END)

        initial_state = self._hydrate_state(state_schema, case.inputs)
        cfg = self._build_config(
            case=case,
            workflow_id=case.workflow_id,
        )

        async with _patched_adapters(self._mode, case.expected_output):
            compiled = replay_g.compile()
            final = await compiled.ainvoke(initial_state, cfg)

        last = final.get("last_exception")
        if last is not None:
            raise _EvalCaseError(str(last))
        return final.get(f"{node_name}_output")

    def _resolve_builder(self, workflow_id: str) -> Any:
        """Import + register the workflow module, return its builder."""

        importlib.import_module(f"ai_workflows.workflows.{workflow_id}")
        return workflows.get(workflow_id)

    def _build_config(
        self,
        *,
        case: EvalCase,
        workflow_id: str,
    ) -> dict[str, Any]:
        """Assemble the LangGraph config for a single-case replay.

        For deterministic replay the tier registry is rewritten so
        every tier routes through :class:`LiteLLMRoute` — the stub
        adapter shape-matches :class:`LiteLLMAdapter`, and using a
        single route kind across tiers keeps the monkey-patch
        surface a single class instead of one per route shape.
        For live mode the workflow's own tier registry is used
        unchanged so real provider calls fire under their real
        routes.
        """

        if self._mode == "deterministic":
            tier_registry = _stub_tier_registry(workflow_id)
        else:
            module = importlib.import_module(
                f"ai_workflows.workflows.{workflow_id}"
            )
            helper = getattr(module, f"{workflow_id}_tier_registry", None)
            tier_registry = helper() if helper is not None else {}

        tracker = CostTracker()
        cost_callback = CostTrackingCallback(
            cost_tracker=tracker, budget_cap_usd=None
        )
        run_id = f"eval-replay-{case.case_id}"
        configurable: dict[str, Any] = {
            "thread_id": run_id,
            "run_id": run_id,
            "tier_registry": tier_registry,
            "cost_callback": cost_callback,
            "workflow": workflow_id,
            "semaphores": {
                name: asyncio.Semaphore(config.max_concurrency)
                for name, config in tier_registry.items()
            },
        }
        return {"configurable": configurable}

    def _hydrate_state(
        self,
        state_schema: type,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Rebuild any pydantic-model state values from their JSON dumps.

        :class:`CaptureCallback` normalises pydantic leaves via
        ``model_dump(mode="json")`` before writing a fixture (see
        :mod:`ai_workflows.evals.capture_callback`). Replay needs
        the live model instances back — the workflow's prompt_fn
        calls ``state["input"].goal`` / similar. :func:`typing.get_type_hints`
        on the workflow's ``TypedDict`` state schema tells us which
        keys were originally pydantic models; everything else passes
        through unchanged.
        """

        hints = get_type_hints(state_schema)
        hydrated: dict[str, Any] = {}
        for key, value in inputs.items():
            expected_type = hints.get(key)
            if (
                expected_type is not None
                and isinstance(expected_type, type)
                and issubclass(expected_type, BaseModel)
                and isinstance(value, dict)
            ):
                hydrated[key] = expected_type(**value)
            else:
                hydrated[key] = value
        return hydrated


def _resolve_node_scope(
    graph: StateGraph,
    node_name: str,
    validator_name: str,
) -> tuple[type, Any, Any] | None:
    """Locate the ``(state_schema, target_spec, validator_spec)`` triple.

    Top-level nodes resolve directly off ``graph.nodes``. When a
    workflow wires an LLM node inside a compiled sub-graph (e.g.
    :mod:`ai_workflows.workflows.slice_refactor`'s ``slice_branch``
    wraps ``slice_worker`` + ``slice_worker_validator``), the target
    node is not visible at the parent ``StateGraph`` level — the
    compiled sub-graph is. :class:`CompiledStateGraph` exposes its
    source ``StateGraph`` via the ``builder`` attribute, so we can
    walk its ``.nodes`` and ``.state_schema`` to resolve both the
    target and its paired validator in the same scope.

    Returns ``None`` when the pair cannot be resolved together
    (either missing entirely or split across scopes — a wiring
    violation that the caller surfaces as an :class:`_EvalCaseError`).
    """

    if node_name in graph.nodes and validator_name in graph.nodes:
        return (
            graph.state_schema,
            graph.nodes[node_name],
            graph.nodes[validator_name],
        )
    for spec in graph.nodes.values():
        runnable = getattr(spec, "runnable", None)
        sub_builder = getattr(runnable, "builder", None)
        if sub_builder is None:
            continue
        sub_nodes = getattr(sub_builder, "nodes", None)
        sub_schema = getattr(sub_builder, "state_schema", None)
        if not sub_nodes or sub_schema is None:
            continue
        if node_name in sub_nodes and validator_name in sub_nodes:
            return (
                sub_schema,
                sub_nodes[node_name],
                sub_nodes[validator_name],
            )
    return None


def _node_exists_anywhere(graph: StateGraph, node_name: str) -> bool:
    """Return ``True`` if ``node_name`` is declared anywhere reachable.

    Checks the top-level graph plus every compiled sub-graph exposed
    via ``builder`` on a node's runnable. Used only to produce a
    precise ``_EvalCaseError`` message distinguishing "node missing"
    from "validator missing".
    """

    if node_name in graph.nodes:
        return True
    for spec in graph.nodes.values():
        runnable = getattr(spec, "runnable", None)
        sub_builder = getattr(runnable, "builder", None)
        if sub_builder is None:
            continue
        sub_nodes = getattr(sub_builder, "nodes", None)
        if sub_nodes and node_name in sub_nodes:
            return True
    return False


def _stub_tier_registry(workflow_id: str) -> dict[str, TierConfig]:
    """Return a stub-friendly tier registry for deterministic replay.

    Every tier declared by the workflow is rewritten to use a
    :class:`LiteLLMRoute` so :class:`StubLLMAdapter` (which shape-
    matches :class:`LiteLLMAdapter`) is the single adapter the
    graph reaches. Tiers on :class:`ClaudeCodeRoute` in production
    get the same rewrite — the replay is deterministic, no
    subprocess fires.
    """

    module = importlib.import_module(f"ai_workflows.workflows.{workflow_id}")
    helper = getattr(module, f"{workflow_id}_tier_registry", None)
    if helper is None:
        return {}
    registry = helper()
    return {
        name: TierConfig(
            name=cfg.name,
            route=LiteLLMRoute(model=f"stub/{cfg.name}"),
            max_concurrency=cfg.max_concurrency,
            per_call_timeout_s=cfg.per_call_timeout_s,
        )
        for name, cfg in registry.items()
    }


class _EvalCaseError(Exception):
    """Internal sentinel — turned into :attr:`EvalResult.error` by the runner."""


class _patched_adapters:
    """Context manager that swaps in the deterministic stubs for the replay.

    Deterministic mode replaces
    ``tiered_node_module.LiteLLMAdapter`` with :class:`StubLLMAdapter`
    and arms the stub with the current case's expected output.
    ClaudeCode is also rerouted by the tier-registry rewrite, so the
    patch site is a single attribute. Live mode is a no-op context.
    """

    def __init__(self, mode: Mode, expected_output: str) -> None:
        self._mode = mode
        self._expected_output = expected_output
        self._patcher: Any = None

    async def __aenter__(self) -> _patched_adapters:
        if self._mode == "deterministic":
            StubLLMAdapter.arm(expected_output=self._expected_output)
            self._patcher = patch.object(
                tiered_node_module, "LiteLLMAdapter", StubLLMAdapter
            )
            self._patcher.start()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._mode == "deterministic":
            if self._patcher is not None:
                self._patcher.stop()
                self._patcher = None
            StubLLMAdapter.disarm()
