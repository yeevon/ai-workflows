"""SqliteSaver binding (M2 Task 08 — KDR-009,
[architecture.md §4.1 / §4.2](../../design_docs/architecture.md)).

Thin factory around LangGraph's built-in SQLite checkpointer. The
factory exists so every workflow that opts in to checkpointing uses the
same default path (``~/.ai-workflows/checkpoints.sqlite``), the same
env-var override (``AIW_CHECKPOINT_DB``), and the same thread-safe
connection flags — and so the caller never constructs the underlying
:mod:`sqlite3` / :mod:`aiosqlite` connection by hand.

Two factories are exposed
-------------------------
* :func:`build_checkpointer` — synchronous; returns
  :class:`langgraph.checkpoint.sqlite.SqliteSaver`. Suits sync graphs
  and the spec's "applied to a plain ``StateGraph`` compiles without
  error" test (the test spec does not name an async variant).
* :func:`build_async_checkpointer` — asynchronous; returns
  :class:`langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver`. Required
  by the T08 smoke graph because every M2 node adapter
  (:func:`tiered_node`, :func:`validator_node`, :func:`human_gate`) is
  an ``async def`` and LangGraph rejects ``.ainvoke`` against the sync
  checkpointer (``NotImplementedError: The SqliteSaver does not support
  async methods``). The async variant is a concrete sibling, not a new
  backend — both are built on the same ``langgraph-checkpoint-sqlite``
  package listed in [architecture.md §6](../../design_docs/architecture.md)
  and both target the same on-disk schema, so a DB file written by one
  is readable by the other.

Invariants kept by this module
------------------------------
* **Separate from the Storage DB (KDR-009).** The default checkpointer
  path lives under ``~/.ai-workflows/`` while :class:`SQLiteStorage`
  takes a caller-supplied path and defaults to nothing. The two never
  share a file on disk. This module never reads or writes any
  ``Storage``-owned table.
* **No hand-rolled checkpoint writes.** We hand LangGraph a connection
  and let the saver own persistence. No bespoke migration, no custom
  serializer, no adapter.
* **Thread-safe connection.** Sync path: ``check_same_thread=False``
  matches the :class:`SqliteSaver` docstring — the checkpointer uses
  its own internal lock. Async path: ``aiosqlite`` runs SQLite on a
  dedicated worker thread and is safe to share across coroutines on a
  single event loop.
* **Tables materialised eagerly.** ``.setup()`` (sync) /
  ``await .setup()`` (async) is invoked before return so tests and the
  smoke graph can query the DB file immediately without waiting for
  the first ``put`` call.

Relationship to sibling modules
-------------------------------
* ``graph/error_handler.py`` — the counter-increment wrapper that
  converts raised bucket exceptions into durable state writes. Those
  writes ride this checkpointer along with every other state key.
* ``graph/human_gate.py`` — the node that triggers
  :func:`langgraph.types.interrupt`; the interrupt snapshot is what
  this checkpointer persists so ``ainvoke`` can resume later via
  ``Command(resume=...)``.
* ``primitives/storage.py`` — the run registry / gate log. Distinct
  database file, distinct schema, distinct connection. KDR-009 pins
  this separation.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import aiosqlite
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

__all__ = [
    "AIW_CHECKPOINT_DB_ENV",
    "DEFAULT_CHECKPOINT_PATH",
    "build_async_checkpointer",
    "build_checkpointer",
    "resolve_checkpoint_path",
]

#: Env var a caller can set to redirect the default checkpoint path. Set
#: to an absolute or ``~``-prefixed path. Consulted only when the
#: factory is called with ``db_path=None``.
AIW_CHECKPOINT_DB_ENV = "AIW_CHECKPOINT_DB"

#: Default on-disk location for the LangGraph checkpoint database.
DEFAULT_CHECKPOINT_PATH = Path.home() / ".ai-workflows" / "checkpoints.sqlite"


def build_checkpointer(db_path: str | Path | None = None) -> SqliteSaver:
    """Create or open a sync :class:`SqliteSaver` bound to a dedicated DB file.

    Path resolution (in order of precedence):

    1. Explicit ``db_path`` argument if non-``None``.
    2. ``AIW_CHECKPOINT_DB`` env var if set.
    3. ``~/.ai-workflows/checkpoints.sqlite``.

    The parent directory is created lazily so the first run on a fresh
    machine does not require manual setup. The SQLite connection is
    opened with ``check_same_thread=False`` — :class:`SqliteSaver`
    coordinates access through its own internal lock, per its
    docstring. :meth:`SqliteSaver.setup` is invoked before return so
    LangGraph-owned tables (``checkpoints``, ``writes``) exist on disk
    immediately.

    Use this factory for sync graphs. For the async graphs that drive
    every M2 adapter, use :func:`build_async_checkpointer`.
    """
    resolved = _prepare_path(db_path)
    conn = sqlite3.connect(str(resolved), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


async def build_async_checkpointer(
    db_path: str | Path | None = None,
) -> AsyncSqliteSaver:
    """Create or open an async :class:`AsyncSqliteSaver` bound to a DB file.

    Identical path-resolution rules to :func:`build_checkpointer`, but
    returns the async variant backed by :mod:`aiosqlite`. Required by
    the M2 smoke graph and by any workflow that invokes nodes via
    :meth:`StateGraph.ainvoke` — the sync :class:`SqliteSaver` raises
    ``NotImplementedError`` on the async checkpoint API.
    """
    resolved = _prepare_path(db_path)
    conn = await aiosqlite.connect(str(resolved))
    saver = AsyncSqliteSaver(conn)
    await saver.setup()
    return saver


def resolve_checkpoint_path(db_path: str | Path | None) -> Path:
    """Return the resolved on-disk path for the checkpoint database.

    Separated from the factories so callers (and tests) can inspect the
    path resolution rules without opening a connection. ``~`` and
    env-var indirections are both expanded.
    """
    if db_path is not None:
        return Path(db_path).expanduser()
    env_override = os.environ.get(AIW_CHECKPOINT_DB_ENV)
    if env_override:
        return Path(env_override).expanduser()
    return DEFAULT_CHECKPOINT_PATH


def _prepare_path(db_path: str | Path | None) -> Path:
    """Resolve ``db_path`` and ensure its parent directory exists."""
    resolved = resolve_checkpoint_path(db_path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved
