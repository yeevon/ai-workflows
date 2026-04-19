"""Top-level command-line interface for ai-workflows.

Exposes the ``aiw`` console script declared in ``pyproject.toml``. Task 01
shipped the bare Typer app and the ``version`` command; M1 Task 12 wires
the primitive commands that validate the storage + cost tracking layer:

* ``aiw list-runs`` — tabular listing of the most recent runs.
* ``aiw inspect <run_id>`` — per-run drill-down (status, dir-hash drift,
  budget, per-task breakdown, per-call usage table).
* ``aiw resume <run_id>`` — placeholder summary (full implementation in
  Milestone 4; the stub exists so the SQLite queries are exercised).
* ``aiw run <workflow>`` — placeholder (full implementation lands in
  Milestone 3 with the Orchestrator).

Global options (``--log-level``, ``--db-path``) attach to the root
callback and flow into every subcommand via the Typer context object.

Relationship to other modules
-----------------------------
* :mod:`ai_workflows.primitives.storage` — ``SQLiteStorage`` owns the
  reads (``get_run``, ``list_runs``, ``get_tasks``, ``list_llm_calls``,
  ``get_cost_breakdown``, ``get_total_cost``).
* :mod:`ai_workflows.primitives.workflow_hash` — ``aiw inspect`` uses
  :func:`compute_workflow_hash` to flag workflow-directory drift (CRIT-02)
  when ``--workflow-dir`` is supplied.
* :mod:`ai_workflows.primitives.logging` — ``configure_logging`` is
  invoked from the root callback so the chosen ``--log-level`` is
  honoured for every subcommand.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import typer

from ai_workflows.primitives.logging import configure_logging
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.workflow_hash import compute_workflow_hash


class LogLevel(StrEnum):
    """Valid ``--log-level`` choices, mirroring :mod:`logging` level names."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


DEFAULT_DB_PATH = Path.home() / ".ai-workflows" / "runs.db"
"""Default SQLite path. Tests override via ``--db-path``."""

_MAX_WORKFLOW_WIDTH = 22
"""Column width cap for workflow names in ``aiw list-runs`` (spec)."""


app = typer.Typer(
    name="aiw",
    help="ai-workflows — run and inspect composable AI workflows.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    log_level: LogLevel = typer.Option(
        LogLevel.INFO,
        "--log-level",
        help="Logging level for the CLI run.",
        case_sensitive=False,
    ),
    db_path: Path | None = typer.Option(
        None,
        "--db-path",
        help=f"Override the default SQLite path ({DEFAULT_DB_PATH}).",
    ),
) -> None:
    """ai-workflows — run and inspect composable AI workflows."""
    configure_logging(level=log_level.value)
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db_path if db_path is not None else DEFAULT_DB_PATH
    ctx.obj["log_level"] = log_level.value


@app.command()
def version() -> None:
    """Print the installed ai-workflows package version."""
    from ai_workflows import __version__

    typer.echo(__version__)


# ---------------------------------------------------------------------------
# list-runs
# ---------------------------------------------------------------------------


@app.command("list-runs")
def list_runs(
    ctx: typer.Context,
    limit: int = typer.Option(
        50, "--limit", help="Max rows to render (newest first)."
    ),
) -> None:
    """Tabular listing of the most recent workflow runs."""
    db_path: Path = ctx.obj["db_path"]
    rows = asyncio.run(_load_runs(db_path, limit))
    typer.echo(_render_list_runs(rows))


async def _load_runs(db_path: Path, limit: int) -> list[dict[str, Any]]:
    storage = await SQLiteStorage.open(db_path)
    return await storage.list_runs(limit=limit)


