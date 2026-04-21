"""``aiw`` — CLI surface for ai-workflows.

Milestone 1 Task 11 reduced this module to ``aiw --help`` / ``aiw version``.
Milestone 3 Task 04 revives the ``aiw run`` command so a user can drive
the ``planner`` :class:`StateGraph` end-to-end from the terminal.
Milestone 3 Task 05 adds the companion ``aiw resume`` command: reads
the run's workflow + budget back from Storage, reseeds the cost tracker
from ``runs.total_cost_usd`` (stamped by ``aiw run`` on gate pause),
rebuilds the graph + checkpointer, and hands ``Command(resume=...)`` to
LangGraph's async saver so the pending ``HumanGate`` clears and the
workflow completes into its artifact (KDR-009). M3 Task 06 adds
``aiw list-runs`` — a pure read over ``Storage.list_runs`` that
surfaces ``runs.total_cost_usd`` per row. The originally-paired
``aiw cost-report`` command was dropped at T06 reframe (2026-04-20);
see ``design_docs/nice_to_have.md §9`` for the triggers that would
justify promoting it. The M4 MCP surface mirrors ``run`` / ``resume`` /
``list-runs``.

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
import json
from typing import Any

import typer

from ai_workflows.primitives.logging import configure_logging
from ai_workflows.primitives.storage import SQLiteStorage, default_storage_path
from ai_workflows.workflows._dispatch import (
    _CROCKFORD,
    ResumePreconditionError,
    UnknownTierError,
    UnknownWorkflowError,
    _generate_ulid,
)
from ai_workflows.workflows._dispatch import (
    resume_run as _dispatch_resume_run,
)
from ai_workflows.workflows._dispatch import (
    run_workflow as _dispatch_run_workflow,
)

__all__ = ["app"]

# Re-exports kept for test imports (M3 T04 tests import _generate_ulid +
# _CROCKFORD from cli directly). The implementation moved to
# ai_workflows.workflows._dispatch at M4 T02 when the dispatch helper
# was extracted; re-exporting avoids churn in the CLI test suite.
__all__ += ["_CROCKFORD", "_generate_ulid"]

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
    multi-command app. Commands revived across M3: ``run`` (T04),
    ``resume`` (T05), ``list-runs`` (T06). The T06 spec originally
    also paired ``cost-report``; that half was dropped at reframe
    (2026-04-20) and deferred to ``nice_to_have.md §9``. The MCP
    mirrors of these commands landed in M4 (`ai_workflows.mcp`).
    """


@app.command()
def version() -> None:
    """Print the installed ai-workflows package version."""
    from ai_workflows import __version__

    typer.echo(__version__)


# ---------------------------------------------------------------------------
# `aiw run`
# ---------------------------------------------------------------------------


