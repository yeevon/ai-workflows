"""Iter-shipped emission tests — 3-iteration autopilot run simulation.

Task: M20 Task 04 — Cross-task iteration compaction
  (iter_<N>-shipped.md at autopilot iteration boundaries).

This module verifies:
- After each iteration, the orchestrator emits
  ``runs/autopilot-<run-ts>-iter<N>-shipped.md`` at the flat hyphenated path
  (NOT a per-run subdirectory form — flat layout matches today's autopilot.md
  convention per round-2 user arbitration; no migration needed).
- Each artifact parses to the expected structure (all required keys present).
- The artifact contains the correct verdict, commit SHA, and reviewer verdicts
  for PROCEED iterations.
- Earlier artifacts are unchanged after later iterations write their own.
- Iterations are independent: iter-2 and iter-3 artifacts do NOT reflect
  iter-1's chat history.

Path naming convention (§Path convention in autopilot.md):
  ``runs/autopilot-<run-ts>-iter<N>-shipped.md``  (close-out artifact, T04)
  ``runs/autopilot-<run-ts>-iter<N>.md``           (kick-off recommendation file, pre-T04)
Both are siblings under the flat ``runs/`` directory.  The ``-shipped.md`` suffix
distinguishes close-out from kick-off.  No per-run subdirectory.

Per-AC coverage:
  AC-1 — autopilot.md Step D writes iter-shipped artifact per iteration boundary.
          (Simulated here with ``make_iter_shipped``; autopilot.md prose change
          verified by smoke-test grep; structural rule tested in this file.)
  AC-3 — Path naming convention documented in autopilot.md per §Path convention.
          (Test descriptions and assertions use the flat hyphenated path form
          ``runs/autopilot-<run-ts>-iter<N>-shipped.md``; carry-over L2 round 4.)
  AC-4 — ``tests/orchestrator/test_iter_shipped_emission.py`` passes for the
          3-iteration simulation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.orchestrator._helpers import (
    ITER_SHIPPED_PROCEED_SECTIONS,
    ITER_SHIPPED_REQUIRED_KEYS,
    make_iter_shipped,
    parse_iter_shipped,
)

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_RUN_TIMESTAMP = "20260427T152243Z"
_DATE = "2026-04-28"

# Task spec filenames used in the 3-iteration fixture (M12 tasks T01..T03).
_ITER1_TASK = "design_docs/phases/milestone_12_audit_cascade/task_01_auditor_tier_configs.md"
_ITER2_TASK = "design_docs/phases/milestone_12_audit_cascade/task_02_graph_adapter_coverage.md"
_ITER3_TASK = "design_docs/phases/milestone_12_audit_cascade/task_03_workflow_wiring.md"


# ---------------------------------------------------------------------------
# Helper: stub orchestrator that writes an iter-shipped artifact to tmp_path
# ---------------------------------------------------------------------------

def _stub_emit_iter_shipped(
    runs_dir: Path,
    run_timestamp: str,
    iteration: int,
    verdict: str,
    task_shipped: str | None = None,
    cycles: int = 2,
    commit_sha: str | None = None,
    reviewer_verdicts: dict[str, str] | None = None,
    carry_over: str = "",
) -> Path:
    """Simulate autopilot Step D: emit iter<N>-shipped.md at the flat hyphenated path.

    Creates the artifact at ``runs/autopilot-<run-ts>-iter<N>-shipped.md`` inside
    ``runs_dir``, mirroring what autopilot.md Step D does in production after Step B's
    AUTO-CLEAN or Step C's CLEAN/LOW-ONLY.

    The flat hyphenated path is authoritative per round-2 user arbitration (no per-run
    subdirectory; the ``-shipped.md`` suffix distinguishes close-out from kick-off).

    Args:
        runs_dir: Base ``runs/`` directory under tmp_path.
        run_timestamp: Run timestamp string (e.g. "20260427T152243Z").
        iteration: 1-based iteration index.
        verdict: One of ``PROCEED``, ``NEEDS-CLEAN-TASKS``, ``HALT-AND-ASK``.
        task_shipped: Task spec filename (for PROCEED verdict).
        cycles: Number of Builder→Auditor cycles (for PROCEED verdict).
        commit_sha: Final commit SHA (for PROCEED verdict).
        reviewer_verdicts: Dict of reviewer name → verdict (for PROCEED verdict).
        carry_over: Carry-over text for the next iteration (empty = "*(none)*").

    Returns:
        The ``Path`` to the written ``autopilot-<run-ts>-iter<N>-shipped.md`` file.
    """
    artifact_text = make_iter_shipped(
        run_timestamp=run_timestamp,
        iteration=iteration,
        date=_DATE,
        verdict=verdict,
        task_shipped=task_shipped,
        cycles=cycles,
        commit_sha=commit_sha or f"abc{iteration:04d}def",
        files_touched=[
            f"ai_workflows/workflows/task_{iteration:02d}.py",
            f"tests/workflows/test_task_{iteration:02d}.py",
            "CHANGELOG.md",
        ],
        auditor_verdict="PASS",
        reviewer_verdicts=reviewer_verdicts or {
            "sr-dev": "SHIP",
            "sr-sdet": "SHIP",
            "security": "SHIP",
            "dependency": "SHIP",
        },
        kdr_additions="none",
        carry_over=carry_over,
    )

    filename = f"autopilot-{run_timestamp}-iter{iteration}-shipped.md"
    artifact_path = runs_dir / filename
    artifact_path.write_text(artifact_text)
    return artifact_path


# ---------------------------------------------------------------------------
# Test class: 3-iteration simulation
# ---------------------------------------------------------------------------

class TestIterShippedEmission:
    """3-iteration autopilot run simulation; validates iter-shipped artifact emission."""

    @pytest.fixture()
    def runs_dir(self, tmp_path: Path) -> Path:
        """Create ``runs/`` under tmp_path."""
        d = tmp_path / "runs"
        d.mkdir(parents=True)
        return d

    # ------------------------------------------------------------------
    # Iter 1: PROCEED verdict
    # ------------------------------------------------------------------

    def test_iter_1_shipped_exists(self, runs_dir: Path) -> None:
        """After iter 1 the orchestrator emits autopilot-<run-ts>-iter1-shipped.md."""
        artifact_path = _stub_emit_iter_shipped(
            runs_dir=runs_dir,
            run_timestamp=_RUN_TIMESTAMP,
            iteration=1,
            verdict="PROCEED",
            task_shipped=_ITER1_TASK,
            cycles=2,
            commit_sha="a1b2c3d",
        )

        # Flat hyphenated form: autopilot-<run-ts>-iter1-shipped.md
        expected_path = runs_dir / f"autopilot-{_RUN_TIMESTAMP}-iter1-shipped.md"
        assert artifact_path == expected_path
        assert artifact_path.exists()

    def test_iter_1_shipped_structure(self, runs_dir: Path) -> None:
        """autopilot-<run-ts>-iter1-shipped.md contains all required keys."""
        artifact_path = _stub_emit_iter_shipped(
            runs_dir=runs_dir,
            run_timestamp=_RUN_TIMESTAMP,
            iteration=1,
            verdict="PROCEED",
            task_shipped=_ITER1_TASK,
            cycles=2,
            commit_sha="a1b2c3d",
        )

        text = artifact_path.read_text()
        parsed = parse_iter_shipped(text)

        for required_key in ITER_SHIPPED_REQUIRED_KEYS:
            key = required_key.strip("*").rstrip(":")
            assert key in parsed, (
                f"Required key {required_key!r} missing from iter1-shipped artifact. "
                f"Present keys: {list(parsed.keys())}"
            )

    def test_iter_1_shipped_verdict_recorded(self, runs_dir: Path) -> None:
        """iter1-shipped artifact records the queue-pick verdict PROCEED."""
        artifact_path = _stub_emit_iter_shipped(
            runs_dir=runs_dir,
            run_timestamp=_RUN_TIMESTAMP,
            iteration=1,
            verdict="PROCEED",
            task_shipped=_ITER1_TASK,
            cycles=2,
            commit_sha="a1b2c3d",
        )

        text = artifact_path.read_text()
        parsed = parse_iter_shipped(text)
        assert parsed.get("Verdict from queue-pick") == "PROCEED", (
            "Verdict from queue-pick must be 'PROCEED' in the iter1-shipped artifact."
        )

    def test_iter_1_shipped_commit_sha_recorded(self, runs_dir: Path) -> None:
        """iter1-shipped artifact records the commit SHA and reviewer verdicts."""
        commit_sha = "a1b2c3d4e5f"
        artifact_path = _stub_emit_iter_shipped(
            runs_dir=runs_dir,
            run_timestamp=_RUN_TIMESTAMP,
            iteration=1,
            verdict="PROCEED",
            task_shipped=_ITER1_TASK,
            cycles=2,
            commit_sha=commit_sha,
            reviewer_verdicts={
                "sr-dev": "SHIP",
                "sr-sdet": "SHIP",
                "security": "SHIP",
                "dependency": "SHIP",
            },
        )

        text = artifact_path.read_text()
        assert commit_sha in text, (
            f"Commit SHA {commit_sha!r} must appear in the iter1-shipped artifact."
        )
        assert "sr-dev=SHIP" in text, (
            "Reviewer verdict 'sr-dev=SHIP' must appear in the iter1-shipped artifact."
        )
        assert "sr-sdet=SHIP" in text, (
            "Reviewer verdict 'sr-sdet=SHIP' must appear in the iter1-shipped artifact."
        )

    def test_iter_1_shipped_has_proceed_sections(self, runs_dir: Path) -> None:
        """iter1-shipped artifact for PROCEED contains all required section headers."""
        artifact_path = _stub_emit_iter_shipped(
            runs_dir=runs_dir,
            run_timestamp=_RUN_TIMESTAMP,
            iteration=1,
            verdict="PROCEED",
            task_shipped=_ITER1_TASK,
            cycles=2,
            commit_sha="a1b2c3d",
        )

        text = artifact_path.read_text()
        for section in ITER_SHIPPED_PROCEED_SECTIONS:
            assert section in text, (
                f"Required section {section!r} missing from iter1-shipped artifact "
                f"(PROCEED verdict)."
            )

    # ------------------------------------------------------------------
    # Iter 2: PROCEED verdict; iter1-shipped unchanged
    # ------------------------------------------------------------------

    def test_iter_2_shipped_exists(self, runs_dir: Path) -> None:
        """After iter 2 the orchestrator emits autopilot-<run-ts>-iter2-shipped.md."""
        _stub_emit_iter_shipped(
            runs_dir=runs_dir,
            run_timestamp=_RUN_TIMESTAMP,
            iteration=1,
            verdict="PROCEED",
            task_shipped=_ITER1_TASK,
            cycles=2,
            commit_sha="a1b2c3d",
        )

        artifact_path = _stub_emit_iter_shipped(
            runs_dir=runs_dir,
            run_timestamp=_RUN_TIMESTAMP,
            iteration=2,
            verdict="PROCEED",
            task_shipped=_ITER2_TASK,
            cycles=3,
            commit_sha="b2c3d4e",
        )

        expected_path = runs_dir / f"autopilot-{_RUN_TIMESTAMP}-iter2-shipped.md"
        assert artifact_path == expected_path
        assert artifact_path.exists()

    def test_iter_1_shipped_unchanged_after_iter_2(self, runs_dir: Path) -> None:
        """autopilot-<run-ts>-iter1-shipped.md is not modified when iter2 is written."""
        iter1_path = _stub_emit_iter_shipped(
            runs_dir=runs_dir,
            run_timestamp=_RUN_TIMESTAMP,
            iteration=1,
            verdict="PROCEED",
            task_shipped=_ITER1_TASK,
            cycles=2,
            commit_sha="a1b2c3d",
        )
        original_text = iter1_path.read_text()
        original_mtime = iter1_path.stat().st_mtime

        _stub_emit_iter_shipped(
            runs_dir=runs_dir,
            run_timestamp=_RUN_TIMESTAMP,
            iteration=2,
            verdict="PROCEED",
            task_shipped=_ITER2_TASK,
            cycles=3,
            commit_sha="b2c3d4e",
        )

        # iter1-shipped must be byte-for-byte unchanged
        assert iter1_path.read_text() == original_text
        assert iter1_path.stat().st_mtime == original_mtime

    # ------------------------------------------------------------------
    # Iter 3: PROCEED verdict; all three coexist independently
    # ------------------------------------------------------------------

    def test_iter_3_shipped_exists(self, runs_dir: Path) -> None:
        """After iter 3 the orchestrator emits autopilot-<run-ts>-iter3-shipped.md."""
        for i, (task, sha, cycles) in enumerate(
            [
                (_ITER1_TASK, "a1b2c3d", 2),
                (_ITER2_TASK, "b2c3d4e", 3),
            ],
            start=1,
        ):
            _stub_emit_iter_shipped(
                runs_dir=runs_dir,
                run_timestamp=_RUN_TIMESTAMP,
                iteration=i,
                verdict="PROCEED",
                task_shipped=task,
                cycles=cycles,
                commit_sha=sha,
            )

        artifact_path = _stub_emit_iter_shipped(
            runs_dir=runs_dir,
            run_timestamp=_RUN_TIMESTAMP,
            iteration=3,
            verdict="PROCEED",
            task_shipped=_ITER3_TASK,
            cycles=1,
            commit_sha="c3d4e5f",
        )

        expected_path = runs_dir / f"autopilot-{_RUN_TIMESTAMP}-iter3-shipped.md"
        assert artifact_path == expected_path
        assert artifact_path.exists()

    def test_all_three_iterations_coexist(self, runs_dir: Path) -> None:
        """All three iter-shipped artifacts exist independently after the 3-iteration loop."""
        params = [
            (1, _ITER1_TASK, "a1b2c3d", 2),
            (2, _ITER2_TASK, "b2c3d4e", 3),
            (3, _ITER3_TASK, "c3d4e5f", 1),
        ]
        for iteration, task, sha, cycles in params:
            _stub_emit_iter_shipped(
                runs_dir=runs_dir,
                run_timestamp=_RUN_TIMESTAMP,
                iteration=iteration,
                verdict="PROCEED",
                task_shipped=task,
                cycles=cycles,
                commit_sha=sha,
            )

        for iteration in range(1, 4):
            expected = runs_dir / f"autopilot-{_RUN_TIMESTAMP}-iter{iteration}-shipped.md"
            assert expected.exists(), (
                f"autopilot-<run-ts>-iter{iteration}-shipped.md should exist "
                "after the 3-iteration loop."
            )

    def test_iter_3_shipped_structure(self, runs_dir: Path) -> None:
        """autopilot-<run-ts>-iter3-shipped.md contains all required keys."""
        artifact_path = _stub_emit_iter_shipped(
            runs_dir=runs_dir,
            run_timestamp=_RUN_TIMESTAMP,
            iteration=3,
            verdict="PROCEED",
            task_shipped=_ITER3_TASK,
            cycles=1,
            commit_sha="c3d4e5f",
        )

        text = artifact_path.read_text()
        parsed = parse_iter_shipped(text)

        for required_key in ITER_SHIPPED_REQUIRED_KEYS:
            key = required_key.strip("*").rstrip(":")
            assert key in parsed, (
                f"Required key {required_key!r} missing from iter3-shipped artifact. "
                f"Present keys: {list(parsed.keys())}"
            )

    # ------------------------------------------------------------------
    # Cycles independence: iter-2 does NOT reflect iter-1 chat history
    # ------------------------------------------------------------------

    def test_iter_3_shipped_does_not_contain_iter_1_task(self, runs_dir: Path) -> None:
        """iter3-shipped artifact is independent: it does not contain iter-1's task text.

        Discriminating two-part assertion:
        1. Assert iter-3's own task IS present in iter3-shipped (proves the artifact
           records the correct task shipped in iter 3).
        2. Assert iter-1's task is NOT present in iter3-shipped (proves the artifact
           is a per-iteration record, not an accumulation of all prior iterations).

        This is a structural test of the per-iteration artifact format.  The cross-task
        context-constancy property is tested in ``test_cross_task_context_constant.py``.
        """
        iter1_task_marker = _ITER1_TASK
        iter3_task_marker = _ITER3_TASK

        # Emit iter-1 and iter-2 first (realistic multi-iteration scenario).
        _stub_emit_iter_shipped(
            runs_dir=runs_dir,
            run_timestamp=_RUN_TIMESTAMP,
            iteration=1,
            verdict="PROCEED",
            task_shipped=iter1_task_marker,
            cycles=2,
            commit_sha="a1b2c3d",
        )
        _stub_emit_iter_shipped(
            runs_dir=runs_dir,
            run_timestamp=_RUN_TIMESTAMP,
            iteration=2,
            verdict="PROCEED",
            task_shipped=_ITER2_TASK,
            cycles=3,
            commit_sha="b2c3d4e",
        )

        iter3_path = _stub_emit_iter_shipped(
            runs_dir=runs_dir,
            run_timestamp=_RUN_TIMESTAMP,
            iteration=3,
            verdict="PROCEED",
            task_shipped=iter3_task_marker,
            cycles=1,
            commit_sha="c3d4e5f",
        )

        iter3_text = iter3_path.read_text()

        # Part 1: iter-3's own task IS present in iter3-shipped.
        assert iter3_task_marker in iter3_text, (
            f"iter3-shipped artifact must contain iter-3's task path "
            f"{iter3_task_marker!r} — the artifact should record what was shipped "
            "in this iteration."
        )

        # Part 2: iter-1's task is NOT present in iter3-shipped.
        assert iter1_task_marker not in iter3_text, (
            f"iter3-shipped artifact must NOT contain iter-1's task path "
            f"{iter1_task_marker!r} — each iter-shipped artifact is an independent "
            "record for that iteration only, not an accumulation of prior iterations."
        )

    # ------------------------------------------------------------------
    # Header format
    # ------------------------------------------------------------------

    def test_iter_shipped_header_format(self, runs_dir: Path) -> None:
        """Iter-shipped artifact begins with '# Autopilot iter N — shipped' header."""
        artifact_path = _stub_emit_iter_shipped(
            runs_dir=runs_dir,
            run_timestamp=_RUN_TIMESTAMP,
            iteration=2,
            verdict="PROCEED",
            task_shipped=_ITER2_TASK,
            cycles=2,
            commit_sha="b2c3d4e",
        )
        text = artifact_path.read_text()
        assert text.startswith("# Autopilot iter 2 — shipped"), (
            f"Artifact must start with '# Autopilot iter N — shipped'. "
            f"Actual start: {text[:60]!r}"
        )

    def test_iter_shipped_telemetry_section_placeholder(self, runs_dir: Path) -> None:
        """Iter-shipped artifact contains Telemetry summary section (empty placeholder).

        The Telemetry summary section is empty at T04 land time and will be
        retrofitted by T22 (per-cycle telemetry) when it lands.  The section
        header must be present now so T22 can find it.
        """
        artifact_path = _stub_emit_iter_shipped(
            runs_dir=runs_dir,
            run_timestamp=_RUN_TIMESTAMP,
            iteration=1,
            verdict="PROCEED",
            task_shipped=_ITER1_TASK,
            cycles=2,
            commit_sha="a1b2c3d",
        )
        text = artifact_path.read_text()
        assert "## Telemetry summary" in text, (
            "Iter-shipped artifact must contain '## Telemetry summary' section header. "
            "T22 (per-cycle telemetry) will populate it; T04 ships the placeholder."
        )

    # ------------------------------------------------------------------
    # Alternative verdict branches: NEEDS-CLEAN-TASKS and HALT-AND-ASK
    # (FIX-SDET-01: cycle-2 carry-over — cover the two unexercised branches)
    # ------------------------------------------------------------------

    def test_iter_shipped_needs_clean_tasks_structure(self) -> None:
        """make_iter_shipped with NEEDS-CLEAN-TASKS emits the milestone-work section.

        Exercises the ``NEEDS-CLEAN-TASKS`` branch of ``make_iter_shipped`` (lines
        694–703 in ``_helpers.py``).  A regression that silently dropped this branch
        would produce an artifact missing the section header and the milestone value,
        causing this test to fail.

        No file I/O needed — the test operates on the in-memory string returned by
        ``make_iter_shipped`` directly, consistent with the pure string-construction
        pattern used by the other tests when they read ``artifact_path.read_text()``.
        """
        milestone = "milestone_15_mcp_surface"
        text = make_iter_shipped(
            run_timestamp=_RUN_TIMESTAMP,
            iteration=2,
            date=_DATE,
            verdict="NEEDS-CLEAN-TASKS",
            clean_tasks_milestone=milestone,
        )

        assert "## Milestone work (if NEEDS-CLEAN-TASKS)" in text, (
            "NEEDS-CLEAN-TASKS artifact must contain "
            "'## Milestone work (if NEEDS-CLEAN-TASKS)' section header."
        )
        assert milestone in text, (
            f"NEEDS-CLEAN-TASKS artifact must contain the milestone string "
            f"{milestone!r} in the body."
        )

    def test_iter_shipped_halt_and_ask_structure(self) -> None:
        """make_iter_shipped with HALT-AND-ASK emits the halt section.

        Exercises the ``HALT-AND-ASK`` branch of ``make_iter_shipped`` (lines
        704–714 in ``_helpers.py``).  A regression that silently dropped this branch
        would produce an artifact missing the section header and the halt reason,
        causing this test to fail.

        No file I/O needed — the test operates on the in-memory string returned by
        ``make_iter_shipped`` directly, consistent with the pure string-construction
        pattern used by the other tests when they read ``artifact_path.read_text()``.
        """
        halt_reason = "Architect returned two options without a recommendation."
        text = make_iter_shipped(
            run_timestamp=_RUN_TIMESTAMP,
            iteration=3,
            date=_DATE,
            verdict="HALT-AND-ASK",
            halt_reason=halt_reason,
        )

        assert "## Halt (if HALT-AND-ASK)" in text, (
            "HALT-AND-ASK artifact must contain '## Halt (if HALT-AND-ASK)' "
            "section header."
        )
        assert halt_reason in text, (
            f"HALT-AND-ASK artifact must contain the halt reason string "
            f"{halt_reason!r} in the body."
        )
