"""Tests for M21 Task 17 — Spec format extension (per-slice file/symbol scope).

This module verifies the parser logic for the optional ``## Slice scope`` section
that task specs may carry to declare per-slice file/symbol boundaries for
parallel-Builder dispatch (T18 prerequisite). It also verifies the
``PARALLEL_ELIGIBLE`` flag written to ``runs/<task>/meta.json`` by
``/auto-implement`` at project-setup time.

Relationship to other modules: pure unit tests against string fixtures; no
``ai_workflows/`` imports needed (this task touches only ``.claude/commands/``
and ``design_docs/``). See ``auto-implement.md`` §Project setup for the runtime
behaviour these tests exercise.
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Minimal parser helpers (mirrors the dispatch-time logic in auto-implement.md)
# ---------------------------------------------------------------------------

_SLICE_SECTION_PATTERN = re.compile(r"^##\s+Slice scope", re.MULTILINE)
_AC_CELL_PATTERN = re.compile(r"AC-\d+(?:,\s*AC-\d+)*")


def has_slice_scope_section(spec_text: str) -> bool:
    """Return True if *spec_text* contains a ``## Slice scope`` section header."""
    return bool(_SLICE_SECTION_PATTERN.search(spec_text))


def parse_slice_rows(spec_text: str) -> list[dict[str, str]]:
    """Parse the Slice scope table from *spec_text*.

    Returns a list of dicts with keys ``slice``, ``acs``, ``files``.
    Returns an empty list when the section is absent.

    The function is intentionally lenient about whitespace so it works against
    hand-authored Markdown tables.
    """
    if not has_slice_scope_section(spec_text):
        return []

    rows: list[dict[str, str]] = []
    in_table = False
    for line in spec_text.splitlines():
        stripped = line.strip()
        # Start collecting rows once we enter the section
        if _SLICE_SECTION_PATTERN.match(stripped):
            in_table = True
            continue
        if not in_table:
            continue
        # Stop at the next ## heading
        if stripped.startswith("##") and not stripped.startswith("###"):
            break
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 3:
            continue
        # Skip header and separator rows
        if cells[0].lower() in ("slice", "---", "------", "-------"):
            continue
        # Skip separator rows including colon-aligned GFM separators (e.g. :------:)
        if all(re.match(r"^:?-+:?$", c) or c == "" for c in cells):
            continue
        rows.append({"slice": cells[0], "acs": cells[1], "files": cells[2]})
    return rows


def collect_acs_from_rows(rows: list[dict[str, str]]) -> list[str]:
    """Return a flat list of all AC identifiers found across *rows*."""
    acs: list[str] = []
    for row in rows:
        for match in re.finditer(r"AC-\d+", row["acs"]):
            acs.append(match.group())
    return acs


def validate_slice_rows(rows: list[dict[str, str]]) -> list[str]:
    """Return a list of violation strings for rows with a blank files column.

    A row with ``files`` equal to empty string (after stripping) is invalid per
    AC-5 ("completely blank value is invalid"). A ``<TODO>`` placeholder is *not*
    blank — callers that need to enforce full resolution should check for that
    separately.
    """
    violations: list[str] = []
    for i, row in enumerate(rows):
        if row["files"].strip() == "":
            violations.append(
                f"Row {i} (slice={row['slice']!r}): files column is blank — must be "
                "a real path or a <TODO> placeholder, not empty."
            )
    return violations


def write_meta_json(task_dir: Path, spec_text: str, pre_task_commit: str, task: str) -> Path:
    """Write ``meta.json`` to *task_dir* per the T17 parallel-flag spec.

    Returns the path to the written file.
    """
    task_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "PARALLEL_ELIGIBLE": has_slice_scope_section(spec_text),
        "pre_task_commit": pre_task_commit,
        "task": task,
    }
    out = task_dir / "meta.json"
    out.write_text(json.dumps(meta, indent=2))
    return out


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

