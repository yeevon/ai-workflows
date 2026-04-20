"""``aiw`` — CLI surface for ai-workflows.

Commands are stubbed pending the LangGraph runtime (M3) and the MCP
surface (M4). M1 Task 11 reduces this module to the bare minimum that
keeps ``aiw --help`` and ``aiw version`` working; every command
removed from the pre-pivot substrate (``list-runs``, ``inspect``,
``resume``, ``run``) was bound to primitives whose shape is being
reworked by the LangGraph pivot — see
[architecture.md §4.4](../../design_docs/architecture.md) for the
target command surface and KDR-009 for the checkpointing model that
``resume`` will rehydrate from.

``TODO(M3)`` / ``TODO(M4)`` pointers below name the milestone that
will re-introduce each command.

Relationship to other modules
-----------------------------
* :mod:`ai_workflows` — the package ``__version__`` dunder read by
  ``aiw version``.
* :mod:`ai_workflows.primitives` / :mod:`ai_workflows.graph` /
  :mod:`ai_workflows.workflows` — deliberately not imported here.
  Under [architecture.md §3](../../design_docs/architecture.md) the
  ``surfaces`` layer consumes ``workflows`` + ``primitives``; this
  stub has no runtime surface yet, so importing either layer would
  only create coupling the M3/M4 rewrites will have to undo.
"""

from __future__ import annotations

import typer

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
    multi-command app (with a single command, ``aiw --help`` would
    otherwise render the ``version`` command's help). Commands
    removed by M1 Task 11 are listed as ``TODO(M3)`` / ``TODO(M4)``
    pointers at the bottom of this module.
    """


@app.command()
def version() -> None:
    """Print the installed ai-workflows package version."""
    from ai_workflows import __version__

    typer.echo(__version__)


# TODO(M3): `run <workflow> <inputs>` — drive a LangGraph StateGraph via
#   the workflows registry (architecture.md §4.4, KDR-001).
# TODO(M3): `resume <run_id> [--gate-response ...]` — rehydrate from
#   LangGraph's SqliteSaver checkpoint (architecture.md §4.4, KDR-009).
# TODO(M3): `list-runs` — query Storage.list_runs (architecture.md §4.1,
#   §4.4).
# TODO(M3): `cost-report <run_id>` — CostTracker rollup
#   (architecture.md §4.1, §4.4).
# TODO(M4): mirror `run` / `resume` / `list-runs` / `cost-report` as
#   FastMCP tools under ``ai_workflows.mcp`` (architecture.md §4.4,
#   KDR-002, KDR-008).


if __name__ == "__main__":  # pragma: no cover - manual invocation only
    app()
