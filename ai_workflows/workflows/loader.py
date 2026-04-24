"""External workflow module discovery (M16 Task 01).

Downstream consumers register their own workflow modules by dotted
Python path via :data:`AIW_EXTRA_WORKFLOW_MODULES` (env var,
comma-separated) or ``--workflow-module`` (repeatable CLI flag on
``aiw`` and ``aiw-mcp``). Each entry is imported once at startup via
:func:`importlib.import_module`; the module's top-level
:func:`ai_workflows.workflows.register` call fires as a side effect
and populates the existing registry.

User code is user-owned (KDR-013 / ADR-0007): this module surfaces
:class:`ExternalWorkflowImportError` on an import failure, naming the
dotted path + the underlying cause, but does not lint, test, or
sandbox the imported module.

Relationship to other modules
-----------------------------
* :mod:`ai_workflows.workflows` — the registry the loader populates
  through each module's top-level :func:`register` call.
* :mod:`ai_workflows.workflows._dispatch` — consults the registry
  first at dispatch time so external modules route correctly even
  though their module path is outside ``ai_workflows.workflows.*``.
* :mod:`ai_workflows.cli` + :mod:`ai_workflows.mcp.__main__` — the
  two surfaces that invoke :func:`load_extra_workflow_modules` at
  startup, after ``load_dotenv`` and before any subcommand body.

Layer rule: loader sits in the workflows layer. It imports stdlib +
``ai_workflows.workflows`` only, so no upward coupling to the graph
or primitives layers.
"""

from __future__ import annotations

import contextlib
import importlib
import os
import pkgutil
from collections.abc import Iterable

__all__ = [
    "ENV_VAR_NAME",
    "ExternalWorkflowImportError",
    "load_extra_workflow_modules",
]

ENV_VAR_NAME = "AIW_EXTRA_WORKFLOW_MODULES"


class ExternalWorkflowImportError(ImportError):
    """Raised when a module named via ``AIW_EXTRA_WORKFLOW_MODULES`` or
    ``--workflow-module`` fails to import.

    Wraps the underlying ``ImportError`` / ``ModuleNotFoundError`` /
    arbitrary ``Exception`` so the caller surfaces a single actionable
    message naming the dotted path + the chained cause. Subclasses
    :class:`ImportError` so existing ``except ImportError`` handlers
    compose without change.
    """

    def __init__(self, module_path: str, cause: BaseException) -> None:
        super().__init__(
            f"failed to import external workflow module {module_path!r}: "
            f"{type(cause).__name__}: {cause}"
        )
        self.module_path = module_path
        self.__cause__ = cause


def load_extra_workflow_modules(
    *, cli_modules: Iterable[str] | None = None
) -> list[str]:
    """Import each named external workflow module so its ``register(...)`` fires.

    Module sources, in import order:

      1. :data:`ENV_VAR_NAME` (``AIW_EXTRA_WORKFLOW_MODULES``) —
         comma-separated dotted paths from the environment. Whitespace
         around each entry is trimmed; empty entries from trailing
         commas or repeated separators are skipped silently.
      2. ``cli_modules`` — the CLI-flag list (``--workflow-module`` on
         ``aiw`` / ``aiw-mcp``). Same trim + empty-skip treatment.

    CLI entries land *after* env entries so a ``--workflow-module``
    flag can extend an env-var baseline. :func:`importlib.import_module`
    is idempotent via Python's ``sys.modules`` cache, and
    :func:`ai_workflows.workflows.register` is idempotent on identical
    re-registration — so calling this function twice in the same
    process (test harnesses doing ``CliRunner.invoke`` back-to-back)
    is a no-op for already-loaded entries.

    If any entries are configured, in-package workflows are eagerly
    pre-imported so their :func:`register` calls populate the registry
    first. That makes the existing :func:`register` collision check
    (``ValueError`` on re-binding) fire reliably when an external
    module tries to register a shipped name — "in-package workflows
    cannot be shadowed" stays load-bearing (KDR-013). When no external
    entries are configured, nothing is imported (the shipped lazy-load
    path is preserved).

    Returns the list of module paths the loader successfully imported,
    in import order.

    Raises :class:`ExternalWorkflowImportError` on the first failed
    import. Earlier entries have already executed their top-level
    side effects in ``sys.modules`` — Python's import system does not
    roll back partial loads and this function does not fake atomicity.
    """
    modules: list[str] = list(_parse_env_entries(os.environ.get(ENV_VAR_NAME, "")))
    if cli_modules is not None:
        for entry in cli_modules:
            stripped = entry.strip()
            if stripped:
                modules.append(stripped)

    if not modules:
        return []

    _eager_import_shipped_workflows()

    imported: list[str] = []
    for dotted in modules:
        try:
            importlib.import_module(dotted)
        except Exception as exc:  # noqa: BLE001 — wrap everything into ExternalWorkflowImportError
            raise ExternalWorkflowImportError(dotted, exc) from exc
        imported.append(dotted)
    return imported


def _parse_env_entries(raw: str) -> list[str]:
    """Split the env-var value into non-empty trimmed dotted paths.

    Accepts comma-separated entries; surrounding whitespace is
    trimmed and empty entries (from trailing commas or ``",,"``) are
    skipped silently.
    """
    return [entry.strip() for entry in raw.split(",") if entry.strip()]


def _eager_import_shipped_workflows() -> None:
    """Import every in-package workflow module so their ``register()`` fires.

    Iterates the ``ai_workflows.workflows`` package via
    :func:`pkgutil.iter_modules` and imports each non-underscore entry
    (skipping private helpers like ``_dispatch`` and this module's
    own ``loader``). A :class:`ModuleNotFoundError` on any single
    module is swallowed — the existing dispatch-time lazy-import
    fallback will surface a proper error if the user later names it
    in ``aiw run``.

    Guaranteeing shipped workflows register *before* external ones
    keeps the :func:`ai_workflows.workflows.register` collision check
    meaningful: an external module that calls ``register("planner", …)``
    then hits the existing ``ValueError`` rather than silently
    shadowing. Without this pre-load, shipped workflows would only
    register lazily on first dispatch, and an external module could
    register a shipped name freely (dispatch would then route to the
    external module).

    **Startup-cost note:** this function is the reason any ``aiw`` or
    ``aiw-mcp`` invocation *with* an external entry configured pays
    the shipped-workflow import cost (~100ms of LangGraph-pulling
    ``planner`` + ``slice_refactor`` imports) at startup rather than
    on first dispatch. Invocations with no external entry bypass this
    call entirely and preserve the lazy-import path.
    """
    import ai_workflows.workflows as pkg

    for module_info in pkgutil.iter_modules(pkg.__path__):
        name = module_info.name
        if name.startswith("_") or name == "loader":
            continue
        with contextlib.suppress(ModuleNotFoundError):
            importlib.import_module(f"ai_workflows.workflows.{name}")
