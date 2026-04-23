# Task 01 — `AIW_WORKFLOWS_PATH` + `AIW_PRIMITIVES_PATH` loader

**Status:** 📝 Planned.
**Grounding:** [milestone README](README.md) · [ai_workflows/workflows/__init__.py:58-76](../../../ai_workflows/workflows/__init__.py#L58-L76) (`register()` API + module-level `_REGISTRY`) · [ai_workflows/workflows/_dispatch.py:202-217](../../../ai_workflows/workflows/_dispatch.py#L202-L217) (dynamic-import site) · [M15 README](../milestone_15_tier_overlay/README.md) (tier overlay — precondition).

## What to Build

A directory-scan loader that runs at `aiw` / `aiw-mcp` startup, walks every directory on `$AIW_WORKFLOWS_PATH` (and `$AIW_PRIMITIVES_PATH`), imports each `*.py` file via `importlib.util.spec_from_file_location`, and lets each module self-register via the existing `register(name, builder)` call. T01 ships the loader + error-surfacing + collision handling; T02 ships the inspection surface (`aiw inspect`, `aiw list-workflows` extension, programmatic-import logging).

## Deliverables

### 1. New module `ai_workflows/workflows/_external_loader.py`

Lives in the workflows layer (alongside `_dispatch.py`) because its job is to populate the workflow registry. Primitives-side user code follows the same mechanism but targets primitives registration points (if any) — module name can stay `_external_loader.py` since the scanning logic is symmetric.

Public surface (internal to the package — no imports from `cli` / `mcp` layers):

```python
def load_external_modules(
    *,
    workflows_path_env: str = "AIW_WORKFLOWS_PATH",
    primitives_path_env: str = "AIW_PRIMITIVES_PATH",
) -> LoadReport:
    """Scan $AIW_PRIMITIVES_PATH then $AIW_WORKFLOWS_PATH, import each *.py.

    Primitives directories scan first so user primitives are available
    when user workflows import them at module load. Returns a LoadReport
    enumerating every file attempted + its outcome (loaded / skipped /
    failed) for use by ``aiw list-workflows`` and ``aiw inspect``.
    """
```

`LoadReport` is a pydantic model in the same module:

```python
class LoadOutcome(BaseModel):
    file_path: Path
    source_env: str  # "AIW_WORKFLOWS_PATH" or "AIW_PRIMITIVES_PATH"
    module_name: str
    status: Literal["loaded", "skipped_not_registered", "failed_import", "failed_register"]
    registered_names: list[str] = Field(default_factory=list)
    error: str | None = None  # traceback excerpt when status is "failed_*"

class LoadReport(BaseModel):
    outcomes: list[LoadOutcome] = Field(default_factory=list)

    def workflows_loaded(self) -> list[str]:
        """Registered names sourced from external modules."""
        ...
    def failures(self) -> list[LoadOutcome]:
        """Modules that failed import or registration."""
        ...
```

### 2. Directory + file enumeration

Inside `load_external_modules()`:

```python
def _directories_from_env(env_name: str) -> list[Path]:
    raw = os.environ.get(env_name, "")
    if not raw:
        return []
    result = []
    for entry in raw.split(os.pathsep):
        entry = entry.strip()
        if not entry:
            continue
        path = Path(entry).expanduser().resolve()
        if not path.exists():
            _LOG.warning("external_path_missing", env=env_name, path=str(path))
            continue
        if not path.is_dir():
            _LOG.warning("external_path_not_directory", env=env_name, path=str(path))
            continue
        result.append(path)
    return result

def _python_files(directory: Path) -> list[Path]:
    """Sorted *.py files excluding dunder files (__init__.py, __main__.py)."""
    return sorted(
        p for p in directory.glob("*.py")
        if not p.name.startswith("__")
    )
```

POSIX convention: `os.pathsep` (colon on POSIX, semicolon on Windows). Expansion handles `~` + env var expansion (`$HOME` etc.) at path-parse time.

### 3. Module import + registration

For each file:

```python
def _import_file(file_path: Path, source_env: str) -> LoadOutcome:
    module_name = _external_module_name(file_path)
    registered_before = set(workflows._REGISTRY.keys())  # import-time snapshot

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        return LoadOutcome(
            file_path=file_path, source_env=source_env,
            module_name=module_name, status="failed_import",
            error="importlib returned None spec — cannot exec",
        )

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # cache so re-scan finds the same object
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        del sys.modules[module_name]
        return LoadOutcome(
            file_path=file_path, source_env=source_env,
            module_name=module_name, status="failed_import",
            error=_format_error(exc),
        )

    new_registrations = set(workflows._REGISTRY.keys()) - registered_before
    if not new_registrations:
        return LoadOutcome(
            file_path=file_path, source_env=source_env,
            module_name=module_name, status="skipped_not_registered",
        )

    return LoadOutcome(
        file_path=file_path, source_env=source_env,
        module_name=module_name, status="loaded",
        registered_names=sorted(new_registrations),
    )


def _external_module_name(file_path: Path) -> str:
    """Return a unique, stable module name for an external file.

    blake2b keyed on the absolute path ensures two identically-named
    files in different directories do not collide in sys.modules.
    """
    digest = hashlib.blake2b(
        str(file_path.resolve()).encode("utf-8"),
        digest_size=8,
    ).hexdigest()
    return f"aiw_external.{digest}.{file_path.stem}"
```

### 4. Collision handling — extend `register()`

[`ai_workflows/workflows/__init__.py`](../../../ai_workflows/workflows/__init__.py) — the existing `register()` function gains a collision check:

```python
class WorkflowCollisionError(ValueError):
    """Raised when register() is called with a name already in _REGISTRY."""

def register(name: str, builder: WorkflowBuilder) -> None:
    if name in _REGISTRY:
        raise WorkflowCollisionError(
            f"workflow name {name!r} is already registered "
            f"(existing builder: {_REGISTRY[name].__module__}.{_REGISTRY[name].__qualname__}); "
            f"cannot register {builder.__module__}.{builder.__qualname__}. "
            f"Rename your workflow or remove the shadowing file."
        )
    _REGISTRY[name] = builder
```

**Important sub-decision:** in-package workflows register **first** (at `_dispatch._import_workflow_module()` time, which still fires before external-load-path scan). Collision check then blocks any external module from shadowing a shipped name. This preserves KDR-013's "in-package workflows cannot be shadowed" invariant.

### 5. Integration points

**Two startup surfaces** to call `load_external_modules()`:

1. **`ai_workflows/cli.py`** — after `configure_logging()` + before Typer command dispatch, call `load_external_modules()`. The `LoadReport` is stored on a module-level variable so T02's `aiw list-workflows` / `aiw inspect` can read it.
2. **`ai_workflows/mcp/__main__.py`** — same pattern, after `configure_logging()` + before `build_server()`. MCP tool invocation sees the extended registry via the same `_dispatch._import_workflow_module()` path (in-package workflows still lazy-import; external workflows are pre-loaded during startup scan).

Both entry points already call `load_dotenv()` at module top (from the 0.1.1 patch). `load_external_modules()` slots in **after** that so env-var-driven paths resolve correctly.

### 6. Tests — `tests/workflows/test_external_load_path.py` (new)

Hermetic. Uses `tmp_path` + `monkeypatch.setenv("AIW_WORKFLOWS_PATH", ...)`. Does **not** actually run any workflow — focus is on the load path, not the dispatch.

- `test_empty_env_returns_empty_report` — no env var set → `LoadReport` has zero outcomes.
- `test_nonexistent_directory_warns_and_skips` — env points at `/tmp/nonexistent` → structlog warning fires + report has zero outcomes.
- `test_single_valid_workflow_file_loads` — write a file that calls `register("tst_wf", builder)`; assert outcome is `"loaded"` + `registered_names == ["tst_wf"]` + the workflow is resolvable via the dispatch layer.
- `test_file_without_register_call_is_skipped` — write a file that defines functions but never calls `register(...)`; outcome is `"skipped_not_registered"`; no exception.
- `test_syntax_error_in_user_file_does_not_crash_startup` — write a file with invalid Python (`def = 1`); outcome is `"failed_import"` + `error` field contains a traceback excerpt; other files in the same directory still load.
- `test_register_exception_during_exec_does_not_crash_startup` — write a file that raises mid-execution (e.g. `raise RuntimeError("boom")`); outcome is `"failed_import"`; sibling files load fine.
- `test_name_collision_with_shipped_workflow_raises` — write a file that calls `register("planner", ...)`; assert `WorkflowCollisionError` is raised at exec time + outcome is `"failed_register"`.
- `test_name_collision_between_two_external_files` — two files, both calling `register("same_name", ...)`; the second one encounters the collision + fails; first one stays registered; outcome reports both.
- `test_primitives_path_scans_before_workflows_path` — one file on `AIW_PRIMITIVES_PATH` imports a helper, one file on `AIW_WORKFLOWS_PATH` uses that helper; asserts load order is deterministic + the workflow successfully imports the primitive.
- `test_multiple_directories_in_path` — colon-delimited list of two directories; both are scanned; collision across directories triggers the collision error at the second `register()`.
- `test_identical_filenames_in_different_directories_do_not_collide` — `~/a/foo.py` and `~/b/foo.py` both get distinct module names (blake2b-hashed); both load; different `register()` names so no collision; assertion is on `sys.modules` having two distinct keys.

### 7. `ai_workflows/workflows/__init__.py` — docstring update

Add a subsection documenting the external-load-path contract + the `register()` collision semantic.

## Acceptance Criteria

- [ ] **AC-1: `load_external_modules()` exists** at `ai_workflows/workflows/_external_loader.py` with the signature specified above.
- [ ] **AC-2: `$AIW_WORKFLOWS_PATH` is honoured.** Unset / empty = no scan. Colon-delimited = each directory scanned. Nonexistent directory = structlog warning + skip.
- [ ] **AC-3: `$AIW_PRIMITIVES_PATH` is honoured** identically to workflows path. Scans **first** (before workflows path).
- [ ] **AC-4: Per-file import uses `importlib.util.spec_from_file_location`.** Unique module names via `aiw_external.<blake2b-hash>.<stem>`. `sys.modules` cache used for re-scan stability.
- [ ] **AC-5: Import errors per file are caught + reported.** `SyntaxError`, `ImportError`, arbitrary `Exception` from `exec_module()` → outcome is `"failed_import"` with traceback excerpt; no crash; sibling files continue loading.
- [ ] **AC-6: Files without `register()` calls are non-fatal.** Outcome is `"skipped_not_registered"`; no warning (valid use case: shared utility file).
- [ ] **AC-7: Name collisions fail loudly.** External module calling `register()` with a name already in `_REGISTRY` raises `WorkflowCollisionError` naming both sources. In-package workflows cannot be shadowed by external ones (in-package loads first).
- [ ] **AC-8: `register()` is extended** with the collision check + `WorkflowCollisionError`. Existing shipped workflows continue to register successfully (no double-register).
- [ ] **AC-9: Integration at both entry points.** `ai_workflows/cli.py` and `ai_workflows/mcp/__main__.py` call `load_external_modules()` after `configure_logging()` + `load_dotenv()`, before command/tool dispatch.
- [ ] **AC-10: `LoadReport` is accessible.** A module-level variable (or an accessor) exposes the last load report so T02's inspection commands can read it without re-scanning.
- [ ] **AC-11: Hermetic tests land green.** `tests/workflows/test_external_load_path.py` — 11 tests covering happy path + every documented failure mode. All pass.
- [ ] **AC-12: Existing tests stay green.** `tests/` — zero regressions. No existing test depends on `register()`'s previous no-collision-check behaviour (verify via grep).
- [ ] **AC-13: Four-layer contract preserved.** `uv run lint-imports` reports 4 kept, 0 broken. `_external_loader.py` lives in `workflows` layer; no imports from `cli` or `mcp`.
- [ ] **AC-14: Gates green.** `uv run pytest` + `uv run lint-imports` + `uv run ruff check` on both branches.
- [ ] **AC-15: Module docstrings** for `_external_loader.py` and the extended `workflows/__init__.py` cite M16 T01 + describe the load contract.
- [ ] **AC-16: CHANGELOG entry.** Under `[Unreleased]` on both branches — new `### Added — M16 Task 01: AIW_WORKFLOWS_PATH external-workflow loader (YYYY-MM-DD)` entry.

## Dependencies

- **M15 landed** (tier overlay + fallback). External workflows inherit the tier-overlay merge at dispatch — no M16 work here, but M15's overlay semantics must be stable before T01 kickoff.
- **0.1.3 patch + 0.2.0 (M15) shipped.** M16 ships as 0.3.0 after M15 closes clean.

## Out of scope (explicit)

- **`aiw inspect <workflow>` command** — T02 deliverable.
- **`aiw list-workflows` extension to show external workflows** — T02 deliverable.
- **Programmatic-import logging default in `ai_workflows/__init__.py`** — T02 deliverable.
- **Entry-point discovery** — deferred to a future milestone (nice_to_have.md candidate).
- **Hot-reload of external directories.** Load happens once at startup. `aiw-mcp` HTTP mode does not pick up new files without restart.
- **Sandboxing of user code.** User code runs with full process privileges per ADR-0007 (M16 T03).
- **Linting user code.** `ruff check` + `lint-imports` stay pointed at the package source only.
- **Any primitives-layer registration surface beyond what already exists.** T01 only enables the load path; any primitive types that users might want to extend stay as they are today. If a concrete user case emerges (e.g. a custom `ValidatorNode` subclass), a future task adds the registration helper.

## Risks

1. **`sys.modules` pollution.** Users loading + unloading different workflow sets in the same Python process could leak memory via `sys.modules[module_name]`. Mitigation: document that `aiw` is designed for a single load-per-process lifecycle; the MCP HTTP long-running server is the only long-lived case, and it's not expected to hot-swap workflows. If this becomes a concern, T0N can add an `unload_external_modules()` helper.
2. **Collision between external-module names.** Blake2b hash over the absolute path makes collisions astronomically unlikely but not impossible. If a collision fires, `sys.modules` overwrites the earlier module silently — no observable error. Mitigation: the collision check at `register()` catches the downstream effect (two files registering the same workflow name); the underlying `sys.modules` collision is advisory-only. If a postmortem surfaces "two files' registrations mysteriously vanished," the module-name hash collision is a hypothesis to check.
3. **Path traversal / symlink attacks.** A malicious entry on `$AIW_WORKFLOWS_PATH` could point at `/etc/passwd.py` or similar. Mitigation: `ai-workflows` is a local-only solo-use tool per `project_local_only_deployment.md`; the env var is set by the operator. The threat model assumes the operator trusts what they put on the path. If a multi-tenant concern ever materialises, the load path becomes a gated surface.
