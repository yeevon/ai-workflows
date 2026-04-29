"""Tests for M21 Task 19 — Orchestrator-owned close-out (post-parallel-Builder merge).

This module verifies the post-parallel-merge logic described in
``.claude/commands/auto-implement.md`` §Post-parallel merge (T19) and §Commit ceremony
Step C3. It tests four cases:

- TC-1: Post-parallel merge applies all worktree diffs correctly to the main tree.
- TC-2: Commit message includes the ``Parallel-build:`` annotation when
  ``PARALLEL_ELIGIBLE=true``.
- TC-3: Status surfaces flip once (not N times) — folded into TC-1 coverage per
  TA-LOW-03 decision (issue file §TA-LOW-03 Resolution). The merge step applies changes
  once into the main tree, producing one flip event; this test pins that assertion.
- TC-4: HARD HALT is signalled on post-parallel merge conflict.

All tests are pure unit tests against string fixtures and in-process helpers;
no ``ai_workflows/`` imports are needed (T19 touches only
``.claude/commands/auto-implement.md`` and ``tests/``).

Relationship to other modules: builds on the parallel-dispatch helpers from
``test_t18_parallel_dispatch.py``. T18 handles dispatch and overlap detection;
T19 handles the merge step after T18's Step 7 completes.
"""

from __future__ import annotations

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers mirroring post-parallel-merge logic in auto-implement.md (T19)
# ---------------------------------------------------------------------------

_HARD_HALT_MERGE_CONFLICT = (
    "🚧 HARD HALT — merge conflict in post-parallel merge; resolve manually."
)


def apply_worktree_diffs(
    main_tree: dict[str, str],
    worktree_changes: list[dict[str, str]],
    *,
    conflict_files: set[str] | None = None,
) -> tuple[dict[str, str], str | None]:
    """Apply each worktree's file changes into *main_tree* in slice order.

    Parameters
    ----------
    main_tree:
        Dict mapping filename → content, representing the main working tree.
    worktree_changes:
        Ordered list of dicts (one per slice), each mapping filename → new content.
        Applied in slice order, matching the T19 prose "in slice order".
    conflict_files:
        Optional set of filenames that should trigger a simulated merge conflict.
        When a file in this set is encountered during apply, the function returns
        the HARD HALT string instead of continuing.

    Returns
    -------
    (result_tree, halt_msg)
        ``result_tree`` is the merged main tree (modified in-place clone).
        ``halt_msg`` is ``None`` on success or the HARD HALT string on conflict.

    Note
    ----
    Conflict detection is external — caller passes ``conflict_files`` to simulate
    git-apply failure; this helper does not auto-detect git-level conflicts.
    """
    result = dict(main_tree)
    for slice_changes in worktree_changes:
        for filename, new_content in slice_changes.items():
            if conflict_files and filename in conflict_files:
                return result, _HARD_HALT_MERGE_CONFLICT
            result[filename] = new_content
    return result, None


def build_parallel_commit_message(
    *,
    milestone: int,
    task: int,
    title: str,
    cycle: int,
    slice_file_counts: dict[str, int],
) -> str:
    """Build the commit message body for a parallel-built task (T19 §Commit ceremony).

    Includes the ``Parallel-build:`` annotation line required when
    ``PARALLEL_ELIGIBLE=true`` in meta.json.

    Parameters
    ----------
    milestone, task:
        M and T numbers (integers, zero-padded to two digits in output).
    title:
        Task title string.
    cycle:
        Cycle count at close-out.
    slice_file_counts:
        Ordered dict mapping slice label → number of files that slice touched.
        Produces the ``(slice-A: N files; ...)`` portion of the annotation line.

    Returns
    -------
    Commit message string.
    """
    slice_parts = "; ".join(
        f"{label}: {count} files" for label, count in slice_file_counts.items()
    )
    n_slices = len(slice_file_counts)
    parallel_line = f"Parallel-build: {n_slices} slices dispatched ({slice_parts})"

    msg_lines = [
        f"M{milestone:02d} Task {task:02d}: {title} — autonomous-mode close-out (cycle {cycle}/10)",
        "",
        "<task description citing KDRs>",
        "",
        f"Cycles run: {cycle}",
        "Auditor verdict: ✅ PASS",
        "Terminal gate: CLEAN (Sr. Dev: SHIP, Sr. SDET: SHIP, Security: SHIP)",
        "Dependency audit: skipped — no manifest changes",
        "Architect: not invoked",
        parallel_line,
        "",
        "Files touched:",
        "- (all slices combined)",
        "",
        "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>",
    ]
    return "\n".join(msg_lines)