_SPEC_WITH_SLICE_SCOPE = """\
# Task 99 — Example with Slice scope

**Status:** 📝 Planned.

## Why this task exists

A demo spec that declares slice boundaries.

## Acceptance criteria

1. AC-1 satisfied when foo.py is updated.
2. AC-2 satisfied when bar.py is updated.
3. AC-3 satisfied when tests pass.

## Slice scope (optional — required for parallel-Builder dispatch)

| Slice | ACs | Files / symbols |
|-------|-----|-----------------|
| slice-A | AC-1, AC-2 | `ai_workflows/primitives/foo.py`, `tests/test_foo.py` |
| slice-B | AC-3 | `ai_workflows/graph/bar.py`, `tests/test_bar.py` |

## Out of scope

Nothing here.
"""

_SPEC_WITHOUT_SLICE_SCOPE = """\
# Task 98 — Serial spec (no Slice scope)

**Status:** 📝 Planned.

## Acceptance criteria

1. AC-1 always runs serial.
"""

_SPEC_WITH_DUPLICATE_AC = """\
# Task 97 — Duplicate AC in two rows (invalid)

## Slice scope (optional — required for parallel-Builder dispatch)

| Slice | ACs | Files / symbols |
|-------|-----|-----------------|
| slice-A | AC-1, AC-2 | `ai_workflows/primitives/foo.py` |
| slice-B | AC-2, AC-3 | `ai_workflows/graph/bar.py` |
"""

_SPEC_WITH_EMPTY_FILES_COLUMN = """\
# Task 96 — Empty files column (draft)

## Slice scope (optional — required for parallel-Builder dispatch)

| Slice | ACs | Files / symbols |
|-------|-----|-----------------|
| slice-A | AC-1 |  |
"""

_SPEC_WITH_TODO_FILES_COLUMN = """\
# Task 95 — TODO files column (draft stub)

## Slice scope (optional — required for parallel-Builder dispatch)

| Slice | ACs | Files / symbols |
|-------|-----|-----------------|
| slice-A | AC-1 | <TODO — fill at spec-review time> |
"""

_SPEC_WITH_COLON_ALIGNED_SEPARATORS = """\
# Task 94 — Colon-aligned GFM separators

## Slice scope (optional — required for parallel-Builder dispatch)

| Slice | ACs | Files / symbols |
| :------ | :---- | :---------------- |
| slice-A | AC-1 | foo.py |
"""


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestSliceScopeDetection:
    """TC-1: Slice scope section detected in a spec that has it (happy path)."""

    def test_detects_slice_scope_section(self) -> None:
        assert has_slice_scope_section(_SPEC_WITH_SLICE_SCOPE) is True

    def test_parses_two_rows(self) -> None:
        rows = parse_slice_rows(_SPEC_WITH_SLICE_SCOPE)
        assert len(rows) == 2

    def test_slice_names_correct(self) -> None:
        rows = parse_slice_rows(_SPEC_WITH_SLICE_SCOPE)
        assert rows[0]["slice"] == "slice-A"
        assert rows[1]["slice"] == "slice-B"

    def test_files_column_populated(self) -> None:
        rows = parse_slice_rows(_SPEC_WITH_SLICE_SCOPE)
        assert "foo.py" in rows[0]["files"]
        assert "bar.py" in rows[1]["files"]

    def test_parses_colon_aligned_table(self) -> None:
        rows = parse_slice_rows(_SPEC_WITH_COLON_ALIGNED_SEPARATORS)
        assert len(rows) == 1, (
            f"Expected exactly 1 data row from colon-aligned separator table, got {rows}"
        )
        assert rows[0]["slice"] == "slice-A"
        assert rows[0]["files"] == "foo.py"


class TestSerialSpecPath:
    """TC-2: Slice scope section absent — serial-as-today path."""

    def test_no_section_returns_false(self) -> None:
        assert has_slice_scope_section(_SPEC_WITHOUT_SLICE_SCOPE) is False

    def test_parse_returns_empty_list(self) -> None:
        rows = parse_slice_rows(_SPEC_WITHOUT_SLICE_SCOPE)
        assert rows == []


