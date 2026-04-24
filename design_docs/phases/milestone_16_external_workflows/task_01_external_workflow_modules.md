# Task 01 — `AIW_EXTRA_WORKFLOW_MODULES` loader + `--workflow-module` flag

**Status:** 📝 Planned.
**Grounding:** [milestone README](README.md) · [ai_workflows/workflows/__init__.py](../../../ai_workflows/workflows/__init__.py) (`register()` + `_REGISTRY`) · [ai_workflows/workflows/_dispatch.py:202-217](../../../ai_workflows/workflows/_dispatch.py#L202-L217) (`_import_workflow_module`) · [ai_workflows/cli.py:104-115](../../../ai_workflows/cli.py#L104-L115) (root Typer callback) · [ai_workflows/mcp/__main__.py:60-110](../../../ai_workflows/mcp/__main__.py#L60-L110) (MCP Typer entry).

## What to Build

A startup-time dotted-module loader. Two input sources (env var + repeatable CLI flag), one `importlib.import_module()` call per entry, `register()` side effects at module top level populate the existing registry. Dispatch is taught to route to the external module when the name is already in `_REGISTRY`. Entire milestone ships in one task.

## Deliverables

### 1. New module `ai_workflows/workflows/loader.py`

Lives in the workflows layer (alongside `_dispatch.py` + `__init__.py`). Imports stdlib + `ai_workflows.workflows` only — no graph or primitives imports needed.

```python
"""M16 Task 01 — external workflow module discovery.

Downstream consumers register their own workflow modules by dotted
Python path via ``AIW_EXTRA_WORKFLOW_MODULES`` (env var,
comma-separated) or ``--workflow-module`` (repeatable CLI flag on
``aiw`` and ``aiw-mcp``). Each entry is imported once at startup via
:func:`importlib.import_module`; the module's top-level
:func:`ai_workflows.workflows.register` call fires as a side effect
and populates the existing registry.

User code is user-owned (KDR-013 / ADR-0007): this module surfaces
``ExternalWorkflowImportError`` on an import failure, naming the
dotted path + the underlying cause, but does not lint, test, or
sandbox the imported module.
"""
from __future__ import annotations

import importlib
import os
from collections.abc import Iterable

__all__ = ["ExternalWorkflowImportError", "load_extra_workflow_modules"]

ENV_VAR_NAME = "AIW_EXTRA_WORKFLOW_MODULES"


class ExternalWorkflowImportError(ImportError):
    """Raised when a module named in AIW_EXTRA_WORKFLOW_MODULES or
    passed via --workflow-module fails to import.

    Wraps the underlying ``ImportError`` / ``ModuleNotFoundError`` /
    arbitrary ``Exception`` so the caller sees a single actionable
    message naming the dotted path + the chained cause.
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
    """Import each named module so its ``register(...)`` calls fire.

    Module sources, in import order:

      1. ``AIW_EXTRA_WORKFLOW_MODULES`` — comma-separated dotted paths
         from the environment.
      2. ``cli_modules`` — the CLI-flag list (``--workflow-module`` on
         ``aiw`` / ``aiw-mcp``).

    CLI entries land *after* env entries so a ``--workflow-module``
    flag can extend an env-var baseline. Python's ``sys.modules``
    cache makes repeat imports of the same dotted path idempotent;
    :func:`ai_workflows.workflows.register` handles identical
    re-registration as a no-op.

    Returns the list of module paths the loader successfully imported,
    in import order.

    Raises :class:`ExternalWorkflowImportError` on the first failed
    import. Earlier entries have already executed their top-level
    side effects in ``sys.modules`` — Python's import system does not
    roll back partial loads, and the loader does not fake atomicity.
    """
    modules: list[str] = []
    for entry in _parse_env_entries(os.environ.get(ENV_VAR_NAME, "")):
        modules.append(entry)
    if cli_modules is not None:
        for entry in cli_modules:
            stripped = entry.strip()
            if stripped:
                modules.append(stripped)

    imported: list[str] = []
    for dotted in modules:
        try:
            importlib.import_module(dotted)
        except Exception as exc:  # noqa: BLE001 — the intent is "wrap everything"
            raise ExternalWorkflowImportError(dotted, exc) from exc
        imported.append(dotted)
    return imported


def _parse_env_entries(raw: str) -> list[str]:
    """Return comma-separated dotted paths, trimmed + empty-skipped."""
    return [e.strip() for e in raw.split(",") if e.strip()]
```

**Design notes:**

- `ExternalWorkflowImportError` subclasses `ImportError` so existing `except ImportError` handlers in caller code compose without change.
- The `try: importlib.import_module(dotted) except Exception: raise ExternalWorkflowImportError(...)` shape deliberately catches `Exception` (not just `ImportError`): a user module with a clean dotted path but a top-level `raise RuntimeError("boom")` should produce the same "which module failed + why" surface as a `ModuleNotFoundError`.
- `__cause__` wiring (via `raise ... from exc` + the explicit `self.__cause__ = cause` in `__init__`) gives the CLI's Typer exception handler a full chained traceback for `--help`-less users while keeping the primary message short.
- No logging inside the loader — failures surface via exception, successes are silent. The CLI and MCP entry points already own their structlog setup; the loader does not duplicate.

### 2. `ai_workflows/workflows/__init__.py` — re-export the loader surface

Extend `__all__` + add re-exports so external callers (and tests) import from the package root:

```python
from ai_workflows.workflows.loader import (
    ExternalWorkflowImportError,
    load_extra_workflow_modules,
)

__all__ = [
    "WorkflowBuilder",
    "register",
    "get",
    "list_workflows",
    "ExternalWorkflowImportError",
    "load_extra_workflow_modules",
]
```

### 3. Dispatch routing extension — `ai_workflows/workflows/_dispatch.py`

Extend [`_import_workflow_module`](../../../ai_workflows/workflows/_dispatch.py#L202-L217) to check the registry first:

```python
def _import_workflow_module(workflow: str) -> Any:
    """Return the module object for a registered workflow.

    M16 Task 01: external workflows loaded via
    :func:`ai_workflows.workflows.load_extra_workflow_modules` at
    startup already populated ``_REGISTRY`` from their own dotted
    paths (e.g. ``cs300.workflows.question_gen``). For those,
    resolving ``ai_workflows.workflows.<workflow>`` would
    ``ModuleNotFoundError``; instead return the builder's source
    module from ``sys.modules`` so
    :func:`_resolve_tier_registry` can find
    ``<workflow>_tier_registry()`` on it.

    In-package workflows preserve their lazy-import fallback: the
    first dispatch call for ``planner`` imports
    ``ai_workflows.workflows.planner``, which triggers the module's
    top-level ``register("planner", build_planner)`` call.
    """
    existing = workflows._REGISTRY.get(workflow)
    if existing is not None:
        module_name = existing.__module__
        module = sys.modules.get(module_name)
        if module is not None:
            return module
        # Fallthrough: if the registered builder's module has somehow
        # been evicted from sys.modules (unusual; explicit del or a
        # reload gone wrong), re-import via its dotted path.
        return importlib.import_module(module_name)

    module_path = f"ai_workflows.workflows.{workflow}"
    try:
        return importlib.import_module(module_path)
    except ModuleNotFoundError:
        with contextlib.suppress(ModuleNotFoundError):
            importlib.import_module("ai_workflows.workflows.planner")
        raise UnknownWorkflowError(workflow, workflows.list_workflows()) from None
```

Add `import sys` to the dispatch module if not already present.

**Why `builder.__module__` over a parallel `_WORKFLOW_MODULES` dict:** a dedicated dict would duplicate state. `builder.__module__` is the standard Python attribute every function carries; `sys.modules[name]` is the standard module registry. No new bookkeeping.

### 4. CLI wiring — `ai_workflows/cli.py`

Extend the root `@app.callback()` to accept repeatable `--workflow-module` options and call `load_extra_workflow_modules()` after `configure_logging()` (but before any subcommand body — the root callback runs before each subcommand). Typer's root-callback pattern:

```python
@app.callback()
def _root(
    workflow_module: list[str] = typer.Option(
        [],
        "--workflow-module",
        help=(
            "Dotted Python path of an extra workflow module to import at "
            "startup (repeatable). Composes with AIW_EXTRA_WORKFLOW_MODULES "
            "— env entries import first, then --workflow-module entries. "
            "The module must be importable via the interpreter's sys.path "
            "and is expected to call ai_workflows.workflows.register(...) "
            "at module top level. See docs/writing-a-workflow.md."
        ),
    ),
) -> None:
    """ai-workflows CLI.

    Root callback: loads dotenv, configures logging, and imports any
    extra workflow modules named via ``AIW_EXTRA_WORKFLOW_MODULES`` or
    ``--workflow-module`` before the subcommand runs. Typer calls the
    root callback once per invocation regardless of which subcommand
    fires, so external registration is live for ``run`` / ``resume`` /
    ``list-runs`` / ``eval *`` alike.
    """
    from ai_workflows.workflows import load_extra_workflow_modules

    try:
        load_extra_workflow_modules(cli_modules=workflow_module)
    except ExternalWorkflowImportError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from None
```

Import `ExternalWorkflowImportError` at the top of the module (under the existing `# noqa: E402` block) alongside the other workflow-layer imports.

**Note on subcommand-specific `configure_logging()` calls:** individual `@app.command()` bodies currently call `configure_logging(level="INFO")` themselves (see `run()` / `resume()` / `list_runs()` / `eval_capture()` / `eval_run()`). The root callback does **not** need to call `configure_logging()` — the subcommand owns that. The loader is called in the root callback because its result (pre-loaded modules) must be visible to every subcommand.

### 5. MCP wiring — `ai_workflows/mcp/__main__.py`

Extend the `_cli` Typer command to accept the same flag and call the loader after `configure_logging()` + before `build_server()`:

```python
@app.command()
def _cli(
    transport: str = typer.Option(...),
    host: str = typer.Option(...),
    port: int = typer.Option(...),
    cors_origin: list[str] = typer.Option(...),
    workflow_module: list[str] = typer.Option(
        [],
        "--workflow-module",
        help=(
            "Dotted Python path of an extra workflow module to import "
            "at server startup (repeatable). Composes with "
            "AIW_EXTRA_WORKFLOW_MODULES. See the CLI help for details."
        ),
    ),
) -> None:
    if transport not in ("stdio", "http"):
        raise typer.BadParameter(...)

    configure_logging(level="INFO")

    from ai_workflows.workflows import (
        ExternalWorkflowImportError,
        load_extra_workflow_modules,
    )

    try:
        load_extra_workflow_modules(cli_modules=workflow_module)
    except ExternalWorkflowImportError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from None

    server = build_server()
    # ... existing transport dispatch ...
```

### 6. KDR-013 + ADR-0007

**`design_docs/architecture.md` §9 KDR table** — add row:

> KDR-013 | External workflow module discovery via `AIW_EXTRA_WORKFLOW_MODULES` (env, comma-separated) and `--workflow-module` (CLI, repeatable) — dotted Python module paths, not filesystem paths. Loading uses `importlib.import_module`; user modules are expected to call `ai_workflows.workflows.register(...)` at module top level. User code is owned by the user — ai-workflows does not lint, test, or sandbox it. Dispatch consults `_REGISTRY` before falling back to in-package import so external modules route correctly. Entry-point discovery and directory-scan loaders are deferred to separate milestones with their own triggers. | [ADR-0007](adr/0007_user_owned_code_contract.md), §4.2

**`design_docs/adr/0007_user_owned_code_contract.md`** — new ADR. Include:

- **Context.** CS-300 (first downstream consumer) needs to register its own workflow modules against `aiw-mcp --transport http` without forking.
- **Decision.** Dotted-path `importlib.import_module` loader via env var + CLI flag; user code owns its own risk surface; framework raises `ExternalWorkflowImportError` on import failure but does not gate / lint / sandbox.
- **Rejected alternatives** (with the trigger that would re-open each):
  - *Entry-point discovery* — re-opens when a consumer wants to pip-publish a distributable workflow package.
  - *Directory scan (`AIW_WORKFLOWS_PATH`)* — re-opens if a consumer asks for loose `.py` file authoring without a package layout (CS-300 explicitly did not want this).
  - *Full plugin protocol / sandboxing* — re-opens under multi-tenant hosting.
- **Consequences.** New failure mode (`ExternalWorkflowImportError`); dispatch has a new code path (registry-first); user code collisions with in-package workflows fail loudly via the existing `register()` `ValueError`.

### 7. Tests

**`tests/workflows/test_external_module_loader.py`** (new) — six tests. Hermetic: uses `tmp_path` + `sys.path` + `monkeypatch.setenv` to create and register a stub module. Does **not** invoke any workflow dispatch.

- `test_env_var_unset_returns_empty_list` — no env, no CLI → `load_extra_workflow_modules()` returns `[]`.
- `test_single_env_entry_imports_and_registers` — write `stub_wf.py` at `tmp_path / "stub_wf.py"`, call `register("stub_wf", <builder>)` at module top level; `monkeypatch.setenv(ENV_VAR_NAME, "stub_wf")` + `monkeypatch.syspath_prepend(tmp_path)`; assert the return list has `["stub_wf"]` and `"stub_wf" in workflows.list_workflows()`.
- `test_comma_separated_entries_import_all` — two stub modules, env set to `"stub_a,stub_b"`; both registered.
- `test_cli_entries_compose_with_env` — env has `stub_a`, `cli_modules=["stub_b"]`; return list is `["stub_a", "stub_b"]` in that order.
- `test_import_failure_raises_external_workflow_import_error` — env names a non-existent module; assert `ExternalWorkflowImportError` raised, `.module_path == "nonexistent"`, `.__cause__` is a `ModuleNotFoundError`.
- `test_idempotent_reload` — call `load_extra_workflow_modules()` twice with the same env; second call returns the same list; no exception. Validates that `register()`'s identical-re-registration no-op holds.

**`tests/cli/test_external_workflow.py`** (new) — one test. Writes a stub workflow module with a complete `register(...)` + `<workflow>_tier_registry` pair at `tmp_path / "stub_cli_wf.py"`; `monkeypatch.syspath_prepend(tmp_path)` + `monkeypatch.setenv("AIW_EXTRA_WORKFLOW_MODULES", "stub_cli_wf")`. Invokes `CliRunner.invoke(cli.app, ["run", "stub_cli_wf", "--goal", "test", "--run-id", "ext-cli-1"])`. The stub workflow's graph is a single node that passes through a deterministic output so no LLM tier fires. Asserts exit code 0 + the expected stdout contract (run-id echo + plan JSON + total cost).

**`tests/mcp/test_external_workflow.py`** (new) — mirror test for the MCP surface. Uses the existing `FastMCP` test-client pattern (see `tests/mcp/test_run_workflow.py` for reference). Asserts `run_workflow(workflow_id="stub_mcp_wf", inputs={...})` succeeds.

**Hermeticity constraint:** the stub module must not trigger any LiteLLM / Claude Code call. A stub graph of `START → pass_through_node → END` with a static state dict is sufficient.

### 8. Documentation

**`docs/writing-a-workflow.md`** — new §External workflows from a downstream consumer. Placement: after the existing "Authoring a workflow" section, before any closing "Next steps" block. Contents:

- **Why a consumer would use this** — two-sentence framing.
- **Minimum module shape** — `register("name", build_fn)` at module top level; `<name>_tier_registry()` helper if the workflow makes LLM calls.
- **Env-var surface** — `AIW_EXTRA_WORKFLOW_MODULES=pkg.workflows.foo,pkg.workflows.bar`.
- **CLI-flag surface** — `aiw --workflow-module pkg.workflows.foo run foo ...` + `aiw-mcp --workflow-module ...`.
- **Composition** — env imports first, CLI appended.
- **Failure mode** — `ExternalWorkflowImportError` at startup name the module + cause; no partial-load rollback is attempted (the same semantic Python itself uses for module imports).
- **User-owned-code boundary** — ADR-0007 summary: user code runs in-process with full privileges; ai-workflows does not lint / test / sandbox it.
- **Worked example** — the CS-300 layout (package at `./cs300/`, `uv pip install -e .`, `aiw-mcp --transport http` with the env var).

**Root `README.md` `## MCP server`** — add a one-line pointer at the bottom of the section:

> **Running your own workflows from a downstream consumer?** See [docs/writing-a-workflow.md §External workflows from a downstream consumer](docs/writing-a-workflow.md#external-workflows-from-a-downstream-consumer).

### 9. CHANGELOG

Under `[Unreleased]` on both branches (mirror entry on design_branch per the release pattern):

```markdown
### Added — M16 Task 01: external workflow module discovery (2026-MM-DD)
- `ai_workflows/workflows/loader.py` — `load_extra_workflow_modules()` + `ExternalWorkflowImportError`.
- `AIW_EXTRA_WORKFLOW_MODULES` env var (comma-separated dotted module paths).
- `--workflow-module` repeatable CLI flag on `aiw` and `aiw-mcp` (composes with env).
- `_dispatch._import_workflow_module` consults the registry first so external modules route correctly.
- KDR-013 in architecture.md §9; ADR-0007 records the user-owned-code contract.
- docs/writing-a-workflow.md gains §External workflows from a downstream consumer.
```

## Acceptance Criteria

- [ ] **AC-1:** `ai_workflows/workflows/loader.py` exists with `load_extra_workflow_modules(*, cli_modules=None) -> list[str]` and `ExternalWorkflowImportError(ImportError)` matching the signature above.
- [ ] **AC-2:** `AIW_EXTRA_WORKFLOW_MODULES` is honoured. Unset / empty → no import. Comma-separated list → each entry imported in order. Whitespace trimmed; empty entries from trailing commas skipped silently.
- [ ] **AC-3:** `--workflow-module` CLI flag is accepted on both `aiw` (root callback) and `aiw-mcp` (root command). Repeatable. Composes with env (env first, CLI appended).
- [ ] **AC-4:** Import mechanism is `importlib.import_module(dotted)`. No filesystem paths; no `spec_from_file_location`.
- [ ] **AC-5:** A non-importable entry raises `ExternalWorkflowImportError` naming the dotted path + chained cause. Startup aborts; subsequent entries are not attempted. Earlier entries' side effects have already landed (documented, not fought).
- [ ] **AC-6:** A module that imports cleanly but does not call `register(...)` is non-fatal at startup. `aiw run <missing>` surfaces the existing "workflow 'X' not registered; known: [...]" error from `_dispatch` (unchanged behaviour).
- [ ] **AC-7:** Idempotence. Re-invocation of `load_extra_workflow_modules()` in the same Python process is a no-op for already-loaded entries (Python `sys.modules` cache + `register()`'s identical-re-registration path).
- [ ] **AC-8:** Name-collision with a shipped workflow is surfaced via the existing `register()` `ValueError` — not a new error type. Existing behaviour preserved.
- [ ] **AC-9:** `_dispatch._import_workflow_module` consults `workflows._REGISTRY` first. If the name is already registered, returns `sys.modules[builder.__module__]` so `_resolve_tier_registry(workflow, module)` finds the `<workflow>_tier_registry()` helper on the external module. In-package lazy-import fallback preserved.
- [ ] **AC-10:** MCP surface parity. `run_workflow(workflow_id="<external>", ...)` succeeds over both stdio and HTTP transports for a workflow registered via the env var or CLI flag. No MCP schema change.
- [ ] **AC-11:** Hermetic tests land green. `tests/workflows/test_external_module_loader.py` (6 tests), `tests/cli/test_external_workflow.py` (1 round-trip test), `tests/mcp/test_external_workflow.py` (round-trip tests for stdio + HTTP).
- [ ] **AC-12:** Existing tests stay green. Zero regressions. Existing `register()` semantics preserved.
- [ ] **AC-13:** Four-layer contract preserved. `uv run lint-imports` reports 4 kept, 0 broken. `loader.py` sits in the workflows layer; no imports from `cli` / `mcp` / `graph` / `primitives`.
- [ ] **AC-14:** Gates green on both branches. `uv run pytest` + `uv run lint-imports` + `uv run ruff check`.
- [ ] **AC-15:** Module docstrings on `loader.py` and the extended `_dispatch.py` function cite M16 T01 + describe the load contract.
- [ ] **AC-16:** KDR-013 row added to `design_docs/architecture.md` §9. ADR-0007 authored at `design_docs/adr/0007_user_owned_code_contract.md` with Context / Decision / Rejected alternatives / Consequences.
- [ ] **AC-17:** `docs/writing-a-workflow.md` gains §External workflows from a downstream consumer with the worked CS-300 example. Root `README.md` `## MCP server` section gains the one-line pointer.
- [ ] **AC-18:** CHANGELOG entry under `[Unreleased]` on both branches matching the pattern in §9 above.

## Dependencies

- **0.1.3 landed.** 2026-04-23. M16 ships on top.
- **M14 (MCP HTTP) landed.** The HTTP-transport round-trip test in `tests/mcp/test_external_workflow.py` rides on M14's HTTP mode.
- **M15 is not a precondition.** M16 ships independently of the tier-overlay work; either can land first. M15 currently has no forcing function.

## Out of scope (explicit)

- `AIW_WORKFLOWS_PATH` directory scan / `spec_from_file_location`. Superseded by dotted-path imports per the CS-300 narrow-scope review.
- `AIW_PRIMITIVES_PATH` — no consumer case.
- `aiw inspect <workflow>` command — deferred (discoverability polish).
- Extension of `aiw list-workflows` to flag external workflows with their source — deferred.
- Programmatic-import logging default in `ai_workflows/__init__.py` — deferred pending a concrete forcing function.
- Entry-point discovery (PEP 621) — deferred; re-opens if a consumer wants to pip-publish a distributable workflow package.
- Hot-reload of external modules in `aiw-mcp --transport http` — deferred; load-once-at-startup is explicit.
- Sandboxing / import isolation — user code runs in-process with full privileges; ADR-0007 records the contract.
- Linting / testing user code — `ruff` + `lint-imports` stay pointed at the package source only.

## Risks

1. **`ExternalWorkflowImportError` message length.** The chained cause's traceback can be long; the primary message stays short (module path + exception class name + first line of the cause). Full traceback still accessible via `__cause__` for debugging. Mitigation: integration test asserts the message format is stable.
2. **Startup-atomicity expectation mismatch.** A consumer may expect "if anything fails, nothing loaded" — Python does not offer that. Earlier entries' `register()` calls have already fired in `sys.modules` by the time a later entry raises. Mitigation: ADR-0007 + the doc section spell this out. Users can clear `sys.modules` manually if they need a clean-slate reload, but the design does not promise to.
3. **Sibling-process pollution.** Two `aiw` invocations share nothing (each is a fresh Python process), so `sys.modules` pollution is a non-issue for the CLI. `aiw-mcp --transport http` is long-lived and loads once at startup — no re-scan, so also not a pollution risk. If hot-reload ever lands, `sys.modules` hygiene becomes a real concern.
4. **Malicious dotted paths.** `AIW_EXTRA_WORKFLOW_MODULES=os; __import__('os').system('rm -rf /')` — not a concern, because `importlib.import_module` only accepts dotted paths, not arbitrary code. The env var is set by the operator (local-only solo-use deployment per `project_local_only_deployment.md` memory). If multi-tenant ever becomes a concern, this surface becomes a gated one.
5. **Registry collision at startup.** An external module calling `register("planner", ...)` will hit the existing `register()` `ValueError` the moment the in-package `planner` module is imported (whichever order). That ordering is "first-to-load wins"; the error is loud and names both sources. No M16-specific defence beyond the existing invariant.
