"""Tests for the workflow name registry (M3 Task 01).

Covers the acceptance criteria from
``design_docs/phases/milestone_3_first_workflow/task_01_workflow_registry.md``.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator

import pytest

from ai_workflows import workflows


@pytest.fixture(autouse=True)
def _reset_registry() -> Iterator[None]:
    """Clear the registry between tests so state does not leak."""
    workflows._reset_for_tests()
    yield
    workflows._reset_for_tests()


def _dummy_builder() -> object:
    return object()


def _other_builder() -> object:
    return object()


def test_register_then_get_round_trips() -> None:
    workflows.register("planner", _dummy_builder)
    assert workflows.get("planner") is _dummy_builder


def test_register_same_pair_is_idempotent() -> None:
    workflows.register("planner", _dummy_builder)
    workflows.register("planner", _dummy_builder)
    assert workflows.get("planner") is _dummy_builder


def test_register_conflict_raises_value_error() -> None:
    workflows.register("planner", _dummy_builder)
    with pytest.raises(ValueError) as excinfo:
        workflows.register("planner", _other_builder)
    message = str(excinfo.value)
    assert "planner" in message
    assert repr(_dummy_builder) in message


def test_get_unknown_name_lists_known_workflows() -> None:
    workflows.register("planner", _dummy_builder)
    workflows.register("slice_refactor", _other_builder)
    with pytest.raises(KeyError) as excinfo:
        workflows.get("missing")
    message = str(excinfo.value)
    assert "missing" in message
    assert "planner" in message
    assert "slice_refactor" in message


def test_get_unknown_name_when_registry_empty() -> None:
    with pytest.raises(KeyError) as excinfo:
        workflows.get("anything")
    assert "(none)" in str(excinfo.value)


def test_list_workflows_returns_sorted_names() -> None:
    workflows.register("zulu", _dummy_builder)
    workflows.register("alpha", _other_builder)
    workflows.register("mike", _dummy_builder)
    assert workflows.list_workflows() == ["alpha", "mike", "zulu"]


def test_list_workflows_empty_returns_empty_list() -> None:
    assert workflows.list_workflows() == []


def test_reset_for_tests_empties_registry() -> None:
    workflows.register("planner", _dummy_builder)
    assert workflows.list_workflows() == ["planner"]
    workflows._reset_for_tests()
    assert workflows.list_workflows() == []


def test_workflows_module_does_not_import_langgraph() -> None:
    """The workflows package must not pull in LangGraph at module load.

    Forces a fresh import with ``langgraph`` removed from ``sys.modules`` and
    masked to ``None`` so any transitive import would fail — if the module
    still loads clean, no ``import langgraph`` was triggered.
    """
    to_unload = [
        name
        for name in sys.modules
        if name == "ai_workflows.workflows"
        or name.startswith("ai_workflows.workflows.")
    ]
    saved = {name: sys.modules.pop(name) for name in to_unload}

    saved_langgraph = {
        name: sys.modules.get(name)
        for name in list(sys.modules)
        if name == "langgraph" or name.startswith("langgraph.")
    }
    for name in saved_langgraph:
        sys.modules[name] = None  # type: ignore[assignment]

    try:
        import importlib

        reloaded = importlib.import_module("ai_workflows.workflows")
        assert hasattr(reloaded, "register")
    finally:
        for name in saved_langgraph:
            original = saved_langgraph[name]
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original
        for name, module in saved.items():
            sys.modules[name] = module
