"""Tests for M21 Task 18 — Worktree-coordinated parallel Builder spawn.

This module verifies the parallel-dispatch logic described in
``.claude/commands/auto-implement.md`` §Functional loop Step 1. It tests the
decision branch on ``PARALLEL_ELIGIBLE``, the concurrency cap of ≤4 slices per
cycle, overlap detection across parallel Builder reports, worktree cleanup for
empty-diff slices, and telemetry naming for parallel invocations.

All tests are pure unit tests against string fixtures and in-process helpers;
no ``ai_workflows/`` imports are needed (T18 touches only
``.claude/commands/auto-implement.md`` and ``tests/``).

Relationship to other modules: builds on the slice-scope parser helpers from
``test_t17_spec_format.py`` which this module imports directly. The T17 helpers
provide ``has_slice_scope_section`` and ``parse_slice_rows`` — T18 adds the
dispatch-level logic on top.
"""

from __future__ import annotations

import importlib.util
import json
import re
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Re-use T17 parser helpers (import by absolute path to avoid package issues)
# ---------------------------------------------------------------------------

_T17_PATH = Path(__file__).parent / "test_t17_spec_format.py"
_spec_t17 = importlib.util.spec_from_file_location("test_t17_spec_format", _T17_PATH)
_t17 = importlib.util.module_from_spec(_spec_t17)  # type: ignore[arg-type]
_spec_t17.loader.exec_module(_t17)  # type: ignore[union-attr]

has_slice_scope_section = _t17.has_slice_scope_section
parse_slice_rows = _t17.parse_slice_rows
write_meta_json = _t17.write_meta_json

# ---------------------------------------------------------------------------
# Parallel-dispatch helpers (mirrors dispatch-time logic in auto-implement.md)
# ---------------------------------------------------------------------------

_MAX_PARALLEL_SLICES = 4


def read_parallel_eligible(meta_json_path: Path) -> bool:
    """Return the ``PARALLEL_ELIGIBLE`` flag from *meta_json_path*.

    Returns False if the file does not exist or the key is absent.
    """
    if not meta_json_path.exists():
        return False
    data = json.loads(meta_json_path.read_text())
    return bool(data.get("PARALLEL_ELIGIBLE", False))