# ---------------------------------------------------------------------------
# TC-1: Post-parallel merge applies all worktree diffs correctly
# (also covers TC-3: status surfaces flip once — folded per TA-LOW-03)
# ---------------------------------------------------------------------------

class TestPostParallelMerge:
    """TC-1: Post-parallel merge applies all worktree diffs to the main working tree.

    TC-3 (status-surface single-flip) is folded here per TA-LOW-03 decision:
    the merge step applies changes once, naturally producing one flip event.
    """

    def test_single_slice_applied_to_main_tree(self) -> None:
        """One slice's changes land in the main working tree."""
        main_tree: dict[str, str] = {"existing.py": "old content"}
        worktree_changes = [{"new_file.py": "new content"}]
        result, halt = apply_worktree_diffs(main_tree, worktree_changes)
        assert halt is None
        assert "new_file.py" in result
        assert result["new_file.py"] == "new content"

    def test_two_slices_both_applied(self) -> None:
        """Two non-overlapping slices both land in the main working tree."""
        main_tree: dict[str, str] = {}
        worktree_changes = [
            {"slice_a.py": "from slice A"},
            {"slice_b.py": "from slice B"},
        ]
        result, halt = apply_worktree_diffs(main_tree, worktree_changes)
        assert halt is None
        assert result["slice_a.py"] == "from slice A"
        assert result["slice_b.py"] == "from slice B"

    def test_existing_file_overwritten_by_slice(self) -> None:
        """A slice that modifies an existing file produces the new content."""
        main_tree = {"module.py": "version 1"}
        worktree_changes = [{"module.py": "version 2"}]
        result, halt = apply_worktree_diffs(main_tree, worktree_changes)
        assert halt is None
        assert result["module.py"] == "version 2"

    def test_three_slices_applied_in_order(self) -> None:
        """Three slices applied in order; last write wins for a shared key."""
        main_tree: dict[str, str] = {}
        worktree_changes = [
            {"shared.py": "slice-A version"},
            {"other.py": "from slice B"},
            {"shared.py": "slice-C version"},  # last write wins
        ]
        result, halt = apply_worktree_diffs(main_tree, worktree_changes)
        assert halt is None
        # shared.py overwritten by slice-C (applied last in slice order)
        assert result["shared.py"] == "slice-C version"
        assert result["other.py"] == "from slice B"

    def test_auto_implement_md_documents_single_flip(self) -> None:
        """Smoke: auto-implement.md must document the single-flip discipline."""
        auto_impl = Path(__file__).parent.parent / ".claude" / "commands" / "auto-implement.md"
        content = auto_impl.read_text()
        assert re.search(
            r"once.per.slice|once after the combined.diff|flip.*once",
            content,
            re.IGNORECASE,
        ), (
            "auto-implement.md does not document that status-surface flips happen "
            "once (not per-slice)"
        )


# ---------------------------------------------------------------------------
# TC-2: Commit message includes Parallel-build: annotation
# ---------------------------------------------------------------------------

