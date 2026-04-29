"""Tests for scripts/orchestration/auditor_rotation.py — rotation trigger logic.

Task: M20 Task 27 — Auditor input-volume threshold for cycle-rotation (client-side
  simulation of clear_tool_uses_20250919).
Relationship: Hermetic tests for the auditor_rotation helper.  Exercises the
  threshold-fire, threshold-no-fire, verdict-PASS, and tunability cases.
  No live agent spawns; all I/O is inside tmp_path.

ACs verified here:
- AC-5: tests/orchestrator/test_auditor_rotation_trigger.py passes — threshold-fire +
         threshold-no-fire + verdict-PASS + tunability cases.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixture: load the module
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def repo_root() -> Path:
    """Return the repository root path."""
    return Path(__file__).parent.parent.parent


@pytest.fixture(scope="module")
def rotation_mod(repo_root):
    """Load scripts/orchestration/auditor_rotation.py as a module.

    scope="module" — the helper has no mutable global state; loading once per
    file avoids 29 redundant importlib.exec_module calls (A-1 fix per sr-sdet).
    """
    mod_path = repo_root / "scripts" / "orchestration" / "auditor_rotation.py"
    spec = importlib.util.spec_from_file_location("auditor_rotation", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# should_rotate — threshold-fire cases (input_tokens >= threshold AND verdict OPEN)
# ---------------------------------------------------------------------------

class TestShouldRotateThresholdFire:
    """Verify rotation fires at or above the threshold when verdict is OPEN."""

    def test_exactly_at_threshold_open(self, rotation_mod):
        """input_tokens == threshold AND verdict OPEN → rotate."""
        result = rotation_mod.should_rotate(
            {"input_tokens": 60_000, "verdict": "OPEN"},
            threshold=60_000,
        )
        assert result is True

    def test_above_threshold_open(self, rotation_mod):
        """input_tokens > threshold AND verdict OPEN → rotate."""
        result = rotation_mod.should_rotate(
            {"input_tokens": 75_000, "verdict": "OPEN"},
            threshold=60_000,
        )
        assert result is True

    def test_far_above_threshold_open(self, rotation_mod):
        """Very high input_tokens AND verdict OPEN → rotate."""
        result = rotation_mod.should_rotate(
            {"input_tokens": 200_000, "verdict": "OPEN"},
            threshold=60_000,
        )
        assert result is True

    def test_open_verdict_case_insensitive_lower(self, rotation_mod):
        """Lowercase 'open' verdict is normalised to OPEN and triggers rotation."""
        result = rotation_mod.should_rotate(
            {"input_tokens": 65_000, "verdict": "open"},
            threshold=60_000,
        )
        assert result is True


# ---------------------------------------------------------------------------
# should_rotate — threshold-no-fire cases (input_tokens < threshold)
# ---------------------------------------------------------------------------

class TestShouldRotateThresholdNoFire:
    """Verify rotation does NOT fire when input_tokens is below the threshold."""

    def test_below_threshold_open(self, rotation_mod):
        """input_tokens < threshold AND verdict OPEN → no rotate."""
        result = rotation_mod.should_rotate(
            {"input_tokens": 30_000, "verdict": "OPEN"},
            threshold=60_000,
        )
        assert result is False

    def test_one_below_threshold_open(self, rotation_mod):
        """input_tokens = threshold - 1 AND verdict OPEN → no rotate."""
        result = rotation_mod.should_rotate(
            {"input_tokens": 59_999, "verdict": "OPEN"},
            threshold=60_000,
        )
        assert result is False

    def test_zero_tokens_open(self, rotation_mod):
        """input_tokens == 0 AND verdict OPEN → no rotate."""
        result = rotation_mod.should_rotate(
            {"input_tokens": 0, "verdict": "OPEN"},
            threshold=60_000,
        )
        assert result is False


# ---------------------------------------------------------------------------
# should_rotate — verdict-PASS cases (loop ends, no rotation needed)
# ---------------------------------------------------------------------------

class TestShouldRotateVerdictPass:
    """Verify rotation never fires when verdict is PASS (loop ends)."""

    def test_pass_above_threshold(self, rotation_mod):
        """input_tokens >= threshold AND verdict PASS → no rotate (loop ends)."""
        result = rotation_mod.should_rotate(
            {"input_tokens": 65_000, "verdict": "PASS"},
            threshold=60_000,
        )
        assert result is False

    def test_pass_exactly_at_threshold(self, rotation_mod):
        """input_tokens == threshold AND verdict PASS → no rotate."""
        result = rotation_mod.should_rotate(
            {"input_tokens": 60_000, "verdict": "PASS"},
            threshold=60_000,
        )
        assert result is False

    def test_pass_below_threshold(self, rotation_mod):
        """input_tokens < threshold AND verdict PASS → no rotate."""
        result = rotation_mod.should_rotate(
            {"input_tokens": 10_000, "verdict": "PASS"},
            threshold=60_000,
        )
        assert result is False

    def test_pass_verdict_case_insensitive(self, rotation_mod):
        """Lowercase 'pass' is normalised; no rotation even at high token count."""
        result = rotation_mod.should_rotate(
            {"input_tokens": 100_000, "verdict": "pass"},
            threshold=60_000,
        )
        assert result is False


# ---------------------------------------------------------------------------
# should_rotate — verdict-BLOCKED cases (user-action required, no rotation)
# ---------------------------------------------------------------------------

class TestShouldRotateVerdictBlocked:
    """Verify rotation never fires when verdict is BLOCKED."""

    def test_blocked_above_threshold(self, rotation_mod):
        """BLOCKED verdict → no rotate regardless of token count."""
        result = rotation_mod.should_rotate(
            {"input_tokens": 80_000, "verdict": "BLOCKED"},
            threshold=60_000,
        )
        assert result is False


# ---------------------------------------------------------------------------
# should_rotate — tunability via threshold parameter
# ---------------------------------------------------------------------------

class TestShouldRotateTunability:
    """Verify the threshold parameter overrides the default 60K."""

    def test_custom_threshold_lower_fires(self, rotation_mod):
        """Custom threshold 40K → fires at 45K input_tokens."""
        result = rotation_mod.should_rotate(
            {"input_tokens": 45_000, "verdict": "OPEN"},
            threshold=40_000,
        )
        assert result is True

    def test_custom_threshold_lower_no_fire_below(self, rotation_mod):
        """Custom threshold 40K → no fire at 39K input_tokens."""
        result = rotation_mod.should_rotate(
            {"input_tokens": 39_000, "verdict": "OPEN"},
            threshold=40_000,
        )
        assert result is False

    def test_custom_threshold_higher_no_fire(self, rotation_mod):
        """Custom threshold 80K → no fire at 65K (would fire at default 60K)."""
        result = rotation_mod.should_rotate(
            {"input_tokens": 65_000, "verdict": "OPEN"},
            threshold=80_000,
        )
        assert result is False

    def test_custom_threshold_exactly_at(self, rotation_mod):
        """Custom threshold 40K → fires at exactly 40K."""
        result = rotation_mod.should_rotate(
            {"input_tokens": 40_000, "verdict": "OPEN"},
            threshold=40_000,
        )
        assert result is True


# ---------------------------------------------------------------------------
# get_threshold — env var override
# ---------------------------------------------------------------------------

class TestGetThreshold:
    """Verify get_threshold() reads AIW_AUDITOR_ROTATION_THRESHOLD from env."""

    def test_default_when_env_unset(self, rotation_mod, monkeypatch):
        """No env var → default 60000."""
        monkeypatch.delenv("AIW_AUDITOR_ROTATION_THRESHOLD", raising=False)
        assert rotation_mod.get_threshold() == 60_000

    def test_reads_env_var(self, rotation_mod, monkeypatch):
        """Env var set to 40000 → returns 40000."""
        monkeypatch.setenv("AIW_AUDITOR_ROTATION_THRESHOLD", "40000")
        assert rotation_mod.get_threshold() == 40_000

    def test_non_integer_env_falls_back(self, rotation_mod, monkeypatch):
        """Non-integer env var → falls back to default 60000."""
        monkeypatch.setenv("AIW_AUDITOR_ROTATION_THRESHOLD", "not-a-number")
        assert rotation_mod.get_threshold() == 60_000

    def test_integration_env_var_lowers_trigger(self, rotation_mod, monkeypatch):
        """AIW_AUDITOR_ROTATION_THRESHOLD=40000 → trigger fires at 45000."""
        monkeypatch.setenv("AIW_AUDITOR_ROTATION_THRESHOLD", "40000")
        threshold = rotation_mod.get_threshold()
        result = rotation_mod.should_rotate(
            {"input_tokens": 45_000, "verdict": "OPEN"},
            threshold=threshold,
        )
        assert result is True

    # --- F-1 boundary cases (sr-sdet cycle-2 fix) ---

    def test_negative_one_falls_back_to_default(self, rotation_mod, monkeypatch):
        """AIW_AUDITOR_ROTATION_THRESHOLD=-1 → falls back to 60000.

        str.isdigit() returns False for negative integers; -1 is documented as not
        a valid "disable rotation" sentinel. Users who want to suppress rotation
        should set the threshold to a large value (e.g. 2000000).
        """
        monkeypatch.setenv("AIW_AUDITOR_ROTATION_THRESHOLD", "-1")
        assert rotation_mod.get_threshold() == 60_000

    def test_zero_falls_back_to_default(self, rotation_mod, monkeypatch):
        """AIW_AUDITOR_ROTATION_THRESHOLD=0 → falls back to 60000.

        Zero would cause every OPEN cycle to rotate (runaway behaviour).
        The guard ``int(stripped) > 0`` prevents accepting zero.
        """
        monkeypatch.setenv("AIW_AUDITOR_ROTATION_THRESHOLD", "0")
        assert rotation_mod.get_threshold() == 60_000

    def test_float_string_falls_back_to_default(self, rotation_mod, monkeypatch):
        """AIW_AUDITOR_ROTATION_THRESHOLD=60000.0 → falls back to 60000.

        Float-formatted strings fail str.isdigit(); only pure positive integer
        strings are accepted. Documented limitation.
        """
        monkeypatch.setenv("AIW_AUDITOR_ROTATION_THRESHOLD", "60000.0")
        assert rotation_mod.get_threshold() == 60_000


# ---------------------------------------------------------------------------
# write_rotation_log — one-line record written correctly
# ---------------------------------------------------------------------------

class TestWriteRotationLog:
    """Verify the rotation log file is written with the correct format."""

    def test_creates_file(self, rotation_mod, tmp_path):
        """write_rotation_log creates runs/<task>/cycle_N/auditor_rotation.txt."""
        log_path = rotation_mod.write_rotation_log(
            "m20_t27", cycle_n=3, input_tokens=65_000, runs_root=tmp_path
        )
        assert log_path.exists()

    def test_file_content_format(self, rotation_mod, tmp_path):
        """Rotation log contains ROTATED: prefix and cycle numbers."""
        log_path = rotation_mod.write_rotation_log(
            "m20_t27", cycle_n=3, input_tokens=65_000, runs_root=tmp_path
        )
        content = log_path.read_text()
        assert "ROTATED:" in content
        assert "cycle 3" in content
        assert "input_tokens=65000" in content
        assert "cycle 4" in content
        assert "compacted" in content

    def test_file_path_convention(self, rotation_mod, tmp_path):
        """Log path follows runs/<task>/cycle_<N>/auditor_rotation.txt convention."""
        log_path = rotation_mod.write_rotation_log(
            "m20_t27", cycle_n=2, input_tokens=70_000, runs_root=tmp_path
        )
        expected = tmp_path / "m20_t27" / "cycle_2" / "auditor_rotation.txt"
        assert log_path == expected

    def test_creates_parent_directories(self, rotation_mod, tmp_path):
        """write_rotation_log creates the cycle directory if it does not exist."""
        log_path = rotation_mod.write_rotation_log(
            "m20_t99", cycle_n=5, input_tokens=80_000, runs_root=tmp_path
        )
        assert log_path.parent.exists()


# ---------------------------------------------------------------------------
# build_compacted_auditor_spawn_input — shape of the compacted input
# ---------------------------------------------------------------------------

class TestBuildCompactedAuditorSpawnInput:
    """Verify the compacted spawn input contains the right sections."""

    def test_contains_spec_path(self, rotation_mod):
        """Compacted input includes task spec path."""
        prompt = rotation_mod.build_compacted_auditor_spawn_input(
            task_spec_path="design_docs/phases/m20/task_27.md",
            issue_file_path="design_docs/phases/m20/issues/task_27_issue.md",
            project_context_brief="Project: ai-workflows",
            git_diff="diff --git a/foo.py b/foo.py",
            cycle_summary_path="runs/m20_t27/cycle_1/summary.md",
            cycle_summary_content="# Cycle 1 summary",
        )
        assert "task_27.md" in prompt

    def test_contains_diff(self, rotation_mod):
        """Compacted input includes the current git diff."""
        prompt = rotation_mod.build_compacted_auditor_spawn_input(
            task_spec_path="spec.md",
            issue_file_path="issue.md",
            project_context_brief="brief",
            git_diff="diff --git a/foo.py",
            cycle_summary_path="runs/cycle_1/summary.md",
            cycle_summary_content="# Cycle 1",
        )
        assert "diff --git a/foo.py" in prompt

    def test_contains_cycle_summary(self, rotation_mod):
        """Compacted input includes the cycle summary content."""
        prompt = rotation_mod.build_compacted_auditor_spawn_input(
            task_spec_path="spec.md",
            issue_file_path="issue.md",
            project_context_brief="brief",
            git_diff="",
            cycle_summary_path="runs/cycle_1/summary.md",
            cycle_summary_content="## What changed this cycle: foo",
        )
        assert "What changed this cycle" in prompt

    def test_rotation_note_present(self, rotation_mod):
        """Compacted input includes a T27 rotation note."""
        prompt = rotation_mod.build_compacted_auditor_spawn_input(
            task_spec_path="spec.md",
            issue_file_path="issue.md",
            project_context_brief="brief",
            git_diff="",
            cycle_summary_path="runs/cycle_1/summary.md",
            cycle_summary_content="",
        )
        assert "T27 rotation" in prompt or "compacted" in prompt

    def test_no_duplication_of_cycle_summary_content(self, rotation_mod):
        """Cycle-summary content appears exactly once — no double-injection.

        F-2 fix (sr-sdet cycle-2): the previous test asserted the absence of strings
        the function is architecturally incapable of introducing (stateless formatter),
        which is a trivially-passing negative assertion.  This replacement passes
        realistic prior-Auditor-verdict text as cycle_summary_content and verifies the
        function does not duplicate it in the output — the actual "no double-injection"
        invariant the spec targets (prior tool-result content excluded).
        """
        prior_content = (
            "Prior Builder report: <content redacted>\n"
            "Prior Auditor verdict: PASS — all ACs green\n"
        )
        prompt = rotation_mod.build_compacted_auditor_spawn_input(
            task_spec_path="spec.md",
            issue_file_path="issue.md",
            project_context_brief="brief",
            git_diff="",
            cycle_summary_path="runs/cycle_1/summary.md",
            cycle_summary_content=prior_content,
        )
        # The prior_content must appear exactly once — no accidental duplication.
        assert prompt.count("Prior Auditor verdict: PASS") == 1, (
            "cycle_summary_content was injected more than once into the compacted prompt"
        )
