"""Tests for M16 Task 01 — external workflow module discovery.

Covers the acceptance criteria for
``ai_workflows.workflows.loader.load_extra_workflow_modules``. All
tests are hermetic: each stub module is written to ``tmp_path`` and
the path is prepended to ``sys.path`` via
``monkeypatch.syspath_prepend`` so ``importlib.import_module`` picks
it up. The registry is reset between tests via an autouse fixture so
state does not leak across cases.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from ai_workflows import workflows
from ai_workflows.workflows.loader import (
    ENV_VAR_NAME,
    ExternalWorkflowImportError,
    load_extra_workflow_modules,
)

_STUB_TEMPLATE = """\
from ai_workflows.workflows import register


def build() -> object:
    return object()


register({name!r}, build)
"""


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Clear the workflow registry + env var + stub modules between tests.

    Deliberately does NOT evict cached shipped-workflow modules
    (``ai_workflows.workflows.planner`` etc.) from ``sys.modules``.
    Evicting them causes the next test that references a shipped
    class (e.g. ``PlannerInput``) to encounter a NEW class object
    after re-import, and ``isinstance`` checks against the
    originally-imported reference break. Tests that need to exercise
    the eager-import mechanism use a spy on ``importlib.import_module``
    instead (see ``test_eager_import_shipped_workflows_requests_shipped_modules``).
    """
    workflows._reset_for_tests()
    monkeypatch.delenv(ENV_VAR_NAME, raising=False)
    for name in list(sys.modules):
        if name.startswith("_m16_stub_"):
            sys.modules.pop(name, None)
    yield
    workflows._reset_for_tests()
    for name in list(sys.modules):
        if name.startswith("_m16_stub_"):
            sys.modules.pop(name, None)


def _write_stub_module(
    tmp_path: Path, module_name: str, *, register_name: str | None = None
) -> None:
    """Write a stub workflow module at ``tmp_path / f"{module_name}.py"``.

    The stub registers under ``register_name`` (defaulting to
    ``module_name``) so the test can verify registration landed.
    """
    path = tmp_path / f"{module_name}.py"
    if register_name is None:
        register_name = module_name
    path.write_text(_STUB_TEMPLATE.format(name=register_name))


def test_env_var_unset_returns_empty_list() -> None:
    """AC-2: no env, no CLI → loader returns empty list."""
    result = load_extra_workflow_modules(cli_modules=None)
    assert result == []


def test_single_env_entry_imports_and_registers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-2, AC-9: env-var entry is imported and the workflow registers."""
    _write_stub_module(tmp_path, "_m16_stub_env_one")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv(ENV_VAR_NAME, "_m16_stub_env_one")

    result = load_extra_workflow_modules()

    assert result == ["_m16_stub_env_one"]
    assert "_m16_stub_env_one" in workflows.list_workflows()


def test_comma_separated_entries_import_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-2: comma-separated env-var entries all import and register.

    Also exercises whitespace trimming + empty-entry skip (trailing
    comma produces an empty string that must not turn into
    ``importlib.import_module('')``).
    """
    _write_stub_module(tmp_path, "_m16_stub_env_a")
    _write_stub_module(tmp_path, "_m16_stub_env_b")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv(
        ENV_VAR_NAME, "_m16_stub_env_a ,  _m16_stub_env_b  , "
    )

    result = load_extra_workflow_modules()

    assert result == ["_m16_stub_env_a", "_m16_stub_env_b"]
    registered = workflows.list_workflows()
    assert "_m16_stub_env_a" in registered
    assert "_m16_stub_env_b" in registered


def test_cli_entries_compose_with_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-3: env-var imports first, CLI entries appended after."""
    _write_stub_module(tmp_path, "_m16_stub_compose_env")
    _write_stub_module(tmp_path, "_m16_stub_compose_cli")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv(ENV_VAR_NAME, "_m16_stub_compose_env")

    result = load_extra_workflow_modules(
        cli_modules=["_m16_stub_compose_cli"]
    )

    assert result == ["_m16_stub_compose_env", "_m16_stub_compose_cli"]


def test_import_failure_raises_external_workflow_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-5: non-importable entry raises with dotted path + chained cause."""
    monkeypatch.setenv(ENV_VAR_NAME, "_m16_stub_does_not_exist")

    with pytest.raises(ExternalWorkflowImportError) as excinfo:
        load_extra_workflow_modules()

    assert excinfo.value.module_path == "_m16_stub_does_not_exist"
    assert isinstance(excinfo.value.__cause__, ModuleNotFoundError)
    # ExternalWorkflowImportError is a subclass of ImportError — existing
    # ``except ImportError`` handlers compose unchanged.
    assert isinstance(excinfo.value, ImportError)


