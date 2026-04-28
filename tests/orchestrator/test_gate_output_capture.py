"""Gate-output capture and parse tests — footer-line regex, fail-closed on missing/empty output.

Task: M20 Task 08 — Gate-output integrity (raw-stdout capture + footer-line parse;
  fail-closed on missing output; load-bearing under default-Sonnet).
Relationship: Tests the gate-output parsing logic described in
  `.claude/commands/_common/gate_parse_patterns.md` and referenced by the
  gate-capture-and-parse convention sections in `.claude/commands/auto-implement.md`
  and `.claude/commands/clean-implement.md`.  The production versions of these rules
  run as markdown-prose logic inside the slash-command orchestrators; this module
  provides a hermetic Python implementation so every parse branch can be exercised
  without live gate invocations.

Per-AC coverage:
  AC-1 — auto-implement.md gate-capture-and-parse convention: structural grep in
          test_auto_clean_stamp_safety.py; footer-parse logic tested here.
  AC-2 — clean-implement.md matches: structural grep in test_auto_clean_stamp_safety.py.
  AC-3 — gate_parse_patterns.md exists with per-gate regex: file-existence + content
          assertion at end of this module.
  AC-4 — Captured gate outputs land at runs/<task>/cycle_<N>/gate_<name>.txt: verified
          by capture-convention tests in test_auto_clean_stamp_safety.py.
  AC-5 — Halt-on-missing-footer surfaces 🚧 BLOCKED: tested here (empty + no-footer cases).
  AC-6 — test_gate_output_capture.py passes (this file).
  AC-7 — test_auto_clean_stamp_safety.py passes (sibling file).
  AC-8 — CHANGELOG.md updated (in CHANGELOG).
  AC-9 — Status surfaces flipped (in spec + milestone README).
"""

from __future__ import annotations

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Gate-output parser (Python mirror of the markdown prose in gate_parse_patterns.md)
# ---------------------------------------------------------------------------

# Per-gate footer-line regex table (mirrors gate_parse_patterns.md §Per-gate footer-line regex).
# Each entry: (gate_name, compiled_footer_re, requires_no_failed_word)
_GATE_PATTERNS: list[tuple[str, re.Pattern[str], bool]] = [
    (
        "pytest",
        re.compile(r"^=+ \d+ passed"),
        True,  # halt if "failed" also appears on the footer line
    ),
    (
        "ruff",
        re.compile(r"^All checks passed\.$|^\d+ files? checked\.$"),
        False,
    ),
    (
        "lint-imports",
        re.compile(r"^Contracts kept$"),
        False,
    ),
]

# Map gate name → (footer_re, requires_no_failed_word)
GATE_PATTERNS: dict[str, tuple[re.Pattern[str], bool]] = {
    name: (pat, no_fail) for name, pat, no_fail in _GATE_PATTERNS
}


class GateParseResult:
    """Result of parsing a single captured gate-output file.

    Attributes:
        passed: True iff the gate passed (footer present, exit-code 0, no failures).
        blocked: True iff the gate should halt the orchestrator.
        reason: Human-readable halt reason (empty when ``passed`` is True).
    """

    def __init__(self, passed: bool, reason: str = "") -> None:
        self.passed = passed
        self.blocked = not passed
        self.reason = reason

    def __repr__(self) -> str:  # pragma: no cover
        return f"GateParseResult(passed={self.passed}, reason={self.reason!r})"


