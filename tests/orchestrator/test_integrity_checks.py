"""Task-integrity safeguard tests — non-empty diff, non-empty test diff, independent gate re-run.

Task: M20 Task 09 — Task-integrity safeguards (non-empty-diff + non-empty test-diff +
  independent pre-stamp gate re-run).
Relationship: Tests the integrity-check logic described in
  `.claude/commands/_common/integrity_checks.md` and referenced by the Pre-commit ceremony
  section in `.claude/commands/auto-implement.md`. The production checks are markdown-prose
  logic inside the orchestrator slash-command; this module provides a hermetic Python
  implementation so every check branch can be exercised without live git or pytest
  invocations.

Reuses `parse_gate_output` from the T08 module
(`tests/orchestrator/test_gate_output_capture.py`) to avoid duplicating the pytest-footer
regex. This mirrors the spec mandate: "Reuse T08's gate-parse infrastructure".

Per-AC coverage:
  AC-1 — auto-implement.md describes the pre-commit ceremony: structural grep in the
          TestAutoImplementCeremonyReference class below.
  AC-2 — integrity_checks.md exists: TestIntegrityChecksFileExists.
  AC-3 — Halt surfaces the specific failed check: verified in each IntegrityCheck test
          class by asserting the reason string contains the check identifier.
  AC-4 — test_integrity_checks.py passes (this file).
  AC-5 — CHANGELOG.md updated (in CHANGELOG).
  AC-6 — Status surfaces flipped (in spec + milestone README).
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Reuse T08's parse_gate_output — single source of truth for pytest-footer regex
# ---------------------------------------------------------------------------
from tests.orchestrator.test_gate_output_capture import parse_gate_output

# ---------------------------------------------------------------------------
# Integrity-check data structures
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parents[2]
_INTEGRITY_CHECKS_FILE = (
    _REPO_ROOT / ".claude" / "commands" / "_common" / "integrity_checks.md"
)
_AUTO_IMPLEMENT_FILE = _REPO_ROOT / ".claude" / "commands" / "auto-implement.md"


@dataclasses.dataclass
class IntegrityResult:
    """Result of running the three pre-commit integrity checks.

    Attributes:
        blocked: True iff any check failed and the commit ceremony must not proceed.
        check_id: Which check fired (1, 2, or 3); None when blocked is False.
        reason: Human-readable description of the failure; empty when blocked is False.
    """

    blocked: bool
    check_id: int | None = None
    reason: str = ""

    def __bool__(self) -> bool:  # pragma: no cover
        return not self.blocked


def _check1_nonempty_diff(diff_stat_output: str) -> IntegrityResult:
    """Check 1 — assert git diff --stat output is non-empty.

    Args:
        diff_stat_output: The stdout of `git diff --stat <pre>..HEAD`.

    Returns:
        IntegrityResult with blocked=False when output is non-empty.
    """
    if not diff_stat_output or not diff_stat_output.strip():
        return IntegrityResult(
            blocked=True,
            check_id=1,
            reason="check 1 (empty diff) failed",
        )
    return IntegrityResult(blocked=False)


def _check2_nonempty_test_diff(
    test_diff_stat_output: str,
    task_kind: str,
) -> IntegrityResult:
    """Check 2 — assert test diff is non-empty for code tasks.

    Args:
        test_diff_stat_output: The stdout of
            `git diff --stat <pre>..HEAD -- tests/`.
        task_kind: The value of the spec's ``**Kind:**`` line (e.g.
            ``"Safeguards / code"``), or the milestone README's
            "Phase / Kind" column value.  Compared case-insensitively
            against the word ``code``.

    Returns:
        IntegrityResult with blocked=False when the check passes or is bypassed.
    """
    # Bypass for non-code tasks
    if "code" not in task_kind.lower():
        return IntegrityResult(blocked=False)

    if not test_diff_stat_output or not test_diff_stat_output.strip():
        return IntegrityResult(
            blocked=True,
            check_id=2,
            reason="check 2 (empty test diff for code task) failed",
        )
    return IntegrityResult(blocked=False)


def _check3_pytest_rerun(pytest_output: str, exit_code: int) -> IntegrityResult:
    """Check 3 — independent pytest re-run; parse footer per T08.

    Reuses :func:`parse_gate_output` from ``test_gate_output_capture.py`` for the
    pytest-footer regex so the pattern is not duplicated.

    Args:
        pytest_output: The captured stdout + stderr of `uv run pytest -q`.
        exit_code: The exit code returned by the pytest process.

    Returns:
        IntegrityResult with blocked=False when pytest passes.
    """
    gate_result = parse_gate_output("pytest", pytest_output, exit_code)
    if gate_result.blocked:
        return IntegrityResult(
            blocked=True,
            check_id=3,
            reason=f"check 3 (pytest failure) failed: {gate_result.reason}",
        )
    return IntegrityResult(blocked=False)


def run_integrity_checks(
    diff_stat_output: str,
    test_diff_stat_output: str,
    task_kind: str,
    pytest_output: str,
    pytest_exit_code: int,
) -> IntegrityResult:
    """Run all three integrity checks in order; short-circuit on first failure.

    This is the Python mirror of the orchestrator's Pre-commit ceremony prose
    in `.claude/commands/auto-implement.md` §Pre-commit ceremony.

    Args:
        diff_stat_output: stdout of `git diff --stat <pre>..HEAD`.
        test_diff_stat_output: stdout of `git diff --stat <pre>..HEAD -- tests/`.
        task_kind: Kind string from the spec's ``**Kind:**`` line (or README fallback).
        pytest_output: Captured stdout + stderr of `uv run pytest -q`.
        pytest_exit_code: Exit code of the pytest process.

    Returns:
        IntegrityResult: blocked=False iff all applicable checks pass.
    """
    result = _check1_nonempty_diff(diff_stat_output)
    if result.blocked:
        return result

    result = _check2_nonempty_test_diff(test_diff_stat_output, task_kind)
    if result.blocked:
        return result

    return _check3_pytest_rerun(pytest_output, pytest_exit_code)


def build_integrity_blocked_message(check_id: int, task_shorthand: str) -> str:
    """Build the canonical BLOCKED halt message for a failed integrity check.

    Args:
        check_id: Which check fired (1, 2, or 3).
        task_shorthand: The task shorthand (e.g. ``"m20_t09"``).

    Returns:
        The canonical halt-message string.
    """
    check_names = {
        1: "empty diff",
        2: "empty test diff for code task",
        3: "pytest failure",
    }
    label = check_names.get(check_id, f"check {check_id}")
    return (
        f"🚧 BLOCKED: task-integrity check {check_id} ({label}) failed; "
        f"see runs/{task_shorthand}/integrity.txt"
    )


# ---------------------------------------------------------------------------
# Tests — five spec-named cases
# ---------------------------------------------------------------------------

_PASSING_PYTEST_OUTPUT = (
    "============================= test session starts ==============================\n"
    "collected 10 items\n"
    "\n"
    "tests/test_foo.py ..........                                             [100%]\n"
    "\n"
    "============================== 10 passed in 0.42s ==============================\n"
)

_FAILING_PYTEST_OUTPUT = (
    "============================= test session starts ==============================\n"
    "collected 15 items\n"
    "\n"
    "tests/test_foo.py .....FFFFF                                            [100%]\n"
    "\n"
    "=========================== 5 failed, 10 passed in 2.00s ===========================\n"
)

_NONEMPTY_PROD_DIFF = (
    " ai_workflows/primitives/storage.py | 12 +++++++-----\n"
    " 1 file changed, 7 insertions(+), 5 deletions(-)\n"
)

_NONEMPTY_TEST_DIFF = (
    " tests/primitives/test_storage.py | 8 ++++++++\n"
    " 1 file changed, 8 insertions(+)\n"
)


class TestCheck1EmptyDiff:
    """AC-3: Check 1 fires when git diff --stat output is empty."""

    def test_empty_diff_is_blocked(self) -> None:
        """Empty diff stat output → blocked=True, check_id=1."""
        result = run_integrity_checks(
            diff_stat_output="",
            test_diff_stat_output=_NONEMPTY_TEST_DIFF,
            task_kind="Safeguards / code",
            pytest_output=_PASSING_PYTEST_OUTPUT,
            pytest_exit_code=0,
        )
        assert result.blocked is True
        assert result.check_id == 1
        assert "check 1" in result.reason
        assert "empty diff" in result.reason

    def test_whitespace_only_diff_is_blocked(self) -> None:
        """Whitespace-only diff stat output is also treated as empty."""
        result = run_integrity_checks(
            diff_stat_output="   \n  \n",
            test_diff_stat_output=_NONEMPTY_TEST_DIFF,
            task_kind="Safeguards / code",
            pytest_output=_PASSING_PYTEST_OUTPUT,
            pytest_exit_code=0,
        )
        assert result.blocked is True
        assert result.check_id == 1

    def test_blocked_message_check1(self) -> None:
        """Canonical BLOCKED message names check 1."""
        msg = build_integrity_blocked_message(1, "m20_t09")
        assert "task-integrity check 1" in msg
        assert "empty diff" in msg
        assert "runs/m20_t09/integrity.txt" in msg
        assert msg.startswith("🚧 BLOCKED")


class TestCheck2EmptyTestDiff:
    """AC-3: Check 2 fires when test diff is empty for a code task."""

    def test_code_task_empty_test_diff_is_blocked(self) -> None:
        """Code task with non-empty prod diff but empty test diff → blocked=True, check_id=2."""
        result = run_integrity_checks(
            diff_stat_output=_NONEMPTY_PROD_DIFF,
            test_diff_stat_output="",
            task_kind="Safeguards / code",
            pytest_output=_PASSING_PYTEST_OUTPUT,
            pytest_exit_code=0,
        )
        assert result.blocked is True
        assert result.check_id == 2
        assert "check 2" in result.reason
        assert "empty test diff" in result.reason

    def test_code_task_whitespace_test_diff_is_blocked(self) -> None:
        """Whitespace-only test diff is also treated as empty for code tasks."""
        result = run_integrity_checks(
            diff_stat_output=_NONEMPTY_PROD_DIFF,
            test_diff_stat_output="\n  \n",
            task_kind="doc + code",
            pytest_output=_PASSING_PYTEST_OUTPUT,
            pytest_exit_code=0,
        )
        assert result.blocked is True
        assert result.check_id == 2

    def test_blocked_message_check2(self) -> None:
        """Canonical BLOCKED message names check 2."""
        msg = build_integrity_blocked_message(2, "m20_t09")
        assert "task-integrity check 2" in msg
        assert "empty test diff for code task" in msg
        assert "runs/m20_t09/integrity.txt" in msg

    def test_kind_containing_code_case_insensitive(self) -> None:
        """Kind comparison is case-insensitive: 'Code' also triggers Check 2."""
        result = run_integrity_checks(
            diff_stat_output=_NONEMPTY_PROD_DIFF,
            test_diff_stat_output="",
            task_kind="Model-tier / Code",
            pytest_output=_PASSING_PYTEST_OUTPUT,
            pytest_exit_code=0,
        )
        assert result.blocked is True
        assert result.check_id == 2


class TestCheck3PytestFailure:
    """AC-3: Check 3 fires when pytest output indicates failure."""

    def test_failing_pytest_is_blocked(self) -> None:
        """Non-empty diffs but failing pytest → blocked=True, check_id=3."""
        result = run_integrity_checks(
            diff_stat_output=_NONEMPTY_PROD_DIFF,
            test_diff_stat_output=_NONEMPTY_TEST_DIFF,
            task_kind="Safeguards / code",
            pytest_output=_FAILING_PYTEST_OUTPUT,
            pytest_exit_code=1,
        )
        assert result.blocked is True
        assert result.check_id == 3
        assert "check 3" in result.reason
        assert "pytest failure" in result.reason

    def test_nonzero_exit_is_blocked_even_with_pass_footer(self) -> None:
        """Non-zero pytest exit code blocks even if a passing footer is present."""
        # This exercises T08's fail-closed exit-code path via the shared parser
        output = (
            "============================= test session starts ==============================\n"
            "============================== 5 passed in 0.10s ==============================\n"
        )
        result = run_integrity_checks(
            diff_stat_output=_NONEMPTY_PROD_DIFF,
            test_diff_stat_output=_NONEMPTY_TEST_DIFF,
            task_kind="Safeguards / code",
            pytest_output=output,
            pytest_exit_code=1,
        )
        assert result.blocked is True
        assert result.check_id == 3

    def test_blocked_message_check3(self) -> None:
        """Canonical BLOCKED message names check 3."""
        msg = build_integrity_blocked_message(3, "m20_t09")
        assert "task-integrity check 3" in msg
        assert "pytest failure" in msg
        assert "runs/m20_t09/integrity.txt" in msg


class TestDocOnlyBypass:
    """AC-3: Check 2 is bypassed for doc-only tasks."""

    def test_doc_only_task_empty_test_diff_is_not_blocked(self) -> None:
        """Doc-only task with empty test diff → no halt (Check 2 bypassed)."""
        result = run_integrity_checks(
            diff_stat_output=_NONEMPTY_PROD_DIFF,
            test_diff_stat_output="",
            task_kind="Compaction / doc",
            pytest_output=_PASSING_PYTEST_OUTPUT,
            pytest_exit_code=0,
        )
        assert result.blocked is False

    def test_analysis_only_task_bypasses_check2(self) -> None:
        """Analysis-only task kind → Check 2 bypassed."""
        result = run_integrity_checks(
            diff_stat_output=_NONEMPTY_PROD_DIFF,
            test_diff_stat_output="",
            task_kind="Model-tier / analysis",
            pytest_output=_PASSING_PYTEST_OUTPUT,
            pytest_exit_code=0,
        )
        assert result.blocked is False

    def test_doc_plus_analysis_task_bypasses_check2(self) -> None:
        """'doc + analysis' task kind → Check 2 bypassed (no 'code' word)."""
        result = run_integrity_checks(
            diff_stat_output=_NONEMPTY_PROD_DIFF,
            test_diff_stat_output="",
            task_kind="Closeout / doc + analysis",
            pytest_output=_PASSING_PYTEST_OUTPUT,
            pytest_exit_code=0,
        )
        assert result.blocked is False


class TestAllChecksPass:
    """AC-3: When all three checks pass, no halt fires."""

    def test_all_pass_returns_not_blocked(self) -> None:
        """Non-empty diff, non-empty test diff, passing pytest → blocked=False."""
        result = run_integrity_checks(
            diff_stat_output=_NONEMPTY_PROD_DIFF,
            test_diff_stat_output=_NONEMPTY_TEST_DIFF,
            task_kind="Safeguards / code",
            pytest_output=_PASSING_PYTEST_OUTPUT,
            pytest_exit_code=0,
        )
        assert result.blocked is False
        assert result.check_id is None
        assert result.reason == ""

    def test_all_pass_doc_task_returns_not_blocked(self) -> None:
        """Doc task: non-empty diff, no test diff, passing pytest → blocked=False."""
        result = run_integrity_checks(
            diff_stat_output=_NONEMPTY_PROD_DIFF,
            test_diff_stat_output="",
            task_kind="Compaction / doc",
            pytest_output=_PASSING_PYTEST_OUTPUT,
            pytest_exit_code=0,
        )
        assert result.blocked is False

    def test_check1_short_circuits_before_check2(self) -> None:
        """Empty diff short-circuits; check_id is 1 even if test diff is also empty."""
        result = run_integrity_checks(
            diff_stat_output="",
            test_diff_stat_output="",
            task_kind="Safeguards / code",
            pytest_output=_PASSING_PYTEST_OUTPUT,
            pytest_exit_code=0,
        )
        assert result.blocked is True
        assert result.check_id == 1  # short-circuit: check 2 never ran

    def test_check2_short_circuits_before_check3(self) -> None:
        """Empty test diff short-circuits; check_id is 2 even if pytest would also fail."""
        result = run_integrity_checks(
            diff_stat_output=_NONEMPTY_PROD_DIFF,
            test_diff_stat_output="",
            task_kind="Safeguards / code",
            pytest_output=_FAILING_PYTEST_OUTPUT,
            pytest_exit_code=1,
        )
        assert result.blocked is True
        assert result.check_id == 2  # short-circuit: check 3 never ran


class TestIndividualChecks:
    """Unit tests for each individual check function."""

    def test_check1_nonempty_passes(self) -> None:
        """Non-empty diff stat output passes Check 1."""
        result = _check1_nonempty_diff(_NONEMPTY_PROD_DIFF)
        assert result.blocked is False

    def test_check1_empty_blocks(self) -> None:
        """Empty diff stat output blocks Check 1."""
        result = _check1_nonempty_diff("")
        assert result.blocked is True
        assert result.check_id == 1

    def test_check2_bypassed_for_non_code_task(self) -> None:
        """Check 2 returns not-blocked for a non-code task regardless of test diff."""
        result = _check2_nonempty_test_diff("", "analysis / doc")
        assert result.blocked is False

    def test_check2_blocks_code_task_with_empty_test_diff(self) -> None:
        """Check 2 blocks a code task with empty test diff."""
        result = _check2_nonempty_test_diff("", "Model-tier / code")
        assert result.blocked is True
        assert result.check_id == 2

    def test_check3_passes_with_valid_output(self) -> None:
        """Check 3 passes with valid pytest output and exit code 0."""
        result = _check3_pytest_rerun(_PASSING_PYTEST_OUTPUT, 0)
        assert result.blocked is False

    def test_check3_blocks_with_empty_output(self) -> None:
        """Check 3 blocks when pytest output is empty (reuses T08 fail-closed logic)."""
        result = _check3_pytest_rerun("", 0)
        assert result.blocked is True
        assert result.check_id == 3


# ---------------------------------------------------------------------------
# AC-2 smoke: integrity_checks.md exists and contains expected content
# ---------------------------------------------------------------------------


class TestIntegrityChecksFileExists:
    """AC-2: .claude/commands/_common/integrity_checks.md exists with expected content."""

    def test_file_exists(self) -> None:
        """integrity_checks.md must exist at the canonical path."""
        assert _INTEGRITY_CHECKS_FILE.exists(), (
            f"integrity_checks.md not found at {_INTEGRITY_CHECKS_FILE}"
        )

    def test_check1_described(self) -> None:
        """File must describe Check 1 (non-empty diff)."""
        content = _INTEGRITY_CHECKS_FILE.read_text()
        assert "Check 1" in content
        assert "non-empty diff" in content.lower() or "Non-empty diff" in content

    def test_check2_described(self) -> None:
        """File must describe Check 2 (non-empty test diff)."""
        content = _INTEGRITY_CHECKS_FILE.read_text()
        assert "Check 2" in content
        assert "test diff" in content.lower()

    def test_check3_described(self) -> None:
        """File must describe Check 3 (pytest re-run)."""
        content = _INTEGRITY_CHECKS_FILE.read_text()
        assert "Check 3" in content
        assert "pytest" in content.lower()

    def test_blocked_message_format_present(self) -> None:
        """File must show the 🚧 BLOCKED halt message format."""
        content = _INTEGRITY_CHECKS_FILE.read_text()
        assert "BLOCKED" in content
        assert "integrity.txt" in content

    def test_bypass_condition_described(self) -> None:
        """File must describe the doc-only bypass for Check 2."""
        content = _INTEGRITY_CHECKS_FILE.read_text()
        assert "doc" in content.lower()
        assert "bypass" in content.lower() or "skip" in content.lower()

    def test_gate_parse_patterns_reference_present(self) -> None:
        """File must reference gate_parse_patterns.md (T08 reuse)."""
        content = _INTEGRITY_CHECKS_FILE.read_text()
        assert "gate_parse_patterns.md" in content


# ---------------------------------------------------------------------------
# AC-1 smoke: auto-implement.md describes the pre-commit ceremony
# ---------------------------------------------------------------------------


class TestAutoImplementCeremonyReference:
    """AC-1: auto-implement.md describes the pre-commit ceremony with three checks."""

    def test_file_exists(self) -> None:
        """auto-implement.md must exist."""
        assert _AUTO_IMPLEMENT_FILE.exists()

    def test_pre_commit_ceremony_section_present(self) -> None:
        """auto-implement.md must describe the pre-commit ceremony."""
        content = _AUTO_IMPLEMENT_FILE.read_text()
        assert re.search(
            r"pre-commit ceremony|task-integrity|integrity_checks\.md",
            content,
            re.IGNORECASE,
        ), "auto-implement.md must reference the pre-commit ceremony or integrity_checks.md"

    def test_three_checks_described(self) -> None:
        """auto-implement.md must describe all three integrity checks."""
        content = _AUTO_IMPLEMENT_FILE.read_text()
        # Check 1 — non-empty diff
        assert re.search(r"git diff --stat", content), "Check 1 git diff --stat not found"
        # Check 2 — non-empty test diff
        assert re.search(r"tests/", content), "Check 2 tests/ path not found"
        # Check 3 — pytest re-run
        assert re.search(r"uv run pytest", content), "Check 3 pytest re-run not found"

    def test_blocked_message_format_present(self) -> None:
        """auto-implement.md must include the canonical BLOCKED message format."""
        content = _AUTO_IMPLEMENT_FILE.read_text()
        assert "task-integrity check" in content
        assert "integrity.txt" in content