def _parse_tier_overrides(entries: list[str]) -> dict[str, str]:
    """Parse repeatable ``--tier-override`` flags into a ``{logical: replacement}`` map.

    Each entry must match ``<logical>=<replacement>`` with non-empty
    halves. M5 T04: surface-boundary parsing only — unknown tier names
    are validated later, inside
    :func:`ai_workflows.workflows._dispatch.run_workflow`, so a
    repeated flag with an unknown tier yields the same
    :class:`UnknownTierError` path the MCP surface hits.
    ``typer.BadParameter`` is the Typer-native way to exit with code 2
    and a readable message; matches Typer's own handling of missing
    required options.
    """
    mapping: dict[str, str] = {}
    for raw in entries:
        if "=" not in raw:
            raise typer.BadParameter(
                f"--tier-override entry must be '<logical>=<replacement>' (got {raw!r})"
            )
        logical, replacement = raw.split("=", 1)
        if not logical or not replacement:
            raise typer.BadParameter(
                f"--tier-override entry must have non-empty sides (got {raw!r})"
            )
        mapping[logical] = replacement
    return mapping


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
    tier_override: list[str] = typer.Option(
        [],
        "--tier-override",
        help=(
            "Override a tier: --tier-override <logical>=<replacement>. "
            "Repeatable. Example: "
            "--tier-override planner-synth=planner-explorer."
        ),
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
    tier_overrides = _parse_tier_overrides(tier_override)
    asyncio.run(
        _run_async(
            workflow=workflow,
            goal=goal,
            context=context,
            max_steps=max_steps,
            budget_cap_usd=budget_cap_usd,
            run_id=run_id,
            tier_overrides=tier_overrides,
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
    tier_overrides: dict[str, str] | None = None,
) -> None:
    """Async body of ``aiw run``.

    Routes through :func:`ai_workflows.workflows._dispatch.run_workflow`
    (shared by the MCP ``run_workflow`` tool) and reformats the returned
    dict into the stdout contract M3 T04 pins: run id + gate handle on
    pause, plan JSON + total cost on completion, ``error: …`` on failure.
    """
    try:
        result = await _dispatch_run_workflow(
            workflow=workflow,
            inputs={"goal": goal, "context": context, "max_steps": max_steps},
            budget_cap_usd=budget_cap_usd,
            run_id=run_id,
            tier_overrides=tier_overrides,
        )
    except UnknownWorkflowError as exc:
        typer.echo(
            f"unknown workflow {exc.workflow!r}; registered: {exc.registered}",
            err=True,
        )
        raise typer.Exit(code=2) from None
    except UnknownTierError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from None

    _emit_cli_run_result(result)


def _emit_cli_run_result(result: dict[str, Any]) -> None:
    """Print the CLI run-result lines matching the M3 T04 stdout contract.

    Must remain byte-identical to the pre-T02 ``_emit_final_state``
    output — AC-5 of M4 T02 pins this via
    :mod:`tests/cli/test_run.py` regression.
    """
    status = result["status"]
    run_id = result["run_id"]
    if status == "pending":
        typer.echo(run_id)
        typer.echo("awaiting: gate")
        typer.echo(
            f"resume with: aiw resume {run_id} --gate-response <approved|rejected>"
        )
        return

    if status == "completed":
        plan = result["plan"]
        typer.echo(json.dumps(plan, indent=2))
        total_cost = result["total_cost_usd"] or 0.0
        typer.echo(f"total cost: ${total_cost:.4f}")
        return

    # errored
    typer.echo(f"error: {result['error']}", err=True)
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

    Routes through :func:`ai_workflows.workflows._dispatch.resume_run`
    (shared with the MCP ``resume_run`` tool) and reformats the returned
    dict into the stdout contract M3 T05 pins: run id + gate handle on
    re-pause, plan JSON + total cost on completion, rejection message
    on reject, ``error: …`` on failure.
    """
    try:
        result = await _dispatch_resume_run(
            run_id=run_id, gate_response=gate_response
        )
    except ResumePreconditionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from None
    except UnknownWorkflowError as exc:
        typer.echo(
            f"unknown workflow {exc.workflow!r}; registered: {exc.registered}",
            err=True,
        )
        raise typer.Exit(code=2) from None

    _emit_cli_resume_result(result)


def _emit_cli_resume_result(result: dict[str, Any]) -> None:
    """Print the CLI resume-result lines matching the M3 T05 stdout contract.

    Must remain byte-identical to the pre-T03 ``_emit_resume_final``
    output — M4 T03 AC-5 pins this via :mod:`tests/cli/test_resume.py`.
    """
    status = result["status"]
    run_id = result["run_id"]
    total = result["total_cost_usd"] or 0.0

    if status == "pending":
        typer.echo(run_id)
        typer.echo("awaiting: gate")
        typer.echo(
            f"resume with: aiw resume {run_id} --gate-response <approved|rejected>"
        )
        return

    if status == "gate_rejected":
        typer.echo(f"plan rejected by gate for run {run_id}")
        typer.echo(f"total cost: ${total:.4f}")
        raise typer.Exit(code=1)

    if status == "completed":
        plan = result["plan"]
        typer.echo(json.dumps(plan, indent=2))
        typer.echo(f"total cost: ${total:.4f}")
        return

    # errored
    message = result.get("error") or "resume produced no plan and no interrupt"
    typer.echo(f"error: {message}", err=True)
    raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# `aiw list-runs`
# ---------------------------------------------------------------------------


@app.command("list-runs")
def list_runs(
    workflow: str | None = typer.Option(
        None,
        "--workflow",
        "-w",
        help="Filter by workflow id (exact match).",
    ),
    status: str | None = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by run status (exact match).",
    ),
    limit: int = typer.Option(
        20,
        "--limit",
        "-n",
        min=1,
        max=500,
        help="Maximum rows to return (newest first).",
    ),
) -> None:
    """List recorded runs (newest first).

    Pure read over :meth:`SQLiteStorage.list_runs` (KDR-009 — the
    command never opens the checkpointer nor compiles a graph). The
    ``runs.total_cost_usd`` scalar stamped by ``aiw run`` / ``aiw
    resume`` is surfaced verbatim; ``NULL`` (pending runs or completed
    rows pre-dating the cost-stamping path) renders as ``—``. Filters
    on ``--workflow`` / ``--status`` are exact matches and compose
    with ``AND``.
    """
    configure_logging(level="INFO")
    asyncio.run(
        _list_runs_async(workflow=workflow, status=status, limit=limit)
    )


async def _list_runs_async(
    *,
    workflow: str | None,
    status: str | None,
    limit: int,
) -> None:
    """Async body of ``aiw list-runs``.

    Split out so the Typer command stays sync while the Storage API
    remains async (same pattern as ``_run_async`` / ``_resume_async``).
    """
    storage = await SQLiteStorage.open(default_storage_path())
    rows = await storage.list_runs(
        limit=limit,
        status_filter=status,
        workflow_filter=workflow,
    )
    _emit_list_runs_table(rows)


def _emit_list_runs_table(rows: list[dict[str, Any]]) -> None:
    """Print the fixed-width run table defined by the T06 spec.

    Column order: ``run_id | workflow | status | started_at | cost_usd``.
    ``cost_usd`` renders as ``$0.0033`` (4 dp) when ``total_cost_usd``
    is populated; ``—`` (em dash) when the column is ``NULL`` — the
    same dash rendering the spec's AC calls out.
    """
    headers = ("run_id", "workflow", "status", "started_at", "cost_usd")
    if not rows:
        typer.echo(" | ".join(headers))
        typer.echo("(no runs)")
        return

    formatted: list[tuple[str, ...]] = []
    for row in rows:
        cost_raw = row.get("total_cost_usd")
        cost_str = f"${cost_raw:.4f}" if cost_raw is not None else "—"
        formatted.append(
            (
                str(row.get("run_id", "")),
                str(row.get("workflow_id", "")),
                str(row.get("status", "")),
                str(row.get("started_at", "")),
                cost_str,
            )
        )

    widths = [len(h) for h in headers]
    for tup in formatted:
        for i, value in enumerate(tup):
            if len(value) > widths[i]:
                widths[i] = len(value)

    def _fmt(cols: tuple[str, ...]) -> str:
        return " | ".join(col.ljust(widths[i]) for i, col in enumerate(cols))

    typer.echo(_fmt(headers))
    for tup in formatted:
        typer.echo(_fmt(tup))


if __name__ == "__main__":  # pragma: no cover - manual invocation only
    app()
