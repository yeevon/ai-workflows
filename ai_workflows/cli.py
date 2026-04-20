"""``aiw`` — CLI surface for ai-workflows.

Milestone 1 Task 11 reduced this module to ``aiw --help`` / ``aiw version``.
Milestone 3 Task 04 revives the ``aiw run`` command so a user can drive
the ``planner`` :class:`StateGraph` end-to-end from the terminal.
Milestone 3 Task 05 adds the companion ``aiw resume`` command: reads
the run's workflow + budget back from Storage, reseeds the cost tracker
from ``runs.total_cost_usd`` (stamped by ``aiw run`` on gate pause),
rebuilds the graph + checkpointer, and hands ``Command(resume=...)`` to
LangGraph's async saver so the pending ``HumanGate`` clears and the
workflow completes into its artifact (KDR-009). M3 Task 06 brings
``aiw list-runs`` / ``aiw cost-report`` back. The M4 MCP surface will
mirror the same four commands.

Relationship to other modules
-----------------------------
* :mod:`ai_workflows` — the package ``__version__`` dunder read by
  ``aiw version``.
* :mod:`ai_workflows.workflows` — registry the ``run`` command resolves
  workflow builders from. Workflow modules are imported lazily so
  registration fires only when the caller names the workflow.
* :mod:`ai_workflows.graph.checkpointer` — the ``AsyncSqliteSaver``
  factory ``run`` compiles the graph against (KDR-009).
* :mod:`ai_workflows.primitives.storage` —
  :class:`SQLiteStorage` + :func:`default_storage_path` for the run
  registry. Distinct on-disk file from the checkpointer (KDR-009).
* :mod:`ai_workflows.primitives.cost` + :mod:`ai_workflows.graph.cost_callback`
  — per-run ledger + budget-cap enforcement threaded through the
  LangGraph config.

The CLI never imports the Anthropic SDK and never reads provider API
keys directly — every env-var lookup stays at the LiteLLM / Claude
Code adapter boundary (KDR-003).
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import secrets
import time
from datetime import UTC, datetime
from typing import Any

import typer
from langgraph.types import Command

from ai_workflows import workflows
from ai_workflows.graph.checkpointer import build_async_checkpointer
from ai_workflows.graph.cost_callback import CostTrackingCallback
from ai_workflows.primitives.cost import CostTracker, TokenUsage
from ai_workflows.primitives.logging import configure_logging
from ai_workflows.primitives.retry import NonRetryable
from ai_workflows.primitives.storage import SQLiteStorage, default_storage_path

__all__ = ["app"]

app = typer.Typer(
    name="aiw",
    help="ai-workflows CLI",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def _root() -> None:
    """ai-workflows CLI.

    Kept as an empty callback so Typer treats ``aiw`` as a
    multi-command app. Commands removed by M1 Task 11 are being
    reintroduced across M3: ``run`` (this task), ``resume`` (T05),
    ``list-runs`` / ``cost-report`` (T06). ``TODO(M4)`` pointers at the
    bottom of this module name the MCP mirrors.
    """


@app.command()
def version() -> None:
    """Print the installed ai-workflows package version."""
    from ai_workflows import __version__

    typer.echo(__version__)


# ---------------------------------------------------------------------------
# ULID-shape run-id generator
# ---------------------------------------------------------------------------

# Crockford base32 (excludes I, L, O, U so run ids can be read aloud).
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _generate_ulid() -> str:
    """Return a 26-char ULID-shape identifier (48-bit ts + 80-bit random).

    Not the ULID spec to the letter — the randomness source is
    :func:`secrets.token_bytes` rather than monotonically-stepping the
    last-generated id — but the shape (26 chars, Crockford base32,
    sortable-ish by leading timestamp) matches and keeps the CLI from
    taking on an extra third-party dependency for a one-call concern.
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


# ---------------------------------------------------------------------------
# `aiw run`
# ---------------------------------------------------------------------------