def parse_gate_output(
    gate_name: str,
    captured_text: str,
    exit_code: int,
) -> GateParseResult:
    """Parse the captured output of a gate command.

    Implements the parse logic described in
    `.claude/commands/_common/gate_parse_patterns.md`.  Fail-closed: any ambiguity
    (empty output, missing footer, non-zero exit, failure-indicating footer) returns a
    blocked result.

    Args:
        gate_name: One of ``"pytest"``, ``"ruff"``, ``"lint-imports"``, or a custom
            slug.  Unknown gate names are treated as blocked (no footer pattern known).
        captured_text: Full text captured from the gate command (stdout + stderr combined
            or structured per `_common/gate_parse_patterns.md` §Capture format).
        exit_code: Integer exit code returned by the gate command.  Non-zero → blocked.

    Returns:
        A :class:`GateParseResult` with ``passed=True`` iff all conditions pass.
    """
    # Condition 1 — empty output
    if not captured_text or not captured_text.strip():
        return GateParseResult(
            passed=False,
            reason=f"gate {gate_name!r} output is empty",
        )

    # Condition 3 — non-zero exit code (checked before footer scan — fail-closed)
    if exit_code != 0:
        return GateParseResult(
            passed=False,
            reason=f"gate {gate_name!r} exit code {exit_code} (non-zero)",
        )

    # Look up footer pattern
    if gate_name not in GATE_PATTERNS:
        return GateParseResult(
            passed=False,
            reason=f"gate {gate_name!r} has no registered footer pattern (unknown gate)",
        )
    footer_re, requires_no_failed = GATE_PATTERNS[gate_name]

    # Condition 2 — scan each line for the footer
    footer_found = False
    footer_line = ""
    for raw_line in captured_text.splitlines():
        line = raw_line.strip()
        if footer_re.match(line):
            footer_found = True
            footer_line = line
            break

    if not footer_found:
        return GateParseResult(
            passed=False,
            reason=(
                f"gate {gate_name!r} footer line missing from captured output "
                f"(expected pattern: {footer_re.pattern!r})"
            ),
        )

    # Condition 4 — footer present but indicates failures
    if requires_no_failed and "failed" in footer_line.lower():
        return GateParseResult(
            passed=False,
            reason=(
                f"gate {gate_name!r} footer indicates failures: {footer_line!r}"
            ),
        )

    return GateParseResult(passed=True)


def build_blocked_message(gate_name: str, task_shorthand: str, cycle: int) -> str:
    """Build the orchestrator halt message for a blocked gate.

    Produces the canonical `🚧 BLOCKED: gate <name> output not parseable; see ...`
    message described in `_common/gate_parse_patterns.md` §Halt condition.

    Args:
        gate_name: The gate that blocked (e.g. ``"pytest"``).
        task_shorthand: The task shorthand (e.g. ``"m20_t08"``).
        cycle: The cycle number (1-based).

    Returns:
        The canonical halt-message string.
    """
    return (
        f"🚧 BLOCKED: gate {gate_name} output not parseable; "
        f"see runs/{task_shorthand}/cycle_{cycle}/gate_{gate_name}.txt"
    )


# ---------------------------------------------------------------------------
# Tests — synthetic gate output
# ---------------------------------------------------------------------------


