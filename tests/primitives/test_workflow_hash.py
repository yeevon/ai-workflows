"""Tests for M1 Task 07 — ``ai_workflows.primitives.workflow_hash``.

Covers every acceptance criterion of CRIT-02 that applies to the hash:

* ``compute_workflow_hash()`` is deterministic (same dir → same hash)
* Hash changes when any content file changes
* ``__pycache__`` / ``.pyc`` / ``.DS_Store`` / ``*.log`` changes do NOT
  affect the hash
* Subdirectory files (``prompts/``, ``schemas/``) contribute to the hash
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ai_workflows.primitives.workflow_hash import compute_workflow_hash


def _make_workflow(root: Path) -> None:
    """Write a realistic mini-workflow under ``root``."""
    (root / "workflow.yaml").write_text(
        "name: example\nsteps: []\n", encoding="utf-8"
    )
    (root / "prompts").mkdir()
    (root / "prompts" / "system.md").write_text("You are a helpful assistant.\n", encoding="utf-8")
    (root / "prompts" / "user.md").write_text("Classify {{x}}.\n", encoding="utf-8")
    (root / "schemas").mkdir()
    (root / "schemas" / "output.json").write_text('{"type": "object"}\n', encoding="utf-8")
    (root / "custom_tools.py").write_text("def my_tool(): ...\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# AC: deterministic + subdirectory coverage
# ---------------------------------------------------------------------------


def test_compute_workflow_hash_is_deterministic(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    _make_workflow(a)
    _make_workflow(b)

    assert compute_workflow_hash(a) == compute_workflow_hash(b)


def test_compute_workflow_hash_is_repeatable_on_same_directory(tmp_path):
    _make_workflow(tmp_path)
    first = compute_workflow_hash(tmp_path)
    second = compute_workflow_hash(tmp_path)
    assert first == second


def test_compute_workflow_hash_returns_lowercase_hex_digest(tmp_path):
    _make_workflow(tmp_path)
    digest = compute_workflow_hash(tmp_path)
    # SHA-256 is 64 hex chars.
    assert len(digest) == 64
    assert digest == digest.lower()
    int(digest, 16)  # must parse as hex


def test_compute_workflow_hash_accepts_str_and_path(tmp_path):
    _make_workflow(tmp_path)
    from_str = compute_workflow_hash(str(tmp_path))
    from_path = compute_workflow_hash(tmp_path)
    assert from_str == from_path


# ---------------------------------------------------------------------------
# AC: content changes invalidate
# ---------------------------------------------------------------------------


def test_touching_a_prompt_changes_the_hash(tmp_path):
    _make_workflow(tmp_path)
    before = compute_workflow_hash(tmp_path)
    (tmp_path / "prompts" / "system.md").write_text("You are precise.\n", encoding="utf-8")
    after = compute_workflow_hash(tmp_path)
    assert before != after


def test_touching_workflow_yaml_changes_the_hash(tmp_path):
    _make_workflow(tmp_path)
    before = compute_workflow_hash(tmp_path)
    (tmp_path / "workflow.yaml").write_text("name: renamed\n", encoding="utf-8")
    after = compute_workflow_hash(tmp_path)
    assert before != after


def test_renaming_a_file_changes_the_hash(tmp_path):
    _make_workflow(tmp_path)
    before = compute_workflow_hash(tmp_path)
    os.rename(tmp_path / "prompts" / "system.md", tmp_path / "prompts" / "system_v2.md")
    after = compute_workflow_hash(tmp_path)
    assert before != after


def test_adding_a_new_file_changes_the_hash(tmp_path):
    _make_workflow(tmp_path)
    before = compute_workflow_hash(tmp_path)
    (tmp_path / "prompts" / "extra.md").write_text("extra\n", encoding="utf-8")
    after = compute_workflow_hash(tmp_path)
    assert before != after


def test_schemas_subdir_contributes_to_hash(tmp_path):
    """CRIT-02 requires every file under the workflow dir to participate."""
    _make_workflow(tmp_path)
    before = compute_workflow_hash(tmp_path)
    (tmp_path / "schemas" / "output.json").write_text('{"type": "array"}\n', encoding="utf-8")
    after = compute_workflow_hash(tmp_path)
    assert before != after


# ---------------------------------------------------------------------------
# AC: ignored patterns are actually ignored
# ---------------------------------------------------------------------------


def test_pycache_changes_do_not_affect_hash(tmp_path):
    _make_workflow(tmp_path)
    before = compute_workflow_hash(tmp_path)
    pycache = tmp_path / "__pycache__"
    pycache.mkdir()
    (pycache / "custom_tools.cpython-312.pyc").write_bytes(b"\x00\x01\x02")
    assert compute_workflow_hash(tmp_path) == before


def test_nested_pycache_is_ignored(tmp_path):
    """__pycache__ anywhere in the tree is ignored, not just at the root."""
    _make_workflow(tmp_path)
    before = compute_workflow_hash(tmp_path)
    nested = tmp_path / "schemas" / "__pycache__"
    nested.mkdir()
    (nested / "cached.pyc").write_bytes(b"\x00\x01")
    assert compute_workflow_hash(tmp_path) == before


def test_stray_pyc_outside_pycache_is_ignored(tmp_path):
    _make_workflow(tmp_path)
    before = compute_workflow_hash(tmp_path)
    (tmp_path / "custom_tools.pyc").write_bytes(b"\x00")
    assert compute_workflow_hash(tmp_path) == before


def test_ds_store_is_ignored(tmp_path):
    _make_workflow(tmp_path)
    before = compute_workflow_hash(tmp_path)
    (tmp_path / ".DS_Store").write_bytes(b"finder-metadata")
    assert compute_workflow_hash(tmp_path) == before


def test_log_files_are_ignored(tmp_path):
    _make_workflow(tmp_path)
    before = compute_workflow_hash(tmp_path)
    (tmp_path / "run.log").write_text("debug\n", encoding="utf-8")
    assert compute_workflow_hash(tmp_path) == before


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_missing_directory_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        compute_workflow_hash(tmp_path / "does-not-exist")


def test_passing_a_file_path_raises_not_a_directory(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("hi", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        compute_workflow_hash(f)


def test_empty_workflow_directory_has_stable_hash(tmp_path):
    """An empty directory is still a valid (if unusual) input."""
    first = compute_workflow_hash(tmp_path)
    second = compute_workflow_hash(tmp_path)
    assert first == second
    assert len(first) == 64


# ---------------------------------------------------------------------------
# Algorithmic guard: iteration order must not change the hash
# ---------------------------------------------------------------------------


def test_hash_is_stable_across_creation_order(tmp_path):
    """Creating files in different orders must not change the digest."""
    order_a = tmp_path / "a"
    order_b = tmp_path / "b"
    order_a.mkdir()
    order_b.mkdir()

    # Order A: write "z" then "a"
    (order_a / "z.txt").write_text("Z\n", encoding="utf-8")
    (order_a / "a.txt").write_text("A\n", encoding="utf-8")

    # Order B: write "a" then "z"
    (order_b / "a.txt").write_text("A\n", encoding="utf-8")
    (order_b / "z.txt").write_text("Z\n", encoding="utf-8")

    assert compute_workflow_hash(order_a) == compute_workflow_hash(order_b)