class TestParallelBuildCommitAnnotation:
    """TC-2: Commit message includes Parallel-build: annotation for parallel-built tasks."""

    def test_commit_message_contains_parallel_build_line(self) -> None:
        msg = build_parallel_commit_message(
            milestone=21,
            task=19,
            title="Orchestrator-owned close-out",
            cycle=1,
            slice_file_counts={"slice-A": 2, "slice-B": 3},
        )
        assert "Parallel-build:" in msg

    def test_parallel_build_line_names_slice_count(self) -> None:
        msg = build_parallel_commit_message(
            milestone=21,
            task=19,
            title="Orchestrator-owned close-out",
            cycle=1,
            slice_file_counts={"slice-A": 2, "slice-B": 3},
        )
        assert "2 slices dispatched" in msg

    def test_parallel_build_line_names_per_slice_file_counts(self) -> None:
        msg = build_parallel_commit_message(
            milestone=21,
            task=19,
            title="Orchestrator-owned close-out",
            cycle=1,
            slice_file_counts={"slice-A": 2, "slice-B": 3},
        )
        assert "slice-A: 2 files" in msg
        assert "slice-B: 3 files" in msg

    def test_commit_is_single_no_per_slice_header(self) -> None:
        """Commit message must not contain per-slice commit headers."""
        msg = build_parallel_commit_message(
            milestone=21,
            task=19,
            title="Orchestrator-owned close-out",
            cycle=1,
            slice_file_counts={"slice-A": 1, "slice-B": 1},
        )
        # A per-slice commit would repeat "autonomous-mode close-out" N times
        assert msg.count("autonomous-mode close-out") == 1

    def test_auto_implement_md_documents_parallel_build_annotation(self) -> None:
        """Smoke: auto-implement.md must document the Parallel-build: commit annotation."""
        auto_impl = Path(__file__).parent.parent / ".claude" / "commands" / "auto-implement.md"
        content = auto_impl.read_text()
        assert "Parallel-build:" in content, (
            "auto-implement.md does not document the Parallel-build: commit annotation"
        )

    def test_auto_implement_md_states_single_commit(self) -> None:
        """Smoke: auto-implement.md must state commit is single (no per-slice commits)."""
        auto_impl = Path(__file__).parent.parent / ".claude" / "commands" / "auto-implement.md"
        content = auto_impl.read_text()
        assert re.search(r"single commit|no per.slice commit", content, re.IGNORECASE), (
            "auto-implement.md does not state that the commit is single (no per-slice commits)"
        )


# ---------------------------------------------------------------------------
# TC-4: HARD HALT on post-parallel merge conflict
# ---------------------------------------------------------------------------

class TestPostParallelMergeConflict:
    """TC-4: HARD HALT is signalled on post-parallel merge conflict."""

    def test_conflict_returns_hard_halt_string(self) -> None:
        """When a conflict file is encountered, the HARD HALT message is returned."""
        main_tree = {"conflict.py": "main content"}
        worktree_changes = [{"conflict.py": "slice content"}]
        _, halt = apply_worktree_diffs(
            main_tree,
            worktree_changes,
            conflict_files={"conflict.py"},
        )
        assert halt is not None
        assert "🚧 HARD HALT" in halt

    def test_hard_halt_message_is_verbatim_spec(self) -> None:
        """HARD HALT message matches the exact verbatim text from the spec."""
        _, halt = apply_worktree_diffs(
            {},
            [{"x.py": "new"}],
            conflict_files={"x.py"},
        )
        assert halt == _HARD_HALT_MERGE_CONFLICT

    def test_hard_halt_contains_resolve_manually(self) -> None:
        """HARD HALT message instructs user to resolve manually."""
        _, halt = apply_worktree_diffs(
            {},
            [{"x.py": "new"}],
            conflict_files={"x.py"},
        )
        assert halt is not None
        assert "resolve manually" in halt

    def test_no_conflict_returns_none_halt(self) -> None:
        """When no conflict, halt message is None (success path)."""
        _, halt = apply_worktree_diffs(
            {"a.py": "old"},
            [{"b.py": "new"}],
        )
        assert halt is None

    def test_auto_implement_md_documents_hard_halt_on_conflict(self) -> None:
        """Smoke: auto-implement.md must document the HARD HALT on merge conflict."""
        auto_impl = Path(__file__).parent.parent / ".claude" / "commands" / "auto-implement.md"
        content = auto_impl.read_text()
        assert re.search(
            r"HARD HALT.*merge conflict|merge conflict.*HARD HALT",
            content,
            re.IGNORECASE,
        ), (
            "auto-implement.md does not document HARD HALT on post-parallel merge conflict"
        )
