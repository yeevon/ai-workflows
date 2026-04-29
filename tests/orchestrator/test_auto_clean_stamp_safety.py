"""AUTO-CLEAN stamp safety tests — orchestrator-level gate-capture and halt logic.

Task: M20 Task 08 — Gate-output integrity (raw-stdout capture + footer-line parse;
  fail-closed on missing output; load-bearing under default-Sonnet).
Relationship: Tests the orchestrator-level stamp-safety logic described in
  `.claude/commands/auto-implement.md` §Gate-capture-and-parse convention and
  `.claude/commands/clean-implement.md` §Gate-capture-and-parse convention.
  Simulates the orchestrator's decision to stamp AUTO-CLEAN (or halt) based on the
  captured gate-output files.

Per-AC coverage:
  AC-1 — auto-implement.md gate-capture-and-parse convention referenced:
          grep assertion in this file + stamp-safety logic tests below.
  AC-2 — clean-implement.md matches: grep assertion in this file.
  AC-4 — Captured gate outputs land at runs/<task>/cycle_<N>/gate_<name>.txt:
          path-convention assertion in TestCapturePathConvention.
  AC-5 — 🚧 BLOCKED message surfaces correctly: tested in TestAutoCleanStampSafety.
  AC-7 — test_auto_clean_stamp_safety.py passes (this file).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.orchestrator.test_gate_output_capture import (
    build_blocked_message,
    parse_gate_output,
)

# ---------------------------------------------------------------------------
# Helpers: orchestrator-level AUTO-CLEAN stamp simulation
# ---------------------------------------------------------------------------

_ALL_GATE_NAMES = ("pytest", "lint-imports", "ruff")

# Minimal "passing" gate outputs for each gate
_PASSING_OUTPUTS: dict[str, tuple[str, int]] = {
    "pytest": (
        "============================= test session starts ==============================\n"
        "collected 10 items\n"
        "\n"
        "============================== 10 passed in 0.50s ==============================\n",
        0,
    ),
    "lint-imports": (
        "Checking imports...\n"
        "Contracts kept\n",
        0,
    ),
    "ruff": (
        "All checks passed.\n",
        0,
    ),
}


def simulate_auto_clean_decision(
    gate_captures: dict[str, tuple[str, int]],
) -> tuple[bool, str]:
    """Simulate the orchestrator's AUTO-CLEAN decision given gate captures.

    Implements the logic described in `.claude/commands/auto-implement.md`
    §Gate-capture-and-parse convention:
    - If any gate fails to parse (empty, missing footer, non-zero exit, failure footer),
      return (False, blocked_message).
    - If all gates pass, return (True, "AUTO-CLEAN").

    Args:
        gate_captures: Dict mapping gate_name → (captured_output_text, exit_code).

    Returns:
        A tuple ``(should_stamp, message)`` where ``should_stamp`` is True iff all
        gates passed, and ``message`` is either ``"AUTO-CLEAN"`` or the first
        `🚧 BLOCKED: ...` message encountered.
    """
    for gate_name, (captured_text, exit_code) in gate_captures.items():
        result = parse_gate_output(gate_name, captured_text, exit_code)
        if result.blocked:
            # Use a synthetic task+cycle for test purposes
            msg = build_blocked_message(gate_name, "m20_t08", 1)
            return False, msg
    return True, "AUTO-CLEAN"


# ---------------------------------------------------------------------------
# Tests — AUTO-CLEAN stamp safety
# ---------------------------------------------------------------------------


class TestAutoCleanStampSafety:
    """AC-5/AC-7: orchestrator stamps or halts based on captured gate files."""

    def test_builder_claims_pass_empty_gate_file_halts(self) -> None:
        """Builder claims pass + empty gate file → orchestrator halts (no AUTO-CLEAN stamp)."""
        # Simulate: Builder reported 'all gates pass', but the captured pytest file is empty
        captures: dict[str, tuple[str, int]] = {
            "pytest": ("", 0),  # empty — Builder's claim is unverified
            "lint-imports": _PASSING_OUTPUTS["lint-imports"],
            "ruff": _PASSING_OUTPUTS["ruff"],
        }
        should_stamp, message = simulate_auto_clean_decision(captures)
        assert should_stamp is False
        assert "BLOCKED" in message
        assert "pytest" in message

    def test_builder_claims_pass_gate_footer_present_stamps(self) -> None:
        """Builder claims pass + gate captures show pass → AUTO-CLEAN stamps."""
        captures: dict[str, tuple[str, int]] = dict(_PASSING_OUTPUTS)
        should_stamp, message = simulate_auto_clean_decision(captures)
        assert should_stamp is True
        assert message == "AUTO-CLEAN"

    def test_builder_claims_pass_one_gate_failure_footer_halts(self) -> None:
        """Builder claims pass but one gate has a failure footer → halt."""
        captures: dict[str, tuple[str, int]] = {
            "pytest": (
                "== 5 failed, 10 passed in 1.00s ==\n",
                1,
            ),
            "lint-imports": _PASSING_OUTPUTS["lint-imports"],
            "ruff": _PASSING_OUTPUTS["ruff"],
        }
        should_stamp, message = simulate_auto_clean_decision(captures)
        assert should_stamp is False
        assert "BLOCKED" in message
        assert "pytest" in message

    def test_all_gates_nonzero_exit_halts(self) -> None:
        """Non-zero exit code on any gate → halt, even if footer looks OK."""
        captures: dict[str, tuple[str, int]] = {
            "pytest": (
                "== 10 passed in 0.50s ==\n",
                0,
            ),
            "lint-imports": ("Contracts kept\n", 1),  # non-zero exit
            "ruff": _PASSING_OUTPUTS["ruff"],
        }
        should_stamp, message = simulate_auto_clean_decision(captures)
        assert should_stamp is False
        assert "BLOCKED" in message
        assert "lint-imports" in message

    def test_blocked_message_references_correct_path(self) -> None:
        """BLOCKED message includes the canonical gate file path."""
        captures: dict[str, tuple[str, int]] = {
            "pytest": ("", 0),
            "lint-imports": _PASSING_OUTPUTS["lint-imports"],
            "ruff": _PASSING_OUTPUTS["ruff"],
        }
        _, message = simulate_auto_clean_decision(captures)
        # Canonical path: runs/<task>/cycle_<N>/gate_<name>.txt
        assert "gate_pytest.txt" in message

    def test_ruff_empty_output_halts(self) -> None:
        """Empty ruff capture → halt even when other gates pass."""
        captures: dict[str, tuple[str, int]] = {
            "pytest": _PASSING_OUTPUTS["pytest"],
            "lint-imports": _PASSING_OUTPUTS["lint-imports"],
            "ruff": ("", 0),
        }
        should_stamp, message = simulate_auto_clean_decision(captures)
        assert should_stamp is False
        assert "ruff" in message

    def test_single_gate_all_pass(self) -> None:
        """With a single gate passing, AUTO-CLEAN stamps correctly."""
        captures: dict[str, tuple[str, int]] = {
            "pytest": _PASSING_OUTPUTS["pytest"],
        }
        should_stamp, message = simulate_auto_clean_decision(captures)
        assert should_stamp is True

    def test_no_gates_stamps(self) -> None:
        """Empty gate dict (no gates required) → AUTO-CLEAN stamps (vacuously).

        # Intentional: empty gate dict returns True; orchestrator must ensure non-empty.
        # The auto-implement.md convention mandates that the gate list is always
        # constructed with at least pytest + lint-imports + ruff before this check runs.
        # An empty dict reaching this function is a caller error, not a normal path.
        """
        should_stamp, message = simulate_auto_clean_decision({})
        assert should_stamp is True
        assert message == "AUTO-CLEAN"


# ---------------------------------------------------------------------------
# AC-4: capture path convention
# ---------------------------------------------------------------------------


class TestCapturePathConvention:
    """AC-4: captured gate outputs land at the canonical path pattern."""

    @pytest.mark.parametrize(
        "gate_name",
        ["pytest", "lint-imports", "ruff", "smoke"],
    )
    def test_gate_filename_convention(self, gate_name: str) -> None:
        """Gate filename embedded in build_blocked_message follows `gate_<name>.txt` convention.

        Derives the filename from the actual build_blocked_message helper rather than
        asserting a string against itself.  The spec requires captured outputs to land at
        ``runs/<task>/cycle_<N>/gate_<name>.txt``; this test verifies the path-building
        logic embeds the correct filename for each gate name.
        """
        task_shorthand = "m20_t08"
        cycle = 1
        msg = build_blocked_message(gate_name, task_shorthand, cycle)
        # Build the expected full path segment the same way the spec prescribes
        expected_path_segment = (
            Path("runs") / task_shorthand / f"cycle_{cycle}" / f"gate_{gate_name}.txt"
        )
        assert str(expected_path_segment) in msg, (
            f"build_blocked_message did not embed the expected path "
            f"'{expected_path_segment}' for gate '{gate_name}'; got: {msg!r}"
        )

    def test_canonical_path_structure(self, tmp_path: Path) -> None:
        """Gate capture file can be created at the canonical path."""
        task_shorthand = "m20_t08"
        cycle = 1
        gate_name = "pytest"
        gate_file = tmp_path / "runs" / task_shorthand / f"cycle_{cycle}" / f"gate_{gate_name}.txt"
        gate_file.parent.mkdir(parents=True)
        gate_file.write_text(
            "EXIT_CODE=0\n"
            "STDOUT:\n"
            "============================== 5 passed in 0.50s ==============================\n"
            "STDERR:\n"
        )
        assert gate_file.exists()
        content = gate_file.read_text()
        assert "EXIT_CODE=0" in content
        assert "5 passed" in content


# ---------------------------------------------------------------------------
# AC-1/AC-2: command file convention references
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parents[2]
_AUTO_IMPLEMENT = _REPO_ROOT / ".claude" / "commands" / "auto-implement.md"
_CLEAN_IMPLEMENT = _REPO_ROOT / ".claude" / "commands" / "clean-implement.md"
_GATE_PATTERNS_FILE = _REPO_ROOT / ".claude" / "commands" / "_common" / "gate_parse_patterns.md"


class TestCommandFileConventionReferences:
    """AC-1/AC-2: both command files reference gate_parse_patterns.md and gate_<name>.txt."""

    def test_auto_implement_references_gate_parse_patterns(self) -> None:
        """auto-implement.md must reference gate_parse_patterns.md."""
        content = _AUTO_IMPLEMENT.read_text()
        assert "gate_parse_patterns.md" in content

    def test_auto_implement_references_gate_name_txt(self) -> None:
        """auto-implement.md must reference gate_<name>.txt path pattern."""
        content = _AUTO_IMPLEMENT.read_text()
        assert "gate_" in content and ".txt" in content

    def test_clean_implement_references_gate_parse_patterns(self) -> None:
        """clean-implement.md must reference gate_parse_patterns.md."""
        content = _CLEAN_IMPLEMENT.read_text()
        assert "gate_parse_patterns.md" in content

    def test_clean_implement_references_gate_name_txt(self) -> None:
        """clean-implement.md must reference gate_<name>.txt path pattern."""
        content = _CLEAN_IMPLEMENT.read_text()
        assert "gate_" in content and ".txt" in content

    def test_both_files_reference_blocked_pattern(self) -> None:
        """Both command files must include the 🚧 BLOCKED halt-message pattern."""
        for cmd_file in (_AUTO_IMPLEMENT, _CLEAN_IMPLEMENT):
            content = cmd_file.read_text()
            assert "BLOCKED" in content, (
                f"{cmd_file.name} must contain 'BLOCKED' halt message"
            )

    def test_gate_patterns_file_exists(self) -> None:
        """gate_parse_patterns.md must exist at the canonical _common/ path."""
        assert _GATE_PATTERNS_FILE.exists()