def _render_list_runs(rows: list[dict[str, Any]]) -> str:
    """Render ``rows`` as a fixed-width text table matching the spec."""
    header = f"{'RUN ID':<10}{'WORKFLOW':<{_MAX_WORKFLOW_WIDTH + 2}}" \
        f"{'STATUS':<12}{'COST':<10}{'STARTED':<16}"
    if not rows:
        return header + "\n(no runs)"
    lines = [header]
    for row in rows:
        run_id = _truncate(str(row.get("run_id", "")), 8)
        workflow = _truncate(str(row.get("workflow_id", "")), _MAX_WORKFLOW_WIDTH)
        status = _truncate(str(row.get("status", "")), 10)
        cost = _format_cost(row.get("total_cost_usd"))
        started = _format_timestamp(row.get("started_at"))
        lines.append(
            f"{run_id:<10}{workflow:<{_MAX_WORKFLOW_WIDTH + 2}}"
            f"{status:<12}{cost:<10}{started:<16}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------


@app.command()
def inspect(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run identifier."),
    workflow_dir: Path | None = typer.Option(
        None,
        "--workflow-dir",
        help="Re-hash this directory to flag drift against the stored hash.",
    ),
) -> None:
    """Drill-down: status, dir-hash drift, budget, task + call breakdowns."""
    db_path: Path = ctx.obj["db_path"]
    payload = asyncio.run(_load_inspect(db_path, run_id))
    if payload is None:
        typer.echo(f"Run not found: {run_id}", err=True)
        raise typer.Exit(code=1)
    typer.echo(_render_inspect(payload, workflow_dir))


async def _load_inspect(
    db_path: Path, run_id: str
) -> dict[str, Any] | None:
    storage = await SQLiteStorage.open(db_path)
    run = await storage.get_run(run_id)
    if run is None:
        return None
    tasks = await storage.get_tasks(run_id)
    calls = await storage.list_llm_calls(run_id)
    breakdown = await storage.get_cost_breakdown(run_id)
    total_cost = await storage.get_total_cost(run_id)
    return {
        "run": run,
        "tasks": tasks,
        "calls": calls,
        "breakdown": breakdown,
        "total_cost": total_cost,
    }


def _render_inspect(
    payload: dict[str, Any], workflow_dir: Path | None
) -> str:
    run = payload["run"]
    tasks: list[dict[str, Any]] = payload["tasks"]
    calls: list[dict[str, Any]] = payload["calls"]
    breakdown: dict[str, float] = payload["breakdown"]
    total_cost: float = payload["total_cost"]

    lines: list[str] = []
    lines.append(f"Run: {run['run_id']}")
    lines.append(f"Workflow: {run['workflow_id']}")
    lines.append(_render_dir_hash_line(run.get("workflow_dir_hash"), workflow_dir))
    lines.append(f"Status: {run.get('status', '')}")
    lines.append(_render_budget_line(total_cost, run.get("budget_cap_usd")))
    lines.append(_render_time_line(run.get("started_at"), run.get("finished_at")))
    lines.append("")

    lines.append("Tasks:")
    if not tasks:
        lines.append("  (none)")
    else:
        task_costs = _per_task_costs(calls)
        for task in tasks:
            task_id = _truncate(str(task.get("task_id", "")), 24)
            status = _truncate(str(task.get("status", "")), 12)
            component = _truncate(str(task.get("component", "")), 14)
            cost = _format_cost(task_costs.get(task.get("task_id"), 0.0))
            lines.append(
                f"  {task_id:<24}{status:<12}{component:<14}{cost}"
            )
    lines.append("")

    lines.append(f"LLM Calls: {len(calls)} total")
    lines.append(_render_call_table(calls))
    if breakdown:
        pieces = " ".join(
            f"{comp}={_format_cost(val)}" for comp, val in sorted(breakdown.items())
        )
        lines.append(f"Cost breakdown: {pieces}")
    else:
        lines.append("Cost breakdown: (none)")
    return "\n".join(lines)


def _render_dir_hash_line(
    stored_hash: str | None, workflow_dir: Path | None
) -> str:
    """Render the ``Dir hash`` line, flagging drift when a path is supplied."""
    short = (stored_hash or "")[:12]
    if workflow_dir is None:
        return f"Dir hash: {short}...  (pass --workflow-dir to compare)"
    try:
        current = compute_workflow_hash(workflow_dir)
    except (FileNotFoundError, NotADirectoryError) as exc:
        return f"Dir hash: {short}...  (current match: ERROR — {exc})"
    marker = "OK" if current == stored_hash else "MISMATCH"
    return f"Dir hash: {short}...  (current match: {marker})"


def _render_budget_line(total: float, cap: float | None) -> str:
    """Format the Budget line per carry-over ``M1-T09-ISS-02``."""
    if cap is None:
        return f"Budget: {_format_cost(total)} (no cap)"
    pct = 0 if cap == 0 else int(round(total / cap * 100))
    return f"Budget: {_format_cost(total)} / {_format_cost(cap)} ({pct}% used)"


def _render_time_line(started_at: str | None, finished_at: str | None) -> str:
    started = _format_timestamp(started_at)
    if not finished_at:
        return f"Started: {started}"
    finished = _format_timestamp(finished_at)
    duration = _format_duration(started_at, finished_at)
    suffix = f" ({duration})" if duration else ""
    return f"Started: {started}  Finished: {finished}{suffix}"


def _render_call_table(calls: list[dict[str, Any]]) -> str:
    """Per-call usage table including ``cache_read`` / ``cache_write``.

    Carry-over ``M1-T04-ISS-01`` requires the cache columns to be visible
    through ``aiw inspect``. Even when zero, the column headers surface the
    field names so downstream tooling (and the CLI-level grep test in the
    carry-over) can find them.
    """
    header = (
        f"  {'MODEL':<22}{'IN':>8}{'OUT':>8}"
        f"{'cache_read':>12}{'cache_write':>12}{'COST':>10}"
    )
    if not calls:
        return header + "\n  (no calls)"
    lines = [header]
    for call in calls:
        model = _truncate(str(call.get("model", "")), 22)
        in_tok = _int_or_zero(call.get("input_tokens"))
        out_tok = _int_or_zero(call.get("output_tokens"))
        cache_read = _int_or_zero(call.get("cache_read_tokens"))
        cache_write = _int_or_zero(call.get("cache_write_tokens"))
        cost = _format_cost(call.get("cost_usd"))
        lines.append(
            f"  {model:<22}{in_tok:>8}{out_tok:>8}"
            f"{cache_read:>12}{cache_write:>12}{cost:>10}"
        )
    return "\n".join(lines)


def _per_task_costs(calls: list[dict[str, Any]]) -> dict[str | None, float]:
    totals: dict[str | None, float] = {}
    for call in calls:
        if call.get("is_local"):
            continue
        key = call.get("task_id")
        totals[key] = totals.get(key, 0.0) + float(call.get("cost_usd") or 0.0)
    return totals


# ---------------------------------------------------------------------------
# resume (stub)
# ---------------------------------------------------------------------------


@app.command()
def resume(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run identifier."),
) -> None:
    """Print a resume summary (full implementation lands in Milestone 4)."""
    db_path: Path = ctx.obj["db_path"]
    run = asyncio.run(_load_run(db_path, run_id))
    if run is None:
        typer.echo(f"Run not found: {run_id}", err=True)
        raise typer.Exit(code=1)
    lines = [
        f"Resume for run {run['run_id']}",
        f"Workflow: {run['workflow_id']}",
        f"Status: {run.get('status', '')}",
        "Tasks that would re-run: (none — stub; Milestone 4)",
        "Workflow hash: stored — pass `aiw inspect --workflow-dir` to compare.",
        "",
        "Full resume available in Milestone 4.",
    ]
    typer.echo("\n".join(lines))


async def _load_run(db_path: Path, run_id: str) -> dict[str, Any] | None:
    storage = await SQLiteStorage.open(db_path)
    return await storage.get_run(run_id)


# ---------------------------------------------------------------------------
# run (stub)
# ---------------------------------------------------------------------------


@app.command()
def run(
    ctx: typer.Context,
    workflow: str = typer.Argument(..., help="Workflow identifier."),
    profile: str | None = typer.Option(
        None, "--profile", help="Profile name (forward-compat; no-op at M1)."
    ),
) -> None:
    """Placeholder — coming in Milestone 3."""
    del ctx, workflow, profile  # forward-compat accepted + ignored at M1
    typer.echo("Not yet implemented — coming in Milestone 3.")


# ---------------------------------------------------------------------------
# Small formatting helpers
# ---------------------------------------------------------------------------


def _truncate(value: str, width: int) -> str:
    """Return ``value`` truncated to ``width`` chars (no ellipsis)."""
    return value if len(value) <= width else value[:width]


def _format_cost(value: Any) -> str:
    """Format a USD cost as ``$X.XX``; ``None`` renders as ``$0.00``."""
    try:
        amount = float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        amount = 0.0
    return f"${amount:.2f}"


def _format_timestamp(value: Any) -> str:
    """Render an ISO-8601 timestamp as ``YYYY-MM-DD HH:MM`` (UTC wall clock)."""
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        return str(value)
    return dt.strftime("%Y-%m-%d %H:%M")


def _format_duration(started: str | None, finished: str | None) -> str:
    """Return a compact ``HhMm`` or ``Nm`` duration string, or empty on error."""
    if not started or not finished:
        return ""
    try:
        start = datetime.fromisoformat(str(started))
        end = datetime.fromisoformat(str(finished))
    except ValueError:
        return ""
    delta = end - start
    total_seconds = int(delta.total_seconds())
    if total_seconds < 0:
        return ""
    minutes, _ = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes}m"
    return f"{minutes}m"


def _int_or_zero(value: Any) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


if __name__ == "__main__":  # pragma: no cover - manual invocation only
    app()