class TestPytestOutputParsing:
    """AC-5/AC-6: pytest gate parsing (valid footer, empty, no-footer, failures, exit-code)."""

    def test_valid_pytest_footer_parses_cleanly(self) -> None:
        """Synthetic gate output with valid pytest footer → passes."""
        output = (
            "============================= test session starts ==============================\n"
            "collected 42 items\n"
            "\n"
            "tests/test_foo.py .........                                               [100%]\n"
            "\n"
            "============================== 42 passed in 1.23s ==============================\n"
        )
        result = parse_gate_output("pytest", output, exit_code=0)
        assert result.passed is True
        assert result.blocked is False
        assert result.reason == ""

    def test_empty_stdout_is_blocked(self) -> None:
        """Synthetic empty stdout → halt."""
        result = parse_gate_output("pytest", "", exit_code=0)
        assert result.blocked is True
        assert "empty" in result.reason

    def test_whitespace_only_stdout_is_blocked(self) -> None:
        """Whitespace-only stdout → halt (treated as empty)."""
        result = parse_gate_output("pytest", "   \n  \n  ", exit_code=0)
        assert result.blocked is True
        assert "empty" in result.reason

    def test_stdout_claiming_pass_without_footer_is_blocked(self) -> None:
        """Stdout claiming pass but missing the footer line → halt."""
        output = (
            "tests passed!\n"
            "All good.\n"
        )
        result = parse_gate_output("pytest", output, exit_code=0)
        assert result.blocked is True
        assert "footer line missing" in result.reason

    def test_nonzero_exit_code_is_blocked_regardless_of_footer(self) -> None:
        """Non-zero exit code → halt even if a passing footer is present."""
        output = (
            "============================= test session starts ==============================\n"
            "============================== 10 passed in 0.50s ==============================\n"
        )
        result = parse_gate_output("pytest", output, exit_code=1)
        assert result.blocked is True
        assert "exit code 1" in result.reason

    def test_failure_footer_nonzero_exit_is_blocked(self) -> None:
        """Non-zero exit code with failure footer → blocked via exit-code branch (Condition 3).

        Note: this footer starts with '5 failed' so the pytest regex (^=+ \\d+ passed) does NOT
        match it.  The test exercises Condition 3 (exit_code != 0), not Condition 4.
        """
        output = (
            "============================= test session starts ==============================\n"
            "collected 15 items\n"
            "\n"
            "=========================== 5 failed, 10 passed in 2.00s ===========================\n"
        )
        result = parse_gate_output("pytest", output, exit_code=1)
        assert result.blocked is True
        assert "exit code 1" in result.reason

    def test_failure_footer_zero_exit_is_blocked_by_condition4(self) -> None:
        """Footer that matches the regex but also contains 'failed' → blocked via Condition 4.

        Uses exit_code=0 so Condition 3 does NOT fire.  The footer '== 10 passed, 5 failed in
        1.0s ==' starts with '\\d+ passed' so the regex matches, but the line also contains
        'failed', which triggers the requires_no_failed guard (Condition 4).
        This is the load-bearing fail-closed path for the pytest gate.
        """
        output = (
            "============================= test session starts ==============================\n"
            "collected 15 items\n"
            "\n"
            "== 10 passed, 5 failed in 1.0s ==\n"
        )
        result = parse_gate_output("pytest", output, exit_code=0)
        assert result.blocked is True
        assert "footer indicates failures" in result.reason

    def test_minimal_valid_footer_passes(self) -> None:
        """Minimal valid footer `== 1 passed ==` parses cleanly."""
        output = "== 1 passed in 0.01s ==\n"
        result = parse_gate_output("pytest", output, exit_code=0)
        assert result.passed is True


class TestRuffOutputParsing:
    """ruff gate parsing."""

    def test_all_checks_passed_footer(self) -> None:
        """`All checks passed.` footer → passes."""
        output = "All checks passed.\n"
        result = parse_gate_output("ruff", output, exit_code=0)
        assert result.passed is True

    def test_n_files_checked_footer(self) -> None:
        """`N files checked.` footer → passes."""
        output = "42 files checked.\n"
        result = parse_gate_output("ruff", output, exit_code=0)
        assert result.passed is True

    def test_singular_file_checked_footer(self) -> None:
        """`1 file checked.` footer → passes."""
        output = "1 file checked.\n"
        result = parse_gate_output("ruff", output, exit_code=0)
        assert result.passed is True

    def test_empty_stdout_is_blocked(self) -> None:
        """Empty ruff stdout → halt."""
        result = parse_gate_output("ruff", "", exit_code=0)
        assert result.blocked is True

    def test_no_footer_is_blocked(self) -> None:
        """ruff stdout without a recognised footer → halt."""
        output = "Found 3 errors.\n"
        result = parse_gate_output("ruff", output, exit_code=1)
        assert result.blocked is True

    def test_nonzero_exit_is_blocked(self) -> None:
        """ruff non-zero exit → halt."""
        output = "All checks passed.\n"  # footer present but exit wrong
        result = parse_gate_output("ruff", output, exit_code=2)
        assert result.blocked is True
        assert "exit code 2" in result.reason