def select_slices_for_cycle(
    rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Split *rows* into (this_cycle, deferred) respecting the ≤4 concurrency cap.

    Returns a 2-tuple:
    - ``this_cycle``: up to 4 slices to dispatch in the current cycle.
    - ``deferred``: remaining slices (5+) deferred to the next cycle.
    """
    this_cycle = rows[:_MAX_PARALLEL_SLICES]
    deferred = rows[_MAX_PARALLEL_SLICES:]
    return this_cycle, deferred


def detect_overlap(builder_reports: list[dict[str, list[str]]]) -> list[str]:
    """Detect files claimed by more than one Builder slice.

    *builder_reports* is a list of dicts, each mapping a slice label to the
    list of files that slice's Builder touched.  Returns a list of violation
    strings — empty if no overlap.

    Example input::

        [
            {"slice-A": ["foo.py", "tests/test_foo.py"]},
            {"slice-B": ["bar.py", "tests/test_foo.py"]},  # overlap!
        ]
    """
    seen: dict[str, str] = {}  # file → first slice that claimed it
    violations: list[str] = []
    for report in builder_reports:
        for slice_label, files in report.items():
            for f in files:
                if f in seen:
                    violations.append(
                        f"🚧 BLOCKED: parallel-Builder overlap detected — {f} "
                        f"modified by {seen[f]} and {slice_label}. "
                        "Review slice scope in spec ## Slice scope section."
                    )
                else:
                    seen[f] = slice_label
    return violations


def plan_telemetry_agent_names(n_slices: int) -> list[str]:
    """Return the list of agent names for telemetry given *n_slices* parallel slices.

    Each parallel slice uses ``builder-slice-<N>`` (1-indexed) so per-slice cost
    is tracked separately in the telemetry records.
    """
    return [f"builder-slice-{i}" for i in range(1, n_slices + 1)]


def plan_worktree_cleanup(worktree_diffs: dict[str, bool]) -> list[str]:
    """Return the list of worktree paths that need ``git worktree remove``.

    *worktree_diffs* maps worktree path → has_changes (True = changes present,
    False = empty diff). Only empty-diff worktrees are returned for immediate
    cleanup; merged worktrees are cleaned up explicitly in Step 6 of auto-implement.md.
    """
    return [path for path, has_changes in worktree_diffs.items() if not has_changes]


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

_SPEC_PARALLEL_ELIGIBLE = """\
# Task 99 — Example spec with Slice scope

**Status:** 📝 Planned.

## Acceptance criteria

1. AC-1 satisfied when foo.py is updated.
2. AC-2 satisfied when bar.py is updated.

## Slice scope (optional — required for parallel-Builder dispatch)

| Slice | ACs | Files / symbols |
|-------|-----|-----------------|
| slice-A | AC-1 | `ai_workflows/primitives/foo.py`, `tests/test_foo.py` |
| slice-B | AC-2 | `ai_workflows/graph/bar.py`, `tests/test_bar.py` |
"""

_SPEC_SERIAL = """\
# Task 98 — Serial spec (no Slice scope)

**Status:** 📝 Planned.

## Acceptance criteria

1. AC-1 always runs serial.
"""

_SPEC_FIVE_SLICES = """\
# Task 97 — Spec with 5 slices (cap test)

## Slice scope (optional — required for parallel-Builder dispatch)

| Slice | ACs | Files / symbols |
|-------|-----|-----------------|
| slice-A | AC-1 | `foo_a.py` |
| slice-B | AC-2 | `foo_b.py` |
| slice-C | AC-3 | `foo_c.py` |
| slice-D | AC-4 | `foo_d.py` |
| slice-E | AC-5 | `foo_e.py` |
"""


# ---------------------------------------------------------------------------
# TC-1: PARALLEL_ELIGIBLE=true triggers parallel path
# ---------------------------------------------------------------------------

class TestParallelEligibleTrue:
    """TC-1: meta.json with PARALLEL_ELIGIBLE=true triggers the parallel path."""

    def test_read_parallel_eligible_true(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir)
            meta = {"PARALLEL_ELIGIBLE": True, "pre_task_commit": "abc123", "task": "m21_t18"}
            (task_dir / "meta.json").write_text(json.dumps(meta))
            assert read_parallel_eligible(task_dir / "meta.json") is True

    def test_round_trip_spec_to_flag(self, tmp_path: Path) -> None:
        """Round-trip: spec with ## Slice scope → write_meta_json → read_parallel_eligible=True."""
        out = write_meta_json(tmp_path, _SPEC_PARALLEL_ELIGIBLE, "abc123", "t99")
        assert read_parallel_eligible(out) is True

    def test_each_slice_has_files(self) -> None:
        rows = parse_slice_rows(_SPEC_PARALLEL_ELIGIBLE)
        for row in rows:
            assert row["files"].strip() != "", f"Slice {row['slice']} has empty files column"


# ---------------------------------------------------------------------------
# TC-2: PARALLEL_ELIGIBLE=false takes serial path
# ---------------------------------------------------------------------------

class TestParallelEligibleFalse:
    """TC-2: meta.json with PARALLEL_ELIGIBLE=false or absent → serial path."""

    def test_read_parallel_eligible_false_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir)
            meta = {"PARALLEL_ELIGIBLE": False, "pre_task_commit": "def456", "task": "m21_t98"}
            (task_dir / "meta.json").write_text(json.dumps(meta))
            assert read_parallel_eligible(task_dir / "meta.json") is False

    def test_missing_meta_json_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            assert read_parallel_eligible(Path(tmpdir) / "meta.json") is False

    def test_serial_spec_has_no_slice_scope(self) -> None:
        assert has_slice_scope_section(_SPEC_SERIAL) is False

    def test_serial_spec_parse_yields_empty_rows(self) -> None:
        rows = parse_slice_rows(_SPEC_SERIAL)
        assert rows == []

    def test_write_meta_json_false_for_serial_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir)
            out = write_meta_json(task_dir, _SPEC_SERIAL, "ghi789", "m21_t98")
            data = json.loads(out.read_text())
            assert data["PARALLEL_ELIGIBLE"] is False