def test_idempotent_reload_does_not_raise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-7: two calls with the same env var do not raise on re-registration.

    Python's ``sys.modules`` cache means the second
    ``importlib.import_module`` is a no-op for an already-loaded
    module (no top-level re-execution, no second ``register()``
    call). This test pins that the loader surface handles that
    cleanly.
    """
    _write_stub_module(tmp_path, "_m16_stub_idempotent")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv(ENV_VAR_NAME, "_m16_stub_idempotent")

    first = load_extra_workflow_modules()
    second = load_extra_workflow_modules()

    assert first == ["_m16_stub_idempotent"]
    assert second == ["_m16_stub_idempotent"]
    assert workflows.list_workflows().count("_m16_stub_idempotent") == 1


def test_module_without_register_call_is_non_fatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-6 (ISS-02): a utility module that imports cleanly but never
    calls ``register(...)`` is accepted silently. The loader does not
    validate that registration actually landed — a shared-helper file
    is a legitimate use case.
    """
    path = tmp_path / "_m16_stub_utility_only.py"
    path.write_text("# no register() call — just a utility module\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv(ENV_VAR_NAME, "_m16_stub_utility_only")

    result = load_extra_workflow_modules()

    assert result == ["_m16_stub_utility_only"]
    assert "_m16_stub_utility_only" not in workflows.list_workflows()


def test_collision_with_shipped_name_raises_via_register(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-8 (ISS-03): an external module registering a name already in
    the registry hits the existing ``register()`` ``ValueError``.

    The external module's top-level ``register(...)`` call raises
    from inside ``importlib.import_module``; the loader wraps that
    into ``ExternalWorkflowImportError`` with the original
    ``ValueError`` as the chained cause.

    Pre-populating the registry with a dummy builder (rather than
    relying on ``_eager_import_shipped_workflows`` to re-import the
    real ``planner`` module mid-test) keeps this test agnostic of
    ``sys.modules`` cache state and focused on the invariant under
    audit: the collision-at-register-time check is what catches
    external-vs-shipped shadowing.
    """
    # Prime the registry with a pre-existing binding. In production
    # this is the shipped planner's top-level register() call; in
    # tests we stand in with a dummy under the same name.
    def _existing_builder() -> object:
        return object()

    workflows.register("planner", _existing_builder)

    path = tmp_path / "_m16_stub_shadows_planner.py"
    path.write_text(
        "from ai_workflows.workflows import register\n"
        "def _shadow() -> object: return object()\n"
        "register('planner', _shadow)\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv(ENV_VAR_NAME, "_m16_stub_shadows_planner")

    with pytest.raises(ExternalWorkflowImportError) as excinfo:
        load_extra_workflow_modules()

    cause = excinfo.value.__cause__
    assert isinstance(cause, ValueError)
    assert "planner" in str(cause)


def test_eager_import_shipped_workflows_requests_shipped_modules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-8 mechanism (ISS-06): the eager-import helper asks
    ``importlib.import_module`` for every non-underscore shipped
    workflow module.

    Uses a spy (no ``sys.modules`` eviction) so this test does not
    cause class-object drift for downstream tests that rely on
    ``isinstance`` against types defined in the shipped modules.
    """
    from ai_workflows.workflows import loader

    requested: list[str] = []
    real_import = loader.importlib.import_module

    def _spy(name: str, *args: object, **kwargs: object) -> object:
        requested.append(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(loader.importlib, "import_module", _spy)

    loader._eager_import_shipped_workflows()

    assert "ai_workflows.workflows.planner" in requested, requested
    assert "ai_workflows.workflows.slice_refactor" in requested, requested
    # Private helpers must be skipped by the underscore filter + the
    # explicit ``loader`` short-circuit in the helper.
    assert "ai_workflows.workflows._dispatch" not in requested
    assert "ai_workflows.workflows.loader" not in requested


def test_import_workflow_module_routes_external_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-9 (ISS-04): ``_dispatch._import_workflow_module`` consults
    the registry first and returns
    ``sys.modules[builder.__module__]`` for externally-registered
    workflows whose module path is outside
    ``ai_workflows.workflows.*``.
    """
    from ai_workflows.workflows import _dispatch

    path = tmp_path / "_m16_stub_dispatch_routing.py"
    path.write_text(
        "from ai_workflows.workflows import register\n"
        "def build() -> object: return object()\n"
        "register('_m16_routing_wf', build)\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv(ENV_VAR_NAME, "_m16_stub_dispatch_routing")

    load_extra_workflow_modules()

    module = _dispatch._import_workflow_module("_m16_routing_wf")
    assert module.__name__ == "_m16_stub_dispatch_routing"