class TestLintImportsOutputParsing:
    """lint-imports gate parsing."""

    def test_contracts_kept_footer_passes(self) -> None:
        """`Contracts kept` footer → passes."""
        output = "Checking imports...\nContracts kept\n"
        result = parse_gate_output("lint-imports", output, exit_code=0)
        assert result.passed is True

    def test_contracts_kept_padded_footer_passes(self) -> None:
        """`Contracts kept` with surrounding whitespace → passes (trimmed before match)."""
        output = "  Contracts kept  \n"
        result = parse_gate_output("lint-imports", output, exit_code=0)
        assert result.passed is True

    def test_empty_stdout_is_blocked(self) -> None:
        """Empty lint-imports stdout → halt."""
        result = parse_gate_output("lint-imports", "", exit_code=0)
        assert result.blocked is True

    def test_no_footer_is_blocked(self) -> None:
        """lint-imports stdout without `Contracts kept` → halt."""
        output = "Layer violation: ai_workflows.graph imports ai_workflows.surfaces\n"
        result = parse_gate_output("lint-imports", output, exit_code=1)
        assert result.blocked is True

    def test_nonzero_exit_is_blocked(self) -> None:
        """lint-imports non-zero exit → halt."""
        output = "Contracts kept\n"  # footer present but exit wrong
        result = parse_gate_output("lint-imports", output, exit_code=1)
        assert result.blocked is True
        assert "exit code 1" in result.reason


class TestUnknownGate:
    """Unknown gate name is fail-closed."""

    def test_unknown_gate_name_is_blocked(self) -> None:
        """Gate with no registered footer pattern → blocked."""
        result = parse_gate_output("unknown-gate", "some output\n", exit_code=0)
        assert result.blocked is True
        assert "unknown gate" in result.reason


class TestBlockedMessage:
    """build_blocked_message produces the canonical 🚧 BLOCKED string."""

    def test_blocked_message_format(self) -> None:
        """Canonical BLOCKED message includes gate name, task, cycle."""
        msg = build_blocked_message("pytest", "m20_t08", 2)
        assert msg.startswith("🚧 BLOCKED: gate pytest output not parseable")
        assert "runs/m20_t08/cycle_2/gate_pytest.txt" in msg

    def test_blocked_message_lint_imports(self) -> None:
        """BLOCKED message for lint-imports uses correct filename."""
        msg = build_blocked_message("lint-imports", "m12_t01", 1)
        assert "gate_lint-imports.txt" in msg


# ---------------------------------------------------------------------------
# AC-3 smoke: gate_parse_patterns.md exists with per-gate regex entries
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parents[2]
_GATE_PATTERNS_FILE = _REPO_ROOT / ".claude" / "commands" / "_common" / "gate_parse_patterns.md"


class TestGateParsePatternsFile:
    """AC-3: gate_parse_patterns.md exists and contains the expected per-gate regex."""

    def test_file_exists(self) -> None:
        """gate_parse_patterns.md must exist at the canonical path."""
        assert _GATE_PATTERNS_FILE.exists(), (
            f"gate_parse_patterns.md not found at {_GATE_PATTERNS_FILE}"
        )

    def test_pytest_pattern_present(self) -> None:
        """File must document the pytest footer-line regex."""
        content = _GATE_PATTERNS_FILE.read_text()
        assert r"^=+ \d+ passed" in content

    def test_ruff_pattern_present(self) -> None:
        """File must document the ruff footer-line regex."""
        content = _GATE_PATTERNS_FILE.read_text()
        assert "All checks passed" in content

    def test_lint_imports_pattern_present(self) -> None:
        """File must document the lint-imports footer-line regex."""
        content = _GATE_PATTERNS_FILE.read_text()
        assert "Contracts kept" in content

    def test_halt_condition_described(self) -> None:
        """File must describe the BLOCKED halt condition."""
        content = _GATE_PATTERNS_FILE.read_text()
        assert "BLOCKED" in content
        assert "gate_<name>.txt" in content or "gate_<name>" in content