# ---------------------------------------------------------------------------
# TC-3: Slice cap — spec with 5 slices, only 4 dispatched in cycle 1
# ---------------------------------------------------------------------------

class TestSliceCap:
    """TC-3: Concurrency cap: spec with 5 slices → 4 dispatched, 1 deferred."""

    def test_five_slices_parsed(self) -> None:
        rows = parse_slice_rows(_SPEC_FIVE_SLICES)
        assert len(rows) == 5

    def test_this_cycle_capped_at_four(self) -> None:
        rows = parse_slice_rows(_SPEC_FIVE_SLICES)
        this_cycle, deferred = select_slices_for_cycle(rows)
        assert len(this_cycle) == 4

    def test_deferred_has_one_slice(self) -> None:
        rows = parse_slice_rows(_SPEC_FIVE_SLICES)
        this_cycle, deferred = select_slices_for_cycle(rows)
        assert len(deferred) == 1

    def test_deferred_is_slice_e(self) -> None:
        rows = parse_slice_rows(_SPEC_FIVE_SLICES)
        _, deferred = select_slices_for_cycle(rows)
        assert deferred[0]["slice"] == "slice-E"

    def test_four_slices_not_deferred(self) -> None:
        """Exactly 4 slices → nothing deferred."""
        rows = parse_slice_rows(_SPEC_FIVE_SLICES)[:4]
        this_cycle, deferred = select_slices_for_cycle(rows)
        assert len(this_cycle) == 4
        assert len(deferred) == 0


# ---------------------------------------------------------------------------
# TC-4: Overlap detection — two slices with same file → violation surfaced
# ---------------------------------------------------------------------------

class TestOverlapDetection:
    """TC-4: Overlap detection raises BLOCKED when two slices touch the same file."""

    def test_no_overlap_returns_empty(self) -> None:
        reports = [
            {"slice-A": ["foo.py", "tests/test_foo.py"]},
            {"slice-B": ["bar.py", "tests/test_bar.py"]},
        ]
        violations = detect_overlap(reports)
        assert violations == []

    def test_overlap_one_file_surfaced(self) -> None:
        reports = [
            {"slice-A": ["foo.py", "shared.py"]},
            {"slice-B": ["bar.py", "shared.py"]},
        ]
        violations = detect_overlap(reports)
        assert len(violations) == 1
        assert "shared.py" in violations[0]

    def test_overlap_violation_contains_blocked_prefix(self) -> None:
        reports = [
            {"slice-A": ["shared.py"]},
            {"slice-B": ["shared.py"]},
        ]
        violations = detect_overlap(reports)
        assert violations[0].startswith("🚧 BLOCKED:")

    def test_overlap_violation_names_both_slices(self) -> None:
        reports = [
            {"slice-A": ["shared.py"]},
            {"slice-B": ["shared.py"]},
        ]
        violations = detect_overlap(reports)
        assert "slice-A" in violations[0]
        assert "slice-B" in violations[0]

    def test_multiple_overlapping_files(self) -> None:
        reports = [
            {"slice-A": ["foo.py", "bar.py"]},
            {"slice-B": ["bar.py", "baz.py"]},
            {"slice-C": ["baz.py"]},
        ]
        violations = detect_overlap(reports)
        # bar.py: slice-A vs slice-B, baz.py: slice-B vs slice-C
        assert len(violations) == 2


# ---------------------------------------------------------------------------
# TC-5: Worktree cleanup — empty-diff Builder → worktree removed (TA-LOW-02)
# ---------------------------------------------------------------------------

