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

__all__ = [
    "ResumePreconditionError",
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


def _build_initial_state(
    module: Any,
    run_id: str,
    inputs: dict[str, Any],
) -> dict[str, Any]:
    """Construct the workflow's initial state dict.

    Looks up the workflow module's ``*Input`` schema by convention
    (planner → ``PlannerInput``) and instantiates it from ``inputs``.
    Matches the CLI's prior behaviour — the CLI formerly unpacked
    ``goal`` / ``context`` / ``max_steps`` into those exact keys of
    ``PlannerInput``.
    """
    input_cls = getattr(module, "PlannerInput", None)
    if input_cls is None:
        raise ValueError(f"workflow {module.__name__!r} exposes no Input schema")
    return {
        "run_id": run_id,
        "input": input_cls(**inputs),
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
    """
    return {
        "configurable": {
            "thread_id": run_id,
            "run_id": run_id,
            "tier_registry": tier_registry,
            "cost_callback": callback,
            "storage": storage,
            "workflow": workflow,
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

    Raises :class:`UnknownWorkflowError` if ``workflow`` is not
    registered (surfaces convert this to their own error shape at the
    boundary).
    """
    workflow_module = _import_workflow_module(workflow)
    builder = workflows.get(workflow)

    run_id_resolved = run_id or _generate_ulid()
    tier_registry = _resolve_tier_registry(workflow, workflow_module)
    initial_state = _build_initial_state(workflow_module, run_id_resolved, inputs)

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
            final = await compiled.ainvoke(initial_state, cfg)
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
            tracker=tracker,
            storage=storage,
        )
    finally:
        await checkpointer.conn.close()


async def _build_result_from_final(
    *,
    final: dict[str, Any],
    run_id: str,
    tracker: CostTracker,
    storage: SQLiteStorage,
) -> dict[str, Any]:
    """Translate the graph's terminal state into the shared result dict.

    Three branches:

    * ``__interrupt__`` in state → HumanGate pause. Stamp
      ``runs.total_cost_usd`` so ``aiw resume`` / ``resume_run`` can
      reseed the cost tracker, and return ``status="pending"`` +
      ``awaiting="gate"``.
    * ``plan`` in state → terminal completion. Return
      ``status="completed"`` with the plan dumped to a plain dict for
      transport.
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

    plan = final.get("plan")
    if plan is not None:
        plan_dump = plan.model_dump() if hasattr(plan, "model_dump") else dict(plan)
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
            final = await compiled.ainvoke(Command(resume=gate_response), cfg)
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
    tracker: CostTracker,
    storage: SQLiteStorage,
) -> dict[str, Any]:
    """Translate the graph's terminal state after ``Command(resume=…)``.

    Four branches (mirrors the pre-refactor ``cli._emit_resume_final``):

    * ``__interrupt__`` in state → another gate fired; stamp cost at
      pause and return ``status="pending"``.
    * ``gate_plan_review_response == "rejected"`` → flip ``runs.status``
      to ``gate_rejected`` with ``finished_at``; return
      ``status="gate_rejected"``.
    * ``plan`` present (response was approved) → flip ``runs.status``
      to ``completed``; return ``status="completed"`` with the plan
      dumped to a plain dict for transport.
    * Fallback — any ``last_exception`` captured by
      ``wrap_with_error_handler`` surfaces as ``status="errored"`` so
      a rare post-gate failure is reported rather than swallowed.
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

    # Prefer the state-recorded response (HumanGate writes it through the
    # ``gate_<id>_response`` key); fall back to the flag the caller
    # passed if the gate node did not get a chance to persist it (e.g.
    # graph errored before the gate's post-interrupt block ran).
    response = final.get("gate_plan_review_response", gate_response)

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

    plan = final.get("plan")
    if plan is not None:
        await storage.update_run_status(run_id, "completed", total_cost_usd=total)
        plan_dump = plan.model_dump() if hasattr(plan, "model_dump") else dict(plan)
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