@app.command()
def run(
    workflow: str = typer.Argument(
        ...,
        help="Workflow name registered in ai_workflows.workflows.",
    ),
    goal: str = typer.Option(
        ...,
        "--goal",
        "-g",
        help="Planning goal to hand the workflow.",
    ),
    context: str | None = typer.Option(
        None,
        "--context",
        "-c",
        help="Optional context hint for the workflow.",
    ),
    max_steps: int = typer.Option(
        10,
        "--max-steps",
        help="Maximum plan length the workflow may emit.",
    ),
    budget_cap_usd: float | None = typer.Option(
        None,
        "--budget",
        help="Per-run USD cap enforced by CostTrackingCallback.",
    ),
    run_id: str | None = typer.Option(
        None,
        "--run-id",
        help="Override the auto-generated run id.",
    ),
) -> None:
    """Execute a workflow end-to-end. Pauses at ``HumanGate`` interrupts.

    Lazy-imports ``ai_workflows.workflows.<workflow>`` so the workflow's
    top-level ``register(...)`` call fires before the builder is
    resolved. Opens :class:`SQLiteStorage` at
    :func:`default_storage_path` and compiles the graph under
    :func:`build_async_checkpointer` so ``HumanGate`` interrupts + the
    eventual ``aiw resume`` ride LangGraph's durable checkpointer
    (KDR-009).
    """
    # Route structured logs to stderr so the CLI's stdout stays the
    # machine-parseable surface (gate hint / plan JSON / cost total).
    configure_logging(level="INFO")
    asyncio.run(
        _run_async(
            workflow=workflow,
            goal=goal,
            context=context,
            max_steps=max_steps,
            budget_cap_usd=budget_cap_usd,
            run_id=run_id,
        )
    )


async def _run_async(
    *,
    workflow: str,
    goal: str,
    context: str | None,
    max_steps: int,
    budget_cap_usd: float | None,
    run_id: str | None,
) -> None:
    """Async body of ``aiw run``.

    Split out so the Typer command can stay sync (Typer does not
    currently support async commands cleanly) while the graph and
    storage APIs remain async.
    """
    workflow_module = _import_workflow_module(workflow)
    builder = workflows.get(workflow)

    run_id_resolved = run_id or _generate_ulid()
    tier_registry = _resolve_tier_registry(workflow, workflow_module)
    initial_state = _build_initial_state(workflow_module, run_id_resolved, goal, context, max_steps)

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
        except Exception as exc:  # noqa: BLE001 — top-level CLI boundary
            await _surface_graph_error(compiled, cfg, exc)
            return

        await _emit_final_state(final, run_id_resolved, tracker, storage)
    finally:
        await checkpointer.conn.close()


