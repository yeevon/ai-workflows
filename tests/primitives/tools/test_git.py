"""Tests for :mod:`ai_workflows.primitives.tools.git` (Task 06).

Covers ``git_diff``, ``git_log``, and — the key AC — ``git_apply``
refuses on a dirty working tree. Uses an isolated repo under the test's
``tmp_path`` so tests don't touch the developer's real repositories.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from ai_workflows.primitives.tools import git


def _git(repo: Path, *args: str) -> str:
    """Run git in ``repo`` and return stdout; raise on non-zero exit."""
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Create a minimal git repo with one commit and return its path."""
    if shutil.which("git") is None:
        pytest.skip("git executable not on PATH")

    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    _git(repo_path, "init", "-q", "-b", "main")
    _git(repo_path, "config", "user.email", "test@example.com")
    _git(repo_path, "config", "user.name", "Test User")
    # Disable GPG signing even if the global config requires it.
    _git(repo_path, "config", "commit.gpgsign", "false")
    (repo_path / "hello.txt").write_text("line 1\nline 2\n", encoding="utf-8")
    _git(repo_path, "add", "hello.txt")
    _git(repo_path, "commit", "-q", "-m", "initial")
    return repo_path


# ---------------------------------------------------------------------------
# git_diff
# ---------------------------------------------------------------------------


def test_git_diff_returns_empty_on_clean_tree(repo: Path, ctx_factory) -> None:
    ctx = ctx_factory(project_root=str(repo))
    out = git.git_diff(ctx, str(repo))

    assert isinstance(out, str)
    assert out == ""


def test_git_diff_returns_diff_text_after_edit(repo: Path, ctx_factory) -> None:
    (repo / "hello.txt").write_text("line 1\nline 2 edited\n", encoding="utf-8")
    ctx = ctx_factory(project_root=str(repo))

    out = git.git_diff(ctx, str(repo))

    assert "hello.txt" in out
    assert "line 2 edited" in out


def test_git_diff_caps_at_100k_chars(
    repo: Path, ctx_factory, monkeypatch
) -> None:
    class _FakeProc:
        returncode = 0
        stdout = "A" * 200_000
        stderr = ""

    def fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _FakeProc()

    monkeypatch.setattr(git.subprocess, "run", fake_run)
    ctx = ctx_factory(project_root=str(repo))

    out = git.git_diff(ctx, str(repo))

    assert len(out) <= 100_000 + len("\n... [truncated at 100000 chars]")
    assert "truncated" in out


def test_git_diff_unknown_ref_returns_string_error(
    repo: Path, ctx_factory
) -> None:
    ctx = ctx_factory(project_root=str(repo))
    out = git.git_diff(ctx, str(repo), ref="nope-not-a-ref")

    assert isinstance(out, str)
    assert out.startswith("Error")


# ---------------------------------------------------------------------------
# git_log
# ---------------------------------------------------------------------------


def test_git_log_returns_oneline_entries(repo: Path, ctx_factory) -> None:
    ctx = ctx_factory(project_root=str(repo))
    out = git.git_log(ctx, str(repo))

    lines = out.splitlines()
    assert len(lines) == 1
    # "<short-sha> initial"
    parts = lines[0].split(" ", 1)
    assert len(parts) == 2
    assert parts[1] == "initial"


def test_git_log_respects_max_entries(repo: Path, ctx_factory) -> None:
    for i in range(5):
        (repo / "hello.txt").write_text(f"line {i}\n", encoding="utf-8")
        _git(repo, "add", "hello.txt")
        _git(repo, "commit", "-q", "-m", f"commit {i}")

    ctx = ctx_factory(project_root=str(repo))
    out = git.git_log(ctx, str(repo), max_entries=3)

    assert len(out.splitlines()) == 3


def test_git_log_non_repo_returns_string_error(tmp_path: Path, ctx_factory) -> None:
    ctx = ctx_factory(project_root=str(tmp_path))
    out = git.git_log(ctx, str(tmp_path))

    assert isinstance(out, str)
    assert out.startswith("Error")


# ---------------------------------------------------------------------------
# git_apply — refuses on dirty tree (key AC)
# ---------------------------------------------------------------------------


def _make_diff(repo: Path) -> str:
    """Stage and emit a diff without committing it."""
    (repo / "hello.txt").write_text("line 1\nline 2 patched\n", encoding="utf-8")
    diff = _git(repo, "diff", "hello.txt")
    _git(repo, "checkout", "--", "hello.txt")
    return diff


def test_git_apply_refuses_dirty_tree(repo: Path, ctx_factory) -> None:
    """AC: git_apply refuses on dirty working tree."""
    diff = _make_diff(repo)
    # Dirty the tree with a change unrelated to the diff.
    (repo / "unrelated.txt").write_text("x", encoding="utf-8")

    ctx = ctx_factory(project_root=str(repo))
    out = git.git_apply(ctx, str(repo), diff)

    assert isinstance(out, str)
    assert out.startswith("DirtyWorkingTreeError")
    assert "unrelated.txt" in out  # porcelain listing is echoed


def test_git_apply_clean_tree_applies_diff(repo: Path, ctx_factory) -> None:
    diff = _make_diff(repo)
    ctx = ctx_factory(project_root=str(repo))

    out = git.git_apply(ctx, str(repo), diff)

    assert out == "Applied diff successfully."
    assert "line 2 patched" in (repo / "hello.txt").read_text(encoding="utf-8")


def test_git_apply_dry_run_uses_apply_check(
    repo: Path, ctx_factory, monkeypatch
) -> None:
    diff = _make_diff(repo)
    captured: list[list[str]] = []
    real_run = subprocess.run

    def spy_run(args, *a, **kw):  # type: ignore[no-untyped-def]
        captured.append(list(args))
        return real_run(args, *a, **kw)

    monkeypatch.setattr(git.subprocess, "run", spy_run)
    ctx = ctx_factory(project_root=str(repo))

    out = git.git_apply(ctx, str(repo), diff, dry_run=True)

    assert out == "[DRY RUN] Diff applies cleanly."
    # Last subprocess call is the apply; confirm --check was passed.
    apply_call = [c for c in captured if "apply" in c][-1]
    assert "--check" in apply_call
    # And the file on disk is untouched.
    assert (repo / "hello.txt").read_text(encoding="utf-8") == "line 1\nline 2\n"


def test_git_apply_bad_diff_returns_string_error(
    repo: Path, ctx_factory
) -> None:
    ctx = ctx_factory(project_root=str(repo))
    out = git.git_apply(ctx, str(repo), "not a real diff\n")

    assert isinstance(out, str)
    assert out.startswith("Error")


def test_git_apply_non_repo_returns_string_error(
    tmp_path: Path, ctx_factory
) -> None:
    ctx = ctx_factory(project_root=str(tmp_path))
    out = git.git_apply(ctx, str(tmp_path), "")

    assert isinstance(out, str)
    # Non-repo → git status fails → DirtyWorkingTreeError or Error.
    assert out.startswith("DirtyWorkingTreeError") or out.startswith("Error")
