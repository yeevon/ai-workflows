# ADR-0007 — User-owned code contract for external workflow modules

**Status:** Accepted (2026-04-24).
**Decision owner:** [M16 Task 01](../phases/milestone_16_external_workflows/task_01_external_workflow_modules.md).
**References:** [architecture.md §4.2](../architecture.md) · [KDR-013](../architecture.md#section-9) · [M16 README](../phases/milestone_16_external_workflows/README.md) · CS-300 feature request filed 2026-04-24 (first downstream consumer — an interactive course-notes site that drives `aiw-mcp --transport http` against its own domain-specific workflow modules).

## Context

`jmdl-ai-workflows==0.1.3` shipped a workflow registry that is closed at the package level. [`_dispatch._import_workflow_module`](../../ai_workflows/workflows/_dispatch.py) hardcodes `importlib.import_module(f"ai_workflows.workflows.{workflow}")`, so the only workflows `aiw run <name>` and `run_workflow(workflow_id=...)` can reach are the ones shipped in-package (`planner`, `slice_refactor`).

CS-300 (the first downstream consumer) authors its own workflow modules (`question_gen`, `grade`, `assess`) in a separate repository and needs them reachable from `aiw-mcp --transport http` without forking the wheel. The pre-M16 options were all bad:

- Fork `jmdl-ai-workflows` and drop the workflow into the source tree — loses upstream sync; ships domain-specific code in the wheel.
- Monkey-patch `_dispatch._import_workflow_module` at runtime — fragile; breaks on every upstream rename.
- Publish the consumer as a pip package just to satisfy entry-points — overkill for a single-machine course-notes repo.

Two tensions shape the decision:

1. **How to discover?** Directory scan (`AIW_WORKFLOWS_PATH` + `spec_from_file_location`) vs. dotted Python module paths (`AIW_EXTRA_WORKFLOW_MODULES` + `importlib.import_module`) vs. PEP 621 entry points.
2. **How much risk surface does the framework own over user code?** Strict (lint, test, sandbox, validator-gate) vs. hands-off (surface errors but do not police).

## Decision

### Discovery: dotted Python module paths

External workflows register via **dotted Python module paths**, not filesystem paths. Two surfaces:

- `AIW_EXTRA_WORKFLOW_MODULES` — comma-separated env var.
- `--workflow-module <dotted>` — repeatable CLI flag on `aiw` + `aiw-mcp`; composes with the env var (env imports first, then CLI entries).

The consumer puts their package on `PYTHONPATH` (typical: `uv pip install -e .` inside the same environment as `jmdl-ai-workflows`) and names the module dotted-path-style. `importlib.import_module` does the work; the module's top-level `register("name", build)` call fires as a side effect and populates the existing registry.

### Risk ownership: user code is user-owned

**The framework surfaces import failures, but does not lint, test, or sandbox imported user code.**

Concretely:

- A module that fails to import raises `ExternalWorkflowImportError` (an `ImportError` subclass) naming the dotted path + chained cause. Startup aborts.
- A module that imports cleanly is trusted to have done what it advertised. No `ruff` check, no `import-linter` check, no `pytest --collect-only`, no static analysis. The framework's own test suite and layer contract point at the package source only.
- User code runs in-process with full Python privileges. No sandboxing.
- Name collisions with shipped workflows fail loudly via the existing `register()` re-binding check; `load_extra_workflow_modules()` eagerly pre-imports shipped workflows so that check fires reliably when an external module tries to shadow a shipped name.

This boundary is **load-bearing** for the framework's scope. ai-workflows ships orchestration primitives + a substrate + surfaces; it does not ship a validator for arbitrary user Python.

## Rejected alternatives

### Directory scan (`AIW_WORKFLOWS_PATH` + `spec_from_file_location`)

The original M16 draft (2026-04-23) proposed filesystem-path scanning with `importlib.util.spec_from_file_location` + a namespaced `aiw_external.<hash>.<stem>` module-name scheme. CS-300 explicitly asked for dotted paths instead; the narrower shape was adopted because:

- Namespace-collision logic becomes unnecessary — dotted paths are unique in `sys.modules` by construction.
- Editable installs are the idiomatic Python extension pattern (`uv pip install -e ./cs300` + env var); directory scan invents a second "loose `.py` file" authoring path alongside a real package.
- Entry points (a future layer) compose cleanly on top of dotted-path imports; composition with file-path scanning is awkward.

**Re-opens if:** a consumer surfaces a concrete case for loose `.py` file authoring without a package layout.

### Entry-point discovery (PEP 621 `[project.entry-points."ai_workflows.workflows"]`)

The right shape for published wheels. The framework would scan entry points at startup and call each advertised builder factory.

Rejected for now because:

- CS-300 is solo-operator + local-only (no pip-publishable output). Entry points would force a package-build + reinstall on every iteration, killing the edit-save-rerun loop.
- Dotted-path imports + entry points compose fine (they are independent discovery channels). Shipping both day-one is speculative scope.

**Re-opens if:** a consumer wants to ship their workflow package on PyPI as a distributable extension.

### Full plugin protocol (`class WorkflowPlugin: def register(registry): ...`)

Would add a layer of indirection (a protocol class) over the existing `register(name, builder)` API. Rejected:

- The existing function is already the public contract; adding a protocol adds surface without solving a concrete problem.
- A protocol implies the framework can validate / enumerate / introspect plugins, which re-opens the "what does the framework own" question this ADR just closed.

**Re-opens if:** a consumer needs structured plugin lifecycle hooks (pre-register, post-register, teardown).

### Sandboxing / import isolation

Execute user code in a restricted Python context (e.g. `restrictedpython`, a subprocess, a Pyodide runtime). Rejected:

- `ai-workflows` is a local-only solo-use tool per [`project_local_only_deployment`](../../.claude/projects/-home-papa-jochy-prj-ai-workflows/memory/project_local_only_deployment.md) memory — the operator supplies both the framework configuration and the external module code. There is no trust boundary to enforce.
- Sandboxing is expensive to implement correctly and distorts the Python import model in ways that would break legitimate workflow code (filesystem access for reading reference materials, subprocess calls for Claude Code, LiteLLM imports).

**Re-opens if:** multi-tenant hosting becomes a concern (not a CS-300 case; not on any current roadmap).

### Linting / testing user code

Run `ruff check` / `import-linter` / `pytest --collect-only` on imported user modules before accepting them. Rejected:

- The framework has no way to know what test fixtures the user's code needs, what ruff config they expect, or what layer rules they intend.
- A lint/test gate is a false-security surface — user code that passes syntactic checks can still do arbitrary runtime mischief. The right boundary is "did it import?" and "did it register what it said it would?"
- Policing user code would invert the direction of the dependency: the framework becomes opinionated about user project layout.

**Re-opens if:** a concrete regression shows that import-time-only validation leaves a recurring failure class that a lint/test gate would reliably catch. Has not surfaced.

## Consequences

- **New failure mode:** `ExternalWorkflowImportError` at CLI / MCP startup. Surfaces + documentation call this out.
- **New dispatch code path:** `_import_workflow_module` consults the registry first; registered external modules route via `sys.modules[builder.__module__]`. Preserves the in-package lazy-import fallback.
- **Existing `register()` collision semantic extends to externals.** In-package workflows cannot be shadowed as long as `load_extra_workflow_modules()` eagerly pre-imports the shipped package before processing externals (which it does).
- **No MCP schema change.** The wire surface is unaffected; the extension is invisible to any existing MCP host.
- **Startup atomicity is best-effort, not guaranteed.** Python's import system does not roll back partial loads. If entry *k* fails, entries *0..k-1* have already executed their top-level side effects. Documented rather than faked.
- **User-owned-code risk boundary is explicit.** Future questions of the form "should the framework lint / test / sandbox X?" are decided by this ADR's hands-off posture — the answer is no unless a new milestone changes the posture.

## Implementation pointers

- Loader module: [`ai_workflows/workflows/loader.py`](../../ai_workflows/workflows/loader.py) — `ExternalWorkflowImportError` + `load_extra_workflow_modules`.
- Dispatch routing extension: [`ai_workflows/workflows/_dispatch.py::_import_workflow_module`](../../ai_workflows/workflows/_dispatch.py).
- CLI wiring: [`ai_workflows/cli.py::_root`](../../ai_workflows/cli.py).
- MCP wiring: [`ai_workflows/mcp/__main__.py::_cli`](../../ai_workflows/mcp/__main__.py).
- Tests: `tests/workflows/test_external_module_loader.py`, `tests/cli/test_external_workflow.py`, `tests/mcp/test_external_workflow.py`.
- Documentation: [`docs/writing-a-workflow.md` §External workflows from a downstream consumer](../../docs/writing-a-workflow.md).
