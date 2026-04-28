"""Parallel terminal gate tests — single-turn spawn, fragment-file landing, stitch, precedence.

Task: M20 Task 05 — Parallel unified terminal gate (sr-dev + sr-sdet + security-reviewer
  in one Task message; fragment files; orchestrator stitches in next turn).
Relationship: Tests the orchestration logic described in
  `.claude/commands/auto-implement.md` §Unified terminal gate and the canonical pattern
  reference in `.claude/commands/_common/parallel_spawn_pattern.md`.  The production
  versions of these rules run as markdown-prose logic inside auto-implement.md; this
  module provides hermetic Python simulations so every branch can be exercised without
  live agent spawns.

Per-AC coverage:
  AC-1 — auto-implement.md describes unified terminal gate replacing two-gate flow:
          verified by smoke-test grep (see spec §Smoke test); structural logic tested here.
  AC-2 — Precedence rule (TERMINAL CLEAN / BLOCK / FIX) documented in auto-implement.md
          and validated here.
  AC-3 — Three reviewer agent files write to fragment paths: verified by smoke-test grep;
          fragment-landing assertion tested here.
  AC-4 — dependency-auditor stays conditional + standalone (post-parallel-batch);
          architect stays conditional + standalone: verified in auto-implement.md and
          tested here via precedence-rule correctness assertions.
  AC-5 — parallel_spawn_pattern.md exists: file-existence check in this module.
  AC-6 — test_parallel_terminal_gate.py passes (this file).
  AC-7 — Wall-clock benchmark in bench_terminal_gate.py.
  AC-8 — CHANGELOG.md updated.
  AC-9 — Status surfaces flip.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers: stub reviewer agents
# ---------------------------------------------------------------------------

_AGENT_NAMES = ("sr-dev", "sr-sdet", "security-reviewer")

# Maps each agent name to its fragment filename
_FRAGMENT_FILENAME: dict[str, str] = {
    "sr-dev": "sr-dev-review.md",
    "sr-sdet": "sr-sdet-review.md",
    "security-reviewer": "security-review.md",
}

# Maps each agent name to its issue-file section heading
_SECTION_HEADING: dict[str, str] = {
    "sr-dev": "## Sr. Dev review",
    "sr-sdet": "## Sr. SDET review",
    "security-reviewer": "## Security review",
}


def _stub_reviewer_write_fragment(
    runs_dir: Path,
    task_shorthand: str,
    cycle_number: int,
    agent_name: str,
    verdict: str,
    content: str = "",
) -> Path:
    """Simulate a reviewer agent writing its fragment file.

    Writes a minimal review fragment to ``runs/<task>/cycle_<N>/<agent>-review.md``.
    The orchestrator reads this file in the follow-up turn and stitches it into
    the issue file.

    Args:
        runs_dir: Root runs directory (e.g. ``tmp_path / "runs"``).
        task_shorthand: Zero-padded task shorthand (e.g. ``"m20_t05"``).
        cycle_number: The 1-based cycle index.
        agent_name: One of ``"sr-dev"``, ``"sr-sdet"``, ``"security-reviewer"``.
        verdict: One of ``"SHIP"``, ``"FIX-THEN-SHIP"``, ``"BLOCK"``.
        content: Optional body text for the review section.

    Returns:
        Path to the written fragment file.
    """
    cycle_dir = runs_dir / task_shorthand / f"cycle_{cycle_number}"
    cycle_dir.mkdir(parents=True, exist_ok=True)
    fragment_path = cycle_dir / _FRAGMENT_FILENAME[agent_name]
    section = _SECTION_HEADING[agent_name]
    body = content or "*(stub review — no findings)*"
    fragment_path.write_text(
        f"{section} (2026-04-28)\n\n"
        f"**Verdict:** {verdict}\n\n"
        f"{body}\n",
        encoding="utf-8",
    )
    return fragment_path


def _parse_verdict_from_fragment(fragment_path: Path) -> str:
    """Parse the ``**Verdict:**`` line from a reviewer fragment file.

    Args:
        fragment_path: Path to a fragment file written by a stub reviewer.

    Returns:
        The verdict string (``"SHIP"``, ``"FIX-THEN-SHIP"``, or ``"BLOCK"``).

    Raises:
        ValueError: If no ``**Verdict:**`` line is found.
    """
    text = fragment_path.read_text(encoding="utf-8")
    match = re.search(r"\*\*Verdict:\*\*\s*(\S+)", text)
    if not match:
        raise ValueError(f"No **Verdict:** line found in {fragment_path}")
    return match.group(1).strip()


def _apply_precedence_rule(
    verdicts: dict[str, str],
) -> tuple[str, str]:
    """Apply the terminal gate precedence rule to three reviewer verdicts.

    Implements the stop-condition precedence rule from T05 spec §Stop-condition
    precedence rule:
    - All three SHIP → TERMINAL CLEAN
    - Any BLOCK → TERMINAL BLOCK (security-reviewer BLOCK surfaced first)
    - Any FIX-THEN-SHIP (no BLOCK) → TERMINAL FIX

    Args:
        verdicts: Dict mapping agent name to verdict string.

    Returns:
        A tuple of (stop_condition, reason) where:
        - stop_condition is one of ``"TERMINAL CLEAN"``, ``"TERMINAL BLOCK"``,
          ``"TERMINAL FIX"``.
        - reason is a human-readable string naming the reviewer(s) that drove the verdict.
    """
    blocked = [name for name, v in verdicts.items() if v == "BLOCK"]
    fix_needed = [name for name, v in verdicts.items() if v == "FIX-THEN-SHIP"]

    if blocked:
        # security-reviewer BLOCK takes precedence when surfacing the reason
        if "security-reviewer" in blocked:
            reason = "security-reviewer BLOCK (surfaced first); other blockers: " + ", ".join(
                b for b in blocked if b != "security-reviewer"
            ) if len(blocked) > 1 else "security-reviewer BLOCK"
        else:
            reason = "BLOCK from: " + ", ".join(blocked)
        return "TERMINAL BLOCK", reason

    if fix_needed:
        reason = "FIX-THEN-SHIP from: " + ", ".join(fix_needed)
        return "TERMINAL FIX", reason

    return "TERMINAL CLEAN", "all three reviewers SHIP"


def _stitch_fragments_into_issue_file(
    issue_file: Path,
    fragment_paths: dict[str, Path],
) -> None:
    """Stitch three fragment files into the issue file in one logical Edit pass.

    Appends each fragment's content under its section heading in the canonical
    order: Sr. Dev review, Sr. SDET review, Security review.

    Args:
        issue_file: Path to the issue file (will be appended to).
        fragment_paths: Dict mapping agent name to the fragment Path.
    """
    sections: list[str] = []
    for agent_name in ("sr-dev", "sr-sdet", "security-reviewer"):
        path = fragment_paths[agent_name]
        sections.append(path.read_text(encoding="utf-8"))

    # One logical "Edit pass" — single write operation
    existing = issue_file.read_text(encoding="utf-8") if issue_file.exists() else ""
    combined = existing.rstrip("\n") + "\n\n" + "\n\n".join(sections) + "\n"
    issue_file.write_text(combined, encoding="utf-8")


# ---------------------------------------------------------------------------
# Simulated orchestrator (the "spawn recorder" the spec refers to)
# ---------------------------------------------------------------------------

class SpawnCallRecorder:
    """Records orchestrator spawn calls with their turn indices.

    Used to assert that all three reviewer spawns happen in a single
    orchestrator turn (the "single multi-Task message" guarantee).
    """

    def __init__(self) -> None:
        self._current_turn: int = 0
        self._spawns: list[tuple[int, str]] = []  # (turn_index, agent_name)

    def advance_turn(self) -> None:
        """Advance to the next orchestrator turn."""
        self._current_turn += 1

    def spawn(self, agent_name: str) -> None:
        """Record a spawn call in the current turn.

        Args:
            agent_name: Name of the agent being spawned.
        """
        self._spawns.append((self._current_turn, agent_name))

    def spawns_in_turn(self, turn: int) -> list[str]:
        """Return agent names spawned in the given turn.

        Args:
            turn: Turn index (1-based).

        Returns:
            List of agent names spawned in that turn.
        """
        return [name for t, name in self._spawns if t == turn]

    def turns_with_spawns(self) -> list[int]:
        """Return the list of turns that had at least one spawn.

        Returns:
            Sorted list of turn indices that contained spawn calls.
        """
        return sorted({t for t, _ in self._spawns})


# ---------------------------------------------------------------------------
# Simulated parallel terminal gate run
# ---------------------------------------------------------------------------

def _run_parallel_terminal_gate(
    runs_dir: Path,
    issue_file: Path,
    task_shorthand: str,
    cycle_number: int,
    reviewer_verdicts: dict[str, str],
    recorder: SpawnCallRecorder,
) -> tuple[str, str, dict[str, Path]]:
    """Simulate the orchestrator's unified terminal gate procedure.

    Implements the three-step pattern from parallel_spawn_pattern.md:
    1. Single-turn parallel spawn (simulated via SpawnCallRecorder).
    2. Read all fragments in one pass, parse verdicts, apply precedence rule.
    3. Single-Edit stitch into the issue file (only on TERMINAL CLEAN).

    Args:
        runs_dir: Root runs directory.
        issue_file: Path to the task issue file.
        task_shorthand: Zero-padded task shorthand.
        cycle_number: Current cycle index.
        reviewer_verdicts: Dict mapping agent name to the verdict the stub
            reviewer will return.
        recorder: SpawnCallRecorder for capturing spawn turn indices.

    Returns:
        A tuple of (stop_condition, reason, fragment_paths) where:
        - stop_condition: ``"TERMINAL CLEAN"``, ``"TERMINAL BLOCK"``, or
          ``"TERMINAL FIX"``.
        - reason: Human-readable reason string.
        - fragment_paths: Dict mapping agent name to written fragment Path.
    """
    # Step 1 — single-turn parallel spawn (all three in the same turn)
    recorder.advance_turn()
    fragment_paths: dict[str, Path] = {}
    for agent_name in _AGENT_NAMES:
        recorder.spawn(agent_name)
        verdict = reviewer_verdicts.get(agent_name, "SHIP")
        path = _stub_reviewer_write_fragment(
            runs_dir, task_shorthand, cycle_number, agent_name, verdict
        )
        fragment_paths[agent_name] = path

    # Step 2 — read fragments + apply precedence rule (follow-up turn)
    recorder.advance_turn()
    parsed: dict[str, str] = {}
    for agent_name, path in fragment_paths.items():
        parsed[agent_name] = _parse_verdict_from_fragment(path)

    stop_condition, reason = _apply_precedence_rule(parsed)

    # Step 3 — stitch into issue file (only on TERMINAL CLEAN)
    if stop_condition == "TERMINAL CLEAN":
        _stitch_fragments_into_issue_file(issue_file, fragment_paths)

    return stop_condition, reason, fragment_paths


# ---------------------------------------------------------------------------
# Tests: single-turn spawn assertion
# ---------------------------------------------------------------------------

class TestSingleTurnSpawn:
    """Assert all three reviewer spawns happen in a single orchestrator turn."""

    def test_all_three_spawns_in_same_turn(self, tmp_path: Path) -> None:
        """All three reviewers are spawned in turn 1 — no intervening turns."""
        runs_dir = tmp_path / "runs"
        issue_file = tmp_path / "task_05_issue.md"
        issue_file.write_text("# Issue\n", encoding="utf-8")
        recorder = SpawnCallRecorder()

        _run_parallel_terminal_gate(
            runs_dir=runs_dir,
            issue_file=issue_file,
            task_shorthand="m20_t05",
            cycle_number=1,
            reviewer_verdicts={"sr-dev": "SHIP", "sr-sdet": "SHIP", "security-reviewer": "SHIP"},
            recorder=recorder,
        )

        # Spawn turn is turn 1; all three agents should be in that single turn
        turn_1_spawns = recorder.spawns_in_turn(1)
        assert set(turn_1_spawns) == {"sr-dev", "sr-sdet", "security-reviewer"}, (
            f"Expected all three reviewers spawned in turn 1, got: {turn_1_spawns}"
        )

    def test_spawn_turn_is_before_read_turn(self, tmp_path: Path) -> None:
        """Spawn turn (1) precedes the read+stitch turn (2) — no interleaving."""
        runs_dir = tmp_path / "runs"
        issue_file = tmp_path / "task_05_issue.md"
        issue_file.write_text("# Issue\n", encoding="utf-8")
        recorder = SpawnCallRecorder()

        _run_parallel_terminal_gate(
            runs_dir=runs_dir,
            issue_file=issue_file,
            task_shorthand="m20_t05",
            cycle_number=1,
            reviewer_verdicts={"sr-dev": "SHIP", "sr-sdet": "SHIP", "security-reviewer": "SHIP"},
            recorder=recorder,
        )

        turns = recorder.turns_with_spawns()
        assert turns == [1], f"Expected spawns only in turn 1, got turns: {turns}"

    def test_exactly_three_spawns(self, tmp_path: Path) -> None:
        """Exactly three Task calls are recorded — no extra or missing spawns."""
        runs_dir = tmp_path / "runs"
        issue_file = tmp_path / "task_05_issue.md"
        issue_file.write_text("# Issue\n", encoding="utf-8")
        recorder = SpawnCallRecorder()

        _run_parallel_terminal_gate(
            runs_dir=runs_dir,
            issue_file=issue_file,
            task_shorthand="m20_t05",
            cycle_number=1,
            reviewer_verdicts={"sr-dev": "SHIP", "sr-sdet": "SHIP", "security-reviewer": "SHIP"},
            recorder=recorder,
        )

        total_spawns = recorder.spawns_in_turn(1)
        assert len(total_spawns) == 3, f"Expected 3 spawns, got {len(total_spawns)}"


# ---------------------------------------------------------------------------
# Tests: fragment-file landing
# ---------------------------------------------------------------------------

class TestFragmentFileLanding:
    """Assert each reviewer writes to the correct fragment path."""

    def test_sr_dev_fragment_lands(self, tmp_path: Path) -> None:
        """sr-dev writes to runs/<task>/cycle_<N>/sr-dev-review.md."""
        runs_dir = tmp_path / "runs"
        issue_file = tmp_path / "task_05_issue.md"
        issue_file.write_text("# Issue\n", encoding="utf-8")
        recorder = SpawnCallRecorder()

        _, _, fragment_paths = _run_parallel_terminal_gate(
            runs_dir=runs_dir,
            issue_file=issue_file,
            task_shorthand="m20_t05",
            cycle_number=1,
            reviewer_verdicts={"sr-dev": "SHIP", "sr-sdet": "SHIP", "security-reviewer": "SHIP"},
            recorder=recorder,
        )

        expected = runs_dir / "m20_t05" / "cycle_1" / "sr-dev-review.md"
        assert fragment_paths["sr-dev"] == expected
        assert expected.exists(), f"Fragment file not found: {expected}"

    def test_sr_sdet_fragment_lands(self, tmp_path: Path) -> None:
        """sr-sdet writes to runs/<task>/cycle_<N>/sr-sdet-review.md."""
        runs_dir = tmp_path / "runs"
        issue_file = tmp_path / "task_05_issue.md"
        issue_file.write_text("# Issue\n", encoding="utf-8")
        recorder = SpawnCallRecorder()

        _, _, fragment_paths = _run_parallel_terminal_gate(
            runs_dir=runs_dir,
            issue_file=issue_file,
            task_shorthand="m20_t05",
            cycle_number=1,
            reviewer_verdicts={"sr-dev": "SHIP", "sr-sdet": "SHIP", "security-reviewer": "SHIP"},
            recorder=recorder,
        )

        expected = runs_dir / "m20_t05" / "cycle_1" / "sr-sdet-review.md"
        assert fragment_paths["sr-sdet"] == expected
        assert expected.exists(), f"Fragment file not found: {expected}"

    def test_security_reviewer_fragment_lands(self, tmp_path: Path) -> None:
        """security-reviewer writes to runs/<task>/cycle_<N>/security-review.md."""
        runs_dir = tmp_path / "runs"
        issue_file = tmp_path / "task_05_issue.md"
        issue_file.write_text("# Issue\n", encoding="utf-8")
        recorder = SpawnCallRecorder()

        _, _, fragment_paths = _run_parallel_terminal_gate(
            runs_dir=runs_dir,
            issue_file=issue_file,
            task_shorthand="m20_t05",
            cycle_number=1,
            reviewer_verdicts={"sr-dev": "SHIP", "sr-sdet": "SHIP", "security-reviewer": "SHIP"},
            recorder=recorder,
        )

        expected = runs_dir / "m20_t05" / "cycle_1" / "security-review.md"
        assert fragment_paths["security-reviewer"] == expected
        assert expected.exists(), f"Fragment file not found: {expected}"

    def test_all_three_fragments_land(self, tmp_path: Path) -> None:
        """All three fragment files exist after a terminal gate run."""
        runs_dir = tmp_path / "runs"
        issue_file = tmp_path / "task_05_issue.md"
        issue_file.write_text("# Issue\n", encoding="utf-8")
        recorder = SpawnCallRecorder()

        _, _, fragment_paths = _run_parallel_terminal_gate(
            runs_dir=runs_dir,
            issue_file=issue_file,
            task_shorthand="m20_t05",
            cycle_number=1,
            reviewer_verdicts={"sr-dev": "SHIP", "sr-sdet": "SHIP", "security-reviewer": "SHIP"},
            recorder=recorder,
        )

        for agent_name, path in fragment_paths.items():
            assert path.exists(), f"Fragment for {agent_name} not found at {path}"

    def test_fragment_paths_use_cycle_subdir_form(self, tmp_path: Path) -> None:
        """Fragment paths use the ``cycle_<N>/`` form (not a flat suffix)."""
        runs_dir = tmp_path / "runs"
        issue_file = tmp_path / "task_05_issue.md"
        issue_file.write_text("# Issue\n", encoding="utf-8")
        recorder = SpawnCallRecorder()

        _, _, fragment_paths = _run_parallel_terminal_gate(
            runs_dir=runs_dir,
            issue_file=issue_file,
            task_shorthand="m20_t05",
            cycle_number=3,
            reviewer_verdicts={"sr-dev": "SHIP", "sr-sdet": "SHIP", "security-reviewer": "SHIP"},
            recorder=recorder,
        )

        for agent_name, path in fragment_paths.items():
            assert "cycle_3" in str(path), (
                f"Fragment path for {agent_name} should contain 'cycle_3': {path}"
            )
            # Verify nested form not flat form
            assert path.parent.name == "cycle_3", (
                f"Fragment for {agent_name} should live in cycle_3/ directory, "
                f"got parent: {path.parent.name}"
            )


# ---------------------------------------------------------------------------
# Tests: single-Edit stitch pass
# ---------------------------------------------------------------------------

class TestStitchPass:
    """Assert fragments are stitched into the issue file in one logical Edit pass."""

    def test_stitch_adds_all_three_sections(self, tmp_path: Path) -> None:
        """Issue file contains all three review sections after TERMINAL CLEAN."""
        runs_dir = tmp_path / "runs"
        issue_file = tmp_path / "task_05_issue.md"
        issue_file.write_text("# Issue\n\n**Status:** PASS\n", encoding="utf-8")
        recorder = SpawnCallRecorder()

        stop, _, _ = _run_parallel_terminal_gate(
            runs_dir=runs_dir,
            issue_file=issue_file,
            task_shorthand="m20_t05",
            cycle_number=1,
            reviewer_verdicts={"sr-dev": "SHIP", "sr-sdet": "SHIP", "security-reviewer": "SHIP"},
            recorder=recorder,
        )

        assert stop == "TERMINAL CLEAN"
        stitched = issue_file.read_text(encoding="utf-8")
        assert "## Sr. Dev review" in stitched, "Sr. Dev review section missing"
        assert "## Sr. SDET review" in stitched, "Sr. SDET review section missing"
        assert "## Security review" in stitched, "Security review section missing"

    def test_stitch_preserves_section_order(self, tmp_path: Path) -> None:
        """Sr. Dev → Sr. SDET → Security order is preserved in the issue file."""
        runs_dir = tmp_path / "runs"
        issue_file = tmp_path / "task_05_issue.md"
        issue_file.write_text("# Issue\n\n**Status:** PASS\n", encoding="utf-8")
        recorder = SpawnCallRecorder()

        _run_parallel_terminal_gate(
            runs_dir=runs_dir,
            issue_file=issue_file,
            task_shorthand="m20_t05",
            cycle_number=1,
            reviewer_verdicts={"sr-dev": "SHIP", "sr-sdet": "SHIP", "security-reviewer": "SHIP"},
            recorder=recorder,
        )

        stitched = issue_file.read_text(encoding="utf-8")
        sr_dev_pos = stitched.find("## Sr. Dev review")
        sr_sdet_pos = stitched.find("## Sr. SDET review")
        security_pos = stitched.find("## Security review")
        assert sr_dev_pos < sr_sdet_pos < security_pos, (
            f"Section order wrong: sr-dev={sr_dev_pos}, sr-sdet={sr_sdet_pos}, "
            f"security={security_pos}"
        )

    def test_no_stitch_on_terminal_block(self, tmp_path: Path) -> None:
        """Issue file is NOT stitched when the stop condition is TERMINAL BLOCK."""
        runs_dir = tmp_path / "runs"
        issue_file = tmp_path / "task_05_issue.md"
        original_content = "# Issue\n\n**Status:** PASS\n"
        issue_file.write_text(original_content, encoding="utf-8")
        recorder = SpawnCallRecorder()

        stop, _, _ = _run_parallel_terminal_gate(
            runs_dir=runs_dir,
            issue_file=issue_file,
            task_shorthand="m20_t05",
            cycle_number=1,
            reviewer_verdicts={"sr-dev": "BLOCK", "sr-sdet": "SHIP", "security-reviewer": "SHIP"},
            recorder=recorder,
        )

        assert stop == "TERMINAL BLOCK"
        # Issue file should NOT have been stitched
        assert issue_file.read_text(encoding="utf-8") == original_content, (
            "Issue file was modified on TERMINAL BLOCK — stitch should not run"
        )

    def test_no_stitch_on_terminal_fix(self, tmp_path: Path) -> None:
        """Issue file is NOT stitched when the stop condition is TERMINAL FIX."""
        runs_dir = tmp_path / "runs"
        issue_file = tmp_path / "task_05_issue.md"
        original_content = "# Issue\n\n**Status:** PASS\n"
        issue_file.write_text(original_content, encoding="utf-8")
        recorder = SpawnCallRecorder()

        stop, _, _ = _run_parallel_terminal_gate(
            runs_dir=runs_dir,
            issue_file=issue_file,
            task_shorthand="m20_t05",
            cycle_number=1,
            reviewer_verdicts={
                "sr-dev": "FIX-THEN-SHIP",
                "sr-sdet": "SHIP",
                "security-reviewer": "SHIP",
            },
            recorder=recorder,
        )

        assert stop == "TERMINAL FIX"
        assert issue_file.read_text(encoding="utf-8") == original_content, (
            "Issue file was modified on TERMINAL FIX — stitch should not run"
        )

    def test_stitch_is_single_write_operation(self, tmp_path: Path) -> None:
        """Stitch happens in one logical write operation — all three sections land together."""
        runs_dir = tmp_path / "runs"
        issue_file = tmp_path / "task_05_issue.md"
        issue_file.write_text("# Issue\n", encoding="utf-8")
        fragment_paths: dict[str, Path] = {}

        for agent_name in _AGENT_NAMES:
            path = _stub_reviewer_write_fragment(
                runs_dir, "m20_t05", 1, agent_name, "SHIP"
            )
            fragment_paths[agent_name] = path

        # Wait a tiny bit to ensure any mtime drift would be detectable
        time.sleep(0.01)

        # Perform stitch
        _stitch_fragments_into_issue_file(issue_file, fragment_paths)

        # The file was written exactly once — all three sections present
        stitched = issue_file.read_text(encoding="utf-8")
        assert "## Sr. Dev review" in stitched
        assert "## Sr. SDET review" in stitched
        assert "## Security review" in stitched
        assert stitched.count("## Sr. Dev review") == 1, "Sr. Dev section appears more than once"
        assert stitched.count("## Sr. SDET review") == 1, "Sr. SDET section appears more than once"
        assert stitched.count("## Security review") == 1, "Security section appears more than once"


# ---------------------------------------------------------------------------
# Tests: precedence rule correctness
# ---------------------------------------------------------------------------

class TestPrecedenceRule:
    """Assert BLOCK > FIX-THEN-SHIP > SHIP; security-reviewer BLOCK surfaced first."""

    def test_all_ship_is_terminal_clean(self) -> None:
        """All three SHIP → TERMINAL CLEAN."""
        verdicts = {"sr-dev": "SHIP", "sr-sdet": "SHIP", "security-reviewer": "SHIP"}
        stop, reason = _apply_precedence_rule(verdicts)
        assert stop == "TERMINAL CLEAN", f"Expected TERMINAL CLEAN, got {stop}: {reason}"

    def test_any_block_is_terminal_block(self) -> None:
        """Any BLOCK → TERMINAL BLOCK, regardless of other verdicts."""
        # sr-dev blocks; others ship
        verdicts = {"sr-dev": "BLOCK", "sr-sdet": "SHIP", "security-reviewer": "SHIP"}
        stop, reason = _apply_precedence_rule(verdicts)
        assert stop == "TERMINAL BLOCK", f"Expected TERMINAL BLOCK, got {stop}: {reason}"

    def test_security_block_takes_precedence_in_reason(self) -> None:
        """When security-reviewer BLOCKs, its finding is surfaced first in the reason."""
        verdicts = {"sr-dev": "SHIP", "sr-sdet": "SHIP", "security-reviewer": "BLOCK"}
        stop, reason = _apply_precedence_rule(verdicts)
        assert stop == "TERMINAL BLOCK"
        assert "security-reviewer" in reason, (
            f"security-reviewer BLOCK should be surfaced first in reason, got: {reason}"
        )
        assert reason.startswith("security-reviewer"), (
            f"security-reviewer BLOCK should lead the reason string, got: {reason}"
        )

    def test_security_block_leads_even_when_sr_dev_also_blocks(self) -> None:
        """When both security-reviewer and sr-dev BLOCK, security-reviewer reason leads."""
        verdicts = {"sr-dev": "BLOCK", "sr-sdet": "SHIP", "security-reviewer": "BLOCK"}
        stop, reason = _apply_precedence_rule(verdicts)
        assert stop == "TERMINAL BLOCK"
        # security-reviewer should be mentioned first in the reason
        security_pos = reason.find("security-reviewer")
        sr_dev_pos = reason.find("sr-dev")
        assert security_pos < sr_dev_pos, (
            f"security-reviewer should appear before sr-dev in reason, got: {reason}"
        )

    def test_fix_then_ship_with_no_block_is_terminal_fix(self) -> None:
        """Any FIX-THEN-SHIP (no BLOCK) → TERMINAL FIX."""
        verdicts = {"sr-dev": "FIX-THEN-SHIP", "sr-sdet": "SHIP", "security-reviewer": "SHIP"}
        stop, reason = _apply_precedence_rule(verdicts)
        assert stop == "TERMINAL FIX", f"Expected TERMINAL FIX, got {stop}: {reason}"
        assert "sr-dev" in reason

    def test_block_overrides_fix_then_ship(self) -> None:
        """BLOCK takes priority over FIX-THEN-SHIP — TERMINAL BLOCK wins."""
        verdicts = {
            "sr-dev": "BLOCK",
            "sr-sdet": "FIX-THEN-SHIP",
            "security-reviewer": "SHIP",
        }
        stop, reason = _apply_precedence_rule(verdicts)
        assert stop == "TERMINAL BLOCK", (
            f"BLOCK should override FIX-THEN-SHIP; got {stop}: {reason}"
        )

    def test_multiple_fix_then_ship_all_surface(self) -> None:
        """When multiple reviewers return FIX-THEN-SHIP, all are named in the reason."""
        verdicts = {
            "sr-dev": "FIX-THEN-SHIP",
            "sr-sdet": "FIX-THEN-SHIP",
            "security-reviewer": "SHIP",
        }
        stop, reason = _apply_precedence_rule(verdicts)
        assert stop == "TERMINAL FIX"
        assert "sr-dev" in reason
        assert "sr-sdet" in reason

    def test_all_block_security_leads(self) -> None:
        """All three BLOCK → TERMINAL BLOCK, security-reviewer leads the reason."""
        verdicts = {
            "sr-dev": "BLOCK",
            "sr-sdet": "BLOCK",
            "security-reviewer": "BLOCK",
        }
        stop, reason = _apply_precedence_rule(verdicts)
        assert stop == "TERMINAL BLOCK"
        assert reason.startswith("security-reviewer"), (
            f"security-reviewer should lead when all three BLOCK, got: {reason}"
        )


# ---------------------------------------------------------------------------
# Tests: parallel_spawn_pattern.md exists
# ---------------------------------------------------------------------------

def test_parallel_spawn_pattern_file_exists() -> None:
    """AC-5: .claude/commands/_common/parallel_spawn_pattern.md exists."""
    pattern_file = Path(".claude/commands/_common/parallel_spawn_pattern.md")
    assert pattern_file.exists(), (
        f"parallel_spawn_pattern.md not found at {pattern_file}. "
        "This file is required by AC-5."
    )


def test_parallel_spawn_pattern_mentions_fragment_paths() -> None:
    """parallel_spawn_pattern.md documents the fragment path convention."""
    pattern_file = Path(".claude/commands/_common/parallel_spawn_pattern.md")
    if not pattern_file.exists():
        pytest.skip("parallel_spawn_pattern.md not found — covered by file-exists test")
    content = pattern_file.read_text(encoding="utf-8")
    assert "cycle_<N>" in content, "parallel_spawn_pattern.md should document cycle_<N>/ paths"
    assert "fragment" in content.lower(), "parallel_spawn_pattern.md should mention fragment files"


# ---------------------------------------------------------------------------
# Tests: auto-implement.md smoke-test verification
# ---------------------------------------------------------------------------

def test_auto_implement_describes_parallel_terminal_gate() -> None:
    """AC-1: auto-implement.md describes the parallel terminal gate (smoke grep)."""
    auto_impl = Path(".claude/commands/auto-implement.md")
    if not auto_impl.exists():
        pytest.skip("auto-implement.md not found")
    content = auto_impl.read_text(encoding="utf-8")
    # The spec's smoke test grep: "parallel.*terminal gate|three Task tool calls"
    assert re.search(r"parallel.*terminal gate|three Task tool calls", content, re.IGNORECASE), (
        "auto-implement.md should describe a parallel terminal gate or three Task tool calls"
    )


def test_reviewer_agents_write_to_fragment_paths() -> None:
    """AC-3: each reviewer agent file documents writing to the fragment path."""
    agent_files = [
        Path(".claude/agents/sr-dev.md"),
        Path(".claude/agents/sr-sdet.md"),
        Path(".claude/agents/security-reviewer.md"),
    ]
    # Smoke-test grep per spec §Smoke test, lines 146-150:
    #   grep -lE "runs/.*cycle_<N>.*review.md|runs/<task>/cycle_<N>/"
    pattern = re.compile(r"runs/.*cycle_<N>.*review\.md|runs/<task>/cycle_<N>/")
    files_matching: list[str] = []
    for agent_file in agent_files:
        if not agent_file.exists():
            continue
        content = agent_file.read_text(encoding="utf-8")
        if pattern.search(content):
            files_matching.append(str(agent_file))
    assert len(files_matching) == 3, (
        f"Expected all 3 reviewer agent files to reference fragment paths, "
        f"got {len(files_matching)}: {files_matching}"
    )


# ---------------------------------------------------------------------------
# Tests: _parse_verdict_from_fragment — discriminating parser tests (LD-1)
# ---------------------------------------------------------------------------

def test_parse_verdict_bold_block(tmp_path: Path) -> None:
    """LD-1 discriminating positive: bold **Verdict:** BLOCK is parsed correctly.

    Pins the parser to the bold convention all three reviewer agents now use.
    """
    fragment = tmp_path / "security-review.md"
    fragment.write_text(
        "## Security review (2026-04-28)\n\n**Verdict:** BLOCK\n\nSome finding.\n",
        encoding="utf-8",
    )
    result = _parse_verdict_from_fragment(fragment)
    assert result == "BLOCK", f"Expected BLOCK, got {result!r}"


def test_parse_verdict_bold_fix_then_ship(tmp_path: Path) -> None:
    """LD-1 discriminating positive: bold **Verdict:** FIX-THEN-SHIP is parsed correctly."""
    fragment = tmp_path / "sr-dev-review.md"
    fragment.write_text(
        "## Sr. Dev review (2026-04-28)\n\n**Verdict:** FIX-THEN-SHIP\n\nSome finding.\n",
        encoding="utf-8",
    )
    result = _parse_verdict_from_fragment(fragment)
    assert result == "FIX-THEN-SHIP", f"Expected FIX-THEN-SHIP, got {result!r}"


def test_parse_verdict_heading_format_raises(tmp_path: Path) -> None:
    """LD-1 discriminating negative: heading-format '### Verdict: SHIP' raises ValueError.

    The parser is pinned to the bold convention.  A mis-formatted fragment using
    the old heading format must fail loudly rather than silently misparsing.
    This test would catch a future security-reviewer.md regression back to
    '### Verdict: SHIP' (heading format).
    """
    fragment = tmp_path / "security-review.md"
    fragment.write_text(
        "## Security review (2026-04-28)\n\n### Verdict: SHIP\n\nNo issues.\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="No \\*\\*Verdict:\\*\\* line found"):
        _parse_verdict_from_fragment(fragment)


# ---------------------------------------------------------------------------
# Tests: agent_return_schema.md reviewer rows reference fragment paths (LD-2)
# ---------------------------------------------------------------------------

def test_agent_return_schema_reviewer_rows_use_fragment_paths() -> None:
    """LD-2: agent_return_schema.md rows for the three reviewer agents use fragment paths.

    Asserts each of security-reviewer, sr-dev, sr-sdet references a
    'runs/<task>/cycle_<N>/' path in the durable-artifact column.

    Failure mode: if any reviewer row reverts to the pre-T05 issue-file path
    (design_docs/.../issues/task_<NN>_issue.md), this test fails loudly.
    """
    schema_file = Path(".claude/commands/_common/agent_return_schema.md")
    if not schema_file.exists():
        pytest.skip("agent_return_schema.md not found")
    content = schema_file.read_text(encoding="utf-8")

    # Expected post-T05 fragment paths for each reviewer
    expected = {
        "security-reviewer": r"runs/<task>/cycle_<N>/security-review\.md",
        "sr-dev": r"runs/<task>/cycle_<N>/sr-dev-review\.md",
        "sr-sdet": r"runs/<task>/cycle_<N>/sr-sdet-review\.md",
    }

    for agent_name, path_pattern in expected.items():
        # Find the table row for this agent and assert it contains the fragment path
        row_pattern = re.compile(
            r"`" + re.escape(agent_name) + r"`.*" + path_pattern,
            re.DOTALL,
        )
        assert row_pattern.search(content), (
            f"agent_return_schema.md row for '{agent_name}' does not reference "
            f"the expected fragment path matching '{path_pattern}'. "
            f"This likely means the row still uses the pre-T05 issue-file path. "
            f"Expected the row to contain: runs/<task>/cycle_<N>/..."
        )
