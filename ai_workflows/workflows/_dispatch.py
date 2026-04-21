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
import secrets
import time
from datetime import UTC, datetime
from typing import Any

from langgraph.types import Command

from ai_workflows import workflows
from ai_workflows.graph.checkpointer import build_async_checkpointer
from ai_workflows.graph.cost_callback import CostTrackingCallback
from ai_workflows.primitives.cost import CostTracker, TokenUsage
from ai_workflows.primitives.retry import NonRetryable
from ai_workflows.primitives.storage import SQLiteStorage, default_storage_path
from ai_workflows.primitives.tiers import TierConfig

__all__ = [
    "ResumePreconditionError",
    "UnknownTierError",
    "UnknownWorkflowError",
    "resume_run",
    "run_workflow",
]


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
    """Import ``ai_workflows.workflows.<workflow>`` or raise :class:`UnknownWorkflowError`.

    The registered-workflows list in the error is eagerly populated by
    re-importing ``ai_workflows.workflows.planner`` — M3's only
    registered workflow — so a typo on first invocation still yields an
    actionable list instead of an empty ``[]``. M5 / M6 additions get
    the same surface for free once their modules register themselves.
    """
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


def _build_cfg(
    *,
    run_id: str,
    workflow: str,
    tier_registry: dict,
    callback: CostTrackingCallback,
    storage: SQLiteStorage,
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
    """
    return {
        "configurable": {
            "thread_id": run_id,
            "run_id": run_id,
            "tier_registry": tier_registry,
            "cost_callback": callback,
            "storage": storage,
            "workflow": workflow,
            "semaphores": _build_semaphores(tier_registry),
        }
    }


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
) -> dict[str, Any]:
    """Dispatch a workflow run end-to-end and return a surface-ready dict.

    Shared by ``aiw run`` and the MCP ``run_workflow`` tool. Result keys:

    * ``run_id`` — resolved run id (auto-generated ULID if caller passed
      ``None``).
    * ``status`` — ``"pending"`` (HumanGate interrupt), ``"completed"``
      (terminal plan artifact), or ``"errored"`` (budget breach or a
      downstream exception the graph's error handler captured).
    * ``awaiting`` — ``"gate"`` when ``status == "pending"``; otherwise
      ``None``.
    * ``plan`` — ``dict`` (``model_dump()`` of the pydantic plan) when
      ``status == "completed"``; otherwise ``None``.
    * ``total_cost_usd`` — rolled-up per-run cost (may be ``0.0``).
    * ``error`` — descriptive error string when
      ``status == "errored"``; otherwise ``None``.

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
        cfg = _build_cfg(
            run_id=run_id_resolved,
            workflow=workflow,
            tier_registry=tier_registry,
            callback=callback,
            storage=storage,
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
            }

        return await _build_result_from_final(
            final=final,
            run_id=run_id_resolved,
            final_state_key=final_state_key,
            tracker=tracker,
            storage=storage,
        )
    finally:
        await checkpointer.conn.close()


async def _build_result_from_final(
    *,
    final: dict[str, Any],
    run_id: str,
    final_state_key: str,
    tracker: CostTracker,
    storage: SQLiteStorage,
) -> dict[str, Any]:
    """Translate the graph's terminal state into the shared result dict.

    Four branches:

    * ``__interrupt__`` in state → HumanGate pause. Stamp
      ``runs.total_cost_usd`` so ``aiw resume`` / ``resume_run`` can
      reseed the cost tracker, and return ``status="pending"`` +
      ``awaiting="gate"``.
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
    """
    total = tracker.total(run_id)

    if "__interrupt__" in final:
        await storage.update_run_status(run_id, "pending", total_cost_usd=total)
        return {
            "run_id": run_id,
            "status": "pending",
            "awaiting": "gate",
            "plan": None,
            "total_cost_usd": total,
            "error": None,
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
        }

    if final.get(final_state_key) is not None:
        plan = final.get("plan")
        plan_dump = (
            plan.model_dump() if hasattr(plan, "model_dump")
            else (dict(plan) if plan else None)
        )
        return {
            "run_id": run_id,
            "status": "completed",
            "awaiting": None,
            "plan": plan_dump,
            "total_cost_usd": total,
            "error": None,
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
        }
    return {
        "run_id": run_id,
        "status": "errored",
        "awaiting": None,
        "plan": None,
        "total_cost_usd": total,
        "error": "workflow ended without plan or gate interrupt",
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
        cfg = _build_cfg(
            run_id=run_id,
            workflow=workflow,
            tier_registry=tier_registry,
            callback=callback,
            storage=storage,
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
                "plan": None,
                "total_cost_usd": tracker.total(run_id),
                "error": error_msg,
            }

        return await _build_resume_result_from_final(
            final=final,
            run_id=run_id,
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
    gate_response: str,
    terminal_gate_id: str | None,
    final_state_key: str = "plan",
    tracker: CostTracker,
    storage: SQLiteStorage,
) -> dict[str, Any]:
    """Translate the graph's terminal state after ``Command(resume=…)``.

    Four branches (mirrors the pre-refactor ``cli._emit_resume_final``):

    * ``__interrupt__`` in state → another gate fired; stamp cost at
      pause and return ``status="pending"``.
    * ``state[f"gate_{terminal_gate_id}_response"] == "rejected"`` →
      flip ``runs.status`` to ``gate_rejected`` with ``finished_at``;
      return ``status="gate_rejected"``.
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
    """
    total = tracker.total(run_id)

    if "__interrupt__" in final:
        await storage.update_run_status(run_id, "pending", total_cost_usd=total)
        return {
            "run_id": run_id,
            "status": "pending",
            "plan": None,
            "total_cost_usd": total,
            "error": None,
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
            "plan": None,
            "total_cost_usd": total,
            "error": None,
        }

    if final.get(final_state_key) is not None:
        await storage.update_run_status(
            run_id, "completed", total_cost_usd=total
        )
        plan = final.get("plan")
        plan_dump = (
            plan.model_dump() if hasattr(plan, "model_dump")
            else (dict(plan) if plan else None)
        )
        return {
            "run_id": run_id,
            "status": "completed",
            "plan": plan_dump,
            "total_cost_usd": total,
            "error": None,
        }

    last = final.get("last_exception")
    if last is not None:
        return {
            "run_id": run_id,
            "status": "errored",
            "plan": None,
            "total_cost_usd": total,
            "error": str(last),
        }
    return {
        "run_id": run_id,
        "status": "errored",
        "plan": None,
        "total_cost_usd": total,
        "error": "resume produced no plan and no interrupt",
    }
