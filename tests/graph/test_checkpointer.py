"""Unit tests for :mod:`ai_workflows.graph.checkpointer` (M2 Task 08).

Covers the three unit-level ACs named in the task spec:

* Custom path is honoured.
* ``AIW_CHECKPOINT_DB`` env var override is honoured.
* Applied to a plain :class:`StateGraph` compiles without error.

Plus: the "separate from the Storage DB" architectural invariant
(KDR-009) and the sanity check that the default path resolves under
``~/.ai-workflows/`` so a solo-dev workstation does not spray
SQLite files across the home directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from ai_workflows.graph.checkpointer import (
    AIW_CHECKPOINT_DB_ENV,
    DEFAULT_CHECKPOINT_PATH,
    build_checkpointer,
    resolve_checkpoint_path,
)


class _State(TypedDict, total=False):
    n: int


def test_custom_path_honoured(tmp_path: Path) -> None:
    """AC: ``build_checkpointer(db_path=...)`` creates the DB at that path."""
    target = tmp_path / "custom" / "checkpoints.sqlite"

    saver = build_checkpointer(target)

    try:
        assert target.exists(), "checkpointer did not create DB file at custom path"
        assert isinstance(saver, SqliteSaver)
    finally:
        saver.conn.close()


def test_env_var_override_honoured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC: ``AIW_CHECKPOINT_DB`` wins when no explicit path is passed."""
    override = tmp_path / "env_override" / "cp.sqlite"
    monkeypatch.setenv(AIW_CHECKPOINT_DB_ENV, str(override))

    saver = build_checkpointer()

    try:
        assert override.exists()
        assert resolve_checkpoint_path(None) == override
    finally:
        saver.conn.close()


def test_explicit_path_beats_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Precedence: explicit arg > env var > default."""
    env_path = tmp_path / "env" / "cp.sqlite"
    explicit_path = tmp_path / "explicit" / "cp.sqlite"
    monkeypatch.setenv(AIW_CHECKPOINT_DB_ENV, str(env_path))

    saver = build_checkpointer(explicit_path)

    try:
        assert explicit_path.exists()
        assert not env_path.exists(), "env path should not be used when explicit given"
    finally:
        saver.conn.close()


def test_default_path_resolves_under_user_home(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default path lives under ``~/.ai-workflows/`` regardless of cwd."""
    monkeypatch.delenv(AIW_CHECKPOINT_DB_ENV, raising=False)

    resolved = resolve_checkpoint_path(None)

    assert resolved == DEFAULT_CHECKPOINT_PATH
    assert resolved.is_absolute()
    assert ".ai-workflows" in resolved.parts


def test_applied_to_plain_stategraph_compiles_without_error(tmp_path: Path) -> None:
    """AC: plugging the checkpointer into a trivial ``StateGraph`` compiles."""
    saver = build_checkpointer(tmp_path / "compile.sqlite")

    try:
        g: StateGraph = StateGraph(_State)
        g.add_node("bump", lambda _s: {"n": 1})
        g.add_edge(START, "bump")
        g.add_edge("bump", END)

        compiled = g.compile(checkpointer=saver)

        result = compiled.invoke({"n": 0}, {"configurable": {"thread_id": "t1"}})
        assert result["n"] == 1
    finally:
        saver.conn.close()


def test_checkpointer_db_is_separate_from_storage_db(tmp_path: Path) -> None:
    """KDR-009 invariant: checkpointer DB must not alias the Storage DB.

    We assert the two never share an on-disk file. The test deliberately
    uses two *distinct* paths in the same tmp directory so a silent
    regression that unified the two (e.g. by pointing the checkpointer at
    the Storage path) would either create the wrong tables on the
    Storage DB or fail to find expected rows.
    """
    storage_path = tmp_path / "storage.sqlite"
    # Simulate the Storage DB existing already.
    storage_path.touch()

    checkpoint_path = tmp_path / "checkpoints.sqlite"
    saver = build_checkpointer(checkpoint_path)

    try:
        assert checkpoint_path.exists()
        assert storage_path.resolve() != checkpoint_path.resolve()
        # SqliteSaver creates its own `checkpoints` table in the
        # checkpoint DB — probe it to confirm the connection is bound to
        # the path we passed, not to Storage.
        cur = saver.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='checkpoints'"
        )
        assert cur.fetchone() is not None
    finally:
        saver.conn.close()


def test_setup_is_idempotent(tmp_path: Path) -> None:
    """Re-opening the same path does not error or drop tables."""
    path = tmp_path / "idem.sqlite"

    first = build_checkpointer(path)
    first.conn.close()
    second = build_checkpointer(path)

    try:
        cur = second.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='checkpoints'"
        )
        assert cur.fetchone() is not None
    finally:
        second.conn.close()


def test_tilde_expansion_in_custom_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``~`` in a custom path expands via ``Path.expanduser``."""
    monkeypatch.setenv("HOME", str(tmp_path))
    resolved = resolve_checkpoint_path("~/nested/cp.sqlite")
    assert resolved == tmp_path / "nested" / "cp.sqlite"