class TestWorktreeCleanup:
    """TC-5: Worktrees with empty diffs are returned for cleanup (git worktree remove).

    Implements TA-LOW-02: explicit git worktree remove <path> step for the
    empty-diff case so no empty-diff worktrees are left behind.
    """

    def test_empty_diff_worktree_scheduled_for_removal(self) -> None:
        worktree_diffs = {
            "/tmp/wt-slice-A": True,   # has changes
            "/tmp/wt-slice-B": False,  # empty diff → must be removed
        }
        to_remove = plan_worktree_cleanup(worktree_diffs)
        assert "/tmp/wt-slice-B" in to_remove

    def test_non_empty_diff_not_scheduled(self) -> None:
        worktree_diffs = {
            "/tmp/wt-slice-A": True,
            "/tmp/wt-slice-B": False,
        }
        to_remove = plan_worktree_cleanup(worktree_diffs)
        assert "/tmp/wt-slice-A" not in to_remove

    def test_all_empty_all_removed(self) -> None:
        worktree_diffs = {
            "/tmp/wt-slice-A": False,
            "/tmp/wt-slice-B": False,
        }
        to_remove = plan_worktree_cleanup(worktree_diffs)
        assert len(to_remove) == 2

    def test_no_empty_diff_nothing_removed(self) -> None:
        worktree_diffs = {
            "/tmp/wt-slice-A": True,
            "/tmp/wt-slice-B": True,
        }
        to_remove = plan_worktree_cleanup(worktree_diffs)
        assert to_remove == []


# ---------------------------------------------------------------------------
# TC-6: Telemetry — parallel invocations use builder-slice-<N> naming
# ---------------------------------------------------------------------------

class TestTelemetryNaming:
    """TC-6: Parallel Builder invocations are named builder-slice-<N> for telemetry."""

    def test_single_slice_naming(self) -> None:
        names = plan_telemetry_agent_names(1)
        assert names == ["builder-slice-1"]

    def test_four_slice_naming(self) -> None:
        names = plan_telemetry_agent_names(4)
        assert names == ["builder-slice-1", "builder-slice-2", "builder-slice-3", "builder-slice-4"]

    def test_naming_is_one_indexed(self) -> None:
        names = plan_telemetry_agent_names(3)
        assert names[0] == "builder-slice-1"
        assert names[-1] == "builder-slice-3"

    def test_naming_pattern_matches_expected_regex(self) -> None:
        names = plan_telemetry_agent_names(4)
        pattern = re.compile(r"^builder-slice-\d+$")
        for name in names:
            assert pattern.match(name), f"{name!r} does not match builder-slice-<N> pattern"

    def test_auto_implement_md_uses_builder_slice_naming(self) -> None:
        """Smoke: auto-implement.md must reference builder-slice-<N> pattern."""
        auto_impl = Path(__file__).parent.parent / ".claude" / "commands" / "auto-implement.md"
        content = auto_impl.read_text()
        assert "builder-slice-" in content, (
            "auto-implement.md does not contain 'builder-slice-' telemetry naming"
        )


# ---------------------------------------------------------------------------
# TestDocAnchors: pin auto-implement.md contracts to helper constants
# ---------------------------------------------------------------------------

class TestDocAnchors:
    """Doc-anchor assertions: verify auto-implement.md contains the constants
    the T18 helpers rely on, so constant drift is caught by CI.

    Reads auto-implement.md once and asserts three contracts:
    1. Concurrency-cap (≤4 slices) is documented.
    2. Exact BLOCKED prefix the spec mandates is present verbatim.
    3. Worktree cleanup step and empty-diff case are both documented.
    """

    @staticmethod
    def _load_auto_implement() -> str:
        path = Path(__file__).parent.parent / ".claude" / "commands" / "auto-implement.md"
        return path.read_text()

    def test_concurrency_cap_documented(self) -> None:
        """auto-implement.md must document the ≤4 concurrency cap."""
        content = self._load_auto_implement()
        assert re.search(r"≤4|cap.*4|4.*slice", content, re.IGNORECASE), (
            "auto-implement.md does not document the ≤4 concurrency cap"
        )

    def test_blocked_prefix_present_verbatim(self) -> None:
        """Exact BLOCKED prefix the spec mandates must appear verbatim."""
        content = self._load_auto_implement()
        assert "🚧 BLOCKED: parallel-Builder overlap detected" in content, (
            "auto-implement.md does not contain the exact BLOCKED prefix "
            "'🚧 BLOCKED: parallel-Builder overlap detected'"
        )

    def test_worktree_cleanup_documented(self) -> None:
        """auto-implement.md must document git worktree remove and empty-diff."""
        content = self._load_auto_implement()
        assert "git worktree remove" in content, (
            "auto-implement.md does not contain 'git worktree remove'"
        )
        assert "empty-diff" in content, (
            "auto-implement.md does not contain 'empty-diff'"
        )