def _build_cfg(
    *,
    run_id: str,
    workflow: str,
    tier_registry: dict,
    callback: CostTrackingCallback,
    storage: SQLiteStorage,
) -> dict[str, Any]:
    """Build the LangGraph ``config["configurable"]`` dict shared by run + resume.

    Keeping this in one place pins the field set both commands pass in
    (``thread_id`` + ``run_id`` kept identical per KDR-009 so the
    checkpointer's thread matches the Storage run id) and eliminates the
    drift between ``_run_async`` and ``_resume_async`` that would
    otherwise accumulate as the field set grows in M4 / M5.
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


def _import_workflow_module(workflow: str) -> Any:
    """Import ``ai_workflows.workflows.<workflow>`` or exit 2 with a nice error.

    The registered-workflows list in the error message is eagerly
    populated by re-importing ``ai_workflows.workflows.planner`` — M3's
    only registered workflow — so a typo on first invocation still
    prints an actionable list instead of an empty ``[]``.
    """
    module_path = f"ai_workflows.workflows.{workflow}"
    try:
        return importlib.import_module(module_path)
    except ModuleNotFoundError:
        with contextlib.suppress(ModuleNotFoundError):
            importlib.import_module("ai_workflows.workflows.planner")
        registered = workflows.list_workflows()
        typer.echo(
            f"unknown workflow {workflow!r}; registered: {registered}",
            err=True,
        )
        raise typer.Exit(code=2) from None


def _resolve_tier_registry(workflow: str, module: Any) -> dict:
    """Return the workflow's tier-registry mapping.

    Each workflow module exports a ``<workflow>_tier_registry()``
    helper — M3 T03/T04 introduced the pattern; M5 onwards will follow.
    Missing helpers fall back to ``{}`` so a workflow that doesn't make
    LLM calls (none today) still runs.
    """
    helper = getattr(module, f"{workflow}_tier_registry", None)
    if helper is None:
        return {}
    return helper()


def _build_initial_state(
    module: Any,
    run_id: str,
    goal: str,
    context: str | None,
    max_steps: int,
) -> dict[str, Any]:
    """Construct the workflow's initial state dict.

    M3 only ships ``planner``; its ``PlannerInput`` schema is looked up
    on the module. When M5/M6 add more workflows they can expose an
    ``Input`` alias (or equivalent) on the module and this helper can
    branch — for now keeping it narrowly specific to the schema
    ``planner.py`` exports.
    """
    input_cls = getattr(module, "PlannerInput", None)
    if input_cls is None:
        raise typer.Exit(code=2)
    return {
        "run_id": run_id,
        "input": input_cls(goal=goal, context=context, max_steps=max_steps),
    }


async def _surface_graph_error(compiled: Any, cfg: dict, exc: Exception) -> None:
    """Print the most meaningful error message and exit non-zero.

    Budget-cap breaches raise :class:`NonRetryable` from
    ``CostTrackingCallback``; ``wrap_with_error_handler`` catches that
    bucket and writes it to ``state["last_exception"]`` before the
    graph routes to its terminal. In the typical cascade the next node
    (a validator reading the output a prior LLM node never wrote)
    raises a plain ``KeyError`` that escapes LangGraph — so the
    Exception surfacing here is often that ``KeyError``, not the
    NonRetryable we actually care about. Inspect the checkpointed state
    via :meth:`aget_state` to recover the bucket exception the user
    needs to see.
    """
    message = str(exc)
    try:
        snapshot = await compiled.aget_state(cfg)
        last = snapshot.values.get("last_exception")
        if last is not None:
            message = str(last)
    except Exception:  # noqa: BLE001 — best-effort; fall back to outer exc
        pass
    typer.echo(f"error: {message}", err=True)
    raise typer.Exit(code=1)


async def _emit_final_state(
    final: dict[str, Any],
    run_id: str,
    tracker: CostTracker,
    storage: SQLiteStorage,
) -> None:
    """Print the expected post-invoke output and update Storage.

    Two clean branches per the task spec:

    * ``__interrupt__`` in the returned state → the graph paused at a
      ``HumanGate``; stamp ``runs.total_cost_usd`` (so ``aiw resume``
      can reseed the cost tracker — see T05 AC-5) and print the run id
      + the exact ``aiw resume`` command the user needs.
    * ``plan`` in the returned state → the graph completed; print the
      pretty-JSON plan + the total cost.

    A third, defensive branch handles the case where the graph reached
    a terminal node without either outcome (e.g. a budget breach whose
    NonRetryable is still sitting in ``state['last_exception']``): we
    surface it as an error and exit non-zero rather than silently
    returning zero with no output.
    """
    if "__interrupt__" in final:
        await storage.update_run_status(
            run_id, "pending", total_cost_usd=tracker.total(run_id)
        )
        typer.echo(run_id)
        typer.echo("awaiting: gate")
        typer.echo(
            f"resume with: aiw resume {run_id} --gate-response <approved|rejected>"
        )
        return

    plan = final.get("plan")
    if plan is not None:
        typer.echo(plan.model_dump_json(indent=2))
        typer.echo(f"total cost: ${tracker.total(run_id):.4f}")
        return

    last = final.get("last_exception")
    if isinstance(last, NonRetryable):
        typer.echo(f"error: {last}", err=True)
        raise typer.Exit(code=1)
    if last is not None:
        typer.echo(f"error: {last}", err=True)
        raise typer.Exit(code=1)
    typer.echo("workflow ended without plan or gate interrupt", err=True)
    raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# `aiw resume`
# ---------------------------------------------------------------------------


@app.command()
def resume(
    run_id: str = typer.Argument(
        ...,
        help="Run id returned by a prior `aiw run` invocation.",
    ),
    gate_response: str = typer.Option(
        "approved",
        "--gate-response",
        "-r",
        help="Response forwarded verbatim to `Command(resume=...)`.",
    ),
) -> None:
    """Rehydrate a checkpointed run and clear the pending ``HumanGate``.

    Reads the run's workflow id + budget cap from Storage, reseeds the
    :class:`CostTracker` from the row's ``total_cost_usd`` (stamped by
    ``aiw run`` on gate pause so budget caps carry across ``run`` +
    ``resume``), recompiles the graph under :func:`build_async_checkpointer`,
    and hands ``Command(resume=gate_response)`` to the saver so the
    gate clears and the workflow advances into its artifact node
    (approved → plan persisted via ``write_artifact``; rejected →
    artifact node no-ops; either way the ``runs`` row lands in its
    terminal state here).
    """
    configure_logging(level="INFO")
    asyncio.run(_resume_async(run_id=run_id, gate_response=gate_response))


async def _resume_async(*, run_id: str, gate_response: str) -> None:
    """Async body of ``aiw resume``.

    Split out so the Typer command can stay sync while the graph and
    Storage APIs remain async (same reason ``_run_async`` is factored
    out of ``run``).
    """
    storage = await SQLiteStorage.open(default_storage_path())
    row = await storage.get_run(run_id)
    if row is None:
        typer.echo(f"no run found: {run_id}", err=True)
        raise typer.Exit(code=2)

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
        # original run rides across verbatim (T05 AC-5).
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
        except Exception as exc:  # noqa: BLE001 — top-level CLI boundary
            await _surface_graph_error(compiled, cfg, exc)
            return

        await _emit_resume_final(
            final=final,
            run_id=run_id,
            gate_response=gate_response,
            tracker=tracker,
            storage=storage,
        )
    finally:
        await checkpointer.conn.close()


async def _emit_resume_final(
    *,
    final: dict[str, Any],
    run_id: str,
    gate_response: str,
    tracker: CostTracker,
    storage: SQLiteStorage,
) -> None:
    """Emit the post-resume output and flip the ``runs`` row to its terminal state.

    Three branches per T05 spec §2 and §6:

    * ``__interrupt__`` in the returned state → another gate fired;
      stamp cost-at-pause and re-print the same three-line handle
      ``aiw run`` prints, so a downstream caller can loop.
    * ``gate_plan_review_response == "rejected"`` → flip ``runs.status``
      to ``gate_rejected`` with ``finished_at`` + the rolled-up
      ``total_cost_usd``; exit 1. No artifact write — that's the
      ``_artifact_node``'s contract (planner.py).
    * ``plan`` present (and response was approved) → flip ``runs.status``
      to ``completed`` with ``total_cost_usd``; print the plan JSON +
      the cost total; exit 0.

    A terminal fallback surfaces any state-resident ``last_exception``
    so a rare post-gate failure is reported rather than swallowed.
    """
    total = tracker.total(run_id)

    if "__interrupt__" in final:
        await storage.update_run_status(
            run_id, "pending", total_cost_usd=total
        )
        typer.echo(run_id)
        typer.echo("awaiting: gate")
        typer.echo(
            f"resume with: aiw resume {run_id} --gate-response <approved|rejected>"
        )
        return

    # Prefer the state-recorded response (HumanGate writes it through
    # the ``gate_<id>_response`` key); fall back to the flag the caller
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
        typer.echo(f"plan rejected by gate for run {run_id}")
        typer.echo(f"total cost: ${total:.4f}")
        raise typer.Exit(code=1)

    plan = final.get("plan")
    if plan is not None:
        await storage.update_run_status(
            run_id, "completed", total_cost_usd=total
        )
        typer.echo(plan.model_dump_json(indent=2))
        typer.echo(f"total cost: ${total:.4f}")
        return

    last = final.get("last_exception")
    if last is not None:
        typer.echo(f"error: {last}", err=True)
        raise typer.Exit(code=1)
    typer.echo("resume produced no plan and no interrupt", err=True)
    raise typer.Exit(code=1)


# TODO(M3): `list-runs` — query Storage.list_runs (architecture.md §4.1,
#   §4.4).
# TODO(M3): `cost-report <run_id>` — CostTracker rollup
#   (architecture.md §4.1, §4.4).
# TODO(M4): mirror `run` / `resume` / `list-runs` / `cost-report` as
#   FastMCP tools under ``ai_workflows.mcp`` (architecture.md §4.4,
#   KDR-002, KDR-008).


if __name__ == "__main__":  # pragma: no cover - manual invocation only
    app()
