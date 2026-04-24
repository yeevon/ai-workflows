"""Shared workflow-dispatch helper for the two surfaces.

M4 Task 02 extracts the reusable core of :mod:`ai_workflows.cli`'s
``_run_async`` into this module so the ``aiw run`` CLI command and the
``run_workflow`` MCP tool (:mod:`ai_workflows.mcp.server`) go through
one path. Both surfaces call :func:`run_workflow` and receive a plain
dict that matches the shape of
:class:`ai_workflows.mcp.schemas.RunWorkflowOutput` / the CLI's existing
stdout contract:

``{run_id, status, awaiting?, plan?, total_cost_usd?, error?}``

Surfaces reformat / re-wrap this dict into whatever their transport
wants (``typer.echo`` lines for the CLI, a :class:`RunWorkflowOutput`
pydantic model for the MCP tool).

``ainvoke`` is always called with ``durability="sync"`` so the
last-completed-step checkpoint hits SQLite before a
:class:`asyncio.CancelledError` can unwind the run (the M6 T02
in-flight ``cancel_run`` → immediate resume path depends on this
guarantee). The flag is a no-op for workflows that never get
cancelled mid-graph (e.g. ``planner``, which spends virtually all
of its wall time paused at a ``HumanGate``) — sync durability only
changes behaviour when the task is actively computing across a
checkpoint boundary. The T02 task spec placed ``durability`` on
:meth:`StateGraph.compile`, but LangGraph exposes it on
:meth:`CompiledStateGraph.ainvoke` instead (verified via
``inspect.signature``); threading at the invoke boundary is the
equivalent wiring.

Placed in the ``workflows`` layer (not under ``mcp/``) because the
helper is fundamentally workflow-running orchestration — both surfaces
sit above it and neither owns it. Import-linter allows this: surfaces
may import :mod:`ai_workflows.workflows`, and workflows may not import
surfaces. :func:`resume_run` lands here in M4 T03; M5 will extend
:func:`run_workflow` with tier-override plumbing (see
[architecture.md §4.4](../../design_docs/architecture.md)).

Relationship to other modules
-----------------------------
* :mod:`ai_workflows.cli` — imports :func:`run_workflow` to implement
  ``aiw run`` and reuses :func:`_generate_ulid` for its auto-id flow.
* :mod:`ai_workflows.mcp.server` — imports :func:`run_workflow` for the
  ``run_workflow`` MCP tool body.
* :mod:`ai_workflows.workflows` — registry the helper resolves
  ``<workflow>`` through; workflows self-register at import time.
* :mod:`ai_workflows.graph.checkpointer` /
  :mod:`ai_workflows.graph.cost_callback` — LangGraph saver and cost
  callback the helper compiles / wires per run (KDR-009).
* :mod:`ai_workflows.primitives.storage` /
  :mod:`ai_workflows.primitives.cost` — run registry and per-run cost
  tracker the helper drives.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import os
import secrets
import sys
import time
from datetime import UTC, datetime
from typing import Any

import structlog
from langgraph.types import Command

from ai_workflows import workflows
from ai_workflows.evals import CaptureCallback
from ai_workflows.graph.checkpointer import build_async_checkpointer
from ai_workflows.graph.cost_callback import CostTrackingCallback
from ai_workflows.primitives.circuit_breaker import CircuitBreaker
from ai_workflows.primitives.cost import CostTracker, TokenUsage
from ai_workflows.primitives.retry import NonRetryable
from ai_workflows.primitives.storage import SQLiteStorage, default_storage_path
from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig

__all__ = [
    "ResumePreconditionError",
    "UnknownTierError",
    "UnknownWorkflowError",
    "resume_run",
    "run_workflow",
]

_LOG = structlog.get_logger(__name__)


# Crockford base32 (excludes I, L, O, U so run ids can be read aloud). Kept as
# module-private; :mod:`ai_workflows.cli` re-exports for its ULID-shape test.
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class UnknownWorkflowError(ValueError):
    """Raised when the named workflow is not registered.

    The CLI converts this to ``typer.Exit(code=2)`` with a "unknown
    workflow … registered: …" message; the MCP tool re-raises so FastMCP
    surfaces a JSON-RPC error (not an uncaught Python exception — per
    M4 T02 AC).
    """

    def __init__(self, workflow: str, registered: list[str]) -> None:
        self.workflow = workflow
        self.registered = registered
        super().__init__(f"unknown workflow {workflow!r}; registered: {registered}")


class UnknownTierError(ValueError):
    """Raised when a ``tier_overrides`` entry names a tier not in the registry.

    M5 Task 04 / 05 introduce ``--tier-override <logical>=<replacement>``
    on the CLI and ``tier_overrides: dict[str, str]`` on the MCP
    ``run_workflow`` tool so a caller can repoint a workflow-declared
    tier at another tier already in the registry (architecture.md §4.4 /
    §8.4). Both names are validated against
    ``<workflow>_tier_registry()`` at dispatch time. The CLI converts
    this to ``typer.Exit(code=2)``; the MCP surface raises a matching
    ``ToolError``. ``kind`` is either ``"logical"`` (left-hand side of
    the ``=``, the tier being overridden) or ``"replacement"``
    (right-hand side, the tier whose config the logical name now points
    at) so error messages name the offending side.
    """

    def __init__(self, tier_name: str, kind: str, registered: list[str]) -> None:
        self.tier_name = tier_name
        self.kind = kind
        self.registered = sorted(registered)
        super().__init__(
            f"unknown {kind} tier {tier_name!r}; registered: {self.registered}"
        )


def _apply_tier_overrides(
    registry: dict[str, Any],
    overrides: dict[str, str] | None,
) -> dict[str, Any]:
    """Return a new registry with each ``logical`` repointed at ``replacement``'s config.

    Pure function — does not mutate ``registry``. Both sides of every
    override are validated against ``registry``; the first unknown name
    raises :class:`UnknownTierError` with the offending name and which
    side it came from. An empty or ``None`` ``overrides`` returns a
    shallow copy of ``registry`` (the idempotency guard T04's tests
    pin: calling ``_apply_tier_overrides`` does not mutate the input
    across runs).
    """
    new_registry = dict(registry)
    if not overrides:
        return new_registry
    for logical, replacement in overrides.items():
        if logical not in registry:
            raise UnknownTierError(logical, "logical", list(registry.keys()))
        if replacement not in registry:
            raise UnknownTierError(
                replacement, "replacement", list(registry.keys())
            )
        new_registry[logical] = registry[replacement]
    return new_registry


class ResumePreconditionError(ValueError):
    """Raised when a run cannot be resumed (missing / cancelled / terminal).

    Two surfaces hit this differently (M4 T03 AC-4): the CLI turns it
    into ``typer.Exit(code=2)`` with the precondition message, and the
    MCP tool re-raises as :class:`fastmcp.exceptions.ToolError` so
    FastMCP emits a JSON-RPC error. Subclassing :class:`ValueError` keeps
    the spec's literal ``raise ValueError(...)`` contract (§Cancelled-run
    precondition block) while letting each surface catch this class
    specifically.
    """


def _generate_ulid() -> str:
    """Return a 26-char ULID-shape identifier (48-bit ts + 80-bit random).

    Not the ULID spec to the letter — the randomness source is
    :func:`secrets.token_bytes` rather than monotonically-stepping the
    last-generated id — but the shape (26 chars, Crockford base32,
    sortable-ish by leading timestamp) matches and keeps the project
    from taking on a third-party dependency for a one-call concern.
    """
    timestamp_ms = int(time.time() * 1000)
    ts_chars: list[str] = []
    for _ in range(10):
        ts_chars.append(_CROCKFORD[timestamp_ms & 0x1F])
        timestamp_ms >>= 5
    ts_part = "".join(reversed(ts_chars))

    random_int = int.from_bytes(secrets.token_bytes(10), "big")
    rand_chars: list[str] = []
    for _ in range(16):
        rand_chars.append(_CROCKFORD[random_int & 0x1F])
        random_int >>= 5
    rand_part = "".join(reversed(rand_chars))

    return ts_part + rand_part


def _import_workflow_module(workflow: str) -> Any:
    """Return the module object backing a registered workflow.

    M16 Task 01 extension: external workflows pre-imported by
    :func:`ai_workflows.workflows.load_extra_workflow_modules` at
    startup already populated ``_REGISTRY`` from their own dotted
    paths (e.g. ``cs300.workflows.question_gen``). For those,
    ``ai_workflows.workflows.<workflow>`` would ``ModuleNotFoundError``;
    instead return the registered builder's source module via
    ``sys.modules[builder.__module__]`` so
    :func:`_resolve_tier_registry` / :func:`_build_initial_state` /
    :func:`_resolve_final_state_key` find the workflow's helpers on it.

    In-package workflows preserve their lazy-import fallback: first
    dispatch for ``planner`` imports ``ai_workflows.workflows.planner``,
    which triggers the module's top-level
    ``register("planner", build_planner)``. The eager-planner-import
    on the error branch is retained so a typo on first invocation
    still yields an actionable registered-workflows list instead of
    an empty ``[]``.
    """
    existing = workflows._REGISTRY.get(workflow)
    if existing is not None:
        module_name = getattr(existing, "__module__", None)
        if module_name:
            module = sys.modules.get(module_name)
            if module is not None:
                return module
            # Fallthrough: the registered builder's module is somehow
            # no longer in sys.modules (explicit del, a reload gone
            # wrong). Re-import via its dotted path.
            return importlib.import_module(module_name)

    module_path = f"ai_workflows.workflows.{workflow}"
    try:
        return importlib.import_module(module_path)
    except ModuleNotFoundError:
        with contextlib.suppress(ModuleNotFoundError):
            importlib.import_module("ai_workflows.workflows.planner")
        raise UnknownWorkflowError(workflow, workflows.list_workflows()) from None


def _resolve_tier_registry(workflow: str, module: Any) -> dict:
    """Return the workflow's tier-registry mapping.

    Each workflow module exports a ``<workflow>_tier_registry()``
    helper (pattern from M3 T03 / T04). Missing helpers fall back to
    ``{}`` so a workflow that doesn't make LLM calls still runs.
    """
    helper = getattr(module, f"{workflow}_tier_registry", None)
    if helper is None:
        return {}
    return helper()


def _resolve_terminal_gate_id(module: Any) -> str | None:
    """Return the ``TERMINAL_GATE_ID`` constant a workflow module exposes.

    The constant names the gate id the workflow pauses at for its
    terminal human approval (``"plan_review"`` for the planner,
    ``"slice_refactor_review"`` for slice_refactor). Dispatch reads the
    resumed response from ``state[f"gate_{TERMINAL_GATE_ID}_response"]``
    when deciding approve/reject at resume time.

    Returns ``None`` for workflows that don't publish the constant
    (future workflows with no strict-review gate, or legacy workflows
    written before the M6 T01-CARRY-DISPATCH-GATE convention). Dispatch
    then falls back to the ``gate_response`` parameter the caller passed
    — correct as long as the workflow has at most one terminal gate.
    """
    return getattr(module, "TERMINAL_GATE_ID", None)


def _resolve_final_state_key(module: Any) -> str:
    """Return the ``FINAL_STATE_KEY`` constant a workflow module exposes (T06).

    Names the state key dispatch reads to decide whether a graph reached
    its terminal artefact-persistence step. For the planner that key is
    ``"plan"`` (the approved :class:`PlannerPlan` the artifact node
    writes); for slice_refactor it is ``"applied_artifact_count"`` (the
    count :func:`slice_refactor._apply` returns). Missing constants fall
    back to ``"plan"`` so legacy workflows written before the M6
    T01-CARRY-DISPATCH-COMPLETE convention still complete. Dispatch
    checks ``state[FINAL_STATE_KEY] is not None`` — a ``0`` integer
    (zero-success aggregate that the reviewer approved anyway for its
    audit trail) still satisfies the check.
    """
    return getattr(module, "FINAL_STATE_KEY", "plan")


def _build_initial_state(
    module: Any,
    run_id: str,
    inputs: dict[str, Any],
) -> dict[str, Any]:
    """Construct the workflow's initial state dict.

    Resolution order (M6 T01):

    1. If the workflow module exposes a callable ``initial_state(run_id,
       inputs) -> dict``, call it. This is the **convention hook** that
       lets workflows whose initial state is not a simple ``PlannerInput``
       participate in shared dispatch without dispatch knowing their
       Input schema name.
    2. Otherwise fall back to the legacy path: look up ``PlannerInput``
       by name and instantiate from ``inputs`` — unchanged for the
       planner workflow so M3's surface behaviour is identical.

    The hook form lets slice_refactor (M6 T01) supply an initial state
    whose ``input`` channel is a :class:`PlannerInput` constructed from a
    caller-supplied :class:`SliceRefactorInput`, without dispatch
    hardcoding either class name. Future workflows follow the same
    pattern.
    """
    hook = getattr(module, "initial_state", None)
    if callable(hook):
        return hook(run_id, inputs)
    input_cls = getattr(module, "PlannerInput", None)
    if input_cls is None:
        raise ValueError(f"workflow {module.__name__!r} exposes no Input schema")
    return {
        "run_id": run_id,
        "input": input_cls(**inputs),
    }


def _build_semaphores(
    tier_registry: dict[str, TierConfig],
) -> dict[str, asyncio.Semaphore]:
    """Build one :class:`asyncio.Semaphore` per tier from the run's registry (M6 T07).

    Each tier's ``TierConfig.max_concurrency`` bounds the number of
    in-flight provider calls dispatched through :func:`tiered_node`'s
    ``configurable["semaphores"]`` lookup. The semaphore is keyed by
    tier name so every :class:`TieredNode` invocation against the same
    tier — including all fan-out branches that share a tier under
    :class:`langgraph.types.Send` — acquires the same lock. Implements
    architecture.md §8.6 ("per-tier concurrency semaphore") at the one
    seam where a run's tier registry is known: the dispatch boundary.

    Semaphores are **per-run, process-local**: one fresh dict per
    dispatched workflow. Two concurrent runs (e.g. two
    ``aiw run slice_refactor`` invocations) see independent
    semaphores, which matches the "process-local" clause in the spec
    and avoids cross-run queueing that would misattribute latency.
    """
    return {
        name: asyncio.Semaphore(config.max_concurrency)
        for name, config in tier_registry.items()
    }


def _build_ollama_circuit_breakers(
    tier_registry: dict[str, TierConfig],
) -> dict[str, CircuitBreaker]:
    """Build one :class:`CircuitBreaker` per Ollama-backed tier (M8 T05).

    Scans the resolved registry for any tier whose route is a
    :class:`LiteLLMRoute` with ``route.model`` starting with
    ``"ollama/"`` and instantiates a breaker using
    :class:`CircuitBreaker`'s architecture.md §8.4 defaults
    (``trip_threshold=3``, ``cooldown_s=60.0``). Non-Ollama tiers
    (Gemini-backed LiteLLM + :class:`ClaudeCodeRoute`) get no entry —
    :func:`ai_workflows.graph.tiered_node._resolve_breaker` would ignore
    them anyway (KDR-003 / architecture.md §8.4 — breakers exist for the
    local Ollama daemon, not hosted providers with their own rate-limit
    semantics), so omitting them keeps the log surface clean.

    Breakers are **per-run, process-local**: one fresh dict per
    dispatched workflow. Two concurrent runs see independent breakers,
    matching the "process-local" clause in the M8 T02 primitive spec.

    Tests that need a shared breaker (to pre-trip it, inject a time
    source, or tighten the threshold) monkey-patch this helper at the
    dispatch boundary — see ``tests/workflows/test_ollama_outage.py``.
    """
    return {
        name: CircuitBreaker(tier=name)
        for name, config in tier_registry.items()
        if isinstance(config.route, LiteLLMRoute)
        and config.route.model.startswith("ollama/")
    }


def _build_cfg(
    *,
    run_id: str,
    workflow: str,
    tier_registry: dict,
    callback: CostTrackingCallback,
    storage: SQLiteStorage,
    eval_capture_callback: CaptureCallback | None = None,
) -> dict[str, Any]:
    """Build the LangGraph ``config["configurable"]`` dict passed to ``ainvoke``.

    Lifts the helper formerly in :mod:`ai_workflows.cli`. ``thread_id``
    and ``run_id`` are kept identical per KDR-009 so the checkpointer's
    thread matches the Storage run id.

    M6 T07 threads a per-tier :class:`asyncio.Semaphore` dict built
    from the tier registry's ``max_concurrency`` budgets. The semaphore
    dict rides ``configurable["semaphores"]`` so :func:`tiered_node`'s
    existing acquisition path (`graph/tiered_node.py`) enforces the cap
    at the provider-call boundary, independent of graph topology (spec
    AC-1).

    M7 T02 optionally threads a :class:`CaptureCallback` through
    ``configurable["eval_capture_callback"]``. ``TieredNode`` reads the
    key duck-typed and no-ops when absent, so unset default paths stay
    byte-identical.

    M8 T05 threads a ``{tier_name: CircuitBreaker}`` dict through
    ``configurable["ollama_circuit_breakers"]`` for every Ollama-backed
    tier in the resolved registry (see
    :func:`_build_ollama_circuit_breakers`). :func:`tiered_node` consults
    this dict on every Ollama-route call and raises :class:`CircuitOpen`
    when the breaker denies; the workflow-layer edges route that to the
    M8 T04 fallback :class:`HumanGate`.
    """
    configurable: dict[str, Any] = {
        "thread_id": run_id,
        "run_id": run_id,
        "tier_registry": tier_registry,
        "cost_callback": callback,
        "storage": storage,
        "workflow": workflow,
        "semaphores": _build_semaphores(tier_registry),
        "ollama_circuit_breakers": _build_ollama_circuit_breakers(tier_registry),
    }
    if eval_capture_callback is not None:
        configurable["eval_capture_callback"] = eval_capture_callback
    return {"configurable": configurable}


def _build_eval_capture_callback(
    *,
    workflow: str,
    run_id: str,
    dataset_override: str | None = None,
) -> CaptureCallback | None:
    """Return a :class:`CaptureCallback` when capture is opted in; else None.

    Opt-in paths (in priority order):

    * ``dataset_override`` — explicit kwarg threaded from a future
      CLI / MCP surface (T04 wires ``--capture-evals <dataset>``; the
      MCP tool is expected to accept an equivalent kwarg).
    * ``AIW_CAPTURE_EVALS`` environment variable — the
      dev-ergonomics path a Builder uses to capture seed fixtures
      (T05) without changing the command line.

    Both paths pass the dataset name to :class:`CaptureCallback`, which
    prefixes its fixture root with the dataset so sibling captures
    (e.g. ``planner-seed`` / ``planner-regen-2026-05``) stay
    disambiguated on disk.
    """

    dataset_name = dataset_override or os.getenv("AIW_CAPTURE_EVALS")
    if not dataset_name:
        return None
    return CaptureCallback(
        dataset_name=dataset_name,
        workflow_id=workflow,
        run_id=run_id,
    )


async def _extract_error_message(compiled: Any, cfg: dict, exc: Exception) -> str:
    """Return the most meaningful error string for a graph invocation failure.

    Budget-cap breaches raise :class:`NonRetryable` from
    ``CostTrackingCallback``; ``wrap_with_error_handler`` catches that
    bucket and writes it to ``state["last_exception"]`` before the
    graph routes to its terminal. In the typical cascade the next node
    (a validator reading the output a prior LLM node never wrote)
    raises a plain ``KeyError`` that escapes LangGraph. Inspect the
    checkpointed state via :meth:`aget_state` to recover the bucket
    exception that actually caused the breach.
    """
    message = str(exc)
    try:
        snapshot = await compiled.aget_state(cfg)
        last = snapshot.values.get("last_exception")
        if last is not None:
            message = str(last)
    except Exception:  # noqa: BLE001 — best-effort; fall back to outer exc
        pass
    return message


async def run_workflow(
    *,
    workflow: str,
    inputs: dict[str, Any],
    budget_cap_usd: float | None = None,
    run_id: str | None = None,
    tier_overrides: dict[str, str] | None = None,
    capture_evals: str | None = None,
) -> dict[str, Any]:
    """Dispatch a workflow run end-to-end and return a surface-ready dict.

    Shared by ``aiw run`` and the MCP ``run_workflow`` tool. Result keys:

    * ``run_id`` — resolved run id (auto-generated ULID if caller passed
      ``None``).
    * ``status`` — ``"pending"`` (HumanGate interrupt), ``"completed"``
      (terminal plan artifact), ``"aborted"`` (ollama-fallback ABORT or
      double-failure slice hard-stop), or ``"errored"`` (budget breach
      or a downstream exception the graph's error handler captured).
    * ``awaiting`` — ``"gate"`` when ``status == "pending"``; otherwise
      ``None``.
    * ``plan`` — ``dict`` (``model_dump()`` of the pydantic plan) when
      ``status == "completed"`` (terminal artefact) or when
      ``status == "pending"`` and ``awaiting == "gate"`` (in-flight
      draft, M11 T01); otherwise ``None``.
    * ``total_cost_usd`` — rolled-up per-run cost (may be ``0.0``).
    * ``error`` — descriptive error string when
      ``status == "errored"`` / ``"aborted"``; otherwise ``None``.
    * ``gate_context`` — dict (M11 T01) populated iff
      ``status == "pending"`` and ``awaiting == "gate"`` with
      ``{gate_prompt, gate_id, workflow_id, checkpoint_ts}``;
      otherwise ``None``.

    ``tier_overrides`` (M5 T04 / T05) is an optional
    ``{logical: replacement}`` map applied against the workflow's
    ``<workflow>_tier_registry()`` before the graph compile step: each
    ``logical`` key gets repointed at ``registry[replacement]``'s
    :class:`TierConfig` (route + concurrency + timeout). Unknown names
    on either side raise :class:`UnknownTierError`; both surfaces
    translate that to their own error shape at the boundary. The
    overrides do not mutate the source registry — a fresh copy is
    threaded into this run's ``config.configurable["tier_registry"]``
    so repeated calls remain idempotent.

    Raises :class:`UnknownWorkflowError` if ``workflow`` is not
    registered and :class:`UnknownTierError` if a ``tier_overrides``
    entry references a tier not in the workflow's registry (surfaces
    convert both to their own error shape at the boundary).
    """
    workflow_module = _import_workflow_module(workflow)
    builder = workflows.get(workflow)

    run_id_resolved = run_id or _generate_ulid()
    base_registry = _resolve_tier_registry(workflow, workflow_module)
    tier_registry = _apply_tier_overrides(base_registry, tier_overrides)
    initial_state = _build_initial_state(workflow_module, run_id_resolved, inputs)
    final_state_key = _resolve_final_state_key(workflow_module)

    storage = await SQLiteStorage.open(default_storage_path())
    checkpointer = await build_async_checkpointer()
    try:
        compiled = builder().compile(checkpointer=checkpointer)

        tracker = CostTracker()
        callback = CostTrackingCallback(
            cost_tracker=tracker, budget_cap_usd=budget_cap_usd
        )
        eval_capture = _build_eval_capture_callback(
            workflow=workflow,
            run_id=run_id_resolved,
            dataset_override=capture_evals,
        )
        cfg = _build_cfg(
            run_id=run_id_resolved,
            workflow=workflow,
            tier_registry=tier_registry,
            callback=callback,
            storage=storage,
            eval_capture_callback=eval_capture,
        )

        await storage.create_run(run_id_resolved, workflow, budget_cap_usd)

        try:
            final = await compiled.ainvoke(
                initial_state, cfg, durability="sync"
            )
        except Exception as exc:  # noqa: BLE001 — surface-boundary catch
            error_msg = await _extract_error_message(compiled, cfg, exc)
            return {
                "run_id": run_id_resolved,
                "status": "errored",
                "awaiting": None,
                "plan": None,
                "total_cost_usd": tracker.total(run_id_resolved),
                "error": error_msg,
                "gate_context": None,
            }

        return await _build_result_from_final(
            final=final,
            run_id=run_id_resolved,
            workflow=workflow,
            final_state_key=final_state_key,
            tracker=tracker,
            storage=storage,
        )
    finally:
        await checkpointer.conn.close()


def _dump_plan(plan: Any) -> dict[str, Any] | None:
    """Serialise an in-flight or terminal plan for transport.

    Accepts a pydantic model (``.model_dump()``), a mapping
    (``dict(plan)``), or ``None``. Returns ``None`` when the plan is
    unset so the MCP output field stays strictly-optional. Shared
    between :func:`_build_result_from_final` and
    :func:`_build_resume_result_from_final` so the pending / completed /
    gate_rejected branches cannot drift in what they emit — surfaces in
    M11 T01 when the interrupt branches started dumping the draft plan
    alongside the existing terminal dumps.
    """
    if plan is None:
        return None
    if hasattr(plan, "model_dump"):
        return plan.model_dump()
    return dict(plan)


def _extract_gate_context(
    final: dict[str, Any], *, workflow: str
) -> dict[str, Any]:
    """Project the :class:`HumanGate` interrupt payload into a review dict.

    M11 T01: at a gate pause, the MCP output needs a minimum
    gate-review surface so the operator (or a skill acting on their
    behalf) has something to approve against. The prompt is not
    written to a state channel — :mod:`ai_workflows.graph.human_gate`
    emits it via ``langgraph.types.interrupt(payload)``, and the
    payload surfaces in ``final["__interrupt__"][0].value`` as a
    dict with keys ``{gate_id, prompt, strict_review, timeout_s,
    default_response_on_timeout}``.

    Defensive ``.get(...)`` everywhere so a malformed or missing
    payload (would be unexpected; the HumanGate always stamps both
    keys) degrades to a stub string rather than an exception and
    emits a ``structlog`` warning so the operator can correlate the
    degraded projection with the run state. ``checkpoint_ts`` is
    stamped at projection time — not the checkpointer's own
    timestamp (LangGraph owns that). The field's operator-triage
    value is "when did the MCP client see this", which
    projection-time gives exactly.
    """
    interrupts = final.get("__interrupt__") or ()
    payload: dict[str, Any]
    if interrupts:
        head = interrupts[0]
        raw = getattr(head, "value", None)
        if isinstance(raw, dict):
            payload = raw
        else:
            _LOG.warning(
                "mcp_gate_context_malformed_payload",
                workflow=workflow,
                payload_type=type(raw).__name__,
            )
            payload = {}
    else:
        _LOG.warning(
            "mcp_gate_context_missing_interrupt",
            workflow=workflow,
        )
        payload = {}
    return {
        "gate_prompt": payload.get("prompt", "<gate prompt not recorded>"),
        "gate_id": payload.get("gate_id", "<unknown>"),
        "workflow_id": workflow,
        "checkpoint_ts": datetime.now(UTC).isoformat(),
    }


async def _build_result_from_final(
    *,
    final: dict[str, Any],
    run_id: str,
    workflow: str,
    final_state_key: str,
    tracker: CostTracker,
    storage: SQLiteStorage,
) -> dict[str, Any]:
    """Translate the graph's terminal state into the shared result dict.

    Four branches:

    * ``__interrupt__`` in state → HumanGate pause. Stamp
      ``runs.total_cost_usd`` so ``aiw resume`` / ``resume_run`` can
      reseed the cost tracker, project the in-flight draft ``plan``
      and a ``gate_context`` review payload (M11 T01), and return
      ``status="pending"`` + ``awaiting="gate"``.
    * ``state["hard_stop_failing_slice_ids"]`` populated → double-failure
      hard-stop fired upstream of the aggregator (M6 T07,
      architecture.md §8.2). Flip ``runs.status`` to ``"aborted"`` with
      ``finished_at`` and return ``status="aborted"`` with a
      descriptive ``error`` enumerating the failing slice ids.
    * ``state[final_state_key]`` is not ``None`` → terminal completion.
      ``final_state_key`` is the workflow's :data:`FINAL_STATE_KEY`
      constant (``"plan"`` for planner, ``"applied_artifact_count"`` for
      slice_refactor — M6 T06 resolves T01-CARRY-DISPATCH-COMPLETE).
      Return ``status="completed"`` with the plan dumped to a plain
      dict for transport when the workflow produces one.
    * Otherwise — the graph finished with neither outcome (usually a
      captured ``NonRetryable`` sitting in ``state["last_exception"]``).
      Return ``status="errored"`` with a descriptive error string so the
      surface can print it instead of silently returning zero output.

    ``workflow`` is the registered workflow name; threaded through so
    the gate-pause branch can stamp it into ``gate_context.workflow_id``
    without a second registry lookup (M11 T01).
    """
    total = tracker.total(run_id)

    if "__interrupt__" in final:
        await storage.update_run_status(run_id, "pending", total_cost_usd=total)
        return {
            "run_id": run_id,
            "status": "pending",
            "awaiting": "gate",
            "plan": _dump_plan(final.get("plan")),
            "total_cost_usd": total,
            "error": None,
            "gate_context": _extract_gate_context(final, workflow=workflow),
        }

    if final.get("ollama_fallback_aborted"):
        # M8 T04: the Ollama-fallback gate resolved to ABORT (planner or
        # slice_refactor). The abort terminal already wrote the
        # ``hard_stop_metadata`` artefact; dispatch flips the run status
        # and surfaces a distinct error message so the operator can tell
        # this abort apart from the §8.2 double-failure hard-stop.
        finished_at = datetime.now(UTC).isoformat()
        await storage.update_run_status(
            run_id,
            "aborted",
            finished_at=finished_at,
            total_cost_usd=total,
        )
        return {
            "run_id": run_id,
            "status": "aborted",
            "awaiting": None,
            "plan": None,
            "total_cost_usd": total,
            "error": (
                "ollama_fallback: operator aborted run at the "
                "circuit-breaker gate"
            ),
            "gate_context": None,
        }

    failing_ids = final.get("hard_stop_failing_slice_ids")
    if failing_ids:
        finished_at = datetime.now(UTC).isoformat()
        await storage.update_run_status(
            run_id,
            "aborted",
            finished_at=finished_at,
            total_cost_usd=total,
        )
        return {
            "run_id": run_id,
            "status": "aborted",
            "awaiting": None,
            "plan": None,
            "total_cost_usd": total,
            "error": (
                "hard-stop: double-failure threshold reached "
                f"({len(failing_ids)} slices failed non-retryably: "
                f"{', '.join(failing_ids)})"
            ),
            "gate_context": None,
        }

    if final.get(final_state_key) is not None:
        return {
            "run_id": run_id,
            "status": "completed",
            "awaiting": None,
            "plan": _dump_plan(final.get("plan")),
            "total_cost_usd": total,
            "error": None,
            "gate_context": None,
        }

    last = final.get("last_exception")
    if last is not None:
        return {
            "run_id": run_id,
            "status": "errored",
            "awaiting": None,
            "plan": None,
            "total_cost_usd": total,
            "error": str(last) if not isinstance(last, NonRetryable) else str(last),
            "gate_context": None,
        }
    return {
        "run_id": run_id,
        "status": "errored",
        "awaiting": None,
        "plan": None,
        "total_cost_usd": total,
        "error": "workflow ended without plan or gate interrupt",
        "gate_context": None,
    }


async def resume_run(
    *,
    run_id: str,
    gate_response: str,
) -> dict[str, Any]:
    """Rehydrate a checkpointed run and clear the pending ``HumanGate``.

    Shared by the ``aiw resume`` CLI command and the ``resume_run`` MCP
    tool (M4 T03). Returns a plain dict with the keys each surface needs:

    * ``run_id`` — the resumed run id (echoed verbatim).
    * ``status`` — ``"pending"`` (another gate fired post-resume),
      ``"completed"`` (plan persisted), ``"gate_rejected"`` (caller
      rejected at the gate), or ``"errored"`` (graph raised /
      post-gate fault captured).
    * ``plan`` — ``dict`` only when ``status == "completed"``.
    * ``total_cost_usd`` — rolled-up per-run cost, reseeded from
      ``runs.total_cost_usd`` so the budget cap carries across the
      run / resume boundary (M3 T05 AC-5 regression).
    * ``error`` — descriptive string when ``status == "errored"``.

    Raises :class:`ResumePreconditionError` if the run id is unknown
    **or** if the row is in ``status="cancelled"`` (M4 T05 relies on
    this guard to make the cancel flip meaningful).
    Raises :class:`UnknownWorkflowError` if the row's ``workflow_id``
    is no longer registered (rare: a workflow was renamed between
    the pause and the resume).
    """
    storage = await SQLiteStorage.open(default_storage_path())
    row = await storage.get_run(run_id)
    if row is None:
        raise ResumePreconditionError(f"no run found: {run_id}")
    if row["status"] == "cancelled":
        raise ResumePreconditionError(
            f"run {run_id} was cancelled and cannot be resumed"
        )

    workflow = row["workflow_id"]
    budget_cap_usd = row["budget_cap_usd"]
    stored_cost = row["total_cost_usd"] or 0.0

    workflow_module = _import_workflow_module(workflow)
    builder = workflows.get(workflow)
    tier_registry = _resolve_tier_registry(workflow, workflow_module)
    terminal_gate_id = _resolve_terminal_gate_id(workflow_module)
    final_state_key = _resolve_final_state_key(workflow_module)

    tracker = CostTracker()
    if stored_cost > 0:
        # Synthetic entry so ``tracker.total(run_id)`` + the per-call
        # ``CostTrackingCallback.check_budget`` both see the cost the
        # preceding ``aiw run`` already incurred. Budget cap from the
        # original run rides across verbatim (M3 T05 AC-5).
        tracker.record(
            run_id,
            TokenUsage(
                cost_usd=stored_cost,
                model="<resumed>",
                tier="<resumed>",
            ),
        )
    callback = CostTrackingCallback(
        cost_tracker=tracker, budget_cap_usd=budget_cap_usd
    )

    checkpointer = await build_async_checkpointer()
    try:
        compiled = builder().compile(checkpointer=checkpointer)
        eval_capture = _build_eval_capture_callback(
            workflow=workflow,
            run_id=run_id,
        )
        cfg = _build_cfg(
            run_id=run_id,
            workflow=workflow,
            tier_registry=tier_registry,
            callback=callback,
            storage=storage,
            eval_capture_callback=eval_capture,
        )

        try:
            final = await compiled.ainvoke(
                Command(resume=gate_response), cfg, durability="sync"
            )
        except Exception as exc:  # noqa: BLE001 — surface-boundary catch
            error_msg = await _extract_error_message(compiled, cfg, exc)
            return {
                "run_id": run_id,
                "status": "errored",
                "awaiting": None,
                "plan": None,
                "total_cost_usd": tracker.total(run_id),
                "error": error_msg,
                "gate_context": None,
            }

        return await _build_resume_result_from_final(
            final=final,
            run_id=run_id,
            workflow=workflow,
            gate_response=gate_response,
            terminal_gate_id=terminal_gate_id,
            final_state_key=final_state_key,
            tracker=tracker,
            storage=storage,
        )
    finally:
        await checkpointer.conn.close()


async def _build_resume_result_from_final(
    *,
    final: dict[str, Any],
    run_id: str,
    workflow: str,
    gate_response: str,
    terminal_gate_id: str | None,
    final_state_key: str = "plan",
    tracker: CostTracker,
    storage: SQLiteStorage,
) -> dict[str, Any]:
    """Translate the graph's terminal state after ``Command(resume=…)``.

    Four branches (mirrors the pre-refactor ``cli._emit_resume_final``):

    * ``__interrupt__`` in state → another gate fired; stamp cost at
      pause, project the re-gated draft ``plan`` and a ``gate_context``
      review payload (M11 T01), and return ``status="pending"`` +
      ``awaiting="gate"``.
    * ``state[f"gate_{terminal_gate_id}_response"] == "rejected"`` →
      flip ``runs.status`` to ``gate_rejected`` with ``finished_at``;
      return ``status="gate_rejected"`` with the last-draft ``plan``
      projected for audit (M11 T01).
    * ``state[final_state_key]`` populated (approved path reached its
      terminal artefact node) → flip ``runs.status`` to ``completed``;
      return ``status="completed"`` with the plan dumped to a plain
      dict when the workflow produces one.
    * Fallback — any ``last_exception`` captured by
      ``wrap_with_error_handler`` surfaces as ``status="errored"`` so
      a rare post-gate failure is reported rather than swallowed.

    ``terminal_gate_id`` is discovered from the workflow module's
    ``TERMINAL_GATE_ID`` constant (M6 T05 — resolves T01-CARRY-DISPATCH-GATE).
    ``final_state_key`` is discovered from the workflow module's
    ``FINAL_STATE_KEY`` constant (M6 T06 — resolves
    T01-CARRY-DISPATCH-COMPLETE): ``"plan"`` for the planner,
    ``"applied_artifact_count"`` for slice_refactor. Before these
    conventions existed the function hardcoded the planner's ids; each
    workflow now publishes its own constants so slice_refactor's
    ``"slice_refactor_review"`` gate + ``"applied_artifact_count"``
    completion signal and the planner's ``"plan_review"`` / ``"plan"``
    pair share one dispatch path. Workflows that omit the constants fall
    back to the caller-supplied ``gate_response`` and the ``"plan"``
    default, keeping the contract backwards-compatible for pre-M6 code.

    ``workflow`` is the registered workflow name; threaded through so
    the interrupt branch can stamp it into ``gate_context.workflow_id``
    without a second registry lookup (M11 T01).
    """
    total = tracker.total(run_id)

    if "__interrupt__" in final:
        await storage.update_run_status(run_id, "pending", total_cost_usd=total)
        return {
            "run_id": run_id,
            "status": "pending",
            "awaiting": "gate",
            "plan": _dump_plan(final.get("plan")),
            "total_cost_usd": total,
            "error": None,
            "gate_context": _extract_gate_context(final, workflow=workflow),
        }

    if final.get("ollama_fallback_aborted"):
        # M8 T04: see :func:`_build_result_from_final` for the rationale.
        # The resume path is the primary trigger for this branch — the
        # Ollama-fallback gate only fires after a human interrupt, so the
        # ABORT terminal always lands on the resume boundary.
        finished_at = datetime.now(UTC).isoformat()
        await storage.update_run_status(
            run_id,
            "aborted",
            finished_at=finished_at,
            total_cost_usd=total,
        )
        return {
            "run_id": run_id,
            "status": "aborted",
            "awaiting": None,
            "plan": None,
            "total_cost_usd": total,
            "error": (
                "ollama_fallback: operator aborted run at the "
                "circuit-breaker gate"
            ),
            "gate_context": None,
        }

    # Prefer the state-recorded response for the workflow's terminal gate;
    # fall back to the flag the caller passed if the gate node did not
    # get a chance to persist it (e.g. graph errored before the gate's
    # post-interrupt block ran) or the workflow omits TERMINAL_GATE_ID.
    if terminal_gate_id is not None:
        response = final.get(
            f"gate_{terminal_gate_id}_response", gate_response
        )
    else:
        response = gate_response

    if response == "rejected":
        finished_at = datetime.now(UTC).isoformat()
        await storage.update_run_status(
            run_id,
            "gate_rejected",
            finished_at=finished_at,
            total_cost_usd=total,
        )
        return {
            "run_id": run_id,
            "status": "gate_rejected",
            "awaiting": None,
            # M11 T01: project the last-draft plan for audit review.
            # ``gate_context`` stays ``None`` — the gate has already
            # resolved, no pending prompt to surface.
            "plan": _dump_plan(final.get("plan")),
            "total_cost_usd": total,
            "error": None,
            "gate_context": None,
        }

    if final.get(final_state_key) is not None:
        await storage.update_run_status(
            run_id, "completed", total_cost_usd=total
        )
        return {
            "run_id": run_id,
            "status": "completed",
            "awaiting": None,
            "plan": _dump_plan(final.get("plan")),
            "total_cost_usd": total,
            "error": None,
            "gate_context": None,
        }

    last = final.get("last_exception")
    if last is not None:
        return {
            "run_id": run_id,
            "status": "errored",
            "awaiting": None,
            "plan": None,
            "total_cost_usd": total,
            "error": str(last),
            "gate_context": None,
        }
    return {
        "run_id": run_id,
        "status": "errored",
        "awaiting": None,
        "plan": None,
        "total_cost_usd": total,
        "error": "resume produced no plan and no interrupt",
        "gate_context": None,
    }
