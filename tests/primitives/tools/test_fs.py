"""Tests for :mod:`ai_workflows.primitives.tools.fs` (Task 06).

Covers the Task 06 acceptance criteria that land in ``fs.py``:

* AC — ``read_file`` handles UTF-8 and latin-1 fallback gracefully.
* AC — every tool returns strings on error paths (no raises).

Plus the supporting behaviour: truncation markers, entry caps, glob
filtering, and regex validation.
"""

from __future__ import annotations

from pathlib import Path

from ai_workflows.primitives.tools import fs


def test_read_file_returns_utf8_content(tmp_path: Path, ctx_factory) -> None:
    target = tmp_path / "hello.txt"
    target.write_text("héllo wörld", encoding="utf-8")
    ctx = ctx_factory(project_root=str(tmp_path))

    out = fs.read_file(ctx, str(target))

    assert out == "héllo wörld"


def test_read_file_falls_back_to_latin1_on_invalid_utf8(
    tmp_path: Path, ctx_factory
) -> None:
    """AC: UTF-8 first, latin-1 fallback — must not raise."""
    target = tmp_path / "latin1.txt"
    target.write_bytes(b"caf\xe9")  # "café" in latin-1; invalid UTF-8
    ctx = ctx_factory(project_root=str(tmp_path))

    out = fs.read_file(ctx, str(target))

    assert isinstance(out, str)
    assert out == "café"  # latin-1 decodes 0xE9 → é


def test_read_file_applies_max_chars_truncation(
    tmp_path: Path, ctx_factory
) -> None:
    target = tmp_path / "big.txt"
    target.write_text("A" * 500, encoding="utf-8")
    ctx = ctx_factory(project_root=str(tmp_path))

    out = fs.read_file(ctx, str(target), max_chars=100)

    assert out.startswith("A" * 100)
    assert "[truncated]" in out


def test_read_file_missing_returns_string_error(tmp_path: Path, ctx_factory) -> None:
    """AC: error paths return a string, do not raise."""
    ctx = ctx_factory(project_root=str(tmp_path))

    out = fs.read_file(ctx, str(tmp_path / "missing.txt"))

    assert isinstance(out, str)
    assert "not found" in out.lower()


def test_read_file_on_directory_returns_string_error(
    tmp_path: Path, ctx_factory
) -> None:
    ctx = ctx_factory(project_root=str(tmp_path))
    out = fs.read_file(ctx, str(tmp_path))

    assert isinstance(out, str)
    assert "Error" in out


def test_write_file_creates_parent_dirs(tmp_path: Path, ctx_factory) -> None:
    ctx = ctx_factory(project_root=str(tmp_path))
    target = tmp_path / "nested" / "deep" / "out.txt"

    result = fs.write_file(ctx, str(target), "payload")

    assert target.read_text(encoding="utf-8") == "payload"
    assert "Wrote 7 chars" in result
    assert "overwrote" not in result


def test_write_file_flags_overwrite(tmp_path: Path, ctx_factory) -> None:
    ctx = ctx_factory(project_root=str(tmp_path))
    target = tmp_path / "out.txt"
    target.write_text("old", encoding="utf-8")

    result = fs.write_file(ctx, str(target), "new")

    assert target.read_text(encoding="utf-8") == "new"
    assert "overwrote" in result.lower()


def test_list_dir_returns_sorted_entries(tmp_path: Path, ctx_factory) -> None:
    (tmp_path / "b.txt").write_text("")
    (tmp_path / "a.txt").write_text("")
    (tmp_path / "c.txt").write_text("")
    ctx = ctx_factory(project_root=str(tmp_path))

    out = fs.list_dir(ctx, str(tmp_path))

    assert out.splitlines() == ["a.txt", "b.txt", "c.txt"]


def test_list_dir_supports_glob_pattern(tmp_path: Path, ctx_factory) -> None:
    (tmp_path / "keep.py").write_text("")
    (tmp_path / "skip.txt").write_text("")
    ctx = ctx_factory(project_root=str(tmp_path))

    out = fs.list_dir(ctx, str(tmp_path), pattern="*.py")

    assert out.splitlines() == ["keep.py"]


def test_list_dir_caps_at_500_entries(tmp_path: Path, ctx_factory) -> None:
    for i in range(600):
        (tmp_path / f"f{i:04}.txt").write_text("")
    ctx = ctx_factory(project_root=str(tmp_path))

    out = fs.list_dir(ctx, str(tmp_path))
    lines = out.splitlines()

    # 500 entries + 1 truncation line.
    assert len(lines) == 501
    assert "truncated" in lines[-1].lower()
    assert "600" in lines[-1]


def test_list_dir_missing_returns_string_error(tmp_path: Path, ctx_factory) -> None:
    ctx = ctx_factory(project_root=str(tmp_path))
    out = fs.list_dir(ctx, str(tmp_path / "nope"))

    assert isinstance(out, str)
    assert "not found" in out.lower()


def test_list_dir_on_file_returns_string_error(tmp_path: Path, ctx_factory) -> None:
    target = tmp_path / "f.txt"
    target.write_text("x", encoding="utf-8")
    ctx = ctx_factory(project_root=str(tmp_path))

    out = fs.list_dir(ctx, str(target))

    assert "not a directory" in out.lower()


def test_grep_returns_file_line_text_format(tmp_path: Path, ctx_factory) -> None:
    target = tmp_path / "log.txt"
    target.write_text("first\nERROR happened\nthird\n", encoding="utf-8")
    ctx = ctx_factory(project_root=str(tmp_path))

    out = fs.grep(ctx, r"ERROR", str(target))
    lines = out.splitlines()

    assert len(lines) == 1
    assert lines[0] == f"{target}:2:ERROR happened"


def test_grep_caps_max_results(tmp_path: Path, ctx_factory) -> None:
    target = tmp_path / "log.txt"
    target.write_text("\n".join(["hit"] * 50), encoding="utf-8")
    ctx = ctx_factory(project_root=str(tmp_path))

    out = fs.grep(ctx, r"hit", str(target), max_results=10)
    lines = out.splitlines()

    # 10 matches + truncation marker.
    assert len(lines) == 11
    assert "capped at 10" in lines[-1]


def test_grep_no_match_returns_string(tmp_path: Path, ctx_factory) -> None:
    target = tmp_path / "log.txt"
    target.write_text("nothing interesting here\n", encoding="utf-8")
    ctx = ctx_factory(project_root=str(tmp_path))

    out = fs.grep(ctx, r"zebra", str(target))

    assert "No matches" in out


def test_grep_invalid_regex_returns_string_error(
    tmp_path: Path, ctx_factory
) -> None:
    target = tmp_path / "log.txt"
    target.write_text("", encoding="utf-8")
    ctx = ctx_factory(project_root=str(tmp_path))

    out = fs.grep(ctx, r"(unterminated", str(target))

    assert isinstance(out, str)
    assert "invalid regex" in out.lower()


def test_grep_recurses_into_subdirectories(tmp_path: Path, ctx_factory) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "nested.txt").write_text("hit here\n", encoding="utf-8")
    ctx = ctx_factory(project_root=str(tmp_path))

    out = fs.grep(ctx, r"hit", str(tmp_path))

    assert "nested.txt" in out


def test_grep_missing_path_returns_string_error(
    tmp_path: Path, ctx_factory
) -> None:
    ctx = ctx_factory(project_root=str(tmp_path))
    out = fs.grep(ctx, r"x", str(tmp_path / "missing"))

    assert "not found" in out.lower()
