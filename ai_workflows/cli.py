"""Top-level command-line interface for ai-workflows.

Exposes the ``aiw`` console script declared in ``pyproject.toml``. In Task 01
this is a minimal shell that only prints help text — subcommands such as
``run``, ``resume``, ``list-runs``, and ``inspect`` are wired in by Task 12
(CLI primitives) once the underlying primitives exist.

The entry point is :data:`app`, a :class:`typer.Typer` instance. Typer
auto-generates ``--help`` from the registered commands and their docstrings,
which is what satisfies the Task 01 acceptance criterion ``aiw --help``.
"""

from __future__ import annotations

import typer

# A single shared Typer app. Subcommand groups (e.g. ``aiw runs ...``) will
# be registered as sub-Typer instances via ``app.add_typer(...)`` in later
# tasks. ``no_args_is_help=True`` means bare ``aiw`` prints help instead of
# silently exiting — friendlier first-run UX.
app = typer.Typer(
    name="aiw",
    help="ai-workflows — run and inspect composable AI workflows.",
    no_args_is_help=True,
    add_completion=False,
)


# NOTE: Typer collapses a single-command app into that command's help, which
# makes ``aiw --help`` print ``Usage: version ...`` instead of ``Usage: aiw
# ...``. Registering a no-op callback forces multi-command mode so ``aiw``
# keeps its own top-level help surface as subcommands are added in later
# tasks. ``invoke_without_command=True`` lets bare ``aiw`` fall through to
# Typer's ``no_args_is_help`` behaviour instead of erroring.
@app.callback(invoke_without_command=True)
def _root(ctx: typer.Context) -> None:
    """ai-workflows — run and inspect composable AI workflows."""
    # The callback body is intentionally empty; Typer handles help/routing.
    return None


@app.command()
def version() -> None:
    """Print the installed ai-workflows package version."""
    from ai_workflows import __version__

    typer.echo(__version__)


if __name__ == "__main__":  # pragma: no cover - manual invocation only
    app()