class TestACToSliceMapping:
    """TC-3: AC-to-slice mapping — every AC in the table appears exactly once."""

    def test_every_ac_appears_once(self) -> None:
        rows = parse_slice_rows(_SPEC_WITH_SLICE_SCOPE)
        acs = collect_acs_from_rows(rows)
        # Each of AC-1, AC-2, AC-3 should appear exactly once
        for ac in ("AC-1", "AC-2", "AC-3"):
            assert acs.count(ac) == 1, f"{ac} expected exactly once, got {acs.count(ac)}"


class TestDuplicateACViolation:
    """TC-4: Duplicate AC in two slice rows raises a detectable violation."""

    def test_duplicate_ac_detected(self) -> None:
        rows = parse_slice_rows(_SPEC_WITH_DUPLICATE_AC)
        acs = collect_acs_from_rows(rows)
        # AC-2 appears in both slice-A and slice-B
        duplicates = [ac for ac in set(acs) if acs.count(ac) > 1]
        assert "AC-2" in duplicates, f"Expected AC-2 in duplicates, got {duplicates}"

    def test_no_duplicates_for_valid_spec(self) -> None:
        rows = parse_slice_rows(_SPEC_WITH_SLICE_SCOPE)
        acs = collect_acs_from_rows(rows)
        duplicates = [ac for ac in set(acs) if acs.count(ac) > 1]
        assert duplicates == [], f"Unexpected duplicates: {duplicates}"


class TestFilesColumnValidation:
    """TC-5: Files column must not be truly empty when section is present.

    A ``<TODO>`` placeholder is acceptable at draft time; a non-``<TODO>``
    non-empty value is valid; a completely blank value is invalid.
    """

    def test_todo_placeholder_is_acceptable(self) -> None:
        rows = parse_slice_rows(_SPEC_WITH_TODO_FILES_COLUMN)
        assert len(rows) == 1
        # TODO placeholder counts as a valid draft value
        assert "<TODO" in rows[0]["files"]

    def test_blank_files_column_is_detectable(self) -> None:
        rows = parse_slice_rows(_SPEC_WITH_EMPTY_FILES_COLUMN)
        assert len(rows) == 1
        # A blank files column is detectable (and callers can reject it)
        assert rows[0]["files"].strip() == ""

    def test_blank_files_column_is_rejected(self) -> None:
        rows = parse_slice_rows(_SPEC_WITH_EMPTY_FILES_COLUMN)
        violations = validate_slice_rows(rows)
        assert len(violations) == 1, (
            f"Expected exactly 1 violation for blank files column, got {violations}"
        )
        assert "slice-A" in violations[0], (
            f"Violation should reference the offending slice, got: {violations[0]!r}"
        )

    def test_nonempty_files_column_is_valid(self) -> None:
        rows = parse_slice_rows(_SPEC_WITH_SLICE_SCOPE)
        for row in rows:
            assert row["files"].strip() != "", f"Files column empty for slice {row['slice']}"


class TestMetaJsonParallelFlag:
    """TC-6: meta.json ``PARALLEL_ELIGIBLE`` written correctly for spec with/without section."""

    def test_eligible_true_when_slice_scope_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir)
            out = write_meta_json(task_dir, _SPEC_WITH_SLICE_SCOPE, "abc123", "m21_t17")
            data = json.loads(out.read_text())
            assert data["PARALLEL_ELIGIBLE"] is True
            assert data["pre_task_commit"] == "abc123"
            assert data["task"] == "m21_t17"

    def test_eligible_false_when_no_slice_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir)
            out = write_meta_json(task_dir, _SPEC_WITHOUT_SLICE_SCOPE, "def456", "m21_t98")
            data = json.loads(out.read_text())
            assert data["PARALLEL_ELIGIBLE"] is False
            assert data["pre_task_commit"] == "def456"

    def test_meta_json_is_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir)
            out = write_meta_json(task_dir, _SPEC_WITH_SLICE_SCOPE, "sha789", "m21_t99")
            # Must not raise
            parsed = json.loads(out.read_text())
            assert isinstance(parsed, dict)
            assert set(parsed.keys()) == {"PARALLEL_ELIGIBLE", "pre_task_commit", "task"}
